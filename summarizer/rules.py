import re
from typing import Any, Dict, List, Optional

def infer_intent_from_text(text: str) -> str:
    t = (text or "").lower()
    # Taxonomy: ["refund_request", "replacement_order", "shipping_delay", "billing_dispute", "technical_issue", "general_inquiry"]
    if any(k in t for k in ["refund", "return", "money back", "credit", "damaged", "broken", "defective"]):
        return "refund_request"
    if any(k in t for k in ["replace", "replacement", "exchange", "wrong", "color", "size", "variant"]):
        return "replacement_order"
    if any(k in t for k in ["late", "delayed", "where is", "tracking", "delivery", "shipment", "carrier", "stuck"]):
        return "shipping_delay"
    if any(k in t for k in ["bill", "billing", "invoice", "charge", "charged", "payment", "dispute", "price"]):
        return "billing_dispute"
    if any(k in t for k in ["error", "fail", "failed", "bug", "glitch", "technical"]):
        return "technical_issue"
    return "general_inquiry"

def infer_sentiment_from_text(text: str) -> str:
    t = (text or "").lower()
    # Sentiment options: positive, neutral, negative, escalated
    if any(k in t for k in ["urgent", "escalate", "manager", "supervisor", "terrible", "awful", "fraud", "worst", "unacceptable"]):
        return "escalated"
    if any(k in t for k in ["delay", "broken", "wrong", "disappointed", "poor", "issue", "late", "slow", "sorry", "decline", "damaged", "defective"]):
        return "negative"
    if any(k in t for k in ["thank", "thanks", "great", "good", "perfect", "happy", "appreciate", "love"]):
        return "positive"
    return "neutral"

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
    if any(k in t for k in ["resolved", "approved", "approve", "done"]):
        return "Resolved/Approved"
    if any(k in t for k in ["pending", "awaiting", "need", "confirm", "question"]):
        return "Pending - Awaiting customer/company action"
    if any(k in t for k in ["reroute", "replacement", "refund", "return", "processing"]):
        return "In progress"
    return "Open"

def extract_entities_from_text(text: str) -> Dict[str, List[str]]:
    # Simple regex extraction for Order IDs, tracking numbers, and amounts
    order_ids = re.findall(r'#\d{5,}|\b\d{5,}-\d{3,}\b|\b\d{6,}\b', text)
    tracking_nums = re.findall(r'\b\d{12,}\b|\b(?:9400\d{18})\b', text)
    amounts = re.findall(r'\$\d+(?:\.\d{2})?', text)
    
    return {
        "order_ids": list(set(order_ids)),
        "tracking_numbers": list(set(tracking_nums)),
        "amounts": list(set(amounts))
    }

def rules_summarize(thread: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tier 1 Rules-based summarizer.
    Produces a structured summary with Markdown template.
    """
    thread_id = thread.get("thread_id")
    order_id = thread.get("order_id") or ""
    product = thread.get("product") or "Unknown Product"
    subject = thread.get("subject") or ""
    topic = thread.get("topic") or ""
    messages: List[Dict[str, Any]] = thread.get("messages", [])

    # Concatenate message texts to infer fields
    customer_messages = [m.get("body", "") for m in messages if m.get("sender") == "customer"]
    company_messages = [m.get("body", "") for m in messages if m.get("sender") == "company"]
    all_text = " ".join([topic, subject] + [m.get("body", "") for m in messages])

    intent = infer_intent_from_text(all_text)
    sentiment = infer_sentiment_from_text(all_text)
    requested_action = infer_requested_action_from_text(" ".join(customer_messages))
    status = infer_status_from_text(" ".join(company_messages) if company_messages else "")

    # Next steps suggestion
    next_steps: List[str] = []
    if intent == "refund_request":
        next_steps.append("Initiate return validation; process Stripe refund if requirements met")
    elif intent == "replacement_order":
        next_steps.append("Create replacement order in CRM; generate shipping label")
    elif intent == "shipping_delay":
        next_steps.append("Request carrier tracking update; notify client of delivery window")
    elif intent == "billing_dispute":
        next_steps.append("Verify payment records; forward to billing department if needed")
    elif intent == "technical_issue":
        next_steps.append("Escalate technical details to Tier 2 support team")
    else:
        next_steps.append("Clarify customer requirements and reply within SLA")

    # SLA based on intent
    sla_hours_map = {
        "refund_request": 24,
        "replacement_order": 24,
        "shipping_delay": 12,
        "billing_dispute": 24,
        "technical_issue": 24,
        "general_inquiry": 24,
    }

    crm_context = {
        "customer_tier": "Standard",
        "sla_hours": sla_hours_map.get(intent, 24),
        "entitlements": [],
        "shipping_constraints": [],
        "customer_id": None,
    }

    # Extract entities
    entities = extract_entities_from_text(all_text)
    order_str = f"Order #{order_id}" if order_id else "None"
    prod_str = product
    track_str = entities["tracking_numbers"][0] if entities["tracking_numbers"] else "None"
    amt_str = entities["amounts"][0] if entities["amounts"] else "None"
    
    # Generate the requested Markdown template
    summary_markdown = (
        f"**Intent:** {intent.replace('_', ' ').title()}\n"
        f"**Customer Sentiment:** {sentiment.title()}\n"
        f"**Root Cause:** Order {order_str} ({prod_str}) reported with {intent.replace('_', ' ')}.\n"
        f"**Current Status:** {status}. Customer request action: {requested_action or 'Review'}.\n"
        f"**Recommended Action:** {'; '.join(next_steps)}.\n"
        f"**Key Entities:** {order_str} | {amt_str} | Tracking: {track_str}"
    )

    return {
        "order_id": order_id,
        "product": product,
        "intent": intent,
        "sentiment": sentiment,
        "requested_action": requested_action,
        "status": status,
        "next_steps": next_steps,
        "crm_context": crm_context,
        "summary_markdown": summary_markdown,
    }
