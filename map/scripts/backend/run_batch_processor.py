#!/usr/bin/env python3
"""
 PROCESADOR INTELIGENTE CON AUTO-RETRY
- Procesa solo imágenes NUEVAS (no en BD)
- Si failure: limpia solo las de esta ejecución
- Auto-programa retries con tiempo incremental
- Gestión automática de tasks de Windows
"""

import os
import sys
import json
import requests
import subprocess
import sqlite3
from datetime import datetime, timedelta
import time
import asyncio

# Agregar paths necesarias
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))

# Importaciones
from imageProcessor import (
    HybridOptimizedProcessor,
    download_imagees_aria2c_optimized,
    verificar_destination_descarga,
)
from extract_enriched_metadata import extract_metadata_enriquecido
from log import log_custom
from map.routes import NAS_PATH, NAS_MOUNT

#  IMPORTAR CLIENTE PARA TAREAS PROGRAMADAS
from task_api_client import process_task_scheduled

# Cargar configuración desde el módulo helper
from config import PROJECT_ROOT, ENV_FILE, load_env_config

# Asegurar que .env está cargado
env_file, loaded = load_env_config()

LIMITE_IMAGENES = 320

# ============================================================================
#  CONFIGURACIÓN
# ============================================================================

API_KEY = os.getenv("NASA_API_KEY", "")
if not API_KEY:
    raise ValueError(f"NASA_API_KEY not configured. Check {env_file}")
API_URL = "https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl"
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "iss", "general.log")
DATABASE_PATH = os.path.join(PROJECT_ROOT, "map", "db", "metadata.db")
RETRY_INFO_FILE = os.path.join(os.path.dirname(__file__), "retry_info.json")
CURRENT_EXECUTION_FILE = os.path.join(
    os.path.dirname(__file__), "current_execution.json"
)

TASK_NAME = "ISS_BatchProcessor"
MAX_RETRIES = 6  # Máximo 6 intentos (10, 20, 30, 40, 50, 60 min)


# ============================================================================
#  GESTIÓN DE TAREAS DE WINDOWS
# ============================================================================


def borrar_task_actual():
    """Borrar la task scheduled actual"""
    try:
        cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/delete",
            "/tn",
            TASK_NAME,
            "/f",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_custom(
                section="Task Management",
                message="Tarea scheduled actual eliminada exitosamente",
                level="INFO",
                file=LOG_FILE,
            )
        else:
            log_custom(
                section="Task Management",
                message="No había task scheduled para eliminar (normal)",
                level="INFO",
                file=LOG_FILE,
            )
    except Exception as e:
        log_custom(
            section="Task Management",
            message=f"Error eliminando task: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def crear_nueva_task_con_mas_tiempo():
    """Create nueva task scheduled con tiempo incremental"""
    try:
        # Leer information de retries
        retry_info = load_retry_info()
        current_attempt = retry_info.get("intento", 0) + 1

        if current_attempt > MAX_RETRIES:
            log_custom(
                section="Task Management",
                message=f"Máximo de {MAX_RETRIES} intentos alcanzado. Proceso detenido.",
                level="ERROR",
                file=LOG_FILE,
            )
            clear_retry_info()
            return False

        # Calcular tiempo de espera (10, 20, 30, 40, 50, 60 min)
        wait_minutes = 10 * current_attempt
        execution_time = datetime.now() + timedelta(minutes=wait_minutes)
        time_str = execution_time.strftime("%H:%M")
        date_str = execution_time.strftime("%d/%m/%Y")

        # Obtener argumentos del script actual
        script_path = os.path.abspath(__file__)
        argumentos = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""

        # Crear comando de task
        task_command = f'python "{script_path}" {argumentos}'

        cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            task_command,
            "/sc",
            "once",
            "/st",
            time_str,
            "/sd",
            date_str,
            "/f",
        ]
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            # Guardar information del retry
            save_retry_info(current_attempt, execution_time.isoformat())

            log_custom(
                section="Task Management",
                message=f"Nueva task scheduled - Intento {current_attempt}/{MAX_RETRIES} en {wait_minutes} minutos ({time_str})",
                level="INFO",
                file=LOG_FILE,
            )

            print(
                f" Reintento {current_attempt}/{MAX_RETRIES} scheduled en {wait_minutes} minutos"
            )
            print(
                f"⏰ Próxima ejecución: {execution_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            return True
        else:
            log_custom(
                section="Task Management",
                message=f"Error creando task: {result.stderr}",
                level="ERROR",
                file=LOG_FILE,
            )
            return False

    except Exception as e:
        log_custom(
            section="Task Management",
            message=f"Error creando nueva task: {e}",
            level="ERROR",
            file=LOG_FILE,
        )
        return False


def crear_task_autoinicio_verificador():
    """Create task scheduled que ejecuta verificador.py al start Windows"""
    try:
        verificador_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "verificador.py")
        )
        cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/create",
            "/tn",
            "ISS_RecoveryCheck",
            "/tr",
            f"python {verificador_path}",
            "/sc",
            "onstart",
            "/rl",
            "HIGHEST",
            "/f",
        ]
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            log_custom(
                section="Task Management",
                message="Tarea de auto-reinicio (ISS_RecoveryCheck) creada correctmente",
                level="INFO",
                file=LOG_FILE,
            )
        else:
            log_custom(
                section="Task Management",
                message=f"No se pudo crear task ISS_RecoveryCheck: {result.stderr}",
                level="WARNING",
                file=LOG_FILE,
            )
    except Exception as e:
        log_custom(
            section="Task Management",
            message=f"Error creando task de auto-reinicio: {e}",
            level="ERROR",
            file=LOG_FILE,
        )


