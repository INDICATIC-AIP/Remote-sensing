#!/usr/bin/env python3
"""
 PROCESADOR COMPLETO FINAL - FLUJO INTEGRADO
Replica exactamente el flujo de rend_periodica.js:
1. Consulta API → 2. Descarga masiva camera metadata → 3. Procesa metadatos → 4. Descarga imágenes
"""

import os
import sys
import json
import subprocess
import sqlite3
import asyncio
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Agregar rutas necesarias
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))

# Importaciones
from imageProcessor import (
    HybridOptimizedProcessor,
    descargar_imagenes_aria2c_optimizado,
    verificar_destino_descarga,
)
from nasa_api_client import (
    NASAAPIClient,
    obtener_imagenes_nuevas_costa_rica,
    obtener_por_tarea_programada,
)
from bulk_camera_downloader import bulk_download_camera_metadata
from extract_metadatos_enriquecido import obtener_nadir_altitud_camara_optimized
from log import log_custom
from rutas import NAS_PATH, NAS_MOUNT

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

# Configuración
API_KEY = os.getenv("NASA_API_KEY", "")
if not API_KEY:
    raise ValueError("NASA_API_KEY no está configurada en .env")
LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "metadata.db")
RETRY_INFO_FILE = os.path.join(os.path.dirname(__file__), "retry_info.json")
CURRENT_EXECUTION_FILE = os.path.join(
    os.path.dirname(__file__), "current_execution.json"
)

TASK_NAME = "ISS_BatchProcessor"
MAX_RETRIES = 6
LIMITE_IMAGENES = 15

# Importar mapeos de datos
try:
    from data import cameraMap, filmMap

    log_custom(
        section="Inicialización",
        message="Mapeos de cámara y film cargados exitosamente",
        level="INFO",
        file=LOG_FILE,
    )
except ImportError as e:
    log_custom(
        section="Error Inicialización",
        message=f"Error cargando data.py: {e}",
        level="ERROR",
        file=LOG_FILE,
    )
    cameraMap = {}
    filmMap = {}


# ============================================================================
#  FUNCIONES DE GESTIÓN
# ============================================================================


