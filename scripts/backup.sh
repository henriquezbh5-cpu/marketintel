#!/usr/bin/env bash
# Logical backup of the Postgres database to S3.
# Usage: ./scripts/backup.sh [retention_days]
set -euo pipefail

RETENTION_DAYS="${1:-30}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="/tmp/marketintel-${TS}.sql.gz"
S3_BUCKET="${BACKUP_BUCKET:?set BACKUP_BUCKET}"
S3_PREFIX="postgres/marketintel"

echo "==> Dumping Postgres → ${DUMP_FILE}"
PGPASSWORD="${POSTGRES_PASSWORD}" \
    pg_dump --format=custom --compress=9 --no-owner --no-acl \
            -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
        | gzip -9 > "$DUMP_FILE"

echo "==> Uploading to s3://${S3_BUCKET}/${S3_PREFIX}/${TS}.sql.gz"
aws s3 cp "$DUMP_FILE" "s3://${S3_BUCKET}/${S3_PREFIX}/${TS}.sql.gz" \
    --storage-class STANDARD_IA \
    --metadata "retention-days=${RETENTION_DAYS}"

echo "==> Pruning backups older than ${RETENTION_DAYS} days"
cutoff="$(date -u -d "-${RETENTION_DAYS} days" +%Y%m%dT000000Z)"
aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" \
    | awk -v cutoff="$cutoff" '$4 < cutoff".sql.gz" {print $4}' \
    | while read -r old; do
        [[ -n "$old" ]] && aws s3 rm "s3://${S3_BUCKET}/${S3_PREFIX}/${old}"
      done

rm -f "$DUMP_FILE"
echo "==> Done."
