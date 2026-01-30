from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Image(Base):
    """
    Represents a NASA-registered image with basic metadata.

    Attributes:
        image_id (int): Unique image identifier.
        nasa_id (str): Unique image identifier provided by NASA.
        date (date): Capture date.
        time (time): Capture time.
        resolution (str): Image resolution.
        path (str): File path of the image on disk.

    Relationships:
        details (ImageDetails): Detailed information associated with the image.
        location_data (MapLocation): Geographic information related to the image.
        camera_info (CameraInformation): Camera information for the image.
    """

    __tablename__ = "Image"

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    nasa_id = Column(String(100), nullable=False, unique=True)
    date = Column(Date, nullable=True)
    time = Column(Time, nullable=True)
    resolution = Column(String(50), nullable=True)
    path = Column(String(255), nullable=True)

    details = relationship(
        "ImageDetails", back_populates="image", cascade="all, delete-orphan"
    )
    location_data = relationship(
        "MapLocation", back_populates="image", cascade="all, delete-orphan"
    )
    camera_info = relationship(
        "CameraInformation", back_populates="image", cascade="all, delete-orphan"
    )


class ImageDetails(Base):
    """
    Additional information about an image, such as capture conditions.

    Attributes:
        image_id (int): Foreign key referencing the associated image.
        features (str): Relevant features detected in the image.
        sun_elevation (float): Sun elevation at capture time.
        sun_azimuth (float): Sun azimuth at capture time.
        cloud_cover (float): Cloud cover percentage.

    Relationships:
        image (Image): Image associated with these details.
    """

    __tablename__ = "ImageDetails"

    image_id = Column(Integer, ForeignKey("Image.image_id"), primary_key=True)
    features = Column(String, nullable=True)
    sun_elevation = Column(Float, nullable=True)
    sun_azimuth = Column(Float, nullable=True)
    cloud_cover = Column(Float, nullable=True)

    image = relationship("Image", back_populates="details")


class MapLocation(Base):
    """
    Geographic location data associated with an image.

    Attributes:
        image_id (int): Foreign key referencing the associated image.
        nadir_lat (float): Latitude at the nadir point.
        nadir_lon (float): Longitude at the nadir point.
        center_lat (float): Center latitude.
        center_lon (float): Center longitude.
        nadir_center (str): Description of nadir/center position.
        altitudee (float): Capture altitude.

    Relationships:
        image (Image): Image associated with this location.
    """

    __tablename__ = "MapLocation"

    image_id = Column(Integer, ForeignKey("Image.image_id"), primary_key=True)
    nadir_lat = Column(Float, nullable=True)
    nadir_lon = Column(Float, nullable=True)
    center_lat = Column(Float, nullable=True)
    center_lon = Column(Float, nullable=True)
    nadir_center = Column(String(50), nullable=True)
    altitudee = Column(Float, nullable=True)

    image = relationship("Image", back_populates="location_data")


class CameraInformation(Base):
    """
    Technical camera information for an image.

    Attributes:
        image_id (int): Foreign key referencing the associated image.
        camera (str): Camera name or type.
        focal_length (float): Lens focal length.
        tilt (str): Camera tilt.
        format (str): Image format used.
        camera_metadata (str): Additional camera metadata.

    Relationships:
        image (Image): Image associated with this camera information.
    """

    __tablename__ = "CameraInformation"

    image_id = Column(Integer, ForeignKey("Image.image_id"), primary_key=True)
    camera = Column(String(100), nullable=True)
    focal_length = Column(Float, nullable=True)
    tilt = Column(String(50), nullable=True)
    format = Column(String(100), nullable=True)
    camera_metadata = Column(String(50), nullable=True)

    image = relationship("Image", back_populates="camera_info")


class Metadatos(Base):
    """
    Combined view that aggregates all metadata related to an image.

    Attributes:
        id (int): Unique identifier.
        image (str): Image filename.
        nasa_id (str): Image identifier provided by NASA.
        date (date): Capture date.
        time (time): Capture time.
        resolution (str): Image resolution.
        nadir_lat (float): Latitude at the nadir point.
        nadir_lon (float): Longitude at the nadir point.
        center_lat (float): Center latitude.
        center_lon (float): Center longitude.
        nadir_center (str): Description of central position.
        altitude (float): Capture altitude.
        place (str): Place associated with the image (if applicable).
        elevacion_sol (float): Solar elevation at capture time.
        azimut_sol (float): Solar azimuth at capture time.
        cobertura_nubosa (float): Cloud cover percentage.
        camera (str): Camera type or model.
        longitude_focal (float): Lens focal length.
        inclinacion (str): Camera tilt angle.
        formato (str): Image format.
        camera_metadata (str): Additional camera information.
    """

    __tablename__ = "Metadatos"  # Vista
    id = Column(Integer, primary_key=True)
    image = Column(String)
    nasa_id = Column(String)
    date = Column(Date)
    time = Column(Time)
    resolution = Column(String)
    nadir_lat = Column(Float)
    nadir_lon = Column(Float)
    center_lat = Column(Float)
    center_lon = Column(Float)
    nadir_center = Column(String)
    altitude = Column(Float)
    place = Column(String)
    elevacion_sol = Column(Float)
    azimut_sol = Column(Float)
    cobertura_nubosa = Column(Float)
    camera = Column(String)
    longitude_focal = Column(Float)
    inclinacion = Column(String)
    formato = Column(String)
    camera_metadata = Column(String)
