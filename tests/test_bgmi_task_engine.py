"""
Unit and Integration Tests for BGMI Task Definitions in Gaming Task Engine.

Requirements tested:
- 9 BGMI task types:
  1. rotation planning
  2. zone awareness
  3. positioning
  4. survival
  5. combat
  6. loot efficiency
  7. vehicle usage
  8. weapon configuration
  9. final-zone decision making
- 8 Allowed measurable metrics:
  survival duration, final placement, kills, deaths, damage,
  rotation timing, distance travelled, zone transitions
- Only generate a task when required evidence data exists in stored sessions.
- Do not invent enemy locations or zone information.
- Insufficient data handling: 'Not enough data to create a personalized task.'
"""

import os
import tempfile
import unittest

from app.models import Session, TimelineEvent, GamingTask, TASK_CATEGORIES
from app.session_storage import SessionStorage
from app.task_engine import (
    GamingTaskEngine,
    BGMI_TASK_TYPES,
    BGMI_MEASURABLE_METRICS,
    BGMI_TASK_DEFINITIONS,
    INSUFFICIENT_DATA_MSG
)
from app.game_adapter import BGMIAdapter


class TestBGMITaskEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_bgmi_tasks.db")
        self.storage = SessionStorage(db_path=self.db_path)
        self.engine = GamingTaskEngine(storage=self.storage)
        self.adapter = BGMIAdapter()

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------
    # 1. CONSTANTS & METRIC INTEGRITY
    # -----------------------------------------------------------------
    def test_bgmi_constants_and_metrics_integrity(self):
        expected_types = {
            "rotation_planning",
            "zone_awareness",
            "positioning",
            "survival",
            "combat",
            "loot_efficiency",
            "vehicle_usage",
            "weapon_configuration",
            "final_zone_decision_making"
        }
        self.assertEqual(set(BGMI_TASK_TYPES), expected_types)

        expected_metrics = {
            "survival duration",
            "final placement",
            "kills",
            "deaths",
            "damage",
            "rotation timing",
            "distance travelled",
            "zone transitions"
        }
        self.assertEqual(set(BGMI_MEASURABLE_METRICS), expected_metrics)

        for task_type in BGMI_TASK_TYPES:
            defn = BGMI_TASK_DEFINITIONS[task_type]
            self.assertIn(defn["metric_to_track"], expected_metrics)
            for opt in defn.get("metrics_options", []):
                self.assertIn(opt, expected_metrics)
            self.assertIn(defn["category"], TASK_CATEGORIES)

    # -----------------------------------------------------------------
    # 2. EVIDENCE-BASED GENERATION FOR ALL 9 TASK TYPES
    # -----------------------------------------------------------------
    def test_rotation_planning_task_with_evidence(self):
        s = Session(
            session_id="bgmi_rot_1",
            game="BGMI",
            map="Erangel",
            player_notes="Delayed rotation to Georgopol bridge caused blue zone damage.",
            performance_metrics={"rotation_timing": "late", "zone_rotations": 2}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="rotation_planning")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "rotation timing")
        self.assertEqual(task.evidence_session_ids, ["bgmi_rot_1"])
        self.assertIn("rotation", task.objective.lower())

    def test_zone_awareness_task_with_evidence(self):
        s = Session(
            session_id="bgmi_zone_1",
            game="BGMI",
            map="Miramar",
            player_notes="Failed to anticipate phase 4 circle shift up the mountain ridge.",
            performance_metrics={"zone_transitions": 3, "bluezone_damage": 85}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="zone_awareness")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "zone transitions")
        self.assertEqual(task.evidence_session_ids, ["bgmi_zone_1"])

    def test_positioning_task_with_evidence(self):
        s = Session(
            session_id="bgmi_pos_1",
            game="BGMI",
            map="Erangel",
            player_notes="Eliminated running across open field with no hardcover dips.",
            performance_metrics={"deaths_in_open": 2}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="positioning")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "deaths")
        self.assertEqual(task.evidence_session_ids, ["bgmi_pos_1"])

    def test_survival_task_with_evidence(self):
        s = Session(
            session_id="bgmi_surv_1",
            game="BGMI",
            map="Sanhok",
            duration="7 min",
            result="Eliminated early (Top 45)",
            player_notes="Early death in Boot Camp skirmish without armor."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="survival")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "survival duration")
        self.assertEqual(task.evidence_session_ids, ["bgmi_surv_1"])

    def test_combat_task_with_evidence(self):
        s = Session(
            session_id="bgmi_com_1",
            game="BGMI",
            map="Livik",
            kills=1,
            player_notes="Whiffed recoil spray in close-quarters hipfire 1v1 duel.",
            performance_metrics={"damage": 120}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="combat")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "damage")
        self.assertEqual(task.evidence_session_ids, ["bgmi_com_1"])

    def test_loot_efficiency_task_with_evidence(self):
        s = Session(
            session_id="bgmi_loot_1",
            game="BGMI",
            map="Erangel",
            player_notes="Caught looting prolonged in Rozhok, under-geared and ran out of ammo.",
            performance_metrics={"loot_time": "6m", "items_looted": 14}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="loot_efficiency")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "rotation timing")
        self.assertEqual(task.evidence_session_ids, ["bgmi_loot_1"])

    def test_vehicle_usage_task_with_evidence(self):
        s = Session(
            session_id="bgmi_veh_1",
            game="BGMI",
            map="Miramar",
            player_notes="Ran on foot across desert without a vehicle or Dacia; intercepted.",
            performance_metrics={"distance_travelled": 850}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="vehicle_usage")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "distance travelled")
        self.assertEqual(task.evidence_session_ids, ["bgmi_veh_1"])

    def test_weapon_configuration_task_with_evidence(self):
        s = Session(
            session_id="bgmi_weap_1",
            game="BGMI",
            map="Erangel",
            configuration={"primary": "M416", "attachments": ["compensator", "half grip"]},
            player_notes="Need to standardize M416 recoil attachments and gyro sensitivity."
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="weapon_configuration")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "damage")
        self.assertEqual(task.evidence_session_ids, ["bgmi_weap_1"])

    def test_final_zone_decision_making_task_with_evidence(self):
        s = Session(
            session_id="bgmi_fzone_1",
            game="BGMI",
            map="Erangel",
            result="Top 3",
            player_notes="Choked final zone 1v1v1; stood up from prone without smoke screen cover.",
            performance_metrics={"final_placement": 3}
        )
        self.storage.create_session(s)

        res = self.engine.create_tasks_from_history(game="BGMI", category="final_zone_decision_making")
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.tasks), 1)
        task = res.tasks[0]
        self.assertEqual(task.metric_to_track, "final placement")
        self.assertEqual(task.evidence_session_ids, ["bgmi_fzone_1"])

    # -----------------------------------------------------------------
    # 3. NEGATIVE TEST: NO EVIDENCE -> INSUFFICIENT DATA
    # -----------------------------------------------------------------
    def test_no_task_generated_when_evidence_missing(self):
        # Clean session without any relevant error telemetry or notes
        s_clean = Session(
            session_id="bgmi_clean_1",
            game="BGMI",
            map="Erangel",
            duration="30 min",
            result="Win",
            kills=10,
            deaths=0,
            player_notes="Clean match, standard rotation, no issues encountered."
        )
        self.storage.create_session(s_clean)

        # Vehicle usage specifically has no evidence
        res = self.engine.create_tasks_from_history(game="BGMI", category="vehicle_usage")
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.message, INSUFFICIENT_DATA_MSG)
        self.assertEqual(len(res.tasks), 0)

    def test_insufficient_data_when_no_sessions_exist(self):
        res = self.engine.generate_bgmi_tasks()
        self.assertEqual(res.status, "insufficient_data")
        self.assertEqual(res.message, INSUFFICIENT_DATA_MSG)
        self.assertEqual(len(res.tasks), 0)

    # -----------------------------------------------------------------
    # 4. ADAPTER INTEGRATION
    # -----------------------------------------------------------------
    def test_bgmi_adapter_generate_tasks(self):
        s = Session(
            session_id="adapter_s1",
            game="BGMI",
            map="Erangel",
            player_notes="Lost rotation due to bridge block and late vehicle start.",
            performance_metrics={"rotation_timing": "late", "distance_travelled": 1200}
        )
        tasks = self.adapter.generate_tasks([s], task_engine=self.engine)
        self.assertIsInstance(tasks, list)
        self.assertGreaterEqual(len(tasks), 1)
        # Check that generated tasks use allowed metrics
        for t in tasks:
            self.assertIn(t.metric_to_track, BGMI_MEASURABLE_METRICS)


if __name__ == "__main__":
    unittest.main()
