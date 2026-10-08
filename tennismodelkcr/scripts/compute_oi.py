"""
scripts/compute_oi.py
=====================
Run this script to compute OI rankings and Elo history from your
match dataset and save the results to data/ for the API to serve.

Usage:
    python scripts/compute_oi.py --matches data/matches.csv --output data/

The script expects a CSV with columns:
    player1_id, player2_id, winner (1 or 2), odds_1, odds_2, surface, date

It produces:
    data/oi_rankings.json     — OI leaderboard (ATP + WTA)
    data/elo_history.json     — Quarterly OI history per player
    data/player_seasons.json  — Season breakdown per player
"""
import argparse
import json
import math
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ── OI computation ────────────────────────────────────────────────────────────
K = 20  # OI decay constant

def implied_prob(odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if odds <= 1.0:
        return 0.99
    return 1.0 / odds


def compute_oi(matches_df: pd.DataFrame) -> dict:
    """Compute OI per player per surface and cumulative quarterly."""
    oi = defaultdict(float)
    oi_surface = defaultdict(lambda: defaultdict(float))
    oi_quarterly = defaultdict(list)  # player_id -> list of (quarter, oi_snapshot)

    matches_df = matches_df.sort_values('date')

    for _, row in matches_df.iterrows():
        p1, p2 = row['player1_id'], row['player2_id']
        winner = int(row['winner'])
        o1, o2 = float(row['odds_1']), float(row['odds_2'])
        surface = str(row['surface']).capitalize()

        p1_implied = implied_prob(o1)
        p2_implied = implied_prob(o2)

        result_p1 = 1.0 if winner == 1 else 0.0
        result_p2 = 1.0 if winner == 2 else 0.0

        oi[p1] += K * (result_p1 - p1_implied)
        oi[p2] += K * (result_p2 - p2_implied)

        oi_surface[p1][surface] += K * (result_p1 - p1_implied)
        oi_surface[p2][surface] += K * (result_p2 - p2_implied)

    return {
        'total': dict(oi),
        'surface': {k: dict(v) for k, v in oi_surface.items()},
    }


def build_quarterly_history(matches_df: pd.DataFrame) -> dict:
    """Build cumulative OI per player per quarter."""
    matches_df = matches_df.copy()
    matches_df['date'] = pd.to_datetime(matches_df['date'])
    matches_df['quarter'] = matches_df['date'].dt.to_period('Q')

    quarters = sorted(matches_df['quarter'].unique())
    labels = [str(q) for q in quarters]

    players = set(matches_df['player1_id'].tolist() + matches_df['player2_id'].tolist())
    cumulative = defaultdict(float)
    history = defaultdict(list)

    for q in quarters:
        q_matches = matches_df[matches_df['quarter'] == q]
        for _, row in q_matches.iterrows():
            p1, p2 = row['player1_id'], row['player2_id']
            winner = int(row['winner'])
            o1, o2 = float(row['odds_1']), float(row['odds_2'])

            p1_implied = implied_prob(o1)
            p2_implied = implied_prob(o2)

            result_p1 = 1.0 if winner == 1 else 0.0
            result_p2 = 1.0 if winner == 2 else 0.0

            cumulative[p1] += K * (result_p1 - p1_implied)
            cumulative[p2] += K * (result_p2 - p2_implied)

        for pid in players:
            history[pid].append(round(cumulative[pid], 1))

    return {'labels': labels, 'series': dict(history)}


def build_player_seasons(matches_df: pd.DataFrame, elo: dict) -> dict:
    """Build season breakdown per player."""
    matches_df = matches_df.copy()
    matches_df['date'] = pd.to_datetime(matches_df['date'])
    matches_df['year'] = matches_df['date'].dt.year

    seasons = defaultdict(list)
    oi_cumulative = defaultdict(float)

    for year in sorted(matches_df['year'].unique()):
        year_df = matches_df[matches_df['year'] == year]
        players_this_year = set(year_df['player1_id'].tolist() + year_df['player2_id'].tolist())

        oi_start = dict(oi_cumulative)
        for _, row in year_df.iterrows():
            p1, p2 = row['player1_id'], row['player2_id']
            winner = int(row['winner'])
            o1, o2 = float(row['odds_1']), float(row['odds_2'])
            r1 = 1.0 if winner == 1 else 0.0
            r2 = 1.0 if winner == 2 else 0.0
            oi_cumulative[p1] += K * (r1 - implied_prob(o1))
            oi_cumulative[p2] += K * (r2 - implied_prob(o2))

        for pid in players_this_year:
            player_matches = year_df[
                (year_df['player1_id'] == pid) | (year_df['player2_id'] == pid)
            ]
            n_matches = len(player_matches)
            oi_change = oi_cumulative[pid] - oi_start.get(pid, 0.0)
            seasons[pid].append({
                'season': str(year),
                'level': 'ATP Tour',
                'matches': n_matches,
                'avg_elo': elo.get(pid, {}).get(str(year), 1800),
                'start_elo': elo.get(pid, {}).get(f'{year}_start', 1800),
                'end_elo': elo.get(pid, {}).get(f'{year}_end', 1800),
                'oi': round(oi_change, 1),
            })

    return dict(seasons)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--matches', default='data/matches.csv')
    parser.add_argument('--output', default='data/')
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading matches from {args.matches}…")
    df = pd.read_csv(args.matches)
    print(f"  {len(df)} matches loaded")

    print("Computing OI…")
    oi_data = compute_oi(df)

    print("Building quarterly history…")
    quarterly = build_quarterly_history(df)

    # Save
    (out / 'elo_history.json').write_text(json.dumps(quarterly, indent=2))
    print(f"  → data/elo_history.json")

    print("Done! Next: update data/oi_rankings.json with player metadata (name, country, elo).")
    print("The OI totals are in oi_data['total'] and oi_data['surface'].")
