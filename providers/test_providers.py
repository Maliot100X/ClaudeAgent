"""Test script for provider implementations."""

import asyncio
import os

from providers import get_provider, ProviderFactory


async def test_fireworks():
    """Test Fireworks provider."""
    print("\n=== Testing Fireworks Provider ===")

    provider = get_provider(
        provider="fireworks",
        api_key=os.getenv("FIREWORKS_API_KEY"),
        model="accounts/fireworks/routers/kimi-k2p5-turbo"
    )

    # Test generate
    response = await provider.generate(
        messages=[{"role": "user", "content": "Say 'Hello from Fireworks!'"}]
    )
    print(f"Generate: {response.content[:50]}...")
    print(f"Usage: {response.usage}")

    # Test stream
    print("\nStream:")
    chunks = []
    async for chunk in provider.stream(
        messages=[{"role": "user", "content": "Count to 3"}]
    ):
        chunks.append(chunk.content)
    print(f"Stream result: {''.join(chunks)[:50]}...")

    print("✓ Fireworks provider working")


async def test_ollama():
    """Test Ollama provider."""
    print("\n=== Testing Ollama Provider ===")

    try:
        provider = get_provider(
            provider="ollama",
            model="llama3.1"
        )

        response = await provider.generate(
            messages=[{"role": "user", "content": "Say 'Hello from Ollama!'"}]
        )
        print(f"Generate: {response.content[:50]}...")
        print("✓ Ollama provider working")
    except Exception as e:
        print(f"✗ Ollama not available: {e}")


async def test_tool_calling():
    """Test tool calling functionality."""
    print("\n=== Testing Tool Calling ===")

    provider = get_provider(
        provider="fireworks",
        api_key=os.getenv("FIREWORKS_API_KEY"),
        model="accounts/fireworks/routers/kimi-k2p5-turbo"
    )

    # Define a simple tool
    def get_weather(location: str) -> str:
        return f"The weather in {location} is sunny and 72°F"

    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state"
                    }
                },
                "required": ["location"]
            }
        }
    }]

    available_functions = {"get_weather": get_weather}

    response = await provider.tool_call(
        messages=[{"role": "user", "content": "What's the weather in San Francisco?"}],
        tools=tools,
        available_functions=available_functions
    )

    print(f"Tool calls: {response.tool_calls}")
    print(f"Response: {response.content}")
    print("✓ Tool calling working")


async def main():
    """Run all tests."""
    print("Starting Provider Tests")
    print("=" * 50)

    # Check for API key
    if not os.getenv("FIREWORKS_API_KEY"):
        print("Warning: FIREWORKS_API_KEY not set")

    try:
        await test_fireworks()
    except Exception as e:
        print(f"✗ Fireworks test failed: {e}")

    try:
        await test_ollama()
    except Exception as e:
        print(f"✗ Ollama test failed: {e}")

    try:
        await test_tool_calling()
    except Exception as e:
        print(f"✗ Tool calling test failed: {e}")

    print("\n" + "=" * 50)
    print("Provider tests completed")


if __name__ == "__main__":
    asyncio.run(main())
