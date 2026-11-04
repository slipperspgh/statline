"""Builds data/nfl.json for the StatLine page from free nflverse data.

Run: python build_data.py
Needs: pip install nflreadpy pandas pyarrow
"""
import json
import os
from datetime import date, datetime, timezone

import nflreadpy as nfl
import pandas as pd

today = date.today()
SEASON = today.year if today.month >= 3 else today.year - 1
HISTORY = [SEASON - 2, SEASON - 1, SEASON]   # seasons used for matchup history
SERIES_SEASONS = [SEASON - 3, SEASON - 2, SEASON - 1, SEASON]


def pick(df, *names):
    """Return the first column name that exists (nflverse renamed some columns)."""
    for n in names:
        if n in df.columns:
            return n
    raise KeyError(f"None of {names} found in columns")


# ---------- Load data ----------
sched = nfl.load_schedules(SERIES_SEASONS).to_pandas()
weekly = nfl.load_player_stats(HISTORY).to_pandas()

TEAM = pick(weekly, "recent_team", "team")
NAME = pick(weekly, "player_display_name", "player_name")
OPP = "opponent_team"
if "season_type" in weekly.columns:
    weekly = weekly[weekly["season_type"] == "REG"]
for c in ["rushing_yards", "rushing_tds", "receiving_yards", "receiving_tds",
          "receptions", "targets", "passing_yards", "passing_tds"]:
    if c not in weekly.columns:
        weekly[c] = 0
    weekly[c] = weekly[c].fillna(0)
weekly["rb_tds"] = weekly["rushing_tds"] + weekly["receiving_tds"]

cur = weekly[weekly["season"] == SEASON]
games_played = cur.groupby(OPP)["week"].nunique()   # games each defense has faced


# ---------- Defense rankings (1 = allows the most) ----------
CATEGORIES = [
    ("Passing yards allowed to QBs", "QB", "passing_yards"),
    ("Passing touchdowns allowed to QBs", "QB", "passing_tds"),
    ("Rushing yards allowed to RBs", "RB", "rushing_yards"),
    ("Touchdowns allowed to RBs", "RB", "rb_tds"),
    ("Targets allowed to WRs", "WR", "targets"),
    ("Catches allowed to WRs", "WR", "receptions"),
    ("Receiving yards allowed to WRs", "WR", "receiving_yards"),
    ("Touchdowns allowed to WRs", "WR", "receiving_tds"),
    ("Receiving yards allowed to TEs", "TE", "receiving_yards"),
    ("Touchdowns allowed to TEs", "TE", "receiving_tds"),
]

defense = {}   # team -> list of [label, "x.x/game", rank]
for label, pos, col in CATEGORIES:
    total = cur[cur["position"] == pos].groupby(OPP)[col].sum()
    per_game = (total / games_played).dropna()
    ranks = per_game.rank(ascending=False, method="min").astype(int)
    for team in per_game.index:
        defense.setdefault(team, []).append(
            [label, f"{per_game[team]:.1f}/game", int(ranks[team])]
        )


# ---------- Upcoming games ----------
upcoming = sched[(sched["season"] == SEASON) & (sched["home_score"].isna())]
games_out = []
next_week = None
if not upcoming.empty:
    next_week = int(upcoming["week"].min())
    upcoming = upcoming[upcoming["week"] == next_week]


# ---------- Injuries ----------
try:
    INJ = nfl.load_injuries([SEASON]).to_pandas()
except Exception as e:
    print("Could not load injuries:", e)
    INJ = pd.DataFrame(columns=["team", "week", "report_status", "full_name", "position"])


def injuries_for(team):
    inj = INJ[(INJ["team"] == team) & (INJ["week"] == next_week)]
    inj = inj[inj["report_status"].isin(["Out", "Doubtful", "Questionable"])]
    rows = []
    for _, r in inj.iterrows():
        rows.append([r["full_name"], r["position"], r["report_status"],
                     str(r.get("report_primary_injury") or "undisclosed").lower()])
    return rows[:8]


# ---------- Past meetings ----------
def series(a, b):
    s = sched[((sched["home_team"] == a) & (sched["away_team"] == b)) |
              ((sched["home_team"] == b) & (sched["away_team"] == a))]
    s = s[s["home_score"].notna()].sort_values("gameday", ascending=False).head(3)
    meetings, wins_a = [], 0
    for _, g in s.iterrows():
        hs, as_ = int(g["home_score"]), int(g["away_score"])
        winner = g["home_team"] if hs > as_ else g["away_team"]
        wins_a += winner == a
        meetings.append([f"{int(g['season'])}, Week {int(g['week'])}",
                         f"{g['home_team']} {hs}, {g['away_team']} {as_}"])
    n = len(meetings)
    summary = f"{a} won {wins_a} of the last {n}" if n else "No recent meetings"
    return {"summary": summary, "meetings": meetings}


# ---------- Player history vs this opponent ----------
KEY = [("QB", "passing_yards", "pass yds"), ("RB", "rushing_yards", "rush yds"),
       ("WR", "receiving_yards", "rec yds")]


def history(team, opp):
    out = []
    mine = cur[cur[TEAM] == team]
    for pos, col, label in KEY:
        top = mine[mine["position"] == pos].groupby(NAME)[col].sum()
        if top.empty:
            continue
        name = top.idxmax()
        h = weekly[(weekly[NAME] == name) & (weekly[OPP] == opp)]
        if len(h):
            out.append([name, f"{len(h)} games", f"{h[col].mean():.0f} {label}/game"])
    return out


for _, g in upcoming.iterrows():
    a, h = g["away_team"], g["home_team"]
    try:
        when = f"{pd.to_datetime(g['gameday']):%A} {g.get('gametime', '')}".strip()
    except Exception:
        when = ""
    games_out.append({
        "away": a, "home": h, "when": when,
        "defense": {"away": defense.get(a, []), "home": defense.get(h, [])},
        "injuries": {"away": injuries_for(a), "home": injuries_for(h)},
        "series": series(a, h),
        "history": {"away": history(a, h), "home": history(h, a)},
    })

os.makedirs("data", exist_ok=True)
with open("data/nfl.json", "w") as f:
    json.dump({
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "season": SEASON, "week": next_week, "games": games_out,
    }, f, indent=1)
print(f"Wrote {len(games_out)} games for season {SEASON}, week {next_week}")
