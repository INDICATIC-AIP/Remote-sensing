#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
. "$PROJECT_DIR/venv/bin/activate"

if grep -qs '/mnt/nas' /proc/mounts; then
    echo "NAS is already mounted."
else
    echo "NAS is not mounted."
    # bash "$SCRIPT_DIR/mount_nas.sh"
fi
# "Automatic Download"   "Night Map"  "Clear logs"
options=("ISS" "NOAA" "View Metadata" "View Images" "Exit")

while true; do
    
    echo "Use the wheel or mouse to move and press Enter or click to select:"
    echo

    selected_option=$(printf '%s\n' "${options[@]}" | fzf --reverse --border --height=50% --margin=1 --pointer=">")

    if [[ -z "$selected_option" ]]; then
        echo "Selection canceled. Exiting..."
        break
    fi

    echo
    echo "Running: $selected_option"
    echo

    if [[ "$selected_option" == "Exit" ]]; then
        echo "Exiting menu..."
        break
    else
        bash "$SCRIPT_DIR/solution.sh" "$selected_option"
        # echo -e "\nPress any key to return to the menu..."
        # read -rsn1
    fi
done
