from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json
import uuid

class TimelineEvent(BaseModel):
    timestamp_or_round: str
    event_type: str  # combat, death, clutch, utility, objective, decision, tilt
    description: str
    impact: str = "neutral"  # positive, negative, neutral
    tilt_indicator: int = 0  # 0 to 10 scale

# =====================================================================
# PHASE 1: SESSION DATA MODEL
# =====================================================================

class Session(BaseModel):
    """
    Core Session Model representing one gaming session.
    A flexible, game-agnostic schema with automatic K/D calculation,
    extensible configuration and performance metrics, and data validation.
    """
    # --- Identity ---
    session_id: Optional[Union[str, int]] = Field(default=None, description="Unique identifier for the session")
    match_id: Optional[str] = Field(default=None, description="Match identifier from game client or API")

    # --- Game (General & Game-Agnostic) ---
    game: Optional[str] = Field(default=None, description="Game title (e.g. Valorant, Elden Ring, Apex Legends)")
    game_mode: Optional[str] = Field(default=None, description="Game mode (e.g. Competitive, Boss Fight, Battle Royale)")
    map: Optional[str] = Field(default=None, description="Map, level, or boss arena")
    configuration: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Extensible loadout, weapon, or settings")

    # --- Timing ---
    started_at: Optional[Union[datetime, str]] = Field(default=None, description="Start timestamp of the session")
    ended_at: Optional[Union[datetime, str]] = Field(default=None, description="End timestamp of the session")
    duration: Optional[Union[int, float, str]] = Field(default=None, description="Duration of session in minutes or formatted string")

    # --- Performance ---
    score: Optional[str] = Field(default=None, description="Match score or round progression (e.g. '18/10', '13-11')")
    round_number: Optional[Union[int, str]] = Field(default=None, description="Current or final round number if applicable")
    kills: Optional[int] = Field(default=None, description="Total kills (must be non-negative)")
    deaths: Optional[int] = Field(default=None, description="Total deaths (must be non-negative)")
    assists: Optional[int] = Field(default=None, description="Total assists (must be non-negative)")
    kd_ratio: Optional[float] = Field(default=None, description="Kill-to-Death ratio (auto-calculated when kills & deaths exist)")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Extensible game-specific telemetry")

    # --- Outcome ---
    result: Optional[str] = Field(default=None, description="Match outcome (e.g. Win, Defeat, Victory, 1st)")

    # --- Player ---
    player_notes: Optional[str] = Field(default=None, description="Player reflections, thoughts, or debrief")
    tags: List[str] = Field(default_factory=list, description="Categorical or tactical tags")

    # --- Data Quality ---
    data_source: Optional[str] = Field(default=None, description="Source of telemetry (e.g. 'manual', 'client_api', 'ocr')")
    data_completeness: Optional[float] = Field(default=None, description="Completeness score between 0.0 and 1.0")

    # --- AI Metadata (Separated from Raw Player Data) ---
    ai_summary: Optional[str] = Field(default=None, description="AI-generated session summary (initially null)")
    ai_insights: Optional[List[str]] = Field(default=None, description="AI-generated strategic insights (initially null)")
    memory_text: Optional[str] = Field(default=None, description="Natural language memory representation")
    memory_importance: Optional[Union[float, int, str]] = Field(default=None, description="Significance weight of memory")
    ai_confidence: Optional[float] = Field(default=None, description="Confidence score of AI memory extraction (0.0 to 1.0)")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions supporting this memory")
    ai_model_version: Optional[str] = Field(default=None, description="AI model version used for generation")
    processing_status: Optional[str] = Field(default="pending", description="Processing status: pending, processed, skipped")

    # --- Backward compatibility aliases ---
    id: Optional[int] = None
    date: Optional[str] = None
    title: Optional[str] = None
    map_or_level: Optional[str] = None
    character_or_loadout: Optional[str] = None
    outcome: Optional[str] = None
    duration_mins: Optional[int] = None
    timestamp: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    timeline: Optional[List[TimelineEvent]] = Field(default_factory=list)
    created_at: Optional[str] = None
    memory_id: Optional[int] = None

    model_config = {
        "extra": "allow",
        "arbitrary_types_allowed": True
    }

    @field_validator("kills", "deaths", "assists", mode="before")
    @classmethod
    def validate_non_negative_counters(cls, value, info):
        """Reject negative kills, negative deaths, and negative assists."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if value < 0:
                raise ValueError(f"{info.field_name} cannot be negative (got {value})")
            return int(value)
        if isinstance(value, str):
            val_strip = value.strip()
            if val_strip.startswith("-"):
                raise ValueError(f"{info.field_name} cannot be negative (got {value})")
            try:
                val_int = int(val_strip)
                if val_int < 0:
                    raise ValueError(f"{info.field_name} cannot be negative (got {value})")
                return val_int
            except ValueError as e:
                if "cannot be negative" in str(e):
                    raise
                pass
        return value

    @field_validator("duration", mode="before")
    @classmethod
    def validate_non_negative_duration(cls, value):
        """Reject negative duration."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if value < 0:
                raise ValueError(f"duration cannot be negative (got {value})")
            return value
        if isinstance(value, str):
            val_strip = value.strip()
            if val_strip.startswith("-"):
                raise ValueError(f"duration cannot be negative (got {value})")
            digits = "".join([c for c in val_strip if c.isdigit() or c == "-"])
            if digits.startswith("-"):
                raise ValueError(f"duration cannot be negative (got {value})")
        return value

    @field_validator("duration_mins", mode="before")
    @classmethod
    def validate_non_negative_duration_mins(cls, value):
        """Reject negative duration_mins for backward compatibility."""
        if value is not None and value < 0:
            raise ValueError(f"duration_mins cannot be negative (got {value})")
        return value

    @model_validator(mode="after")
    def compute_kd_and_sync_fields(self):
        """
        1. Calculate K/D automatically when kills and deaths exist.
           Safely handles deaths = 0 (prevents ZeroDivisionError).
           Does not invent K/D if kills or deaths are missing.
        2. Synchronizes backward compatibility aliases.
        3. Measures data completeness based on non-invented facts.
        """
        # Automatic K/D calculation
        if self.kills is not None and self.deaths is not None:
            if self.deaths == 0:
                # Safe zero-death handling
                self.kd_ratio = float(self.kills)
            else:
                self.kd_ratio = round(float(self.kills) / float(self.deaths), 2)

        # Normalize session_id to string representation if provided
        if self.session_id is not None:
            self.session_id = str(self.session_id)

        # Backward compatibility field synchronization
        if self.started_at and not self.date:
            self.date = str(self.started_at)
        elif self.date and not self.started_at:
            self.started_at = self.date

        if self.started_at and not self.timestamp:
            self.timestamp = str(self.started_at)
        elif self.timestamp and not self.started_at:
            self.started_at = self.timestamp

        if self.result and not self.outcome:
            self.outcome = self.result
        elif self.outcome and not self.result:
            self.result = self.outcome

        if self.map and not self.map_or_level:
            self.map_or_level = self.map
        elif self.map_or_level and not self.map:
            self.map = self.map_or_level

        if self.configuration and not self.character_or_loadout:
            self.character_or_loadout = str(self.configuration) if isinstance(self.configuration, str) else json.dumps(self.configuration)
        elif self.character_or_loadout and not self.configuration:
            self.configuration = self.character_or_loadout

        if self.duration is not None and self.duration_mins is None:
            if isinstance(self.duration, (int, float)):
                self.duration_mins = int(self.duration)
            elif isinstance(self.duration, str):
                digits = "".join([c for c in self.duration if c.isdigit()])
                if digits:
                    self.duration_mins = int(digits)

        if self.stats and not self.performance_metrics:
            self.performance_metrics = dict(self.stats)
        elif self.performance_metrics and not self.stats:
            self.stats = dict(self.performance_metrics)

        # Synchronize round_number with performance_metrics
        if self.round_number is not None and "round_number" not in self.performance_metrics:
            self.performance_metrics["round_number"] = self.round_number
        elif self.round_number is None and "round_number" in self.performance_metrics:
            self.round_number = self.performance_metrics["round_number"]

        # Measure data completeness based on populated core fields (without inventing data)
        if self.data_completeness is None:
            core_tracked = [
                self.session_id,
                self.game,
                self.map,
                self.configuration,
                self.started_at,
                self.duration,
                self.score,
                self.kills,
                self.deaths,
                self.result
            ]
            filled = sum(1 for f in core_tracked if f is not None and f != "")
            self.data_completeness = round(filled / len(core_tracked), 2)

        return self

