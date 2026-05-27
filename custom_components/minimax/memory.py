"""Persistent memory storage for MiniMax conversation agent."""

import time
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_MEMORY_EXPIRY_DAYS, DEFAULT_MEMORY_MAX_COUNT, LOGGER

MEMORY_STORE_VERSION = 1
MEMORY_STORE_KEY = "minimax.memories"


class MemoryStore:
    """Persistent memory storage using HA's Store system."""

    def __init__(
        self,
        entry_id: str,
        max_count: int = DEFAULT_MEMORY_MAX_COUNT,
        expiry_days: int = DEFAULT_MEMORY_EXPIRY_DAYS,
    ) -> None:
        """Initialize memory store."""
        self._hass: HomeAssistant | None = None
        self._entry_id = entry_id
        self._max_count = max_count
        self._expiry_days = expiry_days
        self._store: Store[dict[str, list[dict]]] | None = None
        self._memories: list[dict] = []
        self._loaded = False

    def set_hass(self, hass: HomeAssistant) -> None:
        """Set the hass instance and initialize the store."""
        self._hass = hass
        self._store = Store(hass, MEMORY_STORE_VERSION, MEMORY_STORE_KEY)

    async def async_load(self) -> None:
        """Load memories from disk."""
        if self._loaded or self._store is None:
            return

        data = await self._store.async_load()
        if data is None:
            data = {}

        self._memories = data.get(self._entry_id, [])
        self._loaded = True
        LOGGER.debug(
            "Loaded %d memories for entry %s", len(self._memories), self._entry_id
        )

    async def async_save(self) -> None:
        """Save memories to disk."""
        if self._store is None:
            return

        data = await self._store.async_load()
        if data is None:
            data = {}

        data[self._entry_id] = self._memories
        await self._store.async_save(data)
        LOGGER.debug(
            "Saved %d memories for entry %s", len(self._memories), self._entry_id
        )

    def _enforce_max_count(self) -> None:
        """Remove oldest memories if over max count."""
        while len(self._memories) > self._max_count:
            oldest = min(
                self._memories, key=lambda m: m.get("created_at", float("inf"))
            )
            self._memories.remove(oldest)
            LOGGER.debug(
                "Removed oldest memory to enforce max count: %s",
                oldest.get("fact", "")[:50],
            )

    def _cleanup_expired(self) -> None:
        """Remove expired memories."""
        if self._expiry_days <= 0:
            return

        now = time.time()
        expiry_seconds = self._expiry_days * 24 * 60 * 60
        before_time = now - expiry_seconds

        before = len(self._memories)
        self._memories = [
            m
            for m in self._memories
            if m.get("last_accessed", m.get("created_at", 0)) > before_time
        ]
        removed = before - len(self._memories)

        if removed:
            LOGGER.debug("Cleaned up %d expired memories", removed)

    async def async_add_fact(
        self,
        fact: str,
        category: str = "other",
        source: str = "explicit",
    ) -> str:
        """Add a memory fact. Returns memory ID."""
        if not fact or not fact.strip():
            raise ValueError("Fact cannot be empty")

        await self.async_load()

        memory_id = str(uuid.uuid4())
        now = time.time()

        memory = {
            "id": memory_id,
            "fact": fact.strip(),
            "category": category,
            "source": source,
            "created_at": now,
            "last_accessed": now,
        }

        self._memories.insert(0, memory)
        self._enforce_max_count()
        await self.async_save()

        LOGGER.info("Added memory [%s]: %s", category, fact[:100])
        return memory_id

    async def async_get_facts(self) -> list[dict]:
        """Get all memories for this entry."""
        await self.async_load()
        self._cleanup_expired()

        for memory in self._memories:
            memory["last_accessed"] = time.time()

        if self._memories:
            await self.async_save()

        return list(self._memories)

    async def async_remove_fact(self, fact_or_id: str) -> bool:
        """Remove a specific memory by fact text (partial match) or ID."""
        await self.async_load()

        fact_lower = fact_or_id.lower()

        for memory in self._memories[:]:
            if memory["id"] == fact_or_id or fact_lower in memory["fact"].lower():
                self._memories.remove(memory)
                LOGGER.info("Removed memory: %s", memory["fact"][:100])
                await self.async_save()
                return True

        return False

    async def async_clear(self) -> None:
        """Clear all memories for this entry."""
        self._memories = []
        await self.async_save()
        LOGGER.info("Cleared all memories for entry %s", self._entry_id)

    async def async_get_memory_count(self) -> int:
        """Get the number of stored memories."""
        await self.async_load()
        return len(self._memories)
