# Developer Guide

Guide for developers contributing to or extending the AI Agent Platform.

## Getting Started

### Local Development Setup

```bash
# Clone repository
git clone <repo-url>
cd ai-agent-platform

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your development credentials

# Setup database (requires PostgreSQL)
# Start PostgreSQL and Redis locally, or use Docker:
docker-compose up -d postgres redis

# Run migrations
# (If using Alembic - add migration commands here)

# Start development server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start the agent runtime
python -m agents.runtime

# Start Telegram bot
python run_telegram_bot.py
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:3000

## Project Structure

```
ai-agent-platform/
├── agents/           # Agent runtime and core components
├── api/              # FastAPI REST API
├── database/         # Database models and migrations
├── docs/             # Documentation
├── frontend/         # Next.js dashboard
├── infra/            # Infrastructure configs
├── providers/        # LLM provider implementations
├── scripts/          # Deployment and utility scripts
├── services/         # Market data services
├── skills/           # Agent skills/plugins
├── strategies/       # Trading strategies
├── telegram/         # Telegram bot
└── tests/            # Test suite
```

## Creating a New Skill

Skills are plugins that agents can call. Here's how to create one:

### 1. Create Skill File

```python
# skills/my_custom_skill.py
from typing import Dict, Any
from .base import BaseSkill, SkillContext, SkillResult

class MyCustomSkill(BaseSkill):
    """Description of what this skill does."""

    name = "my_custom_skill"
    description = "Performs custom analysis"

    inputs = {
        "symbol": {
            "type": "string",
            "description": "Trading pair symbol",
            "required": True
        },
        "timeframe": {
            "type": "string",
            "description": "Analysis timeframe",
            "default": "1h"
        }
    }

    outputs = {
        "score": {
            "type": "number",
            "description": "Analysis score"
        },
        "recommendation": {
            "type": "string",
            "description": "Recommendation text"
        }
    }

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute the skill."""
        symbol = context.inputs.get("symbol")
        timeframe = context.inputs.get("timeframe", "1h")

        # Your logic here
        result = await self._analyze(symbol, timeframe)

        return SkillResult(
            success=True,
            outputs=result,
            metadata={"execution_time": 0.5}
        )

    async def _analyze(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        # Implementation
        pass
```

### 2. Register the Skill

```python
# skills/__init__.py
from .my_custom_skill import MyCustomSkill

# Add to skill list
__all__ = [
    # ... existing skills
    "MyCustomSkill",
]
```

### 3. Use in Agent

```python
from agents.base import Agent
from skills import MyCustomSkill

agent = Agent(
    agent_id="trading_agent",
    skills=[MyCustomSkill],
    # ... other config
)
```

## Creating a New Provider

To add support for a new LLM provider:

### 1. Implement Provider Class

```python
# providers/my_provider.py
from typing import AsyncGenerator
from .base import BaseProvider, ProviderConfig
from .base import GenerationResponse, StreamChunk, ToolCall

class MyProvider(BaseProvider):
    """Provider implementation for My LLM service."""

    @property
    def provider_name(self) -> str:
        return "my_provider"

    def _initialize_client(self):
        # Initialize your API client
        import my_provider_sdk
        self._client = my_provider_sdk.Client(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )

    async def generate(
        self,
        prompt: str,
        **kwargs
    ) -> GenerationResponse:
        """Generate text completion."""
        response = await self._client.generate(
            model=self.config.model,
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )

        return GenerationResponse(
            content=response.text,
            usage={
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens
            },
            finish_reason=response.finish_reason
        )

    async def stream(
        self,
        prompt: str,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream text completion."""
        stream = await self._client.generate_stream(
            model=self.config.model,
            prompt=prompt
        )

        async for chunk in stream:
            yield StreamChunk(
                content=chunk.text,
                finish_reason=chunk.finish_reason
            )

    async def tool_call(
        self,
        tools: list,
        messages: list,
        **kwargs
    ) -> list:
        """Execute tool calls."""
        # Implement tool calling logic
        pass
