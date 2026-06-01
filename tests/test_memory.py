"""Tests for MiniMax MemoryStore."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.minimax.memory import MemoryStore

TEST_ENTRY_ID = "test_entry_001"


@pytest.fixture
def mock_store():
    """Mock the HA Store."""
    with patch("custom_components.minimax.memory.Store") as mock:
        instance = MagicMock()
        instance.async_load = AsyncMock(return_value=None)
        instance.async_save = AsyncMock()
        mock.return_value = instance
        yield mock, instance


@pytest.fixture
def hass():
    """Create a mock hass."""
    return MagicMock()


@pytest.fixture
def memory_store(mock_store):
    """Create a MemoryStore without hass set."""
    return MemoryStore(entry_id=TEST_ENTRY_ID, max_count=10, expiry_days=30)


class TestMemoryStoreInit:
    """Test MemoryStore initialization."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        store = MemoryStore(entry_id=TEST_ENTRY_ID)
        assert store._entry_id == TEST_ENTRY_ID
        assert store._max_count == 50
        assert store._expiry_days == 30
        assert store._memories == []
        assert store._loaded is False
        assert store._store is None
        assert store._hass is None

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        store = MemoryStore(entry_id="custom_id", max_count=100, expiry_days=7)
        assert store._entry_id == "custom_id"
        assert store._max_count == 100
        assert store._expiry_days == 7

    def test_set_hass_creates_store(self, memory_store, hass):
        """Test set_hass creates a Store instance."""
        with patch("custom_components.minimax.memory.Store") as mock_store_cls:
            memory_store.set_hass(hass)
            mock_store_cls.assert_called_once_with(hass, 1, "minimax.memories")
            assert memory_store._store is not None


class TestMemoryStoreLoadSave:
    """Test MemoryStore loading and saving."""

    @pytest.mark.asyncio
    async def test_load_from_empty_store(self, memory_store, hass, mock_store):
        """Test loading when store returns None."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value=None)
        memory_store.set_hass(hass)

        await memory_store.async_load()

        assert memory_store._loaded is True
        assert memory_store._memories == []

    @pytest.mark.asyncio
    async def test_load_with_existing_data(self, memory_store, hass, mock_store):
        """Test loading when store has existing data."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {"id": "1", "fact": "User likes coffee", "category": "preference"},
                ]
            }
        )
        memory_store.set_hass(hass)

        await memory_store.async_load()

        assert memory_store._loaded is True
        assert len(memory_store._memories) == 1
        assert memory_store._memories[0]["fact"] == "User likes coffee"

    @pytest.mark.asyncio
    async def test_load_does_not_reload(self, memory_store, hass, mock_store):
        """Test that async_load does not reload after first load."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: []})
        memory_store.set_hass(hass)

        await memory_store.async_load()
        await memory_store.async_load()

        mock_instance.async_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_preserves_other_entries(self, memory_store, hass, mock_store):
        """Test save preserves other entries in the store."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={"other_entry": [{"fact": "other"}]}
        )
        memory_store.set_hass(hass)

        await memory_store.async_load()
        memory_store._memories = [{"id": "1", "fact": "My fact"}]
        await memory_store.async_save()

        saved_data = mock_instance.async_save.call_args[0][0]
        assert "other_entry" in saved_data
        assert TEST_ENTRY_ID in saved_data
        assert saved_data[TEST_ENTRY_ID] == [{"id": "1", "fact": "My fact"}]


