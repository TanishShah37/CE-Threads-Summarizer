MOCK_LLM_RESPONSES = {
    "CE-405467-683": {
        "intent": "refund_request",
        "sentiment": "escalated",
        "root_cause": "Customer received a damaged LED Monitor (Order #405467-683). The carrier packaging was broken on arrival.",
        "resolution_plan": "Verify the item status with customer-provided photos and approve a full refund or replacement.",
        "recommended_actions": [
            "Issue Refund (Stripe mock)",
            "Log Refund Note"
        ],
        "risk_flag": True,
        "entities": {
            "order_id": "405467-683",
            "product": "LED Monitor"
        }
    },
    "CE-681480-462": {
        "intent": "shipping_delay",
        "sentiment": "negative",
        "root_cause": "The shipment for Order #681480-462 (LED Monitor) is delayed with no recent carrier tracking updates.",
        "resolution_plan": "Initiate a carrier trace request and update the customer with the expected delivery window.",
        "recommended_actions": [
            "Request Carrier Update",
            "Escalate to Tier 2"
        ],
        "risk_flag": False,
        "entities": {
            "order_id": "681480-462",
            "product": "LED Monitor"
        }
    },
    "CE-762448-617": {
        "intent": "replacement_order",
        "sentiment": "negative",
        "root_cause": "Customer received an incorrect variant (color/size) of the Vacuum Cleaner for Order #762448-617.",
        "resolution_plan": "Issue a prepaid return shipping label and create a replacement order in the Shopify CRM system.",
        "recommended_actions": [
            "Trigger Replacement (Shopify mock)",
            "Generate Label"
        ],
        "risk_flag": False,
        "entities": {
            "order_id": "762448-617",
            "product": "Vacuum Cleaner"
        }
    },
    "CE-627506-327": {
        "intent": "refund_request",
        "sentiment": "neutral",
        "root_cause": "Customer is requesting a return and refund for the Headphones (Order #627506-327).",
        "resolution_plan": "Provide return instructions, verify returns conditions, and issue refund within 3-5 business days.",
        "recommended_actions": [
            "Issue Refund (Stripe mock)",
            "Log Refund Note"
        ],
        "risk_flag": False,
        "entities": {
            "order_id": "627506-327",
            "product": "Headphones"
        }
    },
    "CE-928163-566": {
        "intent": "general_inquiry",
        "sentiment": "neutral",
        "root_cause": "Outbound address confirmation thread where customer is confused about the address registered on file for Order #928163-566.",
        "resolution_plan": "Send address validation template and confirm details to release shipping hold.",
        "recommended_actions": [
            "Send Template Reply",
            "Log Inquiry Note"
        ],
        "risk_flag": True,
        "entities": {
            "order_id": "928163-566",
            "product": "Vacuum Cleaner"
        }
    }
}
