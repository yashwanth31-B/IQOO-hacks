import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from app.config import settings

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        game TEXT,
        date TEXT,
        duration TEXT,
        score TEXT,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER,
        result TEXT,
        map TEXT,
        configuration TEXT,
        game_mode TEXT,
        started_at TEXT,
        ended_at TEXT,
        kd_ratio REAL,
        performance_metrics_json TEXT DEFAULT '{}',
        player_notes TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        data_source TEXT,
        data_completeness REAL,
        ai_summary TEXT,
        ai_insights_json TEXT DEFAULT '[]',
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

    # Schema migration for existing tables: ensure all columns exist
    cursor.execute("PRAGMA table_info(sessions)")
    existing_cols = {col[1] for col in cursor.fetchall()}
    needed_cols = [
        ("session_id", "TEXT"),
        ("date", "TEXT"),
        ("duration", "TEXT"),
        ("score", "TEXT"),
        ("kills", "INTEGER"),
        ("deaths", "INTEGER"),
        ("assists", "INTEGER"),
        ("result", "TEXT"),
        ("map", "TEXT"),
        ("configuration", "TEXT"),
        ("game_mode", "TEXT"),
        ("started_at", "TEXT"),
        ("ended_at", "TEXT"),
        ("kd_ratio", "REAL"),
        ("tags_json", "TEXT DEFAULT '[]'"),
        ("data_source", "TEXT"),
        ("data_completeness", "REAL"),
        ("ai_summary", "TEXT"),
        ("ai_insights_json", "TEXT DEFAULT '[]'"),
    ]
    for col_name, col_type in needed_cols:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    try:
        cursor.execute("UPDATE sessions SET kd_ratio = ROUND(CAST(kills AS REAL) / MAX(deaths, 1), 2) WHERE kd_ratio IS NULL AND kills IS NOT NULL AND deaths IS NOT NULL")
    except Exception:
        pass

    # 2. Memories Table (Episodic, Semantic, Procedural, AI Engine)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        game TEXT NOT NULL,
        memory_type TEXT NOT NULL, -- 'episodic', 'pattern', 'player_profile'
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
    )
    """)

    # Migration for memories table
    cursor.execute("PRAGMA table_info(memories)")
    existing_mem_cols = {col[1] for col in cursor.fetchall()}
    needed_mem_cols = [
        ("ai_summary", "TEXT"),
        ("ai_insights_json", "TEXT DEFAULT '[]'"),
        ("memory_text", "TEXT"),
        ("evidence_session_ids_json", "TEXT DEFAULT '[]'"),
        ("ai_confidence", "REAL DEFAULT 1.0"),
        ("ai_model_version", "TEXT DEFAULT 'gaming-second-brain-ai-v1'"),
    ]
    for col_name, col_type in needed_mem_cols:
        if col_name not in existing_mem_cols:
            try:
                cursor.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    # 3. Patterns Table (Cross-Session Analysis)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL, -- 'weakness', 'tilt_trigger', 'strength', 'habit'
        game TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        occurrence_count INTEGER NOT NULL,
        affected_sessions_json TEXT NOT NULL DEFAULT '[]',
        actionable_recommendation TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. Recommendations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        game TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        actionable_steps_json TEXT NOT NULL DEFAULT '[]',
        priority TEXT NOT NULL DEFAULT 'Medium',
        trigger_context TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 5. Player Profile Table (Long-Term Information)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_key TEXT UNIQUE NOT NULL,
        profile_value TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        evidence_json TEXT DEFAULT '{}',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 6. Gaming Plans Table
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

    # 7. Plan Evaluations Table
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

    conn.commit()
    conn.close()

def save_session(session_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    game = session_data.get("game") or "Valorant"
    raw_session_id = session_data.get("session_id")
    session_id_str = str(raw_session_id) if raw_session_id is not None else None

    date_val = session_data.get("date") or session_data.get("timestamp") or ""

    raw_duration = session_data.get("duration")
    if raw_duration is not None:
        duration_str = str(raw_duration)
        if duration_str.isdigit():
            duration_mins = int(duration_str)
            duration_str = f"{duration_mins} minutes"
        else:
            digits = "".join([c for c in duration_str if c.isdigit()])
            duration_mins = int(digits) if digits else session_data.get("duration_mins", 30)
    else:
        duration_mins = session_data.get("duration_mins", 30)
        duration_str = f"{duration_mins} minutes" if duration_mins else ""

    kills = session_data.get("kills")
    deaths = session_data.get("deaths")
    assists = session_data.get("assists")
    score = session_data.get("score") or ""
    if not score and kills is not None and deaths is not None:
        score = f"{kills}/{deaths}"
    elif score and (kills is None or deaths is None):
        parts = score.replace("-", "/").split("/")
        if len(parts) >= 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
            kills = int(parts[0].strip())
            deaths = int(parts[1].strip())

    result = session_data.get("result") or session_data.get("outcome") or ""
    outcome = session_data.get("outcome") or result or ""

    map_val = session_data.get("map") or session_data.get("map_or_level") or ""
    map_or_level = session_data.get("map_or_level") or map_val or ""

    config_val = session_data.get("configuration") or session_data.get("character_or_loadout") or ""
    character_or_loadout = session_data.get("character_or_loadout") or config_val or ""

    perf_metrics = session_data.get("performance_metrics") or session_data.get("stats") or {}
    stats = session_data.get("stats") or perf_metrics or {}

    player_notes = session_data.get("player_notes") or ""
    ai_summary = session_data.get("ai_summary") or ""
    ai_insights = session_data.get("ai_insights") or []

    title = session_data.get("title") or f"{game} [{map_val or 'Session'}]"
    timeline = session_data.get("timeline") or []

    cursor.execute("""
    INSERT INTO sessions (
        session_id, game, date, duration, score, kills, deaths, assists,
        result, map, configuration, performance_metrics_json, player_notes,
        ai_summary, ai_insights_json, title, map_or_level, character_or_loadout,
        outcome, duration_mins, timestamp, stats_json, timeline_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id_str,
        game,
        date_val,
        duration_str,
        score,
        kills,
        deaths,
        assists,
        result,
        map_val,
        config_val,
        json.dumps(perf_metrics),
        player_notes,
        ai_summary,
        json.dumps(ai_insights),
        title,
        map_or_level,
        character_or_loadout,
        outcome,
        duration_mins,
        date_val,
        json.dumps(stats),
        json.dumps(timeline)
    ))
    new_id = cursor.lastrowid
    
    if not session_id_str:
        cursor.execute("UPDATE sessions SET session_id = ? WHERE id = ?", (str(new_id), new_id))
    
    conn.commit()
    conn.close()
    return new_id

