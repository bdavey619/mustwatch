"""
ncaaf.py — College football (FBS) data fetcher for Must Watch This Week.

Fetches from the ESPN unofficial API, same host as nba.py / nfl.py.
Returns (list[RawEvent], dict[str, TeamContext]) keyed by "NCAAF:{abbr}".

WHY THIS FETCHER IS SHAPED DIFFERENTLY
--------------------------------------
The MLB/NBA/NFL fetchers pull a standings table and derive team quality from
win percentage. That model breaks in college football:

  * ~136 FBS teams play wildly unequal schedules. A 4-0 Group of Five team and
    a 4-0 SEC team have the same win pct and are not remotely comparable.
  * There is no single league table — teams are spread across conferences that
    never play each other.
  * Records are tiny (12 games) and front-loaded with non-competitive
    non-conference games.

The poll is the sport's own answer to this problem, so this fetcher uses AP
poll position as the primary quality signal and treats win/loss record as
secondary context. Two sources feed it:

  * /rankings          — canonical AP Top 25, fetched once per run.
  * /scoreboard        — per-game, and each competitor carries `curatedRank`
                         (ESPN's live poll position, 99 = unranked) plus a
                         record summary. This is what team contexts are built
                         from, so no standings endpoint is involved.

INFERRED, NOT FETCHED
---------------------
ESPN's college scoreboard exposes no win/loss streak. Rather than leave
momentum dead, an undefeated team is treated as being on a win streak equal to
its win total — the one streak that reliably carries narrative weight in
college football. Every other team gets no streak. This is an inference, and
it is deliberately the only one in this module.

STATUS: unvalidated against a live response. Abbreviations in
config.NCAAF_RIVALRIES in particular need a real run to confirm — ESPN's
college abbreviations are not stable across endpoints the way pro ones are.
"""

import sys
from datetime import datetime, date, timedelta, timezone

import requests

from config import NCAAF_FBS_GROUP_ID
from models import RawEvent, TeamContext

ESPN_API = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
TIMEOUT  = 20

# ESPN uses 99 in curatedRank to mean "unranked".
UNRANKED_SENTINEL = 99

SEASON_TYPE_REGULAR    = 2
SEASON_TYPE_POSTSEASON = 3

_ET = timezone(timedelta(hours=-4))


