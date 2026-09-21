"""
Unit and integration tests for Phase 7: AI Gaming Task Engine.

Requirements tested:
- Converts historical performance information into specific, measurable gaming tasks.
- Task structure: task_id, game, category, objective, description, duration, metric_to_track,
  target, difficulty, evidence_session_ids, status.
- Categories: aim, movement, positioning, map_awareness, decision_making, combat,
  consistency, objective, strategy, configuration.
- Exact display format matching prompt example:
    Task:
    Improve crosshair placement.

    Duration:
    15 minutes.

    Metric:
    Deaths caused by poor positioning.

    Target:
    Reduce repeated positioning mistakes.

    Evidence:
    Session #18
    Session #21
- Tasks must be based on stored evidence (evidence_session_ids).
- Do not invent weaknesses.
- Do not claim causation.
- Insufficient data handling: "Not enough data to create a personalized task."
- No real-time game control: player remains responsible for all game actions.
- Persistence, status updates, and REST API endpoints.
"""

import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from app.models import Session, TimelineEvent, GamingTask, TaskEngineResponse, TASK_CATEGORIES
from app.session_storage import SessionStorage
from app.task_engine import GamingTaskEngine, INSUFFICIENT_DATA_MSG
from app.main import app


class TestPhase7AIGamingTaskEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_task_engine.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.engine = GamingTaskEngine(storage=self.storage)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_example_formatting(self):
        """
        Verifies exact display formatting matching the prompt example:
        Task:
        Improve crosshair placement.

        Duration:
        15 minutes.

        Metric:
        Deaths caused by poor positioning.

        Target:
        Reduce repeated positioning mistakes.

        Evidence:
        Session #18
        Session #21
        """
        task = GamingTask(
            task_id="task-pos-example",
            game="Valorant",
            category="positioning",
            objective="Improve crosshair placement",
            description="Focus on keeping crosshair at head height while navigating corners and holding angles.",
            duration="15 minutes",
            metric_to_track="Deaths caused by poor positioning",
            target="Reduce repeated positioning mistakes",
            difficulty="medium",
            evidence_session_ids=["18", "21"],
            status="pending"
        )

        expected_display = (
            "Task:\n"
            "Improve crosshair placement.\n\n"
            "Duration:\n"
            "15 minutes.\n\n"
            "Metric:\n"
            "Deaths caused by poor positioning.\n\n"
            "Target:\n"
            "Reduce repeated positioning mistakes.\n\n"
            "Evidence:\n"
            "Session #18\n"
            "Session #21"
        )
        self.assertEqual(task.format_display(), expected_display)

    def test_task_categories_validation(self):
        """
        Validates all 10 required categories:
        aim, movement, positioning, map_awareness, decision_making, combat,
        consistency, objective, strategy, configuration.
        Rejects invalid categories.
        """
        expected_cats = {
            "aim", "movement", "positioning", "map_awareness", "decision_making",
            "combat", "consistency", "objective", "strategy", "configuration"
        }
        self.assertEqual(set(TASK_CATEGORIES), expected_cats)

        for cat in expected_cats:
            t = GamingTask(
                task_id=f"task-{cat}",
                game="Valorant",
                category=cat,
                objective=f"Practice {cat}",
                description=f"Description for {cat}",
                duration="15 minutes",
                metric_to_track="Metric",
                target="Target",
                evidence_session_ids=["1"]
            )
            self.assertEqual(t.category, cat)

        # Invalid category should fail validation
        with self.assertRaises(ValueError):
            GamingTask(
                task_id="invalid-cat",
                game="Valorant",
                category="flying_cars",
                objective="Invalid",
                description="Invalid",
                metric_to_track="Metric",
                target="Target"
            )

    def test_insufficient_data_returns_exact_message(self):
        """
        If insufficient data exists (e.g. 0 sessions), returns:
        'Not enough data to create a personalized task.'
        """
        res = self.engine.create_tasks_from_history(game="Valorant")
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.message, "Not enough data to create a personalized task.")
        self.assertEqual(len(res.tasks), 0)

    def test_task_creation_from_historical_evidence(self):
        """
        Verifies task creation derived strictly from factual evidence across stored sessions:
        - Session 18 and Session 21 contain positioning errors.
        - Resulting positioning task correctly references Session 18 and Session 21.
        """
        # Seed Session 18 with positioning mistake
        s18 = Session(
            session_id="18",
            game="Valorant",
            map="Ascent",
            kills=14,
            deaths=12,
            player_notes="Repeated deaths from poor positioning at B Main choke.",
            timeline=[
                TimelineEvent(
                    timestamp_or_round="Round 7",
                    event_type="death",
                    description="Caught in bad angle without cover.",
                    impact="negative",
                    tilt_indicator=4
                )
            ]
        )
        # Seed Session 21 with positioning mistake
        s21 = Session(
            session_id="21",
            game="Valorant",
            map="Ascent",
            kills=16,
            deaths=14,
            player_notes="Positioning errors cost rounds, ego-peeking corner.",
            timeline=[
                TimelineEvent(
                    timestamp_or_round="Round 14",
                    event_type="death",
                    description="Ego-peeked corner without flash.",
                    impact="negative",
                    tilt_indicator=6
                )
            ]
        )
        self.storage.create_session(s18)
        self.storage.create_session(s21)

        res = self.engine.create_tasks_from_history(game="Valorant", category="positioning")

        self.assertEqual(res.status, "success")
        self.assertGreater(len(res.tasks), 0)
        pos_task = res.tasks[0]
        self.assertEqual(pos_task.category, "positioning")
        self.assertEqual(pos_task.objective, "Improve crosshair placement")
        self.assertEqual(pos_task.metric_to_track, "Deaths caused by poor positioning")
        self.assertEqual(pos_task.target, "Reduce repeated positioning mistakes")
        self.assertIn("18", pos_task.evidence_session_ids)
        self.assertIn("21", pos_task.evidence_session_ids)

    def test_do_not_invent_weaknesses(self):
        """
        If a player has excellent aim (e.g. 45% headshot rate), the engine
        must NOT invent an aim weakness task.
        """
        # Session with high headshot % and no positioning notes
        flawless_aim_session = Session(
            session_id="flawless-aim-1",
            game="Valorant",
            map="Haven",
            kills=25,
            deaths=5,
            result="Win",
            performance_metrics={"headshot_pct": 45.0, "accuracy": 42.0},
            player_notes="Clean crosshair snaps all game."
        )
        self.storage.create_session(flawless_aim_session)

        # When requesting aim tasks specifically:
        res = self.engine.create_tasks_from_history(game="Valorant", category="aim")
        # Since aim was excellent, no aim weakness task should be generated
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.message, INSUFFICIENT_DATA_MSG)
        self.assertEqual(len(res.tasks), 0)

    def test_do_not_claim_causation(self):
        """
        Tasks must not claim causation (e.g. 'bad aim caused your loss').
        Phrasing must remain observational and action-oriented.
        """
        s = Session(
            session_id="s-tilt-1",
            game="Valorant",
            kills=10,
            deaths=15,
            result="Defeat",
            timeline=[
                TimelineEvent(
                    timestamp_or_round="Round 12",
                    event_type="tilt",
                    description="Tilt forced aggressive push.",
                    impact="negative",
                    tilt_indicator=8
                )
            ]
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Valorant")
        self.assertEqual(res.status, "success")
        for task in res.tasks:
            text = (task.objective + " " + task.description + " " + task.target).lower()
            self.assertNotIn("caused you to lose", text)
            self.assertNotIn("is why you failed", text)
            self.assertNotIn("responsible for your defeat", text)

    def test_persistence_and_status_transitions(self):
        """
        Tests task persistence in SQLite and updating status:
        pending -> in_progress -> completed.
        """
        task = GamingTask(
            task_id="task-persisted-101",
            game="Valorant",
            category="combat",
            objective="Improve isolated 1v1 duel trade conversion",
            description="Focus on taking fights with utility assistance.",
            duration="15 minutes",
            metric_to_track="Isolated duel win rate",
            target="Achieve positive trade differential",
            evidence_session_ids=["10"],
            status="pending"
        )
        saved = self.engine.save_task(task)
        self.assertEqual(saved.task_id, "task-persisted-101")

        # Retrieve
        fetched = self.engine.get_task_by_id("task-persisted-101")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.status, "pending")

        # Update status -> in_progress
        updated = self.engine.update_task_status("task-persisted-101", "in_progress")
        self.assertEqual(updated.status, "in_progress")

        # Update status -> completed
        completed = self.engine.update_task_status("task-persisted-101", "completed")
        self.assertEqual(completed.status, "completed")

    def test_rest_api_tasks_endpoints(self):
        """
        Tests Fast API endpoints:
        - POST /api/tasks/generate
        - GET /api/tasks
        - GET /api/tasks/{task_id}
        - PATCH /api/tasks/{task_id}/status
        """
        # 1. Seed a session into database
        self.client.post("/api/sessions", json={
            "session_id": "api-sess-1",
            "game": "Valorant",
            "map": "Haven",
            "kills": 12,
            "deaths": 18,
            "result": "Defeat",
            "player_notes": "Positioning errors led to multiple early deaths on C Long.",
            "performance_metrics": {"first_deaths": 5}
        })

        # 2. POST /api/tasks/generate
        res_gen = self.client.post("/api/tasks/generate", json={"game": "Valorant"})
        self.assertEqual(res_gen.status_code, 200)
        data = res_gen.json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["total_tasks"], 0)
        task_id = data["tasks"][0]["task_id"]

        # 3. GET /api/tasks
        res_list = self.client.get("/api/tasks?game=Valorant")
        self.assertEqual(res_list.status_code, 200)
        tasks_list = res_list.json()
        self.assertTrue(any(t["task_id"] == task_id for t in tasks_list))

        # 4. GET /api/tasks/{task_id}
        res_get = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["task_id"], task_id)

        # 5. PATCH /api/tasks/{task_id}/status
        res_patch = self.client.patch(f"/api/tasks/{task_id}/status", json={"status": "in_progress"})
        self.assertEqual(res_patch.status_code, 200)
        self.assertEqual(res_patch.json()["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()