class TestMemoryStoreFacts:
    """Test MemoryStore fact operations."""

    @pytest.mark.asyncio
    async def test_add_fact(self, memory_store, hass, mock_store):
        """Test adding a fact stores it correctly."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: []})
        mock_instance.async_save = AsyncMock()
        memory_store.set_hass(hass)

        memory_id = await memory_store.async_add_fact(
            "User likes coffee", category="preference"
        )

        assert memory_id is not None
        assert len(memory_store._memories) == 1
        assert memory_store._memories[0]["fact"] == "User likes coffee"
        assert memory_store._memories[0]["category"] == "preference"
        assert memory_store._memories[0]["id"] == memory_id
        mock_instance.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_fact_empty_raises_error(self, memory_store, hass, mock_store):
        """Test adding an empty fact raises ValueError."""
        memory_store.set_hass(hass)

        with pytest.raises(ValueError, match="Fact cannot be empty"):
            await memory_store.async_add_fact("")

    @pytest.mark.asyncio
    async def test_add_fact_whitespace_raises(self, memory_store, hass, mock_store):
        """Test adding whitespace-only fact raises ValueError."""
        memory_store.set_hass(hass)

        with pytest.raises(ValueError, match="Fact cannot be empty"):
            await memory_store.async_add_fact("   ")

    @pytest.mark.asyncio
    async def test_add_fact_enforces_max_count(self, memory_store, hass, mock_store):
        """Test add_fact removes oldest when exceeding max_count."""
        _mock_cls, mock_instance = mock_store
        memory_store._max_count = 3
        existing = [
            {"id": "1", "fact": "Oldest", "created_at": 100.0},
            {"id": "2", "fact": "Middle", "created_at": 200.0},
            {"id": "3", "fact": "Newest", "created_at": 300.0},
        ]
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: existing})
        memory_store.set_hass(hass)

        await memory_store.async_add_fact("New fact")

        assert len(memory_store._memories) == 3
        facts = [m["fact"] for m in memory_store._memories]
        assert "Oldest" not in facts
        assert "New fact" in facts

    @pytest.mark.asyncio
    async def test_get_facts(self, memory_store, hass, mock_store):
        """Test getting facts returns stored memories."""
        _mock_cls, mock_instance = mock_store
        now = time.time()
        facts = [
            {
                "id": "1",
                "fact": "Fact one",
                "category": "preference",
                "created_at": now,
                "last_accessed": now,
            },
        ]
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: facts})
        memory_store.set_hass(hass)

        result = await memory_store.async_get_facts()

        assert len(result) == 1
        assert result[0]["fact"] == "Fact one"

    @pytest.mark.asyncio
    async def test_get_facts_empty(self, memory_store, hass, mock_store):
        """Test get_facts returns empty list when no facts."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value=None)
        memory_store.set_hass(hass)

        result = await memory_store.async_get_facts()

        assert result == []

    @pytest.mark.asyncio
    async def test_remove_fact_by_id(self, memory_store, hass, mock_store):
        """Test removing a fact by its ID."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {
                        "id": "abc123",
                        "fact": "User likes coffee",
                        "category": "preference",
                    },
                ]
            }
        )
        mock_instance.async_save = AsyncMock()
        memory_store.set_hass(hass)

        result = await memory_store.async_remove_fact("abc123")

        assert result is True
        assert len(memory_store._memories) == 0
        mock_instance.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_fact_by_partial_match(self, memory_store, hass, mock_store):
        """Test removing a fact by partial text match."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {"id": "1", "fact": "User likes coffee", "category": "preference"},
                    {"id": "2", "fact": "User likes tea", "category": "preference"},
                ]
            }
        )
        mock_instance.async_save = AsyncMock()
        memory_store.set_hass(hass)

        result = await memory_store.async_remove_fact("coffee")

        assert result is True
        assert len(memory_store._memories) == 1
        assert memory_store._memories[0]["fact"] == "User likes tea"

    @pytest.mark.asyncio
    async def test_remove_fact_not_found(self, memory_store, hass, mock_store):
        """Test removing a fact that doesn't exist."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: []})
        memory_store.set_hass(hass)

        result = await memory_store.async_remove_fact("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear(self, memory_store, hass, mock_store):
        """Test clearing all facts."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {"id": "1", "fact": "Fact one"},
                ]
            }
        )
        mock_instance.async_save = AsyncMock()
        memory_store.set_hass(hass)

        await memory_store.async_clear()

        assert memory_store._memories == []
        mock_instance.async_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_memory_count(self, memory_store, hass, mock_store):
        """Test getting memory count."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {"id": "1", "fact": "Fact one"},
                    {"id": "2", "fact": "Fact two"},
                ]
            }
        )
        memory_store.set_hass(hass)

        count = await memory_store.async_get_memory_count()

        assert count == 2


class TestMemoryStoreExpiry:
    """Test MemoryStore expiry cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_facts(self, memory_store, hass, mock_store):
        """Test that expired facts are cleaned up."""
        _mock_cls, mock_instance = mock_store
        now = time.time()
        memory_store._expiry_days = 1  # 1 day expiry

        recent_fact = {
            "id": "1",
            "fact": "Recent",
            "created_at": now - 3600,  # 1 hour ago
            "last_accessed": now - 3600,
        }
        expired_fact = {
            "id": "2",
            "fact": "Expired",
            "created_at": now - 86400 * 10,  # 10 days ago
            "last_accessed": now - 86400 * 10,
        }

        mock_instance.async_load = AsyncMock(
            return_value={TEST_ENTRY_ID: [recent_fact, expired_fact]}
        )
        memory_store.set_hass(hass)

        facts = await memory_store.async_get_facts()

        fact_texts = [f["fact"] for f in facts]
        assert "Recent" in fact_texts
        assert "Expired" not in fact_texts

    @pytest.mark.asyncio
    async def test_cleanup_expired_disabled(self, memory_store, hass, mock_store):
        """Test that expiry cleanup can be disabled."""
        _mock_cls, mock_instance = mock_store
        memory_store._expiry_days = 0

        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {
                        "id": "1",
                        "fact": "Old fact",
                        "created_at": 0.0,
                        "last_accessed": 0.0,
                    },
                ]
            }
        )
        memory_store.set_hass(hass)

        facts = await memory_store.async_get_facts()

        assert len(facts) == 1


