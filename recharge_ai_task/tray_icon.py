"""A full-slot icon whose contrast does not depend on the panel theme."""
from PIL import Image, ImageDraw

IDLE_COLOR = "#ffcc00"
RUNNING_COLOR = "#00df70"


def make_icon(color: str) -> Image.Image:
    # Opaque black/white halves remain distinct even against matching panels.
    # The R+ glyph is drawn geometrically, with no theme or font dependency.
    scale = 4
    image = Image.new("RGBA", (64 * scale, 64 * scale), "#000000")
    draw = ImageDraw.Draw(image)
    def rect(bounds, fill):
        draw.rectangle(tuple(v * scale for v in bounds), fill=fill)
    rect((2, 2, 61, 61), "#ffffff")
    rect((4, 4, 30, 59), "#000000")
    rect((9, 13, 23, 19), "#ffffff")
    rect((9, 13, 15, 45), "#ffffff")
    rect((9, 26, 23, 32), "#ffffff")
    rect((20, 16, 26, 29), "#ffffff")
    draw.polygon([(x * scale, y * scale) for x, y in ((15,29),(21,29),(28,45),(21,45))], fill="#ffffff")
    rect((35, 26, 55, 32), "#000000")
    rect((42, 19, 48, 39), "#000000")
    rect((5, 52, 58, 58), color)
    return image.resize((64, 64), Image.Resampling.LANCZOS)
