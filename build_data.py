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


# ---------- Defense rankings (1 = allows
