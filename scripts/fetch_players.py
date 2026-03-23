"""
Script to download player lists for major sports using the sportsipy library.

This script fetches player metadata for the NFL, NBA, MLB and NHL using
the sportsipy Python package.  It writes the results into JSON files in
the project's ``public`` folder so they can be served by the front-end at
runtime.  Each JSON file is an array of objects with the following fields:

    - ``nm``: The player's full name.
    - ``nmL``: The player's name in lowercase (for lookup).
    - ``pos``: A simple position code.  For the NHL this will be ``F``
      (skater) or ``G`` (goalie).  For the MLB this will be ``H`` for
      hitters and ``P`` for pitchers.  For the NBA it will be the
      player's primary position abbreviation.  For the NFL it will be
      whatever position string the library provides.
    - ``id``: A string identifier for the player.  Some leagues expose
      numeric IDs (e.g. ESPN, Baseball-Reference); when available they
      are converted to strings.  Otherwise a stable slug is used.
    - ``start`` / ``end``: A broad year range the player was active.
      This script does not compute accurate debut/retirement dates; it
      uses a generous window so that the UI's timeline filters include
      all players.
    - ``seasons``: A list with a single dummy season object.  The
      front-end requires a ``seasons`` array on each player for
      compatibility with its existing stat parsing code.  Real stat
      values are not populated here because the sportsipy API does not
      expose full career totals in a single call; instead, the dummy
      record satisfies the type expectations of the React code.

To run this script you must have the ``sportsipy`` package installed in
your Python environment.  You can install it via pip::

    pip install sportsipy

After installing, execute this script from the root of the project::

    python scripts/fetch_players.py

The resulting JSON files will be written to ``public/`` as
``nfl_players.json``, ``nba_players.json``, ``mlb_players.json`` and
``nhl_players.json``.  These files are small enough to be served
directly by the front-end and will allow the application to run
offline without relying on third‑party APIs.

This script is provided as a convenience for developers and is not
invoked automatically by the build process.  Make sure to re-run it
whenever you wish to update the player lists.
"""

import json
import os
from datetime import datetime

try:
    from sportsipy.nfl.teams import Teams as NFLTeams
    from sportsipy.nba.teams import Teams as NBATeams
    from sportsipy.mlb.teams import Teams as MLBTeams
    from sportsipy.nhl.teams import Teams as NHLTeams
except ImportError as exc:
    raise SystemExit(
        "The sportsipy package is required to run this script.\n"
        "Install it via 'pip install sportsipy' and try again."
    ) from exc

# Determine a fallback season to query when the current season's rosters have not yet
# been published on sports-reference.  sportsipy uses the given year as the
# season identifier (e.g. 2024 refers to the 2023-24 NBA season).  If the
# current season is not available, falling back to a completed season will
# generally succeed.  To improve reliability during the off-season, the
# ``_LAST_COMPLETED_YEAR`` constant subtracts two years from the current year,
# ensuring that only rosters from completed seasons are requested.  Feel free
# to adjust this constant if you know rosters are already available for a more
# recent year.
_CURRENT_YEAR = datetime.now().year
# Subtract 2 from the current year to select the last fully completed season.
_LAST_COMPLETED_YEAR = _CURRENT_YEAR - 2
_DEFAULT_YEAR = _LAST_COMPLETED_YEAR


