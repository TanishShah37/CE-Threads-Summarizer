## CE Threads Summarizer Prototype

This prototype ingests CE email threads, generates AI automated draft summaries via a rules-based NLP approach, and supports an edit/approve workflow for CE associates. Approved outputs

### Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py  # runs on http://localhost:8000
```

Data paths:
- Input dataset: `data/ce_exercise_threads.json`
- Approvals: `data/approvals.json`
- Usable export: `data/approved_export.json`

### Stack
- Flask (Python) for API and server-rendered UI shell
- Vanilla JS/CSS for the edit/approve front-end
- Rules-based NLP (no external API) for fast prototyping and deterministic output

### Summarization choice
- Simple keyword-based intent and action extraction from topic/subject and first customer message
- Status inferred from last company message
- Structured bullet summary with next-step playbook and mock CRM context (SLA hours)


### Workflow integration with CRM context
- Mocked `crm_context` added to each thread: `customer_tier` (Standard) and `sla_hours` by intent.


### Edit/Approve step
- UI shows AI draft summary → associate edits → hits Approve.

### Scaling plan
- Replace rules summarizer with hosted LLM (batchable) or local model (vLLM) and add retrieval over message history for better faithfulness.
- Add auth + role-based approvals and audit log.
- Store data in a DB (e.g., Postgres) and emit events to CRM/Helpdesk via webhook/queue.
- Add metrics: time saved, approval rate, deflection rate; measure CSAT impact.

- Approval persists editor name, timestamp, and summary. Export updated concurrently.



