#!/usr/bin/env bash

set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-barq_tasks}"
POSTGRES_USER="${POSTGRES_USER:-barq_app}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/postgres_${POSTGRES_DB}_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

echo "Creating PostgreSQL backup..."
echo "Database: $POSTGRES_DB"
echo "Container: $POSTGRES_CONTAINER"
echo "Output: $BACKUP_FILE"

docker exec "$POSTGRES_CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
    > "$BACKUP_FILE"

echo "Backup completed successfully."


if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file is empty." >&2
    exit 1
fi

echo "Backup size:"
du -h "$BACKUP_FILE"

echo "Backup file:"
ls -lh "$BACKUP_FILE"
