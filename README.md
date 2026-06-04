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
│       ├── components/    # Dashboard, Calendar, Lessons, KnowledgeBase
│       ├── store/         # Zustand (состояние приложения)
│       ├── styles/        # Глобальные CSS-переменные
│       └── utils/         # Вспомогательные функции
├── backend/               # REST API (Python / FastAPI)
│   └── src/
│       ├── models/        # ORM-модели: teachers, students, lessons, knowledge, homework
│       ├── db/            # Миграции Alembic, сиды
│       ├── api/
│       │   ├── routes/    # FastAPI-роутеры
│       │   └── schemas/   # Pydantic-схемы
│       └── services/      # Бизнес-логика
├── bot/                   # Бот-участник конференций (Python)
│   └── src/
│       ├── orchestrator/  # Планировщик + исполнитель урока
│       ├── audio/         # TTS (ElevenLabs / Silero) + ASR (Whisper + VAD)
│       └── vcs/           # Подключение к Zoom / Яндекс Телемост (Playwright)
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
| Bot — VCS | Playwright (Chromium), Web Audio API |
| Bot — TTS | ElevenLabs API / Silero (CPU, офлайн) |
| Bot — ASR | faster-whisper (INT8), webrtcvad |
| LLM | Claude API (Anthropic) |
| База данных | PostgreSQL + Redis |
| Хранилище файлов | S3 / MinIO |
| Интеграции | Zoom Web Client, Miro API, Яндекс Телемост |

---

## Что реализовано

### Frontend — кабинет преподавателя

React-приложение (Vite + Zustand), полностью управляется пользователем.

**Страницы:**
- **Обзор** — статистика (занятий сегодня / на неделе, учеников, тем), список ближайших занятий со ссылками
- **Календарь** — месячная сетка с отображением занятий, клик по дню открывает форму создания
- **Занятия** — таблица всех уроков с сортировкой, фильтрацией по статусу, кнопками удаления
- **База знаний** — произвольное дерево папок и тем (без системных папок), загрузка файлов, переименование и удаление любого узла через hover-кнопки

**Компоненты:**
```
src/components/
├── Dashboard/Dashboard.jsx
├── Calendar/Calendar.jsx
├── Lessons/Lessons.jsx
├── KnowledgeBase/
│   ├── KnowledgeBase.jsx   # корневой компонент
│   ├── KbTree.jsx          # рекурсивное дерево с inline-действиями
│   ├── KbDetail.jsx        # панель файлов выбранной темы
│   └── FolderModals.jsx    # модалки создания / переименования / удаления
└── shared/
    ├── Modal.jsx
    ├── NewLessonModal.jsx
    └── Toast.jsx
```

---

### Backend — Knowledge REST API

17 эндпоинтов, все защищены проверкой владельца (преподаватель видит только свои данные).

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/knowledge/classes` | Список классов со своими разделами |
| GET | `/api/knowledge/classes/{id}/tree` | Полное дерево: класс → разделы → темы |
| POST / PATCH / DELETE | `/api/knowledge/classes/{id}` | CRUD класса |
| GET / POST | `/api/knowledge/classes/{id}/sections` | Разделы класса |
| PATCH / DELETE | `/api/knowledge/sections/{id}` | Обновить / удалить раздел |
| GET / POST | `/api/knowledge/sections/{id}/topics` | Темы раздела |
| GET / PATCH / DELETE | `/api/knowledge/topics/{id}` | Тема с файлами |
| POST | `/api/knowledge/topics/{id}/files` | Загрузка файлов (multipart, до 50 МБ) |
| DELETE | `/api/knowledge/files/{id}` | Удалить файл |
| GET | `/api/knowledge/search?q=...` | Поиск по названию, описанию и ключевым словам |

Слои:
- `src/api/schemas/knowledge.py` — Pydantic-схемы (Create / Update / Read)
- `src/services/knowledge.py` — бизнес-логика, проверки владения
- `src/api/routes/knowledge.py` — FastAPI-роутер
- `src/api/deps.py` — зависимость `get_current_teacher` (заглушка JWT, замена на реальный auth)

---

### Bot — автозапуск по расписанию

**Планировщик (`orchestrator/scheduler.py`):**
- Каждые N секунд опрашивает БД на занятия со статусом `SCHEDULED`
- Запускает бота за `BOT_LAUNCH_OFFSET_SEC` (по умолчанию 60 сек) до начала
- Помечает урок `MISSED` если ученик не пришёл в течение `BOT_MISSED_TIMEOUT_SEC` (600 сек)
- Ограничивает количество одновременных сессий (`BOT_MAX_CONCURRENT`, по умолчанию 5)
- Graceful shutdown: при SIGINT/SIGTERM дожидается завершения всех активных задач

**Исполнитель урока (`orchestrator/runner.py`):**

```
SCHEDULED → IN_PROGRESS
  → бот входит в конференцию
  → приветствие
  → шаги сценария: объяснение → вопрос → слушаем ответ
  → прощание
