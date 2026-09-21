import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.models import Session
from app.mvp_flow import (
    record_mvp_session,
    search_and_analyze_best_performance,
    compare_session_with_history,
    generate_personalized_recommendation,
    generate_ai_memory_summary
)

class TestMVPUserFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_session_model_missing_fields(self):
        """
        DATA MODEL REQUIREMENT:
        'Do not require every field.
        The MVP should work even when some data is missing'
        """
        # Empty session works
        empty_session = Session()
        self.assertIsNone(empty_session.session_id)
        self.assertIsNone(empty_session.game)

        # Partially populated session works
        partial_session = Session(
            game="Valorant",
            score="18/10",
            result="Win"
        )
        self.assertEqual(partial_session.game, "Valorant")
        self.assertEqual(partial_session.score, "18/10")
        self.assertIsNone(partial_session.duration)
        self.assertIsNone(partial_session.assists)
        self.assertIsNone(partial_session.kills)

    def test_session_model_full_15_fields(self):
        """
        DATA MODEL REQUIREMENT:
        Create a Session object containing:
        session_id, game, date, duration, score, kills, deaths, assists,
        result, map, configuration, performance_metrics, player_notes,
        ai_summary, ai_insights
        """
        full_session = Session(
            session_id="18",
            game="Valorant",
            date="2026-09-17T20:00:00",
            duration="72 minutes",
            score="18/10",
            kills=18,
            deaths=10,
            assists=6,
            result="Win",
            map="Ascent",
            configuration="Phantom + preferred sensitivity",
            performance_metrics={"kd": 1.8, "acs": 285},
            player_notes="Felt locked in.",
            ai_summary="Strong performance session. Player achieved a 1.8 K/D and won the match while using their preferred configuration.",
            ai_insights=["Preferred sensitivity optimized duel win rate."]
        )
        data = full_session.model_dump()
        self.assertEqual(data["session_id"], "18")
        self.assertEqual(data["game"], "Valorant")
        self.assertEqual(data["date"], "2026-09-17T20:00:00")
        self.assertEqual(data["duration"], "72 minutes")
        self.assertEqual(data["score"], "18/10")
        self.assertEqual(data["kills"], 18)
        self.assertEqual(data["deaths"], 10)
        self.assertEqual(data["assists"], 6)
        self.assertEqual(data["result"], "Win")
        self.assertEqual(data["map"], "Ascent")
        self.assertEqual(data["configuration"], "Phantom + preferred sensitivity")
        self.assertEqual(data["performance_metrics"]["kd"], 1.8)
        self.assertEqual(data["player_notes"], "Felt locked in.")
        self.assertIn("1.8 K/D", data["ai_summary"])
        self.assertEqual(len(data["ai_insights"]), 1)

    def test_step_1_to_4_record_and_generate_summary(self):
        """
        STEPS 1 - 4:
        STEP 1: User completes a gaming session.
        STEP 2: The system records session information.
        STEP 3: AI creates a short memory summary.
        STEP 4: Store the structured session and AI-generated memory.
        """
        session_data = {
            "session_id": "18",
            "game": "Valorant",
            "duration": "72 minutes",
            "score": "18/10",
            "kills": 18,
            "deaths": 10,
            "assists": 6,
            "result": "Win",
            "map": "Ascent",
            "configuration": "Phantom + preferred sensitivity",
            "performance_metrics": {"kd": 1.8}
        }
        
        # Test Step 3: AI creates short memory summary
        summary = generate_ai_memory_summary(session_data)
        expected = "Strong performance session. Player achieved a 1.8 K/D and won the match while using their preferred configuration."
        self.assertEqual(summary, expected)

        # Test Step 4: Record and store session + memory
        res = record_mvp_session(session_data)
        self.assertTrue(res["success"])
        self.assertEqual(res["step"], 4)
        self.assertEqual(res["session_id"], "18")
        self.assertEqual(res["ai_summary"], expected)
        self.assertIsNotNone(res["memory_id"])

    def test_step_5_to_8_when_did_i_perform_best(self):
        """
        STEPS 5 - 8:
        STEP 5: User asks: 'When did I perform best?'
        STEP 6: The system searches previous sessions.
        STEP 7: AI analyzes the retrieved sessions.
        STEP 8: Return an explanation with evidence from the stored sessions.
        """
        query = "When did I perform best?"
        res = search_and_analyze_best_performance(query)
        self.assertEqual(res["step"], 8)
        self.assertEqual(res["best_session_id"], "18")
        
        explanation = res["explanation"]
        # Must cite Session #18, 1.8 K/D, preferred configuration, and 72 minutes
        self.assertIn("Session #18", explanation)
        self.assertIn("1.8 K/D", explanation)
        self.assertIn("preferred configuration", explanation)
        self.assertIn("72 minutes", explanation)

    def test_step_9_what_was_different(self):
        """
        STEP 9:
        User asks: 'What was different?'
        AI compares Session #18 with relevant previous sessions.
        """
        query = "What was different?"
        res = compare_session_with_history(target_session_id="18", query=query)
        self.assertEqual(res["step"], 9)
        self.assertIn("1.8 K/D", res["explanation"])
        self.assertIn("Phantom + preferred sensitivity", res["explanation"])
        self.assertIn("Ascent", res["explanation"])
        self.assertIn("72 minutes", res["explanation"])
        self.assertIn("comparison", res)

    def test_step_10_what_should_i_do_next(self):
        """
        STEP 10:
        User asks: 'What should I do next?'
        AI generates a personalized recommendation based on historical data.
        """
        query = "What should I do next?"
        res = generate_personalized_recommendation(target_session_id="18", query=query)
        self.assertEqual(res["step"], 10)
        self.assertIn("Phantom", res["explanation"])
        self.assertIn("preferred sensitivity", res["explanation"])
        self.assertGreaterEqual(len(res["recommended_actions"]), 2)

    def test_api_mvp_ask_endpoint(self):
        """
        Test POST /api/mvp/ask with the 3 canonical questions
        """
        # Question 1
        r1 = self.client.post("/api/mvp/ask", json={"query": "When did I perform best?"})
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        self.assertIn("Session #18", data1["explanation"])
        self.assertIn("1.8 K/D", data1["explanation"])

        # Question 2
        r2 = self.client.post("/api/mvp/ask", json={"query": "What was different?"})
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertIn("Session #18", data2["explanation"])

        # Question 3
        r3 = self.client.post("/api/mvp/ask", json={"query": "What should I do next?"})
        self.assertEqual(r3.status_code, 200)
        data3 = r3.json()
        self.assertIn("Phantom", data3["explanation"])

    def test_api_mvp_demo_endpoint(self):
        """
        Test GET /api/mvp/demo returns all 10 steps end-to-end
        """
        response = self.client.get("/api/mvp/demo")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        steps = data["steps"]
        self.assertIn("step_1_user_completes_session", steps)
        self.assertIn("step_2_recorded_session", steps)
        self.assertIn("step_3_ai_memory_summary", steps)
        self.assertIn("step_4_stored_session_and_memory", steps)
        self.assertIn("step_5_user_query", steps)
        self.assertIn("step_6_system_searches_sessions", steps)
        self.assertIn("step_7_ai_analyzes_sessions", steps)
        self.assertIn("step_8_explanation_with_evidence", steps)
        self.assertIn("step_9_what_was_different", steps)
        self.assertIn("step_10_what_should_i_do_next", steps)

if __name__ == "__main__":
    unittest.main()