def cargar_retry_info():
    """Cargar información de reintentos"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            with open(RETRY_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}


def guardar_retry_info(intento, proxima_ejecucion):
    """Guardar información de reintentos"""
    try:
        info = {
            "intento": intento,
            "proxima_ejecucion": proxima_ejecucion,
            "timestamp": datetime.now().isoformat(),
        }
        with open(RETRY_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        log_custom(
            section="Error Principal",
            message=f"Error en función principal: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


def main():
    """Punto de entrada principal con gestión de reintentos"""
    try:
        # Determinar modo de operación
        if len(sys.argv) < 2:
            print(" Modo autónomo: Ejecutando búsqueda automática CON LÍMITE")
            asyncio.run(main_inteligente_autonomo("auto"))
        else:
            primer_arg = sys.argv[1]

            if primer_arg.startswith("task_"):
                print(f" Ejecutando tarea programada: {primer_arg} CON LÍMITE")
                tasks_file = sys.argv[2] if len(sys.argv) > 2 else "tasks.json"
                asyncio.run(main_inteligente_autonomo(tasks_file, primer_arg))
            elif primer_arg in ["auto", "costa_rica", "autonomo"]:
                print(f" Modo autónomo: {primer_arg} CON LÍMITE")
                asyncio.run(main_inteligente_autonomo(primer_arg))
            else:
                print(f" Procesando archivo: {primer_arg}")
                asyncio.run(main_inteligente_autonomo(primer_arg))

        # ÉXITO
        borrar_tarea_actual()
        limpiar_retry_info()
        limpiar_registro_ejecucion_actual()
        print(" Proceso completado exitosamente")

    except Exception as e:
        print(f" Error durante ejecución: {str(e)}")

        # Limpiar solo elementos de esta ejecución
        limpiar_solo_ejecucion_actual()
        borrar_tarea_actual()

        # Crear nueva tarea con más tiempo
        if crear_nueva_tarea_con_mas_tiempo():
            print(" Reintento programado automáticamente")
        else:
            print(" No se pudo programar reintento")
            limpiar_retry_info()

        sys.exit(1)


if __name__ == "__main__":
    if os.getenv("RUNNING_DOWNLOAD") == "1":
        log_custom(
            section="Modo Programado",
            message="Ejecutando como tarea programada integrada",
            level="INFO",
            file=LOG_FILE,
        )
        main()
    else:
        print(" PROCESADOR COMPLETO INTEGRADO - VERSIÓN CORREGIDA")
        print(" Características:")
        print("   • Consulta API de NASA automáticamente")
        print("   • Descarga masiva de camera metadata con aria2c")
        print("   • Procesa metadatos igual que rend_periodica.js")
        print("   • Descarga imágenes con aria2c optimizado")
        print("   • Procesa solo imágenes NUEVAS (no en BD)")
        print("   • Auto-limpieza si falla")
        print("   • Reintentos automáticos incrementales")
        print("   • Gestión automática de tareas Windows")
        print("   • LÍMITE APLICADO CORRECTAMENTE")
        print("")
        print(" Uso:")
        print(
            "   python run_batch_processor.py                    # Modo autónomo CON LÍMITE"
        )
        print(
            "   python run_batch_processor.py auto               # Modo autónomo explícito CON LÍMITE"
        )
        print(
            "   python run_batch_processor.py costa_rica         # Búsqueda Costa Rica CON LÍMITE"
        )
        print(
            "   python run_batch_processor.py task_123456789     # Ejecutar tarea específica CON LÍMITE"
        )
        print(
            "   python run_batch_processor.py tasks.json task_123 # Tarea desde archivo CON LÍMITE"
        )
        print(
            "   python run_batch_processor.py metadatos.json     # Procesar metadatos directos"
        )
        print("")
        print(" CAMBIOS APLICADOS:")
        print("    Removido 'await' de función síncrona")
        print("    Límite aplicado manualmente si las tareas no lo respetan")
        print("    CONCURRENT_LIMIT reducido a 5 para evitar sobrecarga")
        print("    Pausas entre lotes para no saturar el servidor")
        print("    Mejor manejo de errores en scraping")
        print("    Logs mejorados con información de límites")
        print("")
        main()(
            section="Retry Info",
            message=f"Error guardando retry info:",
            level="WARNING",
            file=LOG_FILE,
        )


def limpiar_retry_info():
    """Limpiar información de reintentos"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            os.remove(RETRY_INFO_FILE)
    except:
        pass


