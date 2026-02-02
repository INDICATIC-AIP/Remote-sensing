from sqlalchemy import create_engine, case
from sqlalchemy.orm import sessionmaker
from db.Tables import (
    Base,
    Image,
    ImageDetails,
    MapLocation,
    CameraInformation,
    Metadatos,
)
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from map.routes import DB_URL


class MetadataCRUD:
    """
    CRUD helper for image metadata stored in the database.

    Methods:
        get_paginated_metadata(offset, limit): Return paginated records from the Metadatos view.
        get_camera_name(image_id): Get the camera name for an image by its ID.
        get_image_id_by_nasa_id(nasa_id): Retrieve the internal image ID by NASA ID.
        create_image(...): Create a new image record.
        update_image_path(nasa_id, path): Update the file path for an existing image.
        delete_image(nasa_id): Delete an image and its file if it exists.
        create_image_details(...): Create a details record associated with an image.
        create_map_location(...): Create a geographic location record for an image.
        create_camera_information(...): Create a camera information record for an image.
        close_session(): Close the active database session.
    """

    def __init__(self, db_url=DB_URL):
        """
        Initialize the database connection and create a session.

        Args:
            db_url (str): Database connection URL.
        """
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_paginated_metadata(self, offset=0, limit=100):
        """
        Retrieve a subset of Metadatos records with pagination.

        Args:
            offset (int): Number of records to skip.
            limit (int): Maximum number of records to return.

        Returns:
            list[tuple]: Tuples containing metadata per image.
        """
        try:
            rows = (
                self.session.query(Metadatos)
                .order_by(
                    case(
                        (Metadatos.FECHA.is_(None), 1),  # Si FECHA es NULL → 1
                        else_=0,  # Si no → 0
                    ).asc(),  # Primero los no-nulos (0), luego los NULLs (1)
                    Metadatos.FECHA.asc(),  # Luego ordena por la FECHA real
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                (
                    row.ID,
                    row.IMAGEN,
                    row.NASA_ID,
                    row.FECHA,
                    row.HORA,
                    row.RESOLUCION,
                    row.NADIR_LAT,
                    row.NADIR_LON,
                    row.CENTER_LAT,
                    row.CENTER_LON,
                    row.NADIR_CENTER,
                    row.ALTITUD,
                    row.LUGAR,
                    row.ELEVACION_SOL,
                    row.AZIMUT_SOL,
                    row.COBERTURA_NUBOSA,
                    row.CAMARA,
                    row.LONGITUD_FOCAL,
                    row.INCLINACION,
                    row.FORMATO,
                    row.CAMARA_METADATOS,
                )
                for row in rows
            ]
        except Exception as e:
            print(f"Error retrieving metadata: {e}")
            return []

    def get_all_metadata(self):
        """
        Retrieve all records from the Metadatos view (no pagination).

        Returns:
            list[tuple]: Tuples containing metadata per image.
        """
        try:
            rows = (
                self.session.query(Metadatos)
                .order_by(
                    case(
                        (Metadatos.FECHA.is_(None), 1),  # Si FECHA es NULL → 1
                        else_=0,  # Si no → 0
                    ).asc(),  # Primero los no-nulos (0), luego los NULLs (1)
                    Metadatos.FECHA.asc(),  # Luego ordena por la FECHA real
                )
                .all()
            )
            return [
                (
                    row.ID,
                    row.IMAGEN,
                    row.NASA_ID,
                    row.FECHA,
                    row.HORA,
                    row.RESOLUCION,
                    row.NADIR_LAT,
                    row.NADIR_LON,
                    row.CENTER_LAT,
                    row.CENTER_LON,
                    row.NADIR_CENTER,
                    row.ALTITUD,
                    row.LUGAR,
                    row.ELEVACION_SOL,
                    row.AZIMUT_SOL,
                    row.COBERTURA_NUBOSA,
                    row.CAMARA,
                    row.LONGITUD_FOCAL,
                    row.INCLINACION,
                    row.FORMATO,
                    row.CAMARA_METADATOS,
                )
                for row in rows
            ]
        except Exception as e:
            print(f"Error retrieving all metadata: {e}")
            return []

    def get_camera_name(self, image_id):
        """
        Get the camera name associated with an image.

        Args:
            image_id (int): Image ID.

        Returns:
            str or None: Camera name or None if it does not exist.
        """
        camera_info = (
            self.session.query(CameraInformation.camera)
            .filter_by(image_id=image_id)
            .first()
        )
        return camera_info.camera if camera_info else None

    def get_image_id_by_nasa_id(self, nasa_id):
        """
        Get the internal image ID given the NASA identifier.

        Args:
            nasa_id (str): NASA identifier.

        Returns:
            int or None: Internal image ID or None if not found.
        """
        image = self.session.query(Image.image_id).filter_by(nasa_id=nasa_id).first()
        return image.image_id if image else None

    def create_image(self, nasa_id, date, time, resolution, path):
        """
        Create a new image record in the database.

        Args:
            nasa_id (str): NASA ID.
            date (date): Capture date.
            time (time): Capture time.
            resolution (str): Image resolution.
            path (str): Image file path.

        Returns:
            Image: Created instance.
        """
        new_image = Image(
            nasa_id=nasa_id, date=date, time=time, resolution=resolution, path=path
        )
        self.session.add(new_image)
        self.session.commit()
        print(f"Image created with ID: {new_image.image_id}")
        return new_image

    def update_image_path(self, nasa_id, path):
        """
        Update the file path for an existing image.

        Args:
            nasa_id (str): NASA identifier.
            path (str): New image file path.
        """
        try:
            image = self.session.query(Image).filter_by(nasa_id=nasa_id).first()
            if image:
                image.path = path
                self.session.commit()
                print(f"Path updated for NASA ID: {nasa_id}")
            else:
                print(f"Image not found for NASA ID: {nasa_id}")
        except Exception as e:
            self.session.rollback()
            print(f"Error updating path for NASA ID {nasa_id}: {e}")

    def delete_image(self, nasa_id):
        """
        Delete an image from the database and remove the file if it exists.

        Args:
            nasa_id (str): NASA identifier.
        """
        try:
            image = self.session.query(Image).filter_by(nasa_id=nasa_id).first()
            path = self.session.query(Image.path).filter_by(nasa_id=nasa_id).first()
            if image:
                self.session.delete(image)
                if os.path.exists(path.path):
                    os.remove(path.path)
                self.session.commit()
                print(f"Image deleted for NASA ID: {nasa_id}")
            else:
                print(f"Image not found for NASA ID: {nasa_id}")
        except Exception as e:
            self.session.rollback()
            print(f"Error deleting image for NASA ID {nasa_id}: {e}")

    def create_image_details(
        self, image_id, features, sun_elevation, sun_azimuth, cloud_cover
    ):
        """
        Create an image detail record.

        Args:
            image_id (int): Associated image ID.
            features (str): Observed features.
            sun_elevation (float): Solar elevation.
            sun_azimuth (float): Solar azimuth.
            cloud_cover (float): Cloud cover percentage.

        Returns:
            ImageDetails: Created object.
        """
        new_detail = ImageDetails(
            image_id=image_id,
            features=features,
            sun_elevation=sun_elevation,
            sun_azimuth=sun_azimuth,
            cloud_cover=cloud_cover,
        )
        self.session.add(new_detail)
        self.session.commit()
        print(f"Details created for image_id: {image_id}")
        return new_detail

    def create_map_location(
        self,
        image_id,
        nadir_lat,
        nadir_lon,
        center_lat,
        center_lon,
        nadir_center,
        altitudee,
    ):
        """
        Create a geographic location record associated with an image.

        Args:
            image_id (int): Associated image ID.
            nadir_lat (float): Nadir latitude.
            nadir_lon (float): Nadir longitude.
            center_lat (float): Center latitude.
            center_lon (float): Center longitude.
            nadir_center (str): Position description.
            altitudee (float): Capture altitude.

        Returns:
            MapLocation: Created object.
        """
        new_location = MapLocation(
            image_id=image_id,
            nadir_lat=nadir_lat,
            nadir_lon=nadir_lon,
            center_lat=center_lat,
            center_lon=center_lon,
            nadir_center=nadir_center,
            altitudee=altitudee,
        )
        self.session.add(new_location)
        self.session.commit()
        print(f"Location created for image_id: {image_id}")
        return new_location

    def create_camera_information(
        self, image_id, camera, focal_length, tilt, format, camera_metadata
    ):
        """
        Create a camera information record associated with an image.

        Args:
            image_id (int): Associated image ID.
            camera (str): Camera name.
            focal_length (float): Lens focal length.
            tilt (str): Camera tilt.
            format (str): Image format.
            camera_metadata (str): Other relevant metadata.

        Returns:
            CameraInformation: Created object.
        """
        new_camera = CameraInformation(
            image_id=image_id,
            camera=camera,
            focal_length=focal_length,
            tilt=tilt,
            format=format,
            camera_metadata=camera_metadata,
        )
        self.session.add(new_camera)
        self.session.commit()
        print(f"Camera information created for image_id: {image_id}")
        return new_camera

    def close_session(self):
        self.session.close()
