#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

if [ -x "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
else
    PYTHON_CMD="python3"
fi

clean_logs() {
    local log_dir="$PROJECT_DIR/logs"

    if [ ! -d "$log_dir" ]; then
        echo "Logs folder does not exist: $log_dir"
        return
    fi

    find "$log_dir" -type f -name "*.log" -exec rm -f {} \;
    echo "All .log files in $log_dir have been removed."
}

clean_logs

TASK_ID="$1"

MAX_ITEMS=5

env RUNNING_DOWNLOAD=1 "$PYTHON_CMD" \
    "$PROJECT_DIR/map/scripts/noaa/noaa_commands.py" \
    export_all "$MAX_ITEMS" "$TASK_ID" 2>&1 | tee -a "$PROJECT_DIR/map/scripts/noaa/auto_log.txt"
