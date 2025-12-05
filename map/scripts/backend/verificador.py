#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 Verificador de Corte Inesperado
- Revisa si hubo una ejecución interrumpida
- Si existe current_execution.json, reintenta automáticamente
"""

import os
import subprocess
from datetime import datetime

# === CONFIGURACIÓN ===
SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "run_batch_processor.py")
)
CURRENT_EXECUTION_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "current_execution.json")
)
LOG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "logs", "iss", "general.log")
)

# === FUNCIONES ===


def log_custom(message, level="INFO", section="Verificador Auto-Reinicio"):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] [{section}] {message}\n")
    except Exception as e:
        print(f" Error al escribir log: {e}")


def main():
    if os.path.exists(CURRENT_EXECUTION_FILE):
        log_custom(
            " current_execution.json detectado. Ejecutando reintento automático..."
        )

        try:
            subprocess.Popen(["python", SCRIPT_PATH, "metadatos_periodicos.json"])
            log_custom(" run_batch_processor.py invocado correctamente.")
        except Exception as e:
            log_custom(f" Error al ejecutar el procesador: {e}", level="ERROR")
    else:
        log_custom(" Sin ejecución pendiente. Nada que hacer.")


if __name__ == "__main__":
    main()
