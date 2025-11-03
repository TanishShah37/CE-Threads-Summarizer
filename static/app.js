async function fetchJSON(url) {
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === 'class') e.className = v; else e.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    if (typeof c === 'string') e.appendChild(document.createTextNode(c));
    else e.appendChild(c);
  });
  return e;
}

let state = {
  threads: [],
  selected: null,
};

function baselineSummary(thread) {
  if (!thread) return '';
  return (thread.approval && thread.approval.approved_summary) || thread.ai_summary.summary_markdown || '';
}

function updateApproveButtonState() {
  const btn = document.getElementById('approve-btn');
  const t = state.selected;
  if (!t) { btn.disabled = true; return; }
  const current = document.getElementById('edit-summary').value.trim();
  const base = baselineSummary(t).trim();
  const isFirstApproval = !t.approval; // allow approving AI draft as-is on first pass
  const canApprove = current.length > 0 && (isFirstApproval || current !== base);
  btn.disabled = !canApprove;
  btn.textContent = isFirstApproval ? (canApprove ? 'Approve' : 'Approve') : (canApprove ? 'Approve changes' : 'Approved');
}

function renderThreads() {
  const list = document.getElementById('threads');
  list.innerHTML = '';
  state.threads.forEach((t) => {
    const label = `${t.thread_id} · ${t.topic}`;
    const approved = t.approval ? 'approved' : 'pending';
    const isSelected = state.selected && state.selected.thread_id === t.thread_id;
    const cls = `thread ${approved}` + (isSelected ? ' selected' : '');
    const btn = el('button', { class: cls, 'aria-pressed': isSelected ? 'true' : 'false' }, label);
    btn.addEventListener('click', () => selectThread(t.thread_id));
    list.appendChild(btn);
  });
}

function selectThread(threadId) {
  state.selected = state.threads.find((t) => t.thread_id === threadId);
  const t = state.selected;
  if (!t) return;

  const meta = document.getElementById('meta');
  const intent = t.ai_summary.intent;
  const status = t.ai_summary.status;
  const sla = t.ai_summary.crm_context.sla_hours;
  const statusClass = (() => {
    const s = (status || '').toLowerCase();
    if (s.includes('resolved') || s.includes('approved')) return 'badge-status-resolved';
    if (s.includes('progress')) return 'badge-status-inprogress';
    if (s.includes('pending')) return 'badge-status-inprogress';
    return 'badge-status-open';
  })();

  meta.innerHTML = [
    '<div class="meta-grid">',
    '  <div class="meta-row"><span class="label">Thread</span><div class="value">' + t.thread_id + '</div></div>',
    '  <div class="meta-row"><span class="label">Order</span><div class="value">' + t.order_id + '</div></div>',
    '  <div class="meta-row"><span class="label">Product</span><div class="value">' + t.product + '</div></div>',
    '  <div class="inline-badges">',
    '    <span class="badge badge-intent">' + intent + '</span>',
    '    <span class="badge ' + statusClass + '">' + status + '</span>',
    '    <span class="badge badge-sla">' + sla + 'h SLA</span>',
    '  </div>',
    '</div>'
  ].join('');

  const aiPanelText = (t.approval && t.approval.approved_summary) || t.ai_summary.summary_markdown;
  document.getElementById('ai-summary').textContent = aiPanelText;
  document.getElementById('edit-summary').value =
    (t.approval && t.approval.approved_summary) || t.ai_summary.summary_markdown;
  // Status text is used only for transient save messages; avoid duplicating "Approved" label
  document.getElementById('status').textContent = '';

  // Re-render thread list to reflect selected styling
  renderThreads();

  // Update approve button state based on edited content
  updateApproveButtonState();

  // Fallback: ensure first-approval case is actionable even if timing issues occur
  const btn = document.getElementById('approve-btn');
  if (!t.approval) {
    const val = document.getElementById('edit-summary').value.trim();
    if (val.length > 0) {
      btn.disabled = false;
      btn.textContent = 'Approve';
    }
  }
}

async function approve() {
  const t = state.selected;
  if (!t) return;
  const approved_summary = document.getElementById('edit-summary').value;
  const approver = document.getElementById('approver').value || 'ce_associate';
  const res = await fetch('/api/approve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: t.thread_id, approved_summary, approver }),
  });
  if (!res.ok) {
    document.getElementById('status').textContent = 'Error saving approval';
    return;
  }
  document.getElementById('status').textContent = 'Saved';
  setTimeout(() => { const s = document.getElementById('status'); if (s) s.textContent = ''; }, 1200);
  // Refresh
  await load();
  selectThread(t.thread_id);
  // After reload, baseline changed -> disable Approve until user edits again
  updateApproveButtonState();
  // Refresh metrics after approval
  if (typeof loadMetrics === 'function') {
    loadMetrics();
  }
}

async function load() {
  const payload = await fetchJSON('/api/threads');
  state.threads = payload.threads;
  renderThreads();
}

document.getElementById('approve-btn').addEventListener('click', approve);
document.getElementById('edit-summary').addEventListener('input', updateApproveButtonState);

async function loadMetrics() {
  try {
    const m = await fetchJSON('/api/metrics');
    const elM = document.getElementById('metrics');
    if (!elM) return;
    elM.innerHTML = '';
    const items = [
      { k: m.total_threads, t: 'Total' },
      { k: m.approved_count, t: 'Approved' },
      { k: Math.round(m.approval_rate * 100) + '%', t: 'Approval Rate' },
      { k: Math.round(m.resolved_rate * 100) + '%', t: 'Resolved Rate' },
      { k: Math.round(m.deflection_rate * 100) + '%', t: 'Deflection Rate' },
      { k: m.estimated_time_saved_minutes + 'm', t: 'Time Saved' },
    ];
    items.forEach(({k, t}) => {
      const card = el('div', { class: 'metric' }, [
        el('div', { class: 'k' }, String(k)),
        el('div', { class: 't' }, t),
      ]);
      elM.appendChild(card);
    });
  } catch (e) {
    // no-op
  }
}

load().then(() => {
  if (state.threads[0]) selectThread(state.threads[0].thread_id);
  loadMetrics();
});


