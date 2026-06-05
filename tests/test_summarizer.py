import os
import sys
import unittest

# Ensure import path includes project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from summarizer.rules import (
    infer_intent_from_text,
    infer_status_from_text,
    infer_sentiment_from_text,
    rules_summarize,
)
from summarizer.llm import llm_summarize


class TestSummarizer(unittest.TestCase):
    def test_infer_intent(self):
        self.assertEqual(infer_intent_from_text("Item arrived damaged"), "refund_request")
        self.assertEqual(infer_intent_from_text("Shipment is delayed; where is tracking"), "shipping_delay")
        self.assertEqual(infer_intent_from_text("Wrong color/size variant"), "replacement_order")
        self.assertEqual(infer_intent_from_text("I want a refund"), "refund_request")
        self.assertEqual(infer_intent_from_text("Please invoice confirmation"), "billing_dispute")

    def test_infer_sentiment(self):
        self.assertEqual(infer_sentiment_from_text("This is urgent, get me the manager!"), "escalated")
        self.assertEqual(infer_sentiment_from_text("My order is late, wrong item"), "negative")
        self.assertEqual(infer_sentiment_from_text("Thank you for the great service"), "positive")
        self.assertEqual(infer_sentiment_from_text("Please confirm my shipping address"), "neutral")

    def test_infer_status(self):
        self.assertEqual(infer_status_from_text("case resolved and approved"), "Resolved/Approved")
        self.assertEqual(infer_status_from_text("pending confirmation from customer"), "Pending - Awaiting customer/company action")
        self.assertEqual(infer_status_from_text("processing replacement"), "In progress")
        self.assertEqual(infer_status_from_text("no updates"), "Open")

    def test_rules_summary(self):
        thread = {
            "thread_id": "X-1",
            "topic": "Damaged product on arrival",
            "subject": "Order X-1: Damaged item",
            "initiated_by": "customer",
            "order_id": "X-1",
            "product": "Widget",
            "messages": [
                {"id": "m1", "sender": "customer", "timestamp": "2025-01-01T00:00:00", "body": "Arrived damaged please refund"},
                {"id": "m2", "sender": "company", "timestamp": "2025-01-01T00:10:00", "body": "pending photos"},
            ],
        }
        s = rules_summarize(thread)
        self.assertEqual(s["intent"], "refund_request")
        self.assertEqual(s["sentiment"], "negative")
        self.assertIn("Intent:", s["summary_markdown"])
        self.assertIn("Customer Sentiment:", s["summary_markdown"])

    def test_llm_fallback_summary(self):
        thread = {
            "thread_id": "CE-405467-683",
            "topic": "Damaged product on arrival",
            "subject": "Order 405467-683: Damaged item received",
            "initiated_by": "customer",
            "order_id": "405467-683",
            "product": "LED Monitor",
            "messages": [
                {"id": "m1", "sender": "customer", "timestamp": "2025-01-01T00:00:00", "body": "Arrived damaged please refund"}
            ]
        }
        # Since ANTHROPIC_API_KEY is not set in test environment, it should use high fidelity fallback
        s = llm_summarize(thread)
        self.assertEqual(s["intent"], "refund_request")
        self.assertEqual(s["sentiment"], "escalated")
        self.assertIn("[Mock LLM — no API key]", s["summary_markdown"])


if __name__ == "__main__":
    unittest.main()
