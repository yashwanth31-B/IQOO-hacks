import os
import sys
import unittest
from typing import List, Dict, Any
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import (
    GameState,
    GameStateSnapshot,
    StateTransitionRecord,
    StateUpdateRequest
)
from app.game_state import (
    GameStateDetector,
    GameStateTransitionError,
    GameStateError,
    GAME_PROFILES,
    ManualGameStateProvider,
    SimulatedGameStateProvider,
    VisionGameStateProvider,
    TelemetryGameStateProvider,
    LogGameStateProvider,
    ApiGameStateProvider
)
from app.main import app


class TestPhase5GameStateDetection(unittest.TestCase):
    """
    Phase 5: Generic Game State Detection Layer Tests
    
    Verifies all Phase 5 requirements:
    1. Canonical states representation:
       - lobby, loading, match_started, active_gameplay, round_started,
         round_finished, match_finished, unknown
    2. Different games may use different states.
    3. Normalized internal state model and exact formatted display:
       GAME:
       BGMI

       MAP:
       Erangel

       STATE:
       ACTIVE_GAMEPLAY

       MATCH_TIME:
       18:42
    4. Do not implement computer vision yet.
    5. Simulated and manual state updates for MVP.
    6. Extensible provider architecture for telemetry, logs, APIs, or CV.
    7. Do not invent state information.
    8. Test all state transitions.
    9. REST API endpoints for Game State.
    """

    def setUp(self):
        self.detector = GameStateDetector(strict_transitions=True)
        self.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. CANONICAL STATES REPRESENTATION
    # -------------------------------------------------------------
    def test_all_eight_canonical_states_exist(self):
        """
        Verify all 8 states specified in requirements exist on GameState.
        """
        expected_states = [
            "lobby",
            "loading",
            "match_started",
            "active_gameplay",
            "round_started",
            "round_finished",
            "match_finished",
            "unknown"
        ]
        actual_states = [s.value for s in GameState]
        for state in expected_states:
            self.assertIn(state, actual_states)

    def test_from_string_normalization(self):
        """
        Verify robust parsing and normalization from various string formats.
        """
        self.assertEqual(GameState.from_string("active_gameplay"), GameState.ACTIVE_GAMEPLAY)
        self.assertEqual(GameState.from_string("ACTIVE_GAMEPLAY"), GameState.ACTIVE_GAMEPLAY)
        self.assertEqual(GameState.from_string("Active Gameplay"), GameState.ACTIVE_GAMEPLAY)
        self.assertEqual(GameState.from_string("round-started"), GameState.ROUND_STARTED)
        self.assertEqual(GameState.from_string("ROUND_FINISHED"), GameState.ROUND_FINISHED)
        self.assertEqual(GameState.from_string("Lobby"), GameState.LOBBY)
        self.assertEqual(GameState.from_string("loading"), GameState.LOADING)
        self.assertEqual(GameState.from_string("match_finished"), GameState.MATCH_FINISHED)
        self.assertEqual(GameState.from_string("non_existent_state"), GameState.UNKNOWN)
        self.assertEqual(GameState.from_string(None), GameState.UNKNOWN)

    # -------------------------------------------------------------
    # 2. NORMALIZED STATE MODEL & FORMATTED DISPLAY
    # -------------------------------------------------------------
    def test_normalized_model_and_exact_display_format(self):
        """
        Verify exact display formatting from requirement example:
        GAME:
        BGMI

        MAP:
        Erangel

        STATE:
        ACTIVE_GAMEPLAY

        MATCH_TIME:
        18:42
        """
        snapshot = GameStateSnapshot(
            game="BGMI",
            map="Erangel",
            state=GameState.ACTIVE_GAMEPLAY,
            match_time="18:42"
        )

        expected = "GAME:\nBGMI\n\nMAP:\nErangel\n\nSTATE:\nACTIVE_GAMEPLAY\n\nMATCH_TIME:\n18:42"
        self.assertEqual(snapshot.format_display(), expected)

    # -------------------------------------------------------------
    # 3. DIFFERENT GAMES USE DIFFERENT STATES
    # -------------------------------------------------------------
    def test_different_games_use_different_states(self):
        """
        Requirement: 'Different games may use different states.'
        Verify game profiles differentiate round-based vs continuous vs turn-based states.
        """
        # Valorant is round-based: supports round_started and round_finished
        val_states = self.detector.get_supported_states(game="Valorant")
        self.assertIn(GameState.ROUND_STARTED, val_states)
        self.assertIn(GameState.ROUND_FINISHED, val_states)
        self.assertIn(GameState.ACTIVE_GAMEPLAY, val_states)
        self.assertTrue(self.detector.get_profile("Valorant").is_round_based)

        # BGMI is a battle royale: continuous match without round resets
        bgmi_states = self.detector.get_supported_states(game="BGMI")
        self.assertIn(GameState.ACTIVE_GAMEPLAY, bgmi_states)
        self.assertIn(GameState.MATCH_FINISHED, bgmi_states)
        self.assertNotIn(GameState.ROUND_STARTED, bgmi_states)
        self.assertNotIn(GameState.ROUND_FINISHED, bgmi_states)
        self.assertFalse(self.detector.get_profile("BGMI").is_round_based)

        # Chess is match-based
        chess_states = self.detector.get_supported_states(game="Chess")
        self.assertIn(GameState.ACTIVE_GAMEPLAY, chess_states)
        self.assertIn(GameState.MATCH_FINISHED, chess_states)
        self.assertNotIn(GameState.LOADING, chess_states)

    # -------------------------------------------------------------
    # 4. TEST ALL STATE TRANSITIONS
    # -------------------------------------------------------------
    def test_all_state_transitions_round_based(self):
        """
        Requirement: 'Test all state transitions.'
        Tests complete lifecycle for round-based game (e.g. Valorant / CS2):
        unknown -> lobby -> loading -> match_started -> round_started ->
        active_gameplay -> round_finished -> round_started -> active_gameplay ->
        match_finished -> lobby
        """
        det = GameStateDetector(game="Valorant", map_name="Ascent", strict_transitions=True)
        self.assertEqual(det.get_current_state().state, GameState.UNKNOWN)

        # 1. unknown -> lobby
        s1 = det.transition_to(GameState.LOBBY)
        self.assertEqual(s1.state, GameState.LOBBY)

        # 2. lobby -> loading
        s2 = det.transition_to(GameState.LOADING)
        self.assertEqual(s2.state, GameState.LOADING)

        # 3. loading -> match_started
        s3 = det.transition_to(GameState.MATCH_STARTED)
        self.assertEqual(s3.state, GameState.MATCH_STARTED)

        # 4. match_started -> round_started (Round 1)
        s4 = det.transition_to(GameState.ROUND_STARTED, round_number=1, match_time="00:00")
        self.assertEqual(s4.state, GameState.ROUND_STARTED)
        self.assertEqual(s4.round_number, 1)

        # 5. round_started -> active_gameplay
        s5 = det.transition_to(GameState.ACTIVE_GAMEPLAY, round_number=1, match_time="00:30")
        self.assertEqual(s5.state, GameState.ACTIVE_GAMEPLAY)
        self.assertEqual(s5.match_time, "00:30")

        # 6. active_gameplay -> round_finished
        s6 = det.transition_to(GameState.ROUND_FINISHED, round_number=1, match_time="01:45")
        self.assertEqual(s6.state, GameState.ROUND_FINISHED)

        # 7. round_finished -> round_started (Round 2)
        s7 = det.transition_to(GameState.ROUND_STARTED, round_number=2, match_time="02:00")
        self.assertEqual(s7.state, GameState.ROUND_STARTED)
        self.assertEqual(s7.round_number, 2)

        # 8. round_started -> active_gameplay (Round 2)
        s8 = det.transition_to(GameState.ACTIVE_GAMEPLAY, round_number=2, match_time="02:25")
        self.assertEqual(s8.state, GameState.ACTIVE_GAMEPLAY)

        # 9. active_gameplay -> match_finished
        s9 = det.transition_to(GameState.MATCH_FINISHED, match_time="38:12")
        self.assertEqual(s9.state, GameState.MATCH_FINISHED)

        # 10. match_finished -> lobby
        s10 = det.transition_to(GameState.LOBBY)
        self.assertEqual(s10.state, GameState.LOBBY)

        # Verify history
        history = det.get_history()
        self.assertEqual(len(history), 10)
        self.assertTrue(all(r.is_valid for r in history))

    def test_all_state_transitions_battle_royale(self):
        """
        Requirement: 'Test all state transitions.'
        Tests complete Battle Royale match lifecycle (e.g. BGMI):
        lobby -> loading -> match_started -> active_gameplay -> match_finished -> lobby
        """
        det = GameStateDetector(game="BGMI", map_name="Erangel", strict_transitions=True)

        det.transition_to(GameState.LOBBY)
        self.assertEqual(det.get_current_state().state, GameState.LOBBY)

        det.transition_to(GameState.LOADING)
        self.assertEqual(det.get_current_state().state, GameState.LOADING)

        det.transition_to(GameState.MATCH_STARTED)
        self.assertEqual(det.get_current_state().state, GameState.MATCH_STARTED)

        det.transition_to(GameState.ACTIVE_GAMEPLAY, match_time="18:42")
        self.assertEqual(det.get_current_state().state, GameState.ACTIVE_GAMEPLAY)
        self.assertEqual(det.get_current_state().match_time, "18:42")

        det.transition_to(GameState.MATCH_FINISHED, match_time="24:10")
        self.assertEqual(det.get_current_state().state, GameState.MATCH_FINISHED)

        det.transition_to(GameState.LOBBY)
        self.assertEqual(det.get_current_state().state, GameState.LOBBY)

    def test_invalid_transition_rejected_in_strict_mode(self):
        """
        Illegal transitions must raise GameStateTransitionError when strict_transitions=True,
        unless force=True is provided.
        """
        det = GameStateDetector(game="Valorant", strict_transitions=True)
        det.transition_to(GameState.LOBBY)

        # Illegal jump: lobby -> round_finished
        with self.assertRaises(GameStateTransitionError):
            det.transition_to(GameState.ROUND_FINISHED)

        # Forced jump is permitted
        forced = det.transition_to(GameState.ROUND_FINISHED, force=True)
        self.assertEqual(forced.state, GameState.ROUND_FINISHED)

    # -------------------------------------------------------------
    # 5. SIMULATED AND MANUAL STATE UPDATES
    # -------------------------------------------------------------
    def test_simulated_and_manual_state_updates(self):
        """
        Requirement: 'Use simulated/manual state updates for the MVP.'
        """
        det = GameStateDetector(game="BGMI", map_name="Erangel")

        # Simulated update
        sim_res = det.simulate_state(
            state="active_gameplay",
            match_time="10:15",
            confidence=0.96
        )
        self.assertEqual(sim_res.state, GameState.ACTIVE_GAMEPLAY)
        self.assertEqual(sim_res.source, "simulated")
        self.assertEqual(sim_res.confidence, 0.96)

        # Manual update overrides with 1.0 confidence and manual source
        man_res = det.manual_update(
            state="match_finished",
            match_time="25:30"
        )
        self.assertEqual(man_res.state, GameState.MATCH_FINISHED)
        self.assertEqual(man_res.source, "manual")
        self.assertEqual(man_res.confidence, 1.0)

    # -------------------------------------------------------------
    # 6. EXTENSIBLE ARCHITECTURE & CV DISALLOWANCE
    # -------------------------------------------------------------
    def test_extensible_architecture_providers(self):
        """
        Requirement: 'The architecture must later allow real game telemetry,
        logs, APIs, or computer vision to provide state information.'
        'Do not implement computer vision yet.'
        """
        det = GameStateDetector()

        # Check providers exist
        self.assertIsInstance(det.manual_provider, ManualGameStateProvider)
        self.assertIsInstance(det.simulated_provider, SimulatedGameStateProvider)
        self.assertIsInstance(det.telemetry_provider, TelemetryGameStateProvider)
        self.assertIsInstance(det.log_provider, LogGameStateProvider)
        self.assertIsInstance(det.api_provider, ApiGameStateProvider)
        self.assertIsInstance(det.vision_provider, VisionGameStateProvider)

        # Computer vision must NOT be available
        self.assertFalse(det.vision_provider.is_available())
        with self.assertRaises(NotImplementedError):
            det.vision_provider.read_state()

    # -------------------------------------------------------------
    # 7. DO NOT INVENT STATE INFORMATION
    # -------------------------------------------------------------
    def test_do_not_invent_state_information(self):
        """
        Requirement: 'Do not invent state information.'
        Defaults to UNKNOWN when no state is reported.
        """
        blank_detector = GameStateDetector()
        self.assertEqual(blank_detector.get_current_state().state, GameState.UNKNOWN)
        self.assertIsNone(blank_detector.get_current_state().match_time)

    # -------------------------------------------------------------
    # 8. REST API ENDPOINTS
    # -------------------------------------------------------------
    def test_api_game_state_endpoints(self):
        """
        Verify FastAPI endpoints for Game State Detection.
        """
        # 1. Update state via API
        res_update = self.client.post("/api/game-state/update", json={
            "state": "active_gameplay",
            "game": "BGMI",
            "map": "Erangel",
            "match_time": "18:42",
            "source": "manual"
        })
        self.assertEqual(res_update.status_code, 200)
        data = res_update.json()
        self.assertEqual(data["game"], "BGMI")
        self.assertEqual(data["map"], "Erangel")
        self.assertEqual(data["state"], "active_gameplay")
        self.assertEqual(data["match_time"], "18:42")

        # 2. Get current state via API
        res_get = self.client.get("/api/game-state")
        self.assertEqual(res_get.status_code, 200)
        curr = res_get.json()
        self.assertEqual(curr["state"], "active_gameplay")

        # 3. Get transition history
        res_hist = self.client.get("/api/game-state/history")
        self.assertEqual(res_hist.status_code, 200)
        hist = res_hist.json()
        self.assertIsInstance(hist, list)
        self.assertGreaterEqual(len(hist), 1)

        # 4. Get supported states for game
        res_supp = self.client.get("/api/game-state/supported-states?game=Valorant")
        self.assertEqual(res_supp.status_code, 200)
        supp = res_supp.json()
        self.assertEqual(supp["game"], "Valorant")
        self.assertTrue(supp["is_round_based"])
        self.assertIn("round_started", supp["supported_states"])


if __name__ == "__main__":
    unittest.main()
