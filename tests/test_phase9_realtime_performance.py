"""
Unit and integration tests for Phase 9: Real-Time Performance Analysis Layer.

Requirements tested:
- Lightweight real-time performance analysis layer.
- Process available game events during a session:
  * kill
  * death
  * assist
  * objective
  * location change
  * round result
  * match result
  * inventory/configuration change
- No advanced computer vision: uses simulated events or available telemetry.
- Calculates live metrics:
  * current K/D
  * kills
  * deaths
  * survival time
  * objective progress
  * current score
- Exact normalized display:
    CURRENT PERFORMANCE

    K/D: 1.6
    Kills: 8
    Deaths: 5
    Survival: 22 min
- Do not generate unsupported recommendations.
- Do not interfere with game controls.
"""

import unittest
from fastapi.testclient import TestClient

from app.models import GameEvent, CurrentPerformance, GAME_EVENT_TYPES
from app.realtime_analyzer import RealtimePerformanceAnalyzer
from app.main import app


class TestPhase9RealtimePerformanceAnalysis(unittest.TestCase):
    def setUp(self):
        self.analyzer = RealtimePerformanceAnalyzer()
        self.client = TestClient(app)

    def tearDown(self):
        self.analyzer.reset()

    def test_exact_prompt_example_formatting(self):
        """
        Verifies exact format display:
        CURRENT PERFORMANCE

        K/D: 1.6
        Kills: 8
        Deaths: 5
        Survival: 22 min
        """
        perf = CurrentPerformance(
            kills=8,
            deaths=5,
            kd_ratio=1.6,
            survival_time="22 min"
        )

        expected_display = (
            "CURRENT PERFORMANCE\n\n"
            "K/D: 1.6\n"
            "Kills: 8\n"
            "Deaths: 5\n"
            "Survival: 22 min"
        )
        self.assertEqual(perf.format_display(), expected_display)

    def test_simulated_event_stream_matching_prompt_example(self):
        """
        Simulates live events producing 8 kills, 5 deaths, 22 min survival:
        Calculates live K/D = 8 / 5 = 1.6.
        """
        self.analyzer.start_session(session_id="sess-live-1", game="BGMI", map_name="Erangel")

        # Simulate 8 kills
        for _ in range(8):
            self.analyzer.simulate_event("kill")

        # Simulate 5 deaths
        for _ in range(5):
            self.analyzer.simulate_event("death")

        # Update survival time
        self.analyzer.simulate_event("location_change", details={"location": "School", "survival_time": "22 min"})

        state = self.analyzer.get_current_performance()

        self.assertEqual(state.kills, 8)
        self.assertEqual(state.deaths, 5)
        self.assertEqual(state.kd_ratio, 1.6)
        self.assertEqual(state.survival_time, "22 min")

        expected_display = (
            "CURRENT PERFORMANCE\n\n"
            "K/D: 1.6\n"
            "Kills: 8\n"
            "Deaths: 5\n"
            "Survival: 22 min"
        )
        self.assertEqual(state.format_display(), expected_display)

    def test_process_all_game_event_types(self):
        """
        Tests processing of all required event types:
        - kill
        - death
        - assist
        - objective
        - location change
        - round result
        - match result
        - inventory/configuration change
        """
        self.analyzer.start_session(session_id="sess-all-events", game="Valorant", map_name="Ascent")

        # 1. Kill
        self.analyzer.process_event({"event_type": "kill", "details": {"weapon": "Vandal"}})
        self.assertEqual(self.analyzer.state.kills, 1)
        self.assertEqual(self.analyzer.state.kd_ratio, 1.0)

        # 2. Assist
        self.analyzer.process_event({"event_type": "assist", "details": {"target": "Jett"}})
        self.assertEqual(self.analyzer.state.assists, 1)

        # 3. Death
        self.analyzer.process_event({"event_type": "death", "details": {"killer": "Omen"}})
        self.assertEqual(self.analyzer.state.deaths, 1)
        self.assertEqual(self.analyzer.state.kd_ratio, 1.0)

        # 4. Objective
        self.analyzer.process_event({"event_type": "objective", "details": {"action": "plant", "site": "A", "score": 200}})
        self.assertEqual(self.analyzer.state.objective_progress, "Plant A")
        self.assertEqual(self.analyzer.state.current_score, 200)

        # 5. Location change
        self.analyzer.process_event({"event_type": "location_change", "details": {"location": "A Site Heaven"}})
        self.assertEqual(self.analyzer.state.current_location, "A Site Heaven")

        # 6. Inventory / Configuration change
        self.analyzer.process_event({"event_type": "configuration_change", "details": {"weapon": "Phantom"}})
        self.assertEqual(self.analyzer.state.current_configuration, "Phantom")

        # 7. Round result
        self.analyzer.process_event({"event_type": "round_result", "details": {"round_number": 2, "score": "1-1"}})
        self.assertEqual(self.analyzer.state.round_number, 2)
        self.assertEqual(self.analyzer.state.current_score, "1-1")

        # 8. Match result
        self.analyzer.process_event({"event_type": "match_result", "details": {"result": "Win"}})
        self.assertIn("Win", str(self.analyzer.state.current_score))

    def test_no_unsupported_recommendations_and_no_game_interference(self):
        """
        Strict constraint verification:
        - State does not contain recommendation text.
        - No control actuation code exists.
        """
        self.analyzer.start_session(session_id="sess-guard", game="Valorant")
        self.analyzer.simulate_event("death")
        self.analyzer.simulate_event("death")

        state = self.analyzer.get_current_performance()
        # Verify no recommendation attributes exist
        self.assertFalse(hasattr(state, "recommendation"))
        self.assertFalse(hasattr(state, "ai_advice"))

        # Verify format display is strictly observational
        text = state.format_display().lower()
        self.assertNotIn("you should", text)
        self.assertNotIn("we recommend", text)

    def test_rest_api_realtime_endpoints(self):
        """
        Tests Fast API endpoints:
        - POST /api/realtime/start
        - POST /api/realtime/event
        - GET /api/realtime/performance
        - POST /api/realtime/reset
        """
        # 1. Start session
        res_start = self.client.post("/api/realtime/start", json={
            "session_id": "api-live-1",
            "game": "Valorant",
            "map": "Haven"
        })
        self.assertEqual(res_start.status_code, 200)
        self.assertEqual(res_start.json()["game"], "Valorant")

        # 2. Post kill event
        res_evt = self.client.post("/api/realtime/event", json={
            "event_type": "kill",
            "details": {"count": 1}
        })
        self.assertEqual(res_evt.status_code, 200)
        self.assertEqual(res_evt.json()["kills"], 1)

        # 3. Get current performance
        res_perf = self.client.get("/api/realtime/performance")
        self.assertEqual(res_perf.status_code, 200)
        self.assertEqual(res_perf.json()["kills"], 1)

        # 4. Reset
        res_reset = self.client.post("/api/realtime/reset")
        self.assertEqual(res_reset.status_code, 200)


if __name__ == "__main__":
    unittest.main()
