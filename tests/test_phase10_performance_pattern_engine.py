"""
Unit and integration tests for Phase 10: Performance Pattern Engine.

Requirements tested:
- Analyze stored sessions and identify repeated patterns:
  * repeated deaths
  * repeated map problems
  * repeated positioning issues
  * configuration correlations
  * session-duration patterns
  * performance consistency
  * recurring successful actions
  * recurring unsuccessful actions
- Invariant: Never call something a pattern based on one session. Minimum 2 sessions required.
- Explicitly separates:
    FACT
    PATTERN
    INTERPRETATION
- Exact prompt example formatting:
    FACT:
    Player died at similar locations in three recorded sessions.

    PATTERN:
    Repeated deaths occurred in similar areas.

    INTERPRETATION:
    These locations may deserve review.
- Causation guard: Do not claim why the player died unless stored data establishes it.
- Every pattern must contain evidence_session_ids (minimum 2).
- REST API endpoints (/api/patterns/analyze and /api/patterns/performance).
"""

import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from app.models import Session, TimelineEvent, PerformancePattern, PerformancePatternResponse
from app.session_storage import SessionStorage
from app.pattern_engine import PerformancePatternEngine
from app.main import app


class TestPhase10PerformancePatternEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase10.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.engine = PerformancePatternEngine(storage=self.storage)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_prompt_example_formatting(self):
        """
        Verifies exact format display:
        FACT:
        Player died at similar locations in three recorded sessions.

        PATTERN:
        Repeated deaths occurred in similar areas.

        INTERPRETATION:
        These locations may deserve review.
        """
        pattern = PerformancePattern(
            pattern_id="pat-example",
            pattern_type="repeated_deaths",
            game="Valorant",
            fact="Player died at similar locations in three recorded sessions.",
            pattern="Repeated deaths occurred in similar areas.",
            interpretation="These locations may deserve review.",
            evidence_session_ids=["12", "16", "18"]
        )

        expected_display = (
            "FACT:\n"
            "Player died at similar locations in three recorded sessions.\n\n"
            "PATTERN:\n"
            "Repeated deaths occurred in similar areas.\n\n"
            "INTERPRETATION:\n"
            "These locations may deserve review."
        )
        self.assertEqual(pattern.format_display(), expected_display)

    def test_never_call_pattern_based_on_one_session(self):
        """
        Critical requirement:
        Never call something a pattern based on one session.
        Require multiple relevant observations (minimum 2).
        """
        # 1. Zero sessions -> insufficient data
        res0 = self.engine.analyze_patterns(sessions=[])
        self.assertEqual(res0.status, "insufficient_data")
        self.assertEqual(len(res0.patterns), 0)

        # 2. Exactly one session -> must NEVER produce a pattern
        s1 = Session(
            session_id="1",
            game="Valorant",
            map="Haven",
            kills=10,
            deaths=15,
            result="Defeat",
            player_notes="Died on C Long."
        )
        res1 = self.engine.analyze_patterns(sessions=[s1])
        self.assertEqual(res1.status, "insufficient_data")
        self.assertEqual(len(res1.patterns), 0)

        # 3. Direct model validation prevents < 2 evidence session IDs
        with self.assertRaises(ValueError):
            PerformancePattern(
                pattern_id="pat-invalid",
                pattern_type="repeated_deaths",
                fact="Single occurrence",
                pattern="Invalid single-session pattern",
                interpretation="Invalid",
                evidence_session_ids=["1"]  # Only 1 session -> Must raise ValueError
            )

    def test_repeated_deaths_pattern(self):
        """
        Tests repeated deaths pattern identification across 3 sessions at similar location:
        Sessions 12, 16, 18 contain deaths at C Long.
        """
        for sid in ["12", "16", "18"]:
            self.storage.create_session(Session(
                session_id=sid,
                game="Valorant",
                map="Haven",
                kills=12,
                deaths=14,
                player_notes=f"Eliminated at C Long in session {sid}."
            ))

        res = self.engine.analyze_patterns(game="Valorant", pattern_type="repeated_deaths")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.patterns), 1)

        pat = res.patterns[0]
        self.assertEqual(pat.fact, "Player died at similar locations in three recorded sessions.")
        self.assertEqual(pat.pattern, "Repeated deaths occurred in similar areas.")
        self.assertEqual(pat.interpretation, "These locations may deserve review.")
        self.assertIn("12", pat.evidence_session_ids)
        self.assertIn("16", pat.evidence_session_ids)
        self.assertIn("18", pat.evidence_session_ids)

    def test_repeated_map_problems(self):
        """
        Identifies repeated defeats / difficulty on a specific map across sessions.
        """
        s1 = Session(session_id="map-1", game="Valorant", map="Split", kills=10, deaths=14, result="Defeat")
        s2 = Session(session_id="map-2", game="Valorant", map="Split", kills=8, deaths=15, result="Defeat")
        res = self.engine.analyze_patterns(game="Valorant", pattern_type="repeated_map_problems", sessions=[s1, s2])

        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.patterns), 1)
        pat = res.patterns[0]
        self.assertIn("Split", pat.fact)
        self.assertIn("Split", pat.pattern)
        self.assertEqual(set(pat.evidence_session_ids), {"map-1", "map-2"})

    def test_repeated_positioning_issues(self):
        """
        Identifies repeated positioning problems mentioned in notes or first deaths.
        """
        s1 = Session(session_id="pos-1", game="Valorant", kills=12, deaths=14, player_notes="Caught in bad angle, positioning failed.")
        s2 = Session(session_id="pos-2", game="Valorant", kills=10, deaths=16, player_notes="Ego-peeking exposed corner.")
        res = self.engine.analyze_patterns(game="Valorant", pattern_type="repeated_positioning_issues", sessions=[s1, s2])

        self.assertEqual(res.status, "success")
        pat = res.patterns[0]
        self.assertIn("Positioning", pat.fact)
        self.assertEqual(set(pat.evidence_session_ids), {"pos-1", "pos-2"})

    def test_configuration_correlations(self):
        """
        Discovers performance correlation across configurations (Phantom vs Vandal).
        """
        v1 = Session(session_id="v-1", game="Valorant", configuration="Vandal", kills=20, deaths=10, kd_ratio=2.0)
        v2 = Session(session_id="v-2", game="Valorant", configuration="Vandal", kills=22, deaths=11, kd_ratio=2.0)
        p1 = Session(session_id="p-1", game="Valorant", configuration="Phantom", kills=10, deaths=15, kd_ratio=0.67)
        p2 = Session(session_id="p-2", game="Valorant", configuration="Phantom", kills=11, deaths=16, kd_ratio=0.69)

        res = self.engine.analyze_patterns(game="Valorant", pattern_type="configuration_correlations", sessions=[v1, v2, p1, p2])
        self.assertEqual(res.status, "success")
        pat = res.patterns[0]
        self.assertIn("Vandal", pat.fact)
        self.assertIn("Phantom", pat.fact)
        self.assertIn("correlated", pat.pattern.lower())

    def test_session_duration_patterns(self):
        """
        Discovers performance drop in extended continuous play (>60 mins).
        """
        s_short1 = Session(session_id="dur-s1", game="Valorant", duration=30, kd_ratio=1.8)
        s_short2 = Session(session_id="dur-s2", game="Valorant", duration=40, kd_ratio=1.7)
        s_long1 = Session(session_id="dur-l1", game="Valorant", duration=90, kd_ratio=0.8)
        s_long2 = Session(session_id="dur-l2", game="Valorant", duration=120, kd_ratio=0.7)

        res = self.engine.analyze_patterns(game="Valorant", pattern_type="session_duration_patterns", sessions=[s_short1, s_short2, s_long1, s_long2])
        self.assertEqual(res.status, "success")
        pat = res.patterns[0]
        self.assertIn("60 minutes", pat.fact)
        self.assertIn("tends to decrease", pat.pattern.lower())

    def test_performance_consistency_pattern(self):
        """
        Discovers performance variance or high stability across sessions.
        """
        s1 = Session(session_id="c-1", game="Valorant", kd_ratio=0.5)
        s2 = Session(session_id="c-2", game="Valorant", kd_ratio=2.2)
        s3 = Session(session_id="c-3", game="Valorant", kd_ratio=1.1)

        res = self.engine.analyze_patterns(game="Valorant", pattern_type="performance_consistency", sessions=[s1, s2, s3])
        self.assertEqual(res.status, "success")
        pat = res.patterns[0]
        self.assertIn("variance", pat.pattern.lower())

    def test_recurring_successful_and_unsuccessful_actions(self):
        """
        Identifies recurring successful (e.g. clutch) and unsuccessful (e.g. dry-peeking) actions.
        """
        # Recurring successful actions
        s1 = Session(session_id="succ-1", game="Valorant", timeline=[TimelineEvent(timestamp_or_round="R10", event_type="clutch", description="Won 1v1 post-plant clutch", impact="positive")])
        s2 = Session(session_id="succ-2", game="Valorant", timeline=[TimelineEvent(timestamp_or_round="R18", event_type="clutch", description="Won 1v2 post-plant clutch", impact="positive")])

        res_succ = self.engine.analyze_patterns(game="Valorant", pattern_type="recurring_successful_actions", sessions=[s1, s2])
        self.assertEqual(res_succ.status, "success")
        self.assertIn("clutch", res_succ.patterns[0].fact.lower())

        # Recurring unsuccessful actions
        u1 = Session(session_id="un-1", game="Valorant", player_notes="Dry-peek resulted in opening death.")
        u2 = Session(session_id="un-2", game="Valorant", player_notes="Dry-peek without flash cost round.")
        res_un = self.engine.analyze_patterns(game="Valorant", pattern_type="recurring_unsuccessful_actions", sessions=[u1, u2])
        self.assertEqual(res_un.status, "success")
        self.assertIn("dry-peek", res_un.patterns[0].fact.lower())

    def test_causation_guard_compliance(self):
        """
        Ensures interpretations never state unproven causation:
        e.g. does not claim why the player died unless stored data establishes it.
        """
        s1 = Session(session_id="g-1", game="Valorant", kills=8, deaths=15, player_notes="Died at B Main choke.")
        s2 = Session(session_id="g-2", game="Valorant", kills=9, deaths=14, player_notes="Died at B Main entrance.")

        res = self.engine.analyze_patterns(game="Valorant", sessions=[s1, s2])
        for p in res.patterns:
            interp_lower = p.interpretation.lower()
            self.assertNotIn("caused you to die", interp_lower)
            self.assertNotIn("is the reason you failed", interp_lower)
            self.assertNotIn("caused you to lose", interp_lower)

    def test_rest_api_pattern_endpoints(self):
        """
        Tests Fast API endpoints:
        - POST /api/patterns/analyze
        - GET /api/patterns/performance
        """
        # Seed 2 sessions
        for sid in ["api-pat-1", "api-pat-2"]:
            self.client.post("/api/sessions", json={
                "session_id": sid,
                "game": "BGMI",
                "map": "Erangel",
                "kills": 3,
                "deaths": 1,
                "result": "Defeat",
                "player_notes": "Bridge crossing camped, died in vehicle."
            })

        # POST /api/patterns/analyze
        res_post = self.client.post("/api/patterns/analyze", json={"game": "BGMI"})
        self.assertEqual(res_post.status_code, 200)
        data = res_post.json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["total_patterns"], 0)

        # GET /api/patterns/performance
        res_get = self.client.get("/api/patterns/performance?game=BGMI")
        self.assertEqual(res_get.status_code, 200)
        self.assertGreater(res_get.json()["total_patterns"], 0)


if __name__ == "__main__":
    unittest.main()
