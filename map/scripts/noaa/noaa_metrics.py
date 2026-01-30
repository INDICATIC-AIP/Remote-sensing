"""
NOAA Metrics - Simple performance metrics system
Only main metrics, easy integration
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional


class NOAAMetrics:
    """Sistema simple de métricas para NOAA"""

    def __init__(self, storage_path: str, metadata_path: str):
        self.storage_path = storage_path
        self.metricas_path = os.path.join(
            os.path.dirname(metadata_path), "metricas_rendimiento.json"
        )

        # Variables de tracking
        self.inicio_descarga = None
        self.fin_descarga = None

    def start_descarga(self):
        """Marca inicio de descarga"""
        self.inicio_descarga = time.time()

    def finish_descarga(self):
        """Marca fin de descarga"""
        self.fin_descarga = time.time()

    def calcular_metricas(self, completed_tasks=None, failed_tasks=None):
        """
        Calcula métricas principales del sistema

        Args:
            completed_tasks: Lista de tasks completeds del task_manager
            failed_tasks: Lista de tasks fallidas
        """
        try:
            print(" Calculating metrics de rendimiento...")

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
                    metricas["gee_export_time_min"] = round(
                        sum(tiempos_gee) / len(tiempos_gee), 1
                    )

            # ============================================================================
            #  TIEMPO DE DESCARGA
            # ============================================================================
            if self.inicio_descarga and self.fin_descarga:
                tiempo_descarga = self.fin_descarga - self.inicio_descarga
                metricas["download_time_total_sec"] = round(tiempo_descarga, 1)

            # ============================================================================
            #  ANÁLISIS DE ARCHIVOS
            # ============================================================================
            files_info = self._analizar_files()

            # Tamaños promedio
            if files_info["viirs_count"] > 0:
                metricas["avg_size_viirs_mb"] = round(
                    files_info["viirs_size"] / files_info["viirs_count"], 1
                )

            if files_info["dmsp_count"] > 0:
                metricas["avg_size_dmsp_mb"] = round(
                    files_info["dmsp_size"] / files_info["dmsp_count"], 1
                )

            # Volumen total
            total_gb = (files_info["viirs_size"] + files_info["dmsp_size"]) / 1024
            metricas["total_volume_gb"] = round(total_gb, 2)
            metricas["total_images"] = (
                files_info["viirs_count"] + files_info["dmsp_count"]
            )

            # ============================================================================
            #  VELOCIDAD DE TRANSFERENCIA
            # ============================================================================
            if (
                self.inicio_descarga
                and self.fin_descarga
                and metricas.get("total_volume_gb", 0) > 0
            ):
                tiempo_desc = self.fin_descarga - self.inicio_descarga
                size_mb = metricas["total_volume_gb"] * 1024
                velocidad = size_mb / tiempo_desc
                metricas["transfer_speed_mb_s"] = round(velocidad, 1)

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
            self._mostrar_table_metricas(metricas)

            return metricas

        except Exception as e:
            print(f" Error calculando métricas: {e}")
            return None

    def _analizar_files(self):
        """Analiza files físicos"""
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
            print(f" Error analizando files: {e}")

        return info

    def _guardar_metricas(self, metricas):
        """Guarda métricas en file JSON"""
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
            print(f" Error saving métricas: {e}")

    def _mostrar_table_metricas(self, metricas):
        """Muestra table de métricas principales"""
        print("\n MÉTRICAS DE RENDIMIENTO NOAA")
        print("=" * 60)

        table = [
            (
                "Tiempo promedio exportación GEE",
                f"{metricas.get('gee_export_time_min', 'N/A')} min/image",
            ),
            (
                "Tiempo total descarga Google Drive",
                f"{metricas.get('download_time_total_sec', 'N/A')} segundos",
            ),
            (
                "Velocidad de transferencia",
                f"{metricas.get('transfer_speed_mb_s', 'N/A')} MB/s",
            ),
            (
                "Tamaño promedio VIIRS",
                f"{metricas.get('avg_size_viirs_mb', 'N/A')} MB",
            ),
            (
                "Tamaño promedio DMSP-OLS",
                f"{metricas.get('avg_size_dmsp_mb', 'N/A')} MB",
            ),
            (
                "Volumen total procesado",
                f"{metricas.get('total_volume_gb', 'N/A')} GB ({metricas.get('total_images', 'N/A')} imágenes)",
            ),
            (
                "Tiempo total del proceso",
                f"{metricas.get('tiempo_total_proceso_min', 'N/A')} minutos",
            ),
            ("Tasa de success exportación", f"{metricas.get('tasa_exito_pct', 'N/A')}%"),
        ]

        for metrica, valor in table:
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
                date = sesion.get("timestamp", "")[:19].replace("T", " ")
                print(f" {i}. {date}")
                print(f"   GEE: {sesion.get('gee_export_time_min', 'N/A')} min")
                print(
                    f"   Velocidad: {sesion.get('transfer_speed_mb_s', 'N/A')} MB/s"
                )
                print(f"   Total: {sesion.get('total_images', 'N/A')} imágenes")
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
    self.metrics = NOAAMetrics(self.storage_path, self.metadata_path)

    # 2. En export_imagees_nuevas(), antes de download_from_drive():
    self.metrics.start_descarga()

    # 3. En export_imagees_nuevas(), después de download_from_drive():
    self.metrics.finish_descarga()

    # 4. En export_imagees_nuevas(), al final antes de clear_current_execution():
    self.metrics.calcular_metricas(completed_tasks, failed_tasks)

    # 5. Para ver historial cuando quieras:
    self.metrics.mostrar_historico()
    """
    pass


if __name__ == "__main__":
    # Ejemplo de uso independiente
    metrics = NOAAMetrics("/path/storage", "/path/metadata.json")
    metrics.calcular_metricas()
    metrics.mostrar_historico()
