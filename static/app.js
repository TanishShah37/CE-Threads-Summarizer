// SPA State Management
let state = {
  threads: [],
  selectedThread: null,
  selectedEngine: 'rules', // 'rules' or 'llm'
  originalSummary: '',      // AI Draft summary
  searchMatches: [],
  currentSearchIndex: -1,
  showDiff: false,
  apiKeyConfirmed: false
};

// Helper: Fetch JSON helper
async function fetchJSON(url) {
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

// -------------------------------------------------------------
// API KEY PROMPT OVERLAY
// Checks /api/check_key on load. If no key is set, shows a
// persistent modal prompting the user to enter one.
// The modal re-prompts until a key is saved or user skips.
// -------------------------------------------------------------
async function checkAndPromptAPIKey() {
  try {
    const res = await fetchJSON('/api/check_key');
    if (res.key_set) {
      state.apiKeyConfirmed = true;
      hideApiKeyModal();
      return;
    }
  } catch (e) {
    // endpoint may not exist in older deploys — skip silently
    return;
  }
  showApiKeyModal(false);
}

function showApiKeyModal(isRetry) {
  const overlay = document.getElementById('api-key-overlay');
  const msg = document.getElementById('api-key-message');
  const input = document.getElementById('api-key-input');

  if (isRetry) {
    msg.textContent = '⚠ That key didn\'t work or was empty. Please try again, or click Skip to use mock LLM responses.';
    msg.style.color = '#f97316';
  } else {
    msg.textContent = 'No ANTHROPIC_API_KEY found. Enter your key below to enable live Generative AI summaries. Without it, the LLM engine uses high-fidelity mock responses.';
    msg.style.color = '#94a3b8';
  }

  input.value = '';
  overlay.classList.remove('hidden');
  input.focus();
}

function hideApiKeyModal() {
  document.getElementById('api-key-overlay').classList.add('hidden');
}

async function submitAPIKey() {
  const key = document.getElementById('api-key-input').value.trim();
  if (!key) {
    showApiKeyModal(true);
    return;
  }

  const btn = document.getElementById('api-key-save-btn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const res = await fetch('/api/set_key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key })
    });
    const data = await res.json();

    if (data.ok) {
      state.apiKeyConfirmed = true;
      hideApiKeyModal();
      showToast('✓ API key saved. Generative AI engine is now active.', 'success');
    } else {
      btn.disabled = false;
      btn.textContent = 'Save Key';
      showApiKeyModal(true);
    }
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Save Key';
    showApiKeyModal(true);
  }
}

function skipAPIKey() {
  hideApiKeyModal();
  showToast('Running with mock LLM responses. Add ANTHROPIC_API_KEY to .env to enable live AI.', 'info');
}

// Toast notification helper
function showToast(message, type) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('visible'), 10);
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 400);
  }, 4500);
}

// Keydown enter support on the API key input
document.addEventListener('DOMContentLoaded', () => {
  const keyInput = document.getElementById('api-key-input');
  if (keyInput) {
    keyInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitAPIKey();
    });
  }
});

// -------------------------------------------------------------
// OPERATIONAL METRICS & KPI PANEL
// -------------------------------------------------------------
async function loadMetrics() {
  try {
    const data = await fetchJSON('/api/metrics');
    document.getElementById('kpi-total').textContent = data.total_threads;
    document.getElementById('kpi-approved').textContent = data.approved_count;
    document.getElementById('kpi-rate').textContent = Math.round(data.approval_rate * 100) + '%';
    document.getElementById('kpi-resolved').textContent = Math.round(data.resolved_rate * 100) + '%';
    document.getElementById('kpi-deflected').textContent = Math.round(data.deflection_rate * 100) + '%';
    document.getElementById('kpi-saved').textContent = Math.round(data.estimated_time_saved_minutes / 60 * 10) / 10 + 'h';
  } catch (err) {
    console.error('Failed to load metrics', err);
  }
}

// -------------------------------------------------------------
// THREAD LIST RENDERER
// -------------------------------------------------------------
async function loadThreads() {
  try {
    const data = await fetchJSON('/api/threads');
    state.threads = data.threads;
    renderThreadsList();
  } catch (err) {
    console.error('Failed to load threads', err);
  }
}

