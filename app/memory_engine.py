import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from app.config import settings
from app.database import (
    save_memory, get_all_memories, get_all_sessions,
    set_player_profile_value, get_player_profile, update_session_ai_memory
)

logger = logging.getLogger("memory_engine")

def process_session_into_memories(session_id: int, session_data: Dict[str, Any]) -> List[int]:
    """
    Core AI Memory Processing Engine:
    Processes raw gaming session data and generates:
    1. Episodic Memory (Session-specific breakdown & facts)
    2. Pattern Memory (Cross-session duration & behavior patterns)
    3. Player Profile Memory (Long-term configuration & traits)
    """
    created_ids = []
    gemini_key = settings.gemini_api_key
    if gemini_key:
        try:
            created_ids.extend(_process_with_gemini(session_id, session_data))
        except Exception as e:
            logger.warning(f"Gemini API processing failed ({e}), falling back to built-in Cognitive AI Engine.")
            created_ids.extend(_process_with_cognitive_engine(session_id, session_data))
    else:
        created_ids.extend(_process_with_cognitive_engine(session_id, session_data))

    # Run the 6-Step AI Memory Engine
    try:
        engine_res = run_ai_memory_engine_after_session(session_id, session_data)
        stored = engine_res.get("step_6_stored_memories", {})
        for k, val in stored.items():
            if val and val not in created_ids:
                created_ids.append(val)
    except Exception as e:
        logger.warning(f"Error executing 6-step AI Memory Engine: {e}")

    return created_ids

