import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SRC = ROOT / "src"
LOGO_DIR = PUBLIC / "college_logos"


HEADERS = {"User-Agent": "Mozilla/5.0 Codex"}
FOOTBALL_GROUPS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/groups"
BASKETBALL_GROUPS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/groups"
NFLVERSE_PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet"
WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"


NFL_CONFS = ["ACC", "Big Ten", "Big 12", "SEC"]
NBA_CONFS = ["ACC", "Big Ten", "Big 12", "SEC", "Big East"]
NBA_TARGET_SCHOOLS = [
    "Kentucky",
    "UConn",
    "Duke",
    "Kansas",
    "Texas",
    "North Carolina",
    "Villanova",
    "Arizona",
    "Indiana",
    "Michigan",
    "Gonzaga",
    "St. John's",
    "Notre Dame",
]
CONF_LOGO_KEYS = {
    "ACC": "acc",
    "SEC": "sec",
    "Big Ten": "big_ten",
    "Big 12": "big_12",
    "Big East": "big_east",
}


NFL_SCHOOL_ALIASES = {
    "Miami": "Miami (FL)",
    "Miami (OH)": "Miami (OH)",
    "Louisiana State": "LSU",
    "LSU": "LSU",
    "Mississippi": "Ole Miss",
    "Penn State": "Penn State",
    "Ohio State": "Ohio State",
    "NC State": "NC State",
    "Ole Miss": "Ole Miss",
    "Southern Cal": "USC",
    "USC": "USC",
    "UCF": "UCF",
    "BYU": "BYU",
    "SMU": "SMU",
    "UCLA": "UCLA",
    "TCU": "TCU",
    "Pitt": "Pittsburgh",
    "California": "California",
}

NFL_P4_SCHOOL_TO_CONF = {
    "Alabama": "SEC",
    "Arkansas": "SEC",
    "Auburn": "SEC",
    "Florida": "SEC",
    "Georgia": "SEC",
    "Kentucky": "SEC",
    "LSU": "SEC",
    "Mississippi State": "SEC",
    "Missouri": "SEC",
    "Oklahoma": "SEC",
    "Ole Miss": "SEC",
    "South Carolina": "SEC",
    "Tennessee": "SEC",
    "Texas": "SEC",
    "Texas A&M": "SEC",
    "Vanderbilt": "SEC",
    "Arizona": "Big 12",
    "Arizona State": "Big 12",
    "Baylor": "Big 12",
    "BYU": "Big 12",
    "Cincinnati": "Big 12",
    "Colorado": "Big 12",
    "Houston": "Big 12",
    "Iowa State": "Big 12",
    "Kansas": "Big 12",
    "Kansas State": "Big 12",
    "Oklahoma State": "Big 12",
    "TCU": "Big 12",
    "Texas Tech": "Big 12",
    "UCF": "Big 12",
    "Utah": "Big 12",
    "West Virginia": "Big 12",
    "Boston College": "ACC",
    "California": "ACC",
    "Clemson": "ACC",
    "Duke": "ACC",
    "Florida State": "ACC",
    "Georgia Tech": "ACC",
    "Louisville": "ACC",
    "Miami (FL)": "ACC",
    "NC State": "ACC",
    "North Carolina": "ACC",
    "Pittsburgh": "ACC",
    "SMU": "ACC",
    "Stanford": "ACC",
    "Syracuse": "ACC",
    "Virginia": "ACC",
    "Virginia Tech": "ACC",
    "Wake Forest": "ACC",
    "Illinois": "Big Ten",
    "Indiana": "Big Ten",
    "Iowa": "Big Ten",
    "Maryland": "Big Ten",
    "Michigan": "Big Ten",
    "Michigan State": "Big Ten",
    "Minnesota": "Big Ten",
    "Nebraska": "Big Ten",
    "Northwestern": "Big Ten",
    "Ohio State": "Big Ten",
    "Oregon": "Big Ten",
    "Penn State": "Big Ten",
    "Purdue": "Big Ten",
    "Rutgers": "Big Ten",
    "UCLA": "Big Ten",
    "USC": "Big Ten",
    "Washington": "Big Ten",
    "Wisconsin": "Big Ten",
    "Notre Dame": "Independent",
}

