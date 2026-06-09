"""
LessonRunner — управляет одним активным уроком.

Жизненный цикл:
  prepare()      — создать LessonSession, перевести урок в IN_PROGRESS
  init_audio()   — инициализировать TTS + ASR (загрузка моделей)
  init_dialog()  — создать RAGRetriever + ClaudeDialogEngine
  connect_vcs()  — подключиться к конференции
  conduct()      — вести урок по сценарию
  cleanup()      — отключиться, сохранить транскрипт

На каждом шаге сценария:
  text → TTS → PCM → vcs.send_audio()          (бот говорит)
  vcs.recv_audio() → VAD → Whisper → text       (бот слушает)
  text → RAG → Claude API → reply               (бот отвечает)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from sqlalchemy.orm import Session

from src.models.lesson import Lesson, LessonStatus
from src.models.session import LessonSession, SessionStatus
from src.vcs.client import make_vcs_client, VCSConnectionInfo, VCSPlatformType
from src.audio.tts import make_tts, BaseTTS
from src.audio.asr import make_asr
from src.dialog.retriever import RAGRetriever
from src.dialog.engine import make_dialog_engine, BaseDialogEngine
from src.miro.client import make_miro_client, BaseMiroClient
from src.orchestrator.homework import deliver_homework

# EventBus из backend — публикуем события для SSE
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.abspath(_os.path.join(
    _os.path.dirname(__file__), '..', '..', '..', 'backend')))
try:
    from src.events.bus import event_bus as _event_bus
    _HAS_BUS = True
except ImportError:
    _HAS_BUS = False
    _event_bus = None

logger = logging.getLogger(__name__)

LISTEN_TIMEOUT = 12.0
STEP_PAUSE     = 1.0
CHUNK_SIZE     = 640    # 20 мс PCM @ 16kHz 16-bit mono


class LessonRunner:
    def __init__(self, lesson: Lesson, db: Session):
        self.lesson  = lesson
        self.db      = db
        self.session: LessonSession | None  = None
        self._vcs    = None
        self._tts: BaseTTS | None           = None
        self._asr    = None
        self._llm: BaseDialogEngine | None  = None
        self._miro: BaseMiroClient | None   = None
        self._dialog: list[dict] = []
        self._events: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        try:
            await self._prepare()
            await self._init_audio()
            await self._init_dialog()
            await self._init_miro()
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
    # Инициализация
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
        self._publish('session_started', {
            'lesson_status': 'in_progress',
            'total_steps': self.session.total_steps,
        })

        logger.info(
            "[runner %s] Ученик=%s  Тема=%s  Шагов=%d",
            lesson.id,
            lesson.student.full_name if lesson.student else "—",
            lesson.topic.name if lesson.topic else "—",
            self.session.total_steps,
        )

    async def _init_audio(self) -> None:
        lesson   = self.lesson
        voice_id = lesson.teacher.voice_model_path if lesson.teacher else None
        self._tts = make_tts(voice_id=voice_id)
        self._asr = make_asr()
        await self._asr.preload()
        logger.info("[runner %s] TTS=%s  ASR=%s",
                    lesson.id, type(self._tts).__name__, type(self._asr).__name__)

    async def _init_dialog(self) -> None:
        """Создать RAGRetriever и LLM-движок."""
        lesson = self.lesson
        topic  = lesson.topic

        if topic:
            retriever = RAGRetriever(
                db=self.db,
                topic_id=topic.id,
                teacher_id=lesson.teacher_id,
            )
            topic_context = retriever.get_topic_context()
        else:
            # Нет темы — RAG не нужен, движок будет в stub-режиме
            retriever     = None
            topic_context = "Тема урока не указана."

        self._llm = make_dialog_engine(
            retriever=retriever,
            topic_context=topic_context,
        )
        logger.info("[runner %s] LLM=%s", lesson.id, type(self._llm).__name__)

    async def _init_miro(self) -> None:
        topic = self.lesson.topic
        board_id = topic.miro_board_id if topic else None
        self._miro = make_miro_client(board_id=board_id)
        logger.info("[runner %s] Miro=%s  board=%s",
                    self.lesson.id, type(self._miro).__name__, board_id)

    async def _connect_vcs(self) -> None:
        lesson = self.lesson
        info   = VCSConnectionInfo(
            platform=VCSPlatformType(lesson.vcs_platform.value),
            link=lesson.vcs_link or "",
            display_name=f"Помощник — {lesson.teacher.full_name}",
        )
        self._vcs = make_vcs_client(info)
        await self._vcs.connect()

        self.session.status        = SessionStatus.ACTIVE
        self.session.bot_joined_at = datetime.now(timezone.utc)
        self.db.commit()
        self._log_event("bot_joined", {"link": lesson.vcs_link})
        self._publish('bot_joined', {'link': lesson.vcs_link, 'session_status': 'active'})

    # ──────────────────────────────────────────────────────────────────────
    # Ведение урока
    # ──────────────────────────────────────────────────────────────────────

    async def _conduct_lesson(self) -> None:
        lesson       = self.lesson
        script       = (lesson.topic.lesson_script or []) if lesson.topic else []
        student_name = lesson.student.full_name.split()[0] if lesson.student else "ученик"
        topic_name   = lesson.topic.name if lesson.topic else "химии"

        if not script:
            await self._speak(
                f"Здравствуйте, {student_name}! "
                f"Сегодня занятие по теме «{topic_name}». "
                "Сценарий ещё не добавлен — если у вас есть вопросы, я готов ответить."
            )
            # Открытый вопрос-ответ без сценария
            await self._free_dialog(timeout=60.0)
        else:
            await self._speak(
                f"Здравствуйте, {student_name}! "
                f"Сегодня разберём тему «{topic_name}». Начнём."
            )
            await asyncio.sleep(STEP_PAUSE)

            for i, step in enumerate(script):
                self.session.current_step = i + 1
                self.db.commit()
                self._publish('step_started', {
                    'step': i + 1,
                    'total': len(script),
                    'text': step_text[:120] if step_text else None,
                })

                step_text   = step.get("text", "")
                question    = step.get("question")
                miro_action = step.get("miro_action")
                listen_after = step.get("listen", True)

                logger.info("[runner %s] Шаг %d/%d", lesson.id, i + 1, len(script))

                if miro_action:
                    self._log_event("miro_action", {"action": miro_action, "step": i + 1})
                    self._publish('miro_action', {'action': miro_action, 'step': i + 1})
                    await self._miro.execute(miro_action)

                if step_text:
                    await self._speak(step_text)

                if question:
                    await self._speak(question)
                    self._log_event("question_asked", {"step": i + 1, "question": question})
                    self._publish('question_asked', {'step': i + 1, 'question': question})

                if listen_after and question:
                    await self._listen_and_respond()

                await asyncio.sleep(STEP_PAUSE)

            await self._speak(
                "Отлично! Урок завершён. "
                "Если остались вопросы — задавай, у нас ещё есть минута."
            )
            # Финальный свободный диалог
            await self._free_dialog(timeout=60.0)

            await self._speak(
                "Домашнее задание придёт на почту. До свидания!"
            )

        self.session.status = SessionStatus.FINISHING
        self.db.commit()

    # ──────────────────────────────────────────────────────────────────────
    # Свободный диалог (вопросы ученика без шагов сценария)
    # ──────────────────────────────────────────────────────────────────────

    async def _free_dialog(self, timeout: float = 60.0) -> None:
        """
        Слушаем вопросы ученика в течение timeout секунд.
        На каждую распознанную фразу генерируем LLM-ответ и озвучиваем.
        """
        deadline = asyncio.get_event_loop().time() + timeout

        async for phrase in self._asr.listen(self._vcs, timeout=timeout):
            if not phrase.strip():
                continue

            logger.info("[runner %s] [free] 👂 %s", self.lesson.id, phrase)
            self._dialog.append({
                "role": "student",
                "text": phrase,
                "ts":   datetime.now(timezone.utc).isoformat(),
            })
            self._log_event("student_question", {"text": phrase})
            self._publish('student_question', {'text': phrase})

            # Генерируем ответ через LLM
            try:
                response = await self._llm.respond(phrase)
                reply    = response.text

                if response.used_chunks:
                    self._log_event("rag_chunks_used", {
                        "count":   len(response.used_chunks),
                        "sources": [c.title for c in response.used_chunks],
                    })
            except Exception as e:
                logger.error("[runner %s] LLM ошибка: %s", self.lesson.id, e)
                reply = "Хороший вопрос, давай вернёмся к нему чуть позже."

            self._publish('bot_reply', {'text': reply})
            await self._speak(reply)

            if asyncio.get_event_loop().time() >= deadline:
                break

    # ──────────────────────────────────────────────────────────────────────
    # Ответ на вопрос по ходу сценария
    # ──────────────────────────────────────────────────────────────────────

    async def _listen_and_respond(self) -> None:
        heard = False

        async for phrase in self._asr.listen(self._vcs, timeout=LISTEN_TIMEOUT):
            if not phrase.strip():
                continue

            logger.info("[runner %s] 👂 %s", self.lesson.id, phrase)
            self._dialog.append({
                "role": "student",
                "text": phrase,
                "ts":   datetime.now(timezone.utc).isoformat(),
            })
            self._log_event("student_speech", {"text": phrase})
            self._publish('student_speech', {'text': phrase})
            heard = True

            try:
                response = await self._llm.respond(phrase)
                await self._speak(response.text)
            except Exception as e:
                logger.error("[runner %s] LLM ошибка: %s", self.lesson.id, e)
                await self._speak("Хорошо, продолжаем.")

            break   # один ответ на вопрос

        if not heard:
            await self._speak("Хорошо, двигаемся дальше.")

    # ──────────────────────────────────────────────────────────────────────
    # TTS
    # ──────────────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
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

        for offset in range(0, len(pcm), CHUNK_SIZE):
            chunk = pcm[offset: offset + CHUNK_SIZE]
            if len(chunk) < CHUNK_SIZE:
                chunk += b"\x00" * (CHUNK_SIZE - len(chunk))
            await self._vcs.send_audio(chunk)
            await asyncio.sleep(0.018)

    # ──────────────────────────────────────────────────────────────────────
    # Завершение
    # ──────────────────────────────────────────────────────────────────────

    async def _cleanup(self) -> None:
        now = datetime.now(timezone.utc)

        if self._vcs and self._vcs.connected:
            try:
                await self._vcs.disconnect()
            except Exception as e:
                logger.warning("[runner %s] VCS disconnect: %s", self.lesson.id, e)

        for resource in (self._tts, self._llm, self._miro):
            if resource:
                try:
                    await resource.close()
                except Exception:
                    pass

        if self.session:
            if self.session.status not in (SessionStatus.FAILED,):
                self.session.status = SessionStatus.ENDED
            self.session.bot_left_at    = now
            self.session.dialog_history = self._dialog
            self.session.event_log      = self._events

        # Отправить домашнее задание
        try:
            hw_ok = await deliver_homework(self.db, self.lesson)
            if hw_ok:
                self._publish('homework_sent', {
                    'student_email': self.lesson.student.email if self.lesson.student else None,
                })
        except Exception as e:
            logger.error("[runner %s] Ошибка отправки ДЗ: %s", self.lesson.id, e)

        lesson = self.lesson
        if lesson.status == LessonStatus.IN_PROGRESS:
            lesson.status = LessonStatus.COMPLETED
        lesson.finished_at = now
        lesson.transcript  = self._build_transcript()
        if lesson.status == LessonStatus.COMPLETED:
            self._publish('session_ended', {
                'lesson_status': lesson.status.value,
                'dialog_lines': len(self._dialog),
            })
        else:
            self._publish('session_failed', {
                'lesson_status': lesson.status.value,
            })

        try:
            self.db.commit()
        except Exception as e:
            logger.error("[runner %s] Ошибка сохранения: %s", self.lesson.id, e)

        logger.info("[runner %s] ✓ Статус=%s  Реплик=%d",
                    lesson.id, lesson.status, len(self._dialog))

    # ──────────────────────────────────────────────────────────────────────
    # Вспомогательное
    # ──────────────────────────────────────────────────────────────────────

    def _publish(self, kind: str, data: dict | None = None) -> None:
        """Опубликовать событие в SSE-шину бэкенда."""
        if _HAS_BUS and _event_bus:
            _event_bus.publish(self.lesson.id, kind, data or {})

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
