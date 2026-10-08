/**
 * TennisModel KCR — Main application
 * SPA routing, section rendering, Chart.js charts, player spotlight.
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const FEATS_V6 = [
  'rank_diff','form_diff','elo_diff','elo_exp','surface_wr_diff',
  'surface_wr_j1','surface_wr_j2','surface_enc','ace_diff',
  'win_first_diff','win_second_diff','winners_diff','unforced_diff',
  'bp_save_diff','estilo_j1','estilo_j2','fatiga_diff','sets_diff',
  'h2h_diff','oi_diff','elo_Hard_diff','elo_Clay_diff',
  'elo_Grass_diff','oi_Hard_diff','oi_Clay_diff','oi_Grass_diff',
];

const CHART_COLORS = [
  '#D4A535','#5B9CF6','#18C96A','#E54848','#9B72F6',
  '#E8803A','#2EC4B6','#F4E76E','#FF6B6B','#C5E1A5',
  '#80DEEA','#FFCC80',
];

const COUNTRY_FLAGS = {
  ESP:'🇪🇸',ITA:'🇮🇹',GER:'🇩🇪',USA:'🇺🇸',RUS:'🇷🇺',
  SRB:'🇷🇸',NOR:'🇳🇴',POL:'🇵🇱',BLR:'🇧🇾',KAZ:'🇰🇿',
  AUS:'🇦🇺',DEN:'🇩🇰',GRE:'🇬🇷',BUL:'🇧🇬',ARG:'🇦🇷',
  GBR:'🇬🇧',CRO:'🇭🇷',CAN:'🇨🇦',FRA:'🇫🇷',JPN:'🇯🇵',
};

// ── State ─────────────────────────────────────────────────────────────────────
let state = {
  section: 'predictions',
  oiTour: 'ATP',
  oiData: null,
  oiRankings: null,
  predictions: null,
  visibleSeries: new Set(),
  oiChart: null,
  radarChart: null,
  activePredFilter: 'all',
  compP1: null,
  compP2: null,
};

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Try to restore session
  if (API.loadToken()) {
    showApp();
  }
  initLoginUI();
});

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = '';
  document.querySelector('.nav-right .btn-ghost').textContent = API.getUsername()
    ? `${API.getUsername()} · Sign out`
    : 'Sign out';
  initNavigation();
  loadSection('predictions');
  initModelSection();
}

// ── Login UI ─────────────────────────────────────────────────────────────────
function initLoginUI() {
  // Tab switching
  document.querySelectorAll('.tab-mini').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-mini').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.getElementById('login-form').style.display   = tab === 'login' ? '' : 'none';
      document.getElementById('register-form').style.display = tab === 'register' ? '' : 'none';
    });
  });

  // Login
  document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const u = document.getElementById('login-user').value.trim();
    const p = document.getElementById('login-pass').value;
    const errEl = document.getElementById('login-err');
    errEl.textContent = '';
    try {
      await API.login(u, p);
      showApp();
    } catch (err) {
      errEl.textContent = err.message;
    }
  });

  // Register
  document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const u = document.getElementById('reg-user').value.trim();
    const p = document.getElementById('reg-pass').value;
    const c = document.getElementById('reg-code').value.trim().toUpperCase();
    const errEl = document.getElementById('reg-err');
    errEl.textContent = '';
    try {
      await API.register(u, p, c);
      showApp();
    } catch (err) {
      errEl.textContent = err.message;
    }
  });
}

// ── Navigation ────────────────────────────────────────────────────────────────
function initNavigation() {
  document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const section = btn.dataset.section;
      document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.app-section').forEach(s => s.classList.remove('active'));
      document.getElementById(`sec-${section}`).classList.add('active');
      state.section = section;
      loadSection(section);
    });
  });

  document.getElementById('logout-btn').addEventListener('click', () => {
    API.logout();
    document.getElementById('app').style.display = 'none';
    document.getElementById('login-screen').style.display = '';
  });
}

async function loadSection(section) {
  switch (section) {
    case 'predictions': await loadPredictions(); break;
    case 'rankings':    await loadRankings(); break;
    case 'players':     await loadPlayers(); break;
    case 'comparator':  initComparator(); break;
    case 'model':       break; // static
  }
}

// ── PREDICTIONS ───────────────────────────────────────────────────────────────
async function loadPredictions() {
  if (state.predictions) {
    renderPredictions(state.predictions, state.activePredFilter);
    return;
  }

  document.getElementById('predictions-grid').innerHTML =
    '<div class="loading-state"><div class="spinner"></div><p>Loading predictions…</p></div>';

  try {
    const data = await API.getPredictions();
    state.predictions = data.predictions;
    renderPredictions(state.predictions, 'all');
    initPredFilters();
  } catch (err) {
    document.getElementById('predictions-grid').innerHTML =
      `<div class="empty-state"><p>Failed to load: ${err.message}</p></div>`;
  }

  document.getElementById('refresh-pred-btn').addEventListener('click', () => {
    state.predictions = null;
    loadPredictions();
  });
}

function initPredFilters() {
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activePredFilter = btn.dataset.filter;
      renderPredictions(state.predictions, state.activePredFilter);
    });
  });
}

function renderPredictions(preds, filter) {
  const filtered = filter === 'all' ? preds : preds.filter(p => p.tournament === filter);
  const grid = document.getElementById('predictions-grid');

  if (!filtered.length) {
    grid.innerHTML = '<div class="empty-state"><p>No predictions for this tournament</p></div>';
    return;
  }

  grid.innerHTML = filtered.map(p => predCard(p)).join('');
}

function predCard(p) {
  const pct1 = Math.round(p.p1_win_prob * 100);
  const pct2 = 100 - pct1;
  const conf = p.confidence;
  const confClass = conf >= 0.35 ? 'conf-high' : conf >= 0.15 ? 'conf-medium' : 'conf-low';
  const confLabel = conf >= 0.35 ? 'High' : conf >= 0.15 ? 'Medium' : 'Low';

  const surf = (p.surface || 'Hard').toLowerCase().replace(' ', '-');
  const surfClass = `surf-${surf.includes('clay') ? 'clay' : surf.includes('grass') ? 'grass' : surf.includes('indoor') ? 'indoor' : 'hard'}`;
  const surfLabel = p.surface === 'Indoor Hard' ? 'Indoor' : p.surface;

  const isLive = p.status && (p.status.toLowerCase().includes('live') || p.status.toLowerCase().includes('progress') || p.status === 'inprogress');
  const liveTag = isLive ? '<span class="live-badge">● LIVE</span>' : '';
  const scoreTag = p.score ? `<span class="match-score">${p.score}</span>` : '';
  const hasPrediction = p.p1_win_prob && p.p1_win_prob !== 0.5;

  return `
<div class="pred-card${isLive ? ' pred-card--live' : ''}">
  <div class="pred-meta">
    <span class="pred-tournament">${p.tournament || 'Tournament'}</span>
    <div style="display:flex;gap:6px;align-items:center">
      ${liveTag}
      ${p.surface ? `<span class="pred-surface-tag ${surfClass}">${surfLabel}</span>` : ''}
      ${p.round ? `<span class="pred-round">${p.round}</span>` : ''}
    </div>
  </div>
  <div class="pred-matchup">
    <div class="pred-player">
      <div class="pred-player-name">${p.p1_name || '—'}</div>
      <div class="pred-player-rank">${p.p1_rank ? '#' + p.p1_rank : ''}${p.p1_elo ? ' · <span class="pred-elo-tag">Elo ' + p.p1_elo + '</span>' : ''}</div>
    </div>
    <div class="pred-vs">${scoreTag || 'VS'}</div>
    <div class="pred-player right">
      <div class="pred-player-name">${p.p2_name || '—'}</div>
      <div class="pred-player-rank">${p.p2_rank ? '#' + p.p2_rank : ''}${p.p2_elo ? ' · <span class="pred-elo-tag">Elo ' + p.p2_elo + '</span>' : ''}</div>
    </div>
  </div>
  ${hasPrediction ? `
  <div class="prob-bar-wrap">
    <div class="prob-bar">
      <div class="prob-fill" style="width:${pct1}%"></div>
    </div>
    <div class="prob-labels">
      <span class="prob-p1">${pct1}%</span>
      <span class="prob-p2">${pct2}%</span>
    </div>
  </div>
  <div class="pred-pick">
    <div>
      <div class="pick-label">MODEL PICK</div>
      <div class="pick-name">${p.p1_win_prob > 0.5 ? p.p1_name : p.p2_name}</div>
    </div>
    <span class="confidence-badge ${confClass}">${confLabel} confidence</span>
  </div>` : `<div class="pred-pick"><div class="pick-label" style="opacity:0.5">Partido en curso — sin predicción</div></div>`}
</div>`;
}

// ── OI RANKINGS ───────────────────────────────────────────────────────────────
async function loadRankings() {
  // Load OI chart data if not yet loaded
  if (!state.oiData) {
    try {
      state.oiData = await API.getOIHistory();
    } catch (e) {
      console.error('OI history load failed', e);
    }
  }

  if (!state.oiRankings) {
    try {
      const data = await API.getOIRankings(state.oiTour);
      state.oiRankings = data.rankings;
    } catch (e) {
      console.error('OI rankings load failed', e);
    }
  }

  if (state.oiData) renderOIChart(state.oiData);
  if (state.oiRankings) renderOITable(state.oiRankings);

  // Tour toggle
  document.querySelectorAll('.tour-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.tour-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.oiTour = btn.dataset.tour;
      state.oiRankings = null;
      const data = await API.getOIRankings(state.oiTour);
      state.oiRankings = data.rankings;
      renderOITable(state.oiRankings);
    });
  });

  // Spotlight close
  document.getElementById('sp-close-btn').addEventListener('click', () => {
    document.getElementById('player-spotlight').style.display = 'none';
  });
}

function renderOIChart(data) {
  const ctx = document.getElementById('oi-chart');
  if (!ctx) return;

  if (state.oiChart) {
    state.oiChart.destroy();
    state.oiChart = null;
  }

  const labels = data.labels || [];
  const series = data.series || {};
  const playerIds = Object.keys(series);

  // Init visible set (all on first load)
  if (state.visibleSeries.size === 0) {
    playerIds.forEach(id => state.visibleSeries.add(id));
  }

  const PLAYER_NAMES = {
    alcaraz_c:'Alcaraz', sinner_j:'Sinner', zverev_a:'Zverev',
    fritz_t:'Fritz', medvedev_d:'Medvedev', djokovic_n:'Djokovic',
    rublev_a:'Rublev', ruud_c:'Ruud', sabalenka_a:'Sabalenka',
    swiatek_i:'Świątek', gauff_c:'Gauff', rybakina_e:'Rybakina',
  };

  const datasets = playerIds.map((id, i) => ({
    label: PLAYER_NAMES[id] || id,
    playerId: id,
    data: series[id],
    borderColor: CHART_COLORS[i % CHART_COLORS.length],
    backgroundColor: 'transparent',
    borderWidth: 2,
    tension: 0.35,
    pointRadius: 0,
    pointHoverRadius: 5,
    hidden: !state.visibleSeries.has(id),
  }));

  state.oiChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#09142A',
          borderColor: 'rgba(255,255,255,.11)',
          borderWidth: 1,
          titleColor: '#7A96BC',
          bodyColor: '#EBF1FC',
          padding: 10,
          callbacks: {
            title: items => labels[items[0].dataIndex],
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,.04)' },
          ticks: { color: '#344E70', font: { family: "'JetBrains Mono'", size: 10 }, maxRotation: 0 },
        },
        y: {
          grid: { color: 'rgba(255,255,255,.04)' },
          ticks: { color: '#344E70', font: { family: "'JetBrains Mono'", size: 10 } },
        },
      },
      onClick(event, elements) {
        if (!elements.length) return;
        const el = elements[0];
        const ds = state.oiChart.data.datasets[el.datasetIndex];
        showPlayerSpotlight(ds.playerId, ds.label, ds.borderColor);
      },
    },
  });

  renderChartLegend(playerIds, PLAYER_NAMES);
}

function renderChartLegend(playerIds, names) {
  const legend = document.getElementById('chart-legend');
  if (!legend) return;

  legend.innerHTML = playerIds.map((id, i) => `
    <div class="legend-item${state.visibleSeries.has(id) ? '' : ' dimmed'}" data-id="${id}">
      <div class="legend-dot" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></div>
      <span class="legend-name">${names[id] || id}</span>
    </div>
  `).join('');

  legend.querySelectorAll('.legend-item').forEach((item, i) => {
    item.addEventListener('click', () => {
      const id = item.dataset.id;
      if (state.visibleSeries.has(id)) {
        state.visibleSeries.delete(id);
        item.classList.add('dimmed');
      } else {
        state.visibleSeries.add(id);
        item.classList.remove('dimmed');
      }
      if (state.oiChart) {
        const ds = state.oiChart.data.datasets.find(d => d.playerId === id);
        if (ds) {
          ds.hidden = !state.visibleSeries.has(id);
          state.oiChart.update();
        }
      }
    });

    // Click name to open spotlight
    item.addEventListener('dblclick', () => {
      const id = item.dataset.id;
      const name = item.querySelector('.legend-name').textContent;
      showPlayerSpotlight(id, name, CHART_COLORS[i % CHART_COLORS.length]);
    });
  });
}

function renderOITable(rankings) {
  const tbody = document.getElementById('oi-tbody');
  if (!tbody) return;

  // Detect if we have live data (points field present) or OI data
  const isLiveData = rankings.length > 0 && rankings[0].points !== undefined && rankings[0].oi === 0;

  tbody.innerHTML = rankings.map(r => {
    const flag = COUNTRY_FLAGS[r.country] || '🏳️';
    const oiClass = r.oi >= 0 ? 'oi-pos' : 'oi-neg';
    const oiSign = r.oi >= 0 ? '+' : '';
    if (isLiveData) {
      // Show real ATP/WTA ranking data
      return `
<tr>
  <td><span class="rank-num">${r.rank}</span></td>
  <td>
    <span class="player-name-cell" data-id="${r.id}" data-name="${r.name}">${flag} ${r.name}</span>
  </td>
  <td><span class="country-tag">${r.country}</span></td>
  <td class="num" style="color:var(--gold);font-family:var(--fm);font-weight:600">${(r.points || 0).toLocaleString()}</td>
  <td class="num" colspan="4" style="color:var(--fg3);font-size:11px">—</td>
  <td class="num" style="color:var(--blu);font-family:var(--fm)">${r.elo}</td>
  <td class="num" style="color:var(--fg3);font-family:var(--fm)">—</td>
</tr>`;
    }
    return `
<tr>
  <td><span class="rank-num">${r.rank}</span></td>
  <td>
    <span class="player-name-cell" data-id="${r.id}" data-name="${r.name}">${flag} ${r.name}</span>
  </td>
  <td><span class="country-tag">${r.country}</span></td>
  <td class="num"><span class="oi-val ${oiClass}">${oiSign}${(r.oi || 0).toFixed(1)}</span></td>
  <td class="num"><span class="oi-val ${(r.oi_hard||0) >= 0 ? 'oi-pos' : 'oi-neg'}">${(r.oi_hard||0) >= 0 ? '+' : ''}${(r.oi_hard||0).toFixed(1)}</span></td>
  <td class="num"><span class="oi-val ${(r.oi_clay||0) >= 0 ? 'oi-pos' : 'oi-neg'}">${(r.oi_clay||0) >= 0 ? '+' : ''}${(r.oi_clay||0).toFixed(1)}</span></td>
  <td class="num"><span class="oi-val ${(r.oi_grass||0) >= 0 ? 'oi-pos' : 'oi-neg'}">${(r.oi_grass||0) >= 0 ? '+' : ''}${(r.oi_grass||0).toFixed(1)}</span></td>
  <td class="num" style="color:var(--blu);font-family:var(--fm)">${r.elo}</td>
  <td class="num" style="color:var(--fg3);font-family:var(--fm)">${r.matches}</td>
</tr>`;
  }).join('');

  // Click on player name to open spotlight
  tbody.querySelectorAll('.player-name-cell').forEach(el => {
    el.addEventListener('click', () => {
      showPlayerSpotlight(el.dataset.id, el.dataset.name, '#D4A535');
    });
  });
}

// ── PLAYER SPOTLIGHT ──────────────────────────────────────────────────────────
async function showPlayerSpotlight(playerId, playerName, color) {
  const spotlight = document.getElementById('player-spotlight');
  spotlight.style.display = '';
  spotlight.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  // Update header
  document.getElementById('sp-name').textContent = playerName;
  document.getElementById('sp-name').style.color = color;

  // Find player in rankings for KPIs
  const ranking = state.oiRankings
    ? state.oiRankings.find(r => r.id === playerId) : null;

  const flag = ranking ? (COUNTRY_FLAGS[ranking.country] || '🏳️') : '';
  document.getElementById('sp-flag').textContent = flag;
  document.getElementById('sp-meta').textContent =
    ranking ? `${ranking.country} · Elo ${ranking.elo} · ${ranking.matches} matches` : playerId;

  // KPIs
  const kpis = document.getElementById('sp-kpis');
  if (ranking) {
    const oiSign = ranking.oi >= 0 ? '+' : '';
    kpis.innerHTML = `
      <div class="kpi-item">
        <div class="kpi-label">OI Total</div>
        <div class="kpi-value gold">${oiSign}${ranking.oi.toFixed(1)}</div>
      </div>
      <div class="kpi-item">
        <div class="kpi-label">Elo</div>
        <div class="kpi-value">${ranking.elo}</div>
      </div>
      <div class="kpi-item">
        <div class="kpi-label">OI Hard</div>
        <div class="kpi-value ${ranking.oi_hard >= 0 ? 'grn' : ''}">${ranking.oi_hard >= 0 ? '+' : ''}${ranking.oi_hard.toFixed(1)}</div>
      </div>
      <div class="kpi-item">
        <div class="kpi-label">OI Clay</div>
        <div class="kpi-value">${ranking.oi_clay >= 0 ? '+' : ''}${ranking.oi_clay.toFixed(1)}</div>
      </div>`;
  } else {
    kpis.innerHTML = '';
  }

  // Load season table
  document.getElementById('sp-tbody').innerHTML =
    '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--fg3)"><div class="spinner" style="margin:0 auto"></div></td></tr>';

  try {
    const data = await API.getPlayerSeasons(playerId);
    renderSeasonTable(data.seasons);
  } catch (e) {
    document.getElementById('sp-tbody').innerHTML =
      `<tr><td colspan="8" style="text-align:center;padding:16px;color:var(--fg3)">Season data unavailable</td></tr>`;
  }
}

function hmColor(val, all) {
  const mn = Math.min(...all), mx = Math.max(...all);
  if (mx === mn) return '';
  const t = (val - mn) / (mx - mn);
  if (t >= 0.62) {
    const i = (t - 0.62) / 0.38;
    return `rgba(24,201,106,${(0.08 + i * 0.28).toFixed(2)})`;
  }
  if (t <= 0.38) {
    const i = (0.38 - t) / 0.38;
    return `rgba(229,72,72,${(0.08 + i * 0.28).toFixed(2)})`;
  }
  return 'transparent';
}

function renderSeasonTable(seasons) {
  const tbody = document.getElementById('sp-tbody');
  if (!seasons || !seasons.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:16px;color:var(--fg3)">No season data</td></tr>';
    return;
  }

  const avgElos   = seasons.map(s => s.avg_elo);
  const startElos = seasons.map(s => s.start_elo);
  const endElos   = seasons.map(s => s.end_elo);
  const ois       = seasons.map(s => s.oi);

  tbody.innerHTML = seasons.map(s => {
    const delta = s.end_elo - s.start_elo;
    const deltaClass = delta >= 0 ? 'delta-pos' : 'delta-neg';
    const deltaSign  = delta >= 0 ? '+' : '';
    const oiSign     = s.oi >= 0 ? '+' : '';

    return `
<tr>
  <td style="font-family:var(--fm);color:var(--gold)">${s.season}</td>
  <td style="color:var(--fg2)">${s.level}</td>
  <td class="num">${s.matches}</td>
  <td class="num" style="background:${hmColor(s.avg_elo, avgElos)}">${s.avg_elo}</td>
  <td class="num" style="background:${hmColor(s.start_elo, startElos)}">${s.start_elo}</td>
  <td class="num" style="background:${hmColor(s.end_elo, endElos)}">${s.end_elo}</td>
  <td class="num"><span class="${deltaClass}">${deltaSign}${delta}</span></td>
  <td class="num"><span class="${s.oi >= 0 ? 'oi-pos' : 'oi-neg'}">${oiSign}${s.oi.toFixed(1)}</span></td>
</tr>`;
  }).join('');
}

// ── PLAYERS ───────────────────────────────────────────────────────────────────
async function loadPlayers() {
  if (!state.oiRankings) {
    // Load both tours to show all players
    try {
      const [atp, wta] = await Promise.all([
        API.getOIRankings('ATP'),
        API.getOIRankings('WTA'),
      ]);
      state.oiRankings = atp.rankings;
      state._allPlayers = [...atp.rankings, ...wta.rankings];
    } catch (e) {
      document.getElementById('players-grid').innerHTML =
        `<div class="empty-state"><p>Failed to load players: ${e.message}</p></div>`;
      return;
    }
  }

  const players = state._allPlayers || state.oiRankings || [];
  renderPlayersGrid(players);

  const search = document.getElementById('player-search');
  search.addEventListener('input', () => {
    const q = search.value.toLowerCase();
    const filtered = players.filter(p => p.name.toLowerCase().includes(q));
    renderPlayersGrid(filtered);
  });
}

function renderPlayersGrid(players) {
  const grid = document.getElementById('players-grid');
  if (!players.length) {
    grid.innerHTML = '<div class="empty-state"><p>No players found</p></div>';
    return;
  }

  grid.innerHTML = players.map(p => playerCard(p)).join('');

  grid.querySelectorAll('.player-card').forEach(card => {
    card.addEventListener('click', () => {
      // Switch to rankings tab and show spotlight
      document.querySelector('[data-section="rankings"]').click();
      setTimeout(() => showPlayerSpotlight(card.dataset.id, card.dataset.name, '#D4A535'), 300);
    });
  });
}

function playerCard(p) {
  const flag = COUNTRY_FLAGS[p.country] || '🏳️';
  const oiSign = p.oi >= 0 ? '+' : '';
  const oiColor = p.oi >= 0 ? 'var(--grn)' : 'var(--red)';

  // Surface bar — normalize oi_hard/clay/grass against total
  const total = Math.abs(p.oi_hard || 0) + Math.abs(p.oi_clay || 0) + Math.abs(p.oi_grass || 0) || 1;
  const hardPct  = Math.round(Math.max(0, p.oi_hard  || 0) / total * 100);
  const clayPct  = Math.round(Math.max(0, p.oi_clay  || 0) / total * 100);
  const grassPct = Math.round(Math.max(0, p.oi_grass || 0) / total * 100);

  return `
<div class="player-card" data-id="${p.id}" data-name="${p.name}">
  <div class="player-card-header">
    <div class="player-card-name">${flag} ${p.name}</div>
    <div class="player-card-rank">#${p.rank}</div>
  </div>
  <div style="font-size:11px;color:var(--fg3);font-family:var(--fm)">${p.country}</div>
  <div class="player-card-stats">
    <div class="pc-stat">
      <div class="pc-stat-label">OI</div>
      <div class="pc-stat-val" style="color:${oiColor}">${oiSign}${p.oi.toFixed(0)}</div>
    </div>
    <div class="pc-stat">
      <div class="pc-stat-label">Elo</div>
      <div class="pc-stat-val gold">${p.elo}</div>
    </div>
    <div class="pc-stat">
      <div class="pc-stat-label">Matches</div>
      <div class="pc-stat-val">${p.matches}</div>
    </div>
    <div class="pc-stat">
      <div class="pc-stat-label">Hard OI</div>
      <div class="pc-stat-val" style="font-size:13px">${p.oi_hard >= 0 ? '+' : ''}${(p.oi_hard||0).toFixed(0)}</div>
    </div>
  </div>
  <div class="surface-mini-bars">
    <div class="smb-row">
      <span class="smb-label" style="color:var(--blu)">Hard</span>
      <div class="smb-bar"><div class="smb-fill" style="width:${hardPct}%;background:var(--blu)"></div></div>
      <span class="smb-val">+${(p.oi_hard||0).toFixed(0)}</span>
    </div>
    <div class="smb-row">
      <span class="smb-label" style="color:var(--org)">Clay</span>
      <div class="smb-bar"><div class="smb-fill" style="width:${clayPct}%;background:var(--org)"></div></div>
      <span class="smb-val">+${(p.oi_clay||0).toFixed(0)}</span>
    </div>
    <div class="smb-row">
      <span class="smb-label" style="color:var(--grn)">Grass</span>
      <div class="smb-bar"><div class="smb-fill" style="width:${grassPct}%;background:var(--grn)"></div></div>
      <span class="smb-val">+${(p.oi_grass||0).toFixed(0)}</span>
    </div>
  </div>
</div>`;
}

// ── COMPARATOR ────────────────────────────────────────────────────────────────
function initComparator() {
  const players = state._allPlayers || state.oiRankings || [];
  if (!players.length) {
    // Try to load
    API.getOIRankings('ATP').then(data => {
      state.oiRankings = data.rankings;
      state._allPlayers = data.rankings;
      populateCompSelects(data.rankings);
    });
    return;
  }
  populateCompSelects(players);
}

function populateCompSelects(players) {
  const opts = players.map(p => `<option value="${p.id}" data-country="${p.country}">${COUNTRY_FLAGS[p.country] || ''} ${p.name}</option>`).join('');
  const base = '<option value="">Select player…</option>';
  document.getElementById('comp-p1').innerHTML = base + opts;
  document.getElementById('comp-p2').innerHTML = base + opts;

  document.getElementById('comp-p1').addEventListener('change', updateComparator);
  document.getElementById('comp-p2').addEventListener('change', updateComparator);
}

function updateComparator() {
  const p1Id = document.getElementById('comp-p1').value;
  const p2Id = document.getElementById('comp-p2').value;

  if (!p1Id || !p2Id || p1Id === p2Id) {
    document.getElementById('comp-content').style.display = 'none';
    document.getElementById('comp-empty').style.display = '';
    return;
  }

  const players = state._allPlayers || state.oiRankings || [];
  const p1 = players.find(p => p.id === p1Id);
  const p2 = players.find(p => p.id === p2Id);
  if (!p1 || !p2) return;

  document.getElementById('comp-content').style.display = '';
  document.getElementById('comp-empty').style.display = 'none';

  document.getElementById('comp-leg1').textContent = p1.name.split(' ').pop();
  document.getElementById('comp-leg2').textContent = p2.name.split(' ').pop();

  renderRadar(p1, p2);
  renderStatBars(p1, p2);
  renderWinProb(p1, p2);
}

function normalizeVal(val, maxVal) {
  return Math.min(100, Math.round((val / maxVal) * 100));
}

function renderRadar(p1, p2) {
  const ctx = document.getElementById('radar-chart');
  if (!ctx) return;
  if (state.radarChart) { state.radarChart.destroy(); state.radarChart = null; }

  // Normalize metrics 0-100
  const MAX_OI = 350, MAX_ELO = 2300, MAX_MATCHES = 500;

  const d1 = [
    normalizeVal(Math.max(0, p1.oi), MAX_OI),
    normalizeVal(p1.elo, MAX_ELO),
    normalizeVal(Math.max(0, p1.oi_hard), MAX_OI * 0.7),
    normalizeVal(Math.max(0, p1.oi_clay), MAX_OI * 0.5),
    normalizeVal(Math.max(0, p1.oi_grass), MAX_OI * 0.3),
    normalizeVal(p1.matches, MAX_MATCHES),
  ];
  const d2 = [
    normalizeVal(Math.max(0, p2.oi), MAX_OI),
    normalizeVal(p2.elo, MAX_ELO),
    normalizeVal(Math.max(0, p2.oi_hard), MAX_OI * 0.7),
    normalizeVal(Math.max(0, p2.oi_clay), MAX_OI * 0.5),
    normalizeVal(Math.max(0, p2.oi_grass), MAX_OI * 0.3),
    normalizeVal(p2.matches, MAX_MATCHES),
  ];

  state.radarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['OI Total', 'Elo', 'Hard OI', 'Clay OI', 'Grass OI', 'Matches'],
      datasets: [
        {
          label: p1.name,
          data: d1,
          borderColor: '#D4A535',
          backgroundColor: 'rgba(212,165,53,.12)',
          borderWidth: 2,
          pointBackgroundColor: '#D4A535',
          pointRadius: 4,
        },
        {
          label: p2.name,
          data: d2,
          borderColor: '#5B9CF6',
          backgroundColor: 'rgba(91,156,246,.10)',
          borderWidth: 2,
          pointBackgroundColor: '#5B9CF6',
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#09142A',
          borderColor: 'rgba(255,255,255,.11)',
          borderWidth: 1,
          titleColor: '#7A96BC',
          bodyColor: '#EBF1FC',
        },
      },
      scales: {
        r: {
          min: 0, max: 100,
          grid: { color: 'rgba(255,255,255,.06)' },
          angleLines: { color: 'rgba(255,255,255,.06)' },
          pointLabels: { color: '#7A96BC', font: { family: "'Outfit'", size: 11 } },
          ticks: { display: false, stepSize: 25 },
        },
      },
    },
  });
}

function renderStatBars(p1, p2) {
  const container = document.getElementById('stat-bars');
  const stats = [
    { label: 'OI Total', v1: p1.oi, v2: p2.oi, maxAbs: 350 },
    { label: 'Elo', v1: p1.elo - 1800, v2: p2.elo - 1800, maxAbs: 500 },
    { label: 'Hard OI', v1: p1.oi_hard, v2: p2.oi_hard, maxAbs: 250 },
    { label: 'Clay OI', v1: p1.oi_clay, v2: p2.oi_clay, maxAbs: 150 },
    { label: 'Grass OI', v1: p1.oi_grass, v2: p2.oi_grass, maxAbs: 100 },
  ];

  container.innerHTML = stats.map(s => {
    const mx = Math.max(Math.abs(s.v1), Math.abs(s.v2), 1);
    const pct1 = Math.min(100, Math.round((Math.abs(s.v1) / mx) * 100));
    const pct2 = Math.min(100, Math.round((Math.abs(s.v2) / mx) * 100));

    return `
<div class="stat-bar-row">
  <div class="sb-bar left">
    <div class="sb-fill gold-fill" style="width:${pct1}%"></div>
  </div>
  <div class="sb-label">${s.label}</div>
  <div class="sb-bar right">
    <div class="sb-fill blue-fill" style="width:${pct2}%"></div>
  </div>
</div>`;
  }).join('');
}

function renderWinProb(p1, p2) {
  const eloDiff = p1.elo - p2.elo;
  const oiDiff  = p1.oi - p2.oi;
  const raw = 0.5 + (eloDiff / 400) * 0.4 + (oiDiff / 400) * 0.2;
  const p1Prob = Math.max(0.1, Math.min(0.9, raw));

  const container = document.getElementById('win-prob-display');
  container.innerHTML = `
<div class="wp-names">
  <span style="color:var(--gold)">${p1.name}</span>
  <span style="color:var(--blu)">${p2.name}</span>
</div>
<div class="wp-bar">
  <div class="wp-fill" style="width:${Math.round(p1Prob * 100)}%"></div>
</div>
<div class="wp-probs">
  <span style="color:var(--gold)">${Math.round(p1Prob * 100)}%</span>
  <span style="color:var(--blu)">${Math.round((1 - p1Prob) * 100)}%</span>
</div>
<p style="font-size:11px;color:var(--fg3);text-align:center;margin-top:8px;font-family:var(--fm)">
  Estimated from Elo + OI differential — not a live model prediction
</p>`;
}

// ── MODEL SECTION ────────────────────────────────────────────────────────────
function initModelSection() {
  const grid = document.getElementById('features-grid');
  if (!grid) return;
  grid.innerHTML = FEATS_V6.map((f, i) => `
<div class="feature-item">
  <span class="feat-idx">${String(i + 1).padStart(2, '0')}</span>
  <span class="feat-name">${f}</span>
</div>`).join('');
}
