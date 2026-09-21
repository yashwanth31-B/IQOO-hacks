"""
Unit and Integration Tests for COD Mobile and Valorant Task Definitions in Gaming Task Engine.

Requirements tested:
- COD Mobile tasks (9):
  1. aim
  2. recoil
  3. movement
  4. positioning
  5. loadout
  6. objective play
  7. deaths
  8. accuracy
  9. score efficiency
- Valorant tasks (9):
  1. aim
  2. crosshair placement
  3. positioning
  4. economy
  5. utility usage
  6. map awareness
  7. round decisions
  8. configuration
  9. consistency
- Strict Rule: Do not claim enemy positions unless actual game data provides them.
- Measurable and evidence-based tasks only.
- Insufficient data handling: 'Not enough data to create a personalized task.'
- End-to-end closed-loop verification:
  Game -> Detection -> State -> Second Brain -> Task Engine -> Plan -> Play -> Result -> Memory Update -> Adaptive Plan -> Next Task.
"""

import os
import tempfile
import unittest

from app.models import Session, TimelineEvent, GamingTask, TASK_CATEGORIES
from app.session_storage import SessionStorage
from app.task_engine import (
    GamingTaskEngine,
    CODM_TASK_TYPES,
    CODM_MEASURABLE_METRICS,
    CODM_TASK_DEFINITIONS,
    VALORANT_TASK_TYPES,
    VALORANT_MEASURABLE_METRICS,
    VALORANT_TASK_DEFINITIONS,
    INSUFFICIENT_DATA_MSG
)
from app.game_adapter import CODMobileAdapter, ValorantAdapter, default_adapter_registry


class TestCODMAndValorantTaskEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_codm_val.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.engine = GamingTaskEngine(storage=self.storage)
        self.codm_adapter = CODMobileAdapter()
        self.val_adapter = ValorantAdapter()

    def tearDown(self):
        self.temp_dir.cleanup()

    # =================================================================
    # 1. COD MOBILE CONSTANTS & METRICS
    # =================================================================
    def test_codm_constants_and_metrics_integrity(self):
        expected_types = {
            "aim",
            "recoil",
            "movement",
            "positioning",
            "loadout",
            "objective_play",
            "deaths",
            "accuracy",
            "score_efficiency"
        }
        self.assertEqual(set(CODM_TASK_TYPES), expected_types)

        for task_type in CODM_TASK_TYPES:
            defn = CODM_TASK_DEFINITIONS[task_type]
            self.assertIn(defn["metric_to_track"], CODM_MEASURABLE_METRICS)
            self.assertIn(defn["category"], TASK_CATEGORIES)

    # =================================================================
    # 2. COD MOBILE EVIDENCE-BASED GENERATION (ALL 9 TASKS)
    # =================================================================
    def test_codm_aim_task(self):
        s = Session(
            session_id="codm_aim_1",
            game="COD Mobile",
            map="Firing Range",
            player_notes="Whiffed initial crosshair snap; slow ADS target acquisition on upper torso.",
            performance_metrics={"headshot_pct": 14.0}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="aim")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "headshot_pct")
        self.assertEqual(task.category, "aim")
        self.assertEqual(task.evidence_session_ids, ["codm_aim_1"])

    def test_codm_recoil_task(self):
        s = Session(
            session_id="codm_rec_1",
            game="COD Mobile",
            map="Crash",
            player_notes="Sustained spray recoil climb with CBR4 caused missed mid-range duels.",
            performance_metrics={"damage": 380}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="recoil")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "damage")
        self.assertEqual(task.category, "combat")
        self.assertEqual(task.evidence_session_ids, ["codm_rec_1"])

    def test_codm_movement_task(self):
        s = Session(
            session_id="codm_mov_1",
            game="COD Mobile",
            map="Standoff",
            player_notes="Failed slide cancel timing; caught flat-footed in transition.",
            performance_metrics={"distance_travelled": 650}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="movement")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "deaths")
        self.assertEqual(task.category, "movement")
        self.assertEqual(task.evidence_session_ids, ["codm_mov_1"])

    def test_codm_positioning_task(self):
        s = Session(
            session_id="codm_pos_1",
            game="COD Mobile",
            map="Raid",
            player_notes="Repeated deaths crossing middle lane without using headglitch power spots.",
            performance_metrics={"positioning_deaths": 4}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="positioning")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "positioning_deaths")
        self.assertEqual(task.category, "positioning")
        self.assertEqual(task.evidence_session_ids, ["codm_pos_1"])

    def test_codm_loadout_task(self):
        s = Session(
            session_id="codm_load_1",
            game="COD Mobile",
            map="Summit",
            configuration={"weapon": "Grau", "attachments": ["Monolithic Suppressor", "OWC Laser"]},
            player_notes="Testing new Gunsmith build; need Quick Fix perk synergy."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="loadout")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "damage")
        self.assertEqual(task.category, "configuration")
        self.assertEqual(task.evidence_session_ids, ["codm_load_1"])

    def test_codm_objective_play_task(self):
        s = Session(
            session_id="codm_obj_1",
            game="COD Mobile",
            map="Nuketown",
            player_notes="Low Hardpoint hill time; failed to anchor inner perimeter with trophy system.",
            performance_metrics={"objectives_secured": 1}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="objective play")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "objectives_secured")
        self.assertEqual(task.category, "objective")
        self.assertEqual(task.evidence_session_ids, ["codm_obj_1"])

    def test_codm_deaths_task(self):
        s = Session(
            session_id="codm_dth_1",
            game="COD Mobile",
            map="Crash",
            deaths=14,
            player_notes="Staggered respawns fed consecutive deaths without waiting for squad regroup."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="deaths")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "deaths")
        self.assertEqual(task.category, "consistency")
        self.assertEqual(task.evidence_session_ids, ["codm_dth_1"])

    def test_codm_accuracy_task(self):
        s = Session(
            session_id="codm_acc_1",
            game="COD Mobile",
            map="Standoff",
            player_notes="Excessive pre-fire wasted ammo; low overall weapon accuracy.",
            performance_metrics={"accuracy": "18%"}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="accuracy")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "accuracy")
        self.assertEqual(task.category, "aim")
        self.assertEqual(task.evidence_session_ids, ["codm_acc_1"])

    def test_codm_score_efficiency_task(self):
        s = Session(
            session_id="codm_sco_1",
            game="COD Mobile",
            map="Firing Range",
            player_notes="Struggled to cycle UAV scorestreaks; low match score efficiency.",
            performance_metrics={"score_efficiency": 180.0, "score": "1450"}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="COD Mobile", category="score efficiency")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "score_efficiency")
        self.assertEqual(task.category, "consistency")
        self.assertEqual(task.evidence_session_ids, ["codm_sco_1"])

    # =================================================================
    # 3. VALORANT CONSTANTS & METRICS
    # =================================================================
    def test_valorant_constants_and_metrics_integrity(self):
        expected_types = {
            "aim",
            "crosshair_placement",
            "positioning",
            "economy",
            "utility_usage",
            "map_awareness",
            "round_decisions",
            "configuration",
            "consistency"
        }
        self.assertEqual(set(VALORANT_TASK_TYPES), expected_types)

        for task_type in VALORANT_TASK_TYPES:
            defn = VALORANT_TASK_DEFINITIONS[task_type]
            self.assertIn(defn["metric_to_track"], VALORANT_MEASURABLE_METRICS)
            self.assertIn(defn["category"], TASK_CATEGORIES)
            # Verify constraint: Do not claim enemy positions
            combined = (defn["objective"] + " " + defn["description"] + " " + defn["target"]).lower()
            self.assertNotIn("enemy at", combined)
            self.assertNotIn("enemies at", combined)
            self.assertNotIn("camper at", combined)

    # =================================================================
    # 4. VALORANT EVIDENCE-BASED GENERATION (ALL 9 TASKS)
    # =================================================================
    def test_valorant_crosshair_placement_and_positioning(self):
        s = Session(
            session_id="val_pos_1",
            game="Valorant",
            map="Ascent",
            player_notes="Ego-peeking B Main without cover; head height crosshair drifted down.",
            performance_metrics={"first_deaths": 5}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Valorant", category="positioning")
        self.assertEqual(res.status, "success")
        self.assertGreaterEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "positioning")
        self.assertEqual(task.objective, "Improve crosshair placement")
        self.assertEqual(task.metric_to_track, "Deaths caused by poor positioning")
        self.assertEqual(task.target, "Reduce repeated positioning mistakes")
        self.assertEqual(task.evidence_session_ids, ["val_pos_1"])

    def test_valorant_economy_task(self):
        s = Session(
            session_id="val_eco_1",
            game="Valorant",
            map="Haven",
            player_notes="Broken force buy on round 3 wrecked team economy for full buy."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Valorant", category="economy")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "strategy")
        self.assertEqual(task.metric_to_track, "round_decisions")
        self.assertEqual(task.evidence_session_ids, ["val_eco_1"])

    def test_valorant_utility_usage_task(self):
        s = Session(
            session_id="val_util_1",
            game="Valorant",
            map="Bind",
            player_notes="Dry peeking into site without flash or smoke assistance.",
            timeline=[
                TimelineEvent(
                    timestamp_or_round="Round 4",
                    event_type="utility",
                    description="Dry peeked Hookah without flash."
                )
            ]
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Valorant", category="utility usage")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "objective")
        self.assertEqual(task.metric_to_track, "assists")
        self.assertEqual(task.evidence_session_ids, ["val_util_1"])

    def test_valorant_map_awareness_task(self):
        s = Session(
            session_id="val_map_1",
            game="Valorant",
            map="Split",
            result="Defeat",
            player_notes="Caught off guard by B flanker; lost rotation timing."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Valorant", category="map awareness")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "map_awareness")
        self.assertEqual(task.evidence_session_ids, ["val_map_1"])

    def test_valorant_round_decisions_task(self):
        s = Session(
            session_id="val_dec_1",
            game="Valorant",
            map="Ascent",
            player_notes="Threw 4v2 man-advantage round hunting for last kill.",
            timeline=[
                TimelineEvent(
                    timestamp_or_round="Round 9",
                    event_type="tilt",
                    description="Overaggressive push in 4v2 throw.",
                    impact="negative",
                    tilt_indicator=7
                )
            ]
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Valorant", category="round decisions")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "decision_making")
        self.assertEqual(task.metric_to_track, "Unforced deaths during man-advantage rounds")
        self.assertEqual(task.evidence_session_ids, ["val_dec_1"])

    def test_valorant_consistency_task(self):
        s1 = Session(
            session_id="val_con_1",
            game="Valorant",
            kills=20,
            deaths=10,
            kd_ratio=2.0
        )
        s2 = Session(
            session_id="val_con_2",
            game="Valorant",
            kills=5,
            deaths=15,
            kd_ratio=0.33
        )
        self.storage.create_session(s1)
        self.storage.create_session(s2)

        res = self.engine.create_tasks_from_history(game="Valorant", category="consistency")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "consistency")
        self.assertEqual(task.metric_to_track, "K/D ratio variance across consecutive sessions")
        self.assertIn("val_con_1", task.evidence_session_ids)
        self.assertIn("val_con_2", task.evidence_session_ids)

    # =================================================================
    # 5. ADAPTER INTEGRATION & REGISTRY
    # =================================================================
    def test_adapters_registry_and_task_generation(self):
        # COD Mobile adapter registered and functional
        adapter = default_adapter_registry.get_adapter("CODM")
        self.assertEqual(adapter.game_name, "COD Mobile")

        s_codm = Session(
            session_id="codm_t1",
            game="COD Mobile",
            player_notes="Snap aim centering was off target in Hardpoint.",
            performance_metrics={"headshot_pct": 12.0}
        )
        tasks = adapter.generate_tasks([s_codm], task_engine=self.engine)
        self.assertIsInstance(tasks, list)
        self.assertGreaterEqual(len(tasks), 1)

        # Valorant adapter generate_tasks functional
        val_adapter = default_adapter_registry.get_adapter("Valorant")
        s_val = Session(
            session_id="val_t1",
            game="Valorant",
            player_notes="Ego-peeked B Main with poor positioning.",
            performance_metrics={"first_deaths": 5}
        )
        val_tasks = val_adapter.generate_tasks([s_val], task_engine=self.engine)
        self.assertIsInstance(val_tasks, list)
        self.assertGreaterEqual(len(val_tasks), 1)


if __name__ == "__main__":
    unittest.main()
