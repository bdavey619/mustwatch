"""
config.py — Static configuration for Must Watch This Week.

All weights, marquee players, rivalries, and season parameters.
No I/O or network calls.
"""

# ---------------------------------------------------------------------------
# Scoring weights — components sum to 100
# ---------------------------------------------------------------------------
WEIGHTS = {
    "stakes":              30,
    "competitive_balance": 20,
    "momentum":            15,
    "star_power":          15,
    "narrative_flags":     20,
}

# ---------------------------------------------------------------------------
# Marquee players
# Key: "{SPORT}:{TEAM_ABBR}" — avoids BOS/MIL/PHI/ATL cross-sport collisions
# Tier: "superstar" or "star"
# ---------------------------------------------------------------------------
MARQUEE_PLAYERS: dict[str, list[dict]] = {
    # MLB
    "MLB:LAD": [
        {"name": "Shohei Ohtani",       "tier": "superstar"},
        {"name": "Mookie Betts",         "tier": "superstar"},
        {"name": "Freddie Freeman",      "tier": "star"},
    ],
    "MLB:SD":  [
        {"name": "Fernando Tatis Jr.",   "tier": "superstar"},
        {"name": "Manny Machado",        "tier": "star"},
    ],
    "MLB:NYM": [
        {"name": "Juan Soto",            "tier": "superstar"},
        {"name": "Pete Alonso",          "tier": "star"},
    ],
    "MLB:NYY": [
        {"name": "Aaron Judge",          "tier": "superstar"},
        {"name": "Gerrit Cole",          "tier": "star"},
    ],
    "MLB:ATL": [
        {"name": "Ronald Acuna Jr.",     "tier": "superstar"},
        {"name": "Spencer Strider",      "tier": "star"},
        {"name": "Matt Olson",           "tier": "star"},
    ],
    "MLB:HOU": [
        {"name": "Yordan Alvarez",       "tier": "superstar"},
        {"name": "Jose Altuve",          "tier": "star"},
    ],
    "MLB:PHI": [
        {"name": "Bryce Harper",         "tier": "superstar"},
        {"name": "Zack Wheeler",         "tier": "star"},
        {"name": "Trea Turner",          "tier": "star"},
    ],
    "MLB:BAL": [
        {"name": "Gunnar Henderson",     "tier": "superstar"},
        {"name": "Adley Rutschman",      "tier": "star"},
    ],
    "MLB:KC":  [
        {"name": "Bobby Witt Jr.",       "tier": "superstar"},
        {"name": "Salvador Perez",       "tier": "star"},
    ],
    "MLB:CLE": [
        {"name": "Jose Ramirez",         "tier": "superstar"},
        {"name": "Shane Bieber",         "tier": "star"},
    ],
    "MLB:TEX": [
        {"name": "Corey Seager",         "tier": "superstar"},
    ],
    "MLB:SEA": [
        {"name": "Julio Rodriguez",      "tier": "star"},
    ],
    "MLB:STL": [
        {"name": "Nolan Arenado",        "tier": "star"},
    ],
    "MLB:BOS": [
        {"name": "Rafael Devers",        "tier": "star"},
    ],
    "MLB:LAA": [
        {"name": "Mike Trout",           "tier": "superstar"},
    ],
    "MLB:MIN": [
        {"name": "Byron Buxton",         "tier": "star"},
    ],
    "MLB:CHC": [
        {"name": "Dansby Swanson",       "tier": "star"},
    ],
    "MLB:SF":  [
        {"name": "Matt Chapman",         "tier": "star"},
    ],
    "MLB:MIL": [],
    "MLB:CIN": [],
    "MLB:PIT": [],
    "MLB:AZ":  [],
    "MLB:COL": [],
    "MLB:WSH": [],
    "MLB:MIA": [],
    "MLB:TB":  [],
    "MLB:TOR": [],
    "MLB:DET": [],
    "MLB:CWS": [],
    "MLB:OAK": [],
    "MLB:OAK_ATH": [],

    # NBA
    "NBA:BOS": [
        {"name": "Jayson Tatum",         "tier": "superstar"},
        {"name": "Jaylen Brown",         "tier": "star"},
    ],
    "NBA:LAL": [
        {"name": "LeBron James",         "tier": "superstar"},
        {"name": "Anthony Davis",        "tier": "superstar"},
    ],
    "NBA:GSW": [
        {"name": "Stephen Curry",        "tier": "superstar"},
    ],
    "NBA:MIL": [
        {"name": "Giannis Antetokounmpo","tier": "superstar"},
        {"name": "Damian Lillard",       "tier": "star"},
    ],
    "NBA:DEN": [
        {"name": "Nikola Jokic",         "tier": "superstar"},
        {"name": "Jamal Murray",         "tier": "star"},
    ],
    "NBA:PHX": [
        {"name": "Kevin Durant",         "tier": "superstar"},
        {"name": "Devin Booker",         "tier": "superstar"},
    ],
    "NBA:PHI": [
        {"name": "Joel Embiid",          "tier": "superstar"},
        {"name": "Tyrese Maxey",         "tier": "star"},
    ],
    "NBA:MEM": [
        {"name": "Ja Morant",            "tier": "superstar"},
    ],
    "NBA:DAL": [
        {"name": "Luka Doncic",          "tier": "superstar"},
        {"name": "Kyrie Irving",         "tier": "star"},
    ],
    "NBA:MIN": [
        {"name": "Anthony Edwards",      "tier": "superstar"},
        {"name": "Karl-Anthony Towns",   "tier": "star"},
    ],
    "NBA:CLE": [
        {"name": "Donovan Mitchell",     "tier": "superstar"},
    ],
    "NBA:OKC": [
        {"name": "Shai Gilgeous-Alexander", "tier": "superstar"},
    ],
    "NBA:SAS": [
        {"name": "Victor Wembanyama",    "tier": "superstar"},
    ],
    "NBA:NYK": [
        {"name": "Jalen Brunson",        "tier": "star"},
    ],
    "NBA:IND": [
        {"name": "Tyrese Haliburton",    "tier": "star"},
    ],
    "NBA:MIA": [
        {"name": "Jimmy Butler",         "tier": "star"},
    ],
    "NBA:ATL": [
        {"name": "Trae Young",           "tier": "star"},
    ],
    "NBA:SAC": [
        {"name": "De'Aaron Fox",         "tier": "star"},
        {"name": "Domantas Sabonis",     "tier": "star"},
    ],
    "NBA:TOR": [
        {"name": "Scottie Barnes",       "tier": "star"},
    ],
    "NBA:LAC": [
        {"name": "Kawhi Leonard",        "tier": "superstar"},
    ],
    "NBA:NOP": [
        {"name": "Zion Williamson",      "tier": "star"},
    ],
    "NBA:ORL": [
        {"name": "Paolo Banchero",       "tier": "star"},
    ],
    "NBA:HOU": [
        {"name": "Jalen Green",          "tier": "star"},
    ],
    "NBA:CHI": [],
    "NBA:BKN": [],
    "NBA:DET": [],
    "NBA:CHA": [],
    "NBA:WAS": [],
    "NBA:POR": [],
    "NBA:UTA": [],

    # NFL
    # Quarterbacks carry disproportionate attention weight in football — a
    # marquee QB moves the needle more than a marquee player at any other
    # position. Tier accordingly.
    "NFL:KC":  [
        {"name": "Patrick Mahomes",      "tier": "superstar"},
        {"name": "Travis Kelce",         "tier": "star"},
        {"name": "Chris Jones",          "tier": "star"},
    ],
    "NFL:BUF": [
        {"name": "Josh Allen",           "tier": "superstar"},
    ],
    "NFL:BAL": [
        {"name": "Lamar Jackson",        "tier": "superstar"},
        {"name": "Derrick Henry",        "tier": "star"},
    ],
    "NFL:CIN": [
        {"name": "Joe Burrow",           "tier": "superstar"},
        {"name": "Ja'Marr Chase",        "tier": "superstar"},
        {"name": "Trey Hendrickson",     "tier": "star"},
    ],
    "NFL:PHI": [
        {"name": "Jalen Hurts",          "tier": "superstar"},
        {"name": "Saquon Barkley",       "tier": "superstar"},
        {"name": "A.J. Brown",           "tier": "star"},
    ],
    "NFL:SF":  [
        {"name": "Christian McCaffrey",  "tier": "superstar"},
        {"name": "Nick Bosa",            "tier": "star"},
        {"name": "Brock Purdy",          "tier": "star"},
    ],
    "NFL:DAL": [
        {"name": "Micah Parsons",        "tier": "superstar"},
        {"name": "CeeDee Lamb",          "tier": "superstar"},
        {"name": "Dak Prescott",         "tier": "star"},
    ],
    "NFL:DET": [
        {"name": "Amon-Ra St. Brown",    "tier": "star"},
        {"name": "Aidan Hutchinson",     "tier": "star"},
        {"name": "Jared Goff",           "tier": "star"},
    ],
    "NFL:MIA": [
        {"name": "Tyreek Hill",          "tier": "superstar"},
        {"name": "Tua Tagovailoa",       "tier": "star"},
    ],
    "NFL:MIN": [
        {"name": "Justin Jefferson",     "tier": "superstar"},
    ],
    "NFL:WSH": [
        {"name": "Jayden Daniels",       "tier": "superstar"},
    ],
    "NFL:HOU": [
        {"name": "C.J. Stroud",          "tier": "superstar"},
        {"name": "Nico Collins",         "tier": "star"},
    ],
    "NFL:CLE": [
        {"name": "Myles Garrett",        "tier": "superstar"},
    ],
    "NFL:PIT": [
        {"name": "T.J. Watt",            "tier": "superstar"},
    ],
    "NFL:LAR": [
        {"name": "Puka Nacua",           "tier": "star"},
        {"name": "Matthew Stafford",     "tier": "star"},
    ],
    "NFL:GB":  [
        {"name": "Jordan Love",          "tier": "star"},
    ],
    "NFL:LAC": [
        {"name": "Justin Herbert",       "tier": "star"},
    ],
    "NFL:LV":  [
        {"name": "Maxx Crosby",          "tier": "star"},
    ],
    "NFL:DEN": [
        {"name": "Patrick Surtain II",   "tier": "star"},
        {"name": "Bo Nix",               "tier": "star"},
    ],
    "NFL:CHI": [
        {"name": "Caleb Williams",       "tier": "star"},
    ],
    "NFL:ATL": [
        {"name": "Bijan Robinson",       "tier": "star"},
    ],
    "NFL:TB":  [
        {"name": "Mike Evans",           "tier": "star"},
        {"name": "Baker Mayfield",       "tier": "star"},
    ],
    "NFL:NYJ": [
        {"name": "Sauce Gardner",        "tier": "star"},
    ],
    "NFL:NYG": [
        {"name": "Malik Nabers",         "tier": "star"},
    ],
    "NFL:ARI": [
        {"name": "Marvin Harrison Jr.",  "tier": "star"},
        {"name": "Kyler Murray",         "tier": "star"},
    ],
    "NFL:JAX": [
        {"name": "Trevor Lawrence",      "tier": "star"},
    ],
    "NFL:IND": [
        {"name": "Jonathan Taylor",      "tier": "star"},
    ],
    "NFL:NE":  [
        {"name": "Drake Maye",           "tier": "star"},
    ],
    "NFL:NO":  [
        {"name": "Alvin Kamara",         "tier": "star"},
    ],
    "NFL:SEA": [],
    "NFL:TEN": [],
    "NFL:CAR": [],
}

