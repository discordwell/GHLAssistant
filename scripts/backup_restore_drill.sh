#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DRILL_DIR="${ROOT_DIR}/tmp/backup_drill_${STAMP}"
BACKUP_DIR="${DRILL_DIR}/backups"
RESTORE_DIR="${DRILL_DIR}/restored"

mkdir -p "${BACKUP_DIR}" "${RESTORE_DIR}"

echo "Backup/restore drill directory: ${DRILL_DIR}"

copy_db() {
  local src="$1"
  local name="$2"
  if [[ ! -f "${src}" ]]; then
    echo "WARN: missing ${src}, skipping"
    return
  fi
  cp "${src}" "${BACKUP_DIR}/${name}.sqlite3"
  cp "${BACKUP_DIR}/${name}.sqlite3" "${RESTORE_DIR}/${name}.sqlite3"
  echo "OK: copied ${name}"
}

copy_db "${ROOT_DIR}/crm.db" "crm"
copy_db "${ROOT_DIR}/workflows.db" "workflows"
copy_db "${ROOT_DIR}/hiring.db" "hiring"

python3 - <<'PY'
import sqlite3
from pathlib import Path

root = Path("tmp")
drills = sorted(root.glob("backup_drill_*"))
if not drills:
    raise SystemExit("No drill directory found")
drill = drills[-1]
restore = drill / "restored"
checks = {
    "crm": [
        "auth_account",
        "auth_invite",
        "auth_event",
        "auth_session",
        "auth_password_reset",
    ],
    "workflows": [
        "auth_account",
        "auth_invite",
        "auth_event",
        "auth_session",
        "auth_password_reset",
    ],
}
for name, tables in checks.items():
    db_path = restore / f"{name}.sqlite3"
    if not db_path.exists():
        print(f"WARN: {db_path} missing, skipped")
        continue
    conn = sqlite3.connect(db_path)
    try:
        existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    missing = [t for t in tables if t not in existing]
    if missing:
        raise SystemExit(f"FAIL: {name} missing tables after restore: {', '.join(missing)}")
    print(f"OK: {name} restore includes required auth tables")
print("Backup/restore drill passed")
PY

echo "Drill complete: ${DRILL_DIR}"
