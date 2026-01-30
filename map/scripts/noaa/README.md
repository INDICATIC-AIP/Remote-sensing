# NOAA Module (scripts/noaa/)

## Overview

The **NOAA Module** provides automated collection of satellite nighttime lights data from Google Earth Engine. It focuses on retrieving VIIRS (Visible Infrared Imaging Radiometer Suite) and DMSP-OLS (Defense Meteorological Satellite Program - Operational Linescan System) datasets for the Panama region.

## Module Purpose

This module enables:

- **Automated Data Collection**: Retrieve satellite imagery from Google Earth Engine
- **Batch Processing**: Export multiple images in parallel with retry mechanisms
- **Web Interface**: Interactive visualization and management of collected data
- **Task Scheduling**: Support for periodic data collection tasks
- **Metadata Management**: Generate and maintain metadata for collected images

## Key Components

### 1. **noaa_processor.py**
Main processing engine that handles data export from Google Earth Engine.

**Features**:
- Batch export of VIIRS and DMSP-OLS images
- Robust error handling with automatic retries
- Progress monitoring and status tracking
- File organization and integrity verification
- Integration with Google Drive for data storage

### 2. **noaa_commands.py**
Command-line interface for NOAA operations.

**Available Commands**:
- `generate_tiles`: Generate tile data for web visualization
- `export_all`: Export all pending images from Google Earth Engine
- `listar-candidatos-export`: List available images for export
- `get_metadata YEAR`: Retrieve metadata for a specific year
- `generate_metadata`: Generate metadata file for collected images

**Usage Examples**:
```bash
# Export all pending images
python noaa_commands.py export_all

# List available images for export
python noaa_commands.py listar-candidatos-export

# Generate metadata file
python noaa_commands.py generate_metadata

# Get metadata for specific year
python noaa_commands.py get_metadata 2024
```

### 3. **launch_noaa.sh**
Bash script for launching NOAA data collection tasks.

**Features**:
- Log cleanup before execution
- Environment setup for data downloads
- Integration with task scheduling system
- Progress logging to auto_log.txt

**Usage**:
```bash
# Launch NOAA collection with task ID
./launch_noaa.sh "task_123"

# The script will:
# 1. Clean old log files
# 2. Set download environment
# 3. Run export_all command
# 4. Log output to auto_log.txt
```

### 4. **ui/ - Web Interface**
Professional web interface for NOAA data management and visualization.

**Files**:
- `noaa.html` - Main interface with Leaflet map integration
- `noaa_renderer.js` - Frontend logic for data loading and export
- `tasks_noaa.json` - Configuration for scheduled tasks (currently empty)
- `noaa.css` - Styling for the interface

**Features**:
- Interactive map with opacity controls
- Image export functionality
- Task management interface
- Local image loading and filtering
- Progress monitoring for exports

**Access**:
```bash
# Start local web server
cd ui
python -m http.server 8000

# Open browser to http://localhost:8000/noaa.html
```

### 5. **credentials.json**
Google Earth Engine authentication credentials.

**Setup**:
```bash
# Authenticate with Google Earth Engine
earthengine authenticate

# Copy credentials to project
cp ~/.config/earthengine/credentials ./credentials.json
```

**Security Note**: Never commit credentials.json to version control.

### 6. **Supporting Files**

| File | Purpose |
|------|---------|
| `noaa_metrics.py` | Optional metrics and validation checks |
| `auto_log.txt` | Log file for automated operations |
| `current_noaa_execution.json` | Tracks current export execution status |
| `noaa_retry_info.json` | Stores retry information for failed exports |

## Data Collection Workflow

### 1. **Initial Setup**
```bash
# Authenticate with Google Earth Engine
earthengine authenticate

# Copy credentials
cp ~/.config/earthengine/credentials ./credentials.json
```

### 2. **Check Available Data**
```bash
# List images available for export
python noaa_commands.py listar-candidatos-export
```

### 3. **Export Data**
```bash
# Export all pending images
python noaa_commands.py export_all
```

### 4. **Generate Metadata**
```bash
# Create metadata file for web interface
python noaa_commands.py generate_metadata
```

### 5. **View in Web Interface**
- Open `ui/noaa.html` in a web browser
- Load local images
- Visualize and export data

## Data Pipeline

```
Google Earth Engine Collections
        ↓
    Batch Export (noaa_processor.py)
        ↓
    Google Drive Storage
        ↓
    Local Download & Organization
        ↓
    Metadata Generation
        ↓
    Web Interface Visualization
```

## Configuration

### tasks_noaa.json
Currently empty array `[]`. Can be configured for scheduled tasks:

```json
[
  {
    "id": "noaa_task_abc123",
    "hora": "02:00",
    "frecuencia": "DAILY",
    "intervalo": 1,
    "max_items": 5
  }
]
```

### Environment Variables
- `RUNNING_DOWNLOAD=1`: Enables download mode in launch script
- `MAX_ITEMS`: Maximum items to export per batch (default: 5)

## Output Structure

```
noaa/
├── ui/
│   ├── noaa_metadata.json    # Generated metadata
│   ├── tiles_panama.json     # Tile configuration
│   └── *.tif                 # Downloaded images
├── auto_log.txt              # Execution logs
├── current_noaa_execution.json
└── noaa_retry_info.json
```

## Integration with Other Modules

### With Database (db/)
```python
# Store collection metadata
from db.Crud import DatabaseManager

db = DatabaseManager()
db.insert_image({
    'satellite': 'VIIRS',
    'acquisition_date': '2024-01-15',
    'path': './ui/image_2024.tif'
})
```

### With Periodic Tasks (periodic_tasks/)
The `launch_noaa.sh` script can be integrated with the periodic task scheduler for automated data collection.

### With Main Map Interface
NOAA tiles can be loaded into the main map interface using Leaflet layers.

## Performance Considerations

### Batch Processing
- Exports run in parallel with configurable concurrency
- Automatic retry mechanism for failed exports
- Progress monitoring and status updates

### Memory Management
- Files are processed in batches to manage memory usage
- Partial downloads are cleaned up on failures
- Integrity checks prevent corrupted data

## Troubleshooting

### Authentication Issues
```bash
# Re-authenticate with Earth Engine
earthengine authenticate
cp ~/.config/earthengine/credentials ./credentials.json
```

### Export Failures
- Check `auto_log.txt` for error details
- Verify Google Earth Engine task status
- Retry failed exports manually

### Web Interface Issues
- Ensure metadata file is generated
- Check browser console for JavaScript errors
- Verify file paths in tile configuration

### Log Cleanup
The launch script automatically cleans old logs, but manual cleanup can be done:
```bash
# Remove all log files
find logs/ -name "*.log" -delete
```

## Dependencies

```
google-earth-engine>=0.1.0
earthengine-api>=0.1.0
rasterio>=1.2.0
pillow>=9.0.0
requests>=2.25.0
```

## References

- [Google Earth Engine](https://earthengine.google.com/)
- [VIIRS Nighttime Lights](https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_DNB_MONTHLY_V1_VCMCFG)
- [DMSP-OLS Nighttime Lights](https://developers.google.com/earth-engine/datasets/catalog/NOAA_DMSP-OLS_NIGHTTIME_LIGHTS)

## Setup

To set up the NOAA module:

1. **Authenticate Google Earth Engine** (if not already done):
   ```bash
   earthengine authenticate
   ```

2. **Generate tiles for web visualization**:
   ```bash
   python noaa_commands.py generate_tiles
   ```

---

For scheduling integration, see [Periodic Tasks Module](../periodic_tasks/README.md)
