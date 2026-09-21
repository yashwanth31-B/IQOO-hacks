from typing import Optional, Dict, Any, Union, List, Set, Callable
from datetime import datetime
from abc import ABC, abstractmethod

from app.models import (
    GameState,
    GameStateSnapshot,
    StateTransitionRecord,
    StateUpdateRequest
)


# =====================================================================
# PHASE 5: GAME STATE EXCEPTIONS
# =====================================================================

class GameStateError(Exception):
    """Base exception for game state layer."""
    pass


class GameStateTransitionError(GameStateError):
    """Raised when an invalid state transition is attempted in strict mode."""
    pass


# =====================================================================
# PHASE 5: VALID STATE TRANSITION MATRIX
# =====================================================================

DEFAULT_VALID_TRANSITIONS: Dict[GameState, Set[GameState]] = {
    GameState.UNKNOWN: {
        GameState.LOBBY,
        GameState.LOADING,
        GameState.MATCH_STARTED,
        GameState.ACTIVE_GAMEPLAY,
        GameState.UNKNOWN
    },
    GameState.LOBBY: {
        GameState.LOADING,
        GameState.MATCH_STARTED,
        GameState.UNKNOWN,
        GameState.LOBBY
    },
    GameState.LOADING: {
        GameState.MATCH_STARTED,
        GameState.ACTIVE_GAMEPLAY,
        GameState.LOBBY,
        GameState.UNKNOWN
    },
    GameState.MATCH_STARTED: {
        GameState.ROUND_STARTED,
        GameState.ACTIVE_GAMEPLAY,
        GameState.LOADING,
        GameState.MATCH_FINISHED,
        GameState.UNKNOWN
    },
    GameState.ROUND_STARTED: {
        GameState.ACTIVE_GAMEPLAY,
        GameState.ROUND_FINISHED,
        GameState.MATCH_FINISHED,
        GameState.UNKNOWN
    },
    GameState.ACTIVE_GAMEPLAY: {
        GameState.ROUND_FINISHED,
        GameState.ROUND_STARTED,
        GameState.MATCH_FINISHED,
        GameState.LOBBY,
        GameState.UNKNOWN
    },
    GameState.ROUND_FINISHED: {
        GameState.ROUND_STARTED,
        GameState.ACTIVE_GAMEPLAY,
        GameState.MATCH_FINISHED,
        GameState.LOBBY,
        GameState.UNKNOWN
    },
    GameState.MATCH_FINISHED: {
        GameState.LOBBY,
        GameState.LOADING,
        GameState.MATCH_STARTED,
        GameState.UNKNOWN
    }
}


# =====================================================================
# PHASE 5: GAME SPECIFIC PROFILES
# Different games may use different states.
# =====================================================================

class GameProfile:
    """
    Profile defining state machine rules and raw mappings for specific titles.
    """
    def __init__(
        self,
        name: str,
        supported_states: Set[GameState],
        transitions: Optional[Dict[GameState, Set[GameState]]] = None,
        raw_mappings: Optional[Dict[str, GameState]] = None,
        is_round_based: bool = False
    ):
        self.name = name
        self.supported_states = supported_states
        self.transitions = transitions or DEFAULT_VALID_TRANSITIONS
        self.raw_mappings = raw_mappings or {}
        self.is_round_based = is_round_based

    def is_state_supported(self, state: GameState) -> bool:
        return state in self.supported_states

    def is_transition_valid(self, from_state: GameState, to_state: GameState) -> bool:
        if from_state == to_state:
            return True
        allowed = self.transitions.get(from_state, set())
        return to_state in allowed

    def normalize_raw_state(self, raw: str) -> GameState:
        cleaned = raw.strip().lower()
        if cleaned in self.raw_mappings:
            return self.raw_mappings[cleaned]
        return GameState.from_string(raw)


