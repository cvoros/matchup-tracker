import json
import requests
from datetime import date, timedelta

SEASON = 2026
BASE = "https://statsapi.mlb.com/api/v1/teams/stats"


def fetch_stats(params: dict) -> list[dict]:
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json()["teamStats"][0]["splits"]


def extract_rows(splits: list[dict]) -> list[dict]:
    rows = []
    for s in splits:
        stat = s["stat"]
        gp = int(stat.get("gamesPlayed", 0))
        if gp == 0:
            continue
        rows.append(
            {
                "team": s["team"]["name"],
                "gp": gp,
                "runs": int(stat.get("runs", 0)),
                "ks": int(stat.get("strikeOuts", 0)),
            }
        )
    return rows


def rank_and_score(rows: list[dict]) -> list[dict]:
    # R/G: lower = better matchup → rank 30 = fewest runs = best
    sorted_rpg = sorted(rows, key=lambda x: x["rpg"], reverse=True)
    r_rank_map = {r["team"]: i + 1 for i, r in enumerate(sorted_rpg)}

    # K/G: higher = better matchup → rank 30 = most Ks = best
    sorted_kpg = sorted(rows, key=lambda x: x["kpg"])
    k_rank_map = {r["team"]: i + 1 for i, r in enumerate(sorted_kpg)}

    results = []
    for row in rows:
        rr = r_rank_map[row["team"]]
        kr = k_rank_map[row["team"]]
        results.append(
            {
                "team": row["team"],
                "rpg": round(row["rpg"], 2),
                "kpg": round(row["kpg"], 2),
                "r_rank": rr,
                "k_rank": kr,
                "composite": round((rr + kr) / 2, 1),
            }
        )

    results.sort(key=lambda x: x["composite"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


def build_window(params: dict) -> list[dict]:
    splits = fetch_stats(params)
    rows = extract_rows(splits)
    for row in rows:
        row["rpg"] = row["runs"] / row["gp"]
        row["kpg"] = row["ks"] / row["gp"]
    return rank_and_score(rows)


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

    print("Fetching full season stats...")
    season = build_window(season_params)
    print("Fetching last 30 days stats...")
    last30 = build_window(last30_params)
    print("Fetching last 15 days stats...")
    last15 = build_window(last15_params)

    output = {
        "updated": today.strftime("%Y-%m-%d"),
        "season": season,
        "last30": last30,
        "last15": last15,
    }

    with open("data/stats.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote data/stats.json ({len(season)} teams)")


if __name__ == "__main__":
    main()
