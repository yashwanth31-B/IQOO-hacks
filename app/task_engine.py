"""
Phase 7: AI Gaming Task Engine.

Converts historical performance information into specific, measurable gaming tasks.
Strict rules:
1. Tasks must be based on stored evidence (evidence_session_ids).
2. Do not invent weaknesses.
3. Do not claim causation.
4. If insufficient data exists, return "Not enough data to create a personalized task."
5. Do not create real-time game control: the player remains responsible for all game actions.
"""

import os
import json
import sqlite3
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from app.models import (
    Session,
    GamingTask,
    TaskEngineResponse,
    TASK_CATEGORIES
)
from app.session_storage import SessionStorage, default_session_storage


INSUFFICIENT_DATA_MSG = "Not enough data to create a personalized task."


# =====================================================================
# BGMI SPECIFIC TASK DEFINITIONS & MEASURABLE METRICS
# =====================================================================

BGMI_TASK_TYPES = [
    "rotation_planning",
    "zone_awareness",
    "positioning",
    "survival",
    "combat",
    "loot_efficiency",
    "vehicle_usage",
    "weapon_configuration",
    "final_zone_decision_making"
]

BGMI_MEASURABLE_METRICS = [
    "survival duration",
    "final placement",
    "kills",
    "deaths",
    "damage",
    "rotation timing",
    "distance travelled",
    "zone transitions"
]

BGMI_TASK_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "rotation_planning": {
        "name": "Rotation Planning",
        "category": "strategy",
        "metric_to_track": "rotation timing",
        "objective": "Execute early compound-to-compound rotation planning before blue zone collapse",
        "description": "Scout and plan vehicle rotation paths to central cover structures ahead of the playzone timer.",
        "target": "Zero casualties sustained during zone transitions",
        "duration": "15 minutes",
        "difficulty": "hard",
        "metrics_options": ["rotation timing", "zone transitions", "survival duration"]
    },
    "zone_awareness": {
        "name": "Zone Awareness",
        "category": "map_awareness",
        "metric_to_track": "zone transitions",
        "objective": "Anticipate next circle shift and secure playzone edge high ground",
        "description": "Track safe zone collapse intervals and avoid edge pinches between the blue wall and gatekeeping squads.",
        "target": "Navigate all zone transitions without sustaining playzone boundary damage",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["zone transitions", "survival duration"]
    },
    "positioning": {
        "name": "Positioning",
        "category": "positioning",
        "metric_to_track": "deaths",
        "objective": "Anchor hardcover dips and compound structures prior to initiating engagements",
        "description": "Eliminate dry field crossings; secure vehicle hull or terrain depressions before returning fire.",
        "target": "Reduce deaths caused by poor terrain positioning",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["deaths", "final placement"]
    },
    "survival": {
        "name": "Survival",
        "category": "consistency",
        "metric_to_track": "survival duration",
        "objective": "Extend survival duration into late-game high-placement circles",
        "description": "Adopt disciplined early-game pacing, avoiding unforced hot-drop skirmishes with incomplete loadouts.",
        "target": "Survive past 20 minutes to reach top 10 placement consistently",
        "duration": "20 minutes",
        "difficulty": "medium",
        "metrics_options": ["survival duration", "final placement"]
    },
    "combat": {
        "name": "Combat",
        "category": "combat",
        "metric_to_track": "damage",
        "objective": "Improve medium-range spray recoil control and close-quarters hipfire tracking",
        "description": "Calibrate gyro spray stability on 3x/4x optics and practice rapid peek-firing from hardcover.",
        "target": "Increase combat damage output and positive 1v1 engagement trades",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["damage", "kills"]
    },
    "loot_efficiency": {
        "name": "Loot Efficiency",
        "category": "objective",
        "metric_to_track": "rotation timing",
        "objective": "Streamline compound looting to establish Level 2 gear and medical supplies within 3 minutes",
        "description": "Limit prolonged looting in non-essential areas; secure core essentials and transition immediately to zone rotation.",
        "target": "Complete essential gear acquisition within initial drop phase",
        "duration": "10 minutes",
        "difficulty": "easy",
        "metrics_options": ["rotation timing", "survival duration"]
    },
    "vehicle_usage": {
        "name": "Vehicle Usage",
        "category": "movement",
        "metric_to_track": "distance travelled",
        "objective": "Prioritize vehicle acquisition on landing and maintain mobile rotation readiness",
        "description": "Use vehicles for rapid cross-map transit, emergency hardcover deployment, and perimeter scouting.",
        "target": "Secure transport vehicle for all mid-to-late zone rotations",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["distance travelled", "rotation timing"]
    },
    "weapon_configuration": {
        "name": "Weapon Configuration",
        "category": "configuration",
        "metric_to_track": "damage",
        "objective": "Optimize primary assault rifle attachment loadout for stabilized recoil dampening",
        "description": "Equip compensator and ergonomic foregrip on primary automatic weapon for predictable recoil resets.",
        "target": "Standardize weapon configuration with calibrated recoil attachments",
        "duration": "10 minutes",
        "difficulty": "easy",
        "metrics_options": ["damage", "kills"]
    },
    "final_zone_decision_making": {
        "name": "Final-Zone Decision Making",
        "category": "decision_making",
        "metric_to_track": "final placement",
        "objective": "Execute coordinated utility deployment and position discipline in final circle phases",
        "description": "Use smoke screens to isolate sightlines, refrain from premature prone crawling, and hold throwables for final confrontation.",
        "target": "Convert top 5 match placements into 1st place chicken dinners",
        "duration": "15 minutes",
        "difficulty": "hard",
        "metrics_options": ["final placement", "kills"]
    }
}


# =====================================================================
# FREE FIRE SPECIFIC TASK DEFINITIONS & MEASURABLE METRICS
# =====================================================================

FREE_FIRE_TASK_TYPES = [
    "movement",
    "positioning",
    "combat",
    "weapon_loadout_usage",
    "safe_zone_decisions",
    "survival",
    "objective_performance"
]

FREE_FIRE_MEASURABLE_METRICS = [
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
]

FREE_FIRE_TASK_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "movement": {
        "name": "Movement & Gloo Wall Evasion",
        "category": "movement",
        "metric_to_track": "gloo_wall_speed",
        "objective": "Master evasive sprint-slides and rapid defensive gloo wall deployment",
        "description": "Drill zig-zag evasive sprint patterns and rapid gloo wall shielding when traversing exposed zones.",
        "target": "Deploy gloo shields within 0.3s of enemy contact while repositioning",
        "duration": "10 minutes",
        "difficulty": "medium",
        "metrics_options": ["gloo_wall_speed", "distance travelled", "deaths"]
    },
    "positioning": {
        "name": "Positioning & High Ground Control",
        "category": "positioning",
        "metric_to_track": "deaths",
        "objective": "Secure elevated ridge lines and hardcover structures prior to engaging enemy squads",
        "description": "Prioritize rooftop and ridge control; avoid flat open-ground skirmishes without immediate hard cover.",
        "target": "Reduce deaths sustained from open-ground crossfires",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["deaths", "final placement"]
    },
    "combat": {
        "name": "Combat & Drag-Headshot Execution",
        "category": "combat",
        "metric_to_track": "headshot_rate",
        "objective": "Improve vertical drag-headshot consistency and close-quarters shotgun duel trades",
        "description": "Calibrate swipe sensitivity for upward drag headshots and rapid weapon switches in close quarters.",
        "target": "Increase headshot conversion rate in 1v1 engagements",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["headshot_rate", "damage", "kills"]
    },
    "weapon_loadout_usage": {
        "name": "Weapon & Loadout Synergy",
        "category": "configuration",
        "metric_to_track": "damage",
        "objective": "Align character active ability cooldowns with primary weapon burst range",
        "description": "Synchronize character skill activations (e.g. Alok, Chrono, Tatsuya) with weapon effective ranges.",
        "target": "Maximize damage output utilizing character and weapon loadout synergy",
        "duration": "10 minutes",
        "difficulty": "easy",
        "metrics_options": ["damage", "kills"]
    },
    "safe_zone_decisions": {
        "name": "Safe-Zone Decisions",
        "category": "strategy",
        "metric_to_track": "safezone_damage",
        "objective": "Execute early perimeter rotations ahead of electric safe-zone collapse",
        "description": "Track safe zone collapse intervals and avoid electric border damage while gatekeeping rotating opponents.",
        "target": "Zero safe-zone electric boundary casualties and clean perimeter rotations",
        "duration": "15 minutes",
        "difficulty": "hard",
        "metrics_options": ["safezone_damage", "survival duration", "final placement"]
    },
    "survival": {
        "name": "Survival & Match Pacing",
        "category": "consistency",
        "metric_to_track": "survival duration",
        "objective": "Pace early-game engagements to preserve vest durability into final circle Booyah contests",
        "description": "Adopt disciplined early pacing, avoiding unforced hot-drop skirmishes with tier 1 gear.",
        "target": "Maintain survival duration above 12 minutes to secure top 5 finishes",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["survival duration", "final placement"]
    },
    "objective_performance": {
        "name": "Objective Performance",
        "category": "objective",
        "metric_to_track": "clash_squad_rounds_won",
        "objective": "Prioritize Clash Squad round objectives, Arsenal keys, and squad revival stations",
        "description": "Focus squad coordination on securing Arsenal supply caches, airdrop crates, and revivals under gloo cover.",
        "target": "Achieve high round win conversion in Clash Squad and secure key map objectives",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["clash_squad_rounds_won", "final placement"]
    }
}


