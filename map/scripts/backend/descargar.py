#!/usr/bin/env python3
"""
REPLICAR EXACTAMENTE processPhotoOptimized() de rend_periodica.js
"""

import os
import sys
import json
import asyncio
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Agregar rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from nasa_api_client import NASAAPIClient, obtener_imagenes_nuevas_costa_rica
from extract_metadatos_enriquecido import (
    obtener_nadir_altitud_camara_optimized,
    obtener_camera_metadata_optimized,
)
from log import log_custom

LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")

#  IMPORTAR MAPEOS IGUAL QUE EN JS
try:
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils"))
    )
    from data import cameraMap, filmMap

    print(" Mapeos de cámara y film cargados exitosamente")
except ImportError as e:
    print(f" Error cargando data.py: {e}")
    cameraMap = {}
    filmMap = {}


def find_by_suffix(obj: Dict, suffix: str, fallback=None):
    """Replicar findBySuffix() de JavaScript"""
    for key in obj:
        if key.endswith(suffix) and obj[key] is not None and obj[key] != "":
            return obj[key]
    return fallback


async def process_photo_optimized(
    photo: Dict, metadata_cache: Dict = None, nadir_alt_cache: Dict = None
) -> Optional[Dict]:
    """
     REPLICAR EXACTAMENTE processPhotoOptimized() de rend_periodica.js
    """
    try:
        #  PASO 1: EXTRAER DATOS BÁSICOS (igual que JS)
        filename = find_by_suffix(photo, ".filename")
        directory = find_by_suffix(photo, ".directory")

        if not filename:
            print(" Sin filename:", photo)
            return None

        #  PASO 2: FORMATEAR FECHA Y HORA (igual que JS)
        raw_date = find_by_suffix(photo, ".pdate", "")
        raw_time = find_by_suffix(photo, ".ptime", "")

        formatted_date = ""
        if len(raw_date) == 8:
            formatted_date = f"{raw_date[:4]}.{raw_date[4:6]}.{raw_date[6:8]}"

        formatted_hour = ""
        if len(raw_time) == 6:
            formatted_hour = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}"

        #  PASO 3: RESOLUCIÓN (igual que JS)
        width = find_by_suffix(photo, ".width", "")
        height = find_by_suffix(photo, ".height", "")
        resolucion_texto = f"{width} x {height} pixels" if width and height else ""

        #  PASO 4: MAPEAR CÁMARA (igual que JS)
        camera_code = find_by_suffix(photo, ".camera", "Desconocida")
        camera_desc = cameraMap.get(camera_code, "Desconocida")

        #  PASO 5: MAPEAR FILM (igual que JS)
        film_code = find_by_suffix(photo, ".film", "UNKN")
        film_data = filmMap.get(
            film_code, {"type": "Desconocido", "description": "Desconocido"}
        )

        #  PASO 6: NASA_ID (igual que JS)
        nasa_id = filename.split(".")[0] if filename else "Sin_ID"

        if not nasa_id or nasa_id == "Sin_ID":
            print(f" NASA_ID inválido: {nasa_id}, filename: {filename}")
            return None

        #  PASO 7: SCRAPING CON CACHE (igual que JS)
        if metadata_cache is None:
            metadata_cache = {}
        if nadir_alt_cache is None:
            nadir_alt_cache = {}

        extra_data = nadir_alt_cache.get(nasa_id)
        camera_metadata_path = metadata_cache.get(nasa_id)

        if not extra_data or not camera_metadata_path:
            # Hacer scraping si no está en cache
            promises = []

            if not extra_data:
                promises.append(obtener_nadir_altitud_camara_optimized(nasa_id))
            else:
                promises.append(extra_data)

            if not camera_metadata_path:
                promises.append(obtener_camera_metadata_optimized(nasa_id))
            else:
                promises.append(camera_metadata_path)

            try:
                # Ejecutar promises concurrentemente
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=2) as executor:
                    if not extra_data:
                        future1 = loop.run_in_executor(
                            executor,
                            lambda: asyncio.run(
                                obtener_nadir_altitud_camara_optimized(nasa_id)
                            ),
                        )
                    else:
                        future1 = asyncio.create_task(
                            asyncio.sleep(0, result=extra_data)
                        )

                    if not camera_metadata_path:
                        future2 = loop.run_in_executor(
                            executor,
                            lambda: asyncio.run(
                                obtener_camera_metadata_optimized(nasa_id)
                            ),
                        )
                    else:
                        future2 = asyncio.create_task(
                            asyncio.sleep(0, result=camera_metadata_path)
                        )

                    new_extra_data, new_camera_metadata_path = await asyncio.gather(
                        future1, future2
                    )

                if not extra_data:
                    extra_data = new_extra_data or {
                        "NADIR_CENTER": None,
                        "ALTITUD": None,
                        "CAMARA": None,
                        "FECHA_CAPTURA": None,
                        "GEOTIFF_URL": None,
                        "HAS_GEOTIFF": False,
                    }
                    nadir_alt_cache[nasa_id] = extra_data

                if not camera_metadata_path:
                    camera_metadata_path = new_camera_metadata_path
                    metadata_cache[nasa_id] = camera_metadata_path

            except Exception as promise_error:
                print(f" Error en promises para {nasa_id}: {promise_error}")
                extra_data = {
                    "NADIR_CENTER": None,
                    "ALTITUD": None,
                    "CAMARA": None,
                    "FECHA_CAPTURA": None,
                    "GEOTIFF_URL": None,
                    "HAS_GEOTIFF": False,
                }
                camera_metadata_path = None

        #  PASO 8: DETERMINAR CÁMARA FINAL (igual que JS)
        camera = None
        if (
            "Desconocida" in camera_desc
            or "Desconocido" in camera_desc
            or "Unspecified :" in camera_desc
        ):
            camera = extra_data.get("CAMARA") or "Desconocida"
        else:
            camera = camera_desc

        #  PASO 9: URL INTELIGENTE (igual que JS)
        if extra_data.get("HAS_GEOTIFF") and extra_data.get("GEOTIFF_URL"):
            final_image_url = extra_data["GEOTIFF_URL"]
            print(f" Usando GeoTIFF para {nasa_id}")
        else:
            final_image_url = (
                f"https://eol.jsc.nasa.gov/DatabaseImages/{directory}/{filename}"
                if filename and directory
                else None
            )
            print(f" Usando JPG para {nasa_id}")

        #  PASO 10: FECHA FINAL (igual que JS)
        fecha_final = extra_data.get("FECHA_CAPTURA") or formatted_date

        #  PASO 11: CONSTRUIR RESULTADO FINAL (igual que JS)
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
            "CAMARA_METADATA": camera_metadata_path,
        }

        print(
            f" Procesado: {nasa_id} - URL: {'SI' if final_image_url else 'NO'} - Fecha: {fecha_final}"
        )
        return resultado

    except Exception as error:
        print(f" Error procesando foto: {error}")
        return None


