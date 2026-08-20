"""
test_football.py — Offline tests for the multi-sport scoring engine.

No network. Fixtures are hand-built ESPN-shaped payloads, so these verify the
normalizers, the football scoring models, the MLB wild card race logic, and —
importantly — that MLB and NBA scoring is not disturbed by the football work.

These prove the parsing *logic*. They cannot prove that live payloads have the
shape the fixtures assume — that is what validate_sources.py is for, and it
must be run against the real endpoints before enabling a sport in the
scheduled workflow.

Run: python test_football.py
"""

import sys
from datetime import datetime, date, timezone

import enrich
import score
from models import RawEvent, TeamContext, ScoredEvent
import nfl
import ncaaf

_FAILURES: list[str] = []
_PASSES = 0


def check(label: str, actual, expected) -> None:
    global _PASSES
    if actual == expected:
        _PASSES += 1
    else:
        _FAILURES.append(f"{label}\n      expected: {expected!r}\n      actual:   {actual!r}")


def check_true(label: str, cond: bool) -> None:
    check(label, bool(cond), True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def nfl_team(abbr, wins, losses, ties=0, seed=None, conf="AFC", div=None,
             streak=("W", 0)) -> TeamContext:
    gp = wins + losses + ties
    return TeamContext(
        abbr=abbr, name=abbr, sport="NFL",
        wins=wins, losses=losses,
        win_pct=(wins + 0.5 * ties) / gp if gp else 0.0,
        l10_wins=0, l10_losses=0,
        streak_type=streak[0], streak_n=streak[1],
        games_played=gp, conference=conf, conference_rank=seed,
        ties=ties, division=div,
    )


def ncaaf_team(abbr, wins, losses, ap_rank=None, streak=("W", 0)) -> TeamContext:
    gp = wins + losses
    return TeamContext(
        abbr=abbr, name=abbr, sport="NCAAF",
        wins=wins, losses=losses,
        win_pct=wins / gp if gp else 0.0,
        l10_wins=0, l10_losses=0,
        streak_type=streak[0], streak_n=streak[1],
        games_played=gp, ap_rank=ap_rank,
    )


def event(sport, home, away, postseason=False, note=None, conf_game=False) -> RawEvent:
    return RawEvent(
        game_id="1", sport=sport, home_abbr=home, away_abbr=away,
        home_name=home, away_name=away,
        game_time_utc=datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc),
        game_date=date(2026, 11, 1), venue="Stadium",
        is_postseason=postseason, event_note=note,
        is_conference_game=conf_game,
    )


def event_wk(sport, home, away, week, **kw) -> RawEvent:
    """Event fixture carrying a week number (football opener detection)."""
    base = event(sport, home, away, **kw)
    return RawEvent(**{**base.__dict__, "week": week})


def scored(ev, home_ctx, away_ctx) -> ScoredEvent:
    se = enrich.build_scored_event(ev, home_ctx, away_ctx, date(2026, 11, 1))
    return score.score_event(se)


# ---------------------------------------------------------------------------
# Regression guard: MLB / NBA scoring must be byte-identical
# ---------------------------------------------------------------------------

def test_mlb_nba_unchanged():
    mlb_home = TeamContext(
        abbr="LAD", name="Dodgers", sport="MLB", wins=95, losses=55, win_pct=0.633,
        l10_wins=7, l10_losses=3, streak_type="W", streak_n=3, games_played=150,
        division_rank=1, games_back=None, wild_card_rank=None, wc_games_back=None,
    )
    mlb_away = TeamContext(
        abbr="SD", name="Padres", sport="MLB", wins=88, losses=62, win_pct=0.587,
        l10_wins=6, l10_losses=4, streak_type="W", streak_n=1, games_played=150,
        division_rank=2, games_back=7.0, wild_card_rank=1, wc_games_back=None,
    )
    se = scored(event("MLB", "LAD", "SD"), mlb_home, mlb_away)

    # LAD/SD is a configured rivalry; late season (150/162). SD holds the #1
    # wild card, so both teams are in the race → 22.0.
    check("MLB stakes",   se.stakes_score, 22.0)
    check("MLB balance",  se.competitive_balance_score, 16.0)
    check("MLB momentum", se.momentum_score, 9.0)
    check("MLB star",     se.star_power_score, 15.0)
    check("MLB narrative", se.narrative_flags_score, 8.0)
    check_true("MLB rivalry flag", "rivalry" in se.flags)
    # L10 model still used for baseball
    check("MLB uses L10 momentum", score.score_momentum(mlb_home, mlb_away), 9.0)

    nba_home = TeamContext(
        abbr="BOS", name="Celtics", sport="NBA", wins=50, losses=20, win_pct=0.714,
        l10_wins=8, l10_losses=2, streak_type="W", streak_n=4, games_played=70,
        conference="East", conference_rank=1,
    )
    nba_away = TeamContext(
        abbr="NYK", name="Knicks", sport="NBA", wins=44, losses=26, win_pct=0.629,
        l10_wins=5, l10_losses=5, streak_type="L", streak_n=1, games_played=70,
        conference="East", conference_rank=2,
    )
    se2 = scored(event("NBA", "BOS", "NYK"), nba_home, nba_away)
    check("NBA stakes",  se2.stakes_score, 22.0)
    check("NBA balance", se2.competitive_balance_score, 18.0)
    check("NBA momentum", se2.momentum_score, 9.0)
    check_true("NBA rivalry flag", "rivalry" in se2.flags)
    # first_place_clash (both top 2) should also be present
    check_true("NBA first_place_clash", "first_place_clash" in se2.flags)


