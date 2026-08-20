"""
nfl.py — NFL data fetcher for Must Watch This Week.

Fetches schedule + standings from the ESPN unofficial API — the same host and
response conventions already used by nba.py.

Returns (list[RawEvent], dict[str, TeamContext]) keyed by "NFL:{abbr}".

Two things differ structurally from basketball and are handled here rather
than downstream:

  * Ties. Football games can end tied, so win_pct is (W + 0.5T) / GP and
    games_played must include ties.
  * No last-ten. A 17-game season has no meaningful "L10" — ESPN does not
    publish one for the NFL, and a 10-game window would span more than half
    the season. l10 is left at 0-0 and score.py switches to a streak-based
    momentum model for football. See score.py:_football_momentum.

Preseason (season.type 1) and the Pro Bowl (season.type 4) are dropped at
ingest — neither is ever a must-watch event, and letting them into the pool
would put exhibition football against pennant-race baseball.
"""

import sys
from datetime import datetime, date, timedelta, timezone

import requests

from models import RawEvent, TeamContext

ESPN_API    = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_API_V2 = "https://site.api.espn.com/apis/v2/sports/football/nfl"
TIMEOUT     = 15

# ESPN is inconsistent about a handful of NFL abbreviations across endpoints —
# normalize everything to the forms used as config.py keys.
ESPN_ABBR_MAP = {
    "WAS": "WSH",   # Washington Commanders
    "LA":  "LAR",   # Los Angeles Rams (bare "LA" appears on some endpoints)
    "SD":  "LAC",   # legacy San Diego → Los Angeles Chargers
    "OAK": "LV",    # legacy Oakland → Las Vegas Raiders
    "STL": "LAR",   # legacy St. Louis → Los Angeles Rams
    "JAC": "JAX",   # Jacksonville Jaguars
}

# ESPN season types. 2 (regular) and 3 (postseason) are the only ones we score.
SEASON_TYPE_PRESEASON  = 1
SEASON_TYPE_REGULAR    = 2
SEASON_TYPE_POSTSEASON = 3
SEASON_TYPE_PROBOWL    = 4

_ET = timezone(timedelta(hours=-4))


