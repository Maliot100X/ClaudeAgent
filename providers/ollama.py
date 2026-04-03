"""Ollama provider for local LLM execution."""

import json
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import aiohttp

from .base import (
    BaseProvider,
    GenerationResponse,
    ProviderConfig,
    ProviderType,
    StreamChunk,
    ToolCall,
)


class OllamaProvider(BaseProvider):
    """
    Ollama provider for local LLM execution.

    Default endpoint: http://localhost:11434
    Supports tool calling for compatible models.
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        if config is None:
            config = ProviderConfig.from_env()
            config.provider_type = ProviderType.OLLAMA

        super().__init__(config)

        self.base_url = config.base_url or "http://localhost:11434"
        self.model = config.model or "llama3.1"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        return self.session

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> GenerationResponse:
        """Generate response using Ollama."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        try:
            session = await self._get_session()

            # Convert messages to Ollama format
            ollama_messages = self._convert_messages(messages)

            # Build request
            payload = {
                "model": self.model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": temp,
                    "num_predict": tokens,
                }
            }

            # Add tools if provided
            if tools:
                payload["tools"] = self._convert_tools(tools)

            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise ProviderError(f"Ollama error: {text}")

                data = await response.json()

                # Extract content
                message = data.get("message", {})
                content = message.get("content", "")

                # Extract tool calls
                tool_calls = None
                if "tool_calls" in message:
                    tool_calls = [
                        ToolCall(
                            id=str(uuid.uuid4()),
                            name=tc.get("function", {}).get("name", ""),
                            arguments=tc.get("function", {}).get("arguments", {})
                        )
                        for tc in message["tool_calls"]
                    ]

                # Extract usage
                usage = {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                }

                return GenerationResponse(
                    content=content,
                    usage=usage,
                    finish_reason="stop",
                    tool_calls=tool_calls,
                    raw_response=data,
                )

        except Exception as e:
            raise ProviderError(f"Ollama generation failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response from Ollama."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        try:
            session = await self._get_session()

            ollama_messages = self._convert_messages(messages)

            payload = {
                "model": self.model,
                "messages": ollama_messages,
                "stream": True,
                "options": {
                    "temperature": temp,
                    "num_predict": tokens,
                }
            }

            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise ProviderError(f"Ollama error: {text}")

                async for line in response.content:
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        message = data.get("message", {})
                        content = message.get("content", "")

                        done = data.get("done", False)

                        yield StreamChunk(
                            content=content,
                            finish_reason="stop" if done else None,
                        )

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            raise ProviderError(f"Ollama streaming failed: {str(e)}")

    async def tool_call(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        available_functions: Dict[str, Callable],
        temperature: Optional[float] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> GenerationResponse:
        """Execute tool calling with Ollama."""
        temp = temperature if temperature is not None else self.config.temperature

        all_messages = list(messages)
        all_tool_calls = []

        ollama_tools = self._convert_tools(tools)

        for iteration in range(max_iterations):
            try:
                session = await self._get_session()

                ollama_messages = self._convert_messages(all_messages)

                payload = {
                    "model": self.model,
                    "messages": ollama_messages,
                    "stream": False,
                    "tools": ollama_tools,
                    "options": {
                        "temperature": temp,
                    }
                }

                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise ProviderError(f"Ollama error: {text}")

                    data = await response.json()

                    message = data.get("message", {})
                    content = message.get("content", "")

                    # Check for tool calls
                    if "tool_calls" in message:
                        tool_calls = message["tool_calls"]

                        # Add assistant message with tool calls
                        all_messages.append({
                            "role": "assistant",
                            "content": content,
                            "tool_calls": tool_calls
                        })

                        # Execute each tool call
                        for tc in tool_calls:
                            func_data = tc.get("function", {})
                            tool_name = func_data.get("name", "")
                            args = func_data.get("arguments", {})

                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except:
                                    args = {"raw": args}

                            if tool_name not in available_functions:
                                result = f"Error: Tool '{tool_name}' not found"
                            else:
                                try:
                                    func = available_functions[tool_name]
                                    if asyncio.iscoroutinefunction(func):
                                        result = await func(**args)
                                    else:
                                        result = func(**args)

                                    if not isinstance(result, str):
                                        result = json.dumps(result)

                                except Exception as e:
                                    result = f"Error executing {tool_name}: {str(e)}"

                            # Add tool response
                            all_messages.append({
                                "role": "tool",
                                "content": str(result)
                            })

                            all_tool_calls.append(ToolCall(
                                id=str(uuid.uuid4()),
                                name=tool_name,
                                arguments=args
                            ))
                    else:
                        # No tool calls, return final response
                        usage = {
                            "prompt_tokens": data.get("prompt_eval_count", 0),
                            "completion_tokens": data.get("eval_count", 0),
                            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                        }

                        return GenerationResponse(
                            content=content,
                            usage=usage,
                            finish_reason="stop",
                            tool_calls=all_tool_calls if all_tool_calls else None,
                            raw_response=data,
                        )

            except Exception as e:
                raise ProviderError(f"Ollama tool calling failed: {str(e)}")

        return GenerationResponse(
            content="Maximum tool call iterations reached",
            usage={},
            finish_reason="max_iterations",
            tool_calls=all_tool_calls if all_tool_calls else None,
        )

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert messages to Ollama format."""
        converted = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Ollama uses same role names
            converted_msg = {
                "role": role,
                "content": content
            }

            # Handle tool calls and responses
            if "tool_calls" in msg:
                converted_msg["tool_calls"] = msg["tool_calls"]

            converted.append(converted_msg)

        return converted

    def _convert_tools(self, tools: List[Dict]) -> List[Dict]:
        """Convert tools to Ollama format."""
        ollama_tools = []

        for tool in tools:
            if "type" in tool and tool["type"] == "function":
                func = tool["function"]
            else:
                func = tool

            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {})
                }
            })

        return ollama_tools

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()


class ProviderError(Exception):
    """Provider-specific error."""
    pass


import asyncio
