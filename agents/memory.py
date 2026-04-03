"""Agent memory management system."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
import uuid


class MemoryEntry:
    """A single memory entry."""

    def __init__(
        self,
        content: str,
        memory_type: str = "conversation",
        metadata: Optional[Dict] = None,
        agent_id: Optional[str] = None
    ):
        self.id = str(uuid.uuid4())
        self.content = content
        self.memory_type = memory_type  # conversation, action, observation, insight
        self.metadata = metadata or {}
        self.agent_id = agent_id
        self.timestamp = datetime.utcnow()
        self.embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "metadata": self.metadata,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseMemoryStore(ABC):
    """Abstract base class for memory stores."""

    @abstractmethod
    async def add(self, entry: MemoryEntry) -> None:
        """Add a memory entry."""
        pass

    @abstractmethod
    async def get(
        self,
        memory_id: str
    ) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Search memories by query."""
        pass

    @abstractmethod
    async def get_recent(
        self,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get recent memories."""
        pass

    @abstractmethod
    async def clear(
        self,
        agent_id: Optional[str] = None
    ) -> None:
        """Clear memories for an agent."""
        pass


class InMemoryStore(BaseMemoryStore):
    """In-memory memory store for development/testing."""

    def __init__(self):
        self._memories: Dict[str, MemoryEntry] = {}

    async def add(self, entry: MemoryEntry) -> None:
        """Add a memory entry."""
        self._memories[entry.id] = entry

    async def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        return self._memories.get(memory_id)

    async def search(
        self,
        query: str,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Simple text search in memories."""
        results = []
        for memory in self._memories.values():
            if agent_id and memory.agent_id != agent_id:
                continue
            if memory_type and memory.memory_type != memory_type:
                continue
            if query.lower() in memory.content.lower():
                results.append(memory)
        return sorted(results, key=lambda m: m.timestamp, reverse=True)[:limit]

    async def get_recent(
        self,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get recent memories."""
        memories = [
            m for m in self._memories.values()
            if (not agent_id or m.agent_id == agent_id)
            and (not memory_type or m.memory_type == memory_type)
        ]
        return sorted(memories, key=lambda m: m.timestamp, reverse=True)[:limit]

    async def clear(self, agent_id: Optional[str] = None) -> None:
        """Clear memories."""
        if agent_id:
            self._memories = {
                k: v for k, v in self._memories.items()
                if v.agent_id != agent_id
            }
        else:
            self._memories.clear()


class AgentMemory:
    """Agent memory manager."""

    def __init__(
        self,
        agent_id: str,
        store: Optional[BaseMemoryStore] = None
    ):
        self.agent_id = agent_id
        self.store = store or InMemoryStore()
        self._short_term: List[MemoryEntry] = []  # Session memory
        self._max_short_term = 20

    async def remember(
        self,
        content: str,
        memory_type: str = "conversation",
        metadata: Optional[Dict] = None
    ) -> MemoryEntry:
        """
        Store a memory.

        Args:
            content: Memory content
            memory_type: Type of memory
            metadata: Additional metadata

        Returns:
            Created memory entry
        """
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            agent_id=self.agent_id
        )

        # Add to short-term memory
        self._short_term.append(entry)
        if len(self._short_term) > self._max_short_term:
            self._short_term.pop(0)

        # Persist to long-term store
        await self.store.add(entry)

        return entry

    async def recall(
        self,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """
        Search for relevant memories.

        Args:
            query: Search query
            memory_type: Filter by type
            limit: Maximum results

        Returns:
            List of matching memories
        """
        # First search short-term
        short_results = [
            m for m in reversed(self._short_term)
            if query.lower() in m.content.lower()
            and (not memory_type or m.memory_type == memory_type)
        ][:limit]

        # Then search long-term
        long_results = await self.store.search(
            query=query,
            agent_id=self.agent_id,
            memory_type=memory_type,
            limit=limit - len(short_results)
        )

        return short_results + long_results

    async def get_recent_context(
        self,
        memory_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """
        Get recent memory context.

        Args:
            memory_type: Filter by type
            limit: Maximum results

        Returns:
            List of recent memories
        """
        # Combine short-term and long-term
        short = [
            m for m in reversed(self._short_term)
            if not memory_type or m.memory_type == memory_type
        ][:limit // 2]

        long = await self.store.get_recent(
            agent_id=self.agent_id,
            memory_type=memory_type,
            limit=limit - len(short)
        )

        return short + long

    def get_short_term_context(self, limit: int = 10) -> str:
        """Get short-term memory as context string."""
        entries = self._short_term[-limit:]
        return "\n".join([
            f"[{e.memory_type}] {e.content}"
            for e in entries
        ])

    async def clear(self) -> None:
        """Clear all memories for this agent."""
        self._short_term = []
        await self.store.clear(agent_id=self.agent_id)

    async def summarize(self) -> str:
        """Generate a summary of agent's memories."""
        recent = await self.get_recent_context(limit=20)
        return f"Agent has {len(self._short_term)} short-term and {len(recent)} long-term memories"
