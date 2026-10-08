"""Rankings router — OI rankings, ATP/WTA live rankings."""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..services.auth import get_current_user
from ..services.tennis_api import fetch_atp_rankings, fetch_wta_rankings
from ..services.oi_store import get_oi_rankings, get_oi_history

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


def _live_to_oi_format(players: list, tour: str) -> list:
    """Convert live API ranking data to the OI table format the frontend expects."""
    result = []
    for p in players:
        rank = p.get("ranking") or 0
        points = p.get("points") or 0
        name = p.get("name", "")
        country = p.get("country", "")
        pid = p.get("player_id")
        # Generate a stable id from name if no player_id
        pid_str = str(pid) if pid else name.lower().replace(" ", "_")
        # Estimate Elo from points (rough mapping: top players ~2100-2200)
        elo = max(1500, 2200 - int(rank * 8))
        result.append({
            "rank": rank,
            "id": pid_str,
            "name": name,
            "country": country,
            "points": points,
            "oi": 0.0,
            "oi_hard": 0.0,
            "oi_clay": 0.0,
            "oi_grass": 0.0,
            "elo": elo,
            "matches": 0,
        })
    return result


@router.get("/oi")
async def oi_rankings(
    tour: str = Query("ATP", pattern="^(ATP|WTA)$"),
    limit: int = Query(1000, ge=1, le=2000),
    user: dict = Depends(get_current_user),
):
    """OI rankings from computed data (oi_rankings.json). 816 ATP + 427 WTA players."""
    return {
        "tour": tour,
        "rankings": get_oi_rankings(tour, limit),
        "meta": {
            "description": "OI = cumulative sum of K*(actual - implied_prob_from_odds)",
            "period": "2024-2026",
        },
    }


@router.get("/oi/history")
async def oi_history(
    user: dict = Depends(get_current_user),
):
    """Quarterly OI history for all tracked players (for the OI Breakdown chart)."""
    return get_oi_history()


@router.get("/atp")
async def atp_rankings(
    limit: int = Query(100, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Live ATP rankings from RapidAPI (or demo data if no API key)."""
    data = await fetch_atp_rankings(limit)
    return {"tour": "ATP", "rankings": data}


@router.get("/wta")
async def wta_rankings(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """Live WTA rankings from RapidAPI (or demo data if no API key)."""
    data = await fetch_wta_rankings(limit)
    return {"tour": "WTA", "rankings": data}
