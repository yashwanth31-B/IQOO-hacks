import os
import tempfile
import sqlite3
import unittest
from fastapi.testclient import TestClient

from app.models import (
    Session,
    AIGamingPlan,
    PlanEvaluation,
    TaskEvaluationResult,
    AdaptivePlanCycleResponse
)
from app.session_storage import SessionStorage
from app.player_profile import PlayerProfileManager
from app.cross_session_analyzer import CrossSessionAnalyzer
from app.gaming_plan_engine import GamingPlanEngine
from app.adaptive_plan_engine import AdaptivePlanEngine
from app.main import app


class TestPhase12AdaptivePlanning(unittest.TestCase):
    """
    Unit and integration tests for Phase 12: Adaptive Planning System.
    
    Verifies:
    1. Flow:
       Previous Gaming Plan -> Player completes session -> New Session Data
       -> Compare with previous sessions -> Evaluate task results
       -> Update player memory -> Create next Gaming Plan.
    2. For each task determine:
       * completed
       * partially completed
       * not completed
       * insufficient data
    3. Compare actual performance with historical performance.
    4. Strict Causation Guard:
       - Do not claim that completing a task caused improvement.
       - Exact prompt example:
         Previous focus: Positioning
         New session: Fewer recorded positioning-related deaths.
         AI statement:
         "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions."
         Do not say:
         "Your practice caused the improvement."
    5. Update player memory:
       - Memory record is persisted.
       - Player profile memory is refreshed.
    6. Create next Gaming Plan:
       - Adapts goal and focus based on evaluation results.
       - Never discards previous sessions.
    7. REST API endpoints.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase12.db")
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

    def _seed_historical_sessions(self):
        """Seed initial sessions with recorded positioning issues for baseline comparison."""
        self.storage.create_session({
            "session_id": "base_1",
            "game": "BGMI",
            "map": "Erangel",
            "configuration": "M416 + 4x",
            "duration": 25,
            "kills": 4,
            "deaths": 8,
            "kd_ratio": 0.50,
            "result": "Defeat",
            "performance_metrics": {"positioning_deaths": 4},
            "player_notes": "Caught in open field crossfire multiple times."
        })
        self.storage.create_session({
            "session_id": "base_2",
            "game": "BGMI",
            "map": "Erangel",
            "configuration": "M416 + 4x",
            "duration": 30,
            "kills": 6,
            "deaths": 6,
            "kd_ratio": 1.00,
            "result": "Defeat",
            "performance_metrics": {"positioning_deaths": 3},
            "player_notes": "Bad position on hill rotation."
        })

    # -----------------------------------------------------------------
    # 1. TEST POSITIONING EXAMPLE & CAUSATION GUARD
    # -----------------------------------------------------------------
    def test_positioning_improvement_exact_ai_statement(self):
        """
        Verify exact prompt specification:
        Previous focus: Positioning
        New session: Fewer recorded positioning-related deaths.
        AI statement:
        'Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions.'
        Do not say:
        'Your practice caused the improvement.'
        """
        self._seed_historical_sessions()

        # Step 1: Previous Gaming Plan with Positioning focus
        plan = AIGamingPlan(
            plan_id="plan-pos-001",
            game="BGMI",
            goal="Reduce repeated positioning mistakes",
            focus_area="Positioning",
            recommended_duration="40 minutes",
            warmup="10 minutes",
            practice_tasks=["15 minutes: Hold defensive cover and practice angle clearing."],
            gameplay_tasks=["40 minutes: 1 Match on Erangel. Focus on positioning and cover usage."],
            review_tasks=["5 minutes: Debrief positioning-related deaths."],
            metrics_to_track=["Positioning", "Deaths", "K/D"],
            evidence_session_ids=["base_1", "base_2"],
            ai_reasoning="Historical sessions showed repeated deaths caused by poor positioning.",
            status="ready"
        )
        self.plan_engine._persist_plan(plan)

        # Step 2 & 3: Player completes session -> New Session Data with FEWER positioning deaths (0 vs baseline ~3.5)
        new_session = {
            "session_id": "new_session_10",
            "game": "BGMI",
            "map": "Erangel",
            "configuration": "M416 + 4x",
            "duration": 35,
            "kills": 9,
            "deaths": 3,
            "kd_ratio": 3.00,
            "result": "Win",
            "performance_metrics": {"positioning_deaths": 0},
            "player_notes": "Maintained solid position behind rocks and held angles."
        }

        # Step 4 & 5: Evaluate plan against new session
        evaluation = self.adaptive_engine.evaluate_plan(
            plan_target=plan,
            session_target=new_session
        )

        # Verify exact AI statement requirement
        task_ai_statements = [t.ai_statement for t in evaluation.task_evaluations]
        self.assertTrue(
            any("Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions." in stmt for stmt in task_ai_statements),
            f"Expected statement not found in task evaluations: {task_ai_statements}"
        )
        self.assertIn("Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions.", evaluation.focus_area_result)

        # Verify causation guard: Never say 'Your practice caused the improvement.'
        self.assertNotIn("Your practice caused the improvement.", evaluation.ai_evaluation)
        self.assertIn("The stored data does not establish that the practice caused the improvement", evaluation.ai_evaluation)

    # -----------------------------------------------------------------
    # 2. TEST ALL 4 TASK EVALUATION STATUSES
    # -----------------------------------------------------------------
    def test_all_task_evaluation_statuses(self):
        """
        Verify for each task determine:
        * completed
        * partially completed
        * not completed
        * insufficient data
        """
        self._seed_historical_sessions()

        # Plan with 4 distinct tasks designed to hit all 4 statuses
        plan = AIGamingPlan(
            plan_id="plan-all-statuses",
            game="BGMI",
            goal="Evaluate diverse task outcomes",
            focus_area="Positioning and Combat",
            recommended_duration="40 minutes",
            warmup="10 minutes",
            practice_tasks=[
                # 1. Positioning task -> will be 'completed'
                "Targeted drill on positioning and cover usage.",
                # 2. Duration task (planned 80 mins) -> actual is 35 mins -> 'partially completed'
                "80 minutes: Long endurance gameplay match."
            ],
            gameplay_tasks=[
                # 3. High kill combat requirement (20 kills) -> actual is 2 kills -> 'not completed'
                "Eliminate 20 opponents in high-tempo duels."
            ],
            review_tasks=[
                # 4. Unknown metric task without any data -> 'insufficient data'
                "Track gyro calibration latency and biometric heart rate."
            ],
            metrics_to_track=["Positioning", "Duration", "Kills", "Latency"],
            evidence_session_ids=["base_1", "base_2"],
            ai_reasoning="Multifaceted task evaluation.",
            status="ready"
        )
        self.plan_engine._persist_plan(plan)

        new_session = {
            "session_id": "test_sess_4",
            "game": "BGMI",
            "map": "Erangel",
            "duration": 35,  # Partially completes 80 min task
            "kills": 2,      # Fails 20 kill combat task
            "deaths": 2,
            "kd_ratio": 1.00,
            "performance_metrics": {"positioning_deaths": 0},  # Completes positioning task
            "player_notes": "Good positioning throughout."
        }

        evaluation = self.adaptive_engine.evaluate_plan(
            plan_target=plan,
            session_target=new_session
        )

        statuses = [t.status for t in evaluation.task_evaluations]
        self.assertIn("completed", statuses)
        self.assertIn("partially completed", statuses)
        self.assertIn("not completed", statuses)
        self.assertIn("insufficient data", statuses)

    # -----------------------------------------------------------------
    # 3. COMPARE ACTUAL PERFORMANCE WITH HISTORICAL PERFORMANCE
    # -----------------------------------------------------------------
    def test_compare_actual_with_historical_performance(self):
        """
        Verify comparison between actual performance and historical baseline:
        - baseline K/D
        - baseline deaths
        - delta
        - observational comparison
        """
        self._seed_historical_sessions()

        new_session = {
            "session_id": "comp_sess_1",
            "game": "BGMI",
            "map": "Erangel",
            "duration": 28,
            "kills": 12,
            "deaths": 3,
            "kd_ratio": 4.00,
            "performance_metrics": {"positioning_deaths": 1},
            "player_notes": "Held high ground."
        }

        evaluation = self.adaptive_engine.evaluate_plan(
            session_target=new_session
        )

        comp = evaluation.performance_comparison
        self.assertIsNotNone(comp)
        self.assertEqual(comp["session_id"], "comp_sess_1")
        self.assertEqual(comp["historical_sessions_evaluated"], 2)

        # Baseline K/D was (0.50 + 1.00) / 2 = 0.75
        kd_comp = comp["metrics"]["kd_ratio"]
        self.assertEqual(kd_comp["actual"], 4.00)
        self.assertEqual(kd_comp["historical_baseline"], 0.75)
        self.assertEqual(kd_comp["delta"], 3.25)
        self.assertEqual(kd_comp["comparison"], "higher")

        # Baseline deaths was (8 + 6) / 2 = 7.0; actual was 3 -> fewer
        death_comp = comp["metrics"]["deaths"]
        self.assertEqual(death_comp["actual"], 3)
        self.assertEqual(death_comp["historical_baseline"], 7.0)
        self.assertEqual(death_comp["comparison"], "fewer")

    # -----------------------------------------------------------------
    # 4. FULL END-TO-END ADAPTIVE CYCLE FLOW
    # -----------------------------------------------------------------
    def test_full_adaptive_cycle_flow(self):
        """
        Tests the full Phase 12 flow:
        Previous Gaming Plan
            ↓
        Player completes session
            ↓
        New Session Data
            ↓
        Compare with previous sessions
            ↓
        Evaluate task results
            ↓
        Update player memory
            ↓
        Create next Gaming Plan
        """
        self._seed_historical_sessions()

        # Step 1: Previous Gaming Plan
        plan_1 = self.plan_engine.create_plan(game="BGMI", custom_goal="Positioning and survival")

        # Step 2 & 3: Player completes session -> New Session Data
        session_10 = self.storage.create_session({
            "session_id": "sess_flow_10",
            "game": "BGMI",
            "map": "Erangel",
            "duration": 30,
            "kills": 8,
            "deaths": 2,
            "kd_ratio": 4.00,
            "result": "Win",
            "performance_metrics": {"positioning_deaths": 0},
            "player_notes": "Great cover usage."
        })

        # Steps 4 to 7: Execute Adaptive Cycle
        cycle_res = self.adaptive_engine.execute_adaptive_cycle(
            session_target=session_10,
            plan_target=plan_1
        )

        # 1. Evaluation check
        eval_obj = cycle_res.evaluation
        self.assertEqual(eval_obj.session_id, "sess_flow_10")
        self.assertTrue(len(eval_obj.task_evaluations) >= 1)
        self.assertTrue(eval_obj.goal_completed)

        # 2. Update player memory check
        self.assertTrue(eval_obj.memory_updated)
        self.assertTrue(cycle_res.memory_updated)

        # Verify memory record stored in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memories WHERE memory_type = 'AdaptivePlanEvaluation'")
        mem_count = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(mem_count, 1)

        # 3. Next Gaming Plan check
        next_plan = cycle_res.next_plan
        self.assertIsNotNone(next_plan.plan_id)
        self.assertNotEqual(next_plan.plan_id, plan_1.plan_id)
        # Verify next plan retains all historical sessions (never discards previous sessions)
        self.assertEqual(cycle_res.historical_sessions_count, 3)  # base_1, base_2, sess_flow_10
        self.assertIn("sess_flow_10", next_plan.evidence_session_ids)
        self.assertIn("base_1", next_plan.evidence_session_ids)

        # Verify next plan adjusted focus area adaptively
        self.assertIn("Rotation", next_plan.focus_area)

    # -----------------------------------------------------------------
    # 5. REST API ENDPOINTS
    # -----------------------------------------------------------------
    def test_api_adaptive_planning_endpoints(self):
        """Verify REST API endpoints for Phase 12 adaptive planning."""
        self._seed_historical_sessions()

        # Create base plan
        self.client.post("/api/plan", json={"game": "BGMI"})

        new_session = {
            "session_id": "api_session_12",
            "game": "BGMI",
            "map": "Erangel",
            "duration": 32,
            "kills": 10,
            "deaths": 2,
            "kd_ratio": 5.00,
            "result": "Win",
            "performance_metrics": {"positioning_deaths": 0},
            "player_notes": "Fewer positioning deaths recorded."
        }

        # POST /api/adaptive/evaluate
        eval_resp = self.client.post("/api/adaptive/evaluate", json={"session_data": new_session})
        self.assertEqual(eval_resp.status_code, 200)
        eval_data = eval_resp.json()
        self.assertIn("evaluation_id", eval_data)
        self.assertIn("task_evaluations", eval_data)
        self.assertIn("performance_comparison", eval_data)
        self.assertIn("does not establish that the practice caused the improvement", eval_data["ai_evaluation"])

        # POST /api/adaptive/cycle
        cycle_resp = self.client.post("/api/adaptive/cycle", json={"session_id": "api_session_12"})
        self.assertEqual(cycle_resp.status_code, 200)
        cycle_data = cycle_resp.json()
        self.assertIn("evaluation", cycle_data)
        self.assertIn("next_plan", cycle_data)
        self.assertTrue(cycle_data["memory_updated"])
        self.assertGreaterEqual(cycle_data["historical_sessions_count"], 3)

        # GET /api/adaptive/evaluation/latest
        latest_resp = self.client.get("/api/adaptive/evaluation/latest")
        self.assertEqual(latest_resp.status_code, 200)
        latest_data = latest_resp.json()
        self.assertEqual(latest_data["evaluation_id"], cycle_data["evaluation"]["evaluation_id"])


if __name__ == "__main__":
    unittest.main()
