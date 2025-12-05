import os
import json
import requests
from bs4 import BeautifulSoup


BASE_DIR = os.path.join(os.path.dirname(__file__))

# URL inicial
html_url = "https://eol.jsc.nasa.gov/SearchPhotos/CoordinateRangeSearch.pl?dawndusk=on&LowerLat=6.6&UpperLat=10.5&HasCloudMask=on&LeftLon=-83.2&daytime=on&UseCatalogedWithoutCP=on&UseCatalogedWithCP=on&IncludeHO=on&nighttime=on&RightLon=-76.9&UseNotCataloged=on"

# Realizar la solicitud inicial
response = requests.get(html_url)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")
    script = soup.find("script")

    if script and "window.location.href" in script.text:
        start = script.text.find('"') + 1
        end = script.text.rfind('"')
        redirected_url = script.text[start:end]

        print(f"Redirigiendo a: {redirected_url}")

        # Convertir en URL absoluta si es relativa
        if not redirected_url.startswith("http"):
            redirected_url = f"https://eol.jsc.nasa.gov/SearchPhotos/{redirected_url}"

        # Descargar y procesar las tablas `QueryResults`
        data_files = {}
        for file_type in ["Table.pl", "TextTable.pl"]:
            file_url = redirected_url.replace("Map.pl", file_type) if "Map.pl" in redirected_url else redirected_url.replace("Table.pl", file_type)
            file_response = requests.get(file_url)

            if file_response.status_code == 200:
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
            else:
                print(f"Error al descargar la página {file_type}: {file_response.status_code}")

        # Si ambos archivos existen, procesarlos
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

            # Procesar archivos y combinar datos
            table_data = process_table(data_files["Table.pl"])
            texttable_data = process_texttable(data_files["TextTable.pl"])

            combined_data = []
            for id_text, table_entry in table_data.items():
                if id_text in texttable_data:
                    combined_entry = {**table_entry, **texttable_data[id_text]}
                    combined_data.append(combined_entry)
                else:
                    print(f"No se encontraron coordenadas para el ID {id_text}.")

            # Guardar en JSON
            output_file = os.path.join(BASE_DIR,"combined_output.json")
            with open(output_file, "w", encoding="utf-8") as json_file:
                json.dump(combined_data, json_file, indent=4)

            print(f"Datos combinados y guardados en {output_file}.")
        else:
            print("Error: No se pudieron generar ambos archivos HTML.")
    else:
        print("No se encontró un script de redirección en la página.")
else:
    print(f"Error al realizar la solicitud inicial: {response.status_code}")
