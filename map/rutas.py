import os

# Obtener la ruta absoluta del directorio raíz del proyecto
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Definir la ruta absoluta de la base de datos
DB_PATH = os.path.join(BASE_DIR, "db", "metadata.db")

SCRIPTS_PATH = os.path.join(BASE_DIR, "scripts")

IMAGE_PROCESSOR_PATH = os.path.join(BASE_DIR, "scripts", "imageProcessor.py")

# URL compatible con SQLAlchemy
DB_URL = f"sqlite:///{DB_PATH}"

NAS_MOUNT = "/mnt/nas"
NAS_PATH = os.path.join(NAS_MOUNT,"DATOS API ISS") 
