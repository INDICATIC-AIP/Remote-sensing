import sys
import os
import requests
import gzip
import shutil
import json
from bs4 import BeautifulSoup
import re

# Obtener la ruta del directorio del script
current_dir = os.path.dirname(os.path.abspath(__file__))
script_dir = os.path.dirname(current_dir)

json_path = os.path.join(script_dir, "automatica", "metadatos.json")
enlaces_highres = os.path.join(script_dir, "automatica", "enlaces_highres.txt")  #  ruta corregida
# Cargar el JSON existente si existe
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as json_file:
        try:
            existing_data = json.load(json_file)
            if not isinstance(existing_data, list):
                existing_data = []
        except json.JSONDecodeError:
            existing_data = []
else:
    existing_data = []

def compress_file(input_file, output_file):
    """Comprime un archivo .txt en formato .gz."""
    with open(input_file, 'rb') as f_in:
        with gzip.open(output_file, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

def is_file_unique(temp_file, folder):
    """Compara un archivo comprimido temporal con los existentes en una carpeta."""
    for existing_file in os.listdir(folder):
        existing_path = os.path.join(folder, existing_file)
        if os.path.isfile(existing_path):
            with gzip.open(existing_path, 'rb') as f_existing, open(temp_file, 'rb') as f_temp:
                if f_existing.read() == f_temp.read():
                    return False
    return True

def clean_coordinates(coord):
    """Convierte coordenadas como '7.0° N' o '81.8° W' en números."""
    try:
        if not coord or len(coord) < 3:
            return None
        value = float(re.search(r"[-+]?[0-9]*\.?[0-9]+", coord).group())
        direction = coord[-1].upper()
        if direction in ("S", "W"):
            value = -value
        return value
    except (ValueError, AttributeError):
        return None

def extract_number(value):
    """Extrae el primer número de un texto, ignorando otros caracteres."""
    try:
        match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value)
        return float(match.group(0)) if match else None
    except (ValueError, AttributeError):
        return None

def extract_coordinates(soup, selector):
    """Extrae coordenadas (latitud/longitud) desde un selector en el HTML."""
    element = soup.select_one(selector)
    if element:
        value = element.find_next_sibling(string=True).strip()
        coords = [v.strip() for v in value.split(",")]
        if len(coords) == 2:
            return clean_coordinates(coords[0]), clean_coordinates(coords[1])
    return None, None

