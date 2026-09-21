import sqlite3
import json
import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from app.config import settings
from app.models import Session


# =====================================================================
# PHASE 2: SESSION STORAGE EXCEPTIONS
# =====================================================================

class SessionStorageError(Exception):
    """Base exception for session storage operations."""
    pass


class SessionNotFoundError(SessionStorageError):
    """Raised when a requested session is not found in storage."""
    pass


# =====================================================================
# PHASE 2: SESSION STORAGE IMPLEMENTATION
# =====================================================================

class SessionStorage:
    """
    Persistent Storage Layer for Gaming Sessions.
    
    Provides simple, robust CRUD operations, recent-session queries,
    and session counting backed by a local SQLite database.
    
    Adheres strictly to Phase 2 requirements:
    - Uses the existing Phase 1 Session model.
    - Preserves incomplete sessions without inventing missing data.
    - Preserves raw player data (notes, configurations, custom telemetry).
    - Does not generate AI summaries or insights.
    - Provides basic error handling (SessionNotFoundError, SessionStorageError).
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.db_path
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Initializes table schema and runs non-destructive migrations for existing DBs."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            game TEXT,
            game_mode TEXT,
            map TEXT,
            configuration TEXT,
            started_at TEXT,
            ended_at TEXT,
            duration TEXT,
            score TEXT,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            kd_ratio REAL,
            performance_metrics_json TEXT DEFAULT '{}',
            result TEXT,
            player_notes TEXT,
            tags_json TEXT DEFAULT '[]',
            data_source TEXT,
            data_completeness REAL,
            match_id TEXT,
            ai_summary TEXT,
            ai_insights_json TEXT DEFAULT '[]',
            memory_text TEXT,
            memory_importance REAL,
            ai_confidence REAL,
            evidence_session_ids_json TEXT DEFAULT '[]',
            ai_model_version TEXT,
            processing_status TEXT DEFAULT 'pending',
            -- Backward compatibility columns
            date TEXT,
            title TEXT,
            map_or_level TEXT,
            character_or_loadout TEXT,
            outcome TEXT,
            duration_mins INTEGER,
            timestamp TEXT,
            stats_json TEXT DEFAULT '{}',
            timeline_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Ensure index on session_id for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")

        # Schema migration for any missing columns in pre-existing database files
        cursor.execute("PRAGMA table_info(sessions)")
        cols_info = cursor.fetchall()

        # If legacy table has NOT NULL constraints on optional columns, recreate table cleanly
        has_legacy_notnull = any(col[1] in ('title', 'outcome', 'character_or_loadout') and col[3] == 1 for col in cols_info)
        if has_legacy_notnull:
            cursor.execute("ALTER TABLE sessions RENAME TO sessions_legacy")
            cursor.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                game TEXT,
                game_mode TEXT,
                map TEXT,
                configuration TEXT,
                started_at TEXT,
                ended_at TEXT,
                duration TEXT,
                score TEXT,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kd_ratio REAL,
                performance_metrics_json TEXT DEFAULT '{}',
                result TEXT,
                player_notes TEXT,
                tags_json TEXT DEFAULT '[]',
                data_source TEXT,
                data_completeness REAL,
                match_id TEXT,
                ai_summary TEXT,
                ai_insights_json TEXT DEFAULT '[]',
                memory_text TEXT,
                memory_importance REAL,
                ai_confidence REAL,
                evidence_session_ids_json TEXT DEFAULT '[]',
                ai_model_version TEXT,
                processing_status TEXT DEFAULT 'pending',
                date TEXT,
                title TEXT,
                map_or_level TEXT,
                character_or_loadout TEXT,
                outcome TEXT,
                duration_mins INTEGER,
                timestamp TEXT,
                stats_json TEXT DEFAULT '{}',
                timeline_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("PRAGMA table_info(sessions_legacy)")
            legacy_cols = [c[1] for c in cursor.fetchall()]
            allowed_cols = [
                'id', 'session_id', 'game', 'game_mode', 'map', 'configuration', 'started_at', 'ended_at',
                'duration', 'score', 'kills', 'deaths', 'assists', 'kd_ratio', 'performance_metrics_json',
                'result', 'player_notes', 'tags_json', 'data_source', 'data_completeness', 'match_id',
                'ai_summary', 'ai_insights_json', 'memory_text', 'memory_importance', 'ai_confidence',
                'evidence_session_ids_json', 'ai_model_version', 'processing_status', 'date', 'title',
                'map_or_level', 'character_or_loadout', 'outcome', 'duration_mins', 'timestamp',
                'stats_json', 'timeline_json', 'created_at'
            ]
            common_cols = [c for c in legacy_cols if c in allowed_cols]
            cols_str = ", ".join(common_cols)
            cursor.execute(f"INSERT INTO sessions ({cols_str}) SELECT {cols_str} FROM sessions_legacy")
            cursor.execute("DROP TABLE sessions_legacy")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
            conn.commit()
            cursor.execute("PRAGMA table_info(sessions)")
            cols_info = cursor.fetchall()

        existing_cols = {col[1] for col in cols_info}
        needed_cols = [
            ("session_id", "TEXT"),
            ("game", "TEXT"),
            ("game_mode", "TEXT"),
            ("map", "TEXT"),
            ("configuration", "TEXT"),
            ("started_at", "TEXT"),
            ("ended_at", "TEXT"),
            ("duration", "TEXT"),
            ("score", "TEXT"),
            ("kills", "INTEGER"),
            ("deaths", "INTEGER"),
            ("assists", "INTEGER"),
            ("kd_ratio", "REAL"),
            ("performance_metrics_json", "TEXT DEFAULT '{}'"),
            ("result", "TEXT"),
            ("player_notes", "TEXT"),
            ("tags_json", "TEXT DEFAULT '[]'"),
            ("data_source", "TEXT"),
            ("data_completeness", "REAL"),
            ("match_id", "TEXT"),
            ("ai_summary", "TEXT"),
            ("ai_insights_json", "TEXT DEFAULT '[]'"),
            ("memory_text", "TEXT"),
            ("memory_importance", "REAL"),
            ("ai_confidence", "REAL"),
            ("evidence_session_ids_json", "TEXT DEFAULT '[]'"),
            ("ai_model_version", "TEXT"),
            ("processing_status", "TEXT DEFAULT 'pending'"),
        ]
        for col_name, col_type in needed_cols:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        conn.commit()
        conn.close()

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        """
        Converts a SQLite row into a Phase 1 Session model instance.
        Faithfully deserializes without inventing missing fields.
        """
        keys = row.keys()

        # Configuration: parse JSON dict/list if stored as JSON, else return raw string or None
        raw_config = row["configuration"] if "configuration" in keys else None
        config_val = None
        if raw_config is not None:
            if isinstance(raw_config, str) and (raw_config.startswith("{") or raw_config.startswith("[")):
                try:
                    config_val = json.loads(raw_config)
                except Exception:
                    config_val = raw_config
            else:
                config_val = raw_config

        # Performance metrics: parse JSON dict
        raw_metrics = row["performance_metrics_json"] if "performance_metrics_json" in keys else None
        if not raw_metrics and "stats_json" in keys:
            raw_metrics = row["stats_json"]
        perf_metrics: Dict[str, Any] = {}
        if raw_metrics:
            try:
                perf_metrics = json.loads(raw_metrics)
            except Exception:
                perf_metrics = {}

        # Tags: parse JSON list
        raw_tags = row["tags_json"] if "tags_json" in keys else None
        tags: List[str] = []
        if raw_tags:
            try:
                tags = json.loads(raw_tags)
            except Exception:
                tags = []

        # AI Insights: parse JSON list if populated, else None
        raw_insights = row["ai_insights_json"] if "ai_insights_json" in keys else None
        ai_insights = None
        if raw_insights is not None:
            try:
                parsed = json.loads(raw_insights)
                ai_insights = parsed if parsed else None
            except Exception:
                ai_insights = None

        session_id_val = row["session_id"] if "session_id" in keys and row["session_id"] is not None else (str(row["id"]) if "id" in keys else None)

        # Duration preservation: preserve number or string format
        raw_dur = row["duration"] if "duration" in keys else None
        dur_val = None
        if raw_dur is not None:
            if isinstance(raw_dur, (int, float)):
                dur_val = raw_dur
            elif isinstance(raw_dur, str):
                if raw_dur.isdigit():
                    dur_val = int(raw_dur)
                else:
                    try:
                        dur_val = float(raw_dur)
                    except ValueError:
                        dur_val = raw_dur

        # Evidence session IDs: parse JSON list if populated
        raw_evidence = row["evidence_session_ids_json"] if "evidence_session_ids_json" in keys else None
        evidence_ids = []
        if raw_evidence:
            try:
                evidence_ids = json.loads(raw_evidence)
            except Exception:
                evidence_ids = []

        # Timeline: parse JSON list if populated
        raw_timeline = row["timeline_json"] if "timeline_json" in keys else None
        timeline_events = []
        if raw_timeline:
            try:
                timeline_events = json.loads(raw_timeline)
            except Exception:
                timeline_events = []

        session_data = {
            "id": row["id"] if "id" in keys else None,
            "session_id": session_id_val,
            "match_id": row["match_id"] if "match_id" in keys else None,
            "game": row["game"] if "game" in keys else None,
            "game_mode": row["game_mode"] if "game_mode" in keys else None,
            "map": row["map"] if "map" in keys else None,
            "configuration": config_val,
            "started_at": row["started_at"] if "started_at" in keys and row["started_at"] is not None else (row["date"] if "date" in keys else None),
            "ended_at": row["ended_at"] if "ended_at" in keys else None,
            "duration": dur_val,
            "score": row["score"] if "score" in keys else None,
            "round_number": perf_metrics.get("round_number"),
            "kills": row["kills"] if "kills" in keys else None,
            "deaths": row["deaths"] if "deaths" in keys else None,
            "assists": row["assists"] if "assists" in keys else None,
            "kd_ratio": row["kd_ratio"] if "kd_ratio" in keys else None,
            "performance_metrics": perf_metrics,
            "result": row["result"] if "result" in keys and row["result"] is not None else (row["outcome"] if "outcome" in keys else None),
            "player_notes": row["player_notes"] if "player_notes" in keys else None,
            "tags": tags,
            "timeline": timeline_events,
            "data_source": row["data_source"] if "data_source" in keys else None,
            "data_completeness": row["data_completeness"] if "data_completeness" in keys else None,
            # AI Metadata
            "ai_summary": row["ai_summary"] if "ai_summary" in keys else None,
            "ai_insights": ai_insights,
            "memory_text": row["memory_text"] if "memory_text" in keys else None,
            "memory_importance": row["memory_importance"] if "memory_importance" in keys else None,
            "ai_confidence": row["ai_confidence"] if "ai_confidence" in keys else None,
            "evidence_session_ids": evidence_ids,
            "ai_model_version": row["ai_model_version"] if "ai_model_version" in keys else None,
            "processing_status": row["processing_status"] if "processing_status" in keys and row["processing_status"] is not None else "pending",
        }
        return Session(**session_data)

    def create_session(self, session: Union[Session, Dict[str, Any]]) -> Session:
        """
        Creates and persists a new Gaming Session.
        
        Accepts either a Session instance or a dictionary.
        Preserves incomplete sessions, raw player data, and does not invent missing data or AI info.
        """
        if isinstance(session, dict):
            try:
                session_obj = Session(**session)
            except Exception as e:
                raise SessionStorageError(f"Invalid session data: {e}") from e
        elif isinstance(session, Session):
            session_obj = session
        else:
            raise SessionStorageError(f"Expected Session model or dict, got {type(session).__name__}")

        # Serialization
        config_serialized = None
        if session_obj.configuration is not None:
            if isinstance(session_obj.configuration, (dict, list)):
                config_serialized = json.dumps(session_obj.configuration)
            else:
                config_serialized = str(session_obj.configuration)

        perf_metrics_serialized = json.dumps(session_obj.performance_metrics) if session_obj.performance_metrics is not None else "{}"
        tags_serialized = json.dumps(session_obj.tags) if session_obj.tags is not None else "[]"
        ai_insights_serialized = json.dumps(session_obj.ai_insights) if session_obj.ai_insights is not None else None
        evidence_serialized = json.dumps(session_obj.evidence_session_ids) if session_obj.evidence_session_ids is not None else "[]"
        timeline_serialized = "[]"
        if session_obj.timeline:
            try:
                timeline_serialized = json.dumps([
                    t.model_dump() if hasattr(t, "model_dump") else (t if isinstance(t, dict) else t.__dict__)
                    for t in session_obj.timeline
                ])
            except Exception:
                timeline_serialized = "[]"

        started_at_str = str(session_obj.started_at) if session_obj.started_at is not None else None
        ended_at_str = str(session_obj.ended_at) if session_obj.ended_at is not None else None
        duration_str = str(session_obj.duration) if session_obj.duration is not None else None
        session_id_str = str(session_obj.session_id) if session_obj.session_id is not None else None

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check for existing duplicate session_id
            if session_id_str is not None:
                cursor.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id_str,))
                if cursor.fetchone():
                    raise SessionStorageError(f"Session with session_id '{session_id_str}' already exists.")

            cursor.execute("""
            INSERT INTO sessions (
                session_id, game, game_mode, map, configuration,
                started_at, ended_at, duration, score, kills, deaths, assists,
                kd_ratio, performance_metrics_json, result, player_notes,
                tags_json, data_source, data_completeness,
                match_id, ai_summary, ai_insights_json, memory_text,
                memory_importance, ai_confidence, evidence_session_ids_json,
                ai_model_version, processing_status,
                title, map_or_level, character_or_loadout, outcome,
                duration_mins, timestamp, stats_json, timeline_json, date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id_str,
                session_obj.game,
                session_obj.game_mode,
                session_obj.map,
                config_serialized,
                started_at_str,
                ended_at_str,
                duration_str,
                session_obj.score,
                session_obj.kills,
                session_obj.deaths,
                session_obj.assists,
                session_obj.kd_ratio,
                perf_metrics_serialized,
                session_obj.result,
                session_obj.player_notes,
                tags_serialized,
                session_obj.data_source,
                session_obj.data_completeness,
                session_obj.match_id,
                session_obj.ai_summary,
                ai_insights_serialized,
                session_obj.memory_text,
                session_obj.memory_importance,
                session_obj.ai_confidence,
                evidence_serialized,
                session_obj.ai_model_version,
                session_obj.processing_status,
                session_obj.title,
                session_obj.map,
                str(session_obj.configuration) if session_obj.configuration is not None else None,
                session_obj.result,
                session_obj.duration_mins,
                str(session_obj.started_at) if session_obj.started_at is not None else None,
                perf_metrics_serialized or "{}",
                timeline_serialized,
                started_at_str
            ))
            db_id = cursor.lastrowid

            # If no custom session_id provided, assign auto-generated string id
            if session_id_str is None:
                session_id_str = str(db_id)
                cursor.execute("UPDATE sessions SET session_id = ? WHERE id = ?", (session_id_str, db_id))

            conn.commit()
        finally:
            conn.close()

        stored_session = self.get_session_by_id(session_id_str)
        if stored_session is None:
            raise SessionStorageError(f"Failed to retrieve session immediately after creation: {session_id_str}")
        return stored_session

    def get_session_by_id(self, session_id: Union[int, str]) -> Optional[Session]:
        """
        Retrieves a single session by its session_id (string) or primary key id (int/string).
        Returns None if the session does not exist.
        """
        if session_id is None:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # First attempt lookup by session_id
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (str(session_id),))
            row = cursor.fetchone()

            # If not found and input can be an integer, attempt lookup by primary key id
            if not row and str(session_id).isdigit():
                cursor.execute("SELECT * FROM sessions WHERE id = ?", (int(session_id),))
                row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_session(row)
        finally:
            conn.close()

    get_session = get_session_by_id

    def get_recent_sessions(self, limit: int = 10) -> List[Session]:
        """
        Retrieves the most recent sessions up to `limit`.
        Ordered by id DESC.
        """
        if limit <= 0:
            return []

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [self._row_to_session(r) for r in rows]
        finally:
            conn.close()

    def update_session(self, session_id: Union[int, str], update_data: Union[Session, Dict[str, Any]]) -> Session:
        """
        Updates an existing session by session_id or primary key id.
        Merges update fields into the existing record.
        Raises SessionNotFoundError if the session does not exist.
        """
        if session_id is None:
            raise SessionNotFoundError("session_id must not be None")

        existing = self.get_session_by_id(session_id)
        if existing is None:
            raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")

        # Extract dictionary from update_data
        if isinstance(update_data, Session):
            update_dict = update_data.model_dump(exclude_unset=True)
        elif isinstance(update_data, dict):
            update_dict = dict(update_data)
        else:
            raise SessionStorageError(f"Expected Session model or dict for update, got {type(update_data).__name__}")

        # Merge with existing values
        current_dict = existing.model_dump()
        for key, val in update_dict.items():
            if key in current_dict:
                current_dict[key] = val

        # Validate merged session through Pydantic model
        try:
            updated_session = Session(**current_dict)
        except Exception as e:
            raise SessionStorageError(f"Invalid session update: {e}") from e

        # Prepare serialized values
        config_serialized = None
        if updated_session.configuration is not None:
            if isinstance(updated_session.configuration, (dict, list)):
                config_serialized = json.dumps(updated_session.configuration)
            else:
                config_serialized = str(updated_session.configuration)

        perf_metrics_serialized = json.dumps(updated_session.performance_metrics) if updated_session.performance_metrics is not None else "{}"
        tags_serialized = json.dumps(updated_session.tags) if updated_session.tags is not None else "[]"
        ai_insights_serialized = json.dumps(updated_session.ai_insights) if updated_session.ai_insights is not None else None
        started_at_str = str(updated_session.started_at) if updated_session.started_at is not None else None
        ended_at_str = str(updated_session.ended_at) if updated_session.ended_at is not None else None
        duration_str = str(updated_session.duration) if updated_session.duration is not None else None
        evidence_serialized = json.dumps(updated_session.evidence_session_ids) if updated_session.evidence_session_ids is not None else "[]"

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            UPDATE sessions SET
                game = ?,
                game_mode = ?,
                map = ?,
                configuration = ?,
                started_at = ?,
                ended_at = ?,
                duration = ?,
                score = ?,
                kills = ?,
                deaths = ?,
                assists = ?,
                kd_ratio = ?,
                performance_metrics_json = ?,
                result = ?,
                player_notes = ?,
                tags_json = ?,
                data_source = ?,
                data_completeness = ?,
                match_id = ?,
                ai_summary = ?,
                ai_insights_json = ?,
                memory_text = ?,
                memory_importance = ?,
                ai_confidence = ?,
                evidence_session_ids_json = ?,
                ai_model_version = ?,
                processing_status = ?
            WHERE session_id = ? OR id = ?
            """, (
                updated_session.game,
                updated_session.game_mode,
                updated_session.map,
                config_serialized,
                started_at_str,
                ended_at_str,
                duration_str,
                updated_session.score,
                updated_session.kills,
                updated_session.deaths,
                updated_session.assists,
                updated_session.kd_ratio,
                perf_metrics_serialized,
                updated_session.result,
                updated_session.player_notes,
                tags_serialized,
                updated_session.data_source,
                updated_session.data_completeness,
                updated_session.match_id,
                updated_session.ai_summary,
                ai_insights_serialized,
                updated_session.memory_text,
                updated_session.memory_importance,
                updated_session.ai_confidence,
                evidence_serialized,
                updated_session.ai_model_version,
                updated_session.processing_status,
                str(session_id),
                int(session_id) if str(session_id).isdigit() else -1
            ))
            conn.commit()
        finally:
            conn.close()

        res = self.get_session_by_id(session_id)
        if res is None:
            raise SessionStorageError(f"Could not retrieve updated session: {session_id}")
        return res

    def delete_session(self, session_id: Union[int, str]) -> bool:
        """
        Deletes a session by session_id or primary key id.
        Raises SessionNotFoundError if the session does not exist.
        Returns True upon successful deletion.
        """
        if session_id is None:
            raise SessionNotFoundError("session_id must not be None")

        existing = self.get_session_by_id(session_id)
        if existing is None:
            raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM sessions WHERE session_id = ? OR id = ?",
                (str(session_id), int(session_id) if str(session_id).isdigit() else -1)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def count_sessions(self) -> int:
        """
        Returns the total number of sessions currently stored.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM sessions")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def clear_all_sessions(self) -> None:
        """Helper to clear all sessions (primarily for testing and resets)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM sessions")
            conn.commit()
        finally:
            conn.close()


# =====================================================================
# DEFAULT STORAGE INSTANCE AND HELPER FUNCTIONS
# =====================================================================

default_session_storage = SessionStorage()

def create_session(session: Union[Session, Dict[str, Any]]) -> Session:
    return default_session_storage.create_session(session)

def get_session_by_id(session_id: Union[int, str]) -> Optional[Session]:
    return default_session_storage.get_session_by_id(session_id)

def get_recent_sessions(limit: int = 10) -> List[Session]:
    return default_session_storage.get_recent_sessions(limit)

def update_session(session_id: Union[int, str], update_data: Union[Session, Dict[str, Any]]) -> Session:
    return default_session_storage.update_session(session_id, update_data)

def delete_session(session_id: Union[int, str]) -> bool:
    return default_session_storage.delete_session(session_id)

def count_sessions() -> int:
    return default_session_storage.count_sessions()
