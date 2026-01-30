# Backend Module (scripts/backend/)

## Overview

The **Backend Module** handles the automated acquisition, processing, and storage of NASA ISS (International Space Station) photographs. It integrates with NASA's photo database through web scraping, downloads images and camera metadata using optimized aria2c, and stores enriched metadata in a SQLite database.

## Module Purpose

This module provides:

- **ISS Photo Acquisition**: Automated download of NASA ISS photographs with metadata enrichment
- **Web Scraping**: Extraction of detailed photo information from NASA's website
- **Optimized Downloads**: Parallel image and metadata downloads using aria2c
- **Database Storage**: Structured storage of photo metadata and file locations
- **Batch Processing**: Large-scale processing of photo collections with error recovery

## Core Components

### 1. **run_batch_processor2.py**
Main integrated processor that orchestrates the complete workflow.

**Features**:
- Autonomous processing with configurable limits
- Task scheduling and retry management
- Integration with periodic tasks system
- Error recovery and cleanup
- Windows task management for retries

**Usage**:
```bash
# Autonomous mode with limit
python run_batch_processor2.py

# Process specific task
python run_batch_processor2.py task_123456789

# Costa Rica focused search
python run_batch_processor2.py costa_rica

# Process from metadata file
python run_batch_processor2.py metadata.json
```

**Workflow**:
1. Query NASA API for new images
2. Download camera metadata in bulk
3. Enrich metadata with web scraping
4. Download images with aria2c
5. Store in database

### 2. **imageProcessor.py**
Handles image downloads and database operations using optimized aria2c.

**Key Functions**:
- `download_images_aria2c_optimized()`: Parallel image downloads
- `HybridOptimizedProcessor`: Complete workflow processor
- `verificar_destination_descarga()`: NAS/local destination detection
- `determinar_folder_destination_inteligente()`: Intelligent folder organization

**Download Features**:
- Automatic NAS/local destination detection
- Intelligent file organization by year/mission/camera
- aria2c optimization for high-speed downloads
- Duplicate file detection and skipping
- Progress tracking and logging

**Usage**:
```bash
# Process from metadata file
python imageProcessor.py metadata.json
```

### 3. **extract_enriched_metadata.py**
Web scraping module for NASA photo metadata enrichment.

**Key Functions**:
- `obtener_nadir_altitude_camera_optimized()`: Extract nadir, altitude, camera info
- `obtener_camera_metadata_optimized()`: Download camera metadata files
- `extract_metadata_enriquecido()`: Process API results with scraping

**Scraping Features**:
- Parallel processing with ThreadPoolExecutor
- Caching to avoid duplicate requests
- Error handling with retries
- Camera and film type mapping
- GeoTIFF availability detection

### 4. **bulk_camera_downloader.py**
Bulk download system for camera metadata files.

**Features**:
- Parallel metadata file downloads
- aria2c integration for speed
- NASA ID to file mapping
- Error tracking and reporting

### 5. **data.py**
Data mappings and constants.

**Contents**:
- `cameraMap`: Camera code to description mapping
- `filmMap`: Film type mappings with descriptions

## Data Flow

### Complete Processing Pipeline

1. **API Query**: Search NASA database for ISS photos
2. **Metadata Enrichment**: Scrape NASA website for detailed info
3. **Camera Data Download**: Bulk download camera metadata files
4. **Image Download**: Parallel download of photos using aria2c
5. **Database Storage**: Store enriched metadata in SQLite

### File Organization

The module generates the following directory structure:

#### NAS Mode (Production)
```
/mnt/nas/
├── {year}/                    # e.g., 2024/
│   └── {mission}/            # e.g., ISS073/
│       └── {camera}/         # e.g., Nikon_D5/
│           ├── ISS073-E-123456.jpg
│           └── ISS073-E-123457.tif
└── camera_data/
    ├── ISS073-E-123456.txt
    └── ISS073-E-123457.txt
```

#### Local Mode (Development)
```
scripts/backend/API-NASA/
├── {year}/
│   └── {mission}/
│       └── {camera}/
│           ├── ISS073-E-123456.jpg
│           └── ISS073-E-123457.tif
└── camera_data/
    ├── ISS073-E-123456.txt
    └── ISS073-E-123457.txt
```

### Database Schema

Metadata stored in `db/metadata.db` (SQLite):