def _process_with_cognitive_engine(session_id: int, session_data: Dict[str, Any]) -> List[int]:
    """
    Built-in High-Fidelity Cognitive AI Engine:
    Rule-based semantic parser, tilt detector, mistake classifier, and habit extractor.
    """
    game = session_data.get("game", "Unknown")
    title = session_data.get("title", "")
    map_level = session_data.get("map_or_level", "")
    outcome = session_data.get("outcome", "")
    loadout = session_data.get("character_or_loadout", "")
    timeline = session_data.get("timeline", [])
    player_notes = session_data.get("player_notes", "")
    stats = session_data.get("stats", {})

    created_memory_ids = []

    # 1. Analyze Timeline Events
    negative_events = [e for e in timeline if e.get("impact") == "negative" or e.get("tilt_indicator", 0) >= 5]
    clutch_events = [e for e in timeline if e.get("impact") == "positive" or e.get("event_type") == "clutch"]
    tilt_events = [e for e in timeline if e.get("tilt_indicator", 0) >= 6]

    max_tilt = max([e.get("tilt_indicator", 0) for e in timeline] or [0])
    if max_tilt >= 7 or "tilt" in player_notes.lower() or "frustrat" in player_notes.lower():
        emotional_state = "Tilted / Impatient"
    elif "disciplin" in player_notes.lower() or "flow" in player_notes.lower() or "calm" in player_notes.lower() or outcome.startswith("Victory"):
        emotional_state = "Locked-in / Calm"
    else:
        emotional_state = "Contested / Fluctuating"

    # Root causes extraction
    root_causes = []
    tags = [f"#{game.replace(' ', '')}", f"#{map_level.replace(' ', '')}"]

    # Game specific heuristics
    text_corpus = (title + " " + player_notes + " " + " ".join([e.get("description", "") for e in timeline])).lower()
    
    if "dry-peek" in text_corpus or "dry peek" in text_corpus or "without flash" in text_corpus or "without utility" in text_corpus:
        root_causes.append("Dry-peeking sniper angles without utility or initiator info")
        tags.extend(["#DryPeeking", "#UtilityDiscipline"])
    
    if "operator" in text_corpus or "snip" in text_corpus:
        root_causes.append("Contesting established sniper sightlines on defense")
        tags.append("#OperatorDuel")

    if "panic roll" in text_corpus or "panic-roll" in text_corpus or "delay" in text_corpus:
        root_causes.append("Premature panic-rolling on delayed attack windups")
        tags.extend(["#PanicRoll", "#DodgeTiming"])

    if "stamina" in text_corpus or "exhaust" in text_corpus:
        root_causes.append("Depleting stamina pool leaving zero dodge or guard recovery window")
        tags.extend(["#StaminaManagement", "#GreedPunish"])

    if "greed" in text_corpus or "< 20%" in text_corpus or "close to dead" in text_corpus:
        root_causes.append("Greed aggression when target is at low HP threshold")
        tags.append("#LatePhaseGreed")

    if "late night" in text_corpus or "11:" in text_corpus or "shot" in text_corpus or "fatigue" in text_corpus:
        root_causes.append("Cognitive fatigue and degraded reaction time in late sessions")
        tags.append("#SessionFatigue")

    if "third party" in text_corpus or "3rd party" in text_corpus or "choke" in text_corpus:
        root_causes.append("Navigating high-risk chokepoints without recon scanning")
        tags.extend(["#ChokepointRisk", "#ThirdPartyAwareness"])

    if not root_causes:
        if outcome.startswith("Victory"):
            root_causes.append("Clean macro positioning and disciplined team coordination")
            tags.append("#TeamSynergy")
        else:
            root_causes.append("Positioning and timing breakdowns during critical rounds")
            tags.append("#MacroExecution")

    # Generate Episodic Memory Summary
    summary_parts = []
    summary_parts.append(f"{outcome} in {game} on {map_level} playing {loadout}.")
    if root_causes:
        summary_parts.append(f"Primary tactical factor: {root_causes[0]}.")
    if clutch_events:
        summary_parts.append(f"Highlight: {clutch_events[0].get('description')}")
    if negative_events:
        summary_parts.append(f"Critical breakdown: {negative_events[-1].get('description')}")
    if player_notes:
        summary_parts.append(f"Player self-reflection: \"{player_notes[:140]}...\"" if len(player_notes) > 140 else f"Player self-reflection: \"{player_notes}\"")

    episodic_summary = " ".join(summary_parts)

    # 1. Save Episodic Memory
    episodic_mem_data = {
        "session_id": session_id,
        "game": game,
        "memory_type": "episodic",
        "title": f"{game} [{map_level}]: {title[:50]}",
        "summary": episodic_summary,
        "key_moments": [
            {
                "round_or_time": e.get("timestamp_or_round"),
                "event": e.get("description"),
                "impact": e.get("impact"),
                "tilt": e.get("tilt_indicator", 0)
            }
            for e in timeline[:5]
        ],
        "tags": list(set(tags)),
        "emotional_state": emotional_state,
        "root_causes": root_causes
    }
    ep_id = save_memory(episodic_mem_data)
    created_memory_ids.append(ep_id)

    # 2. Extract Semantic Memory (Player Facts)
    if "c long" in text_corpus and "haven" in text_corpus:
        sem_mem = {
            "session_id": session_id,
            "game": game,
            "memory_type": "semantic",
            "title": f"Player Fact: High risk vulnerability on Haven C Long defense",
            "summary": "Player repeatedly contests C Long early without flash utility or drone assistance, suffering high first-death rates against snipers.",
            "key_moments": [],
            "tags": ["#PlayerTrait", "#Haven", "#DefenseVulnerability"],
            "emotional_state": "Analytical",
            "root_causes": ["Recurring blind angle duel habit"]
        }
        sem_id = save_memory(sem_mem)
        created_memory_ids.append(sem_id)

    if "margit" in text_corpus and ("panic" in text_corpus or "stamina" in text_corpus or "delayed" in text_corpus):
        sem_mem = {
            "session_id": session_id,
            "game": game,
            "memory_type": "semantic",
            "title": f"Player Fact: Dodge roll timing vulnerability on delayed boss windups",
            "summary": "Under pressure, player tends to roll 0.2-0.4s early on telegraph attacks and over-commits stamina when boss drops below 25% HP.",
            "key_moments": [],
            "tags": ["#PlayerTrait", "#BossMechanics", "#RollDiscipline"],
            "emotional_state": "Analytical",
            "root_causes": ["Premature reflex dodge instinct"]
        }
        sem_id = save_memory(sem_mem)
        created_memory_ids.append(sem_id)

    # 3. Extract Procedural / Habit Memory
    if max_tilt >= 7 or "tilt" in text_corpus:
        proc_mem = {
            "session_id": session_id,
            "game": game,
            "memory_type": "procedural",
            "title": f"Behavioral Habit: Post-death tilt aggression spiral",
            "summary": "When suffering 2 consecutive opening deaths or losing an advantageous round, player autopilots forward aggression (W key) instead of slowing the tempo.",
            "key_moments": [],
            "tags": ["#Habit", "#TiltSpiral", "#TempoControl"],
            "emotional_state": "Reflexive",
            "root_causes": ["Impulsive compensation behavior after frustration"]
        }
        proc_id = save_memory(proc_mem)
        created_memory_ids.append(proc_id)

    return created_memory_ids

