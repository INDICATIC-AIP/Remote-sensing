# Automated Light Pollution Monitoring System

Automated acquisition, processing, and management of nighttime satellite images for studying light pollution in the Panama Canal basin.

## Overview

This system integrates NASA ISS, NOAA VIIRS, and DMSP-OLS satellite data sources into an automated repository. Features include API integration, Google Earth Engine processing, scheduled downloads, and hierarchical file organization. [Full details](./PerfilLuminico.pdf)

## Features

- Multiple satellite sources (ISS, VIIRS, DMSP-OLS)
- Automated scheduled downloads
- SQLite database with geospatial metadata
- Electron-based UI with Leaflet maps
- Scalable NAS storage

## Project Structure

```
├── db/                     # SQLite database and schemas
├── logs/                   # System logs organized by module
├── scripts/
│   ├── automatica/         # Automatic extraction scripts
│   ├── backend/            # Processing logic and APIs
│   ├── giras/              # Search and visualization interface
│   ├── noaa/               # Google Earth Engine module
│   ├── periodica/          # Scheduled tasks system
│   └── utils/              # Auxiliary tools
├── main.js                 # Main Electron application
├── package.json            # Node.js dependencies
└── menu.sh                 # Main system menu
```

## Requirements

- **OS**: Windows 11 + WSL2 (Ubuntu 24.04) or Linux
- **Python**: 3.8+ | **Node.js**: 16+
- **Tools**: aria2c, git, curl

## Installation

```bash
# Clone and setup
git clone [repository] && cd [directory]
pip install -r requirements.txt
npm install

# Optional: Configure Google Earth Engine
earthengine authenticate

# Initialize database
python db/Tables.py
```

## Usage

```bash
./menu.sh  # Launch main menu
```

**Modules**:
1. **ISS Search** - API queries with automatic download
2. **NOAA Data** - Google Earth Engine VIIRS/DMSP-OLS processing
3. **Visual Explorer** - File navigation and visualization
4. **Scheduled Tasks** - Automated periodic downloads

## Configuration

**Key Files**:
- `scripts/periodica/tasks.json` - Scheduled tasks
- `scripts/noaa/credentials.json` - Google Earth Engine auth
- `db/metadata.db` - Main database

**Environment**:
```bash
# Copy .env.example to .env and configure your credentials
cp .env.example .env
nano .env

# Required variables:
# - NAS_IP: IP address of your NAS server
# - NAS_SHARE: NAS share name
# - NAS_USERNAME: NAS username
# - NAS_PASSWORD: NAS password
# - NASA_API_KEY: Get from https://api.nasa.gov/
```

## Data Structure

**Database Tables**: Image, ImageDetails, MapLocation, CameraInformation

**File Organization**: `/year/mission/camera/[images + metadata]`

## Logs

Organized in `/logs/` by module: `iss/`, `noaa/`, `explorador.log`, `table.log`

## Architecture

**Stack**: Electron + Python + SQLite  
**APIs**: NASA Photos Database, Google Earth Engine  
**Automation**: Bash + Task Scheduler

**Core Modules**: `imageProcessor.py`, `Crud.py`, `noaa_processor.py`, `main.js`

---
All rights reserved
