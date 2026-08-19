# Upstream

A fantasy baseball streaming-pitcher tool: ranks all 30 MLB teams by how
favorable a matchup they are for an opposing starting pitcher, so you can
find the best waiver-wire streamer for tonight (or the next 5 nights).

**Live site:** https://cvoros.github.io/matchup-tracker/

Static site, no backend. A Python script pulls MLB (and optionally ESPN
Fantasy) data on an hourly GitHub Actions cron, writes it to JSON files
in the repo, and `index.html` reads those files client-side. No build
step, no framework — one HTML file with inline CSS/JS.

---

## What it shows

Every MLB team gets a **composite score from 1.0 (worst matchup) to 10.0
(best matchup)** for a streaming pitcher, based on four per-game rates of
that team's *offense*:

```
score = K/G × 1.0  −  H/G × 1.0  −  BB/G × 1.0  −  R/G × 2.0
```

- **K/G** (strikeouts/game) counts *for* the matchup — batters who strike
  out are outs, good for whoever's on the mound.
- **H/G**, **BB/G**, **R/G** count *against* it. Runs are weighted 2×
  since they're the biggest single line-item in most points formats.

The raw score is then normalized to a 1.0–10.0 scale *within whichever
window is currently selected* (see below), so "10.0" always means "the
best matchup available right now," not an absolute number tied to a
particular season. Teams are ranked 1 (best) through 30 (worst), and
every column — including the individual stat columns, not just the
composite score — is colored in even thirds: **top 10 green, middle 10
yellow, bottom 10 red**.

`R/G` is the offense's *total* runs scored, not earned runs. Earned vs.
unearned is a pitching/defense classification that doesn't exist for an
offense — there's no "earned runs scored" stat to use instead, and
unearned runs are a small, fairly even share of scoring league-wide, so
this doesn't meaningfully skew the ranking.

One thing worth knowing if a number looks surprising: all four windows
below are filtered to **vs. starting pitchers only**, which pushes H/G
noticeably higher than what you'd see on a site like Baseball Reference
(which blends in relief appearances — relievers are generally tougher to
hit than starters). A team leading the league in H/G-vs-starters isn't
necessarily a great offense overall; it's specifically hard on the guy
you're trying to start.

## The three control groups

The header has three independent button groups:

**1. Time window** — Full Season / Last 30 / Last 15 / Last 7 Days
All four are vs. starting pitchers only (MLB Stats API `sitCodes=sp`).

**2. Handedness** — All / vs LHP / vs RHP
Platoon splits, sourced from a different MLB API endpoint
(`stats=statSplits`, `sitCodes=vl`/`vr`).

**3. View** — Team Rank / Calendar
Independent of the other two; just changes how the same data is
displayed.

### Why groups 1 and 2 fight each other

This is a real API limitation, not a UI bug: **the platoon-split
endpoint doesn't support date ranges, and the vs-starters filter doesn't
support handedness sitCodes.** The two features are mutually exclusive
at the API level — there's no request you can make that returns "vs LHP
starters over the last 15 days." (This was tested directly against the
MLB API; combining `sitCodes=sp` with `vl`/`vr` silently returns nothing
useful.)

So the UI enforces the same constraint the API does:
- Pick a time window (30/15/7 days) → handedness resets to **All**.
- Pick vs LHP or vs RHP → the time window is forced to **Full Season**,
  since platoon data only exists for the season as a whole.

A second, smaller quirk from the same endpoint: `statSplits` doesn't
return a `runs` field, so the vs-LHP/vs-RHP windows use **RBI as a proxy
for runs** in the scoring formula instead. It's a close but imperfect
stand-in (RBI slightly undercounts runs scored via non-RBI paths like
errors, wild pitches, etc.).

Also: unlike the four vs-starters windows, **vs LHP/vs RHP includes
every pitcher appearance**, not just starts — there's no way to filter
platoon splits to starters-only. The footer note on the page spells this
out.

## Team Rank view

A sortable table — click any column header to re-sort by it (click again
to flip direction). Click a row to open a modal with that team's
probable opposing pitchers for the next 5 days.

## Calendar view

Same underlying rank data, laid out as 5 day-columns. Each column lists
every game that day, sorted best-matchup-first, showing the batting
team, its rank, and the *opposing* probable pitcher (with handedness).
Portrait mobile collapses the rankings table to Rank/Team/Score only to
fit narrow screens; the calendar reflows to 2 columns, then 1.

### Probable pitcher fallback

MLB's schedule API frequently hasn't posted a probable starter yet for
games a few days out, even when the pick is already public knowledge.
When that happens, the app falls back to **ESPN's public scoreboard
API**, which tends to have it sooner. Since ESPN doesn't return pitcher
handedness, any ESPN-sourced pitcher gets a follow-up name search against
MLB's People API to recover it. If MLB has genuinely not decided a
starter yet, both sources come back empty and the slot shows **TBD**
(with the team abbreviation still shown, so you at least know who's
playing).

### Roster lock awareness

ESPN (and most fantasy platforms) lock daily transactions the moment the
**first MLB game of the day** starts: an add made after that doesn't
take effect until tomorrow, and a drop doesn't clear your roster until
tomorrow either. The app tracks this:

- The header shows **🔓** (with the local lockdown time and a live
  `HH:MM to lockdown` countdown) before the first pitch, and **🔒
  Rosters locked** after.
- Lockdown time = the earliest scheduled start across *all* of MLB for
  the current local date — not just games involving your team.
- Once locked, **both the Calendar view and the team modal skip today
  entirely** and start their 5-day window on tomorrow instead, since
  today's matchups are no longer actionable for a streaming add.