function renderThreadsList() {
  const container = document.getElementById('threads-container');
  container.innerHTML = '';

  if (state.threads.length === 0) {
    container.innerHTML = '<div class="thread-empty">No threads found</div>';
    return;
  }

  state.threads.forEach(t => {
    const isSelected = state.selectedThread && state.selectedThread.thread && state.selectedThread.thread.thread_id === t.thread_id;
    const row = document.createElement('button');
    row.className = `thread-row ${isSelected ? 'selected' : ''}`;

    let timeStr = '';
    if (t.last_updated) {
      try {
        const d = new Date(t.last_updated);
        timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch (e) { }
    }

    row.innerHTML = `
      <div class="thread-row-header">
        <span class="thread-row-id">${t.thread_id}</span>
        <span class="thread-row-status ${t.approved ? 'status-tag-approved' : 'status-tag-pending'}">
          ${t.approved ? 'Approved' : 'Pending'}
        </span>
      </div>
      <div class="thread-row-body">${t.product} : ${t.intent.replace(/_/g, ' ').toUpperCase()}</div>
      <div class="thread-row-footer">
        <div class="badge-intent-dot">
          <span class="intent-color-indicator intent-color-${t.intent}"></span>
          <span>${t.customer_name}</span>
        </div>
        <span>${timeStr} (${t.message_count} msg)</span>
      </div>
    `;

    row.addEventListener('click', () => selectThread(t.thread_id));
    container.appendChild(row);
  });
}

// -------------------------------------------------------------
// SELECT THREAD & LOAD CRM / CONTEXT
// -------------------------------------------------------------
async function selectThread(threadId) {
  try {
    const detail = await fetchJSON(`/api/threads/${threadId}`);
    state.selectedThread = detail;
    state.selectedEngine = detail.approval ? (detail.approval.engine_used || 'rules') : 'rules';

    // Reset search state
    state.searchMatches = [];
    state.currentSearchIndex = -1;
    document.getElementById('thread-search').value = '';
    document.getElementById('search-count').textContent = '';

    // Reset playbook log
    const logBox = document.getElementById('actions-log');
    logBox.style.display = 'none';
    logBox.innerHTML = '';

    renderThreadsList();
    renderCRMProfile(detail.crm_profile);
    renderChatMessages(detail.messages);
    renderPlaybookActions(detail.playbook_actions, threadId);
    updateEngineSelectorUI();

    if (detail.approval) {
      state.originalSummary = detail.summary.draft;
      document.getElementById('ai-summary').textContent = detail.summary.draft;
      document.getElementById('edit-summary').value = detail.approval.approved_summary;
    } else {
      await triggerSummarize();
    }

    updateCharCount();

    const statusBox = document.getElementById('status');
    statusBox.textContent = '';
    statusBox.className = 'status-banner';

    if (state.showDiff) {
      renderDiff();
    }

  } catch (err) {
    console.error('Error selecting thread:', err);
  }
}

// Render CRM Card
function renderCRMProfile(crm) {
  const container = document.getElementById('crm-profile');
  container.innerHTML = `
    <div class="crm-profile-cell">
      <span class="lbl">Customer ID</span>
      <span class="val">${crm.customer_id || 'Unknown'}</span>
    </div>
    <div class="crm-profile-cell">
      <span class="lbl">Customer Tier</span>
      <div>
        <span class="val-badge tier-${(crm.tier || 'standard').toLowerCase()}">${crm.tier || 'Standard'}</span>
      </div>
    </div>
    <div class="crm-profile-cell">
      <span class="lbl">Entitlements</span>
      <span class="val" style="font-size:12px;">${crm.entitlements.length > 0 ? crm.entitlements.join(', ') : 'None'}</span>
    </div>
    <div class="crm-profile-cell">
      <span class="lbl">Shipping Restrictions</span>
      <span class="val" style="font-size:12px;">${crm.shipping_restrictions.length > 0 ? crm.shipping_restrictions.join(', ') : 'None'}</span>
    </div>
  `;
}

// Render Chronological Chat bubbles
function renderChatMessages(messages) {
  const container = document.getElementById('chat-messages');
  container.innerHTML = '';

  if (messages.length === 0) {
    container.innerHTML = '<div class="chat-empty">No message history</div>';
    return;
  }

  messages.forEach(m => {
    const wrapper = document.createElement('div');
    wrapper.className = `chat-bubble-wrapper ${m.role}`;

    let dateStr = m.timestamp;
    try {
      const d = new Date(m.timestamp);
      dateStr = d.toLocaleString();
    } catch (e) { }

    wrapper.innerHTML = `
      <div class="chat-bubble-meta">${m.sender} &bull; ${dateStr}</div>
      <div class="chat-bubble">${m.body}</div>
    `;
    container.appendChild(wrapper);
  });
}

// Render Playbook Action buttons
function renderPlaybookActions(actions, threadId) {
  const container = document.getElementById('playbook-actions-container');
  container.innerHTML = '';

  if (actions.length === 0) {
    container.innerHTML = '<div class="playbook-empty">No playbook actions specified for this intent</div>';
    return;
  }

  actions.forEach(act => {
    const btn = document.createElement('button');
    btn.className = 'btn-action';
    btn.textContent = act;
    btn.addEventListener('click', () => triggerPlaybookAction(act, threadId, btn));
    container.appendChild(btn);
  });
}

// Trigger Playbook actions via webhook mock
async function triggerPlaybookAction(actionType, threadId, buttonElem) {
  try {
    const res = await fetch('/api/trigger_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_type: actionType, thread_id: threadId })
    });

    if (res.ok) {
      const data = await res.json();

      const editor = document.getElementById('edit-summary');
      const separator = editor.value.trim() ? '\n' : '';
      editor.value = editor.value.trim() + separator + data.log_entry;
      updateCharCount();

      if (state.showDiff) {
        renderDiff();
      }

      buttonElem.disabled = true;
      buttonElem.textContent = `✓ ${actionType}`;

      const logBox = document.getElementById('actions-log');
      logBox.style.display = 'block';
      const logItem = document.createElement('div');
      logItem.textContent = data.log_entry;
      logBox.appendChild(logItem);
      logBox.scrollTop = logBox.scrollHeight;
    }
  } catch (err) {
    console.error('Failed triggering playbook action:', err);
  }
}

