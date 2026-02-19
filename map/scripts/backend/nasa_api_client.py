#!/usr/bin/env python3
"""
 CLIENTE API NASA - CONSULTAS INTELIGENTES
Replica la funcionalidad de rend_periodica.js en Python
"""

import os
import sys
import json
import requests
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Importar logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom

# Cargar configuración desde el módulo helper
from config import PROJECT_ROOT, ENV_FILE, load_env_config

# Asegurar que .env está cargado
env_file, loaded = load_env_config()

# Configuración
API_KEY = os.getenv("NASA_API_KEY", "")
if not API_KEY:
    raise ValueError(f"NASA_API_KEY not configured. Check {env_file}")
API_URL = "https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl"
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "iss", "general.log")
DATABASE_PATH = os.path.join(PROJECT_ROOT, "db", "metadata.db")

# Configuración por defecto de Costa Rica
DEFAULT_BOUNDING_BOX = {"latMin": 6.1, "latMax": 10.8, "lonMin": -82.9, "lonMax": -77.3}


class NASAAPIClient:
    """Cliente para consultas inteligentes a la API de NASA"""

    def __init__(self, bounding_box: Dict = None, mode_nocturno: bool = True):
        self.bounding_box = bounding_box or DEFAULT_BOUNDING_BOX
        self.mode_nocturno = mode_nocturno
        self.coord_sources = ["frames", "nadir", "mlcoord"]

        # Configuración de campos por table (igual que en JS)
        self.tables = {
            "frames": [
                "mission",
                "roll",
                "frame",
                "tilt",
                "pdate",
                "ptime",
                "cldp",
                "azi",
                "elev",
                "fclt",
                "lat",
                "lon",
                "nlat",
                "nlon",
                "camera",
                "film",
                "geon",
                "feat",
            ],
            "images": [
                "mission",
                "roll",
                "frame",
                "directory",
                "filename",
                "width",
                "height",
                "annotated",
                "cropped",
                "filesize",
            ],
            "nadir": [
                "mission",
                "roll",
                "frame",
                "pdate",
                "ptime",
                "lat",
                "lon",
                "azi",
                "elev",
                "cldp",
            ],
            "camera": ["mission", "roll", "frame", "fclt", "camera"],
            "captions": ["mission", "roll", "frame", "caption"],
            "mlfeat": ["mission", "roll", "frame", "feat"],
            "mlcoord": [
                "mission",
                "roll",
                "frame",
                "lat",
                "lon",
                "orientation",
                "resolution_long",
                "resolution_short",
                "ul_lat",
                "ul_lon",
                "ur_lat",
                "ur_lon",
                "ll_lat",
                "ll_lon",
                "lr_lat",
                "lr_lon",
            ],
            "publicfeatures": ["mission", "roll", "frame", "features"],
        }

        # Mapeo de tables permitidas por fuente
        self.allowed_return_tables = {
            "frames": ["frames", "images", "camera", "captions", "mlfeat"],
            "nadir": ["nadir", "images", "camera", "captions"],
            "mlcoord": ["mlcoord", "images", "mlfeat", "camera"],
        }

    def build_query(
        self, filters: List[Dict], coord_source: str, bounding_box: Dict
    ) -> str:
        """Construir query string con formato de pipes igual que en JavaScript"""
        query_parts = []

        #  AGREGAR FILTROS ADICIONALES PRIMERO (igual que en JS)
        user_filters = [f for f in filters if f.get("table") == coord_source]
        for filter_item in user_filters:
            table = filter_item.get("table", "")
            field = filter_item.get("field", "")
            operator = filter_item.get("operator", "")
            value = filter_item.get("value", "")

            if table and field and operator and value:
                query_parts.append(f"{table}|{field}|{operator}|{value}")

        #  AGREGAR FILTROS DE BOUNDING BOX (igual que en JS)
        bounding_filters = [
            f"{coord_source}|lat|ge|{bounding_box['latMin']}",
            f"{coord_source}|lat|le|{bounding_box['latMax']}",
            f"{coord_source}|lon|ge|{bounding_box['lonMin']}",
            f"{coord_source}|lon|le|{bounding_box['lonMax']}",
        ]
        query_parts.extend(bounding_filters)

        #  UNIR CON PIPES (no con 'and')
        return "|".join(query_parts)

    def build_return(self, coord_source: str) -> str:
        """Construir campos de retorno con formato de pipes igual que en JavaScript"""
        return_list = []

        #  CAMPOS BÁSICOS ESENCIALES (no todos los por defecto)
        essential_fields = {
            "frames": [
                "mission",
                "roll",
                "frame",
                "pdate",
                "ptime",
                "lat",
                "lon",
                "nlat",
                "nlon",
                "camera",
                "film",
            ],
            "nadir": [
                "mission",
                "roll",
                "frame",
                "pdate",
                "ptime",
                "lat",
                "lon",
                "azi",
                "elev",
            ],
            "mlcoord": ["mission", "roll", "frame", "lat", "lon", "orientation"],
        }

        #  AGREGAR CAMPOS ESENCIALES DE LA FUENTE ACTUAL
        if coord_source in essential_fields:
            for field in essential_fields[coord_source]:
                return_list.append(f"{coord_source}|{field}")

        #  SIEMPRE AGREGAR CAMPOS BÁSICOS DE IMAGES
        essential_image_fields = ["directory", "filename", "width", "height"]
        for field in essential_image_fields:
            return_list.append(f"images|{field}")

        #  UNIR CON PIPES
        return "|".join(return_list)

    def get_nocturno_queries(self, coord_source: str) -> List[Dict]:
        """Get consultas para mode nocturno"""
        if coord_source in ["frames", "nadir"]:
            return [
                {
                    "operator1": "ge",
                    "value1": "003000",
                    "operator2": "le",
                    "value2": "045959",
                },
                {
                    "operator1": "ge",
                    "value1": "050000",
                    "operator2": "le",
                    "value2": "103000",
                },
            ]
        else:
            return [
                {"operator1": None, "value1": None, "operator2": None, "value2": None}
            ]

    async def process_consulta(self, api_url: str, source: str) -> List[Dict]:
        """Process una consulta individual a la API"""
        try:
            log_custom(
                section="Consulta API NASA",
                message=f"Consultando fuente: {source}",
                level="INFO",
                file=LOG_FILE,
            )

            response = requests.get(api_url, timeout=30)
            response.raise_for_status()

            raw_data = response.json()

            if not isinstance(raw_data, list):
                log_custom(
                    section="Consulta API NASA",
                    message=f"No se encontraron results para fuente: {source}",
                    level="WARNING",
                    file=LOG_FILE,
                )
                return []

            # Procesar results y filtrar por alta resolución
            processed_results = []
            for photo in raw_data:
                # Normalizar keys (reemplazar | por .)
                normalized = {}
                for key, value in photo.items():
                    normalized[key.replace("|", ".")] = value

                #  FILTRAR ALTA RESOLUCIÓN - MEJORADO
                directory = normalized.get("images.directory", "").lower()

                # Buscar indicadores de alta resolución
                is_high_res = (
                    "large" in directory
                    or "highres" in directory
                    or "/highres/" in directory
                    or directory.endswith("highres")
                    or "large" in directory
                    or "/large/" in directory
                )

                if is_high_res:
                    normalized["coordSource"] = source
                    processed_results.append(normalized)

            log_custom(
                section="Consulta API NASA",
                message=f"Fuente {source}: {len(processed_results)} results de alta resolución de {len(raw_data)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            return processed_results

        except Exception as e:
            log_custom(
                section="Error Consulta API",
                message=f"Error in consulta {source}: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            return []

    def verificar_nasa_ids_en_bd(self, nasa_ids: List[str]) -> set:
        """Verify qué NASA_IDs ya existen en la base de datos"""
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(nasa_ids))
                query = f"SELECT nasa_id FROM Image WHERE nasa_id IN ({placeholders})"
                cursor.execute(query, nasa_ids)
                existentes = {row[0] for row in cursor.fetchall()}
                return existentes
        except Exception as e:
            log_custom(
                section="Error BD",
                message=f"Error verificando NASA_IDs: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            return set()

    def extraer_nasa_ids_de_results(self, results: List[Dict]) -> List[str]:
        """Extraer NASA_IDs de los results"""
        nasa_ids = []
        for result in results:
            filename = result.get("images.filename")
            if filename:
                nasa_id = filename.split(".")[0]
                if nasa_id and nasa_id != "Sin_ID":
                    nasa_ids.append(nasa_id)
        return nasa_ids

    def filtrar_solo_nuevos(
        self, results: List[Dict], nasa_ids_existentes: set
    ) -> List[Dict]:
        """Filtrar solo results que NO están en BD"""
        nuevos = []
        for result in results:
            filename = result.get("images.filename")
            if filename:
                nasa_id = filename.split(".")[0]
                if nasa_id not in nasa_ids_existentes:
                    nuevos.append(result)
        return nuevos

    def deduplicar_results(self, results: List[Dict]) -> List[Dict]:
        """Deduplicar results por NASA_ID"""
        vistos = set()
        unicos = []
        duplicados = 0

        for result in results:
            filename = result.get("images.filename")
            nasa_id = filename.split(".")[0] if filename else None

            if not nasa_id or nasa_id == "Sin_ID":
                unicos.append(result)
                continue

            if nasa_id not in vistos:
                vistos.add(nasa_id)
                unicos.append(result)
            else:
                duplicados += 1

        log_custom(
            section="Deduplicación API",
            message=f"Resultados únicos: {len(unicos)}, Duplicados eliminados: {duplicados}",
            level="INFO",
            file=LOG_FILE,
        )

        return unicos

    async def fetch_data_inteligente(
        self, filtros_adicionales: List[Dict] = None, limit_imagees: int = 0
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Función principal que replica fetchData() de JavaScript
        Retorna: (todos_los_results, solo_results_nuevos)
        """
        log_custom(
            section="Fetch Data Inteligente",
            message=f"Iniciando consultas inteligentes - Modo nocturno: {self.mode_nocturno}",
            level="INFO",
            file=LOG_FILE,
        )

        # Filtros base (solo coordenadas, sin ptime)
        filtros_base = []
        if filtros_adicionales:
            filtros_base.extend(filtros_adicionales)

        all_results = []

        # Procesar cada fuente de coordenadas
        for source in self.coord_sources:
            consultas = []

            if self.mode_nocturno:
                consultas = self.get_nocturno_queries(source)
            else:
                consultas = [
                    {
                        "operator1": None,
                        "value1": None,
                        "operator2": None,
                        "value2": None,
                    }
                ]

            # Procesar cada consulta nocturna
            for nocturna in consultas:
                filtros_actuales = filtros_base.copy()

                # Agregar filtros de tiempo nocturno si aplica
                if (
                    nocturna["operator1"]
                    and nocturna["operator2"]
                    and source in ["frames", "nadir"]
                ):
                    # Remover filtros existentes de ptime
                    filtros_actuales = [
                        f
                        for f in filtros_actuales
                        if not (f.get("table") == source and f.get("field") == "ptime")
                    ]

                    # Agregar nuevos filtros de tiempo
                    filtros_actuales.extend(
                        [
                            {
                                "table": source,
                                "field": "ptime",
                                "operator": nocturna["operator1"],
                                "value": nocturna["value1"],
                            },
                            {
                                "table": source,
                                "field": "ptime",
                                "operator": nocturna["operator2"],
                                "value": nocturna["value2"],
                            },
                        ]
                    )

                # Construir consulta
                query_string = self.build_query(
                    filtros_actuales, source, self.bounding_box
                )
                return_params = self.build_return(source)

                api_url = (
                    f"{API_URL}?query={query_string}&"
                    f"return={return_params}&key={API_KEY}"
                )

                # Ejecutar consulta
                results = await self.process_consulta(api_url, source)
                all_results.extend(results)

        # Deduplicar todos los results
        results_unicos = self.deduplicar_results(all_results)

        log_custom(
            section="Fetch Data Inteligente",
            message=f"Total results únicos obtenidos: {len(results_unicos)}",
            level="INFO",
            file=LOG_FILE,
        )

        # Verificar cuáles son nuevos (no están en BD)
        if results_unicos:
            todos_nasa_ids = self.extraer_nasa_ids_de_results(results_unicos)
            nasa_ids_existentes = self.verificar_nasa_ids_en_bd(todos_nasa_ids)
            results_nuevos = self.filtrar_solo_nuevos(
                results_unicos, nasa_ids_existentes
            )

            # Aplicar limit si está definido
            if limit_imagees > 0 and len(results_nuevos) > limit_imagees:
                results_nuevos = results_nuevos[:limit_imagees]
                log_custom(
                    section="Límite Aplicado",
                    message=f"Aplicando limit: {limit_imagees} de {len(results_nuevos)} imágenes nuevas",
                    level="INFO",
                    file=LOG_FILE,
                )

            log_custom(
                section="Verificación BD",
                message=f"Imágenes nuevas: {len(results_nuevos)} de {len(results_unicos)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            return results_unicos, results_nuevos

        return [], []

    def convertir_a_formato_metadata(self, results: List[Dict]) -> List[Dict]:
        """Convertir results de API al formato esperado por extract_metadata_enriquecido"""
        log_custom(
            section="Conversión Formato",
            message=f"Convirtiendo {len(results)} results al formato de metadata",
            level="INFO",
            file=LOG_FILE,
        )

        # Los results ya están en el formato correct (normalizado)
        # Solo necesitamos asegurar que tengan los campos necesarios
        return results


# ============================================================================
#  FUNCIONES DE CONVENIENCIA
# ============================================================================


async def obtener_imagees_nuevas_costa_rica(
    limit: int = 0, mode_nocturno: bool = True, filtros_extra: List[Dict] = None
) -> List[Dict]:
    """
    Función de conveniencia para obtener imágenes nuevas de Costa Rica

    Args:
        limit: Límite de imágenes nuevas (0 = sin limit)
        mode_nocturno: Si usar mode nocturno
        filtros_extra: Filtros adicionales

    Returns:
        Lista de results en formato API listos para extract_metadata_enriquecido
    """
    client = NASAAPIClient(
        bounding_box=DEFAULT_BOUNDING_BOX, mode_nocturno=mode_nocturno
    )

    log_custom(
        section="Get Imágenes Costa Rica",
        message=f"Iniciando búsqueda inteligente - Límite: {limit if limit > 0 else 'Sin limit'}, Nocturno: {mode_nocturno}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        todos_results, solo_nuevos = await client.fetch_data_inteligente(
            filtros_adicionales=filtros_extra, limit_imagees=limit
        )

        if not solo_nuevos:
            log_custom(
                section="Sin Resultados Nuevos",
                message="No se encontraron imágenes nuevas para process",
                level="WARNING",
                file=LOG_FILE,
            )
            return []

        # Convertir al formato esperado
        metadata_formato = client.convertir_a_formato_metadata(solo_nuevos)

        log_custom(
            section="Búsqueda Completada",
            message=f"Búsqueda inteligente completed: {len(metadata_formato)} imágenes nuevas listas para processing",
            level="INFO",
            file=LOG_FILE,
        )

        return metadata_formato

    except Exception as e:
        log_custom(
            section="Error Búsqueda",
            message=f"Error during búsqueda inteligente: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


async def obtener_por_task_scheduled(task_data: Dict) -> List[Dict]:
    """
    Obtener imágenes basado en configuration de task scheduled

    Args:
        task_data: Datos de la task con query, return, filtros, etc.

    Returns:
        Lista de results listos para processing
    """
    log_custom(
        section="Scheduled Task",
        message=f"Ejecutando task scheduled: {task_data.get('id', 'unknown')}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        # Si la task tiene query/return directos (formato API)
        if "query" in task_data and "return" in task_data:
            api_url = f"{API_URL}?query={task_data['query']}&return={task_data['return']}&key={API_KEY}"

            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            raw_data = response.json()

            if not isinstance(raw_data, list):
                return []

            # Normalizar results
            results = []
            for photo in raw_data:
                normalized = {}
                for key, value in photo.items():
                    normalized[key.replace("|", ".")] = value

                # Filtrar alta resolución
                directory = normalized.get("images.directory", "").lower()
                if "large" in directory or "highres" in directory:
                    results.append(normalized)

            # Verificar cuáles son nuevos
            client = NASAAPIClient()
            nasa_ids = client.extraer_nasa_ids_de_results(results)
            existentes = client.verificar_nasa_ids_en_bd(nasa_ids)
            solo_nuevos = client.filtrar_solo_nuevos(results, existentes)

            log_custom(
                section="Scheduled Task",
                message=f"Tarea completed: {len(solo_nuevos)} imágenes nuevas de {len(results)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            return solo_nuevos

        # Si la task tiene configuration avanzada
        else:
            #  USAR CONFIGURACIÓN ESPECÍFICA DE LA TAREA
            bounding_box = task_data.get("boundingBox", DEFAULT_BOUNDING_BOX)
            mode_nocturno = task_data.get("modeNocturno", True)
            filtros = task_data.get("filters", [])
            limit = task_data.get("limit", 0)

            log_custom(
                section="Tarea Avanzada",
                message=f"Ejecutando con configuration personalizada - Filtros: {len(filtros)}, Límite: {limit}",
                level="INFO",
                file=LOG_FILE,
            )

            client = NASAAPIClient(
                bounding_box=bounding_box, mode_nocturno=mode_nocturno
            )

            _, solo_nuevos = await client.fetch_data_inteligente(
                filtros_adicionales=filtros, limit_imagees=limit
            )

            return solo_nuevos

    except Exception as e:
        log_custom(
            section="Error Tarea Programada",
            message=f"Error ejecutando task scheduled: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )


# ============================================================================
#  FUNCIÓN DE PRUEBA
# ============================================================================


async def test_api_client():
    """Función de test para verificar funcionamiento"""
    print(" Probando cliente API NASA...")

    try:
        # Prueba básica con limit pequeño
        results = await obtener_imagees_nuevas_costa_rica(mode_nocturno=True)

        print(f" Prueba exitosa: {len(results)} results obtenidos")

        with open("results.json", "w") as f:
            json.dump(results, f, indent=4)

        if results:
            print(f" Primer result:")
            primer_result = results[0]
            print(f"   - Filename: {primer_result.get('images.filename', 'N/A')}")
            print(f"   - Directory: {primer_result.get('images.directory', 'N/A')}")
            print(f"   - Mission: {primer_result.get('frames.mission', 'N/A')}")
            print(f"   - Date: {primer_result.get('frames.pdate', 'N/A')}")

    except Exception as e:
        print(f" Error in test: {str(e)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_api_client())
