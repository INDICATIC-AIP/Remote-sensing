import ee
from ee import ServiceAccountCredentials
import json
import os
import shutil
import time
import sys
from datetime import datetime, timedelta
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional
import signal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom
from noaa_metrics import NOAAMetrics

#  IMPORTAR CONFIGURACIÓN DE RUTAS
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
try:
    from map.routes import NAS_PATH, NAS_MOUNT

    HAS_NAS_CONFIG = True
except ImportError:
    NAS_MOUNT = "/mnt/nas"
    NAS_PATH = os.path.join(NAS_MOUNT, "DATOS API ISS")
    HAS_NAS_CONFIG = False
    print("[WARNING] paths.py no encontrado, usando configuration por defecto")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================================
#  SISTEMA DE RECUPERACIÓN Y CONTROL DE FALLOS
# ============================================================================

NOAA_EXECUTION_FILE = os.path.join(BASE_DIR, "current_noaa_execution.json")
NOAA_RETRY_INFO_FILE = os.path.join(BASE_DIR, "noaa_retry_info.json")
NOAA_TASK_NAME = "NOAA_BatchProcessor"
MAX_RETRIES = 6
SILENT_MODE = False


def set_silent_mode(silent=True):
    """Activa/desactiva el mode silencioso para salidas JSON"""
    global SILENT_MODE
    SILENT_MODE = silent


def log_message(message, force=False, level="INFO"):
    """Log improved: INFO a stdout, ERROR a stderr"""
    if SILENT_MODE and not force:
        return

    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_message = f"[{level}] [{timestamp}] {message}"

    # Enviar a stdout o stderr según el nivel
    if level == "ERROR":
        print(formatted_message, flush=True)
    else:
        print(formatted_message, flush=True)

    # Log a file
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "noaa")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "general.log")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")

    except Exception as e:
        if not hasattr(log_message, "_warned_once"):
            print(f"[WARNING] Log a file deshabilitado (permisos): {e}", flush=True)
            log_message._warned_once = True


# ============================================================================
#  GESTIÓN DE EJECUCIÓN ACTUAL
# ============================================================================


