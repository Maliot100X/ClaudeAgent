# API Reference

Complete API reference for the AI Agent Platform.

## Base URL

```
Development: http://localhost:8000
Production: https://your-domain.com/api
```

## Authentication

Most endpoints require JWT authentication via Bearer token:

```http
Authorization: Bearer <your-jwt-token>
```

## Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-04-03T12:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

---

## Agents

### List Agents

```http
GET /api/v1/agents
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| status | string | Filter by status (running, paused, stopped) |
| limit | integer | Max results (default: 50) |

**Response:**
```json
{
  "agents": [
    {
      "id": "trading_agent_001",
      "name": "Trading Agent",
      "status": "running",
      "goal": "Generate trading signals",
      "skills": ["market_data", "signal_generation"],
      "created_at": "2026-04-03T10:00:00Z",
      "last_active": "2026-04-03T12:00:00Z"
    }
  ],
  "total": 1
}
```

### Get Agent

```http
GET /api/v1/agents/{agent_id}
```

**Response:**
```json
{
  "id": "trading_agent_001",
  "name": "Trading Agent",
  "status": "running",
  "goal": "Generate trading signals",
  "skills": ["market_data", "signal_generation", "risk_analysis"],
  "config": {
    "check_interval": 60,
    "max_signals_per_hour": 10
  },
  "memory": {
    "short_term": [],
    "long_term_id": "mem_001"
  },
  "created_at": "2026-04-03T10:00:00Z",
  "last_active": "2026-04-03T12:00:00Z"
}
```

### Create Agent

```http
POST /api/v1/agents
Content-Type: application/json
```

**Request Body:**
```json
{
  "id": "my_agent",
  "name": "My Agent",
  "goal": "Analyze market trends",
  "skills": ["market_data", "signal_generation"],
  "config": {
    "check_interval": 60
  }
}
```

### Update Agent

```http
PUT /api/v1/agents/{agent_id}
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Updated Name",
  "config": {
    "check_interval": 120
  }
}
```

### Delete Agent

```http
DELETE /api/v1/agents/{agent_id}
```

### Control Agent

```http
POST /api/v1/agents/{agent_id}/control
Content-Type: application/json
```

**Request Body:**
```json
{
  "action": "start"  // start, pause, resume, stop, restart
}
```

### Get Agent Logs

```http
GET /api/v1/agents/{agent_id}/logs
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Max log entries |
| level | string | Filter by level (DEBUG, INFO, WARNING, ERROR) |

---

## Strategies

### List Strategies

```http
GET /api/v1/strategies
```

**Response:**
```json
{
  "strategies": [
    {
      "id": "momentum_btc",
      "name": "BTC Momentum",
      "type": "momentum",
      "status": "running",
      "symbol": "BTC-USD",
      "timeframe": "1h",
      "parameters": {
        "rsi_period": 14,
        "macd_fast": 12
      },
      "created_at": "2026-04-03T10:00:00Z"
    }
  ]
}
```

### Create Strategy

```http
POST /api/v1/strategies
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "BTC Momentum",
  "type": "momentum",
  "symbol": "BTC-USD",
  "timeframe": "1h",
  "parameters": {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30
  },
  "auto_start": true
}
```

### Control Strategy

```http
POST /api/v1/strategies/{strategy_id}/control
Content-Type: application/json
```

**Request Body:**
```json
{
  "action": "start"  // start, stop, pause
}
```

### Get Strategy Performance

```http
GET /api/v1/strategies/{strategy_id}/performance
```

**Response:**
```json
{
  "strategy_id": "momentum_btc",
  "total_signals": 45,
  "win_rate": 0.62,
  "profit_loss": 1250.50,
  "max_drawdown": 0.15,
  "sharpe_ratio": 1.2,
  "period": {
    "start": "2026-04-01T00:00:00Z",
    "end": "2026-04-03T12:00:00Z"
  }
}
```

---

## Signals

### List Signals

```http
GET /api/v1/signals
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| symbol | string | Filter by symbol |
| type | string | Filter by type (BUY, SELL, HOLD) |
| strategy | string | Filter by strategy |
| start_time | string | ISO timestamp |
| end_time | string | ISO timestamp |
| limit | integer | Max results (default: 50) |

**Response:**
```json
{
  "signals": [
    {
      "id": "sig_001",
      "symbol": "BTC-USD",
      "type": "BUY",
      "strength": 0.85,
      "price": 65000.00,
      "reasoning": "RSI oversold, MACD bullish crossover",
      "timestamp": "2026-04-03T12:00:00Z",
      "strategy": "momentum_btc",
      "executed": false
    }
  ],
  "total": 1
}
```

### Get Signal

```http
GET /api/v1/signals/{signal_id}
```

### Get Latest Signals

```http
GET /api/v1/signals/latest
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Number of signals (default: 10) |
| symbols | string | Comma-separated symbols |

---

## Paper Trading

### Get Portfolio

```http
GET /api/v1/paper-trading/portfolio
```

**Response:**
```json
{
  "balance": 8745.50,
  "initial_balance": 10000.00,
  "total_pnl": -1254.50,
  "total_pnl_percent": -12.55,
  "positions_count": 3,
  "last_updated": "2026-04-03T12:00:00Z"
}
```

### Get Positions

```http
GET /api/v1/paper-trading/positions
```

