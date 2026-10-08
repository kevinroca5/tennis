"""Predictions router — match predictions and upcoming fixtures."""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..services.auth import get_current_user
from ..services.model import predict_match, get_model_info
from ..services.tennis_api import fetch_tournaments, fetch_live_scores

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/predictions", tags=["predictions"])


class MatchFeatures(BaseModel):
    """Feature input for a match prediction."""
    # Player meta
    p1_name: str
    p2_name: str
    tournament: Optional[str] = None
    surface: Optional[str] = "Hard"
    round: Optional[str] = None

    # Core features (feats_v6)
    rank_diff: float = 0.0
    form_diff: float = 0.0
    elo_diff: float = 0.0
    elo_exp: float = 0.0
    surface_wr_diff: float = 0.0
    surface_wr_j1: float = 0.0
    surface_wr_j2: float = 0.0
    surface_enc: float = 0.0
    ace_diff: float = 0.0
    win_first_diff: float = 0.0
    win_second_diff: float = 0.0
    winners_diff: float = 0.0
    unforced_diff: float = 0.0
    bp_save_diff: float = 0.0
    estilo_j1: float = 0.0
    estilo_j2: float = 0.0
    fatiga_diff: float = 0.0
    sets_diff: float = 0.0
    h2h_diff: float = 0.0
    oi_diff: float = 0.0
    elo_Hard_diff: float = 0.0
    elo_Clay_diff: float = 0.0
    elo_Grass_diff: float = 0.0
    oi_Hard_diff: float = 0.0
    oi_Clay_diff: float = 0.0
    oi_Grass_diff: float = 0.0


@router.post("/predict")
async def predict(
    req: MatchFeatures,
    user: dict = Depends(get_current_user),
):
    """Run model prediction for a specific match."""
    features = req.model_dump(exclude={"p1_name", "p2_name", "tournament", "surface", "round"})
    # Encode surface for the model (LabelEncoder: Clay=0, Grass=1, Hard=2, I.hard=3)
    surf_map = {"Hard": 2, "Clay": 0, "Grass": 1, "I.hard": 3, "Indoor Hard": 3}
    features["surface_enc"] = surf_map.get(req.surface or "Hard", 2)
    # Determine tour from tournament name (rough heuristic — WTA if known WTA event)
    tour = "wta" if req.tournament and any(x in (req.tournament or "").upper()
                                           for x in ["WTA","WOMEN","LADIES"]) else "atp"
    result = predict_match(features, tour=tour)
    return {
        "p1_name": req.p1_name,
        "p2_name": req.p2_name,
        "tournament": req.tournament,
        "surface": req.surface,
        "round": req.round,
        **result,
    }


