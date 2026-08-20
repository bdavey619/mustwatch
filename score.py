"""
score.py — Pure scoring functions for Must Watch This Week.

No I/O. All functions take data, return numbers.
"""

from config import (
    MARQUEE_PLAYERS, NCAAF_PROGRAM_PRESTIGE,
    SEASON_PHASE_MULTIPLIERS,
    MLB_TOTAL_GAMES, NBA_TOTAL_GAMES, NFL_TOTAL_GAMES, NCAAF_TOTAL_GAMES,
    MLB_RACE_THRESHOLD,
    NBA_PLAYOFF_RANK_CUTOFF, NBA_PLAYIN_RANK_CUTOFF,
    NFL_PLAYOFF_SEED_CUTOFF, NFL_HUNT_SEED_CUTOFF,
    NCAAF_ELITE_RANK, NCAAF_RANKED_CUTOFF,
)
from models import TeamContext, ScoredEvent, RawEvent

# Games in a full season, by sport — drives the season-phase multiplier.
TOTAL_GAMES = {
    "MLB":   MLB_TOTAL_GAMES,
    "NBA":   NBA_TOTAL_GAMES,
    "NFL":   NFL_TOTAL_GAMES,
    "NCAAF": NCAAF_TOTAL_GAMES,
}

FOOTBALL_SPORTS = ("NFL", "NCAAF")


# ---------------------------------------------------------------------------
# Team quality (0–10) — input to competitive_balance
# ---------------------------------------------------------------------------

def team_quality(win_pct: float) -> float:
    """Map win percentage to a quality score from 2–10."""
    if win_pct >= 0.650: return 10.0
    if win_pct >= 0.620: return 9.0
    if win_pct >= 0.580: return 8.0
    if win_pct >= 0.540: return 7.0
    if win_pct >= 0.520: return 6.0
    if win_pct >= 0.500: return 5.0
    if win_pct >= 0.480: return 4.0
    if win_pct >= 0.460: return 3.0
    return 2.0


def nfl_team_quality(win_pct: float) -> float:
    """
    NFL quality curve.

    A 17-game season spreads win percentage far wider than a 162- or 82-game
    one: .650 is a fringe playoff team in baseball and an 11-6 division winner
    in football. Thresholds are stretched to match, so the top of the scale
    stays reserved for genuinely dominant teams.
    """
    if win_pct >= 0.750: return 10.0
    if win_pct >= 0.700: return 9.0
    if win_pct >= 0.650: return 8.0
    if win_pct >= 0.550: return 7.0
    if win_pct >= 0.500: return 6.0
    if win_pct >= 0.450: return 4.0
    if win_pct >= 0.350: return 3.0
    return 2.0


def ncaaf_team_quality(ctx: TeamContext) -> float:
    """
    NCAAF quality from poll position, not record.

    Win percentage is close to meaningless in college football — schedules are
    not comparable — so the poll does the work. An unranked team falls back to
    a record-based floor that cannot reach the top of the scale.
    """
    rank = ctx.ap_rank
    if rank is not None:
        if rank <= 4:  return 10.0
        if rank <= 10: return 9.0
        if rank <= 15: return 8.0
        if rank <= 25: return 7.0

    # Unranked — capped well below any ranked team.
    if ctx.games_played == 0:
        return 3.0
    if ctx.win_pct >= 0.800: return 5.0
    if ctx.win_pct >= 0.600: return 4.0
    if ctx.win_pct >= 0.500: return 3.0
    return 2.0


def quality_for(ctx: TeamContext) -> float:
    """Sport-aware team quality."""
    if ctx.sport == "NCAAF":
        return ncaaf_team_quality(ctx)
    if ctx.sport == "NFL":
        return nfl_team_quality(ctx.win_pct)
    return team_quality(ctx.win_pct)


# ---------------------------------------------------------------------------
# Season phase multiplier
# ---------------------------------------------------------------------------

def season_phase_multiplier(games_played: int, total_games: int) -> float:
    if total_games == 0:
        return 1.0
    pct = games_played / total_games
    if pct < 0.20:
        return SEASON_PHASE_MULTIPLIERS["early"]
    if pct < 0.70:
        return SEASON_PHASE_MULTIPLIERS["mid"]
    return SEASON_PHASE_MULTIPLIERS["late"]


# ---------------------------------------------------------------------------
# Stakes (0–30)
# ---------------------------------------------------------------------------

