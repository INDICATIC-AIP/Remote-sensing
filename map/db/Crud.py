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
from rutas import DB_URL


class MetadataCRUD:
    """
    Clase para realizar operaciones CRUD sobre los metadatos de imágenes almacenados en la base de datos.

    Métodos:
        get_paginated_metadatos(offset, limit): Obtiene registros paginados de la vista Metadatos.
        get_camera_name(image_id): Obtiene el nombre de la cámara para una imagen dada por su ID.
        get_image_id_by_nasa_id(nasa_id): Recupera el ID de una imagen a partir del ID de la NASA.
        create_image(...): Crea un nuevo registro de imagen.
        update_image_path(nasa_id, path): Actualiza la ruta del archivo para una imagen existente.
        delete_image(nasa_id): Elimina una imagen y su archivo asociado, si existe.
        create_image_details(...): Crea un registro de detalles asociados a una imagen.
        create_map_location(...): Crea un registro de localización geográfica para una imagen.
        create_camera_information(...): Crea un registro de información de cámara para una imagen.
        close_session(): Cierra la sesión activa de base de datos.
    """

    def __init__(self, db_url=DB_URL):
        """
        Inicializa la conexión con la base de datos y crea una sesión.

        Args:
            db_url (str): URL de conexión a la base de datos.
        """
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_paginated_metadatos(self, offset=0, limit=100):
        """
        Obtiene un subconjunto de registros de la vista Metadatos con paginación.

        Args:
            offset (int): Número de registros a omitir.
            limit (int): Número máximo de registros a devolver.

        Returns:
            list[tuple]: Lista de tuplas con los metadatos por imagen.
        """
        try:
            rows = (
                self.session.query(Metadatos)
                .order_by(
                    case(
                        (Metadatos.fecha.is_(None), 1),  # Si fecha es NULL → 1
                        else_=0,  # Si no → 0
                    ).asc(),  # Primero los no-nulos (0), luego los NULLs (1)
                    Metadatos.fecha.asc(),  # Luego ordena por la fecha real
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                (
                    row.id,
                    row.imagen,
                    row.nasa_id,
                    row.fecha,
                    row.hora,
                    row.resolucion,
                    row.nadir_lat,
                    row.nadir_lon,
                    row.center_lat,
                    row.center_lon,
                    row.nadir_center,
                    row.altitud,
                    row.lugar,
                    row.elevacion_sol,
                    row.azimut_sol,
                    row.cobertura_nubosa,
                    row.camara,
                    row.longitud_focal,
                    row.inclinacion,
                    row.formato,
                    row.camara_metadatos,
                )
                for row in rows
            ]
        except Exception as e:
            print(f"Error al obtener metadatos: {e}")
            return []

    def get_all_metadatos(self):
        """
        Obtiene todos los registros de la vista Metadatos sin paginación.

        Returns:
            list[tuple]: Lista de tuplas con todos los metadatos por imagen.
        """
        try:
            rows = (
                self.session.query(Metadatos)
                .order_by(
                    case(
                        (Metadatos.fecha.is_(None), 1),  # Si fecha es NULL → 1
                        else_=0,  # Si no → 0
                    ).asc(),  # Primero los no-nulos (0), luego los NULLs (1)
                    Metadatos.fecha.asc(),  # Luego ordena por la fecha real
                )
                .all()
            )
            return [
                (
                    row.id,
                    row.imagen,
                    row.nasa_id,
                    row.fecha,
                    row.hora,
                    row.resolucion,
                    row.nadir_lat,
                    row.nadir_lon,
                    row.center_lat,
                    row.center_lon,
                    row.nadir_center,
                    row.altitud,
                    row.lugar,
                    row.elevacion_sol,
                    row.azimut_sol,
                    row.cobertura_nubosa,
                    row.camara,
                    row.longitud_focal,
                    row.inclinacion,
                    row.formato,
                    row.camara_metadatos,
                )
                for row in rows
            ]
        except Exception as e:
            print(f"Error al obtener todos los metadatos: {e}")
            return []

    def get_camera_name(self, image_id):
        """
        Obtiene el nombre de la cámara asociada a una imagen.

        Args:
            image_id (int): ID de la imagen.

        Returns:
            str or None: Nombre de la cámara o None si no existe.
        """
        camera_info = (
            self.session.query(CameraInformation.camera)
            .filter_by(image_id=image_id)
            .first()
        )
        return camera_info.camera if camera_info else None

    def get_image_id_by_nasa_id(self, nasa_id):
        """
        Obtiene el ID interno de la imagen dado el identificador de la NASA.

        Args:
            nasa_id (str): Identificador de la NASA.

        Returns:
            int or None: ID interno de la imagen o None si no se encuentra.
        """
        image = self.session.query(Image.image_id).filter_by(nasa_id=nasa_id).first()
        return image.image_id if image else None

    def create_image(self, nasa_id, date, time, resolution, path):
        """
        Crea un nuevo registro de imagen en la base de datos.

        Args:
            nasa_id (str): ID de la NASA.
            date (date): Fecha de captura.
            time (time): Hora de captura.
            resolution (str): Resolución de la imagen.
            path (str): Ruta del archivo de imagen.

        Returns:
            Image: Instancia del objeto creado.
        """
        new_image = Image(
            nasa_id=nasa_id, date=date, time=time, resolution=resolution, path=path
        )
        self.session.add(new_image)
        self.session.commit()
        print(f"Imagen creada con ID: {new_image.image_id}")
        return new_image

    def update_image_path(self, nasa_id, path):
        """
        Actualiza la ruta del archivo de una imagen existente.

        Args:
            nasa_id (str): Identificador de la NASA.
            path (str): Nueva ruta del archivo de imagen.
        """
        try:
            image = self.session.query(Image).filter_by(nasa_id=nasa_id).first()
            if image:
                image.path = path
                self.session.commit()
                print(f"path actualizada para NASA ID: {nasa_id}")
            else:
                print(f"Imagen no encontrada para NASA ID: {nasa_id}")
        except Exception as e:
            self.session.rollback()
            print(f"Error al actualizar path para NASA ID {nasa_id}: {e}")

    def delete_image(self, nasa_id):
        """
        Elimina una imagen de la base de datos y borra el archivo si existe.

        Args:
            nasa_id (str): Identificador de la NASA.
        """
        try:
            image = self.session.query(Image).filter_by(nasa_id=nasa_id).first()
            path = self.session.query(Image.path).filter_by(nasa_id=nasa_id).first()
            if image:
                self.session.delete(image)
                if os.path.exists(path.path):
                    os.remove(path.path)
                self.session.commit()
                print(f"Imagen eliminada para NASA ID: {nasa_id}")
            else:
                print(f"Imagen no encontrada para NASA ID: {nasa_id}")
        except Exception as e:
            self.session.rollback()
            print(f"Error al eliminar imagen para NASA ID {nasa_id}: {e}")

    def create_image_details(
        self, image_id, features, sun_elevation, sun_azimuth, cloud_cover
    ):
        """
        Crea un registro de detalles de imagen.

        Args:
            image_id (int): ID de la imagen asociada.
            features (str): Características observadas.
            sun_elevation (float): Elevación solar.
            sun_azimuth (float): Azimut solar.
            cloud_cover (float): Porcentaje de nubes.

        Returns:
            ImageDetails: Objeto creado.
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
        print(f"Detalles creados para image_id: {image_id}")
        return new_detail

    def create_map_location(
        self,
        image_id,
        nadir_lat,
        nadir_lon,
        center_lat,
        center_lon,
        nadir_center,
        altitude,
    ):
        """
        Crea un registro de localización geográfica asociado a una imagen.

        Args:
            image_id (int): ID de la imagen asociada.
            nadir_lat (float): Latitud nadir.
            nadir_lon (float): Longitud nadir.
            center_lat (float): Latitud centro.
            center_lon (float): Longitud centro.
            nadir_center (str): Descripción de posición.
            altitude (float): Altitud de captura.

        Returns:
            MapLocation: Objeto creado.
        """
        new_location = MapLocation(
            image_id=image_id,
            nadir_lat=nadir_lat,
            nadir_lon=nadir_lon,
            center_lat=center_lat,
            center_lon=center_lon,
            nadir_center=nadir_center,
            altitude=altitude,
        )
        self.session.add(new_location)
        self.session.commit()
        print(f"Ubicación creada para image_id: {image_id}")
        return new_location

    def create_camera_information(
        self, image_id, camera, focal_length, tilt, format, camera_metadata
    ):
        """
        Crea un registro de información de cámara asociado a una imagen.

        Args:
            image_id (int): ID de la imagen asociada.
            camera (str): Nombre de la cámara.
            focal_length (float): Longitud focal del lente.
            tilt (str): Inclinación de la cámara.
            format (str): Formato de imagen.
            camera_metadata (str): Otros metadatos relevantes.

        Returns:
            CameraInformation: Objeto creado.
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
        print(f"Información de cámara creada para image_id: {image_id}")
        return new_camera

    def close_session(self):
        self.session.close()