# Game Profiles registry
GAME_PROFILES: Dict[str, GameProfile] = {
    # Round-based tactical shooter: uses round_started & round_finished
    "Valorant": GameProfile(
        name="Valorant",
        supported_states={
            GameState.LOBBY,
            GameState.LOADING,
            GameState.MATCH_STARTED,
            GameState.ROUND_STARTED,
            GameState.ACTIVE_GAMEPLAY,
            GameState.ROUND_FINISHED,
            GameState.MATCH_FINISHED,
            GameState.UNKNOWN
        },
        raw_mappings={
            "buy_phase": GameState.ROUND_STARTED,
            "in_round": GameState.ACTIVE_GAMEPLAY,
            "spike_defused": GameState.ROUND_FINISHED,
            "post_round": GameState.ROUND_FINISHED,
            "agent_select": GameState.LOADING
        },
        is_round_based=True
    ),
    "Counter-Strike 2": GameProfile(
        name="Counter-Strike 2",
        supported_states={
            GameState.LOBBY,
            GameState.LOADING,
            GameState.MATCH_STARTED,
            GameState.ROUND_STARTED,
            GameState.ACTIVE_GAMEPLAY,
            GameState.ROUND_FINISHED,
            GameState.MATCH_FINISHED,
            GameState.UNKNOWN
        },
        raw_mappings={
            "freezetime": GameState.ROUND_STARTED,
            "live": GameState.ACTIVE_GAMEPLAY,
            "round_end": GameState.ROUND_FINISHED
        },
        is_round_based=True
    ),
    # Battle Royale games: Continuous match flow (no individual round resets)
    "BGMI": GameProfile(
        name="BGMI",
        supported_states={
            GameState.LOBBY,
            GameState.LOADING,
            GameState.MATCH_STARTED,
            GameState.ACTIVE_GAMEPLAY,
            GameState.MATCH_FINISHED,
            GameState.UNKNOWN
        },
        raw_mappings={
            "spawn_island": GameState.LOADING,
            "in_plane": GameState.MATCH_STARTED,
            "parachuting": GameState.ACTIVE_GAMEPLAY,
            "on_ground": GameState.ACTIVE_GAMEPLAY,
            "chicken_dinner": GameState.MATCH_FINISHED,
            "eliminated": GameState.MATCH_FINISHED
        },
        is_round_based=False
    ),
    "Free Fire MAX": GameProfile(
        name="Free Fire MAX",
        supported_states={
            GameState.LOBBY,
            GameState.LOADING,
            GameState.MATCH_STARTED,
            GameState.ACTIVE_GAMEPLAY,
            GameState.MATCH_FINISHED,
            GameState.UNKNOWN
        },
        raw_mappings={
            "waiting_area": GameState.LOADING,
            "skydive": GameState.ACTIVE_GAMEPLAY,
            "booyah": GameState.MATCH_FINISHED
        },
        is_round_based=False
    ),
    "Call of Duty Mobile": GameProfile(
        name="Call of Duty Mobile",
        supported_states={
            GameState.LOBBY,
            GameState.LOADING,
            GameState.MATCH_STARTED,
            GameState.ROUND_STARTED,
            GameState.ACTIVE_GAMEPLAY,
            GameState.ROUND_FINISHED,
            GameState.MATCH_FINISHED,
            GameState.UNKNOWN
        },
        is_round_based=True
    ),
    "Chess": GameProfile(
        name="Chess",
        supported_states={
            GameState.LOBBY,
            GameState.MATCH_STARTED,
            GameState.ACTIVE_GAMEPLAY,
            GameState.MATCH_FINISHED,
            GameState.UNKNOWN
        },
        raw_mappings={
            "opening": GameState.ACTIVE_GAMEPLAY,
            "middlegame": GameState.ACTIVE_GAMEPLAY,
            "endgame": GameState.ACTIVE_GAMEPLAY,
            "checkmate": GameState.MATCH_FINISHED,
            "stalemate": GameState.MATCH_FINISHED
        },
        is_round_based=False
    )
}

# Aliases
GAME_PROFILES["BGMI / PUBG Mobile"] = GAME_PROFILES["BGMI"]
GAME_PROFILES["PUBG Mobile"] = GAME_PROFILES["BGMI"]
GAME_PROFILES["Free Fire"] = GAME_PROFILES["Free Fire MAX"]
GAME_PROFILES["CS2"] = GAME_PROFILES["Counter-Strike 2"]


# Default generic fallback profile
DEFAULT_GENERIC_PROFILE = GameProfile(
    name="Generic",
    supported_states=set(GameState),
    transitions=DEFAULT_VALID_TRANSITIONS,
    is_round_based=False
)


# =====================================================================
# PHASE 5: STATE PROVIDER INTERFACES
# Architecture allows telemetry, logs, APIs, or CV to provide state.
# =====================================================================

class BaseGameStateProvider(ABC):
    """Abstract interface for game state providers."""
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Returns provider identifier: 'manual', 'simulated', 'telemetry', 'game_log', 'api', 'cv'."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is currently connected and active."""
        pass

    @abstractmethod
    def read_state(self) -> Optional[GameStateSnapshot]:
        """Fetches the latest detected game state snapshot, or None."""
        pass