def _get(url: str, **params) -> dict:
    r = requests.get(url, params=params or None, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_week(week_start: date, week_end: date) -> tuple[list[RawEvent], dict[str, TeamContext]]:
    """
    Fetch all FBS games in [week_start, week_end].
    Returns (events, contexts) where contexts is keyed by "NCAAF:{abbr}".
    """
    print("  [NCAAF] fetching AP poll...", file=sys.stderr)
    try:
        ap_ranks = _fetch_ap_poll()
    except Exception as e:
        print(f"  [NCAAF] warn: poll fetch failed, falling back to per-game ranks: {e}",
              file=sys.stderr)
        ap_ranks = {}
    print(f"  [NCAAF] {len(ap_ranks)} ranked teams", file=sys.stderr)

    print("  [NCAAF] fetching schedule...", file=sys.stderr)
    events:   list[RawEvent]        = []
    contexts: dict[str, TeamContext] = {}

    current = week_start
    while current <= week_end:
        date_str = current.strftime("%Y%m%d")
        try:
            day_events, day_contexts = _fetch_day(date_str, ap_ranks)
            events.extend(day_events)
            # Later days win on conflict — the most recent record is the truest.
            contexts.update(day_contexts)
        except Exception as e:
            print(f"  [NCAAF] warn: failed fetching {date_str}: {e}", file=sys.stderr)
        current += timedelta(days=1)

    print(f"  [NCAAF] {len(events)} events normalized, "
          f"{len(contexts)} team contexts built", file=sys.stderr)
    return events, contexts


def _fetch_ap_poll() -> dict[str, int]:
    """Return {abbr: rank} from the AP Top 25."""
    data = _get(f"{ESPN_API}/rankings")

    polls = data.get("rankings", []) or []
    poll  = _pick_poll(polls)
    if not poll:
        return {}

    ranks: dict[str, int] = {}
    for item in poll.get("ranks", []) or []:
        abbr = (item.get("team", {}).get("abbreviation") or "").strip().upper()
        if not abbr:
            continue
        try:
            ranks[abbr] = int(item.get("current"))
        except (ValueError, TypeError):
            continue
    return ranks


def _pick_poll(polls: list[dict]) -> dict | None:
    """
    Prefer the College Football Playoff rankings once they exist (they are the
    sport's actual stakes ladder late in the year), then AP, then whatever is
    first.
    """
    def _named(*needles: str) -> dict | None:
        for p in polls:
            name = (p.get("name") or p.get("shortName") or "").lower()
            if all(n in name for n in needles):
                return p
        return None

    return _named("playoff") or _named("ap") or (polls[0] if polls else None)


def _fetch_day(date_str: str, ap_ranks: dict[str, int]) -> tuple[list[RawEvent], dict[str, TeamContext]]:
    # groups=80 restricts to FBS. Without it the response includes FCS and
    # lower divisions and the candidate pool fills with games nobody is
    # choosing an evening around.
    data = _get(
        f"{ESPN_API}/scoreboard",
        dates=date_str,
        groups=NCAAF_FBS_GROUP_ID,
        limit=200,
    )

    events:   list[RawEvent]        = []
    contexts: dict[str, TeamContext] = {}

    for ev in data.get("events", []):
        parsed = _normalize_event(ev, ap_ranks)
        if not parsed:
            continue
        raw, home_ctx, away_ctx = parsed
        events.append(raw)
        contexts[f"NCAAF:{home_ctx.abbr}"] = home_ctx
        contexts[f"NCAAF:{away_ctx.abbr}"] = away_ctx

    return events, contexts


def _normalize_event(
    ev: dict,
    ap_ranks: dict[str, int],
) -> tuple[RawEvent, TeamContext, TeamContext] | None:
    """
    Build the event and both team contexts from a single scoreboard entry.

    Contexts come from the scoreboard rather than a standings table — see the
    module docstring for why there is no standings call here.
    """
    try:
        comp        = ev.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_ctx = _competitor_to_context(home, ap_ranks)
        away_ctx = _competitor_to_context(away, ap_ranks)
        if not home_ctx or not away_ctx:
            return None

        game_time_str = ev.get("date", comp.get("date", ""))
        game_time     = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
        game_date     = game_time.astimezone(_ET).date()

        season_type = ev.get("season", {}).get("type", SEASON_TYPE_REGULAR)

        week_no = ev.get("week", {}).get("number")
        try:
            week_no = int(week_no) if week_no is not None else None
        except (ValueError, TypeError):
            week_no = None

        raw = RawEvent(
            game_id=str(ev.get("id", "")),
            sport="NCAAF",
            home_abbr=home_ctx.abbr,
            away_abbr=away_ctx.abbr,
            home_name=home.get("team", {}).get("displayName", home_ctx.name),
            away_name=away.get("team", {}).get("displayName", away_ctx.name),
            game_time_utc=game_time,
            game_date=game_date,
            venue=comp.get("venue", {}).get("fullName", ""),
            is_postseason=(season_type == SEASON_TYPE_POSTSEASON),
            week=week_no,
            neutral_site=bool(comp.get("neutralSite", False)),
            is_conference_game=bool(comp.get("conferenceCompetition", False)),
            event_note=_event_note(comp),
        )
        return raw, home_ctx, away_ctx

    except Exception as e:
        print(f"  [NCAAF] warn: could not normalize event {ev.get('id')}: {e}", file=sys.stderr)
        return None


def _event_note(comp: dict) -> str | None:
    """Bowl or playoff round label, e.g. 'Rose Bowl'."""
    for note in comp.get("notes", []) or []:
        headline = (note.get("headline") or "").strip()
        if headline:
            return headline
    return None


def _competitor_to_context(competitor: dict, ap_ranks: dict[str, int]) -> TeamContext | None:
    team = competitor.get("team", {})
    abbr = (team.get("abbreviation") or "").strip().upper()
    if not abbr or _is_placeholder_abbr(abbr):
        return None

    wins, losses = _parse_record(competitor)
    gp      = wins + losses
    win_pct = wins / gp if gp > 0 else 0.0

    # Prefer the canonical poll; fall back to the per-game curated rank.
    ap_rank = ap_ranks.get(abbr)
    if ap_rank is None:
        ap_rank = _curated_rank(competitor)

    # Only inference in this module: an undefeated team is on a win streak
    # equal to its win total. Everyone else gets no streak, because ESPN's
    # college scoreboard does not publish one.
    if wins > 0 and losses == 0:
        streak_type, streak_n = "W", wins
    else:
        streak_type, streak_n = "W", 0

    return TeamContext(
        abbr=abbr,
        name=team.get("shortDisplayName") or team.get("displayName") or abbr,
        sport="NCAAF",
        wins=wins,
        losses=losses,
        win_pct=win_pct,
        l10_wins=0,
        l10_losses=0,
        streak_type=streak_type,
        streak_n=streak_n,
        games_played=gp,
        ap_rank=ap_rank,
        division=team.get("conferenceId"),
    )


def _curated_rank(competitor: dict) -> int | None:
    """ESPN's per-game poll position; 99 means unranked."""
    try:
        rank = int(competitor.get("curatedRank", {}).get("current"))
    except (ValueError, TypeError):
        return None
    return None if rank >= UNRANKED_SENTINEL else rank


def _parse_record(competitor: dict) -> tuple[int, int]:
    """
    Pull overall W-L from the competitor's record list.

    ESPN returns several record types (total / home / away / conference); the
    overall one is what matters. Ties are not parsed — college football has not
    had them since overtime arrived in 1996.
    """
    records = competitor.get("records", []) or []

    preferred = None
    for rec in records:
        rec_type = (rec.get("type") or rec.get("name") or "").lower()
        if rec_type in ("total", "overall"):
            preferred = rec
            break
    if preferred is None and records:
        preferred = records[0]
    if preferred is None:
        return 0, 0

    summary = str(preferred.get("summary", "")).strip()
    parts   = summary.split("-")
    if len(parts) < 2:
        return 0, 0
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0


def _is_placeholder_abbr(abbr: str) -> bool:
    if not abbr:
        return True
    return abbr == "TBD" or "/" in abbr