def save_memory(memory_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO memories (session_id, game, memory_type, title, summary, key_moments_json, tags_json, emotional_state, root_causes_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        memory_data.get("session_id"),
        memory_data.get("game"),
        memory_data.get("memory_type", "episodic"),
        memory_data.get("title"),
        memory_data.get("summary"),
        json.dumps(memory_data.get("key_moments", [])),
        json.dumps(memory_data.get("tags", [])),
        memory_data.get("emotional_state", "Focused"),
        json.dumps(memory_data.get("root_causes", []))
    ))
    mem_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return mem_id

def update_session_ai_memory(session_db_id: int, ai_summary: str, ai_insights: Any = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    insights_json = json.dumps(ai_insights) if ai_insights else "[]"
    cursor.execute("""
    UPDATE sessions
    SET ai_summary = ?, ai_insights_json = ?
    WHERE id = ?
    """, (ai_summary, insights_json, session_db_id))
    conn.commit()
    conn.close()

def _row_to_session_dict(r: sqlite3.Row) -> Dict[str, Any]:
    keys = r.keys()
    
    session_id = r["session_id"] if "session_id" in keys and r["session_id"] else str(r["id"])
    game = r["game"] if "game" in keys else ""
    date_val = r["date"] if "date" in keys and r["date"] else (r["timestamp"] if "timestamp" in keys else "")
    duration_val = r["duration"] if "duration" in keys and r["duration"] else (f"{r['duration_mins']} minutes" if "duration_mins" in keys and r["duration_mins"] else "")
    score_val = r["score"] if "score" in keys and r["score"] else ""
    kills_val = r["kills"] if "kills" in keys else None
    deaths_val = r["deaths"] if "deaths" in keys else None
    assists_val = r["assists"] if "assists" in keys else None
    result_val = r["result"] if "result" in keys and r["result"] else (r["outcome"] if "outcome" in keys else "")
    map_val = r["map"] if "map" in keys and r["map"] else (r["map_or_level"] if "map_or_level" in keys else "")
    config_val = r["configuration"] if "configuration" in keys and r["configuration"] else (r["character_or_loadout"] if "character_or_loadout" in keys else "")
    
    perf_metrics = json.loads(r["performance_metrics_json"]) if "performance_metrics_json" in keys and r["performance_metrics_json"] else json.loads(r["stats_json"] if "stats_json" in keys and r["stats_json"] else "{}")
    player_notes_val = r["player_notes"] if "player_notes" in keys and r["player_notes"] else ""
    ai_summary_val = r["ai_summary"] if "ai_summary" in keys and r["ai_summary"] else ""
    ai_insights_val = json.loads(r["ai_insights_json"]) if "ai_insights_json" in keys and r["ai_insights_json"] else []

    title_val = r["title"] if "title" in keys and r["title"] else f"{game} Session"
    map_or_level_val = r["map_or_level"] if "map_or_level" in keys and r["map_or_level"] else map_val
    char_loadout_val = r["character_or_loadout"] if "character_or_loadout" in keys and r["character_or_loadout"] else config_val
    outcome_val = r["outcome"] if "outcome" in keys and r["outcome"] else result_val
    duration_mins_val = r["duration_mins"] if "duration_mins" in keys and r["duration_mins"] else 30
    timestamp_val = r["timestamp"] if "timestamp" in keys and r["timestamp"] else date_val
    stats_val = json.loads(r["stats_json"]) if "stats_json" in keys and r["stats_json"] else perf_metrics
    timeline_val = json.loads(r["timeline_json"]) if "timeline_json" in keys and r["timeline_json"] else []
    created_at_val = str(r["created_at"]) if "created_at" in keys else ""
    game_mode_val = r["game_mode"] if "game_mode" in keys and r["game_mode"] else "Competitive"
    started_at_val = r["started_at"] if "started_at" in keys and r["started_at"] else date_val
    ended_at_val = r["ended_at"] if "ended_at" in keys and r["ended_at"] else None
    data_source_val = r["data_source"] if "data_source" in keys and r["data_source"] else "simulated"
    kd_ratio_val = r["kd_ratio"] if "kd_ratio" in keys and r["kd_ratio"] is not None else None
    if kd_ratio_val is None:
        if kills_val is not None and deaths_val is not None and deaths_val > 0:
            kd_ratio_val = round(kills_val / deaths_val, 2)
        elif kills_val is not None and deaths_val == 0:
            kd_ratio_val = float(kills_val)
        elif perf_metrics and "kd" in perf_metrics:
            try:
                kd_ratio_val = float(perf_metrics["kd"])
            except Exception:
                pass
        elif stats_val and "kda" in stats_val:
            try:
                parts = str(stats_val["kda"]).split("/")
                if len(parts) >= 2 and int(parts[1]) > 0:
                    kd_ratio_val = round(int(parts[0]) / int(parts[1]), 2)
            except Exception:
                pass

    return {
        "id": r["id"],
        "session_id": session_id,
        "game": game,
        "game_mode": game_mode_val,
        "date": date_val,
        "started_at": started_at_val,
        "ended_at": ended_at_val,
        "duration": duration_val,
        "score": score_val,
        "kills": kills_val,
        "deaths": deaths_val,
        "assists": assists_val,
        "kd_ratio": kd_ratio_val,
        "result": result_val,
        "map": map_val,
        "configuration": config_val,
        "performance_metrics": perf_metrics,
        "player_notes": player_notes_val,
        "data_source": data_source_val,
        "ai_summary": ai_summary_val,
        "ai_insights": ai_insights_val,
        # Legacy fields
        "title": title_val,
        "map_or_level": map_or_level_val,
        "character_or_loadout": char_loadout_val,
        "outcome": outcome_val,
        "duration_mins": duration_mins_val,
        "timestamp": timestamp_val,
        "stats": stats_val,
        "timeline": timeline_val,
        "created_at": created_at_val
    }

def get_all_sessions() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY id DESC")
    rows = cursor.fetchall()
    results = [_row_to_session_dict(r) for r in rows]
    conn.close()
    return results

def get_session_by_id(session_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ? OR session_id = ?", (session_id, str(session_id)))
    r = cursor.fetchone()
    if not r:
        conn.close()
        return None
    session_dict = _row_to_session_dict(r)
    conn.close()
    return session_dict

def get_all_memories(memory_type: Optional[str] = None, game: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM memories WHERE 1=1"
    params = []
    if memory_type:
        query += " AND memory_type = ?"
        params.append(memory_type)
    if game:
        query += " AND game = ?"
        params.append(game)
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "game": r["game"],
            "memory_type": r["memory_type"],
            "title": r["title"],
            "summary": r["summary"],
            "key_moments": json.loads(r["key_moments_json"] or "[]"),
            "tags": json.loads(r["tags_json"] or "[]"),
            "emotional_state": r["emotional_state"],
            "root_causes": json.loads(r["root_causes_json"] or "[]"),
            "created_at": str(r["created_at"])
        })
    conn.close()
    return results

def get_all_patterns(game: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM patterns WHERE 1=1"
    params = []
    if game:
        query += " AND game = ?"
        params.append(game)
    query += " ORDER BY confidence_score DESC, occurrence_count DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "category": r["category"],
            "game": r["game"],
            "title": r["title"],
            "description": r["description"],
            "confidence_score": r["confidence_score"],
            "occurrence_count": r["occurrence_count"],
            "affected_session_ids": json.loads(r["affected_sessions_json"] or "[]"),
            "actionable_recommendation": r["actionable_recommendation"]
        })
    conn.close()
    return results

