"""pxl-cleanup: turn AI-generated pixel-style images into true pixel art."""
from .stages import (
    binarize_alpha,
    count_colors,
    place_on_canvas,
    recover_grid,
    reduce_palette,
    remove_background,
)

__version__ = "0.1.1"

__all__ = [
    "binarize_alpha",
    "count_colors",
    "place_on_canvas",
    "recover_grid",
    "reduce_palette",
    "remove_background",
]
