"""
Юнит-тесты TTS и ASR модулей.

Запуск:
    cd bot
    pytest tests/test_audio.py -v

Тесты не требуют API-ключей, моделей или браузера:
  TTS_STUB_MODE=true  → StubTTS
  ASR_STUB_MODE=true  → StubASR
"""

import asyncio
import os
import struct
import sys

import pytest

_bot_root = os.path.dirname(os.path.dirname(__file__))
for p in (_bot_root, os.path.join(_bot_root, "..", "backend")):
    p = os.path.abspath(p)
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["TTS_STUB_MODE"] = "true"
os.environ["ASR_STUB_MODE"] = "true"
os.environ["VCS_STUB_MODE"] = "true"


from src.audio.tts import StubTTS, make_tts, _resample_pcm
from src.audio.asr import (
    StubASR, VAD, PhraseBuffer, make_asr,
    FRAME_BYTES, SAMPLE_RATE,
)


# ═══════════════════════════════════════════════════════════════════════════
#  StubTTS
# ═══════════════════════════════════════════════════════════════════════════

class TestStubTTS:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_returns_bytes(self):
        tts = StubTTS()
        pcm = self._run(tts.synthesize("Привет, ученик!"))
        assert isinstance(pcm, bytes)

    def test_empty_text_returns_empty(self):
        tts = StubTTS()
        pcm = self._run(tts.synthesize(""))
        assert pcm == b""

    def test_whitespace_text_returns_empty(self):
        tts = StubTTS()
        pcm = self._run(tts.synthesize("   "))
        assert pcm == b""

    def test_longer_text_produces_more_audio(self):
        tts = StubTTS()
        short = self._run(tts.synthesize("Привет"))
        long_ = self._run(tts.synthesize("Привет, сегодня мы разберём тему Алканы в органической химии"))
        assert len(long_) > len(short)

    def test_output_is_valid_pcm16(self):
        """Длина PCM кратна 2 (16-bit = 2 байта на сэмпл)."""
        tts = StubTTS()
        pcm = self._run(tts.synthesize("Тест"))
        assert len(pcm) % 2 == 0

    def test_close_is_safe(self):
        tts = StubTTS()
        self._run(tts.close())  # не должно бросать


class TestMakeTTS:
    def test_stub_mode_returns_stub(self):
        tts = make_tts()
        assert isinstance(tts, StubTTS)

    def test_voice_id_ignored_in_stub_mode(self):
        tts = make_tts(voice_id="some-voice-id")
        assert isinstance(tts, StubTTS)


# ═══════════════════════════════════════════════════════════════════════════
#  Конвертация PCM
# ═══════════════════════════════════════════════════════════════════════════

class TestResamplePCM:
    def _make_pcm(self, n_samples: int, value: int = 1000) -> bytes:
        return struct.pack(f"<{n_samples}h", *([value] * n_samples))

    def test_same_rate_returns_unchanged(self):
        pcm = self._make_pcm(100)
        result = _resample_pcm(pcm, 16_000, 16_000)
        assert result == pcm

    def test_downsample_48k_to_16k(self):
        """48kHz → 16kHz: длина должна уменьшиться в 3 раза."""
        pcm = self._make_pcm(4800)   # 100ms @ 48kHz
        result = _resample_pcm(pcm, 48_000, 16_000)
        expected_samples = 4800 * 16_000 // 48_000
        actual_samples   = len(result) // 2
        assert abs(actual_samples - expected_samples) <= 2  # допуск ±2 сэмпла

    def test_output_is_valid_int16(self):
        pcm = self._make_pcm(1000)
        result = _resample_pcm(pcm, 48_000, 16_000)
        assert len(result) % 2 == 0
        samples = struct.unpack(f"<{len(result)//2}h", result)
        assert all(-32768 <= s <= 32767 for s in samples)


# ═══════════════════════════════════════════════════════════════════════════
#  VAD
# ═══════════════════════════════════════════════════════════════════════════

class TestVAD:
    def test_wrong_frame_size_returns_true(self):
        """При неверном размере фрейма VAD не должен крашиться — считает речью."""
        vad = VAD(aggressiveness=2)
        result = vad.is_speech(b"\x00" * 100)  # не 640 байт
        assert result is True

    def test_silence_frame_no_crash(self):
        """Корректный фрейм тишины не должен бросать исключение."""
        vad = VAD(aggressiveness=2)
        silence = b"\x00" * FRAME_BYTES
        result = vad.is_speech(silence)
        assert isinstance(result, bool)

    def test_aggressiveness_range(self):
        """Все допустимые значения агрессивности работают без ошибок."""
        for agg in (0, 1, 2, 3):
            vad = VAD(aggressiveness=agg)
            silence = b"\x00" * FRAME_BYTES
            vad.is_speech(silence)


# ═══════════════════════════════════════════════════════════════════════════
#  PhraseBuffer
# ═══════════════════════════════════════════════════════════════════════════

class TestPhraseBuffer:
    def _frame(self) -> bytes:
        return b"\x01\x00" * (FRAME_BYTES // 2)

    def test_no_speech_no_phrase(self):
        buf = PhraseBuffer(silence_ms=200, max_phrase_ms=5000)
        for _ in range(50):
            result = buf.push(self._frame(), is_speech=False)
        assert result is None

    def test_speech_then_silence_returns_pcm(self):
        buf = PhraseBuffer(silence_ms=200, max_phrase_ms=5000)
        # 10 речевых фреймов
        for _ in range(10):
            buf.push(self._frame(), is_speech=True)
        # Тишина > порога (200ms / 20ms = 10 фреймов)
        result = None
        for _ in range(11):
            result = buf.push(self._frame(), is_speech=False)
            if result:
                break
        assert result is not None
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_max_phrase_forces_flush(self):
        buf = PhraseBuffer(silence_ms=5000, max_phrase_ms=200)
        result = None
        for _ in range(20):
            result = buf.push(self._frame(), is_speech=True)
            if result:
                break
        assert result is not None

    def test_reset_clears_state(self):
        buf = PhraseBuffer(silence_ms=200, max_phrase_ms=5000)
        for _ in range(5):
            buf.push(self._frame(), is_speech=True)
        buf.reset()
        # После сброса нет накопленной речи
        result = buf.push(self._frame(), is_speech=False)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════
#  StubASR
# ═══════════════════════════════════════════════════════════════════════════

class TestStubASR:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_transcribe_once_returns_empty(self):
        asr = StubASR()
        result = self._run(asr.transcribe_once(b"\x00" * 1000))
        assert result == ""

    def test_preload_is_safe(self):
        asr = StubASR()
        self._run(asr.preload())

    def test_listen_yields_nothing(self):
        from src.vcs.client import StubVCSClient, VCSConnectionInfo, VCSPlatformType
        asr  = StubASR()
        vcs  = StubVCSClient(VCSConnectionInfo(VCSPlatformType.ZOOM, "https://example.com"))
        phrases = []

        async def collect():
            async for p in asr.listen(vcs, timeout=0.5):
                phrases.append(p)

        self._run(collect())
        assert phrases == []


class TestMakeASR:
    def test_stub_mode_returns_stub(self):
        asr = make_asr()
        assert isinstance(asr, StubASR)