def load_retry_info():
    """Load information de retries"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            with open(RETRY_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}


def save_retry_info(intento, proxima_execution):
    """Save information de retries"""
    try:
        info = {
            "intento": intento,
            "proxima_execution": proxima_execution,
            "timestamp": datetime.now().isoformat(),
        }
        with open(RETRY_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        log_custom(
            section="Retry Info",
            message=f"Error saving retry info: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def clear_retry_info():
    """Clean information de retries (success o máximo alcanzado)"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            os.remove(RETRY_INFO_FILE)
        log_custom(
            section="Retry Info",
            message="Información de retries limpiada",
            level="INFO",
            file=LOG_FILE,
        )
    except:
        pass


# ============================================================================
#  GESTIÓN DE BASE DE DATOS
# ============================================================================


def verificar_nasa_ids_en_bd(nasa_ids):
    """Verify qué NASA_IDs ya existen en la base de datos"""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            #  USAR TABLA Image CON nasa_id (minúscula)
            placeholders = ",".join("?" * len(nasa_ids))
            query = f"SELECT nasa_id FROM Image WHERE nasa_id IN ({placeholders})"

            cursor.execute(query, nasa_ids)
            existentes = {row[0] for row in cursor.fetchall()}

            return existentes

    except Exception as e:
        log_custom(
            section="Verificación BD",
            message=f"Error verificando NASA_IDs en BD: {e}",
            level="ERROR",
            file=LOG_FILE,
        )
        return set()


def limpiar_nasa_ids_de_bd(nasa_ids):
    """Delete NASA_IDs específicos de la base de datos"""
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            placeholders = ",".join("?" * len(nasa_ids))
            query = f"DELETE FROM metadata WHERE NASA_ID IN ({placeholders})"

            cursor.execute(query, nasa_ids)
            eliminados = cursor.rowcount
            conn.commit()

            log_custom(
                section="Limpieza BD",
                message=f"Eliminados {eliminados} registros de BD: {nasa_ids[:5]}...",
                level="INFO",
                file=LOG_FILE,
            )

    except Exception as e:
        log_custom(
            section="Limpieza BD",
            message=f"Error cleaning BD: {e}",
            level="ERROR",
            file=LOG_FILE,
        )