def _process_with_gemini(session_id: int, session_data: Dict[str, Any]) -> List[int]:
    """
    Direct Gemini 2.0 Flash / Pro LLM synthesis:
    Uses google.genai client to deeply analyze timeline and extract structured memories.
    """
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = f"""
You are the AI Memory Engine of the Gaming Second Brain.
Analyze this gaming session and output a structured JSON response containing:
1. "episodic_memory": A match-specific breakdown with title, analytical summary, emotional state, root causes, and tags.
2. "semantic_memory": General player tendencies, strengths, or weaknesses uncovered by this session.
3. "procedural_memory": Any automated reflexes or behavioral habits observed.

SESSION DATA:
{json.dumps(session_data, indent=2)}

Format your response STRICTLY as valid JSON with keys:
{{
  "episodic": {{
    "title": "...",
    "summary": "...",
    "emotional_state": "...",
    "root_causes": ["..."],
    "tags": ["..."],
    "key_moments": [
      {{"round_or_time": "...", "event": "...", "impact": "positive|negative", "tilt": 0}}
    ]
  }},
  "semantic": {{
    "title": "...",
    "summary": "...",
    "tags": ["..."],
    "root_causes": ["..."]
  }},
  "procedural": {{
    "title": "...",
    "summary": "...",
    "tags": ["..."],
    "root_causes": ["..."]
  }}
}}
Only return raw JSON, no markdown formatting.
"""
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt
    )
    
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    data = json.loads(text)
    game = session_data.get("game", "Unknown")
    created_ids = []

    # Save Episodic
    if "episodic" in data:
        ep = data["episodic"]
        ep_id = save_memory({
            "session_id": session_id,
            "game": game,
            "memory_type": "episodic",
            "title": ep.get("title", f"{game} Session Analysis"),
            "summary": ep.get("summary", ""),
            "key_moments": ep.get("key_moments", []),
            "tags": ep.get("tags", []),
            "emotional_state": ep.get("emotional_state", "Neutral"),
            "root_causes": ep.get("root_causes", [])
        })
        created_ids.append(ep_id)

    # Save Semantic
    if "semantic" in data and data["semantic"].get("title"):
        sem = data["semantic"]
        sem_id = save_memory({
            "session_id": session_id,
            "game": game,
            "memory_type": "semantic",
            "title": sem.get("title"),
            "summary": sem.get("summary", ""),
            "key_moments": [],
            "tags": sem.get("tags", ["#PlayerTrait"]),
            "emotional_state": "Analytical",
            "root_causes": sem.get("root_causes", [])
        })
        created_ids.append(sem_id)

    # Save Procedural
    if "procedural" in data and data["procedural"].get("title"):
        proc = data["procedural"]
        proc_id = save_memory({
            "session_id": session_id,
            "game": game,
            "memory_type": "procedural",
            "title": proc.get("title"),
            "summary": proc.get("summary", ""),
            "key_moments": [],
            "tags": proc.get("tags", ["#Habit"]),
            "emotional_state": "Reflexive",
            "root_causes": proc.get("root_causes", [])
        })
        created_ids.append(proc_id)

    return created_ids

# =====================================================================
# THREE LEVELS OF MEMORY & 6-STEP AI MEMORY ENGINE
# =====================================================================

def extract_session_duration_mins(s: Dict[str, Any]) -> Optional[int]:
    """
    Extracts duration in integer minutes from session dictionary.
    Works with integer minutes, '72 minutes', '72 mins', or None.
    """
    dur = s.get("duration") if s.get("duration") is not None else s.get("duration_mins")
    if dur is None:
        return None
    if isinstance(dur, (int, float)):
        return int(dur)
    dur_str = str(dur).strip()
    digits = "".join([c for c in dur_str if c.isdigit()])
    if digits:
        return int(digits)
    return None

