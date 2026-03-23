import csv
import io
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def fetch_bytes(url, headers=None, timeout=120, retries=3, pause=0.5):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", UA)
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(pause * (attempt + 1))
    raise last_error


def fetch_json(url, headers=None, timeout=120, retries=3):
    return json.loads(fetch_bytes(url, headers=headers, timeout=timeout, retries=retries).decode("utf-8"))


def fetch_csv(url, headers=None, timeout=120, retries=3):
    text = fetch_bytes(url, headers=headers, timeout=timeout, retries=retries).decode("utf-8", "ignore")
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        rows.append({(key or "").lstrip("\ufeff").strip(): value for key, value in row.items()})
    return rows


def season_label(start_year):
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def norm_name(name):
    return re.sub(r"\s+", " ", (name or "").strip())


def norm_key(name):
    name = norm_name(name).lower()
    name = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", name)
    return name.strip()


def as_int(value, default=0):
    if value in (None, "", "None"):
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def as_float(value, default=0.0):
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except Exception:
        return default


def team_code(value):
    value = (value or "").strip().upper()
    return value or "FA"


def write_json(name, data):
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    path = PUBLIC_DIR / name
    data = compact_payload(data)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    print(f"Wrote {len(data)} players to {path}")


def finalize_players(players):
    out = []
    for player in players.values():
        seasons = sorted(player["seasons"].values(), key=lambda s: int(s["year"]))
        if not seasons:
            continue
        player["start"] = int(seasons[0]["year"])
        player["end"] = int(seasons[-1]["year"])
        player["seasons"] = seasons
        out.append(player)
    out.sort(key=lambda p: p["nm"])
    return out


def compact_payload(players):
    required_player = {"nm", "nmL", "pos", "start", "end", "seasons"}
    required_season = {"year", "team"}
    compact = []
    for player in players:
        next_player = {}
        for key, value in player.items():
            if key == "seasons":
                next_player["seasons"] = []
                for season in value:
                    next_season = {}
                    for skey, sval in season.items():
                        if skey in required_season or sval not in (0, 0.0, "", None, False):
                            next_season[skey] = sval
                    next_player["seasons"].append(next_season)
            elif key in required_player or value not in (0, 0.0, "", None, False):
                next_player[key] = value
        compact.append(next_player)
    return compact


def ensure_nfl_player(players, pid, name, pos="", team=""):
    key = pid or norm_key(name)
    player = players.get(key)
    if not player:
        player = {
            "id": pid or "",
            "nm": norm_name(name),
            "nmL": norm_key(name),
            "pos": pos or "",
            "col": "",
            "colConf": "Independent",
            "draftRd": 0,
            "draftPk": 0,
            "isUndrafted": 1,
            "seasons": {},
        }
        players[key] = player
    if pos and not player.get("pos"):
        player["pos"] = pos
    if pid and not player.get("id"):
        player["id"] = pid
    return player


def ensure_nfl_season(player, year, team, draft_rd=0, draft_pk=0):
    season = player["seasons"].get(year)
    if not season:
        season = {
            "year": int(year),
            "team": team_code(team),
            "rush": 0,
            "rec": 0,
            "passYds": 0,
            "passTd": 0,
            "rushTd": 0,
            "recTd": 0,
            "int": 0,
            "fpts": 0,
            "tackles": 0,
            "sacks": 0,
            "forcedFumbles": 0,
            "puntRetYds": 0,
            "kickRetYds": 0,
            "returnTds": 0,
            "fgMade": 0,
            "fgMissed": 0,
            "pointsScored": 0,
            "draftRd": draft_rd,
            "draftPk": draft_pk,
            "ap1": 0,
            "ap2": 0,
            "pb": 0,
            "sb": 0,
            "mvp": 0,
            "opoy": 0,
            "roy": 0,
            "sbMvp": 0,
            "passRating": 0,
            "carries": 0,
            "recs": 0,
            "passAtts": 0,
            "age": 0,
        }
        player["seasons"][year] = season
    return season