@router.get("/upcoming")
async def upcoming_predictions(
    user: dict = Depends(get_current_user),
):
    """Current tournament matches — live scores + upcoming fixtures."""
    live = []
    try:
        live = await fetch_live_scores()
        logger.info("upcoming_predictions: got %d matches from API", len(live))
    except Exception as e:
        logger.error("upcoming_predictions: fetch failed: %s", e)

    if live:
        predictions = []
        for m in live:
            # Normalize different possible schemas from the API
            # Schema A: homeTeam/awayTeam (common sports API pattern)
            p1 = m.get("homeTeam") or m.get("player1") or m.get("home") or m.get("p1") or {}
            p2 = m.get("awayTeam") or m.get("player2") or m.get("away") or m.get("p2") or {}

            def extract_name(obj):
                if isinstance(obj, dict):
                    return (obj.get("name") or obj.get("fullName") or
                            obj.get("shortName") or "")
                if isinstance(obj, str):
                    return obj
                return ""

            p1_name = extract_name(p1)
            p2_name = extract_name(p2)

            # Fallback: flat fields
            if not p1_name:
                p1_name = m.get("p1_name") or m.get("player1Name") or m.get("firstPlayer") or ""
            if not p2_name:
                p2_name = m.get("p2_name") or m.get("player2Name") or m.get("secondPlayer") or ""

            # Skip entries with no player names
            if not p1_name or not p2_name:
                logger.debug("Skipping match with no player names: %s", list(m.keys()))
                continue

            # Tournament name
            tournament = m.get("tournament") or m.get("event") or m.get("competition") or {}
            t_name = (tournament.get("name") or tournament.get("shortName") or ""
                      if isinstance(tournament, dict) else str(tournament))

            # Surface
            surface = m.get("surface") or m.get("court") or m.get("ground") or "Hard"
            if isinstance(surface, dict):
                surface = surface.get("name") or surface.get("type") or "Hard"

            # Round
            rnd = (m.get("round") or m.get("roundName") or m.get("round_name") or
                   m.get("stage") or "")
            if isinstance(rnd, dict):
                rnd = rnd.get("name") or ""

            # Status and score
            status_raw = m.get("status") or m.get("statusName") or m.get("state") or "scheduled"
            if isinstance(status_raw, dict):
                status_raw = status_raw.get("name") or "scheduled"
            score = m.get("score") or m.get("result") or m.get("scores") or ""
            if isinstance(score, dict):
                score = score.get("current") or score.get("display") or ""

            predictions.append({
                "tournament": t_name,
                "round": str(rnd),
                "surface": str(surface),
                "p1_name": p1_name,
                "p2_name": p2_name,
                "p1_win_prob": 0.5,
                "p2_win_prob": 0.5,
                "predicted_winner": 0,
                "confidence": 0.0,
                "model_pick": "",
                "p1_rank": m.get("p1_rank") or m.get("homeRank") or 0,
                "p2_rank": m.get("p2_rank") or m.get("awayRank") or 0,
                "p1_elo": 0,
                "p2_elo": 0,
                "status": str(status_raw).lower(),
                "score": str(score) if score else "",
            })
        if predictions:
            return {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "predictions": predictions,
                "source": "live",
            }

    # Fallback to demo data
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "predictions": _demo_predictions(),
        "source": "demo",
    }


@router.get("/live")
async def live_scores(
    user: dict = Depends(get_current_user),
):
    """Live match scores — raw data from all ATP/WTA endpoints."""
    scores = await fetch_live_scores()
    return {"count": len(scores), "live": scores}


@router.get("/debug")
async def debug_api(
    user: dict = Depends(get_current_user),
):
    """Debug endpoint — show raw API response and parsed matches."""
    from ..services.tennis_api import _api_available, _headers, BASE_URL, TIMEOUT
    import httpx
    from datetime import date

    if not _api_available():
        return {"error": "No RAPIDAPI_KEY configured"}

    today = date.today().isoformat()
    results = {}
    endpoints = [
        f"{BASE_URL}/tennis/v2/atp/live",
        f"{BASE_URL}/tennis/v2/wta/live",
        f"{BASE_URL}/tennis/v2/atp/fixtures",
        f"{BASE_URL}/tennis/v2/wta/fixtures",
        f"{BASE_URL}/tennis/v2/atp/results/{today}",
        f"{BASE_URL}/tennis/v2/wta/results/{today}",
    ]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for url in endpoints:
            key = url.replace(BASE_URL, "").lstrip("/")
            try:
                r = await client.get(url, headers=_headers())
                data = r.json()
                items = data if isinstance(data, list) else data.get("data", [])
                count = len(items) if isinstance(items, list) else "N/A"
                # Show first item structure only
                sample = items[0] if isinstance(items, list) and items else None
                results[key] = {
                    "status": r.status_code,
                    "count": count,
                    "sample_keys": list(sample.keys()) if isinstance(sample, dict) else sample,
                }
            except Exception as e:
                results[key] = {"error": str(e)}

    return {"today": today, "endpoints": results}


@router.get("/tournaments")
async def tournaments(
    user: dict = Depends(get_current_user),
):
    """Upcoming tournaments."""
    data = await fetch_tournaments()
    return {"tournaments": data}


@router.get("/model-info")
async def model_info(user: dict = Depends(get_current_user)):
    """Model metadata and feature list."""
    return get_model_info()