NBA_SCHOOL_ALIASES = {
    "Connecticut": "UConn",
    "UConn": "UConn",
    "Duke": "Duke",
    "Kansas": "Kansas",
    "Texas": "Texas",
    "North Carolina": "North Carolina",
    "Villanova": "Villanova",
    "Arizona": "Arizona",
    "Indiana": "Indiana",
    "Michigan": "Michigan",
    "Gonzaga": "Gonzaga",
    "St. John's (NY)": "St. John's",
    "St. John's": "St. John's",
    "Notre Dame": "Notre Dame",
    "Kentucky": "Kentucky",
    "Southern Methodist": "SMU",
    "Southern California": "USC",
    "California": "California",
    "Southern Methodist University": "SMU",
}

SEARCH_TERMS = {
    "UConn": "University of Connecticut",
    "North Carolina": "University of North Carolina at Chapel Hill",
    "Kansas": "University of Kansas",
    "Texas": "University of Texas at Austin",
    "Arizona": "University of Arizona",
    "Michigan": "University of Michigan",
    "California": "University of California, Berkeley",
    "SMU": "Southern Methodist University",
    "USC": "University of Southern California",
    "South Carolina": "University of South Carolina",
    "UCLA": "University of California, Los Angeles",
    "LSU": "Louisiana State University",
    "Ole Miss": "University of Mississippi",
    "Pittsburgh": "University of Pittsburgh",
    "Notre Dame": "University of Notre Dame",
    "St. John's": "St. John's University",
    "BYU": "Brigham Young University",
    "TCU": "Texas Christian University",
    "UCF": "University of Central Florida",
    "West Virginia": "West Virginia University",
    "NC State": "North Carolina State University",
    "Georgia Tech": "Georgia Institute of Technology",
    "Miami (FL)": "University of Miami",
    "Miami": "University of Miami",
    "Penn State": "Pennsylvania State University",
    "Boston College": "Boston College",
    "Duke": "Duke University",
    "Gonzaga": "Gonzaga University",
    "Villanova": "Villanova University",
    "Kentucky": "University of Kentucky",
    "Indiana": "Indiana University Bloomington",
    "Baylor": "Baylor University",
    "Cincinnati": "University of Cincinnati",
    "Colorado": "University of Colorado Boulder",
    "Houston": "University of Houston",
    "Iowa State": "Iowa State University",
    "Kansas State": "Kansas State University",
    "Oklahoma State": "Oklahoma State University",
    "Texas Tech": "Texas Tech University",
    "Utah": "University of Utah",
    "Washington": "University of Washington",
    "Oregon": "University of Oregon",
    "Florida State": "Florida State University",
    "Wake Forest": "Wake Forest University",
    "Virginia Tech": "Virginia Tech",
    "Virginia": "University of Virginia",
    "Clemson": "Clemson University",
    "Louisville": "University of Louisville",
    "Stanford": "Stanford University",
    "Syracuse": "Syracuse University",
    "Nebraska": "University of Nebraska–Lincoln",
    "Rutgers": "Rutgers University",
    "Purdue": "Purdue University",
    "Northwestern": "Northwestern University",
    "Maryland": "University of Maryland, College Park",
    "Michigan State": "Michigan State University",
    "Minnesota": "University of Minnesota",
    "Wisconsin": "University of Wisconsin–Madison",
    "Illinois": "University of Illinois Urbana-Champaign",
    "Iowa": "University of Iowa",
    "Auburn": "Auburn University",
    "Alabama": "University of Alabama",
    "Arkansas": "University of Arkansas",
    "Florida": "University of Florida",
    "Georgia": "University of Georgia",
    "Mississippi State": "Mississippi State University",
    "Missouri": "University of Missouri",
    "Oklahoma": "University of Oklahoma",
    "South Carolina": "University of South Carolina",
    "Tennessee": "University of Tennessee",
    "Texas A&M": "Texas A&M University",
    "Vanderbilt": "Vanderbilt University",
}


