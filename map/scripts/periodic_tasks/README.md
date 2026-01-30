# Periodic ISS Photos Module (scripts/periodic_tasks/)

## Overview

The **Periodic ISS Photos Module** provides automated collection and processing of NASA ISS (International Space Station) photographs. It includes a web-based interface for searching and downloading ISS photos, along with periodic batch processing capabilities for automated data acquisition.

## Module Purpose

This module enables:

- **ISS Photo Search**: Interactive web interface for searching NASA ISS photographs by location, date, and camera parameters
- **Batch Processing**: Automated periodic collection of ISS photos based on predefined tasks
- **Metadata Management**: Generation and maintenance of photo metadata files
- **Map Visualization**: Geographic display of photo locations with filtering capabilities
- **Download Management**: Bulk download functionality with progress tracking and error handling

## Key Components

### 1. **Web Interface (periodica.html + rend_periodica.js)**
Vue.js-based web application for ISS photo search and management.

**Features**:
- Interactive map with Leaflet for geographic photo location display
- Advanced filtering by date, camera, coordinates, and bounding box
- Real-time photo preview and metadata display
- Bulk download with progress indicators
- Task scheduling interface for periodic operations

**Main Functions**:
- `fetchData()`: Search NASA API for ISS photos
- `descargarAhora()`: Download selected photos with deduplication
- `confirmarCrearCron()`: Schedule periodic download tasks
- `actualizarMapaConFiltros()`: Update map display based on filters

### 2. **Periodic Tasks (tasks.json + launch_periodic.sh)**
Automated batch processing system for ISS photo collection.

**Task Configuration** (tasks.json):
```json
{
  "tasks": [
    {
      "id": "iss_daily_batch",
      "name": "Daily ISS Photo Batch",
      "schedule": "0 2 * * *",
      "enabled": true
    }
  ]
}
```

**Launch Script** (launch_periodic.sh):
- Cleans old log files
- Executes batch processor with virtual environment
- Logs all operations to auto_log.txt

### 3. **Metadata File (metadatos_periodicos.json)**
JSON file containing processed metadata for ISS photos.

**Structure**:
```json
[
  {
    "NASA_ID": "ISS073-E-899142",
    "DATE": "2024-01-15",
    "LAT": 8.945,
    "LON": -79.534,
    "CAMERA": "Nikon D5",
    "ALTITUDE": 408000,
    "CAMARA_METADATA": "/path/to/camera_data/ISS073-E-899142.txt"
  }
]
```

### 4. **Utility Scripts (utils/)**

| File | Purpose |
|------|---------|
| `queryBuilder.js` | Builds API queries with filters and bounding boxes |
| `mapHelpers.js` | Map interaction utilities (Leaflet integration) |
| `photoUtils.js` | Photo processing and metadata utilities |
| `taskManager.js` | Task scheduling and management functions |
| `generalUtils.js` | General helper functions |
| `data.js` | Camera and film type mappings |

### 5. **Log File (auto_log.txt)**
Execution log for periodic tasks and manual operations.

```
2024-01-15 02:00:00 [INFO] Starting ISS photo batch processing
2024-01-15 02:00:15 [INFO] Found 87 new photos
2024-01-15 02:15:30 [SUCCESS] Batch completed (15.5s)
2024-01-15 14:30:00 [INFO] Manual download: 12 photos selected
2024-01-15 14:35:22 [SUCCESS] Download completed (5m 22s)
```

## Usage

### Web Interface

1. **Start the Application**:
   ```bash
   # Open in browser
   firefox periodica.html
   ```

2. **Search Photos**:
   - Set date range and coordinate filters
   - Draw bounding box on map
   - Select camera and film types
   - Click "Buscar" to search

3. **Download Photos**:
   - Select photos from results
   - Choose output folder
   - Click "Descargar Ahora" for immediate download
   - Or "Crear Cron" for scheduled download

### Periodic Tasks

1. **Configure Tasks**:
   Edit `tasks.json` to define batch processing schedules

2. **Run Manually**:
   ```bash
   ./launch_periodic.sh task_id
   ```

3. **Monitor Execution**:
   ```bash
   tail -f auto_log.txt
   ```

## API Integration

### NASA API Queries

The module builds complex queries to NASA's ISS photo API:

```javascript
// Example query construction
const query = queryBuilder.buildQuery(filters, coordSource, boundingBox);
// Result: "images|date|ge|2024-01-01|images|date|le|2024-01-31|nadir|lat|ge|8.0|nadir|lat|le|9.0|nadir|lon|ge|-80.0|nadir|lon|le|-79.0"
```

### Metadata Processing

Photos are processed to extract:
- Geographic coordinates (latitude/longitude)
- Camera metadata (altitude, orientation)
- Date/time information
- File paths and identifiers

## Dependencies

```
vue@3                 # Frontend framework
leaflet@1.7.1         # Map library
axios                 # HTTP client
cheerio               # HTML parsing
nprogress             # Progress indicators
```

## File Structure

```
periodic_tasks/
├── periodica.html           # Main web interface
├── rend_periodica.js        # Vue.js application logic
├── tasks.json              # Task configuration
├── launch_periodic.sh      # Batch execution script
├── metadatos_periodicos.json # Photo metadata
├── auto_log.txt           # Execution logs
├── style.css              # CSS styling
├── template.html          # Vue template
└── utils/
    ├── queryBuilder.js    # Query construction
    ├── mapHelpers.js      # Map utilities
    ├── photoUtils.js      # Photo processing
    ├── taskManager.js     # Task management
    ├── generalUtils.js    # General utilities
    └── data.js           # Data mappings
```

## Integration

### With Backend Module
- Uses `run_batch_processor.py` for periodic execution
- Shares metadata with `extract_enriched_metadata.py`
- Integrates with NASA API client

### With Database
- Stores photo metadata in SQLite database
- Updates location and camera information
- Tracks download status and history

### With Map Interface
- Provides data for main map visualization
- Shares coordinate and photo data
- Enables cross-module photo browsing

## Troubleshooting

### No Photos Found
- Check date range and coordinate filters
- Verify NASA API connectivity
- Review bounding box selection

### Download Failures
- Check available disk space
- Verify network connectivity
- Review auto_log.txt for error details

### Map Not Loading
- Ensure Leaflet CSS/JS are loaded
- Check browser console for JavaScript errors
- Verify coordinate data validity

## References

- [NASA ISS Photo API](https://eol.jsc.nasa.gov/SearchPhotos/)
- [Vue.js Documentation](https://vuejs.org/)
- [Leaflet Maps](https://leafletjs.com/)

---

For main system integration, see [Main README](../../README.md)

For NASA API details, see [Backend Module](../backend/README.md)
