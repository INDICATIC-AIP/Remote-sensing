#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT_ENV_FILE="$ROOT_DIR/.env"

if [ -f "$ROOT_ENV_FILE" ]; then
  set -a
  source "$ROOT_ENV_FILE"
  set +a
fi

usage() {
  cat <<'EOF'
Usage:
  ./ssh_download.sh <iss|noaa|periodic> [options] [remote_project_dir] [user@host]

ISS Examples:
  ./ssh_download.sh iss                              # Default: Costa Rica, 100 photos
  ./ssh_download.sh iss --limit 50                   # 50 photos
  ./ssh_download.sh iss --region panama --limit 200  # Panama, 200 photos

NOAA Examples:
  ./ssh_download.sh noaa

Periodic Examples:
  ./ssh_download.sh periodic task_1744260000000

Expected .env variables at repository root:
  SSH_HOST=<remote-host-ip>
  SSH_USERNAME=<remote-username>
  SSH_PASSWORD=<remote-password>
  SSH_PORT=22
EOF
}

if [ $# -lt 1 ]; then
  usage
  exit 1
fi

MODE="$1"
shift || true

CLI_OPTIONS=()
REMOTE_PROJECT_DIR=""
REMOTE_TARGET_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --limit|--region|--mode)
      CLI_OPTIONS+=("$1" "$2")
      shift 2
      ;;
    /*)
      REMOTE_PROJECT_DIR="$1"
      shift
      ;;
    *@*)
      REMOTE_TARGET_OVERRIDE="$1"
      shift
      ;;
    *)
      CLI_OPTIONS+=("$1")
      shift
      ;;
  esac
done

# Build safe CLI args string to pass to remote
CLI_ARGS=""
for _arg in "${CLI_OPTIONS[@]:-}"; do
  # skip empty options
  if [ -n "$_arg" ]; then
    # shell-escape each arg
    CLI_ARGS+=" $(printf '%q' "$_arg")"
  fi
done

SSH_HOST_ENV="${SSH_HOST:-}"
SSH_USERNAME_ENV="${SSH_USERNAME:-}"
SSH_PASSWORD_ENV="${SSH_PASSWORD:-}"
SSH_PORT_ENV="${SSH_PORT:-22}"

if [ -n "$REMOTE_TARGET_OVERRIDE" ]; then
  REMOTE_TARGET="$REMOTE_TARGET_OVERRIDE"
elif [ -n "$SSH_HOST_ENV" ] && [ -n "$SSH_USERNAME_ENV" ]; then
  REMOTE_TARGET="$SSH_USERNAME_ENV@$SSH_HOST_ENV"
else
  echo "Missing SSH target. Set SSH_HOST and SSH_USERNAME in .env or pass [user@host]." >&2
  usage
  exit 1
fi

if [ -z "$REMOTE_PROJECT_DIR" ]; then
  REMOTE_PROJECT_DIR='${HOME}/API-NASA'
fi

case "$MODE" in
  iss)
    BATCH_SCRIPT="map/scripts/backend/run_batch_processor.py"
    TASKS_FILE="${ISS_TASKS_FILE:-$REMOTE_PROJECT_DIR/map/scripts/periodic_tasks/tasks_panama_night.json}"
    ISS_LIMIT_VALUE="0"
    for ((i=0; i<${#CLI_OPTIONS[@]}; i++)); do
      if [ "${CLI_OPTIONS[$i]}" = "--limit" ] && [ $((i + 1)) -lt ${#CLI_OPTIONS[@]} ]; then
        ISS_LIMIT_VALUE="${CLI_OPTIONS[$((i + 1))]}"
      fi
    done
    if ! [[ "$ISS_LIMIT_VALUE" =~ ^[0-9]+$ ]]; then
      echo "Invalid --limit value: $ISS_LIMIT_VALUE" >&2
      exit 1
    fi
    # Use existing periodic flow (task_api_client + extract_enriched_metadata + imageProcessor).
    # Fixed params: Panama + night windows from tasks_panama_night.json.
    # Optional: --limit N (0 or omitted = sin límite).
    REMOTE_CMD="set -euo pipefail; cd '$REMOTE_PROJECT_DIR'; export PYTHONPATH='$REMOTE_PROJECT_DIR':\$PYTHONPATH; \
  # Ensure project-level and map-level logs directories exist and are writable by the user
  mkdir -p '$REMOTE_PROJECT_DIR/logs' '$REMOTE_PROJECT_DIR/map/logs' >/dev/null 2>&1 || true; \
  chmod u+rwx '$REMOTE_PROJECT_DIR/logs' '$REMOTE_PROJECT_DIR/map/logs' >/dev/null 2>&1 || true; \
  if [ -x '$REMOTE_PROJECT_DIR/venv/bin/python3' ]; then \
    ISS_LIMIT='$ISS_LIMIT_VALUE' RUNNING_DOWNLOAD=1 '$REMOTE_PROJECT_DIR/venv/bin/python3' '$BATCH_SCRIPT' '$TASKS_FILE'; \
  else \
    ISS_LIMIT='$ISS_LIMIT_VALUE' RUNNING_DOWNLOAD=1 python3 '$BATCH_SCRIPT' '$TASKS_FILE'; \
  fi"
    ;;
  noaa)
    REMOTE_SCRIPT="$REMOTE_PROJECT_DIR/map/scripts/launch_noaa.sh"
    REMOTE_CMD="set -euo pipefail; chmod +x '$REMOTE_SCRIPT'; '$REMOTE_SCRIPT' ''"
    ;;
  periodic)
    TASK_ID="${CLI_OPTIONS[0]:-}"
    REMOTE_SCRIPT="$REMOTE_PROJECT_DIR/map/scripts/launch_periodic.sh"
    REMOTE_CMD="set -euo pipefail; chmod +x '$REMOTE_SCRIPT'; '$REMOTE_SCRIPT' '$TASK_ID'"
    ;;
  *)
    echo "Invalid mode: $MODE"
    usage
    exit 1
    ;;
esac

echo "Connecting to $REMOTE_TARGET:$SSH_PORT_ENV..."

if [ -n "$SSH_PASSWORD_ENV" ]; then
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "SSH_PASSWORD is set but sshpass is not installed." >&2
    echo "Install sshpass or use SSH keys and remove SSH_PASSWORD from .env." >&2
    exit 1
  fi

  sshpass -p "$SSH_PASSWORD_ENV" ssh -p "$SSH_PORT_ENV" -o StrictHostKeyChecking=accept-new "$REMOTE_TARGET" "bash -lc \"$REMOTE_CMD\""
else
  ssh -p "$SSH_PORT_ENV" "$REMOTE_TARGET" "bash -lc \"$REMOTE_CMD\""
fi
