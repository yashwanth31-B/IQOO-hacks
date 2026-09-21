"""
Unit and Integration Tests for Free Fire Task Definitions in Gaming Task Engine.

Requirements tested:
- 7 Free Fire task areas:
  1. movement
  2. positioning
  3. combat
  4. weapon/loadout usage
  5. safe-zone decisions
  6. survival
  7. objective performance
- Use only available stored metrics:
  gloo_wall_speed, distance travelled, deaths, damage, headshot_rate,
  kills, safezone_damage, survival duration, final placement, clash_squad_rounds_won
- Only generate tasks when required evidence data exists in stored sessions.
- Do not invent game events.
- Insufficient data handling: 'Not enough data to create a personalized task.'
"""

import os
import tempfile
import unittest

from app.models import Session, TimelineEvent, GamingTask, TASK_CATEGORIES
from app.session_storage import SessionStorage
from app.task_engine import (
    GamingTaskEngine,
    FREE_FIRE_TASK_TYPES,
    FREE_FIRE_MEASURABLE_METRICS,
    FREE_FIRE_TASK_DEFINITIONS,
    INSUFFICIENT_DATA_MSG
)
from app.game_adapter import FreeFireAdapter


class TestFreeFireTaskEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_ff_tasks.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.engine = GamingTaskEngine(storage=self.storage)
        self.adapter = FreeFireAdapter()

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------
    # 1. CONSTANTS & METRIC INTEGRITY
    # -----------------------------------------------------------------
    def test_free_fire_constants_and_metrics_integrity(self):
        expected_types = {
            "movement",
            "positioning",
            "combat",
            "weapon_loadout_usage",
            "safe_zone_decisions",
            "survival",
            "objective_performance"
        }
        self.assertEqual(set(FREE_FIRE_TASK_TYPES), expected_types)

        expected_metrics = {
            "gloo_wall_speed",
            "distance travelled",
            "deaths",
            "damage",
            "headshot_rate",
            "kills",
            "safezone_damage",
            "survival duration",
            "final placement",
            "clash_squad_rounds_won"
        }
        self.assertEqual(set(FREE_FIRE_MEASURABLE_METRICS), expected_metrics)

        for task_type in FREE_FIRE_TASK_TYPES:
            defn = FREE_FIRE_TASK_DEFINITIONS[task_type]
            self.assertIn(defn["metric_to_track"], expected_metrics)
            for opt in defn.get("metrics_options", []):
                self.assertIn(opt, expected_metrics)
            self.assertIn(defn["category"], TASK_CATEGORIES)

    # -----------------------------------------------------------------
    # 2. EVIDENCE-BASED GENERATION FOR ALL 7 TASK TYPES
    # -----------------------------------------------------------------
    def test_movement_task_with_evidence(self):
        s = Session(
            session_id="ff_mov_1",
            game="Free Fire MAX",
            map="Bermuda",
            player_notes="Slow defensive gloo wall deployment while sprinting open chokepoint.",
            performance_metrics={"gloo_wall_speed": 0.85, "distance_travelled": 940}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="movement")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "movement")
        self.assertEqual(task.metric_to_track, "gloo_wall_speed")
        self.assertEqual(task.evidence_session_ids, ["ff_mov_1"])
        self.assertIn("gloo wall", task.objective.lower())

    def test_positioning_task_with_evidence(self):
        s = Session(
            session_id="ff_pos_1",
            game="Free Fire MAX",
            map="Purgatory",
            player_notes="Caught in open ground crossfire below Central high ground ridge.",
            performance_metrics={"deaths_in_open": 3}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="positioning")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "positioning")
        self.assertEqual(task.metric_to_track, "deaths")
        self.assertEqual(task.evidence_session_ids, ["ff_pos_1"])

    def test_combat_task_with_evidence(self):
        s = Session(
            session_id="ff_com_1",
            game="Free Fire MAX",
            map="Kalahari",
            kills=2,
            player_notes="Missed upward drag headshots in close-range M1887 shotgun duels.",
            performance_metrics={"headshot_rate": "15%", "damage": 420}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="combat")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "combat")
        self.assertEqual(task.metric_to_track, "headshot_rate")
        self.assertEqual(task.evidence_session_ids, ["ff_com_1"])

    def test_weapon_loadout_usage_task_with_evidence(self):
        s = Session(
            session_id="ff_weap_1",
            game="Free Fire MAX",
            map="Bermuda",
            configuration={"character": "Alok", "primary": "MP40", "secondary": "Woodpecker"},
            player_notes="Misaligned active skill cooldown with mid-range burst engagements."
        )
        self.storage.create_session(s)

        # Query using human-readable format 'weapon/loadout usage'
        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="weapon/loadout usage")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "configuration")
        self.assertEqual(task.metric_to_track, "damage")
        self.assertEqual(task.evidence_session_ids, ["ff_weap_1"])

    def test_safe_zone_decisions_task_with_evidence(self):
        s = Session(
            session_id="ff_zone_1",
            game="Free Fire MAX",
            map="Alpine",
            player_notes="Late rotation caused heavy electric safe zone boundary damage.",
            performance_metrics={"safezone_damage": 120, "zone_transitions": 2}
        )
        self.storage.create_session(s)

        # Query using hyphenated 'safe-zone decisions'
        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="safe-zone decisions")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "strategy")
        self.assertEqual(task.metric_to_track, "safezone_damage")
        self.assertEqual(task.evidence_session_ids, ["ff_zone_1"])

    def test_survival_task_with_evidence(self):
        s = Session(
            session_id="ff_surv_1",
            game="Free Fire MAX",
            map="Bermuda",
            duration="5 min",
            result="Eliminated (Top 35)",
            player_notes="Hot drop death at Clock Tower with tier 1 vest."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="survival")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "consistency")
        self.assertEqual(task.metric_to_track, "survival duration")
        self.assertEqual(task.evidence_session_ids, ["ff_surv_1"])

    def test_objective_performance_task_with_evidence(self):
        s = Session(
            session_id="ff_obj_1",
            game="Free Fire MAX",
            map="NeXTerra",
            player_notes="Lost Clash Squad rounds due to delayed Arsenal key securement.",
            performance_metrics={"clash_squad_rounds_won": 1, "objectives_secured": 0}
        )
        self.storage.create_session(s)

        # Query using 'objective performance'
        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="objective performance")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.category, "objective")
        self.assertEqual(task.metric_to_track, "clash_squad_rounds_won")
        self.assertEqual(task.evidence_session_ids, ["ff_obj_1"])

    # -----------------------------------------------------------------
    # 3. NEGATIVE TEST: NO EVIDENCE -> INSUFFICIENT DATA
    # -----------------------------------------------------------------
    def test_no_task_generated_when_evidence_missing(self):
        s_clean = Session(
            session_id="ff_clean_1",
            game="Free Fire MAX",
            map="Bermuda",
            duration="16 min",
            result="Booyah #1",
            kills=8,
            deaths=0,
            player_notes="Flawless victory, perfect rotations and cover."
        )
        self.storage.create_session(s_clean)

        # Specific category with no evidence
        res = self.engine.create_tasks_from_history(game="Free Fire MAX", category="safe-zone decisions")
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.message, INSUFFICIENT_DATA_MSG)
        self.assertEqual(len(res.tasks), 0)

    def test_insufficient_data_when_no_sessions_exist(self):
        res = self.engine.generate_free_fire_tasks()
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.message, INSUFFICIENT_DATA_MSG)
        self.assertEqual(len(res.tasks), 0)

    # -----------------------------------------------------------------
    # 4. ADAPTER INTEGRATION
    # -----------------------------------------------------------------
    def test_free_fire_adapter_generate_tasks(self):
        s = Session(
            session_id="adapter_ff_1",
            game="Free Fire MAX",
            map="Bermuda",
            player_notes="Evasive gloo wall slide was slow; caught by AWM sniper in open.",
            performance_metrics={"gloo_wall_speed": 0.72, "deaths_in_open": 1}
        )
        tasks = self.adapter.generate_tasks([s], task_engine=self.engine)
        self.assertIsInstance(tasks, list)
        self.assertGreaterEqual(len(tasks), 1)
        for t in tasks:
            self.assertIn(t.metric_to_track, FREE_FIRE_MEASURABLE_METRICS)


if __name__ == "__main__":
    unittest.main()
