"""
Unit and integration tests for Phase 6: Generic Gaming Performance Engine.

Requirements tested:
- Calculate measurable performance from stored session data.
- Common metrics: K/D, win rate, survival duration, score efficiency, kills per minute,
  deaths per minute, assists, accuracy (when available), damage (when available),
  objective performance (when available).
- Missing data handling: never estimate missing metrics; return "Not enough data."
- Exact normalized Performance Report display format:
    Performance
    K/D: 1.8
    Kills: 18
    Deaths: 10
    Duration: 72 min
    Result: Win
- Game-specific extensible metrics.
- No recommendation generation yet (Phase 6 boundary).
"""

import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from app.models import Session, PerformanceReport
from app.session_storage import SessionStorage
from app.performance_engine import GamingPerformanceEngine, parse_duration_minutes, format_duration_display
from app.main import app


class TestPhase6GamingPerformanceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_perf.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.engine = GamingPerformanceEngine(storage=self.storage)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_prompt_example_formatting(self):
        """
        Verify exact normalized report formatting specified in prompt:
        Performance
        K/D: 1.8
        Kills: 18
        Deaths: 10
        Duration: 72 min
        Result: Win
        """
        session_data = {
            "session_id": "test-exact-001",
            "game": "Valorant",
            "map": "Ascent",
            "kills": 18,
            "deaths": 10,
            "duration": "72 min",
            "result": "Win"
        }
        report = self.engine.calculate_session_performance(session_data)

        self.assertEqual(report.kills, 18)
        self.assertEqual(report.deaths, 10)
        self.assertEqual(report.kd_ratio, 1.8)
        self.assertEqual(report.duration_display, "72 min")
        self.assertEqual(report.result, "Win")

        expected_display = (
            "Performance\n"
            "K/D: 1.8\n"
            "Kills: 18\n"
            "Deaths: 10\n"
            "Duration: 72 min\n"
            "Result: Win"
        )
        self.assertEqual(report.format_display(), expected_display)

    def test_missing_data_returns_not_enough_data_without_estimating(self):
        """
        Strict requirement:
        If accuracy is unavailable: Do not estimate accuracy. Return 'Not enough data.'
        If damage is unavailable: Do not estimate damage. Return 'Not enough data.'
        """
        session_data = {
            "session_id": "test-no-acc",
            "game": "Valorant",
            "kills": 15,
            "deaths": 5
            # accuracy and damage completely absent
        }
        report = self.engine.calculate_session_performance(session_data)

        self.assertIsNone(report.accuracy)
        self.assertIsNone(report.damage)
        self.assertIsNone(report.objective_performance)

        # Must return explicitly "Not enough data."
        self.assertEqual(report.get_metric_display("accuracy"), "Not enough data.")
        self.assertEqual(report.get_metric_display("damage"), "Not enough data.")
        self.assertEqual(report.get_metric_display("objective_performance"), "Not enough data.")
        self.assertEqual(report.get_metric_display("survival_duration"), "Not enough data.")

        # Accuracy and damage must be listed in missing_metrics
        self.assertIn("accuracy", report.missing_metrics)
        self.assertIn("damage", report.missing_metrics)

    def test_kd_ratio_calculations(self):
        """
        Tests standard K/D, zero deaths handling (no ZeroDivisionError),
        and missing kills or deaths handling.
        """
        # 1. Normal K/D: 14 kills, 4 deaths = 3.5
        s1 = Session(game="Valorant", kills=14, deaths=4)
        r1 = self.engine.calculate_session_performance(s1)
        self.assertEqual(r1.kd_ratio, 3.5)

        # 2. Zero deaths: 8 kills, 0 deaths = 8.0
        s2 = Session(game="Valorant", kills=8, deaths=0)
        r2 = self.engine.calculate_session_performance(s2)
        self.assertEqual(r2.kd_ratio, 8.0)

        # 3. 0 kills, 0 deaths = 0.0
        s3 = Session(game="Valorant", kills=0, deaths=0)
        r3 = self.engine.calculate_session_performance(s3)
        self.assertEqual(r3.kd_ratio, 0.0)

        # 4. Missing deaths: cannot calculate K/D
        s4 = {"game": "Valorant", "kills": 10}
        r4 = self.engine.calculate_session_performance(s4)
        self.assertIsNone(r4.kd_ratio)
        self.assertEqual(r4.get_metric_display("kd_ratio"), "Not enough data.")

        # 5. Missing kills: cannot calculate K/D
        s5 = {"game": "Valorant", "deaths": 5}
        r5 = self.engine.calculate_session_performance(s5)
        self.assertIsNone(r5.kd_ratio)
        self.assertEqual(r5.get_metric_display("kd_ratio"), "Not enough data.")

    def test_win_rate_calculation(self):
        """Tests win rate logic for wins, losses, draws, and missing results."""
        # Win
        r_win = self.engine.calculate_session_performance({"game": "Valorant", "result": "Win"})
        self.assertEqual(r_win.win_rate, 100.0)

        # Victory
        r_vic = self.engine.calculate_session_performance({"game": "Valorant", "result": "Victory"})
        self.assertEqual(r_vic.win_rate, 100.0)

        # Loss
        r_loss = self.engine.calculate_session_performance({"game": "Valorant", "result": "Defeat"})
        self.assertEqual(r_loss.win_rate, 0.0)

        # Missing result -> Not enough data
        r_none = self.engine.calculate_session_performance({"game": "Valorant"})
        self.assertIsNone(r_none.win_rate)
        self.assertEqual(r_none.get_metric_display("win_rate"), "Not enough data.")

    def test_rate_metrics_kpm_dpm_score_efficiency(self):
        """
        Tests calculation of kills per minute (KPM), deaths per minute (DPM),
        and score efficiency.
        """
        session_data = {
            "game": "BGMI",
            "kills": 12,
            "deaths": 2,
            "duration": 24, # 24 minutes
            "score": "1200",
            "assists": 5
        }
        report = self.engine.calculate_session_performance(session_data)

        # 12 kills / 24 mins = 0.50 KPM
        self.assertEqual(report.kills_per_minute, 0.5)
        # 2 deaths / 24 mins = 0.08 DPM
        self.assertEqual(report.deaths_per_minute, 0.08)
        # 1200 score / 24 mins = 50.0 score efficiency
        self.assertEqual(report.score_efficiency, 50.0)
        self.assertEqual(report.assists, 5)

    def test_metrics_when_available_accuracy_damage_objective(self):
        """
        Tests that when telemetry contains accuracy, damage, or objective performance,
        they are correctly populated and formatted.
        """
        session_data = {
            "game": "Valorant",
            "kills": 20,
            "deaths": 12,
            "performance_metrics": {
                "accuracy": "38.5%",
                "damage": 2940,
                "objective_performance": {"plants": 3, "defuses": 2}
            }
        }
        report = self.engine.calculate_session_performance(session_data)

        self.assertEqual(report.accuracy, "38.5%")
        self.assertEqual(report.damage, 2940)
        self.assertEqual(report.get_metric_display("accuracy"), "38.5%")
        self.assertEqual(report.get_metric_display("damage"), "2940")
        self.assertIn("accuracy", report.available_metrics)
        self.assertIn("damage", report.available_metrics)
        self.assertIn("objective_performance", report.available_metrics)

    def test_extensible_game_specific_metrics(self):
        """
        Tests that extra game-specific telemetry is preserved and accessible.
        """
        session_data = {
            "game": "Chess",
            "performance_metrics": {
                "centipawn_loss": 18,
                "blunders": 0,
                "brilliant_moves": 2
            }
        }
        report = self.engine.calculate_session_performance(session_data)

        self.assertEqual(report.game_specific_metrics.get("centipawn_loss"), 18)
        self.assertEqual(report.game_specific_metrics.get("blunders"), 0)
        self.assertEqual(report.game_specific_metrics.get("brilliant_moves"), 2)
        self.assertEqual(report.get_metric_display("centipawn_loss"), "18")

    def test_storage_integration_calculate_by_id(self):
        """
        Verifies retrieving a session from persistent storage and calculating its report.
        """
        created = self.storage.create_session(
            Session(
                game="Free Fire MAX",
                map="Bermuda",
                kills=9,
                deaths=1,
                duration="15 min",
                result="1st"
            )
        )
        report = self.engine.calculate_session_by_id(created.session_id)

        self.assertEqual(report.game, "Free Fire MAX")
        self.assertEqual(report.map, "Bermuda")
        self.assertEqual(report.kills, 9)
        self.assertEqual(report.deaths, 1)
        self.assertEqual(report.kd_ratio, 9.0)
        self.assertEqual(report.win_rate, 100.0)

    def test_aggregate_performance_calculation(self):
        """
        Verifies aggregate calculation across multiple sessions.
        """
        s1 = Session(game="Valorant", kills=20, deaths=10, duration=30, result="Win", performance_metrics={"accuracy": 40.0, "damage": 2500})
        s2 = Session(game="Valorant", kills=10, deaths=10, duration=30, result="Loss", performance_metrics={"accuracy": 30.0, "damage": 1500})

        agg = self.engine.calculate_aggregate_performance([s1, s2], game="Valorant")

        # Total kills = 30, deaths = 20 -> K/D = 1.5
        self.assertEqual(agg.kills, 30)
        self.assertEqual(agg.deaths, 20)
        self.assertEqual(agg.kd_ratio, 1.5)
        # 1 win out of 2 -> 50.0%
        self.assertEqual(agg.win_rate, 50.0)
        # Total duration = 60 mins -> KPM = 30/60 = 0.5
        self.assertEqual(agg.kills_per_minute, 0.5)
        # Average accuracy = 35.0%
        self.assertEqual(agg.accuracy, 35.0)
        # Average damage = 2000.0
        self.assertEqual(agg.damage, 2000.0)

    def test_no_recommendations_generated(self):
        """
        Phase 6 constraint:
        Do not create recommendations yet.
        Ensure report does not contain advice or recommendation fields.
        """
        session_data = {
            "game": "Valorant",
            "kills": 5,
            "deaths": 15,
            "result": "Loss"
        }
        report = self.engine.calculate_session_performance(session_data)
        # Verify no recommendations attribute or field exists
        self.assertFalse(hasattr(report, "recommendations"))
        self.assertFalse(hasattr(report, "ai_recommendation"))

    def test_rest_api_performance_endpoints(self):
        """
        Verifies Fast API endpoints:
        - POST /api/performance/calculate
        - GET /api/performance/session/{session_id}
        """
        # 1. POST /api/performance/calculate
        res = self.client.post("/api/performance/calculate", json={
            "game": "Valorant",
            "kills": 18,
            "deaths": 10,
            "duration": "72 min",
            "result": "Win"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["kd_ratio"], 1.8)
        self.assertEqual(data["kills"], 18)
        self.assertEqual(data["deaths"], 10)
        self.assertEqual(data["duration_display"], "72 min")
        self.assertEqual(data["result"], "Win")

        # 2. GET /api/performance/aggregate
        res_agg = self.client.get("/api/performance/aggregate")
        self.assertEqual(res_agg.status_code, 200)


if __name__ == "__main__":
    unittest.main()