def build_nfl():
    release = fetch_json(
        "https://api.github.com/repos/nflverse/nflverse-data/releases/tags/player_stats",
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
        timeout=120,
    )
    assets = {asset["name"]: asset["browser_download_url"] for asset in release.get("assets", [])}
    years = sorted(
        {
            int(match.group(1))
            for name in assets
            for match in [re.match(r"player_stats_season_(\d{4})\.csv$", name)]
            if match
        }
    )
    players = {}
    for year in years:
        season_url = assets.get(f"player_stats_season_{year}.csv")
        if season_url:
            for row in fetch_csv(season_url, timeout=180):
                if row.get("season_type") != "REG":
                    continue
                name = row.get("player_display_name") or row.get("player_name") or ""
                player = ensure_nfl_player(
                    players,
                    row.get("player_id") or "",
                    name,
                    row.get("position") or row.get("position_group") or "",
                    row.get("recent_team") or "",
                )
                season = ensure_nfl_season(player, year, row.get("recent_team") or "")
                season["team"] = team_code(row.get("recent_team"))
                season["rush"] = as_int(row.get("rushing_yards"))
                season["rec"] = as_int(row.get("receiving_yards"))
                season["passYds"] = as_int(row.get("passing_yards"))
                season["passTd"] = as_int(row.get("passing_tds"))
                season["rushTd"] = as_int(row.get("rushing_tds"))
                season["recTd"] = as_int(row.get("receiving_tds"))
                season["fpts"] = round(as_float(row.get("fantasy_points")))
                season["carries"] = as_int(row.get("carries"))
                season["recs"] = as_int(row.get("receptions"))
                season["passAtts"] = as_int(row.get("attempts"))
                season["puntRetYds"] = as_int(row.get("punt_return_yards"))
                season["kickRetYds"] = as_int(row.get("kick_return_yards")) + as_int(row.get("kickoff_return_yards"))
                season["returnTds"] = as_int(row.get("special_teams_tds"))
                completions = as_int(row.get("completions"))
                attempts = season["passAtts"]
                ints = as_int(row.get("interceptions"))
                pass_yards = season["passYds"]
                pass_tds = season["passTd"]
                if attempts > 0:
                    rating = (
                        ((completions / attempts) - 0.3) * 5
                        + ((pass_yards / attempts) - 3) * 0.25
                        + (pass_tds / attempts) * 20
                        + (2.375 - (ints / attempts) * 25)
                    ) / 6 * 100
                    season["passRating"] = max(0, min(158.3, round(rating, 1)))
                season["pointsScored"] = (
                    season["passTd"] * 4
                    + season["rushTd"] * 6
                    + season["recTd"] * 6
                    + as_int(row.get("passing_2pt_conversions")) * 2
                    + as_int(row.get("rushing_2pt_conversions")) * 2
                    + as_int(row.get("receiving_2pt_conversions")) * 2
                    + season["returnTds"] * 6
                )
        def_url = assets.get(f"player_stats_def_{year}.csv")
        if def_url:
            season_totals = {}
            for row in fetch_csv(def_url, timeout=180):
                if row.get("season_type") != "REG":
                    continue
                pid = row.get("player_id") or ""
                name = row.get("player_display_name") or row.get("player_name") or ""
                key = (pid or norm_key(name), team_code(row.get("team")))
                cur = season_totals.setdefault(
                    key,
                    {
                        "pid": pid,
                        "name": name,
                        "team": row.get("team") or "",
                        "pos": row.get("position") or row.get("position_group") or "",
                        "tackles": 0,
                        "int": 0,
                        "sacks": 0,
                        "forcedFumbles": 0,
                        "tds": 0,
                    },
                )
                cur["tackles"] += as_int(row.get("def_tackles"))
                cur["int"] += as_int(row.get("def_interceptions"))
                cur["sacks"] += as_float(row.get("def_sacks"))
                cur["forcedFumbles"] += as_int(row.get("def_fumbles_forced"))
                cur["tds"] += as_int(row.get("def_tds"))
            for cur in season_totals.values():
                player = ensure_nfl_player(players, cur["pid"], cur["name"], cur["pos"], cur["team"])
                season = ensure_nfl_season(player, year, cur["team"])
                season["tackles"] += cur["tackles"]
                season["int"] += cur["int"]
                season["sacks"] += cur["sacks"]
                season["forcedFumbles"] += cur["forcedFumbles"]
                season["pointsScored"] += cur["tds"] * 6
        kick_url = assets.get(f"player_stats_kicking_season_{year}.csv")
        if kick_url:
            for row in fetch_csv(kick_url, timeout=180):
                if row.get("season_type") != "REG":
                    continue
                name = row.get("player_display_name") or row.get("player_name") or ""
                player = ensure_nfl_player(
                    players,
                    row.get("player_id") or "",
                    name,
                    row.get("position") or "K",
                    row.get("team") or "",
                )
                season = ensure_nfl_season(player, year, row.get("team") or "")
                season["fgMade"] = as_int(row.get("fg_made"))
                season["fgMissed"] = as_int(row.get("fg_missed"))
                season["pointsScored"] += season["fgMade"] * 3 + as_int(row.get("pat_made"))
    return finalize_players(players)


