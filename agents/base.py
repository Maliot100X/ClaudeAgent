"""Base agent class and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type
import uuid

from providers import BaseProvider, GenerationResponse


class AgentState(Enum):
    """Agent execution states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class AgentStatus(Enum):
    """Agent health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str
    goal: str
    model: str = "accounts/fireworks/routers/kimi-k2p5-turbo"
    provider_type: str = "fireworks"
    skills: List[str] = field(default_factory=list)
    memory_enabled: bool = True
    max_iterations: int = 10
    schedule: Optional[str] = None  # Cron expression
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Runtime context for an agent."""
    agent_id: str
    state: AgentState = AgentState.IDLE
    status: AgentStatus = AgentStatus.UNKNOWN
    last_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    current_task: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class AgentAction:
    """Represents an action taken by an agent."""
    action_id: str
    agent_id: str
    action_type: str
    timestamp: datetime
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    skill_name: Optional[str] = None
    tool_calls: List[Dict] = field(default_factory=list)
    reasoning: Optional[str] = None
    latency_ms: float = 0.0


class BaseSkill(ABC):
    """Base class for agent skills."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Optional[Dict] = None
    ):
        self.name = name
        self.description = description
        self.parameters = parameters or {}
        self._agent: Optional["BaseAgent"] = None

    @property
    def agent(self) -> Optional["BaseAgent"]:
        """Get the agent this skill is attached to."""
        return self._agent

    @agent.setter
    def agent(self, agent: "BaseAgent"):
        """Set the agent reference."""
        self._agent = agent

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the skill.

        Args:
            **kwargs: Skill-specific parameters

        Returns:
            Dictionary with skill output
        """
        pass

    def to_tool_schema(self) -> Dict:
        """Convert skill to tool schema for LLM."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def __repr__(self) -> str:
        return f"<Skill {self.name}>"


class BaseAgent(ABC):
    """Base class for autonomous agents."""

    def __init__(
        self,
        config: AgentConfig,
        provider: BaseProvider
    ):
        self.config = config
        self.provider = provider
        self.context = AgentContext(agent_id=config.agent_id)
        self.skills: Dict[str, BaseSkill] = {}
        self._available_functions: Dict[str, Callable] = {}
        self._conversation_history: List[Dict[str, str]] = []
        self._tool_call_history: List[Dict] = []
        self._running = False
        self._error: Optional[str] = None

    @property
    def agent_id(self) -> str:
        """Return agent ID."""
        return self.config.agent_id

    @property
    def state(self) -> AgentState:
        """Return current state."""
        return self.context.state

    @property
    def status(self) -> AgentStatus:
        """Return current status."""
        return self.context.status

    def register_skill(self, skill: BaseSkill) -> None:
        """
        Register a skill with the agent.

        Args:
            skill: Skill instance to register
        """
        skill.agent = self
        self.skills[skill.name] = skill
        self._available_functions[skill.name] = skill.execute

    def unregister_skill(self, skill_name: str) -> None:
        """
        Unregister a skill.

        Args:
            skill_name: Name of skill to remove
        """
        if skill_name in self.skills:
            del self.skills[skill_name]
            del self._available_functions[skill_name]

    def get_skill_schemas(self) -> List[Dict]:
        """Get all skill schemas as tool definitions."""
        return [skill.to_tool_schema() for skill in self.skills.values()]

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to conversation history.

        Args:
            role: Message role (system, user, assistant)
            content: Message content
        """
        self._conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history = []

    def get_history(self, limit: int = 100) -> List[Dict[str, str]]:
        """
        Get recent conversation history.

        Args:
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        return self._conversation_history[-limit:]

    @abstractmethod
    async def scan(self) -> Dict[str, Any]:
        """
        Scan data sources for inputs.

        Returns:
            Dictionary of collected data
        """
        pass

    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze data using LLM.

        Args:
            data: Data to analyze

        Returns:
            Analysis results
        """
        pass

    @abstractmethod
    async def act(self, analysis: Dict[str, Any]) -> AgentAction:
        """
        Take action based on analysis.

        Args:
            analysis: Analysis results

        Returns:
            Record of action taken
        """
        pass

    @abstractmethod
    async def run_cycle(self) -> AgentAction:
        """
        Execute one agent cycle.

        Returns:
            Record of actions in this cycle
        """
        pass

    async def generate_reasoning(
        self,
        system_prompt: str,
        user_prompt: str,
        use_tools: bool = True
    ) -> GenerationResponse:
        """
        Generate reasoning using LLM.

        Args:
            system_prompt: System context
            user_prompt: User query
            use_tools: Whether to enable tool calling

        Returns:
            Generation response from LLM
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        if use_tools and self.skills:
            return await self.provider.tool_call(
                messages=messages,
                tools=self.get_skill_schemas(),
                available_functions=self._available_functions
            )
        else:
            return await self.provider.generate(messages=messages)

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "goal": self.config.goal,
            "state": self.state.value,
            "status": self.status.value,
            "model": self.config.model,
            "provider": self.provider.provider_name,
            "skills": list(self.skills.keys()),
            "run_count": self.context.run_count,
            "error_count": self.context.error_count,
            "last_run": self.context.last_run.isoformat() if self.context.last_run else None,
            "config": self.config.config,
            "metadata": self.config.metadata
        }

    def __repr__(self) -> str:
        return f"<Agent {self.agent_id} ({self.state.value})>"
