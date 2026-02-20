"""
 CLIENTE API PARA TAREAS PROGRAMADAS
Maneja tasks con formato query/return directo desde UI
"""

import os
import sys
import json
import requests
import sqlite3
from typing import List, Dict, Optional

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
DATABASE_PATH = os.path.join(PROJECT_ROOT, "map", "db", "metadata.db")

#  LÍMITE CONFIGURABLE DESDE ENTORNO (0 = sin límite)
try:
    LIMITE_IMAGENES = int(os.getenv("ISS_LIMIT", "0"))
except ValueError:
    LIMITE_IMAGENES = 0

    LAST_TASK_STATS = {
        "task_id": "unknown",
        "total_results": 0,
        "unique_results": 0,
        "existing_in_db": 0,
        "new_results": 0,
    }


class TaskAPIClient:
    """Cliente para process tasks scheduleds con formato query/return"""

    def __init__(self):
        self.api_key = API_KEY
        self.api_url = API_URL

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

    def fetch_from_api(self, query: str, return_fields: str) -> List[Dict]:
        """Consultar API de NASA con query y return directos"""
        log_custom(
            section="Task API Client",
            message=f"Consultando API con query: {query[:50]}...",
            level="INFO",
            file=LOG_FILE,
        )

        try:
            params = {"query": query, "return": return_fields, "key": self.api_key}

            response = requests.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()

            raw_data = response.json()

            if not isinstance(raw_data, list):
                log_custom(
                    section="Task API Client",
                    message="API no devolvió una lista válida",
                    level="WARNING",
                    file=LOG_FILE,
                )
                return []

            log_custom(
                section="Task API Client",
                message=f"API devolvió {len(raw_data)} results totales",
                level="INFO",
                file=LOG_FILE,
            )

            return raw_data

        except Exception as e:
            log_custom(
                section="Task API Client",
                message=f"Error consultando API: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            return []

    def normalize_results(self, raw_data: List[Dict]) -> List[Dict]:
        """Normalizar results: reemplazar | por . en las keys"""
        normalized = []

        for photo in raw_data:
            # Convertir keys de formato pipe a punto
            norm = {}
            for key, value in photo.items():
                new_key = key.replace("|", ".")
                norm[new_key] = value

            #  FILTRAR SOLO ALTA RESOLUCIÓN
            directory = norm.get("images.directory", "").lower()

            is_high_res = (
                "large" in directory
                or "highres" in directory
                or "/highres/" in directory
                or directory.endswith("highres")
                or "/large/" in directory
            )

            if is_high_res:
                normalized.append(norm)

        log_custom(
            section="Task API Client",
            message=f"Filtrados {len(normalized)} results de alta resolución de {len(raw_data)} totales",
            level="INFO",
            file=LOG_FILE,
        )

        return normalized

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

    def verificar_nasa_ids_en_bd(self, nasa_ids: List[str]) -> set:
        """Verify qué NASA_IDs ya existen en la base de datos"""
        if not nasa_ids:
            return set()

        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()

                #  USAR TABLA Image CON nasa_id (minúscula)
                placeholders = ",".join("?" * len(nasa_ids))
                query = f"SELECT nasa_id FROM Image WHERE nasa_id IN ({placeholders})"
                cursor.execute(query, nasa_ids)
                existentes = {row[0] for row in cursor.fetchall()}

                log_custom(
                    section="Task API Client",
                    message=f"Verificación BD (Image): {len(existentes)} ya existen de {len(nasa_ids)} consultados",
                    level="INFO",
                    file=LOG_FILE,
                )

                return existentes

        except Exception as e:
            log_custom(
                section="Task API Client",
                message=f"Error verificando NASA_IDs en BD: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            return set()

    def deduplicar_results_multi_consulta(self, results: List[Dict]) -> List[Dict]:
        """Deduplicar results de múltiples consultas por NASA_ID"""
        vistos = set()
        unicos = []
        duplicados = 0
        por_fuente = {}

        for result in results:
            filename = result.get("images.filename")
            nasa_id = filename.split(".")[0] if filename else None
            source = result.get("coordSource", "unknown")

            # Contar por fuente para estadísticas
            if source not in por_fuente:
                por_fuente[source] = 0
            por_fuente[source] += 1

            if not nasa_id or nasa_id == "Sin_ID":
                unicos.append(result)
                continue

            if nasa_id not in vistos:
                vistos.add(nasa_id)
                unicos.append(result)
            else:
                duplicados += 1

        # Log detallado
        log_custom(
            section="Deduplicación Multi-Consulta",
            message=f"Resultados únicos: {len(unicos)}, Duplicados eliminados: {duplicados}",
            level="INFO",
            file=LOG_FILE,
        )

        log_custom(
            section="Estadísticas por Fuente",
            message=f"Totales por fuente: {por_fuente}",
            level="INFO",
            file=LOG_FILE,
        )

        return unicos

    async def process_task_scheduled(self, task: Dict) -> List[Dict]:
        """
        Procesar task scheduled con formato:
        {
          "id": "task_mbsb3or1_u3p",
          "consultas": [
            {
              "source": "frames",
              "query": "frames|ptime|ge|003000|frames|ptime|le|045959|frames|lat|ge|6.1...",
              "return": "frames|mission|frames|roll|frames|frame|frames|pdate|frames|ptime...",
              "modeNocturno": "003000-045959"
            },
            {
              "source": "frames",
              "query": "frames|ptime|ge|050000|frames|ptime|le|103000|frames|lat|ge|6.1...",
              "return": "frames|mission|frames|roll|frames|frame|frames|pdate|frames|ptime...",
              "modeNocturno": "050000-103000"
            }
          ],
          "time": "14:04",
          "frecuencia": "ONCE"
        }
        """
        global LAST_TASK_STATS
        task_id = task.get("id", "unknown")

        log_custom(
            section="Task API Client",
            message=f"Processing scheduled task: {task_id}",
            level="INFO",
            file=LOG_FILE,
        )

        try:
            # 1. Validar que la task tenga consultas
            consultas = task.get("consultas", [])

            if not consultas:
                #  FALLBACK: Mantener compatibilidad con formato antiguo
                if task.get("query") and task.get("return"):
                    log_custom(
                        section="Task API Client",
                        message=f"Using legacy task format (direct query/return) for task {task_id}",
                        level="WARNING",
                        file=LOG_FILE,
                    )

                    raw_data = self.fetch_from_api(task["query"], task["return"])
                    if not raw_data:
                        return []

                    results = self.normalize_results(raw_data)
                    todos_nasa_ids = self.extraer_nasa_ids_de_results(results)
                    nasa_ids_existentes = self.verificar_nasa_ids_en_bd(todos_nasa_ids)
                    results_nuevos = self.filtrar_solo_nuevos(
                        results, nasa_ids_existentes
                    )

                    if LIMITE_IMAGENES > 0 and len(results_nuevos) > LIMITE_IMAGENES:
                        results_nuevos = results_nuevos[:LIMITE_IMAGENES]

                    LAST_TASK_STATS = {
                        "task_id": task_id,
                        "total_results": len(raw_data),
                        "unique_results": len(results),
                        "existing_in_db": len(nasa_ids_existentes),
                        "new_results": len(results_nuevos),
                    }

                    return results_nuevos
                else:
                    raise ValueError(
                        "Task must include 'consultas' array or legacy 'query/return' fields"
                    )

            # 2. Procesar todas las consultas
            todos_los_results = []

            log_custom(
                section="Task API Client",
                message=f"Procesando {len(consultas)} consultas para task {task_id}",
                level="INFO",
                file=LOG_FILE,
            )

            for i, consulta in enumerate(consultas):
                source = consulta.get("source", "unknown")
                query = consulta.get("query")
                return_fields = consulta.get("return")
                mode_nocturno = consulta.get("modeNocturno", "normal")

                if not query or not return_fields:
                    log_custom(
                        section="Task API Client",
                        message=f"Consulta {i + 1} incompleta para fuente {source} - saltando",
                        level="WARNING",
                        file=LOG_FILE,
                    )
                    continue

                log_custom(
                    section="Task API Client",
                    message=f"Ejecutando consulta {i + 1}/{len(consultas)}: {source} (mode: {mode_nocturno})",
                    level="INFO",
                    file=LOG_FILE,
                )

                # 3. Hacer consulta a la API
                raw_data = self.fetch_from_api(query, return_fields)

                if raw_data:
                    # 4. Normalizar y process results
                    results = self.normalize_results(raw_data)

                    # 5. Agregar information de la fuente
                    # for result in results:
                    #     result["coordSource"] = source
                    #     result["modeConsulta"] = mode_nocturno

                    todos_los_results.extend(results)

                    log_custom(
                        section="Task API Client",
                        message=f"Consulta {i + 1} completed: {len(results)} results de alta resolución de {len(raw_data)} totales (fuente: {source})",
                        level="INFO",
                        file=LOG_FILE,
                    )
                else:
                    log_custom(
                        section="Task API Client",
                        message=f"Consulta {i + 1} sin results para fuente {source}",
                        level="WARNING",
                        file=LOG_FILE,
                    )

            if not todos_los_results:
                log_custom(
                    section="Task API Client",
                    message="No se obtuvieron results de ninguna consulta",
                    level="WARNING",
                    file=LOG_FILE,
                )
                LAST_TASK_STATS = {
                    "task_id": task_id,
                    "total_results": 0,
                    "unique_results": 0,
                    "existing_in_db": 0,
                    "new_results": 0,
                }
                return []

            # 6. Deduplicar results combinados
            log_custom(
                section="Task API Client",
                message=f"Deduplicando {len(todos_los_results)} results combinados",
                level="INFO",
                file=LOG_FILE,
            )

            results_unicos = self.deduplicar_results_multi_consulta(todos_los_results)

            # 7. Verificar cuáles ya existen en BD
            todos_nasa_ids = self.extraer_nasa_ids_de_results(results_unicos)
            nasa_ids_existentes = self.verificar_nasa_ids_en_bd(todos_nasa_ids)

            # 8. Filtrar solo los NUEVOS
            results_nuevos = self.filtrar_solo_nuevos(
                results_unicos, nasa_ids_existentes
            )

            if not results_nuevos:
                log_custom(
                    section="Task API Client",
                    message="Todas las imágenes ya están en la base de datos",
                    level="INFO",
                    file=LOG_FILE,
                )
                LAST_TASK_STATS = {
                    "task_id": task_id,
                    "total_results": len(todos_los_results),
                    "unique_results": len(results_unicos),
                    "existing_in_db": len(nasa_ids_existentes),
                    "new_results": 0,
                }
                return []

            # 9.  APLICAR LÍMITE
            if LIMITE_IMAGENES > 0 and len(results_nuevos) > LIMITE_IMAGENES:
                results_nuevos = results_nuevos[:LIMITE_IMAGENES]
                log_custom(
                    section="Task API Client",
                    message=f"Aplicando limit: {LIMITE_IMAGENES} de {len(results_nuevos)} imágenes nuevas",
                    level="INFO",
                    file=LOG_FILE,
                )

            log_custom(
                section="Task API Client",
                message=f"Tarea {task_id} procesada: {len(results_nuevos)} imágenes nuevas de {len(results_unicos)} únicas de {len(todos_los_results)} totales",
                level="INFO",
                file=LOG_FILE,
            )

            LAST_TASK_STATS = {
                "task_id": task_id,
                "total_results": len(todos_los_results),
                "unique_results": len(results_unicos),
                "existing_in_db": len(nasa_ids_existentes),
                "new_results": len(results_nuevos),
            }

            return results_nuevos

        except Exception as e:
            log_custom(
                section="Task API Client",
                message=f"Error processing task {task_id}: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
            raise


# ============================================================================
#  FUNCIÓN DE CONVENIENCIA
# ============================================================================


async def process_task_scheduled(task: Dict) -> List[Dict]:
    """
    Función de conveniencia para process una task scheduled

    Args:
        task: Diccionario con id, query, return, time, frecuencia

    Returns:
        Lista de results nuevos en formato API normalizado
    """
    client = TaskAPIClient()
    return await client.process_task_scheduled(task)


def get_last_task_stats() -> Dict:
    return LAST_TASK_STATS.copy()


# ============================================================================
#  FUNCIÓN DE PRUEBA
# ============================================================================


async def test_task_api_client():
    """Función de test para verificar funcionamiento"""
    print(" Probando Task API Client...")

    # Tarea de ejemplo con tu formato
    task_ejemplo = {
        "id": "test_task",
        "query": "frames|lat|ge|6.1|frames|lat|le|10.8|frames|lon|ge|-82.9|frames|lon|le|-77.3",
        "return": "images|directory|images|filename|images|width|images|height|frames|mission|frames|pdate",
        "time": "13:53",
        "frecuencia": "ONCE",
    }

    try:
        results = await process_task_scheduled(task_ejemplo)

        print(f" Prueba exitosa: {len(results)} results nuevos obtenidos")

        if results:
            print(f" Primer result:")
            primer_result = results[0]
            print(f"   - Filename: {primer_result.get('images.filename', 'N/A')}")
            print(f"   - Directory: {primer_result.get('images.directory', 'N/A')}")
            print(f"   - Mission: {primer_result.get('frames.mission', 'N/A')}")

            # Guardar results para debug
            with open("test_task_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            print(f" Resultados guardados en: test_task_results.json")

    except Exception as e:
        print(f" Error in test: {str(e)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_task_api_client())
