"""Tennis API service via RapidAPI (tennis-api-atp-wta-itf)."""
import httpx
import logging
from typing import Optional, List, Dict

from .config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://tennis-api-atp-wta-itf.p.rapidapi.com"
TIMEOUT = 10.0


def _headers() -> dict:
    return {
        "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
        "X-RapidAPI-Host": "tennis-api-atp-wta-itf.p.rapidapi.com",
    }


def _api_available() -> bool:
    return bool(settings.RAPIDAPI_KEY)


def _normalize_player(p: dict, tour: str) -> dict:
    """Normalize API response to a consistent schema."""
    player = p.get("player", p)
    return {
        "ranking": p.get("position", p.get("ranking")),
        "name": player.get("name", p.get("name", "")),
        "country": player.get("countryAcr", p.get("country", "")),
        "points": p.get("point", p.get("points", 0)),
        "player_id": player.get("id", p.get("player_id")),
    }


# ── Rankings ─────────────────────────────────────────────────────────────────
async def fetch_atp_rankings(limit: int = 100) -> List[Dict]:
    """Fetch live ATP rankings."""
    if not _api_available():
        return _demo_rankings("ATP", limit)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            all_players = []
            page = 1
            while len(all_players) < limit:
                r = await client.get(
                    f"{BASE_URL}/tennis/v2/atp/ranking/singles",
                    params={"pageSize": 100, "pageNo": page},
                    headers=_headers(),
                )
                r.raise_for_status()
                data = r.json()
                players = data.get("data", [])
                if not players:
                    break
                all_players.extend([_normalize_player(p, "ATP") for p in players])
                if not data.get("hasNextPage", False):
                    break
                page += 1
            return all_players[:limit]
        except Exception as e:
            logger.error("ATP rankings fetch failed: %s", e)
            return _demo_rankings("ATP", limit)


async def fetch_wta_rankings(limit: int = 50) -> List[Dict]:
    """Fetch live WTA rankings."""
    if not _api_available():
        return _demo_rankings("WTA", limit)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            all_players = []
            page = 1
            while len(all_players) < limit:
                r = await client.get(
                    f"{BASE_URL}/tennis/v2/wta/ranking/singles",
                    params={"pageSize": 100, "pageNo": page},
                    headers=_headers(),
                )
                r.raise_for_status()
                data = r.json()
                players = data.get("data", [])
                if not players:
                    break
                all_players.extend([_normalize_player(p, "WTA") for p in players])
                if not data.get("hasNextPage", False):
                    break
                page += 1
            return all_players[:limit]
        except Exception as e:
            logger.error("WTA rankings fetch failed: %s", e)
            return _demo_rankings("WTA", limit)


async def fetch_player_profile(player_id: str) -> Optional[Dict]:
    """Fetch player profile by ID."""
    if not _api_available():
        return None

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(
                f"{BASE_URL}/tennis/v2/atp/player/{player_id}",
                headers=_headers(),
            )
            r.raise_for_status()
            return r.json().get("data", {})
        except Exception as e:
            logger.error("Player profile fetch failed for %s: %s", player_id, e)
            return None


async def fetch_live_scores() -> List[Dict]:
    """Fetch today's matches: live + scheduled + recent results for ATP and WTA."""
    if not _api_available():
        return []

    from datetime import date
    today = date.today().isoformat()  # YYYY-MM-DD
    all_matches: List[Dict] = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Try all relevant endpoints and combine results
        endpoints = [
            (f"{BASE_URL}/tennis/v2/atp/live", {}),
            (f"{BASE_URL}/tennis/v2/wta/live", {}),
            (f"{BASE_URL}/tennis/v2/atp/fixtures", {}),
            (f"{BASE_URL}/tennis/v2/wta/fixtures", {}),
            (f"{BASE_URL}/tennis/v2/atp/results/{today}", {}),
            (f"{BASE_URL}/tennis/v2/wta/results/{today}", {}),
        ]

        seen_ids: set = set()
        for url, params in endpoints:
            try:
                r = await client.get(url, params=params, headers=_headers(), timeout=8.0)
                if r.status_code == 200:
                    data = r.json()
                    items = data if isinstance(data, list) else data.get("data", [])
                    if not isinstance(items, list):
                        items = []
                    for item in items:
                        mid = item.get("id") or item.get("matchId") or str(item)[:60]
                        if mid not in seen_ids:
                            seen_ids.add(mid)
                            all_matches.append(item)
                else:
                    logger.debug("Endpoint %s returned %s", url, r.status_code)
            except Exception as e:
                logger.debug("Endpoint %s failed: %s", url, e)

    logger.info("fetch_live_scores: collected %d matches total", len(all_matches))
    return all_matches


