# AI Agent Platform

**Autonomous cryptocurrency trading and analysis platform** with paper trading simulation, multi-model AI support, Telegram control, and real-time dashboard.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)
![Next.js](https://img.shields.io/badge/Next.js-14-black)

## Quick Start

### Docker (Recommended)

```bash
# 1. Clone and setup
git clone <repo-url>
cd ai-agent-platform

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Start all services
docker-compose up -d

# 4. Check status
docker-compose ps
```

### Ubuntu Server (24/7 Operation)

```bash
# Run the automated deployment script
sudo bash scripts/deploy_ubuntu.sh

# Then start the system
ai-agent start

# Or use systemd
systemctl start ai-agent-platform
```

## Your Configuration

### Telegram Bot
- **Bot Token:** `8082924208:AAE3iuMrHb2Dn5EewFDpKOZBNCNhGtiySUI`
- **User ID:** `7764037225` (admin access)
- **Channel:** `ClaudeBot Signals` (`-1003703092807`) - receives trading signals

### AI Models (Ollama Cloud)
- **API Key:** `a4ab724ab8cc4e10bbf0441874f1582d.o8HnSICvioQnjB7sM9IyLdj5`
- **Available Models:**
  - `minimax-m2:cloud`
  - `deepseek-v3.2:cloud`
  - `glm-4.6:cloud`

### Environment Setup

Edit `.env`:

```bash
# Telegram (Required)
TELEGRAM_BOT_TOKEN=8082924208:AAE3iuMrHb2Dn5EewFDpKOZBNCNhGtiySUI
TELEGRAM_CHANNEL_ID=-1003703092807
TELEGRAM_ALLOWED_USERS=7764037225

# AI Provider - Ollama Cloud
MODEL_PROVIDER=ollama
OLLAMA_API_KEY=a4ab724ab8cc4e10bbf0441874f1582d.o8HnSICvioQnjB7sM9IyLdj5
OLLAMA_HOST=https://api.ollama.com
MODEL_NAME=minimax-m2:cloud

# Alternative: Fireworks AI
# MODEL_PROVIDER=fireworks
# FIREWORKS_API_KEY=your_fireworks_key
# MODEL_NAME=accounts/fireworks/routers/kimi-k2p5-turbo
```

## Features

### 🤖 Agent System
- Multi-agent runtime with lifecycle management
- Skill-based plugin architecture
- Memory system (short-term + long-term with pgvector)
- Task queue with Celery workers

### 🧠 AI Models
- **Fireworks AI** - `accounts/fireworks/routers/kimi-k2p5-turbo`
- **Ollama Cloud** - minimax-m2, deepseek-v3.2, glm-4.6
- **Google Gemini** - gemini-pro, gemini-1.5
- **OpenAI** - gpt-4, gpt-3.5-turbo
- Switch models via Telegram: `/models` or `/provider <name>`

### 📊 Trading Strategies
- **Momentum** - RSI + MACD indicators
- **Mean Reversion** - Bollinger Bands
- **Breakout** - Support/Resistance levels
- Paper trading engine with PnL tracking
- Real-time signal broadcasting to Telegram

### 💬 Telegram Control
Commands:
- `/start` - Welcome and setup
- `/status` - System health
- `/agents` - List active agents
- `/signals` - View trading signals
- `/positions` - Paper trading portfolio
- `/models` - View/switch AI models
- `/provider <name>` - Change AI provider
- `/test_provider` - Test current provider
- `/strategies` - List strategies
- `/run_strategy` - Start trading
- `/help` - Full command list

### 🌐 Dashboard
- Next.js + TypeScript + TailwindCSS
- Real-time WebSocket updates
- 3D visualizations with Three.js
- Responsive mobile design

### 🏗️ Infrastructure
- **Backend:** FastAPI + PostgreSQL + Redis
- **Frontend:** Next.js (deployable to Vercel)
- **Workers:** Celery + Redis
- **Containers:** Docker + Docker Compose
- **Monitoring:** Health checks + logging

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Agent Platform                       │
├─────────────────────────────────────────────────────────────┤
│  Telegram Bot    │   Next.js Dashboard   │   REST API       │
│  (Control)       │   (Visualization)     │   (Integration)  │
└────────┬─────────┴───────────┬───────────┴────────┬──────────┘
         │                   │                    │
         └───────────────────┼────────────────────┘
                             ▼
                   ┌──────────────────┐
                   │   Agent Runtime  │
                   │   (LangGraph)    │
                   └────────┬─────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌───────────┐     ┌───────────┐     ┌───────────┐
  │  Skills   │     │ Strategies│     │ Providers │
  │ • Market  │     │ • Momentum│     │ • Ollama  │
  │ • Signal  │     │ • MeanRev │     │ •Fireworks│
  │ • Risk    │     │ • Breakout│     │ • Gemini  │
  └───────────┘     └───────────┘     └───────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
              ┌──────────────────────────┐
              │   Data & Communication   │
              │  PostgreSQL + Redis + WS │
              └──────────────────────────┘
```

## Project Structure

```
ai-agent-platform/
├── agents/              # Agent runtime, memory, registry
├── api/                 # FastAPI routes (REST + WebSocket)
├── database/            # SQLAlchemy models
├── docs/                # Documentation
├── frontend/            # Next.js dashboard
├── providers/           # LLM provider implementations
├── scripts/             # Deployment scripts
├── services/            # Market data adapters
├── skills/              # Agent skills/plugins
├── strategies/          # Trading strategies
├── telegram/            # Telegram bot
├── docker-compose.yml   # Docker orchestration
├── requirements.txt     # Python dependencies
└── .env.example         # Environment template
```

## Telegram Commands

### System Control
```
/status          - System health overview
/models          - View/switch AI models
/provider <name> - Change provider (fireworks, ollama, gemini, openai)
/test_provider   - Test current AI provider
```

### Trading
```
/signals         - Recent trading signals
/positions       - Paper trading portfolio
/strategies      - List available strategies
/run_strategy    - Start a new strategy
/stop_strategy   - Stop running strategy
```

### Agents
```
/agents          - List all agents
/agent_<id>_start - Start specific agent
/agent_<id>_stop  - Stop specific agent
```

## Ubuntu Management

The `ai-agent` command manages the entire platform:

```bash
ai-agent start        # Start all services
ai-agent stop         # Stop all services
ai-agent restart      # Restart services
ai-agent status       # View service status
ai-agent logs api     # View API logs
ai-agent logs telegram-bot  # View bot logs
ai-agent health       # Run health check
ai-agent backup       # Create backup
ai-agent update       # Update to latest version
```

## Deployment Modes

### 1. Docker Compose (Development)
```bash
docker-compose up -d
```

### 2. Ubuntu Systemd (Production 24/7)
```bash
sudo bash scripts/deploy_ubuntu.sh
systemctl enable ai-agent-platform
systemctl start ai-agent-platform
```

### 3. Vercel Dashboard (Frontend Only)
```bash
cd frontend
npm install
vercel --prod
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/agents` | List agents |
| `POST /api/v1/providers/set` | Switch AI provider |
| `GET /api/v1/providers/models` | List all models |
| `GET /api/v1/signals` | Trading signals |
| `GET /api/v1/paper-trading/portfolio` | Portfolio status |
| `WS /ws` | WebSocket real-time |

Full API docs at `/docs` when running.

## Monitoring

### Health Checks
- API health: `curl http://localhost:8000/health`
- Service status: `ai-agent status`
- Logs: `ai-agent logs <service>`

### Logs Location
- Docker: `docker-compose logs -f <service>`
- Ubuntu: `/var/log/ai-agent/`
- Systemd: `journalctl -u ai-agent-api -f`

## Security

- API keys stored in environment variables
- Telegram user ID whitelist
- No credentials in code
- Docker internal networking
- .env files excluded from git

## Documentation

- [Architecture Guide](docs/ARCHITECTURE.md) - System design
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Production setup
- [Developer Guide](docs/DEVELOPER_GUIDE.md) - Contributing
- [API Reference](docs/API_REFERENCE.md) - API documentation
- [Technology Report](docs/TECHNOLOGY_SELECTION_REPORT.md) - Stack choices

## Support

- Telegram: Message your bot `@YourBot`
- Logs: Check `ai-agent logs`
- Issues: Review health check output

## License

MIT License - See LICENSE file

---

**Built with:** FastAPI • Next.js • PostgreSQL • Redis • Docker • Telegram Bot API • Multiple LLM Providers