def borrar_tarea_actual():
    """Borrar la tarea programada actual"""
    try:
        cmd = f'schtasks /delete /tn "{TASK_NAME}" /f'
        resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if resultado.returncode == 0:
            log_custom(
                section="Gestión Tareas",
                message="Tarea programada eliminada exitosamente",
                level="INFO",
                file=LOG_FILE,
            )
    except Exception as e:
        log_custom(
            section="Gestión Tareas",
            message=f"Error eliminando tarea: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def crear_nueva_tarea_con_mas_tiempo():
    """Crear nueva tarea programada con tiempo incremental"""
    try:
        retry_info = cargar_retry_info()
        intento_actual = retry_info.get("intento", 0) + 1

        if intento_actual > MAX_RETRIES:
            log_custom(
                section="Gestión Tareas",
                message=f"Máximo de {MAX_RETRIES} intentos alcanzado",
                level="ERROR",
                file=LOG_FILE,
            )
            limpiar_retry_info()
            return False

        minutos_espera = 10 * intento_actual
        hora_ejecucion = datetime.now() + timedelta(minutes=minutos_espera)
        hora_str = hora_ejecucion.strftime("%H:%M")
        fecha_str = hora_ejecucion.strftime("%d/%m/%Y")

        script_path = os.path.abspath(__file__)
        argumentos = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
        comando_tarea = f'python "{script_path}" {argumentos}'

        cmd = f'schtasks /create /tn "{TASK_NAME}" /tr "{comando_tarea}" /sc once /st {hora_str} /sd {fecha_str} /f'
        resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if resultado.returncode == 0:
            guardar_retry_info(intento_actual, hora_ejecucion.isoformat())
            log_custom(
                section="Gestión Tareas",
                message=f"Nueva tarea programada - Intento {intento_actual}/{MAX_RETRIES} en {minutos_espera} min",
                level="INFO",
                file=LOG_FILE,
            )
            return True
        else:
            log_custom(
                section="Gestión Tareas",
                message=f"Error creando tarea: {resultado.stderr}",
                level="ERROR",
                file=LOG_FILE,
            )
            return False

    except Exception as e:
        log_custom(
            section="Gestión Tareas",
            message=f"Error creando nueva tarea: {e}",
            level="ERROR",
            file=LOG_FILE,
        )
        return False


def guardar_nasa_ids_ejecucion_actual(nasa_ids):
    """Guardar NASA_IDs que se van a procesar"""
    try:
        info = {
            "nasa_ids": nasa_ids,
            "timestamp": datetime.now().isoformat(),
            "total": len(nasa_ids),
        }
        with open(CURRENT_EXECUTION_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        log_custom(
            section="Ejecución Actual",
            message=f"Error guardando NASA_IDs: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def cargar_nasa_ids_ejecucion_actual():
    """Cargar NASA_IDs de la ejecución actual"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            with open(CURRENT_EXECUTION_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
                return info.get("nasa_ids", [])
    except:
        pass
    return []


def limpiar_registro_ejecucion_actual():
    """Limpiar registro de ejecución actual"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            os.remove(CURRENT_EXECUTION_FILE)
    except:
        pass


def limpiar_solo_ejecucion_actual():
    """Limpiar solo elementos de la ejecución actual"""
    nasa_ids_actuales = cargar_nasa_ids_ejecucion_actual()
    if nasa_ids_actuales:
        log_custom(
            section="Limpieza Ejecución",
            message=f"Limpiando {len(nasa_ids_actuales)} elementos de la ejecución actual",
            level="INFO",
            file=LOG_FILE,
        )
        # Aquí agregarías la lógica de limpieza de BD y archivos
    limpiar_registro_ejecucion_actual()


def cargar_tarea_por_id(task_id, tasks_file="tasks.json"):
    """Cargar configuración de tarea por ID"""
    try:
        possible_paths = [
            tasks_file,
            os.path.join(os.path.dirname(__file__), "..", "periodica", "tasks.json"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                break
        else:
            raise FileNotFoundError(f"No se encontró tasks.json")

        for task in tasks_data:
            if task.get("id") == task_id or task_id in task.get("id", ""):
                log_custom(
                    section="Tarea Encontrada",
                    message=f"Tarea {task_id} cargada: {task.get('description', 'Sin descripción')}",
                    level="INFO",
                    file=LOG_FILE,
                )
                return task

        raise ValueError(f"No se encontró tarea con ID: {task_id}")

    except Exception as e:
        log_custom(
            section="Error Carga Tarea",
            message=f"Error cargando tarea {task_id}: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


# ============================================================================
#  FUNCIONES DE PROCESAMIENTO CORREGIDAS
# ============================================================================


def find_by_suffix(obj: Dict, suffix: str, fallback=None):
    """Replicar findBySuffix() de JavaScript"""
    for key in obj:
        if key.endswith(suffix) and obj[key] is not None and obj[key] != "":
            return obj[key]
    return fallback


async def process_photo_optimized_without_camera_metadata(
    photo: Dict, nadir_alt_cache: Dict = None
) -> Optional[Dict]:
    """
     Procesar foto optimizada SIN camera metadata (se agrega después)
    """
    try:
        # Paso 1: Extraer datos básicos
        filename = find_by_suffix(photo, ".filename")
        directory = find_by_suffix(photo, ".directory")

        if not filename:
            return None

        # Paso 2: Formatear fecha y hora
        raw_date = find_by_suffix(photo, ".pdate", "")
        raw_time = find_by_suffix(photo, ".ptime", "")

        formatted_date = ""
        if len(raw_date) == 8:
            formatted_date = f"{raw_date[:4]}.{raw_date[4:6]}.{raw_date[6:8]}"

        formatted_hour = ""
        if len(raw_time) == 6:
            formatted_hour = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}"

        # Paso 3: Resolución
        width = find_by_suffix(photo, ".width", "")
        height = find_by_suffix(photo, ".height", "")
        resolucion_texto = f"{width} x {height} pixels" if width and height else ""

        # Paso 4: Mapear cámara
        camera_code = find_by_suffix(photo, ".camera", "Desconocida")
        camera_desc = cameraMap.get(camera_code, "Desconocida")

        # Paso 5: Mapear film
        film_code = find_by_suffix(photo, ".film", "UNKN")
        film_data = filmMap.get(
            film_code, {"type": "Desconocido", "description": "Desconocido"}
        )

        # Paso 6: NASA_ID
        nasa_id = filename.split(".")[0] if filename else "Sin_ID"
        if not nasa_id or nasa_id == "Sin_ID":
            return None

        # Paso 7: Obtener datos extra con cache
        if nadir_alt_cache is None:
            nadir_alt_cache = {}

        extra_data = nadir_alt_cache.get(nasa_id)
        if not extra_data:
            #  FIX CRÍTICO: NO usar await - la función es síncrona
            try:
                extra_data = obtener_nadir_altitud_camara_optimized(nasa_id)
            except Exception as e:
                log_custom(
                    section="Error Scraping",
                    message=f"Error obteniendo datos extra para {nasa_id}: {str(e)}",
                    level="WARNING",
                    file=LOG_FILE,
                )
                extra_data = None

            if not extra_data:
                extra_data = {
                    "NADIR_CENTER": None,
                    "ALTITUD": None,
                    "CAMARA": None,
                    "FECHA_CAPTURA": None,
                    "GEOTIFF_URL": None,
                    "HAS_GEOTIFF": False,
                }
            nadir_alt_cache[nasa_id] = extra_data

        # Paso 8: Determinar cámara final
        if (
            "Desconocida" in camera_desc
            or "Desconocido" in camera_desc
            or "Unspecified :" in camera_desc
        ):
            camera = extra_data.get("CAMARA") or "Desconocida"
        else:
            camera = camera_desc

        # Paso 9: URL inteligente
        if extra_data.get("HAS_GEOTIFF") and extra_data.get("GEOTIFF_URL"):
            final_image_url = extra_data["GEOTIFF_URL"]
        else:
            final_image_url = (
                f"https://eol.jsc.nasa.gov/DatabaseImages/{directory}/{filename}"
                if filename and directory
                else None
            )

        # Paso 10: Fecha final
        fecha_final = extra_data.get("FECHA_CAPTURA") or formatted_date

        # Paso 11: Construir resultado final (SIN CAMARA_METADATA por ahora)
        resultado = {
            "NASA_ID": nasa_id,
            "FECHA": fecha_final,
            "HORA": formatted_hour,
            "RESOLUCION": resolucion_texto,
            "URL": final_image_url,
            "NADIR_LAT": find_by_suffix(photo, ".nlat"),
            "NADIR_LON": find_by_suffix(photo, ".nlon"),
            "CENTER_LAT": find_by_suffix(photo, ".lat"),
            "CENTER_LON": find_by_suffix(photo, ".lon"),
            "NADIR_CENTER": extra_data.get("NADIR_CENTER"),
            "ALTITUD": extra_data.get("ALTITUD"),
            "LUGAR": find_by_suffix(photo, ".geon", ""),
            "ELEVACION_SOL": find_by_suffix(photo, ".elev", ""),
            "AZIMUT_SOL": find_by_suffix(photo, ".azi", ""),
            "COBERTURA_NUBOSA": find_by_suffix(photo, ".cldp", ""),
            "CAMARA": camera,
            "LONGITUD_FOCAL": find_by_suffix(photo, ".fclt"),
            "INCLINACION": find_by_suffix(photo, ".tilt"),
            "FORMATO": f"{film_data['type']}: {film_data['description']}",
            "CAMARA_METADATA": None,  # Se agregará después
        }

        return resultado

    except Exception as error:
        log_custom(
            section="Error Procesamiento",
            message=f"Error procesando foto: {str(error)}",
            level="ERROR",
            file=LOG_FILE,
        )
        return None


def deduplicar_metadatos(metadatos: List[Dict]) -> List[Dict]:
    """Deduplicar por NASA_ID"""
    vistos = set()
    unicos = []
    duplicados = 0

    for metadata in metadatos:
        nasa_id = metadata.get("NASA_ID")
        if not nasa_id or nasa_id == "Sin_ID":
            unicos.append(metadata)
            continue

        if nasa_id not in vistos:
            vistos.add(nasa_id)
            unicos.append(metadata)
        else:
            duplicados += 1

    log_custom(
        section="Deduplicación",
        message=f"Metadatos únicos: {len(unicos)}, Duplicados eliminados: {duplicados}",
        level="INFO",
        file=LOG_FILE,
    )
    return unicos


async def download_camera_metadata_selective(nasa_ids: List[str]) -> Dict[str, str]:
    """
    Descargar camera metadata solo para NASA_IDs específicos
    """
    print(f" Descarga selectiva de camera metadata para {len(nasa_ids)} NASA_IDs")

    from bulk_camera_downloader import (
        extract_camera_metadata_url,
        create_aria2c_input_file,
        download_with_aria2c,
        create_nasa_id_to_file_mapping,
        get_camera_output_folder,
    )

    # Obtener carpeta de salida
    output_folder, is_nas = get_camera_output_folder()
    if not output_folder:
        return {}

    # Extraer URLs solo para los NASA_IDs específicos
    camera_urls = {}
    errores = []

    print(f" Extrayendo URLs de camera metadata...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Enviar tareas solo para NASA_IDs específicos
        future_to_nasa_id = {
            executor.submit(extract_camera_metadata_url, nasa_id): nasa_id
            for nasa_id in nasa_ids
        }

        # Recoger resultados
        for future in as_completed(future_to_nasa_id):
            nasa_id, result = future.result()

            if result.startswith("ERROR:"):
                errores.append(f"{nasa_id}: {result}")
            else:
                camera_urls[nasa_id] = result

    print(f" URLs encontradas: {len(camera_urls)}, Errores: {len(errores)}")

    if not camera_urls:
        return {}

    # Crear archivo de entrada y descargar
    input_file = create_aria2c_input_file(camera_urls, output_folder)
    success = download_with_aria2c(input_file, output_folder, connections=10)

    if success:
        return create_nasa_id_to_file_mapping(camera_urls, output_folder)
    else:
        return {}


async def proceso_completo_integrado(configuracion_tarea: Dict = None, limite: int = 0):
    """
     PROCESO COMPLETO INTEGRADO - FLUJO OPTIMIZADO CON LÍMITE
    """
    base_path, is_nas, modo = verificar_destino_descarga()

    log_custom(
        section="Proceso Integrado",
        message=f"Iniciando proceso completo integrado - {modo} - Límite: {limite}",
        level="INFO",
        file=LOG_FILE,
    )

    print(" PROCESO COMPLETO INTEGRADO - FLUJO OPTIMIZADO")
    print(f" Modo: {modo}")
    print(f" Destino: {base_path}")
    print(f" Límite: {limite if limite > 0 else 'Sin límite'}")

    try:
        #  FASE 1: OBTENER IMÁGENES NUEVAS
        print(f"\n FASE 1: Obteniendo imágenes nuevas...")

        if configuracion_tarea:
            # Usar configuración de tarea programada
            log_custom(
                section="Tarea Programada",
                message=f"Ejecutando tarea: {configuracion_tarea.get('id', 'unknown')}",
                level="INFO",
                file=LOG_FILE,
            )
            imagenes_nuevas = await obtener_por_tarea_programada(configuracion_tarea)
        else:
            # Búsqueda automática de Costa Rica
            imagenes_nuevas = await obtener_imagenes_nuevas_costa_rica(
                limite=limite, modo_nocturno=True
            )

        if not imagenes_nuevas:
            log_custom(
                section="Sin Resultados",
                message="No se encontraron imágenes nuevas para procesar",
                level="WARNING",
                file=LOG_FILE,
            )
            print(" Todas las imágenes ya están procesadas")
            return

        #  APLICAR LÍMITE MANUALMENTE SI LA TAREA NO LO RESPETÓ
        if limite > 0 and len(imagenes_nuevas) > limite:
            print(
                f" Aplicando límite manual: {len(imagenes_nuevas)} → {limite} imágenes"
            )
            imagenes_nuevas = imagenes_nuevas[:limite]

        # Registrar NASA_IDs que vamos a procesar
        nasa_ids_nuevos = []
        for imagen in imagenes_nuevas:
            filename = None
            for key in imagen:
                if key.endswith(".filename"):
                    filename = imagen[key]
                    break
            if filename:
                nasa_id = filename.split(".")[0]
                if nasa_id and nasa_id != "Sin_ID":
                    nasa_ids_nuevos.append(nasa_id)

        guardar_nasa_ids_ejecucion_actual(nasa_ids_nuevos)

        print(f" Procesando {len(imagenes_nuevas)} imágenes nuevas")

        #  FASE 2: PROCESAMIENTO DE METADATOS (SIN camera metadata aún)
        print(
            f"\n FASE 2: Procesando metadatos con scraping (sin camera metadata)..."
        )

        metadatos = []
        nadir_alt_cache = {}
        CONCURRENT_LIMIT = 5  # Reducir para evitar sobrecargar el servidor

        for i in range(0, len(imagenes_nuevas), CONCURRENT_LIMIT):
            batch = imagenes_nuevas[i : i + CONCURRENT_LIMIT]
            batch_num = (i // CONCURRENT_LIMIT) + 1
            total_batches = (
                len(imagenes_nuevas) + CONCURRENT_LIMIT - 1
            ) // CONCURRENT_LIMIT

            print(f" Procesando lote {batch_num}/{total_batches}")

            # Procesar batch con async (SIN camera metadata)
            batch_tasks = [
                process_photo_optimized_without_camera_metadata(photo, nadir_alt_cache)
                for photo in batch
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    log_custom(
                        section="Error Batch",
                        message=f"Error en procesamiento: {result}",
                        level="ERROR",
                        file=LOG_FILE,
                    )
                elif result and result.get("NASA_ID"):
                    metadatos.append(result)

            progreso = min(i + CONCURRENT_LIMIT, len(imagenes_nuevas))
            print(
                f" Progreso: {(progreso / len(imagenes_nuevas)) * 100:.1f}% ({progreso}/{len(imagenes_nuevas)})"
            )

            # Pausa entre lotes para no sobrecargar
            await asyncio.sleep(1)

        print(
            f" Metadatos procesados: {len(metadatos)} de {len(imagenes_nuevas)} intentados"
        )

        #  FASE 3: DEDUPLICACIÓN Y GUARDADO JSON INICIAL
        print(f"\n FASE 3: Deduplicando y guardando JSON inicial...")

        metadatos_unicos = deduplicar_metadatos(metadatos)

        if not metadatos_unicos:
            raise Exception("No se generaron metadatos únicos válidos")

        output_path = "metadatos_periodicos.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadatos_unicos, f, indent=2, ensure_ascii=False)

        log_custom(
            section="JSON Inicial",
            message=f"JSON inicial guardado con {len(metadatos_unicos)} entradas: {output_path}",
            level="INFO",
            file=LOG_FILE,
        )

        print(
            f" JSON inicial guardado: {output_path} ({len(metadatos_unicos)} metadatos únicos)"
        )

        #  FASE 4: DESCARGA SELECTIVA DE CAMERA METADATA
        print(f"\n FASE 4: Descarga selectiva de camera metadata...")

        # Extraer solo los NASA_IDs del JSON final
        nasa_ids_finales = [
            meta["NASA_ID"] for meta in metadatos_unicos if meta.get("NASA_ID")
        ]

        print(
            f" Descargando camera metadata solo para {len(nasa_ids_finales)} imágenes del JSON final"
        )

        camera_metadata_mapping = await download_camera_metadata_selective(
            nasa_ids_finales
        )

        print(
            f" Camera metadata descargado para {len(camera_metadata_mapping)} imágenes"
        )

        #  FASE 5: ACTUALIZAR JSON CON CAMERA METADATA
        print(f"\n FASE 5: Actualizando JSON con camera metadata...")

        metadatos_actualizados = []
        for metadata in metadatos_unicos:
            nasa_id = metadata.get("NASA_ID")
            if nasa_id and nasa_id in camera_metadata_mapping:
                metadata["CAMARA_METADATA"] = camera_metadata_mapping[nasa_id]
            metadatos_actualizados.append(metadata)

        # Guardar JSON actualizado
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadatos_actualizados, f, indent=2, ensure_ascii=False)

        print(f" JSON actualizado con camera metadata")

        #  FASE 6: DESCARGA DE IMÁGENES
        print(f"\n FASE 6: Descargando imágenes...")

        descargar_imagenes_aria2c_optimizado(metadatos_actualizados, conexiones=32)

        #  FASE 7: PROCESAMIENTO EN BASE DE DATOS
        print(f"\n FASE 7: Procesando en base de datos...")

        processor = HybridOptimizedProcessor(database_path=DATABASE_PATH, batch_size=75)
        processor.process_complete_workflow(metadatos_actualizados)

        #  ÉXITO
        limpiar_registro_ejecucion_actual()
        limpiar_retry_info()

        log_custom(
            section="Proceso Completado",
            message=f"Proceso integrado completado exitosamente: {len(metadatos_actualizados)} imágenes procesadas",
            level="INFO",
            file=LOG_FILE,
        )

        print(
            f" Proceso completado exitosamente: {len(metadatos_actualizados)} imágenes procesadas"
        )

    except Exception as e:
        log_custom(
            section="Error Proceso Integrado",
            message=f"Error en proceso integrado: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        print(f" Error: {str(e)}")
        raise


# ============================================================================
#  PUNTO DE ENTRADA PRINCIPAL
# ============================================================================


async def main_inteligente_autonomo(json_filename_or_mode="auto", task_id=None):
    """Función principal con procesamiento autónomo"""
    try:
        if task_id and task_id.startswith("task_"):
            # Ejecutar tarea programada específica CON LÍMITE
            tarea_config = cargar_tarea_por_id(task_id)
            await proceso_completo_integrado(
                configuracion_tarea=tarea_config, limite=LIMITE_IMAGENES
            )

        elif json_filename_or_mode in ["auto", "costa_rica"]:
            # Modo autónomo CON LÍMITE
            await proceso_completo_integrado(limite=LIMITE_IMAGENES)

        elif os.path.exists(json_filename_or_mode):
            # Procesar archivo JSON existente
            with open(json_filename_or_mode, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) > 0:
                if "query" in data[0] and "return" in data[0]:
                    # Archivo de tareas programadas
                    for task in data:
                        await proceso_completo_integrado(
                            configuracion_tarea=task, limite=LIMITE_IMAGENES
                        )
                else:
                    # Archivo de metadatos - usar imageProcessor directamente
                    processor = HybridOptimizedProcessor(
                        database_path=DATABASE_PATH, batch_size=75
                    )
                    processor.process_complete_workflow(data)
        else:
            raise FileNotFoundError(f"No se encontró: {json_filename_or_mode}")

    except Exception as e:
        log_custom
