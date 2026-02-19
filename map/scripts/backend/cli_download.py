#!/usr/bin/env python3
"""
SIMPLE CLI TO DOWNLOAD ISS IMAGES DIRECTLY TO NAS
Usage:
    python cli_download.py [--limit LIMIT] [--region REGION] [--mode MODE]

Examples:
    python cli_download.py                         # Default: region from .env
    python cli_download.py --limit 50              # Last 50 images
    python cli_download.py --region panama         # Panama region
    python cli_download.py --limit 10 --region panama --mode night
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
LOG_FILE = os.path.join(ROOT_DIR, "logs", "iss", "general.log")

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
    """Print a formatted header"""
    print(f"\n{'=' * (len(text) + 4)}")
    print(f"  {text}")
    print(f"{'=' * (len(text) + 4)}\n")


def validate_region(region: str) -> Dict:
    """Validate and return region configuration"""
    region_key = region.lower()
    if region_key not in REGIONS:
        available = ", ".join(REGIONS.keys())
        raise ValueError(f"Region '{region}' is not valid. Options: {available}")
    return REGIONS[region_key]


async def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Download ISS images directly to NAS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of images to download (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=DEFAULT_REGION,
        help=f"Region: {', '.join(REGIONS.keys())} (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["night", "day"],
        default="night",
        help="Mode: night or day (default: night)",
    )

    args = parser.parse_args()

    # Validar región
    try:
        region_config = validate_region(args.region)
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Start info
    print_header("CLI ISS DOWNLOAD")
    print(f"Region: {region_config['name']}")
    print(f"Limit: {args.limit} images")
    print(f"Mode: {args.mode}")

    # Verificar destino
    base_path, is_nas, mode_str = verificar_destination_descarga()
    print(f"Destination: {mode_str}\n")

    log_custom(
        section="CLI Download",
        message=f"Iniciando descarga - Región: {region_config['name']}, Límite: {args.limit}, Modo: {args.mode}",
        level="INFO",
        file=LOG_FILE,
    )

    try:
        # Crear cliente
        is_nocturno = args.mode == "night"
        client = NASAAPIClient(bounding_box=region_config, mode_nocturno=is_nocturno)

        # Obtener datos
        print_header("Querying NASA API")
        # fetch_data_inteligente returns (all_results, new_results)
        all_results, new_results = await client.fetch_data_inteligente(
            limit_imagees=args.limit
        )

        print(f"Query completed.")
        print(f"  Total found: {len(all_results)}")
        print(f"  New images: {len(new_results)}\n")

        if not new_results:
            print("No new images to download.")
            log_custom(
                section="CLI Download",
                message=f"No new images. Total available: {len(all_results)}",
                level="INFO",
                file=LOG_FILE,
            )
            return

        # Enriquecer metadata (scraping de nadir, altitud, cámara, GeoTIFF)
        print_header("Enriching Metadata")
        print(f"Extracting enriched metadata for {len(new_results)} images...\n")

        log_custom(
            section="CLI Download",
            message=f"Starting metadata enrichment for {len(new_results)} images",
            level="INFO",
            file=LOG_FILE,
        )

        metadata_list = extract_metadata_enriquecido(new_results)

        # Descargar
        print_header("Starting Download")
        print(f"Downloading {len(metadata_list)} images...\n")

        log_custom(
            section="CLI Download",
            message=f"Downloading {len(metadata_list)} new images",
            level="INFO",
            file=LOG_FILE,
        )

        download_imagees_aria2c_optimized(metadata_list, conexiones=32)

        print_header("Download Completed")
        print(f"Successfully downloaded {len(metadata_list)} images.")
        print(f"Location: {base_path}\n")

        log_custom(
            section="CLI Download",
            message=f"Download completed: {len(metadata_list)} images",
            level="INFO",
            file=LOG_FILE,
        )

    except Exception as e:
        print(f"\nError during download: {str(e)}", file=sys.stderr)
        log_custom(
            section="CLI Download Error",
            message=f"Error: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
