"""Command line: pxl-cleanup trex.jpg wolf.jpg --out sprites/"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from . import __version__
from .stages import count_colors, place_on_canvas, recover_grid, reduce_palette, remove_background


def clean(path: Path, out_dir: Path, *, pixel_size: int | None, colors: int,
          canvas: int, margin: int, ground_band: float, fill_holes: bool = True) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)

    nobg = remove_background(Image.open(path), ground_band=ground_band, fill_holes=fill_holes)
    nobg.save(out_dir / "1_nobg.png")

    grid = recover_grid(nobg, pixel_size=pixel_size)
    grid.save(out_dir / "2_grid.png")

    pal = reduce_palette(grid, colors)
    pal.save(out_dir / "3_palette.png")

    final = place_on_canvas(pal, canvas, margin)
    final.save(out_dir / "4_final.png")

    return (f"{path.name}: {nobg.width}x{nobg.height} -> {grid.width}x{grid.height} sprite, "
            f"{count_colors(final)} colors, {canvas}x{canvas} canvas -> {out_dir / '4_final.png'}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="pxl-cleanup",
        description="Turn AI-generated pixel-style images into true pixel art sprites.",
    )
    p.add_argument("inputs", nargs="+", type=Path, help="source images (PNG, JPG, WebP)")
    p.add_argument("-o", "--out", type=Path, default=Path("out"),
                   help="output folder; each input gets a subfolder named after it (default: out)")
    p.add_argument("-s", "--pixel-size", type=int, default=6,
                   help="width of one fake pixel in the source; bigger = smaller sprite, 0 = auto-detect (default: 6)")
    p.add_argument("-c", "--colors", type=int, default=24,
                   help="palette size; 15 matches the Sega Genesis per-sprite limit (default: 24)")
    p.add_argument("--canvas", type=int, default=128, help="square canvas size in pixels (default: 128)")
    p.add_argument("--margin", type=int, default=4, help="empty pixels below the feet (default: 4)")
    p.add_argument("--ground-band", type=float, default=0.80,
                   help="brown pixels below this fraction of the height are treated as ground (default: 0.80; 1.0 disables)")
    p.add_argument("--keep-enclosed-white", action="store_true",
                   help="keep flat white areas inside the sprite instead of treating them as trapped background "
                        "(use for sprites with a plain white patch, like a penguin's belly)")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    failed = 0
    for path in args.inputs:
        try:
            print(clean(path, args.out / path.stem, pixel_size=args.pixel_size or None,
                        colors=args.colors, canvas=args.canvas, margin=args.margin,
                        ground_band=args.ground_band, fill_holes=not args.keep_enclosed_white))
        except Exception as e:  # keep going through a batch
            failed += 1
            print(f"{path.name}: FAILED: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
