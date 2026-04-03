#!/bin/bash
#
# AI Agent Platform - Ubuntu Server Setup Script
# Phase 12: Ubuntu Deployment
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== AI Agent Platform Ubuntu Setup ===${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Get install directory
INSTALL_DIR=${INSTALL_DIR:-"/opt/ai-agent-platform"}
APP_USER=${APP_USER:-"aiagent"}

echo "Install directory: $INSTALL_DIR"
echo "App user: $APP_USER"
echo ""

# ==================== System Dependencies ====================

echo -e "${YELLOW}Installing system dependencies...${NC}"

apt-get update
apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    postgresql-14 \
    postgresql-contrib \
    redis-server \
    nginx \
    git \
    curl \
    wget \
    build-essential \
    nodejs \
    npm \
    supervisor \
    fail2ban \
    ufw \
    logrotate

# Install Node.js 18
if ! command -v node &> /dev/null || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" != "18" ]; then
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

echo -e "${GREEN}System dependencies installed${NC}"

# ==================== Create App User ====================

echo -e "${YELLOW}Creating application user...${NC}"

if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$INSTALL_DIR" -m "$APP_USER"
fi

usermod -aG www-data "$APP_USER"

echo -e "${GREEN}User $APP_USER created${NC}"

# ==================== Database Setup ====================

echo -e "${YELLOW}Setting up PostgreSQL...${NC}"

# Start PostgreSQL
systemctl enable postgresql
systemctl start postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE USER aiagent WITH PASSWORD 'change_me_in_production';
CREATE DATABASE agent_platform OWNER aiagent;
\c agent_platform;
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aiagent;
EOF

echo -e "${GREEN}PostgreSQL configured${NC}"

# ==================== Redis Setup ====================

echo -e "${YELLOW}Setting up Redis...${NC}"

systemctl enable redis-server
systemctl start redis-server

# Configure Redis for persistence
cat >> /etc/redis/redis.conf << 'EOF'

# AI Agent Platform settings
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF

systemctl restart redis-server

echo -e "${GREEN}Redis configured${NC}"

# ==================== Application Directory ====================

echo -e "${YELLOW}Setting up application directory...${NC}"

mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"

# Set permissions
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"

echo -e "${GREEN}Application directory ready at $INSTALL_DIR${NC}"

# ==================== Python Environment ====================

echo -e "${YELLOW}Setting up Python environment...${NC}"

cd "$INSTALL_DIR"
sudo -u "$APP_USER" python3.10 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip wheel

echo -e "${GREEN}Python environment ready${NC}"

# ==================== Nginx Configuration ====================

echo -e "${YELLOW}Configuring Nginx...${NC}"

cat > /etc/nginx/sites-available/ai-agent-platform << 'EOF'
upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name _;  # Accept any hostname

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # API
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # WebSocket
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Static files
    location /static {
        alias /opt/ai-agent-platform/static;
        expires 1d;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/ai-agent-platform /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx config
nginx -t

systemctl restart nginx
systemctl enable nginx

echo -e "${GREEN}Nginx configured${NC}"

# ==================== Systemd Services ====================

echo -e "${YELLOW}Creating systemd services...${NC}"

# Backend API service
cat > /etc/systemd/system/ai-agent-api.service << EOF
[Unit]
Description=AI Agent Platform API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/logs/api.log
StandardError=append:$INSTALL_DIR/logs/api.error.log

[Install]
WantedBy=multi-user.target
EOF

# Telegram Bot service
cat > /etc/systemd/system/ai-agent-telegram.service << EOF
[Unit]
Description=AI Agent Platform Telegram Bot
After=network.target ai-agent-api.service
Wants=ai-agent-api.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python run_telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:$INSTALL_DIR/logs/telegram.log
StandardError=append:$INSTALL_DIR/logs/telegram.error.log

[Install]
WantedBy=multi-user.target
EOF

# Celery Worker service
cat > /etc/systemd/system/ai-agent-celery.service << EOF
[Unit]
Description=AI Agent Platform Celery Worker
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/celery -A agents.celery_config worker --loglevel=info --concurrency=4
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/logs/celery.log
StandardError=append:$INSTALL_DIR/logs/celery.error.log

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat service
cat > /etc/systemd/system/ai-agent-celery-beat.service << EOF
[Unit]
Description=AI Agent Platform Celery Beat Scheduler
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/celery -A agents.celery_config beat --loglevel=info
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/logs/celery-beat.log
StandardError=append:$INSTALL_DIR/logs/celery-beat.error.log

[Install]
WantedBy=multi-user.target
EOF

# Frontend service (using npm start)
cat > /etc/systemd/system/ai-agent-frontend.service << EOF
[Unit]
Description=AI Agent Platform Frontend
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$INSTALL_DIR/frontend
Environment="PATH=/usr/bin:/usr/local/bin"
Environment="NODE_ENV=production"
Environment="NEXT_PUBLIC_API_URL=http://localhost:8000"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/logs/frontend.log
StandardError=append:$INSTALL_DIR/logs/frontend.error.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

echo -e "${GREEN}Systemd services created${NC}"

# ==================== Firewall ====================

echo -e "${YELLOW}Configuring firewall...${NC}"

ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw allow 8000/tcp  # API (internal)
ufw allow 3000/tcp  # Frontend (internal)

ufw --force enable

echo -e "${GREEN}Firewall configured${NC}"

# ==================== Log Rotation ====================

echo -e "${YELLOW}Setting up log rotation...${NC}"

cat > /etc/logrotate.d/ai-agent-platform << EOF
$INSTALL_DIR/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $APP_USER $APP_USER
    sharedscripts
    postrotate
        systemctl reload ai-agent-api ai-agent-telegram ai-agent-celery ai-agent-celery-beat ai-agent-frontend
    endscript
}
EOF

echo -e "${GREEN}Log rotation configured${NC}"

# ==================== Environment File Template ====================

echo -e "${YELLOW}Creating environment file template...${NC}"

cat > "$INSTALL_DIR/.env.example" << 'EOF'
# AI Agent Platform - Environment Configuration
# Copy this file to .env and fill in your actual values

# ==================== API Keys ====================
# Fireworks AI (Primary Provider)
FIREWORKS_API_KEY=fw_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Alternative providers
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Telegram Bot (Required for Telegram control)
TELEGRAM_BOT_TOKEN=xxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Telegram user restrictions
TELEGRAM_ALLOWED_USERS=username1,username2
TELEGRAM_ADMIN_USERS=admin_username

# ==================== Database ====================
DATABASE_URL=postgresql://aiagent:change_me_in_production@localhost/agent_platform
REDIS_URL=redis://localhost:6379/0

# ==================== API Configuration ====================
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000

# ==================== Frontend ====================
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# ==================== Security ====================
SECRET_KEY=generate_a_random_secret_key_here_min_32_chars
JWT_SECRET=another_random_secret_for_jwt_tokens

# ==================== Monitoring ====================
SENTRY_DSN=https://xxxxxxxxxxxxxxxxxxxxxxxxxxxx@sentry.io/xxxxx
PROMETHEUS_PORT=9090

# ==================== Logging ====================
LOG_LEVEL=INFO
LOG_FORMAT=json
EOF

echo -e "${GREEN}Environment template created at $INSTALL_DIR/.env.example${NC}"

# ==================== Installation Summary ====================

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Copy your application code to: $INSTALL_DIR"
echo "   git clone <your-repo> $INSTALL_DIR"
echo ""
echo "2. Install Python dependencies:"
echo "   cd $INSTALL_DIR"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "3. Copy and edit environment file:"
echo "   cp .env.example .env"
echo "   nano .env  # Edit with your API keys"
echo ""
echo "4. Build the frontend:"
echo "   cd frontend"
echo "   npm install"
echo "   npm run build"
echo ""
echo "5. Start all services:"
echo "   systemctl start ai-agent-api"
echo "   systemctl start ai-agent-telegram"
echo "   systemctl start ai-agent-celery"
echo "   systemctl start ai-agent-celery-beat"
echo "   systemctl start ai-agent-frontend"
echo ""
echo "6. Enable services to start on boot:"
echo "   systemctl enable ai-agent-api ai-agent-telegram ai-agent-celery ai-agent-celery-beat ai-agent-frontend"
echo ""
echo "7. Check service status:"
echo "   systemctl status ai-agent-api"
echo ""
echo "Service URLs:"
echo "  - Dashboard: http://your-server-ip/"
echo "  - API Docs: http://your-server-ip/docs"
echo "  - API: http://your-server-ip/api/v1"
echo ""
echo -e "${YELLOW}IMPORTANT: Change the PostgreSQL password in production!${NC}"
echo -e "${YELLOW}Run: sudo -u postgres psql -c \"ALTER USER aiagent WITH PASSWORD 'new_secure_password';\"${NC}"
echo ""