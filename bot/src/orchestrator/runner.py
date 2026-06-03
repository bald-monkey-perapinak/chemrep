"""
LessonRunner — управляет одним активным уроком.

Жизненный цикл:
  1. prepare()  — загрузить данные из БД (тема, сценарий, файлы)
  2. run()      — подключиться к конференции, вести урок по шагам
  3. finish()   — отключиться, сохранить транскрипт, обновить статус

Каждый шаг сценария:
  - бот синтезирует текст в речь (TTS, заглушка)
  - отправляет аудио в конференцию
  - слушает ответ ученика (ASR, заглушка)
  - логирует в LessonSession.dialog_history и event_log
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))

from sqlalchemy.orm import Session

from src.models.lesson import Lesson, LessonStatus
from src.models.session import LessonSession, SessionStatus
from src.vcs.client import make_vcs_client, VCSConnectionInfo, VCSPlatformType

logger = logging.getLogger(__name__)

# Сколько секунд «говорить» один шаг сценария в заглушке
STEP_SPEAK_DELAY = 2.0
# Сколько секунд «слушать» ответ ученика
LISTEN_DELAY = 3.0


class LessonRunner:
    def __init__(self, lesson: Lesson, db: Session):
        self.lesson = lesson
        self.db = db
        self.session: LessonSession | None = None
        self._vcs = None
        self._dialog: list[dict] = []
        self._events: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Главный метод — запускает полный цикл урока."""
        try:
            await self._prepare()
            await self._connect_vcs()
            await self._conduct_lesson()
        except asyncio.CancelledError:
            logger.warning("[runner %s] Задача отменена", self.lesson.id)
            await self._mark_failed("Задача отменена оркестратором")
            raise
        except Exception as exc:
            logger.exception("[runner %s] Необработанная ошибка: %s", self.lesson.id, exc)
            await self._mark_failed(str(exc))
        finally:
            await self._cleanup()

    # ──────────────────────────────────────────────────────────────────────
    # Внутренние этапы
    # ──────────────────────────────────────────────────────────────────────

    async def _prepare(self) -> None:
        """Создать или восстановить LessonSession, загрузить сценарий."""
        lesson = self.lesson

        # Убедиться, что урок ещё в статусе SCHEDULED
        if lesson.status not in (LessonStatus.SCHEDULED,):
            raise RuntimeError(f"Урок {lesson.id} уже в статусе {lesson.status}")

        # Создать сессию
        self.session = LessonSession(
            lesson_id=lesson.id,
            status=SessionStatus.STARTING,
            total_steps=len(lesson.topic.lesson_script or []) if lesson.topic else 0,
            dialog_history=[],
            event_log=[],
        )
        self.db.add(self.session)

        # Перевести урок в IN_PROGRESS
        lesson.status = LessonStatus.IN_PROGRESS
        lesson.started_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(
            "[runner %s] Подготовка завершена. Тема: %s, шагов: %d",
            lesson.id,
            lesson.topic.name if lesson.topic else "—",
            self.session.total_steps,
        )

    async def _connect_vcs(self) -> None:
        """Подключиться к конференции."""
        lesson = self.lesson
        info = VCSConnectionInfo(
            platform=VCSPlatformType(lesson.vcs_platform.value),
            link=lesson.vcs_link or "",
            display_name=f"Помощник — {lesson.teacher.full_name}",
        )
        self._vcs = make_vcs_client(info)
        await self._vcs.connect()

        self.session.status = SessionStatus.ACTIVE
        self.session.bot_joined_at = datetime.now(timezone.utc)
        self.db.commit()

        self._log_event("bot_joined", {"link": lesson.vcs_link})
        logger.info("[runner %s] Бот подключился к конференции", lesson.id)

    async def _conduct_lesson(self) -> None:
        """Основной цикл — проход по шагам сценария."""
        lesson = self.lesson
        script = (lesson.topic.lesson_script or []) if lesson.topic else []

        if not script:
            # Нет сценария — простое приветствие
            await self._speak(
                f"Здравствуйте! Сегодня у нас занятие по теме «{lesson.topic.name if lesson.topic else 'химии'}». "
                "Сценарий урока ещё не добавлен. Преподаватель скоро подключится."
            )
            await asyncio.sleep(5)
        else:
            # Приветствие
            student_name = lesson.student.full_name.split()[0] if lesson.student else "ученик"
            await self._speak(
                f"Здравствуйте, {student_name}! Сегодня мы разберём тему «{lesson.topic.name}». Начнём."
            )
            await asyncio.sleep(1)

            # Шаги сценария
            for i, step in enumerate(script):
                self.session.current_step = i + 1
                self.db.commit()

                text = step.get("text", "")
                miro_action = step.get("miro_action")

                logger.info("[runner %s] Шаг %d/%d", lesson.id, i + 1, len(script))

                # Действие на доске Miro
                if miro_action:
                    self._log_event("miro_action", {"action": miro_action, "step": i + 1})
                    logger.debug("[runner %s] Miro: %s", lesson.id, miro_action)
                    # TODO: вызов реального Miro-клиента

                # Произнести текст
                await self._speak(text)

                # Пауза — «слушаем» ученика
                await self._listen(timeout=LISTEN_DELAY)

            # Завершение
            await self._speak(
                "На этом наш урок заканчивается. Домашнее задание придёт вам на почту. До свидания!"
            )

        self.session.status = SessionStatus.FINISHING
        self.db.commit()
        logger.info("[runner %s] Урок завершён нормально", lesson.id)

    async def _cleanup(self) -> None:
        """Отключиться, сохранить результаты."""
        now = datetime.now(timezone.utc)

        # Отключиться от конференции
        if self._vcs and self._vcs.connected:
            try:
                await self._vcs.disconnect()
            except Exception as e:
                logger.warning("[runner %s] Ошибка при отключении VCS: %s", self.lesson.id, e)

        # Финализировать сессию и урок
        if self.session:
            if self.session.status not in (SessionStatus.FAILED,):
                self.session.status = SessionStatus.ENDED
            self.session.bot_left_at = now
            self.session.dialog_history = self._dialog
            self.session.event_log = self._events

        lesson = self.lesson
        if lesson.status == LessonStatus.IN_PROGRESS:
            lesson.status = LessonStatus.COMPLETED
        lesson.finished_at = now
        lesson.transcript = self._build_transcript()

        try:
            self.db.commit()
        except Exception as e:
            logger.error("[runner %s] Ошибка при сохранении результатов: %s", lesson.id, e)

        logger.info("[runner %s] Очистка завершена. Статус: %s", lesson.id, lesson.status)

    # ──────────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ──────────────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """TTS + отправка аудио в конференцию (сейчас — заглушка)."""
        logger.info("[runner %s] 🔊 %s", self.lesson.id, text[:80])
        self._dialog.append({
            "role": "bot",
            "text": text,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        # TODO: синтезировать текст через TTS (ElevenLabs / Silero)
        # pcm = await tts_client.synthesize(text)
        # await self._vcs.send_audio(pcm)
        await asyncio.sleep(STEP_SPEAK_DELAY)  # эмулируем длительность речи

    async def _listen(self, timeout: float = 5.0) -> str:
        """ASR — слушаем ответ ученика (сейчас — заглушка)."""
        # TODO: recv_audio + whisper/faster-whisper
        await asyncio.sleep(timeout)
        text = ""
        if text:
            self._dialog.append({
                "role": "student",
                "text": text,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        return text

    def _log_event(self, kind: str, data: dict) -> None:
        self._events.append({
            "kind": kind,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    def _build_transcript(self) -> str:
        lines = []
        for m in self._dialog:
            role = "Бот" if m["role"] == "bot" else "Ученик"
            lines.append(f"[{m['ts']}] {role}: {m['text']}")
        return "\n".join(lines)

    async def _mark_failed(self, reason: str) -> None:
        if self.session:
            self.session.status = SessionStatus.FAILED
            self.session.error_message = reason
        self.lesson.status = LessonStatus.CANCELLED
        try:
            self.db.commit()
        except Exception:
            pass
        self._log_event("error", {"reason": reason})
