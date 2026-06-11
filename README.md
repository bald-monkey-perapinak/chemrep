# Ассистент-репетитор по химии

Сервис для проведения автоматизированных онлайн-уроков. Виртуальный ассистент подключается к видеоконференции голосом реального преподавателя, объясняет материал по конспекту, управляет доской Miro и отвечает на вопросы ученика в реальном времени.

---

## Как это работает

1. Преподаватель загружает материалы в базу знаний и назначает занятие
2. В назначенное время бот автоматически подключается к Zoom или Яндекс Телемосту
3. Ученик слышит голос преподавателя и видит интерактивную доску Miro
4. Бот ведёт урок по конспекту, отвечает на вопросы и в конце отправляет домашнее задание

---

## Архитектура

```
chemrep/
├── frontend/              # Веб-кабинет преподавателя (React + Vite)
│   └── src/
│       ├── components/    # Dashboard, Calendar, Lessons, KnowledgeBase, Students, shared/
│       ├── pages/         # LoginPage, Settings
│       ├── hooks/         # useSSE (SSE-подписка)
│       ├── store/         # Zustand (состояние + API-вызовы)
│       ├── styles/        # Глобальные CSS-переменные
│       └── utils/         # api.js (fetch-клиент), helpers.js
├── backend/               # REST API (Python / FastAPI)
│   └── src/
│       ├── models/        # ORM-модели: teachers, students, lessons, knowledge, homework
│       ├── db/            # Миграции Alembic, сиды
│       ├── api/
│       │   ├── routes/    # auth, knowledge, students, lessons, sessions, voice, sse
│       │   └── schemas/   # Pydantic-схемы
│       ├── events/        # EventBus (asyncio pub/sub для SSE)
│       └── services/      # Бизнес-логика knowledge
├── bot/                   # Бот-участник конференций (Python)
│   └── src/
│       ├── orchestrator/  # Scheduler + LessonRunner + homework delivery
│       ├── audio/         # TTS (ElevenLabs / Silero) + ASR (Whisper + VAD)
│       ├── vcs/           # Playwright: Zoom Web Client, Яндекс Телемост
│       ├── dialog/        # RAG retriever + Claude dialog engine
│       └── miro/          # Miro REST API v2 client
├── infra/                 # Docker, Nginx
├── docs/                  # Архитектурные решения, схемы
└── scripts/               # Утилиты и скрипты развёртывания
```

---

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 19, Vite, Zustand |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Bot — VCS | Playwright (Chromium), Web Audio API |
| Bot — TTS | ElevenLabs API / Silero (CPU, офлайн) |
| Bot — ASR | faster-whisper (INT8), webrtcvad |
| Bot — LLM | Claude API (claude-haiku-4-5) |
| Bot — Miro | Miro REST API v2 |
| База данных | PostgreSQL + Redis |
| Хранилище файлов | S3 / MinIO |
| Email | SMTP (gmail / любой провайдер) |

---

## Что реализовано

### Frontend — кабинет преподавателя

React-приложение (Vite + Zustand), полностью подключённое к реальному API.

**Авторизация:**
- Страница входа и регистрации (`LoginPage`)
- JWT-токен хранится в `localStorage`, автоматически подставляется в заголовки
- Auth guard: без токена — редирект на страницу входа
- Кнопка выхода в сайдбаре

**Страницы и компоненты:**

| Раздел | Что делает |
|--------|-----------|
| **Обзор** | Статистика занятий сегодня/на неделе, список учеников, тем в базе. Ближайшие уроки со статусами и ссылками |
| **Календарь** | Месячная сетка, занятия отображаются по дням и платформе. Клик по дню открывает форму создания с предзаполненной датой |
| **Занятия** | Таблица всех уроков: дата, ученик, тема, платформа, статус, текущий шаг сессии бота. Удаление через API |
| **Ученики** | Список учеников с классом и email. Модалка добавления с валидацией. Удаление |
| **База знаний** | Произвольное дерево папок/тем (классы → разделы → темы). Hover-кнопки: добавить вложенную папку, добавить тему, переименовать, удалить. Загрузка файлов в тему через API |
| **Настройки** | Заглушка (настройки профиля и клонирование голоса доступны после подключения бэкенда) |

