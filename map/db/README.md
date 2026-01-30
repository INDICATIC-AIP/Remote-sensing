# Database Layer (db/)

## Overview

The **Database Layer** manages all data persistence, schema definitions, and CRUD operations. It provides a centralized SQLite database for storing satellite imagery metadata, geospatial information, and processing status.

## Files

### `Tables.py`
**Purpose**: Database schema initialization and table creation

- Creates SQLite database structure on first run
- Defines all core tables with proper data types and constraints
- Sets up indices for geospatial queries and fast lookups
- Handles schema migrations and upgrades

**Usage**:
```bash
python Tables.py
```

### `Crud.py`
**Purpose**: CRUD (Create, Read, Update, Delete) operations through MetadataCRUD class

Core database operations for the system:

| Operation | Method | Description |
|-----------|--------|-------------|
| **Create** | `create_image()` | Add new image record with NASA ID |
| **Create** | `create_image_details()` | Add detailed capture information |
| **Create** | `create_map_location()` | Add geographic coordinates |
| **Create** | `create_camera_information()` | Add camera technical specs |
| **Read** | `get_paginated_metadata()` | Retrieve metadata with pagination |
| **Read** | `get_all_metadata()` | Retrieve all metadata records |
| **Read** | `get_camera_name()` | Get camera name for an image |
| **Read** | `get_image_id_by_nasa_id()` | Get internal ID from NASA ID |
| **Update** | `update_image_path()` | Update file path for an image |
| **Delete** | `delete_image()` | Remove image and file from system |

**Usage Example**:
```python
from db.Crud import MetadataCRUD
from datetime import date, time

# Initialize database connection
db = MetadataCRUD()

# Create a complete image record
image = db.create_image(
    nasa_id='ISS073-E-122523',
    date=date(2024, 1, 15),
    time=time(14, 30, 0),
    resolution='4928 x 3280',
    path='/path/to/image.jpg'
)

# Add geographic location
db.create_map_location(
    image_id=image.image_id,
    nadir_lat=8.5,
    nadir_lon=-80.5,
    center_lat=8.6,
    center_lon=-80.4,
    nadir_center='Panama Basin',
    altitudee=408000
)

# Query paginated metadata
metadata = db.get_paginated_metadata(offset=0, limit=100)

# Update image path
db.update_image_path('ISS073-E-122523', '/new/path/image.jpg')

# Close session when done
db.close_session()
```

### `metadata.sql`
**Purpose**: SQL schema definitions

Defines the complete database structure:

#### Core Tables

**Image Table**
```sql
CREATE TABLE Image (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nasa_id VARCHAR(100) NOT NULL UNIQUE,
    date DATE,
    time TIME,
    resolution VARCHAR(50),
    path VARCHAR(255)
)
```

**Purpose**: Core table storing ISS image metadata with NASA identifiers.

**ImageDetails Table**
```sql
CREATE TABLE ImageDetails (
    image_id INTEGER PRIMARY KEY,
    features TEXT,
    sun_elevation REAL,
    sun_azimuth REAL,
    cloud_cover REAL,
    FOREIGN KEY(image_id) REFERENCES Image(image_id)
)
```

**Purpose**: Stores capture conditions including solar position and cloud coverage.

**MapLocation Table**
```sql
CREATE TABLE MapLocation (
    image_id INTEGER PRIMARY KEY,
    nadir_lat REAL,
    nadir_lon REAL,
    center_lat REAL,
    center_lon REAL,
    nadir_center VARCHAR(50),
    altitudee REAL,
    FOREIGN KEY(image_id) REFERENCES Image(image_id)
)
```

**Purpose**: Geographic coordinates with both nadir point and image center locations.

**CameraInformation Table**
```sql
CREATE TABLE CameraInformation (
    image_id INTEGER PRIMARY KEY,
    camera VARCHAR(100),
    focal_length REAL,
    tilt VARCHAR(50),
    format VARCHAR(100),
    camera_metadata VARCHAR(50),
    FOREIGN KEY(image_id) REFERENCES Image(image_id)
)
```

**Purpose**: Technical camera specifications for each capture.

**Metadatos View**
```sql
CREATE VIEW Metadatos AS
SELECT 
    i.image_id as id,
    i.path as image,
    i.nasa_id,
    i.date,
    i.time,
    i.resolution,
    m.nadir_lat,
    m.nadir_lon,
    m.center_lat,
    m.center_lon,
    m.nadir_center,
    m.altitudee as altitude,
    NULL as place,
    d.sun_elevation as elevacion_sol,
    d.sun_azimuth as azimut_sol,
    d.cloud_cover as cobertura_nubosa,
    c.camera,
    c.focal_length as longitude_focal,
    c.tilt as inclinacion,
    c.format as formato,
    c.camera_metadata
FROM Image i
LEFT JOIN MapLocation m ON i.image_id = m.image_id
LEFT JOIN ImageDetails d ON i.image_id = d.image_id
LEFT JOIN CameraInformation c ON i.image_id = c.image_id
```

**Purpose**: Unified view combining all metadata for easy querying and display.

## Database Operations

### Initialization

The database is automatically created when you first instantiate `MetadataCRUD`:

```python
from db.Crud import MetadataCRUD

# This automatically creates the database and all tables
db = MetadataCRUD()
db.close_session()
```

Or initialize manually:

```bash
# Create database schema
python -c "from db.Crud import MetadataCRUD; MetadataCRUD().close_session()"

# Verify database creation
ls -lh metadata.db

# Check tables
sqlite3 metadata.db ".tables"
# Expected output: Image  ImageDetails  MapLocation  CameraInformation  Metadatos
```

