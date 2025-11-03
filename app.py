import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser
from flask import Flask, jsonify, render_template, request, Response
import io
import csv


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_ROOT, "data")
STATIC_DIR = os.path.join(APP_ROOT, "static")
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")

DATASET_PATH = os.path.join(DATA_DIR, "ce_exercise_threads.json")
APPROVALS_PATH = os.path.join(DATA_DIR, "approvals.json")
EXPORT_PATH = os.path.join(DATA_DIR, "approved_export.json")
CRM_PATH = os.path.join(DATA_DIR, "crm.json")


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
    # Minimal normalization for consistent downstream use
    messages = raw.get("messages", [])
    # Sort by timestamp if parseable
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


def infer_intent_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["damaged", "broken", "defective"]):
        return "Damaged/Defective item"
    if any(k in t for k in ["late", "delayed", "where is", "tracking"]):
        return "Delivery delay / tracking"
    if any(k in t for k in ["wrong", "color", "size", "variant"]):
        return "Wrong variant received"
    if any(k in t for k in ["return", "refund"]):
        return "Return/Refund request"
    if any(k in t for k in ["address", "confirm address"]):
        return "Address confirmation"
    return "General inquiry"


def infer_requested_action_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "refund" in t:
        return "Refund"
    if any(k in t for k in ["replace", "replacement"]):
        return "Replacement"
    if "return" in t:
        return "Return"
    if "address" in t and any(k in t for k in ["confirm", "confirmation"]):
        return "Confirm address"
    return None


def infer_status_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["resolved", "approved", "approve"]):
        return "Resolved/Approved"
    if any(k in t for k in ["pending", "awaiting", "need", "confirm"]):
        return "Pending - Awaiting customer/company action"
    if any(k in t for k in ["reroute", "replacement", "refund", "return"]):
        return "In progress"
    return "Open"


