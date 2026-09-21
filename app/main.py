import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Dict, Any

from app.config import settings
from app.database import (
    init_db, save_session, get_all_sessions, get_session_by_id,
    get_all_memories, get_all_patterns, get_all_recommendations,
    clear_all_data
)
from app.models import (
    Session, SessionCreate, SessionResponse, MemoryResponse,
    SearchQuery, SearchResponse, PatternItem,
    RecommendationItem, CopilotChatRequest, CopilotChatResponse,
    BriefingRequest, BriefingResponse, ApiKeyUpdate,
    DetectionResult, DetectionConfirmRequest,
    MapDetectionResult, MatchContext,
    GameState, GameStateSnapshot, StateTransitionRecord, StateUpdateRequest,
    AIMemoryRecord, AIMemoryProcessingResult,
    ProfileFact, PlayerProfile,
    StructuredQuery, NaturalLanguageSearchRequest, NaturalLanguageSearchResponse,
    CrossSessionAnalysisResult, CrossSessionAnalysisRequest,
    AIGamingPlan, CreateGamingPlanRequest,
    PlanEvaluation, AdaptivePlanCycleResponse, AdaptivePlanEvaluationRequest,
    PerformanceReport,
    GamingTask, TaskEngineResponse, CreateTasksRequest,
    GameEvent, CurrentPerformance, ProcessGameEventRequest,
    PerformancePattern, PerformancePatternResponse,
    CrossSessionIntelligenceResponse, CrossSessionIntelligenceRequest,
    FastPlanResponse, FastPlanRequest, FastPlanEvidenceDetail,
    DashboardCompleteSessionRequest,
    GameAdapterInfo, PipelineRunRequest, PipelineRunResponse,
    PlayerExperienceProfile, MapAreaIntelligence, WeaponIntelligence,
    WeaponRecommendation, MapLoadoutStrategy, RotationIntelligence,
    PreGameAdaptivePlan, PreGameIntelligenceResponse, PreGameIntelligenceRequest
)
from app.player_experience import default_player_experience_detector
from app.map_intelligence import default_map_intelligence_module
from app.weapon_intelligence import default_weapon_intelligence_module
from app.pregame_intelligence_engine import default_pregame_intelligence_engine
from app.game_adapter import default_adapter_registry, default_pipeline_orchestrator
from app.fast_plan_engine import default_fast_plan_engine, FastPlanEngine
from app.performance_engine import default_performance_engine, GamingPerformanceEngine
from app.task_engine import default_task_engine, GamingTaskEngine
from app.realtime_analyzer import default_realtime_analyzer, RealtimePerformanceAnalyzer
from app.pattern_engine import default_pattern_engine, PerformancePatternEngine
from app.cross_session_intelligence import default_cross_session_intelligence, CrossSessionIntelligenceEngine
from app.detection import (
    default_detector, KNOWN_GAMES_AND_MAPS, DetectionError, DetectionConnectionError
)
from app.game_state import (
    default_game_state_detector,
    GameStateTransitionError,
    GameStateError
)
from app.session_lifecycle import default_lifecycle_manager
from app.ai_memory_engine import default_ai_memory_engine
from app.player_profile import default_player_profile_manager
from app.natural_language_search import default_nl_search_engine
from app.cross_session_analyzer import default_cross_session_analyzer
from app.gaming_plan_engine import default_gaming_plan_engine
from app.adaptive_plan_engine import default_adaptive_plan_engine
from app.seed_data import SEED_SESSIONS
from app.memory_engine import process_session_into_memories
from app.pattern_analyzer import analyze_cross_session_patterns, get_analytics_summary
from app.semantic_search import search_memories
from app.copilot import generate_pre_match_briefing, handle_copilot_chat
from app.mvp_flow import (
    record_mvp_session, search_and_analyze_best_performance,
    compare_session_with_history, generate_personalized_recommendation,
    handle_mvp_natural_language_query
)

def load_initial_seed_data_if_empty():
    sessions = get_all_sessions()
    if not sessions:
        print("[Second Brain] Populating initial seed gaming sessions and memory layer...")
        for s_data in SEED_SESSIONS:
            s_id = save_session(s_data)
            process_session_into_memories(s_id, s_data)
        analyze_cross_session_patterns()
        print(f"[Second Brain] Loaded {len(SEED_SESSIONS)} sessions, memories, and mined patterns successfully!")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_initial_seed_data_if_empty()
    yield

app = FastAPI(
    title="Gaming Second Brain",
    description="Intelligence & Memory Layer of an AI Gaming Copilot",
    version="1.0.0",
    lifespan=lifespan
)

# Static files setup
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Gaming Second Brain API is running. UI assets loading."})

# 1. System Status & Engine Switching
@app.get("/api/status")
async def get_system_status():
    has_gemini = bool(settings.gemini_api_key)
    active_engine = f"Google Gemini ({settings.gemini_model})" if has_gemini else "Cognitive AI Engine (Local Heuristic NLP)"
    analytics = get_analytics_summary()
    return {
        "status": "online",
        "app_name": settings.app_name,
        "version": settings.version,
        "active_engine": active_engine,
        "has_gemini_key": has_gemini,
        "analytics": analytics
    }

@app.post("/api/settings/api-key")
async def update_api_key(payload: ApiKeyUpdate):
    settings.gemini_api_key = payload.api_key.strip()
    return {
        "success": True,
        "has_gemini_key": bool(settings.gemini_api_key),
        "active_engine": f"Google Gemini ({settings.gemini_model})" if settings.gemini_api_key else "Cognitive AI Engine (Local Heuristic NLP)"
    }

# 2. Session Data (PLAY -> UNDERSTAND)
@app.get("/api/sessions", response_model=List[SessionResponse])
async def list_sessions():
    return get_all_sessions()

