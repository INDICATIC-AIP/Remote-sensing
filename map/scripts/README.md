# Scripts Directory (scripts/)

## Overview

The **Scripts** directory contains the core modules for the light pollution monitoring system. Each subdirectory handles a specific aspect of data acquisition, metadata extraction, storage, and visualization support.

## Directory Structure

```
scripts/
├── metadata_extraction/          # Automatic metadata extraction and mapping
├── backend/                      # API clients and image handling
├── noaa/                         # Google Earth Engine satellite data collection
├── periodic_tasks/               # Scheduled task management
└── utils/                        # Shared utility functions
```

## Module Overview

### 1. **metadata_extraction/** - Automatic Data Extraction
Handles automatic extraction and mapping of ISS imagery metadata.

**Key Features**:
- Automatic ISS image cataloging
- Metadata enrichment with geospatial data
- Interactive web-based filtering and mapping
- Real-time link verification

**Core Files**:
- `metadata.py` - Metadata extraction engine
- `map_filters/` - Filtering and mapping logic
- `ui/` - Web interface for browsing cataloged data

[See detailed documentation](./metadata_extraction/README.md)

---

### 2. **backend/** - API Integration & Data Handling
Central hub for NASA APIs, downloads, and metadata handling.

**Key Features**:
- NASA Photos API client for ISS imagery
- Batch image downloading
- Basic image validation and organization
- Task queue management
- Metrics and statistics generation

**Core Files**:
- `nasa_api_client.py` - NASA API integration
- `imageProcessor.py` - Image handling utilities
- `task_api_client.py` - Distributed task management
- `download.py` - Download orchestration

[See detailed documentation](./backend/README.md)

---

### 3. **noaa/** - Google Earth Engine Data Collection
Satellite data collection for NOAA sources (VIIRS, DMSP-OLS) with a professional English interface.

**Key Features**:
- VIIRS nighttime lights collection
- DMSP-OLS historical data collection
- Google Earth Engine integration
- Time-series data organization
- Professional web interface with real-time progress tracking
- Multi-language ready (currently English)
- Clean, accessible UI design

**Core Files**:
- `noaa_processor.py` - Main collection engine with English logging
- `noaa_renderer.js` - Web interface controller (internationalized)
- `noaa_commands.py` - CLI with clear usage messages
- `credentials.json` - Google authentication
- `ui/noaa.html` - Professional data visualization interface

[See detailed documentation](./noaa/README.md)

---

### 4. **periodic_tasks/** - Scheduled Tasks
Task scheduler for automated periodic data acquisition and maintenance.

**Key Features**:
- Cron-like task scheduling
- Task monitoring and status tracking
- Error recovery and retry logic
- Performance metrics logging

**Core Files**:
- `tasks.json` - Task configuration
- `rend_periodica.js` - Task renderer
- `taskManager.js` - Scheduler engine
- `utils/` - Helper functions

[See detailed documentation](./periodic_tasks/README.md)

---

### 5. **utils/** - Utility Functions
Shared utility functions used across modules.

**Utilities**:
- `log.py` - Centralized logging
- `table2.py` - Database utilities
- `nas_explorer.py` - File system operations

## Quick Start

### Installation
```bash
# Install all module dependencies
pip install -r requirements.txt

# For development with GEE support
pip install -r requirements.txt google-earth-engine
```

### Basic Workflow

```bash
# 1. Initialize database
python db/Tables.py

# 2. Start ISS data acquisition
cd scripts/backend
python nasa_api_client.py --start-date 2024-01-01 --limit 100

# 3. Schedule periodic tasks
cd ../periodic_tasks
node taskManager.js --config tasks.json

# 4. Launch web interface
cd ../../map
npm start
```

## Module Dependencies

```

backend/
├── Requires: nasa_api_client, imageProcessor
└── Outputs: downloads/, metadata.json

noaa/
├── Requires: google-earth-engine, credentials
└── Outputs: geotiff_tiles/, collection_logs.json

periodic_tasks/
├── Requires: all other modules
└── Outputs: task_logs, scheduled_results

map/
├── Requires: all processed data, database
└── Outputs: web interface
```

## Configuration

Each module has its own configuration system:

| Module | Config File | Purpose |
|--------|-------------|---------|
| **backend** | `config.json` | API keys, download limits |
| **noaa** | `credentials.json` | GEE authentication |
| **periodica** | `tasks.json` | Task schedules |

## Logging

All modules use structured logging with English messages for international collaboration:

```
../logs/
├── iss/          # ISS module operations
├── noaa/         # NOAA collection logs with detailed status
├── table.log     # Database operations
└── explorador.log # File system operations
```

**Log Format**: `YYYY-MM-DD HH:MM:SS [LEVEL] Message`

View logs:
```bash
# Real-time ISS logs
tail -f ../logs/iss/iss_*.log

# Search error logs
grep ERROR ../logs/**/*.log

# Filter by log level
grep "\[ERROR\]" ../logs/noaa/*.log
```

All log messages are in English with clear, actionable information.

## API Reference

### Running Modules Independently

**ISS Data Download**
```bash
cd backend
python nasa_api_client.py \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --limit 50
```

**NOAA Data Collection**
```bash
cd noaa
python noaa_processor.py \
  --sensor VIIRS \
  --year 2024 \
  --month 1
```

**Task Scheduling**
```bash
cd periodica
python taskManager.py \
  --action start \
  --config tasks.json \
  --daemon
```

## Performance Optimization

- **Parallel downloads**: Backend supports batch downloads
- **Database indexing**: Automatic index creation on startup
- **API rate limiting**: Built-in throttling to respect API limits

## Troubleshooting

### Module Import Errors
```bash
# Verify installation
python -m pip check

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Database Connection Issues
```bash
# Check database
python db/Tables.py

# Verify path in config
grep DATABASE_PATH */config.json
```

### API Rate Limiting
```bash
# Check API quotas
python backend/nasa_api_client.py --check-quota

# Adjust rate limits in config.json
```

## Integration Flow

```
User Input
  ↓
[periodic_tasks] Schedule
  ↓
[backend] Download from APIs
  ↓
[noaa] Collect satellite data
  ↓
[db] Store in database
  ↓
[map] Visualize results
```

## Development

To add a new data source:

1. Create module in `scripts/new_module/`
2. Implement API client
3. Add data collection flow
4. Register in `periodic_tasks/tasks.json`
5. Update main menu in `menu.sh`

---

For detailed information about each module, see individual README files in their directories.
