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
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Set, Tuple
from dotenv import load_dotenv

# Calcular ROOT_DIR directamente sin depender de imports
_script_path = Path(__file__).resolve()
ROOT_DIR = str(
    _script_path.parents[3]
)  # Walk up 3 levels: backend -> scripts -> map -> root

# Load .env from root
_env_file = os.path.join(ROOT_DIR, ".env")
if os.path.exists(_env_file):
    load_dotenv(_env_file)

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


def _get_year_from_metadata(metadata: Dict) -> int:
    date_str = metadata.get("FECHA", "")
    try:
        return datetime.strptime(date_str, "%Y.%m.%d").year
    except Exception:
        return 2024


def _get_mission_from_metadata(metadata: Dict) -> str:
    nasa_id = metadata.get("NASA_ID", "")
    try:
        return nasa_id.split("-")[0]
    except Exception:
        return "UNKNOWN"


def _resolve_filename(metadata: Dict) -> str:
    url = metadata.get("URL", "")
    url_path = url.split("?", 1)[0]
    raw_basename = os.path.basename(url_path)
    name, ext = os.path.splitext(raw_basename)

    nasa_id = metadata.get("NASA_ID")
    is_geotiff_url = "geotiff" in url.lower() or "getgeotiff.pl" in url.lower()
    if is_geotiff_url and nasa_id:
        return f"{nasa_id}.tif"

    if ext == "":
        return raw_basename + ".jpg"
    return raw_basename


def _resolve_final_path(metadata: Dict, base_path: str) -> str:
    year = _get_year_from_metadata(metadata)
    mission = _get_mission_from_metadata(metadata)
    camera = metadata.get("CAMARA") or "Sin_Camera"
    filename = _resolve_filename(metadata)
    return os.path.join(base_path, str(year), mission, camera, filename)


def _get_existing_ids_from_db(
    db_path: str, nasa_ids: List[str]
) -> Tuple[Set[str], Optional[str]]:
    if not os.path.exists(db_path):
        return set(), f"Database file not found: {db_path}"

    if not nasa_ids:
        return set(), None

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='Image'"
            )
            if cursor.fetchone() is None:
                return set(), "Table 'Image' not found in database"

            placeholders = ",".join("?" * len(nasa_ids))
            query = f"SELECT nasa_id FROM Image WHERE nasa_id IN ({placeholders})"
            cursor.execute(query, nasa_ids)
            rows = cursor.fetchall()
            return {row[0] for row in rows}, None
    except Exception as exc:
        return set(), f"DB query failed: {exc}"


def _print_verification_report(metadata_list: List[Dict], base_path: str):
    db_path = os.path.join(ROOT_DIR, "map", "db", "metadata.db")
    nasa_ids = [m.get("NASA_ID", "") for m in metadata_list if m.get("NASA_ID")]
    existing_ids, db_error = _get_existing_ids_from_db(db_path, nasa_ids)

    print_header("Verification Report")
    print(f"Database path: {db_path}")
    if db_error:
        print(f"Database status: ERROR - {db_error}")
    else:
        print("Database status: OK")

    file_exists_count = 0
    db_exists_count = 0
    both_ok_count = 0

    for item in metadata_list:
        nasa_id = item.get("NASA_ID", "")
        source_url = item.get("URL", "")
        final_path = _resolve_final_path(item, base_path)
        file_exists = os.path.exists(final_path)
        db_exists = nasa_id in existing_ids if nasa_id else False

        if file_exists:
            file_exists_count += 1
        if db_exists:
            db_exists_count += 1
        if file_exists and db_exists:
            both_ok_count += 1

        print(f"- NASA_ID: {nasa_id}")
        print(f"  Source URL: {source_url}")
        print(f"  Final path: {final_path}")
        print(f"  File exists: {'YES' if file_exists else 'NO'}")
        print(f"  In DB(Image): {'YES' if db_exists else 'NO'}")

    print("\nVerification summary:")
    print(f"  Total checked: {len(metadata_list)}")
    print(f"  Files present: {file_exists_count}/{len(metadata_list)}")
    print(f"  DB records present: {db_exists_count}/{len(metadata_list)}")
    print(f"  File + DB consistent: {both_ok_count}/{len(metadata_list)}\n")


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
        print(f"Error: {e}", file=sys.stderr)
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

        _print_verification_report(metadata_list, base_path)

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
