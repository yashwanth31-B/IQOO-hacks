from typing import Dict, List, Optional, Set


# =====================================================================
# PHASE 4: GAME-SPECIFIC MAP REGISTRY
# =====================================================================

class GameMapRegistry:
    """
    Extensible registry for game-specific maps.
    
    Ensures maps are NOT hard-coded into the core architecture, allowing
    runtime registration of games, maps, aliases, and custom maps.
    """

    def __init__(self):
        self._game_maps: Dict[str, List[str]] = {}
        self._game_aliases: Dict[str, str] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initializes default maps for supported MVP titles."""
        defaults = {
            "BGMI": [
                "Erangel", "Miramar", "Sanhok", "Livik", "Vikendi", "Nusa", "Karakin"
            ],
            "Free Fire MAX": [
                "Bermuda", "Purgatory", "Kalahari", "Alpine", "NeXTerra"
            ],
            "Call of Duty Mobile": [
                "Crash", "Firing Range", "Standoff", "Nuketown", "Raid", "Summit", "Isolated", "Blackout"
            ],
            "PUBG New State": [
                "Troi", "Erangel 2051", "Akinta", "Lagna"
            ],
            "Valorant": [
                "Ascent", "Bind", "Haven", "Split", "Icebox", "Breeze", "Fracture", "Pearl", "Lotus", "Sunset", "Abyss"
            ],
            "Honor of Kings": [
                "Gorge of Kings", "Border Break"
            ],
            "League of Legends": [
                "Summoner's Rift", "Howling Abyss", "Rings of Wrath"
            ],
            "Fortnite": [
                "Battle Royale Island", "Reload Island"
            ],
            "Genshin Impact": [
                "Mondstadt", "Liyue", "Inazuma", "Sumeru", "Fontaine", "Natlan"
            ],
            "Chess": [
                "Standard 8x8 Board"
            ],
            "Elden Ring": [
                "Limgrave", "Stormveil Castle", "Raya Lucaria", "Caelid", "Leyndell, Royal Capital", "Mountaintops of the Giants", "Elphael, Brace of the Haligtree"
            ],
            "Apex Legends": [
                "Kings Canyon", "World's Edge", "Olympus", "Storm Point", "Broken Moon", "E-District"
            ],
            "Counter-Strike 2": [
                "Mirage", "Inferno", "Nuke", "Dust II", "Overpass", "Ancient", "Anubis", "Vertigo"
            ],
            "Overwatch 2": [
                "King's Row", "Route 66", "Ilios", "Lijiang Tower", "Midtown", "Circuit Royal", "Esperança"
            ]
        }

        for game, maps in defaults.items():
            self.register_maps(game, maps)

        # Register common aliases
        self.register_alias("BGMI / PUBG Mobile", "BGMI")
        self.register_alias("PUBG Mobile", "BGMI")
        self.register_alias("Battlegrounds Mobile India", "BGMI")
        self.register_alias("Free Fire", "Free Fire MAX")
        self.register_alias("CODM", "Call of Duty Mobile")
        self.register_alias("COD Mobile", "Call of Duty Mobile")
        self.register_alias("New State Mobile", "PUBG New State")
        self.register_alias("LoL", "League of Legends")
        self.register_alias("CS2", "Counter-Strike 2")
        self.register_alias("OW2", "Overwatch 2")

    def resolve_game_name(self, game: str) -> str:
        """Resolves alias or casing to canonical game name."""
        if not game:
            return ""
        trimmed = game.strip()
        if trimmed in self._game_maps:
            return trimmed
        if trimmed in self._game_aliases:
            return self._game_aliases[trimmed]
        # Case-insensitive search
        lower = trimmed.lower()
        for g in self._game_maps:
            if g.lower() == lower:
                return g
        for a, canonical in self._game_aliases.items():
            if a.lower() == lower:
                return canonical
        return trimmed

    def register_maps(self, game: str, maps: List[str]) -> None:
        """Registers a list of maps for a game."""
        canonical = self.resolve_game_name(game) or game
        if canonical not in self._game_maps:
            self._game_maps[canonical] = []
        for m in maps:
            if m not in self._game_maps[canonical]:
                self._game_maps[canonical].append(m)

    def register_map(self, game: str, map_name: str) -> None:
        """Dynamically adds a single map to a game."""
        self.register_maps(game, [map_name])

    def register_alias(self, alias: str, canonical_game: str) -> None:
        """Registers an alias for a canonical game."""
        self._game_aliases[alias] = canonical_game

    def get_maps_for_game(self, game: str) -> List[str]:
        """Returns all registered maps for a game."""
        canonical = self.resolve_game_name(game)
        return list(self._game_maps.get(canonical, []))

    def is_valid_map(self, game: str, map_name: str) -> bool:
        """Checks if map is registered for the specified game."""
        if not game or not map_name:
            return False
        maps = self.get_maps_for_game(game)
        if not maps:
            return False
        # Exact match or case-insensitive match
        if map_name in maps:
            return True
        lower = map_name.strip().lower()
        return any(m.lower() == lower for m in maps)

    def get_default_map(self, game: str) -> Optional[str]:
        """Returns default or primary map for a game if available."""
        maps = self.get_maps_for_game(game)
        return maps[0] if maps else None

    def export_all(self) -> Dict[str, List[str]]:
        """Returns snapshot of all games and their maps."""
        return {g: list(maps) for g, maps in self._game_maps.items()}


# Global default map registry instance
default_map_registry = GameMapRegistry()
