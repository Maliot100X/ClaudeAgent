# Agent Runtime

This module provides the core agent execution system.

## Architecture

```
agents/
├── runtime.py       # Agent runtime engine
├── base.py          # Base agent class
├── memory.py        # Agent memory management
├── task_queue.py    # Task queue management
├── registry.py      # Skill registry
└── loop.py          # Agent execution loop
```

## Agent Lifecycle

1. **Initialize** - Load configuration, skills, memory
2. **Register** - Register with runtime
3. **Run** - Execute agent loop
4. **Scan** - Collect data inputs
5. **Analyze** - Process data with LLM
6. **Act** - Execute skills/tool calls
7. **Log** - Record actions
8. **Broadcast** - Send updates

## Agent Configuration

```python
agent_config = {
    "agent_id": "btc_analyzer_01",
    "goal": "Monitor BTC price and generate trading signals",
    "model": "accounts/fireworks/routers/kimi-k2p5-turbo",
    "skills": ["market_data", "signal_generation"],
    "memory_enabled": True,
    "schedule": "*/5 * * * *"  # Every 5 minutes
}
```

## Usage

```python
from agents import AgentRuntime, Agent

# Create runtime
runtime = AgentRuntime()

# Create agent
agent = Agent(
    agent_id="signal_generator",
    goal="Generate trading signals",
    provider=provider,
    skills=[market_skill, signal_skill]
)

# Register and run
runtime.register_agent(agent)
await runtime.start()
```

## Agent Loop

The agent loop executes continuously:

```
while running:
    1. Scan data sources
    2. Analyze with LLM
    3. Call skills if needed
    4. Generate signals
    5. Log actions
    6. Broadcast state
    7. Sleep until next cycle
```

## Memory System

- **Short-term**: Current conversation context
- **Long-term**: Persistent storage in PostgreSQL
- **Vector memory**: Embeddings for similar past decisions

## Task Queue

- Tasks scheduled via Celery
- Priority-based execution
- Retry logic for failures
