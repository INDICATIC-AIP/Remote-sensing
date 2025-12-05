#!/bin/bash

THIS_DIR="$(dirname "$0")"
CURRENT_DIR="$(dirname "$THIS_DIR")"
ENLACES_FILE="$CURRENT_DIR/automatica/enlaces_photo_id.txt"
ENLACES_HIGHRES_FILE="$CURRENT_DIR/automatica/enlaces_highres.txt"

> "$ENLACES_HIGHRES_FILE"

# Función para mostrar barra de progreso
progress_bar() {
    local current=$1
    local total=$2
    local title=$3
    local width=50  # Ancho de la barra de progreso

    local progress=$((current * width / total))
    local remaining=$((width - progress))

    # Construir la barra con "#" y espacios
    local bar=$(printf "%0.s#" $(seq 1 $progress))
    local space=$(printf "%0.s " $(seq 1 $remaining))

    # Mostrar la barra con título y contador
    printf "\r%s %d/%d : [%s%s] %d%%" "$title" "$current" "$total" "$bar" "$space" $((current * 100 / total))
}

# Leer total de enlaces
TOTAL_ENLACES=$(wc -l < "$ENLACES_FILE")
CURRENT_COUNT=0

# Contadores para archivos encontrados
TIF_COUNT=0
JPG_COUNT=0

while read -r enlace; do
    SUB_HTML_FILE="sub_pagina.html"

    # Descargar la subpágina
    wget -q -O "$SUB_HTML_FILE" "$enlace"

    # Verificar si la descarga fue exitosa
    if [ ! -s "$SUB_HTML_FILE" ]; then
        rm -f "$SUB_HTML_FILE"
        continue
    fi

    # Extraer los enlaces de alta resolución
    all_res_links=$(grep -oP 'href="(/DatabaseImages/ISD/highres/[^"]*|/DatabaseImages/ESC/large/[^"]*)"' "$SUB_HTML_FILE" | sed 's|href="|https://eol.jsc.nasa.gov|; s|"||')

    # Contar archivos .TIF y .JPG
    TIF_COUNT=$((TIF_COUNT + $(echo "$all_res_links" | grep -c '\.TIF$')))
    JPG_COUNT=$((JPG_COUNT + $(echo "$all_res_links" | grep -c '\.JPG$')))

    # Priorizar enlaces .TIF
    best_url=$(echo "$all_res_links" | grep '\.TIF$' | head -n 1)

    # Si no hay enlaces .TIF, tomar el primer enlace disponible
    if [ -z "$best_url" ]; then
        best_url=$(echo "$all_res_links" | head -n 1)
    fi

    # Guardar el mejor enlace encontrado
    if [ -n "$best_url" ]; then
        echo "$best_url" >> "$ENLACES_HIGHRES_FILE"
    fi

    # Incrementar el contador y actualizar la barra de progreso
    CURRENT_COUNT=$((CURRENT_COUNT + 1))
    progress_bar "$CURRENT_COUNT" "$TOTAL_ENLACES" "Procesando Enlaces (TIF: $TIF_COUNT, JPG: $JPG_COUNT):"

    # Limpiar archivos temporales
    rm -f "$SUB_HTML_FILE"
done < "$ENLACES_FILE"
echo ""

echo "Enlaces de alta resolución guardados en: $ENLACES_HIGHRES_FILE"
