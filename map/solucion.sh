#!/bin/bash

# Obtener la opción pasada como argumento
opcion="$1"

# Definir directorio base del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATICA_DIR="$PROJECT_DIR/scripts/automatica"
cd "$PROJECT_DIR" || error_exit "No se pudo cambiar al directorio base del proyecto."

EXPLORADOR_NAS="$PROJECT_DIR/scripts/utils/explorador.py"
METADATOS_JSON="$PROJECT_DIR/scripts/automatica/metadatos.json"
NOAA_DIR="$PROJECT_DIR/scripts/noaa/"
LOG_PATH="$PROJECT_DIR/scripts/utils/log.py"



# Crear directorio de logs si no existe
mkdir -p "$PROJECT_DIR/scripts/logs"

error_exit() {
    python3 "$LOG_PATH" log_custom "" "$1" "ERROR" "$LOG_WEB"
    echo "Presiona Enter para regresar al menú principal..."
    read -r
    exit 1
}

# Función para registrar logs
log_custom() {
    python3 "$LOG_PATH" log_custom "$1" "$2" "$3" "$4"
}


# Función para limpiar archivos de texto (metadatos, enlaces, etc.)
limpiar_txt() {
    archivo1="$1"
    archivo2="$2"
    archivo3="$3"

    if [ -f "$archivo1" ]; then
        > "$archivo1"
        echo "Se ha limpiado: $archivo1"
    else
        echo "El archivo $archivo1 no existe."
    fi

    if [ -f "$archivo2" ]; then
        > "$archivo2"
        echo "Se ha limpiado: $archivo2"
    else
        echo "El archivo $archivo2 no existe."
    fi

    if [ -f "$archivo3" ]; then
        > "$archivo3"
        echo "Se ha limpiado: $archivo3"
    else
        echo "El archivo $archivo3 no existe."
    fi
}

descarga_automatica() {
    clear

     # Sección 1: Recolección de Coordenadas
    if [[ -z "$CRON_MODE" ]]; then
        log_custom "" "Iniciando aplicación de mapa..." "INFO" "$LOG_WEB"
        npm start > /dev/null 2>&1 &
        ELECTRON_PID=$!
        log_custom "" "Dibuja un área en el mapa, genera la URL, y cierra la aplicación." "INFO" "$LOG_WEB"
        wait $ELECTRON_PID || error_exit "La aplicación Electron no se cerró correctamente."
    fi

    PHOTO_ID_FILE="$AUTOMATICA_DIR/enlaces_photo_id.txt"
    [ -s "$PHOTO_ID_FILE" ] || error_exit "El archivo con enlaces no existe o está vacío. Seleccione imágenes"

    # Sección 2: Procesamiento de Enlaces
    log_custom "Procesamiento de Enlaces" "Procesando enlaces para alta resolución..." "INFO" "$LOG_WEB"
    bash "$AUTOMATICA_DIR/bestLinks.sh" || error_exit "Falló el procesamiento de enlaces para alta resolución."

    PHOTO_HIGH_RES="$AUTOMATICA_DIR/enlaces_highres.txt"
    [ -s "$PHOTO_HIGH_RES" ] || error_exit "El archivo 'enlaces_highres.txt' no existe o está vacío."

    # Sección 3: Procesamiento de URLs
    log_custom "Procesamiento de URLs" "Procesando cada URL en el archivo de enlaces..." "INFO" "$LOG_WEB"
    TEMP_DIR="$PROJECT_DIR/temp_html"
    mkdir -p "$TEMP_DIR" || error_exit "No se pudo crear el directorio temporal: $TEMP_DIR"
    trap 'rm -rf "$TEMP_DIR"' EXIT
    while IFS= read -r URL; do
        log_custom "" "Procesando URL: $URL" "INFO" "$LOG_WEB"
        HTML_FILE="$TEMP_DIR/temp.html"
        wget -q -O "$HTML_FILE" "$URL" || { log_custom "" "No se pudo descargar el HTML desde $URL" "ERROR" "$LOG_WEB"; continue; }
        python3 "$AUTOMATICA_DIR/metadatos.py" "$HTML_FILE" || { log_custom "" "Falló la extracción de metadatos para $URL" "ERROR" "$LOG_WEB"; rm -f "$HTML_FILE"; continue; }
       
        rm -f "$HTML_FILE"
    done < "$PHOTO_ID_FILE"
    
    #Sección 4: Organización de Descargas
    log_custom "Organización de Descargas" "Iniciando el proceso de organización y descarga..." "INFO" "$LOG_WEB"
    if [[ -f "$METADATOS_JSON" ]]; then
        log_custom "" "Json creado: insertando en la base de datos y descargando imagenes" "INFO" "$LOG_WEB"
        PYTHONPATH="$PROJECT_DIR" python3 "$PROJECT_DIR/scripts/backend/run_batch_processor.py" $METADATOS_JSON || { log_custom "" "Falló el procesamiento de metadatos y organización para $URL" "ERROR" "$LOG_WEB"; }
    else
        log_custom "" "Json no generado" "INFO" "$LOG_WEB"
    fi

    END_TIME=$(date +%s)
    EXECUTION_TIME=$((END_TIME - START_TIME))
    log_custom "Reporte - Descarga Automática" "Proceso completo finalizado. Tiempo total de ejecución: $EXECUTION_TIME segundos." "INFO" "$LOG_WEB"

    limpiar_txt "$PHOTO_ID_FILE" "$PHOTO_HIGH_RES" "$METADATOS_JSON"

    echo -e "\nFlujo completado exitosamente. Presiona Enter para regresar al menú principal..."
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

# Función para limpiar todos los archivos de logs
# Función para vaciar el contenido de todos los archivos .log
limpiar_logs() {
    local log_dir="$PROJECT_DIR/logs"

    if [ ! -d "$log_dir" ]; then
        echo "⚠️  La carpeta de logs no existe: $log_dir"
        return
    fi

    local count=0
    while IFS= read -r -d '' archivo; do
        > "$archivo"
        echo "🧹 Limpiado: $archivo"
        ((count++))
    done < <(find "$log_dir" -type f -name "*.log" -print0)

    log_custom "Limpieza de Logs" "Se vaciaron $count archivos .log en $log_dir" "INFO" "$LOG_WEB"
    echo "✔️  Limpieza completa. Se vaciaron $count archivos."
}



   # "Descarga Automática")
    #     descarga_automatica
    #     ;;
    # "Descarga Periódica")
    #     descarga_periodica
    #     ;;
     # "Mapa Nocturno")
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
    "Ver Metadatos")
        python3 "$PROJECT_DIR/scripts/utils/table2.py" || error_exit "Error al mostrar los metadatos."
        # echo "Presiona Enter para volver al menú..."
        # read -r
        ;;
    "Ver Imagenes")
        PYTHONPATH="$PROJECT_DIR" python3 "$EXPLORADOR_NAS" || error_exit "Error al mostrar las imagenes del NAS."
        ;;
    
    #      "Borrar logs")
    #  limpiar_logs
    #  echo "Presiona Enter para volver al menú..."
    #  read -r
    #  ;;

   
    "Salir")
        exit 0
        ;;
    *)
        error_exit "Opción no válida. Asegúrate de seleccionar una opción del menú."
        ;;
esac