def test_mlb_wild_card_race():
    """
    A team holding a wild card spot is in the race, even when it is far back
    in its own division.

    wc_games_back=None is ambiguous — it means both "holds a wild card spot"
    and "the API sent no wild card data" — so race membership is read from
    wild_card_rank instead.
    """
    def team(abbr, w, l, gb, wc_rank, wc_gb):
        return TeamContext(
            abbr=abbr, name=abbr, sport="MLB", wins=w, losses=l, win_pct=w / (w + l),
            l10_wins=5, l10_losses=5, streak_type="W", streak_n=1, games_played=w + l,
            games_back=gb, wild_card_rank=wc_rank, wc_games_back=wc_gb,
        )

    # Holds the top wild card while 7 games back in the division
    wc_leader = team("SD", 88, 62, 7.0, 1, None)
    check_true("wild card holder is in the race", score._in_mlb_race(wc_leader))

    # Third and last wild card spot
    check_true("last wild card spot counts",
               score._in_mlb_race(team("NYM", 84, 66, 9.0, 3, None)))

    # Just outside the cutoff but within striking distance
    check_true("close chaser is in the race",
               score._in_mlb_race(team("SF", 80, 70, 12.0, 4, 3.0)))

    # Out of it entirely, and no wild card data at all
    check_true("far-back team with no WC data is not in the race",
               not score._in_mlb_race(team("COL", 50, 100, 30.0, None, None)))

    # Division leader is always in
    check_true("division leader is in the race",
               score._in_mlb_race(team("LAD", 95, 55, None, None, None)))

    # A wild card rank beyond the berths is not, by itself, enough
    check_true("rank 8 alone does not qualify",
               not score._in_mlb_race(team("WSH", 68, 82, 20.0, 8, 14.0)))


def test_mlb_rank_parsing():
    """A missing rank must be None, never 0 — 0 would read as first place."""
    import mlb
    check("missing rank → None", mlb._parse_rank(None), None)
    check("dash rank → None",    mlb._parse_rank("-"), None)
    check("zero rank → None",    mlb._parse_rank(0), None)
    check("numeric string",      mlb._parse_rank("3"), 3)
    check("int rank",            mlb._parse_rank(1), 1)


# ---------------------------------------------------------------------------
# NFL scoring
# ---------------------------------------------------------------------------

def test_nfl_stakes():
    # Two playoff teams, late season
    home = nfl_team("KC", 12, 3, seed=1, conf="AFC", div="AFC West", streak=("W", 4))
    away = nfl_team("BUF", 11, 4, seed=2, conf="AFC", div="AFC East", streak=("W", 2))
    s, detail = score.score_stakes(home, away, is_postseason=False)
    # 15 of 17 games played → late phase → x1.00; both >= .700 → elite tier
    check("NFL elite stakes", s, 24.0)
    check_true("NFL stakes detail", "elite" in detail)

    # Playoff game — every one is single elimination
    s2, d2 = score.score_stakes(home, away, is_postseason=True)
    check("NFL postseason stakes", s2, 30.0)
    check("NFL postseason detail", d2, "playoff elimination game")

    # Two bad teams
    bad_h = nfl_team("CAR", 2, 13, seed=15, conf="NFC", div="NFC South")
    bad_a = nfl_team("NYG", 3, 12, seed=14, conf="NFC", div="NFC East")
    s3, _ = score.score_stakes(bad_h, bad_a, is_postseason=False)
    check("NFL no-stakes game", s3, 5.0)


def test_nfl_season_phase():
    # Week 3 of 17 → early phase. Seeds are published, so the normal standings
    # model applies; only the multiplier is in question here.
    home = nfl_team("KC", 2, 0, seed=1, conf="AFC", div="AFC West")
    away = nfl_team("BUF", 2, 0, seed=2, conf="AFC", div="AFC East")
    s, detail = score.score_stakes(home, away, is_postseason=False)
    # 0.90, not the 0.60 used for baseball: a 17-game season has no games that
    # are 40% less consequential than the rest.
    check("NFL early-season multiplier applied", s, round(24.0 * 0.90, 1))
    check_true("NFL early detail shows multiplier", "×0.90" in detail)


