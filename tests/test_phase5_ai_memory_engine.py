import os
import sys
import unittest
import tempfile
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Session, AIMemoryRecord, AIMemoryProcessingResult
from app.session_storage import SessionStorage
from app.ai_memory_engine import (
    AIMemoryEngine,
    NOT_ENOUGH_DATA,
    AI_MODEL_VERSION
)


class TestPhase5AIMemoryEngine(unittest.TestCase):
    """
    Phase 5: AI Memory Engine Tests
    
    Verifies:
    1. Complete session processing (summarize, extract facts, notable performance, structured insights, store memory).
    2. Incomplete session processing without hallucination or invented data.
    3. Hallucination protection (never invent scores, dates, configurations, maps, performance; use 'Not enough data to determine this.').
    4. Pattern Memory guard (NOT generated unless enough historical sessions exist >= 3).
    5. Player Profile Memory guard (NOT generated unless enough evidence exists >= 3).
    6. Separation of raw session data and AI memory (both remain available).
    7. Storage of all required output fields (ai_summary, ai_insights, memory_text, evidence_session_ids, ai_confidence, ai_model_version).
    """

    def setUp(self):
        # Create an isolated temporary database
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.storage = SessionStorage(db_path=self.temp_db_path)
        self.engine = AIMemoryEngine(storage=self.storage)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # -------------------------------------------------------------
    # 1. COMPLETE SESSION PROCESSING
    # -------------------------------------------------------------
    def test_complete_session_processing(self):
        """
        Test 1: Complete session (Session #18 example).
        Verifies:
        - Summary correctly formed: 'Session #18 was a 72-minute Valorant session on Ascent with 18 kills and 10 deaths (Win).'
        - Facts extracted accurately without fabrication.
        - Notable performance identifies high K/D (1.8).
        - Structured insights generated based strictly on data.
        - Memory stored with all required output fields.
        """
        complete_payload = {
            "session_id": "18",
            "game": "Valorant",
            "game_mode": "Competitive",
            "map": "Ascent",
            "configuration": {"primary_weapon": "Phantom", "sensitivity": 0.35},
            "started_at": "2026-09-18T14:00:00",
            "duration": 72,
            "score": "18/10",
            "kills": 18,
            "deaths": 10,
            "assists": 6,
            "result": "Win",
            "player_notes": "Strong performance session. Preferred sensitivity felt locked in."
        }
        stored_session = self.storage.create_session(complete_payload)

        # Process through AI Memory Engine
        result = self.engine.process_and_store_session(stored_session)

        self.assertIsInstance(result, AIMemoryProcessingResult)

        # 1. Check summary
        summary = result.episodic_memory.ai_summary
        self.assertIn("Session #18", summary)
        self.assertIn("72-minute", summary)
        self.assertIn("Valorant", summary)
        self.assertIn("Ascent", summary)
        self.assertIn("18 kills", summary)
        self.assertIn("10 deaths", summary)

        # 2. Check facts extraction
        facts = result.episodic_memory.facts
        self.assertEqual(facts["session_id"], "18")
        self.assertEqual(facts["game"], "Valorant")
        self.assertEqual(facts["map"], "Ascent")
        self.assertEqual(facts["kills"], 18)
        self.assertEqual(facts["deaths"], 10)
        self.assertEqual(facts["kd_ratio"], 1.8)
        self.assertEqual(facts["duration"], 72)
        self.assertEqual(facts["result"], "Win")

        # 3. Check notable performance
        notable = result.episodic_memory.notable_performance
        self.assertIn("1.8 K/D", notable)
        self.assertIn("18 kills", notable)

        # 4. Check structured insights (supported only by data)
        insights = result.episodic_memory.ai_insights
        self.assertTrue(any("Phantom" in i for i in insights))
        self.assertTrue(any("1.8 K/D" in i for i in insights))

        # 5. Check all required output fields
        ep = result.episodic_memory
        self.assertIsNotNone(ep.ai_summary)
        self.assertIsInstance(ep.ai_insights, list)
        self.assertIsNotNone(ep.memory_text)
        self.assertEqual(ep.evidence_session_ids, ["18"])
        self.assertGreaterEqual(ep.ai_confidence, 0.9)
        self.assertEqual(ep.ai_model_version, AI_MODEL_VERSION)

    # -------------------------------------------------------------
    # 2. INCOMPLETE SESSION & HALLUCINATION PROTECTION
    # -------------------------------------------------------------
    def test_incomplete_session_hallucination_protection(self):
        """
        Test 2: Incomplete session.
        Verifies:
        - Never invents missing scores, dates, configurations, maps, performance, behavior.
        - If performance information is unavailable, explicitly uses: 'Not enough data to determine this.'
        - Summary only includes available facts.
        """
        incomplete_payload = {
            "session_id": "partial-99",
            "game": "Elden Ring",
            "result": "Defeat"
            # duration, kills, deaths, map, configuration, score, player_notes are all None!
        }
        stored_session = self.storage.create_session(incomplete_payload)

        result = self.engine.process_and_store_session(stored_session)
        ep = result.episodic_memory

        # Summary must NOT invent duration or kills/deaths
        summary = ep.ai_summary
        self.assertIn("Elden Ring", summary)
        self.assertNotIn("minute", summary)
        self.assertNotIn("kills", summary)
        self.assertNotIn("deaths", summary)

        # Facts must contain only provided data
        facts = ep.facts
        self.assertEqual(facts["game"], "Elden Ring")
        self.assertEqual(facts["result"], "Defeat")
        self.assertNotIn("kills", facts)
        self.assertNotIn("deaths", facts)
        self.assertNotIn("map", facts)
        self.assertNotIn("duration", facts)

        # Test completely empty session for 'Not enough data to determine this.'
        empty_session = self.storage.create_session({"session_id": "empty-0"})
        notable_empty = self.engine.identify_notable_performance(empty_session)
        self.assertEqual(notable_empty, NOT_ENOUGH_DATA)

    # -------------------------------------------------------------
    # 3. PATTERN MEMORY GUARD (Conditional upon historical data)
    # -------------------------------------------------------------
    def test_pattern_memory_not_generated_without_enough_history(self):
        """
        Test 3: Pattern Memory MUST NOT be generated yet unless enough
        historical sessions exist (>= 3).
        """
        # Scenario A: Only 1 session in database
        s1 = self.storage.create_session({
            "session_id": "single-sess-1",
            "game": "Valorant",
            "kills": 15,
            "deaths": 10,
            "duration": 40
        })
        res1 = self.engine.process_and_store_session(s1)
        # Pattern memory must NOT be generated
        self.assertIsNone(res1.pattern_memory)

        # Scenario B: 2 sessions in database (still below threshold of 3)
        s2 = self.storage.create_session({
            "session_id": "single-sess-2",
            "game": "Valorant",
            "kills": 18,
            "deaths": 10,
            "duration": 45
        })
        res2 = self.engine.process_and_store_session(s2)
        # Pattern memory must NOT be generated
        self.assertIsNone(res2.pattern_memory)

        # Scenario C: 3+ sessions in database -> Pattern Memory IS generated
        s3 = self.storage.create_session({
            "session_id": "single-sess-3",
            "game": "Valorant",
            "kills": 20,
            "deaths": 10,
            "duration": 50
        })
        res3 = self.engine.process_and_store_session(s3)
        self.assertIsNotNone(res3.pattern_memory)
        self.assertEqual(res3.pattern_memory.memory_type, "pattern")
        self.assertIn("shorter than 90 minutes", res3.pattern_memory.ai_summary)

    # -------------------------------------------------------------
    # 4. PLAYER PROFILE MEMORY GUARD (Conditional upon evidence)
    # -------------------------------------------------------------
    def test_player_profile_memory_not_generated_without_enough_evidence(self):
        """
        Test 4: Player Profile Memory MUST NOT be generated yet unless enough
        evidence exists (>= 3 historical sessions with consistent configuration).
        """
        # Scenario A: 1 session -> profile memory is None
        s1 = self.storage.create_session({
            "session_id": "prof-1",
            "game": "Valorant",
            "configuration": "Phantom"
        })
        res1 = self.engine.process_and_store_session(s1)
        self.assertIsNone(res1.player_profile_memory)

        # Scenario B: 3+ sessions with consistent configuration -> profile memory IS generated
        self.storage.create_session({
            "session_id": "prof-2",
            "game": "Valorant",
            "configuration": "Phantom"
        })
        s3 = self.storage.create_session({
            "session_id": "prof-3",
            "game": "Valorant",
            "configuration": "Phantom"
        })
        res3 = self.engine.process_and_store_session(s3)
        self.assertIsNotNone(res3.player_profile_memory)
        self.assertEqual(res3.player_profile_memory.memory_type, "player_profile")
        self.assertIn("Preferred configuration: Phantom.", res3.player_profile_memory.ai_summary)

    # -------------------------------------------------------------
    # 5. SEPARATION OF RAW SESSION DATA AND AI MEMORY
    # -------------------------------------------------------------
    def test_raw_session_and_ai_memory_remain_separate(self):
        """
        Test 5: AI-generated information must remain separate from raw session data.
        After processing:
        RAW SESSION + AI MEMORY should both remain available.
        """
        raw_payload = {
            "session_id": "sep-test-01",
            "game": "Valorant",
            "map": "Haven",
            "kills": 24,
            "deaths": 12,
            "duration": 60,
            "configuration": "Vandal",
            "player_notes": "Pure mechanical dominance on defense."
        }
        stored = self.storage.create_session(raw_payload)

        # Process through AI Memory Engine
        result = self.engine.process_and_store_session(stored)

        # 1. Check raw session fields are untouched
        raw = result.raw_session
        self.assertEqual(raw["session_id"], "sep-test-01")
        self.assertEqual(raw["game"], "Valorant")
        self.assertEqual(raw["map"], "Haven")
        self.assertEqual(raw["kills"], 24)
        self.assertEqual(raw["deaths"], 12)
        self.assertEqual(raw["player_notes"], "Pure mechanical dominance on defense.")

        # 2. Check AI memory is distinct
        mem = result.episodic_memory
        self.assertEqual(mem.memory_type, "episodic")
        self.assertIn("24 kills and 12 deaths", mem.memory_text)
        self.assertEqual(mem.evidence_session_ids, ["sep-test-01"])

        # 3. Verify in storage: Raw session remains valid
        retrieved_session = self.storage.get_session_by_id("sep-test-01")
        self.assertEqual(retrieved_session.kills, 24)
        self.assertEqual(retrieved_session.deaths, 12)
        self.assertEqual(retrieved_session.kd_ratio, 2.0)
        # AI summary is linked to the session
        self.assertIsNotNone(retrieved_session.ai_summary)


if __name__ == "__main__":
    unittest.main()