def score_stakes(
    home: TeamContext,
    away: TeamContext,
    is_postseason: bool,
    is_playin: bool = False,
    event: RawEvent | None = None,
) -> tuple[float, str]:
    """
    Returns (score, detail_string).

    `event` is optional and used only by NCAAF, where postseason games range
    from a national semifinal to a 6-6 team in an exhibition bowl and the round
    label is the only thing that separates them.
    """
    if is_postseason:
        # Prefer the explicit play-in flag (ESPN season.type == 5).
        # Keep seed-range inference as fallback in case the type field is absent.
        if is_playin:
            return 25.0, "play-in game"

        if home.sport == "NBA":
            home_rank = home.conference_rank or 99
            away_rank = away.conference_rank or 99
            if (NBA_PLAYOFF_RANK_CUTOFF < home_rank <= NBA_PLAYIN_RANK_CUTOFF and
                    NBA_PLAYOFF_RANK_CUTOFF < away_rank <= NBA_PLAYIN_RANK_CUTOFF):
                return 25.0, "play-in game (inferred)"

        if home.sport == "NFL":
            # Every NFL playoff game is single elimination — the season ends
            # for one team. Nothing in the regular season compares.
            return 30.0, "playoff elimination game"

        if home.sport == "NCAAF":
            return _ncaaf_postseason_stakes(event)

        return 29.0, "postseason"

    if home.sport == "MLB":
        base, detail = _mlb_stakes_base(home, away)
    elif home.sport == "NFL":
        base, detail = _nfl_stakes_base(home, away)
    elif home.sport == "NCAAF":
        base, detail = _ncaaf_stakes_base(home, away)
    else:
        base, detail = _nba_stakes_base(home, away)

    mult = season_phase_multiplier(
        max(home.games_played, away.games_played),
        TOTAL_GAMES.get(home.sport, MLB_TOTAL_GAMES),
    )

    raw    = round(base * mult, 1)
    detail = f"{detail} ×{mult:.2f}"
    return raw, detail


def _in_mlb_race(ctx: TeamContext) -> bool:
    """True if team is in a meaningful playoff/division race."""
    # Division leader
    if ctx.games_back is None:
        return True
    # Within 5 of division leader
    if ctx.games_back <= MLB_RACE_THRESHOLD:
        return True
    # Within 5 of last wild card spot
    if ctx.wc_games_back is not None and ctx.wc_games_back <= MLB_RACE_THRESHOLD:
        return True
    return False