# =====================================================================
# COD MOBILE SPECIFIC TASK DEFINITIONS & MEASURABLE METRICS
# =====================================================================

CODM_TASK_TYPES = [
    "aim",
    "recoil",
    "movement",
    "positioning",
    "loadout",
    "objective_play",
    "deaths",
    "accuracy",
    "score_efficiency"
]

CODM_MEASURABLE_METRICS = [
    "headshot_pct",
    "damage",
    "deaths",
    "positioning_deaths",
    "accuracy",
    "objectives_secured",
    "score_efficiency",
    "kills",
    "score",
    "distance travelled"
]

CODM_TASK_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "aim": {
        "name": "Snap-Aim & Upper-Torso Centering",
        "category": "aim",
        "metric_to_track": "headshot_pct",
        "objective": "Calibrate snap-aim centering and upper-torso target acquisition",
        "description": "Focus crosshair centering on chest and upper-torso before aiming down sights (ADS).",
        "target": "Increase first-bullet hit conversion and headshot percentage",
        "duration": "10 minutes",
        "difficulty": "medium",
        "metrics_options": ["headshot_pct", "accuracy", "kills"]
    },
    "recoil": {
        "name": "Recoil Compensation & Spray Control",
        "category": "combat",
        "metric_to_track": "damage",
        "objective": "Master vertical recoil control on high fire-rate automatic weapons",
        "description": "Counter-pull swipe gestures to compensate for vertical muzzle climb during sustained full-auto sprays.",
        "target": "Tighten spray groupings and increase damage output in mid-range duels",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["damage", "accuracy", "kills"]
    },
    "movement": {
        "name": "Movement & Slide-Cancel Mechanics",
        "category": "movement",
        "metric_to_track": "deaths",
        "objective": "Execute slide-cancel transitions and jump-peeking around tight corners",
        "description": "Use slide-cancels to break opponent tracking angles without losing sprint momentum into gunfights.",
        "target": "Reduce deaths sustained while transitioning between cover points",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["deaths", "distance travelled"]
    },
    "positioning": {
        "name": "Headglitch Positioning & Choke Control",
        "category": "positioning",
        "metric_to_track": "positioning_deaths",
        "objective": "Anchor headglitch power positions and eliminate open-lane crossings",
        "description": "Hold fortified hardcover sightlines and avoid traversing contested middle lanes without utility.",
        "target": "Eliminate deaths caused by open exposure and bad sightline angles",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["positioning_deaths", "deaths"]
    },
    "loadout": {
        "name": "Gunsmith Loadout & Perk Synergy",
        "category": "configuration",
        "metric_to_track": "damage",
        "objective": "Optimize Gunsmith attachment builds and perk synergy for primary role",
        "description": "Balance ADS speed attachments with recoil stabilization and equip Quick Fix for fast recovery.",
        "target": "Achieve standardized weapon loadout parity across competitive loadout slots",
        "duration": "10 minutes",
        "difficulty": "easy",
        "metrics_options": ["damage", "kills"]
    },
    "objective_play": {
        "name": "Objective Play & Zone Anchoring",
        "category": "objective",
        "metric_to_track": "objectives_secured",
        "objective": "Prioritize Hardpoint hill control, Domination flag captures, and Search & Destroy plants",
        "description": "Hold inner objective perimeters with trophy system utility and defend entry funnels against contesting squads.",
        "target": "Increase direct objective captures and defensive hill hold duration",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["objectives_secured", "score"]
    },
    "deaths": {
        "name": "Death Discipline & Respawn Pacing",
        "category": "consistency",
        "metric_to_track": "deaths",
        "objective": "Eliminate staggered single-man respawns and regroup before re-contesting",
        "description": "Wait for teammate respawn intervals rather than feeding consecutive 1v2+ deaths into held enemy setups.",
        "target": "Reduce death streaks and unforced first-death occurrences",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["deaths"]
    },
    "accuracy": {
        "name": "Weapon Shot Accuracy & Trigger Discipline",
        "category": "aim",
        "metric_to_track": "accuracy",
        "objective": "Improve weapon shot accuracy percentage and minimize wasted pre-fire ammunition",
        "description": "Refine trigger discipline; confirm crosshair alignment before committing to full-auto sprays.",
        "target": "Maintain overall weapon accuracy above 25% across ranked engagements",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["accuracy", "headshot_pct"]
    },
    "score_efficiency": {
        "name": "Score Efficiency & Streak Cycling",
        "category": "consistency",
        "metric_to_track": "score_efficiency",
        "objective": "Maximize match score efficiency through killstreak cycling and objective bonuses",
        "description": "Deploy UAV and utility scorestreaks to accelerate score multiplier and support squad pacing.",
        "target": "Increase match score efficiency and team contribution",
        "duration": "10 minutes",
        "difficulty": "medium",
        "metrics_options": ["score_efficiency", "score"]
    }
}


# =====================================================================
# VALORANT SPECIFIC TASK DEFINITIONS & MEASURABLE METRICS
# =====================================================================

VALORANT_TASK_TYPES = [
    "aim",
    "crosshair_placement",
    "positioning",
    "economy",
    "utility_usage",
    "map_awareness",
    "round_decisions",
    "configuration",
    "consistency"
]

VALORANT_MEASURABLE_METRICS = [
    "Headshot accuracy percentage",
    "headshot_percentage",
    "Deaths caused by poor positioning",
    "deaths",
    "first_deaths",
    "round_decisions",
    "Unforced deaths during man-advantage rounds",
    "damage",
    "assists",
    "average_combat_score",
    "K/D ratio variance across consecutive sessions"
]