NBA_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "identity",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def fetch_nba_resultset(url):
    data = fetch_json(url, headers=NBA_HEADERS, timeout=180, retries=4)
    result = data["resultSets"][0]
    headers = result["headers"]
    return [dict(zip(headers, row)) for row in result["rowSet"]]


def build_nba():
    index_rows = fetch_nba_resultset(
        "https://stats.nba.com/stats/playerindex?Active=&AllStar=&College=&Country=&DraftPick=&DraftRound=&DraftYear=&Height=&Historical=1&LeagueID=00&Season=2025-26&TeamID=0&Weight="
    )
    meta = {}
    for row in index_rows:
        pid = str(row["PERSON_ID"])
        meta[pid] = {
            "nm": norm_name(f"{row['PLAYER_FIRST_NAME']} {row['PLAYER_LAST_NAME']}"),
            "nmL": norm_key(f"{row['PLAYER_FIRST_NAME']} {row['PLAYER_LAST_NAME']}"),
            "id": pid,
            "pos": (row.get("POSITION") or "").strip()[:1],
            "seasons": {},
        }
    players = meta
    hist_rows = fetch_csv("https://raw.githubusercontent.com/peasant98/TheNBACSV/master/nbaNew.csv", timeout=240)
    for row in hist_rows:
        year = as_int(row.get("SeasonStart"))
        if year <= 0 or year >= 1996:
            continue
        gp = as_int(row.get("G"))
        if gp <= 0:
            continue
        name = norm_name(row.get("PlayerName"))
        key = norm_key(name)
        pid = next((pid for pid, p in players.items() if p["nmL"] == key), None)
        player = players.get(pid) if pid else None
        if not player:
            pid = f"hist-{key}"
            player = {
                "nm": name,
                "nmL": key,
                "id": pid,
                "pos": (row.get("Pos") or "").strip()[:1],
                "seasons": {},
            }
            players[pid] = player
        if not player.get("pos"):
            player["pos"] = (row.get("Pos") or "").strip()[:1]
        pts = as_int(row.get("PTS"))
        reb = as_int(row.get("TRB"))
        ast = as_int(row.get("AST"))
        stl = as_int(row.get("STL"))
        blk = as_int(row.get("BLK"))
        fg3m = as_int(row.get("3P"))
        fga = as_int(row.get("FGA"))
        fta = as_int(row.get("FTA"))
        tov = as_int(row.get("TOV"))
        pf = as_int(row.get("PF"))
        ftpct = row.get("FT%") or ""
        player["seasons"][year] = {
            "year": year,
            "team": team_code(row.get("Tm")),
            "pts": round(pts / gp, 1),
            "reb": round(reb / gp, 1),
            "ast": round(ast / gp, 1),
            "stl": round(stl / gp, 1),
            "blk": round(blk / gp, 1),
            "fg3m": round(fg3m / gp, 1),
            "gp": gp,
            "mvp": 0,
            "dpoy": 0,
            "roy": 0,
            "allnba1": 0,
            "allstar": 0,
            "champ": 0,
            "ftpct": as_float(str(ftpct).replace("%", "")) / 100 if ftpct else 0,
            "tripdbl": 0,
            "finals": 0,
            "totReb": reb,
            "totPts": pts,
            "totAst": ast,
            "totStl": stl,
            "totBlk": blk,
            "tot3pm": fg3m,
            "totFga": fga,
            "totFta": fta,
            "totTov": tov,
            "totFouls": pf,
        }
    for year in range(1996, 2025 + 1):
        season = season_label(year)
        url = (
            "https://stats.nba.com/stats/leaguedashplayerstats?"
            + urllib.parse.urlencode(
                {
                    "College": "",
                    "Conference": "",
                    "Country": "",
                    "DateFrom": "",
                    "DateTo": "",
                    "Division": "",
                    "DraftPick": "",
                    "DraftYear": "",
                    "GameScope": "",
                    "GameSegment": "",
                    "Height": "",
                    "LastNGames": "0",
                    "LeagueID": "00",
                    "Location": "",
                    "MeasureType": "Base",
                    "Month": "0",
                    "OpponentTeamID": "0",
                    "Outcome": "",
                    "PORound": "0",
                    "PaceAdjust": "N",
                    "PerMode": "Totals",
                    "Period": "0",
                    "PlayerExperience": "",
                    "PlayerPosition": "",
                    "PlusMinus": "N",
                    "Rank": "N",
                    "Season": season,
                    "SeasonSegment": "",
                    "SeasonType": "Regular Season",
                    "ShotClockRange": "",
                    "StarterBench": "",
                    "TeamID": "0",
                    "TwoWay": "0",
                    "VsConference": "",
                    "VsDivision": "",
                    "Weight": "",
                }
            )
        )
        rows = None
        for attempt in range(5):
            try:
                rows = fetch_nba_resultset(url)
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 * (attempt + 1))
        rows = rows or []
        print(f"NBA {season}: {len(rows)} rows")
        for row in rows:
            gp = as_int(row.get("GP"))
            if gp <= 0:
                continue
            pid = str(row["PLAYER_ID"])
            player = players.setdefault(
                pid,
                {
                    "nm": norm_name(row["PLAYER_NAME"]),
                    "nmL": norm_key(row["PLAYER_NAME"]),
                    "id": pid,
                    "pos": "",
                    "seasons": {},
                },
            )
            pts = as_int(row.get("PTS"))
            reb = as_int(row.get("REB"))
            ast = as_int(row.get("AST"))
            stl = as_int(row.get("STL"))
            blk = as_int(row.get("BLK"))
            fg3m = as_int(row.get("FG3M"))
            fga = as_int(row.get("FGA"))
            fta = as_int(row.get("FTA"))
            tov = as_int(row.get("TOV"))
            pf = as_int(row.get("PF"))
            player["seasons"][year] = {
                "year": year,
                "team": team_code(row.get("TEAM_ABBREVIATION")),
                "pts": round(pts / gp, 1),
                "reb": round(reb / gp, 1),
                "ast": round(ast / gp, 1),
                "stl": round(stl / gp, 1),
                "blk": round(blk / gp, 1),
                "fg3m": round(fg3m / gp, 1),
                "gp": gp,
                "mvp": 0,
                "dpoy": 0,
                "roy": 0,
                "allnba1": 0,
                "allstar": 0,
                "champ": 0,
                "ftpct": as_float(row.get("FT_PCT")),
                "tripdbl": 0,
                "finals": 0,
                "totReb": reb,
                "totPts": pts,
                "totAst": ast,
                "totStl": stl,
                "totBlk": blk,
                "tot3pm": fg3m,
                "totFga": fga,
                "totFta": fta,
                "totTov": tov,
                "totFouls": pf,
            }
    return finalize_players(players)


