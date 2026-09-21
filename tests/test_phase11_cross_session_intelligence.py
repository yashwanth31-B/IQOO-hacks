import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from app.models import Session, CrossSessionIntelligenceResponse
from app.session_storage import SessionStorage
from app.cross_session_intelligence import (
    CrossSessionIntelligenceEngine,
    OptimizedSessionRetriever,
    NOT_ENOUGH_DATA
)
from app.main import app


class TestPhase11CrossSessionIntelligence(unittest.TestCase):
    """
    Unit and integration tests for Phase 11: Cross-Session Intelligence.
    
    Verifies:
    1. Support for all 8 analytical questions:
       - "When did I perform best?"
       - "What changed?"
       - "Am I improving?"
       - "Which map has my strongest recorded performance?"
       - "Which configuration has better recorded results?"
       - "How long are my strongest sessions?"
       - "What mistakes keep repeating?"
       - "What am I improving?"
    2. Exact four-part response structure:
       - ANSWER
       - EVIDENCE
       - INSIGHT
       - RECOMMENDATION
    3. Every answer references stored sessions (evidence_session_ids).
    4. Statistics are calculated strictly from stored data without invention.
    5. Causation guard is strictly enforced in insights.
    6. Insufficient data yields: "Not enough data to determine this."
    7. Retrieval optimization ensures AI does not receive entire match history.
    8. REST API endpoints (/api/intelligence/ask).
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase11.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.retriever = OptimizedSessionRetriever(self.storage)
        self.engine = CrossSessionIntelligenceEngine(storage=self.storage, retriever=self.retriever)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------
    # 1. INSUFFICIENT DATA TESTS (0 and 1 session)
    # -----------------------------------------------------------------
    def test_insufficient_data_empty_db(self):
        """0 sessions must return 'Not enough data to determine this.' for all questions."""
        questions = [
            "When did I perform best?",
            "What changed?",
            "Am I improving?",
            "Which map has my strongest recorded performance?",
            "Which configuration has better recorded results?",
            "How long are my strongest sessions?",
            "What mistakes keep repeating?",
            "What am I improving?"
        ]
        for q in questions:
            res = self.engine.ask(q)
            self.assertEqual(res.status, "insufficient_data")
            self.assertEqual(res.answer, NOT_ENOUGH_DATA)
            self.assertEqual(res.insight, NOT_ENOUGH_DATA)
            self.assertEqual(res.evidence_session_ids, [])
            display = res.format_display()
            self.assertIn("ANSWER:\nNot enough data to determine this.", display)
            self.assertIn("EVIDENCE:\nNot enough data to determine this.", display)
            self.assertIn("INSIGHT:\nNot enough data to determine this.", display)
            self.assertIn("RECOMMENDATION:", display)

    def test_insufficient_data_single_session(self):
        """Never determine cross-session intelligence from a single session."""
        self.storage.create_session({
            "session_id": "solo_1",
            "game": "BGMI",
            "map": "Erangel",
            "configuration": "M416 + 6x",
            "duration": 25,
            "kills": 8,
            "deaths": 2,
            "kd_ratio": 4.0,
            "started_at": "2026-09-10T14:00:00"
        })
        res = self.engine.ask("When did I perform best?")
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.answer, NOT_ENOUGH_DATA)

        res2 = self.engine.ask("Am I improving?")
        self.assertEqual(res2.status, "insufficient_data")
        self.assertEqual(res2.answer, NOT_ENOUGH_DATA)

    # -----------------------------------------------------------------
    # 2. QUESTION 1: "When did I perform best?"
    # -----------------------------------------------------------------
    def test_when_did_i_perform_best(self):
        sessions = [
            {"session_id": "s1", "game": "BGMI", "map": "Erangel", "configuration": "M416", "duration": 20, "kills": 4, "deaths": 4, "kd_ratio": 1.0, "started_at": "2026-09-01T10:00:00"},
            {"session_id": "s2", "game": "BGMI", "map": "Erangel", "configuration": "M416", "duration": 25, "kills": 12, "deaths": 2, "kd_ratio": 6.0, "started_at": "2026-09-02T15:30:00"},
            {"session_id": "s3", "game": "BGMI", "map": "Miramar", "configuration": "AKM", "duration": 18, "kills": 6, "deaths": 3, "kd_ratio": 2.0, "started_at": "2026-09-03T11:00:00"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("When did I perform best?")

        self.assertEqual(res.status, "answered")
        self.assertIn("s2", res.answer)
        self.assertIn("6.00", res.answer)
        self.assertIn("15:30:00", res.answer)
        # Verify evidence references stored sessions
        self.assertTrue(any("Session #s2" in e for e in res.evidence))
        self.assertIn("s2", res.evidence_session_ids)
        # Verify causation guard
        self.assertIn("correlation rather than", res.insight.lower())
        # Verify 4-part structure
        display = res.format_display()
        self.assertIn("ANSWER:", display)
        self.assertIn("EVIDENCE:", display)
        self.assertIn("INSIGHT:", display)
        self.assertIn("RECOMMENDATION:", display)

    # -----------------------------------------------------------------
    # 3. QUESTION 2: "What changed?"
    # -----------------------------------------------------------------
    def test_what_changed(self):
        sessions = [
            {"session_id": "best_1", "game": "Valorant", "map": "Ascent", "configuration": "Vandal + Heavy", "duration": 35, "kills": 24, "deaths": 8, "kd_ratio": 3.0, "result": "Win"},
            {"session_id": "mid_1", "game": "Valorant", "map": "Bind", "configuration": "Phantom", "duration": 30, "kills": 14, "deaths": 12, "kd_ratio": 1.17, "result": "Loss"},
            {"session_id": "worst_1", "game": "Valorant", "map": "Icebox", "configuration": "Judge + Light", "duration": 15, "kills": 4, "deaths": 16, "kd_ratio": 0.25, "result": "Loss"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("What changed?")

        self.assertEqual(res.status, "answered")
        self.assertIn("best_1", res.answer)
        self.assertIn("worst_1", res.answer)
        self.assertIn("Ascent", res.answer)
        self.assertIn("Icebox", res.answer)
        # Verify evidence includes both boundary sessions
        self.assertTrue(any("Session #best_1" in e for e in res.evidence))
        self.assertTrue(any("Session #worst_1" in e for e in res.evidence))
        self.assertEqual(set(res.evidence_session_ids), {"best_1", "worst_1"})
        # Causation guard
        self.assertIn("does not prove", res.insight.lower())

    # -----------------------------------------------------------------
    # 4. QUESTION 3: "Am I improving?"
    # -----------------------------------------------------------------
    def test_am_i_improving_upward_trend(self):
        sessions = [
            {"session_id": "t1", "kills": 5, "deaths": 5, "kd_ratio": 1.0, "started_at": "2026-09-01T10:00:00"},
            {"session_id": "t2", "kills": 7, "deaths": 5, "kd_ratio": 1.4, "started_at": "2026-09-02T10:00:00"},
            {"session_id": "t3", "kills": 9, "deaths": 5, "kd_ratio": 1.8, "started_at": "2026-09-03T10:00:00"},
            {"session_id": "t4", "kills": 12, "deaths": 5, "kd_ratio": 2.4, "started_at": "2026-09-04T10:00:00"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("Am I improving?")

        self.assertEqual(res.status, "answered")
        self.assertIn("Yes", res.answer)
        self.assertIn("upward", res.answer.lower())
        self.assertEqual(res.metrics_summary["trend"], "improving")
        self.assertEqual(len(res.evidence_session_ids), 4)
        self.assertIn("matchmaking", res.insight.lower())

    # -----------------------------------------------------------------
    # 5. QUESTION 4: "Which map has my strongest recorded performance?"
    # -----------------------------------------------------------------
    def test_which_map_strongest(self):
        sessions = [
            {"session_id": "m1", "map": "Erangel", "kills": 10, "deaths": 2, "kd_ratio": 5.0, "result": "Win"},
            {"session_id": "m2", "map": "Erangel", "kills": 8, "deaths": 2, "kd_ratio": 4.0, "result": "Win"},
            {"session_id": "m3", "map": "Miramar", "kills": 3, "deaths": 3, "kd_ratio": 1.0, "result": "Loss"},
            {"session_id": "m4", "map": "Miramar", "kills": 4, "deaths": 4, "kd_ratio": 1.0, "result": "Loss"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("Which map has my strongest recorded performance?")

        self.assertEqual(res.status, "answered")
        self.assertIn("Erangel", res.answer)
        self.assertIn("4.50", res.answer)  # (5.0 + 4.0) / 2
        self.assertTrue(any("Erangel" in e for e in res.evidence))
        self.assertTrue(any("Miramar" in e for e in res.evidence))
        self.assertEqual(len(res.evidence_session_ids), 4)
        self.assertIn("sole cause", res.insight.lower())

    # -----------------------------------------------------------------
    # 6. QUESTION 5: "Which configuration has better recorded results?"
    # -----------------------------------------------------------------
    def test_which_configuration_better(self):
        sessions = [
            {"session_id": "c1", "configuration": "M416 + Comp", "kills": 12, "deaths": 3, "kd_ratio": 4.0},
            {"session_id": "c2", "configuration": "M416 + Comp", "kills": 9, "deaths": 3, "kd_ratio": 3.0},
            {"session_id": "c3", "configuration": "AKM Iron", "kills": 2, "deaths": 4, "kd_ratio": 0.5},
            {"session_id": "c4", "configuration": "AKM Iron", "kills": 3, "deaths": 3, "kd_ratio": 1.0},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("Which configuration has better recorded results?")

        self.assertEqual(res.status, "answered")
        self.assertIn("M416 + Comp", res.answer)
        self.assertIn("3.50", res.answer)  # (4.0 + 3.0) / 2
        self.assertIn("AKM Iron", res.answer)
        self.assertEqual(len(res.evidence_session_ids), 4)
        self.assertIn("does not prove", res.insight.lower())

    # -----------------------------------------------------------------
    # 7. QUESTION 6: "How long are my strongest sessions?"
    # -----------------------------------------------------------------
    def test_how_long_strongest_sessions(self):
        sessions = [
            {"session_id": "d1", "duration": 25, "kills": 10, "deaths": 2, "kd_ratio": 5.0},
            {"session_id": "d2", "duration": 30, "kills": 8, "deaths": 2, "kd_ratio": 4.0},
            {"session_id": "d3", "duration": 100, "kills": 2, "deaths": 4, "kd_ratio": 0.5},
            {"session_id": "d4", "duration": 95, "kills": 3, "deaths": 6, "kd_ratio": 0.5},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("How long are my strongest sessions?")

        self.assertEqual(res.status, "answered")
        # Strongest sessions are d1 (25m, 5.0) and d2 (30m, 4.0) -> avg ~28m
        self.assertIn("minutes in duration", res.answer)
        self.assertTrue(any("25 mins" in e or "30 mins" in e for e in res.evidence))
        self.assertIn("d1", res.evidence_session_ids)
        self.assertIn("correlation rather than", res.insight.lower())

    # -----------------------------------------------------------------
    # 8. QUESTION 7: "What mistakes keep repeating?"
    # -----------------------------------------------------------------
    def test_what_mistakes_keep_repeating_theme(self):
        sessions = [
            {"session_id": "err1", "duration": 15, "kills": 1, "deaths": 6, "kd_ratio": 0.17, "player_notes": "Caught in open field rotation without cover"},
            {"session_id": "err2", "duration": 18, "kills": 2, "deaths": 5, "kd_ratio": 0.40, "player_notes": "Eliminated in open field running to circle"},
            {"session_id": "err3", "duration": 25, "kills": 8, "deaths": 2, "kd_ratio": 4.00, "player_notes": "Good positioning, survived"},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("What mistakes keep repeating?")

        self.assertEqual(res.status, "answered")
        self.assertIn("open field", res.answer.lower())
        self.assertIn("err1", res.evidence_session_ids)
        self.assertIn("err2", res.evidence_session_ids)
        self.assertTrue(any("Session #err1" in e for e in res.evidence))
        self.assertIn("does not identify unrecorded", res.insight.lower())

    def test_what_mistakes_keep_repeating_negative_trades(self):
        sessions = [
            {"session_id": "loss1", "duration": 14, "kills": 2, "deaths": 7, "kd_ratio": 0.28},
            {"session_id": "loss2", "duration": 16, "kills": 1, "deaths": 6, "kd_ratio": 0.16},
            {"session_id": "win1", "duration": 28, "kills": 9, "deaths": 1, "kd_ratio": 9.00},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("What mistakes keep repeating?")

        self.assertEqual(res.status, "answered")
        self.assertIn("unfavorable", res.answer.lower())
        self.assertIn("loss1", res.evidence_session_ids)
        self.assertIn("loss2", res.evidence_session_ids)

    # -----------------------------------------------------------------
    # 9. QUESTION 8: "What am I improving?"
    # -----------------------------------------------------------------
    def test_what_am_i_improving(self):
        sessions = [
            {"session_id": "imp1", "kills": 3, "deaths": 8, "kd_ratio": 0.38, "duration": 15},
            {"session_id": "imp2", "kills": 4, "deaths": 7, "kd_ratio": 0.57, "duration": 18},
            {"session_id": "imp3", "kills": 8, "deaths": 3, "kd_ratio": 2.67, "duration": 26},
            {"session_id": "imp4", "kills": 10, "deaths": 2, "kd_ratio": 5.00, "duration": 29},
        ]
        for s in sessions:
            self.storage.create_session(s)

        res = self.engine.ask("What am I improving?")

        self.assertEqual(res.status, "answered")
        self.assertIn("combat conversion", res.answer.lower())
        self.assertIn("survival discipline", res.answer.lower())
        self.assertEqual(len(res.evidence_session_ids), 4)
        self.assertTrue(any("Earlier sessions" in e for e in res.evidence))
        self.assertTrue(any("Recent sessions" in e for e in res.evidence))
        self.assertIn("unobserved", res.insight.lower())

    # -----------------------------------------------------------------
    # 10. RETRIEVAL OPTIMIZATION VERIFICATION
    # -----------------------------------------------------------------
    def test_retrieval_optimization(self):
        """
        Verify that the AI does not receive the player's entire match history
        unnecessarily:
        - 25 sessions in the database
        - Query retrieves only a targeted subset (e.g. 2 to 5 sessions)
        - Column projections omit full memories and AI blobs
        """
        # Populate 25 sessions
        for i in range(1, 26):
            self.storage.create_session({
                "session_id": f"sess_{i:02d}",
                "game": "BGMI",
                "map": "Erangel" if i % 2 == 0 else "Miramar",
                "configuration": "M416" if i % 3 == 0 else "SCAR-L",
                "duration": 10 + i,
                "kills": (i % 7) + 1,
                "deaths": (i % 4) + 1,
                "kd_ratio": round(((i % 7) + 1) / ((i % 4) + 1), 2),
                "started_at": f"2026-09-{i:02d}T12:00:00",
                "ai_summary": f"Very long AI summary for session {i} that should NOT be passed into analytical footprint...",
                "memory_text": f"Episodic memory text for session {i}..."
            })

        self.assertEqual(self.storage.count_sessions(), 25)

        # Test Question 1: When did I perform best?
        res1 = self.engine.ask("When did I perform best?")
        meta1 = res1.retrieval_metadata
        self.assertTrue(meta1["retrieval_optimized"])
        self.assertEqual(meta1["total_stored_sessions"], 25)
        # Should only retrieve 5 sessions, NOT all 25!
        self.assertLessEqual(meta1["retrieved_session_count"], 5)
        self.assertLess(meta1["retrieved_session_count"], meta1["total_stored_sessions"])

        # Test Question 2: What changed?
        res2 = self.engine.ask("What changed?")
        meta2 = res2.retrieval_metadata
        self.assertTrue(meta2["retrieval_optimized"])
        self.assertEqual(meta2["total_stored_sessions"], 25)
        # Only boundary sessions (top 1 + lowest 1)
        self.assertEqual(meta2["retrieved_session_count"], 2)

        # Test Question 6: How long are my strongest sessions?
        res6 = self.engine.ask("How long are my strongest sessions?")
        meta6 = res6.retrieval_metadata
        self.assertTrue(meta6["retrieval_optimized"])
        self.assertLess(meta6["retrieved_session_count"], 25)

    # -----------------------------------------------------------------
    # 11. REST API ENDPOINTS INTEGRATION
    # -----------------------------------------------------------------
    def test_api_cross_session_intelligence_endpoints(self):
        # Populate sessions in the main DB for API testing
        sessions = [
            {"session_id": "api_1", "game": "BGMI", "map": "Erangel", "configuration": "M416", "duration": 22, "kills": 8, "deaths": 2, "kd_ratio": 4.0},
            {"session_id": "api_2", "game": "BGMI", "map": "Erangel", "configuration": "M416", "duration": 24, "kills": 6, "deaths": 2, "kd_ratio": 3.0},
        ]
        for s in sessions:
            self.storage.create_session(s)

        # POST /api/intelligence/ask
        resp = self.client.post("/api/intelligence/ask", json={"question": "When did I perform best?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertIn("evidence", data)
        self.assertIn("insight", data)
        self.assertIn("recommendation", data)
        self.assertIn("retrieval_metadata", data)

        # GET /api/intelligence/ask
        get_resp = self.client.get("/api/intelligence/ask?question=Which map has my strongest recorded performance?")
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()
        self.assertIn("answer", get_data)
        self.assertIn("insight", get_data)
        self.assertIn("recommendation", get_data)


if __name__ == "__main__":
    unittest.main()
