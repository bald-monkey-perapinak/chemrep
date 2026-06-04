# VCS-интеграция (Zoom / Яндекс Телемост)

Модуль отвечает за подключение бота к видеоконференции, управление
микрофоном и захват входящего аудио.

## Архитектура

```
src/vcs/
├── client.py   — BaseVCSClient, StubVCSClient, фабрика make_vcs_client()
├── base.py     — PlaywrightVCSBase: браузер + аудио-мост (WebAudio API)
├── zoom.py     — ZoomClient   (Zoom Web Client)
└── yandex.py  — YandexClient (Яндекс Телемост)
```

### Принцип работы

Zoom и Яндекс Телемост не предоставляют публичных серверных SDK.
Бот использует **бесголовной Chromium (Playwright)**: открывает страницу
конференции, нажимает нужные кнопки и передаёт аудио через Web Audio API.

```
Python (PCM bytes)
    → asyncio.Queue
    → AudioWorklet "bot-mic-processor"  (подмена getUserMedia)
    → WebRTC MediaStream конференции

Remote audio конференции
    → RTCPeerConnection ontrack
    → AudioWorklet "bot-capture-processor"
    → CDP expose_function "__botRecvAudio"
    → asyncio.Queue
    → Python (PCM bytes)
```

### Аудио-формат

| Параметр | Значение |
|----------|----------|
| Кодек | PCM 16-bit signed |
| Частота дискретизации | 16 000 Гц |
| Каналы | 1 (mono) |
| Размер фрейма | 320 байт = 20 мс |

---

## Режимы работы

### Stub-режим (разработка / CI)

```env
VCS_STUB_MODE=true
```

`StubVCSClient` — логирует вызовы, реального браузера не запускает.
Включается автоматически если `playwright` не установлен.

### Реальный режим (продакшн)

```env
VCS_STUB_MODE=false   # или не задавать
```

Требует установленного Playwright и браузера Chromium.

---

## Установка

### Linux / Docker

```bash
pip install playwright==1.44.0
playwright install chromium
playwright install-deps chromium   # системные зависимости
```

Для headless-сервера без X11:

```bash
apt-get install -y xvfb
# Запуск с виртуальным дисплеем:
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99
python -m src.orchestrator.main
```

Или через Docker — в `Dockerfile` уже настроено (см. `infra/`).

### Windows

```cmd
pip install playwright==1.44.0
playwright install chromium
python -m src.orchestrator.main
```

На Windows виртуальный дисплей не нужен — Chromium работает в headless-режиме нативно.

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `VCS_STUB_MODE` | `false` | `true` — всегда использовать заглушку |
| `VCS_CONNECT_TIMEOUT` | `60` | Таймаут подключения к конференции (сек) |

---

## Поддерживаемые форматы ссылок

**Zoom:**
```
https://zoom.us/j/123456789?pwd=ABCDEF
https://us06web.zoom.us/j/123456789?pwd=ABCDEF
https://zoom.us/j/123456789        # без пароля
```

**Яндекс Телемост:**
```
https://telemost.yandex.ru/j/ROOM_CODE
```

---

## Добавление новой платформы

1. Создать `src/vcs/myplatform.py` — наследоваться от `PlaywrightVCSBase`
2. Переопределить `_join_conference()` и `_leave_conference()`
3. Добавить `VCSPlatformType.MYPLATFORM` в `client.py`
4. Добавить ветку в `make_vcs_client()`

---

## Тесты

```bash
cd bot
pytest tests/test_vcs.py -v
```

Тесты не требуют браузера (`VCS_STUB_MODE=true` выставляется автоматически).

---

## Известные ограничения

- **Zoom** периодически обновляет CSS-селекторы веб-клиента. При поломке
  входа — обновить константы в классе `ZoomSel` в `zoom.py`.
- **Яндекс Телемост** может потребовать авторизацию Яндекс-аккаунта для
  организатора; гостевой вход работает без аккаунта.
- Chromium в headless-режиме потребляет ~300–500 МБ RAM на каждую сессию.
  При 5 одновременных уроках нужно ~2–3 ГБ.
