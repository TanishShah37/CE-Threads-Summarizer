import json
import os
import io
import csv
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, Response
from dateutil import parser as date_parser

from summarizer.rules import rules_summarize, infer_intent_from_text, infer_status_from_text
from summarizer.llm import llm_summarize

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_ROOT, "data")
STATIC_DIR = os.path.join(APP_ROOT, "static")
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")

DATASET_PATH = os.path.join(DATA_DIR, "ce_exercise_threads.json")
APPROVED_SUMMARIES_PATH = os.path.join(DATA_DIR, "approved_summaries.json")
CRM_PATH = os.path.join(DATA_DIR, "crm.json")
PLAYBOOKS_PATH = os.path.join(DATA_DIR, "playbooks.json")
EXPORT_PATH = os.path.join(DATA_DIR, "approved_export.json")

def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default

def save_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def normalize_thread(raw: Dict[str, Any]) -> Dict[str, Any]:
    messages = raw.get("messages", [])
    def ts(m: Dict[str, Any]) -> float:
        try:
            return date_parser.parse(m.get("timestamp", "")).timestamp()
        except Exception:
            return 0.0
    messages = sorted(messages, key=ts)
    return {
        "thread_id": raw.get("thread_id"),
        "topic": raw.get("topic"),
        "subject": raw.get("subject"),
        "initiated_by": raw.get("initiated_by"),
        "order_id": raw.get("order_id"),
        "product": raw.get("product"),
        "messages": messages,
    }

def get_crm_profile(order_id: str) -> Dict[str, Any]:
    crm = load_json(CRM_PATH, default={"customers": []})
    for c in crm.get("customers", []):
        if order_id in c.get("orders", []):
            return {
                "customer_id": c.get("customer_id"),
                "tier": c.get("tier"),
                "entitlements": c.get("entitlements", []),
                "shipping_restrictions": c.get("shipping_constraints", []),
                "shipping_constraints": c.get("shipping_constraints", [])
            }
    return {
        "customer_id": None,
        "tier": "Standard",
        "entitlements": [],
        "shipping_restrictions": [],
        "shipping_constraints": []
    }

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_DIR)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/threads")
def api_threads():
    raw = load_json(DATASET_PATH, default={"threads": []})
    threads = [normalize_thread(t) for t in raw.get("threads", [])]
    approvals = load_json(APPROVED_SUMMARIES_PATH, default={})
    
    thread_list = []
    for t in threads:
        tid = t.get("thread_id")
        appr = approvals.get(tid)
        
        # Determine current state / summary
        summary_info = rules_summarize(t)
        crm_info = get_crm_profile(t.get("order_id"))
        
        # Add CRM context information
        summary_info["crm_context"].update({
            "customer_tier": crm_info["tier"],
            "entitlements": crm_info["entitlements"],
            "shipping_constraints": crm_info["shipping_constraints"],
            "customer_id": crm_info["customer_id"],
        })
        
        thread_list.append({
            "thread_id": tid,
            "customer_name": t.get("initiated_by") or "Customer", # fallback if missing
            "customer_id": crm_info["customer_id"],
            "intent": summary_info["intent"],
            "sentiment": summary_info["sentiment"],
            "message_count": len(t.get("messages", [])),
            "last_updated": t.get("messages", [])[-1].get("timestamp") if t.get("messages") else None,
            "approved": appr is not None,
            "approval": appr,
            "order_id": t.get("order_id"),
            "product": t.get("product")
        })
    return jsonify({"threads": thread_list})

@app.get("/api/threads/<id>")
def api_thread_detail(id: str):
    raw = load_json(DATASET_PATH, default={"threads": []})
    thread_raw = next((t for t in raw.get("threads", []) if t.get("thread_id") == id), None)
    if not thread_raw:
        return jsonify({"error": "Thread not found"}), 404
        
    thread = normalize_thread(thread_raw)
    crm_info = get_crm_profile(thread.get("order_id"))
    
    # Load playbooks mapping
    playbooks = load_json(PLAYBOOKS_PATH, default={})
    
    # Run default rules summarizer
    summary_info = rules_summarize(thread)
    summary_info["crm_context"].update({
        "customer_tier": crm_info["tier"],
        "entitlements": crm_info["entitlements"],
        "shipping_constraints": crm_info["shipping_constraints"],
        "customer_id": crm_info["customer_id"],
    })
    
    # Map intent to playbook actions
    intent = summary_info["intent"]
    actions = playbooks.get(intent, ["Send Template Reply", "Log Inquiry Note"])
    
    approvals = load_json(APPROVED_SUMMARIES_PATH, default={})
    appr = approvals.get(id)
    
    # Format messages
    messages = []
    for m in thread.get("messages", []):
        # Infer sender role/name
        sender_val = m.get("sender") or "customer"
        messages.append({
            "sender": "CE Associate" if sender_val == "company" else (thread.get("initiated_by") or "Customer"),
            "role": sender_val,
            "timestamp": m.get("timestamp"),
            "body": m.get("body")
        })
        
    response_data = {
        "thread": {
            "thread_id": thread.get("thread_id"),
            "topic": thread.get("topic"),
            "subject": thread.get("subject"),
            "order_id": thread.get("order_id"),
            "product": thread.get("product")
        },
        "messages": messages,
        "crm_profile": crm_info,
        "summary": {
            "engine": "rules",
            "draft": summary_info["summary_markdown"],
            "intent": intent,
            "sentiment": summary_info["sentiment"],
            "entities": {
                "order_id": thread.get("order_id"),
                "product": thread.get("product")
            }
        },
        "playbook_actions": actions,
        "approval": appr
    }
    return jsonify(response_data)

