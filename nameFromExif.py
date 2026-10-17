import argparse
import os
import random
from datetime import datetime

import exifread
from PIL import ExifTags, Image
from pillow_heif import register_heif_opener

DEFAULT_FORMAT = "IMG_%Y%m%d_%H%M%S.jpg"
JPEG_EXTENSIONS = (".jpg", ".jpeg")
HEIF_EXTENSIONS = (".heic", ".heif")
SUPPORTED_EXTENSIONS = JPEG_EXTENSIONS + HEIF_EXTENSIONS

register_heif_opener(thumbnails=False)


def get_pillow_datetime_original(file_path: str) -> str | None:
    with Image.open(file_path) as image:
        exif = image.getexif()
        date_str = exif.get(36867)
        if date_str:
            return str(date_str)

        # Some files with a .HEIC extension contain JPEG data. Pillow exposes
        # their DateTimeOriginal value through the nested EXIF IFD.
        date_str = exif.get_ifd(ExifTags.IFD.Exif).get(36867)
        return str(date_str) if date_str else None


parser = argparse.ArgumentParser(
    description="Renames image files in folder to name based on 'EXIF DateTimeOriginal' field"
)
parser.add_argument("-p", "--path", dest="path", required=True, help="path")
parser.add_argument(
    "-f",
    "--format",
    dest="format",
    default=DEFAULT_FORMAT,
    help="new name format (HEIF files keep their original extension with the default)",
)
args = parser.parse_args()

only_files = [
    f for f in os.listdir(args.path) if os.path.isfile(os.path.join(args.path, f))
]
for file in only_files:
    extension = os.path.splitext(file)[1]
    if extension.lower() not in SUPPORTED_EXTENSIONS:
        continue
    log_message = file
    try:
        file_path = os.path.join(args.path, file)
        if extension.lower() in HEIF_EXTENSIONS:
            date_str = get_pillow_datetime_original(file_path)
        else:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f)
            date_str = tags.get("EXIF DateTimeOriginal") or tags.get(
                "Image DateTimeOriginal"
            )

        if not date_str:
            continue
        dt = datetime.strptime(str(date_str), "%Y:%m:%d %H:%M:%S")
        new_name = dt.strftime(args.format)

        # The default format predates HEIF support and ends in ".jpg". Keep a
        # HEIF image's real extension; renaming it to JPEG would not convert it.
        if extension.lower() in HEIF_EXTENSIONS and args.format == DEFAULT_FORMAT:
            new_name = os.path.splitext(new_name)[0] + extension

        if file != new_name:
            if os.path.exists(os.path.join(args.path, new_name)):
                stem, new_extension = os.path.splitext(new_name)
                while os.path.exists(os.path.join(args.path, new_name)):
                    new_name = f"{stem}_{random.randint(1000, 9999)}{new_extension}"
            os.rename(os.path.join(args.path, file), os.path.join(args.path, new_name))
            log_message += f" --> {new_name}"

    except Exception as ex:
        log_message += f" --X ERROR: {type(ex).__name__} {ex}"

    if log_message != file:
        print(log_message)
