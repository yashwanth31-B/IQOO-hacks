import unittest
import os
import tempfile
from fastapi.testclient import TestClient

from app.models import Session, StructuredQuery, NaturalLanguageSearchRequest, NaturalLanguageSearchResponse
from app.session_storage import SessionStorage
from app.natural_language_search import NaturalLanguageSearchEngine, NOT_ENOUGH_DATA
from app.main import app


class TestPhase7NaturalLanguageSearch(unittest.TestCase):
    """
    Unit and integration tests for Phase 7: Natural Language Search.
    Verifies:
    1. Structured Query Generation (intent, filters, sort, limit, required_metrics, comparison_needed)
    2. Intent 1: best_session
    3. Intent 2: worst_session
    4. Intent 3: recent_performance
    5. Intent 4: map_performance
    6. Intent 5: configuration_performance
    7. Intent 6: improvement
    8. Intent 7: session_duration
    9. Intent 8: performance_comparison
    10. Insufficient data handling: "Not enough data to determine this."
    11. REST API endpoints (/api/search/natural-language and /api/nl-search)
    """

    def setUp(self):
        # Create isolated temp database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase7.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.search_engine = NaturalLanguageSearchEngine(storage=self.storage)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _seed_standard_sessions(self):
        """Helper to seed a variety of multi-session gaming telemetry."""
        sessions = [
            {
                "session_id": "12",
                "game": "Valorant",
                "map": "Fracture",
                "configuration": "Vandal configuration",
                "duration": 45,
                "score": "8/13",
                "kills": 6,
                "deaths": 14,
                "assists": 2,
                "result": "Defeat",
                "started_at": "2026-09-15T18:00:00"
            },
            {
                "session_id": "14",
                "game": "Valorant",
                "map": "Ascent",
                "configuration": "Phantom configuration",
                "duration": 65,
                "score": "13/9",
                "kills": 20,
                "deaths": 12,
                "assists": 5,
                "result": "Win",
                "started_at": "2026-09-16T19:00:00"
            },
            {
                "session_id": "18",
                "game": "Valorant",
                "map": "Ascent",
                "configuration": "Phantom configuration",
                "duration": 72,
                "score": "18/10",
                "kills": 18,
                "deaths": 10,
                "assists": 6,
                "result": "Win",
                "started_at": "2026-09-17T20:00:00"
            },
            {
                "session_id": "21",
                "game": "Valorant",
                "map": "Haven",
                "configuration": "Phantom configuration",
                "duration": 105,
                "score": "11/13",
                "kills": 14,
                "deaths": 16,
                "assists": 4,
                "result": "Defeat",
                "started_at": "2026-09-18T21:00:00"
            }
        ]
        for s in sessions:
            self.storage.create_session(s)

    # -----------------------------------------------------------------
    # STRUCTURED QUERY GENERATION TESTS
    # -----------------------------------------------------------------
    def test_structured_query_generation(self):
        """Verify StructuredQuery attributes: intent, filters, sort, limit, required_metrics, comparison_needed."""
        # Query: When did I perform best?
        q1 = self.search_engine.parse_query_to_structured("When did I perform best?")
        self.assertEqual(q1.intent, "best_session")
        self.assertIn("kd_ratio", q1.sort)
        self.assertEqual(q1.limit, 1)
        self.assertFalse(q1.comparison_needed)
        self.assertIn("kd_ratio", q1.required_metrics)

        # Query: What was my worst session?
        q2 = self.search_engine.parse_query_to_structured("What was my worst session?")
        self.assertEqual(q2.intent, "worst_session")
        self.assertIn("ASC", q2.sort)
        self.assertEqual(q2.limit, 1)

        # Query: Which map do I perform best on?
        q3 = self.search_engine.parse_query_to_structured("Which map do I perform best on?")
        self.assertEqual(q3.intent, "map_performance")
        self.assertTrue(q3.comparison_needed)
        self.assertIn("map", q3.required_metrics)

        # Query: What configuration do I perform best with?
        q4 = self.search_engine.parse_query_to_structured("What configuration do I perform best with?")
        self.assertEqual(q4.intent, "configuration_performance")
        self.assertTrue(q4.comparison_needed)
        self.assertIn("configuration", q4.required_metrics)

        # Query: Am I improving?
        q5 = self.search_engine.parse_query_to_structured("Am I improving?")
        self.assertEqual(q5.intent, "improvement")
        self.assertTrue(q5.comparison_needed)

        # Query: Show me my recent performance.
        q6 = self.search_engine.parse_query_to_structured("Show me my recent performance.")
        self.assertEqual(q6.intent, "recent_performance")
        self.assertFalse(q6.comparison_needed)

    # -----------------------------------------------------------------
    # INTENT 1: BEST SESSION
    # -----------------------------------------------------------------
    def test_intent_best_session(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("When did I perform best?")

        self.assertEqual(res.structured_query.intent, "best_session")
        self.assertEqual(res.status, "answered")
        self.assertIn("Session #18", res.answer)
        self.assertIn("1.8", res.answer)
        self.assertEqual(res.evidence_session_ids, ["18"])
        self.assertNotEqual(res.answer, NOT_ENOUGH_DATA)

    # -----------------------------------------------------------------
    # INTENT 2: WORST SESSION
    # -----------------------------------------------------------------
    def test_intent_worst_session(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("What was my worst session?")

        self.assertEqual(res.structured_query.intent, "worst_session")
        self.assertEqual(res.status, "answered")
        self.assertIn("Session #12", res.answer)
        self.assertIn("0.4", res.answer)  # 6 kills / 14 deaths = 0.43 K/D
        self.assertEqual(res.evidence_session_ids, ["12"])
        self.assertNotEqual(res.answer, NOT_ENOUGH_DATA)

    # -----------------------------------------------------------------
    # INTENT 3: RECENT PERFORMANCE
    # -----------------------------------------------------------------
    def test_intent_recent_performance(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("Show me my recent performance.")

        self.assertEqual(res.structured_query.intent, "recent_performance")
        self.assertEqual(res.status, "answered")
        self.assertTrue(len(res.evidence_session_ids) >= 2)
        self.assertIn("win rate", res.answer)
        self.assertNotEqual(res.answer, NOT_ENOUGH_DATA)

    # -----------------------------------------------------------------
    # INTENT 4: MAP PERFORMANCE
    # -----------------------------------------------------------------
    def test_intent_map_performance(self):
        self._seed_standard_sessions()
        # General map query
        res = self.search_engine.search("Which map do I perform best on?")

        self.assertEqual(res.structured_query.intent, "map_performance")
        self.assertEqual(res.status, "answered")
        self.assertIn("Ascent", res.answer)
        self.assertTrue(any(sid in res.evidence_session_ids for sid in ["14", "18"]))

        # Specific map query
        res_specific = self.search_engine.search("How do I perform on Haven?")
        self.assertEqual(res_specific.structured_query.intent, "map_performance")
        self.assertIn("Haven", res_specific.answer)
        self.assertIn("21", res_specific.evidence_session_ids)

    # -----------------------------------------------------------------
    # INTENT 5: CONFIGURATION PERFORMANCE
    # -----------------------------------------------------------------
    def test_intent_configuration_performance(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("What configuration do I perform best with?")

        self.assertEqual(res.structured_query.intent, "configuration_performance")
        self.assertEqual(res.status, "answered")
        self.assertIn("Phantom configuration", res.answer)
        self.assertTrue(len(res.evidence_session_ids) >= 2)

    # -----------------------------------------------------------------
    # INTENT 6: IMPROVEMENT
    # -----------------------------------------------------------------
    def test_intent_improvement(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("Am I improving?")

        self.assertEqual(res.structured_query.intent, "improvement")
        self.assertEqual(res.status, "answered")
        self.assertTrue(len(res.evidence_session_ids) >= 2)
        self.assertTrue("improving" in res.answer or "consistent" in res.answer or "dipped" in res.answer)

    # -----------------------------------------------------------------
    # INTENT 7: SESSION DURATION
    # -----------------------------------------------------------------
    def test_intent_session_duration(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("How long are my sessions usually?")

        self.assertEqual(res.structured_query.intent, "session_duration")
        self.assertEqual(res.status, "answered")
        self.assertIn("minutes", res.answer)
        self.assertTrue(len(res.evidence_session_ids) >= 2)

    # -----------------------------------------------------------------
    # INTENT 8: PERFORMANCE COMPARISON
    # -----------------------------------------------------------------
    def test_intent_performance_comparison_two_sessions(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("Compare Session #18 and Session #14")

        self.assertEqual(res.structured_query.intent, "performance_comparison")
        self.assertEqual(res.status, "answered")
        self.assertIn("18", res.evidence_session_ids)
        self.assertIn("14", res.evidence_session_ids)
        self.assertIn("Session #18", res.answer)
        self.assertIn("Session #14", res.answer)

    def test_intent_performance_comparison_general(self):
        self._seed_standard_sessions()
        res = self.search_engine.search("How did my last session compare to previous sessions?")

        self.assertEqual(res.structured_query.intent, "performance_comparison")
        self.assertEqual(res.status, "answered")
        self.assertTrue(len(res.evidence_session_ids) >= 2)

    # -----------------------------------------------------------------
    # INSUFFICIENT DATA / HALLUCINATION PROTECTION TESTS
    # -----------------------------------------------------------------
    def test_zero_sessions_returns_not_enough_data(self):
        """When 0 sessions exist in storage, every intent must return 'Not enough data to determine this.'"""
        queries = [
            "When did I perform best?",
            "What was my worst session?",
            "Show me my recent performance.",
            "Which map do I perform best on?",
            "What configuration do I perform best with?",
            "Am I improving?",
            "How long are my sessions usually?",
            "How did my last session compare to previous sessions?"
        ]
        for q in queries:
            res = self.search_engine.search(q)
            self.assertEqual(res.answer, NOT_ENOUGH_DATA, f"Failed for query: {q}")
            self.assertEqual(res.status, "insufficient_data")
            self.assertEqual(res.evidence_session_ids, [])

    def test_single_session_insufficient_for_improvement_and_comparison(self):
        """Improvement and comparison require multiple sessions."""
        self.storage.create_session({
            "session_id": "99",
            "game": "Valorant",
            "kills": 15,
            "deaths": 10,
            "kd_ratio": 1.5,
            "result": "Win"
        })

        res_improve = self.search_engine.search("Am I improving?")
        self.assertEqual(res_improve.answer, NOT_ENOUGH_DATA)
        self.assertEqual(res_improve.status, "insufficient_data")

        res_comp = self.search_engine.search("How did my last session compare to previous sessions?")
        self.assertEqual(res_comp.answer, NOT_ENOUGH_DATA)
        self.assertEqual(res_comp.status, "insufficient_data")

    def test_unknown_map_returns_not_enough_data(self):
        """Querying performance on an unplayed map must return 'Not enough data to determine this.'"""
        self._seed_standard_sessions()
        res = self.search_engine.search("How do I perform on Icebox?")
        self.assertEqual(res.answer, NOT_ENOUGH_DATA)
        self.assertEqual(res.status, "insufficient_data")

    # -----------------------------------------------------------------
    # REST API ENDPOINT TESTS
    # -----------------------------------------------------------------
    def test_api_search_endpoints(self):
        """Verify POST /api/search/natural-language and POST /api/nl-search endpoints."""
        payload = {"query": "When did I perform best?"}

        res1 = self.client.post("/api/search/natural-language", json=payload)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertIn("structured_query", data1)
        self.assertEqual(data1["structured_query"]["intent"], "best_session")
        self.assertIn("answer", data1)
        self.assertIn("evidence_session_ids", data1)

        res2 = self.client.post("/api/nl-search", json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["structured_query"]["intent"], "best_session")


if __name__ == "__main__":
    unittest.main()