class TestMemoryStoreEdgeCases:
    """Test MemoryStore edge cases."""

    @pytest.mark.asyncio
    async def test_save_without_load(self, memory_store, hass, mock_store):
        """Test that save works even without loading first."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={})
        memory_store.set_hass(hass)

        memory_store._memories = [{"id": "1", "fact": "Direct fact"}]
        await memory_store.async_save()

        mock_instance.async_save.assert_called_once()

    def test_enforce_max_count_removes_oldest(self, memory_store):
        """Test _enforce_max_count removes oldest memories."""
        memory_store._max_count = 2
        memory_store._memories = [
            {"id": "1", "fact": "Oldest", "created_at": 100.0},
            {"id": "2", "fact": "Middle", "created_at": 200.0},
            {"id": "3", "fact": "Newest", "created_at": 300.0},
        ]

        memory_store._enforce_max_count()

        assert len(memory_store._memories) == 2
        assert memory_store._memories[0]["fact"] == "Middle"
        assert memory_store._memories[1]["fact"] == "Newest"

    def test_enforce_max_count_under_limit(self, memory_store):
        """Test _enforce_max_count does nothing when under limit."""
        memory_store._max_count = 10
        memory_store._memories = [
            {"id": "1", "fact": "Only one", "created_at": 100.0},
        ]

        memory_store._enforce_max_count()

        assert len(memory_store._memories) == 1

    def test_enforce_max_count_empty(self, memory_store):
        """Test _enforce_max_count handles empty list."""
        memory_store._memories = []
        memory_store._enforce_max_count()
        assert memory_store._memories == []

    @pytest.mark.asyncio
    async def test_add_fact_timestamp(self, memory_store, hass, mock_store):
        """Test add_fact sets created_at and last_accessed timestamps."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: []})
        memory_store.set_hass(hass)

        await memory_store.async_add_fact("Timed fact")

        memory = memory_store._memories[0]
        assert memory["created_at"] > 0
        assert memory["last_accessed"] == memory["created_at"]

    @pytest.mark.asyncio
    async def test_get_facts_updates_last_accessed(
        self, memory_store, hass, mock_store
    ):
        """Test get_facts updates last_accessed timestamps."""
        _mock_cls, mock_instance = mock_store
        now = time.time()
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [
                    {
                        "id": "1",
                        "fact": "Fact",
                        "created_at": now,
                        "last_accessed": now,
                    },
                ]
            }
        )
        memory_store.set_hass(hass)

        before = time.time()
        await memory_store.async_get_facts()
        after = time.time()

        fact = memory_store._memories[0]
        assert before <= fact["last_accessed"] <= after


class TestMemoryStoreSaveEdgeCases:
    """Test edge cases in async_save and add_fact truncation."""

    @pytest.mark.asyncio
    async def test_async_save_without_hass_returns_early(
        self, memory_store, mock_store
    ):
        """Test async_save is a no-op when _store is None (line 57-58)."""
        _mock_cls, mock_instance = mock_store
        memory_store._store = None
        memory_store._memories = [{"id": "1", "fact": "Should not save"}]

        await memory_store.async_save()

        mock_instance.async_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_save_when_load_returns_none(
        self, memory_store, hass, mock_store
    ):
        """Test async_save when existing store data is None (line 61-62)."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value=None)
        memory_store.set_hass(hass)
        memory_store._memories = [{"id": "1", "fact": "New fact"}]

        await memory_store.async_save()

        saved_data = mock_instance.async_save.call_args[0][0]
        assert saved_data == {TEST_ENTRY_ID: [{"id": "1", "fact": "New fact"}]}

    @pytest.mark.asyncio
    async def test_add_fact_truncates_long_content(
        self, memory_store, hass, mock_store
    ):
        """Test that facts longer than MAX_FACT_LENGTH are truncated (line 116)."""
        from custom_components.minimax.memory import MAX_FACT_LENGTH

        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: []})
        memory_store.set_hass(hass)

        long_fact = "x" * (MAX_FACT_LENGTH + 100)

        await memory_store.async_add_fact(long_fact)

        stored = memory_store._memories[0]["fact"]
        assert len(stored) == MAX_FACT_LENGTH
        assert stored == "x" * MAX_FACT_LENGTH

    @pytest.mark.asyncio
    async def test_add_fact_strips_invalid_control_chars(
        self, memory_store, hass, mock_store
    ):
        """Test that add_fact strips invalid control characters."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(return_value={TEST_ENTRY_ID: []})
        memory_store.set_hass(hass)

        dirty_fact = "Hello\x00World\x01Foo\x07Bar"
        await memory_store.async_add_fact(dirty_fact)

        stored = memory_store._memories[0]["fact"]
        assert "\x00" not in stored
        assert "\x01" not in stored
        assert "\x07" not in stored
        assert stored == "HelloWorldFooBar"

    @pytest.mark.asyncio
    async def test_add_fact_inserts_at_beginning(self, memory_store, hass, mock_store):
        """Test that new facts are inserted at the beginning of the list."""
        _mock_cls, mock_instance = mock_store
        mock_instance.async_load = AsyncMock(
            return_value={
                TEST_ENTRY_ID: [{"id": "old", "fact": "Old", "created_at": 100.0}]
            }
        )
        memory_store.set_hass(hass)

        await memory_store.async_add_fact("New fact")

        assert memory_store._memories[0]["fact"] == "New fact"
        assert memory_store._memories[1]["fact"] == "Old"