def ensure_public_dir():
    """Return the absolute path to the public directory and create it if needed."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    public_dir = os.path.join(base_dir, "public")
    if not os.path.isdir(public_dir):
        os.makedirs(public_dir, exist_ok=True)
    return public_dir


def make_player_record(name: str, pos: str, identifier: str) -> dict:
    """Return a minimal player dictionary compatible with the front-end."""
    name = name.strip()
    return {
        "nm": name,
        "nmL": name.lower(),
        "pos": pos or "",
        "id": str(identifier),
        # Use a broad range to ensure timeline filters include the player.
        "start": 1900,
        "end": datetime.now().year + 1,
        # Provide a dummy season entry.  Actual stat parsing is handled
        # separately on demand by the front-end.
        "seasons": [
            {
                "year": datetime.now().year,
                "team": "",
            }
        ],
    }


def _accumulate_players(TeamClass, start_year: int, pos_func) -> list:
    """
    Generic helper to gather players across multiple seasons.  Iterates from
    ``start_year`` up to the default year and aggregates unique players.  For
    each appearance it updates the player's start/end years and appends a
    season stub.  ``pos_func`` should be a callable that takes the raw
    position string and returns a normalized code (e.g. "P"/"H" for MLB or
    "G"/"F" for NHL).
    """
    players_map = {}
    end_year = _DEFAULT_YEAR
    for year in range(start_year, end_year + 1):
        try:
            teams = TeamClass(year)
        except Exception:
            # If the year isn't available, continue.
            continue
        for team in teams:
            try:
                roster = team.roster
            except Exception:
                continue
            for player in getattr(roster, 'players', []):
                name = (player.name or "").strip()
                if not name:
                    continue
                key = name.lower()
                raw_pos = player.position or ""
                pos = pos_func(raw_pos)
                identifier = player.player_id or name
                if key not in players_map:
                    rec = make_player_record(name, pos, identifier)
                    rec['start'] = year
                    rec['end'] = year
                    # initialize seasons with the first appearance
                    rec['seasons'] = [
                        {
                            'year': year,
                            'team': getattr(team, 'abbreviation', '') or getattr(team, 'name', '') or ''
                        }
                    ]
                    players_map[key] = rec
                else:
                    rec = players_map[key]
                    rec['start'] = min(rec['start'], year)
                    rec['end'] = max(rec['end'], year)
                    rec['seasons'].append({
                        'year': year,
                        'team': getattr(team, 'abbreviation', '') or getattr(team, 'name', '') or ''
                    })
    # Return a list of aggregated player records
    return list(players_map.values())


# Historical start years for each league.  These values reflect the earliest
# seasons typically available on sports-reference via sportsipy.  They can be
# adjusted if you wish to include even earlier seasons, though doing so may
# significantly increase runtime without yielding additional players.
_EARLIEST_YEAR_BY_LEAGUE = {
    "NFL": 1920,  # National Football League founded in 1920
    "NBA": 1947,  # Basketball Association of America/NBA launched in 1947
    "MLB": 1871,  # National Association dates back to 1871; MLB rosters are
                   # generally available from the late 19th century onward
    "NHL": 1917,  # National Hockey League founded in 1917
}


def fetch_nfl_players() -> list:
    """
    Gather NFL players across all available seasons.  Uses the historical
    start year defined in ``_EARLIEST_YEAR_BY_LEAGUE`` to iterate from the
    league's inception up through the most recently available season.  If
    you wish to constrain the timeframe for performance reasons, adjust
    the start year accordingly.
    """
    start_year = _EARLIEST_YEAR_BY_LEAGUE.get("NFL", 1950)
    return _accumulate_players(NFLTeams, start_year, lambda p: p or "")


def fetch_nba_players() -> list:
    """
    Gather NBA players across all available seasons.  Uses the historical
    start year defined in ``_EARLIEST_YEAR_BY_LEAGUE`` to iterate from the
    league's inception up through the most recently available season.  If
    you wish to constrain the timeframe for performance reasons, adjust
    the start year accordingly.
    """
    start_year = _EARLIEST_YEAR_BY_LEAGUE.get("NBA", 1950)
    return _accumulate_players(NBATeams, start_year, lambda p: p or "")


def fetch_mlb_players() -> list:
    """
    Gather MLB players across all available seasons.  Uses the historical
    start year defined in ``_EARLIEST_YEAR_BY_LEAGUE`` to iterate from the
    league's earliest recorded seasons up through the most recent season.  A
    helper is used to classify positions into pitchers (``"P"``) and hitters
    (``"H"``) based on the sports-reference position abbreviation.  If you
    need a shorter window for performance reasons, adjust ``start_year``.
    """
    start_year = _EARLIEST_YEAR_BY_LEAGUE.get("MLB", 1950)
    return _accumulate_players(
        MLBTeams,
        start_year,
        lambda p: (
            "P" if (p or "").upper() in {"P", "SP", "RP"} else "H"
        ),
    )


def fetch_nhl_players() -> list:
    """
    Gather NHL players across all available seasons.  Uses the historical
    start year defined in ``_EARLIEST_YEAR_BY_LEAGUE`` to iterate from the
    league's inception up through the most recently available season.  A
    helper is used to normalize positions into goalies (``"G"``) and
    skaters (``"F"``).  Adjust ``start_year`` to narrow the timeframe if
    necessary.
    """
    start_year = _EARLIEST_YEAR_BY_LEAGUE.get("NHL", 1950)
    return _accumulate_players(
        NHLTeams,
        start_year,
        lambda p: ("G" if (p or "F").upper().startswith("G") else "F"),
    )


def main() -> None:
    public_dir = ensure_public_dir()
    datasets = {
        "nfl_players.json": fetch_nfl_players,
        "nba_players.json": fetch_nba_players,
        "mlb_players.json": fetch_mlb_players,
        "nhl_players.json": fetch_nhl_players,
    }
    for filename, fetch_fn in datasets.items():
        print(f"Fetching {filename.replace('_players.json','').upper()} players …")
        players = fetch_fn()
        out_path = os.path.join(public_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(players, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(players)} players to {out_path}")


if __name__ == "__main__":
    main()