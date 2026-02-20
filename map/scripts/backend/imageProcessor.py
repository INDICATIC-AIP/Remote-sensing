# ==========================================
# DESCARGA DIRECTA AL NAS CON ARIA2C OPTIMIZADO
# ==========================================

import os
import re
import shutil
import sys
import subprocess
import time
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import List, Dict, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from map.routes import NAS_PATH, NAS_MOUNT

#  IMPORTAR LOG_CUSTOM
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom

#  LOG COHERENTE EN RUTA CORRECTA
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "iss", "general.log")


def verificar_destination_descarga():
    """
    VERIFICAR DESTINO: NAS (production) o LOCAL (solo tests)
    """
    nas_available = os.path.exists(NAS_PATH) and os.access(NAS_PATH, os.R_OK | os.W_OK)

    if nas_available:
        #  PRODUCCIÓN: Descargar directamente al NAS
        base_path = NAS_PATH
        mode = "PRODUCCIÓN (NAS)"
        log_custom(
            section="Configuración Descarga",
            message=f"NAS disponible - Modo PRODUCCIÓN: {NAS_PATH}",
            level="INFO",
            file=LOG_FILE,
        )
    else:
        #  DESARROLLO: Descargar local (solo para tests)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "API-NASA"))
        mode = "DESARROLLO (Local - solo tests)"
        log_custom(
            section="Configuración Descarga",
            message=f"NAS no disponible - Modo DESARROLLO local: {base_path} (SOLO PARA PRUEBAS)",
            level="WARNING",
            file=LOG_FILE,
        )

    return base_path, nas_available, mode


def determinar_folder_destination_inteligente(metadata: Dict, base_path: str) -> str:
    """
    DETERMINAR CARPETA FINAL: NAS o Local según disponibilidad
    """
    year = _get_year_from_metadata(metadata)
    mission = _get_mission_from_metadata(metadata)
    camera = metadata.get("CAMARA") or "Sin_Camera"

    #  ESTRUCTURA: {base_path}/{year}/{mission}/{camera}/
    folder_destination = os.path.join(base_path, str(year), mission, camera)

    # Crear directory si no existe
    os.makedirs(folder_destination, exist_ok=True)

    return folder_destination