// -------------------------------------------------------------
// ENGINE DRAFT GENERATION
// -------------------------------------------------------------
async function triggerSummarize() {
  const t = state.selectedThread;
  if (!t) return;

  const aiSummaryBox = document.getElementById('ai-summary');
  aiSummaryBox.textContent = 'Summarizing thread context...';

  try {
    const res = await fetch('/api/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: t.thread.thread_id, engine: state.selectedEngine })
    });
    const summaryPayload = await res.json();

    state.originalSummary = summaryPayload.draft;
    aiSummaryBox.textContent = summaryPayload.draft;

    if (!t.approval) {
      document.getElementById('edit-summary').value = summaryPayload.draft;
    }

    // Update engine badge
    const activeBadge = document.getElementById('active-engine-badge');
    activeBadge.textContent = state.selectedEngine === 'rules' ? 'Rules-Based' : 'Claude LLM';
    activeBadge.className = `engine-badge-tag ${state.selectedEngine === 'rules' ? 'rules' : 'llm'}`;

  } catch (err) {
    console.error('Summarize error:', err);
    aiSummaryBox.textContent = 'Error generating AI summary draft.';
  }
}

// FIX: correct engine toggle UI logic
function updateEngineSelectorUI() {
  const rulesBtn = document.getElementById('engine-rules-btn');
  const llmBtn = document.getElementById('engine-llm-btn');

  if (state.selectedEngine === 'rules') {
    rulesBtn.classList.add('active');
    llmBtn.classList.remove('active');
  } else {
    llmBtn.classList.add('active');
    rulesBtn.classList.remove('active');
  }
}

// Toggle engine button listeners
document.getElementById('engine-rules-btn').addEventListener('click', () => {
  if (state.selectedEngine === 'rules') return;
  state.selectedEngine = 'rules';
  updateEngineSelectorUI();
  triggerSummarize().then(() => {
    if (state.showDiff) renderDiff();
  });
});

