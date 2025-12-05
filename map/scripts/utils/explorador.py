import gi
import os
import subprocess
import shutil
import mimetypes
import sys
import threading
from pathlib import Path

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from rutas import NAS_MOUNT, NAS_PATH

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib
from log import log_custom

LOGFILE = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "explorador.log")


class FileExplorer(Gtk.Window):
    def __init__(self):
        super().__init__(title="NAS")
        self.set_default_size(900, 600)
        self.set_border_width(10)

        if os.path.ismount(NAS_MOUNT):
            path = NAS_PATH
            log_custom(
                message=f"NAS montado detectado. Usando ruta local en NAS: {path}",
                level="INFO",
                file=LOGFILE,
            )
        else:
            path = os.path.join("scripts", "backend", "API-NASA")
            log_custom(
                message=f" NAS no disponible. Usando carpeta local: {path}",
                level="INFO",
                file=LOGFILE,
            )

        self.base_folder = os.path.abspath(path)
        self.current_folder = self.base_folder
        log_custom(message=self.current_folder, level="INFO", file=LOGFILE)
        if not os.path.exists(self.current_folder):
            log_custom(
                message="No existe, debe descargar imagenes primero",
                level="WARNING",
                file=LOGFILE,
            )
            exit(1)

        # Cache para thumbnails
        self.thumbnail_cache = {}
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "nas_explorer")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        #  Lista de archivos y carpetas con iconos
        self.liststore = Gtk.ListStore(str, str, str)  # (Icono, Nombre, Ruta)

        #  Variables para copiar/pegar archivos
        self.copied_path = None

        #  Contenedor de navegación
        self.nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        #  Vista de archivos
        self.treeview = Gtk.TreeView(model=self.liststore)

        #  Columna de iconos
        icon_renderer = Gtk.CellRendererPixbuf()
        column_icon = Gtk.TreeViewColumn("Tipo", icon_renderer, icon_name=0)
        self.treeview.append_column(column_icon)

        #  Columna de nombres
        text_renderer = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn("Nombre", text_renderer, text=1)
        self.treeview.append_column(column_name)

        self.treeview.connect("row-activated", self.on_double_click)
        self.treeview.connect("button-press-event", self.on_right_click)

        #  Contenedor principal con scroll
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.treeview)

        #  Layout principal
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.pack_start(self.nav_box, False, False, 0)
        vbox.pack_start(scrolled_window, True, True, 0)

        self.add(vbox)
        self.connect("destroy", Gtk.main_quit)

        #  Cargar archivos después de inicializar la UI
        self.load_files(self.current_folder)

        self.show_all()

    def get_available_image_viewer(self):
        """Detecta el mejor visor de imágenes disponible para TIFF grandes (NOAA), priorizando velocidad."""
        viewers = [
            # Más rápidos para TIFF grandes
            ("gthumb", ["gthumb"]),  # Muy rápido con TIFF
            ("gpicview", ["gpicview"]),  # Ligero y rápido
            ("mirage", ["mirage"]),  # Específico para imágenes
            ("ristretto", ["ristretto"]),  # Xfce, muy eficiente
            ("xviewer", ["xviewer"]),  # MATE, optimizado
            ("eog", ["eog"]),  # GNOME, soporte nativo TIFF
            ("nomacs", ["nomacs"]),  # Rápido para imágenes grandes
            ("gwenview", ["gwenview"]),  # KDE, buen rendimiento
        ]

        for name, cmd in viewers:
            try:
                # Verificar si el comando existe
                subprocess.run(
                    ["which", cmd[0]],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                log_custom(
                    message=f"Visor para NOAA encontrado: {name} ({cmd[0]})",
                    level="INFO",
                    file=LOGFILE,
                )
                return cmd
            except subprocess.CalledProcessError:
                continue

        # Fallback a xdg-open si no hay nada más
        return ["xdg-open"]

    def get_feh_optimized(self):
        """Retorna comando de feh optimizado para imágenes normales."""
        try:
            # Verificar si feh está disponible
            subprocess.run(
                ["which", "feh"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Comando feh optimizado para velocidad
            return [
                "feh",
                "--scale-down",  # Escalar si es muy grande
                # "--auto-zoom",
                # "--borderless",
                "--auto-rotate",  # Rotar automáticamente según EXIF
                "--cache-thumbnails",  # Cache de thumbnails para navegación
                "--geometry",
                "1200x900",  # Tamaño inicial razonable
            ]
        except subprocess.CalledProcessError:
            # Si feh no está disponible, usar xdg-open
            return ["xdg-open"]

    def check_imagemagick_available(self):
        """Verifica si ImageMagick está disponible."""
        try:
            subprocess.run(
                ["convert", "-version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def create_thumbnail_async(self, file_path, callback):
        """Crea thumbnail en un hilo separado para no bloquear la UI."""

        def generate_thumbnail():
            try:
                # Verificar si ImageMagick está disponible
                if not self.check_imagemagick_available():
                    log_custom(
                        message="ImageMagick no encontrado. Instalalo con: sudo apt install imagemagick",
                        level="WARNING",
                        file=LOGFILE,
                    )
                    GLib.idle_add(callback, None)
                    return

                # Usar convert de ImageMagick para generar thumbnail rápido
                thumbnail_path = os.path.join(
                    self.cache_dir, f"{os.path.basename(file_path)}_thumb.jpg"
                )

                if not os.path.exists(thumbnail_path):
                    # Generar thumbnail pequeño y rápido
                    subprocess.run(
                        [
                            "convert",
                            file_path,
                            "-thumbnail",
                            "200x200>",  # Máximo 200px manteniendo aspecto
                            "-quality",
                            "70",  # Calidad reducida para velocidad
                            thumbnail_path,
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                # Llamar al callback en el hilo principal
                GLib.idle_add(callback, thumbnail_path)

            except Exception as e:
                log_custom(
                    message=f"Error generando thumbnail: {e}",
                    level="WARNING",
                    file=LOGFILE,
                )
                GLib.idle_add(callback, None)

        thread = threading.Thread(target=generate_thumbnail)
        thread.daemon = True
        thread.start()

    def show_image_preview_dialog(self, file_path):
        """Muestra una vista previa rápida del TIFF antes de abrirlo completamente."""
        dialog = Gtk.Dialog(
            title=f"Vista previa - {os.path.basename(file_path)}",
            parent=self,
            modal=True,
        )
        dialog.set_default_size(400, 400)

        # Botones
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.add_button("Abrir completo", Gtk.ResponseType.OK)

        # Contenedor para la imagen
        image_widget = Gtk.Image()
        spinner = Gtk.Spinner()
        spinner.start()

        # Layout
        content_area = dialog.get_content_area()
        content_area.pack_start(spinner, True, True, 0)
        content_area.pack_start(image_widget, True, True, 0)
        content_area.show_all()
        image_widget.hide()

        def on_thumbnail_ready(thumbnail_path):
            spinner.stop()
            spinner.hide()
            if thumbnail_path and os.path.exists(thumbnail_path):
                image_widget.set_from_file(thumbnail_path)
                image_widget.show()
            else:
                # Mostrar icono genérico si falla
                image_widget.set_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
                image_widget.show()

        # Generar thumbnail
        self.create_thumbnail_async(file_path, on_thumbnail_ready)

        response = dialog.run()
        dialog.destroy()

        return response == Gtk.ResponseType.OK

    def is_noaa_image(self, file_path):
        """Detecta si la imagen es de NOAA basándose en la ruta o contenido."""
        path_lower = file_path.lower()

        # Detectar por ruta
        noaa_indicators = [
            "noaa",
            "nasa",
            "goes",
            "himawari",
            "meteosat",
            "sentinel",
            "landsat",
            "modis",
            "viirs",
        ]

        for indicator in noaa_indicators:
            if indicator in path_lower:
                return True

        # También considerar archivos muy grandes como posibles NOAA
        try:
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # >50MB probablemente sea satélite
                return True
        except OSError:
            pass

        return False

    def open_tiff_optimized(self, file_path):
        """Abre archivos TIFF con lógica específica: NOAA -> vista previa, otros -> feh optimizado."""

        # Detectar si es imagen NOAA/satélite
        if self.is_noaa_image(file_path):
            file_size = os.path.getsize(file_path)
            log_custom(
                message=f"Imagen NOAA/satélite detectada ({file_size / 1024 / 1024:.1f}MB), mostrando vista previa",
                level="INFO",
                file=LOGFILE,
            )

            # Para NOAA, siempre mostrar vista previa primero
            if not self.show_image_preview_dialog(file_path):
                return  # Usuario canceló

            # Si el usuario quiere ver completa, usar el mejor visor disponible
            viewer_cmd = self.get_available_image_viewer()
        else:
            # Para imágenes normales, usar feh optimizado directamente
            log_custom(
                message=f"Imagen normal detectada, usando feh optimizado",
                level="INFO",
                file=LOGFILE,
            )
            viewer_cmd = self.get_feh_optimized()

        try:
            log_custom(
                message=f"Abriendo TIFF con: {' '.join(viewer_cmd)} {file_path}",
                level="INFO",
                file=LOGFILE,
            )

            # Ejecutar con prioridad normal para no saturar el sistema
            process = subprocess.Popen(
                viewer_cmd + [file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: os.nice(5),  # Menor prioridad
            )

        except Exception as e:
            log_custom(
                message=f"Error al abrir TIFF optimizado: {e}",
                level="ERROR",
                file=LOGFILE,
            )
            # Fallback a método original
            self.open_file_fallback(file_path)

    def open_file_fallback(self, file_path):
        """Método de apertura de archivos original como fallback."""
        try:
            subprocess.Popen(
                ["xdg-open", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log_custom(
                message=f"Error en fallback: {e}",
                level="ERROR",
                file=LOGFILE,
            )

    def update_navigation_bar(self):
        """Actualiza la barra de navegación con botones clickeables (limitado a /images)."""
        for child in self.nav_box.get_children():
            self.nav_box.remove(child)

        path_parts = (
            self.current_folder.replace(self.base_folder, "")
            .strip(os.sep)
            .split(os.sep)
        )
        built_path = self.base_folder

        #  Botón para ir a la raíz (/images)
        root_button = Gtk.Button(label="Datos API ISS")
        root_button.connect("clicked", self.on_nav_button_click, self.base_folder)
        self.nav_box.pack_start(root_button, False, False, 0)

        #  Crear botones para subcarpetas
        for part in path_parts:
            if part:
                built_path = os.path.join(built_path, part)
                button = Gtk.Button(label=part)
                button.connect("clicked", self.on_nav_button_click, built_path)
                self.nav_box.pack_start(
                    Gtk.Label(label=" / "), False, False, 0
                )  # Separador "/"
                self.nav_box.pack_start(button, False, False, 0)

        self.nav_box.show_all()

    def on_nav_button_click(self, widget, folder):
        """Cambia la carpeta solo si está dentro de /images."""
        if folder.startswith(self.base_folder):
            self.load_files(folder)

    def load_files(self, folder):
        """Carga la lista de archivos en la carpeta dada con iconos."""
        if not folder.startswith(self.base_folder):  #  Restringe salir de /images
            return

        self.liststore.clear()
        self.current_folder = folder
        self.update_navigation_bar()

        try:
            for filename in sorted(os.listdir(folder)):
                file_path = os.path.join(folder, filename)
                icon_name = self.get_file_icon(file_path)
                self.liststore.append([icon_name, filename, file_path])
        except FileNotFoundError:
            log_custom(
                message=f"ERROR: No se pudo acceder a la carpeta '{folder}'.",
                level="ERROR",
                file=LOGFILE,
            )

    def get_file_icon(self, file_path):
        """Devuelve el icono adecuado para archivos y carpetas."""
        if os.path.isdir(file_path):
            return "folder"  #  Icono de carpeta
        else:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                if "image" in mime_type:
                    return "image-x-generic"  #  Icono de imagen
                elif "text" in mime_type:
                    return "text-x-generic"  #  Icono de texto
                elif "audio" in mime_type:
                    return "audio-x-generic"  #  Icono de audio
                elif "video" in mime_type:
                    return "video-x-generic"  #  Icono de video
            return "unknown"  #  Icono genérico

    def on_double_click(self, treeview, path, column):
        """Abre archivos o entra en carpetas con doble clic."""
        model = treeview.get_model()
        file_path = model[path][2]  # Ruta completa

        if os.path.isdir(file_path):  # Si es una carpeta, navegar
            self.load_files(file_path)
        else:
            self.open_file(file_path)

    def on_right_click(self, widget, event):
        """Muestra el menú de clic derecho con opción de descargar."""
        if event.button == Gdk.BUTTON_SECONDARY:  # Clic derecho
            selection = self.treeview.get_selection()
            model, tree_iter = selection.get_selected()
            if not tree_iter:
                return  # No hacer nada si no hay selección

            file_path = model[tree_iter][2]

            menu = Gtk.Menu()

            #  Opción "Abrir"
            open_item = Gtk.MenuItem(label="Abrir")
            open_item.connect("activate", lambda _: self.open_file(file_path))
            menu.append(open_item)

            #  Opciones específicas para TIFF
            if file_path.lower().endswith((".tif", ".tiff")):
                if self.is_noaa_image(file_path):
                    preview_item = Gtk.MenuItem(label="Vista previa (NOAA)")
                    preview_item.connect(
                        "activate", lambda _: self.show_image_preview_dialog(file_path)
                    )
                    menu.append(preview_item)
                else:
                    quick_view_item = Gtk.MenuItem(label="Vista rápida (feh)")
                    quick_view_item.connect(
                        "activate", lambda _: self.open_with_feh_direct(file_path)
                    )
                    menu.append(quick_view_item)

            #  Opción "Descargar"
            download_item = Gtk.MenuItem(label="Descargar")
            download_item.connect("activate", lambda _: self.download_file(file_path))
            menu.append(download_item)

            #  Opción "Eliminar"
            # delete_item = Gtk.MenuItem(label="Eliminar")
            # delete_item.connect("activate", lambda _: self.delete_file(file_path))
            # menu.append(delete_item)

            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)

    def download_file(self, file_path):
        """Descarga un archivo o carpeta a una ubicación elegida por el usuario."""
        dialog = Gtk.FileChooserDialog(
            title="Selecciona dónde guardar el archivo",
            parent=self,
            action=Gtk.FileChooserAction.SAVE
            if os.path.isfile(file_path)
            else Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE,
            Gtk.ResponseType.OK,
        )

        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name(os.path.basename(file_path))  # Nombre por defecto

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            dest_path = dialog.get_filename()  # Ruta elegida por el usuario

            # Si es una carpeta, descargar todo su contenido
            try:
                if os.path.isdir(file_path):
                    shutil.copytree(file_path, dest_path)
                else:
                    shutil.copy2(file_path, dest_path)

                log_custom(
                    message=f"Archivo descargado en: {dest_path}",
                    level="INFO",
                    file=LOGFILE,
                )
            except FileExistsError:
                log_custom(
                    message=f" El archivo ya existe en el destino: {dest_path}",
                    level="WARNING",
                    file=LOGFILE,
                )
            except Exception as e:
                log_custom(
                    message=f"Error al descargar: {e}", level="ERROR", file=LOGFILE
                )

        dialog.destroy()

    def open_file(self, file_path):
        """Abre el archivo con optimizaciones específicas según el tipo."""
        try:
            if file_path.lower().endswith((".tif", ".tiff")):
                # Usar método optimizado para TIFF
                self.open_tiff_optimized(file_path)
            elif file_path.endswith(".txt"):
                subprocess.run(
                    [
                        "yad",
                        "--text-info",
                        f"--filename={file_path}",
                        "--title=Contenido del archivo",
                        "--width=600",
                        "--height=400",
                    ],
                    check=True,
                )
            else:
                subprocess.Popen(
                    ["xdg-open", file_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # thumb = os.listdir(self.cache_dir)
            # subprocess.run(
            #     [
            #         "rm",
            #         f"{thumb}",
            #     ],
            #     check=True,
            # )

        except Exception as e:
            log_custom(
                message=f"Error al abrir el archivo: {e}",
                level="ERROR",
                file=LOGFILE,
            )

    def delete_file(self, file_path):
        """Elimina un archivo con confirmación."""
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"¿Seguro que quieres eliminar este archivo?\n{file_path}",
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            try:
                os.remove(file_path) if os.path.isfile(file_path) else shutil.rmtree(
                    file_path
                )
                log_custom(
                    message=f"Archivo eliminado: {file_path}",
                    level="INFO",
                    file=LOGFILE,
                )
                self.load_files(self.current_folder)  # Refresca la lista
            except Exception as e:
                log_custom(
                    message=f"Error al eliminar: {e}", level="ERROR", file=LOGFILE
                )

    def open_with_feh_direct(self, file_path):
        """Abre directamente con feh optimizado sin vista previa."""
        try:
            feh_cmd = self.get_feh_optimized()
            log_custom(
                message=f"Abriendo directamente con feh: {' '.join(feh_cmd)} {file_path}",
                level="INFO",
                file=LOGFILE,
            )

            subprocess.Popen(
                feh_cmd + [file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: os.nice(5),
            )
        except Exception as e:
            log_custom(
                message=f"Error abriendo con feh: {e}",
                level="ERROR",
                file=LOGFILE,
            )
            self.open_file_fallback(file_path)


# Ejecutar la aplicación GTK
if __name__ == "__main__":
    app = FileExplorer()
    Gtk.main()
    