# ---------------------------------------------------------------------------
# Marquee pitchers — name → tier
# Used to detect ace_duel narrative flag when both probable starters qualify.
# Keep small and review quarterly alongside MARQUEE_PLAYERS.
# "elite" = clearly frontline ace; "star" = reliable top-of-rotation starter
# ---------------------------------------------------------------------------
MARQUEE_PITCHERS: dict[str, str] = {
    # Elite — ace-tier starters
    "Shohei Ohtani":       "elite",   # confirmed pitching in 2026
    "Yoshinobu Yamamoto":  "elite",
    "Paul Skenes":         "elite",
    "Tarik Skubal":        "elite",
    "Zack Wheeler":        "elite",
    "Gerrit Cole":         "elite",
    "Spencer Strider":     "elite",
    "Corbin Burnes":       "elite",
    "Chris Sale":          "elite",
    # Star — top-of-rotation starters
    "Logan Webb":          "star",
    "Framber Valdez":      "star",
    "Shane Bieber":        "star",
    "Kevin Gausman":       "star",
    "Hunter Greene":       "star",
    "Freddy Peralta":      "star",
    "Blake Snell":         "star",
    "Tyler Glasnow":       "star",
    "Dylan Cease":         "star",
    "George Kirby":        "star",
    "Sandy Alcantara":     "star",
    "Kodai Senga":         "star",
    "Luis Castillo":       "star",
}

