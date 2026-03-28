import json
import os
import re
import sys
from io import BytesIO
from urllib.parse import parse_qs, unquote, urlparse

import requests
from PIL import Image
from rembg import remove


ROOT = os.path.dirname(os.path.dirname(__file__))
INPUT_PATH = os.path.join(ROOT, "scripts", "nbc_nfl_sources.json")
OUTPUT_DIR = os.path.join(ROOT, "public", "headshots", "nbc")
OUTPUT_MAP = os.path.join(ROOT, "public", "nfl_headshots_nbc.json")


def slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def norm_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_og_image(page_url: str) -> str | None:
    html = requests.get(page_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if not m:
        return None
    raw = m.group(1)
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    if "url" in qs and qs["url"]:
        return unquote(qs["url"][0])
    return raw


def process_image(img_url: str, out_path: str):
    raw = requests.get(img_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).content
    src = Image.open(BytesIO(raw)).convert("RGBA")
    nobg = Image.open(BytesIO(remove(raw))).convert("RGBA")
    bbox = nobg.getbbox()
    if bbox:
        nobg = nobg.crop(bbox)
    scale = 2
    target_w = max(700, nobg.width * scale)
    target_h = int(nobg.height * (target_w / max(1, nobg.width)))
    nobg = nobg.resize((target_w, target_h), Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    nobg.save(out_path, "PNG")


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"Missing input file: {INPUT_PATH}")
        sys.exit(1)
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)
    out_map = {}
    if os.path.exists(OUTPUT_MAP):
        try:
            with open(OUTPUT_MAP, "r", encoding="utf-8") as f:
                out_map.update(json.load(f))
        except Exception:
            pass
    for item in items:
        name = item.get("name", "").strip()
        page_url = item.get("url", "").strip()
        if not name or not page_url:
            continue
        img_url = extract_og_image(page_url)
        if not img_url:
            print(f"Skipping {name}: no og:image")
            continue
        file_slug = slugify(name)
        rel_path = f"/headshots/nbc/{file_slug}.png"
        out_path = os.path.join(OUTPUT_DIR, f"{file_slug}.png")
        process_image(img_url, out_path)
        out_map[norm_name(name)] = rel_path
        print(f"Processed {name} -> {rel_path}")
    with open(OUTPUT_MAP, "w", encoding="utf-8") as f:
        json.dump(out_map, f, indent=2, sort_keys=True)
    print(f"Wrote {OUTPUT_MAP}")


if __name__ == "__main__":
    main()
