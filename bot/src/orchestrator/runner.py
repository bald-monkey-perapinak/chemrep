"""
LessonRunner — управляет одним активным уроком.

Жизненный цикл:
  prepare()  — создать LessonSession, перевести урок в IN_PROGRESS
  run()      — подключиться к конференции, вести урок по сценарию
  cleanup()  — отключиться, сохранить транскрипт и результаты

Аудио-pipeline на каждом шаге:
  текст шага → TTS.synthesize() → PCM → vcs.send_audio() (бот говорит)
  vcs.recv_audio() → VAD → PhraseBuffer → Whisper → текст (бот слушает)
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
from src.audio.tts import make_tts, BaseTTS
from src.audio.asr import make_asr

logger = logging.getLogger(__name__)

# Сколько секунд слушать ученика после каждого шага
LISTEN_TIMEOUT   = 12.0
# Пауза (сек) между шагами
STEP_PAUSE       = 1.0
# Размер PCM-чанка для отправки в VCS (20 мс = 640 байт)
CHUNK_SIZE       = 640


class LessonRunner:
    def __init__(self, lesson: Lesson, db: Session):
        self.lesson  = lesson
        self.db      = db
        self.session: LessonSession | None = None
        self._vcs    = None
        self._tts: BaseTTS | None = None
        self._asr    = None
        self._dialog: list[dict] = []
        self._events: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        try:
            await self._prepare()
            await self._init_audio()
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
    # Подготовка
    # ──────────────────────────────────────────────────────────────────────

    async def _prepare(self) -> None:
        lesson = self.lesson
        if lesson.status not in (LessonStatus.SCHEDULED,):
            raise RuntimeError(f"Урок {lesson.id} уже в статусе {lesson.status}")

        self.session = LessonSession(
            lesson_id=lesson.id,
            status=SessionStatus.STARTING,
            total_steps=len(lesson.topic.lesson_script or []) if lesson.topic else 0,
            dialog_history=[],
            event_log=[],
        )
        self.db.add(self.session)
        lesson.status     = LessonStatus.IN_PROGRESS
        lesson.started_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(
            "[runner %s] Подготовка: ученик=%s, тема=%s, шагов=%d",
            lesson.id,
            lesson.student.full_name if lesson.student else "—",
            lesson.topic.name if lesson.topic else "—",
            self.session.total_steps,
        )

    async def _init_audio(self) -> None:
        """Инициализировать TTS и ASR (загрузка моделей)."""
        lesson = self.lesson

        # Голос преподавателя — берём voice_id из профиля
        voice_id = None
        if lesson.teacher and lesson.teacher.voice_model_path:
            # voice_model_path хранит ElevenLabs voice_id после клонирования
            voice_id = lesson.teacher.voice_model_path

        self._tts = make_tts(voice_id=voice_id)
        self._asr = make_asr()

        # Преждевременная загрузка Whisper — чтобы не было задержки на первом вопросе
        await self._asr.preload()
        logger.info("[runner %s] TTS=%s, ASR=%s инициализированы",
                    lesson.id, type(self._tts).__name__, type(self._asr).__name__)

    async def _connect_vcs(self) -> None:
        lesson = self.lesson
        info   = VCSConnectionInfo(
            platform=VCSPlatformType(lesson.vcs_platform.value),
            link=lesson.vcs_link or "",
            display_name=f"Помощник — {lesson.teacher.full_name}",
        )
        self._vcs = make_vcs_client(info)
        await self._vcs.connect()

        self.session.status       = SessionStatus.ACTIVE
        self.session.bot_joined_at = datetime.now(timezone.utc)
        self.db.commit()
        self._log_event("bot_joined", {"link": lesson.vcs_link})

    # ──────────────────────────────────────────────────────────────────────
    # Ведение урока
    # ──────────────────────────────────────────────────────────────────────

    async def _conduct_lesson(self) -> None:
        lesson = self.lesson
        script = (lesson.topic.lesson_script or []) if lesson.topic else []
        student_name = lesson.student.full_name.split()[0] if lesson.student else "ученик"
        topic_name   = lesson.topic.name if lesson.topic else "химии"

        if not script:
            await self._speak(
                f"Здравствуйте, {student_name}! Сегодня занятие по теме «{topic_name}». "
                "Сценарий ещё не добавлен — преподаватель скоро подключится."
            )
            await asyncio.sleep(5)
        else:
            # Приветствие
            await self._speak(
                f"Здравствуйте, {student_name}! "
                f"Сегодня мы разберём тему «{topic_name}». Начнём."
            )
            await asyncio.sleep(STEP_PAUSE)

            for i, step in enumerate(script):
                self.session.current_step = i + 1
                self.db.commit()

                step_text    = step.get("text", "")
                question     = step.get("question")   # вопрос ученику (опционально)
                miro_action  = step.get("miro_action")
                listen_after = step.get("listen", True)  # слушать ли ответ

                logger.info("[runner %s] Шаг %d/%d", lesson.id, i + 1, len(script))

                # Действие на доске Miro
                if miro_action:
                    self._log_event("miro_action", {"action": miro_action, "step": i + 1})
                    # TODO: await miro_client.execute(miro_action)

                # Произнести объяснение
                if step_text:
                    await self._speak(step_text)

                # Задать вопрос и послушать ответ
                if question:
                    await self._speak(question)
                    self._log_event("question_asked", {"step": i + 1, "question": question})

                if listen_after and question:
                    await self._listen_and_respond()

                await asyncio.sleep(STEP_PAUSE)

            # Завершение
            await self._speak(
                "Отлично! На этом наш урок заканчивается. "
                "Домашнее задание придёт вам на почту. До свидания!"
            )

        self.session.status = SessionStatus.FINISHING
        self.db.commit()

    # ──────────────────────────────────────────────────────────────────────
    # TTS — бот говорит
    # ──────────────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """Синтезировать текст и отправить аудио в конференцию чанками."""
        if not text.strip():
            return

        logger.info("[runner %s] 🔊 %s", self.lesson.id, text[:100])
        self._dialog.append({
            "role": "bot",
            "text": text,
            "ts":   datetime.now(timezone.utc).isoformat(),
        })

        try:
            pcm = await self._tts.synthesize(text)
        except Exception as e:
            logger.error("[runner %s] TTS ошибка: %s", self.lesson.id, e)
            return

        # Отправляем по 20-мс чанкам, чтобы не переполнять очередь VCS
        for offset in range(0, len(pcm), CHUNK_SIZE):
            chunk = pcm[offset: offset + CHUNK_SIZE]
            if len(chunk) < CHUNK_SIZE:
                # Добивить тишиной до полного фрейма
                chunk += b"\x00" * (CHUNK_SIZE - len(chunk))
            await self._vcs.send_audio(chunk)
            await asyncio.sleep(0.018)  # ~55 фреймов/сек, чуть быстрее realtime

    # ──────────────────────────────────────────────────────────────────────
    # ASR — бот слушает
    # ──────────────────────────────────────────────────────────────────────

    async def _listen_and_respond(self) -> None:
        """
        Слушать ответ ученика LISTEN_TIMEOUT секунд.
        Если ученик что-то сказал — залогировать и подтвердить.
        Если ничего — мягко продолжить.
        """
        heard_anything = False

        async for phrase in self._asr.listen(self._vcs, timeout=LISTEN_TIMEOUT):
            logger.info("[runner %s] 👂 %s", self.lesson.id, phrase)
            self._dialog.append({
                "role": "student",
                "text": phrase,
                "ts":   datetime.now(timezone.utc).isoformat(),
            })
            self._log_event("student_speech", {"text": phrase})
            heard_anything = True
            # После первой фразы выходим — один ответ на вопрос
            break

        if not heard_anything:
            logger.info("[runner %s] Тишина — продолжаем", self.lesson.id)
            await self._speak("Хорошо, двигаемся дальше.")

    # ──────────────────────────────────────────────────────────────────────
    # Завершение
    # ──────────────────────────────────────────────────────────────────────

    async def _cleanup(self) -> None:
        now = datetime.now(timezone.utc)

        if self._vcs and self._vcs.connected:
            try:
                await self._vcs.disconnect()
            except Exception as e:
                logger.warning("[runner %s] Ошибка VCS disconnect: %s", self.lesson.id, e)

        if self._tts:
            try:
                await self._tts.close()
            except Exception:
                pass

        if self.session:
            if self.session.status not in (SessionStatus.FAILED,):
                self.session.status = SessionStatus.ENDED
            self.session.bot_left_at      = now
            self.session.dialog_history   = self._dialog
            self.session.event_log        = self._events

        lesson = self.lesson
        if lesson.status == LessonStatus.IN_PROGRESS:
            lesson.status = LessonStatus.COMPLETED
        lesson.finished_at = now
        lesson.transcript  = self._build_transcript()

        try:
            self.db.commit()
        except Exception as e:
            logger.error("[runner %s] Ошибка сохранения: %s", self.lesson.id, e)

        logger.info("[runner %s] ✓ Завершено. Статус=%s, фраз=%d",
                    lesson.id, lesson.status, len(self._dialog))

    # ──────────────────────────────────────────────────────────────────────
    # Вспомогательное
    # ──────────────────────────────────────────────────────────────────────

    def _log_event(self, kind: str, data: dict) -> None:
        self._events.append({
            "kind": kind,
            "data": data,
            "ts":   datetime.now(timezone.utc).isoformat(),
        })

    def _build_transcript(self) -> str:
        lines = []
        for m in self._dialog:
            role = "Бот" if m["role"] == "bot" else "Ученик"
            lines.append(f"[{m['ts']}] {role}: {m['text']}")
        return "\n".join(lines)

    async def _mark_failed(self, reason: str) -> None:
        if self.session:
            self.session.status        = SessionStatus.FAILED
            self.session.error_message = reason
        self.lesson.status = LessonStatus.CANCELLED
        self._log_event("error", {"reason": reason})
        try:
            self.db.commit()
        except Exception:
            pass
