"""
Unit and integration tests for Phase 8: AI Gaming Plan.

Requirements tested:
- Create an AI Gaming Plan using:
  * player profile
  * previous sessions
  * performance metrics
  * detected game
  * detected map
  * AI tasks
  * historical patterns
- Plan fields:
  plan_id, game, map, goal, focus_area, recommended_duration, warmup,
  practice_tasks, gameplay_tasks, review_tasks, metrics_to_track,
  evidence_session_ids, ai_reasoning, status.
- Exact display format matching prompt:
     AI GAMING PLAN

    Game: BGMI
    Map: Erangel

    Goal:
    Improve survival and rotation decisions.

    Warm-up:
    10 minutes

    Practice:
    15 minutes

    Gameplay:
    40 minutes

    Review:
    10 minutes

    Track:
    Survival time
    Deaths
    Rotation decisions
    Final placement

    Evidence:
    Session #12
    Session #16
    Session #18
- Flow verification:
    Game detected -> Map detected -> Retrieve player history -> Identify relevant patterns -> Generate tasks -> Build Gaming Plan
- Insufficient data handling:
    "Not enough data to create a personalized plan."
"""

import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from app.models import Session, TimelineEvent, AIGamingPlan
from app.session_storage import SessionStorage
from app.player_profile import PlayerProfileManager
from app.performance_engine import GamingPerformanceEngine
from app.task_engine import GamingTaskEngine
from app.cross_session_analyzer import CrossSessionAnalyzer
from app.gaming_plan_engine import GamingPlanEngine, INSUFFICIENT_DATA_MSG
from app.main import app


