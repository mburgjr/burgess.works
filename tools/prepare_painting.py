"""
Turn a painting scan into the image the site shows.

Steps, in order:

1. Optional crop and quarter turn.
2. Resize to 2400 px on the long side.
3. Black point: the darkest 0.1% of the painting goes to black, so grey
   scanner shadows read as dark again (--black-strength makes it gentler;
   0 skips it).
4. Optional paper whitening (--paper, for works on paper): the paper's grey
   or tint becomes white.
5. Glare removal (skipped with --no-glare): thin bright flecks where the
   scanner light catches the canvas weave are pulled down to their
   surroundings; painted highlights are thicker and stay.

tools/README.md explains each step, why its settings were chosen, how to tune
them, and which scan and options produced each current painting. Always run
it on the original scan: a second pass doubles the black point and glare
corrections.

Needs numpy, scipy and Pillow. Example:

    python3 tools/prepare_painting.py scan.jpg content/paintings/sky.jpg
    python3 tools/prepare_painting.py scan.jpg out.jpg --crop 210 10 2272 3252 --rotate left
"""

import argparse
from pathlib import Path
from typing import Final

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

LONG_SIDE: Final[int] = 2400
JPEG_QUALITY: Final[int] = 88
LUMINANCE_WEIGHTS: Final[np.ndarray] = np.array([0.299, 0.587, 0.114], dtype=np.float32)

# Black point: this fraction of the darkest pixels sets the new black.
BLACK_PERCENTILE: Final[float] = 0.1
BLACK_FRACTION: Final[float] = 0.85

# Glare removal, tuned on the 2400 px images (filter "D"). The window is
# vertical only because the flecks are thin horizontal streaks.
GLARE_WINDOW_HEIGHT: Final[int] = 7
GLARE_STRENGTH: Final[float] = 0.8
GLARE_THRESHOLD: Final[float] = 4.0
GLARE_REFERENCE_SMOOTHING: Final[float] = 1.2
GLARE_MASK_SMOOTHING: Final[float] = 0.7

# Paper (--paper): pixels this bright and this close to grey count as paper.
PAPER_MIN_LUMINANCE: Final[float] = 180.0
PAPER_MAX_CHROMA: Final[float] = 25.0


def scale_luminance(pixels: np.ndarray, luminance: np.ndarray, target: np.ndarray) -> np.ndarray:
    """
    Scale each pixel's three channels together so its luminance becomes `target`.

    Args:
        pixels: Float RGB image, shape (height, width, 3).
        luminance: Current luminance of `pixels`, shape (height, width).
        target: Wanted luminance, shape (height, width).

    Returns:
        The rescaled float RGB image, clipped to 0..255. Hue is unchanged.
    """
    scale = np.where(luminance > 0, target / np.maximum(luminance, 1e-3), 1.0)
    return np.clip(pixels * scale[..., None], 0, 255)


def set_black_point(pixels: np.ndarray, strength: float) -> np.ndarray:
    """
    Stretch the tones so the darkest pixels of the painting become black.

    Args:
        pixels: Float RGB image, shape (height, width, 3).
        strength: 1 for the full black point, smaller for a gentler one
            (0.5 moves the black half as far), 0 for no change.

    Returns:
        The stretched float RGB image. One linear stretch is shared by all
        channels, so colours keep their hue.
    """
    luminance = pixels @ LUMINANCE_WEIGHTS
    black = strength * BLACK_FRACTION * float(np.percentile(luminance, BLACK_PERCENTILE))
    return np.clip((pixels - black) * (255.0 / (255.0 - black)), 0, 255)


def whiten_paper(pixels: np.ndarray) -> np.ndarray:
    """
    Make the paper of a work on paper white, removing its grey or tint.

    The paper colour is the per-channel median of the light, nearly grey
    pixels; each channel is scaled so that colour becomes white. Darker
    corners of the sheet end up near white rather than exactly white.

    Args:
        pixels: Float RGB image, shape (height, width, 3).

    Returns:
        The rescaled float RGB image, clipped to 0..255.

    Raises:
        SystemExit: If almost nothing in the image looks like paper.
    """
    luminance = pixels @ LUMINANCE_WEIGHTS
    chroma = pixels.max(axis=2) - pixels.min(axis=2)
    paper = (luminance > PAPER_MIN_LUMINANCE) & (chroma < PAPER_MAX_CHROMA)
    if paper.mean() < 0.05:
        raise SystemExit("--paper: under 5% of the image looks like light paper")
    paper_colour = np.median(pixels[paper], axis=0)
    return np.clip(pixels * (255.0 / paper_colour), 0, 255)


