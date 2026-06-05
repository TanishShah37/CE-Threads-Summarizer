# CE Support Workstation & Thread Summarizer

This prototype is a production-grade workstation for Customer Experience (CE) associates, designed to summarize raw email threads, surface CRM profile insights, trigger playbook actions, edit/approve AI drafts, and calculate real-time business ROI.

## Features

- **Dual-Engine NLP Summarization**:
  - **Tier 1 (Rules-Based)**: Keyword intent classifier, polarity sentiment scorer, and entities extractor (zero cost, deterministic, offline-first).
  - **Tier 2 (Generative AI)**: Interfaces with Anthropic's Claude (`claude-3-5-sonnet-20241022`) for structured, high-fidelity JSON summaries. Gracefully falls back to mock responses when no API key is set.
- **3-Column Workspace SPA**:
  - **Left Sidebar**: Operations Metrics (KPI indicators) + Active Mail inbox list.
  - **Center Column**: Customer CRM Profile (tier, entitlements, shipping constraints) + Chat bubble thread history with keyword search matching (scroll-to-match loop) + CRM Playbook actions with simulated webhooks.
  - **Right Column**: AI Copilot workstation with textarea editor, word-level LCS Diff Viewer ("Show Changes"), Levenshtein edit distance logging, and real-time ROI Impact Calculator.

---

## Getting Started

### Local Setup & Execution

1. Create and activate a virtual environment (optional but recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. (Optional) Configure Anthropic API:
   Set `ANTHROPIC_API_KEY` in your environment or write it to a `.env` file in the root directory:
   ```bash
   echo "ANTHROPIC_API_KEY=your_key_here" > .env
   ```

4. Run the Flask server:
   ```bash
   python3 app.py
   ```
   Open `http://localhost:8000` in your web browser.

---

## Directory Structure

```
ce-summarizer/
├── app.py                      # Flask routing & CRM mappings
├── summarizer/
│   ├── rules.py                # Rules-based NLP logic (Tier 1)
│   ├── llm.py                  # Generative AI Claude module (Tier 2)
│   └── mock_responses.py       # High-fidelity mock LLM payloads
├── data/
│   ├── ce_exercise_threads.json# Source inbox dataset
│   ├── crm.json                # CRM Customer database
│   ├── playbooks.json          # Intent -> Playbook Action mappings
│   ├── approved_summaries.json # Approval logs database (gitignored)
│   └── approved_export.json    # Export file generated on approvals
├── static/
│   ├── styles.css              # Premium dark glassmorphism stylesheet
│   └── app.js                  # Client SPA logic, diff engine, ROI calculator
├── templates/
│   └── index.html              # Core SPA markup
├── tests/
│   ├── test_routes.py          # API route unit tests
│   └── test_summarizer.py      # Rules & LLM unit tests
└── requirements.txt            # Python dependencies
```

---

## Running Automated Tests

Run the automated test suite to verify route mappings and NLP engines:
```bash
python3 -m unittest discover tests
```
All tests verify endpoint status codes, JSON outputs, and fallback summarizer logic.