async def replicate_descargar_ahora(limite: int = 0):
    """
     REPLICAR EXACTAMENTE descargarAhora() de rend_periodica.js
    """
    print(" REPLICANDO descargarAhora() COMPLETO")
    print("=" * 60)

    #  PASO 1: Obtener imágenes nuevas (igual que fetchData + verificar)
    print(" PASO 1: Obteniendo imágenes nuevas...")
    imagenes_to_process = await obtener_imagenes_nuevas_costa_rica(
        limite=limite, modo_nocturno=True
    )

    if not imagenes_to_process:
        print(" No hay imágenes nuevas para procesar")
        return []

    print(f" Procesando {len(imagenes_to_process)} imágenes nuevas")

    #  PASO 2: Cache para evitar llamadas duplicadas (igual que JS)
    metadata_cache = {}
    nadir_alt_cache = {}

    #  PASO 3: Procesar con concurrencia limitada (igual que JS)
    CONCURRENT_LIMIT = 10
    metadatos = []
    procesados = 0

    print(f" PASO 2: Procesando metadatos con límite de {CONCURRENT_LIMIT}...")

    for i in range(0, len(imagenes_to_process), CONCURRENT_LIMIT):
        batch = imagenes_to_process[i : i + CONCURRENT_LIMIT]
        batch_num = (i // CONCURRENT_LIMIT) + 1
        total_batches = (
            len(imagenes_to_process) + CONCURRENT_LIMIT - 1
        ) // CONCURRENT_LIMIT

        print(
            f" Procesando lote {batch_num}/{total_batches}: elementos {i} a {min(i + CONCURRENT_LIMIT - 1, len(imagenes_to_process) - 1)}"
        )

        # Procesar batch con async
        batch_tasks = [
            process_photo_optimized(photo, metadata_cache, nadir_alt_cache)
            for photo in batch
        ]

        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        for j, result in enumerate(batch_results):
            if isinstance(result, Exception):
                print(f" Error en elemento {i + j}: {result}")
            elif result and result.get("NASA_ID"):
                metadatos.append(result)
                print(f" Procesado exitosamente: {result['NASA_ID']}")
            else:
                print(f" Resultado sin NASA_ID válido")

        procesados = min(i + CONCURRENT_LIMIT, len(imagenes_to_process))
        progreso = (procesados / len(imagenes_to_process)) * 100
        print(f" Progreso: {progreso:.1f}% ({procesados}/{len(imagenes_to_process)})")

        # Pequeña pausa entre lotes
        if i + CONCURRENT_LIMIT < len(imagenes_to_process):
            await asyncio.sleep(0.1)

    print(
        f" RESUMEN: {len(metadatos)} metadatos procesados de {len(imagenes_to_process)} intentados"
    )

    #  PASO 4: Deduplicar (igual que JS)
    print(" PASO 3: Deduplicando metadatos...")
    metadatos_unicos = deduplicar_metadatos(metadatos)

    #  PASO 5: Guardar JSON (igual que JS)
    output_path = "metadatos_replicados.json"

    if metadatos_unicos:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadatos_unicos, f, indent=2, ensure_ascii=False)

        print(f" JSON guardado: {output_path}")
        print(f" Metadatos únicos: {len(metadatos_unicos)}")

        # Mostrar primeros 3 ejemplos
        print(f" Primeros 3 ejemplos:")
        for i, metadata in enumerate(metadatos_unicos[:3]):
            print(
                f"   {i + 1}. {metadata.get('NASA_ID')} - {metadata.get('FECHA')} - {metadata.get('CAMARA')}"
            )

    return metadatos_unicos


def deduplicar_metadatos(metadatos: List[Dict]) -> List[Dict]:
    """Deduplicar por NASA_ID (igual que JS)"""
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
            print(f" Duplicado detectado y eliminado: {nasa_id}")

    print(
        f" Deduplicación completada: {len(unicos)} únicos, {duplicados} duplicados eliminados"
    )
    return unicos


async def main():
    """Función principal de prueba"""
    print(" REPLICADOR DE processPhotoOptimized()")
    print(" Objetivo: Generar mismo JSON que rend_periodica.js")
    print()

    try:
        # Probar con límite pequeño primero
        metadatos = await replicate_descargar_ahora(limite=20)

        if metadatos:
            print(f"\n ÉXITO: {len(metadatos)} metadatos generados")
            print(" Compara el archivo 'metadatos_replicados.json' con el de la UI")
        else:
            print("\n No se generaron metadatos")

    except Exception as e:
        print(f"\n Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