→ COMPLETED (транскрипт, лог событий, история диалога сохранены)
→ CANCELLED / FAILED при ошибке
```

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
- Парсит ссылки вида `zoom.us/j/ID?pwd=PWD` и региональные `us06web.zoom.us/...`

**YandexClient** (`vcs/yandex.py`):
- Открывает `telemost.yandex.ru/j/{room_code}`
- Нажимает «Войти как гость», вводит имя, ждёт готовности комнаты

**Формат аудио:** PCM 16-bit, 16 000 Гц, mono, фреймы по 20 мс (640 байт).

Управление режимами:
- `VCS_STUB_MODE=true` — заглушка без браузера (для CI и разработки)
- playwright не установлен — автоматический откат на заглушку с предупреждением

---

### Bot — TTS / ASR

**TTS (`audio/tts.py`):**

| Бэкенд | Условие включения | Особенности |
|--------|-----------------|-------------|
| `ElevenLabsTTS` | `ELEVENLABS_API_KEY` задан | Клонированный голос через `Teacher.voice_model_path`, модель `eleven_turbo_v2` |
| `SileroTTS` | ключ не задан | Локально, CPU, модель `v4_ru` ~30 МБ, голос `baya` |
| `StubTTS` | `TTS_STUB_MODE=true` | Возвращает тишину нужной длины |

**ASR pipeline (`audio/asr.py`):**
```
vcs.recv_audio()
  → VAD (webrtcvad, 20-мс фреймы) — отсекает тишину
  → PhraseBuffer — буферизует речь, детектирует паузу >800 мс как конец фразы
  → WhisperTranscriber (faster-whisper, модель base, INT8, ~1.5x realtime на CPU)
  → текст фразы → runner
```

- `make_asr()` — автовыбор: `ASR_STUB_MODE=true` → заглушка, нет `faster-whisper` → заглушка с предупреждением
- Whisper предзагружается при старте урока, до входа в конференцию

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
| `teachers` | Аккаунты преподавателей, голосовой профиль (`voice_model_path` — ElevenLabs voice_id) |
| `students` | Ученики, привязанные к преподавателю |
| `lessons` | Запланированные и проведённые занятия |
| `lesson_sessions` | Runtime-состояние: текущий шаг, история диалога, лог событий |
| `knowledge_classes` | Уровни (8, 9, 10, 11 класс) |
| `knowledge_sections` | Разделы (Органическая химия, Реакции…) |
| `knowledge_topics` | Темы со сценарием урока и привязкой к Miro |
| `topic_files` | Файлы материалов (PDF, DOCX, PNG) — хранятся в S3 |
| `homeworks` | Домашние задания с трекингом доставки |

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | `postgresql://chemrep:password@localhost:5432/chemrep` | Строка подключения к PostgreSQL |
| `ELEVENLABS_API_KEY` | — | Ключ ElevenLabs (если не задан — используется Silero) |
| `ANTHROPIC_API_KEY` | — | Claude API (для LLM-диалога, следующий этап) |
| `MIRO_ACCESS_TOKEN` | — | Miro API (следующий этап) |
| `VCS_STUB_MODE` | `false` | `true` — не запускать браузер, использовать заглушку |
| `VCS_CONNECT_TIMEOUT` | `60` | Таймаут подключения к конференции (сек) |
| `TTS_STUB_MODE` | `false` | `true` — TTS возвращает тишину |
| `ASR_STUB_MODE` | `false` | `true` — ASR возвращает пустую строку |
| `SCHEDULER_POLL_INTERVAL` | `30` | Как часто планировщик опрашивает БД (сек) |
| `BOT_LAUNCH_OFFSET_SEC` | `60` | За сколько до урока запускать бота |
| `BOT_MISSED_TIMEOUT_SEC` | `600` | Через сколько пометить урок MISSED |
| `BOT_MAX_CONCURRENT` | `5` | Лимит одновременных сессий |
| `LOG_LEVEL` | `INFO` | Уровень логирования (DEBUG / INFO / WARNING) |

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
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
MIRO_ACCESS_TOKEN=...
JWT_SECRET=any-random-secret
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

Открыть: http://localhost:5173

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

## Тесты (бот)

```cmd
cd bot
pytest tests/ -v
```

Тесты не требуют браузера, API-ключей или БД — все внешние зависимости заменяются заглушками через переменные окружения.

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
- [x] Веб-кабинет преподавателя (React, полное управление структурой)
- [x] Knowledge REST API (17 эндпоинтов, CRUD + загрузка файлов + поиск)
- [x] Автозапуск бота по расписанию (Scheduler + LessonRunner)
- [x] Подключение к Zoom / Яндекс Телемост (Playwright + Web Audio Bridge)
- [x] Синтез речи TTS (ElevenLabs + Silero, PCM 16kHz)
- [x] Распознавание речи ASR (faster-whisper + VAD, streaming pipeline)
- [ ] LLM-диалог с RAG по базе знаний (Claude API)
- [ ] Управление доской Miro
- [ ] Backend REST API: auth, lessons, students, sessions
- [ ] Запись уроков и транскрипты
- [ ] Клонирование голоса преподавателя (ElevenLabs Voice Clone)
