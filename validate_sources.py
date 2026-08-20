"""
validate_sources.py — Check every live-data assumption the fetchers make.

The NFL and NCAAF fetchers were written against ESPN's response conventions
without ever seeing a live payload (the build environment blocked
site.api.espn.com). The unit tests in test_football.py prove the parsing logic
against hand-built fixtures; they prove nothing about whether the real payloads
have the shape those fixtures assume. This script closes that gap.

It makes real network calls, walks each assumption the fetchers depend on, and
reports pass / fail / warn per item.

Usage:
  python validate_sources.py                    # all sports
  python validate_sources.py --sports nfl       # one sport
  python validate_sources.py --date 2026-11-07  # probe a specific week

Exit code is 0 only when there are no FAILs. WARNs are informational — they
flag degraded-but-survivable conditions (a missing optional field, an
out-of-season endpoint) rather than broken assumptions.

Run this before enabling a sport in .github/workflows/generate.yml.

Several checks are only meaningful in season — poll population, FBS slate size,
college abbreviation coverage and playoffSeed all read empty before games are
played. A clean run in the offseason proves the endpoints are reachable and
parse, not that the data is usable.

Note also that passing here is necessary but not sufficient: see the season
opener BLOCKER in TODO.md, which is a scoring problem rather than a schema one.
"""

import argparse
import sys
from datetime import date, timedelta

import requests

import config

TIMEOUT = 25

_RESULTS: list[tuple[str, str, str, str]] = []   # (sport, status, label, detail)

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"


def record(sport: str, status: str, label: str, detail: str = "") -> None:
    _RESULTS.append((sport, status, label, detail))
    mark = {PASS: "✓", FAIL: "✗", WARN: "!", INFO: "·"}[status]
    line = f"  {mark} [{status:<4}] {label}"
    if detail:
        line += f"\n           {detail}"
    print(line, flush=True)


def expect(sport: str, cond: bool, label: str, detail: str = "",
           soft: bool = False) -> bool:
    """Record PASS when cond holds, otherwise FAIL (or WARN when soft)."""
    if cond:
        record(sport, PASS, label)
        return True
    record(sport, WARN if soft else FAIL, label, detail)
    return False


