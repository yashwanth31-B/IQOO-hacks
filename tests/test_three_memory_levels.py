import os
import sys
import unittest
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.models import Session
from app.memory_engine import (
    generate_episodic_memory_summary,
    discover_pattern_memory,
    generate_player_profile_memory,
    step_1_summarize_session,
    step_2_extract_important_facts,
    step_3_identify_notable_performance,
    step_4_compare_previous_sessions,
    step_5_update_player_profile,
    run_ai_memory_engine_after_session
)

class TestThreeMemoryLevelsAndEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # =================================================================
    # 1. EPISODIC MEMORY TESTS
    # =================================================================
    def test_episodic_memory_canonical_example(self):
        """
        1. EPISODIC MEMORY
        Individual gaming events.
        Example: "Session #18 was a 72-minute Valorant session with 1.8 K/D."
        """
        session_data = {
            "session_id": "18",
            "game": "Valorant",
            "duration": "72 minutes",
            "score": "18/10",
            "kills": 18,
            "deaths": 10,
            "configuration": "Phantom + preferred sensitivity",
            "map": "Ascent",
            "result": "Win"
        }
        summary = generate_episodic_memory_summary(session_data)
        expected = "Session #18 was a 72-minute Valorant session with 1.8 K/D."
        self.assertEqual(summary, expected)

    def test_episodic_memory_do_not_invent_facts(self):
        """
        Episodic Memory must NOT invent facts if data is omitted.
        """
        # Case A: Missing duration -> does not invent 72 minutes
        no_dur = {"session_id": "18", "game": "Valorant", "kills": 18, "deaths": 10}
        summary_no_dur = generate_episodic_memory_summary(no_dur)
        self.assertNotIn("72", summary_no_dur)
        self.assertNotIn("minute", summary_no_dur)
        self.assertEqual(summary_no_dur, "Session #18 was a Valorant session with 1.8 K/D.")

        # Case B: Missing KD/kills/deaths -> does not invent 1.8 K/D
        no_kd = {"session_id": "18", "game": "Valorant", "duration": "72 minutes"}
        summary_no_kd = generate_episodic_memory_summary(no_kd)
        self.assertNotIn("1.8", summary_no_kd)
        self.assertNotIn("K/D", summary_no_kd)
        self.assertEqual(summary_no_kd, "Session #18 was a 72-minute Valorant session.")

        # Case C: Missing both duration and KD
        sparse = {"session_id": "18", "game": "Valorant"}
        summary_sparse = generate_episodic_memory_summary(sparse)
        self.assertEqual(summary_sparse, "Session #18 was a Valorant session.")

    # =================================================================
    # 2. PATTERN MEMORY TESTS
    # =================================================================
    def test_pattern_memory_canonical_example(self):
        """
        2. PATTERN MEMORY
        Patterns discovered across multiple sessions.
        Example: "The player tends to perform better during sessions shorter than 90 minutes."
        """
        sessions = [
            {"session_id": "1", "duration": "45 minutes", "kills": 15, "deaths": 10, "result": "Win"},
            {"session_id": "2", "duration": "60 minutes", "kills": 20, "deaths": 10, "result": "Win"},
            {"session_id": "3", "duration": "120 minutes", "kills": 8, "deaths": 16, "result": "Defeat"},
            {"session_id": "18", "duration": "72 minutes", "kills": 18, "deaths": 10, "result": "Win"}
        ]
        pattern = discover_pattern_memory(sessions)
        self.assertEqual(pattern["level"], "2. PATTERN MEMORY")
        self.assertEqual(pattern["status"], "discovered")
        self.assertEqual(
            pattern["description"],
            "The player tends to perform better during sessions shorter than 90 minutes."
        )

    def test_pattern_memory_insufficient_data(self):
        """
        If data is unavailable (<2 sessions with duration), explicitly say:
        "Not enough data to determine this."
        """
        # Empty sessions
        empty_pattern = discover_pattern_memory([])
        self.assertEqual(empty_pattern["description"], "Not enough data to determine this.")

        # Only 1 session with duration
        single_session = [{"session_id": "1", "duration": "72 minutes", "kills": 18, "deaths": 10}]
        single_pattern = discover_pattern_memory(single_session)
        self.assertEqual(single_pattern["description"], "Not enough data to determine this.")

        # Sessions without duration
        no_dur_sessions = [
            {"session_id": "1", "kills": 10, "deaths": 10},
            {"session_id": "2", "kills": 12, "deaths": 8}
        ]
        no_dur_pattern = discover_pattern_memory(no_dur_sessions)
        self.assertEqual(no_dur_pattern["description"], "Not enough data to determine this.")

    # =================================================================
    # 3. PLAYER PROFILE MEMORY TESTS
    # =================================================================
    def test_player_profile_memory_canonical_example(self):
        """
        3. PLAYER PROFILE MEMORY
        Long-term information.
        Example: "Preferred configuration: Phantom + sensitivity X."
        """
        sessions = [
            {"session_id": "1", "configuration": "Phantom + preferred sensitivity", "result": "Win", "kills": 15, "deaths": 10},
            {"session_id": "2", "configuration": "Vandal default", "result": "Defeat", "kills": 10, "deaths": 12},
            {"session_id": "18", "configuration": "Phantom + preferred sensitivity", "result": "Win", "kills": 18, "deaths": 10}
        ]
        profile = generate_player_profile_memory(sessions)
        self.assertEqual(profile["level"], "3. PLAYER PROFILE MEMORY")
        self.assertEqual(profile["preferred_configuration"], "Phantom + preferred sensitivity")
        self.assertEqual(profile["summary"], "Preferred configuration: Phantom + preferred sensitivity.")
        self.assertEqual(profile["peak_kd"], 1.8)

    def test_player_profile_memory_insufficient_data(self):
        """
        If configuration data is unavailable, explicitly say:
        "Preferred configuration: Not enough data to determine this."
        """
        sessions_no_config = [
            {"session_id": "1", "game": "Valorant", "kills": 10, "deaths": 10},
            {"session_id": "2", "game": "Valorant", "kills": 12, "deaths": 8}
        ]
        profile = generate_player_profile_memory(sessions_no_config)
        self.assertEqual(profile["preferred_configuration"], "Not enough data to determine this.")
        self.assertEqual(profile["summary"], "Preferred configuration: Not enough data to determine this.")

    # =================================================================
    # 4. AI MEMORY ENGINE 6-STEP WORKFLOW TESTS
    # =================================================================
    def test_engine_step_1_to_6_full_pipeline(self):
        """
        After each session:
        1. Summarize the session.
        2. Extract important facts.
        3. Identify notable performance.
        4. Compare against previous sessions when enough data exists.
        5. Update relevant player profile information.
        6. Store the generated memory.
        """
        s18_data = {
            "session_id": "18",
            "game": "Valorant",
            "date": "2026-09-17T20:00:00",
            "duration": "72 minutes",
            "score": "18/10",
            "kills": 18,
            "deaths": 10,
            "assists": 6,
            "result": "Win",
            "map": "Ascent",
            "configuration": "Phantom + preferred sensitivity",
            "performance_metrics": {"kd": 1.8, "acs": 285},
            "player_notes": "Felt locked in."
        }

        result = run_ai_memory_engine_after_session(session_id=18, session_data=s18_data)

        # Step 1: Summarize the session
        self.assertEqual(result["step_1_summary"], "Session #18 was a 72-minute Valorant session with 1.8 K/D.")

        # Step 2: Extract important facts (Do not invent facts)
        facts = result["step_2_extracted_facts"]
        self.assertEqual(facts["session_id"], "18")
        self.assertEqual(facts["game"], "Valorant")
        self.assertEqual(facts["duration_minutes"], 72)
        self.assertEqual(facts["kills"], 18)
        self.assertEqual(facts["deaths"], 10)
        self.assertEqual(facts["kd"], 1.8)
        self.assertEqual(facts["configuration"], "Phantom + preferred sensitivity")
        self.assertEqual(facts["map"], "Ascent")
        self.assertEqual(facts["result"], "Win")

        # Step 3: Identify notable performance
        self.assertIn("1.8 K/D", result["step_3_notable_performance"])
        self.assertIn("highest recorded performance", result["step_3_notable_performance"])

        # Step 4: Compare against previous sessions
        self.assertIn("historical average", result["step_4_comparison"])
        self.assertIn("1.8", result["step_4_comparison"])

        # Step 5: Update relevant player profile information
        profile = result["step_5_profile_updates"]
        self.assertEqual(profile["preferred_configuration"], "Phantom + preferred sensitivity")
        self.assertEqual(profile["preferred_configuration_summary"], "Preferred configuration: Phantom + preferred sensitivity.")

        # Step 6: Store generated memory (All 3 levels stored)
        stored = result["step_6_stored_memories"]
        self.assertIsNotNone(stored["episodic_memory_id"])
        self.assertIsNotNone(stored["pattern_memory_id"])
        self.assertIsNotNone(stored["player_profile_memory_id"])

    def test_engine_missing_data_explicit_not_enough_data(self):
        """
        When data is unavailable:
        Explicitly say: "Not enough data to determine this."
        """
        # Step 3: Missing performance metrics
        notable_empty = step_3_identify_notable_performance({})
        self.assertEqual(notable_empty, "Not enough data to determine this.")

        # Step 4: 0 previous sessions
        compare_empty = step_4_compare_previous_sessions({"kills": 18, "deaths": 10}, previous_sessions=[])
        self.assertEqual(compare_empty, "Not enough data to determine this.")

        # Step 4: Current session has no KD
        compare_no_kd = step_4_compare_previous_sessions({"game": "Valorant"}, previous_sessions=[{"kills": 10, "deaths": 10}])
        self.assertEqual(compare_no_kd, "Not enough data to determine this.")

    # =================================================================
    # 5. API ENDPOINTS TESTS
    # =================================================================
    def test_api_memories_tiers_endpoint(self):
        """
        GET /api/memories/tiers returns the 3 levels of memory
        """
        res = self.client.get("/api/memories/tiers")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("episodic", data)
        self.assertIn("pattern", data)
        self.assertIn("player_profile", data)
        self.assertIsInstance(data["episodic"], list)

    def test_api_player_profile_endpoint(self):
        """
        GET /api/player/profile returns active profile information
        """
        res = self.client.get("/api/player/profile")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("profile_memory", data)
        self.assertIn("stored_attributes", data)

    def test_api_memory_engine_process_endpoint(self):
        """
        POST /api/memory-engine/process executes the 6-step engine
        """
        payload = {
            "session_id": "18",
            "game": "Valorant",
            "duration": "72 minutes",
            "score": "18/10",
            "kills": 18,
            "deaths": 10,
            "result": "Win",
            "map": "Ascent",
            "configuration": "Phantom + preferred sensitivity"
        }
        res = self.client.post("/api/memory-engine/process", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["step_1_summary"], "Session #18 was a 72-minute Valorant session with 1.8 K/D.")
        self.assertIn("kd", data["step_2_extracted_facts"])
        self.assertIn("episodic_memory", data)
        self.assertIn("pattern_memory", data)
        self.assertIn("player_profile_memory", data)

if __name__ == "__main__":
    unittest.main()
