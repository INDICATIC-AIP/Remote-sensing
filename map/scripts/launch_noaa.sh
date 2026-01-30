#!/bin/bash

clean_logs() {
    local log_dir="$PROJECT_DIR/logs"

    if [ ! -d "$log_dir" ]; then
        echo "Logs folder does not exist: $log_dir"
        return
    fi

    find "$log_dir" -type f -name "*.log" -exec rm -f {} \;
    echo "All .log files in $log_dir have been removed."
    log_custom "Log Cleanup" "All logs were removed from the logs folder" "INFO"
}

clean_logs

TASK_ID="$1"

MAX_ITEMS=5

env RUNNING_DOWNLOAD=1 /home/jose/API-NASA/venv/bin/python3 \
  /home/jose/API-NASA/map/scripts/noaa/noaa_commands.py \
  export_all "$MAX_ITEMS" "$TASK_ID" 2>&1 | tee -a /home/jose/API-NASA/map/scripts/noaa/auto_log.txt