# ---------------------------------------------------------------------------
# Rivalries — frozenset pairs using "{SPORT}:{ABBR}" keys
# ---------------------------------------------------------------------------
RIVALRIES: set[frozenset] = {
    # MLB
    frozenset({"MLB:NYY", "MLB:BOS"}),
    frozenset({"MLB:LAD", "MLB:SF"}),
    frozenset({"MLB:LAD", "MLB:SD"}),
    frozenset({"MLB:CHC", "MLB:STL"}),
    frozenset({"MLB:NYY", "MLB:NYM"}),
    frozenset({"MLB:PHI", "MLB:NYM"}),
    frozenset({"MLB:LAD", "MLB:HOU"}),
    frozenset({"MLB:ATL", "MLB:PHI"}),
    frozenset({"MLB:NYY", "MLB:HOU"}),
    frozenset({"MLB:BAL", "MLB:NYY"}),
    frozenset({"MLB:LAD", "MLB:ATL"}),
    frozenset({"MLB:BOS", "MLB:HOU"}),
    frozenset({"MLB:MIN", "MLB:CLE"}),
    # NBA
    frozenset({"NBA:BOS", "NBA:LAL"}),
    frozenset({"NBA:BOS", "NBA:MIA"}),
    frozenset({"NBA:GSW", "NBA:LAL"}),
    frozenset({"NBA:LAL", "NBA:LAC"}),
    frozenset({"NBA:BOS", "NBA:NYK"}),
    frozenset({"NBA:PHI", "NBA:BOS"}),
    frozenset({"NBA:MIL", "NBA:BOS"}),
    frozenset({"NBA:GSW", "NBA:CLE"}),
    frozenset({"NBA:DEN", "NBA:LAL"}),
    frozenset({"NBA:DAL", "NBA:OKC"}),
    frozenset({"NBA:MIL", "NBA:PHI"}),
    # NFL — divisional blood feuds plus the modern playoff rivalries
    frozenset({"NFL:GB",  "NFL:CHI"}),
    frozenset({"NFL:GB",  "NFL:MIN"}),
    frozenset({"NFL:GB",  "NFL:DET"}),
    frozenset({"NFL:CHI", "NFL:MIN"}),
    frozenset({"NFL:DAL", "NFL:PHI"}),
    frozenset({"NFL:DAL", "NFL:WSH"}),
    frozenset({"NFL:DAL", "NFL:NYG"}),
    frozenset({"NFL:PHI", "NFL:NYG"}),
    frozenset({"NFL:PHI", "NFL:WSH"}),
    frozenset({"NFL:PIT", "NFL:BAL"}),
    frozenset({"NFL:PIT", "NFL:CLE"}),
    frozenset({"NFL:PIT", "NFL:CIN"}),
    frozenset({"NFL:BAL", "NFL:CLE"}),
    frozenset({"NFL:BAL", "NFL:CIN"}),
    frozenset({"NFL:KC",  "NFL:LV"}),
    frozenset({"NFL:KC",  "NFL:DEN"}),
    frozenset({"NFL:KC",  "NFL:LAC"}),
    frozenset({"NFL:DEN", "NFL:LV"}),
    frozenset({"NFL:NE",  "NFL:NYJ"}),
    frozenset({"NFL:NE",  "NFL:BUF"}),
    frozenset({"NFL:NE",  "NFL:MIA"}),
    frozenset({"NFL:BUF", "NFL:MIA"}),
    frozenset({"NFL:BUF", "NFL:NYJ"}),
    frozenset({"NFL:SF",  "NFL:SEA"}),
    frozenset({"NFL:SF",  "NFL:LAR"}),
    frozenset({"NFL:SEA", "NFL:LAR"}),
    frozenset({"NFL:NO",  "NFL:ATL"}),
    frozenset({"NFL:NO",  "NFL:TB"}),
    frozenset({"NFL:ATL", "NFL:CAR"}),
    frozenset({"NFL:IND", "NFL:TEN"}),
    frozenset({"NFL:IND", "NFL:HOU"}),
    frozenset({"NFL:KC",  "NFL:BUF"}),   # modern postseason rivalry
    frozenset({"NFL:SF",  "NFL:DAL"}),   # historic
}