class SessionCreate(BaseModel):
    # Phase 1 Core fields
    session_id: Optional[Union[str, int]] = None
    match_id: Optional[str] = None
    game: Optional[str] = None
    game_mode: Optional[str] = None
    map: Optional[str] = None
    configuration: Optional[Union[Dict[str, Any], str]] = None
    started_at: Optional[Union[datetime, str]] = None
    ended_at: Optional[Union[datetime, str]] = None
    duration: Optional[Union[int, float, str]] = None
    score: Optional[str] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    kd_ratio: Optional[float] = None
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    player_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    data_source: Optional[str] = None
    data_completeness: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_insights: Optional[List[str]] = None
    memory_text: Optional[str] = None
    memory_importance: Optional[Union[float, int, str]] = None
    ai_confidence: Optional[float] = None
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list)
    ai_model_version: Optional[str] = None
    processing_status: Optional[str] = "pending"

    # Legacy fields
    date: Optional[str] = None
    title: Optional[str] = None
    map_or_level: Optional[str] = None
    character_or_loadout: Optional[str] = None
    outcome: Optional[str] = None
    duration_mins: Optional[int] = None
    stats: Dict[str, Any] = Field(default_factory=dict)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    timestamp: Optional[str] = None

    model_config = {"extra": "allow"}

class SessionResponse(BaseModel):
    id: Optional[int] = None
    session_id: Optional[Union[str, int]] = None
    match_id: Optional[str] = None
    game: Optional[str] = None
    game_mode: Optional[str] = None
    map: Optional[str] = None
    configuration: Optional[Union[Dict[str, Any], str]] = None
    started_at: Optional[Union[datetime, str]] = None
    ended_at: Optional[Union[datetime, str]] = None
    duration: Optional[Union[int, float, str]] = None
    score: Optional[str] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    kd_ratio: Optional[float] = None
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    player_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    data_source: Optional[str] = None
    data_completeness: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_insights: Optional[Any] = None
    memory_text: Optional[str] = None
    memory_importance: Optional[Union[float, int, str]] = None
    ai_confidence: Optional[float] = None
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list)
    ai_model_version: Optional[str] = None
    processing_status: Optional[str] = "pending"

    # Legacy fields
    title: Optional[str] = None
    map_or_level: Optional[str] = None
    character_or_loadout: Optional[str] = None
    outcome: Optional[str] = None
    duration_mins: Optional[int] = None
    stats: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timeline: Optional[List[TimelineEvent]] = Field(default_factory=list)
    timestamp: Optional[str] = None
    date: Optional[str] = None
    created_at: Optional[str] = None
    memory_id: Optional[int] = None

    model_config = {"extra": "allow"}

class MemoryResponse(BaseModel):
    id: int
    session_id: Optional[Union[int, str]] = None
    game: str
    memory_type: str  # 'episodic' (match-specific), 'semantic' (player facts), 'procedural' (habits)
    title: str
    summary: str
    key_moments: List[Dict[str, Any]]
    tags: List[str]
    emotional_state: str
    root_causes: List[str]
    created_at: str

class SearchQuery(BaseModel):
    query: str
    game: Optional[str] = None
    limit: int = 5

class SearchResultItem(BaseModel):
    memory_id: int
    session_id: Optional[Union[int, str]] = None
    game: str
    memory_type: str
    title: str
    summary: str
    relevance_score: float
    matched_tags: List[str]
    snippet: str

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    ai_synthesized_answer: str
    key_takeaway: str

class PatternItem(BaseModel):
    id: int
    category: str  # 'weakness', 'tilt_trigger', 'strength', 'habit'
    game: str
    title: str
    description: str
    confidence_score: float
    occurrence_count: int
    affected_session_ids: List[int]
    actionable_recommendation: str

class RecommendationItem(BaseModel):
    id: int
    category: str  # 'tactical', 'mental_game', 'mechanics', 'loadout'
    game: str
    title: str
    description: str
    actionable_steps: List[str]
    priority: str  # 'High', 'Medium', 'Low'
    trigger_context: str

class CopilotChatRequest(BaseModel):
    message: str
    game: Optional[str] = None
    context_mode: str = "all_memories"  # all_memories, recent, patterns

class CopilotChatResponse(BaseModel):
    reply: str
    relevant_memories_used: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    source_engine: str = "Gaming Second Brain Copilot"
    answer: Optional[str] = None
    evidence: Optional[str] = None
    insight: Optional[str] = None
    recommendation: Optional[str] = None
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list)

    model_config = {
        "extra": "allow"
    }

class BriefingRequest(BaseModel):
    game: str
    map_or_boss: str
    character_or_role: Optional[str] = None

class BriefingResponse(BaseModel):
    game: str
    target: str
    historical_record: str
    primary_threat: str
    key_rules_to_win: List[str]
    recommended_focus: str
    copilot_quote: str

class ApiKeyUpdate(BaseModel):
    api_key: str

# Three Levels of Memory Models
class EpisodicMemoryModel(BaseModel):
    level: str = "1. EPISODIC MEMORY"
    session_id: Optional[Any] = None
    summary: str  # Example: "Session #18 was a 72-minute Valorant session with 1.8 K/D."
    game: Optional[str] = None
    duration: Optional[Any] = None
    score: Optional[str] = None
    kd: Optional[float] = None
    map: Optional[str] = None
    configuration: Optional[str] = None
    result: Optional[str] = None
    extracted_facts: Dict[str, Any] = Field(default_factory=dict)

class PatternMemoryModel(BaseModel):
    level: str = "2. PATTERN MEMORY"
    pattern_type: str
    description: str  # Example: "The player tends to perform better during sessions shorter than 90 minutes."
    confidence: float = 0.0
    status: str = "discovered"  # "discovered" or "insufficient_data"
    evidence_sessions: List[Any] = Field(default_factory=list)

class PlayerProfileMemoryModel(BaseModel):
    level: str = "3. PLAYER PROFILE MEMORY"
    preferred_configuration: str  # Example: "Phantom + preferred sensitivity" or "Not enough data to determine this."
    summary: str  # Example: "Preferred configuration: Phantom + preferred sensitivity."
    peak_kd: Optional[float] = None
    peak_session_id: Optional[Any] = None
    average_kd: Optional[float] = None
    total_sessions: int = 0
    best_map: Optional[str] = None
    primary_game: Optional[str] = None
    profile_facts: Dict[str, Any] = Field(default_factory=dict)

class ThreeTierMemoriesResponse(BaseModel):
    episodic: List[Dict[str, Any]]
    pattern: List[Dict[str, Any]]
    player_profile: List[Dict[str, Any]]

class MemoryEngineResult(BaseModel):
    session_id: Any
    step_1_summary: str
    step_2_extracted_facts: Dict[str, Any]
    step_3_notable_performance: str
    step_4_comparison: str
    step_5_profile_updates: Dict[str, Any]
    step_6_stored_memories: Dict[str, Any]
    episodic_memory: EpisodicMemoryModel
    pattern_memory: PatternMemoryModel
    player_profile_memory: PlayerProfileMemoryModel

# =====================================================================
# PHASE 3: GAME AND MAP DETECTION MODELS
# =====================================================================

class GameDetectionResult(BaseModel):
    """
    Structured outcome of game and map detection (Phase 3).
    Identifies:
    - game
    - game_version if available
    - game_mode if available
    - map if available
    - confidence (detection confidence)
    - detection_source (manual, simulated, api, game_log)
    """
    game: Optional[str] = Field(default=None, description="Detected game title")
    game_version: Optional[str] = Field(default=None, description="Detected game version if available")
    game_mode: Optional[str] = Field(default=None, description="Detected game mode")
    map: Optional[str] = Field(default=None, description="Detected map, level, or arena")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    detection_source: str = Field(
        default="simulated",
        description="Source of detection: 'manual', 'simulated', 'api', 'game_log'"
    )
    is_confident: bool = Field(default=True, description="Whether detection meets confidence threshold")
    message: Optional[str] = Field(default=None, description="Status or uncertainty message")
    raw_telemetry: Dict[str, Any] = Field(default_factory=dict, description="Raw context or telemetry used")

    model_config = {
        "extra": "allow"
    }

    @field_validator("detection_source")
    @classmethod
    def validate_detection_source(cls, v: str) -> str:
        allowed = {"manual", "simulated", "api", "game_log"}
        if v not in allowed:
            raise ValueError(f"Invalid detection_source '{v}'. Allowed sources: {allowed}")
        return v

    @model_validator(mode="after")
    def check_confidence_and_uncertainty(self):
        UNCERTAIN_MSG = "Unable to confidently detect game/map."
        if self.confidence < 0.6 or not self.game:
            self.is_confident = False
            if not self.message:
                self.message = UNCERTAIN_MSG
        else:
            self.is_confident = True
        return self

    def format_display(self, include_details: bool = False) -> str:
        """
        Formats display matching Phase 3 specification:
        GAME:
        BGMI

        CONFIDENCE:
        0.96

        SOURCE:
        simulated
        """
        lines = [
            f"GAME:\n{self.game or 'Unknown'}",
            f"CONFIDENCE:\n{self.confidence:.2f}",
            f"SOURCE:\n{self.detection_source}"
        ]
        if include_details:
            if self.game_version:
                lines.append(f"VERSION:\n{self.game_version}")
            if self.game_mode:
                lines.append(f"MODE:\n{self.game_mode}")
        return "\n\n".join(lines)


