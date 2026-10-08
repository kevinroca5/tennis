"""
OI (Overperformance Index) and Elo data store.
In production this is populated by running scripts/compute_oi.py
on the full match dataset. Here we expose the read API.
The computed data lives in data/oi_rankings.json and data/elo_history.json.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
OI_FILE = DATA_DIR / "oi_rankings.json"
ELO_FILE = DATA_DIR / "elo_history.json"
PLAYER_SEASONS_FILE = DATA_DIR / "player_seasons.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.error("Failed to load %s: %s", path, e)
    return default


# ── OI Rankings ──────────────────────────────────────────────────────────────
def get_oi_rankings(tour: str = "ATP", limit: int = 1000) -> List[Dict]:
    """Return OI rankings for tour. Falls back to demo data if file missing."""
    data = _load_json(OI_FILE, None)
    if data:
        key = tour.upper()
        rankings = data.get(key, [])
        return rankings[:limit]
    return _demo_oi_rankings(tour, limit)


# ── Elo History (quarterly, for line chart) ───────────────────────────────────
def get_oi_history(player_ids: Optional[List[str]] = None) -> Dict:
    """Return quarterly OI/Elo history. Optionally filter by player IDs."""
    data = _load_json(ELO_FILE, None)
    if data:
        if player_ids:
            return {k: v for k, v in data.items() if k in player_ids}
        return data
    return _demo_oi_history()


# ── Player Season Breakdown ───────────────────────────────────────────────────
def get_player_seasons(player_id: str) -> Optional[List[Dict]]:
    """Return season-by-season breakdown for a player (for the spotlight table)."""
    data = _load_json(PLAYER_SEASONS_FILE, None)
    if data:
        return data.get(player_id)
    # Demo fallback
    return _demo_player_seasons(player_id)


# ── Demo data ────────────────────────────────────────────────────────────────
def _demo_oi_rankings(tour: str, limit: int) -> List[Dict]:
    """Hardcoded demo OI rankings — replace with computed data in production."""
    if tour.upper() == "ATP":
        rows = [
            {"rank":1,"id":"alcaraz_c","name":"Carlos Alcaraz","country":"ESP","oi":+312.4,"oi_hard":+180.2,"oi_clay":+95.8,"oi_grass":+36.4,"elo":2184,"matches":318},
            {"rank":2,"id":"sinner_j","name":"Jannik Sinner","country":"ITA","oi":+298.7,"oi_hard":+210.5,"oi_clay":+52.1,"oi_grass":+36.1,"elo":2201,"matches":342},
            {"rank":3,"id":"zverev_a","name":"Alexander Zverev","country":"GER","oi":+241.3,"oi_hard":+130.4,"oi_clay":+88.9,"oi_grass":+22.0,"elo":2082,"matches":387},
            {"rank":4,"id":"fritz_t","name":"Taylor Fritz","country":"USA","oi":+198.6,"oi_hard":+162.3,"oi_clay":+18.4,"oi_grass":+17.9,"elo":1994,"matches":309},
            {"rank":5,"id":"medvedev_d","name":"Daniil Medvedev","country":"RUS","oi":+187.2,"oi_hard":+155.8,"oi_clay":+14.2,"oi_grass":+17.2,"elo":2041,"matches":398},
            {"rank":6,"id":"djokovic_n","name":"Novak Djokovic","country":"SRB","oi":+162.9,"oi_hard":+88.4,"oi_clay":+47.1,"oi_grass":+27.4,"elo":2112,"matches":287},
            {"rank":7,"id":"rublev_a","name":"Andrey Rublev","country":"RUS","oi":+124.5,"oi_hard":+78.2,"oi_clay":+38.9,"oi_grass":+7.4,"elo":1967,"matches":412},
            {"rank":8,"id":"ruud_c","name":"Casper Ruud","country":"NOR","oi":+98.3,"oi_hard":+32.1,"oi_clay":+58.4,"oi_grass":+7.8,"elo":1918,"matches":356},
            {"rank":9,"id":"hurkacz_h","name":"Hubert Hurkacz","country":"POL","oi":+87.6,"oi_hard":+62.4,"oi_clay":+8.2,"oi_grass":+17.0,"elo":1942,"matches":298},
            {"rank":10,"id":"dimitrov_g","name":"Grigor Dimitrov","country":"BUL","oi":+76.2,"oi_hard":+54.8,"oi_clay":+12.1,"oi_grass":+9.3,"elo":1892,"matches":276},
        ]
    else:
        rows = [
            {"rank":1,"id":"sabalenka_a","name":"Aryna Sabalenka","country":"BLR","oi":+287.3,"oi_hard":+198.4,"oi_clay":+54.2,"oi_grass":+34.7,"elo":2134,"matches":298},
            {"rank":2,"id":"swiatek_i","name":"Iga Świątek","country":"POL","oi":+264.8,"oi_hard":+112.4,"oi_clay":+128.6,"oi_grass":+23.8,"elo":2098,"matches":312},
            {"rank":3,"id":"gauff_c","name":"Coco Gauff","country":"USA","oi":+198.4,"oi_hard":+142.8,"oi_clay":+32.4,"oi_grass":+23.2,"elo":1987,"matches":284},
            {"rank":4,"id":"rybakina_e","name":"Elena Rybakina","country":"KAZ","oi":+176.2,"oi_hard":+98.6,"oi_clay":+28.4,"oi_grass":+49.2,"elo":2012,"matches":267},
            {"rank":5,"id":"paolini_j","name":"Jasmine Paolini","country":"ITA","oi":+142.8,"oi_hard":+82.4,"oi_clay":+48.6,"oi_grass":+11.8,"elo":1934,"matches":254},
        ]
    return rows[:limit]


def _demo_oi_history() -> Dict:
    """Demo quarterly OI history for 8 ATP + 4 WTA players."""
    labels = ["Q1'21","Q2'21","Q3'21","Q4'21","Q1'22","Q2'22","Q3'22","Q4'22",
              "Q1'23","Q2'23","Q3'23","Q4'23","Q1'24","Q2'24","Q3'24","Q4'24",
              "Q1'25","Q2'25","Q3'25","Q4'25","Q1'26","Q2'26","Q3'26"]
    return {
        "labels": labels,
        "series": {
            "alcaraz_c": [0,0,18,42,78,112,148,168,198,221,248,264,278,286,294,302,308,312,316,314,316,314,312],
            "sinner_j":  [12,24,38,54,72,95,118,142,165,188,210,228,244,258,270,280,288,294,298,296,298,297,299],
            "zverev_a":  [45,62,80,98,112,128,145,158,172,185,195,208,218,224,230,234,238,240,241,239,241,240,241],
            "fritz_t":   [8,15,28,38,52,68,82,96,108,120,132,142,152,162,170,178,184,188,194,196,196,197,199],
            "medvedev_d":[85,98,112,128,140,148,158,165,170,175,178,180,182,183,184,185,186,186,187,187,188,187,187],
            "djokovic_n":[120,132,140,148,152,155,158,158,160,160,161,161,162,162,162,163,163,162,163,162,163,163,163],
            "rublev_a":  [18,28,42,55,65,75,84,92,98,104,108,112,115,118,120,122,123,124,124,124,125,124,125],
            "ruud_c":    [5,12,22,35,48,58,66,72,78,82,86,89,91,93,95,96,97,98,98,97,98,98,98],
            "sabalenka_a":[22,38,55,72,92,112,135,155,175,195,215,232,248,260,270,278,283,286,287,285,287,286,287],
            "swiatek_i": [35,52,72,95,118,142,162,180,198,214,228,240,250,256,260,263,264,265,264,263,265,264,265],
            "gauff_c":   [2,8,18,30,45,62,80,98,115,130,148,162,172,180,186,192,195,197,198,196,198,197,198],
            "rybakina_e":[5,12,22,38,55,72,90,108,124,138,150,160,168,173,175,175,176,175,176,175,176,175,176],
        }
    }


def _demo_player_seasons(player_id: str) -> List[Dict]:
    """Demo season breakdown for a player."""
    season_data = {
        "alcaraz_c": [
            {"season":"2021","level":"ATP 250-500","matches":42,"avg_elo":1712,"start_elo":1645,"end_elo":1788,"oi":18.4},
            {"season":"2022","level":"ATP 250-Masters","matches":78,"avg_elo":1892,"start_elo":1788,"end_elo":2021,"oi":96.2},
            {"season":"2023","level":"Grand Slams+Masters","matches":85,"avg_elo":2048,"start_elo":2021,"end_elo":2112,"oi":124.8},
            {"season":"2024","level":"Grand Slams+Masters","matches":72,"avg_elo":2142,"start_elo":2112,"end_elo":2168,"oi":98.4},
            {"season":"2025","level":"Grand Slams+Masters","matches":41,"avg_elo":2178,"start_elo":2168,"end_elo":2184,"oi":42.2},
        ],
        "sinner_j": [
            {"season":"2021","level":"ATP 250-500","matches":58,"avg_elo":1748,"start_elo":1698,"end_elo":1812,"oi":24.2},
            {"season":"2022","level":"ATP 500-Masters","matches":82,"avg_elo":1924,"start_elo":1812,"end_elo":2042,"oi":108.4},
            {"season":"2023","level":"Grand Slams+Masters","matches":88,"avg_elo":2084,"start_elo":2042,"end_elo":2148,"oi":118.2},
            {"season":"2024","level":"Grand Slams+Masters","matches":78,"avg_elo":2162,"start_elo":2148,"end_elo":2189,"oi":82.6},
            {"season":"2025","level":"Grand Slams+Masters","matches":36,"avg_elo":2196,"start_elo":2189,"end_elo":2201,"oi":24.8},
        ],
    }
    # Return generic data if player not in demo set
    return season_data.get(player_id, [
        {"season":"2021","level":"ATP Tour","matches":48,"avg_elo":1720,"start_elo":1680,"end_elo":1760,"oi":22.0},
        {"season":"2022","level":"ATP Tour","matches":64,"avg_elo":1840,"start_elo":1760,"end_elo":1920,"oi":58.0},
        {"season":"2023","level":"ATP Tour","matches":72,"avg_elo":1950,"start_elo":1920,"end_elo":1980,"oi":78.0},
        {"season":"2024","level":"ATP Tour","matches":68,"avg_elo":2010,"start_elo":1980,"end_elo":2040,"oi":62.0},
        {"season":"2025","level":"ATP Tour","matches":32,"avg_elo":2055,"start_elo":2040,"end_elo":2068,"oi":28.0},
    ])
