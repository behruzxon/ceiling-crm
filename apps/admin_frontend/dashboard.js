/* SystemaX Admin Dashboard — vanilla JS */
'use strict';

const API = (localStorage.getItem('sx_api_url') || 'http://localhost:8000');
const TOKEN_KEY = 'sx_token';

// ── Auth helpers ──────────────────────────────────────────────────────────────

function getToken() { return localStorage.getItem(TOKEN_KEY); }

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  window.location.href = 'index.html';
}

async function apiFetch(path, opts) {
  const token = getToken();
  if (!token) { logout(); return null; }

  const res = await fetch(API + path, Object.assign({
    headers: Object.assign({
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token,
    }, (opts && opts.headers) || {}),
  }, opts));

  if (res.status === 401) { logout(); return null; }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Navigation ────────────────────────────────────────────────────────────────

function showSection(id) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const sec = document.getElementById('section-' + id);
  const nav = document.querySelector('[data-section="' + id + '"]');
  if (sec) sec.classList.add('active');
  if (nav) nav.classList.add('active');
  document.getElementById('topbar-title').textContent = id.charAt(0).toUpperCase() + id.slice(1);

  const loaders = {
    dashboard: loadDashboard,
    leads: loadLeads,
    chats: loadChats,
    analytics: loadAnalytics,
    billing: loadBilling,
  };
  if (loaders[id]) loaders[id]();
}

// ── Dashboard overview ────────────────────────────────────────────────────────

async function loadDashboard() {
  const el = document.getElementById('dashboard-cards');
  el.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const data = await apiFetch('/admin/api/analytics/overview');
    if (!data) return;
    el.innerHTML = [
      card('Total Leads', data.total_leads, 'All time'),
      card('Today', data.leads_today, 'New leads today'),
      card('This Week', data.leads_7d, 'Last 7 days'),
      card('Hot', data.hot_leads, 'Score 70-100', 'color:#f87171'),
      card('Warm', data.warm_leads, 'Score 35-69', 'color:#fb923c'),
      card('Conversion', (data.conversion_rate * 100).toFixed(1) + '%', 'Won / total'),
      card('AI Today', data.ai_messages_today, 'Messages processed'),
      card('Attention', data.attention_queue, 'Need follow-up'),
    ].join('');
  } catch (e) {
    el.innerHTML = '<div class="empty">Failed to load dashboard: ' + e.message + '</div>';
  }
}

function card(title, value, sub, extraStyle) {
  return '<div class="card">'
    + '<div class="card-title">' + title + '</div>'
    + '<div class="card-value"' + (extraStyle ? ' style="' + extraStyle + '"' : '') + '>' + value + '</div>'
    + '<div class="card-sub">' + sub + '</div>'
    + '</div>';
}

// ── Leads ─────────────────────────────────────────────────────────────────────

var leadsPage = 1;

async function loadLeads(reset) {
  if (reset) leadsPage = 1;
  const tbody = document.getElementById('leads-tbody');
  tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading…</td></tr>';

  const status = document.getElementById('leads-filter-status').value;
  const source = document.getElementById('leads-filter-source').value;
  const qs = '?page=' + leadsPage + '&limit=20'
    + (status ? '&lead_status=' + status : '')
    + (source ? '&source=' + source : '');

  try {
    const leads = await apiFetch('/admin/api/leads' + qs);
    if (!leads) return;
    if (!leads.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">No leads found.</td></tr>';
      return;
    }
    tbody.innerHTML = leads.map(function(l) {
      var chip = l.lead_status
        ? '<span class="chip chip-' + l.lead_status + '">' + l.lead_status + '</span>'
        : '<span class="chip chip-none">—</span>';
      return '<tr>'
        + '<td>' + l.id + '</td>'
        + '<td>' + esc(l.name) + '</td>'
        + '<td>' + esc(l.phone) + '</td>'
        + '<td>' + esc(l.district) + '</td>'
        + '<td>' + esc(l.source) + '</td>'
        + '<td>' + chip + '</td>'
        + '<td>' + fmtDate(l.created_at) + '</td>'
        + '</tr>';
    }).join('');

    document.getElementById('leads-page-info').textContent = 'Page ' + leadsPage;
    document.getElementById('leads-prev').disabled = leadsPage <= 1;
    document.getElementById('leads-next').disabled = leads.length < 20;
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">Error: ' + e.message + '</td></tr>';
  }
}

// ── Chats ─────────────────────────────────────────────────────────────────────

var chatsPage = 1;

async function loadChats(reset) {
  if (reset) chatsPage = 1;
  const list = document.getElementById('chat-list');
  list.innerHTML = '<div class="loading">Loading…</div>';
  document.getElementById('chat-messages').innerHTML =
    '<div class="empty">Select a conversation</div>';

  try {
    const chats = await apiFetch('/admin/api/chats?page=' + chatsPage + '&limit=20');
    if (!chats) return;
    if (!chats.length) {
      list.innerHTML = '<div class="empty">No conversations yet.</div>';
      return;
    }
    list.innerHTML = chats.map(function(c) {
      return '<div class="chat-item" onclick="openChat(' + c.user_id + ')">'
        + '<div class="chat-item-id">User #' + c.user_id + ' &bull; ' + c.message_count + ' msgs</div>'
        + '<div class="chat-item-preview">' + esc(c.last_message || '—') + '</div>'
        + '<div class="chat-item-time">' + fmtDate(c.updated_at) + '</div>'
        + '</div>';
    }).join('');
    document.getElementById('chats-page-info').textContent = 'Page ' + chatsPage;
    document.getElementById('chats-prev').disabled = chatsPage <= 1;
    document.getElementById('chats-next').disabled = chats.length < 20;
  } catch (e) {
    list.innerHTML = '<div class="empty">Error: ' + e.message + '</div>';
  }
}

