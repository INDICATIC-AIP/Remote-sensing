#!/usr/bin/env python3
"""
 DESCARGA MASIVA DE CAMERA METADATA CON ARIA2C
1. Extrae todas las URLs de camera metadata
2. Las descarga masivamente con aria2c
3. Organiza los files descargados
"""

import os
import sys
import json
import asyncio
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup
import time

# Agregar paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from nasa_api_client import obtener_imagees_nuevas_costa_rica
from log import log_custom
from map.routes import NAS_PATH, NAS_MOUNT

LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")


def get_camera_output_folder():
    """Determinar folder de salida para camera metadata"""
    try:
        nas_available = os.path.ismount(NAS_MOUNT) and os.path.exists(NAS_PATH)

        if nas_available:
            camera_data_path = os.path.join(NAS_PATH, "camera_data")
            mode = "PRODUCCIÓN (NAS)"
        else:
            camera_data_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "API-NASA", "camera_data")
            )
            mode = "DESARROLLO (Local)"

        os.makedirs(camera_data_path, exist_ok=True)

        log_custom(
            section="Camera Metadata Bulk",
            message=f"Carpeta configurada - {mode}: {camera_data_path}",
            level="INFO",
            file=LOG_FILE,
        )

        return camera_data_path, nas_available

    except Exception as e:
        log_custom(
            section="Error Camera Metadata",
            message=f"Error configurando folder: {e}",
            level="ERROR",
            file=LOG_FILE,
        )
        return None, False


def extract_camera_metadata_url(nasa_id: str, timeout: int = 8) -> Tuple[str, str]:
    """
    Extraer URL de camera metadata para un NASA_ID específico
    Retorna: (nasa_id, url_or_error)
    """
    try:
        parts = nasa_id.split("-")
        if len(parts) != 3:
            return nasa_id, f"ERROR: NASA_ID mal formateado"

        mission, roll, frame = parts
        url = f"https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Buscar botón de camera metadata
        button = soup.find("input", {"type": "button", "value": "View camera metadata"})

        if button and button.get("onclick"):
            onclick_value = button.get("onclick")
            start = onclick_value.find("('") + 2
            end = onclick_value.find("')", start)
            file_url = onclick_value[start:end]

            if file_url and file_url.startswith("/"):
                full_url = f"https://eol.jsc.nasa.gov{file_url}"
                return nasa_id, full_url
            else:
                return nasa_id, "ERROR: URL de file inválida"
        else:
            return nasa_id, "ERROR: No se encontró botón de camera metadata"

    except Exception as e:
        return nasa_id, f"ERROR: {str(e)}"