# Backward compatibility alias
DetectionResult = GameDetectionResult


class DetectionConfirmRequest(BaseModel):
    """
    Payload for confirming or manually correcting detected game/map info.
    Only confirmed values are persisted into a Session.
    """
    game: str
    game_mode: Optional[str] = None
    map: Optional[str] = None
    detection_source: str = "manual"
    confidence: float = 1.0
    session_id: Optional[Union[str, int]] = None
    configuration: Optional[Union[Dict[str, Any], str]] = None
    started_at: Optional[Union[datetime, str]] = None
    player_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    model_config = {
        "extra": "allow"
    }

# =====================================================================
# PHASE 4: MAP AND MATCH DETECTION MODELS
# =====================================================================

class MapDetectionResult(BaseModel):
    """
    Phase 4: Map Detection Result Structure.
    Detects or allows manual input for game-specific maps.
    If map information is unavailable: 'Map not detected.'
    """
    map: Optional[str] = Field(default=None, description="Detected or input map name")
    game: Optional[str] = Field(default=None, description="Game title associated with this map")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Detection confidence score")
    detection_source: str = Field(
        default="simulated",
        description="Source of detection: 'manual', 'simulated', 'api', 'game_log'"
    )
    is_confident: bool = Field(default=True, description="Whether detection meets confidence threshold")
    message: Optional[str] = Field(default=None, description="Status or uncertainty message")
    raw_telemetry: Dict[str, Any] = Field(default_factory=dict, description="Raw context or telemetry used")

    model_config = {
        "extra": "allow"
    }

    @field_validator("detection_source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        allowed = {"manual", "simulated", "api", "game_log"}
        if v not in allowed:
            raise ValueError(f"Invalid detection_source '{v}'. Allowed sources: {allowed}")
        return v

    @model_validator(mode="after")
    def check_map_availability(self):
        UNAVAILABLE_MSG = "Map not detected."
        if not self.map or self.confidence < 0.6:
            self.is_confident = False
            if not self.message:
                self.message = UNAVAILABLE_MSG
        else:
            self.is_confident = True
        return self

    def format_display(self) -> str:
        """
        Formats display for Map detection:
        GAME:
        Valorant

        MAP:
        Ascent

        CONFIDENCE:
        0.95

        SOURCE:
        simulated
        """
        lines = []
        if self.game:
            lines.append(f"GAME:\n{self.game}")
        map_val = self.map if (self.map and self.is_confident) else (self.message or "Map not detected.")
        lines.append(f"MAP:\n{map_val}")
        lines.append(f"CONFIDENCE:\n{self.confidence:.2f}")
        lines.append(f"SOURCE:\n{self.detection_source}")
        return "\n\n".join(lines)


class MatchContext(BaseModel):
    """
    Phase 4: Match Context Structure.
    Stores and connects match details:
    - map
    - game mode
    - match ID
    - round number if applicable
    - detection confidence
    - detection source
    """
    game: Optional[str] = Field(default=None, description="Game title")
    map: Optional[str] = Field(default=None, description="Map or arena name")
    game_mode: Optional[str] = Field(default=None, description="Game mode (e.g. Competitive, Classic Battle Royale)")
    match_id: Optional[str] = Field(default=None, description="Unique match identifier")
    round_number: Optional[Union[int, str]] = Field(default=None, description="Current or final round number if applicable")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")
    detection_source: str = Field(default="simulated", description="Detection source: 'manual', 'simulated', 'api', 'game_log'")
    is_confirmed: bool = Field(default=False, description="Whether player has confirmed this match context")
    map_detection: Optional[MapDetectionResult] = Field(default=None, description="Embedded map detection result")
    raw_telemetry: Dict[str, Any] = Field(default_factory=dict, description="Raw context or telemetry used")

    model_config = {
        "extra": "allow"
    }

    def confirm(
        self,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        match_id: Optional[str] = None,
        round_number: Optional[Union[int, str]] = None
    ) -> "MatchContext":
        """Allows manual confirmation and overrides."""
        if map_name is not None:
            self.map = map_name
        if game_mode is not None:
            self.game_mode = game_mode
        if match_id is not None:
            self.match_id = match_id
        if round_number is not None:
            self.round_number = round_number
        self.detection_source = "manual"
        self.confidence = 1.0
        self.is_confirmed = True
        return self

    def to_session_payload(self) -> Dict[str, Any]:
        """Converts match context into dictionary suitable for Session create or update."""
        payload: Dict[str, Any] = {}
        if self.game is not None:
            payload["game"] = self.game
        if self.map is not None:
            payload["map"] = self.map
        if self.game_mode is not None:
            payload["game_mode"] = self.game_mode
        if self.match_id is not None:
            payload["match_id"] = self.match_id
        if self.detection_source is not None:
            payload["data_source"] = self.detection_source
        if self.round_number is not None:
            payload["round_number"] = self.round_number
            payload["performance_metrics"] = {"round_number": self.round_number}
        return payload

# =====================================================================
# PHASE 5: GAME STATE DETECTION MODELS
# =====================================================================

class GameState(str, Enum):
    """
    Normalized internal game states.
    Different games may map custom engine states into these canonical states.
    """
    LOBBY = "lobby"
    LOADING = "loading"
    MATCH_STARTED = "match_started"
    ACTIVE_GAMEPLAY = "active_gameplay"
    ROUND_STARTED = "round_started"
    ROUND_FINISHED = "round_finished"
    MATCH_FINISHED = "match_finished"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, val: Union[str, "GameState", None]) -> "GameState":
        if isinstance(val, cls):
            return val
        if not val or not isinstance(val, str):
            return cls.UNKNOWN
        clean = val.strip().lower().replace(" ", "_").replace("-", "_")
        for member in cls:
            if member.value == clean or member.name.lower() == clean:
                return member
        return cls.UNKNOWN


class GameStateSnapshot(BaseModel):
    """
    Normalized Game State Snapshot.
    Captures active state, game, map, match time, and provenance.
    """
    game: Optional[str] = Field(default=None, description="Game title")
    map: Optional[str] = Field(default=None, description="Map or level name")
    state: GameState = Field(default=GameState.UNKNOWN, description="Normalized game state")
    match_time: Optional[str] = Field(default=None, description="Match timer string (e.g. '18:42')")
    match_time_seconds: Optional[float] = Field(default=None, description="Elapsed match duration in seconds")
    round_number: Optional[Union[int, str]] = Field(default=None, description="Current or completed round number")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")
    source: str = Field(
        default="simulated",
        description="Source of state detection: 'manual', 'simulated', 'telemetry', 'game_log', 'api', 'cv'"
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of this snapshot")
    raw_state: Optional[str] = Field(default=None, description="Raw telemetry state before normalization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional contextual state metadata")

    model_config = {
        "extra": "allow"
    }

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, v: Any) -> GameState:
        return GameState.from_string(v)

    def format_display(self) -> str:
        """
        Formats display matching Phase 5 specification:
        GAME:
        BGMI

        MAP:
        Erangel

        STATE:
        ACTIVE_GAMEPLAY

        MATCH_TIME:
        18:42
        """
        lines = []
        if self.game:
            lines.append(f"GAME:\n{self.game}")
        if self.map:
            lines.append(f"MAP:\n{self.map}")
        state_str = self.state.value.upper() if isinstance(self.state, GameState) else str(self.state).upper()
        lines.append(f"STATE:\n{state_str}")
        if self.match_time:
            lines.append(f"MATCH_TIME:\n{self.match_time}")
        return "\n\n".join(lines)


class StateTransitionRecord(BaseModel):
    """Historical audit of a game state transition."""
    from_state: GameState
    to_state: GameState
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(default="simulated")
    match_time: Optional[str] = None
    game: Optional[str] = None
    is_valid: bool = True
    reason: Optional[str] = None


class StateUpdateRequest(BaseModel):
    """Payload for updating game state via API."""
    state: Union[GameState, str]
    game: Optional[str] = None
    map: Optional[str] = None
    match_time: Optional[str] = None
    round_number: Optional[Union[int, str]] = None
    source: str = "manual"
    force: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

# =====================================================================
# PHASE 6: GAMING PERFORMANCE ENGINE MODELS
# =====================================================================

