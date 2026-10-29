#!/bin/bash
# Startup script for the AlloyDB Omni VM (runs on every boot; idempotent).
# Data lives on the separate persistent disk "omni-data", so the database survives VM rebuilds.
set -euo pipefail

OMNI_IMAGE="google/alloydbomni:17.10.0"
DATA_DEV="/dev/disk/by-id/google-omni-data"
MOUNT="/mnt/omni"

# 1. Data disk: format on first boot only, then mount.
if ! blkid "$DATA_DEV" >/dev/null 2>&1; then
  mkfs.ext4 -F -m 0 -E lazy_itable_init=0,lazy_journal_init=0 "$DATA_DEV"
fi
mkdir -p "$MOUNT"
mountpoint -q "$MOUNT" || mount -o discard,defaults "$DATA_DEV" "$MOUNT"
grep -q "$DATA_DEV" /etc/fstab || echo "$DATA_DEV $MOUNT ext4 discard,defaults,nofail 0 2" >> /etc/fstab
mkdir -p "$MOUNT/data"

# 2. Docker.
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y docker.io
  systemctl enable --now docker
fi

# 3. AlloyDB Omni: password from Secret Manager (never stored in VM metadata).
if ! docker ps -a --format '{{.Names}}' | grep -qx omni; then
  PW="$(gcloud secrets versions access latest --secret=omni-postgres-password)"
  docker pull "$OMNI_IMAGE"
  docker run -d --name omni --restart unless-stopped \
    -e POSTGRES_PASSWORD="$PW" \
    -p 5432:5432 \
    -v "$MOUNT/data":/var/lib/postgresql/data \
    --shm-size=1g \
    "$OMNI_IMAGE"
else
  docker start omni >/dev/null 2>&1 || true
fi
