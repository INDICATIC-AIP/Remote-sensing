# Acciones comunes

### Vaciar o reiniciar base de datos SQLite
```bash
cd db
rm metadata.db
sqlite3 metadata.db < metadata.sql
cd ..
```


### Montar NAS o Servidor de almacenamiento local
```bash
# Primero, configura tus credenciales en .env (ver archivo .env.example)
source .env

# Crear archivo de credenciales (si no existe)
sudo mkdir -p /root
echo -e "username=$NAS_USERNAME\npassword=$NAS_PASSWORD" | sudo tee /root/.smbcredentials > /dev/null
sudo chmod 600 /root/.smbcredentials

# Montar NAS
sudo mkdir -p /mnt/nas
sudo mount -t cifs "//$NAS_IP/$NAS_SHARE" /mnt/nas -o credentials=/root/.smbcredentials,vers=3.0,uid=$(id -u),gid=$(id -g),file_mode=0644,dir_mode=0755

# Si necesitas mover datos locales al NAS:
# sudo mv /mnt/nas /mnt/nas_local && sudo mkdir -p /mnt/nas
# [mount command]
# cp -r /mnt/nas_local/* /mnt/nas/

// desmontar

sudo umount /mnt/nas

## Explorador de Archivos NAS

### Configuración del punto de montaje NAS:
```bash
sudo mkdir -p /mnt/nas
sudo chown jose:jose /mnt/nas
sudo apt install cifs-utils
sshfs -p 2222 indicatic@desktop-c9jv5od:/mnt/nas /mnt/nas
```

---

## Entorno Virtual PyGObject

### Instalación de dependencias del sistema:
```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-glib-2.0
```

### Configuración del entorno virtual:
```bash
cd ~/API-NASA
rm -rf venv
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install --upgrade pip
```

### Arreglar problema de pip en venv:
```bash
# Si pip apunta a /usr/bin/pip después de activar venv:
exec bash
source venv/bin/activate
which pip  # Debe mostrar: /home/jose/API-NASA/venv/bin/pip
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