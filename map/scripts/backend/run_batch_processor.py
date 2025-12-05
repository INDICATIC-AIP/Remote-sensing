#!/usr/bin/env python3
"""
 PROCESADOR INTELIGENTE CON AUTO-RETRY
- Procesa solo imágenes NUEVAS (no en BD)
- Si falla: limpia solo las de esta ejecución
- Auto-programa reintentos con tiempo incremental
- Gestión automática de tareas de Windows
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

# Agregar rutas necesarias
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))

# Importaciones
from imageProcessor import (
    HybridOptimizedProcessor,
    descargar_imagenes_aria2c_optimizado,
    verificar_destino_descarga,
)
from extract_metadatos_enriquecido import extract_metadatos_enriquecido
from log import log_custom
from rutas import NAS_PATH, NAS_MOUNT

#  IMPORTAR CLIENTE PARA TAREAS PROGRAMADAS
from task_api_client import procesar_tarea_programada

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

LIMITE_IMAGENES = 15

# ============================================================================
#  CONFIGURACIÓN
# ============================================================================

API_KEY = os.getenv("NASA_API_KEY", "")
if not API_KEY:
    raise ValueError("NASA_API_KEY no está configurada en .env")
API_URL = "https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl"
LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "metadata.db")
RETRY_INFO_FILE = os.path.join(os.path.dirname(__file__), "retry_info.json")
CURRENT_EXECUTION_FILE = os.path.join(
    os.path.dirname(__file__), "current_execution.json"
)

TASK_NAME = "ISS_BatchProcessor"
MAX_RETRIES = 6  # Máximo 6 intentos (10, 20, 30, 40, 50, 60 min)


# ============================================================================
#  GESTIÓN DE TAREAS DE WINDOWS
# ============================================================================


def borrar_tarea_actual():
    """Borrar la tarea programada actual"""
    try:
        cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/delete",
            "/tn",
            TASK_NAME,
            "/f",
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        if resultado.returncode == 0:
            log_custom(
                section="Gestión Tareas",
                message="Tarea programada actual eliminada exitosamente",
                level="INFO",
                file=LOG_FILE,
            )
        else:
            log_custom(
                section="Gestión Tareas",
                message="No había tarea programada para eliminar (normal)",
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
        # Leer información de reintentos
        retry_info = cargar_retry_info()
        intento_actual = retry_info.get("intento", 0) + 1

        if intento_actual > MAX_RETRIES:
            log_custom(
                section="Gestión Tareas",
                message=f"Máximo de {MAX_RETRIES} intentos alcanzado. Proceso detenido.",
                level="ERROR",
                file=LOG_FILE,
            )
            limpiar_retry_info()
            return False

        # Calcular tiempo de espera (10, 20, 30, 40, 50, 60 min)
        minutos_espera = 10 * intento_actual
        hora_ejecucion = datetime.now() + timedelta(minutes=minutos_espera)
        hora_str = hora_ejecucion.strftime("%H:%M")
        fecha_str = hora_ejecucion.strftime("%d/%m/%Y")

        # Obtener argumentos del script actual
        script_path = os.path.abspath(__file__)
        argumentos = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""

        # Crear comando de tarea
        comando_tarea = f'python "{script_path}" {argumentos}'

        cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            comando_tarea,
            "/sc",
            "once",
            "/st",
            hora_str,
            "/sd",
            fecha_str,
            "/f",
        ]
        resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if resultado.returncode == 0:
            # Guardar información del reintento
            guardar_retry_info(intento_actual, hora_ejecucion.isoformat())

            log_custom(
                section="Gestión Tareas",
                message=f"Nueva tarea programada - Intento {intento_actual}/{MAX_RETRIES} en {minutos_espera} minutos ({hora_str})",
                level="INFO",
                file=LOG_FILE,
            )

            print(
                f" Reintento {intento_actual}/{MAX_RETRIES} programado en {minutos_espera} minutos"
            )
            print(
                f"⏰ Próxima ejecución: {hora_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}"
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


def crear_tarea_autoinicio_verificador():
    """Crear tarea programada que ejecuta verificador.py al iniciar Windows"""
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
        resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if resultado.returncode == 0:
            log_custom(
                section="Gestión Tareas",
                message="Tarea de auto-reinicio (ISS_RecoveryCheck) creada correctamente",
                level="INFO",
                file=LOG_FILE,
            )
        else:
            log_custom(
                section="Gestión Tareas",
                message=f"No se pudo crear tarea ISS_RecoveryCheck: {resultado.stderr}",
                level="WARNING",
                file=LOG_FILE,
            )
    except Exception as e:
        log_custom(
            section="Gestión Tareas",
            message=f"Error creando tarea de auto-reinicio: {e}",
            level="ERROR",
            file=LOG_FILE,
        )


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
            section="Retry Info",
            message=f"Error guardando retry info: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def limpiar_retry_info():
    """Limpiar información de reintentos (éxito o máximo alcanzado)"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            os.remove(RETRY_INFO_FILE)
        log_custom(
            section="Retry Info",
            message="Información de reintentos limpiada",
            level="INFO",
            file=LOG_FILE,
        )
    except:
        pass


