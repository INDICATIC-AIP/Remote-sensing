"""
Configuration utility for finding project root and loading .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def find_project_root(start_path=None):
    """
    Find project root by searching for .env or other markers.
    Walks up the directory tree until it finds .env, requirements.txt, or package.json
    """
    if start_path is None:
        start_path = os.path.abspath(os.path.dirname(__file__))

    current = Path(start_path)

    # Markers that identify project root
    markers = [".env", ".git", "requirements.txt", "package.json"]

    # Search up to 5 levels up
    for _ in range(5):
        for marker in markers:
            if (current / marker).exists():
                return str(current)

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # Fallback to a reasonable default
    return str(Path(__file__).parent.parent.parent)


def load_env_config():
    """
    Load .env configuration from project root.
    Returns (env_file_path, success)
    """
    project_root = find_project_root()
    env_file = os.path.join(project_root, ".env")

    if not os.path.exists(env_file):
        return env_file, False

    load_dotenv(env_file, override=True)
    return env_file, True


# Module-level initialization
PROJECT_ROOT = find_project_root()
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")

# Auto-load on import
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)