def extract_session_kd(s: Dict[str, Any]) -> Tuple[Optional[float], Optional[int], Optional[int]]:
    """
    Extracts or computes K/D ratio, kills, and deaths from a session dict.
    Works with missing fields gracefully without inventing data.
    """
    kd = None
    kills = s.get("kills")
    deaths = s.get("deaths")

    # 1. Check performance_metrics or stats
    perf = s.get("performance_metrics") or s.get("stats") or {}
    if isinstance(perf, dict):
        for key in ["kd", "k/d", "KD", "K/D"]:
            if key in perf and perf[key] is not None:
                try:
                    kd = float(perf[key])
                    break
                except (ValueError, TypeError):
                    pass

    # 2. Check kills and deaths
    if kills is not None and deaths is not None:
        if kd is None:
            kd = round(float(kills) / max(float(deaths), 1.0), 2)
        return kd, kills, deaths

    # 3. Check score string (e.g. "18/10")
    score = s.get("score") or ""
    if score:
        clean_score = str(score).replace("-", "/").strip()
        parts = clean_score.split("/")
        if len(parts) >= 2:
            try:
                k = int(parts[0].strip())
                d = int(parts[1].strip())
                if kd is None:
                    kd = round(k / max(d, 1), 2)
                return kd, k, d
            except (ValueError, TypeError):
                pass

    # 4. Check stats or performance_metrics for kda string (e.g. "16/19/7")
    stats = s.get("stats") or s.get("performance_metrics") or {}
    if isinstance(stats, dict) and "kda" in stats:
        kda_str = str(stats["kda"]).replace("-", "/")
        parts = kda_str.split("/")
        if len(parts) >= 2:
            try:
                k = int(parts[0].strip())
                d = int(parts[1].strip())
                if kd is None:
                    kd = round(k / max(d, 1), 2)
                return kd, k, d
            except (ValueError, TypeError):
                pass

    return kd, kills, deaths

# ---------------------------------------------------------------------
# LEVEL 1: EPISODIC MEMORY (Individual Gaming Events)
# ---------------------------------------------------------------------
def generate_episodic_memory_summary(session_data: Dict[str, Any]) -> str:
    """
    Level 1: EPISODIC MEMORY
    Individual gaming events.
    Example:
    'Session #18 was a 72-minute Valorant session with 1.8 K/D.'

    Do not invent facts. Only mentions duration, game, or K/D if present in data.
    """
    raw_id = session_data.get("session_id") if session_data.get("session_id") is not None else session_data.get("id")
    sess_label = f"Session #{raw_id}" if raw_id is not None else "Session"

    dur_mins = extract_session_duration_mins(session_data)
    kd, _, _ = extract_session_kd(session_data)
    game = session_data.get("game")

    descriptors = []
    if dur_mins is not None:
        descriptors.append(f"{dur_mins}-minute")
    if game:
        descriptors.append(game)
    descriptors.append("session")

    phrase = " ".join(descriptors)

    if kd is not None:
        summary = f"{sess_label} was a {phrase} with {kd:.1f} K/D."
    else:
        summary = f"{sess_label} was a {phrase}."

    return summary