@app.post("/api/summarize")
def api_summarize():
    data = request.get_json(force=True)
    thread_id = data.get("thread_id")
    engine = data.get("engine", "rules")
    
    raw = load_json(DATASET_PATH, default={"threads": []})
    thread_raw = next((t for t in raw.get("threads", []) if t.get("thread_id") == thread_id), None)
    if not thread_raw:
        return jsonify({"error": "Thread not found"}), 404
        
    thread = normalize_thread(thread_raw)
    
    if engine == "llm":
        summary_info = llm_summarize(thread)
    else:
        summary_info = rules_summarize(thread)
        
    # Inject CRM details
    crm_info = get_crm_profile(thread.get("order_id"))
    summary_info["crm_context"].update({
        "customer_tier": crm_info["tier"],
        "entitlements": crm_info["entitlements"],
        "shipping_constraints": crm_info["shipping_constraints"],
        "customer_id": crm_info["customer_id"],
    })
    
    return jsonify({
        "engine": engine,
        "draft": summary_info["summary_markdown"],
        "intent": summary_info["intent"],
        "sentiment": summary_info.get("sentiment", "neutral"),
        "entities": {
            "order_id": thread.get("order_id"),
            "product": thread.get("product")
        }
    })

@app.post("/api/approve")
def api_approve():
    data = request.get_json(force=True)
    thread_id = data.get("thread_id")
    approved_summary = data.get("approved_summary")
    approver = data.get("approver") or "ce_associate"
    engine_used = data.get("engine_used") or "rules"
    edit_distance = data.get("edit_distance") or 0
    
    if not thread_id or approved_summary is None:
        return jsonify({"error": "thread_id and approved_summary are required"}), 400
        
    ensure_dirs()
    approvals = load_json(APPROVED_SUMMARIES_PATH, default={})
    
    approved_intent = infer_intent_from_text(approved_summary)
    approved_status = infer_status_from_text(approved_summary)
    
    record = {
        "approved_summary": approved_summary,
        "approver": approver,
        "approved_at": datetime.utcnow().isoformat() + "Z",
        "approved_intent": approved_intent,
        "approved_status": approved_status,
        "engine_used": engine_used,
        "edit_distance": edit_distance
    }
    approvals[thread_id] = record
    save_json(APPROVED_SUMMARIES_PATH, approvals)
    
    # Denormalize and export
    export_records = []
    raw = load_json(DATASET_PATH, default={"threads": []})
    threads = [normalize_thread(t) for t in raw.get("threads", [])]
    for t in threads:
        tid = t.get("thread_id")
        appr = approvals.get(tid, {})
        crm_info = get_crm_profile(t.get("order_id"))
        rules_info = rules_summarize(t)
        
        rec = {
            "thread_id": tid,
            "order_id": t.get("order_id"),
            "product": t.get("product"),
            "intent": rules_info.get("intent"),
            "status": rules_info.get("status"),
            "approved_summary": appr.get("approved_summary"),
            "approved_intent": appr.get("approved_intent"),
            "approved_status": appr.get("approved_status"),
            "customer_id": crm_info.get("customer_id"),
            "customer_tier": crm_info.get("tier"),
            "entitlements": crm_info.get("entitlements"),
            "shipping_constraints": crm_info.get("shipping_constraints"),
        }
        export_records.append(rec)
    save_json(EXPORT_PATH, export_records)
    
    return jsonify({"ok": True, "approval": record})

@app.post("/api/trigger_action")
def api_trigger_action():
    data = request.get_json(force=True)
    action_type = data.get("action_type")
    thread_id = data.get("thread_id")
    
    if not action_type or not thread_id:
        return jsonify({"error": "action_type and thread_id are required"}), 400
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] Action: {action_type} - SUCCESS"
    
    return jsonify({
        "ok": True,
        "log_entry": log_entry
    })

