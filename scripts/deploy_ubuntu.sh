#!/bin/bash
#
# AI Agent Platform - Ubuntu 24/7 Deployment Script
# This script sets up the entire system to run continuously
#

set -e

echo "=========================================="
echo "AI Agent Platform - Ubuntu Deployment"
echo "=========================================="
echo ""

# Configuration
INSTALL_DIR="/opt/ai-agent-platform"
SERVICE_USER="ai-agent"
LOG_DIR="/var/log/ai-agent"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (use sudo)"
    exit 1
fi

# 1. System Update
echo ""
log_info "Step 1: Updating system packages..."
apt-get update && apt-get upgrade -y
log_success "System updated"

# 2. Install system dependencies
echo ""
log_info "Step 2: Installing system dependencies..."
apt-get install -y \
    curl \
    wget \
    git \
    nano \
    htop \
    net-tools \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    build-essential \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip

log_success "System dependencies installed"

# 3. Install Docker
echo ""
log_info "Step 3: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    usermod -aG docker $SUDO_USER 2>/dev/null || true
    log_success "Docker installed"
else
    log_warning "Docker already installed, skipping..."
fi

# 4. Install Docker Compose
echo ""
log_info "Step 4: Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_success "Docker Compose installed"
else
    log_warning "Docker Compose already installed, skipping..."
fi

# 5. Create service user
echo ""
log_info "Step 5: Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$INSTALL_DIR" -M "$SERVICE_USER"
    log_success "Service user '$SERVICE_USER' created"
else
    log_warning "Service user already exists"
fi

# 6. Create directories
echo ""
log_info "Step 6: Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "/etc/ai-agent-platform"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"
chmod 755 "$INSTALL_DIR"
chmod 755 "$LOG_DIR"
log_success "Directories created"

# 7. Setup project files
echo ""
log_info "Step 7: Setting up project files..."

