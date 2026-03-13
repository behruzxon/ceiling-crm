#!/usr/bin/env bash
# =============================================================================
# CeilingCRM — PostgreSQL backup script
# =============================================================================
# Creates a gzip-compressed pg_dump backup and deletes backups older than
# RETENTION_DAYS.  Designed to run as a daily cron job on the Docker host.
#
# Usage:
#   ./deploy/scripts/backup.sh                    # uses defaults
#   BACKUP_DIR=/mnt/nfs/backups ./deploy/scripts/backup.sh  # custom dir
#
# Cron example (daily at 03:00):
#   0 3 * * * /opt/ceiling-crm/deploy/scripts/backup.sh >> /var/log/ceiling-crm-backup.log 2>&1
# =============================================================================

set -euo pipefail

# ── Configuration (override via env vars) ────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# DB connection — reads from .env or env vars already set on the host.
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-15432}"
PGUSER="${POSTGRES_USER:-ceilingcrm}"
PGPASSWORD="${POSTGRES_PASSWORD:-}"
PGDATABASE="${POSTGRES_DB:-ceilingcrm}"
export PGPASSWORD

# Docker mode: if the postgres container is running and BACKUP_VIA_DOCKER=1,
# exec pg_dump inside the container instead of requiring pg_dump on the host.
BACKUP_VIA_DOCKER="${BACKUP_VIA_DOCKER:-0}"
DOCKER_CONTAINER="${DOCKER_CONTAINER:-ceiling-crm-postgres-1}"

# ── Derived ──────────────────────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="${PGDATABASE}_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

# ── Preflight ────────────────────────────────────────────────────────────────
mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting backup → ${FILEPATH}"

# ── Dump ─────────────────────────────────────────────────────────────────────
if [ "${BACKUP_VIA_DOCKER}" = "1" ]; then
    docker exec "${DOCKER_CONTAINER}" \
        pg_dump -U "${PGUSER}" -d "${PGDATABASE}" --no-owner --no-acl \
        | gzip > "${FILEPATH}"
else
    pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
        --no-owner --no-acl \
        | gzip > "${FILEPATH}"
fi

# ── Verify ───────────────────────────────────────────────────────────────────
FILESIZE="$(stat -c%s "${FILEPATH}" 2>/dev/null || stat -f%z "${FILEPATH}" 2>/dev/null || echo 0)"
if [ "${FILESIZE}" -lt 100 ]; then
    echo "[$(date -Iseconds)] ERROR: backup file too small (${FILESIZE} bytes), aborting"
    rm -f "${FILEPATH}"
    exit 1
fi

echo "[$(date -Iseconds)] Backup complete: ${FILENAME} ($(( FILESIZE / 1024 )) KB)"

# ── Retention: delete backups older than RETENTION_DAYS ──────────────────────
DELETED="$(find "${BACKUP_DIR}" -name "${PGDATABASE}_*.sql.gz" -type f -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)"
if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date -Iseconds)] Cleaned ${DELETED} backup(s) older than ${RETENTION_DAYS} days"
fi

echo "[$(date -Iseconds)] Done"