def build_mlb():
    shared_name = "y1prhc795jk8zvmelfd3jq7tl389y6cd"
    folder_html = fetch_bytes(f"https://sabr.app.box.com/s/{shared_name}", timeout=120).decode("utf-8", "ignore")
    start = folder_html.find("Box.postStreamData = ")
    end = folder_html.find(";</script>", start)
    folder_data = json.loads(folder_html[start + 21 : end])
    items = folder_data["/app-api/enduserapp/shared-folder"]["items"]
    item_ids = {item["name"]: item["id"] for item in items}

    def box_csv(name, timeout):
        file_id = item_ids[name]
        url = f"https://sabr.app.box.com/index.php?rm=box_download_shared_file&shared_name={shared_name}&file_id=f_{file_id}"
        return fetch_csv(url, timeout=timeout)

    people_rows = box_csv("People.csv", 180)
    batting_rows = box_csv("Batting.csv", 240)
    pitching_rows = box_csv("Pitching.csv", 240)
    fielding_rows = box_csv("Fielding.csv", 240)
    college_rows = box_csv("CollegePlaying.csv", 180)
    school_rows = box_csv("Schools.csv", 180)
    hall_rows = box_csv("HallOfFame.csv", 180)
    team_rows = box_csv("Teams.csv", 180)
    series_rows = box_csv("SeriesPost.csv", 180)

    people = {row["playerID"]: row for row in people_rows}
    schools = {}
    for row in school_rows:
        school_id = row.get("schoolID") or ""
        if school_id:
            schools[school_id] = (
                row.get("name_full")
                or row.get("schoolName")
                or row.get("name")
                or school_id
            )
    college_hist = {}
    for row in college_rows:
        school_id = row.get("schoolID") or ""
        player_id = row.get("playerID") or ""
        if not school_id or not player_id:
            continue
        bucket = college_hist.setdefault(player_id, {})
        bucket[school_id] = bucket.get(school_id, 0) + 1
    college_by_player = {}
    for player_id, counts in college_hist.items():
        top_school = max(counts.items(), key=lambda item: (item[1], item[0]))[0]
        college_by_player[player_id] = schools.get(top_school, top_school)
    hof_players = {
        row.get("playerID")
        for row in hall_rows
        if (row.get("inducted") or "").strip().upper() == "Y"
    }
    team_meta = {}
    for row in team_rows:
        year = as_int(row.get("yearID"))
        team = team_code(row.get("teamID"))
        if year <= 0 or not team:
            continue
        meta = team_meta.setdefault((year, team), {"lg": "", "ws": 0})
        lg = (row.get("lgID") or "").strip().upper()
        if lg in {"AL", "NL"}:
            meta["lg"] = lg
        if (row.get("WSWin") or "").strip().upper() == "Y":
            meta["ws"] = 1
    post_flags = {}
    for row in series_rows:
        year = as_int(row.get("yearID"))
        if year <= 0:
            continue
        round_id = ((row.get("round") or row.get("Round") or "")).strip().upper()
        winner = team_code(row.get("teamIDwinner") or row.get("teamIDWinner"))
        loser = team_code(row.get("teamIDloser") or row.get("teamIDLoser"))
        for team in [winner, loser]:
            if not team:
                continue
            flags = post_flags.setdefault((year, team), {"alds": 0, "nlds": 0, "alcs": 0, "nlcs": 0})
            if round_id == "ALDS":
                flags["alds"] = 1
            elif round_id == "NLDS":
                flags["nlds"] = 1
            elif round_id == "ALCS":
                flags["alcs"] = 1
            elif round_id == "NLCS":
                flags["nlcs"] = 1

    positions = {}
    for row in fielding_rows:
        key = (row["playerID"], as_int(row["yearID"]))
        cur = positions.setdefault(key, {})
        pos = (row.get("POS") or "").strip().upper()
        if pos:
            cur[pos] = cur.get(pos, 0) + as_int(row.get("G"))

    players = {}

    def ensure_player(player_id, fallback_name=""):
        info = people.get(player_id, {})
        first = info.get("nameFirst", "")
        last = info.get("nameLast", "")
        full_name = norm_name(f"{first} {last}") or norm_name(fallback_name) or player_id
        key = norm_key(full_name)
        player = players.get(key)
        if not player:
            player = {
                "id": player_id,
                "nm": full_name,
                "nmL": key,
                "pos": "H",
                "country": (info.get("birthCountry") or "USA").upper()[:3],
                "col": college_by_player.get(player_id, ""),
                "hof": 1 if player_id in hof_players else 0,
                "seasons": {},
            }
            players[key] = player
        return player

    for row in batting_rows:
        year = as_int(row.get("yearID"))
        if year <= 0:
            continue
        player = ensure_player(row["playerID"])
        season = player["seasons"].setdefault(
            year,
            {
                "year": year,
                "team": team_code(row.get("teamID")),
                "lg": "",
                "hr": 0,
                "rbi": 0,
                "avg": 0,
                "sb": 0,
                "ops": 0,
                "w": 0,
                "era": 0,
                "k": 0,
                "sv": 0,
                "mvp": 0,
                "cy": 0,
                "roy": 0,
                "gs": 0,
                "allstar": 0,
                "ws": 0,
                "losses": 0,
                "war": 0,
                "bb": 0,
                "runs": 0,
                "triples": 0,
                "hits": 0,
                "gg": 0,
                "fieldPos": "",
                "alds": 0,
                "nlds": 0,
                "alcs": 0,
                "nlcs": 0,
                "hof": 1 if player["hof"] else 0,
                "country": player["country"],
                "throws": 0,
                "wsmvp": 0,
                "battitle": 0,
                "slg": 0,
                "obp": 0,
                "tb": 0,
                "cs": 0,
                "hitK": 0,
                "hitBb": 0,
                "hbp": 0,
                "doubles": 0,
                "gidp": 0,
                "pa": 0,
                "ip": 0,
            },
        )
        season["team"] = team_code(row.get("teamID"))
        meta = team_meta.get((year, season["team"]), {})
        if meta.get("lg"):
            season["lg"] = meta["lg"]
        if meta.get("ws"):
            season["ws"] = 1
        season.update(post_flags.get((year, season["team"]), {}))
        ab = as_int(row.get("AB"))
        hits = as_int(row.get("H"))
        doubles = as_int(row.get("2B"))
        triples = as_int(row.get("3B"))
        hr = as_int(row.get("HR"))
        bb = as_int(row.get("BB"))
        hbp = as_int(row.get("HBP"))
        sf = as_int(row.get("SF"))
        sh = as_int(row.get("SH"))
        season["hr"] += hr
        season["rbi"] += as_int(row.get("RBI"))
        season["sb"] += as_int(row.get("SB"))
        season["bb"] += bb
        season["runs"] += as_int(row.get("R"))
        season["triples"] += triples
        season["hits"] += hits
        season["tb"] += hits + doubles + 2 * triples + 3 * hr
        season["cs"] += as_int(row.get("CS"))
        season["hitK"] += as_int(row.get("SO"))
        season["hitBb"] += bb
        season["hbp"] += hbp
        season["doubles"] += doubles
        season["gidp"] += as_int(row.get("GIDP"))
        season["pa"] += ab + bb + hbp + sf + sh
        season["_ab"] = season.get("_ab", 0) + ab
        season["_sf"] = season.get("_sf", 0) + sf
        season["_sh"] = season.get("_sh", 0) + sh
        season["fieldPos"] = season.get("fieldPos") or ""
        app = positions.get((row["playerID"], year))
        if app:
            best_pos = max(app.items(), key=lambda item: item[1])[0]
            season["fieldPos"] = best_pos
            if best_pos == "P":
                player["pos"] = "P"
    for row in pitching_rows:
        year = as_int(row.get("yearID"))
        if year <= 0:
            continue
        player = ensure_player(row["playerID"])
        season = player["seasons"].setdefault(
            year,
            {
                "year": year,
                "team": team_code(row.get("teamID")),
                "lg": "",
                "hr": 0,
                "rbi": 0,
                "avg": 0,
                "sb": 0,
                "ops": 0,
                "w": 0,
                "era": 0,
                "k": 0,
                "sv": 0,
                "mvp": 0,
                "cy": 0,
                "roy": 0,
                "gs": 0,
                "allstar": 0,
                "ws": 0,
                "losses": 0,
                "war": 0,
                "bb": 0,
                "runs": 0,
                "triples": 0,
                "hits": 0,
                "gg": 0,
                "fieldPos": "",
                "alds": 0,
                "nlds": 0,
                "alcs": 0,
                "nlcs": 0,
                "hof": 1 if player["hof"] else 0,
                "country": player["country"],
                "throws": 0,
                "wsmvp": 0,
                "battitle": 0,
                "slg": 0,
                "obp": 0,
                "tb": 0,
                "cs": 0,
                "hitK": 0,
                "hitBb": 0,
                "hbp": 0,
                "doubles": 0,
                "gidp": 0,
                "pa": 0,
                "ip": 0,
            },
        )
        season["team"] = team_code(row.get("teamID"))
        meta = team_meta.get((year, season["team"]), {})
        if meta.get("lg"):
            season["lg"] = meta["lg"]
        if meta.get("ws"):
            season["ws"] = 1
        season.update(post_flags.get((year, season["team"]), {}))
        season["w"] += as_int(row.get("W"))
        season["losses"] += as_int(row.get("L"))
        season["k"] += as_int(row.get("SO"))
        season["sv"] += as_int(row.get("SV"))
        season["gs"] += as_int(row.get("GS"))
        season["ip"] += round(as_int(row.get("IPouts")) / 3, 1)
        season["_er"] = season.get("_er", 0) + as_int(row.get("ER"))
        season["_ipouts"] = season.get("_ipouts", 0) + as_int(row.get("IPouts"))
        if season["gs"] > 0 or season["w"] > 0 or season["sv"] > 0:
            player["pos"] = "P"
            season["fieldPos"] = "P"
    for player in players.values():
        for season in player["seasons"].values():
            ab = season.pop("_ab", 0)
            sf = season.pop("_sf", 0)
            sh = season.pop("_sh", 0)
            if ab > 0:
                season["avg"] = round(season["hits"] / ab, 3)
                season["slg"] = round(season["tb"] / ab, 3)
            obp_denom = ab + season["hitBb"] + season["hbp"] + sf
            if obp_denom > 0:
                season["obp"] = round((season["hits"] + season["hitBb"] + season["hbp"]) / obp_denom, 3)
            season["ops"] = round(season["obp"] + season["slg"], 3)
            ipouts = season.pop("_ipouts", 0)
            er = season.pop("_er", 0)
            if ipouts > 0:
                season["era"] = round(er * 27 / ipouts, 2)
            season["pa"] = season["pa"] or ab + season["hitBb"] + season["hbp"] + sf + sh
    return finalize_players(players)


