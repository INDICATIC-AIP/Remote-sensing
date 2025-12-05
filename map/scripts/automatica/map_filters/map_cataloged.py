import json
import requests
import sys
from bs4 import BeautifulSoup
import argparse
import urllib.parse
import re
import os
BASE_DIR = os.path.join(os.path.dirname(__file__))

CAMERA_MAPPING = {
    "Ansco Autoset": "AA",
    "Canon Digital IXUS 700": "C1",
    "Sony HDW-700 HDTV (High Definition Television)": "DV",
    "Kodak DCS460 Electronic Still Camera": "E2",
    "Kodak DCS660 Electronic Still Camera": "E3",
    "Kodak DCS760c Electronic Still Camera": "E4",
    "Hasselblad": "HB",
    "Linhof": "LH",
    "Maurer model 220G": "MA",
    "Maurer with Xenotar 80mm f/2.8 lens": "MS",
    "Nikon D1 Electronic Still Camera": "N1",
    "Nikon D2Xs Electronic Still Camera": "N2",
    "Nikon D3 Electronic Still Camera": "N3",
    "Nikon D3X Electronic Still Camera": "N4",
    "Nikon D3S Electronic Still Camera": "N5",
    "Nikon D4 Electronic Still Camera": "N6",
    "Nikon D800E Electronic Still Camera": "N7",
    "Nikon D5 Electronic Still Camera": "N8",
    "Nikon D850 Electronic Still Camera": "N9",
    "Nikon D6 Electronic Still Camera": "NA",
    "Nikon Z9 Electronic Still Camera": "NB",
    "Nikon 35mm film camera": "NK",
    "Rolleiflex": "RX",
    "Skylab Multispectral (S190A)": "SA",
    "Skylab Earth Terrain (S190B)": "SB",
}

def log_message(message):
    """Guarda logs en generated_url.txt para depuración."""
    with open( os.path.join(BASE_DIR, "generated_url.txt"), "a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")

def save_json(data):
    """Guarda los datos extraídos en combined_output.json"""
    output_file =  os.path.join(BASE_DIR, "combined_output.json")

    if not data:
        log_message(" No se encontraron datos para guardar en JSON.")
        return

    with open(output_file, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=4)

    log_message(f" Datos guardados en {output_file} ({len(data)} elementos)")

def parse_arguments():
    """Parsea los argumentos pasados al script y solo incluye los recibidos."""
    parser = argparse.ArgumentParser(description='Process cataloged search parameters')

    parser.add_argument('--camera-tilt', nargs="+", help="Camera tilt options")
    parser.add_argument('--cloud-cover', nargs="+", help="Cloud cover percentage")
    parser.add_argument('--months', nargs="+", help="Selected months")
    parser.add_argument('--min-focal-length', type=str, help="Minimum focal length")
    parser.add_argument('--max-focal-length', type=str, help="Maximum focal length")
    parser.add_argument('--min-sun-elevation', type=str, help="Minimum sun elevation angle")
    parser.add_argument('--max-sun-elevation', type=str, help="Maximum sun elevation angle")
    parser.add_argument('--cameras', nargs="+", help="Selected cameras")
    parser.add_argument('--film-classifications', nargs="+", help="Selected film classifications")
    parser.add_argument('--films', nargs="+", help="Selected films")
    parser.add_argument('--has-cloud-mask', action='store_true', help="Filter by cloud mask")
    parser.add_argument('--min-megapixels', type=str, help="Minimum megapixels")

    return parser.parse_args()


def extract_number(value):
    """Extrae el número de un string como '70mm' o '85 mm'."""
    if not value:
        return None
    match = re.search(r"\d+(\.\d+)?", value)
    return match.group(0) if match else None

def build_url(args):
    """Construye la URL de búsqueda con parámetros correctamente formateados."""
    base_url = "https://eol.jsc.nasa.gov/SearchPhotos/Technical.pl"
    
    # Diccionario base con los parámetros fijos
    url_params = {
        "SearchPublicCB": "on",
        "IncludePanCB": "on",
        "geon": "Panama",
        "SearchGeonCB": "on",
        "SearchFeatCB": "on"
    }

    if args.has_cloud_mask:
        url_params["HasCloudMask"] = "on"

    # Manejo de Camera Tilt
    if args.camera_tilt:
        tilt_mapping = {
            "Near Vertical": "tiltNV",
            "Low Oblique": "tiltLO",
            "High Oblique": "tiltHO"
        }
        for tilt in args.camera_tilt:
            if tilt in tilt_mapping:
                url_params[tilt_mapping[tilt]] = "on"

    # Manejo de Cloud Cover
    if args.cloud_cover:
        cover_mapping = {
            "No clouds present": "clouds0",
            "1-10%": "clouds10",
            "11-25%": "clouds25",
            "26-50%": "clouds50",
            "51-75%": "clouds75",
            "76-100%": "clouds100"
        }
        for cover in args.cloud_cover:
            if cover in cover_mapping:
                url_params[cover_mapping[cover]] = "on"

    # Parámetros con valores únicos
    # if args.min_focal_length:
    #     url_params["minfclt"] = args.min_focal_length
    # if args.max_focal_length:
    #     url_params["maxfclt"] = args.max_focal_length
    if args.min_focal_length:
        clean_min = extract_number(args.min_focal_length)
        if clean_min:
            url_params["minfclt"] = clean_min

    if args.max_focal_length:
        clean_max = extract_number(args.max_focal_length)
        if clean_max:
            url_params["maxfclt"] = clean_max

    if args.min_sun_elevation:
        url_params["minsun"] = args.min_sun_elevation
    if args.max_sun_elevation:
        url_params["maxsun"] = args.max_sun_elevation
    if args.min_megapixels:
        url_params["MinMegapixels"] = args.min_megapixels

    # Diccionario de conversión de meses
    month_mapping = {
        "January": "01", "February": "02", "March": "03", "April": "04",
        "May": "05", "June": "06", "July": "07", "August": "08",
        "September": "09", "October": "10", "November": "11", "December": "12"
    }

    if args.months:
        formatted_months = "%00".join([month_mapping[month] for month in args.months if month in month_mapping])
        if formatted_months:
            url_params["month"] = formatted_months  #  No usar `urlencode()` aquí

    if args.cameras:
        formatted_cameras = [CAMERA_MAPPING.get(camera, camera) for camera in args.cameras]
        url_params["camera"] = "%00".join(formatted_cameras)  #  No usar `urlencode()`

    if args.film_classifications:
        formatted_film_classes = "%00".join(args.film_classifications)
        url_params["filmnclass"] = formatted_film_classes  #  No usar `urlencode()`

    if args.films:
        formatted_films = "%00".join([film.split(":")[0] for film in args.films])
        url_params["film"] = formatted_films  #  No usar `urlencode()`

    # Construcción manual de la URL con parámetros correctamente formateados
    encoded_params = []
    for key, value in url_params.items():
        if "%00" in value:
            encoded_params.append(f"{key}={value}")  #  No usar `urllib.parse.quote()` aquí
        else:
            encoded_params.append(f"{key}={urllib.parse.quote(str(value))}")  #  Codificar solo valores normales

    final_url = f"{base_url}?{'&'.join(encoded_params)}"

    log_message(f"Generated URL: {final_url}")
    return final_url