def test_nfl_ties():
    """A tie must count as half a win, and games_played must include it."""
    t = nfl_team("PIT", 8, 7, ties=1, seed=7, conf="AFC", div="AFC North")
    check("NFL games played includes tie", t.games_played, 16)
    check("NFL tie counts half", round(t.win_pct, 4), round(8.5 / 16, 4))


def test_nfl_momentum_uses_streak_not_l10():
    """Football must not read the placeholder 0-0 L10 as a ten-game losing run."""
    hot  = nfl_team("BAL", 10, 2, seed=1, conf="AFC", div="AFC North", streak=("W", 6))
    cold = nfl_team("CLE", 4, 8, seed=13, conf="AFC", div="AFC North", streak=("L", 3))

    m = score.score_momentum(hot, cold)
    # hot 6.0 + cold 1.5 = 7.5, +3.0 bonus for the 5+ win run
    check("NFL momentum from streak", m, 10.5)

    # Sanity: the L10 model would have produced the minimum here.
    check("NFL momentum beats L10 placeholder floor", m > 6.0, True)


def test_nfl_flags():
    # Divisional rivalry, both leading a division
    home = nfl_team("BAL", 11, 3, seed=2, conf="AFC", div="AFC North", streak=("W", 3))
    away = nfl_team("PIT", 10, 4, seed=3, conf="AFC", div="AFC North", streak=("W", 1))
    se = scored(event("NFL", "BAL", "PIT"), home, away)

    check_true("NFL rivalry flag",        "rivalry" in se.flags)
    check_true("NFL division_clash flag", "division_clash" in se.flags)
    check_true("NFL first_place_clash",   "first_place_clash" in se.flags)
    # rivalry 8 + division 6 + first place 5 = 19, capped at 12
    check("NFL tier-2 cap holds", se.narrative_flags_score, 12.0)

    # Postseason → tier 1 only, no stacking
    se_post = scored(event("NFL", "BAL", "PIT", postseason=True), home, away)
    check("NFL postseason narrative", se_post.narrative_flags_score, 20.0)
    check("NFL postseason flags exclusive", se_post.flags, ["elimination_game"])


def test_nfl_undefeated_showdown():
    home = nfl_team("DET", 6, 0, seed=1, conf="NFC", div="NFC North", streak=("W", 6))
    away = nfl_team("SF",  6, 0, seed=2, conf="NFC", div="NFC West",  streak=("W", 6))
    se = scored(event("NFL", "DET", "SF"), home, away)
    check_true("NFL undefeated_showdown", "undefeated_showdown" in se.flags)

    # Too early to count — 3 games is not a sample
    h2 = nfl_team("DET", 3, 0, seed=1, conf="NFC", div="NFC North", streak=("W", 3))
    a2 = nfl_team("SF",  3, 0, seed=2, conf="NFC", div="NFC West",  streak=("W", 3))
    se2 = scored(event("NFL", "DET", "SF"), h2, a2)
    check_true("NFL undefeated needs sample", "undefeated_showdown" not in se2.flags)


def test_nfl_quality_curve():
    """NFL thresholds must be stretched relative to the MLB/NBA curve."""
    # .647 (11-6) is a good NFL team but not a 10 on the MLB curve's terms
    check("NFL 11-6 quality", score.nfl_team_quality(11 / 17), 7.0)
    check("NFL 13-4 quality", score.nfl_team_quality(13 / 17), 10.0)
    # MLB curve unchanged
    check("MLB .650 still 10", score.team_quality(0.650), 10.0)


# ---------------------------------------------------------------------------
# NCAAF scoring
# ---------------------------------------------------------------------------

def test_ncaaf_poll_drives_quality():
    top = ncaaf_team("UGA", 8, 0, ap_rank=1)
    mid = ncaaf_team("MISS", 6, 2, ap_rank=18)
    unranked_good = ncaaf_team("TOL", 8, 0, ap_rank=None)

    check("NCAAF #1 quality", score.ncaaf_team_quality(top), 10.0)
    check("NCAAF #18 quality", score.ncaaf_team_quality(mid), 7.0)
    # An undefeated unranked team must not outrank a ranked one
    check("NCAAF unranked capped", score.ncaaf_team_quality(unranked_good), 5.0)
    check_true("NCAAF ranked beats unranked",
               score.ncaaf_team_quality(mid) > score.ncaaf_team_quality(unranked_good))


def test_ncaaf_stakes():
    a = ncaaf_team("UGA", 8, 0, ap_rank=1)
    b = ncaaf_team("ALA", 7, 1, ap_rank=6)
    s, detail = score.score_stakes(a, b, is_postseason=False)
    # 8 of 12 games → mid phase (0.667) → ×0.95 on the football curve
    check("NCAAF top-10 stakes", s, round(26.0 * 0.95, 1))
    check_true("NCAAF stakes names ranks", "#1" in detail and "#6" in detail)

    unranked_a = ncaaf_team("VAN", 3, 5)
    unranked_b = ncaaf_team("PUR", 2, 6)
    s2, _ = score.score_stakes(unranked_a, unranked_b, is_postseason=False)
    check("NCAAF unranked stakes", s2, round(4.0 * 0.95, 1))


