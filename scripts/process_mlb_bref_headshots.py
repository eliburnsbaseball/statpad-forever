import json
import os
import re
import sys
from io import BytesIO

from PIL import Image
from rembg import remove


ROOT = os.path.dirname(os.path.dirname(__file__))
INPUT_PATH = os.path.join(ROOT, "scripts", "mlb_bref_sources.json")
OUTPUT_DIR = os.path.join(ROOT, "public", "headshots", "mlb")
OUTPUT_MAP = os.path.join(ROOT, "public", "mlb_headshots_bref.json")


def process_image(raw_path: str, out_path: str):
    raw = open(raw_path, "rb").read()
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
    items = json.load(open(INPUT_PATH, "r", encoding="utf-8"))
    out_map = {}
    for item in items:
        pid = str(item.get("id", "")).strip()
        name = item.get("nm", "").strip()
        raw_rel = item.get("raw", "").strip()
        raw_path = os.path.join(ROOT, raw_rel.replace("/", os.sep)) if raw_rel else ""
        if not pid or not raw_path or not os.path.exists(raw_path):
            continue
        out_path = os.path.join(OUTPUT_DIR, f"{pid}.png")
        rel_path = f"/headshots/mlb/{pid}.png"
        process_image(raw_path, out_path)
        out_map[pid] = rel_path
        print(f"Processed {name or pid} -> {rel_path}")
    with open(OUTPUT_MAP, "w", encoding="utf-8") as f:
        json.dump(out_map, f, indent=2, sort_keys=True)
    print(f"Wrote {OUTPUT_MAP}")


if __name__ == "__main__":
    main()