class PerformanceReport(BaseModel):
    """
    Phase 6: Normalized Performance Report.
    Calculates and presents measurable performance from stored session data.
    Does not estimate metrics when required data is missing (returns 'Not enough data.').
    """
    session_id: Optional[Union[str, int]] = Field(default=None, description="Session identifier")
    game: Optional[str] = Field(default=None, description="Game title")
    map: Optional[str] = Field(default=None, description="Map or level")
    
    # Core Measurable Metrics
    kd_ratio: Optional[float] = Field(default=None, description="Kills / Deaths ratio")
    kills: Optional[int] = Field(default=None, description="Total kills")
    deaths: Optional[int] = Field(default=None, description="Total deaths")
    assists: Optional[int] = Field(default=None, description="Total assists")
    win_rate: Optional[float] = Field(default=None, description="Win rate percentage")
    duration_mins: Optional[float] = Field(default=None, description="Duration in minutes")
    duration_display: Optional[str] = Field(default=None, description="Formatted duration string e.g. '72 min'")
    survival_duration: Optional[Union[float, str]] = Field(default=None, description="Survival duration when available")
    result: Optional[str] = Field(default=None, description="Match outcome")
    
    # Rate and Efficiency Metrics
    kills_per_minute: Optional[float] = Field(default=None, description="Kills per minute (KPM)")
    deaths_per_minute: Optional[float] = Field(default=None, description="Deaths per minute (DPM)")
    score_efficiency: Optional[float] = Field(default=None, description="Score efficiency")
    
    # Metrics When Available (None when missing, never estimated)
    accuracy: Optional[Union[float, str]] = Field(default=None, description="Weapon/hit accuracy when available")
    damage: Optional[Union[float, int]] = Field(default=None, description="Damage dealt when available")
    objective_performance: Optional[Union[Dict[str, Any], float, str]] = Field(default=None, description="Objective performance stats when available")
    
    # Extensible game-specific metrics
    game_specific_metrics: Dict[str, Any] = Field(default_factory=dict, description="Extensible game-specific telemetry")
    
    # Availability tracking
    available_metrics: List[str] = Field(default_factory=list, description="List of metrics with sufficient data")
    missing_metrics: List[str] = Field(default_factory=list, description="List of metrics with missing data")

    model_config = {
        "extra": "allow"
    }

    def get_metric_display(self, metric_name: str) -> str:
        """
        Returns metric value or explicitly 'Not enough data.' if unavailable.
        """
        val = getattr(self, metric_name, None)
        if val is None:
            val = self.game_specific_metrics.get(metric_name)
        if val is None:
            return "Not enough data."
        if isinstance(val, float):
            return f"{val:.2f}".rstrip("0").rstrip(".") if "." in f"{val:.2f}" else f"{val:.2f}"
        return str(val)

    def format_display(self, minimal: bool = True) -> str:
        """
        Formats normalized display matching Phase 6 specification:
        Performance
        K/D: 1.8
        Kills: 18
        Deaths: 10
        Duration: 72 min
        Result: Win
        """
        lines = ["Performance"]
        if self.kd_ratio is not None:
            kd_str = f"{self.kd_ratio:.2f}".rstrip("0").rstrip(".") if "." in f"{self.kd_ratio:.2f}" else f"{self.kd_ratio}"
            lines.append(f"K/D: {kd_str}")
        if self.kills is not None:
            lines.append(f"Kills: {self.kills}")
        if self.deaths is not None:
            lines.append(f"Deaths: {self.deaths}")
        if self.duration_display:
            lines.append(f"Duration: {self.duration_display}")
        elif self.duration_mins is not None:
            mins_val = int(self.duration_mins) if self.duration_mins.is_integer() else self.duration_mins
            lines.append(f"Duration: {mins_val} min")
        if self.result is not None:
            lines.append(f"Result: {self.result}")

        if not minimal:
            if self.assists is not None:
                lines.append(f"Assists: {self.assists}")
            if self.win_rate is not None:
                lines.append(f"Win Rate: {self.win_rate:.1f}%")
            if self.kills_per_minute is not None:
                lines.append(f"Kills Per Minute: {self.kills_per_minute:.2f}")
            if self.deaths_per_minute is not None:
                lines.append(f"Deaths Per Minute: {self.deaths_per_minute:.2f}")
            if self.score_efficiency is not None:
                lines.append(f"Score Efficiency: {self.score_efficiency:.2f}")
            if self.accuracy is not None:
                lines.append(f"Accuracy: {self.accuracy}")
            if self.damage is not None:
                lines.append(f"Damage: {self.damage}")
            if self.objective_performance is not None:
                lines.append(f"Objective Performance: {self.objective_performance}")
            for k, v in self.game_specific_metrics.items():
                lines.append(f"{k.replace('_', ' ').title()}: {v}")

        return "\n".join(lines)

# =====================================================================
# PHASE 7: AI GAMING TASK ENGINE MODELS
# =====================================================================

TASK_CATEGORIES = [
    "aim",
    "movement",
    "positioning",
    "map_awareness",
    "decision_making",
    "combat",
    "consistency",
    "objective",
    "strategy",
    "configuration"
]

BGMI_CATEGORY_MAP: Dict[str, str] = {
    "rotation_planning": "strategy",
    "rotation planning": "strategy",
    "zone_awareness": "map_awareness",
    "zone awareness": "map_awareness",
    "positioning": "positioning",
    "survival": "consistency",
    "combat": "combat",
    "loot_efficiency": "objective",
    "loot efficiency": "objective",
    "vehicle_usage": "movement",
    "vehicle usage": "movement",
    "weapon_configuration": "configuration",
    "weapon configuration": "configuration",
    "final-zone decision making": "decision_making",
    "final_zone_decision_making": "decision_making",
    "final zone decision making": "decision_making",
    "final-zone decision-making": "decision_making",
}

FREE_FIRE_CATEGORY_MAP: Dict[str, str] = {
    "movement": "movement",
    "positioning": "positioning",
    "combat": "combat",
    "weapon/loadout usage": "configuration",
    "weapon_loadout_usage": "configuration",
    "weapon loadout usage": "configuration",
    "weapon usage": "configuration",
    "weapon_usage": "configuration",
    "loadout usage": "configuration",
    "loadout_usage": "configuration",
    "weapon": "configuration",
    "loadout": "configuration",
    "safe-zone decisions": "strategy",
    "safe_zone_decisions": "strategy",
    "safe zone decisions": "strategy",
    "safe_zone": "strategy",
    "safe zone": "strategy",
    "safe-zone": "strategy",
    "survival": "consistency",
    "objective performance": "objective",
    "objective_performance": "objective",
    "objective": "objective",
}

CODM_CATEGORY_MAP: Dict[str, str] = {
    "aim": "aim",
    "recoil": "combat",
    "recoil control": "combat",
    "movement": "movement",
    "positioning": "positioning",
    "loadout": "configuration",
    "weapon loadout": "configuration",
    "gunsmith": "configuration",
    "objective play": "objective",
    "objective_play": "objective",
    "objective": "objective",
    "deaths": "consistency",
    "accuracy": "aim",
    "score efficiency": "consistency",
    "score_efficiency": "consistency",
}

VALORANT_CATEGORY_MAP: Dict[str, str] = {
    "aim": "aim",
    "crosshair placement": "positioning",
    "crosshair_placement": "positioning",
    "crosshair": "positioning",
    "positioning": "positioning",
    "economy": "strategy",
    "eco": "strategy",
    "utility usage": "objective",
    "utility_usage": "objective",
    "utility": "objective",
    "map awareness": "map_awareness",
    "map_awareness": "map_awareness",
    "round decisions": "decision_making",
    "round_decisions": "decision_making",
    "decision_making": "decision_making",
    "configuration": "configuration",
    "consistency": "consistency",
}

class GamingTask(BaseModel):
    """
    Phase 7: AI Gaming Task.
    Represents a specific, measurable gaming task derived strictly from stored historical performance data.
    Does not assume causation and does not implement real-time game control.
    """
    task_id: str = Field(description="Unique task identifier")
    game: str = Field(description="Target game title")
    category: str = Field(description="Task category from valid list")
    objective: str = Field(description="Specific, actionable objective")
    description: str = Field(description="Detailed task description without claiming causation")
    duration: str = Field(default="15 minutes", description="Target practice or focus duration")
    metric_to_track: str = Field(description="Measurable metric to track during task")
    target: str = Field(description="Observable target outcome")
    difficulty: str = Field(default="medium", description="Task difficulty level")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions evidencing the need for this task")
    status: str = Field(default="pending", description="Task status: pending, in_progress, completed, skipped")
    created_at: Optional[str] = None

    model_config = {
        "extra": "allow"
    }

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        cat_clean = value.strip().lower()
        if cat_clean in BGMI_CATEGORY_MAP:
            return BGMI_CATEGORY_MAP[cat_clean]
        if cat_clean in FREE_FIRE_CATEGORY_MAP:
            return FREE_FIRE_CATEGORY_MAP[cat_clean]
        if cat_clean in CODM_CATEGORY_MAP:
            return CODM_CATEGORY_MAP[cat_clean]
        if cat_clean in VALORANT_CATEGORY_MAP:
            return VALORANT_CATEGORY_MAP[cat_clean]
        if cat_clean not in TASK_CATEGORIES:
            raise ValueError(f"Invalid category '{value}'. Must be one of: {TASK_CATEGORIES}")
        return cat_clean

    def format_display(self) -> str:
        """
        Formats normalized display matching Phase 7 specification:
        Task:
        Improve crosshair placement.

        Duration:
        15 minutes.

        Metric:
        Deaths caused by poor positioning.

        Target:
        Reduce repeated positioning mistakes.

        Evidence:
        Session #18
        Session #21
        """
        dur_str = str(self.duration).strip()
        if not dur_str.endswith("."):
            dur_str += "."
        obj_str = self.objective.strip()
        if not obj_str.endswith("."):
            obj_str += "."
        metric_str = self.metric_to_track.strip()
        if not metric_str.endswith("."):
            metric_str += "."
        target_str = self.target.strip()
        if not target_str.endswith("."):
            target_str += "."

        lines = [
            "Task:",
            obj_str,
            "",
            "Duration:",
            dur_str,
            "",
            "Metric:",
            metric_str,
            "",
            "Target:",
            target_str,
            "",
            "Evidence:"
        ]
        if self.evidence_session_ids:
            for sid in self.evidence_session_ids:
                sid_str = str(sid).strip()
                if not sid_str.startswith("#"):
                    sid_str = f"#{sid_str}"
                lines.append(f"Session {sid_str}")
        else:
            lines.append("None")
        return "\n".join(lines)


