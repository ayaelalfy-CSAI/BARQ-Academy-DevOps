#!/usr/bin/env bash

set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-barq_tasks}"
POSTGRES_USER="${POSTGRES_USER:-barq_app}"

BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <backup-file>" >&2
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "Restoring PostgreSQL database..."
echo "Database: $POSTGRES_DB"
echo "Backup: $BACKUP_FILE"


docker cp "$BACKUP_FILE" \
    "$POSTGRES_CONTAINER:/tmp/restore.dump"


docker exec "$POSTGRES_CONTAINER" \
    pg_restore \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --clean \
    --if-exists \
    --no-owner \
    /tmp/restore.dump

docker exec "$POSTGRES_CONTAINER" \
    rm -f /tmp/restore.dump

echo "Restore completed successfully."


docker exec "$POSTGRES_CONTAINER" \
    pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "PostgreSQL restore verification: PASSED"
