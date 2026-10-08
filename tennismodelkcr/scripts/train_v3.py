"""
Tennis Model Trainer v3 — fully vectorized feature building.
Avoids per-row DataFrame lookups by pre-joining everything before the loop.
"""

import pickle, warnings, time
import pandas as pd
import numpy as np
from collections import defaultdict
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")
t_start = time.time()

UPLOADS = "/root/.claude/uploads/9889491c-ad0a-5db2-93db-ddd26a2e0344"
OUT_DIR = "/home/claude/tennismodelkcr/backend/models"
import os; os.makedirs(OUT_DIR, exist_ok=True)

surfaces = ["Hard","Clay","Grass","I.hard"]
K = 32
SURF_MAP = {"hard":"Hard","clay":"Clay","grass":"Grass","i.hard":"I.hard",
            "indoor hard":"I.hard","indoor":"I.hard","carpet":"I.hard"}
ETIQUETAS = {0:"Aggressive Baseliner",1:"All-Court",2:"Serve & Volley",3:"Defensive"}
feats_v6 = [
    "rank_diff","form_diff","elo_diff","elo_exp",
    "surface_wr_diff","surface_wr_j1","surface_wr_j2","surface_enc",
    "ace_diff","win_first_diff","win_second_diff","winners_diff",
    "unforced_diff","bp_save_diff","estilo_j1","estilo_j2",
    "fatiga_diff","sets_diff","h2h_diff","oi_diff",
    "elo_Hard_diff","elo_Clay_diff","elo_Grass_diff",
    "oi_Hard_diff","oi_Clay_diff","oi_Grass_diff",
]


def nombre_a_clave(s):
    parts = str(s).strip().split()
    return f"{parts[-1]} {parts[0][0]}.".lower() if len(parts)>=2 else str(s).lower().strip()


def build_elo_series(df_sorted):
    """Compute pre-match Elo for winner and loser using iterative update."""
    elo = defaultdict(lambda: 1500.0)
    elo_w_arr, elo_l_arr, exp_arr = [], [], []
    wids = df_sorted["winner_id"].values
    lids = df_sorted["loser_id"].values
    for wid, lid in zip(wids, lids):
        ew, el = elo[wid], elo[lid]
        exp_w = 1 / (1 + 10 ** ((el - ew) / 400))
        elo_w_arr.append(ew); elo_l_arr.append(el); exp_arr.append(exp_w)
        elo[wid] += K * (1 - exp_w)
        elo[lid] += K * (0 - exp_w)
    return np.array(elo_w_arr), np.array(elo_l_arr), np.array(exp_arr), dict(elo)


def build_surface_elo(df_sorted):
    """Surface-specific Elo. Returns dict of surface -> defaultdict(pid->elo)."""
    elo = {s: defaultdict(lambda: 1500.0) for s in surfaces}
    for _, row in df_sorted.iterrows():
        s = row["surface"]
        if s not in surfaces: continue
        w, l = row["winner_id"], row["loser_id"]
        ew, el = elo[s][w], elo[s][l]
        exp_w = 1/(1+10**((el-ew)/400))
        elo[s][w] += K*(1-exp_w); elo[s][l] += K*(0-exp_w)
    return elo


