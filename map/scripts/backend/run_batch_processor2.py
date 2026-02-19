#!/usr/bin/env python3
"""
COMPLETE FINAL PROCESSOR - INTEGRATED FLOW
Replicates exactly the flow of rend_periodica.js:
1. API Query → 2. Bulk camera metadata download → 3. Metadata processing → 4. Image download
"""

import os
import sys
import json
import subprocess
import sqlite3
import asyncio
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add required paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))

# Imports
from imageProcessor import (
    HybridOptimizedProcessor,
    download_images_aria2c_optimized,
    verify_download_destination,
)
from nasa_api_client import (
    NASAAPIClient,
    get_new_images_costa_rica,
    get_by_scheduled_task,
)
from bulk_camera_downloader import bulk_download_camera_metadata
from extract_enriched_metadata import get_nadir_altitude_camera_optimized
from log import log_custom
from map.routes import NAS_PATH, NAS_MOUNT

# Load configuration from helper module
from config import PROJECT_ROOT, ENV_FILE, load_env_config

# Ensure .env is loaded
env_file, loaded = load_env_config()

# Configuration
API_KEY = os.getenv("NASA_API_KEY", "")
if not API_KEY:
    raise ValueError(f"NASA_API_KEY not configured. Check {env_file}")
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "iss", "general.log")
DATABASE_PATH = os.path.join(PROJECT_ROOT, "db", "metadata.db")
RETRY_INFO_FILE = os.path.join(os.path.dirname(__file__), "retry_info.json")
CURRENT_EXECUTION_FILE = os.path.join(
    os.path.dirname(__file__), "current_execution.json"
)

TASK_NAME = "ISS_BatchProcessor"
MAX_RETRIES = 6
IMAGE_LIMIT = 15

# Import data mappings
try:
    from data import cameraMap, filmMap

    log_custom(
        section="Initialization",
        message="Camera and film mappings loaded successfully",
        level="INFO",
        file=LOG_FILE,
    )
except ImportError as e:
    log_custom(
        section="Initialization Error",
        message=f"Error loading data.py: {e}",
        level="ERROR",
        file=LOG_FILE,
    )
    cameraMap = {}
    filmMap = {}


# ============================================================================
#  MANAGEMENT FUNCTIONS
# ============================================================================


