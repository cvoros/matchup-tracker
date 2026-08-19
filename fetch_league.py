"""
Fetches ESPN Fantasy league data and writes data/league.json.

Required env vars:
  ESPN_LEAGUE_ID  — league ID from the fantasy URL
  ESPN_S2         — espn_s2 cookie value
  ESPN_SWID       — SWID cookie value (used to pick the default team)

If any env var is missing the script exits 0 silently so the
workflow still passes for users who haven't configured it.

Privacy: output contains team names/abbrevs/rosters only — no owner
names, SWIDs, or member info.
"""

import json
import os
import sys
import requests
from datetime import date, datetime, timezone

# MLB seasons never span a calendar-year boundary, so "the season" is
# always just whatever year it currently is — no manual bump needed.
# (If ESPN issues a new league ID on renewal, ESPN_LEAGUE_ID still needs
# updating by hand — see README "Start of season" checklist.)
SEASON = date.today().year
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{lid}"


def get_env():
    lid  = os.environ.get("ESPN_LEAGUE_ID")
    s2   = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")
    if not all([lid, s2, swid]):
        print("ESPN env vars not set — skipping league fetch.")
        sys.exit(0)
    return int(lid), s2, swid


def espn_get(url, cookies, params=None, headers=None):
    r = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=30)
    r.raise_for_status()
    return r.json()


def extract_pitchers(team) -> list[dict]:
    """SP/RP entries from a team's roster. IDs are ESPN player IDs."""
    pitchers = []
    for entry in team.get("roster", {}).get("entries", []):
        player = entry["playerPoolEntry"]["player"]
        pos_id = player.get("defaultPositionId")
        if pos_id in (1, 11):  # 1=SP, 11=RP
            pitchers.append({
                "name": player["fullName"],
                "espnId": player["id"],
                "positionId": pos_id,
            })
    return pitchers


def fetch_fa_pitcher_ids(base_url, cookies) -> list[dict]:
    """FA/waiver pitchers (SP + RP eligible) as {name, espnId} — used only
    to hyperlink FA names to their ESPN fantasy player page. Badge
    determination is roster-derived and does not depend on this list.
    Slots 14=SP, 15=RP; some openers/bulk arms are RP-eligible in ESPN
    but start games, so both slots are needed to cover every pitcher
    that can appear as a probable starter. ~1,900 exist league-wide;
    2,500 leaves headroom."""
    data = espn_get(
        base_url,
        cookies,
        params={"view": "kona_player_info"},
        headers={"x-fantasy-filter": json.dumps({
            "players": {
                "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                "filterSlotIds": {"value": [14, 15]},
                "limit": 2500,
                "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
            }
        })},
    )
    out = []
    for entry in data.get("players", []):
        player = entry.get("player", {})
        name, pid = player.get("fullName"), player.get("id")
        if name and pid:
            out.append({"name": name, "espnId": pid})
    return out


def fetch_league_data(league_id, cookies):
    """Does the actual ESPN calls. Raised exceptions (expired cookies,
    league not found, network issues, etc.) are handled by the caller."""
    base_url = BASE.format(season=SEASON, lid=league_id)
    swid = cookies["SWID"]

    # ESPN returns rosters as of a given scoring period. The default
    # (current) period lags behind pending moves — managers add pitchers
    # for upcoming starts that only show up in the *next* period. Fetch
    # that next period so ownership reflects the latest roster intent.
    print("Fetching league metadata...")
    meta = espn_get(base_url, cookies, params={"view": "mTeam"})
    latest = meta.get("status", {}).get("latestScoringPeriod") \
        or meta.get("scoringPeriodId", 0)
    next_period = latest + 1
    print(f"  latest scoring period {latest}, fetching rosters as of {next_period}")

    print("Fetching teams and rosters...")
    data = espn_get(base_url, cookies,
                    params={"view": ["mTeam", "mRoster"], "scoringPeriodId": next_period})
    teams_raw = data["teams"]

    default_team_id = None
    teams = []
    for t in teams_raw:
        if t.get("primaryOwner") == swid:
            default_team_id = t["id"]
        teams.append({
            "id": t["id"],
            "name": t.get("name", ""),
            "abbrev": t.get("abbrev", ""),
            "pitchers": extract_pitchers(t),
        })

    print(f"  {len(teams)} teams, default team id: {default_team_id}")

    print("Fetching free-agent SP ids (for name links)...")
    free_agents = fetch_fa_pitcher_ids(base_url, cookies)
    print(f"  {len(free_agents)} FA/waiver SP ids")

    return default_team_id, teams, free_agents


def main():
    league_id, espn_s2, swid = get_env()
    cookies = {"espn_s2": espn_s2, "SWID": swid}

    # A broken ESPN session (expired cookie, league gone/renewed under a
    # new ID, ESPN outage, etc.) shouldn't be a hard failure — treat it
    # the same as "not configured" so it can't block the stats.json
    # commit in the same workflow run. See README "Start of season"
    # checklist for how to notice and fix an actually-expired session.
    try:
        default_team_id, teams, free_agents = fetch_league_data(league_id, cookies)
    except requests.exceptions.RequestException as e:
        print(f"ESPN league fetch failed ({e}) — leaving existing "
              f"data/league.json untouched. Cookies may have expired; "
              f"see README.")
        sys.exit(0)

    # Ownership (mine / opponent / free agent) is derived in the UI from
    # the rosters — anyone not rostered by any team is a free agent. The
    # freeAgents list is only a name->espnId lookup for hyperlinking.
    output = {
        "updated": date.today().strftime("%Y-%m-%d"),
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leagueId": league_id,
        "defaultTeamId": default_team_id,
        "teams": teams,
        "freeAgents": free_agents,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/league.json", "w") as f:
        json.dump(output, f, indent=2)

    print("Wrote data/league.json")


if __name__ == "__main__":
    main()