def save_current_execution(export_data, storage_info):
    """Save status de la ejecución actual"""
    try:
        info = {
            "export_data": [
                {
                    "dataset": dataset,
                    "id_ee": id_ee,
                    "task_id": f"noaa_{id_ee}",
                    "status": "prepared",
                }
                for dataset, id_ee, _, _ in export_data
            ],
            "storage_info": storage_info,
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(export_data),
        }

        with open(NOAA_EXECUTION_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        log_message(f" Estado de ejecución guardado: {len(export_data)} tasks")

    except Exception as e:
        log_message(f" Error saving status de ejecución: {e}", level="WARNING")


def load_current_execution():
    """Load status de ejecución actual"""
    try:
        if os.path.exists(NOAA_EXECUTION_FILE):
            with open(NOAA_EXECUTION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_message(f" Error loading ejecución actual: {e}", level="WARNING")
    return None


def clear_current_execution():
    """Clean registro de ejecución actual (success)"""
    try:
        if os.path.exists(NOAA_EXECUTION_FILE):
            os.remove(NOAA_EXECUTION_FILE)
        log_message(" Estado de ejecución limpiado")
    except:
        pass


def clear_failed_execution():
    """Clean elementos de la ejecución fallida"""
    execution = load_current_execution()

    if not execution:
        return

    export_data = execution.get("export_data", [])
    log_message(f" Limpiando {len(export_data)} elementos de ejecución fallida")

    # Cancelar tasks de GEE pendientes
    try:
        cancel_pending_gee_tasks([task["task_id"] for task in export_data])
    except Exception as e:
        log_message(f" Error cancelando tasks GEE: {e}", level="WARNING")

    # Limpiar files descargados parcialmente
    try:
        clean_partial_files([task["id_ee"] for task in export_data])
    except Exception as e:
        log_message(f" Error cleaning files parciales: {e}", level="WARNING")

    # Limpiar registro
    clear_current_execution()


def cancel_pending_gee_tasks(task_descriptions):
    """Cancelar tasks de Google Earth Engine pendientes"""
    try:
        # Obtener todas las tasks
        tasks = ee.batch.Task.list()

        cancelled_count = 0
        for task in tasks:
            if task.config.get("description") in task_descriptions and task.state in [
                "RUNNING",
                "READY",
            ]:
                try:
                    task.cancel()
                    cancelled_count += 1
                    log_message(
                        f" Tarea GEE cancelada: {task.config.get('description')}"
                    )
                except:
                    pass

        if cancelled_count > 0:
            log_message(f" {cancelled_count} tasks GEE canceladas")

    except Exception as e:
        log_message(f" Error cancelando tasks GEE: {e}", level="WARNING")


def clean_partial_files(id_ees):
    """Clean files descargados parcialmente"""
    try:
        # Buscar files relacionados en folder de trabajo
        working_folders = [
            os.path.join(BASE_DIR, "../backend/API-NASA", "NOAA"),
            os.path.join(NAS_PATH, "NOAA") if os.path.exists(NAS_PATH) else None,
        ]

        removed_count = 0
        for folder in working_folders:
            if not folder or not os.path.exists(folder):
                continue

            for id_ee in id_ees:
                # Buscar files con este ID
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        if id_ee in file and file.endswith(".tif"):
                            file_path = os.path.join(root, file)
                            try:
                                # Verificar si el file está completo/válido
                                if not verify_tif_integrity(file_path):
                                    os.remove(file_path)
                                    removed_count += 1
                                    log_message(f" Archivo parcial eliminado: {file}")
                            except:
                                pass

        if removed_count > 0:
            log_message(f" {removed_count} files parciales eliminados")

    except Exception as e:
        log_message(f" Error cleaning files parciales: {e}", level="WARNING")


def verify_tif_integrity(filepath):
    """Verify integridad básica de file TIF - MEJORADO"""
    try:
        if not os.path.exists(filepath):
            return False

        # Verificar size mínimo - REDUCIDO para regiones pequeñas como Panamá
        # file_size = os.path.getsize(filepath)
        # if file_size < 500:  # 500 bytes en place de 1KB
        #     return False

        # Verificar headers TIF
        with open(filepath, "rb") as f:
            header = f.read(8)  # Leer más bytes para mejor verificación

            # TIF headers: II*\x00 (little endian) o MM\x00* (big endian)
            if len(header) < 4:
                return False

            # Verificar magic numbers de TIFF
            if header[:2] == b"II":  # Little endian
                if header[2:4] != b"*\x00":
                    return False
            elif header[:2] == b"MM":  # Big endian
                if header[2:4] != b"\x00*":
                    return False
            else:
                return False

        # Para files NOAA pequeños (regiones como Panamá), cualquier file > 500 bytes con headers corrects es válido
        # log_message(f" TIF válido: {os.path.basename(filepath)} ({file_size} bytes)")
        return True

    except Exception as e:
        log_message(f" Error verificando TIF: {e}")
        return False


# ============================================================================
#  SISTEMA DE REINTENTOS
# ============================================================================


def load_retry_info():
    """Load information de retries"""
    try:
        if os.path.exists(NOAA_RETRY_INFO_FILE):
            with open(NOAA_RETRY_INFO_FILE, "r", encoding="utf-8") as f:
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
        with open(NOAA_RETRY_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        log_message(f" Error saving retry info: {e}", level="WARNING")


def clear_retry_info():
    """Clean information de retries"""
    try:
        if os.path.exists(NOAA_RETRY_INFO_FILE):
            os.remove(NOAA_RETRY_INFO_FILE)
        log_message(" Información de retries limpiada")
    except:
        pass


def create_retry_task():
    """Create task scheduled para retry automático"""
    try:
        retry_info = load_retry_info()
        current_attempt = retry_info.get("intento", 0) + 1

        if current_attempt > MAX_RETRIES:
            log_message(f" Máximo de {MAX_RETRIES} intentos alcanzado", level="ERROR")
            clear_retry_info()
            return False

        # Tiempo incremental: 10, 20, 30, 40, 50, 60 min
        wait_minutes = 10 * current_attempt
        execution_time = datetime.now() + timedelta(minutes=wait_minutes)
        time_str = execution_time.strftime("%H:%M")
        date_str = execution_time.strftime("%d/%m/%Y")

        # Crear comando de task (ajustar según tu script principal)
        script_path = os.path.abspath(__file__.replace("_processor.py", "_commands.py"))
        task_command = f'python "{script_path}" export_all'

        cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/create",
            "/tn",
            NOAA_TASK_NAME,
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
            save_retry_info(current_attempt, execution_time.isoformat())
            log_message(
                f" Reintento {current_attempt}/{MAX_RETRIES} scheduled en {wait_minutes}min"
            )
            return True
        else:
            log_message(
                f" Error creando task de retry: {result.stderr}",
                level="ERROR",
            )
            return False

    except Exception as e:
        log_message(f" Error creando task de retry: {e}", level="ERROR")
        return False


# ============================================================================
#  GESTOR DE TAREAS ROBUSTO
# ============================================================================


class RobustGEETaskManager:
    """Gestor robusto de tasks de Google Earth Engine"""

    def __init__(self, max_concurrent_tasks: int = 6, check_interval: int = 15):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.check_interval = check_interval
        self.tasks = []
        self.completed_tasks = []
        self.failed_tasks = []
        self.lock = threading.Lock()
        self.interrupted = False

    def add_task(self, task, metadata: Dict):
        """Añade una task con sus metadata"""
        with self.lock:
            self.tasks.append(
                {
                    "task": task,
                    "metadata": metadata,
                    "start_time": time.time(),
                    "status": "QUEUED",
                }
            )

    def start_all_tasks(self):
        """Inicia todas las tasks en lotes para respetar limits"""
        total_tasks = len(self.tasks)
        if total_tasks == 0:
            return

        log_message(
            f" Iniciando {total_tasks} tasks en lotes de {self.max_concurrent_tasks}"
        )

        try:
            # Procesar en lotes
            for i in range(0, total_tasks, self.max_concurrent_tasks):
                if self.interrupted:
                    log_message(" Inicio de tasks interrumpido")
                    break

                batch = self.tasks[i : i + self.max_concurrent_tasks]
                batch_num = (i // self.max_concurrent_tasks) + 1
                total_batches = (
                    total_tasks + self.max_concurrent_tasks - 1
                ) // self.max_concurrent_tasks

                log_message(
                    f" Lote {batch_num}/{total_batches}: starting {len(batch)} tasks"
                )

                # Iniciar tasks del lote
                for task_info in batch:
                    if self.interrupted:
                        break

                    try:
                        task_info["task"].start()
                        task_info["status"] = "STARTED"
                        log_message(f" Iniciada: {task_info['metadata']['id_ee']}")
                    except Exception as e:
                        log_message(
                            f" Error starting {task_info['metadata']['id_ee']}: {e}"
                        )
                        task_info["status"] = "START_FAILED"

                # Pausa entre lotes
                if i + self.max_concurrent_tasks < total_tasks and not self.interrupted:
                    time.sleep(2)

            # Emitir progreso de lanzamiento
            if not self.interrupted:
                print(f"ProgresoLanzado: {total_tasks}/{total_tasks}", flush=True)

        except Exception as e:
            log_message(f" Error during inicio de tasks: {e}", level="ERROR")
            self.interrupted = True

    def monitor_tasks(self, progress_callback=None):
        """Monitorea todas las tasks hasta que terminen"""
        if not self.tasks:
            log_message(" No hay tasks para monitorear")
            return

        log_message(f" Monitoreando {len(self.tasks)} tasks...")

        try:
            while not self.interrupted:
                active_tasks = []
                completed_count = len(self.completed_tasks)
                failed_count = len(self.failed_tasks)

                with self.lock:
                    for task_info in self.tasks:
                        if task_info["status"] in [
                            "COMPLETED",
                            "FAILED",
                            "START_FAILED",
                        ]:
                            continue

                        try:
                            status = task_info["task"].status()
                            state = status.get("state", "UNKNOWN")
                            task_info["current_state"] = state

                            if state == "COMPLETED":
                                task_info["status"] = "COMPLETED"
                                task_info["completion_time"] = time.time()
                                self.completed_tasks.append(task_info)

                                if progress_callback:
                                    progress_callback("completed", task_info)

                            elif state == "FAILED":
                                task_info["status"] = "FAILED"
                                task_info["error"] = status.get(
                                    "error_message", "Error desconocido"
                                )
                                self.failed_tasks.append(task_info)

                                if progress_callback:
                                    progress_callback("failed", task_info)

                            elif state in ["RUNNING", "READY"]:
                                active_tasks.append(task_info)

                        except Exception as e:
                            log_message(
                                f" Error verificando {task_info['metadata']['id_ee']}: {e}"
                            )
                            active_tasks.append(task_info)

                # Actualizar progreso
                completed_count = len(self.completed_tasks)
                failed_count = len(self.failed_tasks)
                running_count = sum(
                    1 for t in active_tasks if t.get("current_state") == "RUNNING"
                )
                total_count = len(self.tasks)

                progress_pct = (
                    (completed_count / total_count * 100) if total_count > 0 else 0
                )
                progress_msg = (
                    f" Progreso: {progress_pct:.1f}% | "
                    f" {completed_count} |  {running_count} |  {failed_count}"
                )
                log_message(progress_msg)

                # Emitir progreso para UI
                print(f"ProgresoReal: {completed_count}/{total_count}", flush=True)

                # Verificar si terminaron todas
                if len(active_tasks) == 0:
                    log_message(" Todas las tasks terminaron")
                    break

                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            self.interrupted = True
            log_message(" Monitoreo interrumpido por usuario")
        except Exception as e:
            self.interrupted = True
            log_message(f" Error during monitoreo: {e}", level="ERROR")

        return self.completed_tasks, self.failed_tasks

    def interrupt(self):
        """Interrumpir el gestor de tasks"""
        self.interrupted = True


# ============================================================================
#  NOAA PROCESSOR ROBUSTO
# ============================================================================

# service_account = "noaa-lights@noaa-lights-455703.iam.gserviceaccount.com"
# key_path = os.path.join(os.path.dirname(__file__), "credentials.json")

# credentials = ee.ServiceAccountCredentials(service_account, key_path)


class NOAAProcessor:
    def __init__(self, region=None, project="noaa-lights-455703"):
        try:
            # service_account = "noaa-lights@noaa-lights-455703.iam.gserviceaccount.com"
            # key_path = os.path.join(os.path.dirname(__file__), "credentials.json")

            # if os.path.exists(key_path):
            #     credentials = ServiceAccountCredentials(service_account, key_path)
            #     ee.Initialize(credentials)
            #     log_message(" Autenticado con cuenta de servicio")
            # else:
            ee.Initialize(project=project)
            log_message(" Autenticado con usuario (earthengine authenticate)")

        except Exception as e:
            log_message(f" Error de autenticación Earth Engine: {e}", level="ERROR")
            sys.exit(1)

        # self.region = region or ee.Geometry.Rectangle([-83.1, 7.0, -77.2, 9.6])
        self.region = region or ee.Geometry.Rectangle(
            [-80.4654093347489, 8.230836436612165, -78.8284464441239, 9.68500734309484]
        )
        self.metadata_path = self.get_correct_path_noaa(
            "scripts/backend/API-NASA/noaa_metadata.json"
        )

        # Configuración de almacenamiento
        self.storage_path, self.storage_type = self._determine_storage_location()

        self.max_items = 10
        self.vis_params = {"min": 0, "max": 63}
        self.task_manager = RobustGEETaskManager(
            max_concurrent_tasks=6, check_interval=10
        )

        # Configurar manejo de señales
        self._setup_signal_handlers()

        log_message(f" Almacenamiento: {self.storage_type} → {self.storage_path}")
        self.metrics = NOAAMetrics(self.storage_path, self.metadata_path)

    def _setup_signal_handlers(self):
        """Configurar manejo de señales para interrupciones"""

        def signal_handler(signum, frame):
            log_message(f" Señal {signum} recibida, cleaning...")
            self.task_manager.interrupt()
            clear_failed_execution()
            sys.exit(1)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _determine_storage_location(self) -> tuple[str, str]:
        """Determina ubicación de almacenamiento en orden de prioridad"""
        # 1. Verificar NAS
        if self._check_nas_available():
            nas_noaa_path = os.path.join(NAS_PATH, "NOAA")
            os.makedirs(nas_noaa_path, exist_ok=True)
            return nas_noaa_path, "NAS"

        # 2. Fallback local
        local_path = os.path.join(BASE_DIR, "../backend/API-NASA", "NOAA")
        os.makedirs(local_path, exist_ok=True)
        return local_path, "Local"

    def _check_nas_available(self) -> bool:
        """Verificación improved del NAS"""
        try:
            if not os.path.exists(NAS_MOUNT):
                return False

            if not os.path.ismount(NAS_MOUNT):
                return False

            if not os.path.exists(NAS_PATH):
                try:
                    os.makedirs(NAS_PATH, exist_ok=True)
                except:
                    return False

            # Prueba de escritura
            test_file = os.path.join(NAS_PATH, ".noaa_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test noaa")
                os.remove(test_file)
                return True
            except:
                return False

        except:
            return False

    def verificar_execution_previa(self):
        """Verify si hay ejecución previa interrumpida"""
        execution = load_current_execution()

        if execution:
            timestamp = execution.get("timestamp", "")
            total_tasks = execution.get("total_tasks", 0)

            log_message(f" Ejecución previa interrumpida detectada:")
            log_message(f"    Timestamp: {timestamp}")
            log_message(f"    Total tasks: {total_tasks}")

            # Limpiar automáticamente
            log_message(" Limpiando ejecución previa...")
            clear_failed_execution()

            return True

        return False

    def export_imagees_nuevas(self):
        """Exporta imágenes nuevas con sistema robusto"""
        log_message(" Iniciando exportación robusta...")

        # Verificar ejecución previa interrumpida
        self.verificar_execution_previa()
        self.metrics.inicio_proceso = time.time()

        try:
            # Verificar configuration
            log_message(f" Verificando configuration...")
            self.storage_path, self.storage_type = self._determine_storage_location()
            working_folder = self._get_working_folder()
            log_message(f" Carpeta de trabajo: {working_folder}")

            # Preparar exportaciones
            export_data = self._prepare_exportaciones()

            if not export_data:
                log_message(" No hay imágenes nuevas para exportar")
                #  VERIFICAR ARCHIVOS EXISTENTES
                log_message(" Verificando files existentes...")
                files_fisicos = self._verificar_files_fisicos()
                log_message(f" Se encontraron {len(files_fisicos)} files en NOAA")
                return

            # Guardar status de ejecución
            storage_info = {
                "storage_path": self.storage_path,
                "storage_type": self.storage_type,
                "working_folder": working_folder,
            }
            save_current_execution(export_data, storage_info)

            # Añadir tasks al gestor
            for dataset, id_ee, image, task in export_data:
                metadata = {"dataset": dataset, "id_ee": id_ee, "image": image}
                self.task_manager.add_task(task, metadata)

            log_message(f" Preparadas {len(export_data)} tasks de exportación")

            # Iniciar tasks
            self.task_manager.start_all_tasks()

            # Monitorear con callback
            def progress_callback(event_type: str, task_info: Dict):
                if event_type == "completed":
                    self._handle_completed_task(task_info)
                elif event_type == "failed":
                    self._handle_failed_task(task_info)

            # Monitorear hasta complete
            completed_tasks, failed_tasks = self.task_manager.monitor_tasks(
                progress_callback
            )

            # Verificar si fue interrumpido
            if self.task_manager.interrupted:
                raise Exception("Proceso interrumpido")

            # Resumen
            log_message(f" Resumen:  {len(completed_tasks)} |  {len(failed_tasks)}")

            if completed_tasks:
                # Proceso de descarga y organización
                log_message(" Iniciando descarga desde Drive...")

                # Esperar para que Drive procese
                log_message("⏳ Esperando 30s para processing en Drive...")
                time.sleep(30)

                # Descargar con métricas
                self.metrics.start_descarga()
                download_success = self.download_from_drive()
                self.metrics.finish_descarga()

                if download_success:
                    log_message(" Organizando files...")
                    self._organizar_files_descargados(completed_tasks)
                    # self._organizar_files_descargados()

                else:
                    raise Exception("Error in descarga desde Drive")

            log_message(" Actualizando metadata de task actual...")
            self._actualizar_metadata_task_actual(completed_tasks)

            #  ÉXITO TOTAL
            self.metrics.calcular_metricas(completed_tasks, failed_tasks)
            clear_current_execution()
            clear_retry_info()
            log_message(" Exportación completed exitosamente")

        except Exception as e:
            #  FALLO: Limpiar y prepare retry
            log_message(f" Error during exportación: {str(e)}", level="ERROR")

            # Limpiar elementos de esta ejecución
            clear_failed_execution()

            # Crear task de retry
            if create_retry_task():
                log_message(" Reintento automático scheduled")
            else:
                log_message(" No se pudo programar retry", level="ERROR")

            raise  # Re-lanzar para que el llamador maneje

    def _get_working_folder(self) -> str:
        """Get folder de trabajo"""
        return self.storage_path

    def download_from_drive(self, remote="gdrive"):
        """Descarga robusta desde Drive con feedback improved"""
        try:
            working_folder = self._get_working_folder()
            log_message(f" DESCARGANDO DESDE {remote.upper()}")
            log_message(f" Destino: {working_folder}")

            # Verificar rclone
            log_message(" Verificando configuration de rclone...")
            try:
                check_result = subprocess.run(
                    ["rclone", "listremotes"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if remote not in check_result.stdout:
                    log_message(f" Remote '{remote}' no está configurado en rclone")
                    log_message(f" Remotes disponibles: {check_result.stdout.strip()}")
                    return False
                else:
                    log_message(f" Remote '{remote}' configurado correctmente")
            except Exception as e:
                log_message(f" Error verificando rclone: {e}")
                return False

            # Mostrar comando que se va a ejecutar
            cmd = [
                "rclone",
                "copy",
                f"{remote}:",
                working_folder,
                "--include",
                "viirs_*.tif",
                "--include",
                "dmsp_*.tif",
                # "--include",
                # "noaa_*.tif",  # Fallback
                "--update",
                "--progress",
                "--stats",
                "5s",
                "--transfers",
                "4",
                "--checkers",
                "8",
                "--verbose",
            ]
            log_message(f" Ejecutando: {' '.join(cmd)}")

            # Descarga con progreso improved
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True,
            )

            log_message(" Monitoreando progreso de rclone...")
            lines_shown = 0

            for line in iter(process.stdout.readline, ""):
                line = line.strip()
                if line:
                    # Mostrar progreso si tiene porcentaje
                    if "Transferred:" in line and "%" in line:
                        import re

                        percent_match = re.search(r"(\d+)%", line)
                        if percent_match:
                            percent = int(percent_match.group(1))
                            print(f"PROGRESS: {percent}", flush=True)
                            log_message(f" Progreso: {percent}% - {line}")
                        continue

                    # Mostrar líneas importantes o cada pocas líneas
                    if (
                        any(
                            keyword in line.lower()
                            for keyword in [
                                "copied",
                                "transferred",
                                "error",
                                "failed",
                                "skipped",
                            ]
                        )
                        or lines_shown < 5
                    ):
                        log_message(f"rclone: {line}")
                        lines_shown += 1

            process.stdout.close()
            return_code = process.wait()

            log_message(f" rclone terminó con código: {return_code}")

            if return_code == 0:
                # Verificar qué se descargó
                try:
                    all_files = os.listdir(working_folder)
                    tif_files = [f for f in all_files if f.endswith(".tif")]
                    log_message(f" Archivos .tif en destination: {len(tif_files)}")

                    if tif_files:
                        log_message(" DESCARGA EXITOSA - Archivos encontrados:")
                        for f in tif_files[:10]:  # Mostrar máximo 10
                            file_path = os.path.join(working_folder, f)
                            file_size = os.path.getsize(file_path)
                            log_message(f"    {f} ({file_size} bytes)")
                        if len(tif_files) > 10:
                            log_message(f"   ... y {len(tif_files) - 10} files más")
                    else:
                        log_message(
                            " DESCARGA COMPLETADA PERO NO SE ENCONTRARON ARCHIVOS .TIF NUEVOS"
                        )
                        log_message(
                            " Esto significa que todos los files ya estaban actualizados"
                        )

                    print(f"PROGRESS: 100", flush=True)
                    return len(tif_files) > 0

                except Exception as e:
                    log_message(f" Error verificando files descargados: {e}")
                    return False
            else:
                log_message(f" rclone falló con código {return_code}")
                return False

        except Exception as e:
            log_message(f" Error during descarga: {e}")
            return False

    def _mover_file(self, id_ee: str, dataset: str):
        """Mover file con verificación de integridad"""
        working_folder = self._get_working_folder()

        # Buscar file
        # possible_names = [f"noaa_{id_ee}.tif", f"{id_ee}.tif"]
        prefix = "viirs" if dataset == "VIIRS" else "dmsp"
        possible_names = [f"{prefix}_{id_ee}.tif", f"noaa_{id_ee}.tif", f"{id_ee}.tif"]
        src = None
        nombre_file = None

        for name in possible_names:
            potential_src = os.path.join(working_folder, name)
            if os.path.exists(potential_src):
                src = potential_src
                nombre_file = name
                break

        if not src:
            log_message(f" Archivo no encontrado: {possible_names}")
            return False

        # Determinar destination
        if dataset == "VIIRS":
            year = id_ee.split("_")[0] if "_" in id_ee else id_ee[:4]
            dst_dir = os.path.join(working_folder, "VIIRS", year)
        else:
            dst_dir = os.path.join(working_folder, "DMSP-OLS")

        dst = os.path.join(dst_dir, f"noaa_{id_ee}.tif")

        try:
            os.makedirs(dst_dir, exist_ok=True)
            file_size = os.path.getsize(src)
            log_message(f" Organizando: {nombre_file} ({file_size} bytes)")

            #  MOVER ARCHIVO (esto falta o está mal)
            shutil.move(src, dst)

            if os.path.exists(dst):
                log_message(f" Organizado: {dst}")
                return True
            else:
                log_message(f" Error: file no se movió correctmente")
                return False

        except Exception as e:
            log_message(f" Error organizando {nombre_file}: {e}")
            return False

    def _organizar_files_descargados(self, completed_tasks):
        """Organiza files descargados con verificación"""
        log_message(" Organizando files descargados...")

        # if not completed_tasks:
        #     log_message(" No hay tasks completeds para organizar")
        #     return

        working_folder = self._get_working_folder()
        log_message(f" Carpeta de trabajo: {working_folder}")

        # Verificar files disponibles
        try:
            all_files = os.listdir(working_folder)
            tif_files = [f for f in all_files if f.endswith(".tif")]
            log_message(f" Archivos .tif disponibles: {len(tif_files)}")

            for f in tif_files:
                file_path = os.path.join(working_folder, f)
                file_size = os.path.getsize(file_path)
                log_message(f"   {f} ({file_size} bytes)")

        except Exception as e:
            log_message(f" Error listando files: {e}")
            return

        organized_count = 0
        failed_count = 0

        for f in tif_files:
            if not f.endswith(".tif"):
                continue

            # Detectar tipo por nombre de file
            if f.startswith("viirs_"):
                id_ee = f.replace("viirs_", "").replace(".tif", "")
                dataset = "VIIRS"
            elif f.startswith("dmsp_"):
                id_ee = f.replace("dmsp_", "").replace(".tif", "")
                dataset = "DMSP"
            else:
                # Fallback para files con noaa_
                id_ee = f.replace("noaa_", "").replace(".tif", "")
                dataset = "VIIRS" if "_" in id_ee else "DMSP"

            log_message(f" Organizando: {id_ee} ({dataset})")

            success = self._mover_file(id_ee, dataset)
            if success:
                organized_count += 1
                log_message(f" Completado: {id_ee}")
            else:
                failed_count += 1
                log_message(f" Falló organización: {id_ee}")

        log_message(f" Organización completed:")
        log_message(f"   Organizados: {organized_count}")
        log_message(f"   Fallidos: {failed_count}")

        # Verificar estructura final
        self._verificar_estructura_final()

    # def _organizar_files_descargados(self):
    #     """Organiza todos los files .tif encontrados en la folder de trabajo"""
    #     log_message(" Organizando files descargados...")

    #     working_folder = self._get_working_folder()
    #     log_message(f" Carpeta de trabajo: {working_folder}")

    #     try:
    #         all_files = os.listdir(working_folder)
    #         tif_files = [f for f in all_files if f.endswith(".tif")]
    #         log_message(f" Archivos .tif disponibles: {len(tif_files)}")
    #     except Exception as e:
    #         log_message(f" Error listando files: {e}")
    #         return

    #     organized_count = 0
    #     failed_count = 0

    #     for f in tif_files:
    #         id_ee = f.replace("noaa_", "").replace(".tif", "")
    #         dataset = "VIIRS" if "_" in id_ee else "DMSP"

    #         log_message(f" Organizando: {id_ee} ({dataset})")

    #         success = self._mover_file(id_ee, dataset)
    #         if success:
    #             organized_count += 1
    #             try:
    #                 self._actualizar_metadata(id_ee, dataset, image=None)
    #                 log_message(f" Completado: {id_ee}")
    #             except Exception as e:
    #                 log_message(f" Error in metadata de {id_ee}: {e}")
    #         else:
    #             failed_count += 1
    #             log_message(f" Falló organización: {id_ee}")

    #     log_message(f" Organización completed:")
    #     log_message(f"   Organizados: {organized_count}")
    #     log_message(f"   Fallidos: {failed_count}")

    #     self._verificar_estructura_final()

    def _verificar_estructura_final(self):
        """Verificación de estructura final"""
        working_folder = self._get_working_folder()
        log_message(f" Verificando estructura en {self.storage_type}: {working_folder}")

        try:
            # Verificar VIIRS
            viirs_path = os.path.join(working_folder, "VIIRS")
            if os.path.exists(viirs_path):
                for year_folder in os.listdir(viirs_path):
                    year_path = os.path.join(viirs_path, year_folder)
                    if os.path.isdir(year_path):
                        files = [f for f in os.listdir(year_path) if f.endswith(".tif")]
                        log_message(f"   VIIRS/{year_folder}: {len(files)} files")

            # Verificar DMSP-OLS
            dmsp_path = os.path.join(working_folder, "DMSP-OLS")
            if os.path.exists(dmsp_path):
                files = [f for f in os.listdir(dmsp_path) if f.endswith(".tif")]
                log_message(f"   DMSP-OLS: {len(files)} files")

            # Calcular espacio usado
            total_size = 0
            for root, dirs, files in os.walk(working_folder):
                for file in files:
                    if file.endswith(".tif"):
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)

            size_mb = total_size / (1024 * 1024)
            log_message(f" Espacio total usado: {size_mb:.1f} MB")

        except Exception as e:
            log_message(f" Error verificando estructura: {e}")

    def _prepare_exportaciones(self) -> List[Tuple]:
        """Prepara exportaciones de manera eficiente"""
        metadata = self._cargar_json(self.metadata_path)
        nuevas = []

        colecciones = [
            ("DMSP", ee.ImageCollection("NOAA/DMSP-OLS/NIGHTTIME_LIGHTS")),
            ("VIIRS", ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG")),
        ]

        log_message(" Buscando imágenes nuevas...")

        for dataset, coleccion_base in colecciones:
            log_message(f" Procesando {dataset}...")

            try:
                coleccion = coleccion_base.filterBounds(self.region).sort(
                    "system:time_start", False
                )

                ids = coleccion.aggregate_array("system:id").getInfo()
                times = coleccion.aggregate_array("system:time_start").getInfo()

                log_message(f" {dataset}: {len(ids)} imágenes totales")

                nuevas_dataset = 0
                for full_id, t in zip(ids, times):
                    id_ee = full_id.split("/")[-1]

                    if id_ee in metadata:
                        continue

                    image = ee.Image(full_id)
                    nuevas.append((dataset, id_ee, image))
                    nuevas_dataset += 1

                log_message(f" {dataset}: {nuevas_dataset} imágenes nuevas")

            except Exception as e:
                log_message(f" Error processing {dataset}: {e}")

        # Limitar para tests
        if self.max_items:
            nuevas = nuevas[: self.max_items]
            log_message(f" Limitando a {self.max_items} elementos")

        # Crear tasks de exportación
        tasks = []
        for dataset, id_ee, image in nuevas:
            scale = 1000

            if dataset == "DMSP":
                image = image.select("stable_lights")
            elif dataset == "VIIRS":
                image = image.select("avg_rad")

            # task = ee.batch.Export.image.toDrive(
            #     image=image.clip(self.region),
            #     description=f"noaa_{id_ee}",
            #     fileNamePrefix=f"noaa_{id_ee}",
            prefix = "viirs" if dataset == "VIIRS" else "dmsp"
            task = ee.batch.Export.image.toDrive(
                image=image.clip(self.region),
                description=f"{prefix}_{id_ee}",
                fileNamePrefix=f"{prefix}_{id_ee}",
                region=self.region,
                scale=scale,
                maxPixels=1e13,
                fileFormat="GeoTIFF",
            )
            tasks.append((dataset, id_ee, image, task))

        log_message(f" Preparadas {len(tasks)} tasks")
        return tasks

    def _handle_completed_task(self, task_info: Dict):
        """Maneja task completed"""
        metadata = task_info["metadata"]
        id_ee = metadata["id_ee"]
        log_message(f" Completada: {id_ee}")

    def _handle_failed_task(self, task_info: Dict):
        """Maneja task fallida"""
        metadata = task_info["metadata"]
        id_ee = metadata["id_ee"]
        error = task_info.get("error", "Error desconocido")
        log_message(f" Fallida: {id_ee} - {error}")

    def _actualizar_metadata(self, id_ee: str, dataset: str, image):
        """Actualiza metadata de image procesada"""
        try:
            date = image.date().format("YYYY-MM-dd").getInfo()
            info = {
                "dataset": dataset,
                "date": date,
                "region": "Panama",
                "resolution": "1km" if dataset == "DMSP" else "500m",
                "procesado": datetime.now().isoformat(),
            }

            metadata = self._cargar_json(self.metadata_path)
            metadata[id_ee] = info
            self._guardar_json(self.metadata_path, metadata)

            log_message(f" Metadatos actualizados: {id_ee}")
        except Exception as e:
            log_message(f" Error actualizando metadata {id_ee}: {e}")

    def _guardar_json(self, path: str, data: Dict):
        """Guarda file JSON con manejo de errors"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_message(f" Error saving {path}: {e}")

    def _cargar_json(self, path: str) -> Dict:
        """Load file JSON con manejo de errors"""
        try:
            if not os.path.isabs(path):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                path_absoluta = os.path.join(base_dir, path)
                if not os.path.exists(path_absoluta):
                    path_absoluta = os.path.abspath(path)
                path = path_absoluta

            if not os.path.exists(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=2)
                return {}

            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)

        except Exception as e:
            log_message(f" Error loading {path}: {e}")
            return {}

    def get_correct_path_noaa(self, original_path):
        """Detecta ubicación correct para metadata - ARREGLADO"""

        #  POSSIBLE LOCATIONS IN PRIORITY ORDER
        possible_paths = [
            # 1. NAS path if available
            "/mnt/nas/DATOS API ISS/NOAA/noaa_metadata.json",
            # 2. Relative path from current script
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "backend",
                "API-NASA",
                "noaa_metadata.json",
            ),
            # 3. Absolute path from BASE_DIR
            os.path.join(BASE_DIR, "..", "backend", "API-NASA", "noaa_metadata.json"),
            # 4. Path in UI
            os.path.join(BASE_DIR, "ui", "noaa_metadata.json"),
            # 5. Original path as fallback
            original_path,
        ]

        # Verificar si NAS está montado
        nas_mounted = False
        try:
            result = subprocess.run(
                ["mountpoint", "/mnt/nas"], capture_output=True, text=True
            )
            nas_mounted = result.returncode == 0
        except:
            pass

        # Buscar primera path que existe o sea creatable
        for path in possible_paths:
            # Saltar NAS si no está montado
            if "/mnt/nas" in path and not nas_mounted:
                continue

            try:
                # Convertir a path absoluta
                abs_path = os.path.abspath(path)

                # Si existe, usarla
                if os.path.exists(abs_path):
                    log_message(f" Usando metadata existentes: {abs_path}")
                    return abs_path

                # Si no existe, verificar si se puede crear el directory
                parent_dir = os.path.dirname(abs_path)
                if os.path.exists(parent_dir) or self._can_create_directory(parent_dir):
                    log_message(f" Usando nueva ubicación de metadata: {abs_path}")
                    return abs_path

            except Exception as e:
                continue

        # Fallback final: crear en directory del script
        fallback_path = os.path.join(BASE_DIR, "metadata_noaa.json")
        log_message(f" Usando fallback para metadata: {fallback_path}")
        return fallback_path

    def _can_create_directory(self, directory_path):
        """Verify si se puede crear un directory"""
        try:
            # Verificar directorys padre hasta encontrar uno que exista
            current = directory_path
            while current and current != os.path.dirname(current):
                if os.path.exists(current):
                    # Verificar permisos de escritura
                    return os.access(current, os.W_OK)
                current = os.path.dirname(current)
            return False
        except:
            return False

    # ============================================================================
    #  MÉTODOS ADICIONALES PARA COMPATIBILIDAD
    # ============================================================================

    def generate_tiles_json(self, output_path="scripts/noaa/ui/tiles_panama.json"):
        """Genera tiles JSON de forma optimized"""
        output_path = os.path.abspath(output_path)
        log_message(f" Guardando tiles en: {output_path}")

        tiles = {}
        colecciones = [
            (
                "DMSP",
                ee.ImageCollection("NOAA/DMSP-OLS/NIGHTTIME_LIGHTS"),
                "stable_lights",
                "1km",
            ),
            (
                "VIIRS",
                ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG"),
                "avg_rad",
                "500m",
            ),
        ]

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = []

                for dataset, coleccion, band, resolution in colecciones:
                    future = executor.submit(
                        self._process_collection_tiles,
                        dataset,
                        coleccion,
                        band,
                        resolution,
                    )
                    futures.append(future)

                for future in as_completed(futures):
                    try:
                        dataset_tiles = future.result()
                        tiles.update(dataset_tiles)
                    except Exception as e:
                        log_message(f" Error processing colección: {e}")

            # Guardar tiles
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(tiles, f, indent=2)
            log_message(f" Tiles guardado en: {output_path}")

        except Exception as e:
            log_message(f" Error generando tiles: {e}")

    def _process_collection_tiles(
        self, dataset: str, coleccion, band: str, resolution: str
    ) -> Dict:
        """Procesa tiles de una colección específica"""
        tiles = {}

        try:
            coleccion_filtrada = coleccion.filterBounds(self.region).sort(
                "system:time_start", True
            )
            ids = coleccion_filtrada.aggregate_array("system:id").getInfo()
            dates = coleccion_filtrada.aggregate_array("system:time_start").getInfo()

            for full_id, t in zip(ids, dates):
                try:
                    id_ee = full_id.split("/")[-1]
                    image = ee.Image(full_id).select(band).clip(self.region)
                    url = image.getMapId(self.vis_params)["tile_fetcher"].url_format
                    date = (
                        datetime.utcfromtimestamp(t / 1000).strftime("%Y-%m")
                        if dataset == "VIIRS"
                        else id_ee[-4:]
                    )

                    tiles[date] = {
                        "tile": url,
                        "dataset": dataset,
                        "id": id_ee,
                        "type": band,
                        "resolution": resolution,
                    }
                    log_message(f" {dataset} {id_ee}")
                except Exception as e:
                    log_message(f" Error {dataset} {id_ee}: {e}")
        except Exception as e:
            log_message(f" Error processing colección {dataset}: {e}")

        return tiles

    def get_metadata(self, year: str) -> Optional[Dict]:
        """Obtiene metadata para un año específico"""
        try:
            set_silent_mode(True)

            metadata_result = {}
            colecciones = [
                ("DMSP", ee.ImageCollection("NOAA/DMSP-OLS/NIGHTTIME_LIGHTS")),
                ("VIIRS", ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG")),
            ]

            for dataset, coleccion in colecciones:
                try:
                    coleccion_filtrada = coleccion.filterBounds(self.region)

                    if dataset == "VIIRS":
                        start_date = f"{year}-01-01"
                        end_date = f"{int(year) + 1}-01-01"
                        coleccion_filtrada = coleccion_filtrada.filterDate(
                            start_date, end_date
                        )

                    coleccion_filtrada = coleccion_filtrada.sort(
                        "system:time_start", False
                    )
                    image_list = coleccion_filtrada.getInfo()

                    dataset_metadata = {}

                    for image_info in image_list["features"]:
                        full_id = image_info["id"]
                        id_ee = full_id.split("/")[-1]
                        properties = image_info["properties"]

                        if dataset == "DMSP":
                            if year not in id_ee:
                                continue
                        elif dataset == "VIIRS":
                            time_start = properties.get("system:time_start", 0)
                            if time_start:
                                img_year = datetime.utcfromtimestamp(
                                    time_start / 1000
                                ).year
                                if str(img_year) != year:
                                    continue

                        dataset_metadata[id_ee] = {
                            "dataset": dataset,
                            "system_id": full_id,
                            "noaa_metadata": properties,
                            "extracted_at": datetime.now().isoformat(),
                        }

                    if dataset_metadata:
                        metadata_result[dataset] = dataset_metadata

                except Exception as e:
                    if not SILENT_MODE:
                        log_message(
                            f" Error getting metadata {dataset} para {year}: {e}"
                        )

            return metadata_result if metadata_result else None

        except Exception as e:
            if not SILENT_MODE:
                log_message(f" Error getting metadata para {year}: {e}")
            return None
        finally:
            set_silent_mode(False)

    def _ordenar_metadata(self, metadata: Dict) -> Dict:
        """Ordena metadata: DMSP por año, VIIRS por año y mes"""
        # Separar por dataset
        dmsp_items = []
        viirs_items = []

        for id_ee, data in metadata.items():
            dataset = data.get("dataset", "")

            if dataset == "DMSP":
                year = int(id_ee[-4:])  # Últimos 4 caracteres
                dmsp_items.append((year, id_ee, data))
            elif dataset == "VIIRS":
                props = data.get("properties", {})
                time_start = props.get("system:time_start", 0)
                dt = datetime.utcfromtimestamp(time_start / 1000)
                viirs_items.append((dt.year, dt.month, id_ee, data))

        # Ordenar DMSP por año (descendente)
        dmsp_items.sort(key=lambda x: x[0], reverse=True)
        # Ordenar VIIRS por año y mes (descendente)
        viirs_items.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # Reconstruir diccionario ordenado
        metadata_ordenados = {}
        for year, id_ee, data in dmsp_items:
            metadata_ordenados[id_ee] = data
        for year, month, id_ee, data in viirs_items:
            metadata_ordenados[id_ee] = data

        return metadata_ordenados

    def _actualizar_metadata_task_actual(self, completed_tasks):
        """Actualiza metadata SOLO de las imágenes de la task actual usando API de Earth Engine"""
        try:
            log_message(" Actualizando metadata de task actual...")

            # Cargar metadata existentes
            metadata_existentes = self._cargar_json(self.metadata_path)

            nuevos_agregados = 0

            for task_info in completed_tasks:
                metadata = task_info["metadata"]
                dataset = metadata["dataset"]
                id_ee = metadata["id_ee"]
                image = metadata["image"]

                # Verificar si file existe físicamente
                if not self._file_existe_en_noaa(id_ee, dataset):
                    log_message(f" Archivo no encontrado físicamente: {id_ee}")
                    continue

                # Solo agregar si NO existe en metadata
                if id_ee not in metadata_existentes:
                    try:
                        #  USAR METADATOS DE EARTH ENGINE API
                        ee_info = image.getInfo()
                        properties = ee_info.get("properties", {})
                        bands = ee_info.get("bands", [])
                        system_id = properties.get(
                            "system:id", f"NOAA/{dataset}/{id_ee}"
                        )

                        metadata_existentes[id_ee] = {
                            "id": id_ee,
                            "dataset": dataset,
                            "properties": properties,
                            "bands": bands,
                            "system_id": system_id,
                            "almacenamiento": self.storage_path,  #  RUTA DONDE ESTÁ GUARDADO
                            "agregado": datetime.now().isoformat(),
                        }

                        nuevos_agregados += 1
                        log_message(f" Metadatos agregados: {id_ee}")

                    except Exception as e:
                        log_message(f" Error getting metadata EE de {id_ee}: {e}")
                else:
                    log_message(f" Ya existe en metadata: {id_ee}")

            #  GUARDAR SIN ORDENAR
            self._guardar_json(self.metadata_path, metadata_existentes)

            log_message(
                f" Metadatos actualizados: {nuevos_agregados} nuevos de {len(completed_tasks)} tasks"
            )
            return True

        except Exception as e:
            log_message(f" Error actualizando metadata de task: {e}")
            return False

    def _verificar_files_fisicos(self):
        """Verifica qué files existen físicamente en las folders NOAA"""
        files_encontrados = []

        try:
            # Verificar DMSP-OLS
            dmsp_path = os.path.join(self.storage_path, "DMSP-OLS")
            if os.path.exists(dmsp_path):
                for file in os.listdir(dmsp_path):
                    if file.endswith(".tif"):
                        id_ee = file.replace("noaa_", "").replace(".tif", "")
                        files_encontrados.append(id_ee)

            # Verificar VIIRS por años
            viirs_path = os.path.join(self.storage_path, "VIIRS")
            if os.path.exists(viirs_path):
                for year_folder in os.listdir(viirs_path):
                    year_path = os.path.join(viirs_path, year_folder)
                    if os.path.isdir(year_path):
                        for file in os.listdir(year_path):
                            if file.endswith(".tif"):
                                id_ee = file.replace("noaa_", "").replace(".tif", "")
                                files_encontrados.append(id_ee)

            log_message(f" Archivos físicos encontrados: {len(files_encontrados)}")
            return files_encontrados

        except Exception as e:
            log_message(f" Error verificando files físicos: {e}")
            return []

    def _file_existe_en_noaa(self, id_ee: str, dataset: str):
        """Verifica si un file específico existe en las folders NOAA"""
        try:
            if dataset == "DMSP":
                file_path = os.path.join(
                    self.storage_path, "DMSP-OLS", f"noaa_{id_ee}.tif"
                )
            elif dataset == "VIIRS":
                year = id_ee.split("_")[0] if "_" in id_ee else id_ee[:4]
                file_path = os.path.join(
                    self.storage_path, "VIIRS", year, f"noaa_{id_ee}.tif"
                )
            else:
                return False

            return os.path.exists(file_path)

        except Exception as e:
            log_message(f" Error verificando file {id_ee}: {e}")
            return False

    def generate_metadata_file(
        self, output_path="scripts/backend/API-NASA/metadata_noaa.json"
    ):
        """Genera metadata_noaa.json compatible con la UI"""
        try:
            set_silent_mode(True)

            output_path = self.get_correct_path_noaa(os.path.abspath(output_path))

            if not SILENT_MODE:
                print(f" Generando metadata en: {output_path}")

            metadata_ui = {}

            colecciones = [
                ("DMSP", ee.ImageCollection("NOAA/DMSP-OLS/NIGHTTIME_LIGHTS")),
                ("VIIRS", ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG")),
            ]

            total_images = 0

            for dataset, coleccion in colecciones:
                try:
                    if not SILENT_MODE:
                        print(f" Procesando {dataset}...")

                    coleccion_filtrada = coleccion.filterBounds(self.region).sort(
                        "system:time_start", False
                    )
                    image_list = coleccion_filtrada.getInfo()

                    for image_info in image_list["features"]:
                        full_id = image_info["id"]
                        id_ee = full_id.split("/")[-1]
                        properties = image_info["properties"]
                        bands = image_info.get("bands", [])

                        # metadata_ui[id_ee] = {
                        #     "id": id_ee,
                        #     "dataset": dataset,
                        #     "properties": properties,
                        #     "bands": bands,
                        #     "system_id": full_id,
                        #     "extracted_at": datetime.now().isoformat(),
                        # }
                        metadata_ui[id_ee] = {
                            "id": id_ee,
                            "dataset": dataset,
                            "properties": properties,
                            "bands": bands,
                            "system_id": full_id,
                            "almacenamiento": self.storage_path,
                        }

                        total_images += 1

                    if not SILENT_MODE:
                        count = len(
                            [
                                k
                                for k, v in metadata_ui.items()
                                if v["dataset"] == dataset
                            ]
                        )
                        print(f"[INFO] {dataset}: {count} imágenes procesadas")

                except Exception as e:
                    if not SILENT_MODE:
                        print(
                            f"[ERROR] Error processing {dataset}: {e}", file=sys.stderr
                        )

            # Guardar file
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(metadata_ui, f, indent=2, ensure_ascii=False)

                if not SILENT_MODE:
                    print(f"[INFO] Metadatos guardados: {output_path}")
                    print(f"[INFO] Total: {total_images} imágenes")

                return True

            except Exception as e:
                if not SILENT_MODE:
                    print(f"[ERROR] Error saving file: {e}", file=sys.stderr)
                return False

        except Exception as e:
            if not SILENT_MODE:
                print(f"[ERROR] Error generando metadata: {e}", file=sys.stderr)
            return False
        finally:
            set_silent_mode(False)

    def get_storage_info(self) -> dict:
        """Información de almacenamiento"""
        return {
            "storage_type": self.storage_type,
            "storage_path": self.storage_path,
            "nas_available": self.storage_type == "NAS",
            "nas_mount_point": NAS_MOUNT if self.storage_type == "NAS" else None,
        }


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================


def verificar_configuration_nas():
    """Verify configuration del NAS"""
    try:
        if os.path.ismount(NAS_MOUNT):
            print(f" NAS montado en: {NAS_MOUNT}")

            if os.path.exists(NAS_PATH):
                print(f" Ruta NOAA disponible: {NAS_PATH}")

                stat = os.statvfs(NAS_MOUNT)
                free_space = stat.f_bavail * stat.f_frsize / (1024**3)
                print(f" Espacio libre: {free_space:.1f} GB")
                return True
            else:
                print(f" Ruta NOAA no existe: {NAS_PATH}")
                return False
        else:
            print(f" NAS no montado en: {NAS_MOUNT}")
            return False

    except Exception as e:
        print(f" Error verificando NAS: {e}")
        return False


def mostrar_configuration():
    """Muestra configuration actual"""
    print(" CONFIGURACIÓN NOAA ROBUSTA:")
    print(f" NAS Mount: {NAS_MOUNT}")
    print(f" NAS Path: {NAS_PATH}")
    print(f" Config desde paths.py: {HAS_NAS_CONFIG}")

    nas_ok = verificar_configuration_nas()

    if nas_ok:
        print(" MODO: NAS disponible")
    else:
        print(" MODO: Local fallback")


def main():
    """Función principal robusta"""
    processor = NOAAProcessor()

    log_message(" Iniciando NOAA Processor Robusto...")

    try:
        # Mostrar configuration
        info = processor.get_storage_info()
        log_message(f" Configuración:")
        for key, value in info.items():
            log_message(f"  {key}: {value}")

        # Ejecutar exportación robusta
        processor.export_imagees_nuevas()

        log_message(" Proceso completed exitosamente")

        processor.generate_metadata_file()

    except Exception as e:
        log_message(f" Error in proceso principal: {e}", level="ERROR")
        sys.exit(1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "check_config":
        mostrar_configuration()
    else:
        main()
