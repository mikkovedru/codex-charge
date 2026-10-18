"""Convert approved symbol and lockup artwork into runtime and documentation assets."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def prepare(symbol: Path, lockup: Path) -> None:
    assets = ROOT / "recharge_ai_task" / "assets"
    docs = ROOT / "docs" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    with Image.open(symbol) as source:
        artwork = ImageOps.contain(source.convert("RGB"), (512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (512, 512), "white")
    canvas.paste(artwork, ((512-artwork.width)//2, (512-artwork.height)//2))
    canvas.save(assets / "logo-symbol.png", optimize=True)
    # A dark outside edge and the artwork's opaque white background stay
    # visible on light and dark panels. No symbolic theme recoloring is used.
    framed = ImageOps.expand(canvas.resize((496, 496), Image.Resampling.LANCZOS), border=8, fill="#101820")
    for size in ICON_SIZES:
        framed.resize((size, size), Image.Resampling.LANCZOS).save(assets / f"icon-{size}.png", optimize=True)
    framed.save(assets / "recharge-ai-task.ico", sizes=[(s,s) for s in ICON_SIZES if s <= 256])
    with Image.open(lockup) as source:
        for size, destination in ((128, assets / "logo-lockup.png"), (512, docs / "logo-lockup.png")):
            image = ImageOps.contain(source.convert("RGB"), (size, size), Image.Resampling.LANCZOS)
            image.save(destination, optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", type=Path, required=True, help="Approved text-free artwork")
    parser.add_argument("--lockup", type=Path, required=True, help="Approved artwork with the project name")
    args = parser.parse_args()
    prepare(args.symbol, args.lockup)
