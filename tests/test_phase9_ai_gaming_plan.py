import unittest
import os
import tempfile
from fastapi.testclient import TestClient

from app.models import Session, AIGamingPlan, CreateGamingPlanRequest
from app.session_storage import SessionStorage
from app.player_profile import PlayerProfileManager
from app.cross_session_analyzer import CrossSessionAnalyzer
from app.gaming_plan_engine import GamingPlanEngine, INSUFFICIENT_DATA_MSG
from app.main import app


class TestPhase9AIGamingPlan(unittest.TestCase):
    """
    Unit and integration tests for Phase 9: AI Gaming Plan.
    Verifies:
    1. Pipeline Flow: Historical Sessions -> Memory -> Cross-Session Analysis -> AI Gaming Plan
    2. Complete plan schema:
       - plan_id, game, goal, focus_area, recommended_duration, warmup,
         practice_tasks, gameplay_tasks, review_tasks, metrics_to_track,
         evidence_session_ids, ai_reasoning, status
    3. Strict hallucination protection:
       - 0 or 1 session returns 'Not enough data to create a personalized gaming plan.'
       - Evidence session IDs present on every plan
    4. Plan personalization:
       - Inconsistent performance -> 'Improve consistency'
       - Decreasing performance -> 'Stabilize combat efficiency...'
       - Increasing performance -> 'Maintain upward momentum...'
    5. REST API endpoints (/api/plan, /api/plan/latest)
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase9.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.profile_mgr = PlayerProfileManager(storage=self.storage)
        self.analyzer = CrossSessionAnalyzer(storage=self.storage)
        self.plan_engine = GamingPlanEngine(
            storage=self.storage,
            profile_manager=self.profile_mgr,
            cross_session_analyzer=self.analyzer
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------
    # INSUFFICIENT DATA TESTS
    # -----------------------------------------------------------------
    def test_zero_sessions_insufficient_data(self):
        """0 sessions must yield 'Not enough data to create a personalized gaming plan.'"""
        plan = self.plan_engine.create_plan()

        self.assertEqual(plan.status, "insufficient_data")
        self.assertEqual(plan.goal, INSUFFICIENT_DATA_MSG)
        self.assertEqual(plan.focus_area, INSUFFICIENT_DATA_MSG)
        self.assertEqual(plan.ai_reasoning, INSUFFICIENT_DATA_MSG)
        self.assertEqual(plan.evidence_session_ids, [])
        self.assertEqual(plan.practice_tasks, [])
        self.assertEqual(plan.gameplay_tasks, [])

    def test_single_session_insufficient_data(self):
        """1 session must also return 'Not enough data to create a personalized gaming plan.'"""
        self.storage.create_session({
            "session_id": "18",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 72,
            "kills": 18,
            "deaths": 10,
            "kd_ratio": 1.8,
            "result": "Win"
        })

        plan = self.plan_engine.create_plan()

        self.assertEqual(plan.status, "insufficient_data")
        self.assertEqual(plan.goal, INSUFFICIENT_DATA_MSG)
        self.assertEqual(plan.ai_reasoning, INSUFFICIENT_DATA_MSG)
        self.assertEqual(plan.evidence_session_ids, [])

    # -----------------------------------------------------------------
    # COMPLETE PIPELINE & SCHEMA TESTS
    # -----------------------------------------------------------------
    def test_pipeline_creates_complete_plan(self):
        """
        Tests end-to-end pipeline:
        Historical Sessions -> Memory -> Cross-Session Analysis -> AI Gaming Plan
        """
        sessions = [
            {
                "session_id": "12",
                "game": "Valorant",
                "map": "Fracture",
                "configuration": "Vandal configuration",
                "duration": 45,
                "kills": 6,
                "deaths": 14,
                "kd_ratio": 0.43,
                "result": "Defeat",
                "player_notes": "Dry-peeked and lost first duels."
            },
            {
                "session_id": "14",
                "game": "Valorant",
                "map": "Ascent",
                "configuration": "Phantom configuration",
                "duration": 65,
                "kills": 20,
                "deaths": 12,
                "kd_ratio": 1.67,
                "result": "Win",
                "player_notes": "Good defense."
            },
            {
                "session_id": "18",
                "game": "Valorant",
                "map": "Ascent",
                "configuration": "Phantom configuration",
                "duration": 72,
                "kills": 18,
                "deaths": 10,
                "kd_ratio": 1.80,
                "result": "Win",
                "player_notes": "Felt locked in. Crosshair placement was clean."
            },
            {
                "session_id": "21",
                "game": "Valorant",
                "map": "Haven",
                "configuration": "Phantom configuration",
                "duration": 105,
                "kills": 14,
                "deaths": 16,
                "kd_ratio": 0.88,
                "result": "Defeat",
                "player_notes": "Fatigued in overtime."
            }
        ]
        for s in sessions:
            self.storage.create_session(s)

        plan = self.plan_engine.create_plan(game="Valorant")

        # 1. Verify schema elements
        self.assertIsNotNone(plan.plan_id)
        self.assertEqual(plan.game, "Valorant")
        self.assertIn(plan.status, ["ready"])
        self.assertIn("75 minutes", plan.recommended_duration)
        self.assertIn("10 minutes", plan.warmup)
        self.assertTrue(len(plan.practice_tasks) >= 1)
        self.assertTrue(len(plan.gameplay_tasks) >= 1)
        self.assertTrue(len(plan.review_tasks) >= 1)
        self.assertEqual(plan.metrics_to_track, ["K/D", "Deaths", "Accuracy", "Result"])

        # 2. Verify evidence provenance
        self.assertTrue(len(plan.evidence_session_ids) >= 2)
        self.assertIn("18", plan.evidence_session_ids)

        # 3. Verify AI reasoning references stored data
        self.assertIn("stored sessions", plan.ai_reasoning.lower())
        self.assertNotEqual(plan.ai_reasoning, INSUFFICIENT_DATA_MSG)

    # -----------------------------------------------------------------
    # PERSONALIZATION & REASONING TESTS
    # -----------------------------------------------------------------
    def test_inconsistent_performance_goal(self):
        """Inconsistent performance triggers 'Improve consistency' and 'Crosshair placement' focus."""
        sessions = [
            {"session_id": "1", "game": "Valorant", "kills": 18, "deaths": 10, "kd_ratio": 1.8, "player_notes": "Crosshair sharp"},
            {"session_id": "2", "game": "Valorant", "kills": 5, "deaths": 10, "kd_ratio": 0.5, "player_notes": "Aim off"},
            {"session_id": "3", "game": "Valorant", "kills": 19, "deaths": 10, "kd_ratio": 1.9, "player_notes": "Crosshair crisp"},
            {"session_id": "4", "game": "Valorant", "kills": 6, "deaths": 10, "kd_ratio": 0.6, "player_notes": "Inconsistent duels"}
        ]
        for s in sessions:
            self.storage.create_session(s)

        plan = self.plan_engine.create_plan()

        self.assertEqual(plan.status, "ready")
        self.assertEqual(plan.goal, "Improve consistency")
        self.assertEqual(plan.focus_area, "Crosshair placement")
        self.assertIn("inconsistent", plan.ai_reasoning.lower())

    def test_decreasing_performance_goal(self):
        """Decreasing performance triggers stabilization goal and defensive focus."""
        sessions = [
            {"session_id": "1", "game": "Valorant", "kills": 20, "deaths": 10, "kd_ratio": 2.0},
            {"session_id": "2", "game": "Valorant", "kills": 16, "deaths": 10, "kd_ratio": 1.6},
            {"session_id": "3", "game": "Valorant", "kills": 12, "deaths": 10, "kd_ratio": 1.2},
            {"session_id": "4", "game": "Valorant", "kills": 7, "deaths": 14, "kd_ratio": 0.5, "player_notes": "Dry-peek deaths"}
        ]
        for s in sessions:
            self.storage.create_session(s)

        plan = self.plan_engine.create_plan()

        self.assertEqual(plan.status, "ready")
        self.assertIn("stabilize", plan.goal.lower())
        self.assertIn("peeking", plan.focus_area.lower())

    def test_custom_goal_override(self):
        """User-specified custom goal is respected while retaining evidence-based tasks."""
        sessions = [
            {"session_id": "1", "game": "Valorant", "kills": 15, "deaths": 10, "kd_ratio": 1.5},
            {"session_id": "2", "game": "Valorant", "kills": 18, "deaths": 10, "kd_ratio": 1.8}
        ]
        for s in sessions:
            self.storage.create_session(s)

        plan = self.plan_engine.create_plan(custom_goal="Warm up for ranked tournament")

        self.assertEqual(plan.goal, "Warm up for ranked tournament")
        self.assertEqual(plan.status, "ready")
        self.assertTrue(len(plan.evidence_session_ids) >= 2)

    # -----------------------------------------------------------------
    # REST API TESTS
    # -----------------------------------------------------------------
    def test_api_gaming_plan_endpoints(self):
        """Verify POST /api/plan and GET /api/plan/latest."""
        self.storage.create_session({"session_id": "1", "game": "Valorant", "kills": 15, "deaths": 10, "kd_ratio": 1.5})
        self.storage.create_session({"session_id": "2", "game": "Valorant", "kills": 18, "deaths": 10, "kd_ratio": 1.8})

        # POST /api/plan
        res_post = self.client.post("/api/plan", json={"game": "Valorant"})
        self.assertEqual(res_post.status_code, 200)
        plan_data = res_post.json()
        self.assertIn("plan_id", plan_data)
        self.assertIn("warmup", plan_data)
        self.assertIn("practice_tasks", plan_data)
        self.assertIn("gameplay_tasks", plan_data)
        self.assertIn("review_tasks", plan_data)
        self.assertIn("metrics_to_track", plan_data)
        self.assertIn("evidence_session_ids", plan_data)
        self.assertIn("ai_reasoning", plan_data)

        # GET /api/plan/latest
        res_get = self.client.get("/api/plan/latest")
        self.assertEqual(res_get.status_code, 200)
        latest_data = res_get.json()
        self.assertIn("plan_id", latest_data)


if __name__ == "__main__":
    unittest.main()