def _demo_predictions() -> list:
    return [
        {
            "tournament": "Shanghai Masters",
            "round": "QF",
            "surface": "Hard",
            "p1_name": "Jannik Sinner",
            "p2_name": "Grigor Dimitrov",
            "p1_win_prob": 0.782,
            "p2_win_prob": 0.218,
            "predicted_winner": 1,
            "confidence": 0.564,
            "model_pick": "Sinner",
            "p1_rank": 1,
            "p2_rank": 10,
            "p1_elo": 2201,
            "p2_elo": 1892,
        },
        {
            "tournament": "Shanghai Masters",
            "round": "QF",
            "surface": "Hard",
            "p1_name": "Carlos Alcaraz",
            "p2_name": "Taylor Fritz",
            "p1_win_prob": 0.641,
            "p2_win_prob": 0.359,
            "predicted_winner": 1,
            "confidence": 0.282,
            "model_pick": "Alcaraz",
            "p1_rank": 3,
            "p2_rank": 4,
            "p1_elo": 2184,
            "p2_elo": 1994,
        },
        {
            "tournament": "Shanghai Masters",
            "round": "QF",
            "surface": "Hard",
            "p1_name": "Alexander Zverev",
            "p2_name": "Andrey Rublev",
            "p1_win_prob": 0.598,
            "p2_win_prob": 0.402,
            "predicted_winner": 1,
            "confidence": 0.196,
            "model_pick": "Zverev",
            "p1_rank": 2,
            "p2_rank": 7,
            "p1_elo": 2082,
            "p2_elo": 1967,
        },
        {
            "tournament": "Shanghai Masters",
            "round": "QF",
            "surface": "Hard",
            "p1_name": "Daniil Medvedev",
            "p2_name": "Novak Djokovic",
            "p1_win_prob": 0.534,
            "p2_win_prob": 0.466,
            "predicted_winner": 1,
            "confidence": 0.068,
            "model_pick": "Medvedev",
            "p1_rank": 5,
            "p2_rank": 6,
            "p1_elo": 2041,
            "p2_elo": 2112,
        },
        {
            "tournament": "WTA Finals",
            "round": "RR",
            "surface": "Hard",
            "p1_name": "Aryna Sabalenka",
            "p2_name": "Iga Świątek",
            "p1_win_prob": 0.558,
            "p2_win_prob": 0.442,
            "predicted_winner": 1,
            "confidence": 0.116,
            "model_pick": "Sabalenka",
            "p1_rank": 1,
            "p2_rank": 2,
            "p1_elo": 2134,
            "p2_elo": 2098,
        },
        {
            "tournament": "WTA Finals",
            "round": "RR",
            "surface": "Hard",
            "p1_name": "Coco Gauff",
            "p2_name": "Elena Rybakina",
            "p1_win_prob": 0.512,
            "p2_win_prob": 0.488,
            "predicted_winner": 1,
            "confidence": 0.024,
            "model_pick": "Gauff",
            "p1_rank": 3,
            "p2_rank": 4,
            "p1_elo": 1987,
            "p2_elo": 2012,
        },
        {
            "tournament": "Vienna Open",
            "round": "SF",
            "surface": "Indoor Hard",
            "p1_name": "Alexander Zverev",
            "p2_name": "Holger Rune",
            "p1_win_prob": 0.664,
            "p2_win_prob": 0.336,
            "predicted_winner": 1,
            "confidence": 0.328,
            "model_pick": "Zverev",
            "p1_rank": 2,
            "p2_rank": 8,
            "p1_elo": 2082,
            "p2_elo": 1878,
        },
        {
            "tournament": "Vienna Open",
            "round": "SF",
            "surface": "Indoor Hard",
            "p1_name": "Taylor Fritz",
            "p2_name": "Hubert Hurkacz",
            "p1_win_prob": 0.521,
            "p2_win_prob": 0.479,
            "predicted_winner": 1,
            "confidence": 0.042,
            "model_pick": "Fritz",
            "p1_rank": 4,
            "p2_rank": 12,
            "p1_elo": 1994,
            "p2_elo": 1942,
        },
    ]
