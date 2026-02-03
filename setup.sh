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

# System libraries required by some native binaries (sound, NSPR)
echo "Installing system libraries: libnspr4, libasound2 (will enable 'universe' if needed)"
# Ensure add-apt-repository is available
sudo apt install -y software-properties-common || true
sudo add-apt-repository -y universe || true
sudo apt update
if ! sudo apt install -y libnspr4 libasound2 libasound2-dev; then
  echo "Warning: could not install libnspr4/libasound2 via apt. Check your apt sources or install manually."
fi

# Initialize the SQLite database if the init script exists
if [ -f "map/db/init_db.sh" ]; then
  chmod +x map/db/init_db.sh || true
  echo "Running database initialization: map/db/init_db.sh"
  bash map/db/init_db.sh || echo "Database initialization failed, continuing setup"
else
  echo "map/db/init_db.sh not found — database initialization will be skipped"
fi

# Ensure project scripts are executable (exclude virtualenv)
echo "Setting executable permissions for project scripts (excluding venv)"
# Make all .sh files executable
find . -path './venv' -prune -o -type f -name '*.sh' -print0 | xargs -0 chmod +x 2>/dev/null || true
# Make files with a shebang executable (skip binary files and venv)
find . -path './venv' -prune -o -type f -print0 | while IFS= read -r -d '' f; do
  if head -n1 "$f" 2>/dev/null | grep -q '^#!'; then
    chmod +x "$f" 2>/dev/null || true
  fi
done

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

echo "✅ Setup complete. If you see authentication or authorization messages, follow the instructions above for Google Drive and Earth Engine."
source venv/bin/activate
cd map/