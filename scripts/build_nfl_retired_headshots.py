import html
import json
import re
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
NFL_PLAYERS_PATH = ROOT / "public" / "nfl_players.json"
NFL_HEADSHOTS_PATH = ROOT / "public" / "nfl_headshots.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}
LETTERS = [chr(code) for code in range(ord("a"), ord("z") + 1)]


def normalize_name(value: str) -> str:
    value = html.unescape(value or "").lower().strip()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_rows(page_html: str):
    rows = re.findall(r"<tr>(.*?)</tr>", page_html, re.S)
    parsed = []
    for row in rows:
        name_match = re.search(r'aria-label="([^"]+) profile page"', row)
        img_match = re.search(r'<img alt="[^"]*"[^>]*src="([^"]+)"', row)
        span_match = re.search(r"(\d{4})\s*-\s*(\d{4})", row)
        if not name_match or not img_match or not span_match:
            continue
        raw_name = html.unescape(name_match.group(1)).strip()
        if "?" in raw_name or raw_name.lower() == "unknown":
            continue
        parsed.append(
            {
                "name": raw_name,
                "name_key": normalize_name(raw_name),
                "img": img_match.group(1),
                "start": int(span_match.group(1)),
                "end": int(span_match.group(2)),
            }
        )
    return parsed


def choose_player(candidates, start, end):
    exact = [p for p in candidates if int(p.get("start") or 0) == start and int(p.get("end") or 0) == end]
    if exact:
        return exact[0]

    overlapping = []
    for player in candidates:
        p_start = int(player.get("start") or 0)
        p_end = int(player.get("end") or 0)
        overlap = min(p_end, end) - max(p_start, start)
        if overlap >= 0:
            distance = abs(p_start - start) + abs(p_end - end)
            overlapping.append((distance, -overlap, player))
    if overlapping:
        overlapping.sort(key=lambda item: (item[0], item[1]))
        return overlapping[0][2]

    nearest = []
    for player in candidates:
        p_start = int(player.get("start") or 0)
        p_end = int(player.get("end") or 0)
        distance = abs(p_start - start) + abs(p_end - end)
        nearest.append((distance, player))
    nearest.sort(key=lambda item: item[0])
    return nearest[0][1] if nearest else None


def fetch_letter(letter: str) -> str:
    url = f"https://www.nfl.com/players/retired/{letter}?after=&query={letter}"
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            print(f"{letter}: retry {attempt + 1} failed: {exc}")
    raise last_error


def main():
    players = json.loads(NFL_PLAYERS_PATH.read_text(encoding="utf-8"))
    try:
        headshots = json.loads(NFL_HEADSHOTS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        headshots = {}

    by_name = {}
    for player in players:
        name_key = normalize_name(player.get("nm", ""))
        if not name_key or not player.get("id"):
            continue
        by_name.setdefault(name_key, []).append(player)

    all_rows = []
    for letter in LETTERS:
        try:
            page_html = fetch_letter(letter)
        except Exception as exc:
            print(f"{letter}: skipped after retries: {exc}")
            continue
        rows = extract_rows(page_html)
        all_rows.extend(rows)
        print(f"{letter}: {len(rows)} rows")

    added = 0
    matched = 0
    unmatched = []
    seen_keys = set()
    for row in all_rows:
        dedupe_key = (row["name_key"], row["start"], row["end"])
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        candidates = by_name.get(row["name_key"], [])
        if not candidates:
            unmatched.append(row)
            continue
        player = choose_player(candidates, row["start"], row["end"])
        if not player or not player.get("id"):
            unmatched.append(row)
            continue
        matched += 1
        if headshots.get(player["id"]) != row["img"]:
            headshots[player["id"]] = row["img"]
            added += 1

    NFL_HEADSHOTS_PATH.write_text(json.dumps(headshots, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"rows={len(seen_keys)} matched={matched} updated={added} unmatched={len(unmatched)}")
    if unmatched:
        preview = unmatched[:20]
        print("unmatched preview:")
        for row in preview:
            print(f"  {row['name']} {row['start']}-{row['end']}")


if __name__ == "__main__":
    main()