class TaskEngineResponse(BaseModel):
    """
    Response model for AI Gaming Task Engine requests.
    """
    tasks: List[GamingTask] = Field(default_factory=list, description="List of generated personalized gaming tasks")
    total_tasks: int = Field(default=0, description="Count of generated tasks")
    status: str = Field(default="success", description="'success' or 'insufficient_data'")
    message: str = Field(default="Tasks created from historical sessions.", description="Status message or 'Not enough data to create a personalized task.'")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="All session IDs used as evidence")

    model_config = {
        "extra": "allow"
    }


class CreateTasksRequest(BaseModel):
    game: Optional[str] = Field(default=None, description="Optional game filter")
    category: Optional[str] = Field(default=None, description="Optional specific category filter")
    limit: int = Field(default=5, ge=1, le=20, description="Max tasks to generate")

# =====================================================================
# PHASE 9: REAL-TIME PERFORMANCE ANALYSIS MODELS
# =====================================================================

GAME_EVENT_TYPES = [
    "kill",
    "death",
    "assist",
    "objective",
    "location_change",
    "round_result",
    "match_result",
    "configuration_change",
    "inventory_change"
]

class GameEvent(BaseModel):
    """
    Represents an atomic real-time gameplay event processed during a live session.
    """
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:8]}", description="Unique event identifier")
    event_type: str = Field(description="kill, death, assist, objective, location_change, round_result, match_result, configuration_change, inventory_change")
    timestamp: Optional[Union[datetime, str]] = Field(default=None, description="Event timestamp")
    details: Dict[str, Any] = Field(default_factory=dict, description="Event payload telemetry")

    model_config = {
        "extra": "allow"
    }


class CurrentPerformance(BaseModel):
    """
    Phase 9: Real-time Live Performance State.
    Calculates and presents measurable live metrics from streamed or simulated game events.
    Does not interfere with game controls and does not generate unsupported recommendations.
    """
    session_id: Optional[str] = Field(default=None, description="Current session ID")
    game: Optional[str] = Field(default=None, description="Current game title")
    map: Optional[str] = Field(default=None, description="Current map")
    kd_ratio: Optional[float] = Field(default=0.0, description="Current live K/D ratio")
    kills: int = Field(default=0, description="Current live kill count")
    deaths: int = Field(default=0, description="Current live death count")
    assists: int = Field(default=0, description="Current live assist count")
    survival_time: Optional[str] = Field(default=None, description="Current survival time display e.g. '22 min'")
    survival_time_seconds: float = Field(default=0.0, description="Elapsed survival time in seconds")
    objective_progress: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Live objective progress")
    current_score: Optional[Union[str, int, float]] = Field(default=None, description="Current score or round score")
    current_location: Optional[str] = Field(default=None, description="Current player zone/location")
    current_configuration: Optional[str] = Field(default=None, description="Active weapon/loadout")
    round_number: Optional[int] = Field(default=None, description="Current round")
    recent_events: List[GameEvent] = Field(default_factory=list, description="Audit trail of processed live events")

    model_config = {
        "extra": "allow"
    }

    def format_display(self, minimal: bool = True) -> str:
        """
        Formats normalized display matching Phase 9 specification:
        CURRENT PERFORMANCE

        K/D: 1.6
        Kills: 8
        Deaths: 5
        Survival: 22 min
        """
        lines = ["CURRENT PERFORMANCE", ""]
        if self.kd_ratio is not None:
            kd_str = f"{self.kd_ratio:.2f}".rstrip("0").rstrip(".") if "." in f"{self.kd_ratio:.2f}" else f"{self.kd_ratio}"
            lines.append(f"K/D: {kd_str}")
        elif self.kills is not None and self.deaths is not None:
            kd_val = float(self.kills) if self.deaths == 0 else round(self.kills / self.deaths, 2)
            kd_str = f"{kd_val:.2f}".rstrip("0").rstrip(".") if "." in f"{kd_val:.2f}" else f"{kd_val}"
            lines.append(f"K/D: {kd_str}")
        else:
            lines.append("K/D: 0.0")

        lines.append(f"Kills: {self.kills}")
        lines.append(f"Deaths: {self.deaths}")
        if self.survival_time:
            surv_str = str(self.survival_time).strip()
            if not surv_str.endswith("min") and not surv_str.endswith("mins") and ":" not in surv_str:
                surv_str = f"{surv_str} min"
            lines.append(f"Survival: {surv_str}")
        elif self.survival_time_seconds > 0:
            mins = int(self.survival_time_seconds // 60)
            lines.append(f"Survival: {mins} min")

        if not minimal:
            if self.assists:
                lines.append(f"Assists: {self.assists}")
            if self.current_score is not None:
                lines.append(f"Score: {self.current_score}")
            if self.objective_progress is not None:
                lines.append(f"Objective Progress: {self.objective_progress}")
            if self.current_location:
                lines.append(f"Location: {self.current_location}")
            if self.current_configuration:
                lines.append(f"Configuration: {self.current_configuration}")

        return "\n".join(lines)


class ProcessGameEventRequest(BaseModel):
    event_type: str = Field(description="kill, death, assist, objective, location_change, round_result, match_result, configuration_change")
    session_id: Optional[str] = Field(default=None, description="Optional target session ID")
    timestamp: Optional[Union[datetime, str]] = Field(default=None, description="Event timestamp")
    details: Dict[str, Any] = Field(default_factory=dict, description="Event telemetry details")

# =====================================================================
# PHASE 10: PERFORMANCE PATTERN ENGINE MODELS
# =====================================================================

class PerformancePattern(BaseModel):
    """
    Phase 10: Performance Pattern.
    Identifies repeated performance patterns across multiple stored sessions.
    Strictly requires >= 2 observations before calling anything a pattern.
    Separates: FACT, PATTERN, INTERPRETATION.
    Never claims causation unless stored data establishes it.
    """
    pattern_id: str = Field(default_factory=lambda: f"pat-{uuid.uuid4().hex[:8]}", description="Unique pattern identifier")
    pattern_type: str = Field(description="repeated_deaths, repeated_map_problems, repeated_positioning_issues, configuration_correlations, session_duration_patterns, performance_consistency, recurring_successful_actions, recurring_unsuccessful_actions")
    game: Optional[str] = Field(default=None, description="Game title")
    fact: str = Field(description="Direct, non-speculative factual observation from sessions")
    pattern: str = Field(description="Aggregated pattern discovered across multiple sessions")
    interpretation: str = Field(description="Cautious interpretation without unproven causation")
    evidence_session_ids: List[Union[str, int]] = Field(description="IDs of sessions supporting this pattern (minimum 2)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    created_at: Optional[str] = None

    model_config = {
        "extra": "allow"
    }

    @field_validator("evidence_session_ids")
    @classmethod
    def validate_minimum_evidence(cls, val: List[Union[str, int]]) -> List[Union[str, int]]:
        if len(val) < 2:
            raise ValueError(f"Never call something a pattern based on one session. Minimum 2 sessions required (got {len(val)}).")
        return val

    def format_display(self, include_evidence: bool = False) -> str:
        """
        Formats display matching Phase 10 specification:
        FACT:
        Player died at similar locations in three recorded sessions.

        PATTERN:
        Repeated deaths occurred in similar areas.

        INTERPRETATION:
        These locations may deserve review.
        """
        lines = [
            "FACT:",
            self.fact,
            "",
            "PATTERN:",
            self.pattern,
            "",
            "INTERPRETATION:",
            self.interpretation
        ]
        if include_evidence and self.evidence_session_ids:
            lines.append("")
            lines.append("Evidence:")
            for sid in self.evidence_session_ids:
                s_str = str(sid).strip()
                if not s_str.startswith("#"):
                    s_str = f"#{s_str}"
                lines.append(f"Session {s_str}")
        return "\n".join(lines)


class PerformancePatternResponse(BaseModel):
    patterns: List[PerformancePattern] = Field(default_factory=list, description="List of identified performance patterns")
    total_patterns: int = Field(default=0, description="Count of identified patterns")
    status: str = Field(default="success", description="'success' or 'insufficient_data'")
    message: str = Field(default="Patterns identified from stored sessions.", description="Status message")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="All session IDs used as evidence")

    model_config = {
        "extra": "allow"
    }



class AIMemoryRecord(BaseModel):
    """
    Structured AI Memory Record representing processed session intelligence.
    Stores episodic memory (and conditional pattern/player profile memories),
    strictly isolated from raw session telemetry.
    """
    id: Optional[int] = None
    session_id: Optional[Union[str, int]] = None
    memory_type: str = Field(default="episodic", description="'episodic', 'pattern', 'player_profile'")
    ai_summary: str = Field(description="Structured session summary strictly derived from factual telemetry")
    ai_insights: List[str] = Field(default_factory=list, description="Data-supported strategic observations")
    memory_text: str = Field(description="Human-readable memory text representation")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions supporting this memory")
    ai_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score of AI extraction")
    ai_model_version: str = Field(default="gaming-second-brain-ai-v1", description="Model version tag")
    created_at: Optional[str] = None
    facts: Dict[str, Any] = Field(default_factory=dict, description="Extracted factual telemetry")
    notable_performance: Optional[str] = None

    model_config = {
        "extra": "allow"
    }


class AIMemoryProcessingResult(BaseModel):
    """
    Output payload of the Phase 5 AI Memory Engine.
    Contains the raw session, generated episodic memory, and conditional historical memories.
    """
    raw_session: Dict[str, Any]
    episodic_memory: AIMemoryRecord
    pattern_memory: Optional[AIMemoryRecord] = None
    player_profile_memory: Optional[AIMemoryRecord] = None
    historical_sessions_count: int = 0
    message: str = "Session processed into AI memory."

    model_config = {
        "extra": "allow"
    }

# =====================================================================
# PHASE 6: PLAYER PROFILE MEMORY MODELS
# =====================================================================

class ProfileFact(BaseModel):
    """
    Represents an individual long-term player profile preference or habit.
    Requires multiple session evidence before being determined.
    """
    value: str = Field(description="Derived preference value, or 'Not enough data to determine this.'")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions supporting this fact")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    status: str = Field(default="insufficient_data", description="'determined' or 'insufficient_data'")

    model_config = {
        "extra": "allow"
    }


class PlayerProfile(BaseModel):
    """
    Lightweight Long-Term Player Profile built from multiple sessions and episodic memories.
    Tracks preferences with explicit evidence session IDs.
    """
    preferred_game: ProfileFact
    frequently_played_maps: ProfileFact
    frequently_used_configurations: ProfileFact
    preferred_session_duration: ProfileFact
    recurring_strengths: ProfileFact
    recurring_improvement_areas: ProfileFact
    total_sessions_analyzed: int = 0
    last_updated: Optional[str] = None

    model_config = {
        "extra": "allow"
    }


# =====================================================================
# PHASE 7: NATURAL LANGUAGE SEARCH MODELS
# =====================================================================

class StructuredQuery(BaseModel):
    """
    Structured query representation derived from natural language question.
    Contains intent, filters, sort order, limits, metrics, and comparison flags.
    """
    intent: str = Field(description="Detected query intent (e.g. best_session, worst_session, recent_performance, map_performance, configuration_performance, improvement, session_duration, performance_comparison)")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Criteria filters (e.g. game, map, configuration)")
    sort: Optional[str] = Field(default=None, description="Sorting direction (e.g. 'kd_ratio DESC', 'started_at DESC')")
    limit: int = Field(default=5, ge=1, description="Maximum sessions to inspect")
    required_metrics: List[str] = Field(default_factory=list, description="Telemetry metrics needed to answer the question")
    comparison_needed: bool = Field(default=False, description="Whether cross-session comparison is required")
    target_entity: Optional[str] = Field(default=None, description="Specific target entity if requested (e.g. 'Ascent', 'Phantom')")

    model_config = {
        "extra": "allow"
    }


class NaturalLanguageSearchRequest(BaseModel):
    query: str = Field(description="Natural language question about stored gaming sessions")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Optional pre-filters")


class NaturalLanguageSearchResponse(BaseModel):
    query: str = Field(description="Original natural language query")
    structured_query: StructuredQuery = Field(description="Generated structured query")
    answer: str = Field(description="Evidence-backed explanation or 'Not enough data to determine this.'")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="Session IDs providing concrete evidence")
    evidence_sessions: List[Dict[str, Any]] = Field(default_factory=list, description="Session telemetry used in evidence")
    metrics_used: Dict[str, Any] = Field(default_factory=dict, description="Calculated statistics or values")
    status: str = Field(default="answered", description="'answered' or 'insufficient_data'")

    model_config = {
        "extra": "allow"
    }


