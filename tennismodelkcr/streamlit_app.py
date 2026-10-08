"""
Tennis KCR — Streamlit Dashboard
Predicciones del día + Rankings OI (ATP/WTA).
"""
import sys
import os
import json
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from datetime import date

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tennis KCR",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stTabs"] button { color: #6b7080 !important; font-weight: 500; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #e8eaf0 !important; }

.match-card {
    background: #1a1d27;
    border: 1px solid #2a2d3a;
    border-radius: 12px;
    padding: 18px 22px;
    margin-bottom: 14px;
}
.match-card:hover { border-color: #3d8ef8; transition: border-color .2s; }

.badge {
    display: inline-block;
    font-size: 11px; font-weight: 600;
    padding: 3px 9px; border-radius: 20px;
    margin-right: 6px; text-transform: uppercase; letter-spacing: .5px;
}
.badge-live   { background:#3a1010; color:#f84d4d; }
.badge-done   { background:#1a1a1a; color:#4a5068; }
.badge-sched  { background:#1e2a1e; color:#6bcf6b; }
.badge-hard   { background:#1e3a5f; color:#3d8ef8; }
.badge-clay   { background:#3a2010; color:#f8944d; }
.badge-grass  { background:#1e3a2f; color:#3dca8f; }
.badge-indoor { background:#2a2040; color:#a07ef8; }
.badge-round  { background:#2a2030; color:#a07ef8; }

.player-name  { font-size:17px; font-weight:600; color:#e8eaf0; }
.player-dim   { color:#4a5068; }
.prob-pct     { font-size:22px; font-weight:700; }
.prob-high    { color:#3dca8f; }
.prob-mid     { color:#f8c84d; }
.prob-low     { color:#f86b6b; }
.prob-bar-outer { background:#2a2d3a; border-radius:6px; height:8px; margin:8px 0; overflow:hidden; }
.prob-bar-inner { height:8px; border-radius:6px; background:linear-gradient(90deg,#3d8ef8,#3dca8f); }
.score-text   { color:#f8c84d; font-weight:600; font-size:14px; }
.model-tag    { display:inline-block; background:#222536; color:#4a5068;
                border:1px solid #2a2d3a; border-radius:6px; padding:2px 8px;
                font-size:11px; margin-top:6px; }

/* Rankings table */
.oi-row-pos { color:#3dca8f; font-weight:700; }
.oi-row-neg { color:#f86b6b; font-weight:700; }
.oi-row-neu { color:#f8c84d; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Model / data loaders
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def load_model_service():
    try:
        from backend.services.model import predict_match, get_model_info
        dummy = {f: 0.0 for f in [
            'rank_diff','form_diff','elo_diff','elo_exp','surface_wr_diff',
            'surface_wr_j1','surface_wr_j2','surface_enc','ace_diff',
            'win_first_diff','win_second_diff','winners_diff','unforced_diff',
            'bp_save_diff','estilo_j1','estilo_j2','fatiga_diff','sets_diff',
            'h2h_diff','oi_diff','elo_Hard_diff','elo_Clay_diff',
            'elo_Grass_diff','oi_Hard_diff','oi_Clay_diff','oi_Grass_diff',
        ]}
        predict_match(dummy, tour="atp")
        predict_match(dummy, tour="wta")
        return predict_match, get_model_info()
    except Exception as e:
        return None, {"error": str(e)}


@st.cache_data(show_spinner=False)
def load_oi_rankings() -> dict:
    path = ROOT / "data" / "oi_rankings.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"ATP": [], "WTA": []}


@st.cache_data(ttl=120, show_spinner=False)
def fetch_matches() -> list:
    rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
    if not rapidapi_key:
        return _demo_matches()
    try:
        import httpx
        BASE = "https://tennis-api-atp-wta-itf.p.rapidapi.com"
        hdrs = {"X-RapidAPI-Key": rapidapi_key,
                "X-RapidAPI-Host": "tennis-api-atp-wta-itf.p.rapidapi.com"}
        today = date.today().isoformat()
        endpoints = [
            f"{BASE}/tennis/v2/atp/live", f"{BASE}/tennis/v2/wta/live",
            f"{BASE}/tennis/v2/atp/fixtures", f"{BASE}/tennis/v2/wta/fixtures",
            f"{BASE}/tennis/v2/atp/results/{today}", f"{BASE}/tennis/v2/wta/results/{today}",
        ]
        all_m, seen = [], set()
        with httpx.Client(timeout=8.0) as client:
            for url in endpoints:
                try:
                    r = client.get(url, headers=hdrs)
                    if r.status_code == 200:
                        data = r.json()
                        items = data if isinstance(data, list) else data.get("data", [])
                        for item in (items if isinstance(items, list) else []):
                            mid = item.get("id") or item.get("matchId") or str(item)[:60]
                            if mid not in seen:
                                seen.add(mid); all_m.append(item)
                except Exception:
                    pass
        return all_m or _demo_matches()
    except Exception:
        return _demo_matches()


# ══════════════════════════════════════════════════════════════════════════════
# Match helpers
# ══════════════════════════════════════════════════════════════════════════════

def _demo_matches():
    return [
        {"_demo":True,"tournament":"Shanghai Masters","round":"QF","surface":"Hard",
         "p1_name":"Jannik Sinner","p2_name":"Grigor Dimitrov",
         "p1_rank":1,"p2_rank":10,"elo_diff":309.0,"rank_diff":-9,"status":"scheduled","score":""},
        {"_demo":True,"tournament":"Shanghai Masters","round":"QF","surface":"Hard",
         "p1_name":"Carlos Alcaraz","p2_name":"Taylor Fritz",
         "p1_rank":3,"p2_rank":4,"elo_diff":190.0,"rank_diff":-1,"status":"live","score":"6-4 3-2"},
        {"_demo":True,"tournament":"Shanghai Masters","round":"QF","surface":"Hard",
         "p1_name":"Alexander Zverev","p2_name":"Andrey Rublev",
         "p1_rank":2,"p2_rank":7,"elo_diff":115.0,"rank_diff":-5,"status":"scheduled","score":""},
        {"_demo":True,"tournament":"Shanghai Masters","round":"QF","surface":"Hard",
         "p1_name":"Daniil Medvedev","p2_name":"Novak Djokovic",
         "p1_rank":5,"p2_rank":6,"elo_diff":-71.0,"rank_diff":1,"status":"finished","score":"6-4 3-6 7-6"},
        {"_demo":True,"tournament":"WTA Finals","round":"RR","surface":"Hard",
         "p1_name":"Aryna Sabalenka","p2_name":"Iga Świątek",
         "p1_rank":1,"p2_rank":2,"elo_diff":36.0,"rank_diff":-1,"status":"live","score":"4-4"},
        {"_demo":True,"tournament":"WTA Finals","round":"RR","surface":"Hard",
         "p1_name":"Coco Gauff","p2_name":"Elena Rybakina",
         "p1_rank":3,"p2_rank":4,"elo_diff":-25.0,"rank_diff":1,"status":"scheduled","score":""},
    ]


def parse_match(m: dict):
    if m.get("_demo"):
        return m
    def _name(obj):
        if isinstance(obj, dict):
            return obj.get("name") or obj.get("fullName") or obj.get("shortName") or ""
        return str(obj) if obj else ""
    p1o = m.get("homeTeam") or m.get("player1") or m.get("home") or m.get("p1") or {}
    p2o = m.get("awayTeam") or m.get("player2") or m.get("away") or m.get("p2") or {}
    p1 = _name(p1o) or m.get("p1_name") or m.get("player1Name") or ""
    p2 = _name(p2o) or m.get("p2_name") or m.get("player2Name") or ""
    if not p1 or not p2:
        return None
    tourn = m.get("tournament") or m.get("event") or {}
    t = (tourn.get("name") or tourn.get("shortName") or "" if isinstance(tourn, dict) else str(tourn))
    surf = m.get("surface") or m.get("court") or "Hard"
    if isinstance(surf, dict): surf = surf.get("name") or "Hard"
    rnd = m.get("round") or m.get("roundName") or m.get("stage") or ""
    if isinstance(rnd, dict): rnd = rnd.get("name") or ""
    status = m.get("status") or m.get("statusName") or "scheduled"
    if isinstance(status, dict): status = status.get("name") or "scheduled"
    score = m.get("score") or m.get("result") or ""
    if isinstance(score, dict): score = score.get("current") or score.get("display") or ""
    return {"tournament":t,"round":str(rnd),"surface":str(surf),
            "p1_name":p1,"p2_name":p2,
            "p1_rank":m.get("p1_rank") or m.get("homeRank") or 0,
            "p2_rank":m.get("p2_rank") or m.get("awayRank") or 0,
            "elo_diff":float(m.get("elo_diff") or 0),
            "rank_diff":float(m.get("rank_diff") or 0),
            "status":str(status).lower(),"score":str(score) if score else ""}


def build_features(m: dict) -> dict:
    surf_map = {"Hard":2,"Clay":0,"Grass":1,"I.hard":3,"Indoor Hard":3}
    surf_enc = surf_map.get(m.get("surface","Hard"), 2)
    rank_diff = float(m.get("rank_diff") or 0)
    elo_diff  = float(m.get("elo_diff") or 0)
    p1r, p2r = m.get("p1_rank") or 0, m.get("p2_rank") or 0
    if rank_diff == 0 and p1r and p2r:
        rank_diff = float(p2r - p1r)
    surf = m.get("surface","Hard")
    elo_h = elo_diff*0.9 if surf=="Hard"  else elo_diff*0.4
    elo_c = elo_diff*0.9 if surf=="Clay"  else elo_diff*0.4
    elo_g = elo_diff*0.9 if surf=="Grass" else elo_diff*0.4
    base = {f: 0.0 for f in [
        'rank_diff','form_diff','elo_diff','elo_exp','surface_wr_diff',
        'surface_wr_j1','surface_wr_j2','surface_enc','ace_diff',
        'win_first_diff','win_second_diff','winners_diff','unforced_diff',
        'bp_save_diff','estilo_j1','estilo_j2','fatiga_diff','sets_diff',
        'h2h_diff','oi_diff','elo_Hard_diff','elo_Clay_diff',
        'elo_Grass_diff','oi_Hard_diff','oi_Clay_diff','oi_Grass_diff',
    ]}
    base.update({"rank_diff":rank_diff,"elo_diff":elo_diff,"surface_enc":float(surf_enc),
                 "elo_Hard_diff":elo_h,"elo_Clay_diff":elo_c,"elo_Grass_diff":elo_g})
    return base


def detect_tour(m):
    t = (m.get("tournament") or "").upper()
    return "wta" if any(x in t for x in ["WTA","WOMEN","LADIES","FINALS"]) else "atp"


def predict(m):
    fn, _ = load_model_service()
    if fn is None:
        return {"p1_win_prob":0.5,"p2_win_prob":0.5,"confidence":0.0,
                "predicted_winner":0,"model_version":"unavailable"}
    return fn(build_features(m), tour=detect_tour(m))


def surf_badge(surface):
    cls = {"Hard":"badge-hard","Clay":"badge-clay","Grass":"badge-grass",
           "Indoor Hard":"badge-indoor"}.get(surface,"badge-hard")
    return f'<span class="badge {cls}">{surface}</span>'


def status_badge(status):
    if any(x in status for x in ["live","progress","play"]):
        return '<span class="badge badge-live">● En vivo</span>'
    if any(x in status for x in ["finish","ended","complete"]):
        return '<span class="badge badge-done">■ Terminado</span>'
    return '<span class="badge badge-sched">○ Programado</span>'


def prob_cls(p):
    return "prob-high" if p >= 0.65 else ("prob-mid" if p >= 0.50 else "prob-low")


def render_match_card(m):
    pred   = predict(m)
    p1p    = pred.get("p1_win_prob", 0.5)
    p2p    = pred.get("p2_win_prob", 0.5)
    winner = pred.get("predicted_winner", 0)
    ver    = pred.get("model_version","?")
    p1_pct, p2_pct = int(round(p1p*100)), int(round(p2p*100))

    p1  = m["p1_name"];  p2  = m["p2_name"]
    r1  = m.get("p1_rank") or 0;  r2 = m.get("p2_rank") or 0
    r1h = f'<span class="player-dim" style="font-size:12px"> #{r1}</span>' if r1 else ""
    r2h = f'<span class="player-dim" style="font-size:12px"> #{r2}</span>' if r2 else ""

    p1_cls = "player-name" if winner != 2 else "player-name player-dim"
    p2_cls = "player-name" if winner != 1 else "player-name player-dim"

    score  = m.get("score","")
    score_html = f'<span class="score-text">{score}</span>' if score else ""
    rnd    = m.get("round","")
    rnd_h  = f'<span class="badge badge-round">{rnd}</span>' if rnd else ""
    tourn  = m.get("tournament","")

    st.markdown(f"""
<div class="match-card">
  <div style="display:flex;align-items:center;gap:6px;margin-bottom:12px;flex-wrap:wrap;">
    {status_badge(m.get("status",""))}
    {surf_badge(m.get("surface","Hard"))}
    {rnd_h}
    <span style="color:#4a5068;font-size:12px">{tourn}</span>
    <span style="margin-left:auto">{score_html}</span>
  </div>
  <div style="display:flex;align-items:center;margin-bottom:10px;">
    <div style="flex:1;min-width:0;">
      <span class="{p1_cls}">{p1}{r1h}</span>
    </div>
    <div style="padding:0 16px;color:#4a5068;font-size:11px;font-weight:600;letter-spacing:1px;flex-shrink:0">VS</div>
    <div style="flex:1;min-width:0;text-align:right;">
      <span class="{p2_cls}">{r2h}{p2}</span>
    </div>
  </div>
  <div class="prob-bar-outer"><div class="prob-bar-inner" style="width:{p1_pct}%"></div></div>
  <div style="display:flex;justify-content:space-between;margin-top:6px;">
    <div>
      <span class="prob-pct {prob_cls(p1p)}">{p1_pct}%</span>
      <span style="color:#4a5068;font-size:12px;margin-left:4px">{p1.split()[-1]}</span>
    </div>
    <div style="text-align:right">
      <span style="color:#4a5068;font-size:12px;margin-right:4px">{p2.split()[-1]}</span>
      <span class="prob-pct {prob_cls(p2p)}">{p2_pct}%</span>
    </div>
  </div>
  <div><span class="model-tag">modelo: {ver}</span></div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Predicciones del día
# ══════════════════════════════════════════════════════════════════════════════

def page_predictions():
    _, info = load_model_service()
    if info and not info.get("error"):
        atp_ok = info.get("atp_available", False)
        wta_ok = info.get("wta_available", False)
        st.markdown(
            f'<div style="background:#1a1d27;border:1px solid #2a2d3a;border-radius:8px;'
            f'padding:10px 16px;margin-bottom:20px;display:flex;gap:24px;flex-wrap:wrap;">'
            f'<span style="color:#4a5068;font-size:13px">{"🟢" if atp_ok else "🟡"} '
            f'ATP {info["test_accuracy"]["atp"]*100:.0f}% acc</span>'
            f'<span style="color:#4a5068;font-size:13px">{"🟢" if wta_ok else "🟡"} '
            f'WTA {info["test_accuracy"]["wta"]*100:.0f}% acc</span>'
            f'<span style="color:#4a5068;font-size:13px;margin-left:auto">↻ cada 2 min</span>'
            f'</div>', unsafe_allow_html=True)

    col_r, _ = st.columns([1, 3])
    with col_r:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.cache_data.clear(); st.rerun()

    with st.spinner("Cargando partidos..."):
        raw = fetch_matches()

    parsed = [p for m in raw if (p := parse_match(m))]
    is_demo = all(m.get("_demo") for m in raw[:3]) if raw else True

    if is_demo:
        st.info("📊 Datos de demostración — añade RAPIDAPI_KEY en `.env` para datos reales.")

    # Filters
    tourneys = sorted({m.get("tournament","") for m in parsed if m.get("tournament")})
    surfaces = sorted({m.get("surface","") for m in parsed if m.get("surface")})
    c1, c2, c3 = st.columns(3)
    with c1: sel_t = st.selectbox("Torneo", ["Todos"] + tourneys)
    with c2: sel_s = st.selectbox("Superficie", ["Todos"] + surfaces)
    with c3: sel_st = st.selectbox("Estado", ["Todos","En vivo","Programados","Terminados"])

    f = parsed
    if sel_t  != "Todos": f = [m for m in f if m.get("tournament") == sel_t]
    if sel_s  != "Todos": f = [m for m in f if m.get("surface") == sel_s]
    if sel_st == "En vivo":     f = [m for m in f if any(x in m.get("status","") for x in ["live","progress","play"])]
    elif sel_st == "Programados": f = [m for m in f if m.get("status","") in ["scheduled",""]]
    elif sel_st == "Terminados":  f = [m for m in f if any(x in m.get("status","") for x in ["finish","ended","complete"])]

    def _sort(m):
        s = m.get("status","")
        return 0 if any(x in s for x in ["live","progress","play"]) else (2 if any(x in s for x in ["finish","ended","complete"]) else 1)

    f.sort(key=_sort)
    st.markdown(f'<p style="color:#4a5068;font-size:13px;margin:8px 0 16px 0">{len(f)} partidos</p>', unsafe_allow_html=True)

    if not f:
        st.markdown('<div style="text-align:center;padding:60px 0;color:#4a5068">Sin partidos con estos filtros.</div>', unsafe_allow_html=True)
        return

    mid = (len(f)+1)//2
    ca, cb = st.columns(2)
    with ca:
        for m in f[:mid]: render_match_card(m)
    with cb:
        for m in f[mid:]: render_match_card(m)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Rankings OI
# ══════════════════════════════════════════════════════════════════════════════

def render_player_card(row, tour, oi_field):
    """Render a single player OI card."""
    oi_val   = row[oi_field]
    oi_col   = "#3dca8f" if oi_val > 100 else ("#8be0c0" if oi_val > 0 else ("#f8944d" if oi_val > -100 else "#f86b6b"))
    rank_lbl = f"{'ATP' if tour=='ATP' else 'WTA'} #{int(row['atp_rank'])}" if row.get('atp_rank') else ""
    surf_lbl = {"oi":"Global","oi_hard":"Hard","oi_clay":"Clay","oi_grass":"Grass"}.get(oi_field,"Global")
    # Mini surface bars
    bars = ""
    for sf, sk, sc in [("H","oi_hard","#3d8ef8"),("C","oi_clay","#f8944d"),("G","oi_grass","#3dca8f")]:
        v = row.get(sk, 0)
        w = min(100, max(0, int((v + 600) / 12)))  # scale -600..+600 → 0..100
        bars += (f'<div style="display:flex;align-items:center;gap:6px;margin-top:3px;">'
                 f'<span style="color:#4a5068;font-size:10px;width:8px">{sf}</span>'
                 f'<div style="flex:1;background:#2a2d3a;border-radius:3px;height:4px;">'
                 f'<div style="width:{w}%;height:4px;border-radius:3px;background:{sc}"></div></div>'
                 f'<span style="color:{sc};font-size:10px;width:40px;text-align:right">{v:+.0f}</span>'
                 f'</div>')
    st.markdown(f"""
<div class="match-card" style="padding:16px 18px;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div style="color:#4a5068;font-size:11px;font-weight:600;letter-spacing:.5px">#{int(row['rank'])} · {rank_lbl}</div>
      <div style="color:#e8eaf0;font-size:16px;font-weight:600;margin:4px 0">{row['name']}</div>
      <div style="color:#4a5068;font-size:12px">{int(row['matches'])} partidos</div>
    </div>
    <div style="text-align:right;">
      <div style="color:#4a5068;font-size:10px;text-transform:uppercase;letter-spacing:.5px">OI {surf_lbl}</div>
      <div style="color:{oi_col};font-size:26px;font-weight:700;line-height:1.1">{oi_val:+.1f}</div>
    </div>
  </div>
  <div style="margin-top:10px;border-top:1px solid #2a2d3a;padding-top:10px">{bars}</div>
</div>
""", unsafe_allow_html=True)


def page_oi_rankings():
    data = load_oi_rankings()

    st.markdown("""
<div style="background:#1a1d27;border:1px solid #2a2d3a;border-radius:8px;
            padding:14px 18px;margin-bottom:20px;">
  <p style="margin:0;color:#6b7080;font-size:13px;line-height:1.6">
    <b style="color:#e8eaf0">OI (Overperformance Index)</b> — mide cuánto rinde un jugador
    por encima de lo esperado según las cuotas del mercado.<br>
    Se actualiza partido a partido: <code style="color:#a07ef8">OI += K × (resultado − prob_mercado)</code>
    con K=32 y base 1500. Un OI alto = bate sistemáticamente las expectativas.
  </p>
</div>
""", unsafe_allow_html=True)

    # ── Controls row ──────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        tour = st.radio("Tour", ["ATP", "WTA"], horizontal=True)
    with c2:
        surf_tab = st.radio("Superficie", ["Global","Hard","Clay","Grass"], horizontal=True)

    oi_field = {"Global":"oi","Hard":"oi_hard","Clay":"oi_clay","Grass":"oi_grass"}[surf_tab]
    players  = data.get(tour, [])

    if not players:
        st.warning("No hay datos de OI para este tour.")
        return

    df_all = pd.DataFrame(players).sort_values(oi_field, ascending=False).reset_index(drop=True)
    df_all["rank"] = df_all.index + 1

    # ── Search + list ─────────────────────────────────────────────────────────
    search = st.text_input("🔍 Buscar jugador", placeholder="Ej: Sinner, Alcaraz, Paolini...")

    df_filtered = df_all.copy()
    if search:
        df_filtered = df_filtered[df_filtered["name"].str.contains(search, case=False, na=False)]

    if df_filtered.empty:
        st.info("No se encontró ningún jugador.")
        return

    rank_lbl = "ATP" if tour == "ATP" else "WTA"

    # Build display table
    col_map = {"rank":"#","name":"Jugador","atp_rank":f"{rank_lbl} Rank",
               "oi":"OI Global","oi_hard":"OI Hard","oi_clay":"OI Clay",
               "oi_grass":"OI Grass","matches":"Partidos"}
    df_show = df_filtered[["rank","name","atp_rank","oi","oi_hard","oi_clay","oi_grass","matches"]].rename(columns=col_map)

    def color_oi(val):
        if not isinstance(val, (int, float)): return ""
        if val > 100:  return "color:#3dca8f;font-weight:600"
        if val > 0:    return "color:#8be0c0"
        if val > -100: return "color:#f8944d"
        return "color:#f86b6b;font-weight:600"

    styled = (
        df_show.style
        .applymap(color_oi, subset=["OI Global","OI Hard","OI Clay","OI Grass"])
        .format({"OI Global":"{:+.1f}","OI Hard":"{:+.1f}","OI Clay":"{:+.1f}","OI Grass":"{:+.1f}"})
        .set_properties(**{"background-color":"#1a1d27","color":"#e8eaf0","border":"1px solid #2a2d3a"})
        .set_table_styles([
            {"selector":"thead th","props":[("background","#13161f"),("color","#6b7080"),
             ("font-size","12px"),("text-transform","uppercase"),("letter-spacing","0.5px"),
             ("border","1px solid #2a2d3a")]},
            {"selector":"tbody tr:hover td","props":[("background-color","#222536")]},
        ])
    )

    st.markdown(f'<p style="color:#4a5068;font-size:13px;margin-bottom:8px">{len(df_show)} jugadores</p>',
                unsafe_allow_html=True)

    # ── Table + multiselect side by side ──────────────────────────────────────
    col_table, col_sel = st.columns([3, 1])

    with col_table:
        st.dataframe(styled, use_container_width=True, height=520)

    with col_sel:
        st.markdown('<p style="color:#6b7080;font-size:12px;margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Seleccionar jugadores</p>',
                    unsafe_allow_html=True)
        # Options: show rank + name in the list
        options = [f"#{int(r['rank'])} {r['name']}" for _, r in df_filtered.iterrows()]
        selected = st.multiselect(
            label="jugadores",
            options=options,
            default=[],
            label_visibility="collapsed",
            placeholder="Elige uno o varios…",
        )

    # ── Cards for selected players ────────────────────────────────────────────
    if selected:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<h3 style="color:#e8eaf0;font-size:15px;font-weight:600;margin-bottom:14px">'
            f'Detalle — {len(selected)} jugador{"es" if len(selected)>1 else ""}</h3>',
            unsafe_allow_html=True)

        # Parse selected names back to df rows
        sel_names = [s.split(" ", 1)[1] for s in selected]  # strip "#N "
        df_cards  = df_filtered[df_filtered["name"].isin(sel_names)]

        cols = st.columns(min(3, len(df_cards)))
        for i, (_, row) in enumerate(df_cards.iterrows()):
            with cols[i % len(cols)]:
                render_player_card(row, tour, oi_field)
    else:
        st.markdown(
            '<p style="color:#4a5068;font-size:13px;margin-top:12px">'
            '← Selecciona jugadores en la lista para ver su tarjeta de detalle.</p>',
            unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Header + navigation
# ══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown("""
<div style="padding:24px 0 16px 0;display:flex;align-items:center;gap:14px;">
  <span style="font-size:36px">🎾</span>
  <div>
    <h1 style="margin:0;font-size:28px;font-weight:700;color:#e8eaf0">Tennis KCR</h1>
    <p style="margin:0;color:#4a5068;font-size:14px">Predicciones ML · Rankings OI</p>
  </div>
</div>
""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📅  Partidos del día", "📊  Rankings OI"])

    with tab1:
        page_predictions()

    with tab2:
        page_oi_rankings()


if __name__ == "__main__":
    main()