def get_all_recommendations(game: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM recommendations WHERE 1=1"
    params = []
    if game:
        query += " AND game = ?"
        params.append(game)
    query += " ORDER BY id ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "category": r["category"],
            "game": r["game"],
            "title": r["title"],
            "description": r["description"],
            "actionable_steps": json.loads(r["actionable_steps_json"] or "[]"),
            "priority": r["priority"],
            "trigger_context": r["trigger_context"]
        })
    conn.close()
    return results

def set_player_profile_value(key: str, value: str, category: str = "general", evidence: Optional[Dict[str, Any]] = None):
    """
    Sets or updates a long-term player profile fact.
    Example: key='preferred_configuration', value='Phantom + preferred sensitivity'
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO player_profile (profile_key, profile_value, category, evidence_json, updated_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(profile_key) DO UPDATE SET
        profile_value = excluded.profile_value,
        category = excluded.category,
        evidence_json = excluded.evidence_json,
        updated_at = CURRENT_TIMESTAMP
    """, (key, value, category, json.dumps(evidence or {})))
    conn.commit()
    conn.close()

def get_player_profile() -> Dict[str, Any]:
    """
    Retrieves all stored long-term player profile facts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM player_profile ORDER BY id ASC")
    rows = cursor.fetchall()
    profile = {}
    for r in rows:
        evidence = json.loads(r["evidence_json"] or "{}")
        profile[r["profile_key"]] = {
            "value": r["profile_value"],
            "category": r["category"],
            "evidence": evidence,
            "updated_at": str(r["updated_at"])
        }
    conn.close()
    return profile

def get_memories_by_three_tiers() -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns memories organized into the three user-specified levels:
    1. Episodic Memory (individual gaming events)
    2. Pattern Memory (patterns discovered across multiple sessions)
    3. Player Profile Memory (long-term player information)
    """
    all_memories = get_all_memories()
    tiers = {
        "episodic": [],
        "pattern": [],
        "player_profile": []
    }
    for m in all_memories:
        m_type = m.get("memory_type", "").lower()
        if m_type == "episodic":
            tiers["episodic"].append(m)
        elif m_type in ("pattern", "procedural"):
            tiers["pattern"].append(m)
        elif m_type in ("player_profile", "semantic"):
            tiers["player_profile"].append(m)
        else:
            tiers["episodic"].append(m)
    return tiers

def clear_all_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recommendations")
    cursor.execute("DELETE FROM patterns")
    cursor.execute("DELETE FROM memories")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM player_profile")
    conn.commit()
    conn.close()

# Ensure all database tables exist on import
init_db()