def _get(url: str, **params) -> dict:
    r = requests.get(url, params=params or None, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_week(week_start: date, week_end: date) -> tuple[list[RawEvent], dict[str, TeamContext]]:
    """
    Fetch all NFL games in [week_start, week_end] plus standings.
    Returns (events, contexts) where contexts is keyed by "NFL:{abbr}".
    """
    print("  [NFL] fetching standings...", file=sys.stderr)
    try:
        contexts = _fetch_standings()
    except Exception as e:
        print(f"  [NFL] error: standings fetch failed: {e}", file=sys.stderr)
        contexts = {}
    print(f"  [NFL] standings loaded for {len(contexts)} teams", file=sys.stderr)

    print("  [NFL] fetching schedule...", file=sys.stderr)
    events: list[RawEvent] = []
    current = week_start
    while current <= week_end:
        date_str = current.strftime("%Y%m%d")
        try:
            events.extend(_fetch_day(date_str))
        except Exception as e:
            print(f"  [NFL] warn: failed fetching {date_str}: {e}", file=sys.stderr)
        current += timedelta(days=1)

    print(f"  [NFL] {len(events)} events normalized", file=sys.stderr)
    return events, contexts


def _fetch_day(date_str: str) -> list[RawEvent]:
    data   = _get(f"{ESPN_API}/scoreboard", dates=date_str, limit=50)
    events = []
    for ev in data.get("events", []):
        raw = _normalize_event(ev)
        if raw:
            events.append(raw)
    return events


def _normalize_event(ev: dict) -> RawEvent | None:
    try:
        comp        = ev.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None

        season_type = ev.get("season", {}).get("type", SEASON_TYPE_REGULAR)

        # Exhibition football is never must-watch — drop before it reaches scoring.
        if season_type in (SEASON_TYPE_PRESEASON, SEASON_TYPE_PROBOWL):
            return None

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_team = home.get("team", {})
        away_team = away.get("team", {})

        h_abbr = _norm_abbr(home_team.get("abbreviation", ""))
        a_abbr = _norm_abbr(away_team.get("abbreviation", ""))

        # Playoff brackets carry TBD placeholders until seeding resolves.
        if _is_placeholder_abbr(h_abbr) or _is_placeholder_abbr(a_abbr):
            name = ev.get("name", f"{a_abbr} @ {h_abbr}")
            print(f"  [NFL] skip placeholder: {name!r}", file=sys.stderr)
            return None

        game_time_str = ev.get("date", comp.get("date", ""))
        game_time     = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
        game_date     = game_time.astimezone(_ET).date()

        week_no = ev.get("week", {}).get("number")
        try:
            week_no = int(week_no) if week_no is not None else None
        except (ValueError, TypeError):
            week_no = None

        return RawEvent(
            game_id=str(ev.get("id", "")),
            sport="NFL",
            home_abbr=h_abbr,
            away_abbr=a_abbr,
            home_name=home_team.get("displayName", home_team.get("name", "")),
            away_name=away_team.get("displayName", away_team.get("name", "")),
            game_time_utc=game_time,
            game_date=game_date,
            venue=comp.get("venue", {}).get("fullName", ""),
            is_postseason=(season_type == SEASON_TYPE_POSTSEASON),
            week=week_no,
            neutral_site=bool(comp.get("neutralSite", False)),
            event_note=_event_note(comp),
        )
    except Exception as e:
        print(f"  [NFL] warn: could not normalize event {ev.get('id')}: {e}", file=sys.stderr)
        return None


def _event_note(comp: dict) -> str | None:
    """Round label for postseason games, e.g. 'AFC Championship'."""
    for note in comp.get("notes", []) or []:
        headline = (note.get("headline") or "").strip()
        if headline:
            return headline
    return None


def _norm_abbr(abbr: str) -> str:
    abbr = (abbr or "").strip().upper()
    return ESPN_ABBR_MAP.get(abbr, abbr)


def _is_placeholder_abbr(abbr: str) -> bool:
    """Return True for ESPN composite/TBD team placeholders."""
    if not abbr:
        return True
    return abbr == "TBD" or "/" in abbr


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def _fetch_standings() -> dict[str, TeamContext]:
    """
    Returns contexts keyed by "NFL:{abbr}".

    ESPN nests NFL standings one level deeper than the NBA (conference →
    division → entries, rather than conference → entries), and the depth has
    changed before. Rather than hardcode the nesting, walk the tree and pick up
    entries wherever they appear, remembering the enclosing conference and
    division names on the way down.
    """
    data     = _get(f"{ESPN_API_V2}/standings")
    contexts: dict[str, TeamContext] = {}

    for conference, division, entry in _walk_standings(data, None, None):
        ctx = _entry_to_context(entry, conference, division)
        if ctx:
            contexts[f"NFL:{ctx.abbr}"] = ctx

    return contexts


def _walk_standings(node: dict, conference: str | None, division: str | None):
    """
    Yield (conference, division, entry) for every standings entry in the tree.

    The first level below the root names a conference (AFC/NFC); any deeper
    level names a division (e.g. "AFC East").
    """
    name = (node.get("name") or node.get("shortName") or "").strip()
    if name:
        if conference is None:
            conference = _normalize_conference(name)
        elif division is None:
            division = name

    for entry in node.get("standings", {}).get("entries", []) or []:
        yield conference, division, entry

    for child in node.get("children", []) or []:
        yield from _walk_standings(child, conference, division)


def _normalize_conference(name: str) -> str | None:
    """Map ESPN's conference label to 'AFC' / 'NFC'."""
    upper = name.upper()
    if "AFC" in upper or "AMERICAN" in upper:
        return "AFC"
    if "NFC" in upper or "NATIONAL" in upper:
        return "NFC"
    return None


def _entry_to_context(entry: dict, conference: str | None, division: str | None) -> TeamContext | None:
    team_info = entry.get("team", {})
    raw_abbr  = team_info.get("abbreviation", "")
    if not raw_abbr:
        return None

    abbr  = _norm_abbr(raw_abbr)
    stats = {s.get("name"): s for s in entry.get("stats", []) if s.get("name")}

    wins   = int(_stat_val(stats, "wins",   0) or 0)
    losses = int(_stat_val(stats, "losses", 0) or 0)
    ties   = int(_stat_val(stats, "ties",   0) or 0)

    gp = wins + losses + ties
    # A tie counts as half a win — the NFL's own standings convention.
    win_pct = (wins + 0.5 * ties) / gp if gp > 0 else 0.0

    seed = _stat_val(stats, "playoffSeed", None)
    try:
        conf_rank = int(seed) if seed is not None else None
    except (ValueError, TypeError):
        conf_rank = None

    streak_type, streak_n = _parse_streak(_stat_display(stats, "streak", ""))

    return TeamContext(
        abbr=abbr,
        name=team_info.get("displayName", team_info.get("name", abbr)),
        sport="NFL",
        wins=wins,
        losses=losses,
        win_pct=win_pct,
        # No meaningful last-ten in a 17-game season — football momentum is
        # scored from the streak instead (see module docstring).
        l10_wins=0,
        l10_losses=0,
        streak_type=streak_type,
        streak_n=streak_n,
        games_played=gp,
        conference=conference,
        conference_rank=conf_rank,
        ties=ties,
        division=division,
    )


# ---------------------------------------------------------------------------
# Parsing helpers — mirror nba.py
# ---------------------------------------------------------------------------

def _stat_val(stats: dict, name: str, default):
    """
    Read a numeric stat, preferring `value` but falling back to `displayValue`.

    ESPN populates one or the other depending on the endpoint and the stat. If
    only `displayValue` is set and we ignored it, wins/losses would silently
    read as 0 and every team would look 0-0 — a failure that produces plausible
    output rather than an error, so it is worth the extra branch.
    """
    s = stats.get(name)
    if s is None:
        return default

    v = s.get("value")
    if v is not None:
        return v

    dv = s.get("displayValue")
    if dv is None:
        return default
    try:
        return float(dv) if "." in str(dv) else int(dv)
    except (ValueError, TypeError):
        return default


def _stat_display(stats: dict, name: str, default: str) -> str:
    s = stats.get(name)
    if s is None:
        return default
    dv = s.get("displayValue")
    return str(dv) if dv is not None else default


def _parse_streak(val: str) -> tuple[str, int]:
    """Parse 'W3' / 'L2' / '3' / '-2' into ('W'|'L', n)."""
    if not val:
        return "W", 0
    val = val.strip()
    if val and val[0].upper() in ("W", "L"):
        try:
            return val[0].upper(), int(val[1:])
        except ValueError:
            pass
    try:
        n = int(val)
        return ("W" if n >= 0 else "L"), abs(n)
    except ValueError:
        pass
    return "W", 0
