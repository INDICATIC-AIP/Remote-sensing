import sys
import json
import ee
from datetime import datetime
import os
from io import StringIO

# Import log_custom helper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils")))
from log import log_custom

if len(sys.argv) < 2:
    log_custom(
        "Usage Error",
        "Usage: generate_tiles | export_all | listar-candidatos-export | get_metadata YEAR | generate_metadata",
        "../logs/noaa/general.log",
    )
    sys.exit(1)

cmd = sys.argv[1]

if cmd == "generate_tiles":
    from noaa_processor import NOAAProcessor

    processor = NOAAProcessor()
    processor.generate_tiles_json()

elif cmd == "export_all":
    from noaa_processor import NOAAProcessor

    processor = NOAAProcessor()
    processor.export_imagenes_nuevas()

elif cmd == "listar-candidatos-export":
    from noaa_processor import set_silent_mode

    # Enable silent mode before creating the processor
    set_silent_mode(True)

    from noaa_processor import NOAAProcessor

    processor = NOAAProcessor()

    metadatos = processor._cargar_json("scripts/noaa/ui/noaa_metadata.json")
    resultados = []

    colecciones = [
        ("DMSP", ee.ImageCollection("NOAA/DMSP-OLS/NIGHTTIME_LIGHTS")),
        ("VIIRS", ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG")),
    ]

    for dataset, coleccion in colecciones:
        coleccion = coleccion.filterBounds(processor.region)
        ids = coleccion.aggregate_array("system:id").getInfo()
        times = coleccion.aggregate_array("system:time_start").getInfo()

        for full_id, t in zip(ids, times):
            id_ee = full_id.split("/")[-1]
            if id_ee in metadatos:
                continue

            fecha = datetime.utcfromtimestamp(t / 1000).strftime("%Y-%m-%d")
            resultados.append({"id": id_ee, "dataset": dataset, "fecha": fecha})

    #  SALIDA JSON LIMPIA A STDOUT (esto sí debe ser print)
    print(json.dumps(resultados, indent=2))

elif cmd == "get_metadata":
    from noaa_processor import set_silent_mode

    set_silent_mode(True)

    from noaa_processor import NOAAProcessor

    processor = NOAAProcessor()

    if len(sys.argv) < 3:
        log_custom(
            "Parameter Error",
            "Missing year argument",
            "ERROR",
            "../logs/noaa/general.log",
        )
        sys.exit(1)

    year = sys.argv[2]
    metadata = processor.get_metadata(year)

    if metadata:
        print(json.dumps(metadata, indent=2))  #  JSON debe ir a stdout
    else:
        print("null")  #  JSON debe ir a stdout

# Añadir este comando en noaa_commands.py

elif cmd == "generate_metadata":
    from noaa_processor import NOAAProcessor

    processor = NOAAProcessor()

    # Generate metadata_noaa.json
    success = processor.generate_metadata_file()

    if success:
        print("metadata_noaa.json generated successfully")
    else:
        print("Error generating metadata_noaa.json")
        sys.exit(1)

else:
    log_custom(
        "Command Error", "Unrecognized command", "ERROR", "../logs/noaa/general.log"
    )