# Copy files if running from git repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    log_info "Copying project files from $PROJECT_ROOT..."
    cp -r "$PROJECT_ROOT"/* "$INSTALL_DIR/"
    log_success "Project files copied"
else
    log_warning "Project files not found. Please manually copy files to $INSTALL_DIR"
fi

# 8. Create environment file
echo ""
log_info "Step 8: Environment configuration..."

if [ ! -f "$INSTALL_DIR/.env" ]; then
    if [ -f "$INSTALL_DIR/.env.example" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        log_warning "Created .env from template. Please edit $INSTALL_DIR/.env with your credentials!"
    else
        log_error ".env.example not found. Please create .env manually"
    fi
else
    log_warning ".env already exists, skipping..."
fi

# Set permissions
chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
chmod 600 "$INSTALL_DIR/.env"

# 9. Create systemd services
echo ""
log_info "Step 9: Creating systemd services..."

# API Service
cat > /etc/systemd/system/ai-agent-api.service << EOF
[Unit]
Description=AI Agent Platform API Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
User=root
Group=root
ExecStart=/usr/local/bin/docker-compose up -d api
ExecStop=/usr/local/bin/docker-compose stop api
ExecReload=/usr/local/bin/docker-compose restart api

[Install]
WantedBy=multi-user.target
EOF

# Agent Runtime Service
cat > /etc/systemd/system/ai-agent-runtime.service << EOF
[Unit]
Description=AI Agent Platform Runtime
After=ai-agent-api.service
Requires=ai-agent-api.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
User=root
Group=root
ExecStart=/usr/local/bin/docker-compose up -d agent-runtime
ExecStop=/usr/local/bin/docker-compose stop agent-runtime
ExecReload=/usr/local/bin/docker-compose restart agent-runtime

[Install]
WantedBy=multi-user.target
EOF

# Telegram Bot Service
cat > /etc/systemd/system/ai-agent-telegram.service << EOF
[Unit]
Description=AI Agent Platform Telegram Bot
After=ai-agent-api.service
Requires=ai-agent-api.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
User=root
Group=root
ExecStart=/usr/local/bin/docker-compose up -d telegram-bot
ExecStop=/usr/local/bin/docker-compose stop telegram-bot
ExecReload=/usr/local/bin/docker-compose restart telegram-bot

[Install]
WantedBy=multi-user.target
EOF

# Worker Service
cat > /etc/systemd/system/ai-agent-worker.service << EOF
[Unit]
Description=AI Agent Platform Celery Workers
After=ai-agent-api.service
Requires=ai-agent-api.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
User=root
Group=root
ExecStart=/usr/local/bin/docker-compose up -d celery-worker
ExecStop=/usr/local/bin/docker-compose stop celery-worker
ExecReload=/usr/local/bin/docker-compose restart celery-worker

[Install]
WantedBy=multi-user.target
EOF

# Master service to control all
cat > /etc/systemd/system/ai-agent-platform.service << EOF
[Unit]
Description=AI Agent Platform - All Services
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart

[Install]
WantedBy=multi-user.target
EOF

log_success "Systemd services created"

# 10. Create monitoring script
echo ""
log_info "Step 10: Creating monitoring script..."

cat > "$INSTALL_DIR/scripts/health-check.sh" << 'EOF'
#!/bin/bash
# Health check script for AI Agent Platform

INSTALL_DIR="/opt/ai-agent-platform"
LOG_FILE="/var/log/ai-agent/health-check.log"

mkdir -p /var/log/ai-agent

echo "$(date): Running health check..." >> $LOG_FILE

# Check Docker containers
check_container() {
    local container=$1
    if docker ps | grep -q "$container"; then
        echo "✓ $container running" >> $LOG_FILE
        return 0
    else
        echo "✗ $container NOT running" >> $LOG_FILE
        return 1
    fi
}

# Check API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API responding" >> $LOG_FILE
else
    echo "✗ API NOT responding" >> $LOG_FILE
fi

# Check containers
check_container "ai-agent-api"
check_container "ai-agent-runtime"
check_container "ai-agent-telegram"

echo "---" >> $LOG_FILE
EOF

chmod +x "$INSTALL_DIR/scripts/health-check.sh"

# 11. Setup log rotation
echo ""
log_info "Step 11: Setting up log rotation..."

cat > /etc/logrotate.d/ai-agent-platform << EOF
/var/log/ai-agent/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 $SERVICE_USER $SERVICE_USER
}
EOF

log_success "Log rotation configured"

# 12. Create backup script
echo ""
log_info "Step 12: Creating backup script..."

cat > "$INSTALL_DIR/scripts/backup.sh" << 'EOF'
#!/bin/bash
# Backup script for AI Agent Platform

BACKUP_DIR="/backups/ai-agent-platform"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup environment file
cp /opt/ai-agent-platform/.env $BACKUP_DIR/env_$DATE

# Backup database (if using Docker)
docker exec ai-agent-postgres pg_dump -U postgres ai_agent_platform | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
find $BACKUP_DIR -name "env_*" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x "$INSTALL_DIR/scripts/backup.sh"

# 13. Create update script
echo ""
log_info "Step 13: Creating update script..."

cat > "$INSTALL_DIR/scripts/update.sh" << 'EOF'
#!/bin/bash
# Update script for AI Agent Platform

INSTALL_DIR="/opt/ai-agent-platform"

cd $INSTALL_DIR

echo "Updating AI Agent Platform..."

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

echo "Update completed!"
EOF

chmod +x "$INSTALL_DIR/scripts/update.sh"

# 14. Setup cron jobs
echo ""
log_info "Step 14: Setting up cron jobs..."

cat > /etc/cron.d/ai-agent-platform << EOF
# AI Agent Platform scheduled tasks

# Health check every 5 minutes
*/5 * * * * root /opt/ai-agent-platform/scripts/health-check.sh >/dev/null 2>&1

