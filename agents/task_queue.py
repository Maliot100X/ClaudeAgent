"""Agent task queue and scheduling."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import asyncio
import uuid


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    """Represents a task for an agent."""
    task_id: str
    agent_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

    @classmethod
    def create(
        cls,
        agent_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_for: Optional[datetime] = None
    ) -> "AgentTask":
        """Create a new task."""
        return cls(
            task_id=str(uuid.uuid4()),
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            created_at=datetime.utcnow(),
            scheduled_for=scheduled_for or datetime.utcnow(),
        )


class BaseTaskQueue(ABC):
    """Abstract base class for task queues."""

    @abstractmethod
    async def enqueue(self, task: AgentTask) -> None:
        """Add a task to the queue."""
        pass

    @abstractmethod
    async def dequeue(
        self,
        agent_id: Optional[str] = None
    ) -> Optional[AgentTask]:
        """Get next task from queue."""
        pass

    @abstractmethod
    async def complete(
        self,
        task_id: str,
        result: Any
    ) -> None:
        """Mark task as completed."""
        pass

    @abstractmethod
    async def fail(
        self,
        task_id: str,
        error: str
    ) -> None:
        """Mark task as failed."""
        pass

    @abstractmethod
    async def get_pending(
        self,
        agent_id: Optional[str] = None
    ) -> List[AgentTask]:
        """Get pending tasks."""
        pass

    @abstractmethod
    async def get_task(
        self,
        task_id: str
    ) -> Optional[AgentTask]:
        """Get task by ID."""
        pass


class InMemoryTaskQueue(BaseTaskQueue):
    """In-memory task queue for development."""

    def __init__(self):
        self._tasks: Dict[str, AgentTask] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

    async def enqueue(self, task: AgentTask) -> None:
        """Add task to queue."""
        self._tasks[task.task_id] = task
        await self._queue.put((task.priority.value, task.created_at, task.task_id))

    async def dequeue(
        self,
        agent_id: Optional[str] = None
    ) -> Optional[AgentTask]:
        """Get next available task."""
        while not self._queue.empty():
            _, _, task_id = await self._queue.get()
            task = self._tasks.get(task_id)

            if not task:
                continue

            if task.status != TaskStatus.PENDING:
                continue

            if agent_id and task.agent_id != agent_id:
                # Put back if not for this agent
                await self._queue.put((task.priority.value, task.created_at, task_id))
                continue

            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            return task

        return None

    async def complete(self, task_id: str, result: Any) -> None:
        """Mark task as completed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.utcnow()

    async def fail(self, task_id: str, error: str) -> None:
        """Mark task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.retry_count += 1

            if task.retry_count >= task.max_retries:
                task.status = TaskStatus.FAILED
                task.error = error
                task.completed_at = datetime.utcnow()
            else:
                # Retry
                task.status = TaskStatus.PENDING
                await self._queue.put((task.priority.value, task.created_at, task_id))

    async def get_pending(
        self,
        agent_id: Optional[str] = None
    ) -> List[AgentTask]:
        """Get pending tasks."""
        tasks = [
            t for t in self._tasks.values()
            if t.status == TaskStatus.PENDING
            and (not agent_id or t.agent_id == agent_id)
        ]
        return sorted(tasks, key=lambda t: (t.priority.value, t.created_at))

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)


class TaskScheduler:
    """Schedules and manages agent tasks."""

    def __init__(
        self,
        queue: Optional[BaseTaskQueue] = None
    ):
        self.queue = queue or InMemoryTaskQueue()
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_handler(
        self,
        task_type: str,
        handler: Callable
    ) -> None:
        """
        Register a task handler.

        Args:
            task_type: Type of task
            handler: Async function to handle task
        """
        self._handlers[task_type] = handler

    async def schedule(
        self,
        agent_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        delay_seconds: Optional[int] = None
    ) -> AgentTask:
        """
        Schedule a new task.

        Args:
            agent_id: Agent to execute task
            task_type: Type of task
            payload: Task data
            priority: Task priority
            delay_seconds: Delay before execution

        Returns:
            Created task
        """
        from datetime import timedelta

        scheduled_for = datetime.utcnow()
        if delay_seconds:
            scheduled_for += timedelta(seconds=delay_seconds)

        task = AgentTask.create(
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            scheduled_for=scheduled_for
        )

        await self.queue.enqueue(task)
        return task

    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                task = await self.queue.dequeue()

                if task:
                    handler = self._handlers.get(task.task_type)

                    if handler:
                        try:
                            result = await handler(task)
                            await self.queue.complete(task.task_id, result)
                        except Exception as e:
                            await self.queue.fail(task.task_id, str(e))
                    else:
                        await self.queue.fail(
                            task.task_id,
                            f"No handler for task type: {task.task_type}"
                        )
                else:
                    # No tasks, wait a bit
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(1)

    async def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        # This would need proper implementation with counting
        return {
            "registered_handlers": list(self._handlers.keys()),
            "running": self._running,
        }