async function openChat(userId) {
  document.querySelectorAll('.chat-item').forEach(function(el) {
    el.classList.toggle('active', el.textContent.includes('User #' + userId));
  });
  const msgEl = document.getElementById('chat-messages');
  msgEl.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const chat = await apiFetch('/admin/api/chats/' + userId);
    if (!chat) return;
    if (!chat.messages.length) {
      msgEl.innerHTML = '<div class="empty">No messages in this conversation.</div>';
      return;
    }
    msgEl.innerHTML = chat.messages.map(function(m) {
      var cls = m.role === 'user' ? 'msg-user' : 'msg-assistant';
      return '<div class="msg-bubble ' + cls + '">' + esc(m.text) + '</div>';
    }).join('');
    msgEl.scrollTop = msgEl.scrollHeight;
  } catch (e) {
    msgEl.innerHTML = '<div class="empty">Error: ' + e.message + '</div>';
  }
}

// ── Analytics ─────────────────────────────────────────────────────────────────

async function loadAnalytics() {
  document.getElementById('analytics-content').innerHTML = '<div class="loading">Loading…</div>';
  try {
    const [overview, bySource] = await Promise.all([
      apiFetch('/admin/api/analytics/overview'),
      apiFetch('/admin/api/analytics/leads-by-source'),
    ]);
    if (!overview || !bySource) return;

    const total = Object.values(bySource).reduce(function(a, b) { return a + b; }, 0) || 1;
    const bars = Object.entries(bySource).map(function(e) {
      var pct = Math.round(e[1] / total * 100);
      return '<div class="source-row">'
        + '<div class="source-label">' + esc(e[0]) + '</div>'
        + '<div class="source-track"><div class="source-fill" style="width:' + pct + '%"></div></div>'
        + '<div class="source-count">' + e[1] + '</div>'
        + '</div>';
    }).join('');

    document.getElementById('analytics-content').innerHTML =
      '<div class="cards-grid">'
      + card('Total Leads', overview.total_leads, 'All time')
      + card('Leads Today', overview.leads_today, 'Created today')
      + card('This Week', overview.leads_7d, 'Last 7 days')
      + card('Conversion', (overview.conversion_rate * 100).toFixed(1) + '%', 'Won / total')
      + card('AI Today', overview.ai_messages_today, 'Processed today')
      + card('AI 7-day', overview.ai_messages_7d, 'Last 7 days')
      + '</div>'
      + '<div class="card"><div class="card-title">Leads by Source</div>'
      + '<div class="source-bar">' + bars + '</div></div>';
  } catch (e) {
    document.getElementById('analytics-content').innerHTML =
      '<div class="empty">Error: ' + e.message + '</div>';
  }
}

// ── Billing ───────────────────────────────────────────────────────────────────

async function loadBilling() {
  const el = document.getElementById('billing-content');
  el.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const b = await apiFetch('/admin/api/billing/status');
    if (!b) return;

    var statusClass = 'chip-' + (b.billing_status === 'active' ? 'active' : b.billing_status);
    var expiry = b.subscription_expires_at
      ? fmtDate(b.subscription_expires_at)
      : (b.trial_ends_at ? 'Trial until ' + fmtDate(b.trial_ends_at) : '—');

    el.innerHTML =
      '<div class="cards-grid">'
      + '<div class="card"><div class="card-title">Plan</div><div class="card-value" style="text-transform:uppercase;font-size:1.4rem">' + esc(b.plan) + '</div>'
      + '<div class="card-sub"><span class="chip ' + statusClass + '">' + esc(b.billing_status) + '</span></div></div>'
      + card('Expiry', expiry, b.billing_status === 'trial' ? 'Trial period' : 'Subscription end')
      + card('Leads Used', (b.leads_used !== null ? b.leads_used : '—'), 'of ' + (b.leads_limit !== null ? b.leads_limit : '?') + ' this month')
      + card('AI Messages', (b.ai_messages_used !== null ? b.ai_messages_used : '—'), 'of ' + (b.ai_messages_limit !== null ? b.ai_messages_limit : '?') + ' today')
      + '</div>';
  } catch (e) {
    el.innerHTML = '<div class="empty">Error: ' + e.message + '</div>';
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    var d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  } catch (_) { return iso; }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

(async function init() {
  if (!getToken()) { window.location.href = 'index.html'; return; }

  // Load admin name
  try {
    const me = await apiFetch('/admin/api/auth/me');
    if (me) {
      document.getElementById('admin-name').textContent = me.name + ' (' + me.email + ')';
    }
  } catch (_) {}

  // Wire nav clicks
  document.querySelectorAll('.nav-item[data-section]').forEach(function(el) {
    el.addEventListener('click', function() { showSection(el.dataset.section); });
  });

  // Wire leads filters
  document.getElementById('leads-filter-status').addEventListener('change', function() { loadLeads(true); });
  document.getElementById('leads-filter-source').addEventListener('change', function() { loadLeads(true); });

  // Wire leads pagination
  document.getElementById('leads-prev').addEventListener('click', function() {
    if (leadsPage > 1) { leadsPage--; loadLeads(); }
  });
  document.getElementById('leads-next').addEventListener('click', function() {
    leadsPage++; loadLeads();
  });

  // Wire chats pagination
  document.getElementById('chats-prev').addEventListener('click', function() {
    if (chatsPage > 1) { chatsPage--; loadChats(); }
  });
  document.getElementById('chats-next').addEventListener('click', function() {
    chatsPage++; loadChats();
  });

  // Wire logout
  document.getElementById('logout-btn').addEventListener('click', logout);

  // Show default section
  showSection('dashboard');
})();