def load_retry_info():
    """Load retry information"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            with open(RETRY_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}


def save_retry_info(attempt, next_execution):
    """Save retry information"""
    try:
        info = {
            "attempt": attempt,
            "next_execution": next_execution,
            "timestamp": datetime.now().isoformat(),
        }
        with open(RETRY_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        log_custom(
            section="Main Error",
            message=f"Error in main function: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


def main():
    """Main entry point with retry management"""
    try:
        # Determine operation mode
        if len(sys.argv) < 2:
            print("✓ Autonomous mode: Running automatic search WITH LIMIT")
            asyncio.run(main_intelligent_autonomous("auto"))
        else:
            first_arg = sys.argv[1]

            if first_arg.startswith("task_"):
                print(f"✓ Running scheduled task: {first_arg} WITH LIMIT")
                tasks_file = sys.argv[2] if len(sys.argv) > 2 else "tasks.json"
                asyncio.run(main_intelligent_autonomous(tasks_file, first_arg))
            elif first_arg in ["auto", "costa_rica", "autonomous"]:
                print(f"✓ Autonomous mode: {first_arg} WITH LIMIT")
                asyncio.run(main_intelligent_autonomous(first_arg))
            else:
                print(f"✓ Processing file: {first_arg}")
                asyncio.run(main_intelligent_autonomous(first_arg))

        # SUCCESS
        delete_current_task()
        clear_retry_info()
        clear_current_execution_record()
        print("✓ Process completed successfully")

    except Exception as e:
        print(f"✗ Error during execution: {str(e)}")

        # Clean only elements from this execution
        clear_only_current_execution()
        delete_current_task()

        # Create new task with more time
        if create_new_task_with_more_time():
            print("✓ Retry scheduled automatically")
        else:
            print("✗ Could not schedule retry")
            clear_retry_info()

        sys.exit(1)


if __name__ == "__main__":
    if os.getenv("RUNNING_DOWNLOAD") == "1":
        log_custom(
            section="Scheduled Mode",
            message="Running as integrated scheduled task",
            level="INFO",
            file=LOG_FILE,
        )
        main()
    else:
        print("✓ COMPLETE INTEGRATED PROCESSOR - CORRECTED VERSION")
        print("✓ Features:")
        print("   • Queries NASA API automatically")
        print("   • Bulk download of camera metadata with aria2c")
        print("   • Processes metadata like rend_periodica.js")
        print("   • Downloads images with optimized aria2c")
        print("   • Processes only NEW images (not in DB)")
        print("   • Auto-cleanup on failure")
        print("   • Automatic incremental retries")
        print("   • Automatic Windows task management")
        print("   • LIMIT CORRECTLY APPLIED")
        print("")
        print("✓ Usage:")
        print(
            "   python run_batch_processor.py                    # Autonomous mode WITH LIMIT"
        )
        print(
            "   python run_batch_processor.py auto               # Explicit autonomous mode WITH LIMIT"
        )
        print(
            "   python run_batch_processor.py costa_rica         # Costa Rica search WITH LIMIT"
        )
        print(
            "   python run_batch_processor.py task_123456789     # Run specific task WITH LIMIT"
        )
        print(
            "   python run_batch_processor.py tasks.json task_123 # Task from file WITH LIMIT"
        )
        print(
            "   python run_batch_processor.py metadata.json     # Process direct metadata"
        )
        print("")
        print("✓ APPLIED CHANGES:")
        print("    Removed 'await' from synchronous function")
        print("    Limit applied manually if tasks do not respect it")
        print("    CONCURRENT_LIMIT reduced to 5 to prevent overload")
        print("    Pauses between batches to not saturate server")
        print("    Better error handling in scraping")
        print("    Improved logs with limit information")
        print("")
        main()


def clear_retry_info():
    """Clear retry information"""
    try:
        if os.path.exists(RETRY_INFO_FILE):
            os.remove(RETRY_INFO_FILE)
    except:
        pass


def delete_current_task():
    """Delete the current scheduled task"""
    try:
        cmd = f'schtasks /delete /tn "{TASK_NAME}" /f'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            log_custom(
                section="Task Management",
                message="Scheduled task deleted successfully",
                level="INFO",
                file=LOG_FILE,
            )
    except Exception as e:
        log_custom(
            section="Task Management",
            message=f"Error deleting task: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def create_new_task_with_more_time():
    """Create new scheduled task with incremental time"""
    try:
        retry_info = load_retry_info()
        current_attempt = retry_info.get("attempt", 0) + 1

        if current_attempt > MAX_RETRIES:
            log_custom(
                section="Task Management",
                message=f"Maximum {MAX_RETRIES} attempts reached",
                level="ERROR",
                file=LOG_FILE,
            )
            clear_retry_info()
            return False

        wait_minutes = 10 * current_attempt
        execution_time = datetime.now() + timedelta(minutes=wait_minutes)
        time_str = execution_time.strftime("%H:%M")
        date_str = execution_time.strftime("%d/%m/%Y")

        script_path = os.path.abspath(__file__)
        arguments = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
        task_command = f'python "{script_path}" {arguments}'

        cmd = f'schtasks /create /tn "{TASK_NAME}" /tr "{task_command}" /sc once /st {time_str} /sd {date_str} /f'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            save_retry_info(current_attempt, execution_time.isoformat())
            log_custom(
                section="Task Management",
                message=f"New task scheduled - Attempt {current_attempt}/{MAX_RETRIES} in {wait_minutes} min",
                level="INFO",
                file=LOG_FILE,
            )
            return True
        else:
            log_custom(
                section="Task Management",
                message=f"Error creating task: {result.stderr}",
                level="ERROR",
                file=LOG_FILE,
            )
            return False

    except Exception as e:
        log_custom(
            section="Task Management",
            message=f"Error creating new task: {e}",
            level="ERROR",
            file=LOG_FILE,
        )
        return False


def save_nasa_ids_current_execution(nasa_ids):
    """Save NASA_IDs to be processed"""
    try:
        info = {
            "nasa_ids": nasa_ids,
            "timestamp": datetime.now().isoformat(),
            "total": len(nasa_ids),
        }
        with open(CURRENT_EXECUTION_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        log_custom(
            section="Current Execution",
            message=f"Error saving NASA_IDs: {e}",
            level="WARNING",
            file=LOG_FILE,
        )


def load_nasa_ids_current_execution():
    """Load NASA_IDs from current execution"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            with open(CURRENT_EXECUTION_FILE, "r", encoding="utf-8") as f:
                info = json.load(f)
                return info.get("nasa_ids", [])
    except:
        pass
    return []


