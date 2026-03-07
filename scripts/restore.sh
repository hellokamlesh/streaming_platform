#!/bin/bash
# ============================================
# TorStream - Restore Script
# ============================================

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 backups/torstream_backup_20240228_120000.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Starting TorStream restore from $BACKUP_FILE"
echo "WARNING: This will overwrite existing data!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

# Extract backup
EXTRACT_DIR=$(mktemp -d)
echo "Extracting backup to $EXTRACT_DIR..."
tar xzf "$BACKUP_FILE" -C "$EXTRACT_DIR"

# Find backup files
POSTGRES_DUMP=$(find "$EXTRACT_DIR" -name "postgres_*.dump" | head -1)
REDIS_DUMP=$(find "$EXTRACT_DIR" -name "redis_*.rdb" | head -1)

echo "Found:"
echo "  PostgreSQL: $POSTGRES_DUMP"
echo "  Redis: $REDIS_DUMP"

# Restore PostgreSQL
if [ -f "$POSTGRES_DUMP" ]; then
    echo "Restoring PostgreSQL..."
    docker cp "$POSTGRES_DUMP" torstream-postgres:/tmp/restore.dump
    docker exec torstream-postgres pg_restore -U torstream -d torstream --clean --if-exists /tmp/restore.dump || {
        echo "pg_restore failed, trying pg_dump format..."
        docker exec torstream-postgres pg_restore -U torstream -d torstream -F c /tmp/restore.dump
    }
    docker exec torstream-postgres rm /tmp/restore.dump
    echo "PostgreSQL restore completed"
fi

# Restore Redis
if [ -f "$REDIS_DUMP" ]; then
    echo "Restoring Redis..."
    docker cp "$REDIS_DUMP" torstream-redis:/data/dump.rdb
    docker restart torstream-redis
    echo "Redis restore completed"
fi

# Cleanup
rm -rf "$EXTRACT_DIR"

echo "Restore completed!"
echo "Please restart the application if needed: docker-compose restart app"
