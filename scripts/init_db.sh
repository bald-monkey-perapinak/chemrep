#!/bin/bash
# Скрипт первоначальной настройки БД
# Запускается после docker-compose up

set -e

echo "⏳ Ждём готовности PostgreSQL..."
until pg_isready -h "${POSTGRES_HOST:-localhost}" -U "${POSTGRES_USER:-chemrep}"; do
  sleep 1
done

echo "🗄️  Применяем миграции..."
cd /app
alembic upgrade head

echo "🌱 Загружаем демо-данные..."
python -m src.db.seeds.seed_demo

echo "✅ База данных готова!"
