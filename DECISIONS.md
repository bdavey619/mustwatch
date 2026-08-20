# Must Watch — Decision Log

Chronological record of key product and implementation decisions.

---

## 2026-04-14 — Weekly cadence, not nightly

**Decision:** Publish once weekly (Monday morning), not daily or nightly.

**Rationale:** "Must Watch Tonight" already exists — it's ESPN. A weekly format is a differentiated planning tool: read it Monday, decide where to spend your attention for the week. It also reduces data ops complexity significantly for Phase 1. A nightly variant may be added later as a lightweight companion.

---

## 2026-04-14 — Unified ranked list, not grouped by sport

**Decision:** One ranked list across MLB and NBA — not "best MLB game + best NBA game" separately.

**Rationale:** Grouping by sport avoids the hard question. A unified list forces the engine to actually answer: is this NBA game more compelling than that MLB game this week? That's where the editorial value lives. Grouping by sport produces a schedule, not a ranking.

---

## 2026-04-14 — Start with MLB + NBA only

**Decision:** Phase 1 covers only MLB and NBA. NFL, NHL, Premier League, PGA, and ATP deferred.

**Rationale:** Both sports are in season simultaneously in April–June. Both have good free data sources. Both have enough weekly events that ranking is meaningful. Adding leagues too early produces shallow coverage across many sports instead of sharp coverage across two. Expand only after the core engine is validated.

---

## 2026-04-14 — Rank story setup, not predicted game quality

**Decision:** The engine scores narrative going *into* a game, not whether the game will actually be good.

**Rationale:** Game quality cannot be reliably predicted. Story setup can be evaluated objectively from standings, form, stakes, and context. A high-narrative game that ends in a blowout is not a product failure — we're a preview engine, not a guarantee. Being explicit about this constraint also makes the product's scope honest and defensible.

---

## 2026-04-14 — Manual editorial override required in Phase 1

**Decision:** After automated scoring, a human editor reviews the top 10 candidates and may reorder the top 5 or swap one event before output is generated.

**Rationale:** The scoring framework will produce defensible but imperfect results, especially in edge cases involving cross-sport comparisons, early-season MLB calibration, and events not captured by the 4 narrative flags. The override is not a fallback — it is a designed part of the Phase 1 product. Scoring removes the need to evaluate every game; editorial judgment makes the final call.

---

## 2026-04-14 — Include Monday events with a 1-hour buffer filter

**Decision:** Include upcoming Monday events in the weekly ranking. Exclude any event already started or starting within 1 hour of the generation timestamp.