class ManualGameStateProvider(BaseGameStateProvider):
    """Manual state updates directly from player input."""
    def __init__(self):
        self.last_snapshot: Optional[GameStateSnapshot] = None

    def get_source_name(self) -> str:
        return "manual"

    def is_available(self) -> bool:
        return True

    def read_state(self) -> Optional[GameStateSnapshot]:
        return self.last_snapshot

    def set_state(self, snapshot: GameStateSnapshot) -> None:
        self.last_snapshot = snapshot


class SimulatedGameStateProvider(BaseGameStateProvider):
    """Simulated state updates for testing, development, and MVP."""
    def __init__(self):
        self.current_state: GameState = GameState.UNKNOWN
        self.current_snapshot: Optional[GameStateSnapshot] = None

    def get_source_name(self) -> str:
        return "simulated"

    def is_available(self) -> bool:
        return True

    def read_state(self) -> Optional[GameStateSnapshot]:
        return self.current_snapshot

    def set_state(self, snapshot: GameStateSnapshot) -> None:
        self.current_snapshot = snapshot
        self.current_state = snapshot.state


class TelemetryGameStateProvider(BaseGameStateProvider):
    """Extensible interface for direct game engine telemetry hooks."""
    def __init__(self, connected: bool = False):
        self._connected = connected

    def get_source_name(self) -> str:
        return "telemetry"

    def is_available(self) -> bool:
        return self._connected

    def read_state(self) -> Optional[GameStateSnapshot]:
        if not self._connected:
            return None
        return None


class LogGameStateProvider(BaseGameStateProvider):
    """Extensible interface for real-time game client log parsing."""
    def __init__(self, connected: bool = False):
        self._connected = connected

    def get_source_name(self) -> str:
        return "game_log"

    def is_available(self) -> bool:
        return self._connected

    def read_state(self) -> Optional[GameStateSnapshot]:
        if not self._connected:
            return None
        return None


class ApiGameStateProvider(BaseGameStateProvider):
    """Extensible interface for official game client or tournament APIs."""
    def __init__(self, connected: bool = False):
        self._connected = connected

    def get_source_name(self) -> str:
        return "api"

    def is_available(self) -> bool:
        return self._connected

    def read_state(self) -> Optional[GameStateSnapshot]:
        if not self._connected:
            return None
        return None


class VisionGameStateProvider(BaseGameStateProvider):
    """
    Extensible interface for future Computer Vision screen analysis.
    Requirement: 'Do not implement computer vision yet.'
    """
    def get_source_name(self) -> str:
        return "cv"

    def is_available(self) -> bool:
        # Strictly disabled for MVP
        return False

    def read_state(self) -> Optional[GameStateSnapshot]:
        raise NotImplementedError("Computer vision detection is not yet implemented for the MVP.")


# =====================================================================
# PHASE 5: GAME STATE DETECTOR & STATE MACHINE
# =====================================================================

