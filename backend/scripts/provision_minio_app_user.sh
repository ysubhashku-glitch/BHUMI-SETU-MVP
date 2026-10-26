#!/usr/bin/env bash
# ==============================================================================
# BhumiSetu MinIO Least-Privilege Application User Provisioning Script
# ==============================================================================
# Creates an unprivileged, scoped application user for FastAPI and Celery workers,
# restricting access strictly to the application's evidence vault bucket.
#
# Usage:
#   MINIO_ROOT_USER="minioadmin" \
#   MINIO_ROOT_PASSWORD="<root_secret>" \
#   AWS_S3_BUCKET="bhumisetu-staging-evidence-vault" \
#   APP_USER="bhumisetu_app" \
#   APP_PASSWORD="<app_secret>" \
#   bash scripts/provision_minio_app_user.sh
# ==============================================================================

set -euo pipefail

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://127.0.0.1:9000}"
BUCKET_NAME="${AWS_S3_BUCKET:-bhumisetu-staging-evidence-vault}"
ROOT_USER="${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
ROOT_PASS="${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"
APP_USER="${APP_USER:-bhumisetu_app}"
APP_PASS="${APP_PASSWORD:?APP_PASSWORD is required for application user}"

POLICY_NAME="bhumisetu_vault_policy"

echo "=== BhumiSetu MinIO Least-Privilege Application User Provisioning ==="
echo "Target Endpoint: ${MINIO_ENDPOINT}"
echo "Target Bucket:   ${BUCKET_NAME}"
echo "Application User: ${APP_USER}"

# 1. Alias MinIO admin endpoint
echo "Configuring MinIO client alias..."
mc alias set staging_minio "${MINIO_ENDPOINT}" "${ROOT_USER}" "${ROOT_PASS}" > /dev/null 2>&1

# 2. Idempotently create target evidence bucket
echo "Ensuring bucket '${BUCKET_NAME}' exists..."
mc mb --ignore-existing "staging_minio/${BUCKET_NAME}" > /dev/null 2>&1

# 3. Create or update application user
echo "Creating/updating application user '${APP_USER}'..."
mc admin user add staging_minio "${APP_USER}" "${APP_PASS}" > /dev/null 2>&1

# 4. Generate least-privilege scoped policy JSON
TMP_POLICY=$(mktemp)
cat <<EOF > "${TMP_POLICY}"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}/*"
      ]
    }
  ]
}
EOF

# 5. Register and attach policy
echo "Registering least-privilege bucket policy '${POLICY_NAME}'..."
mc admin policy create staging_minio "${POLICY_NAME}" "${TMP_POLICY}" > /dev/null 2>&1 || \
mc admin policy update staging_minio "${POLICY_NAME}" "${TMP_POLICY}" > /dev/null 2>&1

echo "Attaching policy to application user '${APP_USER}'..."
mc admin policy attach staging_minio "${POLICY_NAME}" --user "${APP_USER}" > /dev/null 2>&1

rm -f "${TMP_POLICY}"
echo "[OK] Dedicated MinIO application user '${APP_USER}' provisioned successfully."
echo "Application containers can now authenticate with scoped access when MINIO_DEDICATED_APP_IDENTITY=true."
