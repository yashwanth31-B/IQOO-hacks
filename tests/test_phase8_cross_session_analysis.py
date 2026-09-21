import unittest
import os
import tempfile
from fastapi.testclient import TestClient

from app.models import Session, CrossSessionAnalysisResult
from app.session_storage import SessionStorage
from app.cross_session_analyzer import CrossSessionAnalyzer, NOT_ENOUGH_DATA
from app.main import app


class TestPhase8CrossSessionAnalysis(unittest.TestCase):
    """
    Unit and integration tests for Phase 8: Cross-Session Analysis.
    Verifies:
    1. Core questions:
       - Am I improving?
       - What changed between my best and worst sessions?
       - Which map do I perform best on?
       - Which configuration produces better results?
       - How does session duration relate to performance?
    2. Strict distinction:
       - FACT
       - PATTERN
       - AI INTERPRETATION
    3. Causation guard (no false causation claimed).
    4. Evidence session IDs returned.
    5. Four required test scenarios:
       - increasing performance
       - decreasing performance
       - inconsistent performance
       - insufficient data (0 and 1 session)
    6. REST API endpoints (/api/analysis/cross-session)
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase8.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.analyzer = CrossSessionAnalyzer(storage=self.storage)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------
    # SCENARIO 1: INCREASING PERFORMANCE
    # -----------------------------------------------------------------
    def test_scenario_increasing_performance(self):
        """Increasing performance (e.g. K/D: 1.0 -> 1.3 -> 1.6 -> 1.9)."""
        sessions = [
            {"session_id": "1", "kills": 10, "deaths": 10, "kd_ratio": 1.0, "started_at": "2026-09-01T10:00:00"},
            {"session_id": "2", "kills": 13, "deaths": 10, "kd_ratio": 1.3, "started_at": "2026-09-02T10:00:00"},
            {"session_id": "3", "kills": 16, "deaths": 10, "kd_ratio": 1.6, "started_at": "2026-09-03T10:00:00"},
            {"session_id": "4", "kills": 19, "deaths": 10, "kd_ratio": 1.9, "started_at": "2026-09-04T10:00:00"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.analyzer.analyze_improvement()

        self.assertEqual(res.status, "determined")
        self.assertEqual(res.metrics_summary["trend"], "increasing")
        # Check FACT distinction
        self.assertTrue(len(res.facts) >= 4)
        self.assertTrue(any("Session #1" in f for f in res.facts))
        # Check PATTERN distinction
        self.assertIn("increased", res.pattern.lower())
        # Check AI INTERPRETATION distinction
        self.assertIn("improving", res.interpretation.lower())
        # Check evidence session IDs
        self.assertEqual(res.evidence_session_ids, ["1", "2", "3", "4"])

    # -----------------------------------------------------------------
    # SCENARIO 2: DECREASING PERFORMANCE
    # -----------------------------------------------------------------
    def test_scenario_decreasing_performance(self):
        """Decreasing performance (e.g. K/D: 2.0 -> 1.6 -> 1.2 -> 0.8)."""
        sessions = [
            {"session_id": "1", "kills": 20, "deaths": 10, "kd_ratio": 2.0, "started_at": "2026-09-01T10:00:00"},
            {"session_id": "2", "kills": 16, "deaths": 10, "kd_ratio": 1.6, "started_at": "2026-09-02T10:00:00"},
            {"session_id": "3", "kills": 12, "deaths": 10, "kd_ratio": 1.2, "started_at": "2026-09-03T10:00:00"},
            {"session_id": "4", "kills": 8, "deaths": 10, "kd_ratio": 0.8, "started_at": "2026-09-04T10:00:00"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.analyzer.analyze_improvement()

        self.assertEqual(res.status, "determined")
        self.assertEqual(res.metrics_summary["trend"], "decreasing")
        self.assertTrue(len(res.facts) >= 4)
        self.assertIn("declined", res.pattern.lower())
        # Verify strict causation guard in interpretation
        self.assertIn("does not conclusively prove", res.interpretation)
        self.assertEqual(res.evidence_session_ids, ["1", "2", "3", "4"])

    # -----------------------------------------------------------------
    # SCENARIO 3: INCONSISTENT PERFORMANCE
    # -----------------------------------------------------------------
    def test_scenario_inconsistent_performance(self):
        """Inconsistent performance with alternating volatility (e.g. 1.8 -> 0.5 -> 1.9 -> 0.6 -> 1.7)."""
        sessions = [
            {"session_id": "1", "kills": 18, "deaths": 10, "kd_ratio": 1.8, "started_at": "2026-09-01T10:00:00"},
            {"session_id": "2", "kills": 5, "deaths": 10, "kd_ratio": 0.5, "started_at": "2026-09-02T10:00:00"},
            {"session_id": "3", "kills": 19, "deaths": 10, "kd_ratio": 1.9, "started_at": "2026-09-03T10:00:00"},
            {"session_id": "4", "kills": 6, "deaths": 10, "kd_ratio": 0.6, "started_at": "2026-09-04T10:00:00"},
            {"session_id": "5", "kills": 17, "deaths": 10, "kd_ratio": 1.7, "started_at": "2026-09-05T10:00:00"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.analyzer.analyze_improvement()

        self.assertEqual(res.status, "determined")
        self.assertEqual(res.metrics_summary["trend"], "inconsistent")
        self.assertIn("variance", res.pattern.lower())
        self.assertIn("inconsistent", res.interpretation.lower())
        self.assertEqual(res.evidence_session_ids, ["1", "2", "3", "4", "5"])

    # -----------------------------------------------------------------
    # SCENARIO 4: INSUFFICIENT DATA (0 and 1 session)
    # -----------------------------------------------------------------
    def test_scenario_insufficient_data_zero_sessions(self):
        """0 sessions must return 'Not enough data to determine this.' with empty evidence IDs."""
        questions = [
            "Am I improving?",
            "What changed between my best and worst sessions?",
            "Which map do I perform best on?",
            "Which configuration produces better results?",
            "How does session duration relate to performance?"
        ]
        for q in questions:
            res = self.analyzer.analyze_question(q)
            self.assertEqual(res.status, "insufficient_data", f"Failed for question: {q}")
            self.assertEqual(res.pattern, NOT_ENOUGH_DATA)
            self.assertEqual(res.interpretation, NOT_ENOUGH_DATA)
            self.assertEqual(res.facts, [])
            self.assertEqual(res.evidence_session_ids, [])

    def test_scenario_insufficient_data_single_session(self):
        """RULE: Never claim a pattern from a single session. 1 session must return 'Not enough data to determine this.'"""
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

        questions = [
            "Am I improving?",
            "What changed between my best and worst sessions?",
            "Which map do I perform best on?",
            "Which configuration produces better results?",
            "How does session duration relate to performance?"
        ]
        for q in questions:
            res = self.analyzer.analyze_question(q)
            self.assertEqual(res.status, "insufficient_data", f"Single-session rule violated for: {q}")
            self.assertEqual(res.pattern, NOT_ENOUGH_DATA)
            self.assertEqual(res.interpretation, NOT_ENOUGH_DATA)
            self.assertEqual(res.evidence_session_ids, [])

    # -----------------------------------------------------------------
    # QUESTION TESTS: BEST VS WORST SESSIONS
    # -----------------------------------------------------------------
    def test_question_best_vs_worst(self):
        """What changed between my best and worst sessions?"""
        self.storage.create_session({
            "session_id": "12",
            "game": "Valorant",
            "map": "Fracture",
            "configuration": "Vandal configuration",
            "duration": 45,
            "kills": 6,
            "deaths": 14,
            "kd_ratio": 0.43,
            "result": "Defeat"
        })
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

        res = self.analyzer.analyze_best_vs_worst()

        self.assertEqual(res.status, "determined")
        self.assertEqual(res.metrics_summary["best_session_id"], "18")
        self.assertEqual(res.metrics_summary["worst_session_id"], "12")
        # Check FACT
        self.assertTrue(len(res.facts) >= 2)
        self.assertIn("18", res.facts[0])
        self.assertIn("12", res.facts[1])
        # Check PATTERN
        self.assertIn("Ascent", res.pattern)
        self.assertIn("Fracture", res.pattern)
        # Check CAUSATION GUARD in interpretation
        self.assertIn("does not prove", res.interpretation)
        self.assertEqual(set(res.evidence_session_ids), {"18", "12"})

    # -----------------------------------------------------------------
    # QUESTION TESTS: MAP PERFORMANCE
    # -----------------------------------------------------------------
    def test_question_map_performance(self):
        """Which map do I perform best on?"""
        self.storage.create_session({"session_id": "14", "map": "Ascent", "kd_ratio": 1.7, "result": "Win"})
        self.storage.create_session({"session_id": "18", "map": "Ascent", "kd_ratio": 1.8, "result": "Win"})
        self.storage.create_session({"session_id": "21", "map": "Haven", "kd_ratio": 0.9, "result": "Defeat"})

        res = self.analyzer.analyze_map_performance()

        self.assertEqual(res.status, "determined")
        self.assertEqual(res.metrics_summary["best_map"], "Ascent")
        # Check FACT
        self.assertTrue(any("Ascent:" in f for f in res.facts))
        self.assertTrue(any("Haven:" in f for f in res.facts))
        # Check PATTERN
        self.assertIn("Ascent", res.pattern)
        # Check CAUSATION GUARD in interpretation
        self.assertIn("does not establish map layout as the sole cause", res.interpretation)
        self.assertIn("14", res.evidence_session_ids)
        self.assertIn("18", res.evidence_session_ids)

    # -----------------------------------------------------------------
    # QUESTION TESTS: CONFIGURATION PERFORMANCE & CAUSATION GUARD
    # -----------------------------------------------------------------
    def test_question_configuration_performance_causation_guard(self):
        """Which configuration produces better results? Verifies causation guard."""
        self.storage.create_session({"session_id": "14", "configuration": "Phantom configuration", "kd_ratio": 1.7})
        self.storage.create_session({"session_id": "18", "configuration": "Phantom configuration", "kd_ratio": 1.8})
        self.storage.create_session({"session_id": "12", "configuration": "Vandal configuration", "kd_ratio": 0.5})

        res = self.analyzer.analyze_configuration_performance()

        self.assertEqual(res.status, "determined")
        self.assertEqual(res.metrics_summary["best_configuration"], "Phantom configuration")
        # Check FACT
        self.assertTrue(len(res.facts) >= 2)
        # Check PATTERN
        self.assertIn("Phantom configuration", res.pattern)
        # Check CAUSATION GUARD: "Do not say a configuration caused better performance..."
        self.assertIn("does not prove that the loadout itself caused superior performance", res.interpretation)
        self.assertTrue(len(res.evidence_session_ids) >= 3)

    # -----------------------------------------------------------------
    # QUESTION TESTS: DURATION VS PERFORMANCE
    # -----------------------------------------------------------------
    def test_question_duration_vs_performance(self):
        """How does session duration relate to performance?"""
        self.storage.create_session({"session_id": "1", "duration": 45, "kd_ratio": 1.6})
        self.storage.create_session({"session_id": "2", "duration": 60, "kd_ratio": 1.7})
        self.storage.create_session({"session_id": "3", "duration": 110, "kd_ratio": 0.8})

        res = self.analyzer.analyze_duration_vs_performance()

        self.assertEqual(res.status, "determined")
        self.assertIn("Sessions under 90 minutes", res.pattern)
        # Causation guard
        self.assertIn("correlation rather than conclusive causation", res.interpretation)
        self.assertEqual(set(res.evidence_session_ids), {"1", "2", "3"})

    # -----------------------------------------------------------------
    # REST API TESTS
    # -----------------------------------------------------------------
    def test_api_cross_session_analysis(self):
        """Verify POST and GET /api/analysis/cross-session endpoints."""
        self.storage.create_session({"session_id": "1", "kd_ratio": 1.0, "started_at": "2026-09-01T10:00:00"})
        self.storage.create_session({"session_id": "2", "kd_ratio": 1.8, "started_at": "2026-09-02T10:00:00"})

        # POST endpoint
        res_post = self.client.post("/api/analysis/cross-session", json={"question": "Am I improving?"})
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.json()
        self.assertIn("facts", data_post)
        self.assertIn("pattern", data_post)
        self.assertIn("interpretation", data_post)
        self.assertIn("evidence_session_ids", data_post)

        # GET endpoint
        res_get = self.client.get("/api/analysis/cross-session?question=Which%20map%20do%20I%20perform%20best%20on%3F")
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.json()
        self.assertIn("pattern", data_get)


if __name__ == "__main__":
    unittest.main()
