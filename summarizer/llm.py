import os
import json
from typing import Any, Dict, Optional
from anthropic import Anthropic
from summarizer.mock_responses import MOCK_LLM_RESPONSES
from summarizer.rules import rules_summarize

# Try to load from dotenv if it's installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def llm_summarize(thread: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tier 2 Generative AI Summarizer.
    Calls Anthropic API or falls back to mock responses.
    """
    thread_id = thread.get("thread_id")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # 1. Fallback check: if API key is missing, use mock responses
    if not api_key:
        return get_mock_or_rule_fallback(thread, is_mock_label=True)

    try:
        client = Anthropic(api_key=api_key)
        
        # Prepare content
        messages_str = ""
        for m in thread.get("messages", []):
            messages_str += f"{m.get('sender').upper()} ({m.get('timestamp')}):\n{m.get('body')}\n\n"
            
        prompt = (
            f"Topic: {thread.get('topic')}\n"
            f"Subject: {thread.get('subject')}\n"
            f"Order ID: {thread.get('order_id')}\n"
            f"Product: {thread.get('product')}\n\n"
            f"Email Thread:\n{messages_str}"
        )
        
        system_prompt = (
            "You are a customer experience assistant. Analyze the given customer email thread and return a valid JSON object ONLY. "
            "Do not wrap the response in markdown code blocks like ```json ... ``` or write any introductory or concluding text. "
            "JSON structure:\n"
            "{\n"
            "  \"intent\": \"refund_request\" | \"replacement_order\" | \"shipping_delay\" | \"billing_dispute\" | \"technical_issue\" | \"general_inquiry\",\n"
            "  \"sentiment\": \"positive\" | \"neutral\" | \"negative\" | \"escalated\",\n"
            "  \"root_cause\": \"brief summary of root cause (max 180 tokens)\",\n"
            "  \"resolution_plan\": \"brief summary of proposed resolution plan\",\n"
            "  \"recommended_actions\": [\"action 1\", \"action 2\"],\n"
            "  \"risk_flag\": true | false,\n"
            "  \"entities\": {\n"
            "    \"order_id\": \"extracted order id or null\",\n"
            "    \"tracking_number\": \"extracted tracking number or null\",\n"
            "    \"amount\": \"extracted dollar amount or null\"\n"
            "  }\n"
            "}\n"
            "Constraints:\n"
            "- Never fabricate order IDs or amounts not present in the thread.\n"
            "- Return ONLY raw valid JSON."
        )

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022", # robust model string
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        text_content = response.content[0].text.strip()
        
        # Clean up any potential markdown wraps
        if text_content.startswith("```"):
            lines = text_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            text_content = "\n".join(lines).strip()
            
        data = json.loads(text_content)
        return format_llm_response(thread, data, is_mock=False)
        
    except Exception as e:
        # Fallback to mock on any api/network failure
        return get_mock_or_rule_fallback(thread, is_mock_label=True)

def format_llm_response(thread: Dict[str, Any], data: Dict[str, Any], is_mock: bool) -> Dict[str, Any]:
    intent = data.get("intent", "general_inquiry")
    sentiment = data.get("sentiment", "neutral")
    root_cause = data.get("root_cause", "")
    resolution_plan = data.get("resolution_plan", "")
    recommended_actions = data.get("recommended_actions", [])
    entities = data.get("entities", {})
    
    order_id = entities.get("order_id") or thread.get("order_id") or "None"
    tracking = entities.get("tracking_number") or "None"
    amount = entities.get("amount") or "None"
    
    label = " [Mock LLM — no API key]" if is_mock else " [Generative AI]"
    
    summary_markdown = (
        f"**Intent:** {intent.replace('_', ' ').title()}{label}\n"
        f"**Customer Sentiment:** {sentiment.title()}\n"
        f"**Root Cause:** {root_cause}\n"
        f"**Current Status:** {resolution_plan}\n"
        f"**Recommended Action:** {'; '.join(recommended_actions)}\n"
        f"**Key Entities:** Order #{order_id} | {amount} | Tracking: {tracking}"
    )
    
    sla_hours_map = {
        "refund_request": 24,
        "replacement_order": 24,
        "shipping_delay": 12,
        "billing_dispute": 24,
        "technical_issue": 24,
        "general_inquiry": 24,
    }
    
    # Enrich CRM context (will be updated by crm.json join in app.py)
    crm_context = {
        "customer_tier": "Standard",
        "sla_hours": sla_hours_map.get(intent, 24),
        "entitlements": [],
        "shipping_constraints": [],
        "customer_id": None,
    }
    
    return {
        "order_id": thread.get("order_id"),
        "product": thread.get("product"),
        "intent": intent,
        "sentiment": sentiment,
        "requested_action": resolution_plan,
        "status": "In progress" if data.get("risk_flag") else "Open",
        "next_steps": recommended_actions,
        "crm_context": crm_context,
        "summary_markdown": summary_markdown,
        "engine": "llm"
    }

def get_mock_or_rule_fallback(thread: Dict[str, Any], is_mock_label: bool) -> Dict[str, Any]:
    thread_id = thread.get("thread_id")
    if thread_id in MOCK_LLM_RESPONSES:
        mock_data = MOCK_LLM_RESPONSES[thread_id]
        return format_llm_response(thread, mock_data, is_mock=is_mock_label)
    
    # If no mock response for this custom thread, fall back to rules summarizer but flag it as mock LLM
    rules_res = rules_summarize(thread)
    if is_mock_label:
        rules_res["summary_markdown"] = rules_res["summary_markdown"].replace(
            "**Intent:**", "**Intent:** [Mock LLM — no API key]"
        )
    return rules_res
