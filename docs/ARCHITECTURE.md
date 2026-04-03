# AI Agent Platform - System Architecture

## Overview

This document describes the technical architecture of the AI Agent Platform, a production-grade autonomous cryptocurrency trading and analysis system.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Agent Platform                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   Client Layer  │    │   Client Layer  │    │   Client Layer  │          │
│  │                 │    │                 │    │                 │          │
│  │  Telegram Bot   │    │  Next.js UI     │    │  REST API       │          │
│  │  (Remote Ctrl)  │    │  (Dashboard)    │    │  (Integration)  │          │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘          │
│           │                      │                      │                    │
│           └──────────────────────┼──────────────────────┘                    │
│                                  ▼                                           │
│                    ┌─────────────────────────┐                                 │
│                    │    FastAPI Gateway    │                                 │
│                    │    (API Layer)        │                                 │
│                    └───────────┬───────────┘                                 │
│                                │                                             │
│           ┌────────────────────┼────────────────────┐                        │
│           ▼                    ▼                    ▼                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │  WebSocket      │  │  REST Routes    │  │  Middleware     │              │
│  │  Manager        │  │  (Telegram/     │  │  (Auth/CORS/    │              │
│  │  (Real-time)    │  │   Agents/       │  │   Rate Limit)   │              │
│  │                 │  │   Strategies)   │  │                 │              │
│  └────────┬────────┘  └─────────────────┘  └─────────────────┘              │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐             │
│  │                    Agent Runtime Layer                       │             │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │             │
│  │  │   Agent     │  │   Memory    │  │   Task Queue        │   │             │
│  │  │   Base      │  │   System    │  │   (Celery/Redis)    │   │             │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │             │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │             │
│  │  │   Registry  │  │   Broadcast │  │   Coordinator       │   │             │
│  │  │   (Skills)  │  │   System    │  │   (LangGraph)       │   │             │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │             │
│  └─────────────────────────────────────────────────────────────┘             │
│                              │                                               │
│           ┌──────────────────┼──────────────────┐                          │
│           ▼                  ▼                  ▼                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │   Skill Layer   │  │  Strategy Layer │  │  Provider Layer │            │
│  │                 │  │                 │  │                 │            │
│  │ • Market Data   │  │ • Momentum      │  │ • Fireworks AI  │            │
│  │ • Signal Gen    │  │ • Mean Revert   │  │ • Google Gemini │            │
│  │ • Risk Analysis │  │ • Breakout      │  │ • OpenAI        │            │
│  │ • Backtest      │  │ • Paper Trading │  │ • Ollama (Local)│            │
│  │ • News Sentiment│  │                 │  │                 │            │
│  │ • Wallet Track  │  │                 │  │                 │            │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘            │
│           │                    │                                            │
│           └────────────────────┼────────────────────┐                     │
│                                ▼                    ▼                     │
│                   ┌─────────────────────┐  ┌─────────────────┐            │
│                   │  Market Data Layer  │  │  Data Layer     │            │
│                   │                     │  │                 │            │
│                   │ • CoinGecko        │  │ • PostgreSQL    │            │
│                   │ • DexScreener      │  │ • pgvector      │            │
│                   │ • CryptoCompare    │  │ • Redis Cache   │            │
│                   │ • WebSocket Feeds  │  │ • Celery        │            │
│                   └─────────────────────┘  └─────────────────┘            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Client Layer

#### Telegram Bot
- **Technology:** python-telegram-bot v20+
- **Purpose:** Remote control and monitoring interface
- **Features:**
  - Command-based interaction (/status, /agents, /run_strategy)
  - Real-time notifications to channels
  - Model/provider switching via commands
  - Inline keyboards for quick actions

#### Next.js Dashboard
- **Technology:** Next.js 14, TypeScript, TailwindCSS, Three.js
- **Purpose:** Web-based visualization and control
- **Features:**
  - Real-time WebSocket updates
  - 3D agent network visualization
  - Signal feed and performance charts
  - Agent conversation inspector

### 2. API Gateway (FastAPI)

**Responsibilities:**
- Request routing and validation
- Authentication and authorization
- WebSocket connection management
- Rate limiting and CORS
- API versioning

**Key Endpoints:**
- `/api/v1/agents/*` - Agent management
- `/api/v1/strategies/*` - Strategy control
- `/api/v1/signals/*` - Signal feed
- `/api/v1/telegram/*` - Bot integration
- `/ws/*` - WebSocket streams

### 3. Agent Runtime

**Core Components:**

#### Agent Base (`agents/base.py`)
- Abstract base class for all agents
- Lifecycle management (init → run → pause → stop)
- Memory integration
- Tool/skill registry

#### Memory System (`agents/memory.py`)
- Short-term: In-memory context window
- Long-term: PostgreSQL + pgvector for semantic search
- Conversation history tracking

#### Task Queue (`agents/task_queue.py`)
- Celery + Redis for distributed task processing
- Async task scheduling
- Retry logic and dead letter queues

#### Registry (`agents/registry.py`)
- Skill plugin management
- Dynamic skill loading
- Version tracking

#### Runtime (`agents/runtime.py`)
- Multi-agent coordination
- Broadcast system for events
- Health monitoring
- Graceful shutdown handling

### 4. Skill Layer

All skills implement the `BaseSkill` interface:

```python
class BaseSkill(ABC):
    name: str
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    
    async def execute(self, context: SkillContext) -> SkillResult:
        ...
```

**Implemented Skills:**

