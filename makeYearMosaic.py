from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".heif",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a year-shaped collage from photo thumbnails."
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing the source photos",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("2026_mosaic.png"),
        help="Output PNG file",
    )

    parser.add_argument(
        "--text",
        default="2026",
        help="Text to create from the photos",
    )

    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="How many times to use each photo",
    )

    parser.add_argument(
        "--orientation",
        choices=("portrait", "landscape"),
        default="landscape",
        help="A4 page orientation",
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Output DPI",
    )

    parser.add_argument(
        "--margin",
        type=int,
        default=140,
        help="Page margin in pixels",
    )

    parser.add_argument(
        "--gap",
        type=int,
        default=6,
        help="Gap between thumbnails in pixels",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Random seed for repeatable layouts",
    )

    parser.add_argument(
        "--font",
        type=Path,
        help="TTF font used for the year",
    )

    parser.add_argument(
        "--background",
        default="white",
        help="Background color",
    )

    parser.add_argument(
        "--preview",
        type=Path,
        help="Optional smaller JPEG preview file",
    )

    return parser.parse_args()


def a4_size(dpi: int, orientation: str) -> tuple[int, int]:
    # A4 = 210 x 297 mm
    width = round(210 / 25.4 * dpi)
    height = round(297 / 25.4 * dpi)

    if orientation == "landscape":
        width, height = height, width

    return width, height


def find_photos(folder: Path) -> list[Path]:
    photos = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    return sorted(photos)


def load_photo(path: Path) -> Image.Image:
    image = Image.open(path)

    # Apply EXIF rotation from camera/phone metadata.
    image = ImageOps.exif_transpose(image)

    return image.convert("RGB")


def make_thumbnail(
    image: Image.Image,
    size: int,
) -> Image.Image:
    """
    Crop the photo to a square without stretching it.
    """
    return ImageOps.fit(
        image,
        (size, size),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def find_font() -> Path:
    """
    Try several common bold fonts.
    """
    possible_fonts = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]

    for font in possible_fonts:
        if font.exists():
            return font

    raise RuntimeError(
        "Could not find a suitable bold font. "
        "Edit find_font() and specify a .ttf font file."
    )


