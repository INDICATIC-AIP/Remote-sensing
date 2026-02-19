import os
import sys
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading

#  IMPORTAR BEAUTIFULSOUP PARA PARSING HTML
from bs4 import BeautifulSoup
import re

#  PROJECT ROOT
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

#  IMPORTAR DEPENDENCIAS PARA LOGGING
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom

#  LOG FILE
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "iss", "general.log")

#  CACHE GLOBAL PARA EVITAR SCRAPING DUPLICADO
metadata_cache = {}
nadir_alt_cache = {}
cache_lock = threading.Lock()


def obtener_nadir_altitude_camera_optimized(nasa_id):
    """SCRAPING DE NADIR, ALTITUD Y CÁMARA - IGUAL QUE EN downloadAtime()"""
    MAX_RETRIES = 2
    TIMEOUT = 8  # 8 segundos

    #  VERIFICAR CACHE PRIMERO
    with cache_lock:
        if nasa_id in nadir_alt_cache:
            return nadir_alt_cache[nasa_id]

    for intento in range(MAX_RETRIES + 1):
        try:
            # Parsear NASA_ID
            parts = nasa_id.split("-")
            if len(parts) != 3:
                log_custom(
                    section="Scraping NASA",
                    message=f"NASA_ID mal formateado: {nasa_id}",
                    level="WARNING",
                    file=LOG_FILE,
                )
                return {
                    "NADIR_CENTER": None,
                    "ALTITUD": None,
                    "CAMARA": None,
                    "FECHA_CAPTURA": None,
                    "GEOTIFF_URL": None,
                    "HAS_GEOTIFF": False,
                }

            mission, roll, frame = parts
            url = f"https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}"

            #  HACER REQUEST CON TIMEOUT
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()

            #  PARSEAR HTML CON BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            #  EXTRAER FECHA DE CAPTURA
            date_captura = None

            # SELECTOR CORREGIDO PARA FECHA
            try:
                date_elements = soup.find_all(
                    "td", string=re.compile(r"Date taken", re.I)
                )
                if date_elements:
                    date_cell = date_elements[0].find_next_sibling("td")
                    if date_cell:
                        date_text = date_cell.get_text(strip=True)
                        # Convertir 2025.03.18 a date object
                        date_captura = datetime.strptime(date_text, "%Y.%m.%d").date()
            except Exception as e:
                log_custom(f" Error extrayendo date para {nasa_id}: {e}", "ERROR")

            # SELECTOR CORREGIDO PARA CÁMARA (comentado por atime, usar DB)

            #  EXTRAER CÁMARA
            camera_text = None
            try:
                camera_elements = soup.find_all(
                    "td", string=re.compile(r"Camera", re.I)
                )
                if camera_elements:
                    for elem in camera_elements:
                        camera_cell = elem.find_next_sibling("td")
                        if camera_cell:
                            camera_text = camera_cell.get_text(strip=True)
                            camera_text = camera_text.replace("/", "_").replace(
                                " ", "_"
                            )
                            break
            except Exception as e:
                log_custom(
                    section="Scraping NASA",
                    message=f" Error extrayendo cámara para {nasa_id}: {e}",
                    level="ERROR",
                    file=LOG_FILE,
                )

            #  BUSCAR INFORMACIÓN DE NADIR
            nadir_text = None
            camera_ems = soup.find_all("em")
            for em in camera_ems:
                if "Nadir to Photo Center:" in em.get_text():
                    next_sibling = em.next_sibling
                    if next_sibling:
                        nadir_text = (
                            next_sibling.strip().replace('"', "").replace("'", "")
                        )
                        break

            #  BUSCAR ALTITUD
            alt_value = None
            altitudee_text = response.text
            alt_match = re.search(
                r"Spacecraft Altitude[^(]*\(([\d.,]+)km\)", altitudee_text
            )
            if alt_match:
                alt_value = float(alt_match.group(1).replace(",", ""))

            #  VERIFICAR GEOTIFF
            has_geotiff = "No GeoTIFF is available for this photo" not in response.text
            geotiff_url = (
                f"https://eol.jsc.nasa.gov/SearchPhotos/GetGeotiff.pl?photo={nasa_id}"
                if has_geotiff
                else None
            )

            #  RESULTADO
            result = {
                "NADIR_CENTER": nadir_text,
                "ALTITUD": alt_value,
                "CAMARA": camera_text,
                "FECHA_CAPTURA": date_captura,
                "GEOTIFF_URL": geotiff_url,
                "HAS_GEOTIFF": has_geotiff,
            }

            #  GUARDAR EN CACHE
            with cache_lock:
                nadir_alt_cache[nasa_id] = result

            log_custom(
                section="Scraping NASA",
                message=f"Datos obtenidos para {nasa_id}: Cámara={camera_text}, Fecha={date_captura}, GeoTIFF={has_geotiff}",
                level="INFO",
                file=LOG_FILE,
            )

            return result

        except Exception as e:
            log_custom(
                section="Scraping NASA",
                message=f"Intento {intento + 1} failed para {nasa_id}: {str(e)}",
                level="WARNING" if intento < MAX_RETRIES else "ERROR",
                file=LOG_FILE,
            )

            if intento < MAX_RETRIES:
                time.sleep(1 * (intento + 1))  # Backoff exponencial
            else:
                # Retornar valores vacíos después de todos los intentos
                return {
                    "NADIR_CENTER": None,
                    "ALTITUD": None,
                    "CAMARA": None,
                    "FECHA_CAPTURA": None,
                    "GEOTIFF_URL": None,
                    "HAS_GEOTIFF": False,
                }


