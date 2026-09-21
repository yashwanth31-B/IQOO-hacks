"""
Phase 8: AI Gaming Plan Engine.

Creates a personalized AI Gaming Plan using:
1. Player Profile (preferences, strengths, areas of improvement)
2. Previous Sessions (historical raw telemetry and debriefs)
3. Performance Metrics (K/D, survival duration, win rate, rates, accuracy)
4. Detected Game (manual or simulated detection)
5. Detected Map (game-specific map detection)
6. AI Tasks (grounded tasks generated from session evidence)
7. Historical Patterns (cross-session trends and performance trajectories)

Strict Flow:
Game detected -> Map detected -> Retrieve player history -> Identify relevant patterns -> Generate tasks -> Build Gaming Plan
"""

import uuid
import json
import sqlite3
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from app.models import (
    Session,
    PlayerProfile,
    PerformanceReport,
    GamingTask,
    AIGamingPlan,
    CreateGamingPlanRequest
)
from app.session_storage import SessionStorage, default_session_storage
from app.player_profile import PlayerProfileManager, default_player_profile_manager
from app.performance_engine import GamingPerformanceEngine, default_performance_engine
from app.task_engine import GamingTaskEngine, default_task_engine
from app.cross_session_analyzer import CrossSessionAnalyzer, default_cross_session_analyzer
from app.detection import default_detector


INSUFFICIENT_DATA_MSG = "Not enough data to create a personalized plan."
MIN_SESSIONS_REQUIRED = 1


