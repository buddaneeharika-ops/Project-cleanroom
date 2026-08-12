/* ═══════════════════════════════════════════════════════════════════════════
   app.js — Form 20 Backlog Dashboard
   ═══════════════════════════════════════════════════════════════════════════ */
'use strict';

let allRecords    = [];
let selectedIds   = new Set();
let sortCol       = 'key';
let sortDir       = 'asc';
let stateSortCol  = 'state';   // states-grouped view: 'state' | 'count'
let stateSortDir  = 'asc';
let editingId     = null;
let toastTimer    = null;
let searchTimer   = null;
let retroMetadata = null;
let filterMetadata = null;
let currentView   = 'states';
let currentDetailState = null;

const filters = {
  state: '', el_type: '', year: '', status: '', sir_only: false, search: '', wip: false, show_bp: false,
};

let activeKpi  = null;
let pieChart   = null;
let barChart   = null;

// Dashboard-only filters (BP hidden by default)
let dashShowBp   = false;
let dashSirOnly  = false;
let dashWeekFilter = '';   // week start date string e.g. "2026-06-01"

let monthlyChart    = null;
let _missingACsTotal = 0;  // total ACs across the 262 mapping entries not yet in Form 20
let _f20TotalYears  = 0;   // form20 distinct years (from SQLite stats)
let _f20Total       = 0;   // form20 total election entries (from SQLite stats)
let _f20ByType      = {};  // form20 by_type from SQLite stats (completed/total per type)

// Glance Report chart instances
let gWeekChart  = null;
let gStateChart = null;
let gCasteChart = null;
let gF20Chart   = null;
let gRetroChart = null;
let gBoothChart = null;

const EL_TYPE_NAMES = { AE: 'Assembly', GE: 'General', BE: 'Bypoll', PE: 'Parliament', LE: 'Local', AC: 'Assembly' };
const STATE_NAMES_MAP = {};  // populated lazily from filter dropdown

const STATUS_CONFIG = {
  'missing':    { bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-100',     dot: 'bg-red-400',     label: 'Not Downloaded' },
  'pending':    { bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-100',   dot: 'bg-amber-400',   label: 'Pending'   },
  'downloaded': { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-100',    dot: 'bg-blue-400',    label: 'Downloaded'},
  'extracted':  { bg: 'bg-violet-50',  text: 'text-violet-700',  border: 'border-violet-100',  dot: 'bg-violet-400',  label: 'Extracted' },
  'completed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', label: 'Completed' },
  'db_pushed':  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', label: 'DB Pushed' },
};

// Bucket a free-text "not downloaded" remark into one short, Status-column-friendly
// label. Categories were derived from the actual recorded reasons; the full original
// note is preserved as a hover tooltip. Order matters: specific checks first, then a
// catch-all of "no usable ECI/CEO source".
function reasonCategory(remark) {
  const r = String(remark || '').trim().toLowerCase();
  if (!r) return null;
  if (r.includes('not in existence')) return 'Not in Existence';
  if (r.includes('not present on drive') || r.includes('local pdf')) return 'Pending Drive Upload';
  if (r.includes('not retrievable') || r.includes('http 500') ||
      r.includes('url was unavailable') || r.includes('source url') ||
      r.includes('returning http')) return 'Source Link Broken';
  return 'Not Available on ECI';
}

// Canonical AC counts per state (from ac_mapping; same across years/types)
const STATE_AC_COUNTS = {
  'AP': 175, 'AR': 60,  'AS': 126, 'BR': 243, 'CG': 90,  'CT': 90,  'GA': 40,
  'GJ': 182, 'HR': 90,  'HP': 68,  'JH': 81,  'KA': 224, 'KL': 140, 'MP': 230,
  'MH': 288, 'MN': 60,  'ML': 60,  'MZ': 40,  'NL': 60,  'OR': 147, 'PB': 117,
  'RJ': 200, 'SK': 32,  'TN': 234, 'TS': 119, 'TR': 60,  'UP': 403, 'UK': 70,
  'WB': 294, 'DL': 70,  'PY': 30,  'JK': 90,  'LD': 1,   'AN': 1,   'CH': 1
};

document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  // bindEvents() restores the last-viewed tab (default: Dashboard) and runs that
  // view's data load, so we don't eagerly load the dashboard here.
  bindEvents();
});

async function loadFilters() {
  try {
    const data = await apiFetch('/api/filters');
    filterMetadata = data.metadata;
    const stateNames = data.state_names;

    const stateEl = document.getElementById('filter-state');
    stateEl.innerHTML = '<option value="">All States</option>';
    Object.keys(filterMetadata).sort().forEach(s => {
      stateEl.appendChild(new Option(`${s} — ${stateNames[s]}`, s));
    });

    document.getElementById('filter-type').innerHTML = '<option value="">All Types</option>';
    document.getElementById('filter-type').disabled = true;
    document.getElementById('filter-year').innerHTML = '<option value="">All Years</option>';
    document.getElementById('filter-year').disabled = true;
  } catch (e) { console.error('loadFilters:', e); }
}

async function loadStats() {
  const params = new URLSearchParams();
  // NOTE: the pipeline strip always reflects the FULL pipeline for the current
  // scope (state/type/year/SIR/BP). It deliberately ignores filters.status/wip so
  // that selecting a stage (via KPI card or sidebar) filters only the table, not
  // the strip — keeping the strip stable across KPI and sidebar clicks alike.
  if (filters.state)    params.set('state',    filters.state);
  if (filters.el_type)  params.set('el_type',  filters.el_type);
  if (filters.year)     params.set('year',     filters.year);
  if (filters.sir_only) params.set('sir_only', '1');
  if (filters.search)   params.set('search',   filters.search);
  if (!filters.show_bp) params.set('hide_bp',  '1');

  try {
    const s = await apiFetch('/api/stats?' + params);
    const bs = s.by_status || {};
    const total = s.total || 0;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? '0'; };
    // Sidebar is the single home for per-stage counts. Completed records are hidden
    // from this page, so "All Remaining" = Not Downloaded + Downloaded + Extracted.
    set('sl-all-count', (bs.missing || 0) + (bs.pending || 0) + (bs.downloaded || 0) + (bs.extracted || 0));
    set('sl-dl-count',  bs.downloaded || '0');
    set('sl-ex-count',  bs.extracted  || '0');
    set('sl-mi-count',  bs.missing    || '0');
    set('sl-wip-count', s.wip_count   || '0');

    const completed = (bs.db_pushed || 0) + (bs.completed || 0);

    // Sidebar progress footer — the single home for overall completion + pipeline mix.
    const segW = (id, n) => {
      const el = document.getElementById(id);
      if (el) el.style.width = (total > 0 ? (n / total) * 100 : 0) + '%';
    };
    segW('seg-completed',  completed);
    segW('seg-extracted',  bs.extracted  || 0);
    segW('seg-downloaded', bs.downloaded || 0);

    // The headline % and "x / y" text use AC-wise coverage (same metric as the
    // Form 20 dashboard panel), so the two numbers stay consistent.
    const ac = s.ac_coverage || {};
    const acPct = ac.pct || 0;
    set('progress-text', `${(ac.form20_acs || 0).toLocaleString()} / ${(ac.mapping_acs || 0).toLocaleString()} ACs completed`);
    const pctSidebar = document.getElementById('progress-pct-sidebar');
    if (pctSidebar) pctSidebar.textContent = acPct + '%';
  } catch (e) { console.error('loadStats:', e); }

  updateRecordBadge();
}

// Header badge: just how many elections the current filters show.
function updateRecordBadge() {
  const badge = document.getElementById('record-count-badge');
  if (!badge) return;
  const count = allRecords.length;
  badge.textContent = count === 1 ? '1 election' : `${count.toLocaleString()} elections`;
}

async function loadRecords() {
  const params = new URLSearchParams();
  if (filters.state)    params.set('state',    filters.state);
  if (filters.el_type)  params.set('el_type',  filters.el_type);
  if (filters.year)     params.set('year',     filters.year);
  if (filters.status)   params.set('status',   filters.status);
  if (filters.sir_only) params.set('sir_only', '1');
  if (filters.wip)      params.set('wip', '1');
  if (filters.search)   params.set('search',   filters.search);
  if (!filters.show_bp) params.set('hide_bp',  '1');

  try {
    allRecords = await apiFetch('/api/records?' + params);
    renderTable();
  } catch (e) {
    document.getElementById('table-body').innerHTML =
      `<tr><td colspan="4" class="px-5 py-10 text-center text-gray-500 text-[12px]">Failed to load — ${e.message}</td></tr>`;
  }
}