| Skill | Purpose | Key Features |
|-------|---------|--------------|
| Market Data | Fetch market data | Multi-source aggregation |
| Signal Generation | Generate trading signals | Technical indicators |
| Risk Analysis | Assess risk | Position sizing, drawdown |
| Strategy Backtest | Validate strategies | Historical simulation |
| News Sentiment | Analyze sentiment | NLP processing |
| Wallet Tracking | Monitor wallets | On-chain data |

### 5. Strategy Layer

#### Strategy Framework

```python
class BaseStrategy(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]
    
    async def analyze(self, data: MarketData) -> Optional[Signal]:
        ...
```

#### Implemented Strategies

**Momentum Strategy**
- Indicators: RSI, MACD
- Entry: RSI < 30 + MACD bullish crossover
- Exit: RSI > 70 + MACD bearish crossover

**Mean Reversion**
- Indicators: Bollinger Bands, RSI
- Entry: Price < lower band + RSI < 30
- Exit: Price > middle band or RSI > 50

**Breakout Strategy**
- Indicators: Support/Resistance levels, Volume
- Entry: Price breaks resistance with volume > 1.5x avg
- Exit: Stop loss at support, take profit at next resistance

#### Paper Trading Engine
- Virtual balance tracking
- Position management
- PnL calculation
- Risk limits (max position size, daily loss limit)
- Trade history logging

### 6. Provider Layer

All providers implement `BaseProvider`:

```python
class BaseProvider(ABC):
    async def generate(self, prompt: str, **kwargs) -> GenerationResponse
    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[StreamChunk]
    async def tool_call(self, tools: List[Tool], messages: List[Message]) -> ToolCallResult
```

**Supported Providers:**

| Provider | Endpoint | Models | Tool Calling |
|----------|----------|--------|--------------|
| Fireworks | api.fireworks.ai | kimi-k2p5-turbo | ✅ |
| Ollama | api.ollama.com | minimax-m2, deepseek-v3.2, glm-4.6 | ✅ |
| Gemini | googleapis.com | gemini-pro | ✅ |
| OpenAI | api.openai.com | gpt-4, gpt-3.5 | ✅ |

**Provider Switching:**
- Environment variable: `MODEL_PROVIDER`
- Runtime switching via Telegram: `/provider <name>`
- Model selection: `/models` command

### 7. Market Data Layer

#### Adapter Pattern

```python
class MarketDataAdapter(ABC):
    async def fetch_markets(self) -> List[Market]
    async def fetch_pairs(self, market: str) -> List[TradingPair]
    async def fetch_prices(self, symbols: List[str]) -> Dict[str, Price]
    async def stream_trades(self, symbols: List[str]) -> AsyncGenerator[Trade]
```

#### Data Sources

| Source | Type | Latency | Coverage |
|--------|------|---------|----------|
| CoinGecko | REST | ~1 min | All major coins |
| DexScreener | REST/WebSocket | Real-time | DEX pairs |
| CryptoCompare | REST/WebSocket | Real-time | Professional feeds |

### 8. Data Layer

#### PostgreSQL Schema

**Core Tables:**
- `agents` - Agent definitions and state
- `agent_logs` - Activity logs
- `signals` - Trading signals
- `positions` - Paper trading positions
- `trades` - Trade history
- `strategies` - Strategy configurations
- `provider_configs` - LLM provider settings

**Extensions:**
- `pgvector` - Vector similarity search
- `pg_trgm` - Text search

#### Redis Usage

- **Cache:** Market data, API responses
- **Pub/Sub:** Real-time updates
- **Queue:** Celery task broker
- **Session:** WebSocket connection state

## Data Flow

### Signal Generation Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Market  │────▶│  Agent   │────▶│  Skill   │────▶│  Signal  │
│  Data    │     │  Runtime │     │  Chain   │     │  Output  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
     ▲                                                  │
     │                                                  ▼
     │                                           ┌──────────┐
     │                                           │ Telegram │
     │                                           │ Channel  │
     │                                           └──────────┘
     │                                                  │
     └──────────────────────────────────────────────────┘
                    (Feedback Loop)
```

1. Market data ingested from multiple sources
2. Agent runtime processes data through skill chain
3. LLM provider generates analysis and signals
4. Signals broadcast to Telegram channel
5. Paper trading engine simulates execution
6. Results logged to database

## Deployment Architecture

### Docker Compose Stack

```
┌─────────────────────────────────────────┐
│           Docker Network                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │   API   │ │ Agent   │ │Telegram │   │
│  │ Server  │ │Runtime  │ │  Bot    │   │
│  └────┬────┘ └────┬────┘ └────┬────┘   │
│       │           │           │        │
│  ┌────┴───────────┴───────────┴────┐   │
│  │           PostgreSQL            │   │
│  └─────────────────────────────────┘   │
│       │                               │
│  ┌────┴────┐ ┌─────────┐              │
│  │  Redis  │ │ Ollama  │              │
│  └─────────┘ └─────────┘              │
└─────────────────────────────────────────┘
```

### Ubuntu Production Deployment

- Systemd services for each component
- Nginx reverse proxy with SSL
- Log rotation with logrotate
- Automatic restart on failure
- Health checks every 30s

## Security Considerations

1. **API Keys:** Stored in environment variables, never in code
2. **Database:** PostgreSQL with SSL, connection pooling
3. **Telegram:** User ID whitelist, channel moderation
4. **Dashboard:** JWT authentication, rate limiting
5. **Network:** Docker internal networking, no external DB exposure

## Scalability

- **Horizontal:** Multiple Celery workers
- **Vertical:** Async/await throughout
- **Caching:** Redis for hot data
- **Database:** Connection pooling, read replicas ready

## Monitoring

- Structured JSON logging
- Agent activity metrics
- Signal generation rate
- API response times
- Provider latency tracking
