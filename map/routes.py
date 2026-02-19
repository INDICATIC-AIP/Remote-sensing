import os
from dotenv import load_dotenv

# Load environment configuration
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(ENV_FILE)

# Get the absolute path to the project root directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Absolute path to the database
DB_PATH = os.path.join(BASE_DIR, "db", "metadata.db")

SCRIPTS_PATH = os.path.join(BASE_DIR, "scripts")

IMAGE_PROCESSOR_PATH = os.path.join(BASE_DIR, "scripts", "imageProcessor.py")

# SQLAlchemy-compatible URL
DB_URL = f"sqlite:///{DB_PATH}"

# NAS configuration - read from .env or use defaults
NAS_MOUNT = os.getenv("NAS_MOUNT", "/mnt/nas_local")
NAS_PATH = os.getenv("NAS_PATH", os.path.join(NAS_MOUNT, "DATOS API ISS"))