# =====================================================================
# PHASE 8: CROSS-SESSION ANALYSIS MODELS
# =====================================================================

class CrossSessionAnalysisResult(BaseModel):
    """
    Evidence-backed cross-session pattern discovery.
    Strictly distinguishes between:
    - FACT: concrete individual session observations
    - PATTERN: aggregated statistical discovery across multiple sessions
    - AI INTERPRETATION: data-supported synthesis without invented causation
    """
    question: str = Field(description="The analytical question asked")
    analysis_type: str = Field(description="'improving', 'best_vs_worst', 'map_performance', 'configuration_performance', 'duration_vs_performance'")
    facts: List[str] = Field(default_factory=list, description="Concrete observed facts from individual sessions")
    pattern: str = Field(description="Cross-session pattern discovered across multiple sessions")
    interpretation: str = Field(description="AI interpretation with strict causation guard")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions supporting this pattern")
    status: str = Field(default="determined", description="'determined' or 'insufficient_data'")
    metrics_summary: Dict[str, Any] = Field(default_factory=dict, description="Underlying quantitative metrics")

    model_config = {
        "extra": "allow"
    }


class CrossSessionAnalysisRequest(BaseModel):
    question: str = Field(description="Question to analyze across sessions")


# =====================================================================
# PHASE 9: AI GAMING PLAN MODELS
# =====================================================================

class AIGamingPlan(BaseModel):
    """
    Phase 8: AI Gaming Plan.
    Personalized plan for the player's next gaming session.
    Derived strictly from:
    - player profile
    - previous sessions
    - performance metrics
    - detected game
    - detected map
    - AI tasks
    - historical patterns
    """
    plan_id: str = Field(description="Unique plan identifier")
    game: str = Field(description="Target game title")
    map: Optional[str] = Field(default=None, description="Detected or target map")
    goal: str = Field(description="Target objective for the session (e.g. 'Improve consistency')")
    focus_area: str = Field(description="Key mechanical/tactical focus area (e.g. 'Crosshair placement')")
    recommended_duration: str = Field(description="Recommended total duration (e.g. '75 minutes')")
    warmup: str = Field(description="Warmup routine (e.g. '10 minutes')")
    practice: Optional[str] = Field(default="15 minutes", description="Practice duration summary")
    gameplay: Optional[str] = Field(default="40 minutes", description="Gameplay duration summary")
    review: Optional[str] = Field(default="10 minutes", description="Review duration summary")
    practice_tasks: List[str] = Field(default_factory=list, description="Dedicated practice drills (e.g. '20 minutes')")
    gameplay_tasks: List[str] = Field(default_factory=list, description="In-match focus rules (e.g. '40 minutes')")
    review_tasks: List[str] = Field(default_factory=list, description="Post-match debrief tasks (e.g. '5 minutes')")
    metrics_to_track: List[str] = Field(default_factory=lambda: ["K/D", "Deaths", "Accuracy", "Result"], description="Metrics to track")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions supporting this plan")
    ai_reasoning: str = Field(description="Explanation of why this plan was selected based on stored data")
    status: str = Field(default="ready", description="'ready' or 'insufficient_data'")
    created_at: Optional[str] = None

    model_config = {
        "extra": "allow"
    }

    def format_display(self, leading_space: bool = True) -> str:
        """
        Formats normalized display matching Phase 8 specification:
         AI GAMING PLAN

        Game: BGMI
        Map: Erangel

        Goal:
        Improve survival and rotation decisions.

        Warm-up:
        10 minutes

        Practice:
        15 minutes

        Gameplay:
        40 minutes

        Review:
        10 minutes

        Track:
        Survival time
        Deaths
        Rotation decisions
        Final placement

        Evidence:
        Session #12
        Session #16
        Session #18
        """
        header = " AI GAMING PLAN" if leading_space else "AI GAMING PLAN"
        lines = [header, ""]
        if self.game:
            lines.append(f"Game: {self.game}")
        if self.map:
            lines.append(f"Map: {self.map}")
        lines.append("")
        lines.append("Goal:")
        lines.append(self.goal)
        lines.append("")
        lines.append("Warm-up:")
        warmup_str = self.warmup
        if ":" in warmup_str:
            warmup_str = warmup_str.split(":")[0].strip()
        lines.append(warmup_str)
        lines.append("")
        lines.append("Practice:")
        practice_str = self.practice
        if not practice_str:
            if self.practice_tasks:
                first_p = self.practice_tasks[0]
                practice_str = first_p.split(":")[0].strip() if ":" in first_p else first_p
            else:
                practice_str = "15 minutes"
        lines.append(practice_str)
        lines.append("")
        lines.append("Gameplay:")
        gameplay_str = self.gameplay
        if not gameplay_str:
            if self.gameplay_tasks:
                first_g = self.gameplay_tasks[0]
                gameplay_str = first_g.split(":")[0].strip() if ":" in first_g else first_g
            else:
                gameplay_str = "40 minutes"
        lines.append(gameplay_str)
        lines.append("")
        lines.append("Review:")
        review_str = self.review
        if not review_str:
            if self.review_tasks:
                first_r = self.review_tasks[0]
                review_str = first_r.split(":")[0].strip() if ":" in first_r else first_r
            else:
                review_str = "10 minutes"
        lines.append(review_str)
        lines.append("")
        lines.append("Track:")
        if self.metrics_to_track:
            for m in self.metrics_to_track:
                lines.append(str(m))
        else:
            lines.append("None")
        lines.append("")
        lines.append("Evidence:")
        if self.evidence_session_ids:
            for sid in self.evidence_session_ids:
                s_str = str(sid).strip()
                if not s_str.startswith("#"):
                    s_str = f"#{s_str}"
                lines.append(f"Session {s_str}")
        else:
            lines.append("None")
        return "\n".join(lines)


