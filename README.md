# Michael Burgess

## Adding work

Each section has a folder in `content/`. An item is a file plus a `.yaml` file
with the same name, e.g. `harbour-at-dusk.jpg` and `harbour-at-dusk.yaml`. Name
files anything you like (lowercase with dashes is easiest); the name only has
to match between the two files.

Items show up newest first, ordered by `year`, `month` and, if given, `day`.
Nothing needs renumbering when you add something: give it its date and it
lands in the right place.

| Folder              | File          | YAML fields                                   |
| ------------------- | ------------- | --------------------------------------------- |
| `content/paintings` | `.jpg`, `.png`, `.webp` | `title`, `medium`, `size`, `year`, `month`, `day`, `prints`, `show` |
| `content/poems`     | `.txt` (the poem, line breaks kept) | `title`, `year`, `month`, `day`, `show` |
| `content/guitar`    | `.pdf`        | `title`, `key`, `year`, `month`, `day`, `show` |

- Only `title` is required.
- `month` is a name (`October`, `Oct`) or a number (`10`). The site shows only
  the year; the month and day are just for ordering.
- Items from the same month go in title order. Add `day` (1-31) to put one
  before another.
- Items without a date go after all dated ones in that section.
- `prints: false` hides the BUY PRINT button.
- `show: false` keeps an item off the site without deleting it; leave it out
  or set `show: true` to show it.

The build stops with a message naming the file if a date is not valid.

Example `content/paintings/harbour-at-dusk.yaml`:

```yaml
title: "Harbour at Dusk"
medium: "Oil"
size: '16" x 12"'      # single quotes, because of the inch marks
year: 2026
month: October
prints: true
```

Then run `python3 build.py` (needs `pip install pyyaml`) and reload the page.
On GitHub, pushing runs the build for you.

## Preparing a painting scan

`tools/prepare_painting.py` turns a raw scan into the image the site shows:
it resizes to 2400 px, sets the black point so dark tones read as dark, and
removes the glare flecks the scanner light leaves on the canvas weave.
Optional `--crop LEFT TOP RIGHT BOTTOM` and `--rotate left|right` come first.
It needs numpy, scipy and Pillow.

```
python3 tools/prepare_painting.py scan.jpg content/paintings/new-painting.jpg
```

Always run it on the original scan, not on a file it already produced.
See `tools/README.md` for how each step works, how to tune it, and which
scan and options produced each current painting.

## Preview

```
python3 build.py && python3 -m http.server 8000
```

Open http://localhost:8000.
