import argparse
import os
from pathlib import Path
from typing import Dict, List

from imageProcessor import HybridOptimizedProcessor, verificar_destination_descarga

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "map" / "db" / "metadata.db"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}


def build_metadata_from_existing_files(base_path: Path, limit: int) -> List[Dict]:
    metadata: List[Dict] = []

    for file_path in sorted(base_path.rglob("*")):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in VALID_EXTENSIONS:
            continue

        rel_parts = file_path.relative_to(base_path).parts
        if len(rel_parts) < 4:
            continue

        year, mission, camera = rel_parts[0], rel_parts[1], rel_parts[2]
        nasa_id = file_path.stem

        if not nasa_id or "-" not in nasa_id:
            continue

        metadata.append(
            {
                "NASA_ID": nasa_id,
                "URL": f"https://eol.jsc.nasa.gov/DatabaseImages/seed/{file_path.name}",
                "FECHA": f"{year}.01.01",
                "HORA": "00:00:00 GMT",
                "CAMARA": camera,
                "FORMATO": file_path.suffix.lower().lstrip("."),
                "RESOLUCION": None,
            }
        )

        if limit > 0 and len(metadata) >= limit:
            break

    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poblar BD usando imágenes ya existentes en NAS/local sin redescargar"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Cantidad máxima a procesar"
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help="Ruta base de imágenes (si se omite usa NAS/local detectado por el proyecto)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Solo muestra candidatos"
    )
    args = parser.parse_args()

    if args.base_path:
        base_path = Path(args.base_path).resolve()
    else:
        detected_base, _, _ = verificar_destination_descarga()
        base_path = Path(detected_base).resolve()

    if not base_path.exists():
        raise FileNotFoundError(f"No existe ruta base: {base_path}")

    metadata = build_metadata_from_existing_files(base_path, args.limit)

    print(f"Base path: {base_path}")
    print(f"Candidatos encontrados: {len(metadata)}")

    if not metadata:
        print("No se encontraron archivos compatibles para sembrar BD.")
        return

    for item in metadata[: min(5, len(metadata))]:
        print(f" - {item['NASA_ID']} ({item['CAMARA']})")

    if args.dry_run:
        print("Dry-run finalizado sin escribir en BD.")
        return

    processor = HybridOptimizedProcessor(
        database_path=str(DATABASE_PATH), batch_size=75
    )

    prepared_data = processor._prepare_data_from_organized_files(
        metadata, str(base_path)
    )
    print(f"Registros preparados con archivo existente: {len(prepared_data)}")

    if not prepared_data:
        print("No hay rutas válidas de archivos para insertar en BD.")
        return

    processor._write_to_database_optimized(prepared_data)
    print(
        f"Siembra completada para {len(prepared_data)} registros (sin redescargar; deduplicación por NASA_ID)."
    )


if __name__ == "__main__":
    main()