function renderTable() {
  const tbody = document.getElementById('table-body');
  const thead = document.getElementById('table-head');
  updateRecordBadge();

  if (!allRecords.length) {
    tbody.innerHTML = `
      <tr><td colspan="4" class="px-5 py-12 text-center">
        <div class="flex flex-col items-center gap-2 text-gray-400">
          <span class="material-symbols-outlined" style="font-size:28px;">search_off</span>
          <p class="text-[12px]">No records match the current filters.</p>
        </div>
      </td></tr>`;
    document.getElementById('pagination-text').textContent = 'Showing 0 records';
    return;
  }

  if (currentView === 'states') {
    // ── State grouped view ──────────────────────────────────────────────────
    const grouped = {};
    allRecords.forEach(rec => {
      const s = rec.state_name || rec.state;
      if (!grouped[s]) grouped[s] = [];
      grouped[s].push(rec);
    });

    const stateKeys = Object.keys(grouped).sort((a, b) => {
      let cmp;
      if (stateSortCol === 'count') cmp = grouped[a].length - grouped[b].length;
      else cmp = a.localeCompare(b);
      return stateSortDir === 'asc' ? cmp : -cmp;
    });

    document.getElementById('pagination-text').textContent =
      `${allRecords.length} remaining elections across ${stateKeys.length} states`;

    const arrow = col => stateSortCol === col
      ? `<span class="ml-0.5">${stateSortDir === 'asc' ? '▲' : '▼'}</span>` : '';

    thead.innerHTML = `
      <tr>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-50 select-none st-sortable" data-col="state">State${arrow('state')}</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-50 select-none st-sortable" data-col="count">Remaining${arrow('count')}</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider w-[40%]">Pipeline</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider text-right">Open</th>
      </tr>`;

    let html = '';
    stateKeys.forEach(s => {
      const records = grouped[s];
      let missing = 0, extracted = 0, downloaded = 0;
      records.forEach(r => {
        const st = r.overall_status;
        if (st === 'missing')         missing++;
        else if (st === 'extracted')  extracted++;
        else if (st === 'downloaded') downloaded++;
      });
      const chips = [
        missing    > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-gray-100 text-gray-500 border border-gray-200 px-2 py-0.5 rounded-full">${missing} Not Downloaded</span>` : '',
        downloaded > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full">${downloaded} Downloaded</span>` : '',
        extracted  > 0 ? `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold bg-violet-50 text-violet-700 border border-violet-100 px-2 py-0.5 rounded-full">${extracted} Extracted</span>` : '',
      ].filter(Boolean).join('');

      const stateCode = records[0]?.state;
      const canonicalAC = STATE_AC_COUNTS[stateCode] || 0;
      const totalStateACs = canonicalAC > 0 ? (records.length * canonicalAC).toLocaleString() : '';

      html += `
        <tr class="trow bg-white border-b border-gray-50 cursor-pointer transition-colors"
            onclick="openStateDetail('${s.replace(/'/g, "\\'")}')">
          <td class="px-5 py-3">
            <div class="flex items-center gap-3">
              <div class="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-gray-400" style="font-size:13px;">map</span>
              </div>
              <p class="text-[13px] font-semibold text-gray-900">${x(s)}</p>
            </div>
          </td>
          <td class="px-5 py-3 whitespace-nowrap">
            <span class="text-[13px] font-semibold text-gray-700 tabular-nums">${records.length}</span>
            <span class="text-[11px] text-gray-400 ml-1">elections</span>
            ${totalStateACs ? `<span class="text-[11px] text-gray-400 ml-1">(${totalStateACs} ACs)</span>` : ''}
          </td>
          <td class="px-5 py-3">
            <div class="flex items-center gap-1.5 flex-wrap">${chips || '<span class="text-[11px] text-gray-300">—</span>'}</div>
          </td>
          <td class="px-5 py-3 text-right">
            <span class="material-symbols-outlined text-gray-300" style="font-size:16px;">chevron_right</span>
          </td>
        </tr>`;
    });
    tbody.innerHTML = html;

    thead.querySelectorAll('.st-sortable').forEach(th => {
      th.addEventListener('click', () => {
        const c = th.dataset.col;
        stateSortDir = stateSortCol === c && stateSortDir === 'asc' ? 'desc' : 'asc';
        stateSortCol = c;
        renderTable();
      });
    });

  } else {
    // ── Detail view (records for a single state) ───────────────────────────
    const records = allRecords
      .filter(r => (r.state_name || r.state) === currentDetailState)
      .sort((a, b) => {
        let va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
        if (typeof va === 'string') { va = va.toLowerCase(); vb = vb.toLowerCase(); }
        if (va < vb) return sortDir === 'asc' ? -1 : 1;
        if (va > vb) return sortDir === 'asc' ?  1 : -1;
        return 0;
      });

    document.getElementById('pagination-text').textContent =
      `${records.length} remaining elections in ${currentDetailState}`;

    const arrow = col => sortCol === col
      ? `<span class="ml-0.5">${sortDir === 'asc' ? '▲' : '▼'}</span>` : '';

    thead.innerHTML = `
      <tr>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-50 select-none sortable" data-col="key">Record ID${arrow('key')}</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider">Status</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-50 select-none sortable" data-col="el_year">Election${arrow('el_year')}</th>
        <th class="px-5 py-3 text-[10.5px] font-semibold text-gray-400 uppercase tracking-wider text-right">Actions</th>
      </tr>`;

    tbody.innerHTML = records.map(rec => {
      const sel = selectedIds.has(rec.id);
      const cfg = STATUS_CONFIG[rec.overall_status] || STATUS_CONFIG['missing'];
      const rowClass = sel ? 'trow-selected' : 'trow';

      return `
        <tr class="${rowClass} bg-white border-b border-gray-50 transition-colors" data-id="${rec.id}">
          <td class="px-5 py-2.5 align-top cursor-pointer" onclick="openModal(${rec.id})">
            <p class="text-[12.5px] font-semibold text-gray-900 leading-tight">${x(rec.key)}</p>
            ${rec.is_sir_state ? '<p class="text-[11px] text-amber-600 font-medium mt-0.5">SIR Priority</p>' : ''}
          </td>
          <td class="px-5 py-2.5 align-top">
            <div class="flex flex-col items-start gap-1">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${cfg.bg} ${cfg.text} ${cfg.border}">
                <span class="w-1.5 h-1.5 rounded-full ${cfg.dot} shrink-0"></span>
                ${cfg.label}
              </span>
              ${rec.overall_status === 'missing'
                ? `<span class="text-[10.5px] text-gray-500 leading-tight" title="${x(rec.remark || '')}">${x(reasonCategory(rec.remark) || 'Reason not recorded')}</span>`
                : ''}
            </div>
          </td>
          <td class="px-5 py-2.5 align-top">
            <p class="text-[12.5px] font-medium text-gray-700">${x(EL_TYPE_NAMES[String(rec.el_type).split('-')[0]] || rec.el_type)}${String(rec.el_type).includes('-BP') ? ' Bypoll' : ''} · ${rec.el_year}</p>
          </td>
          <td class="px-5 py-2.5 align-top text-right">
            <div class="flex items-center justify-end gap-1.5">
              <button class="btn-wip flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold border transition-colors
                ${rec.wip
                  ? 'bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100'
                  : 'bg-white text-gray-400 border-gray-200 hover:bg-gray-50 hover:text-gray-600'}"
                data-id="${rec.id}" title="Toggle LF In Progress">
                <span class="material-symbols-outlined" style="font-size:13px;">${rec.wip ? 'hourglass_top' : 'hourglass_empty'}</span>
                LF WIP
              </button>
              <button class="btn-edit p-1.5 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-gray-700 transition-colors" data-id="${rec.id}">
                <span class="material-symbols-outlined" style="font-size:15px;">edit</span>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');

    tbody.querySelectorAll('.btn-wip').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        const id = +e.currentTarget.dataset.id;
        const rec = allRecords.find(r => r.id === id);
        if (!rec) return;
        try {
          const updated = await apiFetch(`/api/records/${id}`, 'PATCH', { wip: rec.wip ? 0 : 1 });
          const idx = allRecords.findIndex(r => r.id === id);
          if (idx >= 0) allRecords[idx] = updated;
          renderTable(); loadStats();
        } catch (err) {
          showToast('Failed to update WIP status', true);
        }
      });
    });

    tbody.querySelectorAll('.btn-edit').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        openModal(+e.currentTarget.dataset.id);
      });
    });

    thead.querySelectorAll('.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const c = th.dataset.col;
        sortDir = sortCol === c && sortDir === 'asc' ? 'desc' : 'asc';
        sortCol = c;
        renderTable();
      });
    });
  }
}

window.goBackToStates = function () {
  currentView = 'states';
  currentDetailState = null;
  document.getElementById('detail-header').classList.add('hidden');
  // Clear the URL hash so a refresh lands on the states view
  history.pushState(null, '', window.location.pathname + window.location.search);
  renderTable();
};

window.openStateDetail = function (stateName) {
  currentView = 'detail';
  currentDetailState = stateName;
  document.getElementById('detail-header').classList.remove('hidden');
  document.getElementById('detail-state-name').textContent = stateName;
  // Write the state name into the URL hash so a refresh restores this view
  history.pushState(null, '', '#state=' + encodeURIComponent(stateName));
  renderTable();
};

// ── URL State Persistence ────────────────────────────────────────────────────
// Read the URL hash on load or back/forward navigation and restore the view.
function readStateFromURL() {
  const hash = window.location.hash; // e.g. "#state=Uttar%20Pradesh"
  if (hash && hash.startsWith('#state=')) {
    const stateName = decodeURIComponent(hash.slice('#state='.length));
    if (stateName) {
      // Restore detail view — data may not be loaded yet, so we set variables
      // and renderTable() will be called again once data arrives.
      currentView = 'detail';
      currentDetailState = stateName;
      const detailHeader = document.getElementById('detail-header');
      if (detailHeader) detailHeader.classList.remove('hidden');
      const detailName = document.getElementById('detail-state-name');
      if (detailName) detailName.textContent = stateName;
      return;
    }
  }
  // No hash or unrecognised hash — land on states view
  currentView = 'states';
  currentDetailState = null;
}

// Restore view from URL on initial page load
document.addEventListener('DOMContentLoaded', readStateFromURL);

// Restore view when the user hits the browser Back / Forward button
window.addEventListener('popstate', function () {
  readStateFromURL();
  renderTable();
});

function x(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function updateSelectAll() {
  const cb = document.getElementById('select-all');
  if (!cb) return;
  const ids  = allRecords.map(r => r.id);
  const selN = ids.filter(id => selectedIds.has(id)).length;
  cb.indeterminate = selN > 0 && selN < ids.length;
  cb.checked       = ids.length > 0 && selN === ids.length;
}

function updateSelBar() {}
function clearSelection() { selectedIds.clear(); renderTable(); }

function openModal(id) {
  const rec = allRecords.find(r => r.id === id);
  if (!rec) return;
  editingId = id;
  document.getElementById('modal-title').textContent = `${rec.state} — ${rec.el_type} — ${rec.el_year}`;
  document.getElementById('modal-key').textContent   = rec.key;
  document.getElementById('edit-status').value       = rec.overall_status || 'missing';
  document.getElementById('edit-remark').value       = rec.remark || '';
  const overlay = document.getElementById('overlay');
  const card    = document.getElementById('modal-card');
  overlay.classList.remove('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-95'); card.classList.add('scale-100');
}

function closeModal() {
  const overlay = document.getElementById('overlay');
  const card    = document.getElementById('modal-card');
  overlay.classList.add('opacity-0', 'pointer-events-none');
  card.classList.remove('scale-100'); card.classList.add('scale-95');
  editingId = null;
}

async function saveModal() {
  if (!editingId) return;
  const newStatus = document.getElementById('edit-status').value;
  const body = {
    overall_status: newStatus,
    remark: document.getElementById('edit-remark').value.trim() || null,
  };
  try {
    const updated = await apiFetch(`/api/records/${editingId}`, 'PATCH', body);
    closeModal();

    // If the user is viewing a specific status filter and the record's new status
    // no longer matches that filter, the record will disappear from the list.
    // Show a clear informational toast so the user knows the update was saved.
    const statusLabels = {
      missing: 'Not Downloaded', downloaded: 'Downloaded',
      extracted: 'Extracted', db_pushed: 'DB Pushed'
    };
    const newLabel = statusLabels[updated.overall_status] || updated.overall_status;
    const filterChanged = filters.status && filters.status !== 'remaining' && filters.status !== updated.overall_status;

    // Reload from server to get a correctly filtered view
    await loadRecords();
    loadStats();

    if (filterChanged) {
      showToast(`Status set to "${newLabel}". Record moved out of current view.`);
    } else {
      showToast('Record updated successfully');
    }
  } catch (e) { showToast('Save failed: ' + e.message, true); }
}

async function syncFromExcel() {
  const btn = document.getElementById('reload-btn');
  if (!btn) return;
  btn.disabled = true;
  try {
    const data = await apiFetch('/api/reload', 'POST', {});
    if (data.success) { showToast('Database synced from Excel'); loadStats(); loadRecords(); }
    else showToast('Sync failed: ' + data.error, true);
  } catch (e) { showToast('Sync error: ' + e.message, true); }
  finally { btn.disabled = false; }
}

async function syncAWS() {
  const btn = document.getElementById('sync-aws-btn');
  if (!btn) return;
  btn.disabled = true;
  try {
    const data = await apiFetch('/api/sync-rds', 'POST', {});
    if (data.success) { showToast(data.message); loadStats(); loadRecords(); }
    else showToast('AWS Sync failed: ' + data.message, true);
  } catch (e) { showToast('AWS Sync error: ' + e.message, true); }
  finally { btn.disabled = false; }
}

function handleSideNav(view) {
  document.querySelectorAll('.sidelink').forEach(el => {
    el.classList.remove('sl-active', 'sl-wip-active');
    el.classList.remove('text-gray-900', 'text-amber-900');

    if (el.dataset.view === view) {
      if (view === 'wip') {
        el.classList.add('sl-wip-active');
      } else {
        el.classList.add('sl-active');
      }
    }
  });

  const statusMap = { downloaded: 'downloaded', extracted: 'extracted', completed: 'completed', pending: 'pending', missing: 'missing' };
  if (statusMap[view]) {
    filters.status = statusMap[view];
    filters.wip    = false;
  } else if (view === 'wip') {
    filters.status = '';
    filters.wip    = true;
  } else {
    filters.status = '';
    filters.wip    = false;
  }
  setActiveKpi(null);
  loadStats(); loadRecords();
}

window.handleKpiClick = function (status) {
  if (activeKpi === status) {
    setActiveKpi(null);
    filters.status = '';
    filters.wip    = false;
  } else {
    setActiveKpi(status);
    filters.status = status;
    filters.wip    = false;
    document.querySelectorAll('.sidelink').forEach(el => {
      el.classList.remove('sl-active', 'sl-wip-active');
    });
  }
  goBackToStates();
  loadRecords();
};

function setActiveKpi(status) {
  activeKpi = status;
  const kpiMap = {
    remaining:  { id: 'kpi-total-remaining', cls: 'kpi-active-slate'   },
    downloaded: { id: 'kpi-downloaded',      cls: 'kpi-active-blue'    },
    extracted:  { id: 'kpi-extracted',       cls: 'kpi-active-violet'  },
    missing:    { id: 'kpi-missing',         cls: 'kpi-active-red'     },
  };
  const allCls = ['kpi-active-blue', 'kpi-active-violet', 'kpi-active-red', 'kpi-active-emerald', 'kpi-active-slate'];
  Object.entries(kpiMap).forEach(([s, cfg]) => {
    const btn = document.getElementById(cfg.id);
    if (!btn) return;
    if (s === status) {
      btn.classList.add(cfg.cls);
    } else {
      btn.classList.remove(...allCls);
    }
  });
}

function setDashToggle(btn, active, icon, label, color) {
  // color: 'amber' | 'indigo'
  const palette = {
    amber:  { bg: 'bg-amber-50',  text: 'text-amber-700',  border: 'border-amber-200',  iconOn: 'text-amber-500'  },
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', iconOn: 'text-indigo-500' },
  }[color];
  const iconCls = active ? palette.iconOn : 'text-gray-400';
  btn.innerHTML = `<span class="material-symbols-outlined ${iconCls}" style="font-size:13px;">${icon}</span> ${label}`;
  if (active) {
    btn.classList.remove('bg-white', 'text-gray-500', 'border-gray-200');
    btn.classList.add(palette.bg, palette.text, palette.border);
  } else {
    btn.classList.remove(palette.bg, palette.text, palette.border);
    btn.classList.add('bg-white', 'text-gray-500', 'border-gray-200');
  }
}

function showToast(msg, isErr = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = el.className.replace(/bg-\w+-\d+/g, '');
  el.classList.add(isErr ? 'bg-red-600' : 'bg-gray-900');
  el.classList.remove('opacity-0', 'pointer-events-none', 'translate-y-2');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.add('opacity-0', 'pointer-events-none', 'translate-y-2');
  }, 3000);
}

async function apiFetch(url, method = 'GET', body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function openRetroModal() {
  document.getElementById('retro-overlay').classList.remove('opacity-0', 'pointer-events-none');
  document.getElementById('retro-card').classList.remove('scale-95');
  document.getElementById('retro-card').classList.add('scale-100');

  (async () => {
    if (!retroMetadata) {
      try {
        retroMetadata = await apiFetch('/api/retro/metadata');
      } catch (e) {
        showToast('Failed to load retro metadata', true); return;
      }
    }
    const stateEl  = document.getElementById('retro-state');
    const currState = stateEl.value;
    stateEl.innerHTML = '<option value="">All States</option>';
    Object.keys(retroMetadata).sort().forEach(s => stateEl.appendChild(new Option(s, s)));
    if (currState && retroMetadata[currState]) {
      stateEl.value = currState;
    } else {
      document.getElementById('retro-type').innerHTML = '<option value="">All Types</option>';
      document.getElementById('retro-type').disabled  = true;
      document.getElementById('retro-year').innerHTML = '<option value="">All Years</option>';
      document.getElementById('retro-year').disabled  = true;
    }
    updateRetroCountLocal();
  })();
}

function closeRetroModal() {
  document.getElementById('retro-overlay').classList.add('opacity-0', 'pointer-events-none');
  document.getElementById('retro-card').classList.remove('scale-100');
  document.getElementById('retro-card').classList.add('scale-95');
}

function updateRetroCountLocal() {
  if (!retroMetadata) return;
  const s = document.getElementById('retro-state').value;
  const t = document.getElementById('retro-type').value;
  const y = document.getElementById('retro-year').value;

  let count = 0;
  if (s && t && y) {
    count = retroMetadata[s]?.[t]?.[y] || 0;
  } else if (s && t) {
    Object.values(retroMetadata[s]?.[t] || {}).forEach(c => count += c);
  } else if (s) {
    Object.values(retroMetadata[s] || {}).forEach(types => Object.values(types).forEach(c => count += c));
  } else {
    Object.values(retroMetadata || {}).forEach(states =>
      Object.values(states).forEach(types => Object.values(types).forEach(c => count += c)));
  }

  const preview = document.getElementById('retro-count-preview');
  preview.textContent = count === 1 ? '1 record found' : `${count.toLocaleString()} records found`;

  const btn = document.getElementById('retro-download');
  if (s && t && y && count > 0) {
    btn.disabled = false;
    btn.removeAttribute('aria-disabled');
    btn.className = 'px-4 py-2 text-[12.5px] font-semibold rounded-lg transition-all flex items-center gap-1.5 text-white cursor-pointer shadow-sm bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700';
  } else {
    btn.disabled = true;
    btn.setAttribute('aria-disabled', 'true');
    btn.className = 'px-4 py-2 text-[12.5px] font-semibold rounded-lg transition-all flex items-center gap-1.5 bg-gray-200 text-gray-400 cursor-not-allowed';
  }
}

function bindEvents() {
  document.getElementById('filter-state').addEventListener('change', e => {
    filters.state   = e.target.value;
    filters.el_type = '';
    filters.year    = '';
    const typeEl = document.getElementById('filter-type');
    const yearEl = document.getElementById('filter-year');
    typeEl.innerHTML = '<option value="">All Types</option>';
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (filters.state && filterMetadata?.[filters.state]) {
      typeEl.disabled = false;
      Object.keys(filterMetadata[filters.state]).sort().forEach(t => typeEl.appendChild(new Option(t, t)));
    } else { typeEl.disabled = true; }
    yearEl.disabled = true;
    loadStats(); loadRecords();
  });

  document.getElementById('filter-type').addEventListener('change', e => {
    filters.el_type = e.target.value;
    filters.year    = '';
    const yearEl = document.getElementById('filter-year');
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (filters.state && filters.el_type && filterMetadata?.[filters.state]?.[filters.el_type]) {
      yearEl.disabled = false;
      Object.keys(filterMetadata[filters.state][filters.el_type]).sort((a, b) => b.localeCompare(a))
        .forEach(y => yearEl.appendChild(new Option(y, y)));
    } else { yearEl.disabled = true; }
    loadStats(); loadRecords();
  });

  document.getElementById('filter-year').addEventListener('change',  e => { filters.year     = e.target.value; loadStats(); loadRecords(); });
  document.getElementById('filter-sir').addEventListener('change',   e => { filters.sir_only = e.target.checked; loadStats(); loadRecords(); });

  document.getElementById('global-search').addEventListener('input', e => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { filters.search = e.target.value.trim(); loadRecords(); }, 250);
  });

  document.getElementById('clear-filters').addEventListener('click', () => {
    Object.assign(filters, { state: '', el_type: '', year: '', status: '', sir_only: false, search: '', show_bp: false });
    ['filter-state', 'filter-type', 'filter-year'].forEach(id => { document.getElementById(id).value = ''; });
    document.getElementById('filter-type').disabled = true;
    document.getElementById('filter-year').disabled = true;
    document.getElementById('filter-sir').checked   = false;
    document.getElementById('global-search').value  = '';
    setActiveKpi(null);
    const bpBtn = document.getElementById('toggle-bp-btn');
    if (bpBtn) {
      bpBtn.innerHTML = '<span class="material-symbols-outlined text-gray-400" style="font-size:13px;">filter_alt</span> Show BP';
      bpBtn.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-indigo-200');
      bpBtn.classList.add('bg-white', 'text-gray-500', 'border-gray-200');
    }
    handleSideNav('all');
  });

  document.getElementById('select-all')?.addEventListener('change', e => {
    allRecords.forEach(r => e.target.checked ? selectedIds.add(r.id) : selectedIds.delete(r.id));
    renderTable(); updateSelBar();
  });

  // Sortable headers are (re)bound inside renderTable() for the detail view —
  // the static <thead> here is replaced on first render, so binding it is moot.

  document.getElementById('modal-close').addEventListener('click',  closeModal);
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  document.getElementById('modal-save').addEventListener('click',   saveModal);
  document.getElementById('overlay').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });

  document.querySelectorAll('.sidelink').forEach(el => {
    el.addEventListener('click', e => { e.preventDefault(); handleSideNav(el.dataset.view); });
  });

  // ── Tab navigation ──────────────────────────────────────────────────────
  const navTabs = [
    { id: 'nav-listing',   viewId: 'listing-view',   setup: () => { loadStats(); loadRecords(); } },
    { id: 'nav-dashboard', viewId: 'dashboard-view', setup: loadDashboardStats },
    { id: 'nav-glance',    viewId: 'glance-view',    setup: loadGlancePanel },
  ];

  function switchTab(activeId) {
    navTabs.forEach(t => {
      const nav  = document.getElementById(t.id);
      const view = document.getElementById(t.viewId);
      if (!nav || !view) return;
      if (t.id === activeId) {
        view.classList.remove('hidden'); view.classList.add('flex');
        nav.classList.add('active');
        if (t.setup) t.setup();
      } else {
        view.classList.add('hidden'); view.classList.remove('flex');
        nav.classList.remove('active');
      }
    });
    // The records search box only applies to the Backlog Tracker — hide it on the
    // Dashboard and Weekly Report. Inline display lets the responsive `sm:block`
    // class take over again when shown.
    const searchWrap = document.getElementById('global-search-wrap');
    if (searchWrap) searchWrap.style.display = (activeId === 'nav-listing') ? '' : 'none';

    // Remember the active tab so a browser reload restores the same page.
    try { localStorage.setItem('activeTab', activeId); } catch (e) {}
  }

  navTabs.forEach(t => {
    const el = document.getElementById(t.id);
    if (el) el.addEventListener('click', () => switchTab(t.id));
  });

  // Footer quick links mirror the top nav tabs
  const FOOTER_LINK_TO_TAB = { dashboard: 'nav-dashboard', listing: 'nav-listing', glance: 'nav-glance' };
  document.querySelectorAll('.footer-link').forEach(el => {
    el.addEventListener('click', () => {
      const navId = FOOTER_LINK_TO_TAB[el.dataset.view];
      if (navId) switchTab(navId);
    });
  });

  const dashRefreshBtn = document.getElementById('dash-refresh-btn');
  if (dashRefreshBtn) dashRefreshBtn.addEventListener('click', loadDashboardStats);

  // Glance Report → calendar week picker
  initGlanceCalendar();

  document.getElementById('nav-retro').addEventListener('click', e => {
    e.preventDefault(); openRetroModal();
  });

  document.getElementById('retro-close').addEventListener('click',  closeRetroModal);
  document.getElementById('retro-cancel').addEventListener('click', closeRetroModal);
  document.getElementById('retro-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeRetroModal();
  });

  document.getElementById('retro-state').addEventListener('change', e => {
    const s = e.target.value;
    const typeEl = document.getElementById('retro-type');
    const yearEl = document.getElementById('retro-year');
    typeEl.innerHTML = '<option value="">All Types</option>';
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (s && retroMetadata?.[s]) {
      typeEl.disabled = false;
      Object.keys(retroMetadata[s]).sort().forEach(t => typeEl.appendChild(new Option(t, t)));
    } else { typeEl.disabled = true; }
    yearEl.disabled = true;
    updateRetroCountLocal();
  });

  document.getElementById('retro-type').addEventListener('change', e => {
    const s = document.getElementById('retro-state').value;
    const t = e.target.value;
    const yearEl = document.getElementById('retro-year');
    yearEl.innerHTML = '<option value="">All Years</option>';
    if (s && t && retroMetadata?.[s]?.[t]) {
      yearEl.disabled = false;
      Object.keys(retroMetadata[s][t]).sort((a, b) => b.localeCompare(a)).forEach(y => yearEl.appendChild(new Option(y, y)));
    } else { yearEl.disabled = true; }
    updateRetroCountLocal();
  });

  document.getElementById('retro-year').addEventListener('change', updateRetroCountLocal);

  // Format segmented control (CSV / Excel) → writes to hidden #retro-format
  document.querySelectorAll('.retro-fmt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const fmtInput = document.getElementById('retro-format');
      if (fmtInput) fmtInput.value = btn.dataset.fmt;
      document.querySelectorAll('.retro-fmt-btn').forEach(b => {
        const active = b === btn;
        b.classList.toggle('bg-white', active);
        b.classList.toggle('text-gray-900', active);
        b.classList.toggle('shadow-sm', active);
        b.classList.toggle('text-gray-500', !active);
        b.classList.toggle('hover:text-gray-700', !active);
      });
    });
  });

  document.getElementById('retro-download').addEventListener('click', async () => {
    const state  = document.getElementById('retro-state').value;
    const type   = document.getElementById('retro-type').value;
    const year   = document.getElementById('retro-year').value;
    const fmt    = document.getElementById('retro-format').value;
    if (!state || !type || !year) { showToast('Please select State, Type, and Year.', true); return; }

    const btn = document.getElementById('retro-download');
    btn.disabled = true;
    btn.innerHTML = '<span class="material-symbols-outlined animate-spin" style="font-size:14px;">refresh</span> Downloading…';
    try {
      const res = await fetch(`/api/retro/export?state=${state}&el_type=${type}&year=${year}&format=${fmt}`);
      if (!res.ok) { const err = await res.json(); throw new Error(err.error || 'Export failed'); }
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = `Retro_${state}_${type}_${year}.${fmt}`; a.click();
      URL.revokeObjectURL(url);
      showToast('Download started');
      closeRetroModal();
    } catch (e) { showToast(e.message, true); }
    finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:14px;">download</span> Download';
      updateRetroCountLocal();
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closeRetroModal(); clearSelection(); }
  });

  // BP toggle
  const bpBtn = document.getElementById('toggle-bp-btn');
  if (bpBtn) {
    bpBtn.addEventListener('click', () => {
      filters.show_bp = !filters.show_bp;
      if (filters.show_bp) {
        bpBtn.innerHTML = '<span class="material-symbols-outlined text-indigo-500" style="font-size:13px;">filter_alt_off</span> Hide BP';
        bpBtn.classList.remove('bg-white', 'text-gray-500', 'border-gray-200');
        bpBtn.classList.add('bg-indigo-50', 'text-indigo-700', 'border-indigo-200');
      } else {
        bpBtn.innerHTML = '<span class="material-symbols-outlined text-gray-400" style="font-size:13px;">filter_alt</span> Show BP';
        bpBtn.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-indigo-200');
        bpBtn.classList.add('bg-white', 'text-gray-500', 'border-gray-200');
      }
      loadStats(); loadRecords();
    });
  }

  // ── Restore the last-viewed tab across reloads ───────────────────────────
  // Runs last, after every view's handlers are wired. Defaults to Dashboard.
  // Retro Export is a modal (not a persistent view), so it is never stored here
  // and never re-opened on reload.
  const PERSIST_TABS = new Set(navTabs.map(t => t.id));
  let startTab = 'nav-dashboard';
  try {
    const saved = localStorage.getItem('activeTab');
    if (saved && PERSIST_TABS.has(saved)) startTab = saved;
  } catch (e) {}
  switchTab(startTab);
}


// ── Dashboard ─────────────────────────────────────────────────────────────────
// ── Dashboard extended analytics (retro, caste) ───────────
let analyticsLoaded = false;

async function loadDashboardAnalytics(forceRefresh = false) {
  if (analyticsLoaded && !forceRefresh) return;
  try {
    const res = await fetch('/api/dashboard/analytics');
    if (!res.ok && res.status !== 202) { console.error('analytics fetch:', res.status); return; }
    const d = await res.json();
    renderRetroPanel(d.retro);
    renderCastePanel(d.caste);
    renderBoothPanel(d.booth);
    if (_firstLoad) {
      _firstLoad = false;
      // Optionally trigger a silent background sync of Form 20 cache
    }
    if (res.status === 200) {
      analyticsLoaded = true;
    } else {
      // Cache still building — retry in 15s to fill in by_type and top_states
      setTimeout(() => loadDashboardAnalytics(true), 15000);
    }
  } catch (e) {
    console.error('loadDashboardAnalytics:', e);
  }
}

function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-IN');
}

function typeColor(type) {
  const m = { AE:'#6366f1', GE:'#3b82f6', 'AE-BP':'#a78bfa', 'GE-BP':'#93c5fd' };
  return m[type] || '#94a3b8';
}

function renderForm20Panel(stats) {
  const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const bs        = stats.by_status || {};
  const total     = stats.total || 0;
  const completed = (bs.db_pushed || 0) + (bs.completed || 0);
  const pct       = total > 0 ? Math.round((completed / total) * 100) : 0;
  const circ      = 163.4;
  const dash      = circ * (1 - pct / 100);

  // Ring chart
  const ring    = document.getElementById('f20-ring');
  const ringPct = document.getElementById('f20-ring-pct');
  if (ring)    ring.style.strokeDashoffset = dash;
  if (ringPct) ringPct.textContent = pct + '%';

  _f20TotalYears = stats.total_years || 0;
  _f20Total      = stats.total       || 0;
  _f20ByType     = stats.by_type     || {};

  setEl('f20-pct',        pct + '%');
  setEl('f20-pct-badge',  pct + '% complete');
  setEl('f20-counts',     `${completed.toLocaleString()} / ${total.toLocaleString()} elections in DB`);
  const progEl = document.getElementById('f20-prog');
  if (progEl) progEl.style.width = pct + '%';

  // By election type (AE, GE — excluding BP variants)
  const typeWrap = document.getElementById('f20-type-rows');
  if (typeWrap && stats.by_type) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-gray-700'  },
      'GE': { label: 'General',  bg: 'bg-blue-500'  },
    };
    const entries = Object.entries(stats.by_type)
      .filter(([t]) => !t.includes('-BP'))
      .sort((a, b) => b[1].total - a[1].total);

    typeWrap.innerHTML = entries.map(([type, d]) => {
      const p   = d.total > 0 ? Math.round((d.completed / d.total) * 100) : 0;
      const m   = TYPE_META[type] || { label: type, bg: 'bg-gray-400' };
      const pctColor = p === 100 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${p}%"></div>
          </div>
          <div class="flex items-center gap-1 shrink-0 w-[72px] justify-end">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${d.completed}/${d.total}</span>
          </div>
        </div>`;
    }).join('');
  }

  // Top completed states
  const stateWrap = document.getElementById('f20-state-rows');
  if (stateWrap && stats.by_state) {
    const topStates = [...stats.by_state]
      .filter(s => s.completed > 0)
      .sort((a, b) => b.completed - a.completed)
      .slice(0, 8);
    const max = topStates[0]?.completed || 1;
    stateWrap.className = 'grid grid-cols-4 gap-1.5';
    stateWrap.innerHTML = topStates.map(s => {
      const intensity = Math.round((s.completed / max) * 9) + 1;
      const bg = intensity >= 8 ? 'bg-gray-100 border-gray-300' :
                 intensity >= 5 ? 'bg-gray-50 border-gray-200' : 'bg-gray-50 border-gray-100';
      const tc = intensity >= 8 ? 'text-gray-800' : 'text-gray-600';
      return `
        <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5">
          <span class="text-[10.5px] font-bold ${tc}">${s.state}</span>
          <span class="text-[12px] font-black text-gray-900 tabular-nums leading-none">${s.completed}</span>
          <span class="text-[9px] text-gray-400 leading-none">elections</span>
        </div>`;
    }).join('');
  }
}