```

### 2. Register in Factory

```python
# providers/factory.py
from .my_provider import MyProvider
from .base import ProviderType

class ProviderFactory:
    _providers = {
        # ... existing providers
        ProviderType.MY_PROVIDER: MyProvider,
    }
```

### 3. Add to ProviderType Enum

```python
# providers/base.py
class ProviderType(Enum):
    FIREWORKS = "fireworks"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OPENAI = "openai"
    MY_PROVIDER = "my_provider"  # Add here
```

## Creating a New Strategy

Trading strategies analyze market data and generate signals.

### 1. Implement Strategy

```python
# strategies/my_strategy.py
from typing import Optional, List
from .base import BaseStrategy, Signal, SignalType
from services import MarketData

class MyStrategy(BaseStrategy):
    """Custom trading strategy."""

    name = "my_strategy"
    description = "Custom analysis strategy"

    def __init__(self):
        super().__init__()
        self.lookback_period = 20
        self.threshold = 0.02

    async def analyze(
        self,
        symbol: str,
        market_data: MarketData
    ) -> Optional[Signal]:
        """Analyze market data and generate signal."""
        # Fetch historical data
        data = await market_data.get_ohlcv(
            symbol=symbol,
            timeframe=self.timeframe,
            limit=self.lookback_period
        )

        if len(data) < self.lookback_period:
            return None

        # Your analysis logic
        signal_type = self._generate_signal(data)

        if signal_type:
            return Signal(
                id=self._generate_id(),
                symbol=symbol,
                type=signal_type,
                strength=self._calculate_strength(data),
                price=data[-1]["close"],
                reasoning="Custom strategy analysis",
                timestamp=datetime.utcnow(),
                strategy=self.name,
                metadata={"indicators": self._get_indicators(data)}
            )

        return None

    def _generate_signal(self, data: List[dict]) -> Optional[SignalType]:
        # Implement your logic
        pass
```

### 2. Register Strategy

```python
# strategies/__init__.py
from .my_strategy import MyStrategy

__all__ = [
    # ... existing strategies
    "MyStrategy",
]
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=agents --cov=strategies --cov-report=html
```

### Writing Tests

```python
# tests/test_my_skill.py
import pytest
from skills import MyCustomSkill

@pytest.fixture
def skill():
    return MyCustomSkill()

@pytest.mark.asyncio
async def test_skill_execution(skill):
    context = SkillContext(
        inputs={"symbol": "BTC-USD"},
        agent_id="test"
    )

    result = await skill.execute(context)

    assert result.success is True
    assert "score" in result.outputs
```

## Debugging

### Enable Debug Logging

```python
# In your script or .env
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Agent Debugging

```python
# agents/base.py
class Agent:
    async def run(self):
        self.logger.debug(f"Agent {self.agent_id} starting cycle")
        # Add breakpoints or detailed logging
```

### API Debugging

```bash
# Start with reload and debug
uvicorn api.main:app --reload --log-level debug
```

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Document with docstrings
- Maximum line length: 100

### TypeScript
- Use strict mode
- Prefer interfaces over types
- Document complex functions

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## Common Patterns

### Async Context Managers

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_resource():
    resource = await create_resource()
    try:
        yield resource
    finally:
        await resource.cleanup()
```

### Circuit Breaker Pattern

```python
from functools import wraps
import asyncio

def circuit_breaker(threshold=5, timeout=60):
    failures = 0
    last_failure = None

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal failures, last_failure

            if failures >= threshold:
                if last_failure and (time.time() - last_failure) < timeout:
                    raise Exception("Circuit breaker open")
                failures = 0

            try:
                result = await func(*args, **kwargs)
                failures = 0
                return result
            except Exception as e:
                failures += 1
                last_failure = time.time()
                raise e

        return wrapper
    return decorator
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Update documentation
6. Submit a pull request

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Next.js Documentation](https://nextjs.org/docs)
