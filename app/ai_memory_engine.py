import json
import sqlite3
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.models import Session, AIMemoryRecord, AIMemoryProcessingResult
from app.session_storage import SessionStorage, default_session_storage


# =====================================================================
# CONSTANTS & HALLUCINATION GUARDS
# =====================================================================

NOT_ENOUGH_DATA = "Not enough data to determine this."
AI_MODEL_VERSION = "gaming-second-brain-ai-v1"
HISTORICAL_SESSIONS_THRESHOLD = 3


# =====================================================================
# PHASE 5: AI MEMORY ENGINE
# =====================================================================

class AIMemoryEngine:
    """
    AI Memory Engine for Gaming Second Brain (Phase 5).
    
    Processes completed gaming sessions into structured, verifiable intelligence:
    1. Summarizes the session strictly using recorded telemetry.
    2. Extracts important facts without inventing values.
    3. Identifies notable performance.
    4. Generates structured insights supported strictly by data.
    5. Stores the generated memory, keeping AI memory strictly separate from raw session telemetry.
    
    Hallucination Protection:
    - Never invents scores, dates, configurations, maps, performance, or behavior.
    - If information is unavailable, explicitly uses: 'Not enough data to determine this.'
    - Pattern Memory and Player Profile Memory are NOT generated unless sufficient
      historical evidence exists (>= 3 sessions).
    """

    def __init__(self, storage: Optional[SessionStorage] = None, model_version: str = AI_MODEL_VERSION):
        self.storage = storage or default_session_storage
        self.model_version = model_version
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.storage.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Ensures the memories table exists on the configured database."""
        conn = self._get_connection()
        cursor = conn.cursor()
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
        conn.commit()
        conn.close()

    def _to_session(self, session_data: Union[Session, Dict[str, Any]]) -> Session:
        if isinstance(session_data, Session):
            return session_data
        if isinstance(session_data, dict):
            return Session(**session_data)
        raise ValueError(f"Expected Session or dict, got {type(session_data).__name__}")

    # -----------------------------------------------------------------
    # 1. SUMMARIZE THE SESSION
    # -----------------------------------------------------------------
    def summarize_session(self, session: Union[Session, Dict[str, Any]]) -> str:
        """
        Summarizes the session strictly based on recorded fields.
        Never invents missing values (kills, deaths, maps, duration, etc.).
        Example complete:
        'Session #18 was a 72-minute Valorant session with 18 kills and 10 deaths.'
        """
        s = self._to_session(session)
        sid = s.session_id or s.id or "current"
        sid_str = f"Session #{sid}" if str(sid).isdigit() else f"Session {sid}"

        parts = []

        # Duration phrase (only if present)
        dur_phrase = ""
        if s.duration is not None:
            if isinstance(s.duration, (int, float)):
                dur_phrase = f"{int(s.duration)}-minute "
            elif isinstance(s.duration, str):
                s_strip = s.duration.strip().lower()
                if "min" in s_strip:
                    dur_phrase = f"{s.duration.strip()} "
                elif s_strip.isdigit():
                    dur_phrase = f"{s_strip}-minute "
                else:
                    dur_phrase = f"{s.duration.strip()} "

        # Game phrase
        game_phrase = s.game if s.game else "gaming"

        # Map phrase
        map_phrase = f" on {s.map}" if s.map else ""

        # Performance phrase (kills & deaths)
        perf_phrase = ""
        if s.kills is not None and s.deaths is not None:
            perf_phrase = f" with {s.kills} kills and {s.deaths} deaths"
        elif s.kills is not None:
            perf_phrase = f" with {s.kills} kills"
        elif s.deaths is not None:
            perf_phrase = f" with {s.deaths} deaths"

        # Result phrase
        result_phrase = ""
        if s.result:
            result_phrase = f" ({s.result})"

        summary = f"{sid_str} was a {dur_phrase}{game_phrase} session{map_phrase}{perf_phrase}{result_phrase}."
        # Clean up any double spaces
        summary = " ".join(summary.split())
        return summary

    # -----------------------------------------------------------------
    # 2. EXTRACT IMPORTANT FACTS
    # -----------------------------------------------------------------
    def extract_important_facts(self, session: Union[Session, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extracts factual attributes directly from the session.
        Never fabricates facts that are missing.
        """
        s = self._to_session(session)
        facts: Dict[str, Any] = {}

        if s.session_id is not None:
            facts["session_id"] = str(s.session_id)
        elif s.id is not None:
            facts["session_id"] = str(s.id)

        if s.game:
            facts["game"] = s.game
        if s.game_mode:
            facts["game_mode"] = s.game_mode
        if s.map:
            facts["map"] = s.map
        if s.configuration:
            facts["configuration"] = s.configuration
        if s.started_at:
            facts["started_at"] = str(s.started_at)
        if s.ended_at:
            facts["ended_at"] = str(s.ended_at)
        if s.duration is not None:
            facts["duration"] = s.duration
        if s.score:
            facts["score"] = s.score
        if s.kills is not None:
            facts["kills"] = s.kills
        if s.deaths is not None:
            facts["deaths"] = s.deaths
        if s.assists is not None:
            facts["assists"] = s.assists
        if s.kd_ratio is not None:
            facts["kd_ratio"] = s.kd_ratio
        if s.result:
            facts["result"] = s.result
        if s.player_notes:
            facts["player_notes"] = s.player_notes
        if s.performance_metrics:
            facts["performance_metrics"] = s.performance_metrics
        if s.tags:
            facts["tags"] = s.tags
        if s.data_source:
            facts["data_source"] = s.data_source

        return facts

    # -----------------------------------------------------------------
    # 3. IDENTIFY NOTABLE PERFORMANCE
    # -----------------------------------------------------------------
    def identify_notable_performance(
        self,
        session: Union[Session, Dict[str, Any]],
        historical_sessions: Optional[List[Session]] = None
    ) -> str:
        """
        Identifies notable achievements or combat trends.
        If data is unavailable, explicitly returns: 'Not enough data to determine this.'
        """
        s = self._to_session(session)

        has_kd = s.kd_ratio is not None or (s.kills is not None and s.deaths is not None)
        has_result = bool(s.result)
        has_kills = s.kills is not None

        # Check if performance telemetry exists
        if not has_kd and not has_result and not has_kills:
            return NOT_ENOUGH_DATA

        # High kill / K/D performance
        if s.kd_ratio is not None:
            kd = s.kd_ratio
            # Check for flawless match
            if s.deaths == 0 and s.kills is not None and s.kills > 0:
                return f"Flawless performance: Player recorded {s.kills} kills with 0 deaths."

            if kd >= 1.8:
                perf_desc = f"Strong performance session: Player achieved a {kd:.1f} K/D"
                if s.kills is not None and s.deaths is not None:
                    perf_desc += f" ({s.kills} kills, {s.deaths} deaths)"
                if s.result:
                    perf_desc += f" and won the match" if s.result.lower().startswith("win") else f" with match result {s.result}"
                return perf_desc + "."
            elif kd >= 1.0:
                return f"Positive performance: Maintained a {kd:.1f} K/D ratio."
            else:
                return f"Challenging performance: Recorded a {kd:.1f} K/D ratio."

        if s.result:
            return f"Notable outcome: Match ended in {s.result}."

        return NOT_ENOUGH_DATA

    # -----------------------------------------------------------------
    # 4. GENERATE STRUCTURED INSIGHTS (Supported only by data)
    # -----------------------------------------------------------------
    def generate_structured_insights(self, session: Union[Session, Dict[str, Any]]) -> List[str]:
        """
        Generates structured insights ONLY when supported by recorded telemetry.
        Never generates hallucinated or unsupported claims.
        """
        s = self._to_session(session)
        insights: List[str] = []

        # Insight 1: Configuration / Weapon usage
        if s.configuration:
            if isinstance(s.configuration, dict):
                weapon = s.configuration.get("primary_weapon") or s.configuration.get("weapon")
                sens = s.configuration.get("sensitivity")
                if weapon and sens is not None:
                    insights.append(f"Used {weapon} configuration with sensitivity {sens}.")
                elif weapon:
                    insights.append(f"Equipped {weapon} configuration.")
                else:
                    insights.append(f"Recorded configuration settings: {json.dumps(s.configuration)}.")
            elif isinstance(s.configuration, str):
                insights.append(f"Active loadout configuration: {s.configuration}.")

        # Insight 2: High K/D combat conversion
        if s.kd_ratio is not None and s.kd_ratio >= 1.5:
            if s.result and s.result.lower().startswith("win"):
                insights.append(f"High combat conversion ({s.kd_ratio:.1f} K/D) directly correlated with match victory.")
            else:
                insights.append(f"Achieved strong combat efficiency of {s.kd_ratio:.1f} K/D.")

        # Insight 3: Player reflection / notes
        if s.player_notes:
            insights.append(f"Player debrief: \"{s.player_notes}\"")

        # Insight 4: Duration insight
        if s.duration is not None and isinstance(s.duration, (int, float)) and s.duration > 60:
            insights.append(f"Extended session duration ({s.duration} minutes).")

        return insights

    # -----------------------------------------------------------------
    # 5. GENERATE EPISODIC MEMORY
    # -----------------------------------------------------------------
    def generate_episodic_memory(self, session: Union[Session, Dict[str, Any]]) -> AIMemoryRecord:
        """
        Creates Episodic Memory representing this individual gaming session.
        """
        s = self._to_session(session)
        summary = self.summarize_session(s)
        facts = self.extract_important_facts(s)
        notable = self.identify_notable_performance(s)
        insights = self.generate_structured_insights(s)

        sid = s.session_id or s.id or "unknown"
        sid_val = str(sid) if sid is not None else "unknown"

        return AIMemoryRecord(
            session_id=sid_val,
            memory_type="episodic",
            ai_summary=summary,
            ai_insights=insights,
            memory_text=summary,
            evidence_session_ids=[sid_val],
            ai_confidence=1.0,
            ai_model_version=self.model_version,
            created_at=datetime.now().isoformat(),
            facts=facts,
            notable_performance=notable
        )

    # -----------------------------------------------------------------
    # 6. GENERATE PATTERN MEMORY (Conditional upon historical data)
    # -----------------------------------------------------------------
    def generate_pattern_memory(
        self,
        current_session: Session,
        historical_sessions: List[Session]
    ) -> Optional[AIMemoryRecord]:
        """
        Pattern Memory represents patterns discovered across MULTIPLE sessions.
        RULE: Do NOT generate this yet unless enough historical sessions exist (>= 3).
        """
        all_sessions = historical_sessions + [current_session]
        if len(all_sessions) < HISTORICAL_SESSIONS_THRESHOLD:
            return None

        # Analyze duration vs performance across sessions
        short_sessions = []
        long_sessions = []
        for sess in all_sessions:
            if sess.duration is not None and sess.kd_ratio is not None:
                dur_mins = None
                if isinstance(sess.duration, (int, float)):
                    dur_mins = sess.duration
                elif isinstance(sess.duration, str) and sess.duration.isdigit():
                    dur_mins = int(sess.duration)

                if dur_mins is not None:
                    if dur_mins < 90:
                        short_sessions.append(sess.kd_ratio)
                    else:
                        long_sessions.append(sess.kd_ratio)

        # Discovered pattern rule
        if short_sessions and len(short_sessions) >= 2:
            avg_short = sum(short_sessions) / len(short_sessions)
            avg_long = (sum(long_sessions) / len(long_sessions)) if long_sessions else 0.0

            if not long_sessions or avg_short > avg_long:
                pattern_desc = "The player tends to perform better during sessions shorter than 90 minutes."
                evidence_ids = [str(s.session_id or s.id) for s in all_sessions if s.session_id or s.id]
                return AIMemoryRecord(
                    session_id=current_session.session_id,
                    memory_type="pattern",
                    ai_summary=pattern_desc,
                    ai_insights=[f"Average K/D in sessions <90 mins: {avg_short:.2f}"],
                    memory_text=pattern_desc,
                    evidence_session_ids=evidence_ids,
                    ai_confidence=0.9,
                    ai_model_version=self.model_version,
                    created_at=datetime.now().isoformat()
                )

        return None

    # -----------------------------------------------------------------
    # 7. GENERATE PLAYER PROFILE MEMORY (Conditional upon historical data)
    # -----------------------------------------------------------------
    def generate_player_profile_memory(
        self,
        current_session: Session,
        historical_sessions: List[Session]
    ) -> Optional[AIMemoryRecord]:
        """
        Player Profile Memory represents long-term player information.
        RULE: Do NOT generate this yet unless enough evidence exists (>= 3).
        """
        all_sessions = historical_sessions + [current_session]
        if len(all_sessions) < HISTORICAL_SESSIONS_THRESHOLD:
            return None

        # Inspect configurations across sessions
        configs = []
        for sess in all_sessions:
            if sess.configuration:
                if isinstance(sess.configuration, dict):
                    weapon = sess.configuration.get("primary_weapon") or sess.configuration.get("weapon")
                    if weapon:
                        configs.append(str(weapon))
                elif isinstance(sess.configuration, str) and sess.configuration.strip():
                    configs.append(sess.configuration.strip())

        if not configs:
            return None

        from collections import Counter
        most_common_config, count = Counter(configs).most_common(1)[0]

        # Require at least 2 sessions using this configuration for evidence
        if count >= 2:
            profile_summary = f"Preferred configuration: {most_common_config}."
            evidence_ids = [str(s.session_id or s.id) for s in all_sessions if s.session_id or s.id]
            return AIMemoryRecord(
                session_id=current_session.session_id,
                memory_type="player_profile",
                ai_summary=profile_summary,
                ai_insights=[f"Preferred configuration identified across {count} sessions."],
                memory_text=profile_summary,
                evidence_session_ids=evidence_ids,
                ai_confidence=0.92,
                ai_model_version=self.model_version,
                created_at=datetime.now().isoformat()
            )

        return None

    # -----------------------------------------------------------------
    # 8. PROCESS AND STORE SESSION MEMORY
    # -----------------------------------------------------------------
    def process_and_store_session(
        self,
        session_target: Union[Session, Dict[str, Any], str, int]
    ) -> AIMemoryProcessingResult:
        """
        Primary entry point for Phase 5.
        Processes completed session, stores AI memory in database,
        and ensures raw session data remains available and separate.
        """
        # Resolve target session
        if isinstance(session_target, (str, int)):
            session_obj = self.storage.get_session_by_id(session_target)
            if not session_obj:
                raise ValueError(f"Session with ID '{session_target}' not found in storage.")
        else:
            session_obj = self._to_session(session_target)

        # Retrieve prior sessions for historical pattern analysis
        all_prior = self.storage.get_recent_sessions(limit=50)
        curr_sid = str(session_obj.session_id or session_obj.id or "")
        history = [s for s in all_prior if str(s.session_id or s.id) != curr_sid]

        # 1. Generate Episodic Memory
        episodic_mem = self.generate_episodic_memory(session_obj)

        # 2. Conditionally Generate Pattern Memory (only when sufficient history exists)
        pattern_mem = self.generate_pattern_memory(session_obj, history)

        # 3. Conditionally Generate Player Profile Memory (only when sufficient evidence exists)
        profile_mem = self.generate_player_profile_memory(session_obj, history)

        # 4. Store Generated Memory in SQLite database
        self._persist_ai_memory_record(episodic_mem)
        if pattern_mem:
            self._persist_ai_memory_record(pattern_mem)
        if profile_mem:
            self._persist_ai_memory_record(profile_mem)

        # 5. Link summary back to session without modifying raw telemetry
        if session_obj.session_id:
            try:
                self.storage.update_session(
                    session_id=session_obj.session_id,
                    update_data={
                        "ai_summary": episodic_mem.ai_summary,
                        "ai_insights": episodic_mem.ai_insights
                    }
                )
            except Exception:
                pass

        # 6. Dynamically update long-term Player Profile Memory (Phase 6)
        try:
            from app.player_profile import default_player_profile_manager
            default_player_profile_manager.update_profile_from_sessions()
        except Exception:
            pass

        # Raw session remains pristine
        raw_session_dict = session_obj.model_dump()

        return AIMemoryProcessingResult(
            raw_session=raw_session_dict,
            episodic_memory=episodic_mem,
            pattern_memory=pattern_mem,
            player_profile_memory=profile_mem,
            historical_sessions_count=len(history),
            message="Session processed into AI memory."
        )

    def _persist_ai_memory_record(self, record: AIMemoryRecord) -> int:
        """
        Saves the AI Memory Record directly to the database.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO memories (
                session_id, game, memory_type, title, summary,
                ai_summary, ai_insights_json, memory_text,
                evidence_session_ids_json, ai_confidence, ai_model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.session_id,
                record.facts.get("game", "Unknown"),
                record.memory_type,
                f"{record.memory_type.upper()}: {record.ai_summary[:40]}",
                record.ai_summary,
                record.ai_summary,
                json.dumps(record.ai_insights),
                record.memory_text,
                json.dumps(record.evidence_session_ids),
                record.ai_confidence,
                record.ai_model_version
            ))
            record_id = cursor.lastrowid
            conn.commit()
            record.id = record_id
            return record_id
        finally:
            conn.close()


# Default singleton instance
default_ai_memory_engine = AIMemoryEngine()
