"""
LessonRunner — управляет одним активным уроком.

Жизненный цикл:
  prepare()      — создать LessonSession, перевести урок в IN_PROGRESS
  init_audio()   — инициализировать TTS + ASR (загрузка моделей)
  init_dialog()  — создать RAGRetriever + TutorDialogEngine
  connect_vcs()  — подключиться к конференции
  conduct()      — вести урок по сценарию
  cleanup()      — отключиться, сохранить транскрипт

На каждом шаге сценария:
  text → TTS → PCM → vcs.send_audio()          (бот говорит)
  vcs.recv_audio() → VAD → Whisper → text       (бот слушает)
  text → IntentClassifier → TeachingStrategy    (классификация + выбор методики)
  text → RAG → Claude API → reply               (бот отвечает)
  StudentModel → обновление прогресса           (отслеживание понимания)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from typing import Optional

_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from sqlalchemy.orm import Session

from src.models.lesson import Lesson, LessonStatus
from src.models.session import LessonSession, SessionStatus
from src.models.student import StudentProgress
from src.vcs.client import make_vcs_client, VCSConnectionInfo, VCSPlatformType
from src.audio.tts import make_tts, BaseTTS
from src.audio.asr import make_asr
from src.dialog.retriever import RAGRetriever
from src.dialog.tutor_engine import make_tutor_engine, TutorDialogEngine, StubTutorEngine, TutorResponse
from src.dialog.script_processor import process_lesson_script, ProcessedScript
from src.dialog.lesson_summary import generate_lesson_summary, format_summary_for_tts, format_summary_for_db
from src.board.client import make_board_client, BaseBoardClient
from src.orchestrator.homework import deliver_homework
from src.orchestrator.checkpoint import LessonCheckpoint
from src.orchestrator.reconnect import ReconnectManager, is_connection_error
from src.orchestrator.audio_pipeline import AudioPipeline
from src.dialog.pace_controller import PaceController
from src.vcs.monitor import VCSMonitor
from src.llm.version_manager import LLMVersionManager
from src.logging_config import set_lesson_context, set_step_context

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
STUDENT_CONNECT_TIMEOUT = 600  # 10 minutes
STUDENT_CONNECT_CHECK_INTERVAL = 30  # Check every 30 seconds


class LessonRunner:
    def __init__(self, lesson: Lesson, db: Session):
        self.lesson  = lesson
        self.db      = db
        self.session: LessonSession | None  = None
        self._vcs    = None
        self._tts: BaseTTS | None           = None
        self._asr    = None
        self._llm: TutorDialogEngine | StubTutorEngine | None  = None
        self._board: BaseBoardClient | None = None
        self._dialog: list[dict] = []
        self._events: list[dict] = []
        self._checkpoint = LessonCheckpoint(db)
        self._recording_allowed = False
        self._audio_pipeline: AudioPipeline | None = None
        self._reconnect: ReconnectManager | None = None
        self._pace_controller = PaceController()
        self._vcs_monitor = VCSMonitor()
        self._llm_version_manager = LLMVersionManager()

    # ──────────────────────────────────────────────────────────────────────
    # Публичный API
    # ──────────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        set_lesson_context(
            str(self.lesson.id),
            student_id=str(self.lesson.student_id) if self.lesson.student_id else None,
        )
        try:
            await self._prepare()
            await self._init_audio()
            await self._init_dialog()
            await self._init_board()
            await self._connect_vcs()
            await self._conduct_lesson()
        except asyncio.CancelledError:
            logger.warning("[runner %s] Задача отменена", self.lesson.id)
            try:
                if self._audio_pipeline and self._vcs and self._vcs.connected:
                    await self._audio_pipeline.speak("Урок завершается. До свидания!")
            except Exception:
                pass
            await self._mark_failed("Задача отменена оркестратором")
            raise
        except Exception as exc:
            logger.exception("[runner %s] Необработанная ошибка: %s", self.lesson.id, exc)
            await self._mark_failed(str(exc))
        finally:
            await self._cleanup()
            set_lesson_context(None)

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
        """Создать RAGRetriever и профессиональный TutorDialogEngine."""
        lesson = self.lesson
        topic  = lesson.topic

        # Получаем данные ученика
        student_name = lesson.student.full_name.split()[0] if lesson.student else "ученик"
        student_grade = lesson.student.grade if lesson.student and lesson.student.grade else 9

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

        # Загружаем профиль стиля преподавателя
        teaching_style = self._load_teaching_style()

        self._llm = make_tutor_engine(
            retriever=retriever,
            topic_context=topic_context,
            student_name=student_name,
            student_grade=student_grade,
            teaching_style=teaching_style,
        )
        logger.info(
            "[runner %s] LLM=%s  student=%s grade=%d",
            lesson.id, type(self._llm).__name__, student_name, student_grade,
        )

        # Загружаем прогресс ученика из предыдущих уроков
        await self._load_student_progress()

    async def _init_board(self) -> None:
        session_id = str(self.session.id) if self.session else None
        # Generate JWT token for board WebSocket auth
        board_token = ""
        try:
            from src.config.jwt import get_jwt_secret, ALGORITHM, ACCESS_TOKEN_EXPIRE_MIN
            from jose import jwt
            from datetime import timedelta
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MIN)
            board_token = jwt.encode(
                {"sub": str(self.lesson.teacher_id), "exp": expire, "type": "access"},
                get_jwt_secret(),
                algorithm=ALGORITHM,
            )
        except Exception as e:
            logger.warning("[runner %s] Could not generate board token: %s", self.lesson.id, e)

        self._board = make_board_client(session_id=session_id, token=board_token)
        logger.info("[runner %s] Board=%s  session=%s",
                    self.lesson.id, type(self._board).__name__, session_id)

    async def _connect_vcs(self) -> None:
        lesson = self.lesson

        # Check parental consent before recording
        if not self._check_recording_consent():
            logger.warning(
                "[runner %s] Нет согласия родителя на запись — запись отключена",
                lesson.id,
            )

        info   = VCSConnectionInfo(
            platform=VCSPlatformType(lesson.vcs_platform.value),
            link=lesson.vcs_link or "",
            display_name=f"Помощник — {lesson.teacher.full_name}",
        )
        self._vcs = make_vcs_client(info)
        try:
            await self._vcs.connect()
            self._vcs_monitor.record_success()
        except Exception as e:
            self._vcs_monitor.record_failure(str(e))
            raise

        # Инициализируем пайплайн аудио и менеджер переподключения
        self._audio_pipeline = AudioPipeline(
            tts=self._tts,
            vcs=self._vcs,
            dialog_log=self._dialog,
            lesson_id=lesson.id,
        )
        self._reconnect = ReconnectManager(
            on_reconnect=self._do_reconnect_vcs,
            on_event=self._log_event,
        )

        self.session.status        = SessionStatus.ACTIVE
        self.session.bot_joined_at = datetime.now(timezone.utc)
        self.db.commit()

        # Начинаем запись аудио (только при наличии согласия)
        if self._recording_allowed:
            self._vcs.start_recording()

        self._log_event("bot_joined", {"link": lesson.vcs_link})
        self._publish('bot_joined', {'link': lesson.vcs_link, 'session_status': 'active'})

    async def _wait_for_student(self, timeout: float = STUDENT_CONNECT_TIMEOUT) -> bool:
        """
        Wait for student to connect to the conference.
        Returns True if student connected, False on timeout.
        """
        start_time = asyncio.get_running_loop().time()

        while asyncio.get_running_loop().time() - start_time < timeout:
            # Check if student is in the conference
            if self._vcs and self._vcs.student_connected():
                logger.info(f"[runner {self.lesson.id}] Student connected")
                return True
            
            await asyncio.sleep(STUDENT_CONNECT_CHECK_INTERVAL)
        
        logger.warning(f"[runner {self.lesson.id}] Student connect timeout after {timeout}s")
        return False

    def _check_recording_consent(self) -> bool:
        """Check if parental consent exists for recording this student."""
        try:
            from src.models.consent import ParentalConsent
            student = self.lesson.student
            if not student:
                return False

            consent = self.db.query(ParentalConsent).filter(
                ParentalConsent.student_id == student.id,
                ParentalConsent.consent_given == True,  # noqa: E712
                ParentalConsent.recording_allowed == True,  # noqa: E712
            ).first()

            if consent:
                self._recording_allowed = True
                logger.info("[runner %s] Consent found for student %s", self.lesson.id, student.id)
                return True

            self._recording_allowed = False
            self._notify_parent_no_consent(student)
            return False
        except Exception as e:
            logger.debug("[runner %s] Consent check failed: %s", self.lesson.id, e)
            self._recording_allowed = False
            return False

    def _notify_parent_no_consent(self, student) -> None:
        """Notify parent that a lesson was conducted (without recording) due to missing consent."""
        try:
            from src.models.consent import ParentalConsent
            consent = self.db.query(ParentalConsent).filter(
                ParentalConsent.student_id == student.id,
            ).first()
            if not consent or not consent.parent_email:
                return

            import os, smtplib, ssl
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            host = os.getenv("SMTP_HOST", "smtp.gmail.com")
            port = int(os.getenv("SMTP_PORT", "465"))
            user = os.getenv("SMTP_USER", "")
            password = os.getenv("SMTP_PASSWORD", "") or os.getenv("SMTP_PASS", "")

            if not user or not password:
                return

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Урок по химии — {student.full_name}"
            msg["From"] = user
            msg["To"] = consent.parent_email

            html = f"""
            <p>Здравствуйте, {consent.parent_name}!</p>
            <p>Сегодня состоялся урок по химии с учеником <b>{student.full_name}</b>.</p>
            <p>Запись урока не велась, так как не было получено согласие на запись.</p>
            <p>Чтобы в будущем записи уроков были доступны, пожалуйста, дайте согласие через личный кабинет преподавателя.</p>
            <p>С уважением,<br>ХимТьютор</p>
            """
            msg.attach(MIMEText(html, "html", "utf-8"))

            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) as server:
                server.login(user, password)
                server.sendmail(user, consent.parent_email, msg.as_string())
            logger.info("[runner] Parent notification sent to %s", consent.parent_email)
        except Exception as e:
            logger.debug("[runner] Parent notification failed: %s", e)

    # ──────────────────────────────────────────────────────────────────────
    # Ведение урока
    # ──────────────────────────────────────────────────────────────────────

    async def _conduct_lesson(self) -> None:
        lesson       = self.lesson
        raw_script   = (lesson.topic.lesson_script or []) if lesson.topic else []
        student_name = lesson.student.full_name.split()[0] if lesson.student else "ученик"
        topic_name   = lesson.topic.name if lesson.topic else "химии"

        # Обрабатываем сценарий (автогенерация команд доски, сложности и т.д.)
        processed_script = ProcessedScript(steps=[], key_concepts=[])
        if raw_script:
            processed_script = process_lesson_script(
                raw_script,
                topic_name=topic_name,
                topic_description=lesson.topic.description if lesson.topic else "",
            )
            logger.info(
                "[runner %s] Сценарий обработан: %d шагов, концепции: %s",
                lesson.id, len(processed_script.steps),
                ", ".join(processed_script.key_concepts[:5]),
            )

        script = processed_script.steps

        # Устанавливаем контекст шагов в движке
        if hasattr(self._llm, 'set_step_context'):
            self._llm.set_step_context(0, len(script))

        if not script:
            await self._speak(
                f"Здравствуйте, {student_name}! "
                f"Сегодня занятие по теме «{topic_name}». "
                "Сценарий ещё не добавлен — если у вас есть вопросы, я готов ответить."
            )
            await self._free_dialog_with_reconnect(timeout=60.0)
        else:
            await self._speak(
                f"Здравствуйте, {student_name}! "
                f"Сегодня разберём тему «{topic_name}». Начнём."
            )
            await asyncio.sleep(STEP_PAUSE)

            i = 0
            while i < len(script):
                step = script[i]
                step_text   = step.text
                question    = step.question
                board_commands = step.board_commands
                listen_after = step.listen
                speak_only = step.speak_only
                difficulty = step.difficulty

                # Обновляем контекст шага в движке
                if hasattr(self._llm, 'set_step_context'):
                    self._llm.set_step_context(i, len(script))

                set_step_context(i + 1)

                self.session.current_step = i + 1
                self.db.commit()

                # Сохраняем чекпоинт для восстановления после сбоя
                self._checkpoint.save_checkpoint(
                    str(self.lesson.id),
                    step=i,
                    state={
                        "current_step": i,
                        "total_steps": len(script),
                        "consecutive_correct": getattr(self._llm, '_consecutive_correct', 0),
                        "consecutive_incorrect": getattr(self._llm, '_consecutive_incorrect', 0),
                    },
                )
                self._publish('step_started', {
                    'step': i + 1,
                    'total': len(script),
                    'text': step_text[:120] if step_text else None,
                    'difficulty': difficulty,
                    'key_concepts': step.key_concepts,
                })

                logger.info(
                    "[runner %s] Шаг %d/%d (difficulty=%s, speak_only=%s, concepts=%s)",
                    lesson.id, i + 1, len(script), difficulty, speak_only,
                    ", ".join(step.key_concepts[:3]),
                )

                # Выполняем команды доски (если не speak_only)
                if not speak_only:
                    for cmd in board_commands:
                        self._log_event("board_action", {"command": cmd, "step": i + 1})
                        self._publish('board_action', {'command': cmd, 'step': i + 1})
                        if self._board:
                            await self._board.execute(cmd)
                    # Уведомляем если доска недоступна
                    if self._board and hasattr(self._board, '_available') and not self._board._available:
                        self._log_event("board_unavailable", {"step": i + 1})
                        self._publish('board_unavailable', {'step': i + 1})

                # Озвучиваем текст шага
                if step_text:
                    await self._speak_with_reconnect(step_text)

                # Задаём вопрос (если есть)
                if question:
                    await self._speak_with_reconnect(question)
                    self._log_event("question_asked", {"step": i + 1, "question": question})
                    self._publish('question_asked', {'step': i + 1, 'question': question})

                # Слушаем ответ ученика (если нужно)
                if listen_after and question:
                    response = await self._listen_and_respond_with_reconnect()

                    # Проверяем, нужно ли адаптировать темп
                    if response and hasattr(response, 'strategy') and response.strategy:
                        adjustment = response.strategy.next_step_adjustment
                        if adjustment < 0 and i > 0:
                            # Вернуться на шаг назад
                            i = max(0, i - 1)
                            logger.info(
                                "[runner %s] Адаптация: возврат к шагу %d (reason: %s)",
                                lesson.id, i + 1, response.strategy.reason,
                            )
                            continue
                        elif adjustment > 0 and i < len(script) - 1:
                            # Ускориться (пропустить текущий шаг)
                            logger.info(
                                "[runner %s] Адаптация: ускорение (reason: %s)",
                                lesson.id, response.strategy.reason,
                            )

                await asyncio.sleep(STEP_PAUSE)
                i += 1

            # Генерируем сводку урока
            summary = None
            if hasattr(self._llm, 'get_student_model'):
                student_model = self._llm.get_student_model()
                summary = generate_lesson_summary(
                    student_model=student_model,
                    topic_name=topic_name,
                    topics_covered=processed_script.key_concepts,
                    steps_completed=len(script),
                    total_steps=len(script),
                )
                # Сохраняем сводку
                self._log_event("lesson_summary", {
                    "brief": summary.brief_summary,
                    "accuracy": summary.accuracy_percent,
                    "understanding": summary.overall_understanding,
                })
                self._publish('lesson_summary', {
                    'brief': summary.brief_summary,
                    'accuracy': summary.accuracy_percent,
                })

            # Завершение урока
            await self._speak_with_reconnect(
                "Отлично! Урок завершён. "
                "Если остались вопросы — задавай, у нас ещё есть минута."
            )
            await self._free_dialog_with_reconnect(timeout=60.0)

            # Озвучиваем краткую сводку
            if summary:
                await self._speak_with_reconnect(summary.student_summary)

            await self._speak_with_reconnect(
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
        deadline = asyncio.get_running_loop().time() + timeout
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

                # Логируем дополнительную информацию
                if hasattr(response, 'intent') and response.intent:
                    self._log_event("intent_classified", {
                        "type": response.intent.type.value,
                        "confidence": response.intent.confidence,
                    })
                if hasattr(response, 'strategy') and response.strategy:
                    self._log_event("teaching_strategy", {
                        "method": response.strategy.method.value,
                        "reason": response.strategy.reason,
                    })

                if hasattr(response, 'used_chunks') and response.used_chunks:
                    self._log_event("rag_chunks_used", {
                        "count":   len(response.used_chunks),
                        "sources": [c.title for c in response.used_chunks],
                    })

                # Выполняем команды доски из ответа
                if hasattr(response, 'board_commands') and response.board_commands:
                    for cmd in response.board_commands:
                        self._log_event("board_action", {"command": cmd})
                        self._publish('board_action', {'command': cmd})
                        if self._board:
                            await self._board.execute(cmd)

            except Exception as e:
                logger.error("[runner %s] LLM ошибка: %s", self.lesson.id, e)
                reply = "Хороший вопрос, давай вернёмся к нему чуть позже."

            self._publish('bot_reply', {'text': reply})
            await self._speak(reply)

            if asyncio.get_running_loop().time() >= deadline:
                break

    # ──────────────────────────────────────────────────────────────────────
    # Ответ на вопрос по ходу сценария
    # ──────────────────────────────────────────────────────────────────────

    async def _listen_and_respond(self) -> Optional[TutorResponse]:
        """
        Слушаем ответ ученика и реагируем.
        Возвращает TutorResponse для адаптации темпа урока.
        """
        import time as _time
        heard = False
        last_response = None
        response_start = _time.monotonic()

        async for phrase in self._asr.listen(self._vcs, timeout=LISTEN_TIMEOUT):
            if not phrase.strip():
                continue

            response_time = _time.monotonic() - response_start
            logger.info("[runner %s] 👂 %s (response_time=%.1fs)", self.lesson.id, phrase, response_time)
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

                # Логируем дополнительную информацию
                if hasattr(response, 'intent') and response.intent:
                    self._log_event("intent_classified", {
                        "type": response.intent.type.value,
                        "confidence": response.intent.confidence,
                    })
                if hasattr(response, 'strategy') and response.strategy:
                    self._log_event("teaching_strategy", {
                        "method": response.strategy.method.value,
                        "reason": response.strategy.reason,
                    })
                if hasattr(response, 'understanding') and response.understanding:
                    self._log_event("understanding_level", {
                        "level": response.understanding.value,
                    })

                # Выполняем команды доски из ответа
                if hasattr(response, 'board_commands') and response.board_commands:
                    for cmd in response.board_commands:
                        self._log_event("board_action", {"command": cmd, "step": self.session.current_step})
                        self._publish('board_action', {'command': cmd, 'step': self.session.current_step})
                        if self._board:
                            await self._board.execute(cmd)

                await self._speak(response.text)
                last_response = response

                # Record response time for pace adaptation
                is_correct = hasattr(response, 'intent') and response.intent and response.intent.type.value == 'correct_answer'
                self._pace_controller.record_response(response_time, is_correct)

                # Генерируем дополнительную задачу при ошибках
                if hasattr(self._llm, 'generate_practice_if_needed'):
                    practice = await self._llm.generate_practice_if_needed()
                    if practice:
                        self._log_event("practice_exercise", {"text": practice})
                        self._publish('practice_exercise', {'text': practice})
                        await self._speak(practice)

            except Exception as e:
                logger.error("[runner %s] LLM ошибка: %s", self.lesson.id, e)
                await self._speak("Хорошо, продолжаем.")

            break   # один ответ на вопрос

        if not heard:
            await self._speak("Хорошо, двигаемся дальше.")

        return last_response

    # ──────────────────────────────────────────────────────────────────────
    # TTS
    # ──────────────────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """Озвучить текст через AudioPipeline."""
        await self._audio_pipeline.speak(text)

    async def _speak_with_reconnect(self, text: str) -> None:
        """_speak с автоматическим переподключением при ошибке соединения."""
        await self._reconnect.execute_with_reconnect(
            lambda: self._speak(text),
            operation_name="speaking",
        )

    async def _listen_and_respond_with_reconnect(self) -> Optional[TutorResponse]:
        """_listen_and_respond с переподключением."""
        return await self._reconnect.execute_with_reconnect_return(
            self._listen_and_respond,
            operation_name="listening",
        )

    async def _free_dialog_with_reconnect(self, timeout: float = 60.0) -> None:
        """_free_dialog с переподключением."""
        await self._reconnect.execute_with_reconnect(
            lambda: self._free_dialog(timeout=timeout),
            operation_name="free_dialog",
        )

    async def _do_reconnect_vcs(self) -> bool:
        """Логика переподключения для ReconnectManager."""
        if self._vcs:
            try:
                self._vcs._recorder.stop()
            except Exception as e:
                logger.debug("[runner %s] Recorder stop: %s", self.lesson.id, e)
            try:
                await self._vcs.disconnect()
            except Exception as e:
                logger.debug("[runner %s] VCS disconnect during reconnect: %s", self.lesson.id, e)

        lesson = self.lesson
        info = VCSConnectionInfo(
            platform=VCSPlatformType(lesson.vcs_platform.value),
            link=lesson.vcs_link or "",
            display_name=f"Помощник — {lesson.teacher.full_name}",
        )
        self._vcs = make_vcs_client(info)
        await self._vcs.connect()
        self._vcs.start_recording()

        # Обновляем AudioPipeline с новым VCS
        self._audio_pipeline = AudioPipeline(
            tts=self._tts,
            vcs=self._vcs,
            dialog_log=self._dialog,
            lesson_id=lesson.id,
        )
        return True

    async def _cleanup(self) -> None:
        now = datetime.now(timezone.utc)

        # Останавливаем запись аудио и сохраняем в S3 (только при согласии)
        if self._vcs and self._vcs.connected:
            try:
                if self._recording_allowed:
                    wav_data = self._vcs.stop_recording()
                    if wav_data and len(wav_data) > 1000:  # минимум 1KB
                        await self._save_recording(wav_data)
                else:
                    logger.info("[runner %s] Запись не сохранена — нет согласия родителя", self.lesson.id)
            except Exception as e:
                logger.warning("[runner %s] Ошибка сохранения записи: %s", self.lesson.id, e)

        if self._vcs and self._vcs.connected:
            try:
                await self._vcs.disconnect()
            except Exception as e:
                logger.warning("[runner %s] VCS disconnect: %s", self.lesson.id, e)

        for resource in (self._tts, self._llm, self._board):
            if resource:
                try:
                    await resource.close()
                except Exception as e:
                    logger.debug("[runner %s] Resource close: %s", self.lesson.id, e)

        if self.session:
            if self.session.status not in (SessionStatus.FAILED,):
                self.session.status = SessionStatus.ENDED
            self.session.bot_left_at    = now
            self.session.dialog_history = self._dialog
            self.session.event_log      = self._events

        # Сохраняем сводку урока в сессию
        await self._save_lesson_summary()

        # Сохраняем прогресс ученика для следующего урока
        await self._save_student_progress()

        # Отправить домашнее задание
        try:
            hw_ok = await deliver_homework(self.db, self.lesson)
            if hw_ok:
                self._publish('homework_sent', {
                    'student_email': self.lesson.student.email if self.lesson.student else None,
                })
            else:
                # Notify parent via Telegram that email delivery failed
                try:
                    from src.orchestrator.notifier import notify_homework_sent
                    from src.models.consent import ParentalConsent
                    student = self.lesson.student
                    if student:
                        consent = self.db.query(ParentalConsent).filter(
                            ParentalConsent.student_id == student.id,
                        ).first()
                        if consent and consent.parent_telegram_chat_id:
                            await notify_homework_sent(
                                parent_chat_id=consent.parent_telegram_chat_id,
                                student_name=student.full_name,
                                topic_name=self.lesson.topic.name if self.lesson.topic else "урок",
                                teacher_name=self.lesson.teacher.full_name,
                            )
                except Exception:
                    pass
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

    def _load_teaching_style(self) -> str:
        """Загрузить кастомный стиль преподавания из профиля."""
        try:
            from src.models.training import TeachingProfile
            profile = self.db.query(TeachingProfile).filter(
                TeachingProfile.teacher_id == self.lesson.teacher_id
            ).first()
            if profile and profile.custom_prompt:
                logger.info("[runner %s] Загружен профиль стиля: %d видео, %d мин",
                            self.lesson.id, profile.videos_count, profile.total_duration_min)
                return profile.custom_prompt
        except Exception as e:
            logger.debug("[runner %s] Не удалось загрузить профиль стиля: %s", self.lesson.id, e)
        return ""

    async def _mark_failed(self, reason: str) -> None:
        if self.session:
            self.session.status        = SessionStatus.FAILED
            self.session.error_message = reason
        self.lesson.status = LessonStatus.CANCELLED
        self._log_event("error", {"reason": reason})
        try:
            self.db.commit()
        except Exception as e:
            logger.error("[runner %s] Failed to commit after mark_failed: %s", self.lesson.id, e)

    async def _save_recording(self, wav_data: bytes) -> None:
        """Сохранить запись аудио урока в S3."""
        try:
            import sys as _sys, os as _os
            _sys.path.insert(0, _os.path.abspath(_os.path.join(
                _os.path.dirname(__file__), '..', '..', '..', 'backend')))
            from src.utils.s3 import upload_bytes

            lesson_id = str(self.lesson.id)
            key = f"recordings/{lesson_id}/lesson.wav"
            upload_bytes(wav_data, key, content_type="audio/wav")

            # Сохраняем путь в модели урока
            self.lesson.recording_path = key
            self.db.commit()
            logger.info("[runner %s] Запись сохранена в S3: %s (%.1f сек)",
                        self.lesson.id, key, len(wav_data) / 32000)
        except Exception as e:
            logger.error("[runner %s] Ошибка сохранения записи в S3: %s", self.lesson.id, e)

    async def _load_student_progress(self) -> None:
        """Загрузить прогресс ученика из предыдущих уроков."""
        if not hasattr(self._llm, 'get_student_model'):
            return

        student = self.lesson.student
        if not student:
            return

        try:
            # Ищем последний прогресс этого ученика
            progress = (
                self.db.query(StudentProgress)
                .filter(StudentProgress.student_id == student.id)
                .order_by(StudentProgress.created_at.desc())
                .first()
            )

            if progress and progress.student_model_snapshot:
                student_model = self._llm.get_student_model()
                # Восстанавливаем агрегаты из сохранённого прогресса
                snapshot = progress.student_model_snapshot
                student_model.total_correct = snapshot.get("total_correct", 0)
                student_model.total_incorrect = snapshot.get("total_incorrect", 0)
                student_model.overall_confidence = snapshot.get("overall_confidence", 0.5)
                student_model.weak_topics = snapshot.get("weak_topics", [])
                student_model.strong_topics = snapshot.get("strong_topics", [])
                student_model.common_errors = snapshot.get("common_errors", [])
                student_model.total_clarifications = snapshot.get("total_clarifications", 0)
                student_model.total_questions = snapshot.get("total_questions", 0)

                logger.info(
                    "[runner %s] Загружен прогресс ученика: correct=%d incorrect=%d confidence=%.2f weak=%s",
                    self.lesson.id, student_model.total_correct, student_model.total_incorrect,
                    student_model.overall_confidence, student_model.weak_topics,
                )
            else:
                logger.info("[runner %s] Предыдущий прогресс ученика не найден", self.lesson.id)

        except Exception as e:
            logger.warning("[runner %s] Ошибка загрузки прогресса ученика: %s", self.lesson.id, e)

    async def _save_student_progress(self) -> None:
        """Сохранить прогресс ученика для следующего урока."""
        if not hasattr(self._llm, 'get_student_model'):
            return

        student = self.lesson.student
        if not student:
            return

        try:
            student_model = self._llm.get_student_model()
            snapshot = student_model.to_dict()

            progress = StudentProgress(
                student_id=student.id,
                lesson_id=self.lesson.id,
                total_correct=student_model.total_correct,
                total_incorrect=student_model.total_incorrect,
                overall_confidence=student_model.overall_confidence,
                weak_topics=student_model.weak_topics,
                strong_topics=student_model.strong_topics,
                common_errors=student_model.common_errors,
                recommendations=self._llm.get_recommendations(),
                student_model_snapshot=snapshot,
            )
            self.db.add(progress)
            self.db.commit()

            logger.info(
                "[runner %s] Прогресс ученика сохранён: correct=%d incorrect=%d",
                self.lesson.id, student_model.total_correct, student_model.total_incorrect,
            )
        except Exception as e:
            logger.error("[runner %s] Ошибка сохранения прогресса ученика: %s", self.lesson.id, e)

    async def _save_lesson_summary(self) -> None:
        """Сохранить сводку урока в lesson_sessions.summary."""
        if not self.session:
            return
        if not hasattr(self._llm, 'get_student_model'):
            return

        try:
            student_model = self._llm.get_student_model()
            topic_name = self.lesson.topic.name if self.lesson.topic else "химии"
            raw_script = (self.lesson.topic.lesson_script or []) if self.lesson.topic else []
            key_concepts = []
            for step in raw_script:
                key_concepts.extend(step.get("key_concepts", []))

            summary = generate_lesson_summary(
                student_model=student_model,
                topic_name=topic_name,
                topics_covered=list(dict.fromkeys(key_concepts))[:10],
                steps_completed=self.session.current_step or 0,
                total_steps=self.session.total_steps or 0,
            )
            self.session.summary = format_summary_for_db(summary)
            logger.info("[runner %s] Сводка урока сохранена в сессию", self.lesson.id)
        except Exception as e:
            logger.warning("[runner %s] Ошибка сохранения сводки: %s", self.lesson.id, e)
