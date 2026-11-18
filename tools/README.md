# Painting scan preparation

`prepare_painting.py` turns a raw flatbed scan of a painting into the image the
site shows. Every painting in `content/paintings` was made with it.

## Quick use

```
python3 tools/prepare_painting.py <scan.jpg> content/paintings/<name>.jpg
```

Options:

- `--crop LEFT TOP RIGHT BOTTOM` keeps only that box of the scan, in pixels of
  the original scan (before any turn). See "Finding a crop box" below.
- `--rotate left` or `--rotate right` turns it a quarter turn.
- `--black-strength FACTOR` sets how strong the black point is (step 3): 1 is
  the default, 0.3 a light touch, 0 none.
- `--paper` makes the paper white, for works on paper (step 4).
- `--no-glare` skips glare removal (step 5), keeping the canvas texture as
  scanned.

`--black-strength 0 --no-glare` gives the scan exactly as it was, only cropped,
turned and resized.
Then add `<name>.yaml` next to the image and run `python3 build.py` (see the
main README).

It needs Python 3 with numpy, scipy and Pillow. It runs on your computer only;
the GitHub deploy does not run it, so commit the finished `.jpg`.

**Always start from the original scan.** Running the script on an image it has
already produced applies the black point and the glare filter a second time,
which crushes the shadows and flattens the canvas texture.

## What it does, in order

### 1. Crop and turn (optional)

Removes what isn't the painting, such as the scanner bed or tape around a
sheet of paper, and fixes the orientation. Find the crop box by opening the
scan in any image viewer and reading off the pixel positions of the corners.
Crop slightly inside the edge so no dark border survives.

### 2. Resize

Shrinks the image so its long side is 2400 px (`LONG_SIDE`). That is sharp on
any phone or desktop screen while keeping each file around 0.5 to 1.5 MB, so
pages load quickly. Images already smaller are left as they are.

### 3. Black point

Scans of paintings come out with grey, washed-out shadows: the scanner never
records true black, so dark paint reads as charcoal.

The script measures the luminance (perceived brightness) of every pixel, takes
the level below which the darkest 0.1% of pixels fall (`BLACK_PERCENTILE`), and
uses 85% of that level as the new black (`BLACK_FRACTION`). Everything is then
stretched linearly so that level becomes 0 and white stays at 255.

- The same stretch is applied to red, green and blue, so colours keep their hue.
- Because the black point comes from each painting's own darkest pixels,
  paintings that already reach black (Pharmacy, Seeing is Believing) barely
  change, while grey scans (Grigori, The Supermarkets Partition The Sky) get
  noticeably deeper shadows.
- Using 85% of the level rather than all of it leaves the darkest details
  slightly above pure black, so they don't merge into a flat black patch.

For one painting that should change less, use `--black-strength`: it scales
how far the black moves, so 0.3 is a light touch and 0 leaves the tones as
scanned. To change the default for every painting, raise `BLACK_FRACTION`
toward 1.0 or raise `BLACK_PERCENTILE` for deeper shadows, or lower them for
gentler ones.

### 4. Paper whitening (`--paper` only)

A scanned sheet of paper comes out light grey, often with a slight tint, and
darker toward the edges. With `--paper`, the script finds the paper by
taking every pixel that is both light (luminance above 180,
`PAPER_MIN_LUMINANCE`) and nearly grey (the gap between its strongest and
weakest channel under 25, `PAPER_MAX_CHROMA`), takes the median colour of
those pixels as the paper colour, and scales red, green and blue separately
so that colour becomes pure white.

- Scaling each channel separately also removes a yellow or blue tint, the way
  white balance does in a photo editor. The drawing's colours move with it.
- The paper is evened out globally, not patch by patch, so a sheet that was
  darker at one edge stays slightly darker there (near white rather than
  white). Tried on Mammal, the middle of the sheet went from about 236 to 252
  out of 255 and the darkest corner from about 222 to 239; Mammal is shown
  without it, with its paper as scanned.
- If under 5% of the image looks like light paper, the script stops with an
  error instead of guessing; it is meant for drawings on mostly blank paper.

Don't use it on canvases: a painted background is not paper and would be
shifted toward white.

### 5. Glare removal

The scanner lights the painting from a low angle, so the raised threads of the
canvas weave catch the light. On the scan this shows up as thin, bright,
horizontal flecks over the whole painting, most visible on dark smooth areas
(the green background of Bubble, the grey wall in I Like Freeze Pops Too).

The filter works on luminance:

1. **Find the underlying brightness.** A grey opening (a minimum filter
   followed by a maximum filter) with a window 7 px tall and 1 px wide
   (`GLARE_WINDOW_HEIGHT`) removes any bright feature shorter than 7 px
   vertically. The flecks are 1 to 3 px tall, so they disappear; anything
   painted that is taller survives. The window is one pixel wide because the
   flecks are horizontal: a square window also flattens real horizontal detail
   and leaves a blocky pattern.