**Стор (`useStore.js`):**
- Навигация между разделами ( Zustand )
- Локальный стейт: занятия, ученики, дерево KB с мутациями: `addLesson`, `deleteLesson`, `addStudent`, `deleteStudent`, `addRootFolder`, `addChildNode`, `renameNode`, `deleteNode`, `addFiles`, `deleteFile`
- Toast-уведомления

**API-клиент (`utils/api.js`):**
Покрывает все 42 эндпоинта: auth (login отправляет form-encoded данные), lessons, students, knowledge (классы/разделы/темы/файлы/поиск), sessions, voice. Автоматический logout при 401.

**SSE-мониторинг (`useSSE.js` + `LessonMonitor.jsx`):**
Подписка на Server-Sent Events для отслеживания урока в реальном времени. Панель показывает: статус подключения, прогресс по сценарию (шаг N/M), последнюю реплику диалога, лог событий с иконками и таймстемпами. Автоскролл к новым событиям. Кнопка вызова мониторинга на уроках со статусами scheduled/in_progress.

**Vite-прокси:**
В dev-режиме запросы `/api/*` проксируются на `localhost:8000` (без CORS-проблем).

---

### Backend — REST API

Всего **42 эндпоинта** в 7 роутерах + health. Все защищены JWT (кроме `/auth/register`, `/auth/login` и `/health`).

**Auth (`/api/auth`):**

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/auth/register` | Создать аккаунт преподавателя |
| POST | `/api/auth/login` | Войти, получить JWT-токен (7 дней) |
| GET  | `/api/auth/me` | Профиль текущего преподавателя |
| PATCH | `/api/auth/me` | Обновить имя, платформу по умолчанию |

Реализация: `python-jose` (HS256), `passlib[bcrypt]`, зависимость `get_current_teacher()` используется всеми защищёнными роутерами.

**Students (`/api/students`):**

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/students` | Список учеников (фильтр по активным) |
| POST | `/api/students` | Добавить ученика (имя, email, класс, заметки) |
| GET | `/api/students/{id}` | Профиль ученика + последние 20 уроков |
| PATCH | `/api/students/{id}` | Обновить данные |
| DELETE | `/api/students/{id}` | Удалить ученика |

**Lessons (`/api/lessons`):**

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/lessons` | Список занятий с фильтрами по статусу, ученику, датам |
| POST | `/api/lessons` | Создать занятие |
| GET | `/api/lessons/{id}` | Занятие + вложенная сессия бота + ДЗ |
| PATCH | `/api/lessons/{id}` | Обновить занятие или его статус |
| DELETE | `/api/lessons/{id}` | Удалить занятие |
| GET | `/api/lessons/{id}/session` | Статус сессии бота (для polling с фронтенда) |
| PATCH | `/api/lessons/{id}/homework` | Создать или обновить ДЗ к занятию |

**Knowledge (`/api/knowledge`):**

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/knowledge/classes` | Список классов со своими разделами |
| GET | `/api/knowledge/classes/{id}/tree` | Полное дерево: класс → разделы → темы |
| POST / PATCH / DELETE | `/api/knowledge/classes/{id}` | CRUD класса |
| GET / POST | `/api/knowledge/classes/{id}/sections` | Разделы класса |
| PATCH / DELETE | `/api/knowledge/sections/{id}` | Обновить / удалить раздел |
| GET / POST | `/api/knowledge/sections/{id}/topics` | Темы раздела |
| GET / PATCH / DELETE | `/api/knowledge/topics/{id}` | Тема с файлами |
| POST | `/api/knowledge/topics/{id}/files` | Загрузка файлов (multipart, до 50 МБ, валидация MIME) |
| DELETE | `/api/knowledge/files/{id}` | Удалить файл |
| GET | `/api/knowledge/search?q=...` | Поиск по названию, описанию и ключевым словам |

