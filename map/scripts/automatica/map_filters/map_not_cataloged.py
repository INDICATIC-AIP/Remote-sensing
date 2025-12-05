import os
import json
import requests
from bs4 import BeautifulSoup
import sys
import argparse

BASE_DIR = os.path.join(os.path.dirname(__file__))

def parse_arguments():
    """Parsea los argumentos pasados al script y solo incluye los recibidos."""
    parser = argparse.ArgumentParser(description='Process search parameters')

    # Se aceptan valores explícitos "on" o "off"
    parser.add_argument('--daytime', type=str, choices=['on', 'off'], default='off')
    parser.add_argument('--nighttime', type=str, choices=['on', 'off'], default='off')
    parser.add_argument('--dawndusk', type=str, choices=['on', 'off'], default='off')
    parser.add_argument('--HO', type=str, choices=['on', 'off'], default='off')
    parser.add_argument('--hasCloudMask', type=str, choices=['on', 'off'], default='off')

    return parser.parse_args()

def main():
    args = parse_arguments()

    print("Valores recibidos desde la línea de comandos:")
    print(f"daytime: {args.daytime}, nighttime: {args.nighttime}, dawndusk: {args.dawndusk}, HO: {args.HO}, hasCloudMask: {args.hasCloudMask}")

    # Base de la URL
    url_params = {
        "LowerLat": "6.6",
        "UpperLat": "10.5",
        "LeftLon": "-83.2",
        "RightLon": "-76.9",
        "UseNotCataloged": "on"
    }

    # Solo agregar parámetros si están en "on"
    if args.daytime == "on":
        url_params["daytime"] = "on"
    if args.nighttime == "on":
        url_params["nighttime"] = "on"
    if args.dawndusk == "on":
        url_params["dawndusk"] = "on"
    if args.HO == "on":
        url_params["IncludeHO"] = "on"
    if args.hasCloudMask == "on":
        url_params["HasCloudMask"] = "on"

    # Construcción dinámica de la URL
    html_url = "https://eol.jsc.nasa.gov/SearchPhotos/CoordinateRangeSearch.pl?" + "&".join(f"{key}={value}" for key, value in url_params.items())

    # Guardar la URL en un archivo para que la lea `renderer.js`
    url_file = os.path.join(BASE_DIR,"generated_url.txt")
    with open(url_file, "w", encoding="utf-8") as file:
        file.write(html_url)

    # Realizar la solicitud
    try:
        response = requests.get(html_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        script = soup.find("script")

        if script and "window.location.href" in script.text:
            start = script.text.find('"') + 1
            end = script.text.rfind('"')
            redirected_url = script.text[start:end]

            print(f"Redirigiendo a: {redirected_url}")

            if not redirected_url.startswith("http"):
                redirected_url = f"https://eol.jsc.nasa.gov/SearchPhotos/{redirected_url}"

            # Descargar datos
            data_files = {}
            for file_type in ["Table.pl", "TextTable.pl"]:
                file_url = redirected_url.replace("Map.pl", file_type) if "Map.pl" in redirected_url else redirected_url.replace("Table.pl", file_type)
                file_response = requests.get(file_url)
                file_response.raise_for_status()

                file_soup = BeautifulSoup(file_response.text, "html.parser")
                table = file_soup.find("table", id="QueryResults")

                if table:
                    temp_file = f"temp_{file_type.lower().replace('.pl', '')}_table.html"
                    with open(temp_file, "w", encoding="utf-8") as file:
                        file.write(str(table))
                    data_files[file_type] = temp_file
                    print(f"Tabla {file_type} guardada como {temp_file}.")
                else:
                    print(f"No se encontró la tabla QueryResults en {file_type}.")

            if all(os.path.exists(data_files[file]) for file in ["Table.pl", "TextTable.pl"]):
                def process_table(file_path):
                    with open(file_path, "r", encoding="utf-8") as file:
                        soup = BeautifulSoup(file, "html.parser")

                    table = soup.find("table", id="QueryResults")
                    if not table:
                        print(f"No se encontró la tabla con id 'QueryResults' en {file_path}.")
                        return {}

                    data = {}
                    rows = table.find_all("tr")
                    print(f"Procesando {len(rows)} filas en {file_path}.")

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 3:
                            img_tag = cols[0].find("img")
                            thumbnail_url = f"https://eol.jsc.nasa.gov{img_tag['src']}" if img_tag and "src" in img_tag.attrs else None
                            id_text = cols[2].text.strip()

                            if id_text not in data:
                                data[id_text] = {"id": id_text, "thumbnail": thumbnail_url}
                    return data

                def process_texttable(file_path):
                    with open(file_path, "r", encoding="utf-8") as file:
                        soup = BeautifulSoup(file, "html.parser")

                    table = soup.find("table", id="QueryResults")
                    if not table:
                        print(f"No se encontró la tabla con id 'QueryResults' en {file_path}.")
                        return {}

                    data = {}
                    rows = table.find_all("tr")
                    print(f"Procesando {len(rows)} filas en {file_path}.")

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 4:
                            try:
                                id_link = cols[0].find("a")
                                image_url = f"https://eol.jsc.nasa.gov/SearchPhotos/{id_link['href']}" if id_link and "href" in id_link.attrs else None
                                id_text = id_link.text.strip() if id_link else None
                                lat = float(cols[2].text.strip())
                                lon = float(cols[3].text.strip())

                                if id_text not in data:
                                    data[id_text] = {
                                        "latitude": lat,
                                        "longitude": lon,
                                        "image_url": image_url
                                        }
                            except ValueError:
                                print(f"Error al convertir coordenadas en fila con ID {cols[0].text.strip()}.")
                    return data

                table_data = process_table(data_files["Table.pl"])
                texttable_data = process_texttable(data_files["TextTable.pl"])

                combined_data = []
                for id_text, table_entry in table_data.items():
                    if id_text in texttable_data:
                        combined_entry = {**table_entry, **texttable_data[id_text]}
                        combined_data.append(combined_entry)
                    else:
                        print(f"No se encontraron coordenadas para el ID {id_text}.")

                output_file = os.path.join(BASE_DIR,"combined_output.json")
                with open(output_file, "w", encoding="utf-8") as json_file:
                    json.dump(combined_data, json_file, indent=4)

                print(f"Datos combinados y guardados en {output_file}.")
            else:
                print("Error: No se pudieron generar ambos archivos HTML.")

    except requests.exceptions.RequestException as e:
        print(f"Error al hacer la petición HTTP: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
