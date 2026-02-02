import gi
import os
import subprocess
import shutil
import mimetypes
import sys
import threading
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
sys.path.insert(
    1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)
from routes import NAS_MOUNT, NAS_PATH

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib
from log import log_custom

LOGFILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "logs", "nas_explorer.log"
)


class NasExplorer(Gtk.Window):
    def __init__(self):
        super().__init__(title="NAS Browser")
        self.set_default_size(900, 600)
        self.set_border_width(10)

        if os.path.ismount(NAS_MOUNT):
            path = NAS_PATH
            log_custom(
                message=f"Mounted NAS detected. Using NAS path: {path}",
                level="INFO",
                file=LOGFILE,
            )
        else:
            path = os.path.join("scripts", "backend", "API-NASA")
            log_custom(
                message=f"NAS not available. Using local folder: {path}",
                level="INFO",
                file=LOGFILE,
            )

        self.base_folder = os.path.abspath(path)
        self.current_folder = self.base_folder
        log_custom(message=self.current_folder, level="INFO", file=LOGFILE)
        if not os.path.exists(self.current_folder):
            log_custom(
                message="Path does not exist; download images first.",
                level="WARNING",
                file=LOGFILE,
            )
            exit(1)

        # Thumbnail cache
        self.thumbnail_cache = {}
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "nas_explorer")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        #  List of files and folders with icons
        self.liststore = Gtk.ListStore(str, str, str)  # (Icon, Name, Path)

        #  Copy/paste helpers
        self.copied_path = None

        #  Navigation container
        self.nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        #  File view
        self.treeview = Gtk.TreeView(model=self.liststore)

        #  Icon column
        icon_renderer = Gtk.CellRendererPixbuf()
        column_icon = Gtk.TreeViewColumn("Type", icon_renderer, icon_name=0)
        self.treeview.append_column(column_icon)

        #  Name column
        text_renderer = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn("Name", text_renderer, text=1)
        self.treeview.append_column(column_name)

        self.treeview.connect("row-activated", self.on_double_click)
        self.treeview.connect("button-press-event", self.on_right_click)

        #  Main container with scroll
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.treeview)

        #  Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.pack_start(self.nav_box, False, False, 0)
        vbox.pack_start(scrolled_window, True, True, 0)

        self.add(vbox)
        self.connect("destroy", Gtk.main_quit)

        #  Load files after UI initialization
        self.load_files(self.current_folder)

        self.show_all()

    def get_available_image_viewer(self):
        """Pick the best available viewer for large NOAA TIFF files, prioritizing speed."""
        viewers = [
            # Más rápidos para TIFF grandes
            ("gthumb", ["gthumb"]),  # Muy rápido con TIFF
            ("gpicview", ["gpicview"]),  # Ligero y rápido
            ("mirage", ["mirage"]),  # Específico para imágenes
            ("ristretto", ["ristretto"]),  # Xfce, muy eficiente
            ("xviewer", ["xviewer"]),  # MATE, optimized
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

        # Fallback to xdg-open if nothing else is available
        return ["xdg-open"]

    def get_feh_optimized(self):
        """Return feh command optimized for normal images."""
        try:
            # Ensure feh is available
            subprocess.run(
                ["which", "feh"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # feh command optimized for speed
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
            # If feh is missing, fall back to xdg-open
            return ["xdg-open"]

    def check_imagemagick_available(self):
        """Check whether ImageMagick is available."""
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
        """Create thumbnails on a background thread to avoid blocking the UI."""

        def generate_thumbnail():
            try:
                # Check if ImageMagick is available
                if not self.check_imagemagick_available():
                    log_custom(
                        message="ImageMagick not found. Install with: sudo apt install imagemagick",
                        level="WARNING",
                        file=LOGFILE,
                    )
                    GLib.idle_add(callback, None)
                    return

                # Use ImageMagick convert to generate a quick thumbnail
                thumbnail_path = os.path.join(
                    self.cache_dir, f"{os.path.basename(file_path)}_thumb.jpg"
                )

                if not os.path.exists(thumbnail_path):
                    # Generate a small, fast thumbnail
                    subprocess.run(
                        [
                            "convert",
                            file_path,
                            "-thumbnail",
                            "200x200>",  # Max 200px while keeping aspect
                            "-quality",
                            "70",  # Lower quality for speed
                            thumbnail_path,
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                # Call the callback on the main thread
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
        """Show a quick preview of the TIFF before fully opening it."""
        dialog = Gtk.Dialog(
            title=f"Preview - {os.path.basename(file_path)}",
            parent=self,
            modal=True,
        )
        dialog.set_default_size(400, 400)

        # Buttons
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.add_button("Open full", Gtk.ResponseType.OK)

        # Container for the image
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
                # Show generic icon on failure
                image_widget.set_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
                image_widget.show()

        # Generate thumbnail
        self.create_thumbnail_async(file_path, on_thumbnail_ready)

        response = dialog.run()
        dialog.destroy()

        return response == Gtk.ResponseType.OK

    def is_noaa_image(self, file_path):
        """Detect whether the image is NOAA based on path or size hints."""
        path_lower = file_path.lower()

        # Detect by path
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

        # Consider very large files as possible NOAA assets
        try:
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # >50MB likely satellite imagery
                return True
        except OSError:
            pass

        return False

    def open_tiff_optimized(self, file_path):
        """Open TIFF files with specific logic: NOAA -> preview first, others -> feh."""

        # Detect whether the image is NOAA/satellite
        if self.is_noaa_image(file_path):
            file_size = os.path.getsize(file_path)
            log_custom(
                message=f"NOAA/satellite image detected ({file_size / 1024 / 1024:.1f}MB), showing preview",
                level="INFO",
                file=LOGFILE,
            )

            # Always show preview first for NOAA
            if not self.show_image_preview_dialog(file_path):
                return  # User cancelled

            # If the user wants full view, use the best available viewer
            viewer_cmd = self.get_available_image_viewer()
        else:
            # For normal images, use feh directly
            log_custom(
                message="Normal image detected, using feh",
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

            # Run with lower priority to avoid hogging the system
            process = subprocess.Popen(
                viewer_cmd + [file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: os.nice(5),  # Lower priority
            )

        except Exception as e:
            log_custom(
                message=f"Error opening optimized TIFF: {e}",
                level="ERROR",
                file=LOGFILE,
            )
            # Fallback to original method
            self.open_file_fallback(file_path)

    def open_file_fallback(self, file_path):
        """Fallback file opening method."""
        try:
            subprocess.Popen(
                ["xdg-open", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            log_custom(
                message=f"Error in fallback: {e}",
                level="ERROR",
                file=LOGFILE,
            )

    def update_navigation_bar(self):
        """Update navigation bar with clickable buttons (limited to /images)."""
        for child in self.nav_box.get_children():
            self.nav_box.remove(child)

        path_parts = (
            self.current_folder.replace(self.base_folder, "")
            .strip(os.sep)
            .split(os.sep)
        )
        built_path = self.base_folder

        #  Root button (/images)
        root_button = Gtk.Button(label="API ISS Data")
        root_button.connect("clicked", self.on_nav_button_click, self.base_folder)
        self.nav_box.pack_start(root_button, False, False, 0)

        #  Create buttons for subfolders
        for part in path_parts:
            if part:
                built_path = os.path.join(built_path, part)
                button = Gtk.Button(label=part)
                button.connect("clicked", self.on_nav_button_click, built_path)
                self.nav_box.pack_start(
                    Gtk.Label(label=" / "), False, False, 0
                )  # Separator "/"
                self.nav_box.pack_start(button, False, False, 0)

        self.nav_box.show_all()

    def on_nav_button_click(self, widget, folder):
        """Change folder only if it is inside /images."""
        if folder.startswith(self.base_folder):
            self.load_files(folder)

    def load_files(self, folder):
        """Load the file list for the given folder with icons."""
        if not folder.startswith(self.base_folder):  # Restrict leaving /images
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
                message=f"ERROR: Unable to access folder '{folder}'.",
                level="ERROR",
                file=LOGFILE,
            )

    def get_file_icon(self, file_path):
        """Return the appropriate icon for files and folders."""
        if os.path.isdir(file_path):
            return "folder"
        else:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                if "image" in mime_type:
                    return "image-x-generic"
                elif "text" in mime_type:
                    return "text-x-generic"
                elif "audio" in mime_type:
                    return "audio-x-generic"
                elif "video" in mime_type:
                    return "video-x-generic"
            return "unknown"

    def on_double_click(self, treeview, path, column):
        """Open files or navigate folders on double click."""
        model = treeview.get_model()
        file_path = model[path][2]  # Full path

        if os.path.isdir(file_path):  # If folder, navigate
            self.load_files(file_path)
        else:
            self.open_file(file_path)

    def on_right_click(self, widget, event):
        """Show context menu with download option."""
        if event.button == Gdk.BUTTON_SECONDARY:  # Clic derecho
            selection = self.treeview.get_selection()
            model, tree_iter = selection.get_selected()
            if not tree_iter:
                return  # Do nothing if nothing is selected

            file_path = model[tree_iter][2]

            menu = Gtk.Menu()

            #  Option "Open"
            open_item = Gtk.MenuItem(label="Open")
            open_item.connect("activate", lambda _: self.open_file(file_path))
            menu.append(open_item)

            #  TIFF-specific options
            if file_path.lower().endswith((".tif", ".tiff")):
                if self.is_noaa_image(file_path):
                    preview_item = Gtk.MenuItem(label="Preview (NOAA)")
                    preview_item.connect(
                        "activate", lambda _: self.show_image_preview_dialog(file_path)
                    )
                    menu.append(preview_item)
                else:
                    quick_view_item = Gtk.MenuItem(label="Quick view (feh)")
                    quick_view_item.connect(
                        "activate", lambda _: self.open_with_feh_direct(file_path)
                    )
                    menu.append(quick_view_item)

            #  Option "Download"
            download_item = Gtk.MenuItem(label="Download")
            download_item.connect("activate", lambda _: self.download_file(file_path))
            menu.append(download_item)

            #  Opción "Delete"
            # delete_item = Gtk.MenuItem(label="Delete")
            # delete_item.connect("activate", lambda _: self.delete_file(file_path))
            # menu.append(delete_item)

            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)

    def download_file(self, file_path):
        """Download a file or folder to a user-selected destination."""
        dialog = Gtk.FileChooserDialog(
            title="Select where to save the file",
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
        dialog.set_current_name(os.path.basename(file_path))  # Default name

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            dest_path = dialog.get_filename()  # User-selected path

            # If folder, download its contents
            try:
                if os.path.isdir(file_path):
                    shutil.copytree(file_path, dest_path)
                else:
                    shutil.copy2(file_path, dest_path)

                log_custom(
                    message=f"File downloaded to: {dest_path}",
                    level="INFO",
                    file=LOGFILE,
                )
            except FileExistsError:
                log_custom(
                    message=f"File already exists at destination: {dest_path}",
                    level="WARNING",
                    file=LOGFILE,
                )
            except Exception as e:
                log_custom(message=f"Download error: {e}", level="ERROR", file=LOGFILE)

        dialog.destroy()

    def open_file(self, file_path):
        """Open the file with type-specific optimizations."""
        try:
            if file_path.lower().endswith((".tif", ".tiff")):
                # Use optimized method for TIFF
                self.open_tiff_optimized(file_path)
            elif file_path.endswith(".txt"):
                subprocess.run(
                    [
                        "yad",
                        "--text-info",
                        f"--filename={file_path}",
                        "--title=File contents",
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

        except Exception as e:
            log_custom(
                message=f"Error opening file: {e}",
                level="ERROR",
                file=LOGFILE,
            )

    def delete_file(self, file_path):
        """Delete a file with confirmation."""
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Are you sure you want to delete this file?\n{file_path}",
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            try:
                os.remove(file_path) if os.path.isfile(file_path) else shutil.rmtree(
                    file_path
                )
                log_custom(
                    message=f"File deleted: {file_path}",
                    level="INFO",
                    file=LOGFILE,
                )
                self.load_files(self.current_folder)  # Refresh list
            except Exception as e:
                log_custom(message=f"Error deleting: {e}", level="ERROR", file=LOGFILE)

    def open_with_feh_direct(self, file_path):
        """Open directly with feh without preview."""
        try:
            feh_cmd = self.get_feh_optimized()
            log_custom(
                message=f"Opening directly with feh: {' '.join(feh_cmd)} {file_path}",
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
                message=f"Error opening with feh: {e}",
                level="ERROR",
                file=LOGFILE,
            )
            self.open_file_fallback(file_path)


# Ejecutar la aplicación GTK
if __name__ == "__main__":
    app = NasExplorer()
    Gtk.main()