Бизнес-логика в `src/services/knowledge.py`: проверка владения на каждом уровне иерархии, дедупликация файлов по имени, поддерживаемые MIME-типы (PDF, DOCX, XLSX, PNG, JPEG, TXT).

**Sessions (`/api/sessions`):**

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/sessions/{lesson_id}` | Полная сессия: статус, диалог, лог событий |
| GET | `/api/sessions/{lesson_id}/transcript` | Транскрипт урока (plain text) |
| GET | `/api/sessions/{lesson_id}/dialog` | Только реплики (JSON) |

**SSE (`/api/sse`):**

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/sse/lessons/{lesson_id}?token=...` | SSE-поток событий урока в реальном времени |
| GET | `/api/sse/active` | Список уроков с активными подписчиками (отладка) |

JWT-аутентификация через query-параметр (EventSource не поддерживает заголовки). Heartbeat каждые 15 сек. При подключении отправляет текущее состояние сессии. Закрывается при `session_ended` / `session_failed`.

**Voice (`/api/voice`):**

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/voice/status` | Есть ли клонированный голос, готов ли |
| POST | `/api/voice/clone` | Загрузить 1–25 аудиофайлов → ElevenLabs Voice Clone API → сохранить voice_id |
| DELETE | `/api/voice` | Удалить клон из ElevenLabs и из профиля |

---

### Bot — автозапуск по расписанию

**Планировщик (`orchestrator/scheduler.py`):**
- Каждые `SCHEDULER_POLL_INTERVAL` секунд (30) опрашивает БД на занятия со статусом `SCHEDULED`
- Запускает бота за `BOT_LAUNCH_OFFSET_SEC` (60) до начала
- Помечает урок `MISSED` если прошло `BOT_MISSED_TIMEOUT_SEC` (600) и сессия не создана
- Лимит `BOT_MAX_CONCURRENT` (5) одновременных сессий
- Graceful shutdown: при SIGINT/SIGTERM дожидается завершения всех активных asyncio-задач

**Исполнитель урока (`orchestrator/runner.py`):**

```
SCHEDULED → IN_PROGRESS
  1. _prepare()     — создать LessonSession в БД
  2. _init_audio()  — загрузить TTS + Whisper (preload до конференции)
  3. _init_dialog() — создать RAGRetriever + ClaudeDialogEngine
  4. _init_miro()   — подключить MiroClient к доске темы
  5. _connect_vcs() — Playwright → Chromium → Zoom / Телемост
  6. _conduct()     — шаги сценария: _speak() → _miro.execute() → _listen_and_respond()
                    → _free_dialog() (Q&A в конце)
  7. _cleanup()     — deliver_homework() → disconnect VCS → сохранить транскрипт
→ COMPLETED / FAILED
```

**Отправка ДЗ (`orchestrator/homework.py`):**
- Ищет файл с ролью `homework` в теме урока
- Формирует HTML-письмо с описанием и ссылкой
- Отправляет через SMTP (SMTP_HOST / SMTP_USER / SMTP_PASSWORD)
- Обновляет `Homework.delivery_status` → `sent` / `failed`
- `HW_STUB_MODE=true` — только лог без реальной отправки

---

### Bot — VCS (Zoom / Яндекс Телемост)

Браузерная автоматизация через Playwright (Chromium headless).

**Аудио-мост (Web Audio API + CDP):**
```
Python PCM → asyncio.Queue → AudioWorklet "bot-mic-processor"
  → подмена getUserMedia → WebRTC MediaStream конференции

Remote audio конференции → RTCPeerConnection ontrack
  → AudioWorklet "bot-capture-processor" → CDP expose_function
  → asyncio.Queue → Python PCM
```

**ZoomClient** (`vcs/zoom.py`):
- Открывает `app.zoom.us/wc/join/{meeting_id}`
- Вводит имя, выбирает Computer Audio, ждёт тулбар
- Парсит `zoom.us/j/ID?pwd=PWD` и региональные `us06web.zoom.us/...`

**YandexClient** (`vcs/yandex.py`):
- Открывает `telemost.yandex.ru/j/{room_code}`
- Нажимает «Войти как гость», вводит имя, ждёт готовности комнаты

**Формат аудио:** PCM 16-bit, 16 000 Гц, mono, фреймы 20 мс (640 байт).

Управление режимами: `VCS_STUB_MODE=true` — заглушка без браузера. При отсутствии playwright — автооткат на заглушку.

---

### Bot — TTS / ASR

**TTS (`audio/tts.py`):**

| Бэкенд | Условие включения | Особенности |
|--------|-----------------|-------------|
| `ElevenLabsTTS` | `ELEVENLABS_API_KEY` задан | `eleven_turbo_v2`, voice_id из `Teacher.voice_model_path`, MP3 → PCM через pydub+ffmpeg |
| `SileroTTS` | ключ не задан | Локально, CPU, модель `v4_ru` ~30 МБ, голос `baya`, 48kHz → 16kHz ресэмплинг |
| `StubTTS` | `TTS_STUB_MODE=true` | Тишина нужной длины (100 мс/слово) |

**ASR pipeline (`audio/asr.py`):**

```
vcs.recv_audio()
  → VAD (webrtcvad, 20-мс фреймы)      — отсекает тишину, экономит CPU
  → PhraseBuffer                        — буферизует речь, пауза >800 мс = конец фразы
  → WhisperTranscriber                  — faster-whisper base, INT8, ~1.5x realtime на CPU
  → текст фразы
```

Все компоненты с заглушками: `ASR_STUB_MODE=true` или отсутствие `faster-whisper` → `StubASR`.

---

### Bot — LLM-диалог с RAG

**RAG Retriever (`dialog/retriever.py`):**

Ищет релевантные фрагменты из БД по вопросу ученика без векторной БД — через keyword matching:

```
вопрос ученика → _extract_keywords() → _keyword_score() по источникам

Источники (по весу):
  extracted_text файлов темы   ×1.2   ← наивысший приоритет
  шаги lesson_script           ×1.0
  мета темы (name/desc/kw)     ×0.5
  смежные темы раздела         ×0.4   ← только при явном совпадении
```

**Dialog Engine (`dialog/engine.py`):**

| Параметр | Значение |
|----------|----------|
| Модель | `claude-haiku-4-5-20251001` |
| `max_tokens` | 300 (ответы короткие — зачитываются вслух) |
| История | последние N пар user/assistant в каждом запросе |
| RAG | релевантные чанки вставляются в последнее user-сообщение |
| Fallback | при HTTP-ошибке → «повтори вопрос», без краша |

`LLM_STUB_MODE=true` или нет `ANTHROPIC_API_KEY` → `StubDialogEngine` (циклические заглушки).

---

### Bot — Miro (`miro/client.py`)

Управляет доской через Miro REST API v2. `board_id` берётся из `KnowledgeTopic.miro_board_id`.

**Поддерживаемые действия в `lesson_script[].miro_action`:**

| Действие | Описание |
|---------|----------|
| `show_frame:<frame_id>` | Сфокусировать viewport на фрейме |
| `create_sticky:<text>` | Создать жёлтый стикер с текстом |
| `create_text:<text>` | Создать текстовый блок |
| `draw_shape:<shape>:<label>` | Нарисовать фигуру (rectangle/circle/triangle/rhombus) с подписью |
| `highlight:<item_id>` | Выделить элемент красной рамкой |
| `clear_highlights` | Сбросить выделения у всех shapes |
| `zoom_in` / `zoom_out` | Логирует масштабирование (viewport через клиент) |

`MIRO_STUB_MODE=true` или нет токена → `StubMiroClient`.

---

## Схема базы данных

```
teachers
  ├── students          (1:N)
  ├── lessons           (1:N)  →  lesson_sessions (1:1)
  │                             →  homeworks       (1:1)
  └── knowledge_classes (1:N)
        └── knowledge_sections (1:N)
              └── knowledge_topics (1:N)
                    └── topic_files (1:N)