def make_text_mask(
    page_size: tuple[int, int],
    text: str,
    margin: int,
    font_path: Path | None = None,
) -> Image.Image:
    """
    Create a grayscale image where the text is white
    and the rest is black.
    """
    page_width, page_height = page_size

    mask = Image.new(
        "L",
        page_size,
        0,
    )

    if not font_path:
        font_path = find_font()

    # Start very large and shrink until the text fits.
    font_size = int(page_height * 0.75)

    while font_size > 20:
        font = ImageFont.truetype(
            str(font_path),
            font_size,
        )

        draw = ImageDraw.Draw(mask)

        bbox = draw.textbbox(
            (0, 0),
            text,
            font=font,
            stroke_width=0,
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if (
            text_width <= page_width - margin * 2
            and text_height <= page_height - margin * 2
        ):
            break

        font_size -= 10

    draw = ImageDraw.Draw(mask)

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (page_width - text_width) // 2 - bbox[0]
    y = (page_height - text_height) // 2 - bbox[1]

    draw.text(
        (x, y),
        text,
        fill=255,
        font=font,
    )

    return mask


def candidate_positions(
    mask: Image.Image,
    thumb_size: int,
    gap: int,
    margin: int,
) -> list[tuple[int, int]]:
    """
    Find grid positions where a thumbnail can be placed.

    A thumbnail is accepted if its center lies inside
    the text mask.
    """
    width, height = mask.size

    step = thumb_size + gap

    positions = []

    for y in range(margin, height - thumb_size - margin + 1, step):
        for x in range(margin, width - thumb_size - margin + 1, step):

            center_x = x + thumb_size // 2
            center_y = y + thumb_size // 2

            if mask.getpixel((center_x, center_y)) > 127:
                positions.append((x, y))

    return positions


def choose_thumbnail_size(
    mask: Image.Image,
    photo_count: int,
    gap: int,
    margin: int,
) -> tuple[int, list[tuple[int, int]]]:
    """
    Find the largest thumbnail size that provides
    at least one position for every photo.
    """
    if photo_count <= 0:
        raise ValueError("No photos found")

    # Start large and gradually reduce.
    for thumb_size in range(300, 29, -2):

        positions = candidate_positions(
            mask,
            thumb_size,
            gap,
            margin,
        )

        if len(positions) >= photo_count:
            return thumb_size, positions

    raise RuntimeError(
        "Could not fit all photos into the text. " "Try reducing --gap or --margin."
    )


def distribute_positions(
    positions: list[tuple[int, int]],
    photo_count: int,
    rng: random.Random,
) -> list[tuple[int, int]]:
    """
    Spread photos across the entire available text area,
    instead of clustering them in one part of the number.
    """
    if photo_count >= len(positions):
        return positions[:photo_count]

    shuffled = positions[:]
    rng.shuffle(shuffled)

    # Select approximately evenly from the shuffled positions.
    step = len(shuffled) / photo_count

    selected = []

    for i in range(photo_count):
        index = min(
            int(i * step),
            len(shuffled) - 1,
        )
        selected.append(shuffled[index])

    return selected


def create_mosaic(
    photos: list[Path],
    text: str,
    page_size: tuple[int, int],
    margin: int,
    gap: int,
    seed: int,
    background: str,
    font_path: Path | None = None,
) -> tuple[Image.Image, int]:

    rng = random.Random(seed)

    mask = make_text_mask(
        page_size,
        text,
        margin,
        font_path,
    )

    thumb_size, all_positions = choose_thumbnail_size(
        mask,
        len(photos),
        gap,
        margin,
    )

    positions = distribute_positions(
        all_positions,
        len(photos),
        rng,
    )

    rng.shuffle(photos)
    rng.shuffle(positions)

    result = Image.new(
        "RGB",
        page_size,
        background,
    )

    print(f"Photos:              {len(photos)}")
    print(f"Available positions: {len(all_positions)}")
    print(f"Thumbnail size:      {thumb_size}px")
    print(f"Page size:           {page_size[0]} x {page_size[1]}")

    for index, (photo_path, position) in enumerate(
        zip(photos, positions),
        start=1,
    ):
        try:
            image = load_photo(photo_path)

            thumbnail = make_thumbnail(
                image,
                thumb_size,
            )

            result.paste(
                thumbnail,
                position,
            )

            print(f"[{index:4}/{len(photos)}] " f"{photo_path.name}")

        except Exception as exc:
            print(f"WARNING: unable to process " f"{photo_path}: {exc}")

    return result, thumb_size


def save_preview(
    image: Image.Image,
    path: Path,
) -> None:
    preview = image.copy()

    max_width = 1200

    if preview.width > max_width:
        scale = max_width / preview.width

        preview = preview.resize(
            (
                round(preview.width * scale),
                round(preview.height * scale),
            ),
            Image.Resampling.LANCZOS,
        )

    preview.save(
        path,
        "JPEG",
        quality=90,
        optimize=True,
    )


def main() -> None:
    args = parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Input directory does not exist: " f"{args.input_dir}")

    photos = find_photos(args.input_dir)

    if not photos:
        raise SystemExit(f"No supported photos found in " f"{args.input_dir}")

    original_count = len(photos)
    photos = photos * args.repeat

    print(
        f"Found {original_count} unique photos; "
        f"using {len(photos)} tiles ({args.repeat}x each)."
    )

    page_size = a4_size(
        args.dpi,
        args.orientation,
    )

    result, thumb_size = create_mosaic(
        photos=photos,
        text=args.text,
        page_size=page_size,
        margin=args.margin,
        gap=args.gap,
        seed=args.seed,
        background=args.background,
        font_path=args.font,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.save(
        args.output,
        "PNG",
        dpi=(args.dpi, args.dpi),
    )

    print()
    print(f"Saved: {args.output}")
    print(f"Thumbnail size: {thumb_size}px")

    if args.preview:
        args.preview.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        save_preview(
            result,
            args.preview,
        )

        print(f"Preview: {args.preview}")


if __name__ == "__main__":
    main()