def compute_oi(season_dfs):
    """Returns oi_global (pid->float), oi_surf (surf->pid->float), pid_to_name."""
    oi_g = defaultdict(float)
    oi_s = {s: defaultdict(float) for s in surfaces}
    # Initialize at 0, we'll add 1500 below
    pid2name = {}
    if not season_dfs:
        return oi_g, oi_s, pid2name
    df = pd.concat(season_dfs, ignore_index=True)
    df["date_timestamp"] = pd.to_numeric(df["date_timestamp"], errors="coerce")
    df = df.dropna(subset=["home_odds_match_winner","away_odds_match_winner","winner_code","date_timestamp"])
    df = df.sort_values("date_timestamp").reset_index(drop=True)
    # Vectorized: compute delta per row
    ho = df["home_odds_match_winner"].values.astype(float)
    ao = df["away_odds_match_winner"].values.astype(float)
    wc = df["winner_code"].values.astype(int)
    valid = (ho > 1) & (ao > 1)
    df_v = df[valid].copy()
    ho_v = ho[valid]; ao_v = ao[valid]; wc_v = wc[valid]
    total_v = 1/ho_v + 1/ao_v
    ph_v = (1/ho_v) / total_v
    res_v = (wc_v == 1).astype(float)
    dh_v = K * (res_v - ph_v)   # delta for home
    da_v = K * ((1-res_v) - (1-ph_v))  # delta for away

    hids = df_v["home_id"].values
    aids = df_v["away_id"].values
    hnames = df_v["home_name"].values if "home_name" in df_v else [""] * len(df_v)
    anames = df_v["away_name"].values if "away_name" in df_v else [""] * len(df_v)
    surfs_raw = df_v["surface"].values if "surface" in df_v else ["Hard"] * len(df_v)

    for i in range(len(df_v)):
        try:
            hid = int(hids[i]); aid = int(aids[i])
            pid2name[hid] = str(hnames[i]); pid2name[aid] = str(anames[i])
            oi_g[hid] += dh_v[i]; oi_g[aid] += da_v[i]
            sup = SURF_MAP.get(str(surfs_raw[i]).strip().lower())
            if sup in surfaces:
                oi_s[sup][hid] += dh_v[i]; oi_s[sup][aid] += da_v[i]
        except Exception:
            continue

    # Shift so baseline is 1500
    for pid in oi_g: oi_g[pid] += 1500.0
    for s in surfaces:
        for pid in oi_s[s]: oi_s[s][pid] += 1500.0

    return oi_g, oi_s, pid2name