### Backup

```bash
# Backup database
cp db/metadata.db db/metadata_backup_$(date +%Y%m%d).db
```

### Verification

```bash
# Check database integrity
sqlite3 db/metadata.db "PRAGMA integrity_check;"

# List all tables
sqlite3 db/metadata.db ".tables"
```

## Data Types & Constraints

| Type | Usage |
|------|-------|
| **TEXT** | Filenames, paths, satellite types |
| **INTEGER** | IDs, resolutions, pixel counts |
| **REAL** | Coordinates, physical measurements |
| **TIMESTAMP** | Acquisition and processing times |
| **BLOB** | (Reserved for binary data) |

## Querying Metadata

The system uses the `Metadatos` view for efficient data retrieval:

```python
from db.Crud import MetadataCRUD

db = MetadataCRUD()

# Get paginated results
metadata = db.get_paginated_metadata(offset=0, limit=50)

# Get all metadata (use with caution for large datasets)
all_metadata = db.get_all_metadata()

# Access specific fields from results
for record in metadata:
    image_id, image_path, nasa_id, date, time, resolution, \
    nadir_lat, nadir_lon, center_lat, center_lon, nadir_center, \
    altitude, place, sun_elevation, sun_azimuth, cloud_cover, \
    camera, focal_length, tilt, format, camera_metadata = record
    
    print(f"NASA ID: {nasa_id}, Date: {date}, Location: ({nadir_lat}, {nadir_lon})")

# Get camera name for specific image
image_id = db.get_image_id_by_nasa_id('ISS073-E-122523')
if image_id:
    camera = db.get_camera_name(image_id)
    print(f"Camera: {camera}")

db.close_session()
```

### Custom Queries

For advanced queries, access the session directly:

```python
from db.Crud import MetadataCRUD
from db.Tables import Metadatos, MapLocation
from datetime import date

db = MetadataCRUD()

# Query images by date range
images_in_range = db.session.query(Metadatos).filter(
    Metadatos.date.between(date(2024, 1, 1), date(2024, 1, 31))
).all()

# Query by geographic bounds
images_in_region = db.session.query(Metadatos).filter(
    Metadatos.nadir_lat.between(8.0, 9.0),
    Metadatos.nadir_lon.between(-81.0, -80.0)
).all()

# Query by camera type
images_by_camera = db.session.query(Metadatos).filter(
    Metadatos.camera.like('%Nikon%')
).all()

db.close_session()
```

## Performance Considerations

- **Primary keys**: Automatic indexing on `image_id` across all tables
- **Unique constraint**: Index on `nasa_id` for fast lookups
- **Foreign keys**: Relationships optimized with SQLAlchemy ORM
- **Pagination**: Use `get_paginated_metadata()` to limit memory usage
- **View optimization**: `Metadatos` view pre-joins all related tables
- **Regular maintenance**: 
  ```bash
  # Vacuum database monthly
  sqlite3 metadata.db "VACUUM;"
  
  # Analyze query performance
  sqlite3 metadata.db "ANALYZE;"
  ```

### Best Practices

1. **Use pagination** for large result sets:
   ```python
   # Good: paginated access
   db.get_paginated_metadata(offset=0, limit=100)
   
   # Avoid: loading all records at once
   # db.get_all_metadata()  # Only for small datasets
   ```

2. **Close sessions** after use:
   ```python
   db = MetadataCRUD()
   try:
       # ... operations ...
   finally:
       db.close_session()
   ```

3. **Batch operations** for multiple inserts:
   ```python
   for image_data in batch:
       image = db.create_image(**image_data)
       db.create_map_location(image.image_id, **location_data)
   # Session commits automatically after each operation
   ```

## Troubleshooting

### Database Locked
```bash
# Check for running processes
lsof | grep metadata.db

# Kill blocking process if needed
fuser -k metadata.db

# Or wait for automatic timeout (SQLAlchemy handles this)
```

### Connection Issues
```python
# Ensure you're using the correct database URL
from map.routes import DB_URL
print(f"Database URL: {DB_URL}")

# Test connection
from db.Crud import MetadataCRUD
try:
    db = MetadataCRUD()
    print("Connection successful")
    db.close_session()
except Exception as e:
    print(f"Connection failed: {e}")
```

### Duplicate NASA ID
```python
# Handle unique constraint violations
try:
    db.create_image(nasa_id='ISS073-E-122523', ...)
except Exception as e:
    if 'UNIQUE constraint' in str(e):
        print("Image already exists, updating path instead")
        db.update_image_path('ISS073-E-122523', new_path)
```

### Query Performance
```bash
# Analyze query plans
sqlite3 metadata.db "EXPLAIN QUERY PLAN SELECT * FROM Metadatos WHERE date > '2024-01-01';"

# Check database size
du -h metadata.db

# Optimize database
sqlite3 metadata.db "VACUUM; ANALYZE;"
```

### Schema Migration
```bash
# Backup before any schema changes
cp metadata.db metadata_backup_$(date +%Y%m%d).db

# For schema updates, preserve data:
sqlite3 metadata.db .dump > backup.sql
rm metadata.db
# Update Tables.py with new schema
python -c "from db.Crud import MetadataCRUD; MetadataCRUD().close_session()"
sqlite3 metadata.db < backup.sql
```

## Integration with Other Modules

- **backend/**: Uses CRUD operations to store API results
- **scripts/**: Queries database for processing workflows
- **periodic_tasks/**: Manages scheduled metadata updates
- **map/**: Visualizes database records on web maps

---

For detailed CRUD method documentation, see [Crud.py](Crud.py)
