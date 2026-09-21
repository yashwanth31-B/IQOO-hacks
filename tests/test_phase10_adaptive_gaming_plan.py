import unittest
import os
import tempfile
from fastapi.testclient import TestClient

from app.models import (
    Session,
    AIGamingPlan,
    PlanEvaluation,
    AdaptivePlanCycleResponse,
    AdaptivePlanEvaluationRequest
)
from app.session_storage import SessionStorage
from app.player_profile import PlayerProfileManager
from app.cross_session_analyzer import CrossSessionAnalyzer
from app.gaming_plan_engine import GamingPlanEngine
from app.adaptive_plan_engine import AdaptivePlanEngine
from app.main import app


class TestPhase10AdaptiveGamingPlan(unittest.TestCase):
    """
    Unit and integration tests for Phase 10: Adaptive Gaming Plan.
    Verifies:
    1. Full Flow:
       Previous Plan -> Player Plays -> New Session -> Compare Expected vs Actual
       -> Evaluate Plan -> Create Improved Next Plan
    2. Evaluation Criteria:
       - goal completed
       - performance change
       - focus-area result
       - session duration
       - relevant metrics
       - plan effectiveness
    3. Strict Causation Guard:
       - AI evaluation does NOT claim the plan caused improvement.
       - Uses neutral evidence-based language:
         'Your K/D was higher than your previous recorded session. The stored data does not establish that the practice caused the improvement.'
    4. Next Plan Generation:
       - Uses new session together with historical sessions.
       - Never discards previous sessions.
    5. Multiple Plan -> Session Cycles (Cycle 1 -> Cycle 2 -> Cycle 3).
    6. REST API Endpoints (/api/plan/evaluate, /api/plan/adaptive-cycle, /api/plan/evaluation/latest).
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase10.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.profile_mgr = PlayerProfileManager(storage=self.storage)
        self.analyzer = CrossSessionAnalyzer(storage=self.storage)
        self.plan_engine = GamingPlanEngine(
            storage=self.storage,
            profile_manager=self.profile_mgr,
            cross_session_analyzer=self.analyzer
        )
        self.adaptive_engine = AdaptivePlanEngine(
            storage=self.storage,
            gaming_plan_engine=self.plan_engine,
            profile_manager=self.profile_mgr,
            cross_session_analyzer=self.analyzer
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_base_sessions(self):
        """Seed 2 initial sessions so that plan generation has baseline data."""
        self.storage.create_session({
            "session_id": "10",
            "game": "Valorant",
            "map": "Fracture",
            "configuration": "Vandal configuration",
            "duration": 50,
            "kills": 8,
            "deaths": 12,
            "kd_ratio": 0.67,
            "result": "Defeat",
            "player_notes": "Struggled with first duels."
        })
        self.storage.create_session({
            "session_id": "11",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 65,
            "kills": 15,
            "deaths": 10,
            "kd_ratio": 1.50,
            "result": "Win",
            "player_notes": "Defense crosshair placement felt better."
        })

    # -----------------------------------------------------------------
    # STEP 1: EVALUATE PLAN (Expected vs Actual & Causation Guard)
    # -----------------------------------------------------------------
    def test_evaluate_plan_improved_kd_causation_guard(self):
        """
        Verify Plan Evaluation when K/D improves:
        AI evaluation must use neutral language and state:
        'The stored data does not establish that the practice caused the improvement.'
        """
        self._seed_base_sessions()

        # Step 1: Initial Plan (Focus on crosshair placement)
        plan_1 = self.plan_engine.create_plan(game="Valorant", custom_goal="Improve consistency")

        # Step 2: Player Plays -> New Session with K/D = 1.80 (Higher than previous 1.50)
        session_12 = self.storage.create_session({
            "session_id": "12",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 72,
            "kills": 18,
            "deaths": 10,
            "kd_ratio": 1.80,
            "result": "Win",
            "player_notes": "Clean crosshair placement on Ascent."
        })

        # Step 3 & 4: Evaluate Plan vs Session 12
        eval_res = self.adaptive_engine.evaluate_plan(plan_target=plan_1, session_target=session_12)

        # 1. Goal completed
        self.assertTrue(eval_res.goal_completed)
        # 2. Performance change
        self.assertIn("improved", eval_res.performance_change.lower())
        self.assertIn("1.80", eval_res.performance_change)
        # 3. Focus-area result
        self.assertIn("crosshair placement", eval_res.focus_area_result.lower())
        # 4. Session duration
        self.assertIn("72", eval_res.session_duration)
        # 5. Relevant metrics
        self.assertIn("planned_metrics_to_track", eval_res.relevant_metrics)
        self.assertEqual(eval_res.relevant_metrics["actual_metrics"]["K/D"], 1.80)
        # 6. Plan effectiveness
        self.assertEqual(eval_res.plan_effectiveness, "effective")

        # 7. CAUSATION GUARD: Exact neutral phrasing required by prompt
        self.assertIn("Your K/D was higher than your previous recorded session", eval_res.ai_evaluation)
        self.assertIn("The stored data does not establish that the practice caused the improvement", eval_res.ai_evaluation)

        # 8. Evidence IDs
        self.assertIn("12", eval_res.evidence_session_ids)
        self.assertIn("11", eval_res.evidence_session_ids)

    def test_evaluate_plan_decreased_kd_causation_guard(self):
        """Verify neutral causation guard when K/D decreases."""
        self._seed_base_sessions()

        plan_1 = self.plan_engine.create_plan(game="Valorant")

        # New session with lower performance
        session_12 = self.storage.create_session({
            "session_id": "12",
            "game": "Valorant",
            "map": "Haven",
            "configuration": "Phantom configuration",
            "duration": 90,
            "kills": 7,
            "deaths": 14,
            "kd_ratio": 0.50,
            "result": "Defeat",
            "player_notes": "Difficult duels and fatigue."
        })

        eval_res = self.adaptive_engine.evaluate_plan(plan_target=plan_1, session_target=session_12)

        self.assertFalse(eval_res.goal_completed)
        self.assertIn("declined", eval_res.performance_change.lower())
        self.assertIn("Your K/D was lower than your previous recorded session", eval_res.ai_evaluation)
        self.assertIn("does not establish that the plan was the sole cause", eval_res.ai_evaluation)

    # -----------------------------------------------------------------
    # STEP 2: CREATE IMPROVED NEXT PLAN
    # -----------------------------------------------------------------
    def test_create_improved_next_plan_preserves_all_history(self):
        """
        Next plan must incorporate the new session together with historical sessions.
        Never discard previous sessions.
        """
        self._seed_base_sessions()
        plan_1 = self.plan_engine.create_plan(game="Valorant")

        session_12 = self.storage.create_session({
            "session_id": "12",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 70,
            "kills": 19,
            "deaths": 10,
            "kd_ratio": 1.90,
            "result": "Win"
        })

        eval_res = self.adaptive_engine.evaluate_plan(plan_target=plan_1, session_target=session_12)
        next_plan = self.adaptive_engine.create_next_plan(evaluation=eval_res, previous_plan=plan_1)

        self.assertIsNotNone(next_plan.plan_id)
        self.assertNotEqual(next_plan.plan_id, plan_1.plan_id)
        self.assertEqual(next_plan.game, "Valorant")
        self.assertEqual(next_plan.status, "ready")

        # Check that historical sessions are preserved in evidence
        # Should include session 10, 11, and 12
        evidence_set = set(next_plan.evidence_session_ids)
        self.assertTrue("12" in evidence_set)
        self.assertTrue("11" in evidence_set or "10" in evidence_set)
        self.assertTrue(len(evidence_set) >= 3)

        # Check adaptive reasoning references evaluation
        self.assertIn(eval_res.evaluation_id, next_plan.ai_reasoning)

    # -----------------------------------------------------------------
    # MULTIPLE PLAN -> SESSION CYCLES
    # -----------------------------------------------------------------
    def test_multiple_plan_session_cycles(self):
        """
        Tests multiple sequential cycles:
        Cycle 1: Plan 1 -> Session 1 -> Evaluation 1 -> Plan 2
        Cycle 2: Plan 2 -> Session 2 -> Evaluation 2 -> Plan 3
        Cycle 3: Plan 3 -> Session 3 -> Evaluation 3 -> Plan 4
        """
        self._seed_base_sessions()

        # ================= CYCLE 1 =================
        # 1. Plan 1
        plan_1 = self.plan_engine.create_plan(game="Valorant", custom_goal="Improve consistency")

        # 2. Player Plays -> Session 12
        s12 = self.storage.create_session({
            "session_id": "12",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 70,
            "kills": 18,
            "deaths": 10,
            "kd_ratio": 1.80,
            "result": "Win"
        })

        # 3. Adaptive Cycle 1 -> Plan 2
        cycle_1 = self.adaptive_engine.execute_adaptive_cycle(session_target=s12, plan_target=plan_1)
        plan_2 = cycle_1.next_plan

        self.assertEqual(cycle_1.evaluation.session_id, "12")
        self.assertTrue(cycle_1.evaluation.goal_completed)
        self.assertIn("does not establish that the practice caused the improvement", cycle_1.evaluation.ai_evaluation)
        self.assertEqual(cycle_1.historical_sessions_count, 3)  # Sessions 10, 11, 12

        # ================= CYCLE 2 =================
        # 1. Player Plays with Plan 2 -> Session 13
        s13 = self.storage.create_session({
            "session_id": "13",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 75,
            "kills": 20,
            "deaths": 11,
            "kd_ratio": 1.82,
            "result": "Win",
            "player_notes": "Angle discipline held all match."
        })

        # 2. Adaptive Cycle 2 -> Plan 3
        cycle_2 = self.adaptive_engine.execute_adaptive_cycle(session_target=s13, plan_target=plan_2)
        plan_3 = cycle_2.next_plan

        self.assertEqual(cycle_2.evaluation.session_id, "13")
        self.assertTrue(cycle_2.evaluation.goal_completed)
        self.assertEqual(cycle_2.historical_sessions_count, 4)  # Sessions 10, 11, 12, 13
        # Check cumulative history is never discarded
        self.assertTrue(len(plan_3.evidence_session_ids) >= 3)

        # ================= CYCLE 3 =================
        # 1. Player Plays with Plan 3 -> Session 14
        s14 = self.storage.create_session({
            "session_id": "14",
            "game": "Valorant",
            "map": "Haven",
            "configuration": "Phantom configuration",
            "duration": 80,
            "kills": 16,
            "deaths": 12,
            "kd_ratio": 1.33,
            "result": "Win"
        })

        # 2. Adaptive Cycle 3 -> Plan 4
        cycle_3 = self.adaptive_engine.execute_adaptive_cycle(session_target=s14, plan_target=plan_3)
        plan_4 = cycle_3.next_plan

        self.assertEqual(cycle_3.evaluation.session_id, "14")
        self.assertEqual(cycle_3.historical_sessions_count, 5)  # Sessions 10, 11, 12, 13, 14
        self.assertIsNotNone(plan_4.plan_id)
        self.assertTrue(len(plan_4.practice_tasks) >= 1)
        self.assertTrue(len(plan_4.gameplay_tasks) >= 1)

    # -----------------------------------------------------------------
    # REST API TESTS
    # -----------------------------------------------------------------
    def test_api_adaptive_plan_endpoints(self):
        """Verify /api/plan/evaluate, /api/plan/adaptive-cycle, and /api/plan/evaluation/latest."""
        self._seed_base_sessions()

        # Generate base plan
        self.client.post("/api/plan", json={"game": "Valorant"})

        # Record a resulting session
        new_session_payload = {
            "session_id": "100",
            "game": "Valorant",
            "map": "Ascent",
            "configuration": "Phantom configuration",
            "duration": 72,
            "kills": 25,
            "deaths": 10,
            "kd_ratio": 2.50,
            "result": "Win"
        }

        # POST /api/plan/evaluate
        res_eval = self.client.post("/api/plan/evaluate", json={"session_data": new_session_payload})
        self.assertEqual(res_eval.status_code, 200)
        eval_data = res_eval.json()
        self.assertIn("evaluation_id", eval_data)
        self.assertIn("performance_change", eval_data)
        self.assertIn("does not establish that the practice caused the improvement", eval_data["ai_evaluation"])

        # GET /api/plan/evaluation/latest
        res_latest = self.client.get("/api/plan/evaluation/latest")
        self.assertEqual(res_latest.status_code, 200)
        latest_eval = res_latest.json()
        self.assertIsNotNone(latest_eval)
        self.assertEqual(latest_eval["evaluation_id"], eval_data["evaluation_id"])

        # POST /api/plan/adaptive-cycle
        res_cycle = self.client.post("/api/plan/adaptive-cycle", json={"session_id": "100"})
        self.assertEqual(res_cycle.status_code, 200)
        cycle_data = res_cycle.json()
        self.assertIn("evaluation", cycle_data)
        self.assertIn("next_plan", cycle_data)
        self.assertGreaterEqual(cycle_data["historical_sessions_count"], 3)


if __name__ == "__main__":
    unittest.main()