class TestPhase8AIGamingPlan(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase8.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.profile_mgr = PlayerProfileManager(storage=self.storage)
        self.perf_engine = GamingPerformanceEngine(storage=self.storage)
        self.task_engine = GamingTaskEngine(storage=self.storage)
        self.analyzer = CrossSessionAnalyzer(storage=self.storage)

        self.plan_engine = GamingPlanEngine(
            storage=self.storage,
            profile_manager=self.profile_mgr,
            performance_engine=self.perf_engine,
            task_engine=self.task_engine,
            cross_session_analyzer=self.analyzer
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_prompt_example_formatting(self):
        """
        Verifies exact format display matching prompt specification:
         AI GAMING PLAN

        Game: BGMI
        Map: Erangel

        Goal:
        Improve survival and rotation decisions.

        Warm-up:
        10 minutes

        Practice:
        15 minutes

        Gameplay:
        40 minutes

        Review:
        10 minutes

        Track:
        Survival time
        Deaths
        Rotation decisions
        Final placement

        Evidence:
        Session #12
        Session #16
        Session #18
        """
        plan = AIGamingPlan(
            plan_id="plan-test-exact",
            game="BGMI",
            map="Erangel",
            goal="Improve survival and rotation decisions.",
            focus_area="Survival & Rotation Decisions",
            recommended_duration="75 minutes",
            warmup="10 minutes",
            practice="15 minutes",
            gameplay="40 minutes",
            review="10 minutes",
            metrics_to_track=[
                "Survival time",
                "Deaths",
                "Rotation decisions",
                "Final placement"
            ],
            evidence_session_ids=["12", "16", "18"],
            ai_reasoning="Synthesized from historical BGMI Erangel sessions.",
            status="ready"
        )

        expected_display = (
            " AI GAMING PLAN\n\n"
            "Game: BGMI\n"
            "Map: Erangel\n\n"
            "Goal:\n"
            "Improve survival and rotation decisions.\n\n"
            "Warm-up:\n"
            "10 minutes\n\n"
            "Practice:\n"
            "15 minutes\n\n"
            "Gameplay:\n"
            "40 minutes\n\n"
            "Review:\n"
            "10 minutes\n\n"
            "Track:\n"
            "Survival time\n"
            "Deaths\n"
            "Rotation decisions\n"
            "Final placement\n\n"
            "Evidence:\n"
            "Session #12\n"
            "Session #16\n"
            "Session #18"
        )
        self.assertEqual(plan.format_display(), expected_display)

    def test_insufficient_data_returns_exact_message(self):
        """
        If insufficient data exists (e.g. 0 sessions), returns:
        'Not enough data to create a personalized plan.'
        """
        plan = self.plan_engine.create_plan(game="BGMI", map_name="Erangel")
        self.assertEqual(plan.status, "insufficient_data")
        self.assertEqual(plan.goal, "Not enough data to create a personalized plan.")
        self.assertEqual(plan.ai_reasoning, "Not enough data to create a personalized plan.")
        self.assertEqual(len(plan.evidence_session_ids), 0)

    def test_full_phase8_flow_creation(self):
        """
        Tests the complete 6-step flow:
        1. Game detected (BGMI)
        2. Map detected (Erangel)
        3. Retrieve player history (Sessions 12, 16, 18)
        4. Identify relevant patterns (zone rotation deaths, survival variance)
        5. Generate AI tasks
        6. Build Gaming Plan
        """
        # Seed Session 12
        self.storage.create_session(Session(
            session_id="12",
            game="BGMI",
            map="Erangel",
            kills=4,
            deaths=1,
            duration=22,
            result="Top 10",
            player_notes="Eliminated during zone 4 vehicle rotation outside Pochinki.",
            performance_metrics={"survival_duration": "22 min", "first_deaths": 0}
        ))
        # Seed Session 16
        self.storage.create_session(Session(
            session_id="16",
            game="BGMI",
            map="Erangel",
            kills=6,
            deaths=1,
            duration=18,
            result="Top 15",
            player_notes="Bridge rotation was camped, died crossing water.",
            performance_metrics={"survival_duration": "18 min", "first_deaths": 1}
        ))
        # Seed Session 18
        self.storage.create_session(Session(
            session_id="18",
            game="BGMI",
            map="Erangel",
            kills=8,
            deaths=1,
            duration=26,
            result="Top 5",
            player_notes="Rotated early to compound, survived to final circle.",
            performance_metrics={"survival_duration": "26 min", "first_deaths": 0}
        ))

        # Run flow
        plan = self.plan_engine.create_plan(game="BGMI", map_name="Erangel")

        # Verify Plan fields
        self.assertIsNotNone(plan.plan_id)
        self.assertEqual(plan.game, "BGMI")
        self.assertEqual(plan.map, "Erangel")
        self.assertEqual(plan.goal, "Improve survival and rotation decisions.")
        self.assertEqual(plan.warmup, "10 minutes")
        self.assertEqual(plan.practice, "15 minutes")
        self.assertEqual(plan.gameplay, "40 minutes")
        self.assertEqual(plan.review, "10 minutes")
        self.assertIn("Survival time", plan.metrics_to_track)
        self.assertIn("Deaths", plan.metrics_to_track)
        self.assertIn("Rotation decisions", plan.metrics_to_track)
        self.assertIn("Final placement", plan.metrics_to_track)

        # Verify Evidence includes historical sessions
        self.assertIn("12", plan.evidence_session_ids)
        self.assertIn("16", plan.evidence_session_ids)
        self.assertIn("18", plan.evidence_session_ids)
        self.assertEqual(plan.status, "ready")

    def test_plan_includes_all_required_fields(self):
        """
        Verify all 14 fields from prompt specification are present in AIGamingPlan:
        plan_id, game, map, goal, focus_area, recommended_duration, warmup,
        practice_tasks, gameplay_tasks, review_tasks, metrics_to_track,
        evidence_session_ids, ai_reasoning, status.
        """
        self.storage.create_session(Session(
            session_id="s-val-1",
            game="Valorant",
            map="Ascent",
            kills=18,
            deaths=10,
            result="Win",
            player_notes="Clean site holds on A site."
        ))

        plan = self.plan_engine.create_plan(game="Valorant", map_name="Ascent")

        required_attrs = [
            "plan_id", "game", "map", "goal", "focus_area",
            "recommended_duration", "warmup", "practice_tasks",
            "gameplay_tasks", "review_tasks", "metrics_to_track",
            "evidence_session_ids", "ai_reasoning", "status"
        ]
        for attr in required_attrs:
            self.assertTrue(hasattr(plan, attr), f"AIGamingPlan missing field '{attr}'")
            val = getattr(plan, attr)
            self.assertIsNotNone(val, f"Field '{attr}' should not be None")

    def test_rest_api_plan_endpoint(self):
        """
        Verifies REST API endpoint:
        POST /api/plan with game and map
        """
        # Seed session via API
        self.client.post("/api/sessions", json={
            "session_id": "api-plan-1",
            "game": "BGMI",
            "map": "Erangel",
            "kills": 5,
            "deaths": 1,
            "duration": "20 min",
            "result": "Top 10"
        })

        res = self.client.post("/api/plan", json={
            "game": "BGMI",
            "map": "Erangel"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["game"], "BGMI")
        self.assertEqual(data["map"], "Erangel")
        self.assertEqual(data["status"], "ready")
        self.assertIn("api-plan-1", data["evidence_session_ids"])


if __name__ == "__main__":
    unittest.main()