def build_features_vectorized(df_in, le, swr_df, oi_df, oi_surf_dfs, elo_surf, h2h_agg, estilo, stats_bp, pid_name_idx):
    """
    Build feature rows without per-row DataFrame lookups.
    All lookups are done via pre-joined columns on df_in.
    Returns DataFrame with feats_v6 + label columns.
    """
    SURFS = surfaces
    df = df_in.copy()

    # Surface encode
    surf_valid = df["surface"].isin(SURFS)
    df = df[surf_valid & df["winner_form"].notna() & df["loser_form"].notna() &
            df["elo_winner"].notna() & df["elo_loser"].notna()].copy()

    if len(df) == 0:
        return pd.DataFrame(columns=feats_v6+["label"])

    df["surface_enc"] = le.transform(df["surface"])

    # For winner and loser, pre-join swr, oi, elo_surf, estilo, stats
    for role, id_col in [("w","winner_id"),("l","loser_id")]:
        pid_col = df[id_col].values
        df[f"swr_{role}"] = [swr_df.get((p, df.iloc[i]["surface"]), 0.5)
                              for i,p in enumerate(pid_col)]
        df[f"oi_{role}"]  = [oi_df.get(p, 1500.0) for p in pid_col]
        for s in ["Hard","Clay","Grass"]:
            df[f"oi_{s}_{role}"] = [oi_surf_dfs[s].get(p,1500.0) for p in pid_col]
            df[f"elo_{s}_{role}"] = [elo_surf[s].get(p,1500.0) for p in pid_col]
        df[f"estilo_{role}"] = [estilo.get(p,1) for p in pid_col]
        df[f"bp_{role}"]  = [stats_bp.get((p,df.iloc[i]["surface"]),0.60)  for i,p in enumerate(pid_col)]
        df[f"ace_{role}"] = [stats_bp.get((p,df.iloc[i]["surface"]+"_ace"),0.05) for i,p in enumerate(pid_col)]
        df[f"srv1_{role}"]= [stats_bp.get((p,df.iloc[i]["surface"]+"_s1"),0.65) for i,p in enumerate(pid_col)]
        df[f"srv2_{role}"]= [stats_bp.get((p,df.iloc[i]["surface"]+"_s2"),0.50) for i,p in enumerate(pid_col)]

    # H2H: pre-join
    def h2h_diff_val(row):
        sup = row["surface"]
        wid = row["winner_id"]; lid = row["loser_id"]
        h1 = h2h_agg.get((wid,lid,sup)); h2 = h2h_agg.get((lid,wid,sup))
        wr1 = h1[0]/h1[1] if h1 and h1[1]>=2 else None
        wr2 = h2[0]/h2[1] if h2 and h2[1]>=2 else None
        return (wr1-wr2) if (wr1 is not None and wr2 is not None) else 0.0
    df["h2h_diff_raw"] = [h2h_diff_val(row) for _,row in df.iterrows()]

    # Fill NaN fatigue columns
    for c in ["dias_descanso_w","dias_descanso_l","sets_semana_w","sets_semana_l","rank_diff"]:
        if c not in df: df[c] = 0.0
        df[c] = df[c].fillna(0 if "dias" not in c else 7)

    # Now build 2 rows per match (winner perspective + loser perspective)
    rows = []
    for j1w, label in [(True,1),(False,0)]:
        sign = 1 if j1w else -1
        t = df.copy()
        t["label"] = label
        t["rank_diff_f"]       = sign * t["rank_diff"]
        t["form_diff"]         = sign * (t["winner_form"] - t["loser_form"])
        t["elo_diff"]          = sign * (t["elo_winner"] - t["elo_loser"])
        t["elo_exp"]           = t["elo_exp_w"] if j1w else 1 - t["elo_exp_w"]
        s1, s2 = ("w","l") if j1w else ("l","w")
        t["surface_wr_diff"]   = t[f"swr_{s1}"] - t[f"swr_{s2}"]
        t["surface_wr_j1"]     = t[f"swr_{s1}"]
        t["surface_wr_j2"]     = t[f"swr_{s2}"]
        t["ace_diff"]          = t[f"ace_{s1}"] - t[f"ace_{s2}"]
        t["win_first_diff"]    = t[f"srv1_{s1}"] - t[f"srv1_{s2}"]
        t["win_second_diff"]   = t[f"srv2_{s1}"] - t[f"srv2_{s2}"]
        t["winners_diff"]      = 0.0
        t["unforced_diff"]     = 0.0
        t["bp_save_diff"]      = t[f"bp_{s1}"] - t[f"bp_{s2}"]
        t["estilo_j1"]         = t[f"estilo_{s1}"]
        t["estilo_j2"]         = t[f"estilo_{s2}"]
        dj1 = "dias_descanso_w" if j1w else "dias_descanso_l"
        dj2 = "dias_descanso_l" if j1w else "dias_descanso_w"
        t["fatiga_diff"]       = sign * (t[dj1] - t[dj2])
        sj1 = "sets_semana_w" if j1w else "sets_semana_l"
        sj2 = "sets_semana_l" if j1w else "sets_semana_w"
        t["sets_diff"]         = sign * (t[sj2] - t[sj1])
        t["h2h_diff"]          = sign * t["h2h_diff_raw"]
        t["oi_diff"]           = sign * (t[f"oi_{s1}"] - t[f"oi_{s2}"])
        for s in ["Hard","Clay","Grass"]:
            t[f"elo_{s}_diff"]  = sign*(t[f"elo_{s}_{s1}"] - t[f"elo_{s}_{s2}"])
            t[f"oi_{s}_diff"]   = sign*(t[f"oi_{s}_{s1}"] - t[f"oi_{s}_{s2}"])
        # Rename to match feats_v6
        t = t.rename(columns={
            "rank_diff_f":"rank_diff",
            "elo_Hard_diff":"elo_Hard_diff","elo_Clay_diff":"elo_Clay_diff","elo_Grass_diff":"elo_Grass_diff",
            "oi_Hard_diff":"oi_Hard_diff","oi_Clay_diff":"oi_Clay_diff","oi_Grass_diff":"oi_Grass_diff",
        })
        rows.append(t[feats_v6+["label"]])
    return pd.concat(rows, ignore_index=True).dropna(subset=feats_v6)


