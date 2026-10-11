"""Exporta el logo y los favicons conservando el arte original del cliente."""

from pathlib import Path

from PIL import Image, ImageChops, ImageOps

IMAGE_DIRECTORY = Path(__file__).resolve().parents[1] / "static" / "images"


def main():
    source = IMAGE_DIRECTORY / "logo-betesda-original.png"
    with Image.open(source) as original:
        image = original.convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        background.alpha_composite(image)
        image = background.convert("RGB")

    # Recorta únicamente el margen blanco exterior y deja espacio alrededor del dibujo.
    difference = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
    bounds = difference.convert("L").point(lambda pixel: 255 if pixel > 12 else 0).getbbox()
    if bounds is None:
        raise ValueError("El archivo del logo no contiene un dibujo visible.")
    left, top, right, bottom = bounds
    padding = 32
    artwork = image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )
    logo = ImageOps.pad(artwork, (1000, 640), method=Image.Resampling.LANCZOS, color="white")
    logo.save(IMAGE_DIRECTORY / "logo-betesda.png", optimize=True)
    square = ImageOps.pad(artwork, (256, 256), method=Image.Resampling.LANCZOS, color="white")
    square.save(IMAGE_DIRECTORY / "favicon-betesda.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for size in (16, 32):
        square.resize((size, size), Image.Resampling.LANCZOS).save(
            IMAGE_DIRECTORY / f"favicon-betesda-{size}.png", optimize=True
        )
    square.resize((180, 180), Image.Resampling.LANCZOS).save(
        IMAGE_DIRECTORY / "apple-touch-icon-betesda.png", optimize=True
    )
    print("Logo y favicons exportados desde el original del cliente.")


if __name__ == "__main__":
    main()