def fetch_json(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_bytes(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.content


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def normalize_name(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_school(name, alias_map):
    name = (name or "").strip()
    if not name:
        return ""
    name = re.sub(r"\s+\([^)]*\)$", "", name).strip()
    name = name.replace("St. John’s", "St. John's")
    name = name.replace("Saint John's", "St. John's")
    return alias_map.get(name, name)


def get_espn_group_children(url, top_name):
    data = fetch_json(url)
    groups = data.get("groups", [])
    for group in groups:
        if group.get("name") == top_name:
            return group.get("children", [])
    return []


def download_logo(url, stem):
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGO_DIR / f"{stem}.png"
    path.write_bytes(fetch_bytes(url))
    return f"/college_logos/{stem}.png"


def build_conference_team_map(children, wanted_conf_names, alias_map):
    schools = []
    school_to_conf = {}
    school_logo_map = {}
    for child in children:
        conf_name = child.get("name", "")
        conf_short = None
        if "Atlantic Coast" in conf_name:
            conf_short = "ACC"
        elif "Big Ten" in conf_name:
            conf_short = "Big Ten"
        elif "Big 12" in conf_name:
            conf_short = "Big 12"
        elif "Southeastern" in conf_name:
            conf_short = "SEC"
        elif "Big East" in conf_name:
            conf_short = "Big East"
        elif "Independent" in conf_name:
            conf_short = "Independent"
        if conf_short not in wanted_conf_names:
            continue
        for team in child.get("teams", []):
            school = canonical_school(team.get("shortDisplayName") or team.get("displayName") or "", alias_map)
            if not school:
                continue
            logos = team.get("logos") or []
            logo_href = logos[0]["href"] if logos else ""
            if school not in school_to_conf:
                school_to_conf[school] = conf_short
                schools.append(school)
            if logo_href and school not in school_logo_map:
                school_logo_map[school] = download_logo(logo_href, slugify(school))
    return schools, school_to_conf, school_logo_map


def resolve_wikidata_school_id(school):
    query = SEARCH_TERMS.get(school, school)
    data = fetch_json(
        WIKIDATA_SEARCH_URL,
        {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "type": "item",
            "search": query,
            "limit": 8,
        },
    )
    items = data.get("search", [])
    school_words = ("university", "college", "institute", "school")
    for item in items:
        desc = (item.get("description") or "").lower()
        label = (item.get("label") or "").lower()
        if any(word in desc for word in school_words) or any(word in label for word in school_words):
            return item["id"]
    return items[0]["id"] if items else ""


def fetch_wikidata_alumni(qid):
    query = f"""
    SELECT ?playerLabel WHERE {{
      ?player wdt:P69 wd:{qid};
              wdt:P106/wdt:P279* wd:Q3665646.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    r = requests.get(
        WIKIDATA_SPARQL_URL,
        params={"format": "json", "query": query},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return [row["playerLabel"]["value"] for row in data["results"]["bindings"] if row.get("playerLabel")]


def enrich_nfl_players(nfl_school_to_conf):
    nfl_players_path = PUBLIC / "nfl_players.json"
    players = json.loads(nfl_players_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(NFLVERSE_PLAYERS_URL, columns=["display_name", "position", "college_name"])
    df["norm_name"] = df["display_name"].map(normalize_name)
    nflverse_map = {}
    for _, row in df.iterrows():
        norm = row["norm_name"]
        school = canonical_school(str(row["college_name"]), NFL_SCHOOL_ALIASES)
        if not norm or not school:
            continue
        nflverse_map.setdefault(norm, set()).add(school)
    for player in players:
        nm = player.get("nm") or ""
        norm = normalize_name(nm)
        current_col = canonical_school(player.get("col", ""), NFL_SCHOOL_ALIASES)
        schools = nflverse_map.get(norm, set())
        chosen = ""
        if len(schools) == 1:
            chosen = next(iter(schools))
        elif current_col and current_col in schools:
            chosen = current_col
        elif current_col:
            chosen = current_col
        if chosen:
            player["col"] = chosen
        col = canonical_school(player.get("col", ""), NFL_SCHOOL_ALIASES)
        if col in nfl_school_to_conf:
            player["col"] = col
            player["colConf"] = nfl_school_to_conf[col]
    nfl_players_path.write_text(json.dumps(players, ensure_ascii=False), encoding="utf-8")


def enrich_nba_players(nba_school_to_conf):
    nba_players_path = PUBLIC / "nba_players.json"
    players = json.loads(nba_players_path.read_text(encoding="utf-8"))
    local_by_name = {}
    for player in players:
        local_by_name.setdefault(normalize_name(player.get("nm", "")), []).append(player)

    school_to_qid = {}
    for school in sorted(nba_school_to_conf.keys()):
        qid = resolve_wikidata_school_id(school)
        if qid:
            school_to_qid[school] = qid

    for school, qid in school_to_qid.items():
        conf = nba_school_to_conf[school]
        for alumnus in fetch_wikidata_alumni(qid):
            norm = normalize_name(alumnus)
            if norm not in local_by_name:
                continue
            for player in local_by_name[norm]:
                player["col"] = school
                player["colConf"] = conf

    nba_players_path.write_text(json.dumps(players, ensure_ascii=False), encoding="utf-8")


def build_college_meta_js(
    nfl_schools,
    nba_target_schools,
    nfl_confs,
    nba_confs,
    logo_map,
):
    content = [
        "export const NFL_POWER4_SCHOOLS = " + json.dumps(nfl_schools, ensure_ascii=False, indent=2) + ";",
        "export const NFL_POWER4_CONFS = " + json.dumps(nfl_confs, ensure_ascii=False, indent=2) + ";",
        "export const NBA_COLLEGE_SCHOOLS = " + json.dumps(nba_target_schools, ensure_ascii=False, indent=2) + ";",
        "export const NBA_MAJOR_CONFS = " + json.dumps(nba_confs, ensure_ascii=False, indent=2) + ";",
        "export const COLLEGE_LOGOS = " + json.dumps(logo_map, ensure_ascii=False, indent=2) + ";",
    ]
    (SRC / "collegeMeta.js").write_text("\n\n".join(content) + "\n", encoding="utf-8")


def main():
    football_children = get_espn_group_children(FOOTBALL_GROUPS_URL, "NCAA Division I")
    basketball_children = get_espn_group_children(BASKETBALL_GROUPS_URL, "NCAA Division I")

    football_teams = []
    for child in football_children:
        if child.get("name") == "FBS":
            football_teams.extend(child.get("teams", []))
    nfl_school_to_conf = dict(NFL_P4_SCHOOL_TO_CONF)
    nfl_schools = sorted(nfl_school_to_conf.keys())
    nfl_logo_map = {}
    for team in football_teams:
        school = canonical_school(team.get("shortDisplayName") or team.get("displayName") or "", NFL_SCHOOL_ALIASES)
        if school not in nfl_school_to_conf:
            continue
        logos = team.get("logos") or []
        logo_href = logos[0]["href"] if logos else ""
        if logo_href and school not in nfl_logo_map:
            nfl_logo_map[school] = download_logo(logo_href, slugify(school))
    nba_conf_schools, nba_school_to_conf, nba_logo_map = build_conference_team_map(
        basketball_children,
        set(NBA_CONFS),
        NBA_SCHOOL_ALIASES,
    )

    conf_logo_map = {}
    for conf_name, conf_key in CONF_LOGO_KEYS.items():
        conf_logo_map[conf_name] = download_logo(
            f"https://a.espncdn.com/i/teamlogos/ncaa_conf/500/{conf_key}.png",
            slugify(conf_name),
        )

    enrich_nfl_players(nfl_school_to_conf)
    enrich_nba_players(nba_school_to_conf)

    all_logo_map = {}
    all_logo_map.update(nfl_logo_map)
    all_logo_map.update(nba_logo_map)
    all_logo_map.update(conf_logo_map)

    build_college_meta_js(
        sorted(nfl_schools),
        NBA_TARGET_SCHOOLS,
        NFL_CONFS,
        NBA_CONFS,
        all_logo_map,
    )

    print("NFL schools", len(nfl_schools))
    print("NBA conf schools", len(nba_conf_schools))
    print("logos", len(all_logo_map))


if __name__ == "__main__":
    main()