def extract_metadata(html_file):
    """ Extrae los metadatos de un archivo HTML. """
    with open(html_file, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    def get_metadata_value(selector):
        """ Extrae y limpia un valor basado en un selector CSS. """
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else "No encontrado"



    def get_URL(nasa_id):
        with open(enlaces_highres, 'r', encoding='utf-8') as archivo:
            for linea in archivo:
                if nasa_id in linea:
                    return linea.strip()  
        return "NASA_ID NO ENCONTRADO"

    nadir_center_el = soup.select_one("em:has(b:-soup-contains('Nadir to Photo Center:'))")
    if nadir_center_el and nadir_center_el.b and nadir_center_el.b.next_sibling:
        raw_text = nadir_center_el.b.next_sibling.strip()
        nadir_center_value = extract_number(raw_text)
    else:
        nadir_center_value = None

    metadata = {
        "NASA_ID": get_metadata_value("table.table tr:has(td b:-soup-contains('NASA Photo ID')) td:last-child"),
        "FECHA": get_metadata_value("table.table tr:has(td b:-soup-contains('Date taken')) td:last-child"),
        "HORA": get_metadata_value("table.table tr:has(td b:-soup-contains('Time taken')) td:last-child"),
        "RESOLUCION": get_metadata_value("div#myModal1 td[style='text-align:right'] h5"),
        "URL" :  None,
        "NADIR_LAT": None,
        "NADIR_LON": None,
        "CENTER_LAT": None,
        "CENTER_LON": None,
        "NADIR_CENTER": None,
        "ALTITUD": None,
        "LUGAR": get_metadata_value("div#ImageDetails tr:has(td b:-soup-contains('Features:')) td:last-child"),
        "ELEVACION_SOL": extract_number(get_metadata_value("tr:has(td b:-soup-contains('Sun Elevation Angle')) td:last-child")),
        "AZIMUT_SOL": extract_number(get_metadata_value("tr:has(td b:-soup-contains('Sun Azimuth')) td:last-child")),
        "COBERTURA_NUBOSA": extract_number(get_metadata_value("tr:has(td b:-soup-contains('Cloud Cover Percentage')) td:last-child")),
        "CAMARA": get_metadata_value("div#CameraInformation tr:has(td b:-soup-contains('Camera:')) td:last-child"),
        "LONGITUD_FOCAL": extract_number(get_metadata_value("tr:has(td b:-soup-contains('Focal Length')) td:last-child")),
        "INCLINACION": get_metadata_value("div#CameraInformation tr:has(td b:-soup-contains('Camera Tilt')) td:last-child"),
        "FORMATO": get_metadata_value("div#CameraInformation tr:has(td b:-soup-contains('Format')) td:last-child"),
        "CAMARA_METADATA": None
    }

    metadata["URL"]  = get_URL(metadata["NASA_ID"])

    # Extraer coordenadas
    metadata["NADIR_LAT"], metadata["NADIR_LON"] = extract_coordinates(soup, "em:has(b:-soup-contains('Spacecraft nadir point:'))")
    metadata["CENTER_LAT"], metadata["CENTER_LON"] = extract_coordinates(soup, "em:has(b:-soup-contains('Photo center point:'))")

    # Extraer valor numérico (ej. "47.3") después del texto "Nadir to Photo Center:"
    nadir_center_el = soup.select_one("em:has(b:-soup-contains('Nadir to Photo Center:'))")
    if nadir_center_el and nadir_center_el.b and nadir_center_el.b.next_sibling:
        raw_text = nadir_center_el.b.next_sibling.strip()
        nadir_center_value = extract_number(raw_text)
    else:
        nadir_center_value = None
    metadata["NADIR_CENTER"] = nadir_center_value


    alt_el = soup.select_one("em:has(b:-soup-contains('Spacecraft Altitude'))")
    if alt_el:
    # Obtener todo el texto del elemento <em> y su texto adyacente
        full_text = alt_el.get_text(strip=True, separator=" ")
        altitud_valor = extract_number(full_text)
    else:
        altitud_valor = None
    metadata["ALTITUD"] = altitud_valor

    # Descargar el archivo .txt del botón
    button = soup.find("input", {"type": "button", "value": "View camera metadata"})
    if button and "onclick" in button.attrs:
        try:
            onclick_value = button["onclick"]
            start = onclick_value.find("('") + 2
            end = onclick_value.find("')", start)
            file_url = onclick_value[start:end]

            if file_url:
                output_folder = "scripts/camera_data"
                os.makedirs(output_folder, exist_ok=True)

                full_url = "https://eol.jsc.nasa.gov" + file_url
                response = requests.get(full_url)

                # Si la respuesta no es exitosa, lanzar un error controlado
                if response.status_code != 200:
                    raise requests.exceptions.RequestException(f"Error {response.status_code} al descargar el archivo.")

                temp_path = "temp_download.txt"
                compressed_temp_path = "temp_download.txt.gz"

                # Guardar y comprimir
                with open(temp_path, "wb") as txt_file:
                    txt_file.write(response.content)
                compress_file(temp_path, compressed_temp_path)
                os.remove(temp_path)

                # Comparar y guardar si es único
                if is_file_unique(compressed_temp_path, output_folder):
                    final_path = os.path.join(output_folder, os.path.basename(file_url) + ".gz")
                    os.rename(compressed_temp_path, final_path)
                    metadata["CAMARA_METADATA"] = final_path
                else:
                    os.remove(compressed_temp_path)
                    metadata["CAMARA_METADATA"] = "Duplicado no guardado"
            else:
                raise ValueError("URL del archivo de cámara no encontrada.")

        except Exception as e:
            print(f"Advertencia: No se pudo descargar el archivo de cámara ({e}). Continuando sin él.")
            metadata["CAMARA_METADATA"] = "No disponible"  # Ahora tiene un valor claro en vez de estar vacío

    else:
        print("Advertencia: No se encontró el botón de metadatos de cámara.")
        metadata["CAMARA_METADATA"] = "No disponible"


    return metadata

# Procesar múltiples archivos HTML pasados como argumentos
if len(sys.argv) < 2:
    print("Error: No se proporcionaron archivos HTML.")
    sys.exit(1)

for html_file in sys.argv[1:]:
    if not os.path.isfile(html_file):
        print(f"Error: El archivo {html_file} no existe. Omitiendo.")
        continue

    metadata = extract_metadata(html_file)

    # Verificar si el NASA_ID ya existe en el JSON
    if any(entry["NASA_ID"] == metadata["NASA_ID"] for entry in existing_data):
        print(f"NASA_ID {metadata['NASA_ID']} ya existe en el JSON. No se duplicará.")
    else:
        existing_data.append(metadata)  # Agregar nuevo metadato

# Guardar el JSON actualizado
with open(json_path, "w", encoding="utf-8") as json_file:
    json.dump(existing_data, json_file, ensure_ascii=False, indent=4)

print(f" Metadatos guardados en {json_path}")
sys.exit(0)