**Rationale:** Excluding all Monday events wastes legitimate content — a Monday night playoff game is compelling regardless of the day. The 1-hour buffer ensures the ranked list is always actionable (users won't find a game that just started). Same-day events are labeled `TONIGHT` to communicate immediacy without restructuring the list.

---

## 2026-04-14 — Dry-run milestone before rendering or explanations

**Decision:** Milestone 1 is terminal output only — ranked candidates with score breakdowns, no HTML, no LLM explanations, no editorial CLI.

**Rationale:** The most important thing to validate first is whether real data flows into defensible rankings. Building the rendering and explanation layers before the scoring is validated wastes effort — if the ranking logic is wrong, the explanations are wrong too. Dry-run first; polish second.

---

## 2026-04-14 — Use statsapi.mlb.com for MLB, ESPN unofficial API for NBA

**Decision:** MLB data from `statsapi.mlb.com/api/v1`. NBA data from `site.api.espn.com` (unofficial).

**Rationale:** `statsapi.mlb.com` is already used in this repo (padres/yankees briefs) and proven reliable. ESPN's unofficial API is the most accessible free source for NBA schedule and standings data. Neither requires an API key for Phase 1 data needs. Risk: ESPN schema is undocumented and can change — log raw responses during early runs.

---

## 2026-04-14 — Tier 2 narrative flags capped at 12, not 20

**Decision:** `rivalry` + `playoff_rematch` + `first_place_clash` can stack but are capped at 12 points combined. `elimination_game` (Tier 1) is a hard 20 with no stacking.

**Rationale:** Preserving the top of the narrative range (13–20) for genuinely terminal events. A regular season rivalry game with a playoff rematch flavor is interesting (14 raw → capped at 12), but it should not score as high as an actual elimination game. The cap enforces that distinction without requiring complex conditional logic.

---

## 2026-04-14 — Season-phase multiplier for regular season MLB stakes

**Decision:** Regular season stakes scores are multiplied by a season-phase factor: ×0.60 (first 20% of games), ×0.85 (middle 50%), ×1.00 (final 30%).

**Rationale:** A close division race in Game 15 of 162 is meaningfully less urgent than the same race in Game 140. The multiplier prevents April games from inflating to the same stakes level as September games — a defensible editorial judgment. Risk: this may suppress genuinely compelling early-season storylines. The editorial override exists precisely for this case.

---

## 2026-04-16 — Scheduled automation via mustwatch-auto branch + PR review gate

**Decision:** Weekly generation runs automatically via GitHub Actions. Output is committed to a machine-owned branch (`mustwatch-auto`) and a PR is opened against `main` for review. Publishing requires a deliberate merge — automation never writes directly to `main`.

**Rationale:** Blind publishing to `main` would remove the editorial gate that is designed into Phase 1. A PR-based approach preserves review without requiring a manual run every Monday. If the output is fine, merge takes seconds. If it needs adjustment, the branch can be replaced by running the workflow again after a local tweak or by doing a full manual run. The `--auto` flag accepts the default top 5; a custom order still requires the interactive local workflow.

**Pattern:** `workflow_dispatch` is also wired in, so the workflow can be triggered manually at any time (e.g. mid-week if a major storyline emerges or if Monday's run needs a redo).

---

## 2026-04-14 — Static marquee player list in config.py, manually maintained

**Decision:** `MARQUEE_PLAYERS` is a dict in `config.py` rather than a dynamically fetched roster list.

**Rationale:** Dynamic roster APIs add complexity and fragility for minimal gain in Phase 1. The set of truly marquee players (superstars and stars worth surfacing in rankings) is small and slow-changing. A curated static list is more reliable and more editorially intentional. Review quarterly and after major trades/injuries.

---

## 2026-08-20 — Expand to NFL and college football

**Decision:** Add NFL and NCAAF fetchers. Sport coverage becomes selectable at runtime via `--sports`; the default is MLB + NBA + NFL, with NCAAF opt-in.

**Rationale:** The unified cross-sport ranking has been inert since mid-June. Ten consecutive published editions — 2026-06-15 through 2026-08-10 — contained only MLB events, and the 2026-08-16 edition had a single candidate. A ranking engine whose entire editorial premise is "is this NBA game more compelling than that MLB game?" cannot answer that question when only one league is in season.

NFL is the largest gap: from November through February the list would otherwise be NBA-only while the country watches football. NCAAF covers late August through early January, and its Saturday-centric schedule fits the weekly cadence better than any sport already in the system.

**Note on the TODO gate:** `TODO.md` said not to expand coverage until 4+ consecutive weeks felt right without heavy override. That gate was written to protect against expanding while ranking *quality* was unproven. The summer exposed a different failure — the product losing its cross-sport premise entirely for a third of the year. The gate still applies to ranking-quality work; it should not block a fix for a structural coverage hole.

---

## 2026-08-20 — Football uses streak-based momentum, not L10

**Decision:** NFL and NCAAF momentum is scored from the win/loss streak. `l10_wins`/`l10_losses` stay at 0-0 for football and the placeholder is never passed to the LLM.

**Rationale:** A ten-game window is more than half an NFL season and nearly all of a college one, so "last ten" is not a recent-form signal in football — it is most of the season, which competitive balance already measures. ESPN does not publish an NFL L10 either. Streak is the football equivalent: a three-game win streak in a 17-game season is what a long hot stretch is in baseball.

The prompt-side handling matters as much as the scoring. `explain._l10` returns `None` for football rather than "L10 0-0" — feeding a placeholder to the model would invite it to describe a team as having lost ten straight, which is exactly the hallucination class the product is built to avoid.

---

## 2026-08-20 — NCAAF quality comes from the poll, not the record

**Decision:** College football team quality is derived from AP (or CFP, once published) poll position. Win percentage is only a fallback floor for unranked teams, capped below any ranked team.

**Rationale:** ~136 FBS teams play wildly unequal schedules and there is no single league table. A 4-0 Group of Five team and a 4-0 SEC team have identical records and are not comparable. The poll is the sport's own answer to that problem, so the engine uses it rather than inventing a worse one.

This also removes the need for a college standings endpoint: contexts are built from the scoreboard payload itself, where each competitor carries a record summary and a `curatedRank`.

---

## 2026-08-20 — NCAAF star power is program prestige, not poll rank

**Decision:** College star power comes from a static `NCAAF_PROGRAM_PRESTIGE` list (blueblood / major), deliberately independent of poll position. No marquee *player* list is maintained for college football.

**Rationale:** Two reasons. First, maintenance: college rosters turn over every year and tracking marquee players across ~136 programs is not sustainable, whereas blue-blood status changes on a decade timescale.

Second, and more important: an earlier draft derived college star power from poll rank, which meant rank drove stakes, competitive balance *and* star power — three of five components from one signal. A smoke run showed this floating ranked college games above comparable NFL games for no defensible reason. Prestige is a genuinely separate signal: a night game in Tuscaloosa draws a national audience whether or not Alabama is ranked that week.

---

## 2026-08-20 — Every NFL playoff game is an elimination game; most bowls are not

**Decision:** NFL postseason scores 30 stakes and gets the Tier 1 `elimination_game` flag. NCAAF postseason splits: College Football Playoff games score 29–30 and flag as elimination; all other bowls score 15 and get no flag.

**Rationale:** The NBA's postseason model does not transfer. A best-of-seven Game 2 is not terminal; every NFL playoff game is, by construction. Conversely, most of the ~40 college bowls are opt-out-riddled exhibitions between 6-6 teams. Scoring all "postseason" football identically would both understate January NFL and flood every late-December edition with games nobody planned an evening around. The round label from the source is the only thing that separates them, so it is read for that purpose and nothing else.

---

## 2026-08-20 — Scheduled workflow pinned to validated sports

**Decision:** The GitHub Actions workflow runs `--sports mlb,nba`. NFL and NCAAF are enabled only after a manual run confirms live payloads parse.

**Rationale:** The NFL and NCAAF fetchers were written against ESPN's documented-by-convention response shapes but could not be validated — the build environment's egress policy blocks `site.api.espn.com` entirely, so no live payload was ever fetched. Unit tests cover the normalizers and scoring against hand-built fixtures, which proves the logic but not the schema assumptions. Shipping unvalidated ingestion straight into the published Monday page would put the editorial gate at risk for no benefit; flipping one flag after a successful dry run costs nothing.

---

## 2026-08-20 — Wild card position read from rank, not from a missing value

**Decision:** `score._in_mlb_race` determines wild card standing from `wild_card_rank`, not from `wc_games_back is None`. `mlb.py` parses absent ranks to `None` rather than `0`.

**Rationale:** A bug surfaced while adding football. `models.py` documents `wc_games_back = None` as "holds a wild card spot" — the MLB API returns `"-"` for teams in position — but `_in_mlb_race` read that same `None` as "no wild card data" and returned False. A team leading the wild card while more than 5 games back in its division therefore scored as out of the race entirely, dropping stakes from 22 to 15.

The fix does not simply invert the check, because that `None` is genuinely ambiguous: it also appears when the API omits the field. Reading `wild_card_rank` instead uses a positive signal, so a missing payload still degrades to "not in the race" rather than sweeping every team in.

The parsing half mattered too: `int(tr.get("wildCardRank", 0))` turned a missing rank into 0, which compares as better than first place. Any logic keying off rank would have silently treated every unranked team as a wild card leader.

**Impact:** This changes published MLB rankings — teams holding a wild card berth now score 22 stakes rather than 15 where they previously fell through. That is the correct behavior, but it is a real output change and worth diffing against a recent edition before the next publish.

---

## 2026-08-20 — Live schema validation is a script, not a manual checklist

**Decision:** Add `validate_sources.py`, which calls the real endpoints and asserts every assumption the fetchers make, rather than keeping those assumptions as prose checkboxes in TODO.md.

**Rationale:** The NFL and NCAAF fetchers shipped unvalidated because the build environment blocked `site.api.espn.com`. The gap between "unit tests pass" and "this works against ESPN" is entirely schema assumptions, and a list of things to eyeball by hand is not a durable way to check thirty of them.

The failure mode that motivated this is silence, not errors. A wrong college abbreviation in `NCAAF_RIVALRIES` does not raise — the rivalry simply never fires. A stat that arrives as `displayValue` instead of `value` does not raise — every team reads 0-0. A missing `playoffSeed` does not raise — the stakes model quietly falls back to win-pct tiers. The script checks precisely these, and the same run doubles as a regression check on the MLB wild card fix.

It is also the reason the workflow stays pinned: enabling a sport is now gated on a command that either passes or does not, rather than on judgment about whether the code looks right.

---

## 2026-08-20 — Missing data is not bad data

**Decision:** When a team has played too few games for its record to carry signal, the engine returns an explicit neutral rather than letting the record fall through the normal curves. Introduces `MIN_GAMES_FOR_RECORD`, `NEUTRAL_TEAM_QUALITY`, `NEUTRAL_STAKES_BASE`, and a per-sport season-phase curve.

**Rationale:** An NFL Week 1 matchup between Mahomes and Allen scored 36/100 — below a routine September MLB game at 70 — and would never have reached the top 5. Three components bottomed out simultaneously, all for the same reason: nobody had played yet. `win_pct` of 0.0 mapped to the worst quality tier, no published playoff seed meant stakes fell through to "no meaningful stakes", and the ×0.60 early-season multiplier then cut that in half again.

The underlying error is treating *absence of evidence* as *evidence of absence*. A 0-0 team is not a .000 team. The fix makes the distinction explicit rather than tuning the numbers around it.

Two details matter. First, the multiplier is deliberately not applied to the neutral baseline: the discount exists to say a standings-derived claim is premature, and when there is no standings claim, applying it charges the same uncertainty twice — which is precisely how stakes reached 3.0/30. Second, the phase curve is now per-sport. The original 0.60/0.85/1.00 is a fair statement about April baseball and a poor one about September football, where the first 20% of the season is Weeks 1–4.

College football is exempt from the neutral path: the preseason AP poll gives every ranked team a meaningful position from Week 1, so its stakes model already works with zero games played.

**Calibration check:** A marquee opener moves 36.0 → 60.0. A nothing opener (Panthers/Titans) sits at 41.0, and the same marquee matchup in Week 12 with real standings scores 76.8. The fix lifts openers into contention without lifting them indiscriminately, and preserves the ordering between an opener and a genuine late-season contest.

**Scope — all four sports, decided deliberately:** the sample-sufficiency rule was scoped to every sport rather than to football alone. Confining it to NFL and NCAAF was considered and rejected.

The rule is not a football rule. Twelve games into a baseball season a 3-9 team is not established as bad, and scoring it as a .250 team is the same error the NFL opener exposed — it is only *conspicuous* in football because three games of seventeen is a fifth of the season where three of 162 is noise. Fixing it in one sport and not the others would leave the engine deciding the same question two different ways depending on which league it happened to be looking at, which is difficult to defend in a product whose entire premise is comparing across leagues.

The concrete effect: competitive balance shifts for the first 20 MLB games and the first 10 NBA games. An April 9-3 vs 3-9 matchup now scores balance 12.0 rather than 4.0. Phase multipliers for MLB and NBA are untouched, so the change is confined to early-season balance and does not touch the stakes model, which has real standings from opening day in both sports.

A preseason prior seeded from prior-year finish would beat a flat neutral for all four sports and is the natural next step; noted in TODO.md.