def download_imagees_aria2c_optimized(metadata, conexiones=32):
    """
     DESCARGA DIRECTA CON ARIA2C OPTIMIZADO AL DESTINO FINAL
    Sin transferencias posteriores - Descarga directa donde debe estar
    """
    if not metadata:
        log_custom(
            section="Descarga Directa",
            message="No hay metadata válidos para download",
            level="WARNING",
            file=LOG_FILE,
        )
        return

    #  VERIFICAR DESTINO (NAS o Local)
    base_path, is_nas, mode = verificar_destination_descarga()

    log_custom(
        section="Descarga Directa",
        message=f"Iniciando descarga DIRECTA - {mode} - {len(metadata)} imágenes",
        level="INFO",
        file=LOG_FILE,
    )

    #  AGRUPAR POR CARPETA DE DESTINO FINAL
    grupos_por_folder = {}
    total_urls_nuevas = 0

    for metadata in metadata:
        url = metadata.get("URL")
        if not url:
            continue

        # Determinar folder final directamente
        folder_destination = determinar_folder_destination_inteligente(
            metadata, base_path
        )

        if folder_destination not in grupos_por_folder:
            grupos_por_folder[folder_destination] = []

        # Normalizar filename: eliminar query string y manejar GeoTIFFs
        url_path = url.split("?", 1)[0]
        raw_basename = os.path.basename(url_path)
        name, ext = os.path.splitext(raw_basename)

        # Si la URL apunta a GetGeotiff.pl o no tiene extensión clara, usar NASA_ID.tif cuando sea posible
        nasa_id = metadata.get("NASA_ID") or metadata.get("NASA_ID".upper()) or None
        is_geotiff_url = "geotiff" in url.lower() or "getgeotiff.pl" in url.lower()

        if is_geotiff_url and nasa_id:
            filename = f"{nasa_id}.tif"
        else:
            # Si no hay extensión, intentar añadir .jpg por defecto
            if ext == "":
                filename = raw_basename + ".jpg"
            else:
                filename = raw_basename

        filepath = os.path.join(folder_destination, filename)

        # Solo download si no existe
        if not os.path.exists(filepath):
            grupos_por_folder[folder_destination].append(url)
            total_urls_nuevas += 1

    log_custom(
        section="Descarga Directa",
        message=f"Archivos nuevos: {total_urls_nuevas} en {len(grupos_por_folder)} folders - Destino: {mode}",
        level="INFO",
        file=LOG_FILE,
    )

    if total_urls_nuevas == 0:
        log_custom(
            section="Descarga Directa",
            message="Todos los files ya existen en el destination",
            level="INFO",
            file=LOG_FILE,
        )
        return

    #  DESCARGA OPTIMIZADA CON ARIA2C
    total_downloaded = 0
    urls_procesadas = 0
    start_time = time.time()

    for folder_destination, urls in grupos_por_folder.items():
        if not urls:
            continue

        log_custom(
            section="Descarga Directa",
            message=f"Descargando {len(urls)} imágenes a: {folder_destination}",
            level="INFO",
            file=LOG_FILE,
        )

        # Crear file temporal de URLs
        temp_file = os.path.join(
            folder_destination, f"urls_batch_{int(time.time())}.txt"
        )

        with open(temp_file, "w") as f:
            for url in urls:
                f.write(url + "\n")

        #  ARIA2C OPTIMIZADO PARA NAS/LOCAL
        command = [
            "aria2c",
            "-i",
            temp_file,
            "-d",
            folder_destination,  #  DESCARGA DIRECTA AL DESTINO FINAL
            "-j",
            str(conexiones),  # Más conexiones para NAS
            "--max-connection-per-server=16",
            "--min-split-size=1M",  # Chunks más pequeños para mejor paralelización
            "--split=32",  # Más splits por file
            "--summary-interval=1",  # Progreso cada segundo
            "--continue=true",
            "--timeout=45",
            "--retry-wait=2",
            "--max-tries=5",
            "--console-log-level=info",
            "--optimize-concurrent-downloads=true",  #  Optimización aria2c
            "--stream-piece-selector=geom",  # Mejor para downloads grandes
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        ]

        #  CONFIGURACIÓN ESPECÍFICA PARA NAS
        if is_nas:
            command.extend(
                [
                    "--file-allocation=failurec",  # Mejor para NAS
                    "--disk-cache=64M",  # Cache para NAS
                ]
            )
        else:
            command.extend(
                [
                    "--file-allocation=none",  # Más rápido para local
                    "--disk-cache=32M",
                ]
            )

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
            )

            folder_downloaded = 0
            last_logged_progress = 0

            for line in iter(process.stdout.readline, ""):
                line = line.strip()
                if not line:
                    continue

                #  DETECTAR DESCARGAS COMPLETADAS
                if "Download complete:" in line or ("[#" in line and "100%" in line):
                    folder_downloaded += 1
                    total_downloaded += 1
                    urls_procesadas += 1

                    #  CALCULAR Y ENVIAR PROGRESO REAL
                    if total_urls_nuevas > 0:
                        progress = int((urls_procesadas / total_urls_nuevas) * 100)
                        print(f"PROGRESS: {progress}", flush=True)

                        # Log progreso cada 20% o al complete folder
                        if (progress - last_logged_progress >= 20) or (
                            folder_downloaded == len(urls)
                        ):
                            log_custom(
                                section="Descarga Directa",
                                message=f"Progreso: {progress}% ({total_downloaded}/{total_urls_nuevas}) - Carpeta: {folder_downloaded}/{len(urls)}",
                                level="INFO",
                                file=LOG_FILE,
                            )
                            last_logged_progress = progress

                #  DETECTAR ERRORES CRÍTICOS
                elif "ERROR" in line and not any(
                    ignorable in line for ignorable in ["SSL", "certificate", "retry"]
                ):
                    log_custom(
                        section="Descarga Directa",
                        message=f"Error aria2c: {line}",
                        level="ERROR",
                        file=LOG_FILE,
                    )

                #  VELOCIDAD (log ocasional)
                elif "DL:" in line and "MB/s" in line and folder_downloaded % 50 == 0:
                    log_custom(
                        section="Descarga Directa",
                        message=f"Velocidad: {line}",
                        level="INFO",
                        file=LOG_FILE,
                    )

            # Esperar proceso
            process.wait()

            # Limpiar file temporal
            if os.path.exists(temp_file):
                os.remove(temp_file)

            if process.returncode == 0:
                log_custom(
                    section="Descarga Directa",
                    message=f"Carpeta completed exitosamente: {len(urls)} imágenes en {folder_destination}",
                    level="INFO",
                    file=LOG_FILE,
                )
            else:
                log_custom(
                    section="Descarga Directa",
                    message=f"Error in folder {folder_destination} - código: {process.returncode}",
                    level="ERROR",
                    file=LOG_FILE,
                )

        except Exception as e:
            log_custom(
                section="Descarga Directa",
                message=f"Error ejecutando aria2c: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )

            # Limpiar temporal en caso de error
            if os.path.exists(temp_file):
                os.remove(temp_file)

    #  RESUMEN FINAL
    download_time = time.time() - start_time
    rate = total_downloaded / download_time if download_time > 0 else 0

    log_custom(
        section="Descarga Directa",
        message=f"DESCARGA COMPLETADA - {mode}: {total_downloaded}/{total_urls_nuevas} imágenes en {download_time:.1f}s ({rate:.1f} img/s)",
        level="INFO",
        file=LOG_FILE,
    )

    # Asegurar 100% al final
    print("PROGRESS: 100", flush=True)


def _get_year_from_metadata(metadata: Dict) -> int:
    """Extraer año de metadata"""
    date_str = metadata.get("FECHA", "")
    try:
        return datetime.strptime(date_str, "%Y.%m.%d").year
    except Exception:
        return 2024


def _get_mission_from_metadata(metadata: Dict) -> str:
    """Extraer misión de metadata"""
    nasa_id = metadata.get("NASA_ID", "")
    try:
        return nasa_id.split("-")[0]
    except Exception:
        return "UNKNOWN"


class HybridOptimizedProcessor:
    """Procesador híbrido con descarga directa al destination final"""

    def __init__(self, database_path: str, batch_size: int = 75):
        self.database_path = database_path
        self.batch_size = batch_size
        self.setup_sqlite_optimizations()

    def setup_sqlite_optimizations(self):
        """Configurar SQLite para máximo rendimiento"""
        import sqlite3

        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        optimizations = [
            "PRAGMA journal_mode = WAL;",
            "PRAGMA synchronous = NORMAL;",
            "PRAGMA cache_size = 20000;",
            "PRAGMA temp_store = memory;",
            "PRAGMA mmap_size = 536870912;",
            "PRAGMA optimize;",
        ]

        for opt in optimizations:
            cursor.execute(opt)
        conn.commit()
        conn.close()

        log_custom(
            section="Base de Datos",
            message="SQLite configurado para máximo rendimiento",
            level="INFO",
            file=LOG_FILE,
        )

    def process_complete_workflow(self, metadata_list: List[Dict]):
        """FLUJO COMPLETO CON DESCARGA DIRECTA"""
        total_start = time.time()

        # Verificar configuration al inicio
        base_path, is_nas, mode = verificar_destination_descarga()

        log_custom(
            section="Workflow ISS",
            message=f"Iniciando workflow híbrido - {mode} - {len(metadata_list)} elementos",
            level="INFO",
            file=LOG_FILE,
        )

        #  FASE 1: DESCARGA DIRECTA AL DESTINO FINAL
        log_custom(
            section="Workflow ISS",
            message="FASE 1: Descarga directa con aria2c optimized",
            level="INFO",
            file=LOG_FILE,
        )

        download_start = time.time()
        download_imagees_aria2c_optimized(metadata_list, conexiones=32)
        download_time = time.time() - download_start

        log_custom(
            section="Workflow ISS",
            message=f"FASE 1 completed en {download_time:.2f}s - Descarga directa a {mode}",
            level="INFO",
            file=LOG_FILE,
        )

        #  FASE 2: PREPARACIÓN DATOS
        log_custom(
            section="Workflow ISS",
            message="FASE 2: Preparando datos para base de datos",
            level="INFO",
            file=LOG_FILE,
        )

        prep_start = time.time()
        prepared_data = self._prepare_data_from_organized_files(
            metadata_list, base_path
        )
        prep_time = time.time() - prep_start

        log_custom(
            section="Workflow ISS",
            message=f"FASE 2 completed en {prep_time:.2f}s - {len(prepared_data)} registros prepareds",
            level="INFO",
            file=LOG_FILE,
        )

        #  FASE 3: ESCRITURA SQLITE
        log_custom(
            section="Workflow ISS",
            message="FASE 3: Escribiendo en base de datos SQLite",
            level="INFO",
            file=LOG_FILE,
        )

        db_start = time.time()
        self._write_to_database_optimized(prepared_data)
        db_time = time.time() - db_start

        log_custom(
            section="Workflow ISS",
            message=f"FASE 3 completed en {db_time:.2f}s",
            level="INFO",
            file=LOG_FILE,
        )

        #  RESUMEN FINAL (sin fase de transferencia - ya está en destination)
        total_time = time.time() - total_start

        log_custom(
            section="Workflow ISS",
            message=f"WORKFLOW COMPLETADO - {mode} - Total: {total_time:.1f}s | Descarga: {download_time:.1f}s | Preparación: {prep_time:.1f}s | DB: {db_time:.1f}s",
            level="INFO",
            file=LOG_FILE,
        )

    def _prepare_data_from_organized_files(
        self, metadata_list: List[Dict], base_path: str
    ) -> List[Dict]:
        """PREPARAR DATOS CON RUTA CORRECTA SEGÚN DESTINO"""

        def process_single_metadata(metadata):
            nasa_id = metadata.get("NASA_ID")
            if not nasa_id:
                return None

            parsed_data = {
                "nasa_id": nasa_id,
                "date": self._parse_date(metadata.get("FECHA")),
                "time": self._parse_time(metadata.get("HORA")),
                "resolution": metadata.get("RESOLUCION"),
                "features": metadata.get("LUGAR"),
                "sun_elevation": self._to_float(metadata.get("ELEVACION_SOL")),
                "sun_azimuth": self._to_float(metadata.get("AZIMUT_SOL")),
                "cloud_cover": self._to_float(metadata.get("COBERTURA_NUBOSA")),
                "nadir_lat": self._to_float(metadata.get("NADIR_LAT")),
                "nadir_lon": self._to_float(metadata.get("NADIR_LON")),
                "center_lat": self._to_float(metadata.get("CENTER_LAT")),
                "center_lon": self._to_float(metadata.get("CENTER_LON")),
                "nadir_center": metadata.get("NADIR_CENTER"),
                "altitude": self._to_float(metadata.get("ALTITUD")),
                "camera": metadata.get("CAMARA"),
                "focal_length": self._to_float(metadata.get("LONGITUD_FOCAL")),
                "tilt": metadata.get("INCLINACION"),
                "format": metadata.get("FORMATO"),
                "camera_metadata": metadata.get("CAMARA_METADATA"),
                "url": metadata.get("URL"),
            }

            #  BUSCAR ARCHIVO EN DESTINO CORRECTO (NAS o Local)
            final_path = self._find_organized_file_path(metadata, base_path)
            parsed_data["path"] = final_path
            return parsed_data

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(process_single_metadata, metadata_list))

        prepared_data = [r for r in results if r is not None]

        log_custom(
            section="Preparación Datos",
            message=f"Preparados {len(prepared_data)}/{len(metadata_list)} elementos",
            level="INFO",
            file=LOG_FILE,
        )

        return prepared_data

    def _find_organized_file_path(self, metadata: Dict, base_path: str) -> str:
        """Buscar file en la estructura organizada (NAS o Local)"""
        url = metadata.get("URL")
        if not url:
            return None

        filename = os.path.basename(url)
        year = _get_year_from_metadata(metadata)
        mission = _get_mission_from_metadata(metadata)
        camera = metadata.get("CAMARA") or "Sin_Camara"

        #  RUTA SEGÚN DESTINO (NAS o Local)
        final_path = os.path.join(base_path, str(year), mission, camera, filename)

        return final_path if os.path.exists(final_path) else None

    def _write_to_database_optimized(self, prepared_data: List[Dict]):
        """ESCRITURA SQLITE CON LOGS COHERENTES"""
        sys.path.append(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        )
        from db.Crud import MetadataCRUD
        from db.Tables import Image

        log_custom(
            section="Base de Datos",
            message=f"Escribiendo {len(prepared_data)} registros en lotes de {self.batch_size}",
            level="INFO",
            file=LOG_FILE,
        )

        crud = MetadataCRUD()
        total_batches = (len(prepared_data) + self.batch_size - 1) // self.batch_size
        written = 0
        skipped = 0

        try:
            for i in range(0, len(prepared_data), self.batch_size):
                batch = prepared_data[i : i + self.batch_size]
                batch_num = (i // self.batch_size) + 1

                try:
                    # Verificar existentes
                    nasa_ids_in_batch = [item["nasa_id"] for item in batch]
                    existing_ids = set()

                    for nasa_id in nasa_ids_in_batch:
                        if crud.session.query(
                            crud.session.query(Image)
                            .filter_by(nasa_id=nasa_id)
                            .exists()
                        ).scalar():
                            existing_ids.add(nasa_id)

                    new_items = [
                        item for item in batch if item["nasa_id"] not in existing_ids
                    ]

                    if not new_items:
                        skipped += len(batch)
                        continue

                    # Crear registros nuevos
                    for item in new_items:
                        existing_image = (
                            crud.session.query(Image)
                            .filter_by(nasa_id=item["nasa_id"])
                            .first()
                        )
                        if existing_image:
                            skipped += 1
                            continue

                        image_record = crud.create_image(
                            nasa_id=item["nasa_id"],
                            date=item["date"],
                            time=item["time"],
                            resolution=item["resolution"],
                            path=item["path"],
                        )

                        if image_record:
                            crud.create_image_details(
                                image_id=image_record.image_id,
                                features=item["features"],
                                sun_elevation=item["sun_elevation"],
                                sun_azimuth=item["sun_azimuth"],
                                cloud_cover=item["cloud_cover"],
                            )

                            crud.create_map_location(
                                image_id=image_record.image_id,
                                nadir_lat=item["nadir_lat"],
                                nadir_lon=item["nadir_lon"],
                                center_lat=item["center_lat"],
                                center_lon=item["center_lon"],
                                nadir_center=item["nadir_center"],
                                altitude=item["altitude"],
                            )

                            crud.create_camera_information(
                                image_id=image_record.image_id,
                                camera=item["camera"],
                                focal_length=item["focal_length"],
                                tilt=item["tilt"],
                                format=item["format"],
                                camera_metadata=item["camera_metadata"],
                            )

                            written += 1
                        else:
                            skipped += 1

                    crud.session.commit()

                    #  PROGRESO PARA ELECTRON
                    progress = int((written + skipped) / len(prepared_data) * 100)
                    print(f"PROGRESS: {progress}", flush=True)

                    # Log cada 10 lotes
                    if batch_num % 10 == 0 or batch_num == total_batches:
                        log_custom(
                            section="Base de Datos",
                            message=f"Lote {batch_num}/{total_batches}: {written} escritos, {skipped} duplicados",
                            level="INFO",
                            file=LOG_FILE,
                        )

                except Exception as e:
                    log_custom(
                        section="Base de Datos",
                        message=f"Error in lote {batch_num}: {str(e)}",
                        level="ERROR",
                        file=LOG_FILE,
                    )
                    crud.session.rollback()
                    skipped += len(batch)
                    continue

        except Exception as e:
            log_custom(
                section="Base de Datos",
                message=f"Error general en escritura: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
        finally:
            try:
                crud.session.close()
            except:
                pass

        log_custom(
            section="Base de Datos",
            message=f"Escritura completed: {written} nuevos, {skipped} duplicados",
            level="INFO",
            file=LOG_FILE,
        )

    def _to_float(self, value):
        try:
            return float(re.search(r"[-+]?[0-9]*\.?[0-9]+", str(value)).group())
        except Exception:
            return None

    def _parse_date(self, value):
        try:
            return datetime.strptime(value, "%Y.%m.%d").date()
        except Exception:
            return None

    def _parse_time(self, value):
        try:
            from datetime import datetime

            return datetime.strptime(value.replace(" GMT", ""), "%H:%M:%S").time()
        except Exception:
            return None


# ==========================================
# FUNCIÓN PRINCIPAL OPTIMIZADA
# ==========================================


def main_hibrido_directo_nas(json_filename):
    """FUNCIÓN PRINCIPAL CON DESCARGA DIRECTA AL DESTINO FINAL"""
    import json

    if not os.path.exists(json_filename):
        log_custom(
            section="Error Archivo",
            message=f"No se encontró el file JSON: {json_filename}",
            level="ERROR",
            file=LOG_FILE,
        )
        return

    log_custom(
        section="Inicio Procesamiento",
        message=f"Iniciando processing desde: {json_filename}",
        level="INFO",
        file=LOG_FILE,
    )

    # Verificar destination al inicio
    base_path, is_nas, mode = verificar_destination_descarga()

    # Cargar metadata
    try:
        with open(json_filename, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except json.JSONDecodeError as e:
        log_custom(
            section="Error JSON",
            message=f"Error al parsear JSON: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        return
    except Exception as e:
        log_custom(
            section="Error Lectura",
            message=f"Error al leer file: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        return

    log_custom(
        section="Validación",
        message=f"Cargados {len(metadata)} registros para processing",
        level="INFO",
        file=LOG_FILE,
    )

    if not metadata:
        log_custom(
            section="Error Datos",
            message="El file JSON está vacío",
            level="ERROR",
            file=LOG_FILE,
        )
        return

    # Verificar estructura
    sample_metadata = metadata[0] if metadata else {}
    expected_fields = ["NASA_ID", "URL", "FECHA", "HORA"]
    missing_fields = [
        field for field in expected_fields if field not in sample_metadata
    ]

    if missing_fields:
        log_custom(
            section="Error Estructura",
            message=f"Faltan campos requeridos: {missing_fields}",
            level="ERROR",
            file=LOG_FILE,
        )
        return

    #  EJECUTAR PROCESADOR
    try:
        processor = HybridOptimizedProcessor(
            database_path=database_path,
            batch_size=75,
        )

        processor.process_complete_workflow(metadata)

        log_custom(
            section="Procesamiento Completado",
            message=f"Procesamiento completed exitosamente - {mode}",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        log_custom(
            section="Processing Error",
            message=f"Error during el processing: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        import traceback

        log_custom(
            section="Error Traceback",
            message=f"Traceback: {traceback.format_exc()}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        main_hibrido_directo_nas(sys.argv[1])
    else:
        log_custom(
            section="Información de Uso",
            message="Usage: python imageProcessor.py periodic_metadata.json",
            level="INFO",
            file=LOG_FILE,
        )

# ==========================================
# VARIABLES GLOBALES NECESARIAS
# ==========================================

if "database_path" not in globals():
    database_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "db", "metadata.db"
    )