async def fetch_tournaments() -> List[Dict]:
    """Fetch upcoming/current tournaments."""
    if not _api_available():
        return _demo_tournaments()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(
                f"{BASE_URL}/tennis/v2/atp/tournaments",
                headers=_headers(),
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            return [
                {
                    "name": t.get("name", ""),
                    "location": t.get("city", t.get("country", "")),
                    "surface": t.get("court", {}).get("name", "") if isinstance(t.get("court"), dict) else "",
                    "category": t.get("rank", {}).get("name", "") if isinstance(t.get("rank"), dict) else "",
                    "start_date": t.get("startDate", ""),
                }
                for t in data
            ]
        except Exception as e:
            logger.error("Tournaments fetch failed: %s", e)
            return _demo_tournaments()


# ── Demo fallbacks (used when no API key is set) ─────────────────────────────
def _demo_rankings(tour: str, limit: int) -> List[Dict]:
    """Returns demo ranking data."""
    if tour == "ATP":
        players = [
            {"ranking": 1, "name": "Jannik Sinner", "country": "ITA", "points": 11330},
            {"ranking": 2, "name": "Carlos Alcaraz", "country": "ESP", "points": 9255},
            {"ranking": 3, "name": "Alexander Zverev", "country": "GER", "points": 6885},
            {"ranking": 4, "name": "Taylor Fritz", "country": "USA", "points": 5310},
            {"ranking": 5, "name": "Casper Ruud", "country": "NOR", "points": 4550},
            {"ranking": 6, "name": "Novak Djokovic", "country": "SRB", "points": 4320},
            {"ranking": 7, "name": "Andrey Rublev", "country": "RUS", "points": 4075},
            {"ranking": 8, "name": "Holger Rune", "country": "DEN", "points": 3520},
            {"ranking": 9, "name": "Grigor Dimitrov", "country": "BUL", "points": 3280},
            {"ranking": 10, "name": "Alex de Minaur", "country": "AUS", "points": 3155},
            {"ranking": 11, "name": "Stefanos Tsitsipas", "country": "GRE", "points": 2980},
            {"ranking": 12, "name": "Hubert Hurkacz", "country": "POL", "points": 2845},
        ]
    else:
        players = [
            {"ranking": 1, "name": "Aryna Sabalenka", "country": "BLR", "points": 10725},
            {"ranking": 2, "name": "Iga Swiatek", "country": "POL", "points": 9365},
            {"ranking": 3, "name": "Coco Gauff", "country": "USA", "points": 7085},
            {"ranking": 4, "name": "Elena Rybakina", "country": "KAZ", "points": 5920},
            {"ranking": 5, "name": "Jasmine Paolini", "country": "ITA", "points": 4810},
            {"ranking": 6, "name": "Barbora Krejcikova", "country": "CZE", "points": 4420},
            {"ranking": 7, "name": "Emma Navarro", "country": "USA", "points": 3960},
            {"ranking": 8, "name": "Jessica Pegula", "country": "USA", "points": 3750},
        ]
    return players[:limit]


def _demo_tournaments() -> List[Dict]:
    return [
        {"name": "China Open", "location": "Beijing", "surface": "Hard", "category": "WTA 1000", "start_date": "2025-09-30"},
        {"name": "Shanghai Masters", "location": "Shanghai", "surface": "Hard", "category": "ATP Masters 1000", "start_date": "2025-10-06"},
        {"name": "Vienna Open", "location": "Vienna", "surface": "Indoor Hard", "category": "ATP 500", "start_date": "2025-10-21"},
    ]