def remove_glare(pixels: np.ndarray) -> np.ndarray:
    """
    Pull down thin bright flecks where the scanner light caught the canvas weave.

    A grey opening with a tall, one-pixel-wide window removes bright features
    shorter than the window; its smoothed result is the reference brightness.
    Pixels brighter than the reference by more than a threshold are darkened
    toward it.

    Args:
        pixels: Float RGB image, shape (height, width, 3).

    Returns:
        The float RGB image with the flecks reduced.
    """
    luminance = pixels @ LUMINANCE_WEIGHTS
    opened = ndimage.grey_opening(luminance, size=(GLARE_WINDOW_HEIGHT, 1))
    reference = ndimage.gaussian_filter(opened, sigma=GLARE_REFERENCE_SMOOTHING)
    excess = np.clip(luminance - np.minimum(luminance, reference) - GLARE_THRESHOLD, 0, None)
    excess = ndimage.gaussian_filter(excess, sigma=GLARE_MASK_SMOOTHING)
    return scale_luminance(pixels, luminance, luminance - GLARE_STRENGTH * excess)


def prepare(
    scan: Image.Image,
    crop: tuple[int, int, int, int] | None,
    rotate: str | None,
    black_strength: float,
    paper: bool,
    glare: bool,
) -> Image.Image:
    """
    Run every step on one scan.

    Args:
        scan: The scan as loaded from disk.
        crop: Box (left, top, right, bottom) in scan pixels to keep, or None.
        rotate: "left" or "right" for a quarter turn, or None.
        black_strength: How strong a black point to set; see `set_black_point`.
        paper: Whether to make the paper white (works on paper only).
        glare: Whether to remove the canvas glare flecks.

    Returns:
        The finished RGB image.
    """
    image = ImageOps.exif_transpose(scan).convert("RGB")
    if crop is not None:
        image = image.crop(crop)
    if rotate == "left":
        image = image.transpose(Image.Transpose.ROTATE_90)
    elif rotate == "right":
        image = image.transpose(Image.Transpose.ROTATE_270)
    image.thumbnail((LONG_SIDE, LONG_SIDE), Image.LANCZOS)
    pixels = set_black_point(np.asarray(image).astype(np.float32), black_strength)
    if paper:
        pixels = whiten_paper(pixels)
    if glare:
        pixels = remove_glare(pixels)
    return Image.fromarray(pixels.round().astype(np.uint8))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scan", type=Path, help="the scan to prepare")
    parser.add_argument("output", type=Path, help="where to write the finished .jpg")
    parser.add_argument("--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
                        help="keep only this box of the scan, in scan pixels")
    parser.add_argument("--rotate", choices=["left", "right"], help="turn a quarter turn")
    parser.add_argument("--black-strength", type=float, default=1.0, metavar="FACTOR",
                        help="black point strength: 1 full (default), 0.3 a light touch, 0 none")
    parser.add_argument("--paper", action="store_true", help="make the paper white (works on paper)")
    parser.add_argument("--no-glare", action="store_true", help="keep the canvas glare flecks as scanned")
    args = parser.parse_args()
    if not 0 <= args.black_strength <= 1:
        parser.error("--black-strength must be between 0 and 1")
    Image.MAX_IMAGE_PIXELS = None
    finished = prepare(Image.open(args.scan), tuple(args.crop) if args.crop else None, args.rotate,
                       args.black_strength, args.paper, not args.no_glare)
    finished.save(args.output, quality=JPEG_QUALITY, optimize=True, progressive=True)
    print(f"{args.output}: {finished.size[0]} x {finished.size[1]}")


if __name__ == "__main__":
    main()
