"""The four cleanup stages. Each takes and returns a PIL RGBA image."""
from __future__ import annotations

import logging

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.cluster.vq import kmeans2


def remove_background(img: Image.Image, ground_band: float = 0.80,
                      fill_holes: bool = True, hole_min: float = 0.003) -> Image.Image:
    """Stage 1: remove a plain light background and any ground patch, then crop.

    Near-white pixels, plus warm brown pixels in the bottom part of the image,
    are treated as background when they connect to the image border. The
    sprite's dark outline stops the fill, so light areas enclosed by the
    outline (teeth, eye highlights, a pale belly) are kept.

    Background can also be trapped inside the sprite, for example between legs
    whose feet touch or that stand on a shadow line. With fill_holes, an
    enclosed white patch is removed too when it is the same flat color as the
    outer background and covers at least hole_min of the sprite's area.
    Shaded or off-white areas (eye whites, cream bellies) and tiny highlights
    are kept.

    ground_band: fraction of the image height below which brown "dirt" pixels
    count as background. Set to 1.0 to disable ground removal.
    """
    rgb = np.array(img.convert("RGB")).astype(np.int16)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    h, w = mn.shape

    white = (mn > 215) & (mx - mn < 30)
    rows = np.arange(h)[:, None].repeat(w, 1)
    ground = (r > g) & (g > b) & (r - b > 35) & (mx > 70) & (rows > int(h * ground_band))

    labels, _ = ndimage.label(white | ground)
    edge = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    background = np.isin(labels, edge[edge > 0])

    if fill_holes:
        background |= _enclosed_background(rgb, white, background, hole_min)
    # Swallow the 1-2px light JPEG halo between the background and the outline.
    background |= ndimage.binary_dilation(background, iterations=2) & (mn > 150)

    alpha = np.where(background, 0, 255).astype(np.uint8)
    if not alpha.any():
        raise ValueError("Background removal left nothing; is the image all background?")
    out = np.dstack([rgb.astype(np.uint8), alpha])
    ys, xs = np.where(alpha > 0)
    return Image.fromarray(out[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA")


def _enclosed_background(rgb: np.ndarray, white: np.ndarray, background: np.ndarray,
                         hole_min: float) -> np.ndarray:
    """White patches inside the sprite that match the outer background."""
    outer = white & background
    if not outer.any():
        return np.zeros_like(white)
    bg_color = np.median(rgb[outer], axis=0)
    sprite_area = max(int((~background).sum()), 1)

    holes = np.zeros_like(white)
    labels, n = ndimage.label(white & ~background)
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        region = labels[sl] == i
        area = int(region.sum())
        if area < hole_min * sprite_area:
            continue  # small highlight, glint or tooth
        pix = rgb[sl][region]
        same_color = np.abs(np.median(pix, axis=0) - bg_color).max() <= 10
        flat = pix.std(axis=0).max() <= 6  # painted white has shading; background doesn't
        if same_color and flat:
            holes[sl] |= region
    return holes


def recover_grid(img: Image.Image, pixel_size: int | None = 6, max_colors: int = 32) -> Image.Image:
    """Stage 2: rebuild each fake "pixel" block as one real pixel (via unfake).

    pixel_size: width of one fake pixel in the source image. None = auto-detect.
    Bigger values give a smaller sprite.
    """
    import unfake  # imported here so the other stages work without it

    logging.getLogger("unfake.py").setLevel(logging.WARNING)
    result = unfake.process_image_sync(
        img.convert("RGBA"),
        max_colors=max_colors,
        manual_scale=pixel_size,
        cleanup={"morph": False, "jaggy": True},
        snap_grid=True,
    )
    return binarize_alpha(result["image"])


def binarize_alpha(img: Image.Image, threshold: int = 128) -> Image.Image:
    """Make every pixel fully opaque or fully transparent, as in real pixel art."""
    a = np.array(img.convert("RGBA"))
    a[..., 3] = np.where(a[..., 3] >= threshold, 255, 0)
    a[a[..., 3] == 0] = 0
    return Image.fromarray(a, "RGBA")


def reduce_palette(img: Image.Image, colors: int = 24, seed: int = 1) -> Image.Image:
    """Stage 3: reduce to `colors` colors.

    k-means runs over the *distinct* colors rather than every pixel, so small
    accents (a stripe, an eye) get their own palette entry instead of being
    averaged into the large areas.
    """
    a = np.array(img.convert("RGBA"))
    opaque = a[..., 3] > 0
    pix = a[opaque][:, :3].astype(float)
    uniq = np.unique(pix, axis=0)
    if len(uniq) <= colors:
        return Image.fromarray(a, "RGBA")
    centers, _ = kmeans2(uniq, colors, minit="++", iter=50, seed=seed)
    idx = ((pix[:, None, :] - centers[None]) ** 2).sum(-1).argmin(1)
    a[opaque, :3] = np.clip(np.rint(centers[idx]), 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def place_on_canvas(img: Image.Image, size: int = 128, margin: int = 4) -> Image.Image:
    """Stage 4: bottom-center the sprite on a square canvas.

    Every sprite's feet land `margin` pixels above the bottom edge, so
    different sprites line up without per-sprite positioning.
    """
    if img.width > size or img.height > size - margin:
        raise ValueError(
            f"Sprite is {img.width}x{img.height}, too big for a {size}px canvas "
            f"with a {margin}px margin. Use a larger pixel size or canvas."
        )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, size - margin - img.height))
    return canvas


def count_colors(img: Image.Image) -> int:
    a = np.array(img.convert("RGBA"))
    return len(np.unique(a[a[..., 3] > 0][:, :3], axis=0))