def train_tour(tour):
    print(f"\n{'='*60}\nTRAINING {tour} MODEL\n{'='*60}")
    t0 = time.time()

    # ── Load ──────────────────────────────────────────────────────────────────
    if tour == "ATP":
        df_main = pd.read_csv(f"{UPLOADS}/20b175c7-df_500_v2.csv", low_memory=False)
        sfx = ["f841e5fd-2024-atp-season.csv","4a61cfbd-2025-atp-season.csv","7fd660de-2026-atp-season.csv"]
        out = f"{OUT_DIR}/tennis_model_v3.pkl"
    else:
        df_main = pd.read_csv(f"{UPLOADS}/e1393082-df_wta.csv", low_memory=False)
        sfx = ["d99f06c0-2024-wta-season.csv","049a6484-2025-wta-season.csv","ce6dd21b-2026-wta-season.csv"]
        out = f"{OUT_DIR}/tennis_model_wta.pkl"

    print(f"  Main CSV: {len(df_main)} rows")
    df_main["date"] = pd.to_datetime(df_main["date"], utc=True, errors="coerce")
    df_main["year"] = df_main["date"].dt.year
    df_main["surface"] = df_main["surface"].fillna("Hard")
    df_main = df_main.sort_values("date").reset_index(drop=True)

    le = LabelEncoder().fit(surfaces)
    etiquetas_list = list(ETIQUETAS.values())

    # ── Elo ───────────────────────────────────────────────────────────────────
    print("  Computing Elo...")
    ew_arr, el_arr, exp_arr, elo_final = build_elo_series(df_main)
    df_main["elo_winner"] = ew_arr
    df_main["elo_loser"]  = el_arr
    df_main["elo_exp_w"]  = exp_arr

    train_df = df_main[df_main["year"].isin([2019,2020,2021,2022,2023])].copy()
    val_df   = df_main[df_main["year"] == 2024].copy()
    test_df  = df_main[df_main["year"].isin([2025,2026])].copy()
    print(f"  Splits: Train={len(train_df)} Val={len(val_df)} Test={len(test_df)}")

    # ── Surface Elo (train only) ───────────────────────────────────────────────
    print("  Computing surface Elo (train-only)...")
    elo_surf = build_surface_elo(train_df)

    # ── Surface win rate (train only) ─────────────────────────────────────────
    print("  Computing surface win rates...")
    swr_dict = {}
    for (pid, sup), grp in train_df.groupby(["winner_id","surface"]):
        pass  # We'll use a different approach
    # Faster: stack wins+losses per player+surface
    train_w = train_df[["winner_id","surface"]].copy(); train_w["won"] = 1; train_w = train_w.rename(columns={"winner_id":"pid"})
    train_l = train_df[["loser_id","surface"]].copy();  train_l["won"] = 0; train_l = train_l.rename(columns={"loser_id":"pid"})
    train_all = pd.concat([train_w, train_l], ignore_index=True)
    swr_agg = train_all.groupby(["pid","surface"]).agg(wins=("won","sum"), n=("won","count")).reset_index()
    swr_agg = swr_agg[swr_agg["n"] >= 5]
    swr_agg["wr"] = swr_agg["wins"] / swr_agg["n"]
    swr_dict = {(row["pid"], row["surface"]): row["wr"] for _, row in swr_agg.iterrows()}

    # ── OI ratings ────────────────────────────────────────────────────────────
    print("  Computing OI...")
    season_dfs = []
    for f in sfx:
        try: season_dfs.append(pd.read_csv(f"{UPLOADS}/{f}", low_memory=False))
        except Exception as e: print(f"    Skip {f}: {e}")
    oi_g, oi_s, pid2name = compute_oi(season_dfs)
    print(f"  OI: {len(oi_g)} players")

    # Name->season_pid for bridging
    name2spid = {nombre_a_clave(n): p for p, n in pid2name.items()}
    # Also build pid->name from main CSV
    pid2name_main = {}
    for _, row in df_main.iterrows():
        if "winner_name" in row: pid2name_main[row["winner_id"]] = row.get("winner_name","")
        if "loser_name" in row:  pid2name_main[row["loser_id"]]  = row.get("loser_name","")

    def resolve_oi(main_pid, surf_key="global"):
        # Direct
        if main_pid in oi_g:
            return oi_g[main_pid] if surf_key=="global" else oi_s.get(surf_key,{}).get(main_pid, 1500.0)
        # Via name bridge
        name = pid2name_main.get(main_pid,"")
        spid = name2spid.get(nombre_a_clave(name)) if name else None
        if spid is not None:
            return oi_g.get(spid,1500.0) if surf_key=="global" else oi_s.get(surf_key,{}).get(spid,1500.0)
        return 1500.0

    # Build flat oi lookups
    all_pids = set(df_main["winner_id"]) | set(df_main["loser_id"])
    oi_g_flat  = {p: resolve_oi(p) for p in all_pids}
    oi_s_flat  = {s: {p: resolve_oi(p,s) for p in all_pids} for s in ["Hard","Clay","Grass"]}

    # ── Estilo ─────────────────────────────────────────────────────────────────
    estilo_dict = {}
    for pid in all_pids:
        h = swr_dict.get((pid,"Hard"),0.5)
        c = swr_dict.get((pid,"Clay"),0.5)
        g = swr_dict.get((pid,"Grass"),0.5)
        if g>h and g>c: estilo_dict[pid] = 2
        elif c>h and c>g: estilo_dict[pid] = 3
        elif h>0.5: estilo_dict[pid] = 0
        else: estilo_dict[pid] = 1

    # ── Stats (bp_save, ace, serve %) ─────────────────────────────────────────
    print("  Building stats from season files...")
    stats_bp = {}  # (pid, surf) -> bp_save; (pid, surf+"_ace") -> ace; etc.
    if season_dfs:
        df_s = pd.concat(season_dfs, ignore_index=True)
        df_s = df_s.dropna(subset=["winner_code"])
        for _, row in df_s.iterrows():
            sup = SURF_MAP.get(str(row.get("surface","")).strip().lower(), "Hard")
            for side in ["home","away"]:
                pid_v = row.get(f"{side}_id")
                if pd.isna(pid_v): continue
                pid = int(pid_v)
                for metric, suffix, div in [
                    ("bp_save_pct",      f"{side}_break_points_saved_perc", 100),
                    ("ace_rate",         f"{side}_aces",                     20),
                    ("win_first_pct",    f"{side}_service_points_won_perc", 100),
                ]:
                    v = row.get(suffix)
                    if pd.notna(v):
                        v = float(v)/div if float(v)>1 else float(v)
                        key = (pid, sup) if metric=="bp_save_pct" else (pid, sup+"_"+metric[:3])
                        stats_bp[key] = v

    # ── H2H ───────────────────────────────────────────────────────────────────
    print("  Building H2H...")
    # Vectorized using groupby
    h2h_w = df_main[["winner_id","loser_id","surface"]].copy()
    h2h_w.columns = ["pid1","pid2","surface"]
    h2h_w["wins"] = 1
    h2h_l = df_main[["loser_id","winner_id","surface"]].copy()
    h2h_l.columns = ["pid1","pid2","surface"]
    h2h_l["wins"] = 0
    h2h_all = pd.concat([h2h_w, h2h_l])
    h2h_agg_df = h2h_all.groupby(["pid1","pid2","surface"]).agg(wins=("wins","sum"),n=("wins","count")).reset_index()
    h2h_agg = {(r["pid1"],r["pid2"],r["surface"]):(r["wins"],r["n"]) for _,r in h2h_agg_df.iterrows()}

    # ── Ranking / historial ────────────────────────────────────────────────────
    ranking_dict = {}
    historial = defaultdict(list)
    for _, row in df_main.iterrows():
        if pd.notna(row.get("winner_rank")): ranking_dict[row["winner_id"]] = int(row["winner_rank"])
        if pd.notna(row.get("loser_rank")):  ranking_dict[row["loser_id"]]  = int(row["loser_rank"])
        historial[row["winner_id"]].append(1)
        historial[row["loser_id"]].append(0)

    # ── Build feature matrix (vectorized) ─────────────────────────────────────
    print("  Building feature matrix...")
    pid2name_estilo = {}  # already have estilo_dict with indices

    # Pre-compute per-pid columns for main df
    def enrich(df_in):
        df = df_in.copy()
        for role, id_col in [("w","winner_id"),("l","loser_id")]:
            pids = df[id_col].values
            surfs = df["surface"].values
            df[f"swr_{role}"]    = [swr_dict.get((p,s),0.5) for p,s in zip(pids,surfs)]
            df[f"oi_{role}"]     = [oi_g_flat.get(p,1500.0) for p in pids]
            df[f"estilo_{role}"] = [estilo_dict.get(p,1) for p in pids]
            df[f"bp_{role}"]     = [stats_bp.get((p,s),0.60) for p,s in zip(pids,surfs)]
            df[f"ace_{role}"]    = [stats_bp.get((p,s+"_ace"),0.05) for p,s in zip(pids,surfs)]
            df[f"srv1_{role}"]   = [stats_bp.get((p,s+"_win"),0.65) for p,s in zip(pids,surfs)]
            df[f"srv2_{role}"]   = [stats_bp.get((p,s+"_win"),0.50)-0.15 for p,s in zip(pids,surfs)]
            for s in ["Hard","Clay","Grass"]:
                df[f"oi_{s}_{role}"]  = [oi_s_flat[s].get(p,1500.0) for p in pids]
                df[f"elo_{s}_{role}"] = [elo_surf[s].get(p,1500.0) for p in pids]
        return df

    def h2h_series(df_in):
        def hval(row):
            s = row["surface"]
            w,l = row["winner_id"],row["loser_id"]
            h1 = h2h_agg.get((w,l,s)); h2 = h2h_agg.get((l,w,s))
            wr1 = h1[0]/h1[1] if h1 and h1[1]>=2 else None
            wr2 = h2[0]/h2[1] if h2 and h2[1]>=2 else None
            return (wr1-wr2) if (wr1 is not None and wr2 is not None) else 0.0
        return df_in.apply(hval, axis=1)

    def build_ds(df_raw, label):
        mask = (df_raw["surface"].isin(surfaces) &
                df_raw["winner_form"].notna() & df_raw["loser_form"].notna() &
                df_raw["elo_winner"].notna() & df_raw["elo_loser"].notna())
        df = df_raw[mask].copy()
        if len(df)==0: return pd.DataFrame(columns=feats_v6+["label"])
        df = enrich(df)
        df["h2h_raw"]    = h2h_series(df)
        df["surface_enc"] = le.transform(df["surface"].values)
        for c in ["dias_descanso_w","dias_descanso_l","sets_semana_w","sets_semana_l","rank_diff"]:
            if c not in df: df[c]=0.0
            df[c]=df[c].fillna(7 if "dias" in c else 0)

        sign = 1 if label else -1
        s1,s2 = ("w","l") if label else ("l","w")
        t = pd.DataFrame({
            "rank_diff":       sign*df["rank_diff"],
            "form_diff":       sign*(df["winner_form"]-df["loser_form"]),
            "elo_diff":        sign*(df["elo_winner"]-df["elo_loser"]),
            "elo_exp":         df["elo_exp_w"] if label else 1-df["elo_exp_w"],
            "surface_wr_diff": df[f"swr_{s1}"]-df[f"swr_{s2}"],
            "surface_wr_j1":   df[f"swr_{s1}"],
            "surface_wr_j2":   df[f"swr_{s2}"],
            "surface_enc":     df["surface_enc"],
            "ace_diff":        df[f"ace_{s1}"]-df[f"ace_{s2}"],
            "win_first_diff":  df[f"srv1_{s1}"]-df[f"srv1_{s2}"],
            "win_second_diff": df[f"srv2_{s1}"]-df[f"srv2_{s2}"],
            "winners_diff":    0.0,
            "unforced_diff":   0.0,
            "bp_save_diff":    df[f"bp_{s1}"]-df[f"bp_{s2}"],
            "estilo_j1":       df[f"estilo_{s1}"],
            "estilo_j2":       df[f"estilo_{s2}"],
            "fatiga_diff":     sign*(df["dias_descanso_w"]-df["dias_descanso_l"]) if label
                                else sign*(df["dias_descanso_l"]-df["dias_descanso_w"]),
            "sets_diff":       sign*(df["sets_semana_l"]-df["sets_semana_w"]) if label
                                else sign*(df["sets_semana_w"]-df["sets_semana_l"]),
            "h2h_diff":        sign*df["h2h_raw"],
            "oi_diff":         sign*(df[f"oi_{s1}"]-df[f"oi_{s2}"]),
            "elo_Hard_diff":   sign*(df[f"elo_Hard_{s1}"]-df[f"elo_Hard_{s2}"]),
            "elo_Clay_diff":   sign*(df[f"elo_Clay_{s1}"]-df[f"elo_Clay_{s2}"]),
            "elo_Grass_diff":  sign*(df[f"elo_Grass_{s1}"]-df[f"elo_Grass_{s2}"]),
            "oi_Hard_diff":    sign*(df[f"oi_Hard_{s1}"]-df[f"oi_Hard_{s2}"]),
            "oi_Clay_diff":    sign*(df[f"oi_Clay_{s1}"]-df[f"oi_Clay_{s2}"]),
            "oi_Grass_diff":   sign*(df[f"oi_Grass_{s1}"]-df[f"oi_Grass_{s2}"]),
            "label":           int(label),
        })
        return t.dropna(subset=feats_v6)

    print("    Train set...")
    t_win = build_ds(train_df, True)
    t_los = build_ds(train_df, False)
    ds_train = pd.concat([t_win, t_los], ignore_index=True)
    print("    Val set...")
    v_win = build_ds(val_df, True); v_los = build_ds(val_df, False)
    ds_val = pd.concat([v_win, v_los], ignore_index=True)
    print("    Test set...")
    tx_win = build_ds(test_df, True); tx_los = build_ds(test_df, False)
    ds_test = pd.concat([tx_win, tx_los], ignore_index=True)
    print(f"  Datasets: Train={len(ds_train)} Val={len(ds_val)} Test={len(ds_test)}")

    # ── Train model ───────────────────────────────────────────────────────────
    print("  Training GBM model...")
    model = CalibratedClassifierCV(
        GradientBoostingClassifier(n_estimators=150, max_depth=4, random_state=42, subsample=0.8),
        cv=3
    )
    model.fit(ds_train[feats_v6], ds_train["label"])

    if len(ds_val):
        print(f"  Val acc (2024):    {(model.predict(ds_val[feats_v6])==ds_val['label']).mean():.1%}")
    if len(ds_test):
        print(f"  Test acc (2025-26):{(model.predict(ds_test[feats_v6])==ds_test['label']).mean():.1%}")

    # ── Save ──────────────────────────────────────────────────────────────────
    bundle = {
        "modelo":         model,
        "label_encoder":  le,
        "feats":          feats_v6,
        "elo_ratings":    dict(elo_final),
        "historial":      dict(historial),
        "ranking_dict":   ranking_dict,
        "stats_dict":     stats_bp,  # reuse stats_bp as stats_dict fallback
        "estilo_dict":    {p: ETIQUETAS[v] for p,v in estilo_dict.items()},
        "etiquetas":      ETIQUETAS,
        "h2h_dict":       h2h_agg,
        "oi_ratings":     dict(oi_g),
        "oi_g_flat":      oi_g_flat,
        "oi_s_flat":      oi_s_flat,
        "oi_by_surface":  {s: dict(oi_s[s]) for s in surfaces},
        "elo_by_surface": {s: dict(elo_surf[s]) for s in surfaces},
        "pid_to_name":    pid2name,
        "swr_dict":       swr_dict,
    }
    with open(out, "wb") as f:
        pickle.dump(bundle, f)
    sz = os.path.getsize(out)/1024/1024
    print(f"\n✅ Saved {out} ({sz:.1f} MB) in {time.time()-t0:.0f}s")
    return out


if __name__ == "__main__":
    train_tour("ATP")
    train_tour("WTA")
    print(f"\nTotal time: {time.time()-t_start:.0f}s")
