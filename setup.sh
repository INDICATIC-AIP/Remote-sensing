#!/bin/bash
set -e

# API-NASA System Setup

# NAS Mount
sudo mkdir -p /mnt/nas
sudo chown "$USER":"$USER" /mnt/nas
sudo apt update
sudo apt install -y cifs-utils
if [ -f /root/.smbcredentials ]; then
  sudo mount -t cifs "//IP_NAS/DIRECTORY" /mnt/nas -o credentials=/root/.smbcredentials,vers=3.0,uid=$(id -u),gid=$(id -g),file_mode=0644,dir_mode=0755 || true
fi
sudo apt install -y fzf
# PyGObject Virtual Environment
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-glib-2.0
cd "$(dirname "$0")"
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install --upgrade pip
pip install SQLAlchemy textual requests beautifulsoup4 earthengine-api python-dotenv

# Database & Python APIs
sudo apt install -y sqlite3

# Node.js & Maps
sudo apt install -y nodejs npm
source venv/bin/activate
npm install electron --save-dev
npm install leaflet leaflet.markercluster
npm install axios cheerio googleapis nprogress sqlite3

# Download Tools
sudo apt install -y aria2 rclone feh nfs-common yad imagemagick



# Yellow message for rclone
echo -e "\033[1;33mPlease configure rclone manually for Google Drive using: rclone config\033[0m"
rclone config

# Google Earth Engine Setup
echo -e "\033[1;33mIf you have not authenticated Google Earth Engine, run: earthengine authenticate\033[0m"

# System Verification
which pip
ls /mnt/nas || echo "NAS no montado"

node --version
npm --version

# Search and run noaa_commands.py if it exists
source venv/bin/activate
NOAA_PATH=$(find . -type f -name 'noaa_commands.py' | head -n 1)
if [ -n "$NOAA_PATH" ]; then
  python3 "$NOAA_PATH" generate_tiles || echo "NOAA command failed or does not exist"
else
  echo "noaa_commands.py not found in the project."
fi

echo "✅ Setup completo. Si ves mensajes de error de autenticación, sigue las instrucciones anteriores para Google Drive y Earth Engine."
echo "Setup complete. Check the previous messages for manual steps if necessary."
echo "✅ Setup complete. If you see authentication error messages, follow the instructions above for Google Drive and Earth Engine."
source venv/bin/activate
cd map/