import json
import os
import requests
from datetime import date, timedelta

SEASON = 2026
BASE = "https://statsapi.mlb.com/api/v1/teams/stats"
TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1&activeStatus=Y"


def fetch_abbr_map() -> dict:
    """Returns {teamId: abbreviation} for all active MLB teams."""
    r = requests.get(TEAMS_URL, timeout=30)
    r.raise_for_status()
    return {t["id"]: t["abbreviation"] for t in r.json()["teams"]}

# Weighted score per game (from the streaming pitcher's perspective):
#   K/G  × +1.0  (batter Ks = outs, good for pitcher)
#   H/G  × -1.0  (hits hurt)
#   BB/G × -0.5  (walks hurt, less than hits)
#   R/G  × -2.0  (runs are the biggest fantasy damage)
# Higher score = better matchup for streaming pitcher
WEIGHTS = {"kpg": 1.0, "hpg": -1.0, "bbpg": -1.0, "rpg": -2.0}


def fetch_stats(params: dict) -> list[dict]:
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["stats"][0]["splits"]


def extract_rows(splits: list[dict], abbr_map: dict) -> list[dict]:
    rows = []
    for s in splits:
        stat = s["stat"]
        gp = int(stat.get("gamesPlayed", 0))
        if gp == 0:
            continue
        tid = s["team"]["id"]
        rows.append(
            {
                "team": s["team"]["name"],
                "abbr": abbr_map.get(tid, s["team"]["name"][:3].upper()),
                "teamId": tid,
                "gp": gp,
                "runs": int(stat.get("runs", 0)),
                "ks": int(stat.get("strikeOuts", 0)),
                "hits": int(stat.get("hits", 0)),
                "bb": int(stat.get("baseOnBalls", 0)),
            }
        )
    return rows


def compute_scores(rows: list[dict]) -> list[dict]:
    results = []
    for row in rows:
        gp = row["gp"]
        rpg  = row["runs"] / gp
        kpg  = row["ks"]   / gp
        hpg  = row["hits"] / gp
        bbpg = row["bb"]   / gp

        score = (
            kpg  * WEIGHTS["kpg"]  +
            hpg  * WEIGHTS["hpg"]  +
            bbpg * WEIGHTS["bbpg"] +
            rpg  * WEIGHTS["rpg"]
        )

        results.append(
            {
                "team":  row["team"],
                "abbr":  row["abbr"],
                "teamId": row["teamId"],
                "rpg":   round(rpg,  2),
                "kpg":   round(kpg,  2),
                "hpg":   round(hpg,  2),
                "bbpg":  round(bbpg, 2),
                "score": round(score, 2),
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


def build_window(params: dict, abbr_map: dict) -> list[dict]:
    splits = fetch_stats(params)
    rows = extract_rows(splits, abbr_map)
    return compute_scores(rows)


def main():
    today = date.today()
    common = dict(season=SEASON, sportId=1, group="hitting", gameType="R")

    season_params = {**common, "stats": "season"}
    last30_params = {
        **common,
        "stats": "byDateRange",
        "startDate": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        "endDate": today.strftime("%Y-%m-%d"),
    }
    last15_params = {
        **common,
        "stats": "byDateRange",
        "startDate": (today - timedelta(days=15)).strftime("%Y-%m-%d"),
        "endDate": today.strftime("%Y-%m-%d"),
    }

    print("Fetching team abbreviations...")
    abbr_map = fetch_abbr_map()

    print("Fetching full season stats...")
    season = build_window(season_params, abbr_map)
    print("Fetching last 30 days stats...")
    last30 = build_window(last30_params, abbr_map)
    print("Fetching last 15 days stats...")
    last15 = build_window(last15_params, abbr_map)

    output = {
        "updated": today.strftime("%Y-%m-%d"),
        "season": season,
        "last30": last30,
        "last15": last15,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/stats.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote data/stats.json ({len(season)} teams)")


if __name__ == "__main__":
    main()