```

| Таблица | Назначение |
|---------|-----------|
| `teachers` | Аккаунты, `hashed_password`, `voice_model_path` (ElevenLabs voice_id), `voice_model_ready` |
| `students` | Ученики: имя, email, телефон, класс, заметки |
| `lessons` | Занятия: `scheduled_at`, `vcs_platform`, `vcs_link`, `status`, `transcript` |
| `lesson_sessions` | Runtime-состояние бота: `current_step`, `dialog_history` (JSON), `event_log` (JSON), `error_message` |
| `knowledge_classes` | Уровни (8–11 класс), `grade_number`, `sort_order` |
| `knowledge_sections` | Разделы внутри класса, `sort_order` |
| `knowledge_topics` | Темы: `lesson_script` (JSON), `miro_board_id`, `estimated_duration_min`, `is_published` |
| `topic_files` | Файлы: `original_name`, `storage_path` (S3), `mime_type`, `size_bytes`, `file_role`, `text_extracted` |
| `homeworks` | ДЗ: `title`, `description`, `file_path`, `delivery_status`, `sent_at`, `due_date` |

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | `postgresql://chemrep:password@localhost:5432/chemrep` | Строка подключения к PostgreSQL |
| `JWT_SECRET` | `change-me-in-production-please` | Секрет для подписи JWT |
| `ANTHROPIC_API_KEY` | — | Claude API (LLM-диалог) |
| `ELEVENLABS_API_KEY` | — | ElevenLabs (TTS + клонирование голоса) |
| `MIRO_ACCESS_TOKEN` | — | Miro REST API v2 |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP-сервер для отправки ДЗ |
| `SMTP_PORT` | `465` | SMTP-порт (SSL) |
| `SMTP_USER` | — | Email отправителя |
| `SMTP_PASSWORD` | — | Пароль / App Password |
| `VCS_STUB_MODE` | `false` | `true` — не запускать браузер |
| `VCS_CONNECT_TIMEOUT` | `60` | Таймаут подключения к конференции (сек) |
| `TTS_STUB_MODE` | `false` | `true` — TTS возвращает тишину |
| `ASR_STUB_MODE` | `false` | `true` — ASR возвращает пустую строку |
| `LLM_STUB_MODE` | `false` | `true` — LLM возвращает заглушки |
| `MIRO_STUB_MODE` | `false` | `true` — Miro не вызывает API |
| `HW_STUB_MODE` | `false` | `true` — ДЗ только логируется, не отправляется |
| `SCHEDULER_POLL_INTERVAL` | `30` | Как часто планировщик опрашивает БД (сек) |
| `BOT_LAUNCH_OFFSET_SEC` | `60` | За сколько до урока запускать бота |
| `BOT_MISSED_TIMEOUT_SEC` | `600` | Через сколько пометить урок MISSED |
| `BOT_MAX_CONCURRENT` | `5` | Лимит одновременных сессий |
| `LOG_LEVEL` | `INFO` | Уровень логирования (DEBUG / INFO / WARNING) |

---

## Тесты

```cmd
cd bot
pytest tests/ -v
```

77 тестов, не требуют браузера, БД или API-ключей. Все внешние зависимости заменяются заглушками через env-переменные.

| Файл | Покрытие |
|------|----------|
| `tests/test_vcs.py` | 19 тестов: парсинг ссылок Zoom/Yandex, фабрика, StubVCSClient lifecycle |
| `tests/test_audio.py` | 22 теста: StubTTS, ресэмплинг PCM, VAD, PhraseBuffer, StubASR, фабрики |
| `tests/test_dialog.py` | 36 тестов: RAG keyword scoring, PhraseBuffer, StubDialogEngine, _build_messages, _extract_reply |

---

