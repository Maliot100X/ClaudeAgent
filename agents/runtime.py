"""Agent runtime and execution engine."""

from typing import Any, Callable, Dict, List, Optional
import asyncio
import signal
import sys
from datetime import datetime

from .base import AgentAction, AgentConfig, AgentContext, AgentState, AgentStatus, BaseAgent
from .memory import AgentMemory, BaseMemoryStore, InMemoryStore
from .task_queue import AgentTask, TaskPriority, TaskScheduler


class AgentRuntime:
    """
    Runtime engine for managing and executing agents.

    Responsibilities:
    - Agent lifecycle management
    - Task scheduling
    - State broadcasting
    - Health monitoring
    """

    def __init__(
        self,
        memory_store: Optional[BaseMemoryStore] = None
    ):
        self.agents: Dict[str, BaseAgent] = {}
        self.scheduler = TaskScheduler()
        self.memory_store = memory_store or InMemoryStore()
        self._running = False
        self._broadcast_handlers: List[Callable] = []
        self._agent_tasks: Dict[str, asyncio.Task] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        """
        Register an agent with the runtime.

        Args:
            agent: Agent instance to register
        """
        self.agents[agent.agent_id] = agent

        # Create memory for agent
        agent_memory = AgentMemory(
            agent_id=agent.agent_id,
            store=self.memory_store
        )
        agent._memory = agent_memory

    def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister an agent.

        Args:
            agent_id: Agent to remove
        """
        if agent_id in self.agents:
            agent = self.agents[agent_id]

            # Stop if running
            if agent.state == AgentState.RUNNING:
                self.stop_agent(agent_id)

            del self.agents[agent_id]

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """List all registered agent IDs."""
        return list(self.agents.keys())

    def on_broadcast(self, handler: Callable) -> None:
        """
        Register a broadcast handler.

        Args:
            handler: Function to call with broadcast messages
        """
        self._broadcast_handlers.append(handler)

    async def _broadcast(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Broadcast an event to all handlers.

        Args:
            event_type: Type of event
            data: Event data
        """
        message = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        for handler in self._broadcast_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                print(f"Broadcast handler error: {e}")

    async def start_agent(
        self,
        agent_id: str,
        continuous: bool = True
    ) -> bool:
        """
        Start an agent.

        Args:
            agent_id: Agent to start
            continuous: Whether to run continuously

        Returns:
            True if started successfully
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        if agent.state == AgentState.RUNNING:
            return True

        agent.context.state = AgentState.RUNNING
        agent.context.status = AgentStatus.HEALTHY
        agent._running = True

        if continuous:
            # Start continuous loop
            task = asyncio.create_task(self._agent_loop(agent_id))
            self._agent_tasks[agent_id] = task

        await self._broadcast(
            "agent_started",
            {"agent_id": agent_id, "continuous": continuous}
        )

        return True

    async def stop_agent(self, agent_id: str) -> bool:
        """
        Stop an agent.

        Args:
            agent_id: Agent to stop

        Returns:
            True if stopped successfully
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False

        agent._running = False
        agent.context.state = AgentState.STOPPED

        # Cancel task if running
        task = self._agent_tasks.get(agent_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._agent_tasks[agent_id]

        await self._broadcast(
            "agent_stopped",
            {"agent_id": agent_id}
        )

        return True

    async def pause_agent(self, agent_id: str) -> bool:
        """Pause an agent temporarily."""
        agent = self.agents.get(agent_id)
        if not agent or agent.state != AgentState.RUNNING:
            return False

        agent.context.state = AgentState.PAUSED

        await self._broadcast(
            "agent_paused",
            {"agent_id": agent_id}
        )

        return True

    async def resume_agent(self, agent_id: str) -> bool:
        """Resume a paused agent."""
        agent = self.agents.get(agent_id)
        if not agent or agent.state != AgentState.PAUSED:
            return False

        agent.context.state = AgentState.RUNNING

        await self._broadcast(
            "agent_resumed",
            {"agent_id": agent_id}
        )

        return True

    async def run_agent_once(self, agent_id: str) -> Optional[AgentAction]:
        """
        Run a single agent cycle.

        Args:
            agent_id: Agent to run

        Returns:
            Action taken or None
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        try:
            action = await agent.run_cycle()

            # Update context
            agent.context.last_run = datetime.utcnow()
            agent.context.run_count += 1

            # Record memory
            if hasattr(agent, '_memory'):
                await agent._memory.remember(
                    content=f"Action: {action.action_type} - {action.reasoning}",
                    memory_type="action",
                    metadata={
                        "action_id": action.action_id,
                        "skill_name": action.skill_name
                    }
                )

            # Broadcast
            await self._broadcast(
                "agent_action",
                {
                    "agent_id": agent_id,
                    "action": {
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "skill_name": action.skill_name,
                        "timestamp": action.timestamp.isoformat(),
                        "reasoning": action.reasoning
                    }
                }
            )

            return action

        except Exception as e:
            agent.context.error_count += 1
            agent.context.status = AgentStatus.WARNING if agent.context.error_count < 5 else AgentStatus.CRITICAL

            await self._broadcast(
                "agent_error",
                {
                    "agent_id": agent_id,
                    "error": str(e)
                }
            )

            return None

    async def _agent_loop(self, agent_id: str) -> None:
        """
        Continuous loop for an agent.

        Args:
            agent_id: Agent to run
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return

        while agent._running:
            try:
                if agent.state == AgentState.PAUSED:
                    await asyncio.sleep(1)
                    continue

                await self.run_agent_once(agent_id)

                # Wait for next cycle
                # Default: 5 minutes, can be configured per agent
                interval = agent.config.config.get("cycle_interval", 300)
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Agent loop error for {agent_id}: {e}")
                await asyncio.sleep(5)

    async def start(self) -> None:
        """Start the runtime."""
        self._running = True

        # Start scheduler
        await self.scheduler.start()

        # Setup signal handlers
        self._setup_signal_handlers()

        await self._broadcast(
            "runtime_started",
            {"agents": list(self.agents.keys())}
        )

    async def stop(self) -> None:
        """Stop the runtime and all agents."""
        self._running = False

        # Stop all agents
        for agent_id in list(self.agents.keys()):
            await self.stop_agent(agent_id)

        # Stop scheduler
        await self.scheduler.stop()

        await self._broadcast(
            "runtime_stopped",
            {}
        )

    def _setup_signal_handlers(self) -> None:
        """Setup OS signal handlers."""
        def signal_handler(sig, frame):
            print(f"\nReceived signal {sig}, shutting down...")
            asyncio.create_task(self.stop())
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def get_status(self) -> Dict[str, Any]:
        """Get runtime status."""
        return {
            "running": self._running,
            "agents": {
                agent_id: {
                    "state": agent.state.value,
                    "status": agent.status.value,
                    "run_count": agent.context.run_count,
                    "error_count": agent.context.error_count,
                    "last_run": agent.context.last_run.isoformat() if agent.context.last_run else None,
                }
                for agent_id, agent in self.agents.items()
            },
            "scheduler": await self.scheduler.get_stats()
        }

    async def schedule_task(
        self,
        agent_id: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> AgentTask:
        """
        Schedule a task for an agent.

        Args:
            agent_id: Target agent
            task_type: Type of task
            payload: Task data
            priority: Task priority

        Returns:
            Created task
        """
        return await self.scheduler.schedule(
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
            priority=priority
        )
