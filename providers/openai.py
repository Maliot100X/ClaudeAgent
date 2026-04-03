"""OpenAI compatible provider implementation."""

import json
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from openai import AsyncOpenAI

from .base import (
    BaseProvider,
    GenerationResponse,
    ProviderConfig,
    ProviderType,
    StreamChunk,
    ToolCall,
)


class OpenAIProvider(BaseProvider):
    """
    OpenAI and OpenAI-compatible API provider.

    Default endpoint: https://api.openai.com/v1
    Supports all OpenAI models and compatible APIs.
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        if config is None:
            config = ProviderConfig.from_env()
            config.provider_type = ProviderType.OPENAI

        super().__init__(config)

        if not config.api_key:
            raise ValueError("OPENAI_API_KEY is required")

        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or "https://api.openai.com/v1",
            timeout=config.timeout,
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> GenerationResponse:
        """Generate response using OpenAI API."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        try:
            if tools:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    tools=tools,
                    tool_choice="auto",
                    **kwargs
                )
            else:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=tokens,
                    **kwargs
                )

            # Extract tool calls if present
            tool_calls = None
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                tool_calls = self._parse_tool_calls(response.choices[0].message.tool_calls)

            return GenerationResponse(
                content=response.choices[0].message.content or "",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason,
                tool_calls=tool_calls,
                raw_response=response,
            )

        except Exception as e:
            raise ProviderError(f"OpenAI generation failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response from OpenAI API."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta

                yield StreamChunk(
                    content=delta.content or "",
                    finish_reason=chunk.choices[0].finish_reason,
                    tool_calls=self._parse_tool_calls(delta.tool_calls) if hasattr(delta, 'tool_calls') and delta.tool_calls else None,
                )

        except Exception as e:
            raise ProviderError(f"OpenAI streaming failed: {str(e)}")

    async def tool_call(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        available_functions: Dict[str, Callable],
        temperature: Optional[float] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> GenerationResponse:
        """Execute tool calling with OpenAI API."""
        temp = temperature if temperature is not None else self.config.temperature

        all_messages = list(messages)
        all_tool_calls = []

        for iteration in range(max_iterations):
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=all_messages,
                    temperature=temp,
                    tools=tools,
                    tool_choice="auto",
                    **kwargs
                )

                message = response.choices[0].message

                # Check for tool calls
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    # Add assistant message with tool calls
                    all_messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tc in message.tool_calls:
                        tool_name = tc.function.name

                        if tool_name not in available_functions:
                            result = f"Error: Tool '{tool_name}' not found"
                        else:
                            try:
                                # Parse arguments
                                args = json.loads(tc.function.arguments)
                                # Execute function
                                func = available_functions[tool_name]
                                if asyncio.iscoroutinefunction(func):
                                    result = await func(**args)
                                else:
                                    result = func(**args)

                                # Convert result to string
                                if not isinstance(result, str):
                                    result = json.dumps(result)

                            except Exception as e:
                                result = f"Error executing {tool_name}: {str(e)}"

                        # Add tool response
                        all_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(result)
                        })

                        all_tool_calls.append(ToolCall(
                            id=tc.id,
                            name=tool_name,
                            arguments=args
                        ))
                else:
                    # No tool calls, return final response
                    return GenerationResponse(
                        content=message.content or "",
                        usage={
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                            "total_tokens": response.usage.total_tokens if response.usage else 0,
                        },
                        finish_reason=response.choices[0].finish_reason,
                        tool_calls=all_tool_calls if all_tool_calls else None,
                        raw_response=response,
                    )

            except Exception as e:
                raise ProviderError(f"OpenAI tool calling failed: {str(e)}")

        # Max iterations reached
        return GenerationResponse(
            content="Maximum tool call iterations reached",
            usage={},
            finish_reason="max_iterations",
            tool_calls=all_tool_calls if all_tool_calls else None,
        )

    def _parse_tool_calls(self, raw_tool_calls: Any) -> List[ToolCall]:
        """Parse OpenAI tool calls to standard format."""
        tool_calls = []
        if not raw_tool_calls:
            return tool_calls

        for tc in raw_tool_calls:
            if hasattr(tc, 'id'):
                # OpenAI object format
                function = tc.function
                args = function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {"raw": args}

                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=function.name,
                    arguments=args
                ))
            else:
                # Dict format
                tool_calls.append(ToolCall(
                    id=tc.get('id', str(uuid.uuid4())),
                    name=tc.get('name', tc.get('function', {}).get('name', '')),
                    arguments=tc.get('arguments', tc.get('function', {}).get('arguments', {}))
                ))

        return tool_calls


class ProviderError(Exception):
    """Provider-specific error."""
    pass


import asyncio