2. **Smooth that reference** with a Gaussian blur (`GLARE_REFERENCE_SMOOTHING`,
   sigma 1.2 px) so it has no hard steps.
3. **Measure the excess.** For each pixel, how much brighter it is than the
   reference, minus a small allowance (`GLARE_THRESHOLD`, 4 of 255) so normal
   paint texture isn't touched. The excess map is blurred slightly
   (`GLARE_MASK_SMOOTHING`, sigma 0.7 px) so corrections blend in.
4. **Pull the flecks down** by 80% of their excess (`GLARE_STRENGTH`). Like the
   black point, red, green and blue are scaled together, so colours don't shift.

Painted highlights, like the white streak on Bubble or the thick strokes of
Snowball, are much larger than the window, so they keep their brightness and
texture.

The parameters were tuned on the 2400 px images, which is why the script
resizes before this step. On a different size, scale `GLARE_WINDOW_HEIGHT`
with the image (about 7 px per 2400 px of long side).

#### How the settings were chosen

Five versions were compared on Bubble, which had the most glare:

| Version | Window (h x w) | Strength | Threshold | Smoothing | Result |
| ------- | -------------- | -------- | --------- | --------- | ------ |
| A | 5 x 1 | 0.6 | 6 | none | Clean, but many flecks remain |
| B | 7 x 3 | 0.85 | 4 | none | Fewer flecks, but a blocky tiled pattern |
| C | 9 x 3 | 1.0 | 2 | none | Strongest, very blocky |
| **D** | **7 x 1** | **0.8** | **4** | **1.2 / 0.7** | **Most flecks gone, no artefacts (used)** |
| E | 9 x 1 | 1.0 | 3 | 1.5 / 0.7 | Almost no flecks, softens the edges of highlights |

To remove more glare, move toward E (taller window, strength 1.0, lower
threshold). If highlights start to look soft or smeared, move back toward A.
Avoid windows wider than one pixel.

#### Limits

- It only removes small bright flecks. Large reflections or a sheen across a
  varnished area are not glare in this sense and are left alone.
- Very fine light details shorter than 7 px, such as a single white dot, are
  dimmed slightly.
- The best fix is still at scan time: scanning with the canvas turned 90 or 180
  degrees changes which way the light hits the weave, and a matte surface
  reflects less.

## How each current painting was made

From the scans in `Paintings.zip`; all other settings are the defaults above.

| Image | Scan | Extra options |
| ----- | ---- | ------------- |
| `grigori.jpg` | `Grigori/Image_20261117_0001.jpg` | |
| `bubble.jpg` | `Bubble/bubble.jpg` | |
| `snowball.jpg` | `Snowball/snowball.jpg` | |
| `weve-all-done-something-very-wrong.jpg` | `We've All Done Something Very Wrong/Image_20261101_0001_stitch.jpg` | |
| `sunday-evenings.jpg` | `Sunday Evenings/sunday_evenings.jpg` | |
| `the-supermarkets-partition-the-sky.jpg` | `The Supermarkets Partition The Sky/the_supermarkets_partition_the_sky.jpg` | `--black-strength 0.3 --no-glare` (close to the scan) |
| `mammal.jpg` | `Mammal/mammal.jpg` | `--crop 210 10 2272 3252 --rotate left` |
| `sheeps-on-the-side-of-the-road.jpg` | `Sheeps on the Side of the Road/Image_20261101_0001_stitch.jpg` | |
| `pharmacy.jpg` | `Pharmacy/Image_20261101_0001_stitch.jpg` | |
| `i-like-freeze-pops-too.jpg` | `I Like Freeze Pops Too/i_like_freeze_pops_too.jpg` | |
| `seeing-is-believing.jpg` | `Seeing is Believing/Image_20261101_0001.jpg` | |

Where a folder had several partial scans, the stitched full image was used.

## Finding a crop box

The crop box is in pixels of the original scan, before any turn, written as
the left, top, right and bottom edges of the part to keep.

1. Open the original scan in an image editor that shows the cursor's pixel
   position. GIMP shows it at the bottom left; on a Mac, Preview's Tools >
   Show Inspector shows a selection's position and size.
2. Point at the top-left corner of what you want to keep and note x and y:
   those are LEFT and TOP.
3. Point at the bottom-right corner and note x and y: RIGHT and BOTTOM.
4. Run the script with `--crop LEFT TOP RIGHT BOTTOM`, plus any `--rotate`.

For example, Mammal's scan is 2440 x 3356 px and the paper runs from about
x 195 to 2286 and from the top to y 3265, so `--crop 210 10 2272 3252` keeps
the paper and a hair less, leaving no scanner bed or tape in the picture.
Cropping tighter, for instance closer around the animal, is the same command
with a smaller box.
