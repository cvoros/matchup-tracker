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

SEASON = 2026
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


def main():
    league_id, espn_s2, swid = get_env()
    cookies = {"espn_s2": espn_s2, "SWID": swid}
    base_url = BASE.format(season=SEASON, lid=league_id)

    print("Fetching teams and rosters...")
    data = espn_get(base_url, cookies, params={"view": ["mTeam", "mRoster"]})
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

    # Ownership (mine / opponent / free agent) is derived in the UI from
    # these rosters — anyone not rostered by any team is a free agent.
    output = {
        "updated": date.today().strftime("%Y-%m-%d"),
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "defaultTeamId": default_team_id,
        "teams": teams,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/league.json", "w") as f:
        json.dump(output, f, indent=2)

    print("Wrote data/league.json")


if __name__ == "__main__":
    main()
