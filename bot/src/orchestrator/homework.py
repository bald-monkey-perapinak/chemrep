"""
Homework Delivery — отправка домашнего задания после урока.

Стратегии доставки:
  email  — SMTP (через SMTP_HOST / SMTP_USER / SMTP_PASSWORD)
  stub   — логирование без реальной отправки

Логика:
  1. Ищем файл с ролью "homework" среди файлов темы
  2. Формируем письмо с текстом ДЗ и ссылкой/приложением
  3. Отправляем на email ученика (с retry)
  4. Обновляем Homework.delivery_status в БД
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # seconds between retries


# ──────────────────────────────────────────────────────────────────────────
# Формирование письма
# ──────────────────────────────────────────────────────────────────────────

def _build_email(
    student_name:    str,
    teacher_name:    str,
    topic_name:      str,
    hw_description:  Optional[str],
    hw_url:          Optional[str],
    due_date:        Optional[str],
) -> str:
    """Собрать HTML-текст письма."""
    lines = [
        f"<p>Здравствуйте, <b>{student_name}</b>!</p>",
        f"<p>По итогам урока <b>«{topic_name}»</b> ваш преподаватель {teacher_name} выдал домашнее задание.</p>",
    ]

    if hw_description:
        lines.append(f"<h3>Задание:</h3><p>{hw_description}</p>")

    if hw_url:
        lines.append(f'<p><a href="{hw_url}">📎 Открыть материалы</a></p>')

    if due_date:
        lines.append(f"<p><i>Срок выполнения: {due_date}</i></p>")

    lines.append("<p>Удачи!</p>")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Отправка через SMTP
# ──────────────────────────────────────────────────────────────────────────

async def _send_smtp_async(
    to_email: str,
    subject:  str,
    html:     str,
) -> None:
    """Send email via SMTP with async retry logic."""
    host     = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port     = int(os.getenv("SMTP_PORT", "465"))
    user     = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "") or os.getenv("SMTP_PASS", "")

    if not user or not password:
        raise RuntimeError("SMTP_USER и SMTP_PASSWORD не настроены")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            def _send_sync():
                with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as server:
                    server.login(user, password)
                    server.sendmail(user, to_email, msg.as_string())
            await asyncio.to_thread(_send_sync)
            return  # success
        except (smtplib.SMTPException, ConnectionError, OSError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    "[SMTP] Попытка %d/%d не удалась: %s. Повтор через %ds...",
                    attempt + 1, MAX_RETRIES, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("[SMTP] Все %d попыток исчерпаны", MAX_RETRIES)

    raise last_error or RuntimeError("SMTP delivery failed after retries")


# ──────────────────────────────────────────────────────────────────────────
# Основная функция
# ──────────────────────────────────────────────────────────────────────────

async def deliver_homework(db, lesson) -> bool:
    """
    Отправить ДЗ по итогам урока.

    Возвращает True если отправка прошла успешно.
    Обновляет Homework.delivery_status в БД.
    """
    from src.models.homework import Homework, HomeworkDeliveryStatus

    # Нет ученика или email — пропускаем
    student = lesson.student
    if not student or not student.email:
        logger.info("[HW] Нет email у ученика %s — пропускаем ДЗ", lesson.id)
        return False

    # Ищем ДЗ в БД (создаём если нет, но тема содержит homework-файл)
    hw = lesson.homework
    topic = lesson.topic

    if hw is None:
        # Попробуем найти файл с ролью homework в теме
        hw_file = None
        if topic:
            from src.models.knowledge import TopicFile
            hw_file = db.query(TopicFile).filter(
                TopicFile.topic_id == topic.id,
                TopicFile.file_role == "homework",
            ).first()

        if hw_file or (topic and topic.lesson_script):
            hw = Homework(
                lesson_id=lesson.id,
                title=f"Домашнее задание — {topic.name}" if topic else "Домашнее задание",
                external_url=hw_file.storage_path if hw_file else None,
            )
            db.add(hw)
            db.commit()
        else:
            logger.info("[HW] Нет ДЗ для урока %s", lesson.id)
            return False

    stub_mode = os.getenv("HW_STUB_MODE", "false").lower() == "true"

    subject = f"Домашнее задание: {topic.name if topic else 'урок'}"
    html    = _build_email(
        student_name=student.full_name,
        teacher_name=lesson.teacher.full_name,
        topic_name=topic.name if topic else "урок",
        hw_description=hw.description,
        hw_url=hw.external_url,
        due_date=hw.due_date.strftime("%d.%m.%Y") if hw.due_date else None,
    )

    if stub_mode:
        logger.info("[HW-stub] Письмо для %s: %s", student.email, subject)
        hw.delivery_status = HomeworkDeliveryStatus.SENT
        hw.sent_at         = datetime.now(timezone.utc)
        hw.delivery_channel = "email_stub"
        db.commit()
        return True

    try:
        await _send_smtp_async(to_email=student.email, subject=subject, html=html)
        hw.delivery_status  = HomeworkDeliveryStatus.SENT
        hw.sent_at          = datetime.now(timezone.utc)
        hw.delivery_channel = "email"
        db.commit()
        logger.info("[HW] ДЗ отправлено на %s", student.email)

        # Telegram notification if parent chat_id is available
        try:
            from src.orchestrator.notifier import notify_homework_sent
            from src.models.consent import ParentalConsent
            consent = db.query(ParentalConsent).filter(
                ParentalConsent.student_id == student.id,
            ).first()
            if consent and consent.parent_telegram_chat_id:
                await notify_homework_sent(
                    parent_chat_id=consent.parent_telegram_chat_id,
                    student_name=student.full_name,
                    topic_name=topic.name if topic else "урок",
                    teacher_name=lesson.teacher.full_name,
                )
        except Exception:
            pass

        return True

    except Exception as e:
        logger.error("[HW] Ошибка отправки на %s: %s", student.email, e)
        hw.delivery_status = HomeworkDeliveryStatus.FAILED
        hw.delivery_error  = str(e)
        db.commit()
        return False