function renderRetroPanel(r) {
  if (!r || !r.available) {
    const typeWrap  = document.getElementById('retro-type-rows');
    const stateWrap = document.getElementById('retro-state-rows');
    if (typeWrap)  typeWrap.innerHTML  = `<p class="text-[10.5px] text-gray-400 text-center py-2">${r?.error?.includes('permission') ? 'GRANT SELECT required' : (r?.error || 'Unavailable')}</p>`;
    if (stateWrap) stateWrap.innerHTML = '';
    return;
  }

  // AC-wise coverage — same metric as the Form 20 panel.
  const acTotal = r.total_acs     || 0;
  const acAvail = r.available_acs || 0;
  const pct     = r.coverage_pct_acs || 0;
  const circ    = 163.4;
  const dash    = circ * (1 - Math.min(pct, 100) / 100);

  // Ring chart
  const ring    = document.getElementById('retro-ring');
  const ringPct = document.getElementById('retro-ring-pct');
  if (ring)    ring.style.strokeDashoffset = dash;
  if (ringPct) ringPct.textContent = pct + '%';

  // Main numbers
  const setPct = document.getElementById('retro-pct');
  const setCov = document.getElementById('retro-covered-label');
  const setBar = document.getElementById('retro-prog');
  if (setPct) setPct.textContent = pct + '%';
  if (setCov) setCov.textContent = fmtNum(acAvail) + ' / ' + fmtNum(acTotal) + ' ACs in DB';
  if (setBar) setBar.style.width = Math.min(pct, 100) + '%';

  // Hero ribbon — retro coverage
  const hr = document.getElementById('hero-retro');
  const hrs = document.getElementById('hero-retro-sub');
  if (hr)  hr.textContent  = pct + '%';
  if (hrs) hrs.textContent = fmtNum(acAvail) + ' / ' + fmtNum(acTotal) + ' ACs';

  // ── By Election Type (AE / GE — non-BP), AC-wise ─────────────────────────
  const typeWrap = document.getElementById('retro-type-rows');
  if (typeWrap && r.by_type_acs) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-indigo-500', text: 'text-indigo-600' },
      'GE': { label: 'General',  bg: 'bg-blue-500',   text: 'text-blue-600'  },
    };
    typeWrap.innerHTML = r.by_type_acs.map(t => {
      const p = t.total > 0 ? Math.round((t.available / t.total) * 100) : 0;
      const m = TYPE_META[t.type] || { label: t.type, bg: 'bg-gray-400', text: 'text-gray-600' };
      const pctColor = p === 100 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${t.type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${Math.min(p, 100)}%"></div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0 justify-end whitespace-nowrap">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${fmtNum(t.available)}/${fmtNum(t.total)}</span>
          </div>
        </div>`;
    }).join('');
  }

  // ── Top States — pill grid, AC-wise count + pct ──────────────────────────
  const stateWrap = document.getElementById('retro-state-rows');
  if (stateWrap && r.top_states_acs) {
    const max = r.top_states_acs[0]?.available || 1;
    stateWrap.className = 'grid grid-cols-4 gap-1.5';
    stateWrap.innerHTML = r.top_states_acs.map(s => {
      const intensity = Math.round((s.available / max) * 9) + 1;
      const bg = intensity >= 8 ? 'bg-indigo-100 border-indigo-200' :
                 intensity >= 5 ? 'bg-indigo-50 border-indigo-100' : 'bg-gray-50 border-gray-100';
      const tc = intensity >= 8 ? 'text-indigo-700' : intensity >= 5 ? 'text-indigo-600' : 'text-gray-600';
      return `
        <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5" title="${s.state}: ${fmtNum(s.available)} / ${fmtNum(s.expected)} ACs (${s.pct}%)">
          <span class="text-[11px] font-bold ${tc}">${s.state} - ${s.pct}%</span>
          <span class="text-[10px] font-semibold text-gray-600 tabular-nums leading-none">AC - ${fmtNum(s.available)}</span>
        </div>`;
    }).join('');
  }
}

function _lockHTML(errMsg) {
  const notExist = errMsg && (errMsg.includes('does not exist') || errMsg.includes('relation'));
  const noPerm   = errMsg && errMsg.includes('permission');
  const icon  = notExist ? 'schedule' : 'lock';
  const title = notExist ? 'Table not yet populated' : noPerm ? 'DB access required' : 'Unavailable';
  const detail= notExist ? 'Data will appear once this table is loaded in RDS.'
              : noPerm   ? 'Contact DB admin to grant SELECT access on this table.'
              : (errMsg || 'Unable to load data');
  return `<div class="flex flex-col items-center justify-center gap-2 py-10 px-4 text-center flex-1">
    <span class="material-symbols-outlined text-gray-200" style="font-size:28px;">${icon}</span>
    <p class="text-[11px] font-semibold text-gray-400">${title}</p>
    <p class="text-[10px] text-gray-300 max-w-[180px] leading-relaxed">${detail}</p>
  </div>`;
}

// ── Caste category display-name normalisation ────────────────────────────────
// Merges dirty duplicates (e.g. "MUSLIM" + "Muslim", repeated "Buddhist") and
// produces a clean, human-readable label. Known acronyms stay upper-case.
const CASTE_ACRONYMS = new Set(['SC', 'ST', 'OBC', 'GEN', 'EBC', 'BC', 'SBC', 'MBC', 'DNT']);
function casteDisplayName(raw) {
  const k = String(raw || 'Other').trim();
  if (!k) return 'Other';
  const up = k.toUpperCase();
  if (CASTE_ACRONYMS.has(up)) return up;
  // Title-case multi-word / all-caps names: "MINORITY" -> "Minority"
  return k.toLowerCase().replace(/\b\w/g, ch => ch.toUpperCase());
}

// Palette for caste categories (stable, distinct)
const CASTE_PALETTE = ['#f59e0b','#6366f1','#10b981','#3b82f6','#ec4899','#8b5cf6','#14b8a6','#ef4444','#84cc16','#f97316','#06b6d4','#a855f7'];

function renderCastePanel(d) {
  const pctEl = document.getElementById('caste-pct');
  const subStatesEl = document.getElementById('caste-sub-states');
  const body  = document.getElementById('caste-body');

  // Hero ribbon (populate regardless of layout)
  const heroCaste    = document.getElementById('hero-caste');
  const heroCasteSub = document.getElementById('hero-caste-sub');

  if (!d || !d.available) {
    if (pctEl) pctEl.textContent = '—';
    if (heroCaste) heroCaste.textContent = '—';
    if (body)  body.innerHTML = _lockHTML(d?.error);
    return;
  }

  const acsCovered = d.acs_with_data || 0;
  const realCatN   = (d.by_category || []).length;

  const coveragePctAll = d.coverage_pct_all || 0;
  if (pctEl) pctEl.textContent = coveragePctAll + '% AC coverage';
  if (subStatesEl) subStatesEl.textContent = fmtNum(d.states);
  if (heroCaste)    heroCaste.textContent    = fmtNum(acsCovered);
  if (heroCasteSub) heroCasteSub.textContent = `${realCatN} categories · ${fmtNum(d.states)} states`;

  if (!body) return;

  const stateProgress = d.state_progress || [];
  const totalAcsAll   = d.total_acs_all || 0;

  const circ = 163.4;
  const dash = circ * (1 - Math.min(coveragePctAll, 100) / 100);
  const topStates = [...stateProgress].sort((a, b) => b.acs - a.acs).slice(0, 8);
  const maxTopAc = topStates[0]?.acs || 1;

  body.innerHTML = `
    <div class="p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 fade-up">

      <!-- LEFT: Ring + KPIs -->
      <div class="lg:col-span-4 flex flex-col gap-2.5">
        <div class="rounded-xl border border-gray-100 bg-gradient-to-br from-gray-50 to-white p-3 flex items-center gap-3">
          <div class="relative shrink-0 w-[64px] h-[64px]">
            <svg width="64" height="64" viewBox="0 0 64 64" class="-rotate-90">
              <circle cx="32" cy="32" r="26" fill="none" stroke="#e5e7eb" stroke-width="6"/>
              <circle cx="32" cy="32" r="26" fill="none" stroke="#f59e0b" stroke-width="6"
                stroke-dasharray="${circ}" stroke-dashoffset="${dash}" stroke-linecap="round"
                style="transition:stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)"/>
            </svg>
            <span class="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-gray-700">${coveragePctAll}%</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[20px] font-black tabular-nums leading-none text-amber-600">${coveragePctAll}%</p>
            <p class="text-[10px] text-gray-400 font-medium mt-0.5">complete</p>
            <p class="text-[10.5px] text-gray-500 tabular-nums mt-0.5 font-medium">${fmtNum(acsCovered)} / ${fmtNum(totalAcsAll)} ACs</p>
          </div>
        </div>
        ${[
          { v: fmtNum(totalAcsAll), l: 'Total ACs',          c: 'text-gray-900',  i: 'map' },
          { v: fmtNum(acsCovered),  l: 'ACs with Caste Data', c: 'text-amber-600', i: 'groups' },
          { v: fmtNum(d.states),    l: 'States',             c: 'text-gray-900',  i: 'public' },
        ].map(k => `
          <div class="rounded-xl border border-gray-100 bg-gradient-to-br from-gray-50 to-white p-3 flex items-center gap-3">
            <span class="material-symbols-outlined text-gray-300" style="font-size:18px;">${k.i}</span>
            <div>
              <p class="text-[20px] font-black tabular-nums leading-none ${k.c}">${k.v}</p>
              <p class="text-[9.5px] text-gray-400 font-medium mt-1 uppercase tracking-wide">${k.l}</p>
            </div>
          </div>`).join('')}
      </div>

      <!-- RIGHT: Top States — AC-wise coverage, pill grid -->
      <div class="lg:col-span-8 flex flex-col">
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2.5">Top States — AC-wise Coverage</p>
        <div class="grid grid-cols-4 gap-1.5">
          ${topStates.map(s => {
            const intensity = Math.round((s.acs / maxTopAc) * 9) + 1;
            const bg = intensity >= 8 ? 'bg-amber-100 border-amber-200' :
                       intensity >= 5 ? 'bg-amber-50 border-amber-100' : 'bg-gray-50 border-gray-100';
            const tc = intensity >= 8 ? 'text-amber-700' : intensity >= 5 ? 'text-amber-600' : 'text-gray-600';
            return `
              <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5" title="${s.state}: ${fmtNum(s.acs)} / ${fmtNum(s.total_acs)} ACs (${s.pct}%)">
                <span class="text-[10.5px] font-bold ${tc}">${s.state}</span>
                <span class="text-[12px] font-black text-gray-900 tabular-nums leading-none">${fmtNum(s.acs)}</span>
                <span class="text-[9px] text-gray-400 tabular-nums leading-none">${s.pct}%</span>
              </div>`;
          }).join('')}
        </div>
      </div>

    </div>`;
}

// ── Booth Details panel — state-wise AC coverage (mirrors the Caste card) ─────
function renderBoothPanel(d) {
  const pctEl       = document.getElementById('booth-pct');
  const subStatesEl = document.getElementById('booth-sub-states');
  const body        = document.getElementById('booth-body');

  // Hero ribbon — booth data (populate regardless of panel layout)
  const heroBooth    = document.getElementById('hero-booth');
  const heroBoothSub = document.getElementById('hero-booth-sub');

  if (!d || !d.available) {
    if (pctEl) pctEl.textContent = '—';
    if (heroBooth) heroBooth.textContent = '—';
    if (body)  body.innerHTML = _lockHTML(d?.error);
    return;
  }

  const acsCovered      = d.acs_with_data || 0;
  const coveragePctAll  = d.coverage_pct_all || 0;
  const totalAcsAll     = d.total_acs_all || 0;
  const stateProgress   = d.state_progress || [];

  if (pctEl)       pctEl.textContent = coveragePctAll + '% AC coverage';
  if (subStatesEl) subStatesEl.textContent = fmtNum(d.states);
  if (heroBooth)    heroBooth.textContent    = fmtNum(acsCovered);
  if (heroBoothSub) heroBoothSub.textContent = `${coveragePctAll}% · ${fmtNum(d.states)} states`;

  if (!body) return;

  const circ = 163.4;
  const dash = circ * (1 - Math.min(coveragePctAll, 100) / 100);
  const topStates = [...stateProgress].sort((a, b) => b.acs - a.acs).slice(0, 10);
  const maxTopAc  = topStates[0]?.acs || 1;

  body.innerHTML = `
    <div class="p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 fade-up">

      <!-- LEFT: Ring + KPIs -->
      <div class="lg:col-span-4 flex flex-col gap-2.5">
        <div class="rounded-xl border border-gray-100 bg-gradient-to-br from-gray-50 to-white p-3 flex items-center gap-3">
          <div class="relative shrink-0 w-[64px] h-[64px]">
            <svg width="64" height="64" viewBox="0 0 64 64" class="-rotate-90">
              <circle cx="32" cy="32" r="26" fill="none" stroke="#e5e7eb" stroke-width="6"/>
              <circle cx="32" cy="32" r="26" fill="none" stroke="#10b981" stroke-width="6"
                stroke-dasharray="${circ}" stroke-dashoffset="${dash}" stroke-linecap="round"
                style="transition:stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)"/>
            </svg>
            <span class="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-gray-700">${coveragePctAll}%</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[20px] font-black tabular-nums leading-none text-emerald-600">${coveragePctAll}%</p>
            <p class="text-[10px] text-gray-400 font-medium mt-0.5">complete</p>
            <p class="text-[10.5px] text-gray-500 tabular-nums mt-0.5 font-medium">${fmtNum(acsCovered)} / ${fmtNum(totalAcsAll)} ACs</p>
          </div>
        </div>
        ${[
          { v: fmtNum(totalAcsAll),      l: 'Total ACs',           c: 'text-gray-900',   i: 'map' },
          { v: fmtNum(acsCovered),       l: 'ACs with Booth Data', c: 'text-emerald-600', i: 'how_to_vote' },
          { v: fmtNum(d.total_booths),   l: 'Booths',              c: 'text-gray-900',   i: 'location_on' },
        ].map(k => `
          <div class="rounded-xl border border-gray-100 bg-gradient-to-br from-gray-50 to-white p-3 flex items-center gap-3">
            <span class="material-symbols-outlined text-gray-300" style="font-size:18px;">${k.i}</span>
            <div>
              <p class="text-[20px] font-black tabular-nums leading-none ${k.c}">${k.v}</p>
              <p class="text-[9.5px] text-gray-400 font-medium mt-1 uppercase tracking-wide">${k.l}</p>
            </div>
          </div>`).join('')}
      </div>

      <!-- RIGHT: State-wise AC coverage, pill grid -->
      <div class="lg:col-span-8 flex flex-col">
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2.5">Top 10 States — AC Coverage (DB vs Total)</p>
        <div class="grid grid-cols-5 gap-1.5">
          ${topStates.map(s => {
            const intensity = Math.round((s.acs / maxTopAc) * 9) + 1;
            const bg = intensity >= 8 ? 'bg-emerald-100 border-emerald-200' :
                       intensity >= 5 ? 'bg-emerald-50 border-emerald-100' : 'bg-gray-50 border-gray-100';
            const tc = intensity >= 8 ? 'text-emerald-700' : intensity >= 5 ? 'text-emerald-600' : 'text-gray-600';
            return `
              <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5" title="${s.state}: ${fmtNum(s.acs)} / ${fmtNum(s.total_acs)} ACs (${s.pct}%)">
                <span class="text-[10.5px] font-bold ${tc}">${s.state} · ${s.pct}%</span>
                <span class="text-[12px] font-black text-gray-900 tabular-nums leading-none">${fmtNum(s.acs)}</span>
                <span class="text-[9px] text-gray-400 tabular-nums leading-none">/ ${fmtNum(s.total_acs)}</span>
              </div>`;
          }).join('')}
        </div>
      </div>

    </div>`;
}

async function loadDashboardStats() {
  try {
    const stats = await apiFetch('/api/stats?hide_bp=1');

    const bs      = stats.by_status || {};
    const total   = stats.total || 0;
    const completed = (bs.db_pushed || 0) + (bs.completed || 0);
    const pct     = total > 0 ? Math.round((completed / total) * 100) : 0;

    // Sidebar progress sync
    const pctSidebar = document.getElementById('progress-pct-sidebar');
    const pbFill     = document.getElementById('progress-bar-fill');
    const progText   = document.getElementById('progress-text');
    if (pctSidebar) pctSidebar.textContent = pct + '%';
    if (pbFill)     pbFill.style.width     = pct + '%';
    if (progText)   progText.textContent   = `${completed} / ${total} completed`;

    // Form 20 analytics card — initial paint from SQLite
    renderForm20Panel(stats);

    // ── Load live Form 20 card stats (reads local JSON, instant) ─────────────
    try {
      const liveStats = await apiFetch('/api/form20_card_stats');
      populateForm20Card(liveStats);
    } catch (e) {
      console.warn('form20_card_stats unavailable:', e);
    }

    // Extended analytics panels (Retro, Caste) from RDS
    const isManualRefresh = document.activeElement?.id === 'dash-refresh-btn';
    loadDashboardAnalytics(isManualRefresh);

  } catch (e) { console.error('loadDashboardStats:', e); }
}

// ── Populate Form 20 card from live JSON stats ────────────────────────────────
function populateForm20Card(d) {
  if (!d) return;
  const setEl = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  const form20  = d.form20_entries  || 0;   // 175 unique (state, type, year) in Form 20
  const acpc    = d.acpc_entries    || 0;   // 560 unique (state, type, year) in AC-PC mapping
  const pct     = d.coverage_pct   || 0;
  const circ    = 163.4;
  const dash    = circ * (1 - pct / 100);

  // Ring chart + % text
  const ring    = document.getElementById('f20-ring');
  const ringPct = document.getElementById('f20-ring-pct');
  if (ring)    ring.style.strokeDashoffset = dash;
  if (ringPct) ringPct.textContent = pct + '%';

  setEl('f20-pct',       pct + '%');
  setEl('f20-pct-label', 'coverage');
  setEl('f20-pct-badge', pct + '% complete');
  setEl('f20-counts',    `${form20.toLocaleString()} / ${acpc.toLocaleString()} ACs in Form 20`);

  // Hero ribbon — pipeline coverage
  setEl('hero-pipeline',     pct + '%');
  setEl('hero-pipeline-sub', `${form20.toLocaleString()} / ${acpc.toLocaleString()} ACs`);

  // Update globals so that we keep track of accurate totals
  _f20Total = form20;
  


  // ── By election type breakdown ─────────────────────────────────────────────
  const typeWrap = document.getElementById('f20-type-rows');
  if (typeWrap && d.by_type) {
    const TYPE_META = {
      'AE': { label: 'Assembly', bg: 'bg-gray-700'  },
      'GE': { label: 'General',  bg: 'bg-blue-500'  },
    };
    const entries = Object.entries(d.by_type)
      .filter(([t]) => !t.includes('-BP'))
      .sort((a, b) => b[1].in_mapping - a[1].in_mapping);

    typeWrap.innerHTML = entries.map(([type, td]) => {
      const done    = td.in_form20  || 0;
      const mapTot  = td.in_mapping || 0;
      const p       = mapTot > 0 ? Math.round((done / mapTot) * 100) : 0;
      const m       = TYPE_META[type] || { label: type, bg: 'bg-gray-400' };
      const pctColor = p === 100 ? 'text-emerald-600' : p >= 80 ? 'text-blue-600' : p >= 50 ? 'text-amber-600' : 'text-rose-500';
      return `
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 w-[90px] shrink-0">
            <span class="w-2 h-2 rounded-full ${m.bg} shrink-0"></span>
            <span class="text-[10.5px] font-semibold text-gray-700">${type}</span>
            <span class="text-[9.5px] text-gray-400">${m.label}</span>
          </div>
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${m.bg} bar-fill" style="width:${p}%"></div>
          </div>
          <div class="flex items-center gap-1.5 shrink-0 justify-end whitespace-nowrap">
            <span class="text-[11px] font-bold tabular-nums ${pctColor}">${p}%</span>
            <span class="text-[9.5px] text-gray-400 tabular-nums">${done.toLocaleString()}/${mapTot.toLocaleString()}</span>
          </div>
        </div>`;
    }).join('');
  }

  // ── Top states from Form 20 ───────────────────────────────────────────────
  const stateWrap = document.getElementById('f20-state-rows');
  if (stateWrap && d.top_states && d.top_states.length > 0) {
    // (STATE_AC_COUNTS is defined at module level)
    const max = d.top_states[0]?.count || 1;
    stateWrap.className = 'grid grid-cols-4 gap-1.5';
    stateWrap.innerHTML = d.top_states.map(s => {
      const intensity = Math.round((s.count / max) * 9) + 1;
      const bg = intensity >= 8 ? 'bg-gray-100 border-gray-300' :
                 intensity >= 5 ? 'bg-gray-50 border-gray-200' : 'bg-gray-50 border-gray-100';
      const tc = intensity >= 8 ? 'text-gray-800' : 'text-gray-600';
      return `
        <div class="flex flex-col items-center justify-center py-1.5 rounded-lg border ${bg} gap-0.5" title="${s.state}: ${fmtNum(s.count)} ACs (${s.pct ?? 0}%)">
          <span class="text-[11px] font-bold ${tc}">${s.state} - ${s.pct ?? 0}%</span>
          <span class="text-[10px] font-semibold text-gray-600 tabular-nums leading-none">AC - ${fmtNum(s.count)}</span>
        </div>`;
    }).join('');
  }
}




// Returns the Monday (YYYY-MM-DD) of the week containing the given date string.
function mondayOf(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  const dow = d.getDay(); // 0 = Sunday ... 6 = Saturday
  const diff = dow === 0 ? -6 : 1 - dow; // shift back to Monday
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

// Renders the week-picker strip: every tracked week as a colored, clickable chip.
// "selected" = the chip matching the active filter, "current" = the live calendar week.
function renderGlanceWeekPicker(weeks, selectedStart) {
  const wrap = document.getElementById('glance-week-picker');
  if (!wrap) return;

  if (!weeks.length) {
    wrap.innerHTML = '<span class="text-[11px] text-gray-400">No weeks tracked yet</span>';
    return;
  }

  wrap.innerHTML = weeks.map(w => {
    const isSelected = selectedStart && w.start === selectedStart;
    const isCurrent  = !!w.is_current;
    let cls = 'bg-white text-gray-600 border-gray-200 hover:border-indigo-300 hover:bg-indigo-50';
    if (isSelected) cls = 'bg-indigo-600 text-white border-indigo-600 shadow-sm';
    else if (isCurrent) cls = 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:border-emerald-300';

    return `
      <button type="button" data-week="${w.start}"
        class="glance-week-chip shrink-0 flex flex-col items-center justify-center px-2.5 py-1 rounded-lg border text-center transition-all duration-150 ${cls}"
        title="${w.display}${w.count ? ' · ' + w.count + ' pushed' : ''}">
        <span class="text-[10.5px] font-semibold leading-tight whitespace-nowrap">${w.display}</span>
        <span class="text-[9px] tabular-nums leading-tight ${isSelected ? 'text-indigo-100' : 'text-gray-400'}">${w.count} pushed</span>
      </button>`;
  }).join('');

  wrap.querySelectorAll('.glance-week-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const dateEl = document.getElementById('glance-date-filter');
      if (!dateEl) return;
      // Clicking the already-selected week clears the filter (back to current week)
      dateEl.value = (mondayOf(dateEl.value) === btn.dataset.week) ? '' : btn.dataset.week;
      loadGlancePanel();
    });
  });
}

// ── Glance Report: calendar week picker ─────────────────────────────────────
let glanceCalMonth = new Date(); // first-of-month cursor for the popup grid

function initGlanceCalendar() {
  const btn   = document.getElementById('glance-cal-btn');
  const popup = document.getElementById('glance-cal-popup');
  if (!btn || !popup) return;

  glanceCalMonth = new Date();
  glanceCalMonth.setDate(1);

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const isHidden = popup.classList.contains('hidden');
    if (isHidden) {
      const dateEl = document.getElementById('glance-date-filter');
      const ref = dateEl && dateEl.value ? new Date(dateEl.value + 'T00:00:00') : new Date();
      glanceCalMonth = new Date(ref.getFullYear(), ref.getMonth(), 1);
      renderGlanceCalendar();
    }
    popup.classList.toggle('hidden');
  });

  document.addEventListener('click', e => {
    if (!popup.classList.contains('hidden') && !popup.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
      popup.classList.add('hidden');
    }
  });

  updateGlanceCalLabel();
}

function updateGlanceCalLabel() {
  const label = document.getElementById('glance-cal-label');
  if (!label) return;
  const dateEl = document.getElementById('glance-date-filter');
  const val = dateEl && dateEl.value;

  if (!val) { label.textContent = 'This Week'; return; }

  const mon = mondayOf(val);
  const sun = new Date(mon + 'T00:00:00');
  sun.setDate(sun.getDate() + 6);
  const fmt = (d, withYear) => {
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${d.getDate()} ${months[d.getMonth()]}${withYear ? ' ' + d.getFullYear() : ''}`;
  };
  const monD = new Date(mon + 'T00:00:00');
  label.textContent = `${fmt(monD, false)} – ${fmt(sun, true)}`;
}

// Renders the popup calendar grid. Clicking any day selects that day's whole
// Mon–Sun week (highlighted together) and reloads the Glance Report.
function renderGlanceCalendar() {
  const popup = document.getElementById('glance-cal-popup');
  if (!popup) return;

  const dateEl = document.getElementById('glance-date-filter');
  const selected = dateEl && dateEl.value ? new Date(dateEl.value + 'T00:00:00') : null;
  const selectedMon = selected ? mondayOf(dateEl.value) : mondayOf(new Date().toISOString().slice(0, 10));

  const today = new Date(); today.setHours(0,0,0,0);
  const todayStr = today.toISOString().slice(0, 10);

  const year  = glanceCalMonth.getFullYear();
  const month = glanceCalMonth.getMonth();
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  // Monday-first grid: start from the Monday on/before the 1st of the month
  const firstOfMonth = new Date(year, month, 1);
  const startOffset  = (firstOfMonth.getDay() + 6) % 7; // 0 = Monday
  const gridStart = new Date(year, month, 1 - startOffset);

  let cells = '';
  for (let i = 0; i < 42; i++) {
    const cell = new Date(gridStart);
    cell.setDate(gridStart.getDate() + i);
    const cellStr = cell.toISOString().slice(0, 10);
    const inMonth = cell.getMonth() === month;
    const inSelectedWeek = mondayOf(cellStr) === selectedMon;
    const isToday = cellStr === todayStr;

    let cls = 'rounded-md';
    if (inSelectedWeek) {
      cls += ' text-white font-bold';
    } else {
      cls += inMonth ? ' text-gray-700 hover:bg-indigo-50' : ' text-gray-300 hover:bg-gray-50';
    }
    if (isToday && !inSelectedWeek) cls += ' ring-2 ring-inset ring-indigo-400';

    let style = '';
    if (inSelectedWeek) {
      style = 'background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#d946ef 100%);';
      if (isToday) style += 'box-shadow:0 0 0 2px #fff inset, 0 0 0 4px #f59e0b inset;';
    }

    cells += `<button type="button" data-date="${cellStr}" style="${style}"
                class="glance-cal-day h-8 w-8 flex items-center justify-center text-[11.5px] transition-colors duration-100 ${cls}">${cell.getDate()}</button>`;
  }

  const weekdayHeaders = ['Mo','Tu','We','Th','Fr','Sa','Su'].map(d =>
    `<span class="h-6 flex items-center justify-center text-[10px] font-bold text-gray-400 uppercase">${d}</span>`
  ).join('');

  popup.innerHTML = `
    <div class="flex items-center justify-between mb-2 px-1">
      <button type="button" id="glance-cal-prev" class="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-500 transition-colors">
        <span class="material-symbols-outlined" style="font-size:16px;">chevron_left</span>
      </button>
      <p class="text-[12.5px] font-bold text-gray-900">${monthNames[month]} ${year}</p>
      <button type="button" id="glance-cal-next" class="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-500 transition-colors">
        <span class="material-symbols-outlined" style="font-size:16px;">chevron_right</span>
      </button>
    </div>
    <div class="grid grid-cols-7 gap-1 mb-1">${weekdayHeaders}</div>
    <div class="grid grid-cols-7 gap-1">${cells}</div>
    <div class="flex items-center justify-between mt-3 pt-2 border-t border-gray-100">
      <button type="button" id="glance-cal-today" class="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 transition-colors">Jump to this week</button>
      <button type="button" id="glance-cal-clear" class="text-[11px] font-medium text-gray-400 hover:text-gray-600 transition-colors">Clear</button>
    </div>`;

  popup.querySelectorAll('.glance-cal-day').forEach(btn => {
    btn.addEventListener('click', () => {
      if (dateEl) dateEl.value = btn.dataset.date;
      updateGlanceCalLabel();
      renderGlanceCalendar();
      popup.classList.add('hidden');
      loadGlancePanel();
    });
  });

  document.getElementById('glance-cal-prev').addEventListener('click', () => {
    glanceCalMonth.setMonth(glanceCalMonth.getMonth() - 1);
    renderGlanceCalendar();
  });
  document.getElementById('glance-cal-next').addEventListener('click', () => {
    glanceCalMonth.setMonth(glanceCalMonth.getMonth() + 1);
    renderGlanceCalendar();
  });
  document.getElementById('glance-cal-today').addEventListener('click', () => {
    if (dateEl) dateEl.value = new Date().toISOString().slice(0, 10);
    glanceCalMonth = new Date(); glanceCalMonth.setDate(1);
    updateGlanceCalLabel();
    renderGlanceCalendar();
    popup.classList.add('hidden');
    loadGlancePanel();
  });
  document.getElementById('glance-cal-clear').addEventListener('click', () => {
    if (dateEl) dateEl.value = '';
    updateGlanceCalLabel();
    renderGlanceCalendar();
    popup.classList.add('hidden');
    loadGlancePanel();
  });
}

// ── Glance Report ─────────────────────────────────────────────────────────────
async function loadGlancePanel() {
  const dateFilter = (document.getElementById('glance-date-filter') || {}).value || '';
  try {
    const params = new URLSearchParams();
    if (dateFilter) params.append('week', dateFilter);
    params.append('hide_bp', '1');

    const glance = await apiFetch('/api/glance_report?' + params.toString());

    renderGlanceWeekPicker(glance.available_weeks || [], mondayOf(dateFilter));

    const accordion = document.getElementById('glance-panel-accordion');
    const countSpan = document.getElementById('glance-panel-count');
    const allWeeks    = glance.all_weeks   || [];
    const allRecords  = glance.all_records || [];
    const weekRecords = (allWeeks[0] && allWeeks[0].records) || [];

    if (countSpan) countSpan.textContent = weekRecords.length + ' records this week';

    renderGlanceAnalytics(glance, allWeeks, allRecords, weekRecords);
    renderGlanceMomentumAndTable();

    if (!accordion) return;

    if (weekRecords.length === 0) {
      accordion.innerHTML = `
        <div class="p-12 text-center flex flex-col items-center gap-3 text-gray-400">
          <span class="material-symbols-outlined" style="font-size:32px;">inbox</span>
          <p class="text-[12.5px] font-medium">No DB pushed records found for this week.</p>
        </div>`;
      return;
    }

    // ── Build state → { years: Set, byWeek: {weekLabel: count} } map ──────────
    const weekLabels = glance.trend_weeks_labels || [];

    const stateMap = {};
    weekRecords.forEach(r => {
      const parts = String(r.key).split('-');
      const st = parts[0] || '?';
      const yr = parts.length >= 2 ? parts[parts.length - 1] : '';
      const ty = parts.length >= 3 ? parts.slice(1, -1).join('-') : '';
      if (!stateMap[st]) stateMap[st] = { elections: [], byWeek: {} };
      stateMap[st].elections.push({ type: ty, year: yr, key: r.key, date: r.date });
    });

    const trend = glance.trend_4_weeks || {};
    weekLabels.forEach(wl => {
      Object.keys(trend).forEach(st => {
        if (!stateMap[st]) stateMap[st] = { elections: [], byWeek: {} };
        stateMap[st].byWeek[wl] = trend[st][wl] || 0;
      });
    });

    const stateNames = {
      AP:'Andhra Pradesh', AR:'Arunachal Pradesh', AS:'Assam', BR:'Bihar', CG:'Chhattisgarh',
      GA:'Goa', GJ:'Gujarat', HR:'Haryana', HP:'Himachal Pradesh', JH:'Jharkhand',
      KA:'Karnataka', KL:'Kerala', MP:'Madhya Pradesh', MH:'Maharashtra', MN:'Manipur',
      ML:'Meghalaya', MZ:'Mizoram', NL:'Nagaland', OR:'Odisha', PB:'Punjab',
      RJ:'Rajasthan', SK:'Sikkim', TN:'Tamil Nadu', TR:'Tripura', UP:'Uttar Pradesh',
      UK:'Uttarakhand', WB:'West Bengal', TS:'Telangana', DL:'Delhi', JK:'Jammu & Kashmir',
      LA:'Ladakh', AN:'Andaman & Nicobar', CH:'Chandigarh', PY:'Puducherry', LD:'Lakshadweep',
      CT:'Chhattisgarh',
    };

    const sortedStates = Object.keys(stateMap).filter(st => stateMap[st].elections.length > 0).sort();
    const maxPerWeek = Math.max(...sortedStates.map(s =>
      Math.max(...weekLabels.map(w => stateMap[s].byWeek[w] || 0))
    ), 1);

    // ── Table header ──────────────────────────────────────────────────────────
    const weekShort = wl => {
      const start = wl.slice(5, 10); // MM-DD
      return start;
    };

    accordion.innerHTML = `
      <!-- Table header -->
      <div class="grid items-center bg-gray-50 border-b border-gray-200 px-5 py-2.5"
           style="grid-template-columns: 56px 1fr 220px auto;">
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">State</p>
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Completed Elections</p>
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider text-center">4-Week Trend</p>
        <p class="text-[10px] font-bold text-gray-400 uppercase tracking-wider text-right">Total</p>
      </div>
      <!-- Rows -->
      ${sortedStates.map(st => {
        const d = stateMap[st];
        // Group elections: deduplicate by type+year, sort by year desc
        const seen = new Set();
        const elections = d.elections.filter(e => {
          const k = e.type + '-' + e.year;
          if (seen.has(k)) return false;
          seen.add(k); return true;
        }).sort((a, b) => (b.year || '').localeCompare(a.year || ''));

        // Year tags grouped by type
        const byType = {};
        elections.forEach(e => {
          if (!byType[e.type]) byType[e.type] = [];
          byType[e.type].push(e.year);
        });

        const tags = Object.entries(byType).map(([ty, yrs]) => {
          const typeColor = {
            AE: 'bg-indigo-50 text-indigo-700 border-indigo-100',
            GE: 'bg-blue-50 text-blue-700 border-blue-100',
            'AE-BP': 'bg-violet-50 text-violet-700 border-violet-100',
            'GE-BP': 'bg-sky-50 text-sky-700 border-sky-100',
          }[ty] || 'bg-gray-50 text-gray-600 border-gray-200';
          return `<span class="inline-flex items-center gap-1 text-[10.5px] font-semibold px-2 py-0.5 rounded-md border ${typeColor}">
            <span class="font-bold">${ty}</span> <span class="text-[10px] font-normal">${yrs.join(', ')}</span>
          </span>`;
        }).join('');

        // Mini sparkbar (4 weeks, oldest left → newest right)
        const bars = weekLabels.map(wl => {
          const cnt = d.byWeek[wl] || 0;
          const h = cnt > 0 ? Math.max(20, Math.round((cnt / maxPerWeek) * 100)) : 4;
          const col = cnt > 0 ? '#6366f1' : '#e5e7eb';
          return `<div class="flex flex-col items-center gap-1" title="${weekShort(wl)}: ${cnt}">
            <span class="text-[8px] text-gray-400 tabular-nums">${cnt > 0 ? cnt : ''}</span>
            <div class="w-5 rounded-sm" style="height:${h}%;background:${col};min-height:3px;max-height:32px;"></div>
            <span class="text-[8px] text-gray-300">${weekShort(wl)}</span>
          </div>`;
        }).join('');

        const total = d.elections.length;
        const fullName = stateNames[st] || st;

        return `
        <div class="grid items-center px-5 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors"
             style="grid-template-columns: 56px 1fr 220px auto;">
          <!-- State -->
          <div>
            <span class="text-[12px] font-bold text-gray-900">${st}</span>
            <p class="text-[9.5px] text-gray-400 leading-none mt-0.5">${fullName}</p>
          </div>
          <!-- Election tags -->
          <div class="flex flex-wrap gap-1.5 pr-4">${tags}</div>
          <!-- Sparkbars -->
          <div class="flex items-end justify-center gap-1.5 h-[48px] px-2">${bars}</div>
          <!-- Total -->
          <div class="text-right">
            <span class="text-[14px] font-bold text-gray-700 tabular-nums">${total}</span>
            <p class="text-[9.5px] text-gray-400">done</p>
          </div>
        </div>`;
      }).join('')}
    `;

  } catch (e) { console.error('loadGlancePanel:', e); }
}

function renderGlanceAnalytics(glance, allWeeks, allRecords, weekRecords) {
  // All pushed records matching the current filters (all-time) — used for the top summary cards
  const allRecs = allRecords || [];
  const total = allRecs.length;

  // Records for the selected/current week only — drives State Performance & Election Type Distribution
  const weekRecs = weekRecords || [];

  const countByStateType = recs => {
    const stateCounts = {}, typeCounts = {};
    recs.forEach(r => {
      const parts = String(r.key).split('-');
      const st = parts[0] || '?';
      const ty = parts.length >= 3 ? parts.slice(1, -1).join('-') : (parts[1] || '?');
      stateCounts[st] = (stateCounts[st] || 0) + 1;
      typeCounts[ty]  = (typeCounts[ty]  || 0) + 1;
    });
    return { stateCounts, typeCounts };
  };

  const { stateCounts } = countByStateType(allRecs);
  const { stateCounts: weekStateCounts, typeCounts: weekTypeCounts } = countByStateType(weekRecs);

  // Weekly series — last 4 weeks for Glance analytics, all-time for context
  const weekly      = glance.weekly_counts     || {};   // last 4 weeks
  const weekKeys    = Object.keys(weekly).sort();
  const activeWeeks = Object.keys(glance.all_weekly_counts || weekly).length; // total active weeks for avg

  // This week vs last week
  const curWeek = glance.current_week || '';
  const thisWeek = weekly[curWeek] || 0;
  let lastWeek = 0;
  if (curWeek) {
    const start = curWeek.slice(0, 10);
    const d = new Date(start + 'T00:00:00');
    d.setDate(d.getDate() - 7);
    const lwStart = d.toISOString().slice(0, 10);
    const lwLabel = Object.keys(weekly).find(k => k.startsWith(lwStart));
    if (lwLabel) lastWeek = weekly[lwLabel];
  }

  const setT = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

  // ── Summary stat cards ──────────────────────────────────────────────────
  const last4WeeksTotal = Object.values(weekly).reduce((a, b) => a + b, 0);
  setT('glance-stat-total',     last4WeeksTotal.toLocaleString());
  setT('glance-stat-total-sub', last4WeeksTotal === 1 ? 'record in last 4 weeks' : 'records in last 4 weeks');
  setT('glance-stat-thisweek',  thisWeek);
  setT('glance-stat-avg',       activeWeeks ? (total / activeWeeks).toFixed(1) : '0');
  setT('glance-stat-weeks',     `over ${activeWeeks} active week${activeWeeks === 1 ? '' : 's'}`);
  setT('glance-stat-states',    Object.keys(stateCounts).length);

  const topState = Object.entries(stateCounts).sort((a, b) => b[1] - a[1])[0];
  setT('glance-stat-topstate',  topState ? `top: ${topState[0]} (${topState[1]})` : 'top: —');

  // Trend chip (this vs last week)
  const trendEl = document.getElementById('glance-stat-trend');
  if (trendEl) {
    const diff = thisWeek - lastWeek;
    let icon, color, text;
    if (diff > 0)      { icon = 'arrow_upward';   color = 'text-emerald-600'; text = `+${diff} vs last week`; }
    else if (diff < 0) { icon = 'arrow_downward'; color = 'text-red-500';     text = `${diff} vs last week`; }
    else               { icon = 'remove';          color = 'text-gray-400';    text = `same as last week`; }
    trendEl.innerHTML = `<span class="material-symbols-outlined ${color}" style="font-size:13px;">${icon}</span><span class="${color} font-medium">${text}</span>`;
  }

  // ── Weekly trend chart (area) ───────────────────────────────────────────
  const wCtx = document.getElementById('glanceWeeklyChart')?.getContext('2d');
  if (wCtx) {
    if (gWeekChart) { gWeekChart.destroy(); gWeekChart = null; }
    const labels = weekKeys.map(k => {
      const s = k.slice(5, 10); const e = k.slice(19, 24);
      return e ? `${s}–${e}` : s;
    });
    const grad = wCtx.createLinearGradient(0, 0, 0, 200);
    grad.addColorStop(0, 'rgba(99,102,241,0.25)');
    grad.addColorStop(1, 'rgba(99,102,241,0.01)');
    gWeekChart = new Chart(wCtx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'DB Pushed',
          data: weekKeys.map(k => weekly[k]),
          borderColor: '#6366f1',
          backgroundColor: grad,
          borderWidth: 2,
          pointBackgroundColor: '#6366f1',
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.35,
          fill: true,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' }, grid: { color: '#f3f4f6' } },
          x: { ticks: { font: { size: 10, family: 'Inter' }, color: '#9ca3af', maxRotation: 0, autoSkip: true }, grid: { display: false } },
        },
      },
    });
  }

  // ── State performance (horizontal bar, top 8) — current week only ───────
  const sCtx = document.getElementById('glanceStateChart')?.getContext('2d');
  if (sCtx) {
    if (gStateChart) { gStateChart.destroy(); gStateChart = null; }
    const sorted = Object.entries(weekStateCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
    gStateChart = new Chart(sCtx, {
      type: 'bar',
      data: {
        labels: sorted.map(s => s[0]),
        datasets: [{ data: sorted.map(s => s[1]), backgroundColor: '#34d399', borderRadius: 4, borderWidth: 0 }],
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0, font: { size: 10, family: 'Inter' }, color: '#9ca3af' }, grid: { color: '#f3f4f6' } },
          y: { ticks: { font: { size: 11, family: 'Inter' }, color: '#374151' }, grid: { display: false } },
        },
      },
    });
  }

  // ── Election type distribution (HTML bars) — current week only ──────────
  const typeWrap = document.getElementById('glance-type-bars');
  if (typeWrap) {
    const sortedTypes = Object.entries(weekTypeCounts).sort((a, b) => b[1] - a[1]);
    const weekTotal = weekRecs.length;
    const palette = ['#6366f1', '#7c3aed', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
    if (!sortedTypes.length) {
      typeWrap.innerHTML = '<p class="text-[12px] text-gray-400 text-center py-3">No data for this week</p>';
    } else {
      typeWrap.innerHTML = sortedTypes.map(([ty, cnt], i) => {
        const pct  = weekTotal ? Math.round((cnt / weekTotal) * 100) : 0;
        const name = EL_TYPE_NAMES[ty] || ty;
        const col  = palette[i % palette.length];
        return `
          <div class="flex items-center gap-3">
            <div class="w-28 shrink-0 flex items-center gap-2">
              <span class="w-2 h-2 rounded-full shrink-0" style="background:${col}"></span>
              <span class="text-[12px] font-semibold text-gray-700">${ty}</span>
              <span class="text-[11px] text-gray-400">${name}</span>
            </div>
            <div class="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div class="h-full rounded-full bar-fill" style="width:${pct}%;background:${col}"></div>
            </div>
            <div class="w-16 shrink-0 text-right">
              <span class="text-[12px] font-bold text-gray-800 tabular-nums">${cnt}</span>
              <span class="text-[11px] text-gray-400 ml-1">${pct}%</span>
            </div>
          </div>`;
      }).join('');
    }
  }

  // ── Election years: last week vs this week ──────────────────────────────
  renderYearComparison(allWeeks);
}

