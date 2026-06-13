#!/bin/bash
set -euo pipefail

# Backup MinIO data
BACKUP_DIR="./backups/minio"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/minio_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

# Copy MinIO data directory
docker cp chemrep-minio:/data /tmp/minio-backup
tar -czf "$BACKUP_FILE" -C /tmp minio-backup
rm -rf /tmp/minio-backup

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "MinIO backup completed: $BACKUP_FILE"
