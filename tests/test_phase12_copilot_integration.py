import os
import sys
import unittest
import tempfile
import sqlite3
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.models import Session
from app.session_storage import SessionStorage
from app.player_profile import PlayerProfileManager
from app.cross_session_analyzer import CrossSessionAnalyzer
from app.gaming_plan_engine import GamingPlanEngine
from app.natural_language_search import NaturalLanguageSearchEngine
from app.copilot import (
    SecondBrainCopilotConnector,
    handle_copilot_chat,
    NOT_ENOUGH_DATA
)


class TestPhase12CopilotIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create isolated temporary database for test determinism
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = os.path.join(cls.temp_dir.name, "test_copilot_phase12.db")
        cls.storage = SessionStorage(db_path=cls.test_db_path)
        cls.profile_mgr = PlayerProfileManager(storage=cls.storage)
        cls.analyzer = CrossSessionAnalyzer(storage=cls.storage)
        cls.plan_engine = GamingPlanEngine(
            storage=cls.storage,
            profile_manager=cls.profile_mgr,
            cross_session_analyzer=cls.analyzer
        )
        cls.nl_search = NaturalLanguageSearchEngine(storage=cls.storage)

        cls.connector = SecondBrainCopilotConnector(
            storage=cls.storage,
            profile_manager=cls.profile_mgr,
            cross_session_analyzer=cls.analyzer,
            gaming_plan_engine=cls.plan_engine,
            nl_search_engine=cls.nl_search
        )

        # Seed test sessions: Session 14 (low performance) and Session 18 (peak performance)
        cls.session_14 = Session(
            session_id="14",
            game="Valorant",
            game_mode="Competitive",
            map="Haven",
            configuration={"primary_weapon": "Vandal", "loadout": "Vandal standard"},
            started_at="2026-09-16T22:30:00",
            duration=60,
            score="10/13",
            kills=11,
            deaths=10,
            assists=4,
            kd_ratio=1.10,
            result="Defeat",
            player_notes="Kept dry peeking C Long into Operator."
        )

        cls.session_18 = Session(
            session_id="18",
            game="Valorant",
            game_mode="Competitive",
            map="Ascent",
            configuration={"primary_weapon": "Phantom", "loadout": "Phantom + preferred sensitivity"},
            started_at="2026-09-17T20:00:00",
            duration=72,
            score="18/10",
            kills=18,
            deaths=10,
            assists=6,
            kd_ratio=1.80,
            result="Win",
            player_notes="Disciplined crosshair placement and patient site anchors."
        )

        cls.storage.create_session(cls.session_14)
        cls.storage.create_session(cls.session_18)

        # Create active plan based on these sessions
        cls.active_plan = cls.plan_engine.create_plan(
            game="Valorant",
            sessions=[cls.session_14, cls.session_18]
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    # -----------------------------------------------------------------
    # 1. REQUIRED QUERY: "What was my best session?"
    # -----------------------------------------------------------------
    def test_query_1_what_was_my_best_session(self):
        res = self.connector.handle_query("What was my best session?")

        # Must contain all 4 sections
        reply = res["reply"]
        self.assertIn("ANSWER:", reply)
        self.assertIn("EVIDENCE:", reply)
        self.assertIn("INSIGHT:", reply)
        self.assertIn("RECOMMENDATION:", reply)

        # Must cite real stored evidence
        self.assertIn("18", res["evidence_session_ids"])
        self.assertIn("1.80", reply)
        self.assertIn("Ascent", reply)
        self.assertIn("Phantom", reply)

        # Verify individual structured fields
        self.assertEqual(res["evidence_session_ids"], ["18"])
        self.assertIn("Session #18", res["answer"])
        self.assertIn("18 kills", res["evidence"])
        self.assertIn("peak combat efficiency", res["insight"].lower())
        self.assertIn("replicate", res["recommendation"].lower())

    # -----------------------------------------------------------------
    # 2. REQUIRED QUERY: "What changed?"
    # -----------------------------------------------------------------
    def test_query_2_what_changed(self):
        res = self.connector.handle_query("What changed?")

        # Must contain all 4 sections
        reply = res["reply"]
        self.assertIn("ANSWER:", reply)
        self.assertIn("EVIDENCE:", reply)
        self.assertIn("INSIGHT:", reply)
        self.assertIn("RECOMMENDATION:", reply)

        # Must cite both best (18) and worst (14) sessions
        self.assertIn("18", res["evidence_session_ids"])
        self.assertIn("14", res["evidence_session_ids"])

        # Must reflect real stored performance delta
        self.assertIn("1.80", reply)
        self.assertIn("1.10", reply)

        # Causation guard in insight
        self.assertTrue(
            "correlate" in res["insight"].lower() or "does not prove" in res["insight"].lower()
        )

        # Actionable recommendation
        self.assertIn("Session #18", res["recommendation"])

    # -----------------------------------------------------------------
    # 3. REQUIRED QUERY: "What should I work on?" / "What should I focus on today?"
    # -----------------------------------------------------------------
    def test_query_3_what_should_i_work_on(self):
        for q in ["What should I work on?", "What should I focus on today?"]:
            res = self.connector.handle_query(q)

            reply = res["reply"]
            self.assertIn("ANSWER:", reply)
            self.assertIn("EVIDENCE:", reply)
            self.assertIn("INSIGHT:", reply)
            self.assertIn("RECOMMENDATION:", reply)

            # Evidence cites real historical sessions
            self.assertTrue(len(res["evidence_session_ids"]) >= 1)
            self.assertIn("Session #18", res["evidence"])

            # Must derive focus from plan/data
            self.assertTrue(len(res["answer"]) > 10)
            self.assertIn("Gaming Plan", res["recommendation"])
            self.assertIn("Warmup", res["recommendation"])

    # -----------------------------------------------------------------
    # 4. REQUIRED QUERY: "What should I do next?"
    # -----------------------------------------------------------------
    def test_query_4_what_should_i_do_next(self):
        res = self.connector.handle_query("What should I do next?")

        reply = res["reply"]
        self.assertIn("ANSWER:", reply)
        self.assertIn("EVIDENCE:", reply)
        self.assertIn("INSIGHT:", reply)
        self.assertIn("RECOMMENDATION:", reply)

        # Must execute active Gaming Plan
        self.assertIn("Gaming Plan", res["answer"])
        self.assertIn("Warmup", res["recommendation"])
        self.assertIn("Practice", res["recommendation"])
        self.assertIn("Gameplay", res["recommendation"])
        self.assertIn("Review", res["recommendation"])

    # -----------------------------------------------------------------
    # 5. HALLUCINATION PROTECTION: Unrecorded facts
    # -----------------------------------------------------------------
    def test_hallucination_protection_unrecorded_topics(self):
        # Asking about a game with no records in Second Brain
        res = self.connector.handle_query("How did I perform in League of Legends?")
        
        self.assertEqual(res["answer"], NOT_ENOUGH_DATA)
        self.assertIn(NOT_ENOUGH_DATA, res["evidence"])
        self.assertEqual(res["insight"], NOT_ENOUGH_DATA)
        self.assertEqual(res["recommendation"], NOT_ENOUGH_DATA)

    # -----------------------------------------------------------------
    # 6. INSUFFICIENT DATA PROTECTION: Empty Database
    # -----------------------------------------------------------------
    def test_insufficient_data_empty_db(self):
        empty_dir = tempfile.TemporaryDirectory()
        empty_db_path = os.path.join(empty_dir.name, "empty.db")
        empty_storage = SessionStorage(db_path=empty_db_path)
        empty_connector = SecondBrainCopilotConnector(storage=empty_storage)

        try:
            # Query 1: Best session with 0 sessions
            r1 = empty_connector.handle_query("What was my best session?")
            self.assertEqual(r1["answer"], NOT_ENOUGH_DATA)
            self.assertIn(NOT_ENOUGH_DATA, r1["evidence"])

            # Query 2: What changed with 0 sessions
            r2 = empty_connector.handle_query("What changed?")
            self.assertEqual(r2["answer"], NOT_ENOUGH_DATA)

            # Query 3: Focus on today with 0 sessions
            r3 = empty_connector.handle_query("What should I focus on today?")
            self.assertEqual(r3["answer"], NOT_ENOUGH_DATA)

            # Query 4: Next step with 0 sessions
            r4 = empty_connector.handle_query("What should I do next?")
            self.assertEqual(r4["answer"], NOT_ENOUGH_DATA)
        finally:
            empty_dir.cleanup()

    # -----------------------------------------------------------------
    # 7. ADDITIONAL CROSS-SESSION QUERIES
    # -----------------------------------------------------------------
    def test_additional_cross_session_queries(self):
        # Am I improving?
        r_imp = self.connector.handle_query("Am I improving?")
        self.assertIn("ANSWER:", r_imp["reply"])
        self.assertIn("EVIDENCE:", r_imp["reply"])

        # Which map do I perform best on?
        r_map = self.connector.handle_query("Which map do I perform best on?")
        self.assertIn("ANSWER:", r_map["reply"])
        self.assertIn("Ascent", r_map["reply"])

        # Which configuration produces better results?
        r_cfg = self.connector.handle_query("Which configuration produces better results?")
        self.assertIn("ANSWER:", r_cfg["reply"])
        self.assertIn("Phantom", r_cfg["reply"])

    # -----------------------------------------------------------------
    # 8. FASTAPI ENDPOINT: POST /api/copilot/chat
    # -----------------------------------------------------------------
    def test_api_copilot_chat_endpoint(self):
        response = self.client.post("/api/copilot/chat", json={
            "message": "What was my best session?"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("ANSWER:", data["reply"])
        self.assertIn("EVIDENCE:", data["reply"])
        self.assertIn("INSIGHT:", data["reply"])
        self.assertIn("RECOMMENDATION:", data["reply"])
        self.assertIn("source_engine", data)

        # Check that endpoint returns structured fields
        self.assertIsNotNone(data.get("answer"))
        self.assertIsNotNone(data.get("evidence"))
        self.assertIsNotNone(data.get("insight"))
        self.assertIsNotNone(data.get("recommendation"))


if __name__ == "__main__":
    unittest.main()
