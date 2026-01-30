import pathlib
import os


def get_size(file_path):
    return os.path.getsize(file_path)


def get_mean(sizes):
    return sum(sizes) / len(sizes) if sizes else 0


def size_to_mb(size):
    return size / 1024 / 1024


images_path = pathlib.Path(__file__).parent / "API-NASA"

jpg_count = 0
tiff_count = 0
image_files = []  # Lista de tuplas (archivo, tamaño)

for file in images_path.rglob("*"):
    if file.is_file():  # Solo archivos
        if file.suffix == ".JPG":
            jpg_count += 1
            size = get_size(file)
            image_files.append((file, size))
        elif file.suffix.lower() == ".tif":
            tiff_count += 1
            size = get_size(file)
            image_files.append((file, size))

print(f"JPG: {jpg_count}")
print(f"TIFF: {tiff_count}")
print(f"Total: {jpg_count + tiff_count}")

if image_files:
    sizes = [size for _, size in image_files]
    print(f"Media: {size_to_mb(get_mean(sizes)):.2f} MB")

    # Encontrar archivo más grande y más pequeño
    max_file = max(image_files, key=lambda x: x[1])
    min_file = min(image_files, key=lambda x: x[1])

    print(f"Max: {size_to_mb(max_file[1]):.2f} MB - {max_file[0]}")
    print(f"Min: {size_to_mb(min_file[1]):.2f} MB - {min_file[0]}")
else:
    print("No se encontraron imágenes")