class GamingPlanEngine:
    """
    Phase 8: AI Gaming Plan Engine.
    Synthesizes a personalized AI Gaming Plan for the player's next session.
    """

    def __init__(
        self,
        storage: Optional[SessionStorage] = None,
        profile_manager: Optional[PlayerProfileManager] = None,
        performance_engine: Optional[GamingPerformanceEngine] = None,
        task_engine: Optional[GamingTaskEngine] = None,
        cross_session_analyzer: Optional[CrossSessionAnalyzer] = None
    ):
        self.storage = storage or default_session_storage
        self.profile_manager = profile_manager or default_player_profile_manager
        self.performance_engine = performance_engine or default_performance_engine
        self.task_engine = task_engine or default_task_engine
        self.cross_session_analyzer = cross_session_analyzer or default_cross_session_analyzer
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.storage.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        return conn

    def _ensure_schema(self) -> None:
        """Ensures the gaming_plans table exists and has all required columns in SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS gaming_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id TEXT UNIQUE NOT NULL,
            game TEXT NOT NULL,
            map TEXT,
            goal TEXT NOT NULL,
            focus_area TEXT NOT NULL,
            recommended_duration TEXT NOT NULL,
            warmup TEXT NOT NULL,
            practice TEXT,
            gameplay TEXT,
            review TEXT,
            practice_tasks_json TEXT NOT NULL DEFAULT '[]',
            gameplay_tasks_json TEXT NOT NULL DEFAULT '[]',
            review_tasks_json TEXT NOT NULL DEFAULT '[]',
            metrics_to_track_json TEXT NOT NULL DEFAULT '[]',
            evidence_session_ids_json TEXT NOT NULL DEFAULT '[]',
            ai_reasoning TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Non-destructive migrations for existing DBs
        cursor.execute("PRAGMA table_info(gaming_plans)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        new_cols = [
            ("map", "TEXT"),
            ("practice", "TEXT"),
            ("gameplay", "TEXT"),
            ("review", "TEXT")
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE gaming_plans ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        conn.commit()
        conn.close()

    def create_plan(
        self,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        custom_goal: Optional[str] = None,
        sessions: Optional[List[Session]] = None
    ) -> AIGamingPlan:
        """
        Executes the Phase 8 6-step flow:
        Step 1: Game detected & Map detected
        Step 2: Retrieve player history
        Step 3: Access Player Profile & Performance Metrics
        Step 4: Identify relevant patterns
        Step 5: Generate AI tasks
        Step 6: Build Gaming Plan
        """
        # -------------------------------------------------------------
        # STEP 1: GAME & MAP DETECTED
        # -------------------------------------------------------------
        target_game = game
        target_map = map_name

        # Fallback to active detector if not explicitly passed
        if not target_game and default_detector and hasattr(default_detector, "last_result") and default_detector.last_result:
            target_game = default_detector.last_result.game
            if not target_map and hasattr(default_detector.last_result, "map"):
                target_map = default_detector.last_result.map

        # -------------------------------------------------------------
        # STEP 2: RETRIEVE PLAYER HISTORY (Previous Sessions)
        # -------------------------------------------------------------
        all_sessions = sessions if sessions is not None else self.storage.get_recent_sessions(limit=100)

        # Filter by game if game is known
        if target_game:
            filtered_sessions = [s for s in all_sessions if s.game and target_game.lower() in s.game.lower()]
        else:
            filtered_sessions = all_sessions

        # If no target_game was specified, deduce from history
        if not target_game and filtered_sessions:
            target_game = filtered_sessions[0].game

        # If no target_map was specified, deduce from history
        if not target_map and filtered_sessions:
            target_map = filtered_sessions[0].map or filtered_sessions[0].map_or_level

        # RULE: If insufficient data exists (< 2 sessions)
        if len(filtered_sessions) < 2:
            return AIGamingPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                game=target_game or "Unknown",
                map=target_map or "Unknown",
                goal=INSUFFICIENT_DATA_MSG,
                focus_area=INSUFFICIENT_DATA_MSG,
                recommended_duration=INSUFFICIENT_DATA_MSG,
                warmup=INSUFFICIENT_DATA_MSG,
                practice="15 minutes",
                gameplay="40 minutes",
                review="10 minutes",
                practice_tasks=[],
                gameplay_tasks=[],
                review_tasks=[],
                metrics_to_track=[],
                evidence_session_ids=[],
                ai_reasoning=INSUFFICIENT_DATA_MSG,
                status="insufficient_data",
                created_at=datetime.now().isoformat()
            )

        # -------------------------------------------------------------
        # STEP 3: PLAYER PROFILE & PERFORMANCE METRICS
        # -------------------------------------------------------------
        profile = self.profile_manager.build_profile(filtered_sessions)
        perf_summary = self.performance_engine.calculate_aggregate_performance(filtered_sessions, game=target_game)

        # Map-specific sessions if map is specified
        map_sessions = []
        if target_map:
            map_sessions = [
                s for s in filtered_sessions
                if (s.map and target_map.lower() in s.map.lower()) or (s.map_or_level and target_map.lower() in s.map_or_level.lower())
            ]

        # Collect evidence session IDs from profile and map
        profile_evidence = (
            profile.preferred_game.evidence_session_ids
            + profile.frequently_used_configurations.evidence_session_ids
            + profile.frequently_played_maps.evidence_session_ids
        )
        map_evidence = [str(s.session_id or s.id) for s in map_sessions if s.session_id or s.id]

        # -------------------------------------------------------------
        # STEP 4: IDENTIFY RELEVANT PATTERNS
        # -------------------------------------------------------------
        trend_analysis = self.cross_session_analyzer.analyze_improvement(filtered_sessions)
        trend_type = trend_analysis.metrics_summary.get("trend", "inconsistent")

        # Collect pattern evidence
        pattern_evidence = trend_analysis.evidence_session_ids

        # -------------------------------------------------------------
        # STEP 5: GENERATE AI TASKS
        # -------------------------------------------------------------
        task_response = self.task_engine.create_tasks_from_history(game=target_game, sessions=filtered_sessions)
        tasks = task_response.tasks
        task_evidence = task_response.evidence_session_ids

        # Combine evidence session IDs
        combined_evidence = []
        # Prioritize map evidence first if available
        for sid in map_evidence + task_evidence + pattern_evidence + profile_evidence:
            sid_str = str(sid)
            if sid_str and sid_str not in combined_evidence:
                combined_evidence.append(sid_str)

        # Fallback to recent session IDs
        if not combined_evidence:
            combined_evidence = [str(s.session_id or s.id) for s in filtered_sessions if s.session_id or s.id]

        # -------------------------------------------------------------
        # STEP 6: BUILD GAMING PLAN
        # -------------------------------------------------------------
        is_battle_royale = bool(
            target_game and any(br in target_game.lower() for br in ["bgmi", "pubg", "free fire", "apex", "fortnite"])
        )

        # Determine Goal & Focus Area strictly from stored telemetry, notes, patterns, and tasks
        all_notes = " ".join((s.player_notes or "") for s in filtered_sessions).lower()
        high_death_sessions = [s for s in filtered_sessions if s.deaths is not None and s.deaths > 12]

        if is_battle_royale:
            focus_area = "Survival & Rotation Decisions"
            goal = "Improve survival and rotation decisions."
        elif "crosshair" in all_notes or trend_type == "inconsistent":
            focus_area = "Crosshair placement"
        elif high_death_sessions or "dry-peek" in all_notes or "ego" in all_notes:
            focus_area = "Utility-supported peeking and site defense discipline"
        elif "fatigue" in all_notes or "tilt" in all_notes:
            focus_area = "Pacing and mental game reset"
        elif tasks:
            focus_area = tasks[0].category.replace("_", " ").title()
        else:
            focus_area = "Crosshair placement"

        if is_battle_royale:
            goal = "Improve survival and rotation decisions."
        elif custom_goal:
            goal = custom_goal
        elif trend_type == "inconsistent":
            goal = "Improve consistency"
        elif trend_type == "decreasing":
            goal = "Stabilize combat efficiency and reduce unforced deaths"
        elif trend_type == "increasing":
            goal = "Maintain upward momentum and solidify high combat conversion"
        elif tasks:
            goal = tasks[0].objective
        else:
            goal = "Improve consistency"

        # Routine Breakdown
        warmup = "10 minutes"
        practice = "15 minutes"
        gameplay = "40 minutes"
        review = "10 minutes"
        recommended_duration = "75 minutes"

        # Tasks lists
        practice_tasks: List[str] = []
        if is_battle_royale:
            practice_tasks.append("15 minutes: Vehicle rotation drills and terrain scout timing in training grounds.")
            practice_tasks.append("Long-range single-tap recoil compensation drills.")
        elif tasks:
            for t in tasks[:2]:
                practice_tasks.append(f"{t.duration}: {t.description}")
        else:
            practice_tasks.append(f"15 minutes: Dedicated warmup and mechanical aim calibration.")

        gameplay_tasks: List[str] = []
        if is_battle_royale:
            map_name_str = target_map or "Erangel"
            gameplay_tasks.append(f"40 minutes: 1-2 matches on {map_name_str} prioritizing early compound control.")
            gameplay_tasks.append("Avoid congested open field crossings without vehicle cover.")
        elif target_map:
            gameplay_tasks.append(f"40 minutes: Competitive matches on {target_map} holding disciplined angles.")
        else:
            gameplay_tasks.append("40 minutes: Competitive play applying mechanical drill focus.")

        review_tasks: List[str] = []
        if is_battle_royale:
            review_tasks.append("10 minutes: Review rotation pathing and log final placement.")
            review_tasks.append("Debrief cause of elimination during zone transitions.")
        else:
            review_tasks.append("10 minutes: Log K/D, unforced mistakes, and tactical takeaways.")

        # Metrics to track
        if is_battle_royale:
            metrics_to_track = [
                "Survival time",
                "Deaths",
                "Rotation decisions",
                "Final placement"
            ]
        else:
            metrics_to_track = [
                "K/D",
                "Deaths",
                "Accuracy",
                "Result"
            ]

        # AI Reasoning
        evidence_phrase = f"Sessions {', '.join('#' + x for x in combined_evidence[:3])}"
        ai_reasoning = (
            f"Plan synthesized from {len(filtered_sessions)} stored sessions ({evidence_phrase}) "
            f"for {target_game} on {target_map or 'standard map'}. "
            f"Cross-session analysis identified {trend_type} performance trajectory. "
            f"Analysis of historical patterns and AI tasks identified '{focus_area}' as highest impact, "
            f"targeting measurable improvement in {', '.join(metrics_to_track[:2])}."
        )

        plan = AIGamingPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            game=target_game or "General",
            map=target_map or "General",
            goal=goal,
            focus_area=focus_area,
            recommended_duration=recommended_duration,
            warmup=warmup,
            practice=practice,
            gameplay=gameplay,
            review=review,
            practice_tasks=practice_tasks,
            gameplay_tasks=gameplay_tasks,
            review_tasks=review_tasks,
            metrics_to_track=metrics_to_track,
            evidence_session_ids=combined_evidence,
            ai_reasoning=ai_reasoning,
            status="ready",
            created_at=datetime.now().isoformat()
        )

        self._persist_plan(plan)
        return plan

    def _persist_plan(self, plan: AIGamingPlan) -> None:
        """Saves generated plan to SQLite storage."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO gaming_plans (
                plan_id, game, map, goal, focus_area, recommended_duration,
                warmup, practice, gameplay, review,
                practice_tasks_json, gameplay_tasks_json,
                review_tasks_json, metrics_to_track_json,
                evidence_session_ids_json, ai_reasoning, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.plan_id,
                plan.game,
                plan.map,
                plan.goal,
                plan.focus_area,
                plan.recommended_duration,
                plan.warmup,
                plan.practice,
                plan.gameplay,
                plan.review,
                json.dumps(plan.practice_tasks),
                json.dumps(plan.gameplay_tasks),
                json.dumps(plan.review_tasks),
                json.dumps(plan.metrics_to_track),
                json.dumps(plan.evidence_session_ids),
                plan.ai_reasoning,
                plan.status,
                plan.created_at or datetime.now().isoformat()
            ))
            conn.commit()
        finally:
            conn.close()

    def get_latest_plan(self) -> Optional[AIGamingPlan]:
        """Retrieves the most recent plan from SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            SELECT plan_id, game, map, goal, focus_area, recommended_duration,
                   warmup, practice, gameplay, review,
                   practice_tasks_json, gameplay_tasks_json,
                   review_tasks_json, metrics_to_track_json,
                   evidence_session_ids_json, ai_reasoning, status, created_at
            FROM gaming_plans ORDER BY id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return None
            return AIGamingPlan(
                plan_id=row[0],
                game=row[1],
                map=row[2],
                goal=row[3],
                focus_area=row[4],
                recommended_duration=row[5],
                warmup=row[6],
                practice=row[7] or "15 minutes",
                gameplay=row[8] or "40 minutes",
                review=row[9] or "10 minutes",
                practice_tasks=json.loads(row[10]),
                gameplay_tasks=json.loads(row[11]),
                review_tasks=json.loads(row[12]),
                metrics_to_track=json.loads(row[13]),
                evidence_session_ids=json.loads(row[14]),
                ai_reasoning=row[15],
                status=row[16],
                created_at=row[17]
            )
        finally:
            conn.close()


# Default singleton instance
default_gaming_plan_engine = GamingPlanEngine()
