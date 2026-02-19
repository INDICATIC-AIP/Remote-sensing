"""
Configuration utility for finding project root and loading .env
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def find_project_root(start_path=None):
    """
    Find project root by prioritizing the nearest existing .env file.
    If no .env exists, fallback to the nearest directory containing .git.
    """
    if start_path is None:
        start_path = os.path.abspath(os.path.dirname(__file__))

    current = Path(start_path)

    # First pass: search for an actual .env file upwards.
    for _ in range(10):
        if (current / ".env").exists():
            return str(current)

        parent = current.parent
        if parent == current:
            break
        current = parent

    # Second pass: fallback to nearest git root.
    current = Path(start_path)
    for _ in range(10):
        if (current / ".git").exists():
            return str(current)

        parent = current.parent
        if parent == current:
            break
        current = parent

    # Final fallback to repository root layout from this file.
    return str(Path(__file__).resolve().parents[3])


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
