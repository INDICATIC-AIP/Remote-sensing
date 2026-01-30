#!/bin/bash

clean_logs() {
    local log_dir="$PROJECT_DIR/logs"

    if [ ! -d "$log_dir" ]; then
        echo "Logs folder does not exist: $log_dir"
        return
    fi

    find "$log_dir" -type f -name "*.log" -exec rm -f {} \;
    echo "All .log files in $log_dir have been removed."
    log_custom "Log Cleanup" "All logs were removed from the logs folder" "INFO" "$LOG_WEB"
}

clean_logs

# Param 1: task ID (e.g., task_1744260000000)
TASK_ID="$1"

# Run with virtualenv and show/save logs
env RUNNING_DOWNLOAD=1 /home/jose/API-NASA/venv/bin/python3 \
  /home/jose/API-NASA/map/scripts/backend/run_batch_processor.py \
  /home/jose/API-NASA/map/scripts/periodic_tasks/tasks.json \
  "$TASK_ID" 2>&1 | tee -a /home/jose/API-NASA/map/scripts/periodic_tasks/auto_log.txt