class CreateGamingPlanRequest(BaseModel):
    game: Optional[str] = Field(default=None, description="Optional target game filter")
    map: Optional[str] = Field(default=None, description="Optional target map filter")
    custom_goal: Optional[str] = Field(default=None, description="Optional user-requested custom goal")


# =====================================================================
# PHASE 12: ADAPTIVE PLANNING MODELS
# =====================================================================

class TaskEvaluationResult(BaseModel):
    """
    Phase 12: Evaluation of an individual task in a Gaming Plan.
    Determines status: 'completed', 'partially completed', 'not completed', 'insufficient data'.
    Provides non-causal AI statement and observed metrics.
    """
    task_id: Optional[str] = Field(default=None, description="Identifier of the task if available")
    task_description: str = Field(description="The task description being evaluated")
    category: Optional[str] = Field(default=None, description="Category of task, e.g. positioning, aim, duration, review")
    status: str = Field(description="'completed', 'partially completed', 'not completed', 'insufficient data'")
    evidence: str = Field(description="Concrete factual evidence from the session and history")
    ai_statement: str = Field(description="Causation-guarded statement without claiming practice caused improvement")
    metrics_observed: Dict[str, Any] = Field(default_factory=dict, description="Observed quantitative values for this task")

    model_config = {
        "extra": "allow"
    }


class PlanEvaluation(BaseModel):
    """
    Phase 12: Structured comparison of previous gaming plan vs actual resulting session.
    Evaluates:
    - goal completed
    - performance change
    - focus-area results
    - session duration
    - relevant metrics
    - plan effectiveness
    - task evaluations (completed, partially completed, not completed, insufficient data)
    - comparison of actual performance with historical performance
    - causation-guarded AI evaluation
    """
    evaluation_id: str = Field(description="Unique evaluation identifier")
    plan_id: str = Field(description="ID of the previous gaming plan being evaluated")
    session_id: str = Field(description="ID of the newly completed session")
    goal_completed: bool = Field(description="Whether the planned goal was achieved in the session")
    performance_change: str = Field(description="Observed change in performance vs previous session/baseline")
    focus_area_result: str = Field(description="Evidence-based observation of the targeted focus area")
    session_duration: str = Field(description="Comparison of planned duration vs actual duration")
    relevant_metrics: Dict[str, Any] = Field(default_factory=dict, description="Expected vs actual metrics tracked")
    plan_effectiveness: str = Field(description="'effective', 'partially_effective', 'neutral', 'ineffective'")
    ai_evaluation: str = Field(description="Neutral, evidence-based assessment with strict causation guard")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of sessions supporting this evaluation")
    task_evaluations: List[TaskEvaluationResult] = Field(default_factory=list, description="Status and evidence for each task")
    performance_comparison: Dict[str, Any] = Field(default_factory=dict, description="Comparison of actual performance with historical performance")
    memory_updated: bool = Field(default=False, description="Whether player memory was updated with this evaluation")
    created_at: Optional[str] = None

    model_config = {
        "extra": "allow"
    }


class AdaptivePlanCycleResponse(BaseModel):
    """
    End-to-end Phase 12 Adaptive Gaming Plan Cycle result.
    Flow: Previous Plan -> Player completes session -> New Session Data
          -> Compare with previous sessions -> Evaluate task results
          -> Update player memory -> Create next Gaming Plan.
    """
    evaluation: PlanEvaluation
    next_plan: AIGamingPlan
    historical_sessions_count: int
    memory_updated: bool = True
    message: str = "Adaptive cycle complete: Evaluated previous plan, updated memory, and generated next plan."

    model_config = {
        "extra": "allow"
    }


class AdaptivePlanEvaluationRequest(BaseModel):
    plan_id: Optional[str] = Field(default=None, description="Optional plan ID to evaluate (defaults to latest)")
    session_id: Optional[Union[str, int]] = Field(default=None, description="Optional session ID to evaluate against (defaults to latest)")
    session_data: Optional[Dict[str, Any]] = Field(default=None, description="Optional new session payload to record and evaluate")


# =====================================================================
# PHASE 11: CROSS-SESSION INTELLIGENCE MODELS
# =====================================================================

class CrossSessionIntelligenceResponse(BaseModel):
    """
    Phase 11: Cross-Session Intelligence Response.
    
    Adheres strictly to the four-part response structure:
    - ANSWER: Direct, evidence-backed conclusion referencing stored sessions
    - EVIDENCE: References to stored session data points
    - INSIGHT: Observational synthesis with strict causation guard
    - RECOMMENDATION: Actionable, evidence-aligned next step
    
    Every answer references stored sessions.
    Never invents statistics or infers unproven causation.
    Returns 'Not enough data to determine this.' when data is insufficient.
    """
    question: str = Field(description="The analytical question asked")
    analysis_type: str = Field(description="Internal category of question")
    answer: str = Field(description="Direct conclusion or 'Not enough data to determine this.'")
    evidence: List[str] = Field(default_factory=list, description="Factual session observations supporting the answer")
    insight: str = Field(description="Analytical insight adhering to the causation guard")
    recommendation: str = Field(description="Actionable guidance aligned with the evidence")
    evidence_session_ids: List[Union[str, int]] = Field(default_factory=list, description="IDs of all stored sessions referenced")
    status: str = Field(default="answered", description="'answered' or 'insufficient_data'")
    metrics_summary: Dict[str, Any] = Field(default_factory=dict, description="Quantitative values calculated from session data")
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict, description="Information on optimized retrieval footprint")

    model_config = {
        "extra": "allow"
    }

    def format_display(self) -> str:
        """
        Formats the output according to the Phase 11 Response Structure specification:
        
        ANSWER
        ...
        
        EVIDENCE
        ...
        
        INSIGHT
        ...
        
        RECOMMENDATION
        ...
        """
        if self.status == "insufficient_data":
            return (
                "ANSWER:\n"
                f"{self.answer}\n\n"
                "EVIDENCE:\n"
                f"{self.answer}\n\n"
                "INSIGHT:\n"
                f"{self.answer}\n\n"
                "RECOMMENDATION:\n"
                f"{self.recommendation}"
            )
        ev_lines = "\n".join(f"- {e}" for e in self.evidence) if self.evidence else "- None recorded."
        return (
            f"ANSWER:\n{self.answer}\n\n"
            f"EVIDENCE:\n{ev_lines}\n\n"
            f"INSIGHT:\n{self.insight}\n\n"
            f"RECOMMENDATION:\n{self.recommendation}"
        )


class CrossSessionIntelligenceRequest(BaseModel):
    """
    Request model for Cross-Session Intelligence queries.
    """
    question: str = Field(description="Natural language question for cross-session intelligence")
    game: Optional[str] = Field(default=None, description="Optional game filter")
    limit: Optional[int] = Field(default=None, description="Optional maximum retrieval limit")


# =====================================================================
# PHASE 13: FAST PLAN & HACKATHON DASHBOARD MODELS
# =====================================================================

