import unittest
import os
import tempfile
import json
from datetime import datetime

from app.models import Session, ProfileFact, PlayerProfile
from app.session_storage import SessionStorage
from app.player_profile import PlayerProfileManager, NOT_ENOUGH_DATA
from app.ai_memory_engine import AIMemoryEngine
from fastapi.testclient import TestClient
from app.main import app


class TestPhase6PlayerProfileMemory(unittest.TestCase):
    """
    Unit and integration tests for Phase 6: Player Profile Memory.
    Verifies:
    1. 0 sessions -> all facts have "Not enough data to determine this."
    2. 1 session -> all facts STILL have "Not enough data to determine this." (never assume from 1 session)
    3. Multiple sessions (>= 2) -> preferences identified with explicit evidence session IDs
    4. Profile updates dynamically as new sessions are processed
    5. REST API endpoints (/api/profile and /api/profile/rebuild)
    """

    def setUp(self):
        # Create a temporary SQLite database for test isolation
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase6.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.profile_mgr = PlayerProfileManager(storage=self.storage)
        self.ai_engine = AIMemoryEngine(storage=self.storage)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_zero_sessions_insufficient_data(self):
        """0 sessions must return 'Not enough data to determine this.' for all dimensions."""
        profile = self.profile_mgr.build_profile(sessions=[])

        self.assertEqual(profile.total_sessions_analyzed, 0)
        self.assertEqual(profile.preferred_game.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.preferred_game.status, "insufficient_data")
        self.assertEqual(profile.preferred_game.evidence_session_ids, [])

        self.assertEqual(profile.frequently_played_maps.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.frequently_used_configurations.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.preferred_session_duration.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.recurring_strengths.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.recurring_improvement_areas.value, NOT_ENOUGH_DATA)

    def test_single_session_never_assumes_preference(self):
        """
        CRITICAL RULE: Never assume a preference from one session.
        Even with complete telemetry, 1 session must return 'Not enough data to determine this.'
        """
        s1 = Session(
            session_id="18",
            game="Valorant",
            game_mode="Competitive",
            map="Ascent",
            configuration="Phantom configuration",
            duration=72,
            score="18/10",
            kills=18,
            deaths=10,
            assists=6,
            result="Win",
            player_notes="Felt locked in. Clean defense."
        )

        profile = self.profile_mgr.build_profile(sessions=[s1])

        self.assertEqual(profile.total_sessions_analyzed, 1)
        self.assertEqual(profile.preferred_game.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.frequently_played_maps.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.frequently_used_configurations.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.preferred_session_duration.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.recurring_strengths.value, NOT_ENOUGH_DATA)
        self.assertEqual(profile.recurring_improvement_areas.value, NOT_ENOUGH_DATA)

        self.assertEqual(profile.preferred_game.evidence_session_ids, [])
        self.assertEqual(profile.frequently_used_configurations.evidence_session_ids, [])

    def test_multiple_sessions_identifies_preferences_with_evidence(self):
        """
        With multiple sessions (>= 2), preferences must be identified and accompanied
        by exact evidence session IDs.
        """
        s14 = Session(
            session_id="14",
            game="Valorant",
            map="Ascent",
            configuration="Phantom configuration",
            duration=65,
            kills=20,
            deaths=12,
            result="Win",
            player_notes="Great crosshair placement and defense."
        )
        s18 = Session(
            session_id="18",
            game="Valorant",
            map="Ascent",
            configuration="Phantom configuration",
            duration=72,
            kills=18,
            deaths=10,
            result="Win",
            player_notes="Felt locked in. Site defense held."
        )
        s21 = Session(
            session_id="21",
            game="Valorant",
            map="Haven",
            configuration="Phantom configuration",
            duration=80,
            kills=22,
            deaths=11,
            result="Win",
            player_notes="Consistent clutches."
        )

        profile = self.profile_mgr.build_profile(sessions=[s14, s18, s21])

        self.assertEqual(profile.total_sessions_analyzed, 3)

        # 1. Preferred game
        self.assertEqual(profile.preferred_game.status, "determined")
        self.assertEqual(profile.preferred_game.value, "Valorant")
        self.assertIn("14", profile.preferred_game.evidence_session_ids)
        self.assertIn("18", profile.preferred_game.evidence_session_ids)
        self.assertIn("21", profile.preferred_game.evidence_session_ids)

        # 2. Frequently played maps
        self.assertEqual(profile.frequently_played_maps.status, "determined")
        self.assertIn("Ascent", profile.frequently_played_maps.value)
        self.assertIn("14", profile.frequently_played_maps.evidence_session_ids)
        self.assertIn("18", profile.frequently_played_maps.evidence_session_ids)

        # 3. Frequently used configurations
        self.assertEqual(profile.frequently_used_configurations.status, "determined")
        self.assertEqual(profile.frequently_used_configurations.value, "Phantom configuration")
        self.assertEqual(set(profile.frequently_used_configurations.evidence_session_ids), {"14", "18", "21"})

        # 4. Preferred session duration
        self.assertEqual(profile.preferred_session_duration.status, "determined")
        self.assertIn("under 90 minutes", profile.preferred_session_duration.value)
        self.assertEqual(set(profile.preferred_session_duration.evidence_session_ids), {"14", "18", "21"})

        # 5. Recurring strengths
        self.assertEqual(profile.recurring_strengths.status, "determined")
        self.assertTrue(len(profile.recurring_strengths.evidence_session_ids) >= 2)

    def test_recurring_improvement_areas_with_evidence(self):
        """
        Recurring improvement areas must be discovered only when multiple sessions show challenges.
        """
        s1 = Session(
            session_id="101",
            game="Valorant",
            map="Bind",
            duration=45,
            kills=8,
            deaths=16,
            kd_ratio=0.5,
            result="Defeat",
            player_notes="Tilted after round 5. High fatigue."
        )
        s2 = Session(
            session_id="102",
            game="Valorant",
            map="Bind",
            duration=50,
            kills=10,
            deaths=18,
            kd_ratio=0.55,
            result="Defeat",
            player_notes="Struggled to stay calm, tilt crept in."
        )

        profile = self.profile_mgr.build_profile(sessions=[s1, s2])

        self.assertEqual(profile.recurring_improvement_areas.status, "determined")
        self.assertNotEqual(profile.recurring_improvement_areas.value, NOT_ENOUGH_DATA)
        self.assertIn("101", profile.recurring_improvement_areas.evidence_session_ids)
        self.assertIn("102", profile.recurring_improvement_areas.evidence_session_ids)

    def test_dynamic_profile_update_when_new_sessions_added(self):
        """
        Profile must update dynamically:
        - 1st session inserted -> status is insufficient_data
        - 2nd session inserted -> status becomes determined with both IDs as evidence
        """
        # Step 1: Save 1st session
        s1_data = {
            "session_id": "sess-1",
            "game": "Apex Legends",
            "map": "World's Edge",
            "configuration": "R-99 + Wingman",
            "duration": 40,
            "kills": 4,
            "deaths": 2,
            "result": "Win"
        }
        self.storage.create_session(s1_data)
        prof_step1 = self.profile_mgr.update_profile_from_sessions()

        self.assertEqual(prof_step1.total_sessions_analyzed, 1)
        self.assertEqual(prof_step1.preferred_game.value, NOT_ENOUGH_DATA)
        self.assertEqual(prof_step1.frequently_used_configurations.value, NOT_ENOUGH_DATA)

        # Step 2: Save 2nd session with matching configuration and game
        s2_data = {
            "session_id": "sess-2",
            "game": "Apex Legends",
            "map": "World's Edge",
            "configuration": "R-99 + Wingman",
            "duration": 35,
            "kills": 5,
            "deaths": 1,
            "result": "Win"
        }
        self.storage.create_session(s2_data)
        prof_step2 = self.profile_mgr.update_profile_from_sessions()

        self.assertEqual(prof_step2.total_sessions_analyzed, 2)
        self.assertEqual(prof_step2.preferred_game.status, "determined")
        self.assertEqual(prof_step2.preferred_game.value, "Apex Legends")
        self.assertEqual(set(prof_step2.preferred_game.evidence_session_ids), {"sess-1", "sess-2"})

        self.assertEqual(prof_step2.frequently_used_configurations.status, "determined")
        self.assertEqual(prof_step2.frequently_used_configurations.value, "R-99 + Wingman")
        self.assertEqual(set(prof_step2.frequently_used_configurations.evidence_session_ids), {"sess-1", "sess-2"})

    def test_api_endpoints(self):
        """Test GET /api/profile and POST /api/profile/rebuild endpoints."""
        res_get = self.client.get("/api/profile")
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertIn("preferred_game", data)
        self.assertIn("frequently_played_maps", data)
        self.assertIn("frequently_used_configurations", data)
        self.assertIn("preferred_session_duration", data)
        self.assertIn("recurring_strengths", data)
        self.assertIn("recurring_improvement_areas", data)
        self.assertIn("evidence_session_ids", data["preferred_game"])

        res_post = self.client.post("/api/profile/rebuild")
        self.assertEqual(res_post.status_code, 200)
        rebuild_data = res_post.json()
        self.assertIn("preferred_game", rebuild_data)
        self.assertIn("evidence_session_ids", rebuild_data["preferred_game"])


if __name__ == "__main__":
    unittest.main()
