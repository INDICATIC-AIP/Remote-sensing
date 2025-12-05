#!/bin/bash

limpiar_logs() {
    local log_dir="$PROJECT_DIR/logs"

    if [ ! -d "$log_dir" ]; then
        echo "La carpeta de logs no existe: $log_dir"
        return
    fi

    find "$log_dir" -type f -name "*.log" -exec rm -f {} \;
    echo "Todos los archivos .log en $log_dir han sido eliminados."
    log_custom "Limpieza de Logs" "Se eliminaron todos los logs de la carpeta logs/" "INFO"
}

limpiar_logs

TASK_ID="$1"

MAX_ITEMS=5

env RUNNING_DOWNLOAD=1 /home/jose/API-NASA/venv/bin/python3 \
  /home/jose/API-NASA/map/scripts/noaa/noaa_commands.py \
  export_all "$MAX_ITEMS" "$TASK_ID" 2>&1 | tee -a /home/jose/API-NASA/map/scripts/noaa/auto_log.txt
