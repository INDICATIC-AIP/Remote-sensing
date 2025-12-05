"""
 SISTEMA DE ESTADO GRANULAR POR FASES
Maneja el estado individual de cada imagen a través de las 3 fases
"""

import os
import sys
import time
from typing import List, Dict, Set
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom

#  LOG COHERENTE
LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")


class EstadoManager:
    """Gestor de estados por imagen y fase"""

    ESTADOS = {
        "PENDIENTE": "PENDIENTE",
        "DESCARGADO": "DESCARGADO",
        "ORGANIZADO": "ORGANIZADO",
        "COMPLETADO": "COMPLETADO",
        "ERROR_DESCARGA": "ERROR_DESCARGA",
        "ERROR_ORGANIZACION": "ERROR_ORGANIZACION",
        "ERROR_BD": "ERROR_BD",
    }

    def __init__(self, archivo_estado="estado_imagenes.txt"):
        self.archivo_estado = archivo_estado
        self.estados = {}  # nasa_id -> estado

    def crear_archivo_inicial(self, metadatos_list: List[Dict]):
        """ CREAR ARCHIVO DE ESTADO INICIAL"""
        log_custom(
            section="Estado Manager",
            message=f"Creando archivo de estado inicial con {len(metadatos_list)} imágenes",
            level="INFO",
            file=LOG_FILE,
        )

        with open(self.archivo_estado, "w", encoding="utf-8") as f:
            f.write(
                f"# Estado de descarga - Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"# Total imágenes: {len(metadatos_list)}\n")
            f.write("# Formato: NASA_ID,ESTADO\n")
            f.write("---\n")

            for metadata in metadatos_list:
                nasa_id = metadata.get("NASA_ID", "SIN_ID")
                if nasa_id != "SIN_ID":
                    f.write(f"{nasa_id},{self.ESTADOS['PENDIENTE']}\n")
                    self.estados[nasa_id] = self.ESTADOS["PENDIENTE"]

        log_custom(
            section="Estado Manager",
            message=f"Archivo de estado creado: {self.archivo_estado}",
            level="INFO",
            file=LOG_FILE,
        )

    def cargar_estado_existente(self) -> bool:
        """ CARGAR ESTADO DESDE ARCHIVO EXISTENTE"""
        if not os.path.exists(self.archivo_estado):
            return False

        log_custom(
            section="Estado Manager",
            message=f"Cargando estado existente desde: {self.archivo_estado}",
            level="INFO",
            file=LOG_FILE,
        )

        self.estados = {}
        with open(self.archivo_estado, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or line == "---" or not line:
                    continue

                try:
                    nasa_id, estado = line.split(",", 1)
                    self.estados[nasa_id] = estado
                except ValueError:
                    continue

        log_custom(
            section="Estado Manager",
            message=f"Estado cargado: {len(self.estados)} imágenes encontradas",
            level="INFO",
            file=LOG_FILE,
        )
        return True

    def actualizar_estado(self, nasa_id: str, nuevo_estado: str):
        """ ACTUALIZAR ESTADO DE UNA IMAGEN"""
        if nuevo_estado not in self.ESTADOS.values():
            log_custom(
                section="Estado Manager",
                message=f"Estado inválido: {nuevo_estado} para {nasa_id}",
                level="ERROR",
                file=LOG_FILE,
            )
            return

        self.estados[nasa_id] = nuevo_estado
        self._escribir_archivo()

        # Log solo para estados importantes
        if nuevo_estado in [
            "COMPLETADO",
            "ERROR_DESCARGA",
            "ERROR_ORGANIZACION",
            "ERROR_BD",
        ]:
            log_custom(
                section="Estado Manager",
                message=f"{nasa_id}: {nuevo_estado}",
                level="INFO" if nuevo_estado == "COMPLETADO" else "WARNING",
                file=LOG_FILE,
            )

    def _escribir_archivo(self):
        """Escribir estados actuales al archivo"""
        with open(self.archivo_estado, "w", encoding="utf-8") as f:
            f.write(
                f"# Estado de descarga - Actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"# Total imágenes: {len(self.estados)}\n")
            f.write("# Formato: NASA_ID,ESTADO\n")
            f.write("---\n")

            for nasa_id, estado in self.estados.items():
                f.write(f"{nasa_id},{estado}\n")

    def obtener_por_estado(self, estados_deseados: List[str]) -> Set[str]:
        """ OBTENER NASA_IDs POR ESTADO(S)"""
        return {
            nasa_id
            for nasa_id, estado in self.estados.items()
            if estado in estados_deseados
        }

    def obtener_pendientes_descarga(self) -> Set[str]:
        """Imágenes que necesitan descarga"""
        return self.obtener_por_estado(["PENDIENTE", "ERROR_DESCARGA"])

    def obtener_pendientes_organizacion(self) -> Set[str]:
        """Imágenes que necesitan organización"""
        return self.obtener_por_estado(["DESCARGADO", "ERROR_ORGANIZACION"])

    def obtener_pendientes_bd(self) -> Set[str]:
        """Imágenes que necesitan guardado en BD"""
        return self.obtener_por_estado(["ORGANIZADO", "ERROR_BD"])

    def obtener_estadisticas(self) -> Dict:
        """ ESTADÍSTICAS DEL PROCESO"""
        stats = {estado: 0 for estado in self.ESTADOS.values()}
        for estado in self.estados.values():
            stats[estado] += 1

        stats["TOTAL"] = len(self.estados)
        stats["COMPLETADAS"] = stats["COMPLETADO"]
        stats["CON_ERRORES"] = (
            stats["ERROR_DESCARGA"] + stats["ERROR_ORGANIZACION"] + stats["ERROR_BD"]
        )
        stats["PENDIENTES"] = (
            stats["TOTAL"] - stats["COMPLETADAS"] - stats["CON_ERRORES"]
        )

        return stats

    def limpiar_archivos_con_errores(self, base_path: str):
        """ LIMPIAR ARCHIVOS DE IMÁGENES CON ERRORES"""
        errores = self.obtener_por_estado(
            ["ERROR_DESCARGA", "ERROR_ORGANIZACION", "ERROR_BD"]
        )

        if not errores:
            return

        log_custom(
            section="Limpieza Estado",
            message=f"Limpiando {len(errores)} archivos con errores del NAS",
            level="INFO",
            file=LOG_FILE,
        )

        archivos_borrados = 0
        for nasa_id in errores:
            # Buscar archivo en estructura organizada
            for year in range(2020, 2030):  # Rango amplio
                for root, dirs, files in os.walk(os.path.join(base_path, str(year))):
                    for file in files:
                        if file.startswith(nasa_id):
                            file_path = os.path.join(root, file)
                            try:
                                os.remove(file_path)
                                archivos_borrados += 1
                                log_custom(
                                    section="Limpieza Estado",
                                    message=f"Borrado: {file_path}",
                                    level="INFO",
                                    file=LOG_FILE,
                                )
                            except Exception as e:
                                log_custom(
                                    section="Limpieza Estado",
                                    message=f"Error borrando {file_path}: {str(e)}",
                                    level="ERROR",
                                    file=LOG_FILE,
                                )

        log_custom(
            section="Limpieza Estado",
            message=f"Limpieza completada: {archivos_borrados} archivos borrados",
            level="INFO",
            file=LOG_FILE,
        )

    def limpiar_bd_con_errores(self, database_path: str):
        """ LIMPIAR REGISTROS DE BD CON ERRORES"""
        errores = self.obtener_por_estado(
            ["ERROR_DESCARGA", "ERROR_ORGANIZACION", "ERROR_BD"]
        )

        if not errores:
            return

        log_custom(
            section="Limpieza BD",
            message=f"Limpiando {len(errores)} registros con errores de la BD",
            level="INFO",
            file=LOG_FILE,
        )

        sys.path.append(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        )
        from db.Crud import MetadataCRUD

        crud = MetadataCRUD()
        registros_borrados = 0

        try:
            for nasa_id in errores:
                try:
                    deleted = crud.delete_by_nasa_id(nasa_id)
                    if deleted:
                        registros_borrados += 1
                except Exception as e:
                    log_custom(
                        section="Limpieza BD",
                        message=f"Error borrando {nasa_id} de BD: {str(e)}",
                        level="ERROR",
                        file=LOG_FILE,
                    )

            crud.session.commit()

        except Exception as e:
            crud.session.rollback()
            log_custom(
                section="Limpieza BD",
                message=f"Error general en limpieza BD: {str(e)}",
                level="ERROR",
                file=LOG_FILE,
            )
        finally:
            crud.session.close()

        log_custom(
            section="Limpieza BD",
            message=f"Limpieza BD completada: {registros_borrados} registros borrados",
            level="INFO",
            file=LOG_FILE,
        )

    def resetear_errores_a_pendiente(self):
        """ RESETEAR ERRORES PARA REINTENTO"""
        errores_actuales = self.obtener_por_estado(
            ["ERROR_DESCARGA", "ERROR_ORGANIZACION", "ERROR_BD"]
        )

        log_custom(
            section="Estado Manager",
            message=f"Reseteando {len(errores_actuales)} imágenes con errores para reintento",
            level="INFO",
            file=LOG_FILE,
        )

        for nasa_id in errores_actuales:
            estado_actual = self.estados[nasa_id]

            # Resetear según el tipo de error
            if estado_actual == "ERROR_DESCARGA":
                self.estados[nasa_id] = "PENDIENTE"
            elif estado_actual == "ERROR_ORGANIZACION":
                self.estados[nasa_id] = "DESCARGADO"
            elif estado_actual == "ERROR_BD":
                self.estados[nasa_id] = "ORGANIZADO"

        self._escribir_archivo()

    def proceso_completado(self) -> bool:
        """ VERIFICAR SI TODO EL PROCESO ESTÁ COMPLETADO"""
        stats = self.obtener_estadisticas()
        return stats["COMPLETADAS"] == stats["TOTAL"]

    def limpiar_archivo_estado(self):
        """ LIMPIAR ARCHIVO AL COMPLETAR TODO"""
        if os.path.exists(self.archivo_estado):
            os.remove(self.archivo_estado)
            log_custom(
                section="Estado Manager",
                message="Archivo de estado eliminado - Proceso completado exitosamente",
                level="INFO",
                file=LOG_FILE,
            )