# Daily backup at 2 AM
0 2 * * * root /opt/ai-agent-platform/scripts/backup.sh >/dev/null 2>&1
EOF

chmod 644 /etc/cron.d/ai-agent-platform
log_success "Cron jobs configured"

# 15. Enable and start services
echo ""
log_info "Step 15: Enabling systemd services..."

systemctl daemon-reload

# Enable services
systemctl enable ai-agent-platform.service
systemctl enable ai-agent-api.service
systemctl enable ai-agent-runtime.service
systemctl enable ai-agent-telegram.service
systemctl enable ai-agent-worker.service

log_success "Services enabled"

# 16. Firewall setup (optional)
echo ""
log_info "Step 16: Firewall configuration..."

if command -v ufw &> /dev/null; then
    ufw allow 8000/tcp comment 'AI Agent API'
    ufw allow 3000/tcp comment 'AI Agent Dashboard'
    log_success "Firewall rules added"
else
    log_warning "UFW not installed, skipping firewall setup"
fi

# 17. Create management commands
echo ""
log_info "Step 17: Creating management commands..."

cat > /usr/local/bin/ai-agent << 'EOF'
#!/bin/bash
# AI Agent Platform management command

INSTALL_DIR="/opt/ai-agent-platform"

case "$1" in
    start)
        echo "Starting AI Agent Platform..."
        cd $INSTALL_DIR && docker-compose up -d
        ;;
    stop)
        echo "Stopping AI Agent Platform..."
        cd $INSTALL_DIR && docker-compose down
        ;;
    restart)
        echo "Restarting AI Agent Platform..."
        cd $INSTALL_DIR && docker-compose restart
        ;;
    status)
        echo "AI Agent Platform Status:"
        cd $INSTALL_DIR && docker-compose ps
        ;;
    logs)
        service="${2:-api}"
        cd $INSTALL_DIR && docker-compose logs -f $service
        ;;
    update)
        echo "Updating AI Agent Platform..."
        /opt/ai-agent-platform/scripts/update.sh
        ;;
    backup)
        echo "Creating backup..."
        /opt/ai-agent-platform/scripts/backup.sh
        ;;
    health)
        /opt/ai-agent-platform/scripts/health-check.sh
        cat /var/log/ai-agent/health-check.log | tail -20
        ;;
    shell)
        service="${2:-api}"
        cd $INSTALL_DIR && docker-compose exec $service /bin/bash
        ;;
    *)
        echo "AI Agent Platform Management"
        echo ""
        echo "Usage: ai-agent <command> [options]"
        echo ""
        echo "Commands:"
        echo "  start       Start all services"
        echo "  stop        Stop all services"
        echo "  restart     Restart all services"
        echo "  status      Show service status"
        echo "  logs [svc]  View logs (default: api)"
        echo "  update      Update to latest version"
        echo "  backup      Create backup"
        echo "  health      Check health status"
        echo "  shell [svc]  Open shell in container"
        echo ""
        echo "Services: api, agent-runtime, telegram-bot, worker, postgres, redis"
        ;;
esac
EOF

chmod +x /usr/local/bin/ai-agent
log_success "Management command 'ai-agent' created"

# Final instructions
echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit configuration:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Add your credentials:"
echo "   - TELEGRAM_BOT_TOKEN"
echo "   - TELEGRAM_CHANNEL_ID"
echo "   - FIREWORKS_API_KEY or OLLAMA_API_KEY"
echo ""
echo "3. Start the system:"
echo "   ai-agent start"
echo "   OR"
echo "   systemctl start ai-agent-platform"
echo ""
echo "4. Check status:"
echo "   ai-agent status"
echo ""
echo "5. View logs:"
echo "   ai-agent logs api"
echo "   ai-agent logs telegram-bot"
echo ""
echo "6. Management commands:"
echo "   ai-agent --help"
echo ""
echo "Services will start automatically on boot."
echo ""
log_success "Deployment completed!"