@app.get("/export/json")
def export_json():
    ensure_dirs()
    approvals = load_json(APPROVED_SUMMARIES_PATH, default={})
    raw = load_json(DATASET_PATH, default={"threads": []})
    threads = [normalize_thread(t) for t in raw.get("threads", [])]
    
    export_records = []
    for t in threads:
        tid = t.get("thread_id")
        ai = rules_summarize(t)
        appr = approvals.get(tid, {})
        export_records.append({
            "thread_id": tid,
            "order_id": t.get("order_id"),
            "product": t.get("product"),
            "intent": ai.get("intent"),
            "status": ai.get("status"),
            "approved_summary": appr.get("approved_summary"),
            "approved_intent": appr.get("approved_intent"),
            "approved_status": appr.get("approved_status"),
            "engine_used": appr.get("engine_used"),
            "edit_distance": appr.get("edit_distance")
        })
    payload = json.dumps(export_records, ensure_ascii=False, indent=2)
    return Response(payload, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=approved_export.json"})

@app.get("/export/csv")
def export_csv():
    ensure_dirs()
    approvals = load_json(APPROVED_SUMMARIES_PATH, default={})
    raw = load_json(DATASET_PATH, default={"threads": []})
    threads = [normalize_thread(t) for t in raw.get("threads", [])]
    
    output = io.StringIO()
    writer = csv.writer(output)
    header = [
        "thread_id", "order_id", "product",
        "intent", "status", "approved_summary", "approved_intent", "approved_status",
        "customer_id", "customer_tier", "entitlements", "shipping_constraints",
        "engine_used", "edit_distance"
    ]
    writer.writerow(header)
    for t in threads:
        tid = t.get("thread_id")
        ai = rules_summarize(t)
        crm_info = get_crm_profile(t.get("order_id"))
        appr = approvals.get(tid, {})
        row = [
            tid,
            t.get("order_id"),
            t.get("product"),
            ai.get("intent"),
            ai.get("status"),
            (appr.get("approved_summary") or "").replace("\n", " ").strip(),
            appr.get("approved_intent"),
            appr.get("approved_status"),
            crm_info.get("customer_id"),
            crm_info.get("tier"),
            ";".join(crm_info.get("entitlements", [])),
            ";".join(crm_info.get("shipping_constraints", [])),
            appr.get("engine_used", ""),
            appr.get("edit_distance", "")
        ]
        writer.writerow(row)
    data = output.getvalue()
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=approved_export.csv"})

@app.get("/api/metrics")
def api_metrics():
    raw = load_json(DATASET_PATH, default={"threads": []})
    threads = [normalize_thread(t) for t in raw.get("threads", [])]
    approvals = load_json(APPROVED_SUMMARIES_PATH, default={})
    
    total = len(threads)
    approved_count = 0
    resolved_count = 0
    deflect_numer = 0
    deflect_denom = 0
    
    for t in threads:
        tid = t.get("thread_id")
        appr = approvals.get(tid)
        ai = rules_summarize(t)
        
        intent = ai.get("intent", "").lower()
        if appr:
            approved_count += 1
            if (appr.get("approved_status") or "").lower().startswith("resolved"):
                resolved_count += 1
                
        # Deflection rate calculation:
        if intent in ("shipping_delay", "general_inquiry"):
            deflect_denom += 1
            status = (appr.get("approved_status") or ai.get("status") or "").lower()
            if status.startswith("resolved"):
                deflect_numer += 1
                
    approval_rate = (approved_count / total) if total else 0.0
    resolved_rate = (resolved_count / total) if total else 0.0
    deflection_rate = (deflect_numer / deflect_denom) if deflect_denom else 0.0
    
    # 8 minutes saved per approved summary based on the new model benchmark
    estimated_time_saved_minutes = approved_count * 8
    
    return jsonify({
        "total_threads": total,
        "approved_count": approved_count,
        "approval_rate": round(approval_rate, 3),
        "resolved_rate": round(resolved_rate, 3),
        "deflection_rate": round(deflection_rate, 3),
        "estimated_time_saved_minutes": estimated_time_saved_minutes,
        "csat_impact": round(approved_count * 0.4, 1) # simple model proxy
    })

# ---------------------------------------------------------------
# ADD THESE TWO ROUTES TO app.py  (paste after the existing routes,
# before the `if __name__ == "__main__":` block)
# ---------------------------------------------------------------

@app.get("/api/check_key")
def api_check_key():
    """Returns whether ANTHROPIC_API_KEY is currently set in the environment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return jsonify({"key_set": bool(key)})

@app.post("/api/set_key")
def api_set_key():
    """
    Accepts an API key from the frontend, writes it to .env,
    and sets it in the current process environment so llm.py picks it up
    immediately without a server restart.
    """
    data = request.get_json(force=True)
    key = (data.get("api_key") or "").strip()

    if not key:
        return jsonify({"ok": False, "error": "Empty key"}), 400

    # Write / overwrite .env file
    env_path = os.path.join(APP_ROOT, ".env")
    try:
        # Preserve any existing lines that aren't ANTHROPIC_API_KEY
        existing_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                existing_lines = [
                    line for line in f.readlines()
                    if not line.startswith("ANTHROPIC_API_KEY")
                ]
        existing_lines.append(f"ANTHROPIC_API_KEY={key}\n")
        with open(env_path, "w") as f:
            f.writelines(existing_lines)
    except OSError as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    # Set in current process environment so llm.py picks it up immediately
    os.environ["ANTHROPIC_API_KEY"] = key

    return jsonify({"ok": True})

if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=8000, debug=True)