document.getElementById('engine-llm-btn').addEventListener('click', () => {
  if (state.selectedEngine === 'llm') return;
  state.selectedEngine = 'llm';
  updateEngineSelectorUI();
  triggerSummarize().then(() => {
    if (state.showDiff) renderDiff();
  });
});

// -------------------------------------------------------------
// CHAR COUNT
// -------------------------------------------------------------
const editSummaryArea = document.getElementById('edit-summary');
editSummaryArea.addEventListener('input', () => {
  updateCharCount();
  if (state.showDiff) {
    renderDiff();
  }
});

function updateCharCount() {
  const val = editSummaryArea.value || '';
  document.getElementById('char-count').textContent = `${val.length} chars`;
}

// -------------------------------------------------------------
// CLIENT-SIDE WORD DIFF VIEWER (LCS)
// -------------------------------------------------------------
function diffWords(oldStr, newStr) {
  const oldWords = oldStr.split(/(\s+)/);
  const newWords = newStr.split(/(\s+)/);

  const n = oldWords.length;
  const m = newWords.length;

  const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));

  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (oldWords[i - 1] === newWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  let i = n, j = m;
  const fragments = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
      fragments.push({ type: 'same', text: oldWords[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      fragments.push({ type: 'ins', text: newWords[j - 1] });
      j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      fragments.push({ type: 'del', text: oldWords[i - 1] });
      i--;
    }
  }

  return fragments.reverse();
}

function renderDiff() {
  const diffPanel = document.getElementById('diff-view');
  const draft = state.originalSummary || '';
  const current = editSummaryArea.value || '';

  diffPanel.innerHTML = '';

  const diffData = diffWords(draft, current);
  diffData.forEach(chunk => {
    if (chunk.type === 'same') {
      diffPanel.appendChild(document.createTextNode(chunk.text));
    } else if (chunk.type === 'ins') {
      const insNode = document.createElement('ins');
      insNode.textContent = chunk.text;
      diffPanel.appendChild(insNode);
    } else if (chunk.type === 'del') {
      const delNode = document.createElement('del');
      delNode.textContent = chunk.text;
      diffPanel.appendChild(delNode);
    }
  });
}

document.getElementById('toggle-diff-btn').addEventListener('click', () => {
  state.showDiff = !state.showDiff;
  const btn = document.getElementById('toggle-diff-btn');
  const panel = document.getElementById('diff-view');

  if (state.showDiff) {
    btn.textContent = 'Hide Changes';
    panel.classList.remove('hidden');
    renderDiff();
  } else {
    btn.textContent = 'Show Changes';
    panel.classList.add('hidden');
  }
});

// Levenshtein character distance for reporting
function computeLevenshtein(a, b) {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;

  const matrix = [];
  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }

  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  return matrix[b.length][a.length];
}

// -------------------------------------------------------------
// APPROVAL SUBMISSION
// -------------------------------------------------------------
document.getElementById('approve-btn').addEventListener('click', async () => {
  const t = state.selectedThread;
  if (!t) return;

  const approved_summary = editSummaryArea.value;
  const approver = document.getElementById('approver').value.trim() || 'ce_associate';
  const distance = computeLevenshtein(state.originalSummary, approved_summary);

  const statusBox = document.getElementById('status');
  statusBox.textContent = 'Submitting approval...';
  statusBox.className = 'status-banner';

  try {
    const res = await fetch('/api/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        thread_id: t.thread.thread_id,
        approved_summary,
        approver,
        engine_used: state.selectedEngine,
        edit_distance: distance
      })
    });

    if (res.ok) {
      statusBox.textContent = '✓ Summary approved and logged!';
      statusBox.className = 'status-banner status-success';

      await loadThreads();
      await selectThread(t.thread.thread_id);
      await loadMetrics();
    } else {
      statusBox.textContent = 'Approval failed. Server responded with error.';
      statusBox.className = 'status-banner status-error';
    }
  } catch (err) {
    statusBox.textContent = 'Network error during approval.';
    statusBox.className = 'status-banner status-error';
  }
});

