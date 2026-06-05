# CE Support Workstation & Thread Summarizer

A production-grade workstation for Customer Experience (CE) associates to summarize raw email threads, surface CRM context, trigger playbook actions, edit/approve AI drafts, and measure real-time business ROI.

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd ce-summarizer

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip3 install -r requirements.txt

# 4. (Optional but recommended) Add your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 5. Run the server
python3 app.py
```

Open **http://localhost:8000** in your browser.

---

## API Key — Optional, Not Mandatory

The app works **fully without an API key**. The LLM engine falls back to high-fidelity mock responses that are pre-written per thread with structured intent, sentiment, root cause, and resolution plan.

| Mode | How to activate | LLM engine behaviour |
|---|---|---|
| **No key (default)** | Just run `python3 app.py` | Uses mock responses — labeled `[Mock LLM — no API key]` |
| **Live AI** | Set `ANTHROPIC_API_KEY` in `.env` or enter it in the UI prompt on first load | Calls Claude (`claude-3-5-sonnet-20241022`) via Anthropic API |

You can also enter the key at runtime — the app prompts you on first load and writes it to `.env` without a server restart.

To get a key: https://console.anthropic.com/settings/keys

---

## Features

- **Dual-Engine NLP Summarization**
  - **Tier 1 — Rules-Based**: Keyword intent classifier, polarity sentiment scorer, entity extractor. Zero cost, deterministic, always works offline.
  - **Tier 2 — Generative AI**: Calls Claude (`claude-3-5-sonnet-20241022`) for structured JSON summaries with root cause, resolution plan, and sentiment. Falls back to mock if no key is set.

- **3-Column Workspace SPA**
  - **Left sidebar**: Operations metrics (KPI strip) + active mail inbox with intent badges and sentiment dots.
  - **Center column**: CRM customer profile card (tier, entitlements, shipping constraints) + chronological chat bubble thread visualizer with keyword search + intent-specific playbook actions with simulated CRM/ERP webhooks.
  - **Right column**: AI Copilot draft viewer, editable associate textarea, word-level LCS diff viewer, Levenshtein edit distance logging, approver name input, and live ROI impact calculator.

- **Export**: Download all approved summaries as JSON or CSV via the header buttons.

---

## Directory Structure

```
ce-summarizer/
├── app.py                        # Flask routes & CRM join logic
├── summarizer/
│   ├── rules.py                  # Tier 1 rules-based NLP engine
│   ├── llm.py                    # Tier 2 Claude API module
│   └── mock_responses.py         # High-fidelity mock LLM payloads (per thread)
├── data/
│   ├── ce_exercise_threads.json  # Source email thread dataset
│   ├── crm.json                  # Customer CRM database
│   ├── playbooks.json            # Intent → playbook action mapping
│   ├── approved_summaries.json   # Approval log (auto-created, gitignored)
│   └── approved_export.json      # Denormalised export (auto-created)
├── static/
│   ├── styles.css                # Dark glassmorphism stylesheet
│   └── app.js                    # SPA logic, diff engine, ROI calculator
├── templates/
│   └── index.html                # Single-page app shell
├── tests/
│   ├── test_routes.py            # Flask API route tests
│   └── test_summarizer.py        # Rules & LLM engine unit tests
├── .env                          # Your API key goes here (gitignored)
├── .env.example                  # Template — copy to .env
└── requirements.txt              # Python dependencies
```

---

## Running Tests

```bash
python3 -m unittest discover tests
```

Covers all API endpoints, approval persistence, rules engine intent/sentiment/status inference, and LLM mock fallback behaviour.

To test individual files:

```bash
python3 -m unittest tests.test_routes
python3 -m unittest tests.test_summarizer
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/threads` | List all threads with metadata |
| `GET` | `/api/threads/<id>` | Full thread detail, CRM profile, summary, playbook actions |
| `POST` | `/api/summarize` | Generate summary — body: `{"thread_id": "...", "engine": "rules" \| "llm"}` |
| `POST` | `/api/approve` | Save approved summary — body: `{"thread_id", "approved_summary", "approver", "engine_used", "edit_distance"}` |
| `POST` | `/api/trigger_action` | Simulate CRM/ERP webhook — body: `{"action_type": "...", "thread_id": "..."}` |
| `GET` | `/api/metrics` | Approval rate, resolution rate, deflection rate, time saved |
| `GET` | `/api/check_key` | Check whether `ANTHROPIC_API_KEY` is set |
| `POST` | `/api/set_key` | Set API key at runtime without server restart |
| `GET` | `/export/json` | Download all approvals as JSON |
| `GET` | `/export/csv` | Download all approvals as CSV |

---

## Manual Verification Checklist

After starting the server, verify:

- [ ] 3-column layout renders at `localhost:8000`
- [ ] Thread list loads with intent badges and sentiment dots
- [ ] Clicking a thread populates CRM card, chat bubbles, and playbook actions
- [ ] Rules engine generates a structured summary draft
- [ ] Toggling to Generative AI loads a different summary (or mock if no key)
- [ ] Editing the summary and clicking Show Changes shows green/red diff markup
- [ ] Clicking a playbook action disables the button, appends a log entry to the textarea
- [ ] Approving with a name saves to `data/approved_summaries.json` and updates the KPI strip
- [ ] ROI sliders update all 5 output values in real time
- [ ] Export JSON and Export CSV buttons download correctly

---

## curl Examples

```bash
# List all threads
curl http://localhost:8000/api/threads

# Get thread detail
curl http://localhost:8000/api/threads/CE-405467-683

# Generate LLM summary
curl -X POST http://localhost:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "CE-405467-683", "engine": "llm"}'

# Approve a summary
curl -X POST http://localhost:8000/api/approve \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "CE-405467-683", "approved_summary": "Refund approved.", "approver": "sarah.chen", "engine_used": "llm", "edit_distance": 18}'

# Trigger a playbook action
curl -X POST http://localhost:8000/api/trigger_action \
  -H "Content-Type: application/json" \
  -d '{"action_type": "Issue Refund (Stripe mock)", "thread_id": "CE-405467-683"}'

# Check API key status
curl http://localhost:8000/api/check_key

# Set API key at runtime
curl -X POST http://localhost:8000/api/set_key \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-ant-..."}'
```

---

## Stack & NLP Notes

**Stack:** Flask (Python 3.11) + Vanilla JS SPA. No build step — install dependencies and run. Flat JSON files as data layer (sufficient for prototype scale).

**NLP choice:** Dual-engine by design. The rules engine gives deterministic, auditable output that always works. The LLM engine (Claude) adds nuance — implicit sentiment, root cause inference, and resolution suggestions that keyword matching misses. The `edit_distance` field logged on every approval creates a quality signal: low edit distance = the AI draft was accurate; high edit distance = the prompt needs tuning.

**Known limitations:** Flat-file storage is not concurrent-safe at scale. Playbook webhooks are simulated. The LLM prompt is not fine-tuned on CE-specific taxonomy.

**Scale-up path:** PostgreSQL + SQLAlchemy for storage → Celery + Redis for async LLM calls → prompt versioning → fine-tune on approved summaries dataset to reduce cost and latency.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | Enables live Claude summaries. Without it, mock responses are used. |

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# then edit .env and add: ANTHROPIC_API_KEY=sk-ant-...
```