import os
import sys
import unittest

# Ensure import path includes project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import (
    infer_intent_from_text,
    infer_status_from_text,
    simple_rules_summary,
)


class TestSummarizer(unittest.TestCase):
    def test_infer_intent(self):
        self.assertEqual(infer_intent_from_text("Item arrived damaged"), "Damaged/Defective item")
        self.assertEqual(infer_intent_from_text("Shipment is delayed; where is tracking"), "Delivery delay / tracking")
        self.assertEqual(infer_intent_from_text("Wrong color/size variant"), "Wrong variant received")
        self.assertEqual(infer_intent_from_text("I want a refund"), "Return/Refund request")
        self.assertEqual(infer_intent_from_text("Please confirm address"), "Address confirmation")

    def test_infer_status(self):
        self.assertEqual(infer_status_from_text("case resolved and approved"), "Resolved/Approved")
        self.assertEqual(infer_status_from_text("pending confirmation from customer"), "Pending - Awaiting customer/company action")
        self.assertEqual(infer_status_from_text("processing replacement"), "In progress")
        self.assertEqual(infer_status_from_text("no updates"), "Open")

    def test_simple_rules_summary(self):
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
        s = simple_rules_summary(thread)
        self.assertEqual(s["intent"], "Damaged/Defective item")
        self.assertIn("Next steps", s["summary_markdown"]) 


if __name__ == "__main__":
    unittest.main()


