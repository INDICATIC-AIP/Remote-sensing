#!/usr/bin/env python3
"""
CLI SIMPLE PARA DESCARGAR ISS FOTOS DIRECTAMENTE AL NAS
Uso:
  python cli_download.py [--limit LIMIT] [--region REGION] [--mode MODE]

Ejemplos:
  python cli_download.py                          # Default: region from .env
  python cli_download.py --limit 50               # Últimas 50 fotos
  python cli_download.py --region panama          # Panamá
  python cli_download.py --limit 200 --region cr  # Costa Rica, 200 fotos
"""

import os
import sys
import asyncio
import argparse
import json
from typing import Dict, Optional
from dotenv import load_dotenv

# Cargar .env desde raíz del proyecto
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ENV_FILE = os.path.join(ROOT_DIR, ".env")
load_dotenv(ENV_FILE)

# Importar clientes
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from nasa_api_client import NASAAPIClient
from imageProcessor import (
    download_imagees_aria2c_optimized,
    verificar_destination_descarga,
)
from extract_enriched_metadata import extract_metadata_enriquecido

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom

# Configuración
LOG_FILE = os.path.join("..", "..", "logs", "iss", "general.log")

# Regiones preconfiguradas
REGIONS = {
    "cr": {
        "name": "Costa Rica",
        "latMin": 6.1,
        "latMax": 10.8,
        "lonMin": -82.9,
        "lonMax": -77.3,
    },
    "panama": {
        "name": "Panamá",
        "latMin": 7.2,
        "latMax": 9.6,
        "lonMin": -82.9,
        "lonMax": -77.2,
    },
    "all": {
        "name": "Global (experimental)",
        "latMin": -90,
        "latMax": 90,
        "lonMin": -180,
        "lonMax": 180,
    },
}

# Leer DEFAULT_REGION del .env, fallback a "panama"
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "panama")
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "100"))


def print_header(text: str):
    """Imprimir encabezado formateado"""
    print("\n╭─ " + "─" * (len(text) + 2) + " ─╮")
    print(f"│ {text} │")
    print("╰─ " + "─" * (len(text) + 2) + " ─╯\n")


def validate_region(region: str) -> Dict:
    """Validar y obtener configuración de región"""
    region_key = region.lower()
    if region_key not in REGIONS:
        available = ", ".join(REGIONS.keys())
        raise ValueError(f"Región '{region}' no válida. Opciones: {available}")
    return REGIONS[region_key]


async def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Descargar ISS fotos directamente al NAS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Número de fotos a descargar (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=DEFAULT_REGION,
        help=f"Región: {', '.join(REGIONS.keys())} (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["nocturno", "diurno"],
        default="nocturno",
        help="Modo: nocturno o diurno (default: nocturno)",
    )

    args = parser.parse_args()

    # Validar región
    try:
        region_config = validate_region(args.region)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Imprimir inicio
    print_header("CLI ISS DOWNLOAD")
    print(f"📍 Región: {region_config['name']}")
    print(f"📊 Límite: {args.limit} fotos")
    print(f"🌙 Modo: {args.mode}")

    # Verificar destino
    base_path, is_nas, mode_str = verificar_destination_descarga()
    print(f"💾 Destino: {mode_str}\n")

    log_custom(
        section="CLI Download",
        message=f"Iniciando descarga - Región: {region_config['name']}, Límite: {args.limit}, Modo: {args.mode}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        # Crear cliente
        is_nocturno = args.mode == "nocturno"
        client = NASAAPIClient(bounding_box=region_config, mode_nocturno=is_nocturno)

        # Obtener datos
        print_header("Consultando NASA API")
        all_results, new_results = await client.fetch_data_inteligente(
            limit_imagees=args.limit
        )

        print(f"✅ Consulta completada")
        print(f"   📷 Total encontrado: {len(all_results)}")
        print(f"   🆕 Nuevos: {len(new_results)}\n")

        if not new_results:
            print("⚠️  No hay fotos nuevas para descargar.")
            log_custom(
                section="CLI Download",
                message=f"No había fotos nuevas. Total encontrado: {len(all_results)}",
                level="INFO",
                file=LOG_FILE,
            )
            return

        # Enriquecer metadata (scraping de nadir, altitud, cámara, GeoTIFF)
        print_header("Enriqueciendo Metadatos")
        print(f"📊 Extrayendo dados enriquecidos de {len(new_results)} fotos...\n")

        log_custom(
            section="CLI Download",
            message=f"Iniciando enriquecimiento de metadata para {len(new_results)} fotos",
            level="INFO",
            file=LOG_FILE,
        )

        metadata_list = extract_metadata_enriquecido(new_results)

        # Descargar
        print_header("Iniciando Descarga")
        print(f"📦 Descargando {len(metadata_list)} fotos...\n")

        log_custom(
            section="CLI Download",
            message=f"Descargando {len(metadata_list)} fotos nuevas",
            level="INFO",
            file=LOG_FILE,
        )

        download_imagees_aria2c_optimized(metadata_list, conexiones=32)

        print_header("Descarga Completada")
        print(f"✅ Se descargaron {len(metadata_list)} fotos correctamente.")
        print(f"📁 Ubicación: {base_path}\n")

        log_custom(
            section="CLI Download",
            message=f"Descarga completada: {len(metadata_list)} fotos",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        print(f"\n❌ Error durante descarga: {str(e)}", file=sys.stderr)
        log_custom(
            section="CLI Download Error",
            message=f"Error: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