def test_ncaaf_bowls_vs_playoff():
    """The exhibition bowls must not score like a national semifinal."""
    a = ncaaf_team("UGA", 12, 1, ap_rank=2)
    b = ncaaf_team("TEX", 11, 2, ap_rank=5)

    cfp = event("NCAAF", "UGA", "TEX", postseason=True,
                note="College Football Playoff Semifinal")
    s_cfp, d_cfp = score.score_stakes(a, b, True, False, cfp)
    check("NCAAF CFP stakes", s_cfp, 29.0)
    check("NCAAF CFP detail", d_cfp, "College Football Playoff")

    title = event("NCAAF", "UGA", "TEX", postseason=True,
                  note="CFP National Championship")
    s_title, _ = score.score_stakes(a, b, True, False, title)
    check("NCAAF title game stakes", s_title, 30.0)

    mid_h = ncaaf_team("IOWA", 6, 6)
    mid_a = ncaaf_team("MINN", 6, 6)
    bowl = event("NCAAF", "IOWA", "MINN", postseason=True, note="Music City Bowl")
    s_bowl, _ = score.score_stakes(mid_h, mid_a, True, False, bowl)
    check("NCAAF exhibition bowl stakes", s_bowl, 15.0)
    check_true("NCAAF bowl scores far below CFP", s_bowl < s_cfp - 10)


def test_ncaaf_flags():
    a = ncaaf_team("OSU", 9, 0, ap_rank=2, streak=("W", 9))
    b = ncaaf_team("MICH", 8, 1, ap_rank=5, streak=("W", 3))
    se = scored(event("NCAAF", "OSU", "MICH", conf_game=True), a, b)

    check_true("NCAAF rivalry flag", "rivalry" in se.flags)
    check_true("NCAAF conference_clash", "conference_clash" in se.flags)
    check_true("NCAAF no first_place_clash", "first_place_clash" not in se.flags)
    check("NCAAF tier-2 cap", se.narrative_flags_score, 12.0)

    # CFP game is elimination; a regular bowl is not
    cfp = event("NCAAF", "OSU", "MICH", postseason=True, note="CFP Quarterfinal")
    check_true("NCAAF CFP elimination flag",
               "elimination_game" in enrich.detect_flags(cfp, a, b))
    bowl = event("NCAAF", "OSU", "MICH", postseason=True, note="Gator Bowl")
    check_true("NCAAF plain bowl not elimination",
               "elimination_game" not in enrich.detect_flags(bowl, a, b))


def test_ncaaf_star_power_is_prestige_not_rank():
    """
    Star power must come from program prestige, independent of poll rank —
    otherwise rank drives stakes, balance AND star power, and every ranked
    college game floats above comparable NFL games.
    """
    uga = ncaaf_team("UGA", 8, 0, ap_rank=1)
    ala = ncaaf_team("ALA", 7, 1, ap_rank=4)
    s, detail = score.score_star_power(uga, ala)
    check("NCAAF blue blood pairing", s, 15.0)
    check_true("NCAAF star detail names programs", "blue bloods" in detail)

    # Same two programs, both unranked — prestige must not move.
    uga_bad = ncaaf_team("UGA", 4, 4, ap_rank=None)
    ala_bad = ncaaf_team("ALA", 4, 4, ap_rank=None)
    s_bad, _ = score.score_star_power(uga_bad, ala_bad)
    check("NCAAF prestige independent of rank", s_bad, 15.0)

    # A top-5 team with no brand must not score as a blue blood.
    tol = ncaaf_team("TOL", 9, 0, ap_rank=3)
    ohio = ncaaf_team("OHIO", 8, 1, ap_rank=None)
    s2, _ = score.score_star_power(tol, ohio)
    check("NCAAF unbranded top-5 gets no star power", s2, 3.0)

    # Mixed: blue blood vs major
    ore = ncaaf_team("ORE", 7, 1, ap_rank=8)
    s3, _ = score.score_star_power(uga, ore)
    check("NCAAF blueblood vs major", s3, 12.0)


