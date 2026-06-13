"""
Scheduler — планировщик занятий.

Каждые POLL_INTERVAL секунд запрашивает из БД занятия со статусом SCHEDULED,
у которых scheduled_at ∈ [now - launch_offset, now + launch_offset].
Для каждого такого занятия запускает LessonRunner в отдельной asyncio-задаче.

Параллельно:
  - следит за «пропущенными» уроками (ученик не пришёл)
  - ограничивает количество одновременных сессий
  - не запускает одно занятие дважды
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))

from sqlalchemy.orm import joinedload

from src.bot_db import get_session
from src.models.lesson import Lesson, LessonStatus
from src.orchestrator.runner import LessonRunner
from config.settings import config

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        # Множество id уроков, для которых уже запущена задача
        self._running: dict[UUID, asyncio.Task] = {}

    # ──────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        """Главный цикл — работает до отмены."""
        logger.info(
            "Scheduler запущен. poll_interval=%ds, launch_offset=%ds, missed_timeout=%ds",
            config.poll_interval,
            config.launch_offset,
            config.missed_timeout,
        )
        while True:
            try:
                await self._tick()
            except Exception:
                logger.exception("Ошибка в tick()")
            await asyncio.sleep(config.poll_interval)

    # ──────────────────────────────────────────────────────────────────────
    # Один «тик» планировщика
    # ──────────────────────────────────────────────────────────────────────

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)

        # Убрать завершённые задачи
        self._cleanup_finished_tasks()

        with get_session() as db:
            # 1. Пометить пропущенные занятия
            self._mark_missed(db, now)

            # 2. Найти занятия, которые пора запускать
            lessons_to_start = self._fetch_upcoming(db, now)

        if lessons_to_start:
            logger.info("Найдено занятий к запуску: %d", len(lessons_to_start))

        for lesson in lessons_to_start:
            if len(self._running) >= config.max_concurrent_sessions:
                logger.warning(
                    "Достигнут лимит одновременных сессий (%d). "
                    "Занятие %s отложено до следующего тика.",
                    config.max_concurrent_sessions,
                    lesson.id,
                )
                break
            self._launch(lesson)

    # ──────────────────────────────────────────────────────────────────────
    # Поиск занятий в БД
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_upcoming(self, db, now: datetime) -> list[Lesson]:
        """
        Занятия, которые нужно запустить прямо сейчас.
        Окно: [now - launch_offset, now + launch_offset].
        Исключаем те, для которых уже запущена задача.
        """
        window_start = now - timedelta(seconds=config.launch_offset)
        window_end = now + timedelta(seconds=config.launch_offset)

        lessons: list[Lesson] = (
            db.query(Lesson)
            .options(
                joinedload(Lesson.teacher),
                joinedload(Lesson.student),
                joinedload(Lesson.topic),
            )
            .filter(
                Lesson.status == LessonStatus.SCHEDULED,
                Lesson.scheduled_at >= window_start,
                Lesson.scheduled_at <= window_end,
            )
            .order_by(Lesson.scheduled_at)
            .all()
        )

        # Исключаем уже запущенные
        return [l for l in lessons if l.id not in self._running]

    def _mark_missed(self, db, now: datetime) -> None:
        """
        Занятия, которые опоздали больше чем на missed_timeout, и для которых
        ни одна сессия не была создана — помечаем как MISSED.
        Также обрабатываем зависшие сессии (IN_PROGRESS без активного runner).
        """
        from src.models.session import LessonSession, SessionStatus

        cutoff = now - timedelta(seconds=config.missed_timeout)
        missed: list[Lesson] = (
            db.query(Lesson)
            .outerjoin(Lesson.session)
            .filter(
                Lesson.status == LessonStatus.SCHEDULED,
                Lesson.scheduled_at < cutoff,
                Lesson.session == None,  # noqa: E711
            )
            .all()
        )
        if missed:
            for lesson in missed:
                lesson.status = LessonStatus.MISSED
                logger.warning(
                    "Занятие %s (ученик %s, %s) помечено как MISSED",
                    lesson.id,
                    lesson.student.full_name if lesson.student else "—",
                    lesson.scheduled_at.isoformat(),
                )
            db.commit()

        # Cleanup stuck IN_PROGRESS sessions that have no active runner
        stuck_timeout = now - timedelta(seconds=config.missed_timeout * 2)
        stuck_sessions: list[LessonSession] = (
            db.query(LessonSession)
            .join(Lesson)
            .filter(
                LessonSession.status.in_([SessionStatus.STARTING, SessionStatus.ACTIVE]),
                LessonSession.bot_joined_at < stuck_timeout,
            )
            .all()
        )
        for session in stuck_sessions:
            if session.lesson_id not in self._running:
                logger.warning(
                    "Зависшая сессия %s (урок %s) — помечаем как FAILED",
                    session.id, session.lesson_id,
                )
                session.status = SessionStatus.FAILED
                session.error_message = "Session timed out (no active runner)"
                if session.lesson:
                    session.lesson.status = LessonStatus.CANCELLED
            db.commit()

    # ──────────────────────────────────────────────────────────────────────
    # Запуск и управление задачами
    # ──────────────────────────────────────────────────────────────────────

    def _launch(self, lesson: Lesson) -> None:
        """Запустить LessonRunner в отдельной asyncio-задаче."""
        lesson_id = lesson.id
        logger.info(
            "▶ Запуск урока %s | Ученик: %s | Тема: %s | %s",
            lesson_id,
            lesson.student.full_name if lesson.student else "—",
            lesson.topic.name if lesson.topic else "—",
            lesson.scheduled_at.isoformat(),
        )

        async def _run_with_own_session():
            # Каждый runner работает со своей сессией БД
            with get_session() as db:
                # Перечитать занятие в этой сессии
                fresh_lesson = (
                    db.query(Lesson)
                    .options(
                        joinedload(Lesson.teacher),
                        joinedload(Lesson.student),
                        joinedload(Lesson.topic),
                    )
                    .filter(Lesson.id == lesson_id)
                    .first()
                )
                if not fresh_lesson:
                    logger.error("Занятие %s не найдено при запуске", lesson_id)
                    return
                runner = LessonRunner(fresh_lesson, db)
                await runner.run()

        task = asyncio.create_task(
            _run_with_own_session(),
            name=f"lesson-{lesson_id}",
        )
        task.add_done_callback(lambda t: self._on_task_done(lesson_id, t))
        self._running[lesson_id] = task

    def _on_task_done(self, lesson_id: UUID, task: asyncio.Task) -> None:
        self._running.pop(lesson_id, None)
        if task.cancelled():
            logger.info("Задача урока %s отменена", lesson_id)
        elif task.exception():
            logger.error("Задача урока %s завершилась с ошибкой: %s", lesson_id, task.exception())
        else:
            logger.info("✓ Задача урока %s завершена успешно", lesson_id)

    def _cleanup_finished_tasks(self) -> None:
        done = [lid for lid, t in self._running.items() if t.done()]
        for lid in done:
            self._running.pop(lid, None)

    # ──────────────────────────────────────────────────────────────────────
    # Graceful shutdown
    # ──────────────────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Отменить все активные сессии и дождаться их завершения."""
        if not self._running:
            return
        logger.info("Завершение работы: отменяем %d активных сессий...", len(self._running))
        for task in self._running.values():
            task.cancel()
        await asyncio.gather(*self._running.values(), return_exceptions=True)
        logger.info("Все сессии завершены")