def obtener_camera_metadata_optimized(nasa_id):
    """DESCARGAR CAMERA METADATA - IGUAL QUE EN downloadAtime()"""
    MAX_RETRIES = 2
    TIMEOUT = 10  # 10 segundos

    #  VERIFICAR CACHE PRIMERO
    with cache_lock:
        if nasa_id in metadata_cache:
            return metadata_cache[nasa_id]

    for intento in range(MAX_RETRIES + 1):
        try:
            parts = nasa_id.split("-")
            if len(parts) != 3:
                return None

            mission, roll, frame = parts
            url = f"https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            #  BUSCAR BOTÓN DE CAMERA METADATA
            button = soup.find(
                "input", {"type": "button", "value": "View camera metadata"}
            )

            if button and button.get("onclick"):
                onclick_value = button.get("onclick")
                # Extraer URL del onclick
                start = onclick_value.find("('") + 2
                end = onclick_value.find("')", start)
                file_url = onclick_value[start:end]

                if file_url and file_url.startswith("/"):
                    # Determinar folder de salida
                    output_folder = get_output_folder()
                    full_url = f"https://eol.jsc.nasa.gov{file_url}"
                    final_path = os.path.join(output_folder, os.path.basename(file_url))

                    # Verificar si ya existe
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                        log_custom(
                            section="Camera Metadata",
                            message=f"Camera metadata ya existe: {final_path}",
                            level="INFO",
                            file=LOG_FILE,
                        )
                        with cache_lock:
                            metadata_cache[nasa_id] = final_path
                        return final_path

                    # Descargar file
                    metadata_response = requests.get(
                        full_url, headers=headers, timeout=TIMEOUT
                    )
                    metadata_response.raise_for_status()

                    if metadata_response.status_code == 200 and metadata_response.text:
                        os.makedirs(output_folder, exist_ok=True)
                        with open(final_path, "w", encoding="utf-8") as f:
                            f.write(metadata_response.text)

                        log_custom(
                            section="Camera Metadata",
                            message=f"Camera metadata descargado: {final_path}",
                            level="INFO",
                            file=LOG_FILE,
                        )

                        with cache_lock:
                            metadata_cache[nasa_id] = final_path
                        return final_path

            return None

        except Exception as e:
            log_custom(
                section="Camera Metadata",
                message=f"Error in camera metadata (intento {intento + 1}) para {nasa_id}: {str(e)}",
                level="WARNING" if intento < MAX_RETRIES else "ERROR",
                file=LOG_FILE,
            )

            if intento < MAX_RETRIES:
                time.sleep(1 * (intento + 1))

    return None


