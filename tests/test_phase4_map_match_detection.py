import os
import sys
import unittest
import tempfile
from typing import Dict, Any
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import MapDetectionResult, MatchContext, Session
from app.map_registry import GameMapRegistry, default_map_registry
from app.session_storage import SessionStorage
from app.detection import (
    GameMapDetector,
    DetectionError,
    DetectionConnectionError
)
from app.session_lifecycle import SessionLifecycleManager, STATE_PLAYING
from app.main import app


class TestPhase4MapMatchDetection(unittest.TestCase):
    """
    Phase 4: Map and Match Detection Tests
    
    Verifies all Phase 4 requirements:
    1. Game-specific maps (BGMI -> Erangel, Valorant -> Ascent, Free Fire -> Bermuda).
    2. Dynamic map registry (maps are not hard-coded into core architecture).
    3. If map information is unavailable: 'Map not detected.'
    4. Detect or allow manual input for:
       - map
       - game mode
       - match ID
       - round number if applicable
       - detection confidence
       - detection source
    5. Manual confirmation of MatchContext.
    6. Connect confirmed data to the active Session.
    7. Strict source integrity (no fake API/game-log claims).
    8. REST API endpoints for Phase 4.
    """

    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.storage = SessionStorage(db_path=self.temp_db_path)
        self.detector = GameMapDetector(api_connected=False, game_log_connected=False)
        self.lifecycle = SessionLifecycleManager(storage=self.storage, detector=self.detector)
        self.client = TestClient(app)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # -------------------------------------------------------------
    # 1. GAME-SPECIFIC MAPS & DISPLAY FORMAT
    # -------------------------------------------------------------
    def test_game_specific_maps_examples(self):
        """
        Verify prompt examples for game-specific maps:
        - BGMI -> Erangel
        - Valorant -> Ascent
        - Free Fire -> Bermuda
        """
        # BGMI -> Erangel
        bgmi_map = self.detector.detect_map(game="BGMI", source="simulated", map_hint="Erangel")
        self.assertIsInstance(bgmi_map, MapDetectionResult)
        self.assertEqual(bgmi_map.game, "BGMI")
        self.assertEqual(bgmi_map.map, "Erangel")
        self.assertTrue(bgmi_map.is_confident)
        self.assertGreaterEqual(bgmi_map.confidence, 0.6)
        self.assertEqual(bgmi_map.detection_source, "simulated")

        # Valorant -> Ascent
        val_map = self.detector.detect_map(game="Valorant", source="simulated", map_hint="Ascent")
        self.assertEqual(val_map.game, "Valorant")
        self.assertEqual(val_map.map, "Ascent")
        self.assertTrue(val_map.is_confident)

        display = val_map.format_display()
        self.assertIn("GAME:\nValorant", display)
        self.assertIn("MAP:\nAscent", display)
        self.assertIn("SOURCE:\nsimulated", display)

        # Free Fire -> Bermuda
        ff_map = self.detector.detect_map(game="Free Fire MAX", source="simulated", map_hint="Bermuda")
        self.assertEqual(ff_map.map, "Bermuda")
        self.assertTrue(ff_map.is_confident)

        # Free Fire alias check
        ff_alias_map = self.detector.detect_map(game="Free Fire", source="simulated", map_hint="Bermuda")
        self.assertEqual(ff_alias_map.map, "Bermuda")
        self.assertTrue(ff_alias_map.is_confident)

    # -------------------------------------------------------------
    # 2. NON-HARDCODED MAP ARCHITECTURE
    # -------------------------------------------------------------
    def test_dynamic_map_registration_not_hardcoded(self):
        """
        Requirement: 'Do not hard-code all maps into the core architecture.'
        Verify that new games and custom maps can be registered dynamically at runtime.
        """
        custom_registry = GameMapRegistry()
        custom_registry.register_maps("SciFiTactics2026", ["NebulaColosseum", "QuantumBase"])

        custom_detector = GameMapDetector(map_registry=custom_registry)

        # Verify custom registered map succeeds
        detected = custom_detector.detect_map(
            game="SciFiTactics2026",
            source="simulated",
            map_hint="NebulaColosseum"
        )
        self.assertTrue(detected.is_confident)
        self.assertEqual(detected.map, "NebulaColosseum")

        # Dynamically add single map to an existing game
        custom_registry.register_map("Valorant", "CommunityCustomMap")
        val_custom = custom_detector.detect_map(
            game="Valorant",
            source="simulated",
            map_hint="CommunityCustomMap"
        )
        self.assertTrue(val_custom.is_confident)
        self.assertEqual(val_custom.map, "CommunityCustomMap")

    # -------------------------------------------------------------
    # 3. UNAVAILABLE MAP -> "Map not detected."
    # -------------------------------------------------------------
    def test_map_unavailable_reports_map_not_detected(self):
        """
        Requirement: If map information is unavailable: 'Map not detected.'
        """
        # Case A: map_hint is None
        res_none = self.detector.detect_map(game="Valorant", source="simulated", map_hint=None)
        self.assertFalse(res_none.is_confident)
        self.assertIsNone(res_none.map)
        self.assertEqual(res_none.message, "Map not detected.")
        self.assertIn("Map not detected.", res_none.format_display())

        # Case B: explicit unknown_map scenario
        res_scenario = self.detector.detect_map(
            game="BGMI",
            source="simulated",
            scenario="unknown_map"
        )
        self.assertFalse(res_scenario.is_confident)
        self.assertEqual(res_scenario.message, "Map not detected.")

        # Case C: map not belonging to game (e.g. Ascent in BGMI)
        res_mismatched = self.detector.detect_map(
            game="BGMI",
            source="simulated",
            map_hint="Ascent"  # Ascent is Valorant, not BGMI
        )
        self.assertFalse(res_mismatched.is_confident)
        self.assertEqual(res_mismatched.message, "Map not detected.")

    # -------------------------------------------------------------
    # 4. LOW CONFIDENCE DETECTION
    # -------------------------------------------------------------
    def test_low_confidence_map_detection(self):
        """
        Low confidence scores (< 0.6) must result in is_confident=False and 'Map not detected.'
        """
        res_low = self.detector.detect_map(
            game="Valorant",
            source="simulated",
            map_hint="Ascent",
            confidence_override=0.4
        )
        self.assertFalse(res_low.is_confident)
        self.assertEqual(res_low.confidence, 0.4)
        self.assertEqual(res_low.message, "Map not detected.")

    # -------------------------------------------------------------
    # 5. MANUAL MAP INPUT
    # -------------------------------------------------------------
    def test_manual_map_input(self):
        """
        Allows manual map input with 100% confidence.
        """
        manual_map = self.detector.detect_map(
            game="Valorant",
            source="manual",
            map_hint="Sunset"
        )
        self.assertTrue(manual_map.is_confident)
        self.assertEqual(manual_map.confidence, 1.0)
        self.assertEqual(manual_map.detection_source, "manual")
        self.assertEqual(manual_map.map, "Sunset")

        # Empty manual input should trigger Map not detected.
        empty_manual = self.detector.detect_map(
            game="Valorant",
            source="manual",
            map_hint=""
        )
        self.assertFalse(empty_manual.is_confident)
        self.assertEqual(empty_manual.message, "Map not detected.")

    # -------------------------------------------------------------
    # 6. MATCH DETECTION & MATCHCONTEXT STRUCTURE
    # -------------------------------------------------------------
    def test_detect_match_all_fields(self):
        """
        Detect or allow manual input for:
        - map
        - game mode
        - match ID
        - round number if applicable
        - detection confidence
        - detection source
        """
        match_ctx = self.detector.detect_match(
            game="Valorant",
            map_name="Ascent",
            game_mode="Competitive",
            match_id="VAL-MATCH-2026-X1",
            round_number=12,
            source="simulated",
            confidence_override=0.92
        )

        self.assertIsInstance(match_ctx, MatchContext)
        self.assertEqual(match_ctx.game, "Valorant")
        self.assertEqual(match_ctx.map, "Ascent")
        self.assertEqual(match_ctx.game_mode, "Competitive")
        self.assertEqual(match_ctx.match_id, "VAL-MATCH-2026-X1")
        self.assertEqual(match_ctx.round_number, 12)
        self.assertEqual(match_ctx.confidence, 0.92)
        self.assertEqual(match_ctx.detection_source, "simulated")
        self.assertFalse(match_ctx.is_confirmed)
        self.assertIsNotNone(match_ctx.map_detection)
        self.assertTrue(match_ctx.map_detection.is_confident)

    # -------------------------------------------------------------
    # 7. MANUAL CONFIRMATION
    # -------------------------------------------------------------
    def test_manual_confirmation_of_match_context(self):
        """
        Allow manual confirmation and overrides on match context.
        """
        initial = self.detector.detect_match(
            game="Valorant",
            scenario="unknown_map"
        )
        self.assertIsNone(initial.map)
        self.assertFalse(initial.is_confirmed)

        confirmed = self.detector.confirm_match_context(
            match_context=initial,
            map_name="Bind",
            game_mode="Premier",
            match_id="CONFIRMED-MATCH-99",
            round_number=7
        )

        self.assertTrue(confirmed.is_confirmed)
        self.assertEqual(confirmed.map, "Bind")
        self.assertEqual(confirmed.game_mode, "Premier")
        self.assertEqual(confirmed.match_id, "CONFIRMED-MATCH-99")
        self.assertEqual(confirmed.round_number, 7)
        self.assertEqual(confirmed.confidence, 1.0)
        self.assertEqual(confirmed.detection_source, "manual")

    # -------------------------------------------------------------
    # 8. CONNECT CONFIRMED DATA TO ACTIVE SESSION
    # -------------------------------------------------------------
    def test_connect_confirmed_data_to_active_session_storage(self):
        """
        Requirement: 'Connect confirmed data to the active Session.'
        Verifies updating an active Session directly in SessionStorage.
        """
        # Create an initial active session with missing/preliminary map and match info
        initial_session = self.storage.create_session({
            "session_id": "session-active-401",
            "game": "Valorant",
            "game_mode": "Unrated",
            "map": "Unknown",
            "started_at": "2026-09-18T20:00:00"
        })

        match_ctx = self.detector.manual_match_input(
            game="Valorant",
            map_name="Ascent",
            game_mode="Competitive",
            match_id="MATCH-ACT-401",
            round_number=13
        )

        updated_session = self.detector.connect_confirmed_data_to_session(
            session_or_id=initial_session.session_id,
            match_context=match_ctx,
            storage=self.storage
        )

        self.assertEqual(updated_session.session_id, "session-active-401")
        self.assertEqual(updated_session.map, "Ascent")
        self.assertEqual(updated_session.game_mode, "Competitive")
        self.assertEqual(updated_session.match_id, "MATCH-ACT-401")
        self.assertEqual(updated_session.round_number, 13)
        self.assertEqual(updated_session.performance_metrics.get("round_number"), 13)
        self.assertEqual(updated_session.data_source, "manual")

        # Verify persisted in database
        persisted = self.storage.get_session_by_id("session-active-401")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.map, "Ascent")
        self.assertEqual(persisted.match_id, "MATCH-ACT-401")
        self.assertEqual(persisted.round_number, 13)

    def test_connect_confirmed_data_via_lifecycle_manager(self):
        """
        Verifies connecting confirmed MatchContext to active Session in SessionLifecycleManager.
        """
        # Start gaming session
        self.lifecycle.start_gaming(game_hint="BGMI", map_hint="Erangel")
        session = self.lifecycle.confirm_and_start_session(session_id="session-bgmi-live")
        self.assertEqual(self.lifecycle.state, STATE_PLAYING)

        # Detect mid-game match update (e.g. round number or specific match id)
        match_ctx = self.detector.detect_match(
            game="BGMI",
            map_name="Erangel",
            game_mode="Classic Battle Royale",
            match_id="MATCH-BGMI-007",
            round_number=4,
            source="simulated"
        )
        match_ctx.confirm()

        updated = self.lifecycle.connect_match_context(match_ctx)
        self.assertEqual(updated.match_id, "MATCH-BGMI-007")
        self.assertEqual(updated.round_number, 4)

        # Confirm lifecycle current_session matches
        self.assertEqual(self.lifecycle.current_session.match_id, "MATCH-BGMI-007")
        self.assertEqual(self.lifecycle.current_session.round_number, 4)

    # -------------------------------------------------------------
    # 9. HONEST SOURCE INTEGRITY
    # -------------------------------------------------------------
    def test_disallow_fake_api_log_claims(self):
        """
        Do not claim API or game log detection when disconnected.
        """
        with self.assertRaises(DetectionConnectionError):
            self.detector.detect_map(game="Valorant", source="api")

        with self.assertRaises(DetectionConnectionError):
            self.detector.detect_match(game="Valorant", source="game_log")

    # -------------------------------------------------------------
    # 10. REST API ENDPOINTS
    # -------------------------------------------------------------
    def test_api_detect_map_and_match_endpoints(self):
        """
        Verify FastAPI endpoints for Phase 4.
        """
        # 1. detect-map
        res_map = self.client.post("/api/detection/detect-map", json={
            "game": "Valorant",
            "map": "Ascent",
            "source": "simulated"
        })
        self.assertEqual(res_map.status_code, 200)
        data = res_map.json()
        self.assertEqual(data["map"], "Ascent")
        self.assertTrue(data["is_confident"])

        # 2. detect-match
        res_match = self.client.post("/api/detection/detect-match", json={
            "game": "Valorant",
            "map": "Ascent",
            "game_mode": "Competitive",
            "round_number": 5,
            "source": "simulated"
        })
        self.assertEqual(res_match.status_code, 200)
        match_data = res_match.json()
        self.assertEqual(match_data["game"], "Valorant")
        self.assertEqual(match_data["map"], "Ascent")
        self.assertEqual(match_data["round_number"], 5)

        # 3. connect-match to created session
        import time
        unique_sid = f"api-session-test-{int(time.time() * 1000)}"
        res_create = self.client.post("/api/detection/confirm", json={
            "session_id": unique_sid,
            "game": "Valorant",
            "map": "Ascent",
            "started_at": "2026-09-18T21:00:00"
        })
        self.assertEqual(res_create.status_code, 200)

        res_conn = self.client.post("/api/detection/connect-match", json={
            "session_id": unique_sid,
            "match_context": {
                "game": "Valorant",
                "map": "Ascent",
                "game_mode": "Premier",
                "match_id": "API-MATCH-101",
                "round_number": 8
            }
        })
        self.assertEqual(res_conn.status_code, 200)
        conn_data = res_conn.json()
        self.assertEqual(conn_data["map"], "Ascent")
        self.assertEqual(conn_data["game_mode"], "Premier")
        self.assertEqual(conn_data["match_id"], "API-MATCH-101")
        self.assertEqual(conn_data["round_number"], 8)


if __name__ == "__main__":
    unittest.main()
