import subprocess
import csv
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header
from textual.containers import Container
from textual.binding import Binding
import os
import sys

# Confirmation dialog
from textual.screen import ModalScreen
from textual.containers import Grid
from textual.widgets import Label, Button
from textual import on
import json
from datetime import datetime
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from routes import DB_URL
from db.Crud import MetadataCRUD
from log import log_custom

crud = MetadataCRUD(db_url=DB_URL)
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "table.log")


def abrir_con_editor_texto(path):
    subprocess.run(
        [
            "yad",
            "--text-info",
            f"--filename={path}",
            "--title=File contents",
            "--width=600",
            "--height=400",
        ],
        check=False,
    )


class ConfirmationDialog(ModalScreen[bool]):
    """Modal dialog to confirm destructive actions."""

    DEFAULT_CSS = """
    ConfirmationDialog {
        align: center middle;
    }
    
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr auto;
        padding: 0 1;
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }
    
    #question {
        column-span: 2;
        height: auto;
        width: 1fr;
        content-align: center middle;
        text-align: center;
        padding: 1;
    }
    
    Button {
        width: 100%;
    }
    """

    def __init__(self, message: str, callback):
        super().__init__()
        self.message = message
        self.callback = callback

    def compose(self):
        yield Grid(
            Label(self.message, id="question"),
            Button("Yes, delete", variant="error", id="confirm"),
            Button("No, cancel", variant="primary", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#confirm")
    def confirm_pressed(self) -> None:
        self.app.pop_screen()
        self.callback(True)

    @on(Button.Pressed, "#cancel")
    def cancel_pressed(self) -> None:
        self.app.pop_screen()
        self.callback(False)


class OptimizedDataTable(DataTable):
    """DataTable optimized para mejor rendimiento"""

    def on_mount(self) -> None:
        """Configura la table cuando se monta"""
        self.show_header = True
        self.zebra_stripes = False
        self.cursor_type = "row"
        self.fixed_rows = 0
        self.fixed_columns = 1
        self.can_focus = True


class DataTableApp(App):
    """Aplicación principal de la table de datos"""

    CSS = """
    Container {
        height: auto;
        width: 100%;
        max-width: 100%;
        align: center middle;
    }
    
    DataTable {
        height: auto;
        width: 100%;
        border: solid green;
    }
    
    DataTable > .datatable--header {
        background: $panel;
        color: $text;
    }
    
    DataTable > .datatable--cursor {
        background: $accent;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("w", "open_image", "Open image", show=True),
        Binding("d", "delete_image", "Delete image", show=True),
        Binding("a", "open_txt", "Open camera txt", show=True),
        Binding("n", "next_page", "Next page", show=True),
        Binding("p", "previous_page", "Previous page", show=True),
        Binding("q", "quit", "Exit", show=True),
        Binding("f", "toggle_source", "Switch source", show=True),
        # Binding("s", "buscar", "Search", show=True),
        Binding("x", "export_csv", "Export CSV", show=True),
    ]

    def __init__(self, headers, data):
        super().__init__()
        self.headers = headers
        self.data = data
        self.offset = 0
        self.limit = 100
        self.fuente = "ISS"  #  Fuente inicial

    def compose(self) -> ComposeResult:
        """Create la interfaz de usuario"""
        yield Header()
        with Container():
            yield OptimizedDataTable()
        yield Footer()

    def on_mount(self) -> None:
        """Configura la table cuando la aplicación se inicia"""
        # table = self.query_one(OptimizedDataTable)

        # table.add_columns(*self.headers)

        # if not self.data:
        #     self.notify("No hay datos en la base de datos.", severity="warning")
        #     return

        # BATCH_SIZE = 100
        # for i in range(0, len(self.data), BATCH_SIZE):
        #     batch = self.data[i:i + BATCH_SIZE]
        #     table.add_rows(batch)
        table = self.query_one(OptimizedDataTable)
        table.add_columns(*self.headers)
        self.load_page()

    def get_correct_path(self, original_path):
        """Detecta si /mnt/nas está montado y ajusta la path"""

        # Verificar si /mnt/nas está montado
        try:
            result = subprocess.run(
                ["mountpoint", "/mnt/nas"], capture_output=True, text=True
            )
            nas_mounted = result.returncode == 0
        except:
            nas_mounted = False

        if nas_mounted:
            # Si está montado, usar /mnt/nas
            return original_path.replace(
                "/home/jose/API-NASA/map/scripts/backend/API-NASA",
                "/mnt/nas/DATOS API ISS/",
            )
        else:
            # Si no está montado, usar path local
            return original_path.replace(
                "/mnt/nas/DATOS API ISS/",
                "/home/jose/API-NASA/map/scripts/backend/API-NASA",
            )

    def get_correct_path_noaa(self, original_path):
        """Detecta si /mnt/nas está montado y ajusta la path"""
        nas_path = "/mnt/nas/DATOS API ISS/NOAA/noaa_metadata.json"

        # Verificar si /mnt/nas está montado
        try:
            result = subprocess.run(
                ["mountpoint", "/mnt/nas"], capture_output=True, text=True
            )
            nas_mounted = result.returncode == 0
        except:
            nas_mounted = False

        if nas_mounted:
            # Si está montado, usar /mnt/nas
            return original_path.replace(original_path, nas_path)
        else:
            # Si no está montado, usar path local
            return original_path.replace(nas_path, original_path)

    def action_open_image(self) -> None:
        """Abre la image de la row seleccionada con feh."""
        table = self.query_one(DataTable)
        if table.row_count == 0:
            self.notify("La table no contiene datos.", severity="error")
            return
        if table.cursor_row is None:
            self.notify("Por favor, selecciona una row primero.", severity="warning")
            return
        try:
            # current_row = table.get_row_at(table.cursor_row)
            # image_path = current_row[1] if current_row else None
            current_row_idx = table.cursor_row
            raw_row = self.data[self.offset + current_row_idx]
            # image_path = raw_row[1]  # path completa
            image_path = self.get_correct_path(
                raw_row[1]
            )  # path ajustada según montaje

            if not image_path:
                self.notify("No hay path de image disponible", severity="error")
                return

            subprocess.run(
                ["feh", "--scale-down", "--geometry", "800x600", image_path],
                check=True,
                capture_output=True,
                text=True,
            )
            self.notify("Imagen abierta correctmente.")
        except FileNotFoundError:
            self.notify("No se encontró el file de image.", severity="error")
        except subprocess.CalledProcessError as e:
            self.notify(
                f"Error al abrir la image con feh: {e.stderr}",
            )
        except Exception as e:
            self.notify(f"Error inesperado: {e}", severity="error")

    # def action_open_txt(self) -> None:
    #     """Abre el file .txt de la row seleccionada con yad."""
    #     table = self.query_one(OptimizedDataTable)
    #     if table.row_count == 0:
    #         self.notify("La table no contiene datos.", severity="error")
    #         return
    #     if table.cursor_row is None:
    #         self.notify("Por favor, selecciona una row primero.", severity="warning")
    #         return
    #     try:
    #         current_row_idx = table.cursor_row
    #         raw_row = self.data[self.offset + current_row_idx]

    #         # Verificar si la row tiene suficientes columns
    #         if len(raw_row) < 22:
    #             self.notify("Fila incompleta", severity="error")
    #             log_custom("TXT", f"Fila incompleta: {raw_row}", "ERROR", LOG_PATH)
    #             return

    #         txt_path = raw_row[20]
    #         log_custom("DEBUG", f"txt_path (índice 21): {txt_path}", "INFO", LOG_PATH)
    #         log_custom("DEBUG", f"type(txt_path): {type(txt_path)}", "INFO", LOG_PATH)

    #         if not txt_path or not os.path.isfile(txt_path):
    #             self.notify(
    #                 f"El file .txt no existe o la path es inválida: {txt_path}",
    #                 severity="error",
    #             )
    #             log_custom(
    #                 "TXT",
    #                 f"Ruta inválida o file no encontrado: {txt_path}",
    #                 "ERROR",
    #                 LOG_PATH,
    #             )
    #             return

    #         subprocess.run(
    #             [
    #                 "yad",
    #                 "--text-info",
    #                 f"--filename={txt_path}",
    #                 "--title=Contenido del file",
    #                 "--width=600",
    #                 "--height=400",
    #             ],
    #             check=False,
    #         )

    #     except FileNotFoundError:
    #         self.notify("No se encontró el file .txt.", severity="error")
    #         log_custom("TXT", "Archivo .txt no encontrado", "ERROR", LOG_PATH)
    #     except subprocess.CalledProcessError as e:
    #         error_msg = (
    #             f"Error al abrir el file TXT con yad: {e.stderr.decode('utf-8')}"
    #         )
    #         self.notify(error_msg, severity="error")
    #         log_custom("TXT", error_msg, "ERROR", LOG_PATH)
    #     except Exception as e:
    #         err = f"Error inesperado al abrir .txt: {e}"
    #         self.notify(err, severity="error")
    #         log_custom("TXT", err, "ERROR", LOG_PATH)

    def action_open_txt(self) -> None:
        """Abre el file .txt de la row seleccionada con yad."""
        import traceback

        table = self.query_one(OptimizedDataTable)
        if table.row_count == 0:
            self.notify("La table no contiene datos.", severity="error")
            return
        if table.cursor_row is None:
            self.notify("Por favor, selecciona una row primero.", severity="warning")
            return

        try:
            current_row_idx = table.cursor_row

            #  Si self.data tiene la misma cantidad de rows que la table, no uses offset
            if current_row_idx >= len(self.data):
                self.notify(
                    f"Índice inválido: {current_row_idx} >= rows disponibles: {len(self.data)}",
                    severity="error",
                )
                log_custom(
                    "TXT",
                    f" Índice inválido directo: {current_row_idx} >= len(data) = {len(self.data)}",
                    "ERROR",
                    LOG_PATH,
                )
                return

            raw_row = self.data[current_row_idx]

            log_custom("TXT", f" Fila recibida: {raw_row}", "INFO", LOG_PATH)

            if not isinstance(raw_row, (list, tuple)):
                self.notify(
                    "La row seleccionada no es una lista ni tupla.", severity="error"
                )
                log_custom(
                    "TXT",
                    f" Tipo de row inesperado: {type(raw_row)}",
                    "ERROR",
                    LOG_PATH,
                )
                return

            if len(raw_row) < 21:
                self.notify(
                    f"La row tiene {len(raw_row)} columns, faltan datos.",
                    severity="error",
                )
                log_custom(
                    "TXT",
                    f" Fila incompleta (esperado 22): {raw_row}",
                    "ERROR",
                    LOG_PATH,
                )
                return

            txt_path = raw_row[20]
            log_custom("TXT", f" Ruta .txt extraída: {txt_path}", "INFO", LOG_PATH)

            if not txt_path or not isinstance(txt_path, str):
                self.notify("La path .txt no es válida.", severity="error")
                log_custom("TXT", f" Ruta inválida: {txt_path}", "ERROR", LOG_PATH)
                return

            if not os.path.isfile(txt_path):
                self.notify("El file .txt no existe.", severity="error")
                log_custom(
                    "TXT", f" Archivo no encontrado: {txt_path}", "ERROR", LOG_PATH
                )
                return

            subprocess.run(
                [
                    "yad",
                    "--text-info",
                    f"--filename={txt_path}",
                    "--title=Contenido del file",
                    "--width=600",
                    "--height=400",
                ],
                check=False,
            )
            self.notify("Archivo .txt abierto correctmente.", severity="success")

        except Exception as e:
            err = f" Error inesperado al abrir .txt: {e}"
            stack = traceback.format_exc()
            self.notify(err, severity="error")
            log_custom("TXT", f"{err}\nTRACEBACK:\n{stack}", "ERROR", LOG_PATH)

    def action_export_csv(self) -> None:
        """Exporta los datos a un file CSV con diálogo para elegir ubicación."""
        try:
            # Obtener todos los datos de la base de datos (no solo la página actual)
            if self.fuente == "ISS":
                all_data = crud.get_all_metadata()
            elif self.fuente == "NOAA":
                all_data = self.cargar_noaa_desde_json()

            if not all_data:
                if self.fuente == "NOAA":
                    self.notify(
                        "No hay datos de NOAA para exportar. El file JSON está vacío o no contiene datos válidos.",
                        severity="warning",
                    )
                else:
                    self.notify(
                        "No hay datos de ISS para exportar.", severity="warning"
                    )
                return

            # Usar yad para mostrar diálogo de guardado
            result = subprocess.run(
                [
                    "yad",
                    "--file",
                    "--save",
                    "--title=Guardar file CSV",
                    "--filename=datos_exportados.csv",
                    "--width=600",
                    "--height=400",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.notify("Exportación cancelada por el usuario.", severity="info")
                return

            file_path = result.stdout.strip()
            if not file_path:
                self.notify("No se especificó una path de file.", severity="error")
                return

            # Preparar los datos para exportar
            rows = []
            for row in all_data:
                # Convertir todos los valores a string y manejar None
                row_str = []
                for cell in row:
                    if cell is None:
                        row_str.append("")
                    elif isinstance(cell, (int, float)):
                        row_str.append(str(cell))
                    else:
                        row_str.append(str(cell))
                rows.append(row_str)

            # Escribir el file CSV
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.headers)
                writer.writerows(rows)

            self.notify(
                f"Datos exportados exitosamente a:\n{file_path}\n\n"
                f"Total de registros: {len(all_data)}",
                severity="success",
            )

            # Log del evento
            log_custom(
                "EXPORT_CSV",
                f"Exportados {len(all_data)} registros a {file_path}",
                "INFO",
                LOG_PATH,
            )

        except subprocess.CalledProcessError as e:
            error_msg = f"Error in el diálogo de file: {e.stderr}"
            self.notify(error_msg, severity="error")
            log_custom("EXPORT_CSV", error_msg, "ERROR", LOG_PATH)
        except PermissionError:
            error_msg = "No tienes permisos para escribir en esa ubicación."
            self.notify(error_msg, severity="error")
            log_custom("EXPORT_CSV", error_msg, "ERROR", LOG_PATH)
        except Exception as e:
            error_msg = f"Error inesperado al exportar CSV: {e}"
            self.notify(error_msg, severity="error")
            log_custom("EXPORT_CSV", error_msg, "ERROR", LOG_PATH)

    def action_delete_image(self) -> None:
        """Elimina una image referenciada por su nasa_id del almacenamiento y la base de datos."""
        table = self.query_one(OptimizedDataTable)
        if table.row_count == 0:
            self.notify("La table no contiene datos.", severity="error")
            return

        if table.cursor_row is None:
            self.notify("Por favor, selecciona una row primero.", severity="warning")
            return

        try:
            # Obtener la row original con paths completas desde self.data
            raw_row = self.data[self.offset + table.cursor_row]
            image_path = raw_row[1]  # Ruta completa de la image
            nasa_id = raw_row[2]  # NASA ID

            if not image_path or not nasa_id:
                self.notify(
                    "No hay datos suficientes para eliminar la image.",
                    severity="error",
                )
                return

            # Eliminar el file si existe
            if os.path.exists(image_path):
                os.remove(image_path)
                self.notify(f"Archivo eliminado: {image_path}", severity="success")

            # Eliminar el registro de la base de datos
            crud.delete_image(nasa_id)
            self.notify(
                f"Imagen eliminada de la base de datos para NASA ID: {nasa_id}",
                severity="success",
            )

            # Refrescar la table
            self.refresh_table()

        except Exception as e:
            self.notify(f"Error al eliminar la image: {e}", severity="error")

    def action_delete_image(self) -> None:
        """Elimina una image referenciada por su nasa_id del almacenamiento y la base de datos."""
        table = self.query_one(OptimizedDataTable)
        if table.row_count == 0:
            self.notify("La table no contiene datos.", severity="error")
            return

        if table.cursor_row is None:
            self.notify("Por favor, selecciona una row primero.", severity="warning")
            return

        try:
            # Obtener la row original con paths completas desde self.data
            raw_row = self.data[self.offset + table.cursor_row]
            image_path = raw_row[1]  # Ruta completa de la image
            nasa_id = raw_row[2]  # NASA ID

            if not image_path or not nasa_id:
                self.notify(
                    "No hay datos suficientes para eliminar la image.",
                    severity="error",
                )
                return

            # Mostrar diálogo de confirmación
            def confirm_deletion(confirmed: bool) -> None:
                if not confirmed:
                    self.notify("Eliminación cancelada.", severity="info")
                    return

                try:
                    # Eliminar el file si existe
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        self.notify(
                            f"Archivo eliminado: {image_path}", severity="success"
                        )

                    # Eliminar el registro de la base de datos
                    crud.delete_image(nasa_id)
                    self.notify(
                        f"Imagen eliminada de la base de datos para NASA ID: {nasa_id}",
                        severity="success",
                    )

                    # Refrescar la table
                    self.refresh_table()

                except Exception as e:
                    self.notify(f"Error al eliminar la image: {e}", severity="error")

            # Crear el diálogo de confirmación
            self.push_screen(
                ConfirmationDialog(
                    f"¿Estás seguro de que quieres eliminar la image?\n\n"
                    f"NASA ID: {nasa_id}\n"
                    f"Archivo: {os.path.basename(image_path)}\n\n"
                    f"Esta acción no se puede deshacer.",
                    confirm_deletion,
                )
            )

        except Exception as e:
            self.notify(f"Error al eliminar la image: {e}", severity="error")

    def refresh_table(self) -> None:
        """Recarga los datos en la table después de una acción."""
        try:
            table = self.query_one(OptimizedDataTable)
            table.clear()

            # Obtener los datos actualizados
            self.data = crud.get_paginated_metadata(
                offset=self.offset, limit=self.limit
            )

            if not self.data:
                self.notify("No hay datos disponibles.", severity="warning")
                return

            for i, row in enumerate(self.data):
                row_str = [str(cell) if cell is not None else "" for cell in row]

                if len(row_str) > 21:
                    # Mostrar path desde año
                    image_path = row_str[1]
                    idx_year = image_path.find("/20")
                    row_str[1] = image_path[idx_year:] if idx_year != -1 else image_path

                    # Mostrar path desde camera_data
                    txt_path = row_str[21]
                    idx_camera = txt_path.find("camera_data")
                    row_str[21] = (
                        txt_path[idx_camera:] if idx_camera != -1 else txt_path
                    )

                table.add_row(*row_str, key=str(i))

            self.notify("Tabla actualizada correctmente", severity="success")

        except Exception as e:
            self.notify(f"Error al refrescar la table: {e}", severity="error")

    def action_next_page(self) -> None:
        new_data = crud.get_paginated_metadata(
            offset=self.offset + self.limit, limit=self.limit
        )

        if not new_data:
            self.notify("No hay más datos para mostrar.", severity="info")
            return

        self.offset += self.limit
        self.load_page()

    def action_previous_page(self) -> None:
        if self.offset >= self.limit:
            self.offset -= self.limit
            self.load_page()
        else:
            self.notify("Ya estás en la primera página.", severity="warning")

    def load_page(self):
        try:
            table = self.query_one(DataTable)
            table.clear()

            if self.fuente == "ISS":
                data = crud.get_paginated_metadata(offset=self.offset, limit=self.limit)
            elif self.fuente == "NOAA":
                data = self.cargar_noaa_desde_json()
                if not data:
                    if self.offset == 0:
                        self.notify(
                            "No hay datos de NOAA disponibles. El file JSON está vacío o no contiene datos válidos.",
                            severity="info",
                        )
                    else:
                        self.notify(
                            "No hay más datos de NOAA para mostrar.", severity="info"
                        )
                        if self.offset >= self.limit:
                            self.offset -= self.limit
                    return
                data = data[self.offset : self.offset + self.limit]

            if not data:
                if self.fuente == "ISS":
                    self.notify(
                        "No hay más datos de ISS para mostrar.", severity="info"
                    )
                else:
                    self.notify(
                        "No hay más datos de NOAA para mostrar.", severity="info"
                    )
                if self.offset >= self.limit:
                    self.offset -= self.limit
                return

            self.data = data  #  NECESARIO para paths completas al abrir/eliminar

            for i, row in enumerate(data):
                row_str = [str(cell) if cell is not None else "" for cell in row]

                if self.fuente == "ISS" and len(row_str) >= 21:
                    # Procesar column IMAGEN (índice 1)
                    full_image_path = row_str[1]
                    if full_image_path:
                        # Buscar el ÚLTIMO "API-NASA/" en la path
                        last_api_nasa_idx = full_image_path.rfind("API-NASA/")
                        if last_api_nasa_idx != -1:
                            row_str[1] = full_image_path[
                                last_api_nasa_idx + len("API-NASA/") :
                            ]
                            # if i < 3: log_custom("DEBUG", f" IMAGEN recortada: '{row_str[1]}'", "INFO", LOG_PATH)
                        elif "/20" in full_image_path:
                            # Fallback: buscar año
                            idx_year = full_image_path.find("/20")
                            row_str[1] = full_image_path[idx_year + 1 :]
                            # if i < 3: log_custom("DEBUG", f" IMAGEN por año: '{row_str[1]}'", "INFO", LOG_PATH)
                        else:
                            # Último fallback: últimas 3 partes
                            parts = full_image_path.split("/")
                            if len(parts) >= 3:
                                row_str[1] = "/".join(parts[-3:])
                            else:
                                row_str[1] = os.path.basename(full_image_path)
                            # if i < 3: log_custom("DEBUG", f" IMAGEN fallback: '{row_str[1]}'", "INFO", LOG_PATH)

                    # Procesar column TXT (índice 20)
                    full_txt_path = row_str[20]
                    if full_txt_path:
                        # Buscar el ÚLTIMO "API-NASA/" en la path
                        last_api_nasa_idx = full_txt_path.rfind("API-NASA/")
                        if last_api_nasa_idx != -1:
                            row_str[20] = full_txt_path[
                                last_api_nasa_idx + len("API-NASA/") :
                            ]
                            # if i < 3: log_custom("DEBUG", f" TXT recortado: '{row_str[20]}'", "INFO", LOG_PATH)
                        elif "camera_data" in full_txt_path:
                            # Fallback: buscar camera_data
                            idx_camera = full_txt_path.find("camera_data")
                            row_str[20] = full_txt_path[idx_camera:]
                            # if i < 3: log_custom("DEBUG", f" TXT por camera_data: '{row_str[20]}'", "INFO", LOG_PATH)
                        else:
                            # Último fallback: últimas 2 partes para txt
                            parts = full_txt_path.split("/")
                            if len(parts) >= 2:
                                row_str[20] = "/".join(parts[-2:])
                            else:
                                row_str[20] = os.path.basename(full_txt_path)
                            # if i < 3: log_custom("DEBUG", f" TXT fallback: '{row_str[20]}'", "INFO", LOG_PATH)

                table.add_row(*row_str, key=str(i))

            self.notify(
                f"[{self.fuente}] Mostrando registros {self.offset + 1} - {self.offset + len(data)}",
                severity="info",
            )

        except Exception as e:
            err = f"Error al cargar datos: {e}"
            self.notify(err, severity="error")
            log_custom("LOAD_PAGE", err, "ERROR", LOG_PATH)

    def action_toggle_source(self) -> None:
        self.fuente = "NOAA" if self.fuente == "ISS" else "ISS"
        self.offset = 0

        # Cambiar headers primero
        if self.fuente == "NOAA":
            self.headers = [
                "ID",
                "DATASET",
                "BANDA_ID",
                "PRECISION",
                "MIN",
                "MAX",
                "DIMENSIONES",
                "CRS",
                "FECHA_INICIO",
                "FECHA_FIN",
                "TAM_MB",
                "FOOTPRINT",
            ]
        else:
            self.headers = [
                "ID",
                "IMAGEN",
                "NASA_ID",
                "FECHA",
                "HORA",
                "RESOLUCION",
                "NADIR_LAT",
                "NADIR_LON",
                "CENTER_LAT",
                "CENTER_LON",
                "NADIR_CENTER",
                "ALTITUD",
                "LUGAR",
                "ELEVACION_SOL",
                "AZIMUT_SOL",
                "COBERTURA_NUBOSA",
                "CAMARA",
                "LONGITUD_FOCAL",
                "INCLINACION",
                "FORMATO",
                "CAMARA_METADATOS",
            ]

        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(*self.headers)
        self.load_page()
        self.notify(f"Fuente cambiada a: {self.fuente}", severity="info")

    def cargar_noaa_desde_json(
        self,
        json_path=os.path.join(
            os.path.dirname(__file__), "..", "backend", "API-NASA", "noaa_metadata.json"
        ),
    ):
        json_path = self.get_correct_path_noaa(json_path)

        try:
            # Verificar si el file existe
            if not os.path.exists(json_path):
                log_custom(
                    "NOAA_JSON",
                    f"Archivo JSON no encontrado: {json_path}",
                    "WARNING",
                    LOG_PATH,
                )
                return []

            # Verificar si el file está vacío
            if os.path.getsize(json_path) == 0:
                log_custom(
                    "NOAA_JSON",
                    f"Archivo JSON está vacío: {json_path}",
                    "INFO",
                    LOG_PATH,
                )
                return []

            with open(json_path, "r") as f:
                metadata = json.load(f)

            # Verificar si el JSON está vacío o es None
            if not metadata or not isinstance(metadata, dict):
                log_custom(
                    "NOAA_JSON",
                    "JSON de NOAA está vacío o no contiene un diccionario válido",
                    "INFO",
                    LOG_PATH,
                )
                return []

            # Verificar si no hay elementos en el diccionario
            if len(metadata) == 0:
                log_custom(
                    "NOAA_JSON", "JSON de NOAA no contiene metadata", "INFO", LOG_PATH
                )
                return []

            rows = []
            for key, meta in metadata.items():
                # Verificar si meta es válido
                if not meta or not isinstance(meta, dict):
                    continue

                props = meta.get("properties", {})
                bands = meta.get("bands", [])

                # Si no hay bandas, saltar este elemento
                if not bands:
                    continue

                for banda in bands:
                    data_type = banda.get("data_type", {})
                    date_inicio = props.get("system:time_start")
                    date_fin = props.get("system:time_end")

                    rows.append(
                        [
                            meta.get("id", key),
                            meta.get("dataset"),
                            banda.get("id"),
                            data_type.get("precision"),
                            data_type.get("min"),
                            data_type.get("max"),
                            str(banda.get("dimensions")),
                            banda.get("crs"),
                            datetime.utcfromtimestamp(date_inicio / 1000)
                            if date_inicio
                            else "",
                            datetime.utcfromtimestamp(date_fin / 1000)
                            if date_fin
                            else "",
                            round(props.get("system:asset_size", 0) / 1e6, 2),
                            str(props.get("system:footprint", {}).get("coordinates")),
                        ]
                    )

            # Si no se processon datos, log informativo
            if len(rows) == 0:
                log_custom(
                    "NOAA_JSON",
                    "JSON de NOAA no contiene datos válidos para mostrar",
                    "INFO",
                    LOG_PATH,
                )

            return rows

        except json.JSONDecodeError as e:
            err = f"Error al decodificar JSON de NOAA: {e}"
            log_custom("NOAA_JSON", err, "WARNING", LOG_PATH)
            return []
        except FileNotFoundError:
            log_custom(
                "NOAA_JSON",
                f"Archivo JSON no encontrado: {json_path}",
                "WARNING",
                LOG_PATH,
            )
            return []
        except Exception as e:
            err = f"Error inesperado al cargar JSON de NOAA: {e}"
            log_custom("NOAA_JSON", err, "ERROR", LOG_PATH)
            return []

    def action_buscar(self) -> None:
        """Solicita al usuario un término de búsqueda y filtra la table."""
        from textual.widgets import Input
        from textual.screen import ModalScreen
        from textual.containers import Vertical
        from textual import on

        class SimpleSearchDialog(ModalScreen):
            def compose(inner_self):
                yield Vertical(
                    Label("Buscar en column (ej. NASA_ID):"),
                    Input(placeholder="Nombre de column", id="col_input"),
                    Label("Término a buscar:"),
                    Input(placeholder="Texto a buscar", id="text_input"),
                    Button("Buscar", id="btn_search"),
                    Button("Cancelar", id="btn_cancel"),
                    id="search_box",
                )

            @on(Button.Pressed, "#btn_search")
            def search(inner_self) -> None:
                col = inner_self.query_one("#col_input", Input).value
                term = inner_self.query_one("#text_input", Input).value

                inner_self.app.pop_screen()

                if not col or not term:
                    self.notify("Por favor, completa ambos campos", severity="warning")
                    return

                if col not in self.headers:
                    self.notify(f"Columna no válida: {col}", severity="error")
                    return

                self.filtrar_datos(col, term)

            @on(Button.Pressed, "#btn_cancel")
            def cancel(inner_self) -> None:
                inner_self.app.pop_screen()

        self.push_screen(SimpleSearchDialog())

    def filtrar_datos(self, column: str, termino: str):
        try:
            idx = self.headers.index(column)
        except ValueError:
            self.notify(f"Columna no encontrada: {column}", severity="error")
            return

        filtrado = [
            row for row in self.data if termino.lower() in str(row[idx]).lower()
        ]
        self.mostrar_results_filtrados(filtrado)

    def mostrar_results_filtrados(self, datos_filtrados):
        table = self.query_one(OptimizedDataTable)
        table.clear()
        for i, row in enumerate(datos_filtrados):
            row_str = [str(cell) if cell is not None else "" for cell in row]
            table.add_row(*row_str, key=str(i))

        self.notify(f"{len(datos_filtrados)} results encontrados.", severity="info")


def run_datatable(headers, data):
    app = DataTableApp(headers, data)
    app.run()


# Ejemplo de uso
if __name__ == "__main__":
    headers = [
        "ID",
        "IMAGEN",
        "NASA_ID",
        "FECHA",
        "HORA",
        "RESOLUCION",
        "NADIR_LAT",
        "NADIR_LON",
        "CENTER_LAT",
        "CENTER_LON",
        "NADIR_CENTER",
        "ALTITUD",
        "LUGAR",
        "ELEVACION_SOL",
        "AZIMUT_SOL",
        "COBERTURA_NUBOSA",
        "CAMARA",
        "LONGITUD_FOCAL",
        "INCLINACION",
        "FORMATO",
        "CAMARA_METADATOS",
    ]
    data = crud.get_paginated_metadata(offset=0, limit=100)

    # Obtener los datos de la base de datos
    try:
        data = crud.get_paginated_metadata(offset=0, limit=100)
        if not data:
            raise ValueError("No hay datos en la base de datos.")
        run_datatable(headers, data)
    except Exception as e:
        log_custom("TABLE", str(e), "ERROR", LOG_PATH)
