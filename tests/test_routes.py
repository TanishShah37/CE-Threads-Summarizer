import os
import sys
import unittest
import json

# Ensure import path includes project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app, APPROVED_SUMMARIES_PATH


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Backup existing approved summaries if any
        self.backup_path = APPROVED_SUMMARIES_PATH + ".bak"
        if os.path.exists(APPROVED_SUMMARIES_PATH):
            os.rename(APPROVED_SUMMARIES_PATH, self.backup_path)

    def tearDown(self):
        # Remove test approvals and restore backup
        if os.path.exists(APPROVED_SUMMARIES_PATH):
            os.remove(APPROVED_SUMMARIES_PATH)
        if os.path.exists(self.backup_path):
            os.rename(self.backup_path, APPROVED_SUMMARIES_PATH)

    def test_api_threads(self):
        response = self.app.get('/api/threads')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("threads", data)
        self.assertGreater(len(data["threads"]), 0)
        
        # Check basic schema on first thread
        t = data["threads"][0]
        self.assertIn("thread_id", t)
        self.assertIn("customer_name", t)
        self.assertIn("intent", t)
        self.assertIn("sentiment", t)

    def test_api_thread_detail(self):
        # Successful retrieve
        response = self.app.get('/api/threads/CE-405467-683')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("thread", data)
        self.assertIn("messages", data)
        self.assertIn("crm_profile", data)
        self.assertIn("playbook_actions", data)
        self.assertEqual(data["thread"]["thread_id"], "CE-405467-683")

        # 404 retrieve
        response_err = self.app.get('/api/threads/CE-INVALID-ID')
        self.assertEqual(response_err.status_code, 404)

    def test_api_summarize(self):
        response = self.app.post('/api/summarize', 
                                 data=json.dumps({"thread_id": "CE-405467-683", "engine": "rules"}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["engine"], "rules")
        self.assertIn("draft", data)
        self.assertIn("intent", data)
        self.assertIn("sentiment", data)

    def test_api_approve(self):
        payload = {
            "thread_id": "CE-405467-683",
            "approved_summary": "Test approved text",
            "approver": "tester",
            "engine_used": "rules",
            "edit_distance": 12
        }
        response = self.app.post('/api/approve',
                                 data=json.dumps(payload),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["approval"]["approved_summary"], "Test approved text")
        self.assertEqual(data["approval"]["approver"], "tester")

        # Verify it saved to approved_summaries.json
        self.assertTrue(os.path.exists(APPROVED_SUMMARIES_PATH))
        with open(APPROVED_SUMMARIES_PATH, 'r') as f:
            saved = json.load(f)
            self.assertIn("CE-405467-683", saved)
            self.assertEqual(saved["CE-405467-683"]["approved_summary"], "Test approved text")

    def test_api_trigger_action(self):
        payload = {
            "action_type": "Issue Refund (Stripe mock)",
            "thread_id": "CE-405467-683"
        }
        response = self.app.post('/api/trigger_action',
                                 data=json.dumps(payload),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["ok"])
        self.assertIn("Action: Issue Refund (Stripe mock) - SUCCESS", data["log_entry"])

    def test_api_metrics(self):
        # Approve one thread first to register save
        payload = {
            "thread_id": "CE-405467-683",
            "approved_summary": "Resolved item status",
            "approver": "tester"
        }
        self.app.post('/api/approve', data=json.dumps(payload), content_type='application/json')

        response = self.app.get('/api/metrics')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertGreater(data["total_threads"], 0)
        self.assertEqual(data["approved_count"], 1)
        self.assertGreater(data["approval_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