def build_nhl():
    players = {}

    def ensure_player(pid, name, pos, goalie=False):
        key = str(pid)
        player = players.get(key)
        if not player:
            player = {
                "id": str(pid),
                "nm": norm_name(name),
                "nmL": norm_key(name),
                "pos": "G" if goalie else ("D" if pos == "D" else "F"),
                "isGoalie": goalie,
                "country": "CAN",
                "seasons": {},
            }
            players[key] = player
        return player

    def fetch_nhl_report(path, sort_query, season_id):
        rows = []
        start = 0
        while True:
            url = (
                f"https://api.nhle.com/stats/rest/en/{path}?isAggregate=false&isGame=false&start={start}&limit=100&sort="
                + urllib.parse.quote(sort_query)
                + "&cayenneExp="
                + urllib.parse.quote(f"seasonId={season_id} and gameTypeId=2")
            )
            payload = fetch_json(url, timeout=180, retries=4)
            batch = payload.get("data", [])
            rows.extend(batch)
            if len(batch) < 100:
                break
            start += 100
        return rows

    start_year = 1917
    end_year = 2025
    for year in range(start_year, end_year + 1):
        season_id = f"{year}{year + 1}"
        skater_summary = fetch_nhl_report("skater/summary", '[{"property":"points","direction":"DESC"}]', season_id)
        skater_rt = fetch_nhl_report("skater/realtime", '[{"property":"hits","direction":"DESC"}]', season_id)
        goalie_summary = fetch_nhl_report("goalie/summary", '[{"property":"wins","direction":"DESC"}]', season_id)
        rt_map = {(row["playerId"], row.get("teamAbbrevs")): row for row in skater_rt}
        print(f"NHL {season_id}: {len(skater_summary)} skaters, {len(goalie_summary)} goalies")
        for row in skater_summary:
            pid = row["playerId"]
            name = row.get("skaterFullName") or f"{row.get('firstName','')} {row.get('lastName','')}"
            player = ensure_player(pid, name, row.get("positionCode") or "")
            rt = rt_map.get((pid, row.get("teamAbbrevs")), {})
            player["seasons"][year] = {
                "year": year,
                "team": team_code(row.get("teamAbbrevs")),
                "goals": as_int(row.get("goals")),
                "assists": as_int(row.get("assists")),
                "points": as_int(row.get("points")),
                "plusminus": as_int(row.get("plusMinus")),
                "pim": as_int(row.get("penaltyMinutes")),
                "hits": as_int(rt.get("hits")),
                "gp": as_int(row.get("gamesPlayed")),
                "hart": 0,
                "norris": 0,
                "selke": 0,
                "vezina": 0,
                "calder": 0,
                "champ": 0,
                "confFinals": 0,
                "scFinals": 0,
                "hof": 0,
                "country": player["country"],
                "wins": 0,
                "losses": 0,
                "svpct": 0,
                "shutouts": 0,
                "gaa": 0,
                "ppg": as_int(row.get("ppGoals")),
                "shg": as_int(row.get("shGoals")),
                "sog": as_int(row.get("shots")),
                "ops": 0,
                "dps": 0,
                "ps": 0,
                "qs": 0,
                "rbs": 0,
                "gsaa": 0,
                "sv": 0,
            }
        for row in goalie_summary:
            pid = row["playerId"]
            name = row.get("goalieFullName") or f"{row.get('firstName','')} {row.get('lastName','')}"
            player = ensure_player(pid, name, "G", goalie=True)
            player["seasons"][year] = {
                "year": year,
                "team": team_code(row.get("teamAbbrevs")),
                "wins": as_int(row.get("wins")),
                "losses": as_int(row.get("losses")) + as_int(row.get("otLosses")),
                "svpct": round(as_float(row.get("savePct")) * 100, 1),
                "shutouts": as_int(row.get("shutouts")),
                "gaa": round(as_float(row.get("goalsAgainstAverage")), 2),
                "hits": 0,
                "gp": as_int(row.get("gamesPlayed")),
                "hart": 0,
                "norris": 0,
                "selke": 0,
                "vezina": 0,
                "calder": 0,
                "champ": 0,
                "confFinals": 0,
                "scFinals": 0,
                "hof": 0,
                "country": player["country"],
                "goals": 0,
                "assists": 0,
                "points": as_int(row.get("points")),
                "plusminus": 0,
                "pim": as_int(row.get("penaltyMinutes")),
                "ppg": 0,
                "shg": 0,
                "sog": 0,
                "ops": 0,
                "dps": 0,
                "ps": 0,
                "qs": 0,
                "rbs": 0,
                "gsaa": 0,
                "sv": as_int(row.get("saves")),
            }
    return finalize_players(players)


def main():
    nfl = build_nfl()
    write_json("nfl_players.json", nfl)
    nba = build_nba()
    write_json("nba_players.json", nba)
    mlb = build_mlb()
    write_json("mlb_players.json", mlb)
    nhl = build_nhl()
    write_json("nhl_players.json", nhl)


if __name__ == "__main__":
    main()