**Fields**:
- `NASA_ID`: Unique photo identifier (e.g., ISS073-E-123456)
- `FECHA`: Capture date (YYYY.MM.DD)
- `HORA`: Capture time (HH:MM:SS)
- `LAT`: Latitude coordinate
- `LON`: Longitude coordinate
- `ALTITUD`: Spacecraft altitude (km)
- `CAMARA`: Camera description
- `NADIR_CENTER`: Nadir center coordinates
- `FILM_TYPE`: Film type description
- `URL`: Image download URL
- `FILE_PATH`: Local file path
- `CAMARA_METADATA`: Camera metadata file path
- `GEOTIFF_AVAILABLE`: Boolean for GeoTIFF availability

## Configuration

### Environment Variables
```bash
# Required in .env file
NASA_API_KEY=your_api_key_here
```

### Destination Detection
The system automatically detects the download destination:

- **NAS Available**: Uses `/mnt/nas` (production mode)
- **NAS Unavailable**: Uses `./API-NASA` (development mode)

### Performance Settings
```python
# In imageProcessor.py
CONEXIONES_ARIA2C = 32  # Parallel connections
MAX_WORKERS_SCRAPING = 10  # Parallel scraping threads
BATCH_SIZE_DB = 75  # Database batch size
```

## Usage Examples

### Autonomous Processing
```bash
# Run complete pipeline autonomously
python run_batch_processor2.py
```

### Manual Metadata Processing
```bash
# Process specific metadata file
python run_batch_processor2.py enriched_metadata.json
```

### Image Download Only
```bash
# Download from prepared metadata
python imageProcessor.py metadata.json
```

## Error Handling

### Retry Logic
- Automatic retry with exponential backoff
- Windows scheduled task recreation on failure
- Partial cleanup on errors
- NASA ID tracking for recovery

### Logging
All operations logged to `logs/iss/general.log`:

```
2024-01-15 02:00:00 [INFO] Starting ISS photo batch processing
2024-01-15 02:05:22 [INFO] Downloaded 45 camera metadata files
2024-01-15 02:15:30 [INFO] Enriched metadata for 50 photos
2024-01-15 02:30:45 [SUCCESS] Downloaded 50 images (2.3 MB/s)
```

## Dependencies

```
requests>=2.28.0          # HTTP requests
beautifulsoup4>=4.11.0    # HTML parsing
aria2>=1.36.0             # Download accelerator
sqlite3                  # Database
python-dotenv>=0.19.0     # Environment variables
```

## Integration

### With Periodic Tasks
- Triggered by `launch_periodic.sh`
- Uses `tasks.json` for configuration
- Integrated with web dashboard

### With Database
- Stores metadata in `db/metadata.db`
- Updates photo locations and status
- Provides data for map visualization

### With Web Interface
- Supplies data to `periodica.html`
- Enables search and download interface
- Shares metadata with map display

## Troubleshooting

### NAS Not Available
```bash
# Check mount status
mount | grep nas

# Manual mount (if configured)
sudo mount -t cifs //IP_NAS/DIRECTORY /mnt/nas -o credentials=/root/.smbcredentials
```

### Download Failures
```bash
# Check aria2c installation
which aria2c

# Verify network connectivity
curl -I https://eol.jsc.nasa.gov/
```

### Database Issues
```bash
# Check database integrity
sqlite3 ../db/metadata.db "PRAGMA integrity_check;"

# Rebuild indexes
sqlite3 ../db/metadata.db "REINDEX;"
```

### Scraping Blocks
```bash
# Reduce parallel workers
MAX_WORKERS_SCRAPING = 5

# Increase delays between requests
time.sleep(2)
```

## Performance Metrics

Typical performance on good network:
- **Camera Metadata**: 50 files/minute
- **Image Downloads**: 10-20 MB/s with aria2c
- **Scraping**: 6 photos/minute (NASA rate limiting)
- **Database**: 1000 records/second batch insert

## File Outputs

### Generated Files
- **Images**: JPG/TIFF format photos
- **Camera Metadata**: TXT files with camera parameters
- **Database Records**: Structured metadata entries
- **Log Files**: Processing logs and error reports

### Temporary Files
- `retry_info.json`: Retry state tracking
- `current_execution.json`: Current processing state
- aria2c input files (auto-cleaned)

---

For main system integration, see [Main README](../../README.md)

For periodic task scheduling, see [Periodic Tasks Module](../periodic_tasks/README.md)