def simple_rules_summary(thread: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lightweight rules-based summarizer tailored to CE threads structure.
    Produces a structured summary useful to associates.
    """
    order_id = thread.get("order_id")
    product = thread.get("product")
    subject = thread.get("subject") or ""
    topic = thread.get("topic") or ""
    messages: List[Dict[str, Any]] = thread.get("messages", [])

    # First customer message often contains core issue
    first_customer: Optional[Dict[str, Any]] = next(
        (m for m in messages if m.get("sender") == "customer"), None
    )
    last_company: Optional[Dict[str, Any]] = next(
        (m for m in reversed(messages) if m.get("sender") == "company"), None
    )

    # use top-level helpers for reusability

    customer_text = (first_customer or {}).get("body", "")
    company_text = (last_company or {}).get("body", "")

    intent = infer_intent_from_text(" ".join([topic, subject, customer_text]))
    requested_action = infer_requested_action_from_text(customer_text)

    # Status heuristic
    status = infer_status_from_text(company_text)

    # Next step suggestion
    next_steps: List[str] = []
    if intent == "Damaged/Defective item":
        next_steps.append("Request photos if not provided; offer refund or replacement")
    if intent == "Wrong variant received":
        next_steps.append("Offer prepaid return label and correct replacement shipment")
    if intent == "Delivery delay / tracking":
        next_steps.append("Provide tracking status; escalate to carrier if >48h stalled")
    if intent == "Return/Refund request":
        next_steps.append("Initiate RMA and inform refund timeline (3–5 business days)")
    if intent == "Address confirmation":
        next_steps.append("Confirm full address and hold shipment until verified")
    if not next_steps:
        next_steps.append("Clarify issue and propose resolution options")

    # SLA by intent (business rule)
    sla_hours_map = {
        "Damaged/Defective item": 24,
        "Wrong variant received": 24,
        "Delivery delay / tracking": 12,
        "Return/Refund request": 24,
        "Address confirmation": 6,
        "General inquiry": 24,
    }

    # Base CRM context; may be overridden by CRM join
    crm_context = {
        "customer_tier": "Standard",
        "sla_hours": sla_hours_map.get(intent, 24),
        "entitlements": [],
        "shipping_constraints": [],
        "customer_id": None,
    }

    bullets = [
        f"Order: {order_id}",
        f"Product: {product}",
        f"Intent: {intent}",
        f"Customer requested: {requested_action or 'Unclear'}",
        f"Status: {status}",
    ]

    summary_text = "\n".join(["- " + b for b in bullets] + [
        "- Next steps: " + "; ".join(next_steps)
    ])

    return {
        "order_id": order_id,
        "product": product,
        "intent": intent,
        "requested_action": requested_action,
        "status": status,
        "next_steps": next_steps,
        "crm_context": crm_context,
        "summary_markdown": summary_text,
    }


def load_threads_with_summaries() -> List[Dict[str, Any]]:
    raw = load_json(DATASET_PATH, default={"threads": []})
    threads = [normalize_thread(t) for t in raw.get("threads", [])]
    crm = load_json(CRM_PATH, default={"customers": []})
    order_to_crm: Dict[str, Dict[str, Any]] = {}
    for c in crm.get("customers", []):
        for oid in c.get("orders", []):
            order_to_crm[oid] = c
    enriched: List[Dict[str, Any]] = []
    for t in threads:
        ai = simple_rules_summary(t)
        # join CRM by order_id if available
        crm_row = order_to_crm.get(t.get("order_id"))
        if crm_row:
            ai_ctx = ai.get("crm_context", {})
            ai_ctx.update({
                "customer_tier": crm_row.get("tier", ai_ctx.get("customer_tier")),
                "entitlements": crm_row.get("entitlements", []),
                "shipping_constraints": crm_row.get("shipping_constraints", []),
                "customer_id": crm_row.get("customer_id"),
            })
            ai["crm_context"] = ai_ctx
        enriched.append({**t, "ai_summary": ai})
    return enriched


def persist_approval(thread_id: str, approved_summary: str, approver: str) -> Dict[str, Any]:
    approvals = load_json(APPROVALS_PATH, default={})
    # Derive approved intent/status from the approved summary text
    approved_intent = infer_intent_from_text(approved_summary)
    approved_status = infer_status_from_text(approved_summary)

    approvals[thread_id] = {
        "approved_summary": approved_summary,
        "approver": approver,
        "approved_at": datetime.utcnow().isoformat() + "Z",
        "approved_intent": approved_intent,
        "approved_status": approved_status,
    }
    save_json(APPROVALS_PATH, approvals)
    # Also write/export a denormalized view for associates
    export_records: List[Dict[str, Any]] = []
    threads = load_threads_with_summaries()
    for t in threads:
        tid = t.get("thread_id")
        ai = t.get("ai_summary", {})
        appr = approvals.get(tid, {})
        rec = {
            "thread_id": tid,
            "order_id": t.get("order_id"),
            "product": t.get("product"),
            "intent": ai.get("intent"),
            "status": ai.get("status"),
            "approved_summary": appr.get("approved_summary"),
            "approved_intent": appr.get("approved_intent"),
            "approved_status": appr.get("approved_status"),
            "customer_id": ai.get("crm_context", {}).get("customer_id"),
            "customer_tier": ai.get("crm_context", {}).get("customer_tier"),
            "entitlements": ai.get("crm_context", {}).get("entitlements"),
            "shipping_constraints": ai.get("crm_context", {}).get("shipping_constraints"),
        }
        export_records.append(rec)
    save_json(EXPORT_PATH, export_records)
    return approvals[thread_id]


app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_DIR)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/threads")
def api_threads():
    threads = load_threads_with_summaries()
    approvals = load_json(APPROVALS_PATH, default={})
    for t in threads:
        tid = t.get("thread_id")
        t["approval"] = approvals.get(tid)
    return jsonify({"threads": threads})


@app.post("/api/approve")
def api_approve():
    data = request.get_json(force=True)
    thread_id = data.get("thread_id")
    approved_summary = data.get("approved_summary")
    approver = data.get("approver") or "ce_associate"
    if not thread_id or not approved_summary:
        return jsonify({"error": "thread_id and approved_summary are required"}), 400
    record = persist_approval(thread_id, approved_summary, approver)
    return jsonify({"ok": True, "approval": record})


 


# Export endpoints
@app.get("/export/json")
def export_json():
    ensure_dirs()
    # Ensure export exists; regenerate from current approvals/threads if needed
    approvals = load_json(APPROVALS_PATH, default={})
    threads = load_threads_with_summaries()
    export_records: List[Dict[str, Any]] = []
    for t in threads:
        tid = t.get("thread_id")
        ai = t.get("ai_summary", {})
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
        })
    payload = json.dumps(export_records, ensure_ascii=False, indent=2)
    return Response(payload, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=approved_export.json"})


@app.get("/export/csv")
def export_csv():
    ensure_dirs()
    approvals = load_json(APPROVALS_PATH, default={})
    threads = load_threads_with_summaries()
    output = io.StringIO()
    writer = csv.writer(output)
    header = [
        "thread_id", "order_id", "product",
        "intent", "status", "approved_summary", "approved_intent", "approved_status",
        "customer_id", "customer_tier", "entitlements", "shipping_constraints",
    ]
    writer.writerow(header)
    for t in threads:
        tid = t.get("thread_id")
        ai = t.get("ai_summary", {})
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
            ai.get("crm_context", {}).get("customer_id"),
            ai.get("crm_context", {}).get("customer_tier"),
            ";".join(ai.get("crm_context", {}).get("entitlements", []) or []),
            ";".join(ai.get("crm_context", {}).get("shipping_constraints", []) or []),
        ]
        writer.writerow(row)
    data = output.getvalue()
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=approved_export.csv"})


@app.get("/api/metrics")
def api_metrics():
    threads = load_threads_with_summaries()
    approvals = load_json(APPROVALS_PATH, default={})
    total = len(threads)
    approved_count = 0
    resolved_count = 0
    deflect_numer = 0
    deflect_denom = 0
    for t in threads:
        tid = t.get("thread_id")
        appr = approvals.get(tid)
        if appr:
            approved_count += 1
            if (appr.get("approved_status") or "").lower().startswith("resolved"):
                resolved_count += 1
        # deflection proxy: intents typically handled without escalation (delivery/address)
        intent = (t.get("ai_summary", {}).get("intent") or "").lower()
        if intent in ("delivery delay / tracking".lower(), "address confirmation".lower()):
            deflect_denom += 1
            st = (approvals.get(tid, {}).get("approved_status") or t.get("ai_summary", {}).get("status") or "").lower()
            if st.startswith("resolved"):
                deflect_numer += 1

    approval_rate = (approved_count / total) if total else 0.0
    resolved_rate = (resolved_count / total) if total else 0.0
    deflection_rate = (deflect_numer / deflect_denom) if deflect_denom else 0.0
    # crude time-saved estimate: 4 minutes saved per approved summary
    estimated_time_saved_minutes = approved_count * 4
    return jsonify({
        "total_threads": total,
        "approved_count": approved_count,
        "approval_rate": round(approval_rate, 3),
        "resolved_rate": round(resolved_rate, 3),
        "deflection_rate": round(deflection_rate, 3),
        "estimated_time_saved_minutes": estimated_time_saved_minutes,
        "csat_impact": None,
        "notes": "Deflection proxy uses intents: delivery/address; time-saved assumes 4m per approval.",
    })


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=8000, debug=True)

