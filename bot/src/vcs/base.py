"""
PlaywrightVCSBase — общая база для Zoom и Yandex Telemost клиентов.

Подход: бесголовной Chromium запускается через Playwright, открывает страницу
конференции. Аудио маршрутизируется через два механизма:

  ВЫВОД (бот говорит):
    Python → asyncio.Queue → inject_audio_chunk() → AudioWorklet → MediaStream
    AudioWorklet заменяет getUserMedia, подавая PCM-данные из очереди
    вместо реального микрофона.

  ВВОД (бот слушает):
    AudioWorklet захватывает выходной поток конференции (remote audio),
    сериализует PCM и передаёт обратно в Python через CDP Runtime.evaluate.

Ограничения:
  - Для работы нужен виртуальный дисплей (Xvfb) в Linux/headless
  - Chrome требует --use-fake-ui-for-media-stream для headless-микрофона
  - Реальный Zoom Web Client блокирует headless-браузеры — нужен user-agent
    обычного Chrome + --disable-blink-features=AutomationControlled
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from abc import abstractmethod
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

from src.vcs.client import BaseVCSClient, VCSConnectionInfo

logger = logging.getLogger(__name__)

# Размер очереди аудио-фреймов (PCM 16-bit 16kHz mono, 20ms = 320 байт/фрейм)
AUDIO_QUEUE_MAXSIZE = 100
# Таймаут ожидания появления кнопки в UI (мс)
UI_TIMEOUT = 30_000


# ─── JavaScript: AudioWorklet, который подаёт наш PCM в MediaStream ───────
_INJECTOR_WORKLET_JS = """
class BotMicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._queue = [];
    this._buf   = new Float32Array(128);
    this.port.onmessage = (e) => {
      // e.data — Float32Array одного фрейма
      this._queue.push(e.data);
    };
  }
  process(inputs, outputs) {
    const out = outputs[0][0];
    if (this._queue.length > 0) {
      const frame = this._queue.shift();
      const len = Math.min(frame.length, out.length);
      for (let i = 0; i < len; i++) out[i] = frame[i];
    }
    return true;
  }
}
registerProcessor('bot-mic-processor', BotMicProcessor);
"""

# ─── JavaScript: захватываем remote audio и шлём в Python через CDP ───────
_CAPTURE_WORKLET_JS = """
class BotCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = [];
  }
  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    // Конвертируем Float32 → Int16 и отправляем как base64
    const i16 = new Int16Array(ch.length);
    for (let i = 0; i < ch.length; i++) {
      i16[i] = Math.max(-32768, Math.min(32767, ch[i] * 32768));
    }
    const bytes = new Uint8Array(i16.buffer);
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    this.port.postMessage(btoa(bin));
    return true;
  }
}
registerProcessor('bot-capture-processor', BotCaptureProcessor);
"""


class PlaywrightVCSBase(BaseVCSClient):
    """
    Базовый класс: запускает Chromium, поднимает аудио-мост,
    делегирует платформо-специфичное подключение наследникам.
    """

    def __init__(self, info: VCSConnectionInfo):
        super().__init__(info)
        self._pw:      Optional[Playwright]     = None
        self._browser: Optional[Browser]        = None
        self._ctx:     Optional[BrowserContext] = None
        self._page:    Optional[Page]           = None
        self._send_queue: asyncio.Queue[bytes]  = asyncio.Queue(maxsize=AUDIO_QUEUE_MAXSIZE)
        self._recv_queue: asyncio.Queue[bytes]  = asyncio.Queue(maxsize=AUDIO_QUEUE_MAXSIZE)
        self._audio_task: Optional[asyncio.Task] = None

    # ── Публичный API ──────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=self._chromium_args(),
        )
        self._ctx = await self._browser.new_context(
            permissions=["microphone", "camera"],
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._ctx.new_page()

        # Прячем признаки автоматизации
        await self._page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )

        # Платформо-специфичное подключение
        await self._join_conference()

        # Поднять аудио-мост (подмена микрофона + захват звука)
        await self._setup_audio_bridge()

        self.connected = True
        logger.info("[%s] Подключён к %s", self.__class__.__name__, self.info.link)

    async def disconnect(self) -> None:
        if self._audio_task:
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass

        if self._page:
            try:
                await self._leave_conference()
            except Exception as e:
                logger.warning("[%s] Ошибка при выходе из конференции: %s", self.__class__.__name__, e)

        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

        self.connected = False
        logger.info("[%s] Отключён", self.__class__.__name__)

    async def send_audio(self, pcm_frame: bytes) -> None:
        """Поставить PCM-фрейм (16-bit 16kHz mono) в очередь отправки."""
        try:
            self._send_queue.put_nowait(pcm_frame)
        except asyncio.QueueFull:
            logger.debug("[%s] send_queue переполнена, фрейм сброшен", self.__class__.__name__)

    async def recv_audio(self) -> bytes:
        """Получить PCM-фрейм из очереди входящего аудио (блокирует до 100ms)."""
        try:
            return await asyncio.wait_for(self._recv_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return b""

    # ── Методы для переопределения в наследниках ───────────────────────────

    @abstractmethod
    async def _join_conference(self) -> None:
        """Открыть ссылку, нажать нужные кнопки, войти в комнату."""
        ...

    @abstractmethod
    async def _leave_conference(self) -> None:
        """Нажать «Выйти» или закрыть страницу."""
        ...

    def _chromium_args(self) -> list[str]:
        return [
            "--disable-blink-features=AutomationControlled",
            "--use-fake-ui-for-media-stream",   # разрешить микрофон без UI-диалога
            "--use-fake-device-for-media-stream",  # фиктивное устройство (заменяем JS-ом)
            "--autoplay-policy=no-user-gesture-required",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]

    # ── Аудио-мост ─────────────────────────────────────────────────────────

    async def _setup_audio_bridge(self) -> None:
        """
        1. Регистрируем AudioWorklet, который вставляет PCM из _send_queue в поток конференции.
        2. Запускаем фоновую задачу, которая читает _recv_queue из CDP-событий.
        """
        page = self._page

        # Добавляем worklet-скрипт как blob:// URL через CDP
        injector_b64 = base64.b64encode(_INJECTOR_WORKLET_JS.encode()).decode()
        capture_b64  = base64.b64encode(_CAPTURE_WORKLET_JS.encode()).decode()

        await page.evaluate(f"""
        async () => {{
            const ctx = new AudioContext({{sampleRate: 16000}});

            // ── Worklet для ИНЖЕКЦИИ звука (бот говорит) ──────────────────
            const injBlob = new Blob(
                [atob('{injector_b64}')],
                {{type: 'application/javascript'}}
            );
            await ctx.audioWorklet.addModule(URL.createObjectURL(injBlob));
            const injNode = new AudioWorkletNode(ctx, 'bot-mic-processor');
            injNode.connect(ctx.destination);
            window.__botMicNode = injNode;

            // Переопределяем getUserMedia, чтобы конференция получила наш поток
            const dest = ctx.createMediaStreamDestination();
            injNode.connect(dest);
            const origGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
            navigator.mediaDevices.getUserMedia = async (constraints) => {{
                if (constraints && constraints.audio) return dest.stream;
                return origGUM(constraints);
            }};

            // ── Worklet для ЗАХВАТА звука конференции ─────────────────────
            const capBlob = new Blob(
                [atob('{capture_b64}')],
                {{type: 'application/javascript'}}
            );
            await ctx.audioWorklet.addModule(URL.createObjectURL(capBlob));
            window.__botAudioCtx = ctx;
            window.__botCaptureNode = null;  // подключим позже, когда появится remote stream

            // Перехватываем RTCPeerConnection, чтобы подключить захват к remote track
            const OrigRTC = window.RTCPeerConnection;
            window.RTCPeerConnection = function(...args) {{
                const pc = new OrigRTC(...args);
                pc.addEventListener('track', (e) => {{
                    if (e.track.kind !== 'audio') return;
                    const src = ctx.createMediaStreamSource(new MediaStream([e.track]));
                    const cap = new AudioWorkletNode(ctx, 'bot-capture-processor');
                    cap.port.onmessage = (ev) => window.__botRecvAudio(ev.data);
                    src.connect(cap);
                    cap.connect(ctx.destination);
                    window.__botCaptureNode = cap;
                }});
                return pc;
            }};
            Object.assign(window.RTCPeerConnection, OrigRTC);
            window.RTCPeerConnection.prototype = OrigRTC.prototype;
        }}
        """)

        # Регистрируем callback для входящего аудио
        await page.expose_function("__botRecvAudio", self._on_recv_audio)

        # Фоновая задача: отправляет фреймы из Python-очереди в worklet
        self._audio_task = asyncio.create_task(self._audio_pump_loop())
        logger.debug("[%s] Аудио-мост установлен", self.__class__.__name__)

    async def _audio_pump_loop(self) -> None:
        """Непрерывно передаёт PCM-фреймы из Python → AudioWorklet браузера."""
        page = self._page
        while True:
            try:
                pcm = await asyncio.wait_for(self._send_queue.get(), timeout=0.5)
                # Конвертируем Int16 PCM → Float32 для Web Audio API
                await page.evaluate(
                    """(b64) => {
                        const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
                        const i16   = new Int16Array(bytes.buffer);
                        const f32   = new Float32Array(i16.length);
                        for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
                        window.__botMicNode?.port.postMessage(f32, [f32.buffer]);
                    }""",
                    base64.b64encode(pcm).decode(),
                )
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("[%s] audio_pump_loop: %s", self.__class__.__name__, e)

    def _on_recv_audio(self, b64: str) -> None:
        """Callback: браузер прислал base64(PCM Int16) входящего аудио."""
        try:
            pcm = base64.b64decode(b64)
            self._recv_queue.put_nowait(pcm)
        except (asyncio.QueueFull, Exception):
            pass
