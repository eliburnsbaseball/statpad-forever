import json
import re
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
NBA_PLAYERS_PATH = ROOT / "public" / "nba_players.json"
NBA_HEADSHOTS_PATH = ROOT / "public" / "nba_headshots.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Host": "stats.nba.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

COMMON_ALL_PLAYERS_URL = (
    "https://stats.nba.com/stats/commonallplayers"
    "?IsOnlyCurrentSeason=0&LeagueID=00&Season=2025-26"
)


def normalize_name(value: str) -> str:
    value = (value or "").lower().replace("*", "").strip()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def choose_player(candidates, start, end):
    exact = [p for p in candidates if int(p.get("FROM_YEAR") or 0) == start and int(p.get("TO_YEAR") or 0) == end]
    if exact:
        return exact[0]

    overlapping = []
    for player in candidates:
        p_start = int(player.get("FROM_YEAR") or 0)
        p_end = int(player.get("TO_YEAR") or 0)
        overlap = min(p_end, end) - max(p_start, start)
        if overlap >= 0:
            distance = abs(p_start - start) + abs(p_end - end)
            overlapping.append((distance, -overlap, player))
    if overlapping:
        overlapping.sort(key=lambda item: (item[0], item[1]))
        return overlapping[0][2]

    nearest = []
    for player in candidates:
        p_start = int(player.get("FROM_YEAR") or 0)
        p_end = int(player.get("TO_YEAR") or 0)
        distance = abs(p_start - start) + abs(p_end - end)
        nearest.append((distance, player))
    nearest.sort(key=lambda item: item[0])
    return nearest[0][1] if nearest else None


def load_nba_index():
    response = requests.get(COMMON_ALL_PLAYERS_URL, headers=HEADERS, timeout=(20, 180))
    response.raise_for_status()
    payload = response.json()
    result_sets = payload.get("resultSets") or []
    rows = []
    headers_row = None
    for rs in result_sets:
        if rs.get("name") == "CommonAllPlayers":
            headers_row = rs.get("headers") or []
            for row in rs.get("rowSet") or []:
                rows.append(dict(zip(headers_row, row)))
            break
    return rows


def headshot_url(person_id):
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{person_id}.png"


def main():
    players = json.loads(NBA_PLAYERS_PATH.read_text(encoding="utf-8"))
    try:
        headshots = json.loads(NBA_HEADSHOTS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        headshots = {}

    official = load_nba_index()
    by_name = {}
    for player in official:
        name_key = normalize_name(player.get("DISPLAY_FIRST_LAST", ""))
        if not name_key:
            continue
        by_name.setdefault(name_key, []).append(player)

    updated = 0
    matched = 0
    unmatched = []
    for local in players:
        local_id = str(local.get("id") or "").strip()
        if not local_id:
            continue
        name_key = normalize_name(local.get("nm", ""))
        if not name_key:
            continue
        candidates = by_name.get(name_key, [])
        if not candidates:
            unmatched.append(local)
            continue
        chosen = choose_player(candidates, int(local.get("start") or 0), int(local.get("end") or 0))
        if not chosen:
            unmatched.append(local)
            continue
        matched += 1
        person_id = str(chosen.get("PERSON_ID") or "").strip()
        if not person_id:
            unmatched.append(local)
            continue
        url = headshot_url(person_id)
        if headshots.get(local_id) != url:
            headshots[local_id] = url
            updated += 1

    NBA_HEADSHOTS_PATH.write_text(json.dumps(headshots, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"matched={matched} updated={updated} unmatched={len(unmatched)}")
    if unmatched:
        for player in unmatched[:25]:
            print(f"{player.get('nm')} {player.get('start')}-{player.get('end')} {player.get('id')}")


if __name__ == "__main__":
    main()
