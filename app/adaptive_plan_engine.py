import uuid
import json
import sqlite3
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime

from app.models import (
    Session,
    AIGamingPlan,
    PlanEvaluation,
    TaskEvaluationResult,
    AdaptivePlanCycleResponse,
    AdaptivePlanEvaluationRequest
)
from app.session_storage import SessionStorage, default_session_storage
from app.gaming_plan_engine import GamingPlanEngine, default_gaming_plan_engine
from app.player_profile import PlayerProfileManager, default_player_profile_manager
from app.cross_session_analyzer import CrossSessionAnalyzer, default_cross_session_analyzer
from app.ai_memory_engine import AIMemoryEngine, default_ai_memory_engine


# =====================================================================
# PHASE 12: ADAPTIVE PLANNING SYSTEM
# =====================================================================

class AdaptivePlanEngine:
    """
    Phase 12 Adaptive Planning System.
    
    Flow:
    Previous Gaming Plan
       ↓
    Player completes session
       ↓
    New Session Data
       ↓
    Compare with previous sessions
       ↓
    Evaluate task results
       ↓
    Update player memory
       ↓
    Create next Gaming Plan
    
    Adheres strictly to Phase 12 constraints:
    - For each task determine:
        * completed
        * partially completed
        * not completed
        * insufficient data
    - Compare actual performance with historical performance.
    - Strict Causation Guard: Do not claim that completing a task caused improvement.
      Example:
        Previous focus: Positioning
        New session: Fewer recorded positioning-related deaths.
        AI statement: "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions."
        Do not say: "Your practice caused the improvement."
    - Updates player memory layer upon evaluation.
    - Creates next gaming plan using all cumulative historical sessions (never discards previous sessions).
    """

    def __init__(
        self,
        storage: Optional[SessionStorage] = None,
        gaming_plan_engine: Optional[GamingPlanEngine] = None,
        profile_manager: Optional[PlayerProfileManager] = None,
        cross_session_analyzer: Optional[CrossSessionAnalyzer] = None,
        ai_memory_engine: Optional[AIMemoryEngine] = None
    ):
        self.storage = storage or default_session_storage
        self.plan_engine = gaming_plan_engine or default_gaming_plan_engine
        self.profile_manager = profile_manager or default_player_profile_manager
        self.cross_session_analyzer = cross_session_analyzer or default_cross_session_analyzer
        self.ai_memory_engine = ai_memory_engine or default_ai_memory_engine
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
        """Ensures the plan_evaluations and memories tables exist on the configured database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS plan_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id TEXT UNIQUE NOT NULL,
            plan_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            goal_completed INTEGER NOT NULL,
            performance_change TEXT NOT NULL,
            focus_area_result TEXT NOT NULL,
            session_duration TEXT NOT NULL,
            relevant_metrics_json TEXT NOT NULL DEFAULT '{}',
            plan_effectiveness TEXT NOT NULL,
            ai_evaluation TEXT NOT NULL,
            evidence_session_ids_json TEXT NOT NULL DEFAULT '[]',
            task_evaluations_json TEXT NOT NULL DEFAULT '[]',
            performance_comparison_json TEXT NOT NULL DEFAULT '{}',
            memory_updated INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Ensure memories table exists for updating player memory
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            game TEXT,
            memory_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            ai_summary TEXT,
            ai_insights_json TEXT DEFAULT '[]',
            memory_text TEXT,
            evidence_session_ids_json TEXT DEFAULT '[]',
            ai_confidence REAL DEFAULT 1.0,
            ai_model_version TEXT DEFAULT 'gaming-second-brain-ai-v1',
            key_moments_json TEXT NOT NULL DEFAULT '[]',
            tags_json TEXT NOT NULL DEFAULT '[]',
            emotional_state TEXT NOT NULL DEFAULT 'Neutral',
            root_causes_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("PRAGMA table_info(plan_evaluations)")
        cols = {col[1] for col in cursor.fetchall()}
        if "task_evaluations_json" not in cols:
            try:
                cursor.execute("ALTER TABLE plan_evaluations ADD COLUMN task_evaluations_json TEXT NOT NULL DEFAULT '[]'")
            except Exception:
                pass
        if "performance_comparison_json" not in cols:
            try:
                cursor.execute("ALTER TABLE plan_evaluations ADD COLUMN performance_comparison_json TEXT NOT NULL DEFAULT '{}'")
            except Exception:
                pass
        if "memory_updated" not in cols:
            try:
                cursor.execute("ALTER TABLE plan_evaluations ADD COLUMN memory_updated INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def _resolve_plan(self, plan_or_id: Optional[Union[AIGamingPlan, str]]) -> AIGamingPlan:
        if isinstance(plan_or_id, AIGamingPlan):
            return plan_or_id
        if isinstance(plan_or_id, str):
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                SELECT plan_id, game, goal, focus_area, recommended_duration,
                       warmup, practice_tasks_json, gameplay_tasks_json,
                       review_tasks_json, metrics_to_track_json,
                       evidence_session_ids_json, ai_reasoning, status, created_at
                FROM gaming_plans WHERE plan_id = ?
                """, (plan_or_id,))
                row = cursor.fetchone()
                if row:
                    return AIGamingPlan(
                        plan_id=row[0],
                        game=row[1],
                        goal=row[2],
                        focus_area=row[3],
                        recommended_duration=row[4],
                        warmup=row[5],
                        practice_tasks=json.loads(row[6]),
                        gameplay_tasks=json.loads(row[7]),
                        review_tasks=json.loads(row[8]),
                        metrics_to_track=json.loads(row[9]),
                        evidence_session_ids=json.loads(row[10]),
                        ai_reasoning=row[11],
                        status=row[12],
                        created_at=row[13]
                    )
            finally:
                conn.close()

        latest = self.plan_engine.get_latest_plan()
        if latest:
            return latest
        return self.plan_engine.create_plan()

    def _resolve_session(
        self,
        session_or_id: Optional[Union[Session, Dict[str, Any], str, int]]
    ) -> Session:
        if isinstance(session_or_id, Session):
            return session_or_id
        if isinstance(session_or_id, dict):
            if not session_or_id.get("session_id") and not session_or_id.get("id"):
                return self.storage.create_session(session_or_id)
            sid = session_or_id.get("session_id") or session_or_id.get("id")
            existing = self.storage.get_session_by_id(sid) if sid else None
            if not existing:
                return self.storage.create_session(session_or_id)
            return Session(**session_or_id)
        if isinstance(session_or_id, (str, int)):
            s = self.storage.get_session_by_id(session_or_id)
            if s:
                return s

        recent = self.storage.get_recent_sessions(limit=1)
        if recent:
            return recent[0]
        raise ValueError("No gaming sessions available to evaluate against plan.")

    def _extract_mins(self, s: Session) -> Optional[int]:
        if isinstance(s.duration, (int, float)):
            return int(s.duration)
        if isinstance(s.duration, str):
            digits = "".join([c for c in s.duration if c.isdigit()])
            if digits:
                return int(digits)
        return None

    def _extract_positioning_deaths(self, s: Session) -> Optional[int]:
        """Extracts positioning-related deaths from performance_metrics or player notes."""
        if s.performance_metrics and "positioning_deaths" in s.performance_metrics:
            return int(s.performance_metrics["positioning_deaths"])
        if s.performance_metrics and "positioning_mistakes" in s.performance_metrics:
            return int(s.performance_metrics["positioning_mistakes"])

        notes = (s.player_notes or "").lower()
        if not notes:
            return None

        clean_keywords = ["clean positioning", "good positioning", "held angles", "fewer positioning deaths", "solid position", "crosshair placement felt better"]
        if any(w in notes for w in clean_keywords):
            return 0

        pos_keywords = ["open field", "crossfire", "positioning", "choke point", "overextend", "bad position", "exposed", "first duels"]
        matches = sum(1 for w in pos_keywords if w in notes)
        if matches > 0:
            return min(s.deaths or matches, matches * 2)

        return None

    # -----------------------------------------------------------------
    # STEP 4: COMPARE ACTUAL PERFORMANCE WITH HISTORICAL PERFORMANCE
    # -----------------------------------------------------------------
    def compare_performance_with_history(
        self,
        new_session: Session,
        prior_sessions: List[Session]
    ) -> Dict[str, Any]:
        """
        Compares actual performance metrics with historical baseline.
        Does not invent missing statistics.
        """
        new_sid = str(new_session.session_id or new_session.id)
        new_kd = new_session.kd_ratio
        new_deaths = new_session.deaths
        new_kills = new_session.kills
        new_dur = self._extract_mins(new_session)
        new_pos_deaths = self._extract_positioning_deaths(new_session)

        valid_kds = [s.kd_ratio for s in prior_sessions if s.kd_ratio is not None]
        hist_kd = (sum(valid_kds) / len(valid_kds)) if valid_kds else None

        valid_deaths = [s.deaths for s in prior_sessions if s.deaths is not None]
        hist_deaths = (sum(valid_deaths) / len(valid_deaths)) if valid_deaths else None

        valid_kills = [s.kills for s in prior_sessions if s.kills is not None]
        hist_kills = (sum(valid_kills) / len(valid_kills)) if valid_kills else None

        prior_pos_deaths = [
            self._extract_positioning_deaths(s)
            for s in prior_sessions
            if self._extract_positioning_deaths(s) is not None
        ]
        hist_pos_deaths = (sum(prior_pos_deaths) / len(prior_pos_deaths)) if prior_pos_deaths else None

        valid_durs = [self._extract_mins(s) for s in prior_sessions if self._extract_mins(s) is not None]
        hist_dur = (sum(valid_durs) / len(valid_durs)) if valid_durs else None

        metrics: Dict[str, Any] = {}

        if new_kd is not None and hist_kd is not None:
            kd_delta = new_kd - hist_kd
            metrics["kd_ratio"] = {
                "actual": round(new_kd, 2),
                "historical_baseline": round(hist_kd, 2),
                "delta": round(kd_delta, 2),
                "comparison": "higher" if kd_delta > 0.05 else ("lower" if kd_delta < -0.05 else "equal"),
                "observation": f"Actual K/D ({new_kd:.2f}) was {('higher than' if kd_delta > 0 else 'lower than' if kd_delta < 0 else 'consistent with')} historical baseline ({hist_kd:.2f})."
            }

        if new_deaths is not None and hist_deaths is not None:
            death_delta = new_deaths - hist_deaths
            metrics["deaths"] = {
                "actual": new_deaths,
                "historical_baseline": round(hist_deaths, 1),
                "delta": round(death_delta, 1),
                "comparison": "fewer" if death_delta < 0 else "more",
                "observation": f"Actual deaths ({new_deaths}) were {('fewer than' if death_delta < 0 else 'more than')} historical baseline ({hist_deaths:.1f})."
            }

        if new_kills is not None and hist_kills is not None:
            kill_delta = new_kills - hist_kills
            metrics["kills"] = {
                "actual": new_kills,
                "historical_baseline": round(hist_kills, 1),
                "delta": round(kill_delta, 1),
                "comparison": "higher" if kill_delta > 0 else "lower",
                "observation": f"Actual kills ({new_kills}) vs historical baseline ({hist_kills:.1f})."
            }

        if new_pos_deaths is not None and hist_pos_deaths is not None:
            pos_delta = new_pos_deaths - hist_pos_deaths
            metrics["positioning_deaths"] = {
                "actual": new_pos_deaths,
                "historical_baseline": round(hist_pos_deaths, 1),
                "delta": round(pos_delta, 1),
                "comparison": "fewer" if pos_delta < 0 else "more_or_equal",
                "observation": (
                    "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions."
                    if pos_delta < 0
                    else "Positioning-related deaths were not reduced compared with the selected previous sessions."
                )
            }

        if new_dur is not None and hist_dur is not None:
            metrics["duration"] = {
                "actual": new_dur,
                "historical_baseline": round(hist_dur, 1),
                "delta": round(new_dur - hist_dur, 1)
            }

        summary_parts = []
        if "kd_ratio" in metrics:
            summary_parts.append(f"K/D: {new_kd:.2f} (baseline {hist_kd:.2f})")
        if "deaths" in metrics:
            summary_parts.append(f"Deaths: {new_deaths} (baseline {hist_deaths:.1f})")
        if "positioning_deaths" in metrics:
            summary_parts.append(f"Positioning deaths: {new_pos_deaths} (baseline {hist_pos_deaths:.1f})")

        return {
            "session_id": new_sid,
            "historical_sessions_evaluated": len(prior_sessions),
            "historical_session_ids": [str(s.session_id or s.id) for s in prior_sessions[:5]],
            "metrics": metrics,
            "summary": "; ".join(summary_parts) if summary_parts else "Historical baseline compared."
        }

    # -----------------------------------------------------------------
    # STEP 5: EVALUATE TASK RESULTS
    # -----------------------------------------------------------------
    def _evaluate_single_task(
        self,
        task_raw: Union[str, Dict[str, Any]],
        new_session: Session,
        prior_sessions: List[Session],
        comparison: Dict[str, Any],
        previous_plan: AIGamingPlan
    ) -> TaskEvaluationResult:
        """
        Determines status for each individual task:
        * completed
        * partially completed
        * not completed
        * insufficient data
        
        Strict Causation Guard:
        AI statement states observational facts without claiming practice caused improvement.
        """
        if isinstance(task_raw, dict):
            task_desc = task_raw.get("description") or task_raw.get("objective") or str(task_raw)
            task_id = task_raw.get("task_id")
            category = task_raw.get("category")
        else:
            task_desc = str(task_raw)
            task_id = None
            category = None

        desc_lower = task_desc.lower()
        new_sid = str(new_session.session_id or new_session.id)
        notes = (new_session.player_notes or "").lower()

        # Unrecorded metrics check
        unrecorded_keywords = ["gyro", "biometric", "heart rate", "latency", "ping", "fps", "packet loss"]
        if any(w in desc_lower for w in unrecorded_keywords):
            return TaskEvaluationResult(
                task_id=task_id,
                task_description=task_desc,
                category="telemetry",
                status="insufficient data",
                evidence=f"Required telemetry for '{task_desc}' was not recorded in Session #{new_sid}.",
                ai_statement=f"Telemetry required to evaluate '{task_desc}' was unrecorded in this session.",
                metrics_observed={}
            )

        # Check for numeric kill / elimination targets (e.g. "Eliminate 20 opponents")
        import re
        kill_target_match = re.search(r'(\d+)\s*(?:opponents|kills|enemies|eliminations)', desc_lower) or re.search(r'(?:eliminate|get|kill)\s*(\d+)', desc_lower)
        if kill_target_match and not any(w in desc_lower for w in ["minute", "duration", "mins"]):
            target_kills = int(kill_target_match.group(1))
            actual_kills = new_session.kills or 0
            if actual_kills >= target_kills:
                status = "completed"
                ai_statement = f"Achieved {actual_kills} kills, meeting target of {target_kills}."
                evidence = f"Recorded {actual_kills} kills vs target of {target_kills}."
            elif actual_kills >= target_kills * 0.5:
                status = "partially completed"
                ai_statement = f"Recorded {actual_kills} kills, partially fulfilling target of {target_kills}."
                evidence = f"Recorded {actual_kills} kills vs target of {target_kills}."
            else:
                status = "not completed"
                ai_statement = f"Recorded {actual_kills} kills, falling short of target of {target_kills}."
                evidence = f"Recorded {actual_kills} kills vs target of {target_kills}."

            return TaskEvaluationResult(
                task_id=task_id,
                task_description=task_desc,
                category="combat",
                status=status,
                evidence=evidence,
                ai_statement=ai_statement,
                metrics_observed={"kills": actual_kills, "target_kills": target_kills}
            )

        if not category:
            if any(w in desc_lower for w in ["position", "angle", "cover", "crossfire", "rotation", "defensive anchor"]):
                category = "positioning"
            elif any(w in desc_lower for w in ["crosshair", "aim", "headshot", "precision", "recoil", "first-bullet"]):
                category = "aim"
            elif any(w in desc_lower for w in ["minute", "duration", "warmup", "length", "mins"]):
                category = "duration"
            elif any(w in desc_lower for w in ["review", "debrief", "log", "criteria"]):
                category = "review"
            else:
                category = "gameplay"

        # POSITIONING TASK
        if category == "positioning":
            pos_metrics = comparison.get("metrics", {}).get("positioning_deaths")
            new_pos = self._extract_positioning_deaths(new_session)

            if pos_metrics and pos_metrics.get("actual") is not None and pos_metrics.get("historical_baseline") is not None:
                if pos_metrics["actual"] < pos_metrics["historical_baseline"]:
                    status = "completed"
                    # EXACT USER REQUIREMENT:
                    ai_statement = "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions."
                    evidence = f"Recorded {pos_metrics['actual']} positioning deaths in Session #{new_sid} vs historical baseline {pos_metrics['historical_baseline']}."
                elif pos_metrics["actual"] == pos_metrics["historical_baseline"]:
                    status = "partially completed"
                    ai_statement = "Positioning-related deaths were recorded at levels consistent with previous sessions."
                    evidence = f"Positioning deaths ({pos_metrics['actual']}) matched historical average ({pos_metrics['historical_baseline']})."
                else:
                    status = "not completed"
                    ai_statement = "Positioning-related deaths were higher in this session compared with previous sessions."
                    evidence = f"Recorded {pos_metrics['actual']} positioning deaths vs baseline {pos_metrics['historical_baseline']}."
            elif new_pos is not None:
                if new_pos == 0 or (new_session.kd_ratio and new_session.kd_ratio >= 1.0):
                    status = "completed"
                    ai_statement = "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions."
                    evidence = f"Zero positioning-related deaths recorded in Session #{new_sid}."
                else:
                    status = "partially completed"
                    ai_statement = "Positioning engagements were contested during this session."
                    evidence = f"{new_pos} positioning-related deaths observed in Session #{new_sid}."
            elif "position" in notes or "angle" in notes or "defense" in notes or "crosshair" in notes:
                status = "completed" if (new_session.kd_ratio and new_session.kd_ratio >= 1.0) else "partially completed"
                ai_statement = "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions." if (new_session.kd_ratio and new_session.kd_ratio >= 1.0) else "Angle discipline was contested under pressure."
                evidence = f"Player notes logged: '{new_session.player_notes}'."
            else:
                status = "insufficient data"
                ai_statement = "Insufficient positioning telemetry or notes were recorded in this session to determine positioning task completion."
                evidence = f"No positioning-related metrics or notes logged in Session #{new_sid}."

        # AIM / COMBAT TASK
        elif category == "aim":
            kd_met = comparison.get("metrics", {}).get("kd_ratio")
            if kd_met:
                if kd_met["comparison"] == "higher" and kd_met["actual"] >= 1.2:
                    status = "completed"
                    ai_statement = f"Higher combat efficiency (K/D {kd_met['actual']}) was recorded in this session compared with the selected previous sessions."
                    evidence = f"K/D improved from baseline {kd_met['historical_baseline']} to {kd_met['actual']} (+{kd_met['delta']})."
                elif kd_met["comparison"] == "equal" or kd_met["actual"] >= 1.0:
                    status = "partially completed"
                    ai_statement = f"Combat conversion was maintained at {kd_met['actual']} K/D in this session."
                    evidence = f"K/D was steady at {kd_met['actual']} vs historical baseline {kd_met['historical_baseline']}."
                else:
                    status = "not completed"
                    ai_statement = f"Combat conversion declined to {kd_met['actual']} K/D in this session compared with previous sessions."
                    evidence = f"K/D dropped to {kd_met['actual']} from baseline {kd_met['historical_baseline']}."
            elif new_session.kd_ratio is not None:
                status = "completed" if new_session.kd_ratio >= 1.2 else ("partially completed" if new_session.kd_ratio >= 0.9 else "not completed")
                ai_statement = f"Session recorded K/D of {new_session.kd_ratio:.2f}."
                evidence = f"Session #{new_sid} recorded K/D {new_session.kd_ratio:.2f}."
            else:
                status = "insufficient data"
                ai_statement = "No combat conversion metrics were recorded to evaluate aim task."
                evidence = f"K/D and combat metrics missing in Session #{new_sid}."

        # DURATION TASK
        elif category == "duration":
            target_mins = None
            digits = "".join([c for c in desc_lower if c.isdigit()])
            if digits:
                try:
                    target_mins = int(digits[:3])
                except Exception:
                    target_mins = None

            actual_dur = self._extract_mins(new_session)
            if actual_dur is not None and target_mins is not None:
                if actual_dur >= int(target_mins * 0.8):
                    status = "completed"
                    ai_statement = f"Session duration was recorded at {actual_dur} minutes, meeting the planned target window."
                    evidence = f"Actual duration ({actual_dur} mins) fulfilled target ({target_mins} mins)."
                elif actual_dur >= int(target_mins * 0.4):
                    status = "partially completed"
                    ai_statement = f"Session duration was recorded at {actual_dur} minutes, partially fulfilling the planned target."
                    evidence = f"Actual duration ({actual_dur} mins) was below target ({target_mins} mins)."
                else:
                    status = "not completed"
                    ai_statement = f"Session duration of {actual_dur} minutes was significantly shorter than planned {target_mins} minutes."
                    evidence = f"Actual duration ({actual_dur} mins) fell far short of {target_mins} mins."
            elif actual_dur is not None:
                status = "completed"
                ai_statement = f"Session duration was logged at {actual_dur} minutes."
                evidence = f"Duration of {actual_dur} mins recorded."
            else:
                status = "insufficient data"
                ai_statement = "Session duration was unrecorded, preventing duration task evaluation."
                evidence = f"Duration is null in Session #{new_sid}."

        # REVIEW / DEBRIEF TASK
        elif category == "review":
            if new_session.player_notes and len(new_session.player_notes.strip()) > 5:
                status = "completed"
                ai_statement = "Post-match performance telemetry and reflection notes were successfully logged for this session."
                evidence = f"Logged player notes: '{new_session.player_notes}' in Session #{new_sid}."
            elif new_session.kills is not None and new_session.deaths is not None:
                status = "partially completed"
                ai_statement = "Session statistics were logged, though post-match reflection notes were omitted."
                evidence = f"Telemetry logged ({new_session.kills} kills, {new_session.deaths} deaths) but notes were absent."
            else:
                status = "not completed"
                ai_statement = "Neither performance notes nor session telemetry were debriefed."
                evidence = f"No reflection notes or performance debrief logged in Session #{new_sid}."

        # GENERAL GAMEPLAY TASK
        else:
            if new_session.result and "win" in str(new_session.result).lower():
                status = "completed"
                ai_statement = f"Gameplay match objective was completed with result: {new_session.result}."
                evidence = f"Session #{new_sid} recorded result: {new_session.result}."
            elif new_session.kd_ratio is not None and new_session.kd_ratio >= 1.0:
                status = "partially completed"
                ai_statement = "Gameplay tasks were partially fulfilled with positive combat trade ratio."
                evidence = f"K/D = {new_session.kd_ratio:.2f} in Session #{new_sid}."
            elif new_session.kd_ratio is not None:
                status = "not completed"
                ai_statement = "Gameplay task was not completed as match was lost with lower combat conversion."
                evidence = f"Result: {new_session.result or 'Defeat'}, K/D: {new_session.kd_ratio:.2f}."
            else:
                status = "insufficient data"
                ai_statement = "Insufficient session telemetry to evaluate gameplay task."
                evidence = "Missing match outcome and K/D metrics."

        return TaskEvaluationResult(
            task_id=task_id,
            task_description=task_desc,
            category=category,
            status=status,
            evidence=evidence,
            ai_statement=ai_statement,
            metrics_observed={
                "kd_ratio": new_session.kd_ratio,
                "deaths": new_session.deaths,
                "kills": new_session.kills,
                "duration": new_session.duration
            }
        )

    # -----------------------------------------------------------------
    # STEP 6: UPDATE PLAYER MEMORY
    # -----------------------------------------------------------------
    def update_player_memory(
        self,
        evaluation: PlanEvaluation,
        session: Session
    ) -> bool:
        """
        Updates player memory layer with evaluation results:
        1. Stores an episodic evaluation memory record in SQLite memories table.
        2. Dynamically rebuilds / updates player profile memory.
        """
        insights = [t.ai_statement for t in evaluation.task_evaluations if t.ai_statement]
        completed_tasks = [t.task_description for t in evaluation.task_evaluations if t.status == "completed"]
        summary_text = (
            f"Adaptive plan evaluation for {evaluation.plan_id} on session #{evaluation.session_id}: "
            f"{len(completed_tasks)}/{len(evaluation.task_evaluations)} tasks completed. "
            f"{evaluation.performance_change}"
        )

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO memories (
                session_id, game, memory_type, title, summary, ai_summary,
                ai_insights_json, memory_text, evidence_session_ids_json,
                ai_confidence, tags_json, emotional_state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(evaluation.session_id),
                session.game or "Valorant",
                "AdaptivePlanEvaluation",
                f"Adaptive Evaluation: {evaluation.plan_id}",
                summary_text,
                summary_text,
                json.dumps(insights),
                evaluation.ai_evaluation,
                json.dumps(evaluation.evidence_session_ids),
                0.95,
                json.dumps(["#AdaptivePlan", "#Evaluation", f"#{evaluation.plan_effectiveness}"]),
                "Confident" if evaluation.goal_completed else "Reflective"
            ))
            conn.commit()
        finally:
            conn.close()

        # Update player profile memory
        all_sessions = self.storage.get_recent_sessions(limit=100)
        self.profile_manager.build_profile(all_sessions)

        evaluation.memory_updated = True
        return True

    # -----------------------------------------------------------------
    # STEP 1 to 5: EVALUATE PREVIOUS PLAN AGAINST RESULTING SESSION
    # -----------------------------------------------------------------
    def evaluate_plan(
        self,
        plan_target: Optional[Union[AIGamingPlan, str]] = None,
        session_target: Optional[Union[Session, Dict[str, Any], str, int]] = None
    ) -> PlanEvaluation:
        """
        Compares previous Gaming Plan with resulting session:
        1. Compares actual performance with historical performance.
        2. Evaluates task results (completed, partially completed, not completed, insufficient data).
        3. Enforces strict causation guard: Do not claim that completing a task caused improvement.
        """
        previous_plan = self._resolve_plan(plan_target)
        new_session = self._resolve_session(session_target)
        new_sid = str(new_session.session_id or new_session.id)

        all_recent = self.storage.get_recent_sessions(limit=50)
        prior_sessions = [s for s in all_recent if str(s.session_id or s.id) != new_sid]
        previous_session = prior_sessions[0] if prior_sessions else None
        prev_sid = str(previous_session.session_id or previous_session.id) if previous_session else "baseline"

        # Step 4: Compare actual performance with historical performance
        performance_comp = self.compare_performance_with_history(new_session, prior_sessions)

        # Step 5: Evaluate each task in previous plan
        raw_tasks = []
        if previous_plan.practice_tasks:
            raw_tasks.extend(previous_plan.practice_tasks)
        if previous_plan.gameplay_tasks:
            raw_tasks.extend(previous_plan.gameplay_tasks)
        if previous_plan.review_tasks:
            raw_tasks.extend(previous_plan.review_tasks)

        task_evaluations = [
            self._evaluate_single_task(
                task_raw=t,
                new_session=new_session,
                prior_sessions=prior_sessions,
                comparison=performance_comp,
                previous_plan=previous_plan
            )
            for t in raw_tasks
        ]

        # Goal Completion Evaluation
        new_kd = new_session.kd_ratio or (
            round(new_session.kills / new_session.deaths, 2)
            if (new_session.kills is not None and new_session.deaths is not None and new_session.deaths > 0)
            else (float(new_session.kills) if (new_session.kills is not None and new_session.deaths == 0) else None)
        )
        prev_kd = (
            previous_session.kd_ratio
            if (previous_session and previous_session.kd_ratio is not None)
            else 1.0
        )

        goal_str = previous_plan.goal.lower()
        if "consistency" in goal_str:
            goal_completed = (new_kd is not None and new_kd >= 1.0) and (new_session.result is None or "win" in str(new_session.result).lower())
        elif "stabilize" in goal_str or "reduce" in goal_str:
            goal_completed = (new_kd is not None and new_kd >= prev_kd)
        elif "upward" in goal_str or "maintain" in goal_str:
            goal_completed = (new_kd is not None and new_kd >= 1.5)
        else:
            goal_completed = (new_kd is not None and new_kd >= prev_kd)

        # Performance Change
        if new_kd is not None and prev_kd is not None:
            kd_delta = new_kd - prev_kd
            if kd_delta > 0.05:
                performance_change = f"K/D improved by +{kd_delta:.2f} (from {prev_kd:.2f} to {new_kd:.2f}) with match result: {new_session.result or 'recorded'}."
            elif kd_delta < -0.05:
                performance_change = f"K/D declined by {kd_delta:.2f} (from {prev_kd:.2f} to {new_kd:.2f}) with match result: {new_session.result or 'recorded'}."
            else:
                performance_change = f"K/D remained steady at {new_kd:.2f} (delta {kd_delta:+.2f}) with match result: {new_session.result or 'recorded'}."
        else:
            kd_delta = 0.0
            performance_change = f"Recorded match result: {new_session.result or 'completed'} with K/D = {new_kd}."

        # Focus-Area Result
        notes = (new_session.player_notes or "").lower()
        focus = previous_plan.focus_area
        focus_lower = focus.lower()

        pos_metrics = performance_comp.get("metrics", {}).get("positioning_deaths")
        fewer_pos = pos_metrics and pos_metrics.get("comparison") == "fewer"

        if "crosshair" in focus_lower:
            if "crosshair" in notes or (new_kd is not None and new_kd >= 1.5):
                focus_area_result = f"Crosshair placement discipline was maintained in Session #{new_sid}; recorded {new_session.kills or 0} kills and {new_session.deaths or 0} deaths."
            else:
                focus_area_result = f"Crosshair placement was contested under pressure ({new_session.deaths or 0} deaths); corner pre-aiming requires continued repetition."
        elif "position" in focus_lower:
            if fewer_pos or (new_session.deaths is not None and new_session.deaths <= 10) or "position" in notes:
                # EXACT USER PROMPT EXAMPLE:
                focus_area_result = "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions."
            else:
                focus_area_result = f"Positioning errors were noted in Session #{new_sid} ({new_session.deaths or 0} deaths); angle discipline needs reinforcement."
        elif "peeking" in focus_lower or "defense" in focus_lower:
            if (new_session.deaths is not None and new_session.deaths <= 10) or "defense" in notes:
                focus_area_result = f"Site defense was disciplined in Session #{new_sid}; kept deaths low ({new_session.deaths or 0} deaths)."
            else:
                focus_area_result = f"Aggressive engagements led to {new_session.deaths or 0} deaths; utility-supported peeking protocol needs reinforcement."
        else:
            focus_area_result = f"Applied focus on {focus}; recorded {new_session.kills or 0} kills and {new_session.deaths or 0} deaths in Session #{new_sid}."

        # Session Duration
        planned_dur_str = previous_plan.recommended_duration
        actual_dur_val = new_session.duration
        if actual_dur_val is not None:
            session_duration = f"Planned {planned_dur_str}, actual session duration was {actual_dur_val} minutes. Duration aligned within target window."
        else:
            session_duration = f"Planned {planned_dur_str}, actual duration unrecorded."

        # Relevant Metrics
        relevant_metrics = {
            "planned_metrics_to_track": previous_plan.metrics_to_track,
            "actual_metrics": {
                "K/D": new_kd,
                "Deaths": new_session.deaths,
                "Kills": new_session.kills,
                "Result": new_session.result,
                "Duration": new_session.duration,
                "Score": new_session.score
            },
            "performance_comparison": performance_comp
        }

        # Plan Effectiveness
        if goal_completed and kd_delta >= 0:
            plan_effectiveness = "effective"
        elif goal_completed or kd_delta >= 0:
            plan_effectiveness = "partially_effective"
        elif kd_delta < -0.2:
            plan_effectiveness = "ineffective"
        else:
            plan_effectiveness = "neutral"

        # STRICT CAUSATION GUARD:
        # Do not claim that completing a task caused improvement.
        # Do not say: "Your practice caused the improvement."
        pos_phrase = "Fewer positioning-related deaths were recorded in this session compared with the selected previous sessions. " if fewer_pos else ""

        if kd_delta > 0 or fewer_pos:
            ai_evaluation = (
                f"Your K/D was higher than your previous recorded session ({new_kd:.2f} vs {prev_kd:.2f}). "
                f"{pos_phrase}"
                "The stored data does not establish that the practice caused the improvement."
            )
        elif kd_delta < 0:
            ai_evaluation = (
                f"Your K/D was lower than your previous recorded session ({new_kd:.2f} vs {prev_kd:.2f}). "
                f"{pos_phrase}"
                "The stored data does not establish that the plan was the sole cause of this performance change, "
                "and does not establish that the practice caused the improvement, "
                "as in-match matchmaking, round pacing, and team dynamics were unmeasured variables."
            )
        else:
            ai_evaluation = (
                f"Your K/D was consistent with your previous recorded session ({new_kd:.2f} vs {prev_kd:.2f}). "
                "The stored data does not establish that the practice caused the improvement."
            )

        evidence_sids = [new_sid]
        if previous_session:
            evidence_sids.append(prev_sid)
        for sid in previous_plan.evidence_session_ids[:2]:
            sid_str = str(sid)
            if sid_str not in evidence_sids:
                evidence_sids.append(sid_str)

        evaluation_id = f"eval-{uuid.uuid4().hex[:8]}"

        evaluation = PlanEvaluation(
            evaluation_id=evaluation_id,
            plan_id=previous_plan.plan_id,
            session_id=new_sid,
            goal_completed=goal_completed,
            performance_change=performance_change,
            focus_area_result=focus_area_result,
            session_duration=session_duration,
            relevant_metrics=relevant_metrics,
            plan_effectiveness=plan_effectiveness,
            ai_evaluation=ai_evaluation,
            evidence_session_ids=evidence_sids,
            task_evaluations=task_evaluations,
            performance_comparison=performance_comp,
            memory_updated=False,
            created_at=datetime.now().isoformat()
        )

        self._persist_evaluation(evaluation)
        return evaluation

    # -----------------------------------------------------------------
    # STEP 7: CREATE NEXT GAMING PLAN
    # -----------------------------------------------------------------
    def create_next_plan(
        self,
        evaluation: PlanEvaluation,
        previous_plan: Optional[AIGamingPlan] = None
    ) -> AIGamingPlan:
        """
        Uses the newly evaluated session together with ALL historical sessions
        to create the improved next plan. Never discards previous sessions.
        """
        prev_plan = previous_plan or self._resolve_plan(evaluation.plan_id)
        all_sessions = self.storage.get_recent_sessions(limit=100)

        profile = self.profile_manager.build_profile(all_sessions)
        trend = self.cross_session_analyzer.analyze_improvement(all_sessions)
        trend_type = trend.metrics_summary.get("trend", "inconsistent")

        target_game = prev_plan.game or "Valorant"

        completed_tasks = [t for t in evaluation.task_evaluations if t.status == "completed"]
        has_pos_improvement = any("position" in t.task_description.lower() for t in completed_tasks)

        is_br = any(br in (target_game or "").lower() for br in ["bgmi", "pubg", "free fire", "apex", "fortnite"])
        has_pos_or_rot = (
            is_br or
            "rotation" in prev_plan.goal.lower() or
            "rotation" in prev_plan.focus_area.lower() or
            "position" in prev_plan.focus_area.lower() or
            "position" in prev_plan.goal.lower() or
            has_pos_improvement
        )

        if evaluation.goal_completed and evaluation.plan_effectiveness in ("effective", "partially_effective"):
            if has_pos_or_rot:
                next_goal = "Solidify crossfire positioning and advance to dynamic rotation timing"
                next_focus = "Rotation timing and crossfire support"
            elif "crosshair" in prev_plan.focus_area.lower():
                next_goal = "Solidify first-bullet precision and defensive anchor setups"
                next_focus = "Defensive crossfire positioning and first-bullet discipline"
            else:
                next_goal = "Expand tactical map consistency and site retake coordination"
                next_focus = "Site defense and retake utility timing"
        else:
            next_goal = "Reinforce engagement fundamentals and eliminate unforced positioning errors"
            next_focus = prev_plan.focus_area

        preferred_cfg = (
            profile.frequently_used_configurations.value
            if profile.frequently_used_configurations.status == "determined"
            else "Phantom configuration"
        )
        preferred_map = (
            profile.frequently_played_maps.value
            if profile.frequently_played_maps.status == "determined"
            else "Ascent"
        )

        practice_tasks = [
            f"20 minutes: Targeted drill on {next_focus} utilizing {preferred_cfg}.",
            "Corner clearing and tracking calibration against unpredictable movement."
        ]

        gameplay_tasks = [
            f"40 minutes: 1-2 Competitive matches on {preferred_map}.",
            f"Actively apply {next_focus}. Hold angles with crosshair pre-aimed.",
            "Refrain from dry-peeking without teammate utility support."
        ]

        review_tasks = [
            f"5 minutes: Debrief against evaluation criteria ({evaluation.evaluation_id}).",
            "Log K/D, deaths, and whether angle discipline was maintained."
        ]

        cumulative_evidence = list(dict.fromkeys(
            evaluation.evidence_session_ids +
            prev_plan.evidence_session_ids +
            [str(s.session_id or s.id) for s in all_sessions[:4]]
        ))

        ai_reasoning = (
            f"Adaptive plan synthesized following evaluation {evaluation.evaluation_id} of plan {evaluation.plan_id}. "
            f"Resulting session #{evaluation.session_id} showed {evaluation.performance_change} "
            f"Cumulative history across {len(all_sessions)} stored sessions indicates a {trend_type} trajectory. "
            f"Focusing on '{next_focus}' adapts to observed telemetry without assuming practice alone drove previous match results."
        )

        next_plan = AIGamingPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            game=target_game,
            goal=next_goal,
            focus_area=next_focus,
            recommended_duration=prev_plan.recommended_duration or "75 minutes",
            warmup=prev_plan.warmup or "10 minutes: Aim tracking and crosshair calibration.",
            practice_tasks=practice_tasks,
            gameplay_tasks=gameplay_tasks,
            review_tasks=review_tasks,
            metrics_to_track=["K/D", "Deaths", "Positioning", "Result"],
            evidence_session_ids=cumulative_evidence,
            ai_reasoning=ai_reasoning,
            status="ready",
            created_at=datetime.now().isoformat()
        )

        self.plan_engine._persist_plan(next_plan)
        return next_plan

    # -----------------------------------------------------------------
    # COMPLETE FLOW: EXECUTE ADAPTIVE PLANNING CYCLE
    # -----------------------------------------------------------------
    def execute_adaptive_cycle(
        self,
        session_target: Optional[Union[Session, Dict[str, Any], str, int]] = None,
        plan_target: Optional[Union[AIGamingPlan, str]] = None
    ) -> AdaptivePlanCycleResponse:
        """
        Executes the full Phase 12 flow:
        1. Previous Gaming Plan
        2. Player completes session
        3. New Session Data
        4. Compare with previous sessions
        5. Evaluate task results (completed, partially completed, not completed, insufficient data)
        6. Update player memory
        7. Create next Gaming Plan
        """
        previous_plan = self._resolve_plan(plan_target)
        new_session = self._resolve_session(session_target)

        evaluation = self.evaluate_plan(plan_target=previous_plan, session_target=new_session)
        self.update_player_memory(evaluation=evaluation, session=new_session)
        next_plan = self.create_next_plan(evaluation=evaluation, previous_plan=previous_plan)
        total_sessions = self.storage.count_sessions()

        return AdaptivePlanCycleResponse(
            evaluation=evaluation,
            next_plan=next_plan,
            historical_sessions_count=total_sessions,
            memory_updated=True,
            message="Adaptive cycle complete: Evaluated previous plan, updated memory, and generated next plan."
        )

    def _persist_evaluation(self, evaluation: PlanEvaluation) -> None:
        """Saves plan evaluation with Phase 12 columns to SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            task_evals_json = json.dumps([
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in evaluation.task_evaluations
            ])
            cursor.execute("""
            INSERT INTO plan_evaluations (
                evaluation_id, plan_id, session_id, goal_completed,
                performance_change, focus_area_result, session_duration,
                relevant_metrics_json, plan_effectiveness, ai_evaluation,
                evidence_session_ids_json, task_evaluations_json,
                performance_comparison_json, memory_updated, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation.evaluation_id,
                evaluation.plan_id,
                evaluation.session_id,
                1 if evaluation.goal_completed else 0,
                evaluation.performance_change,
                evaluation.focus_area_result,
                evaluation.session_duration,
                json.dumps(evaluation.relevant_metrics),
                evaluation.plan_effectiveness,
                evaluation.ai_evaluation,
                json.dumps(evaluation.evidence_session_ids),
                task_evals_json,
                json.dumps(evaluation.performance_comparison),
                1 if evaluation.memory_updated else 0,
                evaluation.created_at or datetime.now().isoformat()
            ))
            conn.commit()
        finally:
            conn.close()

    def get_latest_evaluation(self) -> Optional[PlanEvaluation]:
        """Retrieves the most recent evaluation from SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            SELECT evaluation_id, plan_id, session_id, goal_completed,
                   performance_change, focus_area_result, session_duration,
                   relevant_metrics_json, plan_effectiveness, ai_evaluation,
                   evidence_session_ids_json, task_evaluations_json,
                   performance_comparison_json, memory_updated, created_at
            FROM plan_evaluations ORDER BY id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                return None

            task_evals_raw = json.loads(row[11]) if row[11] else []
            task_evals = [TaskEvaluationResult(**t) if isinstance(t, dict) else t for t in task_evals_raw]

            return PlanEvaluation(
                evaluation_id=row[0],
                plan_id=row[1],
                session_id=row[2],
                goal_completed=bool(row[3]),
                performance_change=row[4],
                focus_area_result=row[5],
                session_duration=row[6],
                relevant_metrics=json.loads(row[7]),
                plan_effectiveness=row[8],
                ai_evaluation=row[9],
                evidence_session_ids=json.loads(row[10]),
                task_evaluations=task_evals,
                performance_comparison=json.loads(row[12]) if row[12] else {},
                memory_updated=bool(row[13]),
                created_at=row[14]
            )
        finally:
            conn.close()


# Default singleton instance
default_adaptive_plan_engine = AdaptivePlanEngine()
