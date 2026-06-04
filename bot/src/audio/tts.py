"""
TTS (Text-to-Speech) — синтез речи.

Поддерживаемые бэкенды:
  ElevenLabsTTS  — облачный API, поддерживает клонирование голоса преподавателя.
                   Требует ELEVENLABS_API_KEY и voice_id.
  SileroTTS      — локальная нейросеть (CPU), не требует API-ключей.
                   Качество ниже, но работает полностью офлайн.
  StubTTS        — тишина (для тестов и stub-режима).

Выбор бэкенда:
  - ELEVENLABS_API_KEY задан → ElevenLabsTTS
  - иначе → SileroTTS (скачивает модель при первом запуске ~30 МБ)
  - TTS_STUB_MODE=true → StubTTS

Выходной формат:
  PCM 16-bit signed, 16 000 Гц, mono (совместимо с VCS-клиентом).
"""

from __future__ import annotations

import asyncio
import io
import logging
import struct
import wave
from abc import ABC, abstractmethod
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Целевой аудиоформат для VCS
TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS    = 1
SAMPLE_WIDTH       = 2  # 16-bit


# ──────────────────────────────────────────────────────────────────────────
# Базовый класс
# ──────────────────────────────────────────────────────────────────────────

class BaseTTS(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Вернуть PCM 16-bit 16kHz mono."""
        ...

    async def close(self) -> None:
        """Освободить ресурсы (соединения, модель)."""
        pass


# ──────────────────────────────────────────────────────────────────────────
# Заглушка
# ──────────────────────────────────────────────────────────────────────────

class StubTTS(BaseTTS):
    """Возвращает тишину нужной длины (100 мс на каждое слово)."""

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        word_count = max(1, len(text.split()))
        duration_ms = word_count * 100
        n_samples = TARGET_SAMPLE_RATE * duration_ms // 1000
        return struct.pack(f"<{n_samples}h", *([0] * n_samples))


# ──────────────────────────────────────────────────────────────────────────
# ElevenLabs
# ──────────────────────────────────────────────────────────────────────────

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"

# Модель: eleven_turbo_v2 — наименьшая задержка, подходит для real-time
ELEVENLABS_MODEL = "eleven_turbo_v2"


class ElevenLabsTTS(BaseTTS):
    """
    Синтез через ElevenLabs API.

    voice_id: ID голоса. Если передан — используется он.
    Если не передан — используется голос по умолчанию ("Rachel").
    Для клонированного голоса преподавателя: передать voice_id из
    Teacher.voice_model_path (после того как клонирование реализовано).
    """

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — нейтральный голос

    def __init__(self, api_key: str, voice_id: Optional[str] = None):
        self._api_key  = api_key
        self._voice_id = voice_id or self.DEFAULT_VOICE_ID
        self._client   = httpx.AsyncClient(
            base_url=ELEVENLABS_BASE,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def synthesize(self, text: str) -> bytes:
        """Запросить MP3 у ElevenLabs, конвертировать в PCM 16kHz."""
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
        except httpx.HTTPStatusError as e:
            logger.error("[ElevenLabs] HTTP %s: %s", e.response.status_code, e.response.text[:200])
            raise
        except Exception as e:
            logger.error("[ElevenLabs] Ошибка синтеза: %s", e)
            raise

    async def close(self) -> None:
        await self._client.aclose()

    def with_voice(self, voice_id: str) -> "ElevenLabsTTS":
        """Вернуть копию клиента с другим голосом (для разных преподавателей)."""
        return ElevenLabsTTS(self._api_key, voice_id)


# ──────────────────────────────────────────────────────────────────────────
# Silero TTS (локально, CPU)
# ──────────────────────────────────────────────────────────────────────────

class SileroTTS(BaseTTS):
    """
    Локальный TTS через Silero Models (PyTorch).
    Модель скачивается автоматически при первом вызове (~30 МБ).

    Требует: torch (CPU-сборка достаточна).
    Язык: русский (v4_ru).
    """

    REPO     = "snakers4/silero-models"
    MODEL    = "v4_ru"
    SPEAKER  = "baya"         # женский голос — ближе к преподавателю
    SAMPLE_RATE = 48_000      # нативная частота Silero

    def __init__(self):
        self._model   = None
        self._lock    = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._lock:
            if self._model is not None:
                return
            logger.info("[Silero] Загружаем модель (первый запуск, ~30 МБ)...")
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
        # audio — float32 tensor [n_samples], конвертируем в PCM 16-bit 16kHz
        pcm_48k = (audio.numpy() * 32767).astype("int16").tobytes()
        return _resample_pcm(pcm_48k, self.SAMPLE_RATE, TARGET_SAMPLE_RATE)


# ──────────────────────────────────────────────────────────────────────────
# Конвертация аудио
# ──────────────────────────────────────────────────────────────────────────

def _mp3_to_pcm16k(mp3_bytes: bytes) -> bytes:
    """
    Конвертирует MP3 → PCM 16-bit 16kHz mono.
    Использует pydub (обёртка над ffmpeg).
    Если ffmpeg не установлен — бросает RuntimeError с подсказкой.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        raise RuntimeError(
            "pydub не установлен. Установите: pip install pydub\n"
            "Также нужен ffmpeg: apt-get install ffmpeg"
        )

    seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    seg = seg.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(TARGET_CHANNELS).set_sample_width(SAMPLE_WIDTH)
    return seg.raw_data


def _resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Простая линейная передискретизация PCM 16-bit mono."""
    if src_rate == dst_rate:
        return pcm

    samples_in = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    ratio      = dst_rate / src_rate
    n_out      = int(len(samples_in) * ratio)
    samples_out = []
    for i in range(n_out):
        src_idx = i / ratio
        lo      = int(src_idx)
        hi      = min(lo + 1, len(samples_in) - 1)
        frac    = src_idx - lo
        val     = int(samples_in[lo] * (1 - frac) + samples_in[hi] * frac)
        samples_out.append(max(-32768, min(32767, val)))

    return struct.pack(f"<{n_out}h", *samples_out)


# ──────────────────────────────────────────────────────────────────────────
# Фабрика
# ──────────────────────────────────────────────────────────────────────────

def make_tts(voice_id: Optional[str] = None) -> BaseTTS:
    """
    Выбирает бэкенд по наличию API-ключа и TTS_STUB_MODE.

    voice_id: если передан — используется как голос ElevenLabs
              (для клонированного голоса преподавателя).
    """
    import os
    if os.getenv("TTS_STUB_MODE", "false").lower() == "true":
        logger.info("[TTS] stub-режим (TTS_STUB_MODE=true)")
        return StubTTS()

    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if api_key:
        logger.info("[TTS] ElevenLabs (voice_id=%s)", voice_id or "default")
        return ElevenLabsTTS(api_key, voice_id)

    logger.info("[TTS] Silero (локальная модель, нет ELEVENLABS_API_KEY)")
    return SileroTTS()
