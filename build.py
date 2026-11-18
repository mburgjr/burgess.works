"""
Build content.js from the folders in content/.

Each item is a file plus a YAML file with the same name, for example
content/paintings/sunset.jpg with content/paintings/sunset.yaml. Items appear
newest first, by the `year`, `month` and optional `day` in their YAML; items
from the same month go in title order unless a `day` says otherwise. Run
`python3 build.py` after adding or changing anything in content/, then
reload the page.
"""

import calendar
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final[Path] = Path(__file__).resolve().parent
PAGES: Final[list[str]] = ["index.html", "paintings.html", "poems.html", "guitar.html"]
SECTION_EXTENSIONS: Final[dict[str, set[str]]] = {
    "paintings": {".jpg", ".jpeg", ".png", ".webp"},
    "poems": {".txt"},
    "guitar": {".pdf"},
}
# Phones can't show a PDF inside the page, so the guitar page shows these
# renders of each PDF page there instead.
PDF_PAGES_DIR: Final[Path] = ROOT / "generated" / "guitar"
PDF_PAGE_WIDTH: Final[int] = 1240
# Lowercase letters, digits and single dashes: safe in URLs and immune to the
# case-sensitivity of the web server.
SAFE_NAME: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
# What the published site is made of, besides the content each page uses.
SITE_FILES: Final[list[str]] = [*PAGES, "style.css", "viewer.js", "content.js"]
SITE_DIRS: Final[list[str]] = ["images"]
SITE_DIR: Final[Path] = ROOT / "_site"
# "march", "Mar" and 3 all mean March.
MONTHS: Final[dict[str, int]] = {
    **{name.lower(): number for number, name in enumerate(calendar.month_name) if name},
    **{name.lower(): number for number, name in enumerate(calendar.month_abbr) if name},
}


def render_pdf_pages(pdf: Path) -> list[str]:
    """
    Render each page of `pdf` to a JPEG in generated/guitar, if not already done.

    The images are named after a hash of the PDF's contents, so a replaced
    PDF always gets new images, whatever its file date.

    Args:
        pdf: The PDF to render.

    Returns:
        The page images' paths relative to the site, in page order.

    Raises:
        SystemExit: If pdftoppm (from poppler-utils) is not installed.
    """
    prefix = f"{pdf.stem}-{hashlib.sha1(pdf.read_bytes()).hexdigest()[:8]}"
    pages = list(PDF_PAGES_DIR.glob(f"{prefix}-*.jpg"))
    if not pages:
        if shutil.which("pdftoppm") is None:
            sys.exit("pdftoppm not found: install poppler-utils (apt) or poppler (brew)")
        PDF_PAGES_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["pdftoppm", "-jpeg", "-jpegopt", "quality=82",
             "-scale-to-x", str(PDF_PAGE_WIDTH), "-scale-to-y", "-1",
             str(pdf), str(PDF_PAGES_DIR / prefix)],
            check=True,
        )
        pages = list(PDF_PAGES_DIR.glob(f"{prefix}-*.jpg"))
    pages.sort(key=lambda page: int(page.stem.rsplit("-", 1)[1]))
    return [page.relative_to(ROOT).as_posix() for page in pages]


