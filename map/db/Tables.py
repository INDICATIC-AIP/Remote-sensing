from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Image(Base):
    """
    Representa una imagen registrada por NASA con metadatos básicos.

    Atributos:
        image_id (int): Identificador único de la imagen.
        nasa_id (str): Identificador único de la imagen proporcionado por la NASA.
        date (date): Fecha de captura de la imagen.
        time (time): Hora de captura de la imagen.
        resolution (str): Resolución de la imagen.
        path (str): Ruta del archivo de la imagen en el sistema.

    Relaciones:
        details (ImageDetails): Información detallada asociada a la imagen.
        location_data (MapLocation): Información geográfica relacionada con la imagen.
        camera_info (CameraInformation): Información de la cámara que capturó la imagen.
    """

    __tablename__ = 'Image'

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    nasa_id = Column(String(100), nullable=False, unique=True)
    date = Column(Date, nullable=True)
    time = Column(Time, nullable=True)
    resolution = Column(String(50), nullable=True)
    path = Column(String(255), nullable=True)

    details = relationship("ImageDetails", back_populates="image", cascade="all, delete-orphan")
    location_data = relationship("MapLocation", back_populates="image", cascade="all, delete-orphan")
    camera_info = relationship("CameraInformation", back_populates="image", cascade="all, delete-orphan")


class ImageDetails(Base):
    """
    Contiene información adicional sobre una imagen, como condiciones de captura.

    Atributos:
        image_id (int): Clave foránea que hace referencia a la imagen asociada.
        features (str): Características relevantes detectadas en la imagen.
        sun_elevation (float): Elevación del sol al momento de la captura.
        sun_azimuth (float): Azimut del sol al momento de la captura.
        cloud_cover (float): Porcentaje de cobertura nubosa en la imagen.

    Relaciones:
        image (Image): Imagen asociada a estos detalles.
    """
    __tablename__ = 'ImageDetails'

    image_id = Column(Integer, ForeignKey('Image.image_id'), primary_key=True)
    features = Column(String, nullable=True)
    sun_elevation = Column(Float, nullable=True)
    sun_azimuth = Column(Float, nullable=True)
    cloud_cover = Column(Float, nullable=True)
    
    image = relationship("Image", back_populates="details")


class MapLocation(Base):
    """
    Contiene datos de localización geográfica asociados a una imagen.

    Atributos:
        image_id (int): Clave foránea que hace referencia a la imagen asociada.
        nadir_lat (float): Latitud en el punto nadir.
        nadir_lon (float): Longitud en el punto nadir.
        center_lat (float): Latitud del centro de la imagen.
        center_lon (float): Longitud del centro de la imagen.
        nadir_center (str): Descripción de la posición nadir/centro.
        altitude (float): Altitud a la que fue tomada la imagen.

    Relaciones:
        image (Image): Imagen asociada a esta localización.
    """

    __tablename__ = 'MapLocation'

    image_id = Column(Integer, ForeignKey('Image.image_id'), primary_key=True)
    nadir_lat = Column(Float, nullable=True)
    nadir_lon = Column(Float, nullable=True)
    center_lat = Column(Float, nullable=True)
    center_lon = Column(Float, nullable=True)
    nadir_center = Column(String(50), nullable=True)
    altitude = Column(Float, nullable=True)

    image = relationship("Image", back_populates="location_data")


class CameraInformation(Base):
    """
    Información técnica de la cámara que capturó la imagen.

    Atributos:
        image_id (int): Clave foránea que hace referencia a la imagen asociada.
        camera (str): Nombre o tipo de la cámara.
        focal_length (float): Longitud focal del lente usado.
        tilt (str): Inclinación de la cámara.
        format (str): Formato de imagen utilizado.
        camera_metadata (str): Otros metadatos relevantes de la cámara.

    Relaciones:
        image (Image): Imagen asociada a esta información de cámara.
    """
    __tablename__ = 'CameraInformation'

    image_id = Column(Integer, ForeignKey('Image.image_id'), primary_key=True)
    camera = Column(String(100), nullable=True)
    focal_length = Column(Float, nullable=True)
    tilt = Column(String(50), nullable=True)
    format = Column(String(100), nullable=True)
    camera_metadata = Column(String(50), nullable=True)

    image = relationship("Image", back_populates="camera_info")


class Metadatos(Base):
    """
    Vista combinada que reúne todos los metadatos relacionados con una imagen.

    Atributos:
        id (int): Identificador único.
        imagen (str): Nombre del archivo de imagen.
        nasa_id (str): Identificador de imagen proporcionado por NASA.
        fecha (date): Fecha de captura.
        hora (time): Hora de captura.
        resolucion (str): Resolución de la imagen.
        nadir_lat (float): Latitud en el punto nadir.
        nadir_lon (float): Longitud en el punto nadir.
        center_lat (float): Latitud del centro de la imagen.
        center_lon (float): Longitud del centro de la imagen.
        nadir_center (str): Descripción de la ubicación central.
        altitud (float): Altitud de la captura.
        lugar (str): Lugar asociado a la imagen (si aplica).
        elevacion_sol (float): Elevación solar al momento de la imagen.
        azimut_sol (float): Azimut solar al momento de la imagen.
        cobertura_nubosa (float): Cobertura nubosa en porcentaje.
        camara (str): Tipo o modelo de cámara.
        longitud_focal (float): Longitud focal del lente.
        inclinacion (str): Ángulo de inclinación de la cámara.
        formato (str): Formato de la imagen.
        camara_metadatos (str): Información adicional sobre la cámara.
    """
    __tablename__ = 'Metadatos'  # Vista
    id = Column(Integer, primary_key=True)
    imagen = Column(String)
    nasa_id = Column(String)
    fecha = Column(Date)
    hora = Column(Time)
    resolucion = Column(String)
    nadir_lat = Column(Float)
    nadir_lon = Column(Float)
    center_lat = Column(Float)
    center_lon = Column(Float)
    nadir_center = Column(String)
    altitud = Column(Float)
    lugar = Column(String)
    elevacion_sol = Column(Float)
    azimut_sol = Column(Float)
    cobertura_nubosa = Column(Float)
    camara = Column(String)
    longitud_focal = Column(Float)
    inclinacion = Column(String)
    formato = Column(String)
    camara_metadatos = Column(String)
