#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
. "$PROJECT_DIR/venv/bin/activate"

if grep -qs '/mnt/nas' /proc/mounts; then
    echo "El NAS ya se encuentra montado."
else
    echo "El NAS no se encuentra montado."
    # bash "$SCRIPT_DIR/montar_nas.sh"
fi
# "Descarga Automática"   "Mapa Nocturno"  "Borrar logs" --prompt="🛰️ "
options=("ISS" "NOAA" "Ver Metadatos" "Ver Imagenes" "Salir")

while true; do
    
    echo "Usa la rueda o el mouse para moverte y presiona Enter o clic para seleccionar:"
    echo

    selected_option=$(printf '%s\n' "${options[@]}" | fzf --reverse --border   --height=50% --margin=1 --pointer="➤")

    if [[ -z "$selected_option" ]]; then
        echo "Selección cancelada. Saliendo..."
        break
    fi

    echo
    echo "Ejecutando: $selected_option"
    echo

    if [[ "$selected_option" == "Salir" ]]; then
        echo "Saliendo del menú..."
        break
    else
        bash "$SCRIPT_DIR/solucion.sh" "$selected_option"
        # echo -e "\nPresiona cualquier tecla para volver al menú..."
        # read -rsn1
    fi
done