@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int):
    s = get_session_by_id(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s

@app.post("/api/sessions", response_model=Dict[str, Any])
async def create_session(payload: Session):
    session_data = payload.model_dump()
    if not session_data.get("timestamp") and not session_data.get("date"):
        from datetime import datetime
        now_iso = datetime.now().isoformat()
        session_data["timestamp"] = now_iso
        session_data["date"] = now_iso

    res = record_mvp_session(session_data)
    analyze_cross_session_patterns()

    return {
        "success": True,
        "session_id": res["session_id"],
        "id": res["db_id"],
        "created_memory_ids": [res["memory_id"]],
        "ai_summary": res["ai_summary"],
        "ai_insights": res["ai_insights"],
        "session": res["session"],
        "message": f"Session #{res['session_id']} stored. Memory node #{res['memory_id']} synthesized."
    }

# =====================================================================
# PHASE 3: GAME AND MAP DETECTION ENDPOINTS
# =====================================================================

@app.get("/api/detection/known-games")
async def get_known_games_and_maps():
    """Returns supported game titles, modes, and maps."""
    return {"games": KNOWN_GAMES_AND_MAPS}

@app.post("/api/detection/detect", response_model=DetectionResult)
async def detect_game_and_map(payload: Dict[str, Any]):
    """
    Triggers simulated or manual detection of game, game mode, and map.
    Returns DetectionResult with confidence and detection source.
    """
    source = payload.get("detection_source") or payload.get("source") or "simulated"
    game_hint = payload.get("game")
    map_hint = payload.get("map")
    mode_hint = payload.get("game_mode")
    scenario = payload.get("scenario")
    confidence = payload.get("confidence")

    try:
        result = default_detector.detect(
            source=source,
            game_hint=game_hint,
            map_hint=map_hint,
            mode_hint=mode_hint,
            scenario=scenario,
            confidence_override=confidence
        )
        return result
    except DetectionConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DetectionError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/detection/confirm", response_model=SessionResponse)
async def confirm_detection_endpoint(payload: DetectionConfirmRequest):
    """
    Player confirms detected (or manually corrected) game and map.
    Only confirmed values are persisted into a Session.
    """
    try:
        detection = DetectionResult(
            game=payload.game,
            game_mode=payload.game_mode,
            map=payload.map,
            confidence=payload.confidence,
            detection_source=payload.detection_source,
            is_confident=True
        )
        additional_fields: Dict[str, Any] = {}
        if payload.session_id is not None:
            additional_fields["session_id"] = payload.session_id
        if payload.configuration is not None:
            additional_fields["configuration"] = payload.configuration
        if payload.started_at is not None:
            additional_fields["started_at"] = payload.started_at
        if payload.player_notes is not None:
            additional_fields["player_notes"] = payload.player_notes
        if payload.tags:
            additional_fields["tags"] = payload.tags

        created_session = default_detector.confirm_detection_and_create_session(
            detection=detection,
            additional_fields=additional_fields
        )
        return created_session
    except DetectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm and store session: {e}")

# =====================================================================
# PHASE 4: MAP AND MATCH DETECTION ENDPOINTS
# =====================================================================

@app.post("/api/detection/detect-map", response_model=MapDetectionResult)
async def detect_map_endpoint(payload: Dict[str, Any]):
    """
    Phase 4: Detects game-specific map.
    Returns MapDetectionResult with 'Map not detected.' if unavailable.
    """
    game = payload.get("game") or "BGMI"
    source = payload.get("detection_source") or payload.get("source") or "simulated"
    map_hint = payload.get("map")
    scenario = payload.get("scenario")
    confidence = payload.get("confidence")
    try:
        return default_detector.detect_map(
            game=game,
            source=source,
            map_hint=map_hint,
            scenario=scenario,
            confidence_override=confidence
        )
    except DetectionConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DetectionError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/detection/detect-match", response_model=MatchContext)
async def detect_match_endpoint(payload: Dict[str, Any]):
    """
    Phase 4: Detect or allow manual input for match details.
    """
    game = payload.get("game")
    map_name = payload.get("map")
    game_mode = payload.get("game_mode")
    match_id = payload.get("match_id")
    round_number = payload.get("round_number")
    source = payload.get("detection_source") or payload.get("source") or "simulated"
    scenario = payload.get("scenario")
    confidence = payload.get("confidence")
    try:
        return default_detector.detect_match(
            game=game,
            map_name=map_name,
            game_mode=game_mode,
            match_id=match_id,
            round_number=round_number,
            source=source,
            scenario=scenario,
            confidence_override=confidence
        )
    except DetectionConnectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DetectionError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/detection/connect-match")
async def connect_match_endpoint(payload: Dict[str, Any]):
    """
    Phase 4: Connects confirmed match context to active session.
    """
    session_id = payload.get("session_id")
    match_ctx_data = payload.get("match_context") or payload
    try:
        match_context = MatchContext(**match_ctx_data) if isinstance(match_ctx_data, dict) else match_ctx_data
        if session_id:
            updated = default_detector.connect_confirmed_data_to_session(session_id, match_context)
        else:
            updated = default_lifecycle_manager.connect_match_context(match_context)
        return updated
    except DetectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# =====================================================================
# PHASE 5: GAME STATE DETECTION ENDPOINTS
# =====================================================================

@app.get("/api/game-state", response_model=GameStateSnapshot)
async def get_game_state_endpoint():
    """Returns current active game state snapshot."""
    return default_game_state_detector.get_current_state()

@app.post("/api/game-state/update", response_model=GameStateSnapshot)
async def update_game_state_endpoint(payload: StateUpdateRequest):
    """
    Updates the active game state.
    Supports manual or simulated sources and validates state transitions.
    """
    try:
        return default_game_state_detector.transition_to(
            target_state=payload.state,
            game=payload.game,
            map_name=payload.map,
            match_time=payload.match_time,
            round_number=payload.round_number,
            source=payload.source,
            force=payload.force,
            metadata=payload.metadata
        )
    except GameStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GameStateError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/game-state/history", response_model=List[StateTransitionRecord])
async def get_game_state_history_endpoint():
    """Returns historical audit log of state transitions."""
    return default_game_state_detector.get_history()

@app.get("/api/game-state/supported-states")
async def get_supported_states_endpoint(game: Optional[str] = None):
    """Returns supported game states and transition profile for a game."""
    profile = default_game_state_detector.get_profile(game)
    return {
        "game": profile.name,
        "is_round_based": profile.is_round_based,
        "supported_states": [s.value for s in profile.supported_states]
    }

# =====================================================================
# PHASE 4: SESSION LIFECYCLE ENDPOINTS
# Flow: IDLE -> DETECTING -> READY -> PLAYING -> COMPLETED
# =====================================================================

@app.get("/api/lifecycle/status")
async def get_lifecycle_status():
    """Returns current real-time session state, timer, and active match telemetry."""
    return default_lifecycle_manager.get_status()

@app.post("/api/lifecycle/start-gaming")
async def start_gaming_flow(payload: Optional[Dict[str, Any]] = None):
    """
    Player clicks START GAMING.
    Transitions: IDLE -> DETECTING -> READY.
    Runs game & map detection.
    """
    body = payload or {}
    source = body.get("source") or body.get("detection_source") or "simulated"
    game_hint = body.get("game")
    map_hint = body.get("map")
    mode_hint = body.get("game_mode")
    scenario = body.get("scenario")
    confidence = body.get("confidence")

    try:
        detection = default_lifecycle_manager.start_gaming(
            source=source,
            game_hint=game_hint,
            map_hint=map_hint,
            mode_hint=mode_hint,
            scenario=scenario,
            confidence_override=confidence
        )
        return {
            "state": default_lifecycle_manager.state,
            "detection": detection.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/lifecycle/start-session", response_model=SessionResponse)
async def start_session_endpoint(payload: Optional[Dict[str, Any]] = None):
    """
    Player confirms and clicks START SESSION.
    Transitions: READY -> PLAYING.
    Creates Session in storage (session_id, game, map, started_at, data_source)
    and starts duration tracking.
    """
    body = payload or {}
    try:
        session = default_lifecycle_manager.confirm_and_start_session(
            game=body.get("game"),
            map_name=body.get("map"),
            game_mode=body.get("game_mode"),
            configuration=body.get("configuration"),
            session_id=body.get("session_id"),
            data_source=body.get("data_source"),
            started_at=body.get("started_at")
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {e}")

@app.post("/api/lifecycle/end-session", response_model=SessionResponse)
async def end_session_endpoint(payload: Optional[Dict[str, Any]] = None):
    """
    Player clicks END SESSION.
    Transitions: PLAYING -> COMPLETED.
    Stores ended_at and duration.
    Allows initial performance data to be recorded.
    Does NOT generate AI summaries yet.
    """
    body = payload or {}
    try:
        session = default_lifecycle_manager.end_session(
            performance_data=body.get("performance_data"),
            ended_at=body.get("ended_at"),
            duration=body.get("duration")
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end session: {e}")

@app.post("/api/lifecycle/performance", response_model=SessionResponse)
async def update_performance_endpoint(payload: Dict[str, Any]):
    """
    Allows performance data (score, kills, deaths, assists, result, player_notes)
    to be entered after session ends.
    """
    try:
        session = default_lifecycle_manager.enter_performance_data(
            session_id=payload.get("session_id"),
            score=payload.get("score"),
            kills=payload.get("kills"),
            deaths=payload.get("deaths"),
            assists=payload.get("assists"),
            result=payload.get("result"),
            player_notes=payload.get("player_notes"),
            performance_metrics=payload.get("performance_metrics"),
            tags=payload.get("tags")
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update performance: {e}")

@app.post("/api/lifecycle/reset")
async def reset_lifecycle_endpoint():
    """Resets lifecycle state back to IDLE."""
    default_lifecycle_manager.reset_to_idle()
    return {"status": "success", "state": "IDLE"}

# =====================================================================
# PHASE 5: AI MEMORY ENGINE ENDPOINT
# =====================================================================

@app.post("/api/ai/process-session", response_model=AIMemoryProcessingResult)
async def process_session_ai_memory_endpoint(payload: Dict[str, Any]):
    """
    Processes a completed gaming session through the Phase 5 AI Memory Engine.
    Summarizes, extracts facts, identifies notable performance, generates data-supported insights,
    and persists episodic memory (and conditional pattern/player profile memories).
    Keeps AI memory separate from raw session data.
    """
    session_target = payload.get("session_id") or payload.get("session") or payload
    try:
        result = default_ai_memory_engine.process_and_store_session(session_target)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process AI memory: {e}")

# =====================================================================
# PHASE 6: GAMING PERFORMANCE ENGINE ENDPOINTS
# =====================================================================

@app.post("/api/performance/calculate", response_model=PerformanceReport)
async def calculate_performance_endpoint(payload: Dict[str, Any]):
    """
    Calculates measurable performance metrics for session payload data.
    Never estimates missing metrics (returns 'Not enough data.').
    """
    report = default_performance_engine.calculate_session_performance(payload)
    return report

@app.get("/api/performance/session/{session_id}", response_model=PerformanceReport)
async def get_session_performance_endpoint(session_id: str):
    """
    Retrieves stored session by ID and calculates its normalized Performance Report.
    """
    try:
        report = default_performance_engine.calculate_session_by_id(session_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/performance/aggregate", response_model=PerformanceReport)
async def get_aggregate_performance_endpoint(game: Optional[str] = None):
    """
    Calculates aggregate measurable performance across all stored sessions.
    Optionally filtered by game.
    """
    sessions = default_performance_engine.storage.get_recent_sessions(limit=1000)
    return default_performance_engine.calculate_aggregate_performance(sessions, game=game)

# =====================================================================
# PHASE 7: AI GAMING TASK ENGINE ENDPOINTS
# =====================================================================

@app.post("/api/tasks/generate", response_model=TaskEngineResponse)
@app.post("/api/tasks/create", response_model=TaskEngineResponse)
async def generate_tasks_endpoint(payload: Optional[CreateTasksRequest] = None):
    """
    Generates specific, measurable gaming tasks from historical performance data.
    Strictly grounds tasks in factual evidence without claiming causation.
    """
    req = payload or CreateTasksRequest()
    return default_task_engine.create_tasks_from_history(
        game=req.game,
        category=req.category,
        limit=req.limit
    )

@app.get("/api/tasks", response_model=List[GamingTask])
async def list_tasks_endpoint(
    game: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Lists persisted gaming tasks with optional game, category, or status filtering.
    """
    return default_task_engine.list_tasks(game=game, category=category, status=status)

@app.get("/api/tasks/{task_id}", response_model=GamingTask)
async def get_task_endpoint(task_id: str):
    """
    Retrieves a single gaming task by its task_id.
    """
    task = default_task_engine.get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return task

@app.patch("/api/tasks/{task_id}/status", response_model=GamingTask)
async def update_task_status_endpoint(task_id: str, payload: Dict[str, str]):
    """
    Updates status of a gaming task (pending, in_progress, completed, skipped).
    """
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="Missing 'status' in payload.")
    try:
        task = default_task_engine.update_task_status(task_id, new_status)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# =====================================================================
# PHASE 9: REAL-TIME PERFORMANCE ANALYSIS ENDPOINTS
# =====================================================================

@app.post("/api/realtime/start", response_model=CurrentPerformance)
async def start_realtime_session_endpoint(payload: Optional[Dict[str, Any]] = None):
    """Initializes a real-time live performance tracking session."""
    body = payload or {}
    return default_realtime_analyzer.start_session(
        session_id=body.get("session_id"),
        game=body.get("game"),
        map_name=body.get("map"),
        initial_config=body.get("configuration")
    )

@app.post("/api/realtime/event", response_model=CurrentPerformance)
async def process_realtime_event_endpoint(payload: ProcessGameEventRequest):
    """
    Processes incoming live game event (kill, death, assist, objective, location_change,
    round_result, match_result, configuration_change).
    Updates live metrics without interfering with game controls.
    """
    return default_realtime_analyzer.process_event(payload.model_dump())

@app.get("/api/realtime/performance", response_model=CurrentPerformance)
async def get_realtime_performance_endpoint():
    """Returns current live performance metrics (K/D, kills, deaths, survival time, score)."""
    return default_realtime_analyzer.get_current_performance()

@app.post("/api/realtime/reset")
async def reset_realtime_endpoint():
    """Resets real-time analyzer state."""
    default_realtime_analyzer.reset()
    return {"status": "success", "message": "Real-time performance analyzer reset."}

# =====================================================================
# PHASE 10: PERFORMANCE PATTERN ENGINE ENDPOINTS
# =====================================================================

@app.post("/api/patterns/analyze", response_model=PerformancePatternResponse)
async def analyze_patterns_endpoint(payload: Optional[Dict[str, Any]] = None):
    """
    Phase 10 Performance Pattern Engine.
    Discovers repeated patterns across stored sessions.
    Strictly separates FACT, PATTERN, and INTERPRETATION.
    Never identifies a pattern from a single session.
    """
    body = payload or {}
    return default_pattern_engine.analyze_patterns(
        game=body.get("game"),
        pattern_type=body.get("pattern_type")
    )

@app.get("/api/patterns/performance", response_model=PerformancePatternResponse)
async def get_performance_patterns_endpoint(
    game: Optional[str] = None,
    pattern_type: Optional[str] = None
):
    """
    Lists discovered recurring performance patterns.
    """
    return default_pattern_engine.analyze_patterns(
        game=game,
        pattern_type=pattern_type
    )

# =====================================================================
# PHASE 11: CROSS-SESSION INTELLIGENCE ENDPOINTS
# =====================================================================

@app.post("/api/intelligence/ask", response_model=CrossSessionIntelligenceResponse)
async def ask_cross_session_intelligence_post(payload: CrossSessionIntelligenceRequest):
    """
    Phase 11 Cross-Session Intelligence.
    Answers analytical performance questions across stored match history:
    - When did I perform best?
    - What changed?
    - Am I improving?
    - Which map has my strongest recorded performance?
    - Which configuration has better recorded results?
    - How long are my strongest sessions?
    - What mistakes keep repeating?
    - What am I improving?
    Strictly separates ANSWER, EVIDENCE, INSIGHT, and RECOMMENDATION.
    Optimizes retrieval so the AI does not receive the player's entire history unnecessarily.
    """
    return default_cross_session_intelligence.ask(
        question=payload.question,
        game=payload.game
    )

@app.get("/api/intelligence/ask", response_model=CrossSessionIntelligenceResponse)
async def ask_cross_session_intelligence_get(
    question: str = "Am I improving?",
    game: Optional[str] = None
):
    """
    GET endpoint for Cross-Session Intelligence.
    """
    return default_cross_session_intelligence.ask(
        question=question,
        game=game
    )

# =====================================================================
# PHASE 6: PLAYER PROFILE MEMORY ENDPOINTS
# =====================================================================

@app.get("/api/profile", response_model=PlayerProfile)
async def get_player_profile_phase6():
    """
    Returns the Phase 6 lightweight long-term Player Profile built from
    multiple sessions and episodic memories.
    Adheres strictly to evidence tracking and insufficient data rules.
    """
    return default_player_profile_manager.get_profile()

@app.post("/api/profile/rebuild", response_model=PlayerProfile)
async def rebuild_player_profile_phase6():
    """
    Forces recalculation and updates the player profile memory from stored sessions.
    """
    return default_player_profile_manager.update_profile_from_sessions()

# =====================================================================
# PHASE 7: NATURAL LANGUAGE SEARCH ENDPOINTS
# =====================================================================

@app.post("/api/search/natural-language", response_model=NaturalLanguageSearchResponse)
@app.post("/api/nl-search", response_model=NaturalLanguageSearchResponse)
async def natural_language_search_endpoint(payload: NaturalLanguageSearchRequest):
    """
    Phase 7 Natural Language Search.
    Architecture: User Question -> Intent Detection -> Structured Query -> Session Retrieval -> Return Relevant Evidence
    """
    return default_nl_search_engine.search(
        query_text=payload.query,
        pre_filters=payload.filters
    )

# =====================================================================
# PHASE 8: CROSS-SESSION ANALYSIS ENDPOINTS
# =====================================================================

@app.post("/api/analysis/cross-session", response_model=CrossSessionAnalysisResult)
async def cross_session_analysis_endpoint(payload: CrossSessionAnalysisRequest):
    """
    Phase 8 Cross-Session Pattern Analysis.
    Analyzes multiple stored sessions to identify evidence-backed patterns.
    Strictly distinguishes FACT from PATTERN from AI INTERPRETATION.
    Prevents false causation.
    """
    return default_cross_session_analyzer.analyze_question(payload.question)

@app.get("/api/analysis/cross-session", response_model=CrossSessionAnalysisResult)
async def get_cross_session_analysis_endpoint(question: str = "Am I improving?"):
    """
    Query cross-session patterns for specific analytical questions.
    """
    return default_cross_session_analyzer.analyze_question(question)

# =====================================================================
# PHASE 9: AI GAMING PLAN ENDPOINTS
# Flow: Historical Sessions -> Memory -> Cross-Session Analysis -> AI Gaming Plan
# =====================================================================

@app.post("/api/plan", response_model=AIGamingPlan)
@app.post("/api/plans/create", response_model=AIGamingPlan)
async def create_gaming_plan_endpoint(payload: Optional[CreateGamingPlanRequest] = None):
    """
    Phase 9 AI Gaming Plan.
    Creates a personalized gaming session plan based strictly on stored sessions,
    player profile memory, and cross-session pattern analysis.
    """
    body = payload or CreateGamingPlanRequest()
    return default_gaming_plan_engine.create_plan(
        game=body.game,
        map_name=body.map,
        custom_goal=body.custom_goal
    )

@app.get("/api/plan/latest", response_model=AIGamingPlan)
@app.get("/api/plans/latest", response_model=AIGamingPlan)
async def get_latest_gaming_plan_endpoint():
    """
    Retrieves the most recent AI Gaming Plan or generates a new one.
    """
    plan = default_gaming_plan_engine.get_latest_plan()
    if plan:
        return plan
    return default_gaming_plan_engine.create_plan()

# =====================================================================
# PHASE 10: ADAPTIVE GAMING PLAN ENDPOINTS
# Flow: Previous Plan -> Player Plays -> New Session -> Compare Expected vs Actual
# -> Evaluate Plan -> Create Improved Next Plan
# =====================================================================

@app.post("/api/plan/evaluate", response_model=PlanEvaluation)
@app.post("/api/adaptive/evaluate", response_model=PlanEvaluation)
async def evaluate_plan_endpoint(payload: Optional[AdaptivePlanEvaluationRequest] = None):
    """
    Phase 12: Evaluates previous plan against resulting session telemetry.
    Strictly adheres to neutral language and causation guard.
    """
    body = payload or AdaptivePlanEvaluationRequest()
    session_target = body.session_data or body.session_id
    return default_adaptive_plan_engine.evaluate_plan(
        plan_target=body.plan_id,
        session_target=session_target
    )

@app.post("/api/plan/adaptive-cycle", response_model=AdaptivePlanCycleResponse)
@app.post("/api/adaptive/cycle", response_model=AdaptivePlanCycleResponse)
async def adaptive_plan_cycle_endpoint(payload: Optional[AdaptivePlanEvaluationRequest] = None):
    """
    Phase 12: Executes the end-to-end adaptive cycle:
    Previous Gaming Plan -> Player completes session -> New Session Data -> Compare with previous sessions
    -> Evaluate task results -> Update player memory -> Create next Gaming Plan.
    """
    body = payload or AdaptivePlanEvaluationRequest()
    session_target = body.session_data or body.session_id
    return default_adaptive_plan_engine.execute_adaptive_cycle(
        session_target=session_target,
        plan_target=body.plan_id
    )

@app.get("/api/plan/evaluation/latest", response_model=Optional[PlanEvaluation])
@app.get("/api/adaptive/evaluation/latest", response_model=Optional[PlanEvaluation])
async def get_latest_plan_evaluation_endpoint():
    """
    Retrieves the most recent plan evaluation.
    """
    return default_adaptive_plan_engine.get_latest_evaluation()

# =====================================================================
# PHASE 13: HACKATHON COCKPIT DASHBOARD ENDPOINTS
# =====================================================================

@app.post("/api/dashboard/fast-plan", response_model=FastPlanResponse)
async def get_dashboard_fast_plan(payload: FastPlanRequest):
    """
    Phase 13: 3-Second AI Pre-Game Plan.
    Returns structured Fast Plan JSON in < 3 seconds grounded in stored evidence.
    """
    return default_fast_plan_engine.generate_plan(
        game=payload.game,
        map_name=payload.map,
        game_mode=payload.game_mode
    )

@app.get("/api/dashboard/overview")
async def get_dashboard_overview(game: Optional[str] = None, map: Optional[str] = None):
    """
    Phase 13: Single aggregator endpoint powering the entire Cockpit HUD.
    Returns detection status, recent memories, performance trend data,
    AI insights from cross-session analysis, and active live metrics.
    """
    # 1. Detection state
    active_detection = getattr(default_detector, "last_result", None)
    curr_game = game or (active_detection.game if active_detection else "BGMI")
    curr_map = map or (active_detection.map if active_detection else "Erangel")
    curr_mode = active_detection.game_mode if active_detection else "Classic"
    is_confirmed = getattr(default_detector, "is_confirmed", True)

    # 2. Live Performance
    live_perf = default_realtime_analyzer.get_current_performance()

    # 3. Recent Sessions for Trend Chart (limit 10)
    sessions = get_all_sessions()
    trend_sessions = []
    for s in reversed(sessions[:10]):
        kd_val = s.get("kd_ratio")
        if kd_val is None and s.get("kills") is not None and s.get("deaths") is not None:
            kd_val = round(s["kills"] / max(s["deaths"], 1), 2)
        trend_sessions.append({
            "session_id": str(s.get("session_id") or s.get("id")),
            "date": s.get("date") or s.get("timestamp") or "",
            "game": s.get("game") or "Unknown",
            "map": s.get("map") or s.get("map_or_level") or "Unknown",
            "kd_ratio": kd_val,
            "kills": s.get("kills"),
            "deaths": s.get("deaths"),
            "score": s.get("score") or "",
            "duration": s.get("duration") or "",
            "result": s.get("result") or s.get("outcome") or ""
        })

    # 4. Recent Memories (limit 4 compact cards)
    all_memories = get_all_memories()
    compact_memories = []
    for m in all_memories[:4]:
        sid = m.get("session_id")
        matching_sess = next((s for s in sessions if str(s.get("session_id") or s.get("id")) == str(sid)), None)
        compact_memories.append({
            "memory_id": m.get("id"),
            "session_id": sid,
            "game": m.get("game") or "Unknown",
            "map": matching_sess.get("map") or matching_sess.get("map_or_level") or "Active Map" if matching_sess else "Active Map",
            "kd_ratio": matching_sess.get("kd_ratio") if matching_sess else None,
            "duration": matching_sess.get("duration") if matching_sess else "60 min",
            "result": matching_sess.get("result") or matching_sess.get("outcome") if matching_sess else "Completed",
            "title": m.get("title") or "Session Memory",
            "summary": m.get("summary") or m.get("ai_summary") or "",
            "created_at": m.get("created_at") or ""
        })

    # 5. AI Insights from Cross-Session Analysis
    patterns_data = default_pattern_engine.analyze_patterns(game=curr_game)
    insights = []
    for p in patterns_data.patterns[:3]:
        insights.append({
            "category": getattr(p, "pattern_type", "General"),
            "title": getattr(p, "pattern", "Performance Pattern"),
            "fact": getattr(p, "fact", ""),
            "description": getattr(p, "interpretation", ""),
            "confidence": getattr(p, "confidence", 1.0),
            "evidence_session_ids": [str(e) for e in getattr(p, "evidence_session_ids", [])],
            "recommendation": getattr(p, "interpretation", "")
        })

    # 6. Pre-Game Intelligence Engine Synthesis (< 3s target)
    pregame_res = default_pregame_intelligence_engine.run_pregame_intelligence(
        game=curr_game,
        map_name=curr_map,
        game_mode=curr_mode,
        detection_source="simulated" if not active_detection else getattr(active_detection, "detection_source", "simulated")
    )

    return {
        "status": "online",
        "current_game": curr_game,
        "current_map": curr_map,
        "current_mode": curr_mode,
        "is_confirmed": is_confirmed,
        "session_status": "ACTIVE" if default_realtime_analyzer.started_at else "READY",
        "ai_status": "AI READY",
        "live_performance": live_perf.model_dump() if live_perf else None,
        "recent_sessions": trend_sessions,
        "recent_memories": compact_memories,
        "ai_insights": insights,
        "pregame_intelligence": pregame_res.model_dump()
    }


# =====================================================================
# PRE-GAME INTELLIGENCE SYSTEM ENDPOINTS
# =====================================================================

@app.post("/api/pregame/intelligence", response_model=PreGameIntelligenceResponse)
async def get_pregame_intelligence_endpoint(payload: PreGameIntelligenceRequest):
    """
    Sub-3-second Pre-Game Intelligence Engine.
    Executes:
    GAME OPENED -> IDENTIFY PLAYER EXPERIENCE -> DETECT GAME -> DETECT MAP ->
    LOAD MAP INTELLIGENCE -> LOAD PLAYER HISTORY -> GENERATE 3-SECOND PRE-GAME PLAN ->
    SHOW STRATEGY + MAP AREAS + LOADOUT INFORMATION -> START SESSION
    """
    return default_pregame_intelligence_engine.run_pregame_intelligence(
        game=payload.game,
        map_name=payload.map,
        game_mode=payload.game_mode,
        detection_source=payload.detection_source or "simulated",
        player_name=payload.player_name or "Manoj",
        include_ai=payload.include_ai
    )

@app.get("/api/pregame/experience", response_model=PlayerExperienceProfile)
async def get_player_experience_endpoint(game: Optional[str] = "BGMI", player_name: Optional[str] = "Manoj"):
    """Determines whether the player is NEW, RETURNING, or EXPERIENCED based strictly on stored history."""
    return default_player_experience_detector.get_experience_profile(game=game, player_name=player_name)

@app.get("/api/pregame/map-intelligence")
async def get_map_intelligence_endpoint(game: str, map: Optional[str] = None):
    """Returns verified map areas, lower-activity areas, drop recommendations, and rotation plan."""
    areas = default_map_intelligence_module.get_map_areas(game, map)
    low_areas, low_msg = default_map_intelligence_module.get_low_enemy_areas(game, map)
    high_areas, high_msg = default_map_intelligence_module.get_high_activity_areas(game, map)
    exp = default_player_experience_detector.get_experience_profile(game=game)
    start_rec = default_map_intelligence_module.recommend_start_area(game, map, exp)
    rotation = default_map_intelligence_module.get_rotation_plan(game, map)
    return {
        "game": game,
        "map": map,
        "map_areas": [a.model_dump() for a in areas],
        "low_enemy_areas": [a.model_dump() for a in low_areas],
        "low_enemy_message": low_msg,
        "high_activity_areas": [a.model_dump() for a in high_areas],
        "high_activity_message": high_msg,
        "recommended_start": start_rec,
        "rotation_plan": rotation.model_dump() if rotation else None
    }

@app.get("/api/pregame/weapons")
async def get_weapon_intelligence_endpoint(game: str, map: Optional[str] = None):
    """Returns verified weapons and personalized Best-for-this-Player recommendation."""
    weapons = default_weapon_intelligence_module.get_weapons_for_game(game)
    rec = default_weapon_intelligence_module.calculate_best_loadout(game, map)
    return {
        "game": game,
        "weapons": [w.model_dump() for w in weapons],
        "recommendation": rec.model_dump()
    }

@app.post("/api/dashboard/session/complete")
async def complete_dashboard_session(payload: DashboardCompleteSessionRequest):
    """
    Phase 13: End Session & Memory Update Flow.
    Stores session, updates player memory, executes cross-session pattern mining,
    and returns concise post-session response:
    SESSION COMPLETE
    Performance recorded.
    MEMORY UPDATED
    Your session has been added to Gaming Second Brain.
    """
    import uuid
    from datetime import datetime
    sid = payload.session_id or f"session_{uuid.uuid4().hex[:6]}"
    now_iso = datetime.now().isoformat()
    kd_val = round(payload.kills / max(payload.deaths, 1), 2)

    session_data = {
        "session_id": sid,
        "game": payload.game,
        "map": payload.map,
        "map_or_level": payload.map,
        "kills": payload.kills,
        "deaths": payload.deaths,
        "assists": payload.assists,
        "kd_ratio": kd_val,
        "score": payload.score or f"{payload.kills}/{payload.deaths}",
        "duration": f"{payload.duration_mins} minutes",
        "duration_mins": payload.duration_mins,
        "result": payload.result or "Win",
        "outcome": payload.result or "Win",
        "timestamp": now_iso,
        "date": now_iso,
        "player_notes": payload.player_notes or "Dashboard completed live session."
    }

    # 1. Save session & record memory
    res = record_mvp_session(session_data)

    # 2. Update cross-session patterns
    analyze_cross_session_patterns()

    # 3. Reset live realtime analyzer
    default_realtime_analyzer.reset()

    # 4. Optional adaptive cycle if plan was tracked
    next_plan = None
    if payload.plan_id:
        try:
            adaptive_res = default_adaptive_plan_engine.execute_adaptive_cycle(
                session_target=session_data,
                plan_target=payload.plan_id
            )
            next_plan = adaptive_res.next_plan.model_dump() if adaptive_res.next_plan else None
        except Exception:
            pass

    return {
        "status": "SESSION COMPLETE",
        "message": "Performance recorded. MEMORY UPDATED. Your session has been added to Gaming Second Brain.",
        "session_id": sid,
        "db_id": res.get("db_id"),
        "kd_ratio": kd_val,
        "kills": payload.kills,
        "deaths": payload.deaths,
        "duration": f"{payload.duration_mins} min",
        "result": payload.result,
        "memory_id": res.get("memory_id"),
        "ai_summary": res.get("ai_summary"),
        "next_plan": next_plan
    }

# ================= MVP USER FLOW ENDPOINTS (STEPS 1 - 10) =================

@app.post("/api/mvp/session", response_model=Dict[str, Any])
async def mvp_record_session_endpoint(payload: Session):
    """
    STEPS 1 - 4 of MVP USER FLOW:
    Records session information, generates AI memory summary, and stores structured session.
    """
    res = record_mvp_session(payload)
    analyze_cross_session_patterns()
    return res

@app.post("/api/mvp/ask", response_model=Dict[str, Any])
async def mvp_ask_endpoint(payload: Dict[str, Any]):
    """
    STEPS 5 - 10 of MVP USER FLOW:
    Handles natural language queries:
    - Step 5-8: 'When did I perform best?'
    - Step 9: 'What was different?'
    - Step 10: 'What should I do next?'
    """
    query = payload.get("query", "When did I perform best?")
    active_session_id = payload.get("session_id")
    res = handle_mvp_natural_language_query(query, active_session_id=active_session_id)
    return res

@app.get("/api/mvp/demo", response_model=Dict[str, Any])
async def mvp_demo_endpoint():
    """
    Simulates and returns all 10 steps of the MVP User Flow end-to-end.
    """
    s18_data = {
        "session_id": "18",
        "game": "Valorant",
        "duration": "72 minutes",
        "score": "18/10",
        "kills": 18,
        "deaths": 10,
        "assists": 6,
        "result": "Win",
        "map": "Ascent",
        "configuration": "Phantom + preferred sensitivity",
        "performance_metrics": {"kd": 1.8, "acs": 285},
        "player_notes": "Felt locked in. Sensitivity tweak was perfect, crosshair didn't jitter once."
    }
    step1_4 = record_mvp_session(s18_data)
    step5_8 = search_and_analyze_best_performance("When did I perform best?")
    step9 = compare_session_with_history(target_session_id="18", query="What was different?")
    step10 = generate_personalized_recommendation(target_session_id="18", query="What should I do next?")

    return {
        "status": "success",
        "steps": {
            "step_1_user_completes_session": "User completes a gaming session.",
            "step_2_recorded_session": s18_data,
            "step_3_ai_memory_summary": step1_4["ai_summary"],
            "step_4_stored_session_and_memory": {
                "session_id": step1_4["session_id"],
                "memory_id": step1_4["memory_id"]
            },
            "step_5_user_query": "When did I perform best?",
            "step_6_system_searches_sessions": f"Retrieved {step5_8['evidence'].get('total_sessions_analyzed', 0)} sessions from memory vault.",
            "step_7_ai_analyzes_sessions": "Evaluated K/D ratios, match outcomes, loadouts, and durations.",
            "step_8_explanation_with_evidence": step5_8["explanation"],
            "step_9_what_was_different": {
                "question": "What was different?",
                "explanation": step9["explanation"]
            },
            "step_10_what_should_i_do_next": {
                "question": "What should I do next?",
                "explanation": step10["explanation"],
                "recommendations": step10["recommended_actions"]
            }
        }
    }

# 3. Live Match Simulation endpoint (For strong hackathon demo)
@app.post("/api/sessions/simulate")
async def simulate_live_session(payload: Dict[str, Any]):
    """
    Simulates a live match unfolding in real-time or fast forward,
    demonstrating the live pipeline: PLAY -> UNDERSTAND -> REMEMBER -> LEARN -> IMPROVE
    """
    scenario = payload.get("scenario", "valorant_haven_choke")
    
    if scenario == "valorant_haven_choke":
        new_session = {
            "game": "Valorant",
            "title": "Live Match: Haven Overtime Battle (Ascendant II)",
            "map_or_level": "Haven",
            "character_or_loadout": "Omen (Phantom, Full Armor)",
            "outcome": "Defeat (12-14 OT)",
            "duration_mins": 44,
            "timestamp": "2026-09-18T10:30:00",
            "stats": {
                "kda": "19/22/8",
                "acs": 224,
                "headshot_pct": 26,
                "first_deaths": 7,
                "clutch_rate": "1/3"
            },
            "player_notes": "Live match ended in heartbreaker overtime. I threw round 25 by ego-peeking C Long again when we had man advantage. Copilot warned me, but I got tempted.",
            "timeline": [
                {
                    "timestamp_or_round": "Round 12 (Halftime)",
                    "event_type": "decision",
                    "description": "Clean defensive A-site smoke rotation, picked off bomb planter.",
                    "impact": "positive",
                    "tilt_indicator": 1
                },
                {
                    "timestamp_or_round": "Round 20 (Clutch)",
                    "event_type": "clutch",
                    "description": "Won 1v1 post-plant on B site with dark cover shadow teleport.",
                    "impact": "positive",
                    "tilt_indicator": 2
                },
                {
                    "timestamp_or_round": "Round 25 (Overtime Mistake)",
                    "event_type": "death",
                    "description": "Ego-peeked C Long at 0:10 without flash. Operator headshot received. Team lost 4v5 round advantage.",
                    "impact": "negative",
                    "tilt_indicator": 9
                }
            ]
        }
    else:
        new_session = {
            "game": "Elden Ring",
            "title": "Live Attempt: Malenia Blade of Miquella Phase 1 Trial",
            "map_or_level": "Elphael, Brace of the Haligtree",
            "character_or_loadout": "Rivers of Blood +10 (Dexterity Build)",
            "outcome": "Defeat (Phase 1 35% HP)",
            "duration_mins": 5,
            "timestamp": "2026-09-18T10:45:00",
            "stats": {
                "boss_health_remaining": "35%",
                "waterfowl_dance_dodged": "Partial (1/3 waves)",
                "panic_roll_count": 6
            },
            "player_notes": "First time facing Waterfowl Dance. Tried panic rolling backwards in a straight line and got shredded by the second flurry.",
            "timeline": [
                {
                    "timestamp_or_round": "0:30 (Opening)",
                    "event_type": "combat",
                    "description": "Clean bleed proc with Corpse Piler weapon art, staggered Malenia.",
                    "impact": "positive",
                    "tilt_indicator": 1
                },
                {
                    "timestamp_or_round": "1:15 (Waterfowl Dance)",
                    "event_type": "death",
                    "description": "Malenia leaped into air for Waterfowl Dance. Panic rolled backwards instead of running away or unlocking camera. Lethal damage taken.",
                    "impact": "negative",
                    "tilt_indicator": 8
                }
            ]
        }

    s_id = save_session(new_session)
    mem_ids = process_session_into_memories(s_id, new_session)
    analyze_cross_session_patterns()

    return {
        "success": True,
        "session": get_session_by_id(s_id),
        "memory_ids": mem_ids,
        "message": "Live match ingested! Memories synthesized and patterns updated."
    }

# 4. Memory Storage (REMEMBER)
@app.get("/api/memories", response_model=List[MemoryResponse])
async def list_memories(memory_type: Optional[str] = None, game: Optional[str] = None):
    return get_all_memories(memory_type=memory_type, game=game)

@app.get("/api/memories/tiers")
async def get_memories_three_tiers():
    """
    Returns memories organized into the three user-specified levels:
    1. Episodic Memory (individual gaming events)
    2. Pattern Memory (patterns discovered across multiple sessions)
    3. Player Profile Memory (long-term player information)
    """
    from app.database import get_memories_by_three_tiers
    return get_memories_by_three_tiers()

@app.get("/api/player/profile")
async def get_player_profile_endpoint():
    """
    Returns active long-term player profile facts.
    """
    from app.database import get_player_profile
    from app.memory_engine import generate_player_profile_memory
    sessions = get_all_sessions()
    profile_memory = generate_player_profile_memory(sessions)
    stored_profile = get_player_profile()
    return {
        "profile_memory": profile_memory,
        "stored_attributes": stored_profile
    }

@app.post("/api/memory-engine/process")
async def process_memory_engine_endpoint(payload: Session):
    """
    Executes the full 6-step AI MEMORY ENGINE workflow on a session:
    1. Summarize the session.
    2. Extract important facts.
    3. Identify notable performance.
    4. Compare against previous sessions when enough data exists.
    5. Update relevant player profile information.
    6. Store the generated memory.
    """
    from app.memory_engine import run_ai_memory_engine_after_session
    sess_dict = payload.model_dump()
    raw_id = sess_dict.get("session_id") or "temp"
    res = run_ai_memory_engine_after_session(raw_id, sess_dict)
    return res

# 5. Natural Language Search (SEMANTIC RETRIEVAL)
@app.post("/api/search", response_model=SearchResponse)
async def semantic_search(payload: SearchQuery):
    results = search_memories(query=payload.query, game=payload.game, limit=payload.limit)
    return results

# 6. Cross-Session Analysis (LEARN)
@app.get("/api/patterns", response_model=List[PatternItem])
async def list_patterns(game: Optional[str] = None):
    return get_all_patterns(game=game)

@app.get("/api/analytics")
async def get_analytics():
    return get_analytics_summary()

# 7. Personalized Recommendations & Copilot (IMPROVE)
@app.get("/api/recommendations", response_model=List[RecommendationItem])
async def list_recommendations(game: Optional[str] = None):
    return get_all_recommendations(game=game)

@app.post("/api/copilot/briefing", response_model=BriefingResponse)
async def get_briefing(payload: BriefingRequest):
    briefing = generate_pre_match_briefing(
        game=payload.game,
        target=payload.map_or_boss,
        character_or_role=payload.character_or_role
    )
    return briefing

@app.post("/api/copilot/chat", response_model=CopilotChatResponse)
async def copilot_chat(payload: CopilotChatRequest):
    res = handle_copilot_chat(message=payload.message, game=payload.game)
    return res

# 8. Reset to Default Seed Data
@app.post("/api/reset")
async def reset_database():
    clear_all_data()
    for s_data in SEED_SESSIONS:
        s_id = save_session(s_data)
        process_session_into_memories(s_id, s_data)
    analyze_cross_session_patterns()
    return {"success": True, "message": "Second Brain database reset to seed data."}


# =====================================================================
# GAME ADAPTER & 6-STAGE PIPELINE ENDPOINTS
# Game -> Game Adapter -> Detection -> Metrics -> Tasks -> Planning
# =====================================================================

@app.get("/api/adapters", response_model=List[GameAdapterInfo])
async def list_game_adapters():
    """Lists all registered game adapters and their capabilities."""
    return default_adapter_registry.list_supported_games()


@app.get("/api/adapters/{game}", response_model=GameAdapterInfo)
async def get_game_adapter_details(game: str):
    """Retrieves metadata and capabilities for a specific game adapter."""
    adapter = default_adapter_registry.get_adapter(game)
    return adapter.to_info()


@app.post("/api/pipeline/run", response_model=PipelineRunResponse)
async def run_gaming_pipeline(payload: PipelineRunRequest):
    """
    Executes the full 6-stage Gaming Second Brain pipeline:
    Game -> Game Adapter -> Detection -> Metrics -> Tasks -> Planning
    """
    return default_pipeline_orchestrator.run_pipeline(payload)

