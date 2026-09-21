import os
import sys
import unittest
import tempfile
import time
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Session, DetectionResult
from app.session_storage import SessionStorage
from app.detection import GameMapDetector
from app.session_lifecycle import (
    SessionLifecycleManager,
    STATE_IDLE,
    STATE_DETECTING,
    STATE_READY,
    STATE_PLAYING,
    STATE_COMPLETED
)


class TestPhase4SessionLifecycle(unittest.TestCase):
    """
    Phase 4: Session Lifecycle & Storage Integration Tests
    
    Verifies the complete flow:
    START GAMING -> Detect Game -> Detect Map -> Confirm -> Create Session -> Start Timer -> PLAYING -> END SESSION
    
    Verifies requirements:
    1. START SESSION creates a Session with:
       - session_id
       - game
       - game_mode
       - map
       - configuration if available
       - started_at
       - data_source
    2. Starts tracking duration.
    3. END SESSION stores:
       - ended_at
       - duration
    4. Allows performance data to be entered after the session:
       - score, kills, deaths, assists, result, player_notes
    5. No AI summaries are generated yet.
    6. State transitions: IDLE -> DETECTING -> READY -> PLAYING -> COMPLETED -> IDLE.
    """

    def setUp(self):
        # Create an isolated temporary database for test execution
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.storage = SessionStorage(db_path=self.temp_db_path)
        self.detector = GameMapDetector()
        self.manager = SessionLifecycleManager(storage=self.storage, detector=self.detector)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_complete_flow_start_to_end_session(self):
        """
        Tests the complete end-to-end flow:
        IDLE -> START GAMING -> DETECTING -> READY -> START SESSION -> PLAYING -> END SESSION -> COMPLETED
        """
        # Step 1: Initial state is IDLE
        status_initial = self.manager.get_status()
        self.assertEqual(status_initial["state"], STATE_IDLE)
        self.assertIsNone(status_initial["session_id"])

        # Step 2: START GAMING (triggers Detection)
        detection = self.manager.start_gaming(
            source="simulated",
            game_hint="Valorant",
            map_hint="Ascent",
            mode_hint="Competitive"
        )
        self.assertEqual(detection.game, "Valorant")
        self.assertEqual(detection.map, "Ascent")
        self.assertEqual(self.manager.state, STATE_READY)

        # Step 3: CONFIRM & START SESSION
        started_session = self.manager.confirm_and_start_session(
            configuration={"weapon": "Phantom", "sensitivity": 0.35},
            session_id="session-val-101"
        )

        # Verify state is PLAYING
        self.assertEqual(self.manager.state, STATE_PLAYING)
        self.assertEqual(started_session.session_id, "session-val-101")
        self.assertEqual(started_session.game, "Valorant")
        self.assertEqual(started_session.game_mode, "Competitive")
        self.assertEqual(started_session.map, "Ascent")
        self.assertEqual(started_session.data_source, "simulated")
        self.assertIsNotNone(started_session.started_at)
        self.assertIsInstance(started_session.configuration, dict)
        self.assertEqual(started_session.configuration["weapon"], "Phantom")

        # Verify session is persisted in storage
        stored = self.storage.get_session_by_id("session-val-101")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.game, "Valorant")
        self.assertEqual(stored.map, "Ascent")
        self.assertIsNone(stored.ended_at)

        # Step 4: Status check during PLAYING
        status_playing = self.manager.get_status()
        self.assertEqual(status_playing["state"], STATE_PLAYING)
        self.assertEqual(status_playing["session_id"], "session-val-101")
        self.assertEqual(status_playing["game"], "Valorant")
        self.assertEqual(status_playing["map"], "Ascent")
        self.assertGreaterEqual(status_playing["elapsed_seconds"], 0)

        # Step 5: END SESSION
        ended_session = self.manager.end_session(
            ended_at="2026-09-18T15:45:00",
            duration=45
        )

        # Verify state is COMPLETED
        self.assertEqual(self.manager.state, STATE_COMPLETED)
        self.assertEqual(ended_session.session_id, "session-val-101")
        self.assertEqual(ended_session.ended_at, "2026-09-18T15:45:00")
        self.assertEqual(ended_session.duration, 45)

        # Verify ended_at and duration are persisted in storage
        persisted_after_end = self.storage.get_session_by_id("session-val-101")
        self.assertEqual(persisted_after_end.ended_at, "2026-09-18T15:45:00")
        self.assertEqual(persisted_after_end.duration, 45)

        # Step 6: Enter post-session performance data
        updated_perf = self.manager.enter_performance_data(
            session_id="session-val-101",
            score="18/10",
            kills=18,
            deaths=10,
            assists=6,
            result="Win",
            player_notes="Great crosshair placement. Preferred sensitivity worked well."
        )

        self.assertEqual(updated_perf.score, "18/10")
        self.assertEqual(updated_perf.kills, 18)
        self.assertEqual(updated_perf.deaths, 10)
        self.assertEqual(updated_perf.assists, 6)
        self.assertEqual(updated_perf.kd_ratio, 1.8)
        self.assertEqual(updated_perf.result, "Win")
        self.assertEqual(updated_perf.player_notes, "Great crosshair placement. Preferred sensitivity worked well.")

        # Critical: Verify AI summaries are NOT generated yet
        self.assertIsNone(updated_perf.ai_summary)
        self.assertIsNone(updated_perf.ai_insights)

        # Step 7: Reset to IDLE
        self.manager.reset_to_idle()
        self.assertEqual(self.manager.state, STATE_IDLE)
        self.assertIsNone(self.manager.current_session)

    def test_start_session_with_manual_corrections(self):
        """Verify player can manually correct detection before starting session."""
        # Initial uncertain detection
        self.manager.start_gaming(source="simulated", scenario="unknown_game")
        self.assertEqual(self.manager.state, STATE_READY)
        self.assertFalse(self.manager.current_detection.is_confident)

        # Player manually confirms Elden Ring on Elphael
        session = self.manager.confirm_and_start_session(
            game="Elden Ring",
            map_name="Elphael, Brace of the Haligtree",
            game_mode="Boss Fight",
            data_source="manual"
        )

        self.assertEqual(self.manager.state, STATE_PLAYING)
        self.assertEqual(session.game, "Elden Ring")
        self.assertEqual(session.map, "Elphael, Brace of the Haligtree")
        self.assertEqual(session.game_mode, "Boss Fight")
        self.assertEqual(session.data_source, "manual")

    def test_cannot_start_without_confirmed_game_and_map(self):
        """Verify starting session without valid game and map raises ValueError."""
        with self.assertRaises(ValueError):
            self.manager.confirm_and_start_session(game=None, map_name=None)

    def test_cannot_end_session_when_not_playing(self):
        """Verify ending session without an active session raises ValueError."""
        with self.assertRaises(ValueError):
            self.manager.end_session()

    def test_duration_auto_calculated_if_omitted_on_end_session(self):
        """Verify duration is automatically computed from elapsed time when omitted."""
        self.manager.confirm_and_start_session(
            game="Apex Legends",
            map_name="Olympus"
        )
        # End immediately
        ended = self.manager.end_session()
        self.assertIsNotNone(ended.duration)
        self.assertGreaterEqual(ended.duration, 1)


if __name__ == "__main__":
    unittest.main()
