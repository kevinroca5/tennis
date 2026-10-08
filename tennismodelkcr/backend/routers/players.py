"""Players router — player profiles, season breakdowns, Elo history."""
from fastapi import APIRouter, Depends, HTTPException, Query
from ..services.auth import get_current_user
from ..services.tennis_api import fetch_player_profile
from ..services.oi_store import get_player_seasons, get_oi_history

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("/{player_id}/profile")
async def player_profile(
    player_id: str,
    user: dict = Depends(get_current_user),
):
    """Full player profile — bio, ranking, surface stats."""
    profile = await fetch_player_profile(player_id)
    if not profile:
        # Return minimal demo profile
        return {
            "id": player_id,
            "name": player_id.replace("_", " ").title(),
            "country": "N/A",
            "ranking": None,
            "demo": True,
        }
    return profile


@router.get("/{player_id}/seasons")
async def player_seasons(
    player_id: str,
    user: dict = Depends(get_current_user),
):
    """Season-by-season breakdown: matches, avg Elo, start/end Elo, OI change."""
    seasons = get_player_seasons(player_id)
    if not seasons:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"player_id": player_id, "seasons": seasons}


@router.get("/{player_id}/oi-history")
async def player_oi_history(
    player_id: str,
    user: dict = Depends(get_current_user),
):
    """Quarterly OI history for a single player."""
    all_history = get_oi_history([player_id])
    data = all_history.get("series", {}).get(player_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Player OI history not found")
    return {
        "player_id": player_id,
        "labels": all_history.get("labels", []),
        "oi": data,
    }