function renderGlanceDatasetSection(analytics, f20Stats) {
  const a = analytics || {};
  const f = f20Stats  || {};

  // ── KPI cards ─────────────────────────────────────────────────────────────
  const setKpi = (pctId, subId, barId, pct, sub) => {
    const pEl = document.getElementById(pctId);
    const sEl = document.getElementById(subId);
    const bEl = document.getElementById(barId);
    if (pEl) pEl.textContent = pct != null ? pct + '%' : '—';
    if (sEl) sEl.textContent = sub;
    if (bEl) bEl.style.width = (pct != null ? Math.min(pct, 100) : 0) + '%';
  };

  const retro = a.retro || {};
  const booth  = a.booth  || {};
  const caste  = a.caste  || {};

  setKpi('gds-f20-pct', 'gds-f20-sub', 'gds-f20-bar',
    f.coverage_pct != null ? f.coverage_pct : null,
    f.form20_entries != null ? `${f.form20_entries.toLocaleString()} / ${(f.acpc_entries||0).toLocaleString()} ACs` : '—');

  setKpi('gds-retro-pct', 'gds-retro-sub', 'gds-retro-bar',
    retro.available && retro.ac_total ? Math.round((retro.ac_available / retro.ac_total) * 100) : null,
    retro.available ? `${retro.ac_available} / ${retro.ac_total} elections` : 'Loading…');

  setKpi('gds-booth-pct', 'gds-booth-sub', 'gds-booth-bar',
    booth.available ? booth.coverage_pct_all : null,
    booth.available ? `${(booth.acs_with_data||0).toLocaleString()} / ${(booth.total_acs_all||0).toLocaleString()} ACs` : 'Loading…');

  setKpi('gds-caste-pct', 'gds-caste-sub', 'gds-caste-bar',
    caste.available ? caste.coverage_pct_all : null,
    caste.available ? `${(caste.acs_with_data||0).toLocaleString()} ACs · ${caste.categories||0} categories` : 'Loading…');
}

