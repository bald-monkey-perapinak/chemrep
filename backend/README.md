# Backend — REST API

Серверная часть: авторизация, хранение данных, оркестрация бота.

## Структура

```
src/
├── api/
│   └── routes/         # Маршруты: /auth, /lessons, /knowledge, /sessions
├── services/           # Бизнес-логика (LessonService, KnowledgeService, BotService)
├── models/             # Модели базы данных (ORM)
├── middleware/         # Auth, валидация, логирование
├── utils/              # Хелперы (email, файлы, токены)
└── config/             # Конфигурация (DB, S3, внешние API)
```

## Основные эндпоинты (планируемые)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | /auth/login | Авторизация преподавателя |
| GET | /lessons | Список занятий |
| POST | /lessons | Создать занятие |
| DELETE | /lessons/:id | Удалить занятие |
| GET | /knowledge | Дерево базы знаний |
| POST | /knowledge/folder | Создать папку |
| POST | /knowledge/file | Загрузить файл |
| POST | /sessions/:id/start | Запустить бота на урок |
| POST | /sessions/:id/stop | Остановить сессию |

## Запуск

```bash
npm install
npm run dev
# или
pip install -r requirements.txt && uvicorn main:app --reload
```