- This re-checks automatically at local midnight without needing a page
  reload (a 20-second interval re-derives lockdown time whenever the
  local date string changes).

## Fantasy league integration (optional)

If three GitHub Actions secrets are configured — `ESPN_LEAGUE_ID`,
`ESPN_S2`, `ESPN_SWID` (the latter two are cookie values from being
logged into `fantasy.espn.com`) — the hourly workflow also pulls your
ESPN Fantasy league's rosters and writes `data/league.json`. If those
secrets aren't set, `fetch_league.py` exits cleanly and the site works
exactly the same without this section; the team picker just stays
hidden.

When it's configured:

- A **team picker** appears next to the title, listing every team in the
  league (not just yours) — anyone in the league can view the tool from
  their own team's perspective. It defaults to whichever team's owner
  matches the `SWID`, and your choice persists in `localStorage`.
- Pitchers get a badge: **🔒 MINE** (blue) if they're on the selected
  team's roster, **★ FA** (purple) if they're not rostered by *any* team
  in the league. No badge if an opponent has them.
- Free-agent names are clickable, linking to ESPN Fantasy's "Add
  Players" page for your league, pre-filled with that player.
  **Known limitation:** on desktop web this link doesn't reliably jump
  straight to the specific player — ESPN's player card is a client-side
  modal with no real bookmarkable URL, so it lands on a nearby filtered
  list instead. It *does* work reliably from the **ESPN Fantasy iPhone
  app** (which treats the link as a Universal Link and opens the exact
  player), and since that's the majority of real usage, the link was
  left as-is rather than "fixed" in a way that would break the mobile
  case. Clicking through also requires being logged into ESPN.
- Ownership is fetched as of ESPN's **next** scoring period, not the
  current one — ESPN's "current period" roster view lags same-day
  transactions, so a manager who already added a pitcher for tomorrow's
  start wouldn't show up correctly if the app naively used "today."
- Free-agent vs. MLB-schedule name matching is accent- and
  case-insensitive (e.g. "Martín Pérez" matches "Martin Perez") to
  paper over spelling differences between the two data sources.

## Data sources

| Source | Used for |
|---|---|
| [MLB Stats API](https://statsapi.mlb.com) | Team batting stats (all windows), schedule/probable pitchers, pitcher handedness, team abbreviations, player name search |
| [ESPN scoreboard API](https://site.api.espn.com) | Fallback probable pitchers MLB hasn't posted yet |
| [ESPN Fantasy API](https://lm-api-reads.fantasy.espn.com) | League rosters and free agents (optional, requires secrets) |

None of these are officially documented public APIs — they're the same
endpoints the real MLB.com and ESPN Fantasy sites use internally, and
could change or break without notice.

## Architecture / repo layout

```
index.html                    the entire frontend — inline CSS + JS, no build step
fetch_stats.py                pulls MLB batting stats → data/stats.json
fetch_league.py               pulls ESPN Fantasy league data → data/league.json (optional)
sw.js                         service worker — see "Why the iPhone app can look stale" below
icons/                        favicon, apple-touch-icon, source art
.github/workflows/update.yml  hourly cron: runs both fetch scripts, commits if changed
data/stats.json               generated — committed to the repo by the workflow
data/league.json              generated — committed to the repo by the workflow (if secrets set)
```

Everything is client-rendered from those two JSON files — there's no
server-side templating or API proxy. `data/stats.json` and
`data/league.json` are fetched with a `?v=<timestamp>` cache-buster so
the browser always gets the latest commit.

### Why the iPhone "app" can look stale

GitHub Pages serves `index.html` with `Cache-Control: max-age=600` (10
minutes), which is normal for a static site — but an iOS **home-screen
web clip** (Add to Home Screen) can reuse a backgrounded WKWebView
process across app switches without ever revalidating past that TTL,
sometimes showing stale content indefinitely. `sw.js` is a minimal
service worker whose only job is to force every navigation to bypass
HTTP cache entirely (`cache: 'no-store'`) and take control immediately
via `skipWaiting`/`clients.claim`. It can't retroactively fix an
*already*-stale install, though — that needs one real fresh load to
register for the first time (force-quitting the home-screen app and
reopening it is usually enough; a hard refresh in Safari on the same URL
also works, since Safari and web clips share the same WebKit cache).

## Running the fetchers locally

```bash
pip install requests
python fetch_stats.py           # writes data/stats.json
```

For the optional fantasy sync:

```bash
export ESPN_LEAGUE_ID=1234567     # from the fantasy.espn.com URL
export ESPN_S2="..."              # espn_s2 cookie, logged into fantasy.espn.com
export ESPN_SWID="{...}"          # SWID cookie, including the braces
python fetch_league.py            # writes data/league.json
```

Then open `index.html` directly, or serve the folder locally
(`python -m http.server`) — either works since it's a static site.

## GitHub repo setup notes

- **Pages**: served from the `main` branch root. Repo must be public (or
  Pages upgraded) for the free tier.
- **Actions permissions**: Settings → Actions → General → Workflow
  permissions must be set to **Read and write**, or the hourly commit
  step will fail with a 401.
- **Secrets** (optional, for the fantasy integration): `ESPN_LEAGUE_ID`,
  `ESPN_S2`, `ESPN_SWID` under Settings → Secrets and variables →
  Actions.
- If editing `.github/workflows/*.yml` via `git push` locally, the
  Personal Access Token needs the **`workflow`** scope — without it,
  GitHub rejects the push outright (classic tokens: Settings → Developer
  settings → Personal access tokens → check the `workflow` box).
