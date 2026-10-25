"""Tests run on a synthetic "fake pixel art" image: a small sprite drawn on a
real grid, upscaled 6x, then put on a white background with a dirt patch,
which is what an image model's pixel-style output looks like."""
import numpy as np
import pytest
from PIL import Image

from pxl_cleanup import (
    count_colors,
    place_on_canvas,
    recover_grid,
    reduce_palette,
    remove_background,
)

SCALE = 6
OUTLINE, BODY, BELLY = (20, 20, 20), (60, 140, 60), (240, 235, 220)


def make_sprite() -> np.ndarray:
    """20x16 true-pixel sprite: dark outline, green body, near-white belly."""
    s = np.zeros((16, 20, 4), np.uint8)
    s[1:15, 2:18] = (*OUTLINE, 255)
    s[2:14, 3:17] = (*BODY, 255)
    s[7:12, 7:13] = (*BELLY, 255)  # light area enclosed by the outline
    return s


@pytest.fixture
def fake_pixel_art() -> Image.Image:
    sprite = Image.fromarray(make_sprite(), "RGBA").resize((20 * SCALE, 16 * SCALE), Image.NEAREST)
    img = Image.new("RGB", (240, 200), (255, 255, 255))
    dirt = Image.new("RGB", (160, 12), (120, 80, 40))
    img.paste(dirt, (40, 180))
    img.paste(sprite, (60, 84), sprite)
    return img


def test_remove_background_keeps_enclosed_light_pixels(fake_pixel_art):
    out = remove_background(fake_pixel_art)
    a = np.array(out)
    assert out.size == (16 * SCALE, 14 * SCALE)  # cropped to the outline, dirt removed
    belly = a[6 * SCALE + 3, 6 * SCALE + 3]
    assert belly[3] == 255 and tuple(belly[:3]) == BELLY


def test_recover_grid_returns_true_resolution(fake_pixel_art):
    grid = recover_grid(remove_background(fake_pixel_art), pixel_size=SCALE)
    assert grid.size == (16, 14)
    assert set(np.unique(np.array(grid)[..., 3])) <= {0, 255}


def test_reduce_palette_caps_colors():
    rng = np.random.default_rng(0)
    a = np.dstack([rng.integers(0, 256, (32, 32, 3)), np.full((32, 32), 255)]).astype(np.uint8)
    out = reduce_palette(Image.fromarray(a, "RGBA"), colors=8)
    assert count_colors(out) <= 8


def test_place_on_canvas_shares_baseline():
    a = place_on_canvas(Image.new("RGBA", (40, 30), (255, 0, 0, 255)), 128, 4)
    b = place_on_canvas(Image.new("RGBA", (90, 70), (0, 0, 255, 255)), 128, 4)
    for img in (a, b):
        alpha = np.array(img)[..., 3]
        assert img.size == (128, 128)
        assert np.where(alpha.any(1))[0].max() == 128 - 4 - 1


def test_place_on_canvas_rejects_oversized_sprite():
    with pytest.raises(ValueError):
        place_on_canvas(Image.new("RGBA", (130, 50), (0, 0, 0, 255)), 128, 4)