# ---------------------------------------------------------------------------
# NCAAF program prestige — the college analogue of MARQUEE_PLAYERS.
#
# College football has no stable marquee-player list: rosters turn over every
# year and tracking ~136 programs is unmaintainable. But the *program* is the
# draw — a night game in Tuscaloosa or the Horseshoe pulls a national audience
# regardless of who is on the roster.
#
# Prestige is deliberately independent of poll rank. Rank already drives stakes
# and competitive balance; reusing it for star power too would count the same
# signal three times and float every ranked college game above comparable NFL
# games. Blue-blood status changes on a decade timescale, so this list is far
# more stable than MARQUEE_PLAYERS.
# ---------------------------------------------------------------------------
NCAAF_PROGRAM_PRESTIGE: dict[str, str] = {
    # "blueblood" — national brand, draws a neutral audience on name alone
    "NCAAF:OSU":  "blueblood",
    "NCAAF:ALA":  "blueblood",
    "NCAAF:MICH": "blueblood",
    "NCAAF:ND":   "blueblood",
    "NCAAF:UGA":  "blueblood",
    "NCAAF:TEX":  "blueblood",
    "NCAAF:USC":  "blueblood",
    "NCAAF:OU":   "blueblood",
    "NCAAF:LSU":  "blueblood",
    "NCAAF:PSU":  "blueblood",
    "NCAAF:FLA":  "blueblood",
    "NCAAF:NEB":  "blueblood",
    "NCAAF:TENN": "blueblood",
    "NCAAF:MIA":  "blueblood",
    "NCAAF:FSU":  "blueblood",
    "NCAAF:AUB":  "blueblood",
    "NCAAF:CLEM": "blueblood",
    # "major" — strong regional brand, real but narrower national pull
    "NCAAF:ORE":  "major",
    "NCAAF:WASH": "major",
    "NCAAF:WIS":  "major",
    "NCAAF:IOWA": "major",
    "NCAAF:TA&M": "major",
    "NCAAF:UCLA": "major",
    "NCAAF:UNC":  "major",
    "NCAAF:VT":   "major",
    "NCAAF:WVU":  "major",
    "NCAAF:MSU":  "major",
    "NCAAF:MISS": "major",
    "NCAAF:OKST": "major",
    "NCAAF:TCU":  "major",
    "NCAAF:UTAH": "major",
    "NCAAF:BYU":  "major",
    "NCAAF:LOU":  "major",
    "NCAAF:ARK":  "major",
    "NCAAF:SC":   "major",
    "NCAAF:MSST": "major",
    "NCAAF:KSU":  "major",
    "NCAAF:BAY":  "major",
    "NCAAF:PITT": "major",
    "NCAAF:ASU":  "major",
    "NCAAF:COLO": "major",
    "NCAAF:ARMY": "major",
    "NCAAF:NAVY": "major",
}