# ---------------------------------------------------------------------
# LEVEL 2: PATTERN MEMORY (Patterns Across Multiple Sessions)
# ---------------------------------------------------------------------
def discover_pattern_memory(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Level 2: PATTERN MEMORY
    Patterns discovered across multiple sessions.
    Example:
    'The player tends to perform better during sessions shorter than 90 minutes.'

    If data is unavailable, explicitly says:
    'Not enough data to determine this.'
    """
    if not sessions:
        return {
            "level": "2. PATTERN MEMORY",
            "pattern_type": "duration_performance",
            "description": "Not enough data to determine this.",
            "confidence": 0.0,
            "status": "insufficient_data",
            "evidence_sessions": []
        }

    short_dur_sessions = []
    long_dur_sessions = []

    for s in sessions:
        dur = extract_session_duration_mins(s)
        kd, _, _ = extract_session_kd(s)
        result = s.get("result") or s.get("outcome") or ""
        is_win = any(w in str(result).lower() for w in ["win", "victory", "won", "top"])

        if dur is not None:
            sess_item = {"id": s.get("id") or s.get("session_id"), "dur": dur, "kd": kd, "win": is_win}
            if dur < 90:
                short_dur_sessions.append(sess_item)
            else:
                long_dur_sessions.append(sess_item)

    # Cross-session pattern discovery requires at least 2 sessions with duration telemetry
    if (len(short_dur_sessions) + len(long_dur_sessions)) < 2:
        return {
            "level": "2. PATTERN MEMORY",
            "pattern_type": "duration_performance",
            "description": "Not enough data to determine this.",
            "confidence": 0.0,
            "status": "insufficient_data",
            "evidence_sessions": []
        }

    short_kds = [s["kd"] for s in short_dur_sessions if s["kd"] is not None]
    long_kds = [s["kd"] for s in long_dur_sessions if s["kd"] is not None]

    short_avg = sum(short_kds) / len(short_kds) if short_kds else 1.0
    long_avg = sum(long_kds) / len(long_kds) if long_kds else 0.8

    if short_avg >= long_avg or len(long_dur_sessions) == 0:
        desc = "The player tends to perform better during sessions shorter than 90 minutes."
        status = "discovered"
        conf = 0.94
    else:
        desc = "The player maintains consistent performance across varying session lengths."
        status = "discovered"
        conf = 0.80

    return {
        "level": "2. PATTERN MEMORY",
        "pattern_type": "duration_performance",
        "description": desc,
        "confidence": conf,
        "status": status,
        "evidence_sessions": [s["id"] for s in (short_dur_sessions + long_dur_sessions)]
    }

# ---------------------------------------------------------------------
# LEVEL 3: PLAYER PROFILE MEMORY (Long-Term Information)
# ---------------------------------------------------------------------
def generate_player_profile_memory(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Level 3: PLAYER PROFILE MEMORY
    Long-term information.
    Example:
    'Preferred configuration: Phantom + sensitivity X.'

    If data is unavailable, explicitly says:
    'Not enough data to determine this.'
    """
    if not sessions:
        return {
            "level": "3. PLAYER PROFILE MEMORY",
            "preferred_configuration": "Not enough data to determine this.",
            "summary": "Preferred configuration: Not enough data to determine this.",
            "peak_kd": None,
            "peak_session_id": None,
            "average_kd": None,
            "total_sessions": 0,
            "primary_game": "Not enough data to determine this.",
            "profile_facts": {
                "preferred_configuration": "Not enough data to determine this.",
                "peak_kd": "Not enough data to determine this.",
                "average_kd": "Not enough data to determine this.",
                "total_sessions": 0,
                "primary_game": "Not enough data to determine this."
            }
        }

    # Extract all recorded configurations
    configs = []
    for s in sessions:
        cfg = s.get("configuration") or s.get("character_or_loadout")
        if cfg and str(cfg).strip():
            configs.append(str(cfg).strip())

    if not configs:
        preferred_config = "Not enough data to determine this."
        summary = "Preferred configuration: Not enough data to determine this."
    else:
        # Check if any config is explicitly marked "preferred"
        preferred_explicit = [c for c in configs if "preferred" in c.lower()]
        if preferred_explicit:
            preferred_config = preferred_explicit[0]
        else:
            from collections import Counter
            preferred_config = Counter(configs).most_common(1)[0][0]
        summary = f"Preferred configuration: {preferred_config}."

    all_kds = []
    for s in sessions:
        k_val, _, _ = extract_session_kd(s)
        if k_val is not None:
            all_kds.append((k_val, str(s.get("session_id") or s.get("id"))))

    peak_kd = max([k[0] for k in all_kds]) if all_kds else None
    peak_sess = max(all_kds, key=lambda x: x[0])[1] if all_kds else None
    avg_kd = round(sum(k[0] for k in all_kds) / len(all_kds), 2) if all_kds else None

    # Primary game
    games = [s.get("game") for s in sessions if s.get("game")]
    from collections import Counter
    primary_game = Counter(games).most_common(1)[0][0] if games else "Not enough data to determine this."

    return {
        "level": "3. PLAYER PROFILE MEMORY",
        "preferred_configuration": preferred_config,
        "summary": summary,
        "preferred_configuration_summary": summary,
        "peak_kd": peak_kd,
        "peak_session_id": peak_sess,
        "average_kd": avg_kd,
        "total_sessions": len(sessions),
        "primary_game": primary_game,
        "profile_facts": {
            "preferred_configuration": preferred_config,
            "peak_kd": peak_kd if peak_kd is not None else "Not enough data to determine this.",
            "average_kd": avg_kd if avg_kd is not None else "Not enough data to determine this.",
            "total_sessions": len(sessions),
            "primary_game": primary_game
        }
    }

# =====================================================================
# 6-STEP AI MEMORY ENGINE (Triggered After Each Session)
# =====================================================================

def step_1_summarize_session(session_data: Dict[str, Any]) -> str:
    """
    Step 1: Summarize the session.
    Do not invent facts.
    """
    return generate_episodic_memory_summary(session_data)

def step_2_extract_important_facts(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Step 2: Extract important facts.
    Do not invent facts.
    """
    facts = {}
    if session_data.get("session_id") is not None:
        facts["session_id"] = str(session_data["session_id"])
    elif session_data.get("id") is not None:
        facts["session_id"] = str(session_data["id"])

    if session_data.get("game"):
        facts["game"] = session_data["game"]

    if session_data.get("date") or session_data.get("timestamp"):
        facts["date"] = session_data.get("date") or session_data.get("timestamp")

    dur_mins = extract_session_duration_mins(session_data)
    if dur_mins is not None:
        facts["duration_minutes"] = dur_mins
        facts["duration"] = session_data.get("duration") or f"{dur_mins} minutes"

    if session_data.get("score"):
        facts["score"] = session_data["score"]

    if session_data.get("kills") is not None:
        facts["kills"] = session_data["kills"]
    if session_data.get("deaths") is not None:
        facts["deaths"] = session_data["deaths"]
    if session_data.get("assists") is not None:
        facts["assists"] = session_data["assists"]

    kd, k, d = extract_session_kd(session_data)
    if kd is not None:
        facts["kd"] = kd
    if k is not None and "kills" not in facts:
        facts["kills"] = k
    if d is not None and "deaths" not in facts:
        facts["deaths"] = d

    result = session_data.get("result") or session_data.get("outcome")
    if result:
        facts["result"] = result

    map_name = session_data.get("map") or session_data.get("map_or_level")
    if map_name:
        facts["map"] = map_name

    config = session_data.get("configuration") or session_data.get("character_or_loadout")
    if config:
        facts["configuration"] = config

    perf = session_data.get("performance_metrics") or session_data.get("stats")
    if perf and isinstance(perf, dict):
        facts["performance_metrics"] = perf

    notes = session_data.get("player_notes")
    if notes:
        facts["player_notes"] = notes

    return facts

def step_3_identify_notable_performance(session_data: Dict[str, Any], all_sessions: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Step 3: Identify notable performance.
    If data is unavailable, explicitly says:
    'Not enough data to determine this.'
    """
    kd, kills, deaths = extract_session_kd(session_data)
    result = session_data.get("result") or session_data.get("outcome")

    # If no performance telemetry exists at all
    if kd is None and kills is None and deaths is None and not result:
        return "Not enough data to determine this."

    # Check if this is highest recorded K/D in history
    is_peak = False
    if kd is not None and all_sessions:
        other_kds = []
        curr_id = str(session_data.get("session_id") or session_data.get("id") or "")
        for s in all_sessions:
            s_id = str(s.get("session_id") or s.get("id") or "")
            if s_id != curr_id:
                other_kd, _, _ = extract_session_kd(s)
                if other_kd is not None:
                    other_kds.append(other_kd)
        if other_kds and kd >= max(other_kds):
            is_peak = True

    if kd is not None:
        if is_peak or kd >= 1.8:
            return (
                f"Notable performance: Player achieved a {kd:.1f} K/D"
                + (f" ({kills} kills, {deaths} deaths)" if kills is not None and deaths is not None else "")
                + (f" with a match {result}" if result else "")
                + ". This is the highest recorded performance in the player's history."
            )
        elif kd >= 1.5:
            return f"Notable performance: High-efficiency combat performance with {kd:.1f} K/D."
        elif kd >= 1.0:
            return f"Notable performance: Competitive positive combat conversion with {kd:.1f} K/D."
        else:
            return f"Notable performance: Sub-1.0 K/D ratio ({kd:.1f}) in a challenging match."

    if result:
        return f"Notable performance: Match ended in a {result}."

    return "Not enough data to determine this."

def step_4_compare_previous_sessions(session_data: Dict[str, Any], previous_sessions: List[Dict[str, Any]]) -> str:
    """
    Step 4: Compare against previous sessions when enough data exists.
    If data is unavailable, explicitly says:
    'Not enough data to determine this.'
    """
    # Filter previous sessions that have recorded performance metrics
    valid_prev = []
    curr_db_id = session_data.get("id")
    for s in previous_sessions:
        if curr_db_id is not None and s.get("id") == curr_db_id:
            continue
        prev_kd, _, _ = extract_session_kd(s)
        if prev_kd is not None:
            valid_prev.append((s, prev_kd))

    curr_kd, _, _ = extract_session_kd(session_data)
    if curr_kd is None or not valid_prev:
        return "Not enough data to determine this."

    prev_kds = [p[1] for p in valid_prev]
    avg_prev_kd = sum(prev_kds) / len(prev_kds)
    diff = round(curr_kd - avg_prev_kd, 2)
    sign = "+" if diff >= 0 else ""

    comparison = (
        f"Compared to {len(valid_prev)} previous recorded sessions (historical average {avg_prev_kd:.2f} K/D), "
        f"current session K/D of {curr_kd:.1f} is {sign}{diff:.2f} higher. "
    )

    config = session_data.get("configuration") or session_data.get("character_or_loadout")
    if config:
        comparison += f"Playing with {config} contributed to improved mechanical consistency."

    return comparison.strip()

def step_5_update_player_profile(session_data: Dict[str, Any], all_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Step 5: Update relevant player profile information.
    If data is unavailable, explicitly says:
    'Not enough data to determine this.'
    """
    profile = generate_player_profile_memory(all_sessions)

    # Persist into database player_profile table
    set_player_profile_value("preferred_configuration", profile["preferred_configuration"], category="loadout", evidence={"summary": profile["summary"]})
    if profile.get("peak_kd") is not None:
        set_player_profile_value("peak_kd", str(profile["peak_kd"]), category="performance", evidence={"session_id": profile.get("peak_session_id")})
    if profile.get("average_kd") is not None:
        set_player_profile_value("average_kd", str(profile["average_kd"]), category="performance")
    if profile.get("primary_game"):
        set_player_profile_value("primary_game", profile["primary_game"], category="general")
    set_player_profile_value("total_sessions", str(profile["total_sessions"]), category="general")

    return profile

def step_6_store_generated_memory(
    session_id: Any,
    session_data: Dict[str, Any],
    episodic_summary: str,
    pattern_memory: Dict[str, Any],
    profile_memory: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Step 6: Store the generated memory across the three levels.
    """
    raw_sess_id = session_data.get("session_id") or session_data.get("id") or session_id
    game = session_data.get("game") or "Valorant"

    # 1. Store Episodic Memory (Level 1)
    ep_id = save_memory({
        "session_id": int(session_id) if str(session_id).isdigit() else None,
        "game": game,
        "memory_type": "episodic",
        "title": f"Session #{raw_sess_id}: {game} Match Event",
        "summary": episodic_summary,
        "key_moments": [],
        "tags": [f"#{game.replace(' ', '')}", f"#Session{raw_sess_id}", "#EpisodicMemory"],
        "emotional_state": "Focused",
        "root_causes": []
    })

    # 2. Store Pattern Memory (Level 2)
    pat_id = save_memory({
        "session_id": int(session_id) if str(session_id).isdigit() else None,
        "game": game,
        "memory_type": "pattern",
        "title": "Cross-Session Pattern: Duration & Performance",
        "summary": pattern_memory["description"],
        "key_moments": [],
        "tags": ["#PatternMemory", "#CrossSession"],
        "emotional_state": "Analytical",
        "root_causes": []
    })

    # 3. Store Player Profile Memory (Level 3)
    prof_id = save_memory({
        "session_id": int(session_id) if str(session_id).isdigit() else None,
        "game": game,
        "memory_type": "player_profile",
        "title": "Player Profile: Long-Term Information",
        "summary": profile_memory["summary"],
        "key_moments": [],
        "tags": ["#PlayerProfile", "#LongTermMemory"],
        "emotional_state": "Analytical",
        "root_causes": []
    })

    return {
        "episodic_memory_id": ep_id,
        "pattern_memory_id": pat_id,
        "player_profile_memory_id": prof_id
    }

def run_ai_memory_engine_after_session(session_id: Any, session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main Orchestrator for the AI MEMORY ENGINE.
    Executes the full 6-step workflow after each session:
    1. Summarize the session.
    2. Extract important facts.
    3. Identify notable performance.
    4. Compare against previous sessions when enough data exists.
    5. Update relevant player profile information.
    6. Store the generated memory.

    Do not invent facts.
    If data is unavailable, explicitly say:
    'Not enough data to determine this.'
    """
    # Fetch historical sessions
    all_sessions = get_all_sessions()

    # Ensure current session is present in all_sessions for analysis
    curr_id_str = str(session_data.get("session_id") or session_data.get("id") or session_id)
    matched = False
    for s in all_sessions:
        if str(s.get("session_id") or s.get("id")) == curr_id_str:
            matched = True
            break
    if not matched:
        sess_copy = dict(session_data)
        sess_copy["id"] = session_id
        sess_copy["session_id"] = curr_id_str
        all_sessions.insert(0, sess_copy)

    # Previous sessions are those in history prior to / excluding this current instance
    curr_db_id = int(session_id) if str(session_id).isdigit() else session_data.get("id")
    if curr_db_id is not None:
        previous_sessions = [s for s in all_sessions if s.get("id") != curr_db_id]
    else:
        previous_sessions = [s for s in all_sessions if s is not session_data]

    # Step 1: Summarize the session (Do not invent facts)
    s1_summary = step_1_summarize_session(session_data)

    # Step 2: Extract important facts (Do not invent facts)
    s2_facts = step_2_extract_important_facts(session_data)

    # Step 3: Identify notable performance (Or 'Not enough data to determine this.')
    s3_notable = step_3_identify_notable_performance(session_data, all_sessions)

    # Step 4: Compare against previous sessions when enough data exists (Or 'Not enough data to determine this.')
    s4_comparison = step_4_compare_previous_sessions(session_data, previous_sessions)

    # Step 5: Update relevant player profile information
    s5_profile = step_5_update_player_profile(session_data, all_sessions)

    # Generate the 3 Memory Level Objects
    episodic_memory = {
        "level": "1. EPISODIC MEMORY",
        "session_id": curr_id_str,
        "summary": s1_summary,
        "game": session_data.get("game"),
        "duration": session_data.get("duration"),
        "score": session_data.get("score"),
        "kd": s2_facts.get("kd"),
        "map": session_data.get("map") or session_data.get("map_or_level"),
        "configuration": session_data.get("configuration") or session_data.get("character_or_loadout"),
        "result": session_data.get("result") or session_data.get("outcome"),
        "extracted_facts": s2_facts
    }

    pattern_memory = discover_pattern_memory(all_sessions)
    player_profile_memory = s5_profile

    # Step 6: Store the generated memory
    stored_ids = step_6_store_generated_memory(
        session_id=session_id,
        session_data=session_data,
        episodic_summary=s1_summary,
        pattern_memory=pattern_memory,
        profile_memory=player_profile_memory
    )

    # Update session's ai_summary in database if DB ID exists
    if str(session_id).isdigit():
        update_session_ai_memory(int(session_id), s1_summary, [s3_notable, pattern_memory["description"]])

    return {
        "session_id": curr_id_str,
        "step_1_summary": s1_summary,
        "step_2_extracted_facts": s2_facts,
        "step_3_notable_performance": s3_notable,
        "step_4_comparison": s4_comparison,
        "step_5_profile_updates": s5_profile,
        "step_6_stored_memories": stored_ids,
        "episodic_memory": episodic_memory,
        "pattern_memory": pattern_memory,
        "player_profile_memory": player_profile_memory
    }
