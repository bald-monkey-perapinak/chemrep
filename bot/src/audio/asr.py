"""
ASR (Automatic Speech Recognition) — распознавание речи ученика.

Pipeline:
  1. VAD (Voice Activity Detection) — webrtcvad определяет, когда ученик говорит.
     Это позволяет не гонять Whisper на тишине и экономить CPU.
  2. Буферизация активных фреймов.
  3. Whisper (faster-whisper) — транскрибирует накопленный сегмент речи.

Класс ASRPipeline запускается как корутина поверх VCS recv_audio():
  async for text in asr.listen(vcs_client):
      ...  # text — распознанная фраза ученика

Параметры:
  model_size:      tiny / base / small / medium / large-v3
                   На CPU рекомендуется "base" (140 МБ, ~1.5x realtime).
  language:        "ru" — только русский (быстрее, точнее)
  vad_aggressiveness: 0–3 (3 — максимальная чувствительность к голосу)
  silence_ms:      сколько мс тишины считать концом фразы (по умолчанию 800)
  max_phrase_ms:   максимальная длина одной фразы (по умолчанию 15 000)
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# Аудиоформат (должен совпадать с VCS и TTS)
SAMPLE_RATE  = 16_000
SAMPLE_WIDTH = 2       # 16-bit
FRAME_MS     = 20      # webrtcvad требует 10 / 20 / 30 мс
FRAME_BYTES  = SAMPLE_RATE * SAMPLE_WIDTH * FRAME_MS // 1000  # = 640


# ──────────────────────────────────────────────────────────────────────────
# VAD-обёртка
# ──────────────────────────────────────────────────────────────────────────

class VAD:
    """Тонкая обёртка над webrtcvad с накоплением фреймов."""

    def __init__(self, aggressiveness: int = 2):
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(aggressiveness)
            self._available = True
        except ImportError:
            logger.warning("[VAD] webrtcvad не установлен — VAD отключён (всё считается речью)")
            self._vad = None
            self._available = False

    def is_speech(self, pcm_frame: bytes) -> bool:
        """True, если в фрейме обнаружена речь."""
        if not self._available or len(pcm_frame) != FRAME_BYTES:
            return True  # без VAD считаем всё речью
        try:
            return self._vad.is_speech(pcm_frame, SAMPLE_RATE)
        except Exception:
            return True


# ──────────────────────────────────────────────────────────────────────────
# Буфер фраз
# ──────────────────────────────────────────────────────────────────────────

class PhraseBuffer:
    """
    Накапливает PCM-фреймы, пока ученик говорит.
    Возвращает накопленный PCM когда детектирует паузу (тишину > silence_ms).
    """

    def __init__(self, silence_ms: int = 800, max_phrase_ms: int = 15_000):
        self._silence_frames   = silence_ms // FRAME_MS
        self._max_frames       = max_phrase_ms // FRAME_MS
        self._speech_frames:   list[bytes] = []
        self._silent_count:    int = 0
        self._in_speech:       bool = False

    def push(self, frame: bytes, is_speech: bool) -> Optional[bytes]:
        """
        Добавить фрейм. Возвращает накопленный PCM если фраза завершена,
        иначе None.
        """
        if is_speech:
            self._in_speech = True
            self._silent_count = 0
            self._speech_frames.append(frame)
        else:
            if self._in_speech:
                self._silent_count += 1
                self._speech_frames.append(frame)   # добавляем паузу в буфер

        # Пауза > порога — фраза завершена
        if self._in_speech and self._silent_count >= self._silence_frames:
            return self._flush()

        # Фраза слишком длинная — принудительно сбрасываем
        if len(self._speech_frames) >= self._max_frames:
            return self._flush()

        return None

    def _flush(self) -> bytes:
        pcm = b"".join(self._speech_frames)
        self._speech_frames = []
        self._silent_count  = 0
        self._in_speech     = False
        return pcm

    def reset(self) -> None:
        self._speech_frames = []
        self._silent_count  = 0
        self._in_speech     = False


# ──────────────────────────────────────────────────────────────────────────
# Whisper-транскрибер
# ──────────────────────────────────────────────────────────────────────────

class WhisperTranscriber:
    """
    Обёртка над faster-whisper.
    Модель загружается лениво при первом вызове.
    """

    def __init__(self, model_size: str = "base", language: str = "ru"):
        self._model_size = model_size
        self._language   = language
        self._model      = None
        self._lock       = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._lock:
            if self._model is not None:
                return
            logger.info("[Whisper] Загружаем модель '%s'...", self._model_size)
            self._model = await asyncio.get_running_loop().run_in_executor(
                None, self._load
            )
            logger.info("[Whisper] Модель готова")

    def _load(self):
        try:
            from faster_whisper import WhisperModel
            return WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",   # INT8 квантизация — в 2x быстрее на CPU
            )
        except ImportError:
            raise RuntimeError(
                "faster-whisper не установлен. "
                "Установите: pip install faster-whisper"
            )

    async def transcribe(self, pcm: bytes) -> str:
        """Транскрибировать PCM 16-bit 16kHz mono. Возвращает текст."""
        if len(pcm) < FRAME_BYTES * 5:   # слишком короткий сигнал
            return ""
        await self._ensure_loaded()
        return await asyncio.get_running_loop().run_in_executor(
            None, self._transcribe_sync, pcm
        )

    def _transcribe_sync(self, pcm: bytes) -> str:
        import numpy as np
        import io, wave

        # faster-whisper принимает float32 numpy array или путь к файлу
        # Конвертируем PCM bytes → float32
        samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        audio   = np.array(samples, dtype=np.float32) / 32768.0

        segments, info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=3,
            vad_filter=True,            # встроенный VAD Whisper (доп. фильтрация)
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        if text:
            logger.debug("[Whisper] Распознано: %s", text)
        return text


# ──────────────────────────────────────────────────────────────────────────
# Главный класс пайплайна
# ──────────────────────────────────────────────────────────────────────────

class ASRPipeline:
    """
    Связывает VAD + PhraseBuffer + WhisperTranscriber в единый пайплайн.

    Использование в runner:
        async for phrase in asr.listen(vcs_client, timeout=10.0):
            handle(phrase)
    """

    def __init__(
        self,
        model_size:         str = "base",
        language:           str = "ru",
        vad_aggressiveness: int = 1,
        silence_ms:         int = 900,
        max_phrase_ms:      int = 15_000,
    ):
        self._vad        = VAD(vad_aggressiveness)
        self._buffer     = PhraseBuffer(silence_ms, max_phrase_ms)
        self._transcriber = WhisperTranscriber(model_size, language)
        self._remainder: bytes = b""   # остаток фрейма от предыдущей итерации

    async def listen(
        self,
        vcs_client,
        timeout: float = 10.0,
    ) -> AsyncIterator[str]:
        """
        Читает аудио из vcs_client.recv_audio() до истечения timeout.
        Yield-ит распознанные фразы по мере их завершения.

        Пример:
            async for phrase in asr.listen(vcs, timeout=15.0):
                print("Ученик сказал:", phrase)
        """
        deadline = asyncio.get_running_loop().time() + timeout
        self._buffer.reset()
        raw_buf = b""

        while asyncio.get_running_loop().time() < deadline:
            chunk = await vcs_client.recv_audio()
            if not chunk:
                continue

            raw_buf += chunk

            # Нарезаем на фреймы нужного размера
            while len(raw_buf) >= FRAME_BYTES:
                frame   = raw_buf[:FRAME_BYTES]
                raw_buf = raw_buf[FRAME_BYTES:]

                is_speech = self._vad.is_speech(frame)
                phrase_pcm = self._buffer.push(frame, is_speech)

                if phrase_pcm:
                    text = await self._transcriber.transcribe(phrase_pcm)
                    if text:
                        yield text

    async def transcribe_once(self, pcm: bytes) -> str:
        """Транскрибировать готовый PCM-буфер без streaming."""
        return await self._transcriber.transcribe(pcm)

    async def preload(self) -> None:
        """Заранее загрузить модель Whisper (вызывать при старте бота)."""
        await self._transcriber._ensure_loaded()


# ──────────────────────────────────────────────────────────────────────────
# Заглушка
# ──────────────────────────────────────────────────────────────────────────

class StubASR:
    """Всегда возвращает пустую строку — для тестов и stub-режима."""

    async def listen(self, vcs_client, timeout: float = 10.0) -> AsyncIterator[str]:
        await asyncio.sleep(min(timeout, 1.0))
        return
        yield  # делает функцию генератором

    async def transcribe_once(self, pcm: bytes) -> str:
        return ""

    async def preload(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Фабрика
# ──────────────────────────────────────────────────────────────────────────

def make_asr(
    model_size: str = "base",
    language:   str = "ru",
) -> "ASRPipeline | StubASR":
    import os
    if os.getenv("ASR_STUB_MODE", "false").lower() == "true":
        logger.info("[ASR] stub-режим (ASR_STUB_MODE=true)")
        return StubASR()

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        logger.warning(
            "[ASR] faster-whisper не установлен — используем заглушку. "
            "Установите: pip install faster-whisper"
        )
        return StubASR()

    return ASRPipeline(model_size=model_size, language=language)
