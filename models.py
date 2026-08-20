"""
models.py — Frozen dataclasses for Must Watch This Week.

Data shapes only — no logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass(frozen=True)
class TeamContext:
    """Enriched team data used for scoring."""
    abbr: str               # Team abbreviation (as returned by API)
    name: str               # Display name
    sport: str              # "MLB", "NBA", "NFL", or "NCAAF"
    wins: int
    losses: int
    win_pct: float
    l10_wins: int
    l10_losses: int
    streak_type: str        # "W" or "L"
    streak_n: int
    games_played: int       # For season-phase multiplier

    # MLB-specific (None for other sports)
    division_rank: int | None   = None
    games_back: float | None    = None      # From division leader; None = first place
    wild_card_rank: int | None  = None
    wc_games_back: float | None = None      # From last wild card spot; None = in WC

    # NBA / NFL — conference standing
    # NBA: conference is "East"/"West", rank is 1–15 (playoffSeed).
    # NFL: conference is "AFC"/"NFC", rank is the 1–16 playoff seed.
    conference: str | None      = None
    conference_rank: int | None = None      # 1 = best in conference

    # NFL / NCAAF — ties are possible in football
    ties: int = 0

    # NFL: division name, e.g. "AFC East". NCAAF: conference name, e.g. "SEC".
    division: str | None = None

    # NCAAF-specific — AP poll rank (1–25); None = unranked.
    # Poll position, not win pct, is the meaningful quality signal in college
    # football, where schedules are wildly uneven and records are not comparable.
    ap_rank: int | None = None


@dataclass(frozen=True)
class RawEvent:
    """Normalized game event before scoring."""
    game_id: str
    sport: str              # "MLB", "NBA", "NFL", or "NCAAF"
    home_abbr: str
    away_abbr: str
    home_name: str
    away_name: str
    game_time_utc: datetime
    game_date: date         # Local date in ET
    venue: str
    is_postseason: bool = False   # playoffs OR play-in
    is_playin: bool     = False   # explicit NBA play-in (ESPN season.type == 5)

    # MLB probable starters (name only; populated when available from schedule API)
    home_probable_pitcher: str | None = None
    away_probable_pitcher: str | None = None

    # NFL / NCAAF
    week: int | None         = None   # Week number within the season
    neutral_site: bool       = False  # Bowl games, Week 0 kickoff games, etc.
    is_conference_game: bool = False  # NCAAF conference matchup

    # Short event label from the source, e.g. "College Football Playoff
    # Semifinal" or "AFC Championship". Display/context only — never scored.
    event_note: str | None = None


@dataclass
class ScoredEvent:
    """Event after enrichment and scoring."""
    raw: RawEvent
    home_ctx: TeamContext
    away_ctx: TeamContext

    # Score components
    stakes_score:              float = 0.0
    competitive_balance_score: float = 0.0
    momentum_score:            float = 0.0
    star_power_score:          float = 0.0
    narrative_flags_score:     float = 0.0
    total_score:               float = 0.0

    # Narrative flags
    flags: list[str] = field(default_factory=list)

    # Display
    timing_label: str = ""

    # Transparency
    stakes_detail:     str = ""
    star_power_detail: str = ""
