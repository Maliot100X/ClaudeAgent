# Deployment Guide

Complete guide for deploying the AI Agent Platform on Ubuntu servers.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Production Deployment](#production-deployment)
4. [Ubuntu Server Setup](#ubuntu-server-setup)
5. [Systemd Services](#systemd-services)
6. [Environment Configuration](#environment-configuration)
7. [SSL/TLS Setup](#ssltls-setup)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- Ubuntu 22.04 LTS or newer
- Docker 24.0+ and Docker Compose
- Git
- Minimum 4GB RAM, 2 CPU cores
- 50GB free disk space

## Quick Start (Docker)

The fastest way to get running:

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd ai-agent-platform

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your credentials
nano .env

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps
```

Services will be available at:
- API: http://localhost:8000
- Dashboard: http://localhost:3000 (if running frontend separately)

## Production Deployment

### Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y git curl wget nano htop net-tools

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Step 2: Project Setup

```bash
# Create app directory
sudo mkdir -p /opt/ai-agent-platform
sudo chown $USER:$USER /opt/ai-agent-platform

# Clone repository
cd /opt
git clone <your-repo-url> ai-agent-platform
cd ai-agent-platform

# Create environment file
cp .env.example .env
nano .env  # Configure your settings
```

### Step 3: Configure Environment

Edit `.env` with your production settings:

```bash
# Telegram (Required)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-100xxxxxxxxx
TELEGRAM_ALLOWED_USERS=your_user_id

# AI Provider (Choose one)
MODEL_PROVIDER=fireworks
FIREWORKS_API_KEY=your_key

# Or use Ollama cloud
MODEL_PROVIDER=ollama
OLLAMA_API_KEY=your_key
OLLAMA_HOST=https://api.ollama.com
MODEL_NAME=minimax-m2:cloud

# Database (Docker internal)
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_agent_platform

# Redis (Docker internal)
REDIS_URL=redis://redis:6379/0

# Security (Generate strong keys)
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
```

### Step 4: Start Services

```bash
# Build and start
docker-compose up -d --build

# Verify all running
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f agent-runtime
docker-compose logs -f telegram-bot
```

## Ubuntu Server Setup (Without Docker)

For native deployment without Docker:

### 1. System Dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y postgresql-14 postgresql-contrib
sudo apt install -y redis-server
sudo apt install -y nginx
sudo apt install -y nodejs npm
```

### 2. PostgreSQL Setup

```bash
# Start PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE ai_agent_platform;
CREATE USER agent_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE ai_agent_platform TO agent_user;
\c ai_agent_platform
CREATE EXTENSION IF NOT EXISTS vector;
EOF
```

### 3. Redis Setup

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Test
redis-cli ping
```

### 4. Python Environment

```bash
cd /opt/ai-agent-platform
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Frontend Build

```bash
cd frontend
npm install
npm run build
```

## Systemd Services

Create systemd services for 24/7 operation:

### API Server Service

```bash
sudo tee /etc/systemd/system/ai-agent-api.service << 'EOF'
[Unit]
Description=AI Agent Platform API Server
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=ai-agent
Group=ai-agent
WorkingDirectory=/opt/ai-agent-platform
Environment=PATH=/opt/ai-agent-platform/venv/bin
EnvironmentFile=/opt/ai-agent-platform/.env
ExecStart=/opt/ai-agent-platform/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ai-agent/api.log
StandardError=append:/var/log/ai-agent/api.error.log

[Install]
WantedBy=multi-user.target
EOF
```

### Agent Runtime Service

```bash
sudo tee /etc/systemd/system/ai-agent-runtime.service << 'EOF'
[Unit]
Description=AI Agent Platform Runtime
After=network.target postgresql.service redis.service ai-agent-api.service

[Service]
Type=simple
User=ai-agent
Group=ai-agent
WorkingDirectory=/opt/ai-agent-platform
Environment=PATH=/opt/ai-agent-platform/venv/bin
EnvironmentFile=/opt/ai-agent-platform/.env
ExecStart=/opt/ai-agent-platform/venv/bin/python -m agents.runtime
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ai-agent/runtime.log
StandardError=append:/var/log/ai-agent/runtime.error.log

[Install]
WantedBy=multi-user.target
EOF
```

### Celery Worker Service

```bash
sudo tee /etc/systemd/system/ai-agent-worker.service << 'EOF'
[Unit]
Description=AI Agent Platform Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=ai-agent
Group=ai-agent
WorkingDirectory=/opt/ai-agent-platform
Environment=PATH=/opt/ai-agent-platform/venv/bin
EnvironmentFile=/opt/ai-agent-platform/.env
ExecStart=/opt/ai-agent-platform/venv/bin/celery -A agents.celery_config worker --loglevel=INFO --concurrency=4
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ai-agent/worker.log
StandardError=append:/var/log/ai-agent/worker.error.log

[Install]
WantedBy=multi-user.target
EOF
```

### Telegram Bot Service

```bash
sudo tee /etc/systemd/system/ai-agent-telegram.service << 'EOF'
[Unit]
Description=AI Agent Platform Telegram Bot
After=network.target ai-agent-api.service

[Service]
Type=simple
User=ai-agent
Group=ai-agent
WorkingDirectory=/opt/ai-agent-platform
Environment=PATH=/opt/ai-agent-platform/venv/bin
EnvironmentFile=/opt/ai-agent-platform/.env
ExecStart=/opt/ai-agent-platform/venv/bin/python run_telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ai-agent/telegram.log
StandardError=append:/var/log/ai-agent/telegram.error.log

[Install]
WantedBy=multi-user.target
EOF
```

### Enable All Services

```bash
# Create log directory
sudo mkdir -p /var/log/ai-agent
sudo chown ai-agent:ai-agent /var/log/ai-agent

# Create user
sudo useradd -r -s /bin/false ai-agent
sudo chown -R ai-agent:ai-agent /opt/ai-agent-platform

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable ai-agent-api ai-agent-runtime ai-agent-worker ai-agent-telegram
sudo systemctl start ai-agent-api ai-agent-runtime ai-agent-worker ai-agent-telegram

# Check status
sudo systemctl status ai-agent-api
sudo systemctl status ai-agent-telegram
```

## Environment Configuration

### Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_CHANNEL_ID` | Channel for signals (e.g., -1003703092807) | Yes |
| `MODEL_PROVIDER` | fireworks, ollama, gemini, openai | Yes |
| `FIREWORKS_API_KEY` | Fireworks AI API key | If using Fireworks |
| `OLLAMA_API_KEY` | Ollama cloud API key | If using Ollama |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `SECRET_KEY` | Random secret for security | Yes |

### Ollama Cloud Configuration

For Ollama cloud models (minimax-m2:cloud, deepseek-v3.2:cloud, glm-4.6:cloud):

```bash
MODEL_PROVIDER=ollama
OLLAMA_API_KEY=a4ab724ab8cc4e10bbf0441874f1582d.o8HnSICvioQnjB7sM9IyLdj5
OLLAMA_HOST=https://api.ollama.com
MODEL_NAME=minimax-m2:cloud
```

## SSL/TLS Setup

### Using Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

### Nginx Configuration

```bash
sudo tee /etc/nginx/sites-available/ai-agent << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/ai-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Troubleshooting

### Check Service Logs

```bash
# Docker logs
docker-compose logs -f <service-name>

# Systemd logs
sudo journalctl -u ai-agent-api -f
sudo journalctl -u ai-agent-telegram -f
```

### Common Issues

**PostgreSQL Connection Failed**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Verify database exists
sudo -u postgres psql -c "\l" | grep ai_agent
```

**Redis Connection Failed**
```bash
# Check Redis
redis-cli ping

# Check service
sudo systemctl status redis-server
```

**Telegram Bot Not Responding**
```bash
# Verify token
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# Check bot logs
docker-compose logs -f telegram-bot
# or
sudo journalctl -u ai-agent-telegram -f
```

**Model Provider Errors**
```bash
# Test provider
cd /opt/ai-agent-platform
source venv/bin/activate
python -c "from providers import ProviderFactory; p = ProviderFactory.from_env(); print(p.provider_name)"
```

### Health Check Script

```bash
#!/bin/bash
# /opt/ai-agent-platform/scripts/health-check.sh

echo "Checking AI Agent Platform health..."

# Check services
echo "Services:"
systemctl is-active ai-agent-api && echo "✓ API" || echo "✗ API"
systemctl is-active ai-agent-runtime && echo "✓ Runtime" || echo "✗ Runtime"
systemctl is-active ai-agent-worker && echo "✓ Worker" || echo "✗ Worker"
systemctl is-active ai-agent-telegram && echo "✓ Telegram" || echo "✗ Telegram"

# Check endpoints
echo -e "\nEndpoints:"
curl -s http://localhost:8000/health && echo "✓ API Health" || echo "✗ API Health"
redis-cli ping && echo "✓ Redis" || echo "✗ Redis"
sudo -u postgres psql -c "SELECT 1" ai_agent_platform > /dev/null 2>&1 && echo "✓ PostgreSQL" || echo "✗ PostgreSQL"

echo -e "\nDone."
```

## Updates

To update the platform:

```bash
cd /opt/ai-agent-platform

# Pull latest code
git pull origin main

# Update Python dependencies
source venv/bin/activate
pip install -r requirements.txt

# Update frontend
cd frontend && npm install && npm run build

# Restart services
sudo systemctl restart ai-agent-api ai-agent-runtime ai-agent-worker ai-agent-telegram

# Or with Docker
docker-compose down
docker-compose up -d --build
```

## Backup

### Database Backup

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/ai-agent"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# PostgreSQL backup
sudo -u postgres pg_dump ai_agent_platform | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +7 -delete
```

Add to crontab:
```bash
0 2 * * * /opt/ai-agent-platform/scripts/backup.sh
```
