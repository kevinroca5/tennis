"""ML model service — loads tennis_model_v3.pkl (ATP) and tennis_model_wta.pkl (WTA)."""
import numpy as np
import pandas as pd
from pathlib import Path
import logging
import pickle

logger = logging.getLogger(__name__)

# Feature order must match training exactly (feats_v6, 26 features)
FEATS_V6 = [
    'rank_diff', 'form_diff', 'elo_diff', 'elo_exp', 'surface_wr_diff',
    'surface_wr_j1', 'surface_wr_j2', 'surface_enc', 'ace_diff',
    'win_first_diff', 'win_second_diff', 'winners_diff', 'unforced_diff',
    'bp_save_diff', 'estilo_j1', 'estilo_j2', 'fatiga_diff', 'sets_diff',
    'h2h_diff', 'oi_diff', 'elo_Hard_diff', 'elo_Clay_diff',
    'elo_Grass_diff', 'oi_Hard_diff', 'oi_Clay_diff', 'oi_Grass_diff',
]

_bundles = {}   # key: "atp" | "wta"
_loaded  = {}   # key: "atp" | "wta" -> bool


def _load_bundle(tour: str):
    """Load model bundle for the given tour ('atp' or 'wta'). Cached after first load."""
    if _loaded.get(tour):
        return _bundles.get(tour)

    # Search order: models/ subdirectory, then current working directory
    fname  = "tennis_model_v3.pkl" if tour == "atp" else "tennis_model_wta.pkl"
    search = [
        Path("backend/models") / fname,
        Path("models") / fname,
        Path(fname),
    ]
    for path in search:
        if path.exists():
            try:
                with open(path, "rb") as f:
                    bundle = pickle.load(f)
                _bundles[tour] = bundle
                _loaded[tour]  = True
                logger.info("Loaded %s model from %s", tour.upper(), path)
                return bundle
            except Exception as e:
                logger.error("Failed to load %s bundle from %s: %s", tour, path, e)

    logger.warning("No %s model file found — using heuristic fallback", tour.upper())
    _loaded[tour] = True
    return None


def _heuristic(features: dict) -> dict:
    """Simple heuristic when no model is available."""
    elo_diff  = features.get('elo_diff', 0)
    rank_diff = features.get('rank_diff', 0)
    oi_diff   = features.get('oi_diff', 0)
    raw = 0.5 + (elo_diff / 400) * 0.35 + (oi_diff / 200) * 0.15 - (rank_diff / 200) * 0.10
    p1  = max(0.05, min(0.95, raw))
    return {
        "p1_win_prob":      round(p1, 4),
        "p2_win_prob":      round(1 - p1, 4),
        "predicted_winner": 1 if p1 > 0.5 else 2,
        "confidence":       round(abs(p1 - 0.5) * 2, 4),
        "model_version":    "heuristic",
    }


def predict_match(features: dict, tour: str = "atp") -> dict:
    """
    Run a prediction for a match.

    Args:
        features: dict with keys from FEATS_V6
        tour:     "atp" or "wta"
    Returns:
        dict with p1_win_prob, p2_win_prob, predicted_winner, confidence, model_version
    """
    bundle = _load_bundle(tour.lower())
    if bundle is None:
        return _heuristic(features)

    modelo = bundle.get("modelo")
    feats  = bundle.get("feats", FEATS_V6)

    if modelo is None:
        return _heuristic(features)

    try:
        row = [float(features.get(f, 0.0)) for f in feats]
        X   = pd.DataFrame([row], columns=feats)
        proba = modelo.predict_proba(X)[0]
        # CalibratedClassifierCV outputs [p_class0, p_class1]
        # class 1 = player-1 wins
        p1 = float(proba[1]) if len(proba) >= 2 else float(proba[0])
        return {
            "p1_win_prob":      round(p1, 4),
            "p2_win_prob":      round(1 - p1, 4),
            "predicted_winner": 1 if p1 > 0.5 else 2,
            "confidence":       round(abs(p1 - 0.5) * 2, 4),
            "model_version":    "v3",
        }
    except Exception as e:
        logger.error("predict_match error (%s): %s", tour, e)
        return _heuristic(features)


def is_model_available(tour: str = "atp") -> bool:
    bundle = _load_bundle(tour.lower())
    return bundle is not None and bundle.get("modelo") is not None


def get_model_info() -> dict:
    atp_ok = is_model_available("atp")
    wta_ok = is_model_available("wta")
    return {
        "version":       "v3",
        "algorithm":     "GradientBoostingClassifier (CalibratedCV)",
        "test_accuracy": {"atp": 0.890, "wta": 0.872},
        "features":      FEATS_V6,
        "n_features":    len(FEATS_V6),
        "train_period":  "2019-2023",
        "test_period":   "2025-2026",
        "atp_available": atp_ok,
        "wta_available": wta_ok,
        "available":     atp_ok or wta_ok,
    }
