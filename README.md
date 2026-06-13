# ХимТьютор

Автоматизированные онлайн-уроки по химии. Бот-репетитор подключается к видеоконференции голосом преподавателя, объясняет материал, ведёт интерактивную доску и отвечает на вопросы ученика.

---

## Как это работает

```
1. Преподаватель создаёт урок в кабинете
2. В назначенное время бот подключается к Zoom / Яндекс Телемосту
3. Бот объясняет материал голосом + пишет на интерактивной доске
4. Ученик отвечает — бот слушает, анализирует, отвечает
5. В конце — сводка урока + домашнее задание на почту
```

---

## Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend  │────▶│   Backend    │────▶│  PostgreSQL  │
│  (React)    │     │  (FastAPI)   │     │  + pgvector  │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────▼───────┐
                    │     Bot      │
                    │  (Python)    │
                    └──┬───┬───┬───┘
                       │   │   │
              ┌────────┘   │   └────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │   VCS    │ │  TTS/ASR │ │ Whiteboard│
        │Playwright│ │ Whisper  │ │  (Node.js)│
        └──────────┘ └──────────┘ └──────────┘
```

---

## Стек

| Компонент | Технологии | Стоимость |
|-----------|-----------|-----------|
| Frontend | React 19, Vite, Zustand | — |
| Backend | Python, FastAPI, SQLAlchemy | — |
| Auth | JWT + bcrypt | — |
| Bot VCS | Playwright (Chromium headless) | — |
| Bot LLM | Gemini Flash / DeepSeek / Claude | $0.01-0.10/урок |
| Bot TTS | Piper / Silero (local) | $0 |
| Bot ASR | faster-whisper base (local) | $0 |
| Whiteboard | Node.js, WebSocket, RDKit, KaTeX | — |
| Database | PostgreSQL + pgvector | — |
| Storage | MinIO (S3-совместимый) | — |
| Embeddings | all-MiniLM-L6-v2 (local) | — |

---

## Быстрый старт

### Требования

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/download/win)

### Запуск

```bash
git clone https://github.com/bald-monkey-perapinak/chemrep.git
cd chemrep

# Создать .env файл
copy .env.example .env

# Запустить всё
docker compose up -d
```

### Открыть

| Сервис | URL |
|--------|-----|
| Кабинет преподавателя | http://localhost |
| API (Swagger) | http://localhost:8000/docs |
| Доска | http://localhost:3001 |
| MinIO Console | http://localhost:9001 |

### Данные для входа

| Поле | Значение |
|------|----------|
| Email | `demo@chemrep.ru` |
| Пароль | `Demo1234` |

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | PostgreSQL | `postgresql://chemrep:password@postgres:5432/chemrep` |
| `JWT_SECRET` | Секрет JWT | автогенерация |
| `CORS_ORIGINS` | Разрешённые домены | `http://localhost:3000` |
| `GEMINI_API_KEY` | Google Gemini (LLM) | — |
| `DEEPSEEK_API_KEY` | DeepSeek (LLM) | — |
| `ANTHROPIC_API_KEY` | Claude (LLM) | — |
| `TTS_ENGINE` | Движок TTS | `piper` |
| `ELEVENLABS_API_KEY` | ElevenLabs (TTS) | — |
| `ASR_MODEL_SIZE` | Размер модели Whisper | `base` |
| `EMBEDDING_MODEL` | Модель эмбеддингов | `all-MiniLM-L6-v2` |

### LLM (приоритет)

```
GEMINI_API_KEY → DeepSeek → Claude → Template ($0)
```

### TTS (приоритет)

```
Piper (local) → Silero (local) → ElevenLabs (API)
```

---

## Структура проекта

```
chemrep/
├── frontend/          # React кабинет преподавателя
├── backend/           # FastAPI REST API
├── bot/               # Бот-репетитор (Python)
├── whiteboard/        # Интерактивная доска (Node.js)
├── nginx/             # Reverse proxy
└── docker-compose.yml
```

---

## Компоненты

### Frontend

| Раздел | Описание |
|--------|----------|
| Обзор | Статистика, ближайшие уроки |
| Календарь | Месячная сетка, клик для создания урока |
| Занятия | Таблица уроков, мониторинг в реальном времени |
| Ученики | CRUD учеников |
| База знаний | Дерево классов → разделов → тем, загрузка файлов |
| Настройки | Профиль, клонирование голоса, обучение по видео |

### Backend (42 эндпоинта)

| Группа | Описание |
|--------|----------|
| Auth | JWT регистрация/вход |
| Students | CRUD учеников |
| Lessons | Управление уроками |
| Knowledge | База знаний с загрузкой файлов |
| Sessions | Сессии бота, транскрипты |
| Voice | Клонирование голоса |
| SSE | Мониторинг урока в реальном времени |
| Extract | Извлечение текста из PDF/DOCX |

### Bot

| Компонент | Описание |
|-----------|----------|
| Scheduler | Автозапуск уроков по расписанию |
| LessonRunner | Ведение урока: TTS → Board → LLM → ASR |
| VCS | Playwright: Zoom, Яндекс Телемост |
| TTS | Piper / Silero / ElevenLabs |
| ASR | faster-whisper + VAD |
| LLM | Gemini / DeepSeek / Claude + RAG |
| Board | WebSocket → Whiteboard |

### Whiteboard

| Функция | Описание |
|---------|----------|
| Структурные формулы | RDKit SMILES → SVG |
| Уравнения | KaTeX + mhchem |
| Рукописный текст | Стиль Cursive |
| Рисование | Карандаш, ластик, цвета |
| Прокрутка | Drag, колёсико, кнопки навигации |

---

## Стоимость

### При 3 уроках/день (90 уроков/мес)

| Статья | Стоимость/мес |
|--------|---------------|
| Сервер (Hetzner CX41) | $24 |
| LLM API (Gemini Flash) | $1 |
| TTS (Piper, local) | $0 |
| ASR (Whisper, local) | $0 |
| Embeddings (local) | $0 |
| **Итого** | **$25/мес** |

### Стоимость за урок

| Компонент | Стоимость |
|-----------|-----------|
| LLM | $0.01-0.03 |
| TTS | $0 |
| ASR | $0 |
| **Итого** | **~$0.02/урок** |

---

## Тесты

```bash
cd bot
pytest tests/ -v
```

---

## Лицензия

MIT
