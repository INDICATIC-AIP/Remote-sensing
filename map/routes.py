import os

# Get the absolute path to the project root directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Absolute path to the database
DB_PATH = os.path.join(BASE_DIR, "db", "metadata.db")

SCRIPTS_PATH = os.path.join(BASE_DIR, "scripts")

IMAGE_PROCESSOR_PATH = os.path.join(BASE_DIR, "scripts", "imageProcessor.py")

# SQLAlchemy-compatible URL
DB_URL = f"sqlite:///{DB_PATH}"

NAS_MOUNT = "/mnt/nas"
NAS_PATH = os.path.join(NAS_MOUNT, "DATOS API ISS")