def test_ncaaf_rank_not_triple_counted():
    """A ranked-but-unbranded matchup must not out-score an NFL playoff race."""
    # Two top-10 but low-prestige programs
    a = ncaaf_team("TOL", 9, 0, ap_rank=4, streak=("W", 9))
    b = ncaaf_team("BOIS", 9, 0, ap_rank=8, streak=("W", 9))
    se_college = scored(event("NCAAF", "TOL", "BOIS"), a, b)

    # Two NFL playoff teams in a division rivalry
    h = nfl_team("BAL", 11, 3, seed=2, conf="AFC", div="AFC North", streak=("W", 3))
    aw = nfl_team("PIT", 10, 4, seed=3, conf="AFC", div="AFC North", streak=("W", 1))
    se_nfl = scored(event("NFL", "BAL", "PIT"), h, aw)

    check_true(
        "unbranded college top-10 does not outrank NFL playoff rivalry",
        se_nfl.total_score > se_college.total_score,
    )


# ---------------------------------------------------------------------------
# Season openers — absence of record data must not score as bad data
# ---------------------------------------------------------------------------

def test_has_record_signal():
    check_true("NFL 0 games: no signal",  not score.has_record_signal(nfl_team("KC", 0, 0)))
    check_true("NFL 3 games: no signal",  not score.has_record_signal(nfl_team("KC", 2, 1)))
    check_true("NFL 4 games: signal",     score.has_record_signal(nfl_team("KC", 3, 1)))

    mlb_early = TeamContext(abbr="LAD", name="LAD", sport="MLB", wins=9, losses=3,
                            win_pct=0.75, l10_wins=7, l10_losses=3, streak_type="W",
                            streak_n=2, games_played=12)
    check_true("MLB 12 games: no signal", not score.has_record_signal(mlb_early))


def test_neutral_quality_before_sample():
    """A 0-0 team must read as unknown, not as a .000 team."""
    fresh = nfl_team("KC", 0, 0)
    check("0-0 NFL quality is neutral", score.quality_for(fresh), 6.0)
    check("0-0 balance is neutral", score.score_competitive_balance(fresh, nfl_team("BUF", 0, 0)), 12.0)

    # Once the sample is real, the record curve takes over again
    established = nfl_team("KC", 13, 1)
    check("13-1 quality is record-based", score.quality_for(established), 10.0)
    bad = nfl_team("CAR", 1, 13)
    check("1-13 quality is record-based", score.quality_for(bad), 2.0)


def test_neutral_stakes_not_discounted():
    """
    The phase multiplier discounts a standings claim. With no standings claim to
    discount, applying it would charge the same uncertainty twice — which is how
    an NFL opener reached 3.0/30.
    """
    h, a = nfl_team("KC", 0, 0), nfl_team("BUF", 0, 0)
    s, detail = score.score_stakes(h, a, is_postseason=False)
    check("neutral stakes use the NFL baseline", s, 15.0)
    check("neutral stakes detail", detail, "standings not yet meaningful")
    check_true("no multiplier applied to neutral stakes", "×" not in detail)


def test_nfl_opener_is_competitive_but_differentiated():
    """
    The fix must lift a marquee opener into contention without lifting every
    opener — otherwise it trades one calibration bug for another.
    """
    marquee = scored(
        event_wk("NFL", "KC", "BUF", week=1),
        nfl_team("KC", 0, 0, div="AFC West"), nfl_team("BUF", 0, 0, div="AFC East"))
    nothing = scored(
        event_wk("NFL", "CAR", "TEN", week=1),
        nfl_team("CAR", 0, 0, div="NFC South"), nfl_team("TEN", 0, 0, div="AFC South"))

    check_true(f"marquee opener is competitive (got {marquee.total_score})",
               marquee.total_score >= 55.0)
    check_true(f"nothing opener stays low (got {nothing.total_score})",
               nothing.total_score <= 45.0)
    check_true("openers are still differentiated",
               marquee.total_score - nothing.total_score >= 15.0)

    # Ordering against the same matchup with real standings must be preserved:
    # Week 1 is compelling, Week 12 with both teams contending is more so.
    late = scored(
        event_wk("NFL", "KC", "BUF", week=12),
        nfl_team("KC", 8, 3, seed=1, div="AFC West", streak=("W", 3)),
        nfl_team("BUF", 8, 3, seed=2, div="AFC East", streak=("W", 2)))
    check_true("Week 12 still outranks Week 1", late.total_score > marquee.total_score)


def test_season_opener_flag():
    h, a = nfl_team("KC", 0, 0), nfl_team("BUF", 0, 0)
    check_true("week 1 flags opener",
               "season_opener" in enrich.detect_flags(event_wk("NFL", "KC", "BUF", week=1), h, a))
    check_true("week 0 flags opener (college kickoff weekend)",
               "season_opener" in enrich.detect_flags(event_wk("NCAAF", "OSU", "TEX", week=0),
                                                     ncaaf_team("OSU", 0, 0, ap_rank=2),
                                                     ncaaf_team("TEX", 0, 0, ap_rank=4)))
    check_true("week 2 does not flag opener",
               "season_opener" not in enrich.detect_flags(event_wk("NFL", "KC", "BUF", week=2), h, a))
    check_true("missing week does not flag opener",
               "season_opener" not in enrich.detect_flags(event("NFL", "KC", "BUF"), h, a))
    check_true("MLB never flags opener",
               "season_opener" not in enrich.detect_flags(
                   event_wk("MLB", "LAD", "SD", week=1),
                   TeamContext(abbr="LAD", name="LAD", sport="MLB", wins=0, losses=0, win_pct=0.0,
                               l10_wins=0, l10_losses=0, streak_type="W", streak_n=0, games_played=0),
                   TeamContext(abbr="SD", name="SD", sport="MLB", wins=0, losses=0, win_pct=0.0,
                               l10_wins=0, l10_losses=0, streak_type="W", streak_n=0, games_played=0)))


