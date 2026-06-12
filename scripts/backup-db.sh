#!/bin/bash
# Backup PostgreSQL database
# Usage: ./scripts/backup-db.sh
# Or via cron: 0 3 * * * /path/to/scripts/backup-db.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="chemrep_${TIMESTAMP}.sql.gz"
CONTAINER="chemrep-postgres-1"
DB_USER="chemrep"
DB_NAME="chemrep"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of ${DB_NAME}..."

docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/$FILENAME"

# Keep only last 30 backups
ls -t "$BACKUP_DIR"/chemrep_*.sql.gz | tail -n +31 | xargs -r rm --

echo "[$(date)] Backup saved: $BACKUP_DIR/$FILENAME"
echo "[$(date)] Backups kept: $(ls "$BACKUP_DIR"/chemrep_*.sql.gz 2>/dev/null | wc -l)"
