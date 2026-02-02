# Setup and Configuration Guide

This guide provides step-by-step instructions for manual setup and troubleshooting.

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [API Configuration](#api-configuration)
3. [Database Operations](#database-operations)
4. [NAS Mounting](#nas-mounting)
5. [Google Earth Engine](#google-earth-engine)
6. [Google Drive Setup](#google-drive-setup)
7. [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Create Python Virtual Environment

```bash
cd $(git rev-parse --show-toplevel)
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install --upgrade pip setuptools wheel
```

### Install Python Packages

```bash
source venv/bin/activate
pip install SQLAlchemy textual requests beautifulsoup4 earthengine-api python-dotenv
```

### Install System Dependencies

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-glib-2.0
sudo apt install -y sqlite3 git curl wget
sudo apt install -y nodejs npm
sudo apt install -y aria2 rclone feh nfs-common yad imagemagick cifs-utils
```

---

## API Configuration

### NASA API Key

1. Visit: https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/
2. Email NASA JSC Earth Observations Laboratory for free API key
3. Store in .env file:

```bash
cp .env.example .env
nano .env
# Add: NASA_API_KEY=your_key_here
```

### Test NASA API

```bash
source .env
curl "https://eol.jsc.nasa.gov/SearchPhotos/API/lookup?Keyword=Panama&APIKey=$NASA_API_KEY"
```

---

## Database Operations

### Initialize Database

```bash
cd db
rm -f metadata.db
sqlite3 metadata.db < metadata.sql
cd ..
```

### Reset Database

```bash
cd db
rm metadata.db
sqlite3 metadata.db < metadata.sql
echo "Database reset complete"
cd ..
```

### Check Database Structure

```bash
sqlite3 db/metadata.db ".tables"
sqlite3 db/metadata.db ".schema Image"
```

### Backup Database

```bash
cp db/metadata.db db/metadata.db.backup.$(date +%Y%m%d)
```

---

## NAS Mounting

### Configure Credentials

```bash
# Edit .env file with NAS details
nano .env

# Add these lines:
# NAS_IP=192.168.1.100
# NAS_SHARE=remote-sensing
# NAS_USERNAME=your_username
# NAS_PASSWORD=your_password
```

### Create SMB Credentials File

```bash
source .env

sudo mkdir -p /root
echo -e "username=$NAS_USERNAME\npassword=$NAS_PASSWORD" | \
  sudo tee /root/.smbcredentials > /dev/null

sudo chmod 600 /root/.smbcredentials
```

### Mount NAS

```bash
source .env

sudo mkdir -p /mnt/nas
sudo mount -t cifs \
  "//$NAS_IP/$NAS_SHARE" \
  /mnt/nas \
  -o credentials=/root/.smbcredentials,vers=3.0,uid=$(id -u),gid=$(id -g),file_mode=0644,dir_mode=0755

# Verify mount
ls /mnt/nas
```

### Unmount NAS

```bash
sudo umount /mnt/nas
```

### SSH/SFTP Alternative

If NAS supports SSH:

```bash
sshfs -p 2222 username@nas-address:/path /mnt/nas
```

---

## Google Earth Engine

### Setup Google Cloud Project

1. Go to: https://console.cloud.google.com/
2. Create new project or select existing
3. Search for "Earth Engine API" and enable it
4. Go to APIs & Services > Credentials
5. Create Service Account
6. Grant Editor role
7. Create JSON key and download
8. Save to: scripts/noaa/credentials.json

### Configure Environment

```bash
nano .env

# Add:
# GEE_SERVICE_ACCOUNT_JSON=scripts/noaa/credentials.json
# GEE_PROJECT_ID=your-gcp-project-id
```

### Request Earth Engine Access

1. Visit: https://earthengine.google.com/signup/
2. Fill in form with project details
3. Submit for approval (24-48 hours)
4. Once approved, service account has access

### Authenticate

```bash
source venv/bin/activate
earthengine authenticate
# Browser will open for authorization
```

### Verify Setup

```bash
earthengine info
# Should show project and quota information
```

---

## Google Drive Setup

### Configure rclone

```bash
rclone config
```

Follow the prompts:
- Name: gdrive
- Storage type: Google Drive (search or enter number)
- Client ID: Press Enter (use default)
- Client Secret: Press Enter (use default)
- Scope: 1 (full access)
- Root folder ID: Press Enter (leave blank)
- Use auto config: y (yes) - browser will open
- Confirm remote: y (yes)

### Mount Google Drive

```bash
sudo mkdir -p /mnt/gdrive

rclone mount gdrive: /mnt/gdrive \
  --daemon \
  --allow-other \
  --vfs-cache-mode writes

# Verify
ls /mnt/gdrive
```

### Unmount Google Drive

```bash
fusermount -u /mnt/gdrive
```

---

## Troubleshooting

### Virtual Environment Issues

**Problem**: `which pip` shows system pip instead of venv

**Solution**:
```bash
exec bash
source venv/bin/activate
which pip  # Should show venv path
```

### Database Issues

**Problem**: Database corrupted or won't open

**Solution**:
```bash
# Check integrity
sqlite3 db/metadata.db "PRAGMA integrity_check;"

# Restore from backup
cp db/metadata.db.backup.* db/metadata.db

# Or reinitialize (loses data)
cd db && rm metadata.db && sqlite3 metadata.db < metadata.sql && cd ..
```

### NAS Mounting Issues

**Problem**: Mount fails with permission denied

**Solution**:
```bash
# Check credentials file
sudo ls -la /root/.smbcredentials

# Try mounting with verbose output
sudo mount -v -t cifs \
  "//$NAS_IP/$NAS_SHARE" \
  /mnt/nas \
  -o credentials=/root/.smbcredentials,vers=3.0,uid=$(id -u),gid=$(id -g)
```

**Problem**: Connection timed out

**Solution**:
```bash
# Verify NAS is reachable
ping $NAS_IP

# Try SMB version 2.0
sudo mount -t cifs \
  "//$NAS_IP/$NAS_SHARE" \
  /mnt/nas \
  -o credentials=/root/.smbcredentials,vers=2.0,uid=$(id -u),gid=$(id -g)
```

### Google Earth Engine Authentication

**Problem**: earthengine authenticate fails

**Solution**:
```bash
earthengine authenticate --force

# Test connection
earthengine info
```

### Google Drive / rclone

**Problem**: rclone mount fails or disconnects

**Solution**:
```bash
# Unmount
fusermount -u /mnt/gdrive

# Remount with additional options
rclone mount gdrive: /mnt/gdrive \
  --daemon \
  --allow-other \
  --vfs-cache-mode writes \
  --vfs-cache-max-age 1h \
  --vfs-cache-max-size 10G
```

### System Verification

Verify all components:

```bash
echo "Python:"
source venv/bin/activate
which python3 && python3 --version

echo "Node.js:"
node --version && npm --version

echo "Database:"
sqlite3 --version

echo "Tools:"
which aria2c && which rclone

echo "NASA API:"
source .env && curl -s "https://eol.jsc.nasa.gov/SearchPhotos/API/lookup?Keyword=Panama&APIKey=$NASA_API_KEY" | head -c 50

echo "Earth Engine:"
earthengine info | head -3

echo "NAS:"
mount | grep nas || echo "NAS not mounted"
```

---

## Base de Datos & APIs Python

### Instalación de SQLite y dependencias de Python:
```bash
sudo apt install sqlite3
```

```bash
pip install SQLAlchemy textual requests beautifulsoup4 earthengine-api
```

---

## Node.js & Mapas

### Instalación de Node.js:
```bash
sudo apt install nodejs npm
```

### Dependencias de Electron y mapas:
```bash
npm install electron --save-dev
npm install leaflet leaflet.markercluster
npm install axios cheerio googleapis nprogress sqlite3
```

---

## Herramientas de Descarga

### Instalación de herramientas:
```bash
sudo apt install aria2 rclone feh nfs-common yad imagemagick
```

---

## Google Drive Setup

### 1. Google Cloud Console:
```
1. Ir a: https://console.cloud.google.com/
2. Crear nuevo proyecto o seleccionar existente
3. APIs & Services → Library → Buscar "Google Drive API" → Enable
4. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
5. Application type: Desktop application
6. Name: rclone-gdrive
7. Download JSON credentials file
```

### 2. Configuración rclone en WSL/Linux:

#### Iniciar configuración:
```bash
rclone config
```

#### Proceso paso a paso:
```
1. Escribe: n (new remote)
2. Name: gdrive (o el nombre que prefieras)
3. Busca Google Drive en la lista (normalmente opción 15 o drive)
4. Client ID: Presiona Enter (vacío para usar el por defecto)
5. Client Secret: Presiona Enter (vacío)
6. Scope: Escribe 1 (acceso completo)
7. Root folder ID: Presiona Enter (vacío para raíz)
8. Service Account File: Presiona Enter (vacío)
9. Edit advanced config? → n (no)
10. Use auto config? → y (yes)
11. Autenticarse en el navegador que se abre automáticamente
12. Configure this as a team drive? → n (no, a menos que uses Google Workspace)
13. Keep this "gdrive" remote? → y (yes)
14. Quit config → q
```

#### Probar y montar Google Drive:
```bash
# Probar la configuración
rclone ls gdrive:

# Crear punto de montaje
sudo mkdir -p /mnt/gdrive

# Montar Google Drive
rclone mount gdrive: /mnt/gdrive --daemon --allow-other --vfs-cache-mode writes

# Verificar montaje
ls /mnt/gdrive
```

---

## Google Earth Engine Setup

### Autenticación inicial:
```bash
# Verificar si ya existe autenticación
earthengine authenticate

# Si necesitas re-autenticar o es primera vez
earthengine authenticate --force
```

**Nota**: El comando abrirá automáticamente tu navegador para autenticar.

**Solución para problemas de autenticación**: https://github.com/gee-community/geemap/issues/1870

### Proceso de autenticación:
```
1. Se abrirá automáticamente el navegador con URL de Google
2. Inicia sesión en tu cuenta de Google
3. Acepta los permisos para Earth Engine
4. Espera el mensaje: "Successfully saved authorization token"
```

### Comandos de prueba:
```bash
# Probar comando básico (requiere año específico)
python3 scripts/noaa/noaa_commands.py get_metadata 2023

# Generar archivo completo de metadatos
python3 scripts/noaa/noaa_commands.py generate_metadata

# Listar candidatos para exportar
python3 scripts/noaa/noaa_commands.py listar-candidatos-export
```

---

## Verificación del Sistema

### Comprobar que todo esté funcionando:
```bash
# Verificar venv activo
which pip  # Debe mostrar ruta del venv

# Verificar montajes
ls /mnt/nas
ls /mnt/gdrive

# Verificar Earth Engine
earthengine authenticate --dry_run

# Verificar Node.js
node --version
npm --version

# Probar comando NOAA
cd ~/API-NASA
python3 scripts/noaa/noaa_commands.py generate_tiles
```

---

## Notas Importantes

- Entorno Virtual: Siempre activar con `source venv/bin/activate` antes de trabajar
- NAS: Verificar conectividad antes de procesar archivos grandes
- Google Drive: El montaje puede desconectarse, re-montar si es necesario
- Earth Engine: Requiere proyecto de Google Cloud configurado
- NOAA: Los comandos generan archivos en `scripts/noaa/ui/`

---

## Solución de Problemas Comunes

### Si pip apunta a sistema en lugar de venv:
```bash
exec bash
source venv/bin/activate
```

### Si falla autenticación de Earth Engine:
```bash
earthengine authenticate --force
```

### Si no monta Google Drive:
```bash
fusermount -u /mnt/gdrive
rclone mount gdrive: /mnt/gdrive --daemon --allow-other --vfs-cache-mode writes
```