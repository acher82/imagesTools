import argparse
import os
import random
from datetime import datetime

import exifread

parser = argparse.ArgumentParser(
    description="Renames image files in folder to name based on 'EXIF DateTimeOriginal' field"
)
parser.add_argument("-p", "--path", dest="path", required=True, help="path")
parser.add_argument(
    "-f",
    "--format",
    dest="format",
    default="IMG_%Y%m%d_%H%M%S.jpg",
    help="new name format",
)
args = parser.parse_args()

only_files = [
    f for f in os.listdir(args.path) if os.path.isfile(os.path.join(args.path, f))
]
for file in only_files:
    if not (file.lower().endswith(".jpg") or file.lower().endswith(".jpeg")):
        continue
    log_message = file
    try:
        f = open(os.path.join(args.path, file), "rb")
        tags = exifread.process_file(f)
        f.close()

        if "EXIF DateTimeOriginal" not in tags:
            continue
        date_str = tags["EXIF DateTimeOriginal"]
        dt = datetime.strptime(date_str.__str__(), "%Y:%m:%d %H:%M:%S")
        new_name = dt.strftime(args.format)
        if file != new_name:
            if os.path.exists(os.path.join(args.path, new_name)):
                new_name = new_name.replace(
                    ".jpg", f"_{random.randint(1000, 9999)}.jpg"
                )
            os.rename(os.path.join(args.path, file), os.path.join(args.path, new_name))
            log_message += f" --> {new_name}"

    except Exception as ex:
        log_message += f" --X ERROR: {type(ex).__name__} {ex}"

    if log_message != file:
        print(log_message)