def extract_table_data(html_content):
    """Extrae ID y miniaturas desde Table.pl."""
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="QueryResults")

    if not table:
        log_message(" No se encontró la tabla QueryResults en Table.pl.")
        return {}

    data = {}
    rows = table.find_all("tr")

    for index, row in enumerate(rows):
        cols = row.find_all("td")

        if len(cols) < 1:
            continue

        img_tag = cols[0].find("img")
        id_text = cols[2].text.strip()

        thumbnail_url = f"https://eol.jsc.nasa.gov{img_tag['src']}" if img_tag and "src" in img_tag.attrs else None
        data[id_text] = {"id": id_text, "thumbnail": thumbnail_url}

    return data

def extract_texttable_data(html_content):
    """Extrae ID, Latitud y Longitud desde TextTable.pl."""
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="QueryResults")

    if not table:
        log_message(" No se encontró la tabla QueryResults en TextTable.pl.")
        return {}

    data = {}
    rows = table.find_all("tr")

    for index, row in enumerate(rows):
        cols = row.find_all("td")

        if len(cols) < 4:
            continue

        try:
            id_link = cols[0].find("a")
            image_url = f"https://eol.jsc.nasa.gov/SearchPhotos/{id_link['href']}" if id_link and "href" in id_link.attrs else None
            id_text = id_link.text.strip() if id_link else None
            lat = float(cols[2].text.strip())
            lon = float(cols[3].text.strip())

            data[id_text] = {
                "latitude": lat,
                "longitude": lon,
                "image_url": image_url
            }

        except ValueError:
            continue

    return data

def main():
    """Función principal que obtiene datos de TextTable.pl y Table.pl y los combina."""
    log_message(" Iniciando ejecución del script...")
    args = parse_arguments()

    final_url = build_url(args)

    try:
        response = requests.get(final_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script")
        top_header = soup.find("h1", class_="top_header")
        if top_header and "Query Aborted" in top_header.text:
            reason_tag = top_header.find_next_sibling()
            reason = reason_tag.get_text(strip=True) if reason_tag else "Motivo desconocido"

            print(f"QueryAborted::{reason}")  # <== ESTO es clave para detectar en Node
            save_json([])
            return



        if script and "window.location.href" in script.text:
            start = script.text.find('"') + 1
            end = script.text.rfind('"')
            redirected_url = script.text[start:end]

            if not redirected_url.startswith("http"):
                redirected_url = f"https://eol.jsc.nasa.gov/SearchPhotos/{redirected_url}"

            log_message(f" Redirigiendo a: {redirected_url}")

            # Obtener `TextTable.pl` PRIMERO (Coordenadas y enlaces)
            text_table_url = redirected_url
            log_message(f" Accediendo a TextTable.pl: {text_table_url}")
            text_table_response = requests.get(text_table_url)
            text_table_response.raise_for_status()
            text_table_data = extract_texttable_data(text_table_response.text)

            # Obtener `Table.pl` DESPUÉS (Miniaturas)
            table_url = redirected_url.replace("TextTable.pl", "Table.pl") if "Table.pl" in redirected_url else redirected_url.replace("ShowQueryResults-", "ShowQueryResults-Table.pl")
            log_message(f" Accediendo a Table.pl: {table_url}")
            table_response = requests.get(table_url)
            table_response.raise_for_status()
            table_data = extract_table_data(table_response.text)

            # Unir ambos conjuntos de datos
            combined_data = []
            for id_text, text_entry in text_table_data.items():
                if id_text in table_data:
                    combined_entry = {**text_entry, **table_data[id_text]}
                else:
                    combined_entry = text_entry  # Si no tiene miniatura, solo se incluyen los datos de TextTable
                combined_data.append(combined_entry)

            # Guardar en JSON
            save_json(combined_data)

    except requests.exceptions.RequestException as e:
        log_message(f" Error en la solicitud HTTP: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
