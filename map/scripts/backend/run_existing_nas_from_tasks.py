#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(Path(__file__).resolve().parents[1] / "utils"))

from imageProcessor import HybridOptimizedProcessor, verificar_destination_descarga
from extract_enriched_metadata import extract_metadata_enriquecido
from task_api_client import process_task_scheduled, get_last_task_stats


DATABASE_PATH = str(PROJECT_ROOT / "map" / "db" / "metadata.db")


def _extract_nasa_id(result: Dict) -> Optional[str]:
    filename = result.get("images.filename")
    if not filename:
        return None
    nasa_id = filename.split(".")[0].strip()
    return nasa_id or None


def _exists_in_nas(base_path: Path, nasa_id: str) -> bool:
    patterns = [f"{nasa_id}.JPG", f"{nasa_id}.jpg", f"{nasa_id}.TIFF", f"{nasa_id}.tif"]
    for pattern in patterns:
        if next(base_path.rglob(pattern), None) is not None:
            return True
    return False


def _find_existing_path(base_path: Path, nasa_id: str) -> Optional[str]:
    patterns = [f"{nasa_id}.JPG", f"{nasa_id}.jpg", f"{nasa_id}.TIFF", f"{nasa_id}.tif"]
    for pattern in patterns:
        match = next(base_path.rglob(pattern), None)
        if match is not None:
            return str(match)
    return None


async def run(tasks_file: str, limit: int) -> None:
    tasks_path = Path(tasks_file)
    if not tasks_path.is_absolute():
        tasks_path = Path.cwd() / tasks_path

    if not tasks_path.exists():
        raise FileNotFoundError(f"No se encontró archivo de tasks: {tasks_path}")

    with tasks_path.open("r", encoding="utf-8") as f:
        tasks = json.load(f)

    if not isinstance(tasks, list) or not tasks:
        raise ValueError("El archivo de tasks está vacío o no tiene formato lista")

    base_path_str, _, mode = verificar_destination_descarga()
    base_path = Path(base_path_str)

    print(" PIPELINE NAS EXISTENTE (sin redescargar)")
    print(f" Modo: {mode}")
    print(f" Ruta imágenes: {base_path}")
    print(f" Tasks a consultar: {len(tasks)}")

    results_nas_existing: List[Dict] = []

    for task in tasks:
        task_id = task.get("id", "unknown")
        print(f"\n Consultando API para task: {task_id}")

        results_nuevos = await process_task_scheduled(task)
        stats = get_last_task_stats()
        print(
            f"  Raw={stats.get('total_results', 0)} | Unique={stats.get('unique_results', len(results_nuevos))} | New(vs DB)={stats.get('new_results', len(results_nuevos))}"
        )

        for result in results_nuevos:
            nasa_id = _extract_nasa_id(result)
            if not nasa_id:
                continue

            if _exists_in_nas(base_path, nasa_id):
                results_nas_existing.append(result)
                if limit > 0 and len(results_nas_existing) >= limit:
                    break

        if limit > 0 and len(results_nas_existing) >= limit:
            break

    print(f"\n Candidatos existentes en NAS encontrados: {len(results_nas_existing)}")

    if not results_nas_existing:
        print("No se encontraron candidatos en NAS para procesar.")
        return

    print(" Ejecutando extracción de metadatos enriquecidos...")
    metadata = extract_metadata_enriquecido(results_nas_existing)
    print(f" Metadatos enriquecidos: {len(metadata)}")

    if not metadata:
        print("No se obtuvieron metadatos enriquecidos para escribir en BD.")
        return

    processor = HybridOptimizedProcessor(database_path=DATABASE_PATH, batch_size=75)
    prepared_data = processor._prepare_data_from_organized_files(
        metadata, str(base_path)
    )

    for item in prepared_data:
        if item.get("path"):
            continue
        nasa_id = item.get("nasa_id")
        if not nasa_id:
            continue
        existing_path = _find_existing_path(base_path, nasa_id)
        if existing_path:
            item["path"] = existing_path

    prepared_existing = [item for item in prepared_data if item.get("path")]

    print(f" Registros con path existente para BD: {len(prepared_existing)}")
    if not prepared_existing:
        print("No hay registros con ruta válida en NAS para insertar.")
        return

    processor._write_to_database_optimized(prepared_existing)
    print(
        f" BD poblada desde NAS existente: {len(prepared_existing)} registros intentados"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta API + procesa solo imágenes que ya existen en NAS para poblar BD"
    )
    parser.add_argument("tasks_file", help="Ruta al JSON de tasks")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Máximo de imágenes existentes en NAS a procesar (0 = sin límite)",
    )
    args = parser.parse_args()

    asyncio.run(run(args.tasks_file, args.limit))


if __name__ == "__main__":
    main()
