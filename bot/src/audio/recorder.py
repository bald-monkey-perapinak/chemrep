"""
Audio Recorder — запись аудио урока для сохранения в S3.

Записывает PCM-фреймы из VCS-бриджей и бота в WAV-файл.
Поддерживает запись как входящего аудио (ученик + бот), так и только бота.

Формат: WAV 16-bit PCM, 16 kHz, mono.
"""

from __future__ import annotations

import asyncio
import io
import logging
import struct
import wave
from typing import Optional

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


class AudioRecorder:
    """
    Записывает PCM-фреймы в WAV-буфер.
    Используется во время урока для записи аудио.
    """

    def __init__(self):
        self._frames: list[bytes] = []
        self._recording = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Начать запись."""
        async with self._lock:
            self._frames.clear()
            self._recording = True
        logger.info("[Recorder] Запись начата")

    async def stop(self) -> None:
        """Остановить запись."""
        async with self._lock:
            self._recording = False
        logger.info("[Recorder] Запись остановлена (%d фреймов)", len(self._frames))

    async def write_frame(self, pcm_frame: bytes) -> None:
        """Записать PCM-фрейм (16-bit, 16kHz, mono, 20ms = 640 байт)."""
        if not self._recording:
            return
        async with self._lock:
            self._frames.append(pcm_frame)

    def is_recording(self) -> bool:
        return self._recording

    def get_wav_bytes(self) -> bytes:
        """Конвертировать записанные фреймы в WAV-файл (bytes)."""
        if not self._frames:
            return b""

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            for frame in self._frames:
                wf.writeframes(frame)

        wav_data = buf.getvalue()
        duration_sec = len(self._frames) * 0.02  # 20ms per frame
        logger.info(
            "[Recorder] WAV создан: %.1f сек, %d байт",
            duration_sec, len(wav_data),
        )
        return wav_data

    def get_duration_sec(self) -> float:
        """Длительность записи в секундах."""
        return len(self._frames) * 0.02

    def clear(self) -> None:
        """Очистить буфер."""
        self._frames.clear()