# ============================================================================
#  GESTIÓN DE BASE DE DATOS
# ============================================================================


def verificar_nasa_ids_en_bd(nasa_ids):
    """Verificar qué NASA_IDs ya existen en la base de datos"""
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
    """Eliminar NASA_IDs específicos de la base de datos"""
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
            message=f"Error limpiando BD: {e}",
            level="ERROR",
            file=LOG_FILE,
        )


def limpiar_imagenes_nas(nasa_ids):
    """Eliminar imágenes específicas del NAS/almacenamiento"""
    try:
        base_path, is_nas, modo = verificar_destino_descarga()
        eliminados = 0

        for nasa_id in nasa_ids:
            # Buscar archivos relacionados con este NASA_ID
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
            message=f"Eliminados {eliminados} archivos del almacenamiento",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        log_custom(
            section="Limpieza NAS",
            message=f"Error limpiando almacenamiento: {e}",
            level="ERROR",
            file=LOG_FILE,
        )


# ============================================================================
#  GESTIÓN DE EJECUCIÓN ACTUAL
# ============================================================================


def guardar_nasa_ids_ejecucion_actual(nasa_ids):
    """Guardar los NASA_IDs que se van a procesar en esta ejecución"""
    try:
        info = {
            "nasa_ids": nasa_ids,
            "timestamp": datetime.now().isoformat(),
            "total": len(nasa_ids),
        }
        with open(CURRENT_EXECUTION_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        log_custom(
            section="Ejecución Actual",
            message=f"Registrados {len(nasa_ids)} NASA_IDs para esta ejecución",
            level="INFO",
            file=LOG_FILE,
        )
    except Exception as e:
        log_custom(
            section="Ejecución Actual",
            message=f"Error guardando NASA_IDs de ejecución: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def cargar_nasa_ids_ejecucion_actual():
    """Cargar los NASA_IDs de la ejecución actual para limpieza"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            with open(CURRENT_EXECUTION_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
                return info.get("nasa_ids", [])
    except:
        pass
    return []


def limpiar_registro_ejecucion_actual():
    """Limpiar registro de ejecución actual (éxito)"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            os.remove(CURRENT_EXECUTION_FILE)
    except:
        pass


def limpiar_solo_ejecucion_actual():
    """Limpiar solo los elementos de la ejecución actual"""
    nasa_ids_actuales = cargar_nasa_ids_ejecucion_actual()

    if nasa_ids_actuales:
        log_custom(
            section="Limpieza Ejecución",
            message=f"Limpiando {len(nasa_ids_actuales)} elementos de la ejecución actual",
            level="INFO",
            file=LOG_FILE,
        )

        # Limpiar BD y NAS solo de estos NASA_IDs
        limpiar_nasa_ids_de_bd(nasa_ids_actuales)
        limpiar_imagenes_nas(nasa_ids_actuales)

        print(f" Limpiados {len(nasa_ids_actuales)} elementos de esta ejecución")

    # Limpiar registro
    limpiar_registro_ejecucion_actual()


# ============================================================================
#  PROCESAMIENTO DE TAREAS PROGRAMADAS - ACTUALIZADO
# ============================================================================


def extraer_nasa_ids_de_resultados(results):
    """Extraer NASA_IDs de los resultados de API"""
    nasa_ids = []
    for result in results:
        filename = result.get("images.filename")
        if filename:
            nasa_id = filename.split(".")[0]
            if nasa_id and nasa_id != "Sin_ID":
                nasa_ids.append(nasa_id)
    return nasa_ids


async def run_task_inteligente(task):
    """Ejecutar tarea programada usando task_api_client"""
    task_id = task.get("id", "unknown")

    log_custom(
        section="Tarea Inteligente",
        message=f"Ejecutando tarea inteligente: {task_id}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        #  USAR EL TASK API CLIENT (que ya probaste)
        log_custom(
            section="Tarea Inteligente",
            message=f"Procesando tarea con task_api_client: {task_id}",
            level="INFO",
            file=LOG_FILE,
        )

        from task_api_client import procesar_tarea_programada

        results_nuevos = await procesar_tarea_programada(task)

        if not results_nuevos:
            log_custom(
                section="Tarea Inteligente",
                message="No se encontraron resultados nuevos",
                level="WARNING",
                file=LOG_FILE,
            )
            print(" No hay imágenes nuevas para procesar")
            return

        print(f" Task API Client devolvió {len(results_nuevos)} imágenes nuevas")

        #  REGISTRAR NASA_IDs PARA LIMPIEZA
        nasa_ids_nuevos = extraer_nasa_ids_de_resultados(results_nuevos)

        guardar_nasa_ids_ejecucion_actual(nasa_ids_nuevos)

        log_custom(
            section="Tarea Inteligente",
            message=f"Registrados {len(nasa_ids_nuevos)} NASA_IDs para procesamiento",
            level="INFO",
            file=LOG_FILE,
        )

        #  GUARDAR RESULTADOS JSON PARA DEBUG
        try:
            results_file = os.path.join(
                os.path.dirname(__file__), "resultados_task_api.json"
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
                message=f"No se pudo guardar resultados Task API: {e}",
                level="WARNING",
                file=LOG_FILE,
            )

        print(
            f" Procesando {len(results_nuevos)} imágenes nuevas con scraping enriquecido..."
        )

        #  APLICAR SCRAPING ENRIQUECIDO
        metadatos = extract_metadatos_enriquecido(results_nuevos)

        if not metadatos:
            raise Exception("No se pudieron extraer metadatos enriquecidos")

        log_custom(
            section="Tarea Inteligente",
            message=f"Metadatos enriquecidos extraídos: {len(metadatos)} registros",
            level="INFO",
            file=LOG_FILE,
        )

        print(f" Scraping completado: {len(metadatos)} metadatos enriquecidos")

        #  DESCARGAR Y PROCESAR IMÁGENES
        print(" Iniciando descarga de imágenes...")
        descargar_imagenes_aria2c_optimizado(metadatos, conexiones=32)

        print(" Procesando imágenes en base de datos...")
        processor = HybridOptimizedProcessor(database_path=DATABASE_PATH, batch_size=75)
        processor.process_complete_workflow(metadatos)

        #   ÉXITO - LIMPIAR REGISTROS DE CONTROL
        limpiar_registro_ejecucion_actual()
        limpiar_retry_info()

        log_custom(
            section="Tarea Inteligente Completada",
            message=f"Tarea completada exitosamente: {len(metadatos)} imágenes procesadas",
            level="INFO",
            file=LOG_FILE,
        )

        print(
            f" Proceso completado: {len(metadatos)} imágenes procesadas exitosamente"
        )

    except Exception as e:
        #  FALLO: Limpiar solo esta ejecución y reintentar
        log_custom(
            section="Error Tarea Inteligente",
            message=f"Error en tarea {task_id}: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )

        print(f" Error durante procesamiento: {str(e)}")
        raise  # Re-lanzar para que main() maneje el reintento


# ============================================================================
#  FUNCIÓN PRINCIPAL ACTUALIZADA
# ============================================================================


async def main_inteligente(json_filename):
    """Función principal con procesamiento inteligente"""

    # Verificar destino
    base_path, is_nas, modo = verificar_destino_descarga()

    log_custom(
        section="Inicio Procesamiento Inteligente",
        message=f"Iniciando procesamiento inteligente desde: {json_filename}",
        level="INFO",
        file=LOG_FILE,
    )

    print(" PROCESADOR INTELIGENTE CON AUTO-RETRY")
    print(f" Modo: {modo}")
    print(f" Destino: {base_path}")

    # Mostrar información de reintentos si existe
    retry_info = cargar_retry_info()
    if retry_info:
        intento = retry_info.get("intento", 0)
        print(f" Reintento {intento}/{MAX_RETRIES}")

    try:
        # Leer archivo de tareas o metadatos
        if not os.path.exists(json_filename):
            raise FileNotFoundError(f"No se encontró el archivo: {json_filename}")

        with open(json_filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Determinar si es archivo de tareas o metadatos
        if isinstance(data, list) and len(data) > 0:
            if "consultas" in data[0] or ("query" in data[0] and "return" in data[0]):
                #  ES ARCHIVO DE TAREAS PROGRAMADAS - USAR TASK API CLIENT
                print(
                    f" Procesando {len(data)} tareas programadas con task_api_client"
                )

                for task in data:
                    await run_task_inteligente(task)

            else:
                # Es archivo de metadatos - procesamiento directo (NO TOCAR)
                print(f" Procesando {len(data)} metadatos directos")

                # Extraer NASA_IDs del archivo
                nasa_ids_archivo = [
                    item.get("NASA_ID") for item in data if item.get("NASA_ID")
                ]

                # Verificar cuáles ya existen
                nasa_ids_existentes = verificar_nasa_ids_en_bd(nasa_ids_archivo)

                # Filtrar solo los nuevos
                metadatos_nuevos = [
                    item
                    for item in data
                    if item.get("NASA_ID") not in nasa_ids_existentes
                ]

                if not metadatos_nuevos:
                    print(" Todos los metadatos ya están procesados")
                    return

                # Aplicar límite si está definido
                if LIMITE_IMAGENES > 0 and len(metadatos_nuevos) > LIMITE_IMAGENES:
                    metadatos_nuevos = metadatos_nuevos[:LIMITE_IMAGENES]
                    print(
                        f" Aplicando límite: procesando {LIMITE_IMAGENES} de {len(metadatos_nuevos)} metadatos"
                    )

                # Registrar los que vamos a procesar
                nasa_ids_nuevos = [item["NASA_ID"] for item in metadatos_nuevos]
                guardar_nasa_ids_ejecucion_actual(nasa_ids_nuevos)

                print(f" Procesando {len(metadatos_nuevos)} metadatos nuevos")

                # Procesar metadatos directamente
                descargar_imagenes_aria2c_optimizado(metadatos_nuevos, conexiones=32)

                processor = HybridOptimizedProcessor(
                    database_path=DATABASE_PATH, batch_size=75
                )
                processor.process_complete_workflow(metadatos_nuevos)

                # Limpiar registros de control
                limpiar_registro_ejecucion_actual()
                limpiar_retry_info()

                print(
                    f" Proceso completado: {len(metadatos_nuevos)} metadatos procesados exitosamente"
                )

        else:
            raise ValueError("Formato de archivo JSON no reconocido")

        #  ÉXITO TOTAL
        log_custom(
            section="Procesamiento Inteligente Completado",
            message="Procesamiento inteligente completado exitosamente",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        #  CUALQUIER FALLO: Limpiar y reintentar
        log_custom(
            section="Error Procesamiento Inteligente",
            message=f"Error durante procesamiento: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )

        print(f" Error: {str(e)}")
        raise  # Re-lanzar para que el manejo principal gestione el reintento


# ============================================================================
#  PUNTO DE ENTRADA PRINCIPAL
# ============================================================================


def main():
    """Punto de entrada principal con gestión de reintentos"""

    try:
        # Procesar argumentos
        if len(sys.argv) < 2:
            print(" Uso: python run_batch_processor.py <archivo_json>")
            print(" Ejemplo: python run_batch_processor.py tasks.json")
            sys.exit(1)

        json_file = sys.argv[1]

        #  EJECUTAR CON ASYNCIO
        asyncio.run(main_inteligente(json_file))

        #  ÉXITO: Borrar tarea programada y limpiar registros
        borrar_tarea_actual()
        limpiar_retry_info()
        limpiar_registro_ejecucion_actual()

        crear_tarea_autoinicio_verificador()

        print(" Proceso completado exitosamente")

    except Exception as e:
        #  FALLO: Gestionar limpieza y reintento
        print(f" Error durante ejecución: {str(e)}")

        # Limpiar solo elementos de esta ejecución
        limpiar_solo_ejecucion_actual()

        # Borrar tarea actual
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
        # Modo tarea programada automática
        log_custom(
            section="Modo Programado Inteligente",
            message="Ejecutando como tarea programada con procesamiento inteligente",
            level="INFO",
            file=LOG_FILE,
        )
        main()
    else:
        # Modo manual
        print(" PROCESADOR INTELIGENTE CON AUTO-RETRY")
        print(" Características:")
        print("   • Procesa solo imágenes NUEVAS (no en BD)")
        print("   • Auto-limpieza si falla")
        print("   • Reintentos automáticos incrementales")
        print("   • Gestión automática de tareas Windows")
        print("")
        main()