async function renderGlanceMomentumAndTable() {
  const wk = (document.getElementById('glance-date-filter') || {}).value || '';
  let momentum;
  try {
    momentum = await apiFetch('/api/weekly_momentum' + (wk ? ('?week=' + encodeURIComponent(wk)) : ''));
  } catch { return; }

  const series   = momentum.series || [];
  const f20Week  = momentum.f20_week  || [];   // selected/current week's pushed Form 20 elections
  const boothWk  = momentum.booth_week || [];  // zero for now
  const casteWk  = momentum.caste_week || [];  // zero for now

  // ── Top-strip Row 2 · per-dataset WEEKLY PUSHES ───────────────────────────
  // Weekly Report tracks what was pushed, not DB totals. Only Form 20 has weekly
  // pushes; Retro / Booth / Caste are zero. (DB totals live on the Main Dashboard.)
  // Row 1 aggregate cards are populated by renderGlanceAnalytics (Form 20 driven).
  const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const f20This = f20Week.length;                                // selected week's Form 20 pushes
  const f20Last4 = series.reduce((a, s) => a + (s.f20 || 0), 0); // last 4 weeks
  setTxt('glance-stat-f20-week', f20This.toLocaleString('en-IN'));
  setTxt('glance-stat-f20-sub',  `${f20Last4.toLocaleString('en-IN')} pushed in last 4 weeks`);
  setTxt('glance-stat-retro-week', '0');
  setTxt('glance-stat-retro-sub',  'pushed this week');
  setTxt('glance-stat-booth-week', '0');
  setTxt('glance-stat-booth-sub',  'pushed this week');
  setTxt('glance-stat-caste-week', '0');
  setTxt('glance-stat-caste-sub',  'pushed this week');

  const labels = series.map(s => {
    const d = new Date(s.week + 'T00:00:00');
    return (d.getMonth()+1).toString().padStart(2,'0') + '-' + d.getDate().toString().padStart(2,'0');
  });

  // Normalise a value array so peak = 100 (common Y-axis for mixed scales)
  const norm = (arr) => {
    const max = Math.max(...arr.filter(v => v != null && v > 0), 1);
    return arr.map(v => v != null ? Math.round((v / max) * 100) : null);
  };

  // Only Form 20 carries real data; Retro / Booth / Caste stay flat at zero.
  const f20vals   = series.map(s => s.f20);
  const retrovals = series.map(() => 0);
  const boothvals = series.map(() => 0);
  const castevals = series.map(() => 0);

  const chartOpts = (rawSets) => ({
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1f2937',
        titleFont: { size: 11, family: 'Inter' },
        bodyFont:  { size: 11, family: 'Inter' },
        padding: 10,
        callbacks: {
          label: ctx => {
            const raw = rawSets[ctx.datasetIndex][ctx.dataIndex];
            const val = raw != null ? raw.toLocaleString() : '0';
            return `  ${ctx.dataset.label}: ${val}`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true, max: 108,
        ticks: { display: false },
        grid: { color: '#f3f4f6' },
      },
      x: {
        ticks: { font: { size: 10, family: 'Inter' }, color: '#9ca3af', maxRotation: 0 },
        grid: { display: false },
      },
    },
  });

  // ── Chart.js v4-safe shared config ────────────────────────────────────────
  const mkChart = (ctx, datasets, rawSets) => new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1f2937',
          padding: 10,
          callbacks: {
            label: c => {
              const raw = rawSets[c.datasetIndex]?.[c.dataIndex];
              return `  ${c.dataset.label}: ${raw != null ? raw.toLocaleString() : '0'}`;
            },
          },
        },
      },
      scales: {
        y: { beginAtZero: true, max: 108, ticks: { display: false }, grid: { color: '#f3f4f6' } },
        x: { ticks: { font: { size: 10 }, color: '#9ca3af', maxRotation: 0 }, grid: { display: false } },
      },
    },
  });

  // ── Category 1: Form 20 & Retro ───────────────────────────────────────────
  const f20Ctx = document.getElementById('glanceMomentumF20Chart')?.getContext('2d');
  if (f20Ctx) {
    if (gF20Chart) { gF20Chart.destroy(); gF20Chart = null; }
    try {
      gF20Chart = mkChart(f20Ctx, [
        {
          label: 'Form 20',
          data: norm(f20vals),
          borderColor: '#111827',
          backgroundColor: 'rgba(17,24,39,0.07)',
          fill: true,
          borderWidth: 2.5,
          pointRadius: f20vals.map(v => v > 0 ? 5 : 3),
          pointHoverRadius: 6,
          pointBackgroundColor: f20vals.map(v => v > 0 ? '#111827' : '#d1d5db'),
          tension: 0.3,
        },
        {
          label: 'Retro',
          data: norm(retrovals),
          borderColor: '#6366f1',
          backgroundColor: 'transparent',
          fill: false,
          borderWidth: 1.5,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.3,
        },
      ], [f20vals, retrovals]);

      // Draw raw election count above each non-zero F20 point after animation
      gF20Chart.options.animation = {
        onComplete({ chart }) {
          const meta = chart.getDatasetMeta(0);
          const c2 = chart.ctx;
          c2.save();
          c2.font = 'bold 11px Inter,sans-serif';
          c2.fillStyle = '#111827';
          c2.textAlign = 'center';
          meta.data.forEach((pt, i) => {
            if (f20vals[i] > 0) c2.fillText(f20vals[i] + ' elections', pt.x, pt.y - 10);
          });
          c2.restore();
        },
      };
      gF20Chart.update('none');
    } catch (e) { console.error('F20 chart error:', e); }
  }

  // ── Category 2: Booth & Caste ─────────────────────────────────────────────
  const boothCtx = document.getElementById('glanceMomentumBoothChart')?.getContext('2d');
  if (boothCtx) {
    if (gBoothChart) { gBoothChart.destroy(); gBoothChart = null; }
    try {
      gBoothChart = mkChart(boothCtx, [
        {
          label: 'Booth',
          data: norm(boothvals),
          borderColor: '#10b981',
          backgroundColor: 'transparent',
          fill: false,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.35,
        },
        {
          label: 'Caste',
          data: norm(castevals),
          borderColor: '#f59e0b',
          backgroundColor: 'transparent',
          fill: false,
          borderWidth: 1.5,
          borderDash: [5, 4],
          pointRadius: 0,
          tension: 0.35,
        },
      ], [boothvals, castevals]);
    } catch (e) { console.error('Booth chart error:', e); }
  }

  // ── Shared helpers ─────────────────────────────────────────────────────────
  const FULL_NAMES = {
    AP:'Andhra Pradesh', AR:'Arunachal Pradesh', AS:'Assam', BR:'Bihar',
    CG:'Chandigarh', CT:'Chhattisgarh', GA:'Goa', GJ:'Gujarat', HR:'Haryana',
    HP:'Himachal Pradesh', JH:'Jharkhand', JK:'Jammu & Kashmir', KA:'Karnataka',
    KL:'Kerala', LA:'Ladakh', LD:'Lakshadweep', MP:'Madhya Pradesh',
    MH:'Maharashtra', MN:'Manipur', ML:'Meghalaya', MZ:'Mizoram', NL:'Nagaland',
    OR:'Odisha', PB:'Punjab', PY:'Puducherry', RJ:'Rajasthan', SK:'Sikkim',
    TN:'Tamil Nadu', TR:'Tripura', TS:'Telangana', UK:'Uttarakhand',
    UP:'Uttar Pradesh', WB:'West Bengal', DL:'Delhi', AN:'Andaman & Nicobar', CH:'Chandigarh',
  };

  const emptyRow = (cols, msg) =>
    `<tr><td colspan="${cols}" class="px-3 py-8 text-center text-[11px] text-gray-400">
       <span class="material-symbols-outlined block mb-1 text-gray-300" style="font-size:22px;">inbox</span>${msg}
     </td></tr>`;

  // ── Category 1: current/selected week's pushed Form 20 — grouped by State.
  // Each state row carries its pushed elections as compact TYPE·YY chips, so
  // the table stays short (one row per state) and never needs to scroll.
  const body1 = document.getElementById('glance-vol-f20-body');
  if (body1) {
    if (!f20Week.length) {
      body1.innerHTML = emptyRow(3, 'No Form 20 pushes this week');
    } else {
      // Aggregate by state
      const byState = {};
      f20Week.forEach(r => {
        const st = r.state; if (!st) return;
        if (!byState[st]) byState[st] = { ac: r.ac || 0, els: [] };
        byState[st].els.push({ type: r.el_type || '—', year: String(r.el_year || '') });
      });
      const allRows = Object.entries(byState).sort((a, b) => b[1].ac - a[1].ac || b[1].els.length - a[1].els.length);
      const maxAc = Math.max(...allRows.map(([, v]) => v.ac), 1);

      // Cap rows so the table never scrolls and stays as tall as the chart.
      const MAX_ROWS = 7, MAX_CHIPS = 3;
      const rows = allRows.slice(0, MAX_ROWS);
      const hiddenStates = allRows.length - rows.length;

      const chip = (type, year) => {
        const yy = year.length >= 2 ? year.slice(-2) : year;
        return `<span class="inline-block text-[9px] font-bold leading-none px-1.5 py-1 rounded mr-1 whitespace-nowrap"
                  style="background:rgba(99,102,241,0.10);color:#4f46e5;">${type}·${yy}</span>`;
      };

      body1.innerHTML = rows.map(([st, v]) => {
        const alpha = Math.max(0.08, Math.round((v.ac / maxAc) * 10) / 10);
        let chips = v.els.slice(0, MAX_CHIPS).map(e => chip(e.type, e.year)).join('');
        if (v.els.length > MAX_CHIPS) {
          chips += `<span class="inline-block text-[9px] font-bold leading-none px-1.5 py-1 rounded text-gray-500"
                      style="background:#f3f4f6;">+${v.els.length - MAX_CHIPS}</span>`;
        }
        return `
          <tr class="border-b border-gray-50 hover:bg-gray-50 transition-colors">
            <td class="px-3 py-2 whitespace-nowrap">
              <span class="text-[11.5px] font-bold text-gray-900">${st}</span>
              <span class="text-[9px] text-gray-400 ml-1">${FULL_NAMES[st] || ''}</span>
            </td>
            <td class="px-3 py-2 whitespace-nowrap">${chips}</td>
            <td class="px-3 py-2 text-right text-[12.5px] font-bold text-gray-800 tabular-nums"
                style="background:rgba(99,102,241,${alpha});">${v.ac.toLocaleString()}</td>
          </tr>`;
      }).join('');
      if (hiddenStates > 0) {
        body1.innerHTML += `
          <tr><td colspan="3" class="px-3 py-1.5 text-center text-[10px] font-medium text-gray-400 bg-gray-50/50">
            +${hiddenStates} more state${hiddenStates > 1 ? 's' : ''}
          </td></tr>`;
      }
    }
  }

  // ── Category 2: this week's pushed Booth & Caste — State · ACs (zero for now)
  const body2 = document.getElementById('glance-vol-booth-body');
  if (body2) {
    // Merge booth + caste by state into a single ACs figure
    const byState = {};
    [...boothWk, ...casteWk].forEach(r => {
      const st = r.state; if (!st) return;
      byState[st] = (byState[st] || 0) + (r.ac || 0);
    });
    const rows = Object.entries(byState).sort((a, b) => b[1] - a[1]);
    if (!rows.length) {
      body2.innerHTML = emptyRow(2, 'No Booth / Caste pushes this week');
    } else {
      const maxAc = Math.max(...rows.map(([, v]) => v), 1);
      body2.innerHTML = rows.map(([st, ac]) => {
        const alpha = Math.max(0.08, Math.round((ac / maxAc) * 10) / 10);
        return `
          <tr class="border-b border-gray-50 hover:bg-gray-50 transition-colors">
            <td class="px-3 py-2">
              <span class="text-[11.5px] font-bold text-gray-900">${st}</span>
              <p class="text-[9px] text-gray-400 leading-none mt-0.5">${FULL_NAMES[st] || ''}</p>
            </td>
            <td class="px-3 py-2 text-right text-[11.5px] font-bold text-gray-800 tabular-nums"
                style="background:rgba(16,185,129,${alpha});">${ac.toLocaleString()}</td>
          </tr>`;
      }).join('');
    }
  }
}