// -------------------------------------------------------------
// CHAT SEARCH & HIGHLIGHTING
// -------------------------------------------------------------
const searchInput = document.getElementById('thread-search');
searchInput.addEventListener('input', runSearch);

document.getElementById('search-next-btn').addEventListener('click', () => {
  if (state.searchMatches.length === 0) return;
  state.currentSearchIndex = (state.currentSearchIndex + 1) % state.searchMatches.length;
  highlightActiveMatch();
});

function runSearch() {
  const q = searchInput.value.trim().toLowerCase();
  const bubbles = document.querySelectorAll('.chat-bubble');
  const countLabel = document.getElementById('search-count');

  bubbles.forEach(b => {
    b.innerHTML = b.textContent;
  });

  state.searchMatches = [];
  state.currentSearchIndex = -1;
  countLabel.textContent = '';

  if (!q) return;

  let matchCount = 0;
  bubbles.forEach((b) => {
    const text = b.textContent;
    const lower = text.toLowerCase();

    if (lower.includes(q)) {
      const regex = new RegExp(`(${escapeRegExp(q)})`, 'gi');
      let matchHtml = text.replace(regex, `<span class="match-highlight" data-match-id="${matchCount}">$1</span>`);
      b.innerHTML = matchHtml;

      const elements = b.querySelectorAll('.match-highlight');
      elements.forEach(el => {
        state.searchMatches.push(el);
        matchCount++;
      });
    }
  });

  if (matchCount > 0) {
    state.currentSearchIndex = 0;
    highlightActiveMatch();
  } else {
    countLabel.textContent = '0/0';
  }
}

function highlightActiveMatch() {
  const countLabel = document.getElementById('search-count');
  state.searchMatches.forEach(el => el.classList.remove('active-match'));

  if (state.currentSearchIndex === -1 || state.searchMatches.length === 0) return;

  const activeEl = state.searchMatches[state.currentSearchIndex];
  activeEl.classList.add('active-match');
  activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  countLabel.textContent = `${state.currentSearchIndex + 1}/${state.searchMatches.length}`;
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// -------------------------------------------------------------
// ROI OUTCOMES CALCULATOR
// -------------------------------------------------------------
const sliderVol = document.getElementById('slider-vol');
const sliderWage = document.getElementById('slider-wage');
const sliderTime = document.getElementById('slider-time');

function updateROICalculations() {
  const vol = parseInt(sliderVol.value);
  const wage = parseInt(sliderWage.value);
  const time = parseInt(sliderTime.value);

  document.getElementById('slider-vol-value').textContent = vol;
  document.getElementById('slider-wage-value').textContent = `$${wage}`;
  document.getElementById('slider-time-value').textContent = `${time} min`;

  const dailyHoursSaved = (vol * time) / 60;
  const annualHoursSaved = dailyHoursSaved * 250;
  const annualLaborSavings = annualHoursSaved * wage;
  const ebitdaContribution = annualLaborSavings * 0.20;
  const csatLift = time * 0.3;

  document.getElementById('roi-hours-daily').textContent = dailyHoursSaved.toFixed(1) + 'h';
  document.getElementById('roi-hours-annual').textContent = Math.round(annualHoursSaved) + 'h';
  document.getElementById('roi-savings-annual').textContent = '$' + Math.round(annualLaborSavings).toLocaleString();
  document.getElementById('roi-ebitda').textContent = '$' + Math.round(ebitdaContribution).toLocaleString();
  document.getElementById('roi-csat').textContent = '+' + csatLift.toFixed(1) + '%';
}

sliderVol.addEventListener('input', updateROICalculations);
sliderWage.addEventListener('input', updateROICalculations);
sliderTime.addEventListener('input', updateROICalculations);

updateROICalculations();

// -------------------------------------------------------------
// APP INITIALIZATION
// -------------------------------------------------------------
window.addEventListener('DOMContentLoaded', async () => {
  await checkAndPromptAPIKey();
  await loadMetrics();
  await loadThreads();

  if (state.threads.length > 0) {
    selectThread(state.threads[0].thread_id);
  }
});