def get(url: str, **params) -> dict:
    r = requests.get(url, params=params or None, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def header(title: str) -> None:
    print(f"\n{'=' * 74}\n  {title}\n{'=' * 74}")


def _stat_names(entry: dict) -> set[str]:
    return {s.get("name") for s in entry.get("stats", []) if s.get("name")}


def _upcoming_dates(anchor: date, span: int = 7) -> list[date]:
    return [anchor + timedelta(days=i) for i in range(span)]


# ---------------------------------------------------------------------------
# NFL
# ---------------------------------------------------------------------------

def validate_nfl(anchor: date) -> None:
    import nfl
    header("NFL — site.api.espn.com/.../football/nfl")

    # --- Standings ---
    try:
        data = get(f"{nfl.ESPN_API_V2}/standings")
    except Exception as e:
        record("NFL", FAIL, "standings endpoint reachable", str(e))
        return
    record("NFL", PASS, "standings endpoint reachable")

    walked = list(nfl._walk_standings(data, None, None))
    expect("NFL", len(walked) >= 32,
           f"standings walker finds all 32 teams (found {len(walked)})",
           "The conference/division nesting differs from what _walk_standings "
           "expects. Inspect data['children'] structure.")

    confs = {c for c, _, _ in walked if c}
    expect("NFL", confs == {"AFC", "NFC"},
           f"conference names normalize to AFC/NFC (got {sorted(confs)})",
           "Check nfl._normalize_conference against the live 'name' fields.")

    divs = {d for _, d, _ in walked if d}
    expect("NFL", len(divs) >= 8,
           f"division names present (found {len(divs)}: {sorted(divs)[:4]}...)",
           "Divisions are used for the division_clash flag. Without them that "
           "flag never fires.", soft=True)

    if walked:
        _, _, sample = walked[0]
        names = _stat_names(sample)
        for stat, why in [
            ("wins",   "core record"),
            ("losses", "core record"),
        ]:
            expect("NFL", stat in names, f"standings stat '{stat}' present ({why})",
                   f"Available stats: {sorted(names)}")
        expect("NFL", "ties" in names, "standings stat 'ties' present",
               "Without it every tie silently becomes a non-game in win_pct.",
               soft=True)

        # playoffSeed is the backbone of the NFL stakes model.
        seeded = [e for _, _, e in walked
                  if nfl._stat_val(_stats(e), "playoffSeed", None) is not None]
        expect("NFL", len(seeded) >= 16,
               f"playoffSeed populated ({len(seeded)}/{len(walked)} teams)",
               "_nfl_stakes_base keys off playoffSeed. When absent it silently "
               "falls back to win-pct tiers, which is far less meaningful. "
               "Expected empty in the preseason.", soft=True)

    # --- Abbreviation coverage ---
    ctxs = {}
    try:
        ctxs = nfl._fetch_standings()
    except Exception as e:
        record("NFL", FAIL, "standings parse to TeamContext", str(e))

    if ctxs:
        record("NFL", INFO, f"parsed {len(ctxs)} team contexts")
        known = {k for k in config.MARQUEE_PLAYERS if k.startswith("NFL:")}
        unknown = sorted(set(ctxs) - known)
        expect("NFL", not unknown,
               "every ESPN abbreviation has a config.py entry",
               f"Unmapped: {unknown}. These teams score 3.0 star power "
               f"regardless of roster. Add to MARQUEE_PLAYERS or "
               f"nfl.ESPN_ABBR_MAP.")

        missing = sorted(known - set(ctxs))
        expect("NFL", not missing,
               "no config.py NFL keys are orphaned",
               f"In config but not returned by ESPN: {missing}", soft=True)

        ties_seen = [c.abbr for c in ctxs.values() if c.ties]
        record("NFL", INFO,
               f"teams with ties: {ties_seen or 'none this season'}")

    # --- Scoreboard ---
    _validate_espn_scoreboard(
        "NFL", nfl.ESPN_API, anchor,
        parse=lambda ev: nfl._normalize_event(ev),
        extra_params={"limit": 50},
    )


def _stats(entry: dict) -> dict:
    return {s.get("name"): s for s in entry.get("stats", []) if s.get("name")}


# ---------------------------------------------------------------------------
# NCAAF
# ---------------------------------------------------------------------------

def validate_ncaaf(anchor: date) -> None:
    import ncaaf
    header("NCAAF — site.api.espn.com/.../football/college-football")

    # --- Rankings ---
    ap_ranks = {}
    try:
        raw = get(f"{ncaaf.ESPN_API}/rankings")
        polls = raw.get("rankings", []) or []
        record("NCAAF", PASS, "rankings endpoint reachable")
        record("NCAAF", INFO,
               f"polls available: {[p.get('name') for p in polls]}")

        picked = ncaaf._pick_poll(polls)
        expect("NCAAF", picked is not None, "a poll is selectable",
               "ncaaf._pick_poll found nothing usable.")

        ap_ranks = ncaaf._fetch_ap_poll()
        expect("NCAAF", len(ap_ranks) >= 20,
               f"poll yields ranked teams (got {len(ap_ranks)})",
               "Expected ~25 in season, 0 in the offseason.", soft=True)
        if ap_ranks:
            top = sorted(ap_ranks.items(), key=lambda kv: kv[1])[:5]
            record("NCAAF", INFO, f"top 5: {top}")
    except Exception as e:
        record("NCAAF", FAIL, "rankings endpoint reachable", str(e))

    # --- Scoreboard + abbreviation harvest ---
    seen_abbrs: set[str] = set()
    parsed_games = 0
    fbs_ok = False
    checked_fields = False

    for d in _upcoming_dates(anchor):
        try:
            raw = get(f"{ncaaf.ESPN_API}/scoreboard",
                      dates=d.strftime("%Y%m%d"),
                      groups=config.NCAAF_FBS_GROUP_ID,
                      limit=200)
        except Exception as e:
            record("NCAAF", WARN, f"scoreboard {d} fetch failed", str(e))
            continue

        events = raw.get("events", []) or []
        if not events:
            continue
        fbs_ok = True

        for ev in events:
            for c in ev.get("competitions", [{}])[0].get("competitors", []):
                ab = (c.get("team", {}).get("abbreviation") or "").strip().upper()
                if ab:
                    seen_abbrs.add(ab)
            if ncaaf._normalize_event(ev, ap_ranks):
                parsed_games += 1

        # Field-level checks on the first real game we see
        if parsed_games and not checked_fields:
            checked_fields = True
            comp = events[0].get("competitions", [{}])[0]
            c0 = comp.get("competitors", [{}])[0]
            expect("NCAAF", "conferenceCompetition" in comp,
                   "scoreboard fields — conferenceCompetition present",
                   "Drives the conference_clash flag.", soft=True)
            expect("NCAAF", bool(c0.get("records")),
                   "scoreboard fields — competitor records present",
                   "Team contexts are built from these; without them every "
                   "record is 0-0.")
            expect("NCAAF", "curatedRank" in c0,
                   "scoreboard fields — curatedRank present",
                   "Fallback when the poll endpoint is unavailable.", soft=True)

    expect("NCAAF", fbs_ok,
           f"FBS scoreboard returns games (groups={config.NCAAF_FBS_GROUP_ID})",
           "No games in the probed week — try --date inside the season.",
           soft=True)
    if fbs_ok:
        record("NCAAF", INFO,
               f"parsed {parsed_games} games, {len(seen_abbrs)} distinct teams")

    # --- The high-risk check: config abbreviations vs. reality ---
    if seen_abbrs or ap_ranks:
        universe = seen_abbrs | set(ap_ranks)
        _check_ncaaf_config_abbrs(universe)
    else:
        record("NCAAF", WARN, "config abbreviation check skipped",
               "No live team data harvested — rerun with --date in season.")


def _check_ncaaf_config_abbrs(universe: set[str]) -> None:
    """
    Verify NCAAF_RIVALRIES / NCAAF_PROGRAM_PRESTIGE keys exist upstream.

    A wrong abbreviation here fails silently — the rivalry simply never fires —
    so it is the single most likely defect in the college config.
    """
    rivalry_abbrs = {a.split(":", 1)[1]
                     for pair in config.NCAAF_RIVALRIES for a in pair}
    prestige_abbrs = {k.split(":", 1)[1]
                      for k in config.NCAAF_PROGRAM_PRESTIGE}

    for label, abbrs in (("NCAAF_RIVALRIES", rivalry_abbrs),
                         ("NCAAF_PROGRAM_PRESTIGE", prestige_abbrs)):
        missing = sorted(a for a in abbrs if a not in universe)
        expect("NCAAF", not missing,
               f"{label} abbreviations all seen upstream "
               f"({len(abbrs) - len(missing)}/{len(abbrs)})",
               f"Not found in live data: {missing}\n           "
               f"These entries are dead — the flag/prestige never fires. "
               f"Only trust this when the probed week is mid-season with a "
               f"full slate.",
               soft=True)


# ---------------------------------------------------------------------------
# MLB — validates the wild card race fix
# ---------------------------------------------------------------------------

def validate_mlb(anchor: date) -> None:
    import mlb
    header("MLB — statsapi.mlb.com (wild card semantics)")

    try:
        ctxs = mlb._fetch_standings()
    except Exception as e:
        record("MLB", FAIL, "standings endpoint reachable", str(e))
        return
    record("MLB", PASS, "standings endpoint reachable")
    expect("MLB", len(ctxs) == 30, f"all 30 teams parsed (got {len(ctxs)})")

    # _parse_rank must never emit 0 — 0 reads as better than first place.
    zero_ranks = [c.abbr for c in ctxs.values()
                  if c.wild_card_rank == 0 or c.division_rank == 0]
    expect("MLB", not zero_ranks, "no rank parsed as 0",
           f"Teams with a 0 rank: {zero_ranks}. mlb._parse_rank should map "
           f"these to None.")

    holders = [c for c in ctxs.values()
               if c.wild_card_rank is not None
               and c.wild_card_rank <= config.MLB_WILD_CARD_SPOTS]
    record("MLB", INFO,
           f"teams holding a wild card spot: "
           f"{[(c.abbr, c.wild_card_rank) for c in holders]}")

    # The exact case the fix addresses: holds a wild card spot while well back
    # in the division.
    from score import _in_mlb_race
    deep = [c for c in holders
            if c.games_back is not None and c.games_back > config.MLB_RACE_THRESHOLD]
    if deep:
        ok = all(_in_mlb_race(c) for c in deep)
        expect("MLB", ok,
               "wild card holders far back in their division count as in the race",
               f"Failing: {[c.abbr for c in deep if not _in_mlb_race(c)]}")
        record("MLB", INFO,
               f"exercised by: {[(c.abbr, f'{c.games_back} GB', f'WC#{c.wild_card_rank}') for c in deep]}")
    else:
        record("MLB", INFO,
               "no wild card holder is currently >5 GB in its division — "
               "the fixed case is not live right now")

    wc_gb_present = [c.abbr for c in ctxs.values() if c.wc_games_back is not None]
    record("MLB", INFO,
           f"teams with a numeric wildCardGamesBack: {len(wc_gb_present)}/30 "
           f"(the rest send '-', which parses to None)")


# ---------------------------------------------------------------------------
# NBA — the known silent L10 fallback
# ---------------------------------------------------------------------------

def validate_nba(anchor: date) -> None:
    import nba
    header("NBA — site.api.espn.com/.../basketball/nba")

    try:
        ctxs = nba._fetch_standings()
    except Exception as e:
        record("NBA", FAIL, "standings endpoint reachable", str(e))
        return
    record("NBA", PASS, "standings endpoint reachable")
    expect("NBA", len(ctxs) == 30, f"all 30 teams parsed (got {len(ctxs)})",
           soft=True)

    # nba._extract_l10 falls back to a neutral 5-5 when ESPN omits the field,
    # which silently flattens momentum for every game.
    neutral = [c.abbr for c in ctxs.values()
               if (c.l10_wins, c.l10_losses) == (5, 5)]
    expect("NBA", len(neutral) < len(ctxs) / 2 if ctxs else False,
           f"L10 data is real, not the 5-5 fallback "
           f"({len(neutral)}/{len(ctxs)} teams read exactly 5-5)",
           "A large count means ESPN is not sending 'Last Ten Games' and every "
           "NBA momentum score is built on filler. See nba._extract_l10.",
           soft=True)

    known = {k for k in config.MARQUEE_PLAYERS if k.startswith("NBA:")}
    unknown = sorted(set(ctxs) - known)
    expect("NBA", not unknown, "every ESPN abbreviation has a config.py entry",
           f"Unmapped: {unknown} — check nba.ESPN_ABBR_MAP.")


# ---------------------------------------------------------------------------
# Shared scoreboard probe
# ---------------------------------------------------------------------------

def _validate_espn_scoreboard(sport, api_base, anchor, parse, extra_params=None):
    """Walk a week of scoreboard days and confirm events normalize."""
    total_raw = 0
    total_parsed = 0
    checked_fields = False

    for d in _upcoming_dates(anchor):
        try:
            raw = get(f"{api_base}/scoreboard",
                      dates=d.strftime("%Y%m%d"), **(extra_params or {}))
        except Exception as e:
            record(sport, WARN, f"scoreboard {d} fetch failed", str(e))
            continue

        events = raw.get("events", []) or []
        total_raw += len(events)

        for ev in events:
            if not checked_fields:
                checked_fields = True
                comp = ev.get("competitions", [{}])[0]
                expect(sport, "type" in ev.get("season", {}),
                       "scoreboard fields — season.type present",
                       "Used to separate preseason / regular / postseason. "
                       "Without it preseason games enter the pool.")
                expect(sport, "number" in ev.get("week", {}),
                       "scoreboard fields — week.number present", soft=True)
                expect(sport, bool(comp.get("venue")),
                       "scoreboard fields — venue present", soft=True)
                expect(sport, len(comp.get("competitors", [])) == 2,
                       "scoreboard fields — two competitors per event")
            if parse(ev):
                total_parsed += 1

    if total_raw == 0:
        record(sport, WARN, "scoreboard returned no events for the probed week",
               "Likely out of season — rerun with --date inside the season.")
        return

    expect(sport, total_parsed > 0,
           f"events normalize ({total_parsed}/{total_raw} parsed)",
           "Every event was rejected. Check the normalizer against a raw "
           "payload.")
    if total_parsed < total_raw:
        record(sport, INFO,
               f"{total_raw - total_parsed} event(s) skipped — expected for "
               f"preseason, Pro Bowl and TBD playoff placeholders")


# ---------------------------------------------------------------------------

VALIDATORS = {
    "MLB": validate_mlb,
    "NBA": validate_nba,
    "NFL": validate_nfl,
    "NCAAF": validate_ncaaf,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sports", help="Comma-separated subset, or 'all' (default)")
    ap.add_argument("--date", help="Anchor date YYYY-MM-DD for schedule probes "
                                   "(default: today)")
    args = ap.parse_args()

    anchor = date.fromisoformat(args.date) if args.date else date.today()

    if args.sports and args.sports.strip().lower() != "all":
        wanted = [s.strip().upper() for s in args.sports.split(",") if s.strip()]
        bad = [s for s in wanted if s not in VALIDATORS]
        if bad:
            print(f"Unknown sport(s): {', '.join(bad)}. "
                  f"Valid: {', '.join(VALIDATORS)}", file=sys.stderr)
            return 2
    else:
        wanted = list(VALIDATORS)

    print(f"Validating live data sources — anchor date {anchor}")

    for sport in wanted:
        try:
            VALIDATORS[sport](anchor)
        except Exception as e:
            record(sport, FAIL, "validator crashed",
                   f"{type(e).__name__}: {e}")

    # --- Summary ---
    header("SUMMARY")
    counts = {PASS: 0, FAIL: 0, WARN: 0, INFO: 0}
    for _, status, _, _ in _RESULTS:
        counts[status] += 1

    print(f"  {counts[PASS]} passed, {counts[FAIL]} failed, "
          f"{counts[WARN]} warnings, {counts[INFO]} notes\n")

    if counts[FAIL]:
        print("  FAILURES:")
        for sport, status, label, detail in _RESULTS:
            if status == FAIL:
                print(f"    [{sport}] {label}")
        print("\n  Do not enable a failing sport in the workflow.\n")
        return 1

    if counts[WARN]:
        print("  WARNINGS (review before enabling):")
        for sport, status, label, _ in _RESULTS:
            if status == WARN:
                print(f"    [{sport}] {label}")
        print()

    print("  No hard failures.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
