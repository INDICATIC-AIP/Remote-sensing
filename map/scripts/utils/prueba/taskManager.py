import datetime
import subprocess
import time
import logging
import json
import socket
import random
import os

class DownloadManager:
    def __init__(self, urls=None, output_dir="/home/jose/API-NASA/descargas", script_path="/home/jose/API-NASA/map/scripts/utils/taskManager.py", 
                 base_task_name="DescargaWSL", max_retries=5, initial_retry_delay=5):
        """
        Inicializa el administrador de descargas con características avanzadas
        
        Args:
            urls (list): Lista de URLs para descargar
            output_dir (str): Directorio de salida para las descargas
            script_path (str): Ruta al script de descarga
            base_task_name (str): Nombre base para las tareas programadas
            max_retries (int): Número máximo de reintentos por descarga
            initial_retry_delay (int): Tiempo inicial de espera entre reintentos (segundos)
        """
        self.urls = urls or [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/2048px-React-icon.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/1200px-Python-logo-notext.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/HTML5_logo_and_wordmark.svg/1200px-HTML5_logo_and_wordmark.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/CSS3_logo_and_wordmark.svg/1200px-CSS3_logo_and_wordmark.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/JavaScript-logo.png/800px-JavaScript-logo.png"
        ]
        self.output_dir = output_dir
        self.script_path = script_path
        self.base_task_name = base_task_name
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.task_db_path = os.path.join(output_dir, "tasks.json")
        self.download_queue_path = os.path.join(output_dir, "download_queue.json")
        
        # Configurar logging
        os.makedirs(output_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(os.path.join(output_dir, f"download_manager_{datetime.date.today()}.log"))
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Inicializar la base de datos de tareas si no existe
        if not os.path.exists(self.task_db_path):
            self._save_tasks([])
            
        # Inicializar la cola de descargas si no existe
        if not os.path.exists(self.download_queue_path):
            self._save_download_queue([])

    def check_internet_connection(self, host="8.8.8.8", port=53, timeout=3):
        """
        Verifica si hay conexión a internet
        
        Args:
            host (str): Host para probar la conexión (Google DNS por defecto)
            port (int): Puerto para probar la conexión
            timeout (int): Tiempo de espera en segundos
            
        Returns:
            bool: True si hay conexión, False en caso contrario
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            self.logger.info("Conexión a internet verificada")
            return True
        except Exception as e:
            self.logger.warning(f"No hay conexión a internet: {e}")
            return False

    def download_files(self):
        """
        Procesa la cola de descargas
        
        Si no hay conexión a internet, las descargas permanecerán en la cola.
        Si una descarga falla, se reintentará con backoff exponencial.
        """
        if os.getenv("RUNNING_DOWNLOAD") != "1":
            return False
            
        self.logger.info(f"Iniciando procesamiento de cola de descargas en {self.output_dir}")
        
        # Verificar conexión a internet
        if not self.check_internet_connection():
            self.logger.warning("No hay conexión a internet. Las descargas quedarán pendientes.")
            self._reschedule_task(15)  # Reprogramar para intentar en 15 minutos
            return False
        
        # Cargar cola de descargas
        download_queue = self._load_download_queue()
        
        if not download_queue:
            download_queue = []

        # Agregar cualquier URL que aún no esté en la cola
        existing_urls = {item['url'] for item in download_queue}
        new_urls = [url for url in self.urls if url not in existing_urls]

        for idx, url in enumerate(new_urls):
            download_queue.append({
                "url": url,
                "id": f"dl_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}",
                "status": "pending",
                "attempts": 0,
                "added_at": datetime.datetime.now().isoformat(),
                "next_attempt": datetime.datetime.now().isoformat()
            })

        self._save_download_queue(download_queue)

        
        # Procesar cada descarga en la cola
        successful_downloads = []
        updated_queue = []
        
        for item in download_queue:
            # Saltar elementos que no están pendientes
            if item["status"] != "pending":
                updated_queue.append(item)
                continue
                
            # Verificar si es tiempo de intentar esta descarga
            next_attempt = datetime.datetime.fromisoformat(item["next_attempt"])
            if next_attempt > datetime.datetime.now():
                self.logger.info(f"Descarga {item['id']} programada para más tarde ({next_attempt.isoformat()})")
                updated_queue.append(item)
                continue
            
            # Intentar la descarga
            self.logger.info(f"Procesando descarga: {item['url']} (Intento {item['attempts'] + 1}/{self.max_retries})")
            
            filename = f"descarga_{item['id']}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            output_path = os.path.join(self.output_dir, filename)
            
            success = self._download_file(item['url'], output_path)
            
            if success:
                self.logger.info(f"Descarga exitosa: {item['url']}")
                item['status'] = 'completed'
                item['completed_at'] = datetime.datetime.now().isoformat()
                item['output_path'] = output_path
                successful_downloads.append(item)
            else:
                item['attempts'] += 1
                
                if item['attempts'] >= self.max_retries:
                    self.logger.error(f"Descarga fallida después de {self.max_retries} intentos: {item['url']}")
                    item['status'] = 'failed'
                    item['failed_at'] = datetime.datetime.now().isoformat()
                else:
                    # Calcular próximo intento con backoff exponencial
                    backoff_time = int(self.initial_retry_delay * (2 ** (item['attempts'] - 1)))
                    # Añadir "jitter" para evitar bloqueos
                    jitter = random.randint(0, int(backoff_time * 0.2))
                    delay = backoff_time + jitter
                    
                    next_attempt = datetime.datetime.now() + datetime.timedelta(seconds=delay)
                    item['next_attempt'] = next_attempt.isoformat()
                    self.logger.info(f"Reintento programado para {item['url']} en {delay} segundos")
            
            updated_queue.append(item)
            
            # Pequeña pausa entre descargas
            time.sleep(2)
        
        # Guardar la cola actualizada
        self._save_download_queue(updated_queue)
        
        # Verificar si quedan descargas pendientes
        pending_downloads = [item for item in updated_queue if item['status'] == 'pending']
        if pending_downloads:
            self.logger.info(f"Quedan {len(pending_downloads)} descargas pendientes. Reprogramando tarea.")
            self._reschedule_task(5)  # Reprogramar en 5 minutos
        
        # Registrar resultados
        with open(os.path.join(self.output_dir, "log.txt"), "a") as f:
            f.write(f"[{datetime.datetime.now()}] Resumen de sesión: {len(successful_downloads)} descargas completadas\n")
            for dl in successful_downloads:
                f.write(f"[{datetime.datetime.now()}] Descargado: {dl['url']} → {dl['output_path']}\n")
        
        return True
    

    def _download_all_with_aria2c(self):
        """
        Descarga todos los archivos en paralelo usando aria2c con un archivo de URLs.
        """
        urls_txt = os.path.join(self.output_dir, "urls.txt")
        
        # Escribir las URLs en un archivo
        with open(urls_txt, "w") as f:
            for url in self.urls:
                f.write(url + "\n")

        cmd = [
            "aria2c",
            "-i", urls_txt,
            "-d", self.output_dir,
            "--max-concurrent-downloads=5",
            "--split=5",
            "--summary-interval=1"
        ]

        self.logger.info(f"Ejecutando descarga paralela con: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                self.logger.info("Descarga paralela completada correctamente")
            else:
                self.logger.error(f"aria2c terminó con errores:\n{proc.stderr}")
        except Exception as e:
            self.logger.error(f"Error al ejecutar aria2c: {e}")


    def _download_file(self, url, output_path):
        """
        Descarga un archivo
        
        Args:
            url (str): URL para descargar
            output_path (str): Ruta donde guardar el archivo
            
        Returns:
            bool: True si la descarga fue exitosa, False en caso contrario
        """
        try:
            filename = os.path.basename(output_path)
            cmd = f"aria2c -o {filename} -d {self.output_dir} {url}"
            
            self.logger.info(f"Ejecutando: {cmd}")
            proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            return proc.returncode == 0
        except Exception as e:
            self.logger.error(f"Error durante la descarga: {e}")
            return False

    def _reschedule_task(self, minutes_from_now):
        """
        Reprograma la tarea actual para ejecutarse más tarde
        
        Args:
            minutes_from_now (int): Minutos a partir de ahora para programar la tarea
            
        Returns:
            bool: True si la tarea se reprogramó correctamente, False en caso contrario
        """
        task_id = os.getenv("TASK_ID", "unknown")
        self.logger.info(f"Reprogramando tarea {task_id} para ejecutarse en {minutes_from_now} minutos")
        
        # Obtener el nombre de la tarea actual
        tasks = self._load_tasks()
        task_name = None
        for task in tasks:
            if task.get('id') == task_id and task.get('status') != 'deleted':
                task_name = task.get('name')
                break
        
        if not task_name:
            # Si no se encuentra la tarea, usar un nombre genérico
            task_name = self._get_next_task_name()
            
        # Crear la nueva tarea programada
        run_at = (datetime.datetime.now() + datetime.timedelta(minutes=minutes_from_now)).strftime("%H:%M")
        return self.create_scheduled_task(run_at=run_at, task_name=task_name)


    def create_scheduled_task(self, run_at=None, json_path=None, frequency="ONCE", modifier=None):
        """
        Crea una tarea programada que ejecuta run_batch_processor.py con el JSON indicado.

        Args:
            run_at (str): Hora de ejecución en formato "HH:MM" 24h.
            json_path (str): Ruta del archivo JSON con los metadatos.
            frequency (str): Frecuencia de ejecución (ONCE, DAILY, WEEKLY, MINUTE, HOURLY).
            modifier (int): Modificador de frecuencia (ej. cada 5 minutos → modifier=5 con frequency=MINUTE).

        Returns:
            bool: True si se creó exitosamente, False si hubo error.
        """
        # if not json_path or not os.path.exists(json_path):
        #     self.logger.error(" JSON de metadatos no encontrado.")
        #     return False

        if run_at is None:
            run_at = (datetime.datetime.now() + datetime.timedelta(minutes=1)).strftime("%H:%M")

        try:
            datetime.datetime.strptime(run_at, "%H:%M")
        except ValueError:
            self.logger.error(" Formato de hora inválido. Usa HH:MM.")
            return False

        task_name = self._get_next_task_name()
        task_id = f"{task_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Comando que ejecutará la tarea en WSL
        command = (
                    'cmd.exe /c start "" /b wsl -d Ubuntu-24.04 '
                    '-- bash -c "RUNNING_DOWNLOAD=1 python3 /home/jose/API-NASA/map/scripts/utils/taskManager.py"'
                )


        schtasks_cmd = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/Create",
            "/TN", task_name,
            "/TR", command,
            "/SC", frequency.upper(),
            "/ST", run_at,
            "/F"
        ]

        # Solo agregar modificador si aplica (ej. cada 5 minutos)
        if frequency.upper() in ["MINUTE", "HOURLY"] and modifier:
            schtasks_cmd.extend(["/MO", str(modifier)])

        self.logger.info(f" Creando tarea '{task_name}' para {run_at} con frecuencia '{frequency.upper()}'...")
        result = subprocess.run(schtasks_cmd, capture_output=True, encoding='utf-8', errors='replace')

        if result.returncode == 0:
            self.logger.info(f" Tarea '{task_name}' creada correctamente.")
            tasks = self._load_tasks()
            tasks.append({
                "id": task_id,
                "name": task_name,
                "scheduled_time": run_at,
                "frequency": frequency,
                "modifier": modifier,
                "json_path": json_path,
                "status": "scheduled",
                "created_at": datetime.datetime.now().isoformat()
            })
            self._save_tasks(tasks)
            return True
        else:
            self.logger.error(f" Error creando tarea: {result.stderr}")
            return False



    def _get_next_task_name(self):
        """
        Genera un nombre único incremental para una nueva tarea
        
        Returns:
            str: Nombre para la nueva tarea
        """
        tasks = self._load_tasks()
        existing_names = [task.get('name', '') for task in tasks]
        
        # Encontrar el mayor número en los nombres existentes
        max_number = 0
        for name in existing_names:
            if name.startswith(self.base_task_name + "_"):
                try:
                    number = int(name.split("_")[-1])
                    max_number = max(max_number, number)
                except (ValueError, IndexError):
                    continue
        
        # Generar el siguiente nombre en secuencia
        return f"{self.base_task_name}_{max_number + 1}"

    def delete_task(self, task_name):
        """
        Elimina una tarea programada
        
        Args:
            task_name (str): Nombre de la tarea a eliminar
            
        Returns:
            bool: True si la tarea se eliminó correctamente o no existía, False en caso contrario
        """
        self.logger.info(f"Eliminando tarea programada: {task_name}")
        result = subprocess.run([
            "/mnt/c/Windows/System32/schtasks.exe",
            "/Delete", "/TN", task_name, "/F"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Actualizar estado en la base de datos
        tasks = self._load_tasks()
        for task in tasks:
            if task["name"] == task_name and task["status"] == "scheduled":
                task["status"] = "deleted"
                task["deleted_at"] = datetime.datetime.now().isoformat()
        
        self._save_tasks(tasks)
        
        return result.returncode == 0 or result.returncode == 1  # 1 significa que la tarea no existía

    def list_tasks(self):
        """
        Lista todas las tareas registradas
        
        Returns:
            list: Lista de tareas
        """
        return self._load_tasks()
    
    def _load_tasks(self):
        """Carga la base de datos de tareas"""
        if not os.path.exists(self.task_db_path):
            return []
        
        try:
            with open(self.task_db_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.logger.error(f"Error al cargar tareas: {e}")
            return []
    
    def _save_tasks(self, tasks):
        """Guarda la base de datos de tareas"""
        try:
            with open(self.task_db_path, 'w') as f:
                json.dump(tasks, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error al guardar tareas: {e}")
    
    def _load_download_queue(self):
        """Carga la cola de descargas"""
        if not os.path.exists(self.download_queue_path):
            return []
        
        try:
            with open(self.download_queue_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.logger.error(f"Error al cargar cola de descargas: {e}")
            return []
    
    def _save_download_queue(self, queue):
        """Guarda la cola de descargas"""
        try:
            with open(self.download_queue_path, 'w') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error al guardar cola de descargas: {e}")

    def list_downloads(self):
        """
        Lista todos los archivos descargados
        
        Returns:
            list: Lista de archivos descargados con metadatos
        """
        downloads = []
        try:
            for file in os.listdir(self.output_dir):
                if file.startswith("descarga_") and file.endswith(".png"):
                    file_path = os.path.join(self.output_dir, file)
                    file_stats = os.stat(file_path)
                    downloads.append({
                        "filename": file,
                        "path": file_path,
                        "size": file_stats.st_size,
                        "created": datetime.datetime.fromtimestamp(file_stats.st_ctime).isoformat()
                    })
        except Exception as e:
            self.logger.error(f"Error al listar descargas: {e}")
        
        return downloads

    def add_to_download_queue(self, urls):
        """
        Añade URLs a la cola de descargas
        
        Args:
            urls (list): Lista de URLs para añadir a la cola
            
        Returns:
            int: Número de URLs añadidas a la cola
        """
        queue = self._load_download_queue()
        
        # Filtrar URLs que ya están en la cola
        existing_urls = {item['url'] for item in queue}
        new_urls = [url for url in urls if url not in existing_urls]
        
        # Añadir nuevas URLs a la cola
        count = 0
        for idx, url in enumerate(new_urls):
            queue.append({
                "url": url,
                "id": f"dl_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}",
                "status": "pending",
                "attempts": 0,
                "added_at": datetime.datetime.now().isoformat(),
                "next_attempt": datetime.datetime.now().isoformat()
            })
            count += 1
        
        self._save_download_queue(queue)
        
        # Si se añadieron URLs, programar una tarea para procesarlas
        if count > 0:
            run_at = (datetime.datetime.now() + datetime.timedelta(minutes=1)).strftime("%H:%M")
            self.create_scheduled_task(run_at=run_at)

        
        return count

    def get_download_queue_status(self):
        """
        Obtiene estadísticas de la cola de descargas
        
        Returns:
            dict: Estadísticas de la cola de descargas
        """
        queue = self._load_download_queue()
        
        # Contar items por estado
        pending = sum(1 for item in queue if item['status'] == 'pending')
        completed = sum(1 for item in queue if item['status'] == 'completed')
        failed = sum(1 for item in queue if item['status'] == 'failed')
        
        return {
            "total": len(queue),
            "pending": pending,
            "completed": completed,
            "failed": failed
        }

    def retry_failed_downloads(self):
        """
        Marca las descargas fallidas como pendientes para volver a intentarlas
        
        Returns:
            int: Número de descargas que se marcarán para reintento
        """
        queue = self._load_download_queue()
        count = 0
        
        for item in queue:
            if item['status'] == 'failed':
                item['status'] = 'pending'
                item['attempts'] = 0
                item['next_attempt'] = datetime.datetime.now().isoformat()
                count += 1
        
        self._save_download_queue(queue)
        
        # Si hay descargas para reintentar, programar una tarea
        if count > 0:
            run_at = (datetime.datetime.now() + datetime.timedelta(minutes=1)).strftime("%H:%M")
            self.create_scheduled_task(run_at=run_at)

        
        return count
    

if __name__ == "__main__":
    if os.getenv("RUNNING_DOWNLOAD") == "1":
        manager = DownloadManager()
        manager.download_files()
    else:
        print("RUNNING_DOWNLOAD no está activa. No se descargará nada.")
