DROP TABLE IF EXISTS CameraInformation;
DROP TABLE IF EXISTS MapLocation;
DROP TABLE IF EXISTS ImageDetails;
DROP TABLE IF EXISTS Image;
DROP VIEW IF EXISTS Metadatos;

CREATE TABLE Image (
    image_id INTEGER PRIMARY KEY AUTOINCREMENT,
    nasa_id VARCHAR(100) NOT NULL UNIQUE,
    date DATE,
    time TIME,
    resolution VARCHAR(50),
    path VARCHAR(255)
);

CREATE TABLE ImageDetails (
    image_id INTEGER PRIMARY KEY,
    features TEXT,
    sun_elevation FLOAT,
    sun_azimuth FLOAT,
    cloud_cover FLOAT,
    FOREIGN KEY (image_id) REFERENCES Image(image_id) 
    ON DELETE CASCADE
);

CREATE TABLE MapLocation (
    image_id INTEGER PRIMARY KEY,
    nadir_lat FLOAT,
    nadir_lon FLOAT,
    center_lat FLOAT,
    center_lon FLOAT,
    nadir_center VARCHAR(50),
    altitude FLOAT,
    FOREIGN KEY (image_id) REFERENCES Image(image_id) 
    ON DELETE CASCADE
);

CREATE TABLE CameraInformation (
    image_id INTEGER PRIMARY KEY,
    camera VARCHAR(100),
    focal_length FLOAT,
    tilt VARCHAR(50),
    format VARCHAR(100),
    camera_metadata VARCHAR(50),
    FOREIGN KEY (image_id) REFERENCES Image(image_id)
    ON DELETE CASCADE
);

CREATE INDEX idx_image_details ON ImageDetails(image_id);
CREATE INDEX idx_map_location ON MapLocation(image_id);
CREATE INDEX idx_camera_info ON CameraInformation(image_id);

CREATE VIEW Metadatos AS
SELECT 
    i.image_id AS ID,
    i.path AS IMAGEN, 
    i.nasa_id AS NASA_ID, 
    i.date AS FECHA, 
    i.time AS HORA, 
    i.resolution AS RESOLUCION,
    ml.nadir_lat AS NADIR_LAT, 
    ml.nadir_lon AS NADIR_LON, 
    ml.center_lat AS CENTER_LAT, 
    ml.center_lon AS CENTER_LON, 
    ml.nadir_center AS NADIR_CENTER, 
    ml.altitude AS ALTITUD, 
    im.features AS LUGAR, 
    im.sun_elevation AS ELEVACION_SOL, 
    im.sun_azimuth AS AZIMUT_SOL, 
    im.cloud_cover AS COBERTURA_NUBOSA, 
    ci.camera AS CAMARA, 
    ci.focal_length AS LONGITUD_FOCAL, 
    ci.tilt AS INCLINACION, 
    ci.format AS FORMATO,
    ci.camera_metadata AS CAMARA_METADATOS
FROM 
    Image AS i
INNER JOIN 
    MapLocation AS ml ON i.image_id = ml.image_id
INNER JOIN 
    ImageDetails AS im ON i.image_id = im.image_id
INNER JOIN 
    CameraInformation AS ci ON i.image_id = ci.image_id;

    
-- ORDER BY i.image_id ASC;


-- select count(*) from Metadatos where ELEVACION_SOL > 300.0;

-- select ELEVACION_SOL from Metadatos ORDER BY ELEVACION_SOL DESC;

-- SELECT ELEVACION_SOL, NASA_ID, FECHA, MISSION FROM Metadatos WHERE ELEVACION_SOL > 0 OR ELEVACION_SOL IS NULL LIMIT 10;

-- SELECT COUNT(*) FROM Metadatos WHERE ( strftime('%H%M' , FECHA) >= '19:45' OR strftime('%H%M' , FECHA) >= '05:30');