from typing import Optional, Dict, Any, Union
from datetime import datetime

from app.models import DetectionResult, GameDetectionResult, MapDetectionResult, MatchContext, Session
from app.session_storage import SessionStorage, default_session_storage
from app.map_registry import GameMapRegistry, default_map_registry


# =====================================================================
# PHASE 3: EXCEPTIONS
# =====================================================================

class DetectionError(Exception):
    """Base exception for detection layer."""
    pass


class DetectionConnectionError(DetectionError):
    """Raised when an unconfigured or disconnected detection source (api, game_log) is requested."""
    pass


# =====================================================================
# KNOWN GAMES AND MAPS REGISTRY
# =====================================================================

KNOWN_GAMES_AND_MAPS: Dict[str, Dict[str, Any]] = {
    "BGMI": {
        "aliases": ["BGMI / PUBG Mobile", "PUBG Mobile", "Battlegrounds Mobile India"],
        "versions": ["3.5", "3.4"],
        "modes": ["Classic Battle Royale", "Payload", "Arena / TDM", "Ultimate Royale"],
        "maps": ["Erangel", "Miramar", "Sanhok", "Livik", "Vikendi", "Nusa", "Karakin"]
    },
    "BGMI / PUBG Mobile": {
        "aliases": ["BGMI", "PUBG Mobile"],
        "versions": ["3.5", "3.4"],
        "modes": ["Classic Battle Royale", "Payload", "Arena / TDM", "Ultimate Royale"],
        "maps": ["Erangel", "Miramar", "Sanhok", "Livik", "Vikendi", "Nusa", "Karakin"]
    },
    "Free Fire MAX": {
        "aliases": ["Free Fire"],
        "versions": ["OB48", "OB47"],
        "modes": ["Battle Royale Ranked", "Clash Squad Ranked", "Lone Wolf"],
        "maps": ["Bermuda", "Purgatory", "Kalahari", "Alpine", "NeXTerra"]
    },
    "Call of Duty Mobile": {
        "aliases": ["CODM", "COD Mobile"],
        "versions": ["Season 9", "Season 8"],
        "modes": ["Multiplayer Ranked", "Battle Royale", "Search & Destroy", "Hardpoint", "Domination"],
        "maps": ["Crash", "Firing Range", "Standoff", "Nuketown", "Raid", "Summit", "Isolated", "Blackout"]
    },
    "PUBG New State": {
        "aliases": ["New State Mobile"],
        "versions": ["0.9.68", "0.9.65"],
        "modes": ["Battle Royale", "Deathmatch", "Bounty Royale"],
        "maps": ["Troi", "Erangel 2051", "Akinta", "Lagna"]
    },
    "Valorant": {
        "versions": ["9.05", "9.04"],
        "modes": ["Competitive", "Unrated", "Deathmatch", "Spike Rush", "Premier"],
        "maps": ["Ascent", "Bind", "Haven", "Split", "Icebox", "Breeze", "Fracture", "Pearl", "Lotus", "Sunset", "Abyss"]
    },
    "Honor of Kings": {
        "versions": ["Global 1.0", "Season 6"],
        "modes": ["Ranked 5v5", "Standard 5v5", "Valley of Heroes"],
        "maps": ["Gorge of Kings", "Border Break"]
    },
    "League of Legends": {
        "versions": ["14.18", "14.17"],
        "modes": ["Ranked Solo/Duo", "Ranked Flex", "Normal Draft", "ARAM", "Arena"],
        "maps": ["Summoner's Rift", "Howling Abyss", "Rings of Wrath"]
    },
    "Fortnite": {
        "versions": ["Chapter 5 Season 4", "Chapter 5 Season 3"],
        "modes": ["Battle Royale", "Zero Build", "Ranked Battle Royale", "Ranked Zero Build"],
        "maps": ["Battle Royale Island", "Reload Island"]
    },
    "Genshin Impact": {
        "versions": ["5.0", "4.8"],
        "modes": ["Single Player Exploration", "Co-op Domain", "Spiral Abyss", "Imaginarium Theater"],
        "maps": ["Mondstadt", "Liyue", "Inazuma", "Sumeru", "Fontaine", "Natlan"]
    },
    "Chess": {
        "versions": ["FIDE Standard", "Chess.com 2026"],
        "modes": ["Blitz (3+2)", "Rapid (10+0)", "Bullet (1+0)", "Classical (30+0)"],
        "maps": ["Standard 8x8 Board"]
    },
    "Elden Ring": {
        "versions": ["1.14"],
        "modes": ["Boss Fight", "Open World", "Dungeon", "PvP Colosseum"],
        "maps": ["Limgrave", "Stormveil Castle", "Raya Lucaria", "Caelid", "Leyndell, Royal Capital", "Mountaintops of the Giants", "Elphael, Brace of the Haligtree"]
    },
    "Apex Legends": {
        "versions": ["Season 22"],
        "modes": ["Ranked Battle Royale", "Trios", "Duos", "Mixtape"],
        "maps": ["Kings Canyon", "World's Edge", "Olympus", "Storm Point", "Broken Moon", "E-District"]
    },
    "Counter-Strike 2": {
        "versions": ["CS2 Release"],
        "modes": ["Premier", "Competitive", "Wingman", "Deathmatch"],
        "maps": ["Mirage", "Inferno", "Nuke", "Dust II", "Overpass", "Ancient", "Anubis", "Vertigo"]
    },
    "Overwatch 2": {
        "versions": ["Season 12"],
        "modes": ["Role Queue Competitive", "Quick Play", "Arcade"],
        "maps": ["King's Row", "Route 66", "Ilios", "Lijiang Tower", "Midtown", "Circuit Royal", "Esperança"]
    }
}


# =====================================================================
# DETECTION LAYER IMPLEMENTATION
# =====================================================================

class GameMapDetector:
    """
    Lightweight Detection Layer for Gaming Sessions.
    
    Phase 3: Game Detection
    Phase 4: Map and Match Detection
    
    Supports:
    - Game-specific maps (via GameMapRegistry, not hard-coded)
    - Simulated & manual detection
    - Connecting confirmed match context to active Session
    - Disallows false claims of automatic API/log detection
    """

    def __init__(
        self,
        api_connected: bool = False,
        game_log_connected: bool = False,
        map_registry: Optional[GameMapRegistry] = None
    ):
        self.api_connected = api_connected
        self.game_log_connected = game_log_connected
        self.map_registry = map_registry or default_map_registry

    def detect(
        self,
        source: str = "simulated",
        game_hint: Optional[str] = None,
        map_hint: Optional[str] = None,
        mode_hint: Optional[str] = None,
        scenario: Optional[str] = None,
        confidence_override: Optional[float] = None
    ) -> DetectionResult:
        """
        Runs game and map detection using the specified detection_source.
        """
        if source in ("api", "game_log"):
            if source == "api" and not self.api_connected:
                raise DetectionConnectionError("API detection source is not connected.")
            if source == "game_log" and not self.game_log_connected:
                raise DetectionConnectionError("game_log detection source is not connected.")

        if source == "manual":
            return self.manual_selection(
                game=game_hint or "Valorant",
                map_name=map_hint or "Ascent",
                game_mode=mode_hint or "Competitive"
            )

        if source == "simulated":
            return self.simulate_detection(
                game=game_hint,
                map_name=map_hint,
                game_mode=mode_hint,
                scenario=scenario,
                confidence=confidence_override
            )

        raise DetectionError(f"Unsupported detection source: '{source}'")

    def simulate_detection(
        self,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        scenario: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> DetectionResult:
        """
        Simulates game and map detection.
        Handles valid detection, unknown game, unknown map, and low confidence.
        """
        # Scenario 1: explicit unknown game
        if scenario == "unknown_game" or (game is not None and game not in KNOWN_GAMES_AND_MAPS and game.lower() == "unknown"):
            return DetectionResult(
                game=None,
                game_mode=None,
                map=None,
                confidence=0.2,
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game/map.",
                raw_telemetry={"scenario": "unknown_game"}
            )

        # Scenario 2: explicit unknown map
        if scenario == "unknown_map":
            detected_game = game or "Valorant"
            return DetectionResult(
                game=detected_game,
                game_mode=game_mode or "Competitive",
                map=None,
                confidence=0.45,
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game/map.",
                raw_telemetry={"scenario": "unknown_map", "game": detected_game}
            )

        # Scenario 3: explicit low confidence
        if scenario == "low_confidence":
            return DetectionResult(
                game=game or "Valorant",
                game_mode=game_mode or "Competitive",
                map=map_name or "Ascent",
                confidence=0.4,
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game/map.",
                raw_telemetry={"scenario": "low_confidence"}
            )

        # Default or hinted simulation
        target_game = game or "Valorant"
        target_mode = game_mode or "Competitive"
        target_map = map_name or "Ascent"
        conf = confidence if confidence is not None else 0.95

        # Validate against known games registry
        if target_game not in KNOWN_GAMES_AND_MAPS:
            # Game is not recognized
            return DetectionResult(
                game=target_game,
                game_mode=target_mode,
                map=None,
                confidence=min(conf, 0.35),
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game/map.",
                raw_telemetry={"reason": "unrecognized_game", "query": target_game}
            )

        known_info = KNOWN_GAMES_AND_MAPS[target_game]
        detected_version = known_info.get("versions", [None])[0] if "versions" in known_info else None

        if not self.map_registry.is_valid_map(target_game, target_map) and target_map not in known_info.get("maps", []):
            # Game recognized, but map is unrecognized
            return GameDetectionResult(
                game=target_game,
                game_version=detected_version,
                game_mode=target_mode,
                map=target_map,
                confidence=min(conf, 0.45),
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game/map.",
                raw_telemetry={"reason": "unrecognized_map", "query_map": target_map}
            )

        # Valid high-confidence detection
        is_confident = conf >= 0.6
        msg = None if is_confident else "Unable to confidently detect game/map."
        return GameDetectionResult(
            game=target_game,
            game_version=detected_version,
            game_mode=target_mode,
            map=target_map,
            confidence=conf,
            detection_source="simulated",
            is_confident=is_confident,
            message=msg,
            raw_telemetry={"matched_registry": True, "game": target_game, "map": target_map}
        )

    def detect_game(
        self,
        source: str = "simulated",
        game_hint: Optional[str] = None,
        version_hint: Optional[str] = None,
        mode_hint: Optional[str] = None,
        scenario: Optional[str] = None,
        confidence_override: Optional[float] = None
    ) -> GameDetectionResult:
        """
        Phase 3: Dedicated game detection method.
        Identifies:
        - game
        - game_version if available
        - game_mode if available
        - detection confidence
        - detection source ('manual', 'simulated')
        """
        if source in ("api", "game_log"):
            if source == "api" and not self.api_connected:
                raise DetectionConnectionError("API detection source is not connected.")
            if source == "game_log" and not self.game_log_connected:
                raise DetectionConnectionError("game_log detection source is not connected.")

        if source == "manual":
            return self.manual_game_detection(
                game=game_hint or "BGMI",
                version=version_hint,
                mode=mode_hint
            )

        if source == "simulated":
            return self.simulate_game_detection(
                game=game_hint,
                version=version_hint,
                mode=mode_hint,
                scenario=scenario,
                confidence=confidence_override
            )

        raise DetectionError(f"Unsupported detection source: '{source}'")

    def simulate_game_detection(
        self,
        game: Optional[str] = None,
        version: Optional[str] = None,
        mode: Optional[str] = None,
        scenario: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> GameDetectionResult:
        """
        Simulates game detection for Phase 3.
        Supports: known game, unknown game, low confidence.
        """
        if scenario == "unknown_game" or (game is not None and game not in KNOWN_GAMES_AND_MAPS and game.lower() in ("unknown", "none")):
            return GameDetectionResult(
                game=None,
                game_version=None,
                game_mode=None,
                confidence=0.2,
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game."
            )

        if scenario == "low_confidence":
            target = game or "BGMI"
            return GameDetectionResult(
                game=target,
                confidence=0.4,
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game."
            )

        target_game = game or "BGMI"
        conf = confidence if confidence is not None else 0.96

        if target_game not in KNOWN_GAMES_AND_MAPS:
            return GameDetectionResult(
                game=target_game,
                confidence=min(conf, 0.35),
                detection_source="simulated",
                is_confident=False,
                message="Unable to confidently detect game."
            )

        info = KNOWN_GAMES_AND_MAPS[target_game]
        detected_version = version or (info.get("versions", [None])[0] if "versions" in info else None)
        detected_mode = mode or (info.get("modes", [None])[0] if "modes" in info else None)

        is_conf = conf >= 0.6
        return GameDetectionResult(
            game=target_game,
            game_version=detected_version,
            game_mode=detected_mode,
            confidence=conf,
            detection_source="simulated",
            is_confident=is_conf,
            message=None if is_conf else "Unable to confidently detect game."
        )

    def manual_game_detection(
        self,
        game: str,
        version: Optional[str] = None,
        mode: Optional[str] = None
    ) -> GameDetectionResult:
        """Manual game selection with 100% confidence."""
        if not game:
            return GameDetectionResult(
                game=None,
                confidence=0.0,
                detection_source="manual",
                is_confident=False,
                message="Unable to confidently detect game."
            )

        info = KNOWN_GAMES_AND_MAPS.get(game, {})
        detected_version = version or (info.get("versions", [None])[0] if "versions" in info else None)
        detected_mode = mode or (info.get("modes", [None])[0] if "modes" in info else None)

        return GameDetectionResult(
            game=game,
            game_version=detected_version,
            game_mode=detected_mode,
            confidence=1.0,
            detection_source="manual",
            is_confident=True,
            message="Manually selected by user."
        )

    def detect_map(
        self,
        game: str,
        source: str = "simulated",
        map_hint: Optional[str] = None,
        scenario: Optional[str] = None,
        confidence_override: Optional[float] = None
    ) -> MapDetectionResult:
        """
        Phase 4: Detects game-specific map using dynamic map registry.
        If map information is unavailable, returns MapDetectionResult with 'Map not detected.'
        """
        if source in ("api", "game_log"):
            if source == "api" and not self.api_connected:
                raise DetectionConnectionError("API detection source is not connected.")
            if source == "game_log" and not self.game_log_connected:
                raise DetectionConnectionError("game_log detection source is not connected.")

        if source == "manual":
            if not map_hint or map_hint.strip().lower() in ("unknown", "none", "map not detected", ""):
                return MapDetectionResult(
                    game=game,
                    map=None,
                    confidence=0.0,
                    detection_source="manual",
                    is_confident=False,
                    message="Map not detected."
                )
            return MapDetectionResult(
                game=game,
                map=map_hint.strip(),
                confidence=1.0,
                detection_source="manual",
                is_confident=True,
                message="Manually entered by player."
            )

        if source == "simulated":
            if scenario == "unknown_map" or not map_hint or str(map_hint).strip().lower() in ("unknown", "none", "map not detected", ""):
                return MapDetectionResult(
                    game=game,
                    map=None,
                    confidence=0.25,
                    detection_source="simulated",
                    is_confident=False,
                    message="Map not detected.",
                    raw_telemetry={"scenario": scenario or "unknown_map"}
                )

            if scenario == "low_confidence" or (confidence_override is not None and confidence_override < 0.6):
                conf = confidence_override if confidence_override is not None else 0.45
                return MapDetectionResult(
                    game=game,
                    map=map_hint.strip(),
                    confidence=conf,
                    detection_source="simulated",
                    is_confident=False,
                    message="Map not detected.",
                    raw_telemetry={"scenario": "low_confidence"}
                )

            canonical_game = self.map_registry.resolve_game_name(game)
            if not self.map_registry.is_valid_map(canonical_game, map_hint):
                return MapDetectionResult(
                    game=game,
                    map=None,
                    confidence=0.35,
                    detection_source="simulated",
                    is_confident=False,
                    message="Map not detected.",
                    raw_telemetry={"reason": "unrecognized_map_for_game", "query_map": map_hint}
                )

            conf = confidence_override if confidence_override is not None else 0.95
            return MapDetectionResult(
                game=game,
                map=map_hint.strip(),
                confidence=conf,
                detection_source="simulated",
                is_confident=True,
                message=None,
                raw_telemetry={"matched_registry": True, "game": canonical_game, "map": map_hint}
            )

        raise DetectionError(f"Unsupported detection source: '{source}'")

    def detect_match(
        self,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        match_id: Optional[str] = None,
        round_number: Optional[Union[int, str]] = None,
        source: str = "simulated",
        scenario: Optional[str] = None,
        confidence_override: Optional[float] = None
    ) -> MatchContext:
        """
        Phase 4: Detect or allow manual input for:
        - map
        - game mode
        - match ID
        - round number if applicable
        - detection confidence
        - detection source
        """
        if source in ("api", "game_log"):
            if source == "api" and not self.api_connected:
                raise DetectionConnectionError("API detection source is not connected.")
            if source == "game_log" and not self.game_log_connected:
                raise DetectionConnectionError("game_log detection source is not connected.")

        resolved_game = game or "BGMI"

        if source == "manual":
            return self.manual_match_input(
                game=resolved_game,
                map_name=map_name,
                game_mode=game_mode,
                match_id=match_id,
                round_number=round_number
            )

        map_detection = self.detect_map(
            game=resolved_game,
            source="simulated",
            map_hint=map_name,
            scenario=scenario,
            confidence_override=confidence_override
        )

        resolved_map = map_detection.map if map_detection.is_confident else None

        # Resolve mode from registry if not provided
        info = KNOWN_GAMES_AND_MAPS.get(resolved_game, {})
        detected_mode = game_mode or (info.get("modes", ["Standard"])[0] if "modes" in info else "Standard")

        detected_match_id = match_id or f"match-{resolved_game.lower().replace(' ', '').replace('/', '')}-{int(datetime.now().timestamp())}"

        return MatchContext(
            game=resolved_game,
            map=resolved_map,
            game_mode=detected_mode,
            match_id=detected_match_id,
            round_number=round_number,
            confidence=map_detection.confidence,
            detection_source="simulated",
            is_confirmed=False,
            map_detection=map_detection,
            raw_telemetry={"scenario": scenario}
        )

    def manual_match_input(
        self,
        game: str,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        match_id: Optional[str] = None,
        round_number: Optional[Union[int, str]] = None
    ) -> MatchContext:
        """
        Allows direct manual input for match details with 100% confidence.
        """
        map_detection = MapDetectionResult(
            game=game,
            map=map_name,
            confidence=1.0 if map_name else 0.0,
            detection_source="manual",
            is_confident=bool(map_name),
            message="Manually entered by player." if map_name else "Map not detected."
        )
        return MatchContext(
            game=game,
            map=map_name,
            game_mode=game_mode or "Standard",
            match_id=match_id or f"manual-{int(datetime.now().timestamp())}",
            round_number=round_number,
            confidence=1.0,
            detection_source="manual",
            is_confirmed=True,
            map_detection=map_detection,
            raw_telemetry={"input_type": "manual"}
        )

    def confirm_match_context(
        self,
        match_context: MatchContext,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        match_id: Optional[str] = None,
        round_number: Optional[Union[int, str]] = None
    ) -> MatchContext:
        """
        Allows manual confirmation and overrides on detected match context.
        """
        return match_context.confirm(
            map_name=map_name,
            game_mode=game_mode,
            match_id=match_id,
            round_number=round_number
        )

    def connect_confirmed_data_to_session(
        self,
        session_or_id: Union[Session, str, int],
        match_context: MatchContext,
        storage: Optional[SessionStorage] = None
    ) -> Session:
        """
        Connects confirmed Map and Match detection data to an active Session.
        Updates map, game_mode, match_id, round_number, and data_source.
        Persists update to session storage.
        """
        target_storage = storage or default_session_storage

        if isinstance(session_or_id, Session):
            session_id = session_or_id.session_id
            existing_session = session_or_id
        else:
            session_id = str(session_or_id)
            existing_session = target_storage.get_session_by_id(session_id)
            if not existing_session:
                raise DetectionError(f"Session '{session_id}' not found in storage.")

        if not match_context.is_confirmed:
            match_context.confirm()

        update_payload: Dict[str, Any] = {}
        if match_context.map is not None:
            update_payload["map"] = match_context.map
        if match_context.game_mode is not None:
            update_payload["game_mode"] = match_context.game_mode
        if match_context.match_id is not None:
            update_payload["match_id"] = match_context.match_id
        if match_context.detection_source is not None:
            update_payload["data_source"] = match_context.detection_source
        if match_context.round_number is not None:
            update_payload["round_number"] = match_context.round_number
            metrics = dict(existing_session.performance_metrics or {})
            metrics["round_number"] = match_context.round_number
            update_payload["performance_metrics"] = metrics

        updated_session = target_storage.update_session(session_id, update_payload)
        return updated_session

    def manual_selection(
        self,
        game: str,
        map_name: str,
        game_mode: Optional[str] = None,
        telemetry: Optional[Dict[str, Any]] = None
    ) -> DetectionResult:
        """
        Direct manual selection by player with 100% confidence.
        """
        if not game or not map_name:
            return DetectionResult(
                game=game or None,
                game_mode=game_mode,
                map=map_name or None,
                confidence=0.0,
                detection_source="manual",
                is_confident=False,
                message="Unable to confidently detect game/map."
            )

        return DetectionResult(
            game=game,
            game_mode=game_mode or "Standard",
            map=map_name,
            confidence=1.0,
            detection_source="manual",
            is_confident=True,
            message="Manually confirmed by player.",
            raw_telemetry=telemetry or {}
        )

    def apply_manual_correction(
        self,
        detection: DetectionResult,
        game: Optional[str] = None,
        map_name: Optional[str] = None,
        game_mode: Optional[str] = None,
        game_version: Optional[str] = None
    ) -> DetectionResult:
        """
        Allows the player to manually correct uncertain or misdetected values.
        Transitions detection_source to 'manual' with 1.0 confidence.
        """
        corrected_game = game if game is not None else detection.game
        corrected_map = map_name if map_name is not None else detection.map
        corrected_mode = game_mode if game_mode is not None else detection.game_mode
        corrected_version = game_version if game_version is not None else detection.game_version

        if not corrected_game:
            return DetectionResult(
                game=corrected_game,
                game_version=corrected_version,
                game_mode=corrected_mode,
                map=corrected_map,
                confidence=0.0,
                detection_source="manual",
                is_confident=False,
                message="Unable to confidently detect game/map."
            )

        return DetectionResult(
            game=corrected_game,
            game_version=corrected_version,
            game_mode=corrected_mode,
            map=corrected_map,
            confidence=1.0,
            detection_source="manual",
            is_confident=True,
            message="Manually corrected by player.",
            raw_telemetry={"prior_detection": detection.model_dump()}
        )

    def confirm_detection_and_create_session(
        self,
        detection: DetectionResult,
        corrections: Optional[Dict[str, Any]] = None,
        additional_fields: Optional[Dict[str, Any]] = None,
        storage: Optional[SessionStorage] = None
    ) -> Session:
        """
        Confirms detected/corrected values and stores the confirmed session.
        CRITICAL RULE: Unconfirmed detections are never stored; only confirmed values are saved.
        """
        active_detection = detection
        if corrections:
            active_detection = self.apply_manual_correction(
                detection=detection,
                game=corrections.get("game"),
                map_name=corrections.get("map"),
                game_mode=corrections.get("game_mode"),
                game_version=corrections.get("game_version")
            )

        if not active_detection.game:
            raise DetectionError("Cannot confirm session without valid game.")

        target_storage = storage or default_session_storage

        session_payload: Dict[str, Any] = {
            "game": active_detection.game,
            "game_mode": active_detection.game_mode,
            "map": active_detection.map,
            "data_source": active_detection.detection_source
        }

        if additional_fields:
            session_payload.update(additional_fields)

        return target_storage.create_session(session_payload)


# Default detector instance
default_detector = GameMapDetector()
