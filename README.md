# ⚗️ ХимТьютор — Ассистент-репетитор по химии

Сервис для проведения автоматизированных онлайн-уроков с ИИ-ассистентом на основе голоса преподавателя.

## Архитектура

```
chemrep/
├── frontend/       # React-приложение (кабинет преподавателя)
├── backend/        # REST API (Node.js / FastAPI)
├── bot/            # Бот-участник конференций (аудио, диалог, Miro)
├── docs/           # Документация, схемы, ADR
├── scripts/        # Скрипты развёртывания и утилиты
└── infra/          # Docker, Nginx, CI/CD конфиги
```

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/bald-monkey-perapinak/chemrep.git
cd chemrep

# 2. Запустить через Docker Compose
docker-compose up --build
```

## Стек технологий

| Слой | Технология |
|------|-----------|
| Frontend | React 18, Vite, Zustand |
| Backend | Node.js / Express или Python / FastAPI |
| Bot | Python, WebRTC / virtual audio |
| TTS/ASR | ElevenLabs / Silero / Whisper |
| LLM | Claude API (Anthropic) |
| База данных | PostgreSQL + Redis |
| Хранилище файлов | S3-совместимое (MinIO / AWS S3) |
| Интеграции | Zoom SDK, Miro API, Яндекс Телемост |

## Документация

- [Описание проекта](docs/project-description.md)
- [Архитектурные решения](docs/architecture.md)
- [API Reference](docs/api.md)
- [Настройка бота](bot/README.md)