// Compares the set of election years pushed last week vs this week.
// allWeeks[0] is the current calendar week (live), allWeeks[1] is last week.
function renderYearComparison(allWeeks) {
  const wrap = document.getElementById('glance-year-compare');
  if (!wrap) return;

  const thisWeek = (allWeeks && allWeeks[0]) || { week: '', records: [] };
  const lastWeek = (allWeeks && allWeeks[1]) || { week: '', records: [] };

  const fmtRange = wl => {
    if (!wl || wl.length < 24) return '—';
    const s = wl.slice(0, 10), e = wl.slice(14, 24);
    const fmt = iso => {
      const [y, m, d] = iso.split('-');
      return `${parseInt(d)} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m)-1]}`;
    };
    return `${fmt(s)} – ${fmt(e)} ${e.slice(0, 4)}`;
  };
  const rangeEl = document.getElementById('glance-year-compare-range');
  if (rangeEl) {
    rangeEl.textContent = `This week: ${fmtRange(thisWeek.week)}  |  Last week: ${fmtRange(lastWeek.week)}`;
  }

  const yearSet = recs => {
    const s = new Set();
    (recs || []).forEach(r => {
      const parts = String(r.key).split('-');
      const yr = parts[parts.length - 1];
      if (yr) s.add(yr);
    });
    return s;
  };

  const thisYears = yearSet(thisWeek.records);
  const lastYears = yearSet(lastWeek.records);

  const onlyLast = [...lastYears].filter(y => !thisYears.has(y)).sort();
  const both     = [...thisYears].filter(y => lastYears.has(y)).sort();
  const onlyThis = [...thisYears].filter(y => !lastYears.has(y)).sort();

  const renderChips = (years, emptyText, color) => {
    if (!years.length) return `<span class="text-[11px] text-gray-300">${emptyText}</span>`;
    return years.map(y => `<span class="inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded border ${color}">${y}</span>`).join(' ');
  };

  const col = (title, icon, iconColor, years, emptyText, chipColor) => `
    <div class="border border-gray-100 rounded-lg p-3">
      <div class="flex items-center gap-1.5 mb-2">
        <span class="material-symbols-outlined ${iconColor}" style="font-size:14px;">${icon}</span>
        <p class="text-[11px] font-semibold text-gray-700">${title}</p>
        <span class="text-[10px] text-gray-400 ml-auto tabular-nums">${years.length}</span>
      </div>
      <div class="flex flex-wrap gap-1">${renderChips(years, emptyText, chipColor)}</div>
    </div>`;

  wrap.innerHTML = [
    col('Only Last Week',  'history',         'text-amber-500',   onlyLast, 'None', 'bg-amber-50 text-amber-700 border-amber-100'),
    col('Both Weeks',      'sync_alt',        'text-indigo-500',  both,     'None', 'bg-indigo-50 text-indigo-700 border-indigo-100'),
    col('Only This Week',  'fiber_new',       'text-emerald-500', onlyThis, 'None', 'bg-emerald-50 text-emerald-700 border-emerald-100'),
  ].join('');
}

// togglePanelWeek removed — accordion replaced with state-grouped grid