def _mlb_stakes_base(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    home_in = _in_mlb_race(home)
    away_in = _in_mlb_race(away)

    if home_in and away_in:
        avg_wpct = (home.win_pct + away.win_pct) / 2
        if avg_wpct >= 0.550:
            return 22.0, "both in race (strong)"
        return 18.0, "both in race"

    if home_in or away_in:
        return 15.0, "one team in race"

    avg_wpct = (home.win_pct + away.win_pct) / 2
    if avg_wpct >= 0.520:
        return 12.0, "both above .500"
    return 5.0, "no meaningful stakes"


def _nba_stakes_base(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    home_rank = home.conference_rank or 99
    away_rank = away.conference_rank or 99

    # Both in direct playoff position (top 6)
    if home_rank <= NBA_PLAYOFF_RANK_CUTOFF and away_rank <= NBA_PLAYOFF_RANK_CUTOFF:
        avg_wpct = (home.win_pct + away.win_pct) / 2
        if avg_wpct >= 0.600:
            return 22.0, "top-6 playoff teams (elite)"
        return 18.0, "both in direct playoff position"

    home_playin = NBA_PLAYOFF_RANK_CUTOFF < home_rank <= NBA_PLAYIN_RANK_CUTOFF
    away_playin = NBA_PLAYOFF_RANK_CUTOFF < away_rank <= NBA_PLAYIN_RANK_CUTOFF

    if (home_rank <= NBA_PLAYOFF_RANK_CUTOFF and away_playin) or \
       (away_rank <= NBA_PLAYOFF_RANK_CUTOFF and home_playin) or \
       (home_playin and away_playin):
        return 16.0, "playoff/play-in implications"

    if home_playin or away_playin:
        return 14.0, "one team in play-in race"

    avg_wpct = (home.win_pct + away.win_pct) / 2
    if avg_wpct >= 0.520:
        return 10.0, "both above .500"
    return 5.0, "no meaningful stakes"


def _nfl_stakes_base(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    """
    NFL regular season stakes, driven by conference playoff seed.

    Seeds 1–7 are playoff position; 8–10 are live in the race. Before ESPN
    publishes a seed (early season) both fall through to 99 and the win-pct
    tiers decide — which the season-phase multiplier then discounts anyway.
    """
    home_seed = home.conference_rank or 99
    away_seed = away.conference_rank or 99

    home_in = home_seed <= NFL_PLAYOFF_SEED_CUTOFF
    away_in = away_seed <= NFL_PLAYOFF_SEED_CUTOFF
    home_hunting = NFL_PLAYOFF_SEED_CUTOFF < home_seed <= NFL_HUNT_SEED_CUTOFF
    away_hunting = NFL_PLAYOFF_SEED_CUTOFF < away_seed <= NFL_HUNT_SEED_CUTOFF

    if home_in and away_in:
        avg_wpct = (home.win_pct + away.win_pct) / 2
        if avg_wpct >= 0.700:
            return 24.0, "two playoff teams (elite)"
        return 20.0, "both in playoff position"

    if (home_in and away_hunting) or (away_in and home_hunting):
        return 17.0, "playoff position vs. team in the hunt"

    if home_hunting and away_hunting:
        return 16.0, "both fighting for the last spots"

    if home_in or away_in:
        return 14.0, "one team in playoff position"

    if home_hunting or away_hunting:
        return 12.0, "one team in the hunt"

    avg_wpct = (home.win_pct + away.win_pct) / 2
    if avg_wpct >= 0.520:
        return 10.0, "both above .500"
    return 5.0, "no meaningful stakes"


def _ncaaf_stakes_base(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    """
    NCAAF regular season stakes, driven by poll position.

    One loss can end a national title case, so a top-10 matchup carries stakes
    closer to a pro playoff game than to a regular season one.
    """
    home_rank = home.ap_rank
    away_rank = away.ap_rank

    home_ranked = home_rank is not None and home_rank <= NCAAF_RANKED_CUTOFF
    away_ranked = away_rank is not None and away_rank <= NCAAF_RANKED_CUTOFF
    home_elite  = home_rank is not None and home_rank <= NCAAF_ELITE_RANK
    away_elite  = away_rank is not None and away_rank <= NCAAF_ELITE_RANK

    if home_elite and away_elite:
        return 26.0, f"top-10 matchup (#{home_rank} vs #{away_rank})"

    if (home_elite and away_ranked) or (away_elite and home_ranked):
        return 22.0, f"top-10 vs ranked (#{home_rank} vs #{away_rank})"

    if home_ranked and away_ranked:
        return 19.0, f"ranked matchup (#{home_rank} vs #{away_rank})"

    if home_elite or away_elite:
        top = home_rank if home_elite else away_rank
        return 13.0, f"one top-10 team (#{top})"

    if home_ranked or away_ranked:
        top = home_rank if home_ranked else away_rank
        return 10.0, f"one ranked team (#{top})"

    avg_wpct = (home.win_pct + away.win_pct) / 2
    if avg_wpct >= 0.600:
        return 7.0, "both winning, neither ranked"
    return 4.0, "no meaningful stakes"


def _ncaaf_postseason_stakes(event: RawEvent | None) -> tuple[float, str]:
    """
    Separate the national title bracket from the exhibition bowls.

    Most of the ~40 bowl games are opt-out-riddled exhibitions between 6-6
    teams. Scoring them all as "postseason" would flood every late-December
    list with games nobody planned an evening around.
    """
    note = (event.event_note or "").lower() if event and event.event_note else ""

    if "national championship" in note:
        return 30.0, "national championship"
    if "playoff" in note or "semifinal" in note or "quarterfinal" in note:
        return 29.0, "College Football Playoff"
    if note:
        return 15.0, f"bowl game ({event.event_note})"
    return 15.0, "bowl game"


# ---------------------------------------------------------------------------
# Competitive balance (0–20)
# ---------------------------------------------------------------------------

def score_competitive_balance(home: TeamContext, away: TeamContext) -> float:
    """
    min(team1_quality, team2_quality) × 2.
    One weak team tanks the score regardless of how strong the opponent is.
    """
    q_home = quality_for(home)
    q_away = quality_for(away)
    return round(min(q_home, q_away) * 2, 1)


# ---------------------------------------------------------------------------
# Momentum (0–15)
# ---------------------------------------------------------------------------

def score_momentum(home: TeamContext, away: TeamContext) -> float:
    """
    L10 quality for each team (0–6 pts each) + streak bonus (0–3).
    Max: 15.

    Football has no usable last-ten window — ten games is most of an NFL season
    and nearly all of a college one — so it uses a streak-based model on the
    same 0–15 scale.
    """
    if home.sport in FOOTBALL_SPORTS or away.sport in FOOTBALL_SPORTS:
        return _football_momentum(home, away)

    def _l10_score(ctx: TeamContext) -> float:
        total = ctx.l10_wins + ctx.l10_losses
        if total == 0:
            return 3.0
        pct = ctx.l10_wins / total
        if pct >= 0.80: return 6.0
        if pct >= 0.70: return 5.0
        if pct >= 0.60: return 4.0
        if pct >= 0.40: return 3.0
        if pct >= 0.30: return 2.0
        return 1.0

    base = _l10_score(home) + _l10_score(away)  # 2–12

    # Bonus: any team on a 7+ game win streak
    streak_bonus = 0.0
    for ctx in (home, away):
        if ctx.streak_type == "W" and ctx.streak_n >= 7:
            streak_bonus = 3.0
            break

    return round(min(base + streak_bonus, 15.0), 1)


def _football_momentum(home: TeamContext, away: TeamContext) -> float:
    """
    Streak-based momentum for football (0–15), same scale as the L10 model.

    A three-game win streak in a 17-game season is the equivalent of a long hot
    stretch in baseball. The bonus fires for a 5+ game run, or for an
    undefeated team once the sample is real.
    """
    def _streak_score(ctx: TeamContext) -> float:
        n = ctx.streak_n
        if ctx.streak_type == "W":
            if n >= 5: return 6.0
            if n == 4: return 5.5
            if n == 3: return 5.0
            if n == 2: return 4.0
            if n == 1: return 3.5
            return 3.0          # no streak recorded — neutral
        # Losing streak
        if n >= 4: return 1.0
        if n == 3: return 1.5
        if n == 2: return 2.0
        if n == 1: return 2.5
        return 3.0

    base = _streak_score(home) + _streak_score(away)   # 2–12

    bonus = 0.0
    for ctx in (home, away):
        on_long_run = ctx.streak_type == "W" and ctx.streak_n >= 5
        undefeated  = ctx.losses == 0 and ctx.games_played >= 5
        if on_long_run or undefeated:
            bonus = 3.0
            break

    return round(min(base + bonus, 15.0), 1)


# ---------------------------------------------------------------------------
# Star power (0–15)
# ---------------------------------------------------------------------------

def score_star_power(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    """Returns (score, detail_string)."""
    # College football deliberately has no marquee player list. Rosters turn
    # over every year and keeping ~136 programs current is unmaintainable — in
    # college the *program* is the draw. See DECISIONS.md 2026-08-20.
    if home.sport == "NCAAF":
        return _ncaaf_star_power(home, away)

    home_key = f"{home.sport}:{home.abbr}"
    away_key = f"{away.sport}:{away.abbr}"

    home_players = MARQUEE_PLAYERS.get(home_key, [])
    away_players = MARQUEE_PLAYERS.get(away_key, [])

    home_supers = [p for p in home_players if p["tier"] == "superstar"]
    home_stars  = [p for p in home_players if p["tier"] == "star"]
    away_supers = [p for p in away_players if p["tier"] == "superstar"]
    away_stars  = [p for p in away_players if p["tier"] == "star"]

    has_home_super = bool(home_supers)
    has_away_super = bool(away_supers)
    has_home_star  = bool(home_stars) or has_home_super
    has_away_star  = bool(away_stars) or has_away_super

    if has_home_super and has_away_super:
        score  = 15.0
        detail = f"{home_supers[0]['name']} vs {away_supers[0]['name']}"
    elif has_home_super and has_away_star:
        score  = 12.0
        star_name = away_stars[0]["name"] if away_stars else away_supers[0]["name"]
        detail = f"{home_supers[0]['name']} vs {star_name}"
    elif has_home_star and has_away_super:
        score  = 12.0
        star_name = home_stars[0]["name"] if home_stars else home_supers[0]["name"]
        detail = f"{star_name} vs {away_supers[0]['name']}"
    elif has_home_star and has_away_star:
        score  = 10.0
        h_name = (home_stars or home_supers)[0]["name"]
        a_name = (away_stars or away_supers)[0]["name"]
        detail = f"{h_name} vs {a_name}"
    elif has_home_star or has_away_star:
        score  = 6.0
        top    = (home_stars or home_supers or away_stars or away_supers)[0]["name"]
        detail = f"{top} (one side)"
    else:
        score  = 3.0
        detail = "no marquee players"

    return score, detail


def _ncaaf_star_power(home: TeamContext, away: TeamContext) -> tuple[float, str]:
    """
    Program prestige stands in for individual star power in college football.

    Deliberately independent of poll position: rank already drives stakes and
    competitive balance, and reusing it here would count one signal three times
    and systematically float ranked college games above comparable NFL games.
    Tiers mirror the superstar/star structure of the pro model.
    """
    h_tier = NCAAF_PROGRAM_PRESTIGE.get(f"NCAAF:{home.abbr}")
    a_tier = NCAAF_PROGRAM_PRESTIGE.get(f"NCAAF:{away.abbr}")

    h_blue  = h_tier == "blueblood"
    a_blue  = a_tier == "blueblood"
    h_named = h_tier is not None
    a_named = a_tier is not None

    if h_blue and a_blue:
        return 15.0, f"{home.name} vs {away.name} (blue bloods)"
    if (h_blue and a_named) or (a_blue and h_named):
        return 12.0, f"{home.name} vs {away.name}"
    if h_named and a_named:
        return 10.0, f"{home.name} vs {away.name}"
    if h_named:
        return 6.0, f"{home.name} (one side)"
    if a_named:
        return 6.0, f"{away.name} (one side)"
    return 3.0, "no marquee programs"


# ---------------------------------------------------------------------------
# Narrative flags (0–20)
# ---------------------------------------------------------------------------

def score_narrative_flags(flags: list[str]) -> float:
    """
    Tier 1: elimination_game = 20, no stacking.
    Tier 2: rivalry=8, undefeated_showdown=7, playoff_rematch=6, ace_duel=6,
            division_clash=6, first_place_clash=5, superstar_matchup=4,
            momentum_mismatch=4, conference_clash=4, marquee_starter=3,
            seed_pressure=3. Capped at 12.
    marquee_starter only fires when ace_duel is absent (enforced in enrich.py).
    NBA-only: superstar_matchup, momentum_mismatch, seed_pressure.
    NFL-only: division_clash.  NCAAF-only: conference_clash.
    NFL + NCAAF: undefeated_showdown.
    """
    if "elimination_game" in flags:
        return 20.0

    tier2 = 0.0
    if "rivalry"             in flags: tier2 += 8.0
    if "undefeated_showdown" in flags: tier2 += 7.0
    if "playoff_rematch"     in flags: tier2 += 6.0
    if "ace_duel"            in flags: tier2 += 6.0
    if "division_clash"      in flags: tier2 += 6.0
    if "first_place_clash"   in flags: tier2 += 5.0
    if "superstar_matchup"   in flags: tier2 += 4.0
    if "momentum_mismatch"   in flags: tier2 += 4.0
    if "conference_clash"    in flags: tier2 += 4.0
    if "marquee_starter"     in flags: tier2 += 3.0
    if "seed_pressure"       in flags: tier2 += 3.0

    return min(tier2, 12.0)


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def score_event(se: ScoredEvent) -> ScoredEvent:
    """
    Compute all score components. Mutates se in place and returns it.
    """
    home = se.home_ctx
    away = se.away_ctx

    stakes, stakes_detail        = score_stakes(home, away, se.raw.is_postseason,
                                                se.raw.is_playin, se.raw)
    comp_balance                  = score_competitive_balance(home, away)
    momentum                      = score_momentum(home, away)
    star_power, star_power_detail = score_star_power(home, away)
    flags_score                   = score_narrative_flags(se.flags)

    se.stakes_score              = stakes
    se.competitive_balance_score = comp_balance
    se.momentum_score            = momentum
    se.star_power_score          = star_power
    se.narrative_flags_score     = flags_score
    se.total_score               = round(stakes + comp_balance + momentum + star_power + flags_score, 1)
    se.stakes_detail             = stakes_detail
    se.star_power_detail         = star_power_detail

    return se
