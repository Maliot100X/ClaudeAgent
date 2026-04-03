"""Google Gemini provider implementation."""

import json
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import Content, GenerationConfig, Tool

from .base import (
    BaseProvider,
    GenerationResponse,
    ProviderConfig,
    ProviderType,
    StreamChunk,
    ToolCall,
)


class GeminiProvider(BaseProvider):
    """
    Google Gemini provider.

    API Endpoint: https://generativelanguage.googleapis.com
    Models: gemini-1.5-pro, gemini-1.5-flash, gemini-1.0-pro
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        if config is None:
            config = ProviderConfig.from_env()
            config.provider_type = ProviderType.GEMINI

        super().__init__(config)

        if not config.api_key:
            raise ValueError("GOOGLE_API_KEY is required for Gemini provider")

        genai.configure(api_key=config.api_key)

        # Map model names
        self.model_name = self._map_model_name(config.model)
        self.model = genai.GenerativeModel(self.model_name)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _map_model_name(self, model: str) -> str:
        """Map generic model names to Gemini model names."""
        model_map = {
            "gemini-pro": "gemini-1.5-pro",
            "gemini-flash": "gemini-1.5-flash",
            "gemini-1.5-pro": "gemini-1.5-pro",
            "gemini-1.5-flash": "gemini-1.5-flash",
        }
        return model_map.get(model, model)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> GenerationResponse:
        """Generate response using Gemini."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        try:
            # Convert messages to Gemini format
            contents = self._convert_messages_to_gemini(messages)

            # Build generation config
            gen_config = GenerationConfig(
                temperature=temp,
                max_output_tokens=tokens,
            )

            # Build tools if provided
            gemini_tools = None
            if tools:
                gemini_tools = self._convert_tools_to_gemini(tools)

            # Generate
            response = await self.model.generate_content_async(
                contents,
                generation_config=gen_config,
                tools=gemini_tools,
                **kwargs
            )

            # Extract tool calls if present
            tool_calls = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    parts = candidate.content.parts
                    tool_calls = self._extract_tool_calls_from_parts(parts)

            # Get text content
            text_content = ""
            if hasattr(response, 'text'):
                text_content = response.text

            return GenerationResponse(
                content=text_content,
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                    "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                    "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
                },
                finish_reason="stop",
                tool_calls=tool_calls,
                raw_response=response,
            )

        except Exception as e:
            raise ProviderError(f"Gemini generation failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response from Gemini."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        try:
            contents = self._convert_messages_to_gemini(messages)

            gen_config = GenerationConfig(
                temperature=temp,
                max_output_tokens=tokens,
            )

            response = await self.model.generate_content_async(
                contents,
                generation_config=gen_config,
                stream=True,
                **kwargs
            )

            async for chunk in response:
                text = ""
                if hasattr(chunk, 'text'):
                    text = chunk.text

                finish_reason = None
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    finish_reason = chunk.candidates[0].finish_reason.name if hasattr(chunk.candidates[0], 'finish_reason') else None

                yield StreamChunk(
                    content=text,
                    finish_reason=finish_reason,
                )

        except Exception as e:
            raise ProviderError(f"Gemini streaming failed: {str(e)}")

    async def tool_call(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        available_functions: Dict[str, Callable],
        temperature: Optional[float] = None,
        max_iterations: int = 5,
        **kwargs
    ) -> GenerationResponse:
        """Execute tool calling with Gemini."""
        temp = temperature if temperature is not None else self.config.temperature

        contents = self._convert_messages_to_gemini(messages)
        gemini_tools = self._convert_tools_to_gemini(tools)

        all_tool_calls = []

        for iteration in range(max_iterations):
            try:
                gen_config = GenerationConfig(temperature=temp)

                response = await self.model.generate_content_async(
                    contents,
                    generation_config=gen_config,
                    tools=gemini_tools,
                    **kwargs
                )

                # Check for function calls
                if response.candidates and response.candidates[0].content:
                    parts = response.candidates[0].content.parts

                    function_calls = [p for p in parts if hasattr(p, 'function_call') and p.function_call]

                    if function_calls:
                        # Execute function calls
                        function_responses = []

                        for part in function_calls:
                            fc = part.function_call
                            tool_name = fc.name
                            args = dict(fc.args) if hasattr(fc.args, 'items') else {}

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

                            function_responses.append({
                                "name": tool_name,
                                "response": {"result": result}
                            })

                            all_tool_calls.append(ToolCall(
                                id=str(uuid.uuid4()),
                                name=tool_name,
                                arguments=args
                            ))

                        # Add function responses to contents
                        contents.append({
                            "role": "model",
                            "parts": [{"function_call": {"name": fc.function_call.name, "args": dict(fc.function_call.args)}} for fc in function_calls]
                        })

                        contents.append({
                            "role": "user",
                            "parts": [{"function_response": {"name": fr["name"], "response": fr["response"]}} for fr in function_responses]
                        })

                    else:
                        # No function calls, return final response
                        text_content = ""
                        if hasattr(response, 'text'):
                            text_content = response.text

                        return GenerationResponse(
                            content=text_content,
                            usage={
                                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
                            },
                            finish_reason="stop",
                            tool_calls=all_tool_calls if all_tool_calls else None,
                            raw_response=response,
                        )

            except Exception as e:
                raise ProviderError(f"Gemini tool calling failed: {str(e)}")

        return GenerationResponse(
            content="Maximum tool call iterations reached",
            usage={},
            finish_reason="max_iterations",
            tool_calls=all_tool_calls if all_tool_calls else None,
        )

    def _convert_messages_to_gemini(
        self,
        messages: List[Dict[str, str]]
    ) -> List[Content]:
        """Convert OpenAI-style messages to Gemini format."""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map roles
            if role == "system":
                # System messages become user messages in Gemini
                contents.append(Content(role="user", parts=[{"text": f"System: {content}"}]))
            elif role == "user":
                contents.append(Content(role="user", parts=[{"text": content}]))
            elif role == "assistant":
                contents.append(Content(role="model", parts=[{"text": content}]))

        return contents

    def _convert_tools_to_gemini(self, tools: List[Dict]) -> List[Tool]:
        """Convert tool definitions to Gemini format."""
        gemini_tools = []

        for tool in tools:
            if "type" in tool and tool["type"] == "function":
                func = tool["function"]
            else:
                func = tool

            # Create function declaration
            func_decl = {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {})
            }

            gemini_tools.append(Tool(function_declarations=[func_decl]))

        return gemini_tools

    def _extract_tool_calls_from_parts(self, parts: List) -> Optional[List[ToolCall]]:
        """Extract tool calls from Gemini response parts."""
        tool_calls = []

        for part in parts:
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                args = dict(fc.args) if hasattr(fc.args, 'items') else {}

                tool_calls.append(ToolCall(
                    id=str(uuid.uuid4()),
                    name=fc.name,
                    arguments=args
                ))

        return tool_calls if tool_calls else None


class ProviderError(Exception):
    """Provider-specific error."""
    pass


import asyncio
