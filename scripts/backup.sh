#!/bin/bash
# ============================================
# TorStream - Backup Script
# ============================================

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting TorStream backup at $(date)"

# PostgreSQL backup
echo "Backing up PostgreSQL..."
docker exec torstream-postgres pg_dump -U torstream -d torstream -F custom > "$BACKUP_DIR/postgres_$TIMESTAMP.dump"

# Redis backup (if available)
echo "Backing up Redis..."
docker exec torstream-redis redis-cli BGSAVE || true
sleep 2
docker cp torstream-redis:/data/dump.rdb "$BACKUP_DIR/redis_$TIMESTAMP.rdb" || echo "Redis backup skipped"

# Video storage backup (metadata only - files are large)
echo "Backing up video metadata..."
docker exec torstream-app tar czf - /app/static/uploads > "$BACKUP_DIR/videos_$TIMESTAMP.tar.gz" || echo "Video backup skipped"

# Compress backup
echo "Compressing backup..."
tar czf "$BACKUP_DIR/torstream_backup_$TIMESTAMP.tar.gz" -C "$BACKUP_DIR" \
    "postgres_$TIMESTAMP.dump" \
    "redis_$TIMESTAMP.rdb" 2>/dev/null || true

# Clean up individual files
rm -f "$BACKUP_DIR/postgres_$TIMESTAMP.dump"
rm -f "$BACKUP_DIR/redis_$TIMESTAMP.rdb"

# Clean old backups
echo "Cleaning old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "torstream_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR/torstream_backup_$TIMESTAMP.tar.gz"
echo "Backup finished at $(date)"
