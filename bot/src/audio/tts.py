"""
TTS (Text-to-Speech) — синтез речи.

Стратегия (оптимизация цена/качество):
  1. Piper TTS (local) — быстрый, качественный, $0
  2. Silero TTS (local) — русский голос, $0
  3. ElevenLabs (API) — клонирование голоса, $0.50/урок

Поддерживаемые бэкенды:
  PiperTTS     — локальная модель (CPU), быстрый, качественный.
  SileroTTS    — локальная модель (CPU), русский голос "baya".
  ElevenLabsTTS — облачный API, клонирование голоса.
  StubTTS      — тишина (для тестов).

Фабрика (приоритет):
  - TTS_ENGINE=piper → PiperTTS
  - TTS_ENGINE=silero → SileroTTS
  - ELEVENLABS_API_KEY → ElevenLabsTTS
  - нет → PiperTTS (local, $0)
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import struct
from abc import ABC, abstractmethod
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Целевой аудиоформат для VCS
TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit


# ──────────────────────────────────────────────────────────────────────────
# Базовый класс
# ──────────────────────────────────────────────────────────────────────────

class BaseTTS(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Вернуть PCM 16-bit 16kHz mono."""
        ...

    async def close(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Заглушка
# ──────────────────────────────────────────────────────────────────────────

class StubTTS(BaseTTS):
    """Тишина нужной длины."""

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        word_count = max(1, len(text.split()))
        duration_ms = word_count * 100
        n_samples = TARGET_SAMPLE_RATE * duration_ms // 1000
        return struct.pack(f"<{n_samples}h", *([0] * n_samples))


# ──────────────────────────────────────────────────────────────────────────
# Piper TTS — быстрый, качественный, $0
# ──────────────────────────────────────────────────────────────────────────

class PiperTTS(BaseTTS):
    """
    Локальный TTS через Piper.
    Установка: pip install piper-tts
    Модели скачиваются автоматически (~20-50MB).
    Скорость: ~0.05-0.1 сек на фразу (в 10x быстрее ElevenLabs).
    """

    def __init__(self, model: str = "ru_RU-irina-medium", speaker: int = 0):
        self._model = model
        self._speaker = speaker
        self._voice = None
        self._lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._voice is not None:
            return
        async with self._lock:
            if self._voice is not None:
                return
            logger.info("[Piper] Загружаем модель %s...", self._model)
            self._voice = await asyncio.get_event_loop().run_in_executor(
                None, self._load
            )
            logger.info("[Piper] Модель загружена")

    def _load(self):
        try:
            from piper import PiperVoice
            voice = PiperVoice.from_pretrained(self._model)
            return voice
        except ImportError:
            raise RuntimeError(
                "piper-tts не установлен. "
                "Установите: pip install piper-tts"
            )

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        await self._ensure_loaded()
        return await asyncio.get_event_loop().run_in_executor(
            None, self._synth_sync, text
        )

    def _synth_sync(self, text: str) -> bytes:
        import numpy as np
        audio_chunks = []
        for chunk in self._voice.synthesize_stream_raw(text):
            audio_chunks.append(chunk)
        audio = np.concatenate(audio_chunks)
        # Piper выдаёт float32, конвертируем в PCM 16-bit
        pcm = (audio * 32767).astype(np.int16).tobytes()
        # Resample если нужно (Piper обычно 22050Hz)
        return _resample_pcm(pcm, 22050, TARGET_SAMPLE_RATE)


# ──────────────────────────────────────────────────────────────────────────
# Silero TTS — локальный, русский, $0
# ──────────────────────────────────────────────────────────────────────────

class SileroTTS(BaseTTS):
    """
    Локальный TTS через Silero Models.
    Модель: v4_ru (русский).
    Качество среднее, но бесплатный.
    """

    REPO = "snakers4/silero-models"
    MODEL = "v4_ru"
    SPEAKER = "baya"
    SAMPLE_RATE = 48_000

    def __init__(self):
        self._model = None
        self._lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._lock:
            if self._model is not None:
                return
            logger.info("[Silero] Загружаем модель...")
            self._model = await asyncio.get_event_loop().run_in_executor(
                None, self._load_model
            )
            logger.info("[Silero] Модель загружена")

    @staticmethod
    def _load_model():
        import torch
        model, _ = torch.hub.load(
            repo_or_dir=SileroTTS.REPO,
            model="silero_tts",
            language="ru",
            speaker=SileroTTS.MODEL,
            trust_repo=True,
        )
        model.eval()
        return model

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        await self._ensure_loaded()
        return await asyncio.get_event_loop().run_in_executor(
            None, self._synth_sync, text
        )

    def _synth_sync(self, text: str) -> bytes:
        import torch
        with torch.no_grad():
            audio = self._model.apply_tts(
                text=text,
                speaker=self.SPEAKER,
                sample_rate=self.SAMPLE_RATE,
            )
        pcm_48k = (audio.numpy() * 32767).astype("int16").tobytes()
        return _resample_pcm(pcm_48k, self.SAMPLE_RATE, TARGET_SAMPLE_RATE)


# ──────────────────────────────────────────────────────────────────────────
# ElevenLabs — облачный API, клонирование голоса
# ──────────────────────────────────────────────────────────────────────────

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
ELEVENLABS_MODEL = "eleven_turbo_v2"


class ElevenLabsTTS(BaseTTS):
    """
    Синтез через ElevenLabs API.
    Дорогой ($0.50/урок), но поддерживает клонирование голоса.
    """

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

    def __init__(self, api_key: str, voice_id: Optional[str] = None):
        self._api_key = api_key
        self._voice_id = voice_id or self.DEFAULT_VOICE_ID
        self._client = httpx.AsyncClient(
            base_url=ELEVENLABS_BASE,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""

        try:
            resp = await self._client.post(
                f"/text-to-speech/{self._voice_id}",
                json={
                    "text": text,
                    "model_id": ELEVENLABS_MODEL,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True,
                    },
                },
                headers={"Accept": "audio/mpeg"},
            )
            resp.raise_for_status()
            mp3_bytes = resp.content
            return await asyncio.get_event_loop().run_in_executor(
                None, _mp3_to_pcm16k, mp3_bytes
            )
        except Exception as e:
            logger.error("[ElevenLabs] Ошибка: %s", e)
            raise

    async def close(self) -> None:
        await self._client.aclose()

    def with_voice(self, voice_id: str) -> "ElevenLabsTTS":
        return ElevenLabsTTS(self._api_key, voice_id)


# ──────────────────────────────────────────────────────────────────────────
# Конвертация аудио
# ──────────────────────────────────────────────────────────────────────────

def _mp3_to_pcm16k(mp3_bytes: bytes) -> bytes:
    """MP3 → PCM 16-bit 16kHz."""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise RuntimeError("pydub не установлен. Установите: pip install pydub")

    seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    seg = seg.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(TARGET_CHANNELS).set_sample_width(SAMPLE_WIDTH)
    return seg.raw_data


def _resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Простая линейная передискретизация PCM 16-bit mono."""
    if src_rate == dst_rate:
        return pcm

    samples_in = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    ratio = dst_rate / src_rate
    n_out = int(len(samples_in) * ratio)
    samples_out = []
    for i in range(n_out):
        src_idx = i / ratio
        lo = int(src_idx)
        hi = min(lo + 1, len(samples_in) - 1)
        frac = src_idx - lo
        val = int(samples_in[lo] * (1 - frac) + samples_in[hi] * frac)
        samples_out.append(max(-32768, min(32767, val)))

    return struct.pack(f"<{n_out}h", *samples_out)


# ──────────────────────────────────────────────────────────────────────────
# Фабрика
# ──────────────────────────────────────────────────────────────────────────

def make_tts(voice_id: Optional[str] = None) -> BaseTTS:
    """
    Выбор бэкенда по приоритету (цена/качество):
      1. TTS_STUB_MODE=true → StubTTS
      2. TTS_ENGINE=piper → PiperTTS ($0, быстрый)
      3. TTS_ENGINE=silero → SileroTTS ($0, русский)
      4. ELEVENLABS_API_KEY → ElevenLabsTTS ($0.50/урок)
      5. нет → PiperTTS (local, $0)
    """
    if os.getenv("TTS_STUB_MODE", "false").lower() == "true":
        logger.info("[TTS] stub-режим")
        return StubTTS()

    # Приоритет: Piper → Silero → ElevenLabs
    engine = os.getenv("TTS_ENGINE", "").lower()

    if engine == "piper":
        logger.info("[TTS] Piper (local, $0)")
        return PiperTTS()

    if engine == "silero":
        logger.info("[TTS] Silero (local, $0)")
        return SileroTTS()

    # Проверяем ElevenLabs
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if api_key:
        logger.info("[TTS] ElevenLabs (API, $0.50/урок)")
        return ElevenLabsTTS(api_key, voice_id)

    # По умолчанию — Piper (local, $0)
    logger.info("[TTS] Piper (local, $0) — нет API ключей")
    return PiperTTS()
