# База данных

PostgreSQL + SQLAlchemy ORM + Alembic (миграции).

## Схема таблиц (ER-диаграмма)

```
teachers
  ├── id (PK, UUID)
  ├── email, hashed_password, full_name
  ├── voice_model_path, voice_model_ready
  └── default_vcs_platform

    │  1:N
    ▼

students                          knowledge_classes
  ├── id (PK, UUID)                 ├── id (PK, UUID)
  ├── teacher_id (FK)               ├── teacher_id (FK → teachers)
  ├── full_name, email, grade       ├── name, grade_number
  └── notes                         └── sort_order

    │  1:N                              │  1:N
    ▼                                   ▼

lessons  ──────────────────────  knowledge_sections
  ├── id (PK, UUID)                 ├── id (PK, UUID)
  ├── teacher_id (FK)               ├── class_id (FK)
  ├── student_id (FK)               └── name, description
  ├── topic_id (FK)
  ├── scheduled_at                      │  1:N
  ├── vcs_platform, vcs_link            ▼
  ├── status                       knowledge_topics
  ├── transcript, recording_path     ├── id (PK, UUID)
  └── homework_sent                  ├── section_id (FK)
                                     ├── name, keywords
    │  1:1                           ├── lesson_script (JSONB)
    ▼                                ├── miro_board_id
lesson_sessions                      └── estimated_duration_min
  ├── id (PK, UUID)
  ├── lesson_id (FK, unique)              │  1:N
  ├── status, current_step               ▼
  ├── dialog_history (JSONB)         topic_files
  └── event_log (JSONB)               ├── id (PK, UUID)
                                      ├── topic_id (FK)
    │  1:1                            ├── original_name
    ▼                                 ├── storage_path (S3)
homeworks                             ├── mime_type, size_bytes
  ├── id (PK, UUID)                   ├── file_role
  ├── lesson_id (FK, unique)          └── extracted_text (для RAG)
  ├── title, description
  ├── file_path / external_url
  └── delivery_status, sent_at
```

## Таблицы

| Таблица | Назначение |
|---------|-----------|
| `teachers` | Аккаунты преподавателей, голосовой профиль |
| `students` | Ученики, привязанные к преподавателю |
| `lessons` | Запланированные и проведённые занятия |
| `lesson_sessions` | Runtime-состояние бота во время урока |
| `knowledge_classes` | Классы (8, 9, 10, 11) |
| `knowledge_sections` | Разделы внутри класса (Органическая химия) |
| `knowledge_topics` | Темы со сценарием урока и привязкой к Miro |
| `topic_files` | Файлы материалов (PDF, DOCX, PNG) → S3 |
| `homeworks` | Домашние задания с трекингом доставки |

## Команды

```bash
cd backend

# Применить миграции
alembic upgrade head

# Создать новую миграцию (после изменения моделей)
alembic revision --autogenerate -m "описание изменений"

# Откатить последнюю миграцию
alembic downgrade -1

# Заполнить демо-данными
python -m src.db.seeds.seed_demo

# Запустить API
uvicorn main:app --reload
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```
DATABASE_URL=postgresql://chemrep:password@localhost:5432/chemrep
```