class GameStateDetector:
    """
    Generic Game State Detection Layer.
    
    Responsibilities:
    - Maintains normalized internal game state.
    - Manages state machine and verifies transitions.
    - Tracks match time and transition history.
    - Accepts simulated and manual state inputs.
    - Supports game-specific state profiles.
    - Provides clean extension points for telemetry, logs, APIs, and CV.
    - Never invents state information (defaults to 'unknown' when absent).
    """

    def __init__(
        self,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        initial_state: GameState = GameState.UNKNOWN,
        strict_transitions: bool = False
    ):
        self.game = game
        self.map = map_name
        self.strict_transitions = strict_transitions
        self.history: List[StateTransitionRecord] = []
        self.listeners: List[Callable[[StateTransitionRecord], None]] = []

        # Providers registry
        self.manual_provider = ManualGameStateProvider()
        self.simulated_provider = SimulatedGameStateProvider()
        self.telemetry_provider = TelemetryGameStateProvider()
        self.log_provider = LogGameStateProvider()
        self.api_provider = ApiGameStateProvider()
        self.vision_provider = VisionGameStateProvider()

        # Initialize current snapshot
        self.current_snapshot = GameStateSnapshot(
            game=game,
            map=map_name,
            state=initial_state,
            match_time=None,
            confidence=1.0 if initial_state != GameState.UNKNOWN else 0.0,
            source="manual" if initial_state != GameState.UNKNOWN else "simulated"
        )

    def get_profile(self, game: Optional[str] = None) -> GameProfile:
        """Looks up game profile or returns generic fallback."""
        target_game = game or self.game
        if target_game and target_game in GAME_PROFILES:
            return GAME_PROFILES[target_game]
        return DEFAULT_GENERIC_PROFILE

    def get_supported_states(self, game: Optional[str] = None) -> Set[GameState]:
        """Returns set of supported states for the game."""
        return self.get_profile(game).supported_states

    def is_valid_transition(
        self,
        from_state: GameState,
        to_state: GameState,
        game: Optional[str] = None
    ) -> bool:
        """Validates state transition against game profile and transition matrix."""
        profile = self.get_profile(game)
        if not profile.is_state_supported(to_state):
            return False
        return profile.is_transition_valid(from_state, to_state)

    def transition_to(
        self,
        target_state: Union[GameState, str],
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        match_time: Optional[str] = None,
        match_time_seconds: Optional[float] = None,
        round_number: Optional[Union[int, str]] = None,
        source: str = "simulated",
        force: bool = False,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GameStateSnapshot:
        """
        Transitions game state to target_state.
        Validates transitions against matrix unless force=True.
        Logs transition history and notifies listeners.
        """
        normalized_target = GameState.from_string(target_state)
        current_state = self.current_snapshot.state
        active_game = game or self.game
        active_map = map_name or self.map

        # Validate transition
        is_valid = self.is_valid_transition(current_state, normalized_target, active_game)
        if not is_valid and self.strict_transitions and not force:
            raise GameStateTransitionError(
                f"Invalid state transition from '{current_state.value}' to '{normalized_target.value}' for game '{active_game}'."
            )

        # Calculate / format match_time string
        formatted_match_time = match_time
        if formatted_match_time is None and match_time_seconds is not None:
            mins = int(match_time_seconds // 60)
            secs = int(match_time_seconds % 60)
            formatted_match_time = f"{mins:02d}:{secs:02d}"
        elif formatted_match_time is None:
            formatted_match_time = self.current_snapshot.match_time

        # Update context
        if game:
            self.game = game
        if map_name:
            self.map = map_name

        new_snapshot = GameStateSnapshot(
            game=active_game,
            map=active_map,
            state=normalized_target,
            match_time=formatted_match_time,
            match_time_seconds=match_time_seconds,
            round_number=round_number if round_number is not None else self.current_snapshot.round_number,
            confidence=confidence,
            source=source,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        record = StateTransitionRecord(
            from_state=current_state,
            to_state=normalized_target,
            source=source,
            match_time=formatted_match_time,
            game=active_game,
            is_valid=is_valid,
            reason=None if is_valid else "Forced transition"
        )
        self.history.append(record)

        self.current_snapshot = new_snapshot

        # Keep providers in sync
        if source == "manual":
            self.manual_provider.set_state(new_snapshot)
        elif source == "simulated":
            self.simulated_provider.set_state(new_snapshot)

        # Notify listeners
        for listener in self.listeners:
            try:
                listener(record)
            except Exception:
                pass

        return new_snapshot

    def manual_update(
        self,
        state: Union[GameState, str],
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        match_time: Optional[str] = None,
        round_number: Optional[Union[int, str]] = None,
        force: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GameStateSnapshot:
        """
        Applies a player manual state update with 100% confidence.
        """
        return self.transition_to(
            target_state=state,
            game=game,
            map_name=map_name,
            match_time=match_time,
            round_number=round_number,
            source="manual",
            force=force,
            confidence=1.0,
            metadata=metadata
        )

    def simulate_state(
        self,
        state: Union[GameState, str],
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        match_time: Optional[str] = None,
        round_number: Optional[Union[int, str]] = None,
        confidence: float = 0.95,
        force: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GameStateSnapshot:
        """
        Simulates state update with simulated source.
        """
        return self.transition_to(
            target_state=state,
            game=game,
            map_name=map_name,
            match_time=match_time,
            round_number=round_number,
            source="simulated",
            force=force,
            confidence=confidence,
            metadata=metadata
        )

    def get_current_state(self) -> GameStateSnapshot:
        """Returns the active state snapshot."""
        return self.current_snapshot

    def get_history(self) -> List[StateTransitionRecord]:
        """Returns the full chronological transition history."""
        return list(self.history)

    def add_listener(self, listener: Callable[[StateTransitionRecord], None]) -> None:
        """Registers a transition event listener."""
        self.listeners.append(listener)

    def reset(
        self,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        state: GameState = GameState.UNKNOWN
    ) -> GameStateSnapshot:
        """Resets detector state and context."""
        self.game = game
        self.map = map_name
        self.current_snapshot = GameStateSnapshot(
            game=game,
            map=map_name,
            state=state,
            match_time=None,
            confidence=0.0 if state == GameState.UNKNOWN else 1.0,
            source="simulated"
        )
        return self.current_snapshot


# Global default game state detector instance
default_game_state_detector = GameStateDetector()