async def extract_all_camera_urls(
    imagees: List[Dict], max_workers: int = 20
) -> Dict[str, str]:
    """
    Extraer todas las URLs de camera metadata usando threading
    """
    print(f" Extrayendo URLs de camera metadata para {len(imagees)} imágenes...")
    print(f" Usando {max_workers} workers concurrentes")

    # Extraer NASA_IDs
    nasa_ids = []
    for image in imagees:
        filename = None
        for key in image:
            if key.endswith(".filename"):
                filename = image[key]
                break

        if filename:
            nasa_id = filename.split(".")[0]
            if nasa_id and nasa_id != "Sin_ID":
                nasa_ids.append(nasa_id)

    print(f" NASA_IDs a process: {len(nasa_ids)}")

    # Extraer URLs con threading
    camera_urls = {}
    errors = []
    procesados = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Enviar todas las tasks
        future_to_nasa_id = {
            executor.submit(extract_camera_metadata_url, nasa_id): nasa_id
            for nasa_id in nasa_ids
        }

        # Recoger results
        for future in as_completed(future_to_nasa_id):
            nasa_id, result = future.result()
            procesados += 1

            if result.startswith("ERROR:"):
                errors.append(f"{nasa_id}: {result}")
                print(f" {nasa_id}: {result}")
            else:
                camera_urls[nasa_id] = result
                print(f" {nasa_id}: URL encontrada")

            # Progreso cada 10%
            if procesados % max(1, len(nasa_ids) // 10) == 0:
                progreso = (procesados / len(nasa_ids)) * 100
                print(
                    f" Progreso extracción: {progreso:.1f}% ({procesados}/{len(nasa_ids)})"
                )

    print(f"\n RESUMEN EXTRACCIÓN:")
    print(f"    URLs encontradas: {len(camera_urls)}")
    print(f"    Errores: {len(errors)}")

    if errors:
        print(f"\n Primeros 5 errors:")
        for error in errors[:5]:
            print(f"   - {error}")

    return camera_urls


def create_aria2c_input_file(camera_urls: Dict[str, str], output_folder: str) -> str:
    """
    Crear file de entrada para aria2c con URLs y nombres de file
    """
    input_file = os.path.join(output_folder, "camera_metadata_urls.txt")

    print(f" Creando file de entrada para aria2c: {input_file}")

    with open(input_file, "w", encoding="utf-8") as f:
        for nasa_id, url in camera_urls.items():
            # Extraer nombre de file de la URL
            filename = os.path.basename(url)
            if not filename or filename == url:
                filename = f"{nasa_id}_camera_metadata.txt"

            # Formato aria2c: URL\n  out=filename\n
            f.write(f"{url}\n")
            f.write(f"  out={filename}\n")

    print(f" Archivo creado con {len(camera_urls)} URLs")
    return input_file


def download_with_aria2c(
    input_file: str, output_folder: str, connections: int = 16
) -> bool:
    """
    Descargar todos los files usando aria2c
    """
    print(f"\n INICIANDO DESCARGA MASIVA CON ARIA2C")
    print(f" Carpeta destination: {output_folder}")
    print(f" Conexiones: {connections}")

    # Comando aria2c optimized para muchos files pequeños
    command = [
        "aria2c",
        "-i",
        input_file,
        "-d",
        output_folder,
        "-j",
        str(connections),  # Conexiones concurrentes
        "--max-connection-per-server=4",  # Conexiones por servidor
        "--min-split-size=1K",  # Archivos pequeños, no dividir
        "--split=1",  # Un hilo por file
        "--summary-interval=5",  # Progreso cada 5 segundos
        "--continue=true",
        "--timeout=30",
        "--retry-wait=2",
        "--max-tries=3",
        "--console-log-level=info",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "--file-allocation=none",  # No pre-asignar espacio
        "--check-certificate=false",  # Para evitar problemas SSL menores
    ]

    try:
        log_custom(
            section="Descarga Camera Metadata",
            message=f"Iniciando descarga masiva con aria2c: {len(open(input_file).readlines()) // 2} files",
            level="INFO",
            file=LOG_FILE,
        )

        start_time = time.time()

        # Ejecutar aria2c
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
        )

        descargados = 0
        errors = 0

        # Monitorear progreso
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue

            # Detectar downloads completeds
            if "Download complete:" in line or ("[#" in line and "100%" in line):
                descargados += 1
                if descargados % 10 == 0:  # Log cada 10 files
                    print(f" Descargados: {descargados}")

            # Detectar errors
            elif "ERROR" in line and "SSL" not in line:
                errors += 1
                print(f" Error: {line}")

            # Mostrar velocidad ocasionalmente
            elif "DL:" in line and "KB/s" in line and descargados % 50 == 0:
                print(f" {line}")

        # Esperar a que termine
        process.wait()

        download_time = time.time() - start_time

        if process.returncode == 0:
            print(f"\n DESCARGA COMPLETADA")
            print(f"    Archivos descargados: {descargados}")
            print(f"    Errores: {errors}")
            print(f"   ⏱ Tiempo total: {download_time:.1f}s")

            log_custom(
                section="Descarga Completada",
                message=f"Camera metadata descargado: {descargados} files en {download_time:.1f}s",
                level="INFO",
                file=LOG_FILE,
            )

            return True
        else:
            print(f" Error in aria2c: código {process.returncode}")
            return False

    except Exception as e:
        print(f" Error ejecutando aria2c: {e}")
        log_custom(
            section="Error Descarga",
            message=f"Error in descarga masiva: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        return False
    finally:
        # Limpiar file temporal
        if os.path.exists(input_file):
            os.remove(input_file)


def create_nasa_id_to_file_mapping(
    camera_urls: Dict[str, str], output_folder: str
) -> Dict[str, str]:
    """
    Crear mapeo de NASA_ID a file descargado
    """
    mapping = {}

    for nasa_id, url in camera_urls.items():
        filename = os.path.basename(url)
        if not filename or filename == url:
            filename = f"{nasa_id}_camera_metadata.txt"

        file_path = os.path.join(output_folder, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            mapping[nasa_id] = file_path

    print(f" Mapeo creado: {len(mapping)} files válidos")
    return mapping


async def bulk_download_camera_metadata(limit: int = 0) -> Dict[str, str]:
    """
    Función principal para descarga masiva de camera metadata

    Returns:
        Dict[nasa_id, file_path] - Mapeo de NASA_ID a file descargado
    """
    print(" DESCARGA MASIVA DE CAMERA METADATA")
    print("=" * 60)

    # Paso 1: Obtener imágenes nuevas
    print(" PASO 1: Obteniendo imágenes nuevas...")
    imagees = await obtener_imagees_nuevas_costa_rica(
        limit=limit, mode_nocturno=True
    )

    if not imagees:
        print(" No hay imágenes nuevas")
        return {}

    print(f" Procesando {len(imagees)} imágenes nuevas")

    # Paso 2: Configurar folder de salida
    output_folder, is_nas = get_camera_output_folder()
    if not output_folder:
        print(" Error configurando folder de salida")
        return {}

    # Paso 3: Extraer URLs de camera metadata
    print(f"\n PASO 2: Extrayendo URLs de camera metadata...")
    camera_urls = await extract_all_camera_urls(imagees, max_workers=20)

    if not camera_urls:
        print(" No se encontraron URLs de camera metadata")
        return {}

    # Paso 4: Crear file de entrada para aria2c
    print(f"\n PASO 3: Preparando descarga masiva...")
    input_file = create_aria2c_input_file(camera_urls, output_folder)

    # Paso 5: Descargar con aria2c
    print(f"\n PASO 4: Descargando con aria2c...")
    success = download_with_aria2c(input_file, output_folder, connections=20)

    if not success:
        print(" Error in descarga masiva")
        return {}

    # Paso 6: Crear mapeo final
    print(f"\n PASO 5: Creando mapeo final...")
    mapping = create_nasa_id_to_file_mapping(camera_urls, output_folder)

    print(f"\n DESCARGA MASIVA COMPLETADA")
    print(f"    Archivos en: {output_folder}")
    print(f"    Mapeo disponible para: {len(mapping)} NASA_IDs")

    return mapping


async def main():
    """Función principal de test"""
    print(" DESCARGADOR MASIVO DE CAMERA METADATA")
    print(" Extrae URLs y descarga con aria2c masivamente")
    print()

    try:
        # Probar con limit pequeño
        mapping = await bulk_download_camera_metadata(limit=20)

        if mapping:
            print(f"\n ÉXITO: {len(mapping)} files descargados")
            print("\n Primeros 5 ejemplos:")
            for i, (nasa_id, file_path) in enumerate(list(mapping.items())[:5]):
                file_size = (
                    os.path.getsize(file_path) if os.path.exists(file_path) else 0
                )
                print(
                    f"   {i + 1}. {nasa_id} → {os.path.basename(file_path)} ({file_size} bytes)"
                )
        else:
            print("\n No se downloadon files")

    except Exception as e:
        print(f"\n Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