def test_neutral_stakes_scope():
    """Neutral stakes apply only when there is genuinely no standings signal."""
    # A published playoff seed is real information even at 0-0
    seeded = nfl_team("KC", 0, 0, seed=1)
    check_true("a published seed suppresses the neutral path",
               not score._needs_neutral_stakes(seeded, nfl_team("BUF", 0, 0)))

    # NCAAF is exempt — the preseason poll works from Week 1
    check_true("NCAAF never uses neutral stakes",
               not score._needs_neutral_stakes(ncaaf_team("OSU", 0, 0, ap_rank=2),
                                               ncaaf_team("TEX", 0, 0, ap_rank=4)))
    s, detail = score.score_stakes(ncaaf_team("OSU", 0, 0, ap_rank=2),
                                   ncaaf_team("TEX", 0, 0, ap_rank=4), is_postseason=False)
    check_true("NCAAF opener still scores off the poll", "top-10" in detail)

    # MLB has standings from opening day
    mlb_open = TeamContext(abbr="LAD", name="LAD", sport="MLB", wins=0, losses=0, win_pct=0.0,
                           l10_wins=0, l10_losses=0, streak_type="W", streak_n=0,
                           games_played=0, games_back=0.0)
    check_true("MLB with standings does not use neutral stakes",
               not score._needs_neutral_stakes(mlb_open, mlb_open))


def test_phase_multiplier_is_sport_aware():
    check("NFL early is mild",   score.season_phase_multiplier(2, 17, "NFL"), 0.90)
    check("NCAAF early is mild", score.season_phase_multiplier(1, 12, "NCAAF"), 0.90)
    # MLB and NBA must be untouched — published output depends on them
    check("MLB early unchanged", score.season_phase_multiplier(10, 162, "MLB"), 0.60)
    check("MLB mid unchanged",   score.season_phase_multiplier(80, 162, "MLB"), 0.85)
    check("MLB late unchanged",  score.season_phase_multiplier(150, 162, "MLB"), 1.00)
    check("NBA early unchanged", score.season_phase_multiplier(5, 82, "NBA"), 0.60)
    check("unknown sport falls back", score.season_phase_multiplier(10, 162, None), 0.60)


def test_explain_hides_empty_record():
    """A 0-0 record must not reach the LLM as '0-0 (0.000)'."""
    import explain
    fresh = nfl_team("KC", 0, 0)
    check("0-0 renders as unplayed", explain._record(fresh), "no games played yet")
    played = nfl_team("KC", 3, 1)
    check_true("real record still renders", "3-1" in explain._record(played))


# ---------------------------------------------------------------------------
# Fetcher normalizers (ESPN-shaped fixtures, no network)
# ---------------------------------------------------------------------------

def _espn_nfl_event(season_type=2, home="KC", away="BUF", tbd=False):
    return {
        "id": "401",
        "date": "2026-11-01T18:00Z",
        "name": f"{away} at {home}",
        "season": {"type": season_type},
        "week": {"number": 9},
        "competitions": [{
            "neutralSite": False,
            "venue": {"fullName": "Arrowhead Stadium"},
            "notes": [{"headline": "AFC Championship"}] if season_type == 3 else [],
            "competitors": [
                {"homeAway": "home", "team": {"abbreviation": "TBD" if tbd else home,
                                              "displayName": home}},
                {"homeAway": "away", "team": {"abbreviation": away, "displayName": away}},
            ],
        }],
    }


def test_nfl_normalizer():
    ev = nfl._normalize_event(_espn_nfl_event(season_type=2))
    check_true("NFL regular season parsed", ev is not None)
    check("NFL sport tag", ev.sport, "NFL")
    check("NFL week parsed", ev.week, 9)
    check("NFL not postseason", ev.is_postseason, False)
    check("NFL venue", ev.venue, "Arrowhead Stadium")

    post = nfl._normalize_event(_espn_nfl_event(season_type=3))
    check("NFL postseason parsed", post.is_postseason, True)
    check("NFL round note", post.event_note, "AFC Championship")

    # Preseason and Pro Bowl must be dropped entirely
    check("NFL preseason dropped", nfl._normalize_event(_espn_nfl_event(season_type=1)), None)
    check("NFL pro bowl dropped",  nfl._normalize_event(_espn_nfl_event(season_type=4)), None)
    # TBD playoff placeholder dropped
    check("NFL TBD dropped", nfl._normalize_event(_espn_nfl_event(season_type=3, tbd=True)), None)


