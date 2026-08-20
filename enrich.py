"""
enrich.py — Normalize events, apply timing filter, detect narrative flags.
"""

import sys
from datetime import datetime, date

from config import (
    RIVALRIES, NCAAF_RIVALRIES, PLAYOFF_REMATCHES, MARQUEE_PITCHERS, MARQUEE_PLAYERS,
    TIMING_FILTER_SECONDS,
    NBA_PLAYOFF_RANK_CUTOFF, NBA_PLAYIN_RANK_CUTOFF,
    NFL_PLAYOFF_SEED_CUTOFF,
)
from models import RawEvent, TeamContext, ScoredEvent


def apply_timing_filter(
    events: list[RawEvent],
    now: datetime,
) -> tuple[list[RawEvent], list[tuple[RawEvent, str]]]:
    """
    Exclude events already started or starting within 1 hour.
    Returns (included, excluded_with_reason).
    """
    included = []
    excluded = []

    for ev in events:
        seconds_until = (ev.game_time_utc - now).total_seconds()
        if seconds_until < TIMING_FILTER_SECONDS:
            if seconds_until < 0:
                reason = "already started"
            else:
                mins = int(seconds_until // 60)
                reason = f"starts in <1hr ({mins}min)"
            excluded.append((ev, reason))
        else:
            included.append(ev)

    return included, excluded


def get_timing_label(ev: RawEvent, generation_date: date) -> str:
    """Return 'TONIGHT' (same day) or 'Weekday, Month Day'."""
    if ev.game_date == generation_date:
        return "TONIGHT"
    return ev.game_date.strftime("%A, %B %-d")


def detect_flags(
    ev: RawEvent,
    home_ctx: TeamContext,
    away_ctx: TeamContext,
) -> list[str]:
    """
    Detect narrative flags for an event.
    Tier 1: elimination_game (20 pts, no stacking)
    Tier 2: rivalry, playoff_rematch, first_place_clash (stackable, capped at 12)
    """
    flags: list[str] = []

    sport    = ev.sport
    home_key = f"{sport}:{home_ctx.abbr}"
    away_key = f"{sport}:{away_ctx.abbr}"
    pair     = frozenset({home_key, away_key})

    # --- Tier 1: elimination_game ---
    if ev.is_postseason and sport == "NBA":
        # Explicit play-in flag (ESPN season.type == 5) is the primary signal.
        if ev.is_playin:
            flags.append("elimination_game")
        else:
            # Fallback: infer from seed range if explicit flag is absent.
            # BOTH teams must be seeds 7–10 — a 2v7 playoff series is not play-in.
            home_rank = home_ctx.conference_rank or 99
            away_rank = away_ctx.conference_rank or 99
            if (NBA_PLAYOFF_RANK_CUTOFF < home_rank <= NBA_PLAYIN_RANK_CUTOFF and
                    NBA_PLAYOFF_RANK_CUTOFF < away_rank <= NBA_PLAYIN_RANK_CUTOFF):
                flags.append("elimination_game")

    # Football postseason is single elimination by construction — unlike a
    # best-of-seven, the loser's season is over in every round.
    if ev.is_postseason and sport == "NFL":
        flags.append("elimination_game")

    if ev.is_postseason and sport == "NCAAF" and _is_cfp_game(ev):
        flags.append("elimination_game")

    # --- Tier 2 (only if Tier 1 not set) ---
    if "elimination_game" not in flags:
        if pair in RIVALRIES or pair in NCAAF_RIVALRIES:
            flags.append("rivalry")

        if pair in PLAYOFF_REMATCHES:
            flags.append("playoff_rematch")

        if _is_first_place_clash(home_ctx, away_ctx):
            flags.append("first_place_clash")

        # ace_duel — MLB only; fires when BOTH probable starters are in MARQUEE_PITCHERS
        if ev.sport == "MLB":
            home_p = ev.home_probable_pitcher
            away_p = ev.away_probable_pitcher
            if home_p and away_p and MARQUEE_PITCHERS.get(home_p) and MARQUEE_PITCHERS.get(away_p):
                flags.append("ace_duel")

        # marquee_starter — MLB only; fires when exactly one starter is marquee
        # (ace_duel already handles the both-marquee case)
        if ev.sport == "MLB" and "ace_duel" not in flags:
            home_p = ev.home_probable_pitcher
            away_p = ev.away_probable_pitcher
            home_is_marquee = bool(home_p and MARQUEE_PITCHERS.get(home_p))
            away_is_marquee = bool(away_p and MARQUEE_PITCHERS.get(away_p))
            if home_is_marquee or away_is_marquee:
                flags.append("marquee_starter")

        # NBA-only narrative flags
        if ev.sport == "NBA":
            # superstar_matchup — both teams have at least one active superstar
            home_supers = [p for p in MARQUEE_PLAYERS.get(home_key, []) if p["tier"] == "superstar"]
            away_supers = [p for p in MARQUEE_PLAYERS.get(away_key, []) if p["tier"] == "superstar"]
            if home_supers and away_supers:
                flags.append("superstar_matchup")

            # momentum_mismatch — one team on a hot streak (L10 ≥ 8W), other struggling (L10 ≤ 5W)
            h_l10 = home_ctx.l10_wins
            a_l10 = away_ctx.l10_wins
            if (h_l10 >= 8 and a_l10 <= 5) or (a_l10 >= 8 and h_l10 <= 5):
                flags.append("momentum_mismatch")

            # seed_pressure — significant seeding gap (≥ 3 spots apart in conference)
            h_rank = home_ctx.conference_rank or 99
            a_rank = away_ctx.conference_rank or 99
            if abs(h_rank - a_rank) >= 3:
                flags.append("seed_pressure")

        # --- Football-only narrative flags ---
        if ev.sport == "NFL":
            # division_clash — divisional games swing tiebreakers and are played
            # twice a year with standings implications attached to both.
            if (home_ctx.division and away_ctx.division and
                    home_ctx.division == away_ctx.division):
                flags.append("division_clash")

        if ev.sport == "NCAAF":
            # conference_clash — the path to a conference title, and in the
            # expanded-playoff era the path to the national bracket.
            if ev.is_conference_game:
                flags.append("conference_clash")

        # undefeated_showdown — both teams unbeaten with a real sample behind
        # them. In football one loss reshapes a season, so an unbeaten team
        # meeting another is the sport's scarcest setup.
        if ev.sport in ("NFL", "NCAAF"):
            if _is_undefeated(home_ctx) and _is_undefeated(away_ctx):
                flags.append("undefeated_showdown")

    return flags


def _is_undefeated(ctx: TeamContext) -> bool:
    """Unbeaten with enough games played for it to mean something."""
    return ctx.losses == 0 and ctx.games_played >= 4


def _is_cfp_game(ev: RawEvent) -> bool:
    """
    True for College Football Playoff games — the only college postseason games
    that are genuinely elimination events. The other ~40 bowls are exhibitions.
    """
    note = (ev.event_note or "").lower()
    return any(k in note for k in
               ("playoff", "semifinal", "quarterfinal", "national championship"))


def _is_first_place_clash(home: TeamContext, away: TeamContext) -> bool:
    """True if both teams are in or within 1 game of first place."""
    if home.sport == "MLB":
        home_gb = home.games_back if home.games_back is not None else 0.0
        away_gb = away.games_back if away.games_back is not None else 0.0
        return home_gb <= 1.0 and away_gb <= 1.0

    if home.sport == "NFL":
        # NFL seeds 1–4 in each conference are exactly the four division
        # winners, so "both leading their division" is a seed test.
        home_seed = home.conference_rank or 99
        away_seed = away.conference_rank or 99
        return home_seed <= 4 and away_seed <= 4

    if home.sport == "NCAAF":
        # No standings table to lead — poll position already drives stakes and
        # star power, so this flag stays off rather than triple-counting it.
        return False

    # NBA
    home_rank = home.conference_rank or 99
    away_rank = away.conference_rank or 99
    return home_rank <= 2 and away_rank <= 2


def build_scored_event(
    ev: RawEvent,
    home_ctx: TeamContext,
    away_ctx: TeamContext,
    generation_date: date,
) -> ScoredEvent:
    """Build a ScoredEvent shell — scores populated later by score.py."""
    flags        = detect_flags(ev, home_ctx, away_ctx)
    timing_label = get_timing_label(ev, generation_date)

    return ScoredEvent(
        raw=ev,
        home_ctx=home_ctx,
        away_ctx=away_ctx,
        flags=flags,
        timing_label=timing_label,
    )


def enrich_events(
    events: list[RawEvent],
    team_contexts: dict[str, TeamContext],
    generation_date: date,
    now: datetime,
) -> tuple[list[ScoredEvent], list[tuple[RawEvent, str]]]:
    """
    Full enrichment pipeline:
    1. Apply timing filter
    2. Look up team contexts (keyed by "SPORT:ABBR")
    3. Detect flags + build ScoredEvent shells
    Returns (enriched_events, excluded_with_reasons).
    """
    included, excluded = apply_timing_filter(events, now)

    result: list[ScoredEvent] = []
    for ev in included:
        home_ctx = team_contexts.get(f"{ev.sport}:{ev.home_abbr}")
        away_ctx = team_contexts.get(f"{ev.sport}:{ev.away_abbr}")

        if not home_ctx or not away_ctx:
            missing = []
            if not home_ctx:
                missing.append(ev.home_abbr)
            if not away_ctx:
                missing.append(ev.away_abbr)
            excluded.append((ev, f"missing team context: {', '.join(missing)}"))
            continue

        se = build_scored_event(ev, home_ctx, away_ctx, generation_date)
        result.append(se)

    return result, excluded