## Быстрый старт (Docker, Windows)

### Требования

- [Docker Desktop для Windows](https://www.docker.com/products/docker-desktop/) — при установке согласиться включить WSL 2
- [Git для Windows](https://git-scm.com/download/win)

После установки запустить Docker Desktop и дождаться значка кита в трее без анимации.

### 1. Клонировать репозиторий

```cmd
git clone https://github.com/bald-monkey-perapinak/chemrep.git
cd chemrep
```

### 2. Настроить переменные окружения

```cmd
copy .env.example .env
```

Открыть `.env` и заполнить:

```env
JWT_SECRET=any-random-secret-32chars
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
MIRO_ACCESS_TOKEN=...
SMTP_USER=your@gmail.com
SMTP_PASSWORD=app-password
```

### 3. Запустить

```cmd
docker-compose up --build
```

### 4. Применить миграции

```cmd
docker-compose exec backend bash scripts/init_db.sh
```

### 5. Открыть

| Сервис | URL |
|--------|-----|
| Веб-кабинет | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/docs |
| MinIO | http://localhost:9001 |

---

## Запуск без Docker (Windows)

### Только фронтенд

Требует [Node.js 18+](https://nodejs.org/):

```cmd
cd frontend
npm install
npm run dev
```

Открыть: http://localhost:3000

### Полный стек

Требует [Python 3.11+](https://www.python.org/downloads/) (при установке: галочка **Add Python to PATH**) и запущенных PostgreSQL + Redis.

**Backend:**
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m src.db.seeds.seed_demo
uvicorn main:app --reload --port 8000
```

**Bot:**
```cmd
cd bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python -m src.orchestrator.main
```

На Windows виртуальный дисплей не нужен — Chromium работает в headless-режиме нативно.

---

## Работа с базой данных

```cmd
cd backend
.venv\Scripts\activate

alembic upgrade head                              # применить миграции
alembic revision --autogenerate -m "описание"    # создать миграцию
alembic downgrade -1                              # откатить последнюю
python -m src.db.seeds.seed_demo                 # загрузить демо-данные
```

---

## Этапы разработки

- [x] Структура проекта и схема базы данных
- [x] Веб-кабинет преподавателя (React, авторизация, управление структурой)
- [x] Knowledge REST API (17 эндпоинтов, CRUD + загрузка файлов + поиск)
- [x] Backend REST API: auth (JWT), lessons, students, sessions, voice (22 эндпоинта)
- [x] Фронтенд подключён к реальному API (авторизация, занятия, ученики, KB, настройки)
- [x] Автозапуск бота по расписанию (Scheduler + LessonRunner)
- [x] Подключение к Zoom / Яндекс Телемост (Playwright + Web Audio Bridge)
- [x] Синтез речи TTS (ElevenLabs + Silero, PCM 16kHz)
- [x] Распознавание речи ASR (faster-whisper + VAD, streaming pipeline)
- [x] LLM-диалог с RAG по базе знаний (Claude API + keyword retriever)
- [x] Управление доской Miro (REST API v2, 7 типов действий)
- [x] Отправка домашнего задания по email (SMTP)
- [x] Клонирование голоса преподавателя (ElevenLabs Voice Clone API)
- [x] SSE-мониторинг урока в реальном времени (EventBus → SSE → useSSE hook → LessonMonitor)
- [x] pgvector + embeddings для семантического RAG (sentence-transformers, cosine similarity)
- [x] Реальная загрузка файлов в S3/MinIO (boto3, presigned URLs)
- [x] Извлечение текста из PDF/DOCX (PyPDF2, python-docx) → автоматическая индексация для RAG
- [x] Запись аудио урока и сохранение в S3 (WAV 16-bit PCM, 16kHz)
- [ ] Страница транскрипта и диалога после урока
- [ ] Уведомления преподавателю (push / email) при ошибке бота
- [ ] Страница статистики: успеваемость ученика, покрытие тем
- [ ] Адаптация сложности объяснений по истории ответов ученика
