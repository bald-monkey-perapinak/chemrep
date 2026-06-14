"""
AudioPipeline — озвучка текста через TTS + отправка аудио в VCS.

Извлекает логику chunked PCM playback из LessonRunner.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CHUNK_SIZE = 640    # 20 мс PCM @ 16kHz 16-bit mono
SPEAK_PAUSE = 0.018  # пауза между чанками


class AudioPipeline:
    """
    Управляет озвучкой текста: TTS → chunked PCM → VCS send_audio.
    """

    def __init__(self, tts, vcs, dialog_log: list[dict], lesson_id):
        self._tts = tts
        self._vcs = vcs
        self._dialog = dialog_log
        self._lesson_id = lesson_id

    async def speak(self, text: str) -> None:
        """Озвучить текст через TTS и отправить в VCS."""
        if not text.strip():
            return

        logger.info("[runner %s] 🔊 %s", self._lesson_id, text[:100])
        self._dialog.append({
            "role": "bot",
            "text": text,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

        try:
            pcm = await self._tts.synthesize(text)
        except Exception as e:
            logger.error("[runner %s] TTS ошибка: %s", self._lesson_id, e)
            return

        for offset in range(0, len(pcm), CHUNK_SIZE):
            chunk = pcm[offset: offset + CHUNK_SIZE]
            if len(chunk) < CHUNK_SIZE:
                chunk += b"\x00" * (CHUNK_SIZE - len(chunk))
            await self._vcs.send_audio(chunk)
            await asyncio.sleep(SPEAK_PAUSE)