VALORANT_TASK_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "aim": {
        "name": "Micro-Flick & First-Bullet Tap Accuracy",
        "category": "aim",
        "metric_to_track": "Headshot accuracy percentage",
        "objective": "Calibrate crosshair tracking and first-bullet accuracy",
        "description": "Perform recoil reset and micro-adjustment drills in shooting range before entering match queues.",
        "target": "Increase headshot accuracy above baseline",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["Headshot accuracy percentage", "headshot_percentage"]
    },
    "crosshair_placement": {
        "name": "Head-Level Crosshair Placement",
        "category": "positioning",
        "metric_to_track": "Deaths caused by poor positioning",
        "objective": "Improve crosshair placement",
        "description": "Focus on keeping crosshair at head height while navigating corners and holding angles.",
        "target": "Reduce repeated positioning mistakes",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["Deaths caused by poor positioning", "first_deaths"]
    },
    "positioning": {
        "name": "Hardcover Anchoring & Angle Isolation",
        "category": "positioning",
        "metric_to_track": "Deaths caused by poor positioning",
        "objective": "Improve crosshair placement",
        "description": "Focus on head-level crosshair placement and clearing angles deliberately before committing to peeks.",
        "target": "Reduce repeated positioning mistakes",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["Deaths caused by poor positioning", "first_deaths"]
    },
    "economy": {
        "name": "Team Economy & Buy-Round Synchronization",
        "category": "strategy",
        "metric_to_track": "round_decisions",
        "objective": "Coordinate team buy thresholds and save round discipline",
        "description": "Adhere strictly to save thresholds ($3900 next round minimum) and avoid broken force buys without team bank parity.",
        "target": "Zero unsynchronized broken buy rounds",
        "duration": "10 minutes",
        "difficulty": "medium",
        "metrics_options": ["round_decisions"]
    },
    "utility_usage": {
        "name": "Coordinated Utility Deployment",
        "category": "objective",
        "metric_to_track": "assists",
        "objective": "Coordinate utility deployment prior to site entry and retakes",
        "description": "Deploy smokes and flashes before executing chokepoint pushes to eliminate unassisted dry peeks.",
        "target": "Increase utility assists and eliminate dry peeks into guarded sites",
        "duration": "15 minutes",
        "difficulty": "medium",
        "metrics_options": ["assists", "damage"]
    },
    "map_awareness": {
        "name": "Minimap Awareness & Rotation Timing",
        "category": "map_awareness",
        "metric_to_track": "first_deaths",
        "objective": "Master rotation timing and choke-point control",
        "description": "Track minimap info, teammate death locations, and rotation timing without giving up defensive flank control.",
        "target": "Eliminate first-death occurrences from unmonitored flanks",
        "duration": "20 minutes",
        "difficulty": "hard",
        "metrics_options": ["first_deaths", "deaths"]
    },
    "round_decisions": {
        "name": "Advantage Discipline & Clutch Decisions",
        "category": "decision_making",
        "metric_to_track": "Unforced deaths during man-advantage rounds",
        "objective": "Maintain disciplined decision making in advantage situations",
        "description": "Refrain from solo aggression when your squad holds numerical or positional advantage; do not dry-peek alone.",
        "target": "Zero unforced deaths when holding advantage",
        "duration": "10 minutes",
        "difficulty": "medium",
        "metrics_options": ["Unforced deaths during man-advantage rounds"]
    },
    "configuration": {
        "name": "Input Sensitivity & Keybind Standardization",
        "category": "configuration",
        "metric_to_track": "damage",
        "objective": "Refine mastery with secondary weapon loadouts",
        "description": "Standardize mouse eDPI and ability keybinds for muscle memory consistency across agents.",
        "target": "Achieve parity with primary weapon configuration",
        "duration": "15 minutes",
        "difficulty": "easy",
        "metrics_options": ["damage"]
    },
    "consistency": {
        "name": "Pre-Match Warmup & Performance Stabilization",
        "category": "consistency",
        "metric_to_track": "K/D ratio variance across consecutive sessions",
        "objective": "Establish consistent pre-match routine and warmup discipline",
        "description": "Run standardized warmup routine in Range and Deathmatch before ranked matches to stabilize opening performance.",
        "target": "Reduce performance variance across consecutive matches",
        "duration": "10 minutes",
        "difficulty": "medium",
        "metrics_options": ["K/D ratio variance across consecutive sessions", "average_combat_score"]
    }
}