def limpiar_imagees_nas(nasa_ids):
    """Delete imágenes específicas del NAS/almacenamiento"""
    try:
        base_path, is_nas, mode = verificar_destination_descarga()
        eliminados = 0

        for nasa_id in nasa_ids:
            # Buscar files relacionados con este NASA_ID
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if nasa_id in file:
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                            eliminados += 1
                        except:
                            pass

        log_custom(
            section="Limpieza NAS",
            message=f"Eliminados {eliminados} files del almacenamiento",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        log_custom(
            section="Limpieza NAS",
            message=f"Error cleaning almacenamiento: {e}",
            level="ERROR",
            file=LOG_FILE,
        )


# ============================================================================
#  GESTIÓN DE EJECUCIÓN ACTUAL
# ============================================================================


def guardar_nasa_ids_execution_actual(nasa_ids):
    """Save los NASA_IDs que se van a process en esta ejecución"""
    try:
        info = {
            "nasa_ids": nasa_ids,
            "timestamp": datetime.now().isoformat(),
            "total": len(nasa_ids),
        }
        with open(CURRENT_EXECUTION_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        log_custom(
            section="Current Execution",
            message=f"Registrados {len(nasa_ids)} NASA_IDs para esta ejecución",
            level="INFO",
            file=LOG_FILE,
        )
    except Exception as e:
        log_custom(
            section="Current Execution",
            message=f"Error saving NASA_IDs de ejecución: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def cargar_nasa_ids_execution_actual():
    """Load los NASA_IDs de la ejecución actual para limpieza"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            with open(CURRENT_EXECUTION_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
                return info.get("nasa_ids", [])
    except:
        pass
    return []


def limpiar_registro_execution_actual():
    """Clean registro de ejecución actual (success)"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            os.remove(CURRENT_EXECUTION_FILE)
    except:
        pass


def limpiar_solo_execution_actual():
    """Clean solo los elementos de la ejecución actual"""
    nasa_ids_actuales = cargar_nasa_ids_execution_actual()

    if nasa_ids_actuales:
        log_custom(
            section="Execution Cleanup",
            message=f"Limpiando {len(nasa_ids_actuales)} elementos de la ejecución actual",
            level="INFO",
            file=LOG_FILE,
        )

        # Limpiar BD y NAS solo de estos NASA_IDs
        limpiar_nasa_ids_de_bd(nasa_ids_actuales)
        limpiar_imagees_nas(nasa_ids_actuales)

        print(f" Limpiados {len(nasa_ids_actuales)} elementos de esta ejecución")

    # Limpiar registro
    limpiar_registro_execution_actual()


# ============================================================================
#  PROCESAMIENTO DE TAREAS PROGRAMADAS - ACTUALIZADO
# ============================================================================


def extraer_nasa_ids_de_results(results):
    """Extraer NASA_IDs de los results de API"""
    nasa_ids = []
    for result in results:
        filename = result.get("images.filename")
        if filename:
            nasa_id = filename.split(".")[0]
            if nasa_id and nasa_id != "Sin_ID":
                nasa_ids.append(nasa_id)
    return nasa_ids


async def run_task_inteligente(task):
    """Ejecutar task scheduled usando task_api_client"""
    task_id = task.get("id", "unknown")

    log_custom(
        section="Tarea Inteligente",
        message=f"Ejecutando task inteligente: {task_id}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        #  USAR EL TASK API CLIENT (que ya probaste)
        log_custom(
            section="Tarea Inteligente",
            message=f"Procesando task con task_api_client: {task_id}",
            level="INFO",
            file=LOG_FILE,
        )

        from task_api_client import process_task_scheduled, get_last_task_stats

        results_nuevos = await process_task_scheduled(task)
        task_stats = get_last_task_stats()
        unique_total = task_stats.get("unique_results", len(results_nuevos))
        existing_in_db = task_stats.get(
            "existing_in_db", max(unique_total - len(results_nuevos), 0)
        )
        new_total = task_stats.get("new_results", len(results_nuevos))

        print("\n Query summary (vs DB):")
        print(f"  Unique candidates: {unique_total}")
        print(f"  Already in DB: {existing_in_db}")
        print(f"  New to process: {new_total}")

        if not results_nuevos:
            log_custom(
                section="Tarea Inteligente",
                message="No se encontraron results nuevos",
                level="WARNING",
                file=LOG_FILE,
            )
            print(" No hay imágenes nuevas para process")
            return

        ask_confirmation = os.getenv("ISS_CONFIRM", "1") == "1" and sys.stdin.isatty()
        if ask_confirmation:
            while True:
                try:
                    answer = (
                        input("Continue with scraping/download? (s/n): ")
                        .strip()
                        .lower()
                    )
                except EOFError:
                    answer = "n"

                if answer in ("s", "y"):
                    break
                if answer == "n":
                    log_custom(
                        section="Task Confirmation",
                        message="Execution cancelled by user after new-vs-db summary",
                        level="WARNING",
                        file=LOG_FILE,
                    )
                    print(" Cancelled by user.")
                    return

                print(" Please answer with 's' (yes) or 'n' (no).")

        print(f" Task API Client devolvió {len(results_nuevos)} imágenes nuevas")

        #  REGISTRAR NASA_IDs PARA LIMPIEZA
        nasa_ids_nuevos = extraer_nasa_ids_de_results(results_nuevos)

        guardar_nasa_ids_execution_actual(nasa_ids_nuevos)

        log_custom(
            section="Tarea Inteligente",
            message=f"Registrados {len(nasa_ids_nuevos)} NASA_IDs para processing",
            level="INFO",
            file=LOG_FILE,
        )

        #  GUARDAR RESULTADOS JSON PARA DEBUG
        try:
            results_file = os.path.join(
                os.path.dirname(__file__), "results_task_api.json"
            )
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results_nuevos, f, indent=2, ensure_ascii=False, default=str)

            log_custom(
                section="Debug",
                message=f"Resultados Task API guardados en: {results_file}",
                level="INFO",
                file=LOG_FILE,
            )
        except Exception as e:
            log_custom(
                section="Debug",
                message=f"No se pudo guardar results Task API: {e}",
                level="WARNING",
                file=LOG_FILE,
            )

        print(
            f" Procesando {len(results_nuevos)} imágenes nuevas con scraping enriquecido..."
        )

        #  APLICAR SCRAPING ENRIQUECIDO
        metadata = extract_metadata_enriquecido(results_nuevos)

        if not metadata:
            raise Exception("No se pudieron extraer metadata enriquecidos")

        log_custom(
            section="Tarea Inteligente",
            message=f"Metadatos enriquecidos extraídos: {len(metadata)} registros",
            level="INFO",
            file=LOG_FILE,
        )

        print(f" Scraping completed: {len(metadata)} metadata enriquecidos")

        #  DESCARGAR Y PROCESAR IMÁGENES
        print(" Running download + DB workflow...")
        processor = HybridOptimizedProcessor(database_path=DATABASE_PATH, batch_size=75)
        processor.process_complete_workflow(metadata)

        #   ÉXITO - LIMPIAR REGISTROS DE CONTROL
        limpiar_registro_execution_actual()
        clear_retry_info()

        log_custom(
            section="Tarea Inteligente Completada",
            message=f"Tarea completed exitosamente: {len(metadata)} imágenes procesadas",
            level="INFO",
            file=LOG_FILE,
        )

        print(f" Proceso completed: {len(metadata)} imágenes procesadas exitosamente")

    except Exception as e:
        #  FALLO: Limpiar solo esta ejecución y reintentar
        log_custom(
            section="Error Tarea Inteligente",
            message=f"Error in task {task_id}: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )

        print(f" Error during processing: {str(e)}")
        raise  # Re-lanzar para que main() maneje el retry


# ============================================================================
#  FUNCIÓN PRINCIPAL ACTUALIZADA
# ============================================================================


async def main_inteligente(json_filename):
    """Función principal con processing inteligente"""

    # Verificar destination
    base_path, is_nas, mode = verificar_destination_descarga()

    log_custom(
        section="Inicio Procesamiento Inteligente",
        message=f"Iniciando processing inteligente desde: {json_filename}",
        level="INFO",
        file=LOG_FILE,
    )

    print(" PROCESADOR INTELIGENTE CON AUTO-RETRY")
    print(f" Modo: {mode}")
    print(f" Destino: {base_path}")

    # Mostrar information de retries si existe
    retry_info = load_retry_info()
    if retry_info:
        intento = retry_info.get("intento", 0)
        print(f" Reintento {intento}/{MAX_RETRIES}")

    try:
        # Leer file de tasks o metadata
        if not os.path.exists(json_filename):
            raise FileNotFoundError(f"No se encontró el file: {json_filename}")

        with open(json_filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Determinar si es file de tasks o metadata
        if isinstance(data, list) and len(data) > 0:
            if "consultas" in data[0] or ("query" in data[0] and "return" in data[0]):
                #  ES ARCHIVO DE TAREAS PROGRAMADAS - USAR TASK API CLIENT
                print(f" Procesando {len(data)} tasks scheduleds con task_api_client")

                for task in data:
                    await run_task_inteligente(task)

            else:
                # Es file de metadata - processing directo (NO TOCAR)
                print(f" Procesando {len(data)} metadata directos")

                # Extraer NASA_IDs del file
                nasa_ids_file = [
                    item.get("NASA_ID") for item in data if item.get("NASA_ID")
                ]

                # Verificar cuáles ya existen
                nasa_ids_existentes = verificar_nasa_ids_en_bd(nasa_ids_file)

                # Filtrar solo los nuevos
                metadata_nuevos = [
                    item
                    for item in data
                    if item.get("NASA_ID") not in nasa_ids_existentes
                ]

                if not metadata_nuevos:
                    print(" Todos los metadata ya están procesados")
                    return

                # Aplicar limit si está definido
                if LIMITE_IMAGENES > 0 and len(metadata_nuevos) > LIMITE_IMAGENES:
                    metadata_nuevos = metadata_nuevos[:LIMITE_IMAGENES]
                    print(
                        f" Aplicando limit: processing {LIMITE_IMAGENES} de {len(metadata_nuevos)} metadata"
                    )

                # Registrar los que vamos a process
                nasa_ids_nuevos = [item["NASA_ID"] for item in metadata_nuevos]
                guardar_nasa_ids_execution_actual(nasa_ids_nuevos)

                print(f" Procesando {len(metadata_nuevos)} metadata nuevos")

                # Procesar metadata directamente
                download_imagees_aria2c_optimized(metadata_nuevos, conexiones=32)

                processor = HybridOptimizedProcessor(
                    database_path=DATABASE_PATH, batch_size=75
                )
                processor.process_complete_workflow(metadata_nuevos)

                # Limpiar registros de control
                limpiar_registro_execution_actual()
                clear_retry_info()

                print(
                    f" Proceso completed: {len(metadata_nuevos)} metadata procesados exitosamente"
                )

        else:
            raise ValueError("Formato de file JSON no reconocido")

        #  ÉXITO TOTAL
        log_custom(
            section="Procesamiento Inteligente Completado",
            message="Procesamiento inteligente completed exitosamente",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        #  CUALQUIER FALLO: Limpiar y reintentar
        log_custom(
            section="Error Procesamiento Inteligente",
            message=f"Error during processing: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )

        print(f" Error: {str(e)}")
        raise  # Re-lanzar para que el manejo principal gestione el retry


# ============================================================================
#  PUNTO DE ENTRADA PRINCIPAL
# ============================================================================


def main():
    """Punto de entrada principal con gestión de retries"""

    try:
        # Procesar argumentos
        if len(sys.argv) < 2:
            print(" Uso: python run_batch_processor.py <file_json>")
            print(" Ejemplo: python run_batch_processor.py tasks.json")
            sys.exit(1)

        json_file = sys.argv[1]

        #  EJECUTAR CON ASYNCIO
        asyncio.run(main_inteligente(json_file))

        #  ÉXITO: Borrar task scheduled y limpiar registros
        borrar_task_actual()
        clear_retry_info()
        limpiar_registro_execution_actual()

        crear_task_autoinicio_verificador()

        print(" Proceso completed exitosamente")

    except Exception as e:
        #  FALLO: Gestionar limpieza y retry
        print(f" Error during ejecución: {str(e)}")

        # Limpiar solo elementos de esta ejecución
        limpiar_solo_execution_actual()

        # Borrar task actual
        borrar_task_actual()

        # Crear nueva task con más tiempo
        if crear_nueva_task_con_mas_tiempo():
            print(" Reintento scheduled automáticamente")
        else:
            print(" No se pudo programar retry")
            clear_retry_info()

        sys.exit(1)


if __name__ == "__main__":
    if os.getenv("RUNNING_DOWNLOAD") == "1":
        # Modo task scheduled automática
        log_custom(
            section="Modo Programado Inteligente",
            message="Ejecutando como task scheduled con processing inteligente",
            level="INFO",
            file=LOG_FILE,
        )
        main()
    else:
        # Modo manual
        print(" PROCESADOR INTELIGENTE CON AUTO-RETRY")
        print(" Características:")
        print("   • Procesa solo imágenes NUEVAS (no en BD)")
        print("   • Auto-limpieza si failure")
        print("   • Reintentos automáticos incrementales")
        print("   • Gestión automática de tasks Windows")
        print("")
        main()
