"""
Fetches ESPN Fantasy league data and writes data/league.json.

Required env vars:
  ESPN_LEAGUE_ID  — league ID from the fantasy URL
  ESPN_S2         — espn_s2 cookie value
  ESPN_SWID       — SWID cookie value (used to identify your team)

If any env var is missing the script exits 0 silently so the
workflow still passes for users who haven't configured it.
"""

import json
import os
import sys
import requests
from datetime import date

SEASON = 2026
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{season}/segments/0/leagues/{lid}"
FA_LIMIT = 50  # how many FA/waiver SPs to include


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


def find_my_team(teams, swid):
    """Return the team whose primaryOwner matches the SWID."""
    for t in teams:
        if t.get("primaryOwner") == swid:
            return t
    return None


def fetch_roster_pitchers(base_url, cookies, my_team_id):
    """Return list of SP/RP on my roster with mlbId."""
    data = espn_get(base_url, cookies, params={"view": "mRoster"})
    my_team = next((t for t in data["teams"] if t["id"] == my_team_id), None)
    if not my_team:
        return []

    pitchers = []
    for entry in my_team["roster"]["entries"]:
        player = entry["playerPoolEntry"]["player"]
        pos_id = player.get("defaultPositionId")
        if pos_id in (1, 11):  # 1=SP, 11=RP
            pitchers.append({
                "name": player["fullName"],
                "mlbId": player["id"],
                "positionId": pos_id,
            })
    return pitchers


def fetch_free_agents(base_url, cookies):
    """Return FA/waiver SPs sorted by % owned descending."""
    data = espn_get(
        base_url,
        cookies,
        params={"view": "kona_player_info"},
        headers={"x-fantasy-filter": json.dumps({
            "players": {
                "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                "filterSlotIds": {"value": [14]},  # SP slot
                "limit": FA_LIMIT,
                "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
            }
        })},
    )
    result = []
    for entry in data.get("players", []):
        player = entry.get("player", {})
        name = player.get("fullName")
        mlb_id = player.get("id")
        if not name or not mlb_id:
            continue
        result.append({
            "name": name,
            "mlbId": mlb_id,
            "status": entry.get("status", "FREEAGENT"),
        })
    return result


def main():
    league_id, espn_s2, swid = get_env()
    cookies = {"espn_s2": espn_s2, "SWID": swid}
    base_url = BASE.format(season=SEASON, lid=league_id)

    print("Fetching league teams...")
    team_data = espn_get(base_url, cookies, params={"view": "mTeam"})
    teams = team_data["teams"]

    my_team = find_my_team(teams, swid)
    if not my_team:
        print(f"Could not find team for SWID {swid} — check ESPN_SWID.")
        sys.exit(1)

    my_team_id = my_team["id"]
    print(f"My team: [{my_team_id}] {my_team['name']} ({my_team['abbrev']})")

    print("Fetching roster...")
    roster = fetch_roster_pitchers(base_url, cookies, my_team_id)
    print(f"  {len(roster)} pitchers on roster")

    print("Fetching free agents...")
    free_agents = fetch_free_agents(base_url, cookies)
    print(f"  {len(free_agents)} FA/waiver SPs")

    output = {
        "updated": date.today().strftime("%Y-%m-%d"),
        "myTeamId": my_team_id,
        "myTeamName": my_team["name"],
        "myTeamAbbr": my_team["abbrev"],
        "roster": roster,
        "freeAgents": free_agents,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/league.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote data/league.json")


if __name__ == "__main__":
    main()