class GamingTaskEngine:
    """
    Phase 7: AI Gaming Task Engine.
    Synthesizes actionable, measurable practice and gameplay focus tasks
    grounded strictly in concrete historical session evidence.
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        self.storage = storage or default_session_storage
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensures the gaming_tasks table exists in SQLite database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS gaming_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            game TEXT NOT NULL,
            category TEXT NOT NULL,
            objective TEXT NOT NULL,
            description TEXT NOT NULL,
            duration TEXT NOT NULL,
            metric_to_track TEXT NOT NULL,
            target TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            evidence_session_ids_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT
        )
        """)
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.storage.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def save_task(self, task: GamingTask) -> GamingTask:
        """Persists a GamingTask into SQLite storage."""
        conn = self._get_connection()
        cursor = conn.cursor()
        created_at = task.created_at or datetime.now().isoformat()
        evidence_json = json.dumps([str(s) for s in task.evidence_session_ids])

        cursor.execute("""
        INSERT OR REPLACE INTO gaming_tasks (
            task_id, game, category, objective, description, duration,
            metric_to_track, target, difficulty, evidence_session_ids_json, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id,
            task.game,
            task.category,
            task.objective,
            task.description,
            task.duration,
            task.metric_to_track,
            task.target,
            task.difficulty,
            evidence_json,
            task.status,
            created_at
        ))
        conn.commit()
        conn.close()
        task.created_at = created_at
        return task

    def get_task_by_id(self, task_id: str) -> Optional[GamingTask]:
        """Retrieves a single task by its task_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gaming_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_task(row)

    def list_tasks(
        self,
        game: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[GamingTask]:
        """Lists persisted gaming tasks with optional filters."""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM gaming_tasks WHERE 1=1"
        params = []
        if game:
            query += " AND LOWER(game) = LOWER(?)"
            params.append(game)
        if category:
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category)
        if status:
            query += " AND LOWER(status) = LOWER(?)"
            params.append(status)
        query += " ORDER BY id DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def update_task_status(self, task_id: str, new_status: str) -> Optional[GamingTask]:
        """Updates the status of a gaming task (e.g. pending -> in_progress -> completed)."""
        valid_statuses = ["pending", "in_progress", "completed", "skipped"]
        status_clean = new_status.strip().lower()
        if status_clean not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of: {valid_statuses}")

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE gaming_tasks SET status = ? WHERE task_id = ?", (status_clean, task_id))
        conn.commit()
        conn.close()
        return self.get_task_by_id(task_id)

    def _row_to_task(self, row: sqlite3.Row) -> GamingTask:
        try:
            evidence = json.loads(row["evidence_session_ids_json"])
        except Exception:
            evidence = []
        return GamingTask(
            task_id=row["task_id"],
            game=row["game"],
            category=row["category"],
            objective=row["objective"],
            description=row["description"],
            duration=row["duration"],
            metric_to_track=row["metric_to_track"],
            target=row["target"],
            difficulty=row["difficulty"],
            evidence_session_ids=evidence,
            status=row["status"],
            created_at=row["created_at"]
        )

    def create_tasks_from_history(
        self,
        game: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
        sessions: Optional[List[Session]] = None
    ) -> TaskEngineResponse:
        """
        Converts stored historical performance information into specific, measurable gaming tasks.
        Enforces strict rules:
        - Must be grounded in factual evidence.
        - Never invent weaknesses.
        - Never claim causation.
        - Returns INSUFFICIENT_DATA_MSG when insufficient data exists.
        """
        # 1. Retrieve sessions
        if sessions is None:
            sessions = self.storage.get_recent_sessions(limit=100)

        # 2. Filter by game if specified
        if game:
            filtered_sessions = [s for s in sessions if s.game and s.game.lower() == game.lower()]
        else:
            filtered_sessions = sessions

        # Insufficient data check: need at least 1 session with factual telemetry to identify any evidence
        if not filtered_sessions:
            return TaskEngineResponse(
                tasks=[],
                total_tasks=0,
                status="insufficient_data",
                message=INSUFFICIENT_DATA_MSG,
                evidence_session_ids=[]
            )

        detected_tasks: List[GamingTask] = []
        target_game = filtered_sessions[0].game or game or "General"

        # Check if BGMI-specific tasks should be prioritized
        if self._is_bgmi_game(target_game):
            bgmi_tasks = self._detect_bgmi_tasks(filtered_sessions, category=category, limit=limit)
            if bgmi_tasks:
                final_tasks = bgmi_tasks[:limit]
                for t in final_tasks:
                    self.save_task(t)
                all_evidence = sorted(list({str(sid) for t in final_tasks for sid in t.evidence_session_ids}))
                return TaskEngineResponse(
                    tasks=final_tasks,
                    total_tasks=len(final_tasks),
                    status="success",
                    message="BGMI tasks created from stored evidence.",
                    evidence_session_ids=all_evidence
                )
            return TaskEngineResponse(
                tasks=[],
                total_tasks=0,
                status="insufficient_data",
                message=INSUFFICIENT_DATA_MSG,
                evidence_session_ids=[]
            )

        # Check if Free Fire-specific tasks should be prioritized
        if self._is_free_fire_game(target_game):
            ff_tasks = self._detect_free_fire_tasks(filtered_sessions, category=category, limit=limit)
            if ff_tasks:
                final_tasks = ff_tasks[:limit]
                for t in final_tasks:
                    self.save_task(t)
                all_evidence = sorted(list({str(sid) for t in final_tasks for sid in t.evidence_session_ids}))
                return TaskEngineResponse(
                    tasks=final_tasks,
                    total_tasks=len(final_tasks),
                    status="success",
                    message="Free Fire tasks created from stored evidence.",
                    evidence_session_ids=all_evidence
                )
            return TaskEngineResponse(
                tasks=[],
                total_tasks=0,
                status="insufficient_data",
                message=INSUFFICIENT_DATA_MSG,
                evidence_session_ids=[]
            )

        # Check if COD Mobile-specific tasks should be prioritized
        if self._is_codm_game(target_game):
            codm_tasks = self._detect_codm_tasks(filtered_sessions, category=category, limit=limit)
            if codm_tasks:
                final_tasks = codm_tasks[:limit]
                for t in final_tasks:
                    self.save_task(t)
                all_evidence = sorted(list({str(sid) for t in final_tasks for sid in t.evidence_session_ids}))
                return TaskEngineResponse(
                    tasks=final_tasks,
                    total_tasks=len(final_tasks),
                    status="success",
                    message="COD Mobile tasks created from stored evidence.",
                    evidence_session_ids=all_evidence
                )
            return TaskEngineResponse(
                tasks=[],
                total_tasks=0,
                status="insufficient_data",
                message=INSUFFICIENT_DATA_MSG,
                evidence_session_ids=[]
            )

        # Check if Valorant-specific tasks should be prioritized
        if self._is_valorant_game(target_game):
            val_tasks = self._detect_valorant_tasks(filtered_sessions, category=category, limit=limit)
            if val_tasks:
                final_tasks = val_tasks[:limit]
                for t in final_tasks:
                    self.save_task(t)
                all_evidence = sorted(list({str(sid) for t in final_tasks for sid in t.evidence_session_ids}))
                return TaskEngineResponse(
                    tasks=final_tasks,
                    total_tasks=len(final_tasks),
                    status="success",
                    message="Valorant tasks created from stored evidence.",
                    evidence_session_ids=all_evidence
                )
            return TaskEngineResponse(
                tasks=[],
                total_tasks=0,
                status="insufficient_data",
                message=INSUFFICIENT_DATA_MSG,
                evidence_session_ids=[]
            )

        # -------------------------------------------------------------
        # 1. POSITIONING EVIDENCE
        # -------------------------------------------------------------
        # Evidence: mentions of positioning/ego-peeking/exposed in notes or timeline, or first_deaths >= 4
        pos_evidence: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            # Check notes
            notes = (s.player_notes or "").lower()
            if any(term in notes for term in ["positioning", "ego-peek", "ego peek", "exposed", "bad angle", "overextended"]):
                pos_evidence.append(sid)
                continue
            # Check timeline events
            if s.timeline:
                for ev in s.timeline:
                    desc = (ev.description or "").lower()
                    if any(term in desc for term in ["ego-peek", "ego peek", "positioning", "exposed", "bad angle"]):
                        pos_evidence.append(sid)
                        break
            # Check stats first_deaths
            perf = s.performance_metrics or s.stats or {}
            fd = perf.get("first_deaths")
            if fd is not None and isinstance(fd, (int, float)) and fd >= 4:
                if sid not in pos_evidence:
                    pos_evidence.append(sid)

        if pos_evidence and (category is None or category.lower() == "positioning"):
            task_pos = GamingTask(
                task_id=f"task-pos-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="positioning",
                objective="Improve crosshair placement",
                description="Focus on head-level crosshair placement and clearing angles deliberately before committing to peeks.",
                duration="15 minutes",
                metric_to_track="Deaths caused by poor positioning",
                target="Reduce repeated positioning mistakes",
                difficulty="medium",
                evidence_session_ids=pos_evidence,
                status="pending"
            )
            detected_tasks.append(task_pos)

        # -------------------------------------------------------------
        # 2. DECISION MAKING EVIDENCE
        # -------------------------------------------------------------
        # Evidence: tilt_indicator >= 5, notes mentioning threw/panic/mistake, or high negative impact decisions
        dec_evidence: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            notes = (s.player_notes or "").lower()
            if any(term in notes for term in ["threw", "panic", "overtime mistake", "tilt", "tempted"]):
                dec_evidence.append(sid)
                continue
            if s.timeline:
                for ev in s.timeline:
                    if ev.tilt_indicator and ev.tilt_indicator >= 5:
                        dec_evidence.append(sid)
                        break
                    if ev.impact == "negative" and ev.event_type in ("decision", "tilt"):
                        dec_evidence.append(sid)
                        break

        if dec_evidence and (category is None or category.lower() == "decision_making"):
            task_dec = GamingTask(
                task_id=f"task-dec-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="decision_making",
                objective="Maintain disciplined decision making in advantage situations",
                description="Refrain from solo aggression when your squad holds numerical or positional advantage.",
                duration="10 minutes",
                metric_to_track="Unforced deaths during man-advantage rounds",
                target="Zero unforced deaths when holding advantage",
                difficulty="medium",
                evidence_session_ids=dec_evidence,
                status="pending"
            )
            detected_tasks.append(task_dec)

        # -------------------------------------------------------------
        # 3. AIM EVIDENCE
        # -------------------------------------------------------------
        # Evidence: low headshot_pct (< 25%) or accuracy (< 30%) recorded in performance_metrics
        aim_evidence: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            perf = s.performance_metrics or s.stats or {}
            hs = perf.get("headshot_pct") or perf.get("headshot_percentage")
            acc = perf.get("accuracy") or perf.get("shot_accuracy")
            if hs is not None:
                try:
                    hs_num = float(str(hs).replace("%", "").strip())
                    if hs_num < 25.0:
                        aim_evidence.append(sid)
                        continue
                except ValueError:
                    pass
            if acc is not None:
                try:
                    acc_num = float(str(acc).replace("%", "").strip())
                    if acc_num < 30.0:
                        aim_evidence.append(sid)
                        continue
                except ValueError:
                    pass

        if aim_evidence and (category is None or category.lower() == "aim"):
            task_aim = GamingTask(
                task_id=f"task-aim-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="aim",
                objective="Calibrate crosshair tracking and first-bullet accuracy",
                description="Perform recoil reset and micro-adjustment drills in shooting range before entering match queues.",
                duration="15 minutes",
                metric_to_track="Headshot accuracy percentage",
                target="Increase headshot accuracy above baseline",
                difficulty="medium",
                evidence_session_ids=aim_evidence,
                status="pending"
            )
            detected_tasks.append(task_aim)

        # -------------------------------------------------------------
        # 4. MOVEMENT EVIDENCE
        # -------------------------------------------------------------
        # Evidence: panic_roll_count in stats or timeline movement errors
        mov_evidence: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            perf = s.performance_metrics or s.stats or {}
            panic = perf.get("panic_roll_count")
            if panic is not None and isinstance(panic, (int, float)) and panic >= 3:
                mov_evidence.append(sid)
                continue
            notes = (s.player_notes or "").lower()
            if any(term in notes for term in ["panic roll", "stamina", "bad dodge", "movement lock"]):
                mov_evidence.append(sid)

        if mov_evidence and (category is None or category.lower() == "movement"):
            task_mov = GamingTask(
                task_id=f"task-mov-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="movement",
                objective="Practice roll discipline and stamina pacing",
                description="Avoid reactive panic rolling; wait for visual attack cue before initiating dodge frames.",
                duration="15 minutes",
                metric_to_track="Panic roll count per engagement",
                target="Reduce panic roll occurrences under 3 per engagement",
                difficulty="medium",
                evidence_session_ids=mov_evidence,
                status="pending"
            )
            detected_tasks.append(task_mov)

        # -------------------------------------------------------------
        # 5. MAP AWARENESS EVIDENCE
        # -------------------------------------------------------------
        # Evidence: specific map with multiple losses or low win rate
        map_losses: Dict[str, List[Union[str, int]]] = {}
        for s in filtered_sessions:
            sid = s.session_id or s.id
            m = s.map or s.map_or_level
            res = (s.result or s.outcome or "").lower()
            if m and sid and any(l in res for l in ["defeat", "loss", "lost"]):
                map_losses.setdefault(m, []).append(sid)

        for map_name, sids in map_losses.items():
            if len(sids) >= 1 and (category is None or category.lower() == "map_awareness"):
                task_map = GamingTask(
                    task_id=f"task-map-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category="map_awareness",
                    objective=f"Master rotation timing and choke-point control on {map_name}",
                    description=f"Study push timings and defensive fallback lines specific to {map_name}.",
                    duration="20 minutes",
                    metric_to_track=f"Early-round survival rate on {map_name}",
                    target=f"Eliminate first-death occurrences on {map_name}",
                    difficulty="hard",
                    evidence_session_ids=sids,
                    status="pending"
                )
                detected_tasks.append(task_map)
                break

        # -------------------------------------------------------------
        # 6. CONSISTENCY EVIDENCE
        # -------------------------------------------------------------
        # Evidence: high K/D variance across >= 2 sessions with kills and deaths
        kd_sessions: List[Session] = [
            s for s in filtered_sessions if s.kd_ratio is not None and (s.session_id or s.id)
        ]
        if len(kd_sessions) >= 2 and (category is None or category.lower() == "consistency"):
            kds = [s.kd_ratio for s in kd_sessions]
            kd_range = max(kds) - min(kds)
            if kd_range >= 0.8:
                con_sids = [s.session_id or s.id for s in kd_sessions]
                task_con = GamingTask(
                    task_id=f"task-con-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category="consistency",
                    objective="Establish consistent pre-match routine and warmup discipline",
                    description="Run standardized warmup routine before ranked matches to stabilize opening performance.",
                    duration="10 minutes",
                    metric_to_track="K/D ratio variance across consecutive sessions",
                    target="Reduce performance variance across consecutive matches",
                    difficulty="medium",
                    evidence_session_ids=con_sids,
                    status="pending"
                )
                detected_tasks.append(task_con)

        # -------------------------------------------------------------
        # 7. COMBAT EVIDENCE
        # -------------------------------------------------------------
        # Evidence: clutch rate 0 or low ACS/damage in losses
        combat_sids: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            perf = s.performance_metrics or s.stats or {}
            cr = perf.get("clutch_rate")
            if cr is not None and isinstance(cr, str) and cr.startswith("0/"):
                combat_sids.append(sid)
                continue
            acs = perf.get("acs")
            if acs is not None and isinstance(acs, (int, float)) and acs < 180:
                combat_sids.append(sid)

        if combat_sids and (category is None or category.lower() == "combat"):
            task_com = GamingTask(
                task_id=f"task-com-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="combat",
                objective="Improve isolated 1v1 duel trade conversion",
                description="Focus on taking engagements with utility support or crossfire coverage rather than dry peeking.",
                duration="15 minutes",
                metric_to_track="Isolated duel win rate",
                target="Achieve positive duel trade conversion",
                difficulty="medium",
                evidence_session_ids=combat_sids,
                status="pending"
            )
            detected_tasks.append(task_com)

        # -------------------------------------------------------------
        # 8. STRATEGY / OBJECTIVE / CONFIGURATION EVIDENCE
        # -------------------------------------------------------------
        # Strategy evidence: sessions with round loss streaks
        strat_sids: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            notes = (s.player_notes or "").lower()
            if any(term in notes for term in ["strategy", "retake", "setup", "rotation failed", "default"]):
                strat_sids.append(sid)

        if strat_sids and (category is None or category.lower() == "strategy"):
            task_strat = GamingTask(
                task_id=f"task-strat-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="strategy",
                objective="Develop synchronized post-plant retake protocols",
                description="Coordinate utility deployment before executing site retakes to maximize trade potential.",
                duration="20 minutes",
                metric_to_track="Retake round success percentage",
                target="Improve post-plant retake coordination",
                difficulty="hard",
                evidence_session_ids=strat_sids,
                status="pending"
            )
            detected_tasks.append(task_strat)

        # Objective evidence: low plants/defuses or captures
        obj_sids: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            if not sid:
                continue
            perf = s.performance_metrics or s.stats or {}
            plants = perf.get("bomb_plants")
            defuses = perf.get("defuses")
            caps = perf.get("objectives_captured")
            if (plants == 0 or defuses == 0 or caps == 0):
                obj_sids.append(sid)

        if obj_sids and (category is None or category.lower() == "objective"):
            task_obj = GamingTask(
                task_id=f"task-obj-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="objective",
                objective="Prioritize active site control and objective securement",
                description="Anchor active objective zones and coordinate objective securement utility.",
                duration="15 minutes",
                metric_to_track="Direct objective interactions per match",
                target="Achieve consistent participation in objective securement",
                difficulty="medium",
                evidence_session_ids=obj_sids,
                status="pending"
            )
            detected_tasks.append(task_obj)

        # Configuration evidence: secondary loadout with poor outcome
        config_sids: List[Union[str, int]] = []
        for s in filtered_sessions:
            sid = s.session_id or s.id
            cfg = s.configuration or s.character_or_loadout
            res = (s.result or s.outcome or "").lower()
            if cfg and sid and any(l in res for l in ["defeat", "loss", "lost"]):
                config_sids.append(sid)

        if config_sids and (category is None or category.lower() == "configuration"):
            task_cfg = GamingTask(
                task_id=f"task-cfg-{uuid.uuid4().hex[:6]}",
                game=target_game,
                category="configuration",
                objective="Refine mastery with secondary weapon loadouts",
                description="Drill spray transfer and weapon range thresholds with secondary configurations.",
                duration="15 minutes",
                metric_to_track="Elimination conversion on tested loadout",
                target="Achieve parity with primary weapon configuration",
                difficulty="easy",
                evidence_session_ids=config_sids,
                status="pending"
            )
            detected_tasks.append(task_cfg)

        # If no tasks could be grounded in evidence, adhere to strict insufficient data rule
        if not detected_tasks:
            return TaskEngineResponse(
                tasks=[],
                total_tasks=0,
                status="insufficient_data",
                message=INSUFFICIENT_DATA_MSG,
                evidence_session_ids=[]
            )

        # Filter by category if requested
        if category:
            cat_clean = category.strip().lower()
            detected_tasks = [t for t in detected_tasks if t.category.lower() == cat_clean]
            if not detected_tasks:
                return TaskEngineResponse(
                    tasks=[],
                    total_tasks=0,
                    status="insufficient_data",
                    message=INSUFFICIENT_DATA_MSG,
                    evidence_session_ids=[]
                )

        # Limit tasks
        final_tasks = detected_tasks[:limit]

        # Persist generated tasks
        for t in final_tasks:
            self.save_task(t)

        all_evidence = sorted(list({str(sid) for t in final_tasks for sid in t.evidence_session_ids}))

        return TaskEngineResponse(
            tasks=final_tasks,
            total_tasks=len(final_tasks),
            status="success",
            message="Tasks created from stored evidence.",
            evidence_session_ids=all_evidence
        )

    def _is_bgmi_game(self, game_name: Optional[str]) -> bool:
        """Determines if the game matches BGMI / PUBG Mobile titles."""
        if not game_name:
            return False
        clean = game_name.strip().lower()
        return (
            clean in ("bgmi", "pubg mobile", "battlegrounds mobile india", "bgmi / pubg mobile", "pubg")
            or "bgmi" in clean
            or "pubg" in clean
            or "battlegrounds" in clean
        )

    def _detect_bgmi_tasks(
        self,
        filtered_sessions: List[Session],
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[GamingTask]:
        """
        Synthesizes BGMI-specific tasks strictly from stored session evidence:
        1. rotation planning
        2. zone awareness
        3. positioning
        4. survival
        5. combat
        6. loot efficiency
        7. vehicle usage
        8. weapon configuration
        9. final-zone decision making

        Strict rules:
        - Only generate a task when the required evidence data exists.
        - Do not invent enemy locations or zone information.
        - Strictly use measurable metrics: survival duration, final placement, kills, deaths,
          damage, rotation timing, distance travelled, zone transitions.
        """
        tasks: List[GamingTask] = []
        target_game = "BGMI"

        cat_clean = category.strip().lower().replace("-", "_").replace(" ", "_") if category else None

        # 1. ROTATION PLANNING (metric: rotation timing)
        if cat_clean is None or cat_clean in ("rotation_planning", "rotation", "strategy"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "rotation_timing" in perf or "zone_rotations" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["rotation", "rotate", "caught in blue", "late rotate", "edge rotate", "circle shift", "bridge block", "blue zone"]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["rotation", "rotate", "blue zone", "safe zone"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["rotation_planning"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-rot-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="rotation_planning"
                ))

        # 2. ZONE AWARENESS (metric: zone transitions)
        if cat_clean is None or cat_clean in ("zone_awareness", "zone", "map_awareness"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "zone_transitions" in perf or "bluezone_damage" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["zone", "safe zone", "circle shift", "phase 4", "phase 5", "playzone", "zone shrink"]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["zone", "circle", "playzone"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["zone_awareness"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-zone-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="zone_awareness"
                ))

        # 3. POSITIONING (metric: deaths)
        if cat_clean is None or cat_clean in ("positioning", "cover"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "deaths_in_open" in perf or "positioning_deaths" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["open field", "caught in open", "ridge", "dip", "tree cover", "compound defense", "third-partied", "no cover", "exposed"]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["open field", "caught in open", "exposed", "bad angle", "positioning"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["positioning"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-pos-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="positioning"
                ))

        # 4. SURVIVAL (metric: survival duration)
        if cat_clean is None or cat_clean in ("survival", "consistency", "survival_duration"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                surv = perf.get("survival_duration") or perf.get("survival_time")
                if surv is not None:
                    ev_ids.append(sid)
                    continue
                if s.duration:
                    try:
                        dur_float = float(str(s.duration).split()[0])
                        if dur_float < 18.0:
                            ev_ids.append(sid)
                            continue
                    except ValueError:
                        pass
                res = (s.result or s.outcome or "").lower()
                if any(w in res for w in ["defeat", "eliminated", "lost", "top 50", "top 40", "top 30", "top 20"]):
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["died early", "early death", "survive", "wiped early"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["survival"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-surv-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="survival"
                ))

        # 5. COMBAT (metric: damage)
        if cat_clean is None or cat_clean in ("combat", "damage"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                dmg = perf.get("damage") or perf.get("damage_dealt")
                if dmg is not None:
                    ev_ids.append(sid)
                    continue
                if s.kills is not None and s.kills <= 2:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["recoil", "spray", "whiff", "lost duel", "hipfire", "missed shots", "lost 1v1"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["combat"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-com-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="combat"
                ))

        # 6. LOOT EFFICIENCY (metric: rotation timing)
        if cat_clean is None or cat_clean in ("loot_efficiency", "loot", "objective"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "loot_time" in perf or "items_looted" in perf or "heals_used" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["looting", "no meds", "ran out of ammo", "caught looting", "level 1 helmet", "under-geared", "low loot"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["loot_efficiency"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-loot-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="loot_efficiency"
                ))

        # 7. VEHICLE USAGE (metric: distance travelled)
        if cat_clean is None or cat_clean in ("vehicle_usage", "vehicle", "movement"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "distance_travelled" in perf or "distance_traveled" in perf or "vehicle_distance" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["vehicle", "car", "buggy", "dacia", "uaz", "no car", "tire shot", "ran on foot", "drive-by", "blown up"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["vehicle_usage"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-veh-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="vehicle_usage"
                ))

        # 8. WEAPON CONFIGURATION (metric: damage)
        if cat_clean is None or cat_clean in ("weapon_configuration", "configuration", "weapon"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                if s.configuration:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["attachment", "compensator", "vertical grip", "m416", "beryl", "akm", "sensitivity", "red dot", "scope", "gyro"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["weapon_configuration"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-weap-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="weapon_configuration"
                ))

        # 9. FINAL-ZONE DECISION MAKING (metric: final placement)
        if cat_clean is None or cat_clean in ("final_zone_decision_making", "decision_making", "final_zone"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                fp = perf.get("final_placement")
                if fp is not None and isinstance(fp, (int, float)) and 2 <= int(fp) <= 10:
                    ev_ids.append(sid)
                    continue
                res = (s.result or s.outcome or "").lower()
                if any(w in res for w in ["top 10", "top 5", "2nd", "3rd", "4th", "5th"]):
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["final circle", "last squad", "top 3", "snake", "prone", "smoke", "threw final", "choked win", "final zone"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = BGMI_TASK_DEFINITIONS["final_zone_decision_making"]
                tasks.append(GamingTask(
                    task_id=f"task-bgmi-fzone-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    bgmi_focus="final_zone_decision_making"
                ))

        return tasks[:limit]

    def generate_bgmi_tasks(
        self,
        sessions: Optional[List[Session]] = None,
        task_type: Optional[str] = None,
        limit: int = 5
    ) -> TaskEngineResponse:
        """
        Public method to generate evidence-based BGMI tasks.
        Supports all 9 specific task types:
        - rotation_planning
        - zone_awareness
        - positioning
        - survival
        - combat
        - loot_efficiency
        - vehicle_usage
        - weapon_configuration
        - final_zone_decision_making
        """
        return self.create_tasks_from_history(
            game="BGMI",
            category=task_type,
            limit=limit,
            sessions=sessions
        )

    def _is_free_fire_game(self, game_name: Optional[str]) -> bool:
        """Determines if the game matches Free Fire / Free Fire MAX titles."""
        if not game_name:
            return False
        clean = game_name.strip().lower()
        return (
            clean in ("free fire", "free fire max", "freefire", "ff", "free fire battlegrounds")
            or "free fire" in clean
            or "freefire" in clean
        )

    def _detect_free_fire_tasks(
        self,
        filtered_sessions: List[Session],
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[GamingTask]:
        """
        Synthesizes Free Fire-specific tasks strictly from stored session evidence:
        1. movement (gloo wall speed, sprint/slide evasions)
        2. positioning (high ground ridge control, cover anchoring)
        3. combat (drag-headshot consistency, close-range duel trades)
        4. weapon/loadout usage (character ability synergy, weapon combo thresholds)
        5. safe-zone decisions (electric border shrink rotations, gatekeeping)
        6. survival (match pacing, vest durability, top-placement survival)
        7. objective performance (Clash Squad round wins, Arsenal key securement, revives)

        Strict rules:
        - Use only available stored metrics.
        - Do not invent game events.
        - Only generate a task when the required evidence data exists.
        """
        tasks: List[GamingTask] = []
        target_game = "Free Fire MAX"

        cat_clean = category.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_") if category else None

        # 1. MOVEMENT (metric: gloo_wall_speed, distance travelled)
        if cat_clean is None or cat_clean in ("movement", "gloo_wall", "gloo_shield", "evasion"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "gloo_wall_speed" in perf or "distance_travelled" in perf or "distance_traveled" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["movement", "sprint", "slide", "gloo wall", "gloo shield", "slow wall", "jump shot", "caught running", "evasion"]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["movement", "sprint", "slide", "gloo wall", "evasion", "gloo"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["movement"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-mov-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="movement"
                ))

        # 2. POSITIONING (metric: deaths)
        if cat_clean is None or cat_clean in ("positioning", "cover", "high_ground"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "deaths_in_open" in perf or "positioning_deaths" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["positioning", "open ground", "caught in open", "high ground", "low ground", "exposed", "bad cover", "crossfire", "ridge", "sandwiched"]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["positioning", "caught in open", "exposed", "high ground", "bad angle"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["positioning"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-pos-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="positioning"
                ))

        # 3. COMBAT (metric: headshot_rate, damage, kills)
        if cat_clean is None or cat_clean in ("combat", "headshot", "drag_headshot", "damage"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "headshot_rate" in perf or "headshot_pct" in perf or "damage" in perf or "damage_dealt" in perf:
                    ev_ids.append(sid)
                    continue
                if s.kills is not None and s.kills <= 2:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["headshot", "drag", "missed shots", "whiff", "whiffed", "lost duel", "lost 1v1", "shotgun", "close range", "drag shot", "combat"]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["whiff", "lost duel", "missed shot", "headshot", "combat"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["combat"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-com-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="combat"
                ))

        # 4. WEAPON/LOADOUT USAGE (metric: damage, kills)
        if cat_clean is None or cat_clean in (
            "weapon_loadout_usage", "weapon_loadout", "weapon_usage", "loadout_usage",
            "weapon", "loadout", "configuration"
        ):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                if s.configuration:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in [
                    "loadout", "character", "skill", "active skill", "cooldown",
                    "alok", "chrono", "k", "homer", "tatsuya", "wukong",
                    "mp40", "m1887", "woodpecker", "awm", "gun skin", "attachments", "weapon combo"
                ]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["loadout", "skill", "weapon", "alok", "chrono", "tatsuya"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["weapon_loadout_usage"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-weap-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="weapon_loadout_usage"
                ))

        # 5. SAFE-ZONE DECISIONS (metric: safezone_damage, survival duration)
        if cat_clean is None or cat_clean in (
            "safe_zone_decisions", "safe_zone", "safezone", "safezone_decisions",
            "strategy", "zone_decisions"
        ):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "safezone_damage" in perf or "bluezone_damage" in perf or "zone_transitions" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in [
                    "safe zone", "safezone", "zone shrink", "electric zone",
                    "caught outside", "late rotate", "gatekeep", "zone damage", "circle shrink"
                ]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["safe zone", "safezone", "zone damage", "electric zone"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["safe_zone_decisions"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-zone-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="safe_zone_decisions"
                ))

        # 6. SURVIVAL (metric: survival duration, final placement)
        if cat_clean is None or cat_clean in ("survival", "consistency", "survival_duration"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                surv = perf.get("survival_duration") or perf.get("survival_time")
                if surv is not None:
                    ev_ids.append(sid)
                    continue
                if s.duration:
                    try:
                        dur_float = float(str(s.duration).split()[0])
                        if dur_float < 10.0:
                            ev_ids.append(sid)
                            continue
                    except ValueError:
                        pass
                res = (s.result or s.outcome or "").lower()
                if any(w in res for w in ["defeat", "eliminated", "lost", "top 40", "top 30", "top 20", "top 15"]):
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["died early", "early death", "survive", "survival", "wiped early", "hot drop", "died off spawn"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["survival"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-surv-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="survival"
                ))

        # 7. OBJECTIVE PERFORMANCE (metric: clash_squad_rounds_won, final placement)
        if cat_clean is None or cat_clean in (
            "objective_performance", "objective", "clash_squad", "clash_squad_objective"
        ):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "clash_squad_rounds_won" in perf or "objectives_secured" in perf or "revives" in perf or "score" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in [
                    "clash squad", "objective", "arsenal", "airdrop", "air drop",
                    "revive", "revival", "booyah", "round win", "buy round", "capture"
                ]):
                    ev_ids.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["objective", "clash squad", "arsenal", "revive"]):
                            ev_ids.append(sid)
                            break
            if ev_ids:
                defn = FREE_FIRE_TASK_DEFINITIONS["objective_performance"]
                tasks.append(GamingTask(
                    task_id=f"task-ff-obj-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    free_fire_focus="objective_performance"
                ))

        return tasks[:limit]

    def generate_free_fire_tasks(
        self,
        sessions: Optional[List[Session]] = None,
        task_type: Optional[str] = None,
        limit: int = 5
    ) -> TaskEngineResponse:
        """
        Public method to generate evidence-based Free Fire tasks.
        Supports all 7 specific task types:
        - movement
        - positioning
        - combat
        - weapon_loadout_usage
        - safe_zone_decisions
        - survival
        - objective_performance
        """
        return self.create_tasks_from_history(
            game="Free Fire MAX",
            category=task_type,
            limit=limit,
            sessions=sessions
        )

    def _is_codm_game(self, game_name: Optional[str]) -> bool:
        """Determines if the game matches Call of Duty Mobile / CODM."""
        if not game_name:
            return False
        clean = game_name.strip().lower()
        return (
            clean in ("cod mobile", "codm", "call of duty mobile", "call of duty: mobile", "call of duty", "cod")
            or "codm" in clean
            or "cod mobile" in clean
            or "call of duty" in clean
        )

    def _detect_codm_tasks(
        self,
        filtered_sessions: List[Session],
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[GamingTask]:
        """
        Synthesizes COD Mobile-specific tasks strictly from stored session evidence:
        1. aim (snap-aim centering, upper-torso target acquisition)
        2. recoil (vertical/horizontal spray control)
        3. movement (slide-cancel mechanics, jump-peeking)
        4. positioning (headglitch power positions, choke control)
        5. loadout (Gunsmith attachment builds, perk synergy)
        6. objective play (Hardpoint hill time, Domination captures, S&D plants)
        7. deaths (death discipline, respawn intervals)
        8. accuracy (weapon shot accuracy, trigger discipline)
        9. score efficiency (scorestreak cycling, point bonuses)
        """
        tasks: List[GamingTask] = []
        target_game = "COD Mobile"

        cat_clean = category.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_") if category else None

        # 1. AIM (metric: headshot_pct)
        if cat_clean is None or cat_clean in ("aim", "snap_aim", "centering"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                hs = perf.get("headshot_pct") or perf.get("headshot_percentage")
                if hs is not None:
                    try:
                        hs_val = float(str(hs).replace("%", "").strip())
                        if hs_val < 25.0:
                            ev_ids.append(sid)
                            continue
                    except ValueError:
                        pass
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["aim", "centering", "snap aim", "whiffed aim", "off target", "ads speed"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["aim"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-aim-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="aim"
                ))

        # 2. RECOIL (metric: damage)
        if cat_clean is None or cat_clean in ("recoil", "combat", "recoil_control"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "recoil_control" in perf or "damage" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["recoil", "spray climb", "horizontal bounce", "bullet spread", "muzzle climb", "kick"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["recoil"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-rec-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="recoil"
                ))

        # 3. MOVEMENT (metric: deaths)
        if cat_clean is None or cat_clean in ("movement", "slide_cancel", "slide"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "distance_travelled" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["slide cancel", "slide-cancel", "jump peek", "dropshot", "drop shot", "movement", "sliding"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["movement"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-mov-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="movement"
                ))

        # 4. POSITIONING (metric: positioning_deaths)
        if cat_clean is None or cat_clean in ("positioning", "headglitch", "cover"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "positioning_deaths" in perf or "deaths_in_open" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["positioning", "headglitch", "head glitch", "open lane", "exposed", "bad angle", "middle lane"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["positioning"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-pos-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="positioning"
                ))

        # 5. LOADOUT (metric: damage)
        if cat_clean is None or cat_clean in ("loadout", "gunsmith", "configuration", "weapon_loadout"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                if s.configuration:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["loadout", "gunsmith", "attachment", "monolithic", "owc", "perk", "quick fix", "cbr4", "grau"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["loadout"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-load-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="loadout"
                ))

        # 6. OBJECTIVE PLAY (metric: objectives_secured)
        if cat_clean is None or cat_clean in ("objective_play", "objective", "hardpoint", "domination"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "objectives_secured" in perf or "bomb_plants" in perf or "captures" in perf or "hill_time" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["hardpoint", "domination", "bomb", "objective", "capture", "hill", "snd", "s&d", "defuse"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["objective_play"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-obj-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="objective_play"
                ))

        # 7. DEATHS (metric: deaths)
        if cat_clean is None or cat_clean in ("deaths", "consistency", "death_discipline"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                if s.deaths is not None and s.deaths >= 10:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["staggered", "trickling", "repeated deaths", "death streak", "died off spawn", "fed kills"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["deaths"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-dth-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="deaths"
                ))

        # 8. ACCURACY (metric: accuracy)
        if cat_clean is None or cat_clean in ("accuracy", "shot_accuracy"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                acc = perf.get("accuracy") or perf.get("shot_accuracy")
                if acc is not None:
                    try:
                        acc_val = float(str(acc).replace("%", "").strip())
                        if acc_val < 25.0:
                            ev_ids.append(sid)
                            continue
                    except ValueError:
                        pass
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["accuracy", "wasted ammo", "pre fire", "trigger discipline", "missed sprays"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["accuracy"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-acc-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="accuracy"
                ))

        # 9. SCORE EFFICIENCY (metric: score_efficiency)
        if cat_clean is None or cat_clean in ("score_efficiency", "score", "efficiency"):
            ev_ids = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                if "score_efficiency" in perf or "score" in perf:
                    ev_ids.append(sid)
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["score", "uav", "scorestreak", "killstreak", "operator skill", "points per minute"]):
                    ev_ids.append(sid)
            if ev_ids:
                defn = CODM_TASK_DEFINITIONS["score_efficiency"]
                tasks.append(GamingTask(
                    task_id=f"task-codm-sco-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=ev_ids,
                    status="pending",
                    codm_focus="score_efficiency"
                ))

        return tasks[:limit]

    def generate_codm_tasks(
        self,
        sessions: Optional[List[Session]] = None,
        task_type: Optional[str] = None,
        limit: int = 5
    ) -> TaskEngineResponse:
        """
        Public method to generate evidence-based COD Mobile tasks.
        Supports all 9 specific task types:
        - aim
        - recoil
        - movement
        - positioning
        - loadout
        - objective_play
        - deaths
        - accuracy
        - score_efficiency
        """
        return self.create_tasks_from_history(
            game="COD Mobile",
            category=task_type,
            limit=limit,
            sessions=sessions
        )

    def _is_valorant_game(self, game_name: Optional[str]) -> bool:
        """Determines if the game matches Valorant."""
        if not game_name:
            return False
        clean = game_name.strip().lower()
        return clean in ("valorant", "val", "riot valorant") or "valorant" in clean

    def _detect_valorant_tasks(
        self,
        filtered_sessions: List[Session],
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[GamingTask]:
        """
        Synthesizes Valorant-specific tasks strictly from stored session evidence:
        1. aim (micro-flicks, first-bullet tap accuracy)
        2. crosshair placement (head-level crosshair tracking)
        3. positioning (angle clearing, hardcover anchoring)
        4. economy (team buy-round synchronization, save thresholds)
        5. utility usage (flash/smoke/recon synchronization before pushes)
        6. map awareness (minimap awareness, flank control)
        7. round decisions (man-advantage discipline, post-plant clutch decisions)
        8. configuration (mouse eDPI and keybind consistency)
        9. consistency (pre-match warmup routines)

        Strict rule: Do not claim enemy positions unless actual game data provides them.
        """
        tasks: List[GamingTask] = []
        target_game = "Valorant"

        cat_clean = category.strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_") if category else None

        # 1. POSITIONING / CROSSHAIR PLACEMENT
        # Matches category 'positioning', 'crosshair_placement', 'crosshair'
        if cat_clean is None or cat_clean in ("positioning", "crosshair_placement", "crosshair", "crosshair_placement"):
            pos_evidence: List[Union[str, int]] = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                notes = (s.player_notes or "").lower()
                if any(term in notes for term in ["positioning", "ego-peek", "ego peek", "exposed", "bad angle", "overextended", "crosshair"]):
                    pos_evidence.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(term in desc for term in ["ego-peek", "ego peek", "positioning", "exposed", "bad angle", "crosshair"]):
                            pos_evidence.append(sid)
                            break
                perf = s.performance_metrics or s.stats or {}
                fd = perf.get("first_deaths")
                if fd is not None and isinstance(fd, (int, float)) and fd >= 4:
                    if sid not in pos_evidence:
                        pos_evidence.append(sid)

            if pos_evidence:
                defn = VALORANT_TASK_DEFINITIONS["positioning"]
                tasks.append(GamingTask(
                    task_id=f"task-val-pos-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=pos_evidence,
                    status="pending",
                    valorant_focus="positioning"
                ))

        # 2. ROUND DECISIONS (metric: Unforced deaths during man-advantage rounds)
        if cat_clean is None or cat_clean in ("round_decisions", "round_decision", "decision_making"):
            dec_evidence: List[Union[str, int]] = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                notes = (s.player_notes or "").lower()
                if any(term in notes for term in ["threw", "panic", "overtime mistake", "tilt", "tempted", "clutch"]):
                    dec_evidence.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        if ev.tilt_indicator and ev.tilt_indicator >= 5:
                            dec_evidence.append(sid)
                            break
                        if ev.impact == "negative" and ev.event_type in ("decision", "tilt"):
                            dec_evidence.append(sid)
                            break

            if dec_evidence:
                defn = VALORANT_TASK_DEFINITIONS["round_decisions"]
                tasks.append(GamingTask(
                    task_id=f"task-val-dec-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=dec_evidence,
                    status="pending",
                    valorant_focus="round_decisions"
                ))

        # 3. AIM (metric: Headshot accuracy percentage)
        if cat_clean is None or cat_clean == "aim":
            aim_evidence: List[Union[str, int]] = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                perf = s.performance_metrics or s.stats or {}
                hs = perf.get("headshot_pct") or perf.get("headshot_percentage")
                acc = perf.get("accuracy") or perf.get("shot_accuracy")
                if hs is not None:
                    try:
                        hs_num = float(str(hs).replace("%", "").strip())
                        if hs_num < 25.0:
                            aim_evidence.append(sid)
                            continue
                    except ValueError:
                        pass
                if acc is not None:
                    try:
                        acc_num = float(str(acc).replace("%", "").strip())
                        if acc_num < 30.0:
                            aim_evidence.append(sid)
                            continue
                    except ValueError:
                        pass

            if aim_evidence:
                defn = VALORANT_TASK_DEFINITIONS["aim"]
                tasks.append(GamingTask(
                    task_id=f"task-val-aim-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=aim_evidence,
                    status="pending",
                    valorant_focus="aim"
                ))

        # 4. ECONOMY (metric: round_decisions)
        if cat_clean is None or cat_clean in ("economy", "eco", "strategy"):
            eco_evidence: List[Union[str, int]] = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["economy", "eco", "force buy", "broken buy", "save round", "bonus round", "credits", "full save", "no money"]):
                    eco_evidence.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        desc = (ev.description or "").lower()
                        if any(w in desc for w in ["eco", "economy", "force buy", "save"]):
                            eco_evidence.append(sid)
                            break

            if eco_evidence:
                defn = VALORANT_TASK_DEFINITIONS["economy"]
                tasks.append(GamingTask(
                    task_id=f"task-val-eco-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=eco_evidence,
                    status="pending",
                    valorant_focus="economy"
                ))

        # 5. UTILITY USAGE (metric: assists)
        if cat_clean is None or cat_clean in ("utility_usage", "utility", "objective"):
            util_evidence: List[Union[str, int]] = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                if not sid:
                    continue
                notes = (s.player_notes or "").lower()
                if any(w in notes for w in ["utility", "flash", "smoke", "recon", "dart", "dry peek", "blind", "molly"]):
                    util_evidence.append(sid)
                    continue
                if s.timeline:
                    for ev in s.timeline:
                        if ev.event_type in ("utility", "flash", "smoke") or any(w in (ev.description or "").lower() for w in ["utility", "flash", "smoke"]):
                            util_evidence.append(sid)
                            break

            if util_evidence:
                defn = VALORANT_TASK_DEFINITIONS["utility_usage"]
                tasks.append(GamingTask(
                    task_id=f"task-val-util-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=util_evidence,
                    status="pending",
                    valorant_focus="utility_usage"
                ))

        # 6. MAP AWARENESS (metric: first_deaths)
        if cat_clean is None or cat_clean in ("map_awareness", "map"):
            map_losses: Dict[str, List[Union[str, int]]] = {}
            for s in filtered_sessions:
                sid = s.session_id or s.id
                m = s.map or s.map_or_level
                res = (s.result or s.outcome or "").lower()
                notes = (s.player_notes or "").lower()
                if m and sid and (any(l in res for l in ["defeat", "loss", "lost"]) or any(w in notes for w in ["flank", "backstab", "rotation", "minimap", "lurker"])):
                    map_losses.setdefault(m, []).append(sid)

            for map_name, sids in map_losses.items():
                if len(sids) >= 1:
                    defn = VALORANT_TASK_DEFINITIONS["map_awareness"]
                    tasks.append(GamingTask(
                        task_id=f"task-val-map-{uuid.uuid4().hex[:6]}",
                        game=target_game,
                        category=defn["category"],
                        objective=f"Master rotation timing and choke-point control on {map_name}",
                        description=f"Study push timings and defensive fallback lines specific to {map_name}.",
                        duration=defn["duration"],
                        metric_to_track=defn["metric_to_track"],
                        target=f"Eliminate first-death occurrences on {map_name}",
                        difficulty=defn["difficulty"],
                        evidence_session_ids=sids,
                        status="pending",
                        valorant_focus="map_awareness"
                    ))
                    break

        # 7. CONFIGURATION (metric: damage)
        if cat_clean is None or cat_clean in ("configuration", "config"):
            cfg_evidence: List[Union[str, int]] = []
            for s in filtered_sessions:
                sid = s.session_id or s.id
                cfg = s.configuration or s.character_or_loadout
                res = (s.result or s.outcome or "").lower()
                notes = (s.player_notes or "").lower()
                if (cfg and sid and any(l in res for l in ["defeat", "loss", "lost"])) or any(w in notes for w in ["sensitivity", "edpi", "keybind", "crosshair profile", "dpi", "loadout"]):
                    cfg_evidence.append(sid)

            if cfg_evidence:
                defn = VALORANT_TASK_DEFINITIONS["configuration"]
                tasks.append(GamingTask(
                    task_id=f"task-val-cfg-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=cfg_evidence,
                    status="pending",
                    valorant_focus="configuration"
                ))

        # 8. CONSISTENCY (metric: K/D ratio variance across consecutive sessions)
        if cat_clean is None or cat_clean in ("consistency", "warmup"):
            kd_sessions = [s for s in filtered_sessions if s.kd_ratio is not None and (s.session_id or s.id)]
            con_sids = []
            if len(kd_sessions) >= 2:
                kds = [s.kd_ratio for s in kd_sessions]
                kd_range = max(kds) - min(kds)
                if kd_range >= 0.8:
                    con_sids = [s.session_id or s.id for s in kd_sessions]
            if not con_sids:
                for s in filtered_sessions:
                    sid = s.session_id or s.id
                    notes = (s.player_notes or "").lower()
                    if any(w in notes for w in ["warmup", "consistency", "inconsistent", "cold", "variable"]):
                        con_sids.append(sid)

            if con_sids:
                defn = VALORANT_TASK_DEFINITIONS["consistency"]
                tasks.append(GamingTask(
                    task_id=f"task-val-con-{uuid.uuid4().hex[:6]}",
                    game=target_game,
                    category=defn["category"],
                    objective=defn["objective"],
                    description=defn["description"],
                    duration=defn["duration"],
                    metric_to_track=defn["metric_to_track"],
                    target=defn["target"],
                    difficulty=defn["difficulty"],
                    evidence_session_ids=con_sids,
                    status="pending",
                    valorant_focus="consistency"
                ))

        return tasks[:limit]

    def generate_valorant_tasks(
        self,
        sessions: Optional[List[Session]] = None,
        task_type: Optional[str] = None,
        limit: int = 5
    ) -> TaskEngineResponse:
        """
        Public method to generate evidence-based Valorant tasks.
        Supports all 9 specific task types:
        - aim
        - crosshair_placement
        - positioning
        - economy
        - utility_usage
        - map_awareness
        - round_decisions
        - configuration
        - consistency
        """
        return self.create_tasks_from_history(
            game="Valorant",
            category=task_type,
            limit=limit,
            sessions=sessions
        )


# Global default engine
default_task_engine = GamingTaskEngine()