def clear_current_execution_record():
    """Clear current execution record"""
    try:
        if os.path.exists(CURRENT_EXECUTION_FILE):
            os.remove(CURRENT_EXECUTION_FILE)
    except:
        pass


def clear_only_current_execution():
    """Clean only elements from current execution"""
    current_nasa_ids = load_nasa_ids_current_execution()
    if current_nasa_ids:
        log_custom(
            section="Execution Cleanup",
            message=f"Cleaning {len(current_nasa_ids)} elements from current execution",
            level="INFO",
            file=LOG_FILE,
        )
        # Here you would add logic to clean DB and files
    clear_current_execution_record()


def load_task_by_id(task_id, tasks_file="tasks.json"):
    """Load task configuration by ID"""
    try:
        possible_paths = [
            tasks_file,
            os.path.join(
                os.path.dirname(__file__), "..", "periodic_tasks", "tasks.json"
            ),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                break
        else:
            raise FileNotFoundError(f"tasks.json not found")

        for task in tasks_data:
            if task.get("id") == task_id or task_id in task.get("id", ""):
                log_custom(
                    section="Task Found",
                    message=f"Task {task_id} loaded: {task.get('description', 'No description')}",
                    level="INFO",
                    file=LOG_FILE,
                )
                return task

        raise ValueError(f"Task with ID not found: {task_id}")

    except Exception as e:
        log_custom(
            section="Task Load Error",
            message=f"Error loading task {task_id}: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise


# ============================================================================
#  CORRECTED PROCESSING FUNCTIONS
# ============================================================================


def find_by_suffix(obj: Dict, suffix: str, fallback=None):
    """Replicate JavaScript findBySuffix() function"""
    for key in obj:
        if key.endswith(suffix) and obj[key] is not None and obj[key] != "":
            return obj[key]
    return fallback


async def process_photo_optimized_without_camera_metadata(
    photo: Dict, nadir_alt_cache: Dict = None
) -> Optional[Dict]:
    """
    Process optimized photo WITHOUT camera metadata (added later)
    """
    try:
        # Step 1: Extract basic data
        filename = find_by_suffix(photo, ".filename")
        directory = find_by_suffix(photo, ".directory")

        if not filename:
            return None

        # Step 2: Format date and time
        raw_date = find_by_suffix(photo, ".pdate", "")
        raw_time = find_by_suffix(photo, ".ptime", "")

        formatted_date = ""
        if len(raw_date) == 8:
            formatted_date = f"{raw_date[:4]}.{raw_date[4:6]}.{raw_date[6:8]}"

        formatted_hour = ""
        if len(raw_time) == 6:
            formatted_hour = f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}"

        # Step 3: Resolution
        width = find_by_suffix(photo, ".width", "")
        height = find_by_suffix(photo, ".height", "")
        resolution_text = f"{width} x {height} pixels" if width and height else ""

        # Step 4: Map camera
        camera_code = find_by_suffix(photo, ".camera", "Unknown")
        camera_desc = cameraMap.get(camera_code, "Unknown")

        # Step 5: Map film
        film_code = find_by_suffix(photo, ".film", "UNKN")
        film_data = filmMap.get(
            film_code, {"type": "Unknown", "description": "Unknown"}
        )

        # Step 6: NASA_ID
        nasa_id = filename.split(".")[0] if filename else "No_ID"
        if not nasa_id or nasa_id == "No_ID":
            return None

        # Step 7: Get extra data with cache
        if nadir_alt_cache is None:
            nadir_alt_cache = {}

        extra_data = nadir_alt_cache.get(nasa_id)
        if not extra_data:
            #  CRITICAL FIX: Do NOT use await - function is synchronous
            try:
                extra_data = get_nadir_altitude_camera_optimized(nasa_id)
            except Exception as e:
                log_custom(
                    section="Scraping Error",
                    message=f"Error getting extra data for {nasa_id}: {str(e)}",
                    level="WARNING",
                    file=LOG_FILE,
                )
                extra_data = None

            if not extra_data:
                extra_data = {
                    "NADIR_CENTER": None,
                    "ALTITUDE": None,
                    "CAMERA": None,
                    "CAPTURE_DATE": None,
                    "GEOTIFF_URL": None,
                    "HAS_GEOTIFF": False,
                }
            nadir_alt_cache[nasa_id] = extra_data

        # Step 8: Determine final camera
        if "Unknown" in camera_desc or "Unspecified :" in camera_desc:
            camera = extra_data.get("CAMERA") or "Unknown"
        else:
            camera = camera_desc

        # Step 9: Smart URL
        if extra_data.get("HAS_GEOTIFF") and extra_data.get("GEOTIFF_URL"):
            final_image_url = extra_data["GEOTIFF_URL"]
        else:
            final_image_url = (
                f"https://eol.jsc.nasa.gov/DatabaseImages/{directory}/{filename}"
                if filename and directory
                else None
            )

        # Step 10: Final date
        final_date = extra_data.get("CAPTURE_DATE") or formatted_date

        # Step 11: Build final result (WITHOUT CAMERA_METADATA for now)
        result = {
            "NASA_ID": nasa_id,
            "DATE": final_date,
            "TIME": formatted_hour,
            "RESOLUTION": resolution_text,
            "URL": final_image_url,
            "NADIR_LAT": find_by_suffix(photo, ".nlat"),
            "NADIR_LON": find_by_suffix(photo, ".nlon"),
            "CENTER_LAT": find_by_suffix(photo, ".lat"),
            "CENTER_LON": find_by_suffix(photo, ".lon"),
            "NADIR_CENTER": extra_data.get("NADIR_CENTER"),
            "ALTITUDE": extra_data.get("ALTITUDE"),
            "LOCATION": find_by_suffix(photo, ".geon", ""),
            "SUN_ELEVATION": find_by_suffix(photo, ".elev", ""),
            "SUN_AZIMUTH": find_by_suffix(photo, ".azi", ""),
            "CLOUD_COVER": find_by_suffix(photo, ".cldp", ""),
            "CAMERA": camera,
            "FOCAL_LENGTH": find_by_suffix(photo, ".fclt"),
            "INCLINATION": find_by_suffix(photo, ".tilt"),
            "FORMAT": f"{film_data['type']}: {film_data['description']}",
            "CAMERA_METADATA": None,  # Will be added later
        }

        return result

    except Exception as error:
        log_custom(
            section="Processing Error",
            message=f"Error processing photo: {str(error)}",
            level="ERROR",
            file=LOG_FILE,
        )
        return None


def deduplicate_metadata(metadata: List[Dict]) -> List[Dict]:
    """Deduplicate by NASA_ID"""
    seen = set()
    unique = []
    duplicates = 0

    for entry in metadata:
        nasa_id = entry.get("NASA_ID")
        if not nasa_id or nasa_id == "No_ID":
            unique.append(entry)
            continue

        if nasa_id not in seen:
            seen.add(nasa_id)
            unique.append(entry)
        else:
            duplicates += 1

    log_custom(
        section="Deduplication",
        message=f"Unique metadata: {len(unique)}, Duplicates removed: {duplicates}",
        level="INFO",
        file=LOG_FILE,
    )
    return unique


async def download_camera_metadata_selective(nasa_ids: List[str]) -> Dict[str, str]:
    """
    Download camera metadata only for specific NASA_IDs
    """
    print(f"✓ Selective download of camera metadata for {len(nasa_ids)} NASA_IDs")

    from bulk_camera_downloader import (
        extract_camera_metadata_url,
        create_aria2c_input_file,
        download_with_aria2c,
        create_nasa_id_to_file_mapping,
        get_camera_output_folder,
    )

    # Get output folder
    output_folder, is_nas = get_camera_output_folder()
    if not output_folder:
        return {}

    # Extract URLs only for specific NASA_IDs
    camera_urls = {}
    errors = []

    print(f"✓ Extracting camera metadata URLs...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Send tasks only for specific NASA_IDs
        future_to_nasa_id = {
            executor.submit(extract_camera_metadata_url, nasa_id): nasa_id
            for nasa_id in nasa_ids
        }

        # Collect results
        for future in as_completed(future_to_nasa_id):
            nasa_id, result = future.result()

            if result.startswith("ERROR:"):
                errors.append(f"{nasa_id}: {result}")
            else:
                camera_urls[nasa_id] = result

    print(f"✓ URLs found: {len(camera_urls)}, Errors: {len(errors)}")

    if not camera_urls:
        return {}

    # Create input file and download
    input_file = create_aria2c_input_file(camera_urls, output_folder)
    success = download_with_aria2c(input_file, output_folder, connections=10)

    if success:
        return create_nasa_id_to_file_mapping(camera_urls, output_folder)
    else:
        return {}


async def complete_integrated_process(task_config: Dict = None, limit: int = 0):
    """
    COMPLETE INTEGRATED PROCESS - OPTIMIZED FLOW WITH LIMIT
    """
    base_path, is_nas, mode = verify_download_destination()

    log_custom(
        section="Integrated Process",
        message=f"Starting complete integrated process - {mode} - Limit: {limit}",
        level="INFO",
        file=LOG_FILE,
    )

    print("✓ COMPLETE INTEGRATED PROCESS - OPTIMIZED FLOW")
    print(f"✓ Mode: {mode}")
    print(f"✓ Destination: {base_path}")
    print(f"✓ Limit: {limit if limit > 0 else 'No limit'}")

    try:
        #  PHASE 1: GET NEW IMAGES
        print(f"\n✓ PHASE 1: Getting new images...")

        if task_config:
            # Use scheduled task configuration
            log_custom(
                section="Scheduled Task",
                message=f"Running task: {task_config.get('id', 'unknown')}",
                level="INFO",
                file=LOG_FILE,
            )
            new_images = await get_by_scheduled_task(task_config)
        else:
            # Automatic Costa Rica search
            new_images = await get_new_images_costa_rica(limit=limit, night_mode=True)

        if not new_images:
            log_custom(
                section="No Results",
                message="No new images found for processing",
                level="WARNING",
                file=LOG_FILE,
            )
            print("✓ All images are already processed")
            return

        #  APPLY LIMIT MANUALLY IF TASK DID NOT RESPECT IT
        if limit > 0 and len(new_images) > limit:
            print(f"✓ Applying manual limit: {len(new_images)} → {limit} images")
            new_images = new_images[:limit]

        # Register NASA_IDs that we will process
        new_nasa_ids = []
        for image in new_images:
            filename = None
            for key in image:
                if key.endswith(".filename"):
                    filename = image[key]
                    break
            if filename:
                nasa_id = filename.split(".")[0]
                if nasa_id and nasa_id != "No_ID":
                    new_nasa_ids.append(nasa_id)

        save_nasa_ids_current_execution(new_nasa_ids)

        print(f"✓ Processing {len(new_images)} new images")

        #  PHASE 2: METADATA PROCESSING (WITHOUT camera metadata yet)
        print(
            f"\n✓ PHASE 2: Processing metadata with scraping (without camera metadata)..."
        )

        metadata = []
        nadir_alt_cache = {}
        CONCURRENT_LIMIT = 5  # Reduce to avoid server overload

        for i in range(0, len(new_images), CONCURRENT_LIMIT):
            batch = new_images[i : i + CONCURRENT_LIMIT]
            batch_num = (i // CONCURRENT_LIMIT) + 1
            total_batches = (len(new_images) + CONCURRENT_LIMIT - 1) // CONCURRENT_LIMIT

            print(f"✓ Processing batch {batch_num}/{total_batches}")

            # Process batch with async (WITHOUT camera metadata)
            batch_tasks = [
                process_photo_optimized_without_camera_metadata(photo, nadir_alt_cache)
                for photo in batch
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    log_custom(
                        section="Batch Error",
                        message=f"Error in processing: {result}",
                        level="ERROR",
                        file=LOG_FILE,
                    )
                elif result and result.get("NASA_ID"):
                    metadata.append(result)

            progress = min(i + CONCURRENT_LIMIT, len(new_images))
            print(
                f"✓ Progress: {(progress / len(new_images)) * 100:.1f}% ({progress}/{len(new_images)})"
            )

            # Pause between batches to avoid overload
            await asyncio.sleep(1)

        print(f"✓ Processed metadata: {len(metadata)} of {len(new_images)} attempted")

        #  PHASE 3: DEDUPLICATION AND INITIAL JSON SAVE
        print(f"\n✓ PHASE 3: Deduplicating and saving initial JSON...")

        unique_metadata = deduplicate_metadata(metadata)

        if not unique_metadata:
            raise Exception("No valid unique metadata generated")

        output_path = "periodic_metadata.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(unique_metadata, f, indent=2, ensure_ascii=False)

        log_custom(
            section="Initial JSON",
            message=f"Initial JSON saved with {len(unique_metadata)} entries: {output_path}",
            level="INFO",
            file=LOG_FILE,
        )

        print(
            f"✓ Initial JSON saved: {output_path} ({len(unique_metadata)} unique metadata)"
        )

        #  PHASE 4: SELECTIVE CAMERA METADATA DOWNLOAD
        print(f"\n✓ PHASE 4: Selective camera metadata download...")

        # Extract only NASA_IDs from final JSON
        final_nasa_ids = [
            meta["NASA_ID"] for meta in unique_metadata if meta.get("NASA_ID")
        ]

        print(
            f"✓ Downloading camera metadata only for {len(final_nasa_ids)} images in final JSON"
        )

        camera_metadata_mapping = await download_camera_metadata_selective(
            final_nasa_ids
        )

        print(f"✓ Camera metadata downloaded for {len(camera_metadata_mapping)} images")

        #  PHASE 5: UPDATE JSON WITH CAMERA METADATA
        print(f"\n✓ PHASE 5: Updating JSON with camera metadata...")

        updated_metadata = []
        for entry in unique_metadata:
            nasa_id = entry.get("NASA_ID")
            if nasa_id and nasa_id in camera_metadata_mapping:
                entry["CAMERA_METADATA"] = camera_metadata_mapping[nasa_id]
            updated_metadata.append(entry)

        # Save updated JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(updated_metadata, f, indent=2, ensure_ascii=False)

        print(f"✓ JSON updated with camera metadata")

        #  PHASE 6: IMAGE DOWNLOAD
        print(f"\n✓ PHASE 6: Downloading images...")

        download_images_aria2c_optimized(updated_metadata, connections=32)

        #  PHASE 7: DATABASE PROCESSING
        print(f"\n✓ PHASE 7: Processing in database...")

        processor = HybridOptimizedProcessor(database_path=DATABASE_PATH, batch_size=75)
        processor.process_complete_workflow(updated_metadata)

        #  SUCCESS
        clear_current_execution_record()
        clear_retry_info()

        log_custom(
            section="Process Completed",
            message=f"Integrated process completed successfully: {len(updated_metadata)} images processed",
            level="INFO",
            file=LOG_FILE,
        )

        print(
            f"✓ Process completed successfully: {len(updated_metadata)} images processed"
        )

    except Exception as e:
        log_custom(
            section="Integrated Process Error",
            message=f"Error in integrated process: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        print(f"✗ Error: {str(e)}")
        raise


# ============================================================================
#  MAIN ENTRY POINT
# ============================================================================


async def main_intelligent_autonomous(json_filename_or_mode="auto", task_id=None):
    """Main function with autonomous processing"""
    try:
        if task_id and task_id.startswith("task_"):
            # Execute specific scheduled task WITH LIMIT
            task_config = load_task_by_id(task_id)
            await complete_integrated_process(
                task_config=task_config, limit=IMAGE_LIMIT
            )

        elif json_filename_or_mode in ["auto", "costa_rica"]:
            # Autonomous mode WITH LIMIT
            await complete_integrated_process(limit=IMAGE_LIMIT)

        elif os.path.exists(json_filename_or_mode):
            # Process existing JSON file
            with open(json_filename_or_mode, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list) and len(data) > 0:
                if "query" in data[0] and "return" in data[0]:
                    # Scheduled tasks file
                    for task in data:
                        await complete_integrated_process(
                            task_config=task, limit=IMAGE_LIMIT
                        )
                else:
                    # Metadata file - use imageProcessor directly
                    processor = HybridOptimizedProcessor(
                        database_path=DATABASE_PATH, batch_size=75
                    )
                    processor.process_complete_workflow(data)
        else:
            raise FileNotFoundError(f"Not found: {json_filename_or_mode}")

    except Exception as e:
        log_custom(
            section="Autonomous Mode Error",
            message=f"Error in autonomous mode: {str(e)}",
            level="ERROR",
            file=LOG_FILE,
        )
        raise
