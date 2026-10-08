/**
 * TennisModel KCR — API client
 * Handles JWT auth token storage and all API calls to the FastAPI backend.
 */

const API = (() => {
  const BASE = '';  // Same origin — FastAPI serves both API and frontend

  // ── Token storage ──────────────────────────────────────────────────────────
  let _token = null;
  let _username = null;

  function saveToken(token, username) {
    _token = token;
    _username = username;
    try {
      localStorage.setItem('kcr_token', token);
      localStorage.setItem('kcr_user', username);
    } catch (_) {}
  }

  function loadToken() {
    try {
      _token = localStorage.getItem('kcr_token');
      _username = localStorage.getItem('kcr_user');
    } catch (_) {}
    return !!_token;
  }

  function clearToken() {
    _token = null;
    _username = null;
    try {
      localStorage.removeItem('kcr_token');
      localStorage.removeItem('kcr_user');
    } catch (_) {}
  }

  function getUsername() { return _username; }
  function isLoggedIn() { return !!_token; }

  // ── Core fetch wrapper ─────────────────────────────────────────────────────
  async function request(path, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (_token && path !== '/api/auth/token' && path !== '/api/auth/register') {
      headers['Authorization'] = `Bearer ${_token}`;
    }

    const res = await fetch(BASE + path, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      clearToken();
      window.location.reload();
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { const d = await res.json(); msg = d.detail || msg; } catch (_) {}
      throw new Error(msg);
    }

    return res.json();
  }

  // ── Auth ───────────────────────────────────────────────────────────────────
  async function login(username, password) {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${BASE}/api/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });

    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || 'Login failed');
    }

    const data = await res.json();
    saveToken(data.access_token, data.username);
    return data;
  }

  async function register(username, password, inviteCode) {
    const data = await request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, invite_code: inviteCode }),
    });
    saveToken(data.access_token, data.username);
    return data;
  }

  function logout() {
    clearToken();
  }

  // ── Rankings ───────────────────────────────────────────────────────────────
  async function getOIRankings(tour = 'ATP') {
    return request(`/api/rankings/oi?tour=${tour}&limit=1000`);
  }

  async function getOIHistory() {
    return request('/api/rankings/oi/history');
  }

  async function getATPRankings() {
    return request('/api/rankings/atp?limit=100');
  }

  async function getWTARankings() {
    return request('/api/rankings/wta?limit=50');
  }

  // ── Predictions ────────────────────────────────────────────────────────────
  async function getPredictions() {
    return request('/api/predictions/upcoming');
  }

  async function predictMatch(features) {
    return request('/api/predictions/predict', {
      method: 'POST',
      body: JSON.stringify(features),
    });
  }

  async function getModelInfo() {
    return request('/api/predictions/model-info');
  }

  // ── Players ────────────────────────────────────────────────────────────────
  async function getPlayerSeasons(playerId) {
    return request(`/api/players/${playerId}/seasons`);
  }

  async function getPlayerProfile(playerId) {
    return request(`/api/players/${playerId}/profile`);
  }

  // ── Health ─────────────────────────────────────────────────────────────────
  async function health() {
    return request('/api/health');
  }

  return {
    loadToken, saveToken, clearToken, isLoggedIn, getUsername,
    login, register, logout,
    getOIRankings, getOIHistory, getATPRankings, getWTARankings,
    getPredictions, predictMatch, getModelInfo,
    getPlayerSeasons, getPlayerProfile,
    health,
  };
})();
