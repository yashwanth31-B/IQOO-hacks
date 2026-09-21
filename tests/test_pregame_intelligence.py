"""
Tests for Pre-Game Intelligence System (Phase 13 Upgrade)
Verifies all 11 required scenarios from Requirement 20:
1. New player
2. Returning player
3. Player with substantial history (experienced)
4. Unknown game
5. Unknown map
6. No map history
7. No weapon history
8. Insufficient data
9. AI timeout
10. AI failure
11. Plan generated within approximately 3 seconds when cached data is available
"""

import time
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    Session,
    PlayerExperienceProfile,
    MapAreaIntelligence,
    PreGameIntelligenceResponse
)
from app.session_storage import SessionStorage
from app.player_experience import PlayerExperienceDetector
from app.map_intelligence import MapIntelligenceModule
from app.weapon_intelligence import WeaponIntelligenceModule
from app.pregame_intelligence_engine import PreGameIntelligenceEngine, default_pregame_intelligence_engine
from app.detection import GameMapDetector


class TestPreGameIntelligenceSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # -----------------------------------------------------------------
    # SCENARIO 1: NEW PLAYER
    # -----------------------------------------------------------------
    def test_01_new_player(self):
        """Scenario 1: New player with 0 recorded sessions in the target game."""
        # Query experience profile for a brand new game
        detector = PlayerExperienceDetector()
        profile = detector.get_experience_profile(game="UnplayedGameTitleXYZ", player_name="Manoj")

        self.assertEqual(profile.experience_level, "NEW PLAYER")
        self.assertEqual(profile.sessions_in_current_game, 0)
        self.assertEqual(profile.welcome_header, "👋 WELCOME")
        self.assertIn("first recorded UnplayedGameTitleXYZ session", profile.message)
        self.assertIn("Second Brain is learning your play style", profile.message)
        self.assertEqual(profile.data_source, "PERSONAL HISTORY")

        # Run pre-game intelligence for new game
        engine = PreGameIntelligenceEngine(experience_detector=detector)
        res = engine.run_pregame_intelligence(game="UnplayedGameTitleXYZ")

        self.assertEqual(res.player_experience.experience_level, "NEW PLAYER")
        self.assertEqual(res.adaptive_plan.plan_type, "BEGINNER PLAN")
        self.assertIn("Survival + map awareness", res.adaptive_plan.focus)

    # -----------------------------------------------------------------
    # SCENARIO 2: RETURNING PLAYER
    # -----------------------------------------------------------------
    def test_02_returning_player(self):
        """Scenario 2: Returning player (1 to 4 sessions) - not yet experienced."""
        # Create mock storage with 2 sessions for a specific game
        import tempfile
        import os
        tmp_db = os.path.join(tempfile.gettempdir(), f"test_ret_player_{time.time_ns()}.db")
        storage = SessionStorage(db_path=tmp_db)

        # Add 2 sessions
        storage.create_session(Session(session_id="ret-1", game="ReturningTestGame", kills=4, deaths=2, kd_ratio=2.0))
        storage.create_session(Session(session_id="ret-2", game="ReturningTestGame", kills=3, deaths=3, kd_ratio=1.0))

        detector = PlayerExperienceDetector(storage=storage)
        profile = detector.get_experience_profile(game="ReturningTestGame", player_name="Manoj")

        self.assertEqual(profile.experience_level, "RETURNING PLAYER")
        self.assertEqual(profile.sessions_in_current_game, 2)
        self.assertEqual(profile.welcome_header, "👋 WELCOME BACK")
        self.assertIn("You've played ReturningTestGame 2 times", profile.message)
        self.assertIn("Your previous gaming memory is ready", profile.message)

        # Check adaptive plan for returning player
        engine = PreGameIntelligenceEngine(experience_detector=detector, storage=storage)
        res = engine.run_pregame_intelligence(game="ReturningTestGame")

        self.assertEqual(res.player_experience.experience_level, "RETURNING PLAYER")
        self.assertEqual(res.adaptive_plan.plan_type, "RETURNING PLAYER PLAN")
        self.assertIn("Improve previous weakness", res.adaptive_plan.focus)

        if os.path.exists(tmp_db):
            os.remove(tmp_db)

    # -----------------------------------------------------------------
    # SCENARIO 3: PLAYER WITH SUBSTANTIAL HISTORY (EXPERIENCED)
    # -----------------------------------------------------------------
    def test_03_experienced_player(self):
        """Scenario 3: Experienced player with >= 5 recorded sessions."""
        # BGMI in database has substantial history (118 sessions)
        detector = PlayerExperienceDetector()
        profile = detector.get_experience_profile(game="BGMI", player_name="Manoj")

        self.assertEqual(profile.experience_level, "EXPERIENCED PLAYER")
        self.assertGreaterEqual(profile.sessions_in_current_game, 5)
        self.assertEqual(profile.welcome_header, "🎯 PLAYER PROFILE")
        self.assertIn("recorded sessions", profile.message)
        self.assertIn("Strongest recorded K/D", profile.message)
        self.assertIn("Most played map", profile.message)

        # Pre-game plan for experienced player
        engine = PreGameIntelligenceEngine(experience_detector=detector)
        res = engine.run_pregame_intelligence(game="BGMI", map_name="Erangel")

        self.assertEqual(res.player_experience.experience_level, "EXPERIENCED PLAYER")
        self.assertEqual(res.adaptive_plan.plan_type, "EXPERIENCED PLAYER PLAN")
        self.assertIn("Performance optimization", res.adaptive_plan.focus)
        self.assertEqual(res.recommended_start["risk"], "HIGH")
        self.assertIn("Experienced players", res.recommended_start["recommended_for"])

    # -----------------------------------------------------------------
    # SCENARIO 4: UNKNOWN GAME
    # -----------------------------------------------------------------
    def test_04_unknown_game(self):
        """Scenario 4: Game not recognized in game registry."""
        res = default_pregame_intelligence_engine.run_pregame_intelligence(
            game="NonExistentGame2026",
            map_name="UnknownMap"
        )

        self.assertFalse(res.game_detection.is_confident)
        self.assertLessEqual(res.game_detection.confidence, 0.45)
        self.assertEqual(len(res.map_areas), 0)
        self.assertEqual(len(res.low_enemy_areas), 0)
        self.assertEqual(len(res.high_activity_areas), 0)
        # Verify hallucination protection: no fake weapons or map areas invented
        self.assertEqual(res.data_sources["map_areas"], "NO DATA")

    # -----------------------------------------------------------------
    # SCENARIO 5: UNKNOWN MAP
    # -----------------------------------------------------------------
    def test_05_unknown_map(self):
        """Scenario 5: Game is known (BGMI), but map is completely unknown."""
        res = default_pregame_intelligence_engine.run_pregame_intelligence(
            game="BGMI",
            map_name="AtlantisUnderwaterCity"
        )

        self.assertFalse(res.map_detection.is_confident)
        self.assertIn("Map not detected", res.map_detection.message)
        self.assertEqual(len(res.map_areas), 0)
        self.assertIsNone(res.recommended_start)
        # Does not hallucinate map locations
        low_areas, low_msg = default_pregame_intelligence_engine.map_module.get_low_enemy_areas("BGMI", "AtlantisUnderwaterCity")
        self.assertEqual(len(low_areas), 0)
        self.assertEqual(low_msg, "Not enough data to determine enemy activity.")

    # -----------------------------------------------------------------
    # SCENARIO 6: NO MAP HISTORY
    # -----------------------------------------------------------------
    def test_06_no_map_history(self):
        """Scenario 6: Valid game & map, but player has 0 historical sessions on this map."""
        map_module = MapIntelligenceModule()
        # Karakin is a valid BGMI map in registry without area telemetry
        areas = map_module.get_map_areas("BGMI", "Karakin")
        self.assertEqual(len(areas), 0)

        # On Erangel (where map data exists), verified areas are loaded cleanly
        erangel_areas = map_module.get_map_areas("BGMI", "Erangel")
        self.assertGreater(len(erangel_areas), 0)
        area_names = [a.area_name for a in erangel_areas]
        self.assertIn("Pochinki", area_names)
        self.assertIn("Gatka", area_names)

    # -----------------------------------------------------------------
    # SCENARIO 7: NO WEAPON HISTORY
    # -----------------------------------------------------------------
    def test_07_no_weapon_history(self):
        """Scenario 7: Game has weapons, but player has never used them."""
        import tempfile
        import os
        tmp_db = os.path.join(tempfile.gettempdir(), f"test_no_wep_{time.time_ns()}.db")
        storage = SessionStorage(db_path=tmp_db)

        weapon_mod = WeaponIntelligenceModule(storage=storage)
        rec = weapon_mod.calculate_best_loadout(game="BGMI", map_name="Erangel")

        self.assertFalse(rec.personal_history_found)
        self.assertEqual(rec.data_source, "GENERAL GAME INFORMATION")
        self.assertIn("No personal performance history available", rec.explanation)
        self.assertEqual(rec.confidence, "Low")

        if os.path.exists(tmp_db):
            os.remove(tmp_db)

    # -----------------------------------------------------------------
    # SCENARIO 8: INSUFFICIENT DATA
    # -----------------------------------------------------------------
    def test_08_insufficient_data(self):
        """Scenario 8: Strict hallucination protection when data is insufficient."""
        map_mod = MapIntelligenceModule()
        low_areas, low_msg = map_mod.get_low_enemy_areas("Chess", "Standard 8x8 Board")
        self.assertEqual(len(low_areas), 0)
        self.assertEqual(low_msg, "Not enough data to determine enemy activity.")

        # Ensure system never claims 'There are no enemies here'
        low_bgmi, bgmi_msg = map_mod.get_low_enemy_areas("BGMI", "Erangel")
        self.assertNotIn("There are no enemies here", bgmi_msg)
        self.assertEqual(bgmi_msg, "Historically lower recorded enemy activity.")

    # -----------------------------------------------------------------
    # SCENARIO 9: AI TIMEOUT
    # -----------------------------------------------------------------
    def test_09_ai_timeout(self):
        """Scenario 9: If AI generation times out, already available factual data is returned first."""
        engine = PreGameIntelligenceEngine()
        res = engine.run_pregame_intelligence(
            game="BGMI",
            map_name="Erangel",
            simulate_timeout=True
        )

        self.assertIsNotNone(res.adaptive_plan)
        self.assertEqual(res.adaptive_plan.plan_type, "FAST FALLBACK PLAN")
        self.assertEqual(res.adaptive_plan.data_source, "HISTORICAL GAME DATA")
        # Factual start area and map data must be intact
        self.assertIsNotNone(res.recommended_start)
        self.assertGreater(len(res.map_areas), 0)

    # -----------------------------------------------------------------
    # SCENARIO 10: AI FAILURE
    # -----------------------------------------------------------------
    def test_10_ai_failure(self):
        """Scenario 10: If AI generation fails, deterministic factual plan is returned safely."""
        engine = PreGameIntelligenceEngine()
        res = engine.run_pregame_intelligence(
            game="BGMI",
            map_name="Erangel",
            simulate_failure=True
        )

        self.assertIsNotNone(res.adaptive_plan)
        self.assertEqual(res.adaptive_plan.plan_type, "GENERAL PLAN")
        self.assertEqual(res.adaptive_plan.data_source, "HISTORICAL GAME DATA")
        self.assertGreater(len(res.adaptive_plan.strategy_steps), 0)

    # -----------------------------------------------------------------
    # SCENARIO 11: SUB-3-SECOND PERFORMANCE RESULT
    # -----------------------------------------------------------------
    def test_11_sub_3_second_performance(self):
        """Scenario 11: Plan and complete pre-game intelligence generated in < 3 seconds."""
        engine = PreGameIntelligenceEngine()

        t0 = time.perf_counter()
        res = engine.run_pregame_intelligence(
            game="BGMI",
            map_name="Erangel",
            game_mode="Classic"
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        self.assertLess(elapsed_ms, 3000.0, f"Expected < 3000ms, got {elapsed_ms}ms")
        self.assertLess(res.generation_time_ms, 3000.0)
        self.assertEqual(res.status, "PRE-GAME INTELLIGENCE READY")
        print(f"\n[Scenario 11 Benchmark] Pre-Game Intelligence completed in: {elapsed_ms:.2f}ms")

    # -----------------------------------------------------------------
    # END-TO-END FASTAPI ENDPOINT TESTS
    # -----------------------------------------------------------------
    def test_12_api_endpoints_integration(self):
        """Verifies all new /api/pregame/* endpoints via FastAPI TestClient."""
        # 1. Main Pre-Game Intelligence endpoint
        resp = self.client.post("/api/pregame/intelligence", json={
            "game": "BGMI",
            "map": "Erangel",
            "game_mode": "Classic",
            "player_name": "Manoj"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("player_experience", data)
        self.assertIn("recommended_start", data)
        self.assertIn("weapon_recommendation", data)
        self.assertIn("rotation_plan", data)
        self.assertIn("adaptive_plan", data)
        self.assertLess(data["generation_time_ms"], 3000.0)

        # 2. Experience profile endpoint
        exp_resp = self.client.get("/api/pregame/experience?game=BGMI&player_name=Manoj")
        self.assertEqual(exp_resp.status_code, 200)
        exp_data = exp_resp.json()
        self.assertEqual(exp_data["experience_level"], "EXPERIENCED PLAYER")

        # 3. Map intelligence endpoint
        map_resp = self.client.get("/api/pregame/map-intelligence?game=BGMI&map=Erangel")
        self.assertEqual(map_resp.status_code, 200)
        map_data = map_resp.json()
        self.assertGreater(len(map_data["map_areas"]), 0)
        self.assertEqual(map_data["low_enemy_message"], "Historically lower recorded enemy activity.")

        # 4. Weapons endpoint
        wep_resp = self.client.get("/api/pregame/weapons?game=BGMI&map=Erangel")
        self.assertEqual(wep_resp.status_code, 200)
        wep_data = wep_resp.json()
        self.assertGreater(len(wep_data["weapons"]), 0)
        self.assertEqual(wep_data["recommendation"]["primary_weapon"], "M416")

        # 5. Dashboard overview integration
        dash_resp = self.client.get("/api/dashboard/overview?game=BGMI&map=Erangel")
        self.assertEqual(dash_resp.status_code, 200)
        dash_data = dash_resp.json()
        self.assertIn("pregame_intelligence", dash_data)
        self.assertEqual(dash_data["pregame_intelligence"]["status"], "PRE-GAME INTELLIGENCE READY")


if __name__ == "__main__":
    unittest.main()
