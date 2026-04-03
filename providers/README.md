# Provider Abstraction Layer

This module provides a unified interface for multiple LLM providers.

## Architecture

```
providers/
├── base.py          # Abstract base class
├── fireworks.py     # Fireworks AI provider
├── gemini.py        # Google Gemini provider
├── ollama.py        # Local Ollama provider
├── openai.py        # OpenAI compatible APIs
└── factory.py       # Provider factory
```

## Usage

```python
from providers import ProviderFactory

provider = ProviderFactory.create(
    provider="fireworks",
    api_key="your_key",
    model="accounts/fireworks/routers/kimi-k2p5-turbo"
)

# Generate response
response = await provider.generate(
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7
)

# Stream response
async for chunk in provider.stream(
    messages=[{"role": "user", "content": "Hello"}]
):
    print(chunk)

# Tool calling
response = await provider.tool_call(
    messages=[{"role": "user", "content": "Get price of BTC"}],
    tools=[market_data_tool],
    available_functions={"get_price": get_price_func}
)
```

## Supported Providers

| Provider | Endpoint | Models |
|----------|----------|--------|
| Fireworks | https://api.fireworks.ai/inference/v1 | Kimi K2.5 Turbo, Llama, Qwen |
| Gemini | https://generativelanguage.googleapis.com | Gemini Pro, Flash |
| Ollama | http://localhost:11434 | Local models |
| OpenAI | https://api.openai.com/v1 | GPT-4, GPT-3.5 |

## Environment Configuration

```bash
# Provider selection
MODEL_PROVIDER=fireworks  # fireworks, gemini, ollama, openai
MODEL_NAME=accounts/fireworks/routers/kimi-k2p5-turbo

# API Keys
FIREWORKS_API_KEY=fw_...
GOOGLE_API_KEY=AIza...
OPENAI_API_KEY=sk-...
OLLAMA_HOST=http://localhost:11434
```

## Adding New Providers

1. Create new file in `providers/`
2. Inherit from `BaseProvider`
3. Implement `generate()`, `stream()`, `tool_call()`
4. Register in `factory.py`
