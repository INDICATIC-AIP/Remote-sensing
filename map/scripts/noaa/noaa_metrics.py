"""
NOAA Metrics - Sistema simple de métricas de rendimiento
Solo las métricas principales, fácil integración
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional


class NOAAMetrics:
    """Sistema simple de métricas para NOAA"""

    def __init__(self, storage_path: str, metadatos_path: str):
        self.storage_path = storage_path
        self.metricas_path = os.path.join(
            os.path.dirname(metadatos_path), "metricas_rendimiento.json"
        )

        # Variables de tracking
        self.inicio_descarga = None
        self.fin_descarga = None

    def iniciar_descarga(self):
        """Marca inicio de descarga"""
        self.inicio_descarga = time.time()

    def finalizar_descarga(self):
        """Marca fin de descarga"""
        self.fin_descarga = time.time()

    def calcular_metricas(self, completed_tasks=None, failed_tasks=None):
        """
        Calcula métricas principales del sistema

        Args:
            completed_tasks: Lista de tareas completadas del task_manager
            failed_tasks: Lista de tareas fallidas
        """
        try:
            print(" Calculando métricas de rendimiento...")

            metricas = {
                "timestamp": datetime.now().isoformat(),
                "storage_path": self.storage_path,
            }

            # ============================================================================
            #  TIEMPO PROMEDIO DE EXPORTACIÓN EN GEE
            # ============================================================================
            if completed_tasks:
                tiempos_gee = []
                for task in completed_tasks:
                    start = task.get("start_time", 0)
                    end = task.get("completion_time", 0)
                    if start and end:
                        tiempo_min = (end - start) / 60
                        tiempos_gee.append(tiempo_min)

                if tiempos_gee:
                    metricas["tiempo_exportacion_gee_min"] = round(
                        sum(tiempos_gee) / len(tiempos_gee), 1
                    )

            # ============================================================================
            #  TIEMPO DE DESCARGA
            # ============================================================================
            if self.inicio_descarga and self.fin_descarga:
                tiempo_descarga = self.fin_descarga - self.inicio_descarga
                metricas["tiempo_descarga_total_seg"] = round(tiempo_descarga, 1)

            # ============================================================================
            #  ANÁLISIS DE ARCHIVOS
            # ============================================================================
            archivos_info = self._analizar_archivos()

            # Tamaños promedio
            if archivos_info["viirs_count"] > 0:
                metricas["tamano_promedio_viirs_mb"] = round(
                    archivos_info["viirs_size"] / archivos_info["viirs_count"], 1
                )

            if archivos_info["dmsp_count"] > 0:
                metricas["tamano_promedio_dmsp_mb"] = round(
                    archivos_info["dmsp_size"] / archivos_info["dmsp_count"], 1
                )

            # Volumen total
            total_gb = (archivos_info["viirs_size"] + archivos_info["dmsp_size"]) / 1024
            metricas["volumen_total_gb"] = round(total_gb, 2)
            metricas["total_imagenes"] = (
                archivos_info["viirs_count"] + archivos_info["dmsp_count"]
            )

            # ============================================================================
            #  VELOCIDAD DE TRANSFERENCIA
            # ============================================================================
            if (
                self.inicio_descarga
                and self.fin_descarga
                and metricas.get("volumen_total_gb", 0) > 0
            ):
                tiempo_desc = self.fin_descarga - self.inicio_descarga
                tamano_mb = metricas["volumen_total_gb"] * 1024
                velocidad = tamano_mb / tiempo_desc
                metricas["velocidad_transferencia_mb_s"] = round(velocidad, 1)

            # ============================================================================
            #  TASA DE ÉXITO
            # ============================================================================
            if completed_tasks is not None and failed_tasks is not None:
                total = len(completed_tasks) + len(failed_tasks)
                if total > 0:
                    tasa_exito = (len(completed_tasks) / total) * 100
                    metricas["tasa_exito_pct"] = round(tasa_exito, 1)

            # ============================================================================
            #  TIEMPO TOTAL DEL PROCESO
            # ============================================================================
            if hasattr(self, "inicio_proceso") and self.inicio_proceso:
                tiempo_total_min = (time.time() - self.inicio_proceso) / 60
                metricas["tiempo_total_proceso_min"] = round(tiempo_total_min, 1)

            # ============================================================================
            #  GUARDAR MÉTRICAS
            # ============================================================================
            self._guardar_metricas(metricas)

            # ============================================================================
            #  MOSTRAR TABLA
            # ============================================================================
            self._mostrar_tabla_metricas(metricas)

            return metricas

        except Exception as e:
            print(f" Error calculando métricas: {e}")
            return None

    def _analizar_archivos(self):
        """Analiza archivos físicos"""
        info = {
            "viirs_count": 0,
            "viirs_size": 0,  # MB
            "dmsp_count": 0,
            "dmsp_size": 0,  # MB
        }

        try:
            # DMSP-OLS
            dmsp_path = os.path.join(self.storage_path, "DMSP-OLS")
            if os.path.exists(dmsp_path):
                for file in os.listdir(dmsp_path):
                    if file.endswith(".tif"):
                        file_path = os.path.join(dmsp_path, file)
                        try:
                            size_mb = os.path.getsize(file_path) / (1024 * 1024)
                            info["dmsp_count"] += 1
                            info["dmsp_size"] += size_mb
                        except:
                            pass

            # VIIRS
            viirs_path = os.path.join(self.storage_path, "VIIRS")
            if os.path.exists(viirs_path):
                for year_folder in os.listdir(viirs_path):
                    year_path = os.path.join(viirs_path, year_folder)
                    if os.path.isdir(year_path):
                        for file in os.listdir(year_path):
                            if file.endswith(".tif"):
                                file_path = os.path.join(year_path, file)
                                try:
                                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                    info["viirs_count"] += 1
                                    info["viirs_size"] += size_mb
                                except:
                                    pass
        except Exception as e:
            print(f" Error analizando archivos: {e}")

        return info

    def _guardar_metricas(self, metricas):
        """Guarda métricas en archivo JSON"""
        try:
            # Cargar historial existente
            if os.path.exists(self.metricas_path):
                with open(self.metricas_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"sesiones": []}

            # Agregar nueva sesión
            data["sesiones"].append(metricas)

            # Mantener solo últimas 20 sesiones
            if len(data["sesiones"]) > 20:
                data["sesiones"] = data["sesiones"][-20:]

            # Guardar
            os.makedirs(os.path.dirname(self.metricas_path), exist_ok=True)
            with open(self.metricas_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f" Métricas guardadas en: {self.metricas_path}")

        except Exception as e:
            print(f" Error guardando métricas: {e}")

    def _mostrar_tabla_metricas(self, metricas):
        """Muestra tabla de métricas principales"""
        print("\n MÉTRICAS DE RENDIMIENTO NOAA")
        print("=" * 60)

        tabla = [
            (
                "Tiempo promedio exportación GEE",
                f"{metricas.get('tiempo_exportacion_gee_min', 'N/A')} min/imagen",
            ),
            (
                "Tiempo total descarga Google Drive",
                f"{metricas.get('tiempo_descarga_total_seg', 'N/A')} segundos",
            ),
            (
                "Velocidad de transferencia",
                f"{metricas.get('velocidad_transferencia_mb_s', 'N/A')} MB/s",
            ),
            (
                "Tamaño promedio VIIRS",
                f"{metricas.get('tamano_promedio_viirs_mb', 'N/A')} MB",
            ),
            (
                "Tamaño promedio DMSP-OLS",
                f"{metricas.get('tamano_promedio_dmsp_mb', 'N/A')} MB",
            ),
            (
                "Volumen total procesado",
                f"{metricas.get('volumen_total_gb', 'N/A')} GB ({metricas.get('total_imagenes', 'N/A')} imágenes)",
            ),
            (
                "Tiempo total del proceso",
                f"{metricas.get('tiempo_total_proceso_min', 'N/A')} minutos",
            ),
            ("Tasa de éxito exportación", f"{metricas.get('tasa_exito_pct', 'N/A')}%"),
        ]

        for metrica, valor in tabla:
            print(f" {metrica:<35} {valor}")

        print("=" * 60)

    def mostrar_historico(self, ultimas=5):
        """Muestra historial de métricas"""
        try:
            if not os.path.exists(self.metricas_path):
                print(" No hay métricas históricas")
                return

            with open(self.metricas_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            sesiones = data.get("sesiones", [])[-ultimas:]

            print(f"\n HISTORIAL MÉTRICAS (Últimas {len(sesiones)})")
            print("=" * 50)

            for i, sesion in enumerate(sesiones, 1):
                fecha = sesion.get("timestamp", "")[:19].replace("T", " ")
                print(f" {i}. {fecha}")
                print(f"   GEE: {sesion.get('tiempo_exportacion_gee_min', 'N/A')} min")
                print(
                    f"   Velocidad: {sesion.get('velocidad_transferencia_mb_s', 'N/A')} MB/s"
                )
                print(f"   Total: {sesion.get('total_imagenes', 'N/A')} imágenes")
                print(f"   Éxito: {sesion.get('tasa_exito_pct', 'N/A')}%")
                print("-" * 30)

        except Exception as e:
            print(f" Error mostrando historial: {e}")


# ============================================================================
#  INTEGRACIÓN FÁCIL CON NOAA PROCESSOR
# ============================================================================


def integrar_metricas_en_processor():
    """
    Código de ejemplo para integrar en NOAAProcessor

    # 1. En __init__ del NOAAProcessor:
    from noaa_metrics import NOAAMetrics
    self.metrics = NOAAMetrics(self.storage_path, self.metadatos_path)

    # 2. En export_imagenes_nuevas(), antes de descargar_desde_drive():
    self.metrics.iniciar_descarga()

    # 3. En export_imagenes_nuevas(), después de descargar_desde_drive():
    self.metrics.finalizar_descarga()

    # 4. En export_imagenes_nuevas(), al final antes de limpiar_ejecucion_actual():
    self.metrics.calcular_metricas(completed_tasks, failed_tasks)

    # 5. Para ver historial cuando quieras:
    self.metrics.mostrar_historico()
    """
    pass


if __name__ == "__main__":
    # Ejemplo de uso independiente
    metrics = NOAAMetrics("/ruta/storage", "/ruta/metadatos.json")
    metrics.calcular_metricas()
    metrics.mostrar_historico()
