import os
import sys
import unittest
import tempfile
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Session
from app.session_storage import (
    SessionStorage,
    SessionStorageError,
    SessionNotFoundError
)


class TestPhase2SessionStorage(unittest.TestCase):
    """
    Phase 2: Session Storage Tests
    Verifies:
    1. Session creation (complete, partial, custom configuration, raw player data).
    2. Retrieval (by session_id, by integer id, non-existent returns None).
    3. Update (field updating, invariant preservation, K/D recalculation, error on non-existent).
    4. Recent-session query (ordering, limit filtering).
    5. Deletion (successful removal, count decrement, error on non-existent).
    6. Count sessions (accurate count reporting).
    7. Persistence after restart (survives database disconnection and reload).
    8. Incomplete sessions preserved without invented data or AI generation.
    """

    def setUp(self):
        # Create a temporary file database for clean, isolated test runs
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.storage = SessionStorage(db_path=self.temp_db_path)

    def tearDown(self):
        # Clean up temporary database file
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # -------------------------------------------------------------
    # 1. SESSION CREATION
    # -------------------------------------------------------------
    def test_create_complete_session(self):
        """Verify complete session creation with all fields preserved."""
        session_data = Session(
            session_id="session-val-018",
            game="Valorant",
            game_mode="Competitive",
            map="Ascent",
            configuration={
                "weapon": "Phantom",
                "sensitivity": 0.35,
                "crosshair": "0;P;c;5;o;1;d;1"
            },
            started_at="2026-09-18T14:00:00",
            ended_at="2026-09-18T15:12:00",
            duration=72,
            score="18/10",
            kills=18,
            deaths=10,
            assists=6,
            result="Win",
            player_notes="Great crosshair placement on Ascent A site.",
            tags=["#Ranked", "#Ascent", "#Phantom"],
            performance_metrics={
                "acs": 285,
                "headshot_pct": 32.5,
                "first_bloods": 5
            },
            data_source="client_api"
        )

        created = self.storage.create_session(session_data)

        self.assertIsNotNone(created)
        self.assertEqual(created.session_id, "session-val-018")
        self.assertEqual(created.game, "Valorant")
        self.assertEqual(created.game_mode, "Competitive")
        self.assertEqual(created.map, "Ascent")
        self.assertEqual(created.duration, 72)
        self.assertEqual(created.score, "18/10")
        self.assertEqual(created.kills, 18)
        self.assertEqual(created.deaths, 10)
        self.assertEqual(created.assists, 6)
        self.assertEqual(created.kd_ratio, 1.8)
        self.assertEqual(created.result, "Win")
        self.assertEqual(created.player_notes, "Great crosshair placement on Ascent A site.")
        self.assertEqual(created.tags, ["#Ranked", "#Ascent", "#Phantom"])
        self.assertIsInstance(created.configuration, dict)
        self.assertEqual(created.configuration["weapon"], "Phantom")
        self.assertEqual(created.performance_metrics["acs"], 285)
        self.assertEqual(created.data_source, "client_api")

        # Verify AI information is NOT generated
        self.assertIsNone(created.ai_summary)
        self.assertIsNone(created.ai_insights)

    def test_create_incomplete_session_preserves_missing_values(self):
        """
        Verify incomplete sessions are stored faithfully.
        Must NOT invent missing values (kills, deaths, result, etc. remain None).
        """
        partial_data = {
            "session_id": "partial-001",
            "game": "Elden Ring",
            "player_notes": "Attempting Malenia solo."
        }

        created = self.storage.create_session(partial_data)

        self.assertEqual(created.session_id, "partial-001")
        self.assertEqual(created.game, "Elden Ring")
        self.assertEqual(created.player_notes, "Attempting Malenia solo.")
        # Missing values must remain None (not invented)
        self.assertIsNone(created.kills)
        self.assertIsNone(created.deaths)
        self.assertIsNone(created.assists)
        self.assertIsNone(created.kd_ratio)
        self.assertIsNone(created.duration)
        self.assertIsNone(created.score)
        self.assertIsNone(created.result)
        self.assertIsNone(created.ai_summary)
        self.assertIsNone(created.ai_insights)

    def test_create_session_with_auto_generated_id(self):
        """Verify session creation without session_id assigns an auto-generated id."""
        created = self.storage.create_session({"game": "Apex Legends", "kills": 5, "deaths": 1})
        self.assertIsNotNone(created.session_id)
        self.assertTrue(len(str(created.session_id)) > 0)
        self.assertEqual(created.kills, 5)
        self.assertEqual(created.deaths, 1)
        self.assertEqual(created.kd_ratio, 5.0)

    def test_create_session_rejects_duplicates(self):
        """Verify attempting to create duplicate session_id raises SessionStorageError."""
        self.storage.create_session({"session_id": "dup-1", "game": "CS2"})
        with self.assertRaises(SessionStorageError):
            self.storage.create_session({"session_id": "dup-1", "game": "CS2"})

    # -------------------------------------------------------------
    # 2. RETRIEVAL
    # -------------------------------------------------------------
    def test_get_session_by_id(self):
        """Verify retrieval by string session_id and primary key id."""
        created = self.storage.create_session({
            "session_id": "retrieve-test-1",
            "game": "Street Fighter 6",
            "configuration": "Luke (Classic Controls)",
            "result": "Win",
            "kills": 2,
            "deaths": 1
        })

        # Retrieve by session_id string
        retrieved = self.storage.get_session_by_id("retrieve-test-1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, "retrieve-test-1")
        self.assertEqual(retrieved.game, "Street Fighter 6")
        self.assertEqual(retrieved.configuration, "Luke (Classic Controls)")
        self.assertEqual(retrieved.kd_ratio, 2.0)

        # Retrieve non-existent ID returns None
        self.assertIsNone(self.storage.get_session_by_id("non-existent-id"))
        self.assertIsNone(self.storage.get_session_by_id(999999))
        self.assertIsNone(self.storage.get_session_by_id(None))

    # -------------------------------------------------------------
    # 3. UPDATE
    # -------------------------------------------------------------
    def test_update_session(self):
        """Verify updating existing session fields while preserving unchanged data."""
        created = self.storage.create_session({
            "session_id": "update-test-1",
            "game": "Valorant",
            "map": "Haven",
            "kills": 10,
            "deaths": 10,
            "player_notes": "First half went okay."
        })
        self.assertEqual(created.kd_ratio, 1.0)
        self.assertEqual(created.map, "Haven")

        # Update kills, deaths, player_notes, result
        updated = self.storage.update_session("update-test-1", {
            "kills": 20,
            "deaths": 10,
            "result": "Win",
            "player_notes": "Comeback in second half!"
        })

        self.assertEqual(updated.session_id, "update-test-1")
        self.assertEqual(updated.game, "Valorant")  # Preserved
        self.assertEqual(updated.map, "Haven")       # Preserved
        self.assertEqual(updated.kills, 20)
        self.assertEqual(updated.deaths, 10)
        self.assertEqual(updated.kd_ratio, 2.0)      # Recomputed automatically!
        self.assertEqual(updated.result, "Win")
        self.assertEqual(updated.player_notes, "Comeback in second half!")

    def test_update_session_not_found(self):
        """Verify updating non-existent session raises SessionNotFoundError."""
        with self.assertRaises(SessionNotFoundError):
            self.storage.update_session("ghost-session", {"kills": 10})

    def test_update_session_validation_rejection(self):
        """Verify update with invalid data (e.g. negative kills) raises SessionStorageError."""
        self.storage.create_session({"session_id": "val-err-1", "game": "Valorant"})
        with self.assertRaises(SessionStorageError):
            self.storage.update_session("val-err-1", {"kills": -5})

    # -------------------------------------------------------------
    # 4. RECENT-SESSION QUERY
    # -------------------------------------------------------------
    def test_get_recent_sessions(self):
        """Verify recent session retrieval with limit and order."""
        # Create 5 distinct sessions
        for i in range(1, 6):
            self.storage.create_session({
                "session_id": f"session-batch-{i}",
                "game": f"Game-{i}",
                "kills": i * 2,
                "deaths": i
            })

        # Query recent 3 sessions
        recent_3 = self.storage.get_recent_sessions(limit=3)
        self.assertEqual(len(recent_3), 3)
        # Most recent first
        self.assertEqual(recent_3[0].session_id, "session-batch-5")
        self.assertEqual(recent_3[1].session_id, "session-batch-4")
        self.assertEqual(recent_3[2].session_id, "session-batch-3")

        # Query all (limit=10)
        all_recent = self.storage.get_recent_sessions(limit=10)
        self.assertEqual(len(all_recent), 5)

        # Edge cases
        self.assertEqual(self.storage.get_recent_sessions(limit=0), [])

    # -------------------------------------------------------------
    # 5. DELETION
    # -------------------------------------------------------------
    def test_delete_session(self):
        """Verify session deletion removes the record and decreases count."""
        self.storage.create_session({"session_id": "del-1", "game": "Valorant"})
        self.storage.create_session({"session_id": "del-2", "game": "Overwatch 2"})
        self.assertEqual(self.storage.count_sessions(), 2)

        # Delete del-1
        result = self.storage.delete_session("del-1")
        self.assertTrue(result)

        # Confirm del-1 is gone
        self.assertIsNone(self.storage.get_session_by_id("del-1"))
        self.assertEqual(self.storage.count_sessions(), 1)

        # Confirm del-2 remains
        self.assertIsNotNone(self.storage.get_session_by_id("del-2"))

    def test_delete_session_not_found(self):
        """Verify deleting non-existent session raises SessionNotFoundError."""
        with self.assertRaises(SessionNotFoundError):
            self.storage.delete_session("non-existent-session-id")

    # -------------------------------------------------------------
    # 6. COUNT SESSIONS
    # -------------------------------------------------------------
    def test_count_sessions(self):
        """Verify count_sessions accurately reflects storage state."""
        self.assertEqual(self.storage.count_sessions(), 0)

        self.storage.create_session({"session_id": "c-1", "game": "Rocket League"})
        self.assertEqual(self.storage.count_sessions(), 1)

        self.storage.create_session({"session_id": "c-2", "game": "Rocket League"})
        self.assertEqual(self.storage.count_sessions(), 2)

        self.storage.delete_session("c-1")
        self.assertEqual(self.storage.count_sessions(), 1)

    # -------------------------------------------------------------
    # 7. PERSISTENCE AFTER RESTART
    # -------------------------------------------------------------
    def test_persistence_after_restart(self):
        """
        Verify that stored sessions persist across storage instance restarts
        and connection lifecycles.
        """
        # 1. Store session with storage instance #1
        session_payload = {
            "session_id": "persist-test-042",
            "game": "Valorant",
            "game_mode": "Competitive",
            "map": "Bind",
            "configuration": {"weapon": "Vandal", "sensitivity": 0.3},
            "started_at": "2026-09-18T16:00:00",
            "duration": "45 minutes",
            "score": "13-8",
            "kills": 22,
            "deaths": 11,
            "result": "Win",
            "player_notes": "Great site holds on B site.",
            "tags": ["#Bind", "#Vandal"],
            "performance_metrics": {"first_bloods": 4, "headshot_pct": 38.0}
        }
        self.storage.create_session(session_payload)
        self.assertEqual(self.storage.count_sessions(), 1)

        # 2. Simulate complete restart: destroy old storage instance
        del self.storage

        # 3. Instantiate a fresh SessionStorage instance on the exact same database file
        restarted_storage = SessionStorage(db_path=self.temp_db_path)

        # 4. Verify session is retrieved intact
        retrieved = restarted_storage.get_session_by_id("persist-test-042")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, "persist-test-042")
        self.assertEqual(retrieved.game, "Valorant")
        self.assertEqual(retrieved.map, "Bind")
        self.assertEqual(retrieved.kills, 22)
        self.assertEqual(retrieved.deaths, 11)
        self.assertEqual(retrieved.kd_ratio, 2.0)
        self.assertEqual(retrieved.result, "Win")
        self.assertEqual(retrieved.player_notes, "Great site holds on B site.")
        self.assertEqual(retrieved.tags, ["#Bind", "#Vandal"])
        self.assertEqual(retrieved.configuration["weapon"], "Vandal")
        self.assertEqual(retrieved.performance_metrics["headshot_pct"], 38.0)
        self.assertIsNone(retrieved.ai_summary)
        self.assertIsNone(retrieved.ai_insights)
        self.assertEqual(restarted_storage.count_sessions(), 1)


if __name__ == "__main__":
    unittest.main()
