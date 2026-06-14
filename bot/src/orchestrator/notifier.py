"""
Telegram Notifier — отправка уведомлений через Telegram Bot API.

Используется для:
  - Уведомления родителей о ДЗ
  - Уведомления преподавателя о проблемах с уроком
  - Статуса обработки видео

Настройка:
  1. Создать бота через @BotFather
  2. Установить TELEGRAM_BOT_TOKEN в .env
  3. Получить chat_id через @userinfobot
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def send_telegram_message(
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    token: Optional[str] = None,
) -> bool:
    """
    Send a message via Telegram Bot API.

    Returns True on success, False on failure.
    """
    token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.debug("[Telegram] No token configured, skipping notification")
        return False

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("[Telegram] Message sent to %s", chat_id)
                return True
            else:
                logger.warning("[Telegram] Failed to send: %s", resp.text[:200])
                return False
    except Exception as e:
        logger.warning("[Telegram] Error sending message: %s", e)
        return False


async def notify_homework_sent(
    parent_chat_id: str,
    student_name: str,
    topic_name: str,
    teacher_name: str,
) -> bool:
    """Notify parent that homework was sent."""
    text = (
        f"<b>Домашнее задание</b>\n\n"
        f"Ученик: <b>{student_name}</b>\n"
        f"Тема: {topic_name}\n"
        f"Преподаватель: {teacher_name}\n\n"
        f"ДЗ отправлено на email. Проверьте почту."
    )
    return await send_telegram_message(parent_chat_id, text)


async def notify_lesson_failed(
    teacher_chat_id: str,
    student_name: str,
    error: str,
) -> bool:
    """Notify teacher about a failed lesson."""
    text = (
        f"<b>Ошибка урока</b>\n\n"
        f"Ученик: {student_name}\n"
        f"Ошибка: {error[:200]}\n\n"
        f"Проверьте логи для подробностей."
    )
    return await send_telegram_message(teacher_chat_id, text)


async def notify_video_processed(
    teacher_chat_id: str,
    video_name: str,
    status: str,
) -> bool:
    """Notify teacher about video processing completion."""
    emoji = "✅" if status == "ready" else "❌"
    text = f"{emoji} Видео <b>{video_name}</b> обработано: {status}"
    return await send_telegram_message(teacher_chat_id, text)
