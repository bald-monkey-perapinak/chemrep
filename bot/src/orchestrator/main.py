"""
Точка входа бота-оркестратора.

Запуск:
    python -m src.orchestrator.main

Или напрямую:
    python bot/src/orchestrator/main.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import os

# Загружаем .env из корня проекта
from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# Добавляем пути
_bot_root = os.path.join(os.path.dirname(__file__), "..", "..")
_backend_root = os.path.join(_bot_root, "..", "backend")
for p in (_bot_root, _backend_root):
    if p not in sys.path:
        sys.path.insert(0, os.path.abspath(p))

from config.settings import config
from src.orchestrator.scheduler import Scheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Заглушить шумные библиотеки
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def main() -> None:
    setup_logging()
    logger = logging.getLogger("bot.main")
    logger.info("=" * 60)
    logger.info("ХимТьютор Bot запущен")
    logger.info("DATABASE_URL: %s", config.database_url.split("@")[-1])  # скрываем пароль
    logger.info("=" * 60)

    scheduler = Scheduler()

    # Обработка сигналов для graceful shutdown
    loop = asyncio.get_running_loop()

    def _handle_signal():
        logger.info("Получен сигнал остановки, завершаем работу...")
        asyncio.create_task(_shutdown(scheduler))

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler
            pass

    try:
        await scheduler.run_forever()
    except asyncio.CancelledError:
        pass
    finally:
        await scheduler.shutdown()
        logger.info("Бот остановлен")


async def _shutdown(scheduler: Scheduler) -> None:
    await scheduler.shutdown()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_event_loop().stop()


if __name__ == "__main__":
    asyncio.run(main())
