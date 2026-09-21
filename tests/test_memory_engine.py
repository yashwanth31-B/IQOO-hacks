import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

class TestGamingSecondBrain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_status_endpoint(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("active_engine", data)
        self.assertIn("analytics", data)
        self.assertGreaterEqual(data["analytics"]["total_sessions"], 1)

    def test_sessions_list(self):
        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        sessions = response.json()
        self.assertIsInstance(sessions, list)
        self.assertGreaterEqual(len(sessions), 1)

    def test_memories_list(self):
        response = self.client.get("/api/memories")
        self.assertEqual(response.status_code, 200)
        memories = response.json()
        self.assertIsInstance(memories, list)
        self.assertGreaterEqual(len(memories), 1)

    def test_semantic_search_haven(self):
        response = self.client.post("/api/search", json={"query": "Why do I keep losing on Haven C site?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ai_synthesized_answer", data)
        self.assertIn("key_takeaway", data)
        self.assertGreaterEqual(len(data["results"]), 1)
        self.assertTrue(any("Haven" in r["title"] or "C Long" in r["snippet"] for r in data["results"]))

    def test_semantic_search_tilt(self):
        response = self.client.post("/api/search", json={"query": "When do I tilt the most?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Tilt", data["ai_synthesized_answer"])

    def test_cross_session_patterns(self):
        response = self.client.get("/api/patterns")
        self.assertEqual(response.status_code, 200)
        patterns = response.json()
        self.assertIsInstance(patterns, list)
        # Should have found the Haven C long weakness and late night fatigue cliff
        titles = [p["title"] for p in patterns]
        self.assertTrue(any("Haven C Long" in t for t in titles))
        self.assertTrue(any("11:00 PM" in t for t in titles))

    def test_pre_match_briefing(self):
        response = self.client.post("/api/copilot/briefing", json={"game": "Valorant", "map_or_boss": "Haven"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["game"], "Valorant")
        self.assertIn("Haven", data["target"])
        self.assertIn("primary_threat", data)
        self.assertGreaterEqual(len(data["key_rules_to_win"]), 2)

    def test_copilot_chat(self):
        response = self.client.post("/api/copilot/chat", json={"message": "Why do I throw on Haven?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("relevant_memories_used", data)
        self.assertGreaterEqual(len(data["relevant_memories_used"]), 1)

    def test_live_simulation(self):
        response = self.client.post("/api/sessions/simulate", json={"scenario": "valorant_haven_choke"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("session", data)
        self.assertGreaterEqual(len(data["memory_ids"]), 1)

    def test_serve_frontend(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Gaming Second Brain", response.content)

if __name__ == "__main__":
    unittest.main()
