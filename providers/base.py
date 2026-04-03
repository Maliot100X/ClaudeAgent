"""Base provider interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import os


class ProviderType(Enum):
    """Supported LLM provider types."""
    FIREWORKS = "fireworks"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENAI = "openai"


@dataclass
class ProviderConfig:
    """Configuration for LLM providers."""
    provider_type: ProviderType
    api_key: Optional[str] = None
    model: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        """Create config from environment variables."""
        provider_type = ProviderType(
            os.getenv("MODEL_PROVIDER", "fireworks")
        )

        # Get API key based on provider
        api_key = None
        if provider_type == ProviderType.FIREWORKS:
            api_key = os.getenv("FIREWORKS_API_KEY")
        elif provider_type == ProviderType.GEMINI:
            api_key = os.getenv("GOOGLE_API_KEY")
        elif provider_type == ProviderType.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")

        # Get base URL
        base_url = os.getenv("MODEL_BASE_URL")
        if not base_url:
            if provider_type == ProviderType.FIREWORKS:
                base_url = "https://api.fireworks.ai/inference/v1"
            elif provider_type == ProviderType.OLLAMA:
                base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        return cls(
            provider_type=provider_type,
            api_key=api_key,
            model=os.getenv("MODEL_NAME", "accounts/fireworks/routers/kimi-k2p5-turbo"),
            base_url=base_url,
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MODEL_MAX_TOKENS", "4096")),
            timeout=int(os.getenv("MODEL_TIMEOUT", "60")),
        )


@dataclass
class ToolCall:
    """Represents a tool/function call from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class GenerationResponse:
    """Standard response from LLM generation."""
    content: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    raw_response: Optional[Any] = None


@dataclass
class StreamChunk:
    """Single chunk from streaming response."""
    content: str
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> GenerationResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional list of tool definitions
            **kwargs: Provider-specific parameters

        Returns:
            GenerationResponse with content and metadata
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream response from the LLM.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Yields:
            StreamChunk objects with incremental content
        """
        pass

    @abstractmethod
    async def tool_call(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        available_functions: Dict[str, Callable],
        temperature: Optional[float] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> GenerationResponse:
        """
        Execute tool calling with the LLM.

        Args:
            messages: List of message dicts
            tools: List of tool schema definitions
            available_functions: Dict mapping tool names to callables
            temperature: Sampling temperature
            max_iterations: Maximum tool call iterations
            **kwargs: Provider-specific parameters

        Returns:
            GenerationResponse with final content and all tool calls
        """
        pass

    def _format_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Format messages for provider. Override in subclass if needed.

        Args:
            messages: Raw message list

        Returns:
            Formatted messages
        """
        return messages

    def _format_tools(
        self,
        tools: List[Dict]
    ) -> List[Dict]:
        """
        Format tool definitions for provider. Override in subclass if needed.

        Args:
            tools: Raw tool definitions

        Returns:
            Formatted tools
        """
        return tools

    def _parse_tool_calls(
        self,
        raw_tool_calls: Any
    ) -> List[ToolCall]:
        """
        Parse provider-specific tool calls to standard format.

        Args:
            raw_tool_calls: Raw tool call data from provider

        Returns:
            List of standardized ToolCall objects
        """
        tool_calls = []
        if raw_tool_calls:
            for tc in raw_tool_calls:
                tool_calls.append(ToolCall(
                    id=getattr(tc, 'id', str(hash(tc))),
                    name=getattr(tc, 'function', {}).get('name', '') if hasattr(tc, 'function') else tc.get('name', ''),
                    arguments=getattr(tc, 'function', {}).get('arguments', {}) if hasattr(tc, 'function') else tc.get('arguments', {})
                ))
        return tool_calls