def read_utf8(path: Path) -> str:
    """
    Read a text file saved as UTF-8.

    Args:
        path: The file to read.

    Returns:
        Its text.

    Raises:
        SystemExit: If the file is not UTF-8, naming it.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sys.exit(f"{path}: save this file as UTF-8 (in most editors: Save As, Encoding UTF-8)")


def write_site(content: dict[str, list[dict[str, Any]]]) -> None:
    """
    Copy just what the site needs into _site/, the folder that gets published.

    Only files the shown items use are copied, so items with `show: false`,
    the build scripts and the notes never go online.

    Args:
        content: The shown items of each section, as written to content.js.
    """
    if SITE_DIR.exists():
        shutil.rmtree(SITE_DIR)
    SITE_DIR.mkdir()
    for name in SITE_FILES:
        shutil.copy2(ROOT / name, SITE_DIR / name)
    for name in SITE_DIRS:
        shutil.copytree(ROOT / name, SITE_DIR / name)
    used = [path for items in content.values() for item in items
            for path in [item.get("file"), *item.get("pages", [])] if path]
    for path in used:
        (SITE_DIR / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, SITE_DIR / path)


def parse_date(meta: dict[str, Any], meta_path: Path) -> tuple[int, int, int]:
    """
    Read an item's year, month and day, turning a month name into its number.

    Args:
        meta: The item's YAML fields; `month` is replaced by its number.
        meta_path: The YAML file, for error messages.

    Returns:
        (year, month, day), with 0 for any that is missing, so undated items
        sort after dated ones.

    Raises:
        SystemExit: If a field is not a valid year, month or day, or a month
            or day is given without a year.
    """
    year, month, day = meta.get("year"), meta.get("month"), meta.get("day")
    # YAML reads `yes`/`true` as booleans, which Python also counts as ints.
    for key, value in (("year", year), ("month", month), ("day", day)):
        if isinstance(value, bool):
            sys.exit(f"{meta_path}: {key} must be a number, not {value!r}")
    if year is not None and not isinstance(year, int):
        sys.exit(f"{meta_path}: year must be a number like 2026, not {year!r}")
    if isinstance(month, str):
        if month.strip().lower() not in MONTHS:
            sys.exit(f"{meta_path}: month must be a month name or 1-12, not {month!r}")
        month = meta["month"] = MONTHS[month.strip().lower()]
    if month is not None and not (isinstance(month, int) and 1 <= month <= 12):
        sys.exit(f"{meta_path}: month must be a month name or 1-12, not {month!r}")
    if day is not None and not (isinstance(day, int) and 1 <= day <= 31):
        sys.exit(f"{meta_path}: day must be 1-31, not {day!r}")
    if year is None and (month is not None or day is not None):
        sys.exit(f"{meta_path}: a month or day needs a year too")
    return year or 0, month or 0, day or 0


def load_section(name: str, extensions: set[str]) -> list[dict[str, Any]]:
    """
    Read one content folder into a list of items, newest first.

    Args:
        name: Folder name under content/, e.g. "paintings".
        extensions: File extensions that count as the item itself.

    Returns:
        One dict per shown item (`show: false` in the YAML leaves an item
        out): its YAML fields and either its file path (relative to the site)
        or, for poems, its text. Items are ordered newest first by year,
        month and day; ties go in title order, and undated items come last.

    Raises:
        SystemExit: If two files share a name, or a YAML file is missing, has
            no title, has an invalid date, or has no matching file.
    """
    folder = ROOT / "content" / name
    if not folder.is_dir():
        return []
    items = []
    dates: list[tuple[int, int, int]] = []
    media_by_stem: dict[str, Path] = {}
    for media in sorted(folder.iterdir()):
        if media.suffix.lower() not in extensions:
            continue
        if not SAFE_NAME.fullmatch(media.stem):
            sys.exit(f"{media}: use only lowercase letters, numbers and dashes in file names, "
                     f"e.g. harbour-at-dusk{media.suffix.lower()}")
        if media.stem in media_by_stem:
            sys.exit(f"{media} and {media_by_stem[media.stem]} share a name; rename one")
        media_by_stem[media.stem] = media

        meta_path = media.with_suffix(".yaml")
        if not meta_path.exists():
            sys.exit(f"{media}: add {meta_path.name} next to it with at least a title")
        meta = yaml.safe_load(read_utf8(meta_path)) or {}
        if not isinstance(meta, dict):
            sys.exit(f"{meta_path}: should be lines of `field: value`, like title: \"Harbour\"")
        if meta.get("title") in (None, ""):
            sys.exit(f"{meta_path}: needs a title")
        # A title like 1984 or yes is read as a number or boolean; keep it as text.
        meta["title"] = str(meta["title"])
        show = meta.pop("show", True)
        if not isinstance(show, bool):
            sys.exit(f"{meta_path}: show must be true or false, not {show!r}")
        date = parse_date(meta, meta_path)
        if not show:
            continue

        item = dict(meta)
        if name == "poems":
            item["text"] = read_utf8(media).rstrip("\n")
        else:
            item["file"] = media.relative_to(ROOT).as_posix()
        if media.suffix.lower() == ".pdf":
            item["pages"] = render_pdf_pages(media)
        items.append(item)
        dates.append(date)

    for meta_path in folder.glob("*.yaml"):
        if meta_path.stem not in media_by_stem:
            sys.exit(f"{meta_path}: no matching file with the same name in {folder}")
    # Title order first, then a stable newest-first sort keeps it for ties.
    by_title = sorted(zip(dates, items), key=lambda pair: pair[1]["title"].lower())
    by_title.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in by_title]


def main() -> None:
    content = {name: load_section(name, extensions) for name, extensions in SECTION_EXTENSIONS.items()}
    # default=str covers YAML dates such as 2024-05-01.
    script = (
        "// Generated by build.py from the content/ folders. Do not edit by hand.\n"
        f"var CONTENT = {json.dumps(content, indent=2, ensure_ascii=False, default=str)};\n"
    )
    (ROOT / "content.js").write_text(script)

    # Drop page images of PDFs that were replaced or deleted.
    used = {page for item in content["guitar"] for page in item["pages"]}
    for page in PDF_PAGES_DIR.glob("*.jpg"):
        if page.relative_to(ROOT).as_posix() not in used:
            page.unlink()

    # A new version tag on every change stops browsers using a stale copy.
    version = hashlib.sha1(script.encode()).hexdigest()[:8]
    for page in PAGES:
        path = ROOT / page
        html = path.read_text()
        updated = re.sub(r'content\.js(\?v=[0-9a-f]*)?"', f'content.js?v={version}"', html)
        if updated != html:
            path.write_text(updated)

    write_site(content)
    counts = ", ".join(f"{len(items)} {name}" for name, items in content.items())
    print(f"content.js and _site/ written: {counts}")


if __name__ == "__main__":
    main()
