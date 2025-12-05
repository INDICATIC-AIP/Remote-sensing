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

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

# Configuración
API_KEY = os.getenv("NASA_API_KEY", "")
if not API_KEY:
    raise ValueError("NASA_API_KEY no está configurada en .env")
API_URL = "https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl"
LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "metadata.db")

# Configuración por defecto de Costa Rica
DEFAULT_BOUNDING_BOX = {"latMin": 6.1, "latMax": 10.8, "lonMin": -82.9, "lonMax": -77.3}


class NASAAPIClient:
    """Cliente para consultas inteligentes a la API de NASA"""

    def __init__(self, bounding_box: Dict = None, modo_nocturno: bool = True):
        self.bounding_box = bounding_box or DEFAULT_BOUNDING_BOX
        self.modo_nocturno = modo_nocturno
        self.coord_sources = ["frames", "nadir", "mlcoord"]

        # Configuración de campos por tabla (igual que en JS)
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

        # Mapeo de tablas permitidas por fuente
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
        """Obtener consultas para modo nocturno"""
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

    async def procesar_consulta(self, api_url: str, source: str) -> List[Dict]:
        """Procesar una consulta individual a la API"""
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
                    message=f"No se encontraron resultados para fuente: {source}",
                    level="WARNING",
                    file=LOG_FILE,
                )
                return []

            # Procesar resultados y filtrar por alta resolución
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
                message=f"Fuente {source}: {len(processed_results)} resultados de alta resolución de {len(raw_data)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            return processed_results

        except Exception as e:
            log_custom(
                section="Error Consulta API",
                message=f"Error en consulta {source}: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            return []

    def verificar_nasa_ids_en_bd(self, nasa_ids: List[str]) -> set:
        """Verificar qué NASA_IDs ya existen en la base de datos"""
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

    def extraer_nasa_ids_de_resultados(self, results: List[Dict]) -> List[str]:
        """Extraer NASA_IDs de los resultados"""
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
        """Filtrar solo resultados que NO están en BD"""
        nuevos = []
        for result in results:
            filename = result.get("images.filename")
            if filename:
                nasa_id = filename.split(".")[0]
                if nasa_id not in nasa_ids_existentes:
                    nuevos.append(result)
        return nuevos

    def deduplicar_resultados(self, resultados: List[Dict]) -> List[Dict]:
        """Deduplicar resultados por NASA_ID"""
        vistos = set()
        unicos = []
        duplicados = 0

        for resultado in resultados:
            filename = resultado.get("images.filename")
            nasa_id = filename.split(".")[0] if filename else None

            if not nasa_id or nasa_id == "Sin_ID":
                unicos.append(resultado)
                continue

            if nasa_id not in vistos:
                vistos.add(nasa_id)
                unicos.append(resultado)
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
        self, filtros_adicionales: List[Dict] = None, limite_imagenes: int = 0
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Función principal que replica fetchData() de JavaScript
        Retorna: (todos_los_resultados, solo_resultados_nuevos)
        """
        log_custom(
            section="Fetch Data Inteligente",
            message=f"Iniciando consultas inteligentes - Modo nocturno: {self.modo_nocturno}",
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

            if self.modo_nocturno:
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
                resultados = await self.procesar_consulta(api_url, source)
                all_results.extend(resultados)

        # Deduplicar todos los resultados
        resultados_unicos = self.deduplicar_resultados(all_results)

        log_custom(
            section="Fetch Data Inteligente",
            message=f"Total resultados únicos obtenidos: {len(resultados_unicos)}",
            level="INFO",
            file=LOG_FILE,
        )

        # Verificar cuáles son nuevos (no están en BD)
        if resultados_unicos:
            todos_nasa_ids = self.extraer_nasa_ids_de_resultados(resultados_unicos)
            nasa_ids_existentes = self.verificar_nasa_ids_en_bd(todos_nasa_ids)
            resultados_nuevos = self.filtrar_solo_nuevos(
                resultados_unicos, nasa_ids_existentes
            )

            # Aplicar límite si está definido
            if limite_imagenes > 0 and len(resultados_nuevos) > limite_imagenes:
                resultados_nuevos = resultados_nuevos[:limite_imagenes]
                log_custom(
                    section="Límite Aplicado",
                    message=f"Aplicando límite: {limite_imagenes} de {len(resultados_nuevos)} imágenes nuevas",
                    level="INFO",
                    file=LOG_FILE,
                )

            log_custom(
                section="Verificación BD",
                message=f"Imágenes nuevas: {len(resultados_nuevos)} de {len(resultados_unicos)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            return resultados_unicos, resultados_nuevos

        return [], []

    def convertir_a_formato_metadatos(self, results: List[Dict]) -> List[Dict]:
        """Convertir resultados de API al formato esperado por extract_metadatos_enriquecido"""
        log_custom(
            section="Conversión Formato",
            message=f"Convirtiendo {len(results)} resultados al formato de metadatos",
            level="INFO",
            file=LOG_FILE,
        )

        # Los resultados ya están en el formato correcto (normalizado)
        # Solo necesitamos asegurar que tengan los campos necesarios
        return results


# ============================================================================
#  FUNCIONES DE CONVENIENCIA
# ============================================================================


async def obtener_imagenes_nuevas_costa_rica(
    limite: int = 0, modo_nocturno: bool = True, filtros_extra: List[Dict] = None
) -> List[Dict]:
    """
    Función de conveniencia para obtener imágenes nuevas de Costa Rica

    Args:
        limite: Límite de imágenes nuevas (0 = sin límite)
        modo_nocturno: Si usar modo nocturno
        filtros_extra: Filtros adicionales

    Returns:
        Lista de resultados en formato API listos para extract_metadatos_enriquecido
    """
    client = NASAAPIClient(
        bounding_box=DEFAULT_BOUNDING_BOX, modo_nocturno=modo_nocturno
    )

    log_custom(
        section="Obtener Imágenes Costa Rica",
        message=f"Iniciando búsqueda inteligente - Límite: {limite if limite > 0 else 'Sin límite'}, Nocturno: {modo_nocturno}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        todos_resultados, solo_nuevos = await client.fetch_data_inteligente(
            filtros_adicionales=filtros_extra, limite_imagenes=limite
        )

        if not solo_nuevos:
            log_custom(
                section="Sin Resultados Nuevos",
                message="No se encontraron imágenes nuevas para procesar",
                level="WARNING",
                file=LOG_FILE,
            )
            return []

        # Convertir al formato esperado
        metadatos_formato = client.convertir_a_formato_metadatos(solo_nuevos)

        log_custom(
            section="Búsqueda Completada",
            message=f"Búsqueda inteligente completada: {len(metadatos_formato)} imágenes nuevas listas para procesamiento",
            level="INFO",
            file=LOG_FILE,
        )

        return metadatos_formato

    except Exception as e:
        log_custom(
            section="Error Búsqueda",
            message=f"Error durante búsqueda inteligente: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


async def obtener_por_tarea_programada(task_data: Dict) -> List[Dict]:
    """
    Obtener imágenes basado en configuración de tarea programada

    Args:
        task_data: Datos de la tarea con query, return, filtros, etc.

    Returns:
        Lista de resultados listos para procesamiento
    """
    log_custom(
        section="Tarea Programada",
        message=f"Ejecutando tarea programada: {task_data.get('id', 'unknown')}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        # Si la tarea tiene query/return directos (formato API)
        if "query" in task_data and "return" in task_data:
            api_url = f"{API_URL}?query={task_data['query']}&return={task_data['return']}&key={API_KEY}"

            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            raw_data = response.json()

            if not isinstance(raw_data, list):
                return []

            # Normalizar resultados
            resultados = []
            for photo in raw_data:
                normalized = {}
                for key, value in photo.items():
                    normalized[key.replace("|", ".")] = value

                # Filtrar alta resolución
                directory = normalized.get("images.directory", "").lower()
                if "large" in directory or "highres" in directory:
                    resultados.append(normalized)

            # Verificar cuáles son nuevos
            client = NASAAPIClient()
            nasa_ids = client.extraer_nasa_ids_de_resultados(resultados)
            existentes = client.verificar_nasa_ids_en_bd(nasa_ids)
            solo_nuevos = client.filtrar_solo_nuevos(resultados, existentes)

            log_custom(
                section="Tarea Programada",
                message=f"Tarea completada: {len(solo_nuevos)} imágenes nuevas de {len(resultados)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            return solo_nuevos

        # Si la tarea tiene configuración avanzada
        else:
            #  USAR CONFIGURACIÓN ESPECÍFICA DE LA TAREA
            bounding_box = task_data.get("boundingBox", DEFAULT_BOUNDING_BOX)
            modo_nocturno = task_data.get("modoNocturno", True)
            filtros = task_data.get("filters", [])
            limite = task_data.get("limite", 0)

            log_custom(
                section="Tarea Avanzada",
                message=f"Ejecutando con configuración personalizada - Filtros: {len(filtros)}, Límite: {limite}",
                level="INFO",
                file=LOG_FILE,
            )

            client = NASAAPIClient(
                bounding_box=bounding_box, modo_nocturno=modo_nocturno
            )

            _, solo_nuevos = await client.fetch_data_inteligente(
                filtros_adicionales=filtros, limite_imagenes=limite
            )

            return solo_nuevos

    except Exception as e:
        log_custom(
            section="Error Tarea Programada",
            message=f"Error ejecutando tarea programada: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )


# ============================================================================
#  FUNCIÓN DE PRUEBA
# ============================================================================


async def test_api_client():
    """Función de prueba para verificar funcionamiento"""
    print(" Probando cliente API NASA...")

    try:
        # Prueba básica con límite pequeño
        resultados = await obtener_imagenes_nuevas_costa_rica(modo_nocturno=True)

        print(f" Prueba exitosa: {len(resultados)} resultados obtenidos")

        with open("resultados.json", "w") as f:
            json.dump(resultados, f, indent=4)

        if resultados:
            print(f" Primer resultado:")
            primer_resultado = resultados[0]
            print(f"   - Filename: {primer_resultado.get('images.filename', 'N/A')}")
            print(f"   - Directory: {primer_resultado.get('images.directory', 'N/A')}")
            print(f"   - Mission: {primer_resultado.get('frames.mission', 'N/A')}")
            print(f"   - Date: {primer_resultado.get('frames.pdate', 'N/A')}")

    except Exception as e:
        print(f" Error en prueba: {str(e)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_api_client())