def get_output_folder():
    """DETERMINAR CARPETA DE SALIDA PARA CAMERA METADATA"""
    try:
        sys.path.append(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        )
        from map.routes import NAS_PATH, NAS_MOUNT
    except ImportError:
        # Valores por defecto si no se puede importar paths
        NAS_PATH = "/mnt/nas"
        NAS_MOUNT = "/mnt/nas"
        log_custom(
            section="Camera Metadata",
            message="No se pudo importar paths, usando valores por defecto",
            level="WARNING",
            file=LOG_FILE,
        )

    # Verificar NAS igual que en imageProcessor
    nas_available = os.path.ismount(NAS_MOUNT) and os.path.exists(NAS_PATH)

    if nas_available:
        camera_data_path = os.path.join(NAS_PATH, "camera_data")
        mode = "PRODUCCIÓN (NAS)"
    else:
        camera_data_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "API-NASA", "camera_data")
        )
        mode = "DESARROLLO (Local)"

    try:
        os.makedirs(camera_data_path, exist_ok=True)
    except Exception as e:
        log_custom(
            section="Camera Metadata",
            message=f"Error creando folder {camera_data_path}: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )

    return camera_data_path


def extract_metadata_enriquecido(results):
    """EXTRACCIÓN DE METADATOS CON SCRAPING COMPLETO - IGUAL QUE downloadAtime()"""

    def find_by_suffix(obj, suffix, fallback=None):
        for key in obj:
            if key.endswith(suffix) and obj[key] not in [None, ""]:
                return obj[key]
        return fallback

    log_custom(
        section="Extracción Metadatos Enriquecida",
        message=f"Extrayendo metadata enriquecidos de {len(results)} results con scraping",
        level="INFO",
        file=LOG_FILE,
    )

    #  IMPORTAR MAPEOS DE CÁMARA Y FILM DESDE data.py
    try:
        from data import cameraMap, filmMap

        log_custom(
            section="Extracción Metadatos",
            message="Mapeos de cámara y film cargados exitosamente desde data.py",
            level="INFO",
            file=LOG_FILE,
        )
    except ImportError as e:
        log_custom(
            section="Extracción Metadatos",
            message=f"Error loading data.py: {str(e)}. Verifica que el file existe en utils/",
            level="ERROR",
            file=LOG_FILE,
        )
        # Sin mapeos por defecto - el proceso failurerá si no se puede cargar data.py
        raise ImportError("No se pudo cargar data.py - proceso detenido")

    def process_image_con_scraping(photo):
        """Process una image individual con scraping completo"""
        try:
            filename = find_by_suffix(photo, ".filename")
            directory = find_by_suffix(photo, ".directory")

            if not filename:
                return None

            #  DATOS BÁSICOS DE LA API
            raw_date = find_by_suffix(photo, ".pdate", "")
            raw_time = find_by_suffix(photo, ".ptime", "")
            formatted_date = (
                raw_date[:4] + "." + raw_date[4:6] + "." + raw_date[6:8]
                if len(raw_date) == 8
                else ""
            )
            formatted_hour = (
                raw_time[:2] + ":" + raw_time[2:4] + ":" + raw_time[4:6]
                if len(raw_time) == 6
                else ""
            )

            width = find_by_suffix(photo, ".width", "")
            height = find_by_suffix(photo, ".height", "")
            resolution_text = f"{width} x {height} pixels" if width and height else ""

            camera_code = find_by_suffix(photo, ".camera", "Desconocida")
            camera_desc = cameraMap.get(camera_code, "Desconocida")

            film_code = find_by_suffix(photo, ".film", "UNKN")
            film_data = filmMap.get(
                film_code, {"type": "Desconocido", "description": "Desconocido"}
            )

            nasa_id = filename.split(".")[0] if filename else "Sin_ID"

            if not nasa_id or nasa_id == "Sin_ID":
                return None

            #  HACER SCRAPING COMPLETO - IGUAL QUE EN downloadAtime()
            extra_data = obtener_nadir_altitude_camera_optimized(nasa_id)
            camera_metadata_path = obtener_camera_metadata_optimized(nasa_id)

            #  DETERMINAR CÁMARA FINAL
            if (
                camera_desc == "Desconocida"
                or "Desconocido" in camera_desc
                or "Unspecified" in camera_desc
            ):
                camera_final = extra_data.get("CAMARA") or "Desconocida"
            else:
                camera_final = camera_desc

            #  DETERMINAR URL FINAL (GeoTIFF vs JPG)
            if extra_data.get("HAS_GEOTIFF") and extra_data.get("GEOTIFF_URL"):
                url_final = extra_data["GEOTIFF_URL"]
            else:
                url_final = (
                    f"https://eol.jsc.nasa.gov/DatabaseImages/{directory}/{filename}"
                    if filename and directory
                    else None
                )

            #  USAR FECHA DE CAPTURA SI ESTÁ DISPONIBLE
            date_final = extra_data.get("FECHA_CAPTURA") or formatted_date

            #  CONSTRUIR METADATOS COMPLETOS
            metadata_completo = {
                "NASA_ID": nasa_id,
                "FECHA": date_final,  #  FECHA REAL DE CAPTURA
                "HORA": formatted_hour,
                "RESOLUCION": resolution_text,
                "URL": url_final,  #  URL INTELIGENTE (GeoTIFF o JPG)
                "NADIR_LAT": find_by_suffix(photo, ".nlat"),
                "NADIR_LON": find_by_suffix(photo, ".nlon"),
                "CENTER_LAT": find_by_suffix(photo, ".lat"),
                "CENTER_LON": find_by_suffix(photo, ".lon"),
                "NADIR_CENTER": extra_data.get("NADIR_CENTER"),  #  DESDE SCRAPING
                "ALTITUD": extra_data.get("ALTITUD"),  #  DESDE SCRAPING
                "LUGAR": find_by_suffix(photo, ".geon", ""),
                "ELEVACION_SOL": find_by_suffix(photo, ".elev", ""),
                "AZIMUT_SOL": find_by_suffix(photo, ".azi", ""),
                "COBERTURA_NUBOSA": find_by_suffix(photo, ".cldp", ""),
                "CAMARA": camera_final,  #  CÁMARA REAL DESDE SCRAPING
                "LONGITUD_FOCAL": find_by_suffix(photo, ".fclt"),
                "INCLINACION": find_by_suffix(photo, ".tilt"),
                "FORMATO": f"{film_data['type']}: {film_data['description']}",
                "CAMARA_METADATA": camera_metadata_path,  #  ARCHIVO DESCARGADO
            }

            return metadata_completo

        except Exception as e:
            log_custom(
                section="Extracción Metadatos",
                message=f"Error processing image con scraping: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            return None

    #  PROCESAMIENTO PARALELO CON SCRAPING
    metadata_enriquecidos = []

    # Usar ThreadPoolExecutor para paralelizar el scraping
    MAX_WORKERS = 10  # Limitar para no saturar el servidor de NASA

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Enviar todas las tasks
        future_to_photo = {
            executor.submit(process_image_con_scraping, photo): photo
            for photo in results
        }

        # Recoger results conforme van completándose
        procesadas = 0
        for future in as_completed(future_to_photo):
            try:
                result = future.result()
                if result:
                    metadata_enriquecidos.append(result)

                procesadas += 1

                # Log progreso cada 10 imágenes
                if procesadas % 10 == 0 or procesadas == len(results):
                    log_custom(
                        section="Extracción Metadatos Enriquecida",
                        message=f"Progreso scraping: {procesadas}/{len(results)} completeds",
                        level="INFO",
                        file=LOG_FILE,
                    )

            except Exception as e:
                log_custom(
                    section="Extracción Metadatos Enriquecida",
                    message=f"Error in future: {str(e)}",
                    level="ERROR",
                    file=LOG_FILE,
                )

    log_custom(
        section="Extracción Metadatos Enriquecida",
        message=f"Metadatos enriquecidos extraídos: {len(metadata_enriquecidos)} registros con scraping completo",
        level="INFO",
        file=LOG_FILE,
    )

    return metadata_enriquecidos
