#!/bin/bash

# Get option passed as argument
opcion="$1"

# Define project base directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATICA_DIR="$PROJECT_DIR/scripts/metadata_extraction"
cd "$PROJECT_DIR" || error_exit "Could not change to project base directory."

EXPLORADOR_NAS="$PROJECT_DIR/scripts/utils/nas_explorer.py"
METADATOS_JSON="$PROJECT_DIR/scripts/metadata_extraction/metadata.json"
NOAA_DIR="$PROJECT_DIR/scripts/noaa/"
LOG_PATH="$PROJECT_DIR/scripts/utils/log.py"



# Create logs directory if missing
mkdir -p "$PROJECT_DIR/scripts/logs"

error_exit() {
    python3 "$LOG_PATH" log_custom "" "$1" "ERROR" "$LOG_WEB"
    echo "Press Enter to return to the main menu..."
    read -r
    exit 1
}

# Helper to write custom logs
log_custom() {
    python3 "$LOG_PATH" log_custom "$1" "$2" "$3" "$4"
}


# Clean up text files (metadata, links, etc.)
limpiar_txt() {
    archivo1="$1"
    archivo2="$2"
    archivo3="$3"

    if [ -f "$archivo1" ]; then
        > "$archivo1"
        echo "Cleaned: $archivo1"
    else
        echo "File does not exist: $archivo1"
    fi

    if [ -f "$archivo2" ]; then
        > "$archivo2"
        echo "Cleaned: $archivo2"
    else
        echo "File does not exist: $archivo2"
    fi

    if [ -f "$archivo3" ]; then
        > "$archivo3"
        echo "Cleaned: $archivo3"
    else
        echo "File does not exist: $archivo3"
    fi
}

descarga_automatica() {
    clear

     # Section 1: Coordinate collection
    if [[ -z "$CRON_MODE" ]]; then
        log_custom "" "Starting map application..." "INFO" "$LOG_WEB"
        npm start > /dev/null 2>&1 &
        ELECTRON_PID=$!
        log_custom "" "Draw an area on the map, generate the URL, and close the application." "INFO" "$LOG_WEB"
        wait $ELECTRON_PID || error_exit "Electron application did not close correctly."
    fi

    PHOTO_ID_FILE="$AUTOMATICA_DIR/enlaces_photo_id.txt"
    [ -s "$PHOTO_ID_FILE" ] || error_exit "Links file is missing or empty. Select images first."

    # Section 2: Link processing
    log_custom "Link Processing" "Processing links for high resolution..." "INFO" "$LOG_WEB"
    bash "$AUTOMATICA_DIR/bestLinks.sh" || error_exit "High-resolution link processing failed."

    PHOTO_HIGH_RES="$AUTOMATICA_DIR/enlaces_highres.txt"
    [ -s "$PHOTO_HIGH_RES" ] || error_exit "File 'enlaces_highres.txt' is missing or empty."

    # Section 3: URL processing
    log_custom "URL Processing" "Processing each URL in the links file..." "INFO" "$LOG_WEB"
    TEMP_DIR="$PROJECT_DIR/temp_html"
    mkdir -p "$TEMP_DIR" || error_exit "Could not create temp directory: $TEMP_DIR"
    trap 'rm -rf "$TEMP_DIR"' EXIT
    while IFS= read -r URL; do
        log_custom "" "Processing URL: $URL" "INFO" "$LOG_WEB"
        HTML_FILE="$TEMP_DIR/temp.html"
        wget -q -O "$HTML_FILE" "$URL" || { log_custom "" "Unable to download HTML from $URL" "ERROR" "$LOG_WEB"; continue; }
        python3 "$AUTOMATICA_DIR/metadata.py" "$HTML_FILE" || { log_custom "" "Metadata extraction failed for $URL" "ERROR" "$LOG_WEB"; rm -f "$HTML_FILE"; continue; }
       
        rm -f "$HTML_FILE"
    done < "$PHOTO_ID_FILE"
    
    # Section 4: Download organization
    log_custom "Download Organization" "Starting organization and download process..." "INFO" "$LOG_WEB"
    if [[ -f "$METADATOS_JSON" ]]; then
        log_custom "" "JSON created: inserting into database and downloading images" "INFO" "$LOG_WEB"
        PYTHONPATH="$PROJECT_DIR" python3 "$PROJECT_DIR/scripts/backend/run_batch_processor.py" $METADATOS_JSON || { log_custom "" "Metadata processing and organization failed for $URL" "ERROR" "$LOG_WEB"; }
    else
        log_custom "" "JSON not generated" "INFO" "$LOG_WEB"
    fi

    END_TIME=$(date +%s)
    EXECUTION_TIME=$((END_TIME - START_TIME))
    log_custom "Report - Automatic Download" "Process completed. Total execution time: $EXECUTION_TIME seconds." "INFO" "$LOG_WEB"

    limpiar_txt "$PHOTO_ID_FILE" "$PHOTO_HIGH_RES" "$METADATOS_JSON"

    echo -e "\nFlow completed successfully. Press Enter to return to the main menu..."
    read -r
}

descarga_periodica() {
    clear
    npm run nasa
}

noaa() {
    clear
    npm run noaa
}

nocturno() {
    clear
    npm run nocturno
}

# Clear all .log files
limpiar_logs() {
    local log_dir="$PROJECT_DIR/logs"

    if [ ! -d "$log_dir" ]; then
        echo "The logs folder does not exist: $log_dir"
        return
    fi

    local count=0
    while IFS= read -r -d '' archivo; do
        > "$archivo"
        echo "Cleaned: $archivo"
        ((count++))
    done < <(find "$log_dir" -type f -name "*.log" -print0)

    log_custom "Log Cleanup" "$count .log files were cleared in $log_dir" "INFO" "$LOG_WEB"
    echo "Cleanup complete. $count files were cleared."
}



    # "Automatic Download")
     #     descarga_automatica
     #     ;;
     # "Periodic Download")
     #     descarga_periodica
     #     ;;
      # "Night Map")
     #     nocturno
     #     ;;

case "$opcion" in
 
    "ISS")
        limpiar_logs
        descarga_periodica
        ;;
    "NOAA")
        limpiar_logs
        noaa
        ;;
    "View Metadata")
        PYTHONPATH="$PROJECT_DIR" python3 "$PROJECT_DIR/scripts/utils/table2.py" || error_exit "Error displaying metadata."
        # echo "Presiona Enter para volver al menú..."
        # read -r
        ;;
    "View Images")
        PYTHONPATH="$PROJECT_DIR" python3 "$EXPLORADOR_NAS" || error_exit "Error displaying NAS images."
        ;;
    
    #      "Borrar logs")
    #  limpiar_logs
    #  echo "Presiona Enter para volver al menú..."
    #  read -r
    #  ;;

   
    "Exit")
        exit 0
        ;;
    *)
        error_exit "Invalid option. Make sure to select a menu option."
        ;;
esac