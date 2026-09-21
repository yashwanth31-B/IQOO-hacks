import os
import sys
import unittest
import tempfile
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import DetectionResult, GameDetectionResult, Session
from app.session_storage import SessionStorage
from app.detection import (
    GameMapDetector,
    DetectionError,
    DetectionConnectionError,
    KNOWN_GAMES_AND_MAPS,
    default_detector
)


class TestPhase3GameMapDetection(unittest.TestCase):
    """
    Phase 3: Game and Map Detection Tests
    
    Verifies the 5 required test cases:
    1. Valid detection.
    2. Unknown game.
    3. Unknown map.
    4. Manual correction.
    5. Low confidence.
    
    Plus core requirements:
    - DetectionResult schema compliance.
    - No false claims of API / game-log detection without connection.
    - Uncertainty message: 'Unable to confidently detect game/map.'
    - Store only confirmed values in the Session (unconfirmed detections never written to DB).
    """

    def setUp(self):
        # Create an isolated temporary database for storage verification
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.storage = SessionStorage(db_path=self.temp_db_path)
        self.detector = GameMapDetector(api_connected=False, game_log_connected=False)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # -------------------------------------------------------------
    # TEST 1: Valid Detection
    # -------------------------------------------------------------
    def test_1_valid_detection(self):
        """
        Test 1: Valid detection identifying game, game mode, map with high confidence.
        """
        result = self.detector.detect(
            source="simulated",
            game_hint="Valorant",
            map_hint="Ascent",
            mode_hint="Competitive"
        )

        self.assertIsInstance(result, DetectionResult)
        self.assertEqual(result.game, "Valorant")
        self.assertEqual(result.map, "Ascent")
        self.assertEqual(result.game_mode, "Competitive")
        self.assertGreaterEqual(result.confidence, 0.8)
        self.assertEqual(result.detection_source, "simulated")
        self.assertTrue(result.is_confident)
        self.assertIsNone(result.message)

    # -------------------------------------------------------------
    # TEST 2: Unknown Game
    # -------------------------------------------------------------
    def test_2_unknown_game(self):
        """
        Test 2: Detection where game is unknown or unrecognized.
        Must show 'Unable to confidently detect game/map.' and mark is_confident=False.
        """
        # Case A: Explicit unknown_game scenario
        result_scenario = self.detector.detect(
            source="simulated",
            scenario="unknown_game"
        )
        self.assertFalse(result_scenario.is_confident)
        self.assertEqual(result_scenario.message, "Unable to confidently detect game/map.")
        self.assertLess(result_scenario.confidence, 0.6)

        # Case B: Completely unrecognized game title
        result_unrecognized = self.detector.detect(
            source="simulated",
            game_hint="SomeRandomNonExistentGame12345",
            map_hint="SomeMap"
        )
        self.assertFalse(result_unrecognized.is_confident)
        self.assertEqual(result_unrecognized.message, "Unable to confidently detect game/map.")
        self.assertLess(result_unrecognized.confidence, 0.6)

    # -------------------------------------------------------------
    # TEST 3: Unknown Map
    # -------------------------------------------------------------
    def test_3_unknown_map(self):
        """
        Test 3: Detection where game is identified but map is unknown.
        Must show 'Unable to confidently detect game/map.' and mark is_confident=False.
        """
        # Case A: Explicit unknown_map scenario
        result_scenario = self.detector.detect(
            source="simulated",
            scenario="unknown_map",
            game_hint="Valorant"
        )
        self.assertFalse(result_scenario.is_confident)
        self.assertIsNone(result_scenario.map)
        self.assertEqual(result_scenario.message, "Unable to confidently detect game/map.")

        # Case B: Known game, but unlisted/unknown map name
        result_unrecognized = self.detector.detect(
            source="simulated",
            game_hint="Valorant",
            map_hint="Atlantis"  # Not a known Valorant map
        )
        self.assertFalse(result_unrecognized.is_confident)
        self.assertEqual(result_unrecognized.message, "Unable to confidently detect game/map.")
        self.assertLess(result_unrecognized.confidence, 0.6)

    # -------------------------------------------------------------
    # TEST 4: Manual Correction
    # -------------------------------------------------------------
    def test_4_manual_correction(self):
        """
        Test 4: Player manually corrects detected values.
        Transitions to manual source with 1.0 confidence and stores confirmed values.
        """
        # Start with an uncertain or low confidence detection
        initial_detection = self.detector.detect(
            source="simulated",
            scenario="unknown_map",
            game_hint="Valorant"
        )
        self.assertFalse(initial_detection.is_confident)

        # Player manually corrects map to "Ascent" and game to "Valorant"
        corrected = self.detector.apply_manual_correction(
            detection=initial_detection,
            game="Valorant",
            map_name="Ascent",
            game_mode="Competitive"
        )

        self.assertTrue(corrected.is_confident)
        self.assertEqual(corrected.game, "Valorant")
        self.assertEqual(corrected.map, "Ascent")
        self.assertEqual(corrected.game_mode, "Competitive")
        self.assertEqual(corrected.confidence, 1.0)
        self.assertEqual(corrected.detection_source, "manual")

        # Confirm and store into database
        confirmed_session = self.detector.confirm_detection_and_create_session(
            detection=corrected,
            additional_fields={"score": "13-10", "result": "Win"},
            storage=self.storage
        )

        self.assertIsNotNone(confirmed_session)
        self.assertEqual(confirmed_session.game, "Valorant")
        self.assertEqual(confirmed_session.map, "Ascent")
        self.assertEqual(confirmed_session.score, "13-10")
        self.assertEqual(confirmed_session.data_source, "manual")

        # Verify persisted in database
        persisted = self.storage.get_session_by_id(confirmed_session.session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.game, "Valorant")
        self.assertEqual(persisted.map, "Ascent")

    # -------------------------------------------------------------
    # TEST 5: Low Confidence
    # -------------------------------------------------------------
    def test_5_low_confidence(self):
        """
        Test 5: Detection with low confidence score (< 0.6).
        Must explicitly flag uncertainty with 'Unable to confidently detect game/map.'
        """
        low_conf_result = self.detector.detect(
            source="simulated",
            scenario="low_confidence",
            confidence_override=0.4
        )

        self.assertFalse(low_conf_result.is_confident)
        self.assertLess(low_conf_result.confidence, 0.6)
        self.assertEqual(low_conf_result.message, "Unable to confidently detect game/map.")

    # -------------------------------------------------------------
    # ADDITIONAL CONSTRAINTS VERIFICATION
    # -------------------------------------------------------------
    def test_do_not_claim_api_or_game_log_when_not_connected(self):
        """
        Requirement: 'Do not claim API/game-log detection if it is not actually connected.'
        """
        # API not connected
        with self.assertRaises(DetectionConnectionError) as ctx:
            self.detector.detect(source="api")
        self.assertIn("API detection source is not connected", str(ctx.exception))

        # Game log not connected
        with self.assertRaises(DetectionConnectionError) as ctx:
            self.detector.detect(source="game_log")
        self.assertIn("game_log detection source is not connected", str(ctx.exception))

    def test_unconfirmed_detection_never_stored(self):
        """
        Requirement: 'Store only confirmed values in the Session.'
        Running detection must NOT create any session in the database.
        """
        initial_count = self.storage.count_sessions()
        self.assertEqual(initial_count, 0)

        # Run several detections without confirming
        self.detector.detect(source="simulated", game_hint="Valorant", map_hint="Ascent")
        self.detector.detect(source="simulated", scenario="unknown_game")
        self.detector.detect(source="simulated", scenario="low_confidence")

        # Database must still have 0 sessions
        self.assertEqual(self.storage.count_sessions(), 0)

        # Only when explicitly confirmed does it write to the database
        valid = self.detector.detect(source="simulated", game_hint="Valorant", map_hint="Bind")
        self.detector.confirm_detection_and_create_session(valid, storage=self.storage)

        self.assertEqual(self.storage.count_sessions(), 1)

    # -------------------------------------------------------------
    # PHASE 3: GAME DETECTION MODULE DEDICATED TESTS
    # -------------------------------------------------------------
    def test_phase3_known_game_bgmi_and_formatted_display(self):
        """
        Phase 3 Test: Known game detection and exact formatted display matching:
        GAME:
        BGMI

        CONFIDENCE:
        0.96

        SOURCE:
        simulated
        """
        result = self.detector.detect_game(
            source="simulated",
            game_hint="BGMI",
            confidence_override=0.96
        )

        self.assertIsInstance(result, GameDetectionResult)
        self.assertEqual(result.game, "BGMI")
        self.assertEqual(result.confidence, 0.96)
        self.assertEqual(result.detection_source, "simulated")
        self.assertEqual(result.game_version, "3.5")
        self.assertEqual(result.game_mode, "Classic Battle Royale")
        self.assertTrue(result.is_confident)

        expected_display = "GAME:\nBGMI\n\nCONFIDENCE:\n0.96\n\nSOURCE:\nsimulated"
        self.assertEqual(result.format_display(), expected_display)

    def test_phase3_all_10_mvp_games_supported(self):
        """
        Phase 3 Test: Verify all 10 supported MVP games:
        1. BGMI / PUBG Mobile
        2. Free Fire MAX
        3. Call of Duty Mobile
        4. PUBG New State
        5. Valorant
        6. Honor of Kings
        7. League of Legends
        8. Fortnite
        9. Genshin Impact
        10. Chess
        """
        mvp_games = [
            "BGMI / PUBG Mobile",
            "Free Fire MAX",
            "Call of Duty Mobile",
            "PUBG New State",
            "Valorant",
            "Honor of Kings",
            "League of Legends",
            "Fortnite",
            "Genshin Impact",
            "Chess"
        ]

        for game in mvp_games:
            # Test simulated detection
            sim_res = self.detector.detect_game(source="simulated", game_hint=game)
            self.assertEqual(sim_res.game, game)
            self.assertTrue(sim_res.is_confident)
            self.assertGreaterEqual(sim_res.confidence, 0.6)
            self.assertEqual(sim_res.detection_source, "simulated")
            self.assertIsNotNone(sim_res.game_version)
            self.assertIsNotNone(sim_res.game_mode)

            # Test manual detection
            man_res = self.detector.detect_game(source="manual", game_hint=game)
            self.assertEqual(man_res.game, game)
            self.assertTrue(man_res.is_confident)
            self.assertEqual(man_res.confidence, 1.0)
            self.assertEqual(man_res.detection_source, "manual")

    def test_phase3_unknown_game(self):
        """
        Phase 3 Test: Unknown or unrecognized game detection.
        Must report is_confident=False and confidence < 0.6.
        """
        # Case A: completely unrecognized title
        res_unrecognized = self.detector.detect_game(
            source="simulated",
            game_hint="UnrealSuperGame99999"
        )
        self.assertFalse(res_unrecognized.is_confident)
        self.assertLess(res_unrecognized.confidence, 0.6)
        self.assertIn("Unable to confidently detect game", res_unrecognized.message)

        # Case B: explicit unknown scenario
        res_scenario = self.detector.detect_game(
            source="simulated",
            scenario="unknown_game"
        )
        self.assertFalse(res_scenario.is_confident)
        self.assertLess(res_scenario.confidence, 0.6)
        self.assertIn("Unable to confidently detect game", res_scenario.message)

    def test_phase3_manual_correction_and_store_confirmed(self):
        """
        Phase 3 Test: Manual correction and storing only confirmed game information.
        """
        # Start with an unknown game detection
        initial = self.detector.detect_game(
            source="simulated",
            scenario="unknown_game"
        )
        self.assertFalse(initial.is_confident)

        # Correct to BGMI manually
        corrected = self.detector.apply_manual_correction(
            detection=initial,
            game="BGMI",
            game_version="3.5",
            game_mode="Classic Battle Royale"
        )
        self.assertTrue(corrected.is_confident)
        self.assertEqual(corrected.game, "BGMI")
        self.assertEqual(corrected.confidence, 1.0)
        self.assertEqual(corrected.detection_source, "manual")

        # Confirm and save to session storage
        session = self.detector.confirm_detection_and_create_session(
            detection=corrected,
            additional_fields={"kills": 7, "deaths": 2, "result": "Win"},
            storage=self.storage
        )
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.game, "BGMI")
        self.assertEqual(session.game_mode, "Classic Battle Royale")
        self.assertEqual(session.data_source, "manual")

        # Verify only confirmed session exists in DB
        persisted = self.storage.get_session_by_id(session.session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.game, "BGMI")

    def test_phase3_low_confidence(self):
        """
        Phase 3 Test: Low confidence game detection.
        Must report is_confident=False and confidence < 0.6.
        """
        low_res = self.detector.detect_game(
            source="simulated",
            game_hint="BGMI",
            confidence_override=0.45
        )
        self.assertFalse(low_res.is_confident)
        self.assertEqual(low_res.confidence, 0.45)
        self.assertIn("Unable to confidently detect game", low_res.message)

    def test_phase3_real_source_enforcement(self):
        """
        Phase 3 Test: Do not claim automatic detection without a real connection.
        """
        with self.assertRaises(DetectionConnectionError):
            self.detector.detect_game(source="api")

        with self.assertRaises(DetectionConnectionError):
            self.detector.detect_game(source="game_log")


if __name__ == "__main__":
    unittest.main()
