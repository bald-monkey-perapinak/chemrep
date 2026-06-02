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
├── frontend/        # Веб-кабинет преподавателя (React)
├── backend/         # REST API + база данных (Python / FastAPI)
│   └── src/
│       ├── models/  # ORM-модели: teachers, students, lessons, knowledge, homework
│       └── db/      # Миграции Alembic, сиды
├── bot/             # Бот-участник конференций (Python)
│   └── src/
│       ├── orchestrator/  # Запуск сессий по расписанию
│       ├── audio/         # TTS, ASR, шумоподавление
│       ├── dialog/        # LLM + RAG
│       ├── miro/          # Управление доской
│       └── vcs/           # Подключение к Zoom / Телемост
├── infra/           # Docker, Nginx
├── docs/            # Архитектурные решения, схемы
└── scripts/         # Утилиты и скрипты развёртывания
```

---

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 18, Vite, Zustand |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Bot | Python, WebRTC / virtual audio |
| TTS / ASR | ElevenLabs / Silero, Whisper |
| LLM | Claude API (Anthropic) |
| База данных | PostgreSQL + Redis |
| Хранилище файлов | S3 / MinIO |
| Интеграции | Zoom SDK, Miro API, Яндекс Телемост |

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
| `teachers` | Аккаунты преподавателей, голосовой профиль |
| `students` | Ученики, привязанные к преподавателю |
| `lessons` | Запланированные и проведённые занятия |
| `lesson_sessions` | Runtime-состояние бота: шаг, история диалога, лог событий |
| `knowledge_classes` | Уровни (8, 9, 10, 11 класс) |
| `knowledge_sections` | Разделы (Органическая химия, Реакции…) |
| `knowledge_topics` | Темы со сценарием урока и привязкой к Miro |
| `topic_files` | Файлы материалов (PDF, DOCX, PNG) — хранятся в S3 |
| `homeworks` | Домашние задания с трекингом доставки |

---

## Быстрый старт

### Требования

- Docker и Docker Compose
- Git

### 1. Клонировать репозиторий

```bash
git clone https://github.com/bald-monkey-perapinak/chemrep.git
cd chemrep
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Открыть `.env` и заполнить ключи:

```env
ANTHROPIC_API_KEY=sk-ant-...       # Claude API
ELEVENLABS_API_KEY=...             # синтез голоса
MIRO_ACCESS_TOKEN=...              # управление доской
ZOOM_API_KEY=...                   # подключение к конференциям (опционально)
JWT_SECRET=any-random-secret       # для авторизации
```

Остальные значения (DATABASE_URL, Redis, MinIO) уже настроены для локальной Docker-среды и менять их не нужно.

### 3. Запустить все сервисы

```bash
docker-compose up --build
```

Это поднимет: PostgreSQL, Redis, MinIO, Backend API, Frontend, Bot.

### 4. Применить миграции и загрузить демо-данные

В отдельном терминале:

```bash
bash scripts/init_db.sh
```

Скрипт дождётся готовности PostgreSQL, применит миграции и заполнит базу демо-данными (преподаватель, 5 учеников, 6 тем, 7 занятий).

### 5. Открыть интерфейс

| Сервис | URL |
|--------|-----|
| Веб-кабинет преподавателя | http://localhost:3000 |
| API документация (Swagger) | http://localhost:8000/docs |
| MinIO (файловое хранилище) | http://localhost:9001 |

---

## Запуск без Docker (для разработки)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m src.db.seeds.seed_demo
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Bot

```bash
cd bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.orchestrator.main
```

---

## Работа с базой данных

```bash
cd backend

# Применить все миграции
alembic upgrade head

# Создать новую миграцию после изменения моделей
alembic revision --autogenerate -m "описание"

# Откатить последнюю миграцию
alembic downgrade -1

# Загрузить демо-данные заново
python -m src.db.seeds.seed_demo
```

---

## Этапы разработки

- [x] Структура проекта и база данных
- [x] Прототип веб-интерфейса (кабинет преподавателя)
- [ ] Backend REST API (auth, lessons, knowledge, sessions)
- [ ] Интеграция с Zoom / Яндекс Телемост
- [ ] Синтез и распознавание речи (TTS / ASR)
- [ ] LLM-диалог с RAG по базе знаний
- [ ] Управление доской Miro
- [ ] Запись уроков и транскрипты
- [ ] Клонирование голоса преподавателя