def test_nfl_stat_fallback():
    """A stat carried only as displayValue must still parse, not read as 0."""
    stats = {
        "wins":        {"displayValue": "11"},
        "losses":      {"value": 6},
        "playoffSeed": {"displayValue": "3"},
    }
    check("value preferred",        nfl._stat_val(stats, "losses", 0), 6)
    check("displayValue fallback",  nfl._stat_val(stats, "wins", 0), 11)
    check("seed via displayValue",  nfl._stat_val(stats, "playoffSeed", None), 3)
    check("missing stat default",   nfl._stat_val(stats, "ties", 0), 0)
    check("unparseable default",    nfl._stat_val({"x": {"displayValue": "-"}}, "x", 0), 0)

    # Full context built from a displayValue-only payload
    entry = {
        "team": {"abbreviation": "DET", "displayName": "Detroit Lions"},
        "stats": [
            {"name": "wins",        "displayValue": "12"},
            {"name": "losses",      "displayValue": "4"},
            {"name": "ties",        "displayValue": "1"},
            {"name": "playoffSeed", "displayValue": "1"},
            {"name": "streak",      "displayValue": "W5"},
        ],
    }
    ctx = nfl._entry_to_context(entry, "NFC", "NFC North")
    check("displayValue-only record", (ctx.wins, ctx.losses, ctx.ties), (12, 4, 1))
    check("displayValue-only gp", ctx.games_played, 17)
    check("displayValue-only seed", ctx.conference_rank, 1)


def test_ncaaf_conference_id_is_str():
    comp = {
        "team": {"abbreviation": "UGA", "displayName": "Georgia", "conferenceId": 8},
        "curatedRank": {"current": 1},
        "records": [{"type": "total", "summary": "10-0"}],
    }
    ctx = ncaaf._competitor_to_context(comp, {})
    check("conferenceId stored as str", ctx.division, "8")

    comp2 = dict(comp, team={"abbreviation": "UGA", "displayName": "Georgia"})
    ctx2 = ncaaf._competitor_to_context(comp2, {})
    check("missing conferenceId → None", ctx2.division, None)


def test_nfl_abbr_normalization():
    check("WAS → WSH", nfl._norm_abbr("WAS"), "WSH")
    check("LA → LAR",  nfl._norm_abbr("LA"),  "LAR")
    check("JAC → JAX", nfl._norm_abbr("JAC"), "JAX")
    check("KC unchanged", nfl._norm_abbr("KC"), "KC")


def test_nfl_standings_walker():
    """ESPN nests NFL standings conference → division → entries."""
    payload = {
        "children": [{
            "name": "American Football Conference",
            "children": [{
                "name": "AFC West",
                "standings": {"entries": [{
                    "team": {"abbreviation": "KC", "displayName": "Kansas City Chiefs"},
                    "stats": [
                        {"name": "wins", "value": 12},
                        {"name": "losses", "value": 4},
                        {"name": "ties", "value": 1},
                        {"name": "playoffSeed", "value": 1},
                        {"name": "streak", "displayValue": "W4"},
                    ],
                }]},
            }],
        }],
    }
    found = list(nfl._walk_standings(payload, None, None))
    check("walker found one entry", len(found), 1)
    conf, div, entry = found[0]
    check("walker conference", conf, "AFC")
    check("walker division", div, "AFC West")

    ctx = nfl._entry_to_context(entry, conf, div)
    check("standings abbr", ctx.abbr, "KC")
    check("standings ties", ctx.ties, 1)
    check("standings gp", ctx.games_played, 17)
    check("standings seed", ctx.conference_rank, 1)
    check("standings streak", (ctx.streak_type, ctx.streak_n), ("W", 4))
    check("standings l10 blank", (ctx.l10_wins, ctx.l10_losses), (0, 0))


def test_nfl_standings_flat_shape():
    """Must also survive the flatter NBA-style nesting if ESPN changes shape."""
    payload = {
        "children": [{
            "name": "National Football Conference",
            "standings": {"entries": [{
                "team": {"abbreviation": "SF", "displayName": "San Francisco 49ers"},
                "stats": [
                    {"name": "wins", "value": 10},
                    {"name": "losses", "value": 7},
                    {"name": "playoffSeed", "value": 5},
                    {"name": "streak", "displayValue": "L2"},
                ],
            }]},
        }],
    }
    found = list(nfl._walk_standings(payload, None, None))
    check("flat walker found entry", len(found), 1)
    conf, div, entry = found[0]
    check("flat walker conference", conf, "NFC")
    check("flat walker division", div, None)
    ctx = nfl._entry_to_context(entry, conf, div)
    check("flat streak parsed", (ctx.streak_type, ctx.streak_n), ("L", 2))