# ---------------------------------------------------------------------------
# NCAAF rivalries — keyed "NCAAF:{ESPN_ABBR}"
#
# College football rivalry games are the sport's single strongest narrative
# signal: they routinely outdraw higher-ranked matchups and are played on
# fixed dates regardless of records. Weighted heavily in scoring for that
# reason. Verify abbreviations against a live ESPN response before trusting
# this list — see NOTES in ncaaf.py.
# ---------------------------------------------------------------------------
NCAAF_RIVALRIES: set[frozenset] = {
    frozenset({"NCAAF:OSU",  "NCAAF:MICH"}),   # The Game
    frozenset({"NCAAF:ALA",  "NCAAF:AUB"}),    # Iron Bowl
    frozenset({"NCAAF:ARMY", "NCAAF:NAVY"}),
    frozenset({"NCAAF:TEX",  "NCAAF:OU"}),     # Red River
    frozenset({"NCAAF:USC",  "NCAAF:ND"}),
    frozenset({"NCAAF:UGA",  "NCAAF:FLA"}),    # Cocktail Party
    frozenset({"NCAAF:UGA",  "NCAAF:AUB"}),
    frozenset({"NCAAF:UGA",  "NCAAF:GT"}),
    frozenset({"NCAAF:ALA",  "NCAAF:LSU"}),
    frozenset({"NCAAF:ALA",  "NCAAF:TENN"}),
    frozenset({"NCAAF:MICH", "NCAAF:MSU"}),
    frozenset({"NCAAF:OSU",  "NCAAF:PSU"}),
    frozenset({"NCAAF:CLEM", "NCAAF:SC"}),
    frozenset({"NCAAF:FSU",  "NCAAF:MIA"}),
    frozenset({"NCAAF:FSU",  "NCAAF:FLA"}),
    frozenset({"NCAAF:MIA",  "NCAAF:FLA"}),
    frozenset({"NCAAF:MISS", "NCAAF:MSST"}),   # Egg Bowl
    frozenset({"NCAAF:TEX",  "NCAAF:TA&M"}),
    frozenset({"NCAAF:OU",   "NCAAF:OKST"}),   # Bedlam
    frozenset({"NCAAF:USC",  "NCAAF:UCLA"}),
    frozenset({"NCAAF:WASH", "NCAAF:ORE"}),
    frozenset({"NCAAF:UTAH", "NCAAF:BYU"}),    # Holy War
    frozenset({"NCAAF:WIS",  "NCAAF:MINN"}),   # Axe
    frozenset({"NCAAF:NEB",  "NCAAF:IOWA"}),
    frozenset({"NCAAF:PITT", "NCAAF:WVU"}),    # Backyard Brawl
    frozenset({"NCAAF:VT",   "NCAAF:UVA"}),
    frozenset({"NCAAF:LOU",  "NCAAF:UK"}),
    frozenset({"NCAAF:KU",   "NCAAF:KSU"}),
    frozenset({"NCAAF:TCU",  "NCAAF:BAY"}),
    frozenset({"NCAAF:ND",   "NCAAF:NAVY"}),
    frozenset({"NCAAF:CAL",  "NCAAF:STAN"}),   # Big Game
    frozenset({"NCAAF:ARIZ", "NCAAF:ASU"}),    # Territorial Cup
}