**Response:**
```json
{
  "positions": [
    {
      "id": "pos_001",
      "symbol": "BTC-USD",
      "side": "long",
      "entry_price": 65000.00,
      "current_price": 67000.00,
      "quantity": 0.5,
      "unrealized_pnl": 1000.00,
      "unrealized_pnl_percent": 3.08,
      "opened_at": "2026-04-02T10:00:00Z"
    }
  ]
}
```

### Get Trades

```http
GET /api/v1/paper-trading/trades
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| symbol | string | Filter by symbol |
| limit | integer | Max results |

**Response:**
```json
{
  "trades": [
    {
      "id": "trade_001",
      "symbol": "BTC-USD",
      "side": "buy",
      "price": 65000.00,
      "quantity": 0.5,
      "value": 32500.00,
      "pnl": null,
      "signal_id": "sig_001",
      "executed_at": "2026-04-02T10:00:00Z"
    }
  ]
}
```

### Reset Portfolio

```http
POST /api/v1/paper-trading/reset
```

**Response:**
```json
{
  "success": true,
  "message": "Portfolio reset to initial balance",
  "new_balance": 10000.00
}
```

---

## Providers (AI Models)

### List Available Providers

```http
GET /api/v1/providers
```

**Response:**
```json
{
  "providers": [
    {
      "id": "fireworks",
      "name": "Fireworks AI",
      "status": "active",
      "models": [
        "accounts/fireworks/routers/kimi-k2p5-turbo"
      ]
    },
    {
      "id": "ollama",
      "name": "Ollama",
      "status": "active",
      "models": [
        "minimax-m2:cloud",
        "deepseek-v3.2:cloud",
        "glm-4.6:cloud"
      ]
    }
  ]
}
```

### Get Current Provider

```http
GET /api/v1/providers/current
```

**Response:**
```json
{
  "provider": "fireworks",
  "model": "accounts/fireworks/routers/kimi-k2p5-turbo",
  "config": {
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

### Set Provider

```http
POST /api/v1/providers/set
Content-Type: application/json
```

**Request Body:**
```json
{
  "provider": "ollama",
  "model": "minimax-m2:cloud"
}
```

**Response:**
```json
{
  "success": true,
  "provider": "ollama",
  "model": "minimax-m2:cloud",
  "message": "Provider switched successfully"
}
```

### Test Provider

```http
POST /api/v1/providers/{provider_id}/test
```

**Response:**
```json
{
  "success": true,
  "latency_ms": 245,
  "test_output": "Hello! I am working correctly."
}
```

---

## Telegram Integration

### Get Bot Status

```http
GET /api/v1/telegram/status
```

**Response:**
```json
{
  "bot_username": "YourBot",
  "status": "running",
  "webhook_configured": true,
  "active_users": 5,
  "messages_sent_24h": 42
}
```

### Send Message

```http
POST /api/v1/telegram/send
Content-Type: application/json
```

**Request Body:**
```json
{
  "chat_id": "7764037225",
  "message": "Custom notification",
  "parse_mode": "Markdown"
}
```

### Broadcast to Channel

```http
POST /api/v1/telegram/broadcast
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "Important update!",
  "parse_mode": "HTML"
}
```

---

## Market Data

### Get Prices

```http
GET /api/v1/market/prices
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| symbols | string | Comma-separated symbols |

**Response:**
```json
{
  "prices": {
    "BTC-USD": {
      "price": 65000.00,
      "change_24h": 2.5,
      "volume_24h": 35000000000,
      "timestamp": "2026-04-03T12:00:00Z"
    }
  }
}
```

### Get OHLCV

```http
GET /api/v1/market/ohlcv/{symbol}
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| timeframe | string | 1m, 5m, 15m, 1h, 4h, 1d |
| limit | integer | Number of candles |

---

## WebSocket

Connect to WebSocket for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['signals', 'trades']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Message Types

**Client → Server:**
```json
// Subscribe to channels
{
  "type": "subscribe",
  "channels": ["signals", "trades", "agents"]
}

// Unsubscribe
{
  "type": "unsubscribe",
  "channels": ["trades"]
}

// Ping
{
  "type": "ping"
}
```

**Server → Client:**
```json
// Signal update
{
  "type": "signal",
  "data": {
    "id": "sig_001",
    "symbol": "BTC-USD",
    "type": "BUY",
    "price": 65000.00,
    "timestamp": "2026-04-03T12:00:00Z"
  }
}

// Trade update
{
  "type": "trade",
  "data": {
    "id": "trade_001",
    "symbol": "BTC-USD",
    "side": "buy",
    "price": 65000.00
  }
}

// Agent status
{
  "type": "agent_status",
  "data": {
    "agent_id": "trading_agent_001",
    "status": "running",
    "last_action": "signal_generated"
  }
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Agent not found",
    "details": {
      "agent_id": "invalid_id"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| BAD_REQUEST | 400 | Invalid request parameters |
| UNAUTHORIZED | 401 | Authentication required |
| FORBIDDEN | 403 | Insufficient permissions |
| RESOURCE_NOT_FOUND | 404 | Resource doesn't exist |
| CONFLICT | 409 | Resource conflict |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

---

## Rate Limiting

API endpoints are rate-limited:

| Endpoint Type | Limit |
|---------------|-------|
| Public (health, prices) | 100/minute |
| Authenticated | 1000/minute |
| WebSocket | 100 messages/minute |

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1712150400
```

---

## Pagination

List endpoints support pagination:

```http
GET /api/v1/signals?limit=20&offset=40
```

**Response includes:**
```json
{
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 40,
    "has_more": true
  }
}
```