class FastPlanEvidenceDetail(BaseModel):
    session_id: str
    fact: str
    metric: Optional[str] = None

class FastPlanResponse(BaseModel):
    plan_id: str
    game: str
    map: str
    goal: str
    focus_area: str
    duration: int = 60
    warmup: int = 10
    gameplay: int = 40
    review: int = 10
    strategy: List[str]
    evidence_session_ids: List[str] = []
    evidence_details: List[FastPlanEvidenceDetail] = []
    is_generic: bool = False
    notice_title: Optional[str] = None
    notice_message: Optional[str] = None
    plan_label: str = "AI PRE-GAME PLAN"
    tasks: List[Dict[str, Any]] = []
    generation_time_ms: float = 0.0
    created_at: Optional[str] = None

class FastPlanRequest(BaseModel):
    game: str
    map: Optional[str] = None
    game_mode: Optional[str] = None

class DashboardCompleteSessionRequest(BaseModel):
    session_id: Optional[str] = None
    game: str
    map: Optional[str] = None
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    score: Optional[str] = None
    duration_mins: int = 30
    result: Optional[str] = "Win"
    plan_id: Optional[str] = None
    player_notes: Optional[str] = None


# =====================================================================
# GAME ADAPTER & PIPELINE MODELS (Game -> Game Adapter -> Detection -> Metrics -> Tasks -> Planning)
# =====================================================================

class GameAdapterInfo(BaseModel):
    game_name: str
    aliases: List[str] = Field(default_factory=list)
    genre: str = "General"
    supported_modes: List[str] = Field(default_factory=list)
    supported_maps: List[str] = Field(default_factory=list)
    specialized_metrics: List[str] = Field(default_factory=list)
    warmup_routines: List[str] = Field(default_factory=list)

class PipelineStageResult(BaseModel):
    stage: str  # "game", "game_adapter", "detection", "metrics", "tasks", "planning"
    status: str = "success"  # "success", "warning", "info"
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)

class PipelineRunRequest(BaseModel):
    game: str
    map: Optional[str] = None
    mode: Optional[str] = None
    raw_events: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[Union[str, int]] = None
    include_stored_history: bool = True

class PipelineRunResponse(BaseModel):
    game: str
    map: Optional[str] = None
    mode: Optional[str] = None
    adapter_used: str
    detection: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    plan: Dict[str, Any] = Field(default_factory=dict)
    stages: List[PipelineStageResult] = Field(default_factory=list)
    pipeline_duration_ms: float = 0.0


# =====================================================================
# PRE-GAME INTELLIGENCE SYSTEM MODELS
# =====================================================================

class PlayerExperienceProfile(BaseModel):
    experience_level: str = Field(description="'NEW PLAYER', 'RETURNING PLAYER', 'EXPERIENCED PLAYER', or 'INSUFFICIENT_DATA'")
    total_sessions: int = Field(default=0, description="Total sessions across all games in database")
    sessions_in_current_game: int = Field(default=0, description="Stored sessions specifically for current game")
    recent_sessions: List[Dict[str, Any]] = Field(default_factory=list, description="Recent sessions for current game")
    data_confidence: float = Field(default=1.0, description="Confidence in experience determination (0.0 to 1.0)")
    last_played_at: Optional[str] = Field(default=None, description="Timestamp of most recent session")
    last_session_kd: Optional[float] = Field(default=None, description="K/D ratio of the last session")
    strongest_kd: Optional[float] = Field(default=None, description="Highest recorded K/D ratio in history")
    most_played_map: Optional[str] = Field(default=None, description="Map with the most played sessions")
    welcome_header: str = Field(default="WELCOME", description="Greeting header (e.g. WELCOME, WELCOME BACK, PLAYER PROFILE)")
    message: str = Field(default="", description="Detailed formatted greeting/profile message")
    data_source: str = Field(default="PERSONAL HISTORY", description="Source attribution label")

class MapAreaIntelligence(BaseModel):
    area_id: str
    map: str
    area_name: str
    historical_activity: str = Field(default="Medium", description="Low, Medium, High")
    historical_enemy_density: str = Field(default="Medium", description="Low, Medium, High")
    loot_quality: str = Field(default="Medium", description="Low, Medium, High, Very High")
    weapon_availability: str = Field(default="Standard", description="Low, Medium, High, Standard")
    vehicle_availability: str = Field(default="Medium", description="None, Low, Medium, High")
    cover_level: str = Field(default="Medium", description="Low, Medium, High")
    risk_level: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH")
    evidence: Union[str, List[str]] = Field(default="Historical map telemetry", description="Evidence supporting area classification")
    confidence: float = Field(default=0.9, description="Confidence score")
    data_source: str = Field(default="HISTORICAL GAME DATA", description="Traceable data source label")
    coordinates: Optional[Dict[str, float]] = Field(default=None, description="Relative coordinates (x, y) 0-100% on map canvas")
    is_objective: bool = Field(default=False, description="Whether this area contains key strategic objective")
    is_choke_point: bool = Field(default=False, description="Whether this area is a common choke point")

class WeaponIntelligence(BaseModel):
    weapon_name: str
    weapon_type: str = Field(description="Assault Rifle, SMG, Sniper Rifle, DMR, Shotgun, Pistol, Sidearm")
    damage: float
    range: Union[float, str]
    recoil: Union[float, str]
    fire_rate: Union[float, str]
    accuracy: Union[float, str]
    attachment_options: List[str] = Field(default_factory=list)
    availability: str = Field(default="Standard Loot")
    player_usage: Optional[int] = Field(default=None, description="Number of sessions player used this weapon")
    player_performance: Optional[Dict[str, Any]] = Field(default=None, description="Average K/D, kills, win rate with weapon")
    confidence: float = Field(default=0.95)
    data_source: str = Field(default="GAME DATA", description="GAME DATA or PERSONAL HISTORY")

class WeaponRecommendation(BaseModel):
    primary_weapon: str
    primary_reason: str
    secondary_weapon: str
    secondary_reason: str
    confidence: str = Field(default="Medium", description="High, Medium, Low")
    data_source: str = Field(default="PERSONAL HISTORY", description="PERSONAL HISTORY or GENERAL GAME INFORMATION")
    personal_history_found: bool = Field(default=False)
    explanation: Optional[str] = None

class MapLoadoutStrategy(BaseModel):
    map: str
    starting_area: str
    recommended_weapon_type: str
    reason: str
    evidence: str = Field(default="Map data + your previous sessions")
    data_source: str = Field(default="GAME DATA + PERSONAL HISTORY")

class RotationIntelligence(BaseModel):
    starting_area: str
    mid_game_route: str
    destination: str
    historical_risk: str = Field(default="Medium", description="Low, Medium, High")
    available_cover: str = Field(default="Covered Route")
    vehicle_availability: str = Field(default="Medium")
    distance: str = Field(default="Moderate")
    safe_zone_info: Optional[str] = Field(default=None, description="Safe zone info when available")
    reason: str = Field(default="Historically lower-risk route based on available data.")
    evidence: Union[str, List[str]] = Field(default="Historical route telemetry")
    data_source: str = Field(default="HISTORICAL GAME DATA")

class PreGameAdaptivePlan(BaseModel):
    plan_type: str = Field(description="'BEGINNER PLAN', 'RETURNING PLAYER PLAN', 'EXPERIENCED PLAYER PLAN'")
    focus: str
    start_area: str
    priority: str
    avoid: Optional[str] = None
    review: Optional[str] = None
    strategy_steps: List[str] = Field(default_factory=list)
    data_source: str = Field(default="AI ANALYSIS")

class PreGameIntelligenceResponse(BaseModel):
    player_experience: PlayerExperienceProfile
    game_detection: GameDetectionResult
    map_detection: MapDetectionResult
    map_areas: List[MapAreaIntelligence] = Field(default_factory=list)
    low_enemy_areas: List[MapAreaIntelligence] = Field(default_factory=list)
    high_activity_areas: List[MapAreaIntelligence] = Field(default_factory=list)
    recommended_start: Optional[Dict[str, Any]] = None
    avoid_areas: List[str] = Field(default_factory=list)
    weapon_recommendation: Optional[WeaponRecommendation] = None
    map_loadout_strategy: Optional[MapLoadoutStrategy] = None
    rotation_plan: Optional[RotationIntelligence] = None
    adaptive_plan: Optional[PreGameAdaptivePlan] = None
    data_sources: Dict[str, str] = Field(default_factory=dict)
    generation_time_ms: float = 0.0
    status: str = "PRE-GAME INTELLIGENCE READY"
    player_greeting: str = ""
    created_at: Optional[str] = None

class PreGameIntelligenceRequest(BaseModel):
    game: str
    map: Optional[str] = None
    game_mode: Optional[str] = None
    detection_source: Optional[str] = "simulated"
    player_name: Optional[str] = "Manoj"
    include_ai: bool = True