# ---------------------------------------------------------------------------
# Playoff rematches (last 2 postseasons)
# ---------------------------------------------------------------------------
PLAYOFF_REMATCHES: set[frozenset] = {
    frozenset({"NBA:BOS", "NBA:DAL"}),   # 2024 NBA Finals
    frozenset({"MLB:LAD", "MLB:NYY"}),   # 2024 World Series
    frozenset({"MLB:LAD", "MLB:NYM"}),   # 2024 NLCS
    frozenset({"MLB:NYY", "MLB:CLE"}),   # 2024 ALCS
    frozenset({"NBA:DEN", "NBA:MIA"}),   # 2023 NBA Finals
    frozenset({"MLB:TEX", "MLB:AZ"}),    # 2023 World Series
    frozenset({"NBA:BOS", "NBA:MIA"}),   # 2023 ECF
    frozenset({"NBA:MIL", "NBA:BOS"}),   # 2023 ECF (Bucks vs Celtics)
}

# ---------------------------------------------------------------------------
# Season configuration
# ---------------------------------------------------------------------------
MLB_TOTAL_GAMES   = 162
NBA_TOTAL_GAMES   = 82
NFL_TOTAL_GAMES   = 17
NCAAF_TOTAL_GAMES = 12

# Playoff race thresholds (games back from cutoff)
MLB_RACE_THRESHOLD     = 5.0   # games back from wild card spot or division lead
NBA_PLAYOFF_RANK_CUTOFF = 6    # top 6 → direct playoff berth
NBA_PLAYIN_RANK_CUTOFF  = 10   # 7–10 → play-in tournament

# NFL — 7 playoff berths per conference since 2020.
NFL_PLAYOFF_SEED_CUTOFF = 7    # seeds 1–7 → playoff berth
NFL_HUNT_SEED_CUTOFF    = 10   # seeds 8–10 → live in the race

# NCAAF — AP poll thresholds. Poll position replaces win pct as the quality
# signal because college records are not comparable across schedules.
NCAAF_ELITE_RANK  = 10   # top 10 → marquee national matchup
NCAAF_RANKED_CUTOFF = 25 # AP poll depth

# NCAAF — ESPN group id for FBS (Division I-A). Without this the scoreboard
# returns every division and drowns the pool in FCS/D-II noise.
NCAAF_FBS_GROUP_ID = 80

# Sports enabled by default when --sports is not passed.
# NCAAF is opt-in: see DECISIONS.md 2026-08-20.
DEFAULT_SPORTS = ("MLB", "NBA", "NFL")
ALL_SPORTS     = ("MLB", "NBA", "NFL", "NCAAF")

# Season phase multipliers (regular season stakes only)
SEASON_PHASE_MULTIPLIERS = {
    "early": 0.60,   # first 20% of season
    "mid":   0.85,   # 20–70%
    "late":  1.00,   # final 30%
}

# Timing filter — exclude events starting within N seconds of generation time
TIMING_FILTER_SECONDS = 3600   # 1 hour

# Candidate pool size
TOP_N_CANDIDATES = 10
