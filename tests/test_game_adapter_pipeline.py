"""
Unit and Integration Tests for Game Adapter Layer & 6-Stage Pipeline
Game -> Game Adapter -> Detection -> Metrics -> Tasks -> Planning
"""

import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db
from app.models import GameState
from app.game_adapter import (
    default_adapter_registry,
    default_pipeline_orchestrator,
    BGMIAdapter,
    ValorantAdapter,
    FreeFireAdapter,
    EldenRingAdapter,
    GenericGameAdapter,
    PipelineOrchestrator
)


class TestGameAdapterPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. ADAPTER REGISTRY & MATCHING
    # -------------------------------------------------------------
    def test_adapter_registry_defaults(self):
        supported = default_adapter_registry.list_supported_games()
        names = [g.game_name for g in supported]
        self.assertIn("BGMI", names)
        self.assertIn("Valorant", names)
        self.assertIn("Free Fire MAX", names)
        self.assertIn("Elden Ring", names)

    def test_adapter_alias_matching(self):
        # BGMI aliases
        self.assertEqual(default_adapter_registry.get_adapter("PUBG Mobile").game_name, "BGMI")
        self.assertEqual(default_adapter_registry.get_adapter("Battlegrounds Mobile India").game_name, "BGMI")

        # Valorant aliases
        self.assertEqual(default_adapter_registry.get_adapter("Val").game_name, "Valorant")
        self.assertEqual(default_adapter_registry.get_adapter("Riot Valorant").game_name, "Valorant")

        # Free Fire aliases
        self.assertEqual(default_adapter_registry.get_adapter("FF").game_name, "Free Fire MAX")
        self.assertEqual(default_adapter_registry.get_adapter("Free Fire").game_name, "Free Fire MAX")

        # Elden Ring aliases
        self.assertEqual(default_adapter_registry.get_adapter("Shadow of the Erdtree").game_name, "Elden Ring")

        # Fallback to generic
        unknown = default_adapter_registry.get_adapter("Super Mario 64")
        self.assertIsInstance(unknown, GenericGameAdapter)
        self.assertEqual(unknown.game_name, "Super Mario 64")

    # -------------------------------------------------------------
    # 2. TELEMETRY NORMALIZATION
    # -------------------------------------------------------------
    def test_telemetry_normalization(self):
        adapter = ValorantAdapter()
        raw_events = [
            {"event_type": "spike_planted", "site": "A"},
            {"event_type": "frag", "weapon": "Vandal", "headshot": True},
            {"event_type": "died", "killer": "Chamber"}
        ]
        norm = [adapter.normalize_telemetry_event(e) for e in raw_events]
        self.assertEqual(norm[0]["event_type"], "objective_planted")
        self.assertEqual(norm[1]["event_type"], "kill")
        self.assertEqual(norm[2]["event_type"], "death")

        stats = adapter.extract_session_stats(raw_events)
        self.assertEqual(stats["kills"], 1)
        self.assertEqual(stats["deaths"], 1)
        self.assertEqual(stats["kd_ratio"], 1.0)

    # -------------------------------------------------------------
    # 3. STATE MACHINE DETECTION BRIDGING
    # -------------------------------------------------------------
    def test_state_transitions_from_telemetry(self):
        adapter = BGMIAdapter()
        state = GameState.LOBBY
        state = adapter.detect_state_transition(state, {"event_type": "plane_spawn"})
        self.assertEqual(state, GameState.MATCH_STARTED)

        state = adapter.detect_state_transition(state, {"event_type": "parachute_land"})
        self.assertEqual(state, GameState.ACTIVE_GAMEPLAY)

        state = adapter.detect_state_transition(state, {"event_type": "chicken_dinner"})
        self.assertEqual(state, GameState.MATCH_FINISHED)

    # -------------------------------------------------------------
    # 4. METRICS CALCULATION (SAFE / NO INVENTED DATA)
    # -------------------------------------------------------------
    def test_metrics_calculation_preserves_missing_data(self):
        adapter = BGMIAdapter()
        session_dict = {
            "session_id": "test_m_1",
            "game": "BGMI",
            "map": "Erangel",
            "kills": 6,
            "deaths": 2,
            "duration": "24 min",
            "result": "Win"
            # Note: accuracy and damage are absent!
        }
        report = adapter.calculate_metrics(session_dict)
        self.assertEqual(report.kd_ratio, 3.0)
        self.assertEqual(report.duration_display, "24 min")
        self.assertIsNone(report.accuracy)
        self.assertIn("K/D: 3", report.format_display())

    # -------------------------------------------------------------
    # 5. FULL 6-STAGE PIPELINE: BGMI
    # -------------------------------------------------------------
    def test_full_6_stage_pipeline_bgmi(self):
        from app.models import PipelineRunRequest
        req = PipelineRunRequest(
            game="BGMI",
            map="Erangel",
            mode="Classic Battle Royale",
            raw_events=[
                {"event_type": "plane_spawn", "timestamp": "00:01"},
                {"event_type": "parachute_land", "area": "Pochinki"},
                {"event_type": "frag", "weapon": "M416"},
                {"event_type": "frag", "weapon": "Kar98k"},
                {"event_type": "safezone_update", "circle": 2},
                {"event_type": "chicken_dinner", "rank": 1}
            ]
        )
        res = default_pipeline_orchestrator.run_pipeline(req)

        self.assertEqual(res.game, "BGMI")
        self.assertEqual(res.map, "Erangel")
        self.assertEqual(res.adapter_used, "BGMIAdapter")

        # Verify all 6 stages exist in chronological order
        stage_names = [s.stage for s in res.stages]
        expected_stages = ["game", "game_adapter", "detection", "metrics", "tasks", "planning"]
        self.assertEqual(stage_names, expected_stages)

        # Stage 3: Detection
        self.assertEqual(res.detection["current_game_state"], GameState.MATCH_FINISHED.value)
        self.assertTrue(res.detection["is_valid_map"])

        # Stage 4: Metrics
        self.assertEqual(res.metrics["kills"], 2)
        self.assertEqual(res.metrics["deaths"], 0)

        # Stage 5: Tasks
        self.assertIsInstance(res.tasks, list)

        # Stage 6: Planning
        self.assertIn("plan_id", res.plan)
        self.assertIn("focus_area", res.plan)
        self.assertGreater(len(res.plan["strategy"]), 0)

    # -------------------------------------------------------------
    # 6. FULL 6-STAGE PIPELINE: VALORANT
    # -------------------------------------------------------------
    def test_full_6_stage_pipeline_valorant(self):
        from app.models import PipelineRunRequest
        req = PipelineRunRequest(
            game="Valorant",
            map="Ascent",
            mode="Competitive",
            raw_events=[
                {"event_type": "buy_phase_start"},
                {"event_type": "barriers_drop"},
                {"event_type": "first_kill", "weapon": "Ghost"},
                {"event_type": "spike_planted", "site": "B"},
                {"event_type": "round_won"}
            ]
        )
        res = default_pipeline_orchestrator.run_pipeline(req)

        self.assertEqual(res.game, "Valorant")
        self.assertEqual(res.adapter_used, "ValorantAdapter")
        self.assertEqual(res.detection["current_game_state"], GameState.ROUND_FINISHED.value)
        self.assertEqual(res.metrics["kills"], 1)

    # -------------------------------------------------------------
    # 7. GENERIC FALLBACK FOR UNKNOWN GAME
    # -------------------------------------------------------------
    def test_pipeline_generic_fallback(self):
        from app.models import PipelineRunRequest
        req = PipelineRunRequest(
            game="StarCraft II",
            map="Lost Temple",
            mode="1v1 Ranked"
        )
        res = default_pipeline_orchestrator.run_pipeline(req)
        self.assertEqual(res.game, "StarCraft II")
        self.assertEqual(res.adapter_used, "StarCraft IIAdapter")
        self.assertEqual(len(res.stages), 6)

    # -------------------------------------------------------------
    # 8. REST API ENDPOINTS
    # -------------------------------------------------------------
    def test_api_adapters_endpoints(self):
        res = self.client.get("/api/adapters")
        self.assertEqual(res.status_code, 200)
        adapters = res.json()
        self.assertIsInstance(adapters, list)
        self.assertGreaterEqual(len(adapters), 4)

        # Test single adapter lookup
        res_val = self.client.get("/api/adapters/Valorant")
        self.assertEqual(res_val.status_code, 200)
        val_data = res_val.json()
        self.assertEqual(val_data["game_name"], "Valorant")
        self.assertIn("Tactical FPS", val_data["genre"])
        self.assertIn("Ascent", val_data["supported_maps"])

    def test_api_pipeline_run_endpoint(self):
        payload = {
            "game": "BGMI",
            "map": "Erangel",
            "mode": "Classic Battle Royale",
            "raw_events": [
                {"event_type": "plane_spawn"},
                {"event_type": "frag", "weapon": "AKM"},
                {"event_type": "died"}
            ]
        }
        res = self.client.post("/api/pipeline/run", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["game"], "BGMI")
        self.assertEqual(data["adapter_used"], "BGMIAdapter")
        self.assertEqual(len(data["stages"]), 6)
        self.assertIn("kd_ratio", data["metrics"])
        self.assertIn("plan", data)


if __name__ == "__main__":
    unittest.main()