def _espn_ncaaf_event(home_rank=3, away_rank=7, conf_game=True):
    def competitor(side, abbr, rank, record):
        return {
            "homeAway": side,
            "team": {"abbreviation": abbr, "displayName": abbr, "shortDisplayName": abbr},
            "curatedRank": {"current": rank},
            "records": [{"type": "total", "summary": record}],
        }
    return {
        "id": "501",
        "date": "2026-11-28T17:00Z",
        "season": {"type": 2},
        "week": {"number": 13},
        "competitions": [{
            "neutralSite": False,
            "conferenceCompetition": conf_game,
            "venue": {"fullName": "Ohio Stadium"},
            "notes": [],
            "competitors": [
                competitor("home", "OSU", home_rank, "10-1"),
                competitor("away", "MICH", away_rank, "9-2"),
            ],
        }],
    }


def test_ncaaf_normalizer():
    parsed = ncaaf._normalize_event(_espn_ncaaf_event(), ap_ranks={})
    check_true("NCAAF event parsed", parsed is not None)
    raw, home_ctx, away_ctx = parsed

    check("NCAAF sport tag", raw.sport, "NCAAF")
    check("NCAAF conference game", raw.is_conference_game, True)
    check("NCAAF home record", (home_ctx.wins, home_ctx.losses), (10, 1))
    check("NCAAF curated rank used", home_ctx.ap_rank, 3)
    check("NCAAF away rank", away_ctx.ap_rank, 7)

    # AP poll overrides the per-game curated rank
    parsed2 = ncaaf._normalize_event(_espn_ncaaf_event(), ap_ranks={"OSU": 1})
    check("NCAAF AP poll wins", parsed2[1].ap_rank, 1)

    # 99 means unranked, not rank 99
    parsed3 = ncaaf._normalize_event(_espn_ncaaf_event(home_rank=99), ap_ranks={})
    check("NCAAF unranked sentinel", parsed3[1].ap_rank, None)


def test_ncaaf_undefeated_streak_inference():
    """The one inference in ncaaf.py: undefeated → win streak of that length."""
    comp = {
        "team": {"abbreviation": "IU", "displayName": "Indiana"},
        "curatedRank": {"current": 8},
        "records": [{"type": "total", "summary": "9-0"}],
    }
    ctx = ncaaf._competitor_to_context(comp, {})
    check("undefeated infers streak", (ctx.streak_type, ctx.streak_n), ("W", 9))

    comp2 = dict(comp, records=[{"type": "total", "summary": "8-1"}])
    ctx2 = ncaaf._competitor_to_context(comp2, {})
    check("one loss → no inferred streak", ctx2.streak_n, 0)


def test_ncaaf_poll_preference():
    polls = [
        {"name": "AP Top 25"},
        {"name": "College Football Playoff Rankings"},
        {"name": "Coaches Poll"},
    ]
    check("CFP poll preferred", ncaaf._pick_poll(polls)["name"],
          "College Football Playoff Rankings")
    check("AP used when no CFP", ncaaf._pick_poll([{"name": "AP Top 25"}])["name"],
          "AP Top 25")
    check("empty poll list", ncaaf._pick_poll([]), None)


def test_ncaaf_record_parsing():
    check("total record preferred", ncaaf._parse_record({
        "records": [
            {"type": "home", "summary": "5-0"},
            {"type": "total", "summary": "9-2"},
        ]}), (9, 2))
    check("malformed record", ncaaf._parse_record({"records": [{"summary": "??"}]}), (0, 0))
    check("missing record", ncaaf._parse_record({}), (0, 0))


# ---------------------------------------------------------------------------
# run.py sport selection
# ---------------------------------------------------------------------------

def test_parse_sports():
    import run
    check("default sports", run.parse_sports(None), ["MLB", "NBA", "NFL"])
    check("all sports", run.parse_sports("all"), ["MLB", "NBA", "NFL", "NCAAF"])
    check("explicit list", run.parse_sports("nfl,mlb"), ["MLB", "NFL"])
    check("canonical order", run.parse_sports("ncaaf,nba"), ["NBA", "NCAAF"])

    try:
        run.parse_sports("nhl")
    except SystemExit:
        check("unknown sport rejected", True, True)
    else:
        check("unknown sport rejected", False, True)


# ---------------------------------------------------------------------------

def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
        except Exception as e:
            _FAILURES.append(f"{t.__name__} raised {type(e).__name__}: {e}")

    print()
    if _FAILURES:
        print(f"  {len(_FAILURES)} FAILED, {_PASSES} passed\n")
        for f in _FAILURES:
            print(f"  ✗ {f}")
        print()
        return 1

    print(f"  All {_PASSES} checks passed across {len(tests)} tests.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
