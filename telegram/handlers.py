"""Enhanced Telegram command handlers with provider/model switching."""

import logging
from typing import Optional, List
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import aiohttp

from .config import TelegramConfig
from .formatters import MessageFormatters

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handlers for all bot commands."""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.formatters = MessageFormatters()

    async def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[dict] = None
    ) -> dict:
        """Make API request to backend."""
        url = f"{self.config.api_base_url}{endpoint}"

        async with aiohttp.ClientSession() as session:
            try:
                if method == "GET":
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        return {"error": f"API error: {resp.status}"}
                elif method == "POST":
                    async with session.post(
                        url,
                        json=data,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        return {"error": f"API error: {resp.status}"}
            except Exception as e:
                logger.error(f"API request failed: {e}")
                return {"error": str(e)}

    def _check_auth(self, update: Update) -> bool:
        """Check if user is authorized."""
        user_id = str(update.effective_user.id) if update.effective_user else None
        username = update.effective_user.username if update.effective_user else None

        # Check user ID or username
        if user_id and self.config.is_user_allowed(user_id):
            return True
        if username and self.config.is_user_allowed(username):
            return True

        # If no allowed_users configured, allow all
        if not self.config.allowed_users:
            return True

        return False

    # ==================== Basic Commands ====================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not self._check_auth(update):
            await update.message.reply_text("⛔️ You are not authorized to use this bot.")
            return

        user = update.effective_user
        welcome_text = f"""
🤖 **Welcome to AI Agent Platform, {user.first_name}!**

This bot controls autonomous trading agents with real-time market data.

**Quick Commands:**
/status - System health
/agents - List active agents
/signals - Trading signals
/positions - Paper trading portfolio

**Wallet Tracking:**
/wallet - View tracked wallets
/add_wallet <address> [name] - Add wallet

**Token Discovery:**
/new_tokens - Latest listings
/trending - Trending tokens
/meme_coins - Hot meme coins

**AI Provider:**
/models - View/switch AI models
/provider <name> - Switch provider
/test_provider - Test connection

Use /help for complete command reference.
        """

        keyboard = [
            [InlineKeyboardButton("📊 Status", callback_data="status"),
             InlineKeyboardButton("🤖 Agents", callback_data="agents")],
            [InlineKeyboardButton("📈 Signals", callback_data="signals"),
             InlineKeyboardButton("💰 Positions", callback_data="positions")],
            [InlineKeyboardButton("💼 Wallets", callback_data="wallet"),
             InlineKeyboardButton("🔥 New Tokens", callback_data="new_tokens")],
            [InlineKeyboardButton("🧠 Models", callback_data="models"),
             InlineKeyboardButton("🌐 Dashboard", callback_data="dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not self._check_auth(update):
            return

        help_text = """
📚 **AI Agent Platform - Complete Command Reference**

**🤖 System Control:**
/start - Welcome and quick start
/status - System health and overview
/help - Show this help message

**🤖 Agent Management:**
/agents - List all agents
/agent_<id>_start - Start specific agent
/agent_<id>_stop - Stop specific agent

**📊 Trading & Strategies:**
/strategies - List available strategies
/run_strategy - Start a new strategy
/stop_strategy - Stop running strategy
/signals - View recent trading signals
/positions - Paper trading portfolio
/history - Trade history

**💼 Wallet Tracking:**
/wallet - View tracked wallets
/add_wallet <address> [name] - Add wallet to track
/remove_wallet <address> - Stop tracking wallet
/wallet_tokens <address> - Show wallet tokens
/wallet_pnl <address> - Show wallet P&L

**🧠 AI Provider Control:**
/models - View/switch AI models
/provider <name> - Switch provider
/test_provider - Test current provider

**📈 Dashboard & Info:**
/dashboard - Get dashboard URL
/logs - System logs info

**🔥 New Token Discovery:**
/new_tokens - Latest new token listings
/trending - Trending tokens
/meme_coins - Hot meme coins

**Examples:**
`/add_wallet So111...234 MyWallet`
`/add_wallet 0x1234...5678 ETHWallet`
`/provider ollama`
`/models ollama/minimax-m2:cloud`
        """

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not self._check_auth(update):
            return

        response = await self._api_request("/api/v1/agents")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        agents = response.get("agents", [])
        running = sum(1 for a in agents if a.get("status") == "running")
        paused = sum(1 for a in agents if a.get("status") == "paused")

        # Get provider info
        provider_resp = await self._api_request("/api/v1/providers/current")
        provider_info = "Unknown"
        if "provider" in provider_resp:
            provider_info = f"{provider_resp['provider'].upper()} ({provider_resp.get('model', 'unknown')})"

        status_text = f"""
📊 **System Status**

**Agents:** {running} running, {paused} paused, {len(agents)} total
**AI Provider:** {provider_info}
**System Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

**Quick Actions:**
/agents - View all agents
/models - Switch AI model
/signals - View signals
        """

        keyboard = [
            [InlineKeyboardButton("🤖 View Agents", callback_data="agents")],
            [InlineKeyboardButton("🧠 Switch Model", callback_data="models")],
            [InlineKeyboardButton("📈 View Signals", callback_data="signals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            status_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # ==================== Agent Commands ====================

    async def agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /agents command."""
        if not self._check_auth(update):
            return

        response = await self._api_request("/api/v1/agents")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        agents = response.get("agents", [])

        if not agents:
            await update.message.reply_text("🤖 No agents configured. Use the API to create agents.")
            return

        text = "🤖 **Active Agents**\n\n"
        keyboard = []

        for agent in agents[:10]:  # Limit to 10
            status_emoji = "🟢" if agent.get("status") == "running" else "🟡" if agent.get("status") == "paused" else "🔴"
            text += f"{status_emoji} **{agent.get('name', 'Unknown')}**\n"
            text += f"   ID: `{agent.get('id')}`\n"
            text += f"   Status: {agent.get('status', 'unknown')}\n"
            text += f"   Skills: {', '.join(agent.get('skills', []))}\n\n"

            # Add control buttons
            if agent.get("status") == "running":
                keyboard.append([
                    InlineKeyboardButton(f"⏹ Stop {agent.get('name')}", callback_data=f"stop_agent:{agent.get('id')}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(f"▶️ Start {agent.get('name')}", callback_data=f"start_agent:{agent.get('id')}")
                ])

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )

    async def agent_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle agent control commands (/agent_<id>_start, /agent_<id>_stop)."""
        if not self._check_auth(update):
            return

        text = update.message.text
        parts = text.split("_")

        if len(parts) < 2:
            await update.message.reply_text("❌ Invalid command format")
            return

        agent_id = parts[1]
        action = parts[-1] if len(parts) > 2 else "status"

        if action == "start":
            response = await self._api_request(
                f"/api/v1/agents/{agent_id}/control",
                method="POST",
                data={"action": "start"}
            )
            await update.message.reply_text(f"✅ Agent `{agent_id}` started" if "error" not in response else f"❌ {response['error']}")
        elif action == "stop":
            response = await self._api_request(
                f"/api/v1/agents/{agent_id}/control",
                method="POST",
                data={"action": "stop"}
            )
            await update.message.reply_text(f"🛑 Agent `{agent_id}` stopped" if "error" not in response else f"❌ {response['error']}")
        else:
            # Get agent details
            response = await self._api_request(f"/api/v1/agents/{agent_id}")
            if "error" in response:
                await update.message.reply_text(f"❌ {response['error']}")
                return
            await update.message.reply_text(self.formatters.format_agent_details(response))

    # ==================== Strategy Commands ====================

    async def strategies(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /strategies command."""
        if not self._check_auth(update):
            return

        response = await self._api_request("/api/v1/strategies")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        strategies = response.get("strategies", [])

        if not strategies:
            await update.message.reply_text("📊 No strategies running. Use /run_strategy to start one.")
            return

        text = "📊 **Trading Strategies**\n\n"

        for strategy in strategies:
            status_emoji = "🟢" if strategy.get("status") == "running" else "🔴"
            text += f"{status_emoji} **{strategy.get('name', 'Unknown')}**\n"
            text += f"   Type: {strategy.get('type', 'unknown')}\n"
            text += f"   Symbol: {strategy.get('symbol', 'unknown')}\n"
            text += f"   Status: {strategy.get('status', 'unknown')}\n\n"

        keyboard = [
            [InlineKeyboardButton("▶️ Run Strategy", callback_data="run_strategy")],
            [InlineKeyboardButton("📈 Performance", callback_data="performance")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def run_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /run_strategy command."""
        if not self._check_auth(update):
            return

        # Show available strategy types
        keyboard = [
            [InlineKeyboardButton("📈 Momentum", callback_data="run_strategy:momentum")],
            [InlineKeyboardButton("📉 Mean Reversion", callback_data="run_strategy:mean_reversion")],
            [InlineKeyboardButton("🚀 Breakout", callback_data="run_strategy:breakout")],
        ]

        await update.message.reply_text(
            "📊 **Start a Strategy**\n\nChoose a strategy type:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def stop_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop_strategy command."""
        if not self._check_auth(update):
            return

        # Get running strategies
        response = await self._api_request("/api/v1/strategies")
        strategies = response.get("strategies", [])
        running = [s for s in strategies if s.get("status") == "running"]

        if not running:
            await update.message.reply_text("🚫 No running strategies to stop.")
            return

        keyboard = [
            [InlineKeyboardButton(f"🛑 Stop {s.get('name')}", callback_data=f"stop_strategy:{s.get('id')}")]
            for s in running[:5]
        ]

        await update.message.reply_text(
            "🛑 **Stop a Strategy**\n\nSelect strategy to stop:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== Signal Commands ====================

    async def signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /signals command."""
        if not self._check_auth(update):
            return

        response = await self._api_request("/api/v1/signals/latest?limit=10")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        signals = response.get("signals", [])

        if not signals:
            await update.message.reply_text("📈 No signals generated yet. Agents need to analyze market data first.")
            return

        text = "📈 **Recent Trading Signals**\n\n"

        for signal in signals[:5]:
            text += self.formatters.format_signal(signal) + "\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="signals")],
            [InlineKeyboardButton("📊 All Signals", callback_data="all_signals")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /positions command."""
        if not self._check_auth(update):
            return

        portfolio = await self._api_request("/api/v1/paper-trading/portfolio")
        positions = await self._api_request("/api/v1/paper-trading/positions")

        if "error" in portfolio:
            await update.message.reply_text(f"❌ Error: {portfolio['error']}")
            return

        text = self.formatters.format_portfolio(portfolio, positions.get("positions", []))

        keyboard = [
            [InlineKeyboardButton("📜 History", callback_data="history")],
            [InlineKeyboardButton("🔄 Reset", callback_data="reset_portfolio")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== Provider/Model Commands ====================

    async def models(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /models command - show and switch models."""
        if not self._check_auth(update):
            return

        # Check if user provided a model argument
        args = context.args
        if args and len(args) > 0:
            # Try to parse provider/model format
            model_arg = args[0]

            if "/" in model_arg:
                parts = model_arg.split("/")
                provider = parts[0]
                model = parts[1] if len(parts) > 1 else None

                # Switch to this model
                response = await self._api_request(
                    "/api/v1/providers/set",
                    method="POST",
                    data={"provider": provider, "model": model}
                )

                if "error" in response:
                    await update.message.reply_text(f"❌ Error: {response['error']}")
                    return

                await update.message.reply_text(
                    f"✅ **Model switched successfully!**\n\n"
                    f"Provider: {response.get('provider', 'unknown').upper()}\n"
                    f"Model: `{response.get('model', 'unknown')}`\n\n"
                    f"Use /test_provider to verify it's working.",
                    parse_mode="Markdown"
                )
                return

        # Show available models
        response = await self._api_request("/api/v1/providers/models")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        models = response.get("models", [])
        current = response.get("current", {})

        text = f"""
🧠 **AI Models**

**Current:**
Provider: {current.get('provider', 'unknown').upper()}
Model: `{current.get('model', 'unknown')}`

**Available Models:**
"""

        # Group by provider
        providers = {}
        for m in models:
            prov = m.get("provider", 'unknown')
            if prov not in providers:
                providers[prov] = []
            providers[prov].append(m)

        keyboard = []

        for prov_id, prov_models in providers.items():
            text += f"\n**{prov_id.upper()}:**\n"
            for m in prov_models:
                model_name = m.get('model', 'unknown')
                is_current = m.get('current', False)
                marker = "✅ " if is_current else "  "
                text += f"{marker}`{prov_id}/{model_name}`\n"

                if not is_current:
                    keyboard.append([InlineKeyboardButton(
                        f"Switch to {prov_id}/{model_name}",
                        callback_data=f"set_model:{prov_id}/{model_name}"
                    )])

        text += "\n_To switch model, use:_\n`/models <provider>/<model>`\n\n_Example:_ `/models ollama/minimax-m2:cloud`"

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )

    async def provider(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /provider command - show and switch providers."""
        if not self._check_auth(update):
            return

        args = context.args
        if args and len(args) > 0:
            provider_name = args[0].lower()

            # Switch to this provider
            response = await self._api_request(
                "/api/v1/providers/set",
                method="POST",
                data={"provider": provider_name}
            )

            if "error" in response:
                await update.message.reply_text(f"❌ Error: {response['error']}")
                return

            await update.message.reply_text(
                f"✅ **Provider switched!**\n\n"
                f"Provider: {response.get('provider', 'unknown').upper()}\n"
                f"Model: `{response.get('model', 'unknown')}`\n\n"
                f"Use /test_provider to verify it's working.",
                parse_mode="Markdown"
            )
            return

        # Show current provider and available options
        response = await self._api_request("/api/v1/providers")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        text = "🧠 **AI Providers**\n\n"
        keyboard = []

        for prov in response:
            status_emoji = "🟢" if prov.get("status") == "active" else "🔴"
            current_marker = " ✅ (current)" if prov.get("current") else ""

            text += f"{status_emoji} **{prov.get('name', prov.get('id', 'Unknown'))}**{current_marker}\n"
            text += f"   ID: `{prov.get('id')}`\n"
            text += f"   Models: {len(prov.get('models', []))} available\n\n"

            if prov.get("status") == "active" and not prov.get("current"):
                keyboard.append([InlineKeyboardButton(
                    f"Switch to {prov.get('name')}",
                    callback_data=f"set_provider:{prov.get('id')}"
                )])

        text += "\n_To switch provider, use:_\n`/provider <name>`\n\n_Example:_ `/provider ollama`"

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )

    async def test_provider(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /test_provider command."""
        if not self._check_auth(update):
            return

        await update.message.reply_text("🧪 Testing current provider... This may take a few seconds.")

        # Get current provider
        current = await self._api_request("/api/v1/providers/current")
        provider_id = current.get("provider", "unknown")

        # Test the provider
        response = await self._api_request(
            f"/api/v1/providers/{provider_id}/test",
            method="POST"
        )

        if "error" in response:
            await update.message.reply_text(f"❌ **Test Failed**\n\n{response['error']}")
            return

        await update.message.reply_text(
            f"✅ **Provider Test Successful**\n\n"
            f"Provider: {provider_id.upper()}\n"
            f"Latency: {response.get('latency_ms', 'unknown')}ms\n"
            f"Response: _{response.get('test_output', 'No output')}_",
            parse_mode="Markdown"
        )

    # ==================== Utility Commands ====================

    async def dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /dashboard command."""
        if not self._check_auth(update):
            return

        dashboard_url = "https://ai-agent-dashboard.vercel.app"  # Update with actual URL

        await update.message.reply_text(
            f"🌐 **Dashboard**\n\n"
            f"Access the web dashboard at:\n{dashboard_url}\n\n"
            f"_Note: Ensure the dashboard is deployed to Vercel._",
            parse_mode="Markdown"
        )

    async def logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /logs command."""
        if not self._check_auth(update):
            return

        await update.message.reply_text(
            "📜 **Recent Logs**\n\n"
            "_Log viewing is available via:_\n"
            "• Docker: `docker-compose logs -f`\n"
            "• System: `journalctl -u ai-agent-api -f`\n"
            "• Files: `/var/log/ai-agent/`",
            parse_mode="Markdown"
        )

    # ==================== Wallet Tracking Commands ====================

    async def wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /wallet command - show tracked wallets."""
        if not self._check_auth(update):
            return

        response = await self._api_request("/api/v1/wallets")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        wallets = response.get("wallets", [])

        if not wallets:
            await update.message.reply_text(
                "💼 **No Wallets Tracked**\n\n"
                "Add a wallet with:\n"
                "`/add_wallet <address> [name]`\n\n"
                "Example:\n"
                "`/add_wallet So111...2345 MySolWallet`",
                parse_mode="Markdown"
            )
            return

        text = "💼 **Tracked Wallets**\n\n"
        keyboard = []

        for wallet in wallets:
            name = wallet.get("name", "Unnamed")
            address = wallet.get("address", "")
            short_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 12 else address
            total_value = wallet.get("total_value_usd", 0)
            sol_balance = wallet.get("sol_balance", 0)
            token_count = wallet.get("token_count", 0)

            text += f"📌 **{name}**\n"
            text += f"   Address: `{short_addr}`\n"
            text += f"   SOL: {sol_balance:.4f}\n"
            text += f"   Value: ${total_value:,.2f}\n"
            text += f"   Tokens: {token_count}\n\n"

            keyboard.append([
                InlineKeyboardButton(f"📊 {name} - Tokens", callback_data=f"wallet_tokens:{address}"),
                InlineKeyboardButton(f"❌ Remove", callback_data=f"remove_wallet:{address}")
            ])

        text += f"\n_Total wallets: {len(wallets)}_"

        keyboard.append([InlineKeyboardButton("➕ Add New Wallet", callback_data="add_wallet")])

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def add_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /add_wallet command."""
        if not self._check_auth(update):
            return

        args = context.args
        if not args or len(args) < 1:
            await update.message.reply_text(
                "❌ **Usage:**\n"
                "`/add_wallet <address> [name]`\n\n"
                "Examples:\n"
                "`/add_wallet So111...2345 MySolWallet`\n"
                "`/add_wallet 0x1234...5678 ETHWallet`",
                parse_mode="Markdown"
            )
            return

        wallet_address = args[0]
        wallet_name = args[1] if len(args) > 1 else "Unnamed"

        # Validate address format (basic check)
        if len(wallet_address) < 20:
            await update.message.reply_text("❌ Invalid wallet address format")
            return

        await update.message.reply_text(f"⏳ Adding wallet `{wallet_address[:12]}...` to tracking...", parse_mode="Markdown")

        # Add wallet via API
        response = await self._api_request(
            "/api/v1/wallets",
            method="POST",
            data={
                "address": wallet_address,
                "name": wallet_name,
                "chain": "solana" if wallet_address.startswith("So") or len(wallet_address) < 45 else "ethereum"
            }
        )

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        # Fetch initial wallet data
        wallet_data = await self._api_request(f"/api/v1/wallets/{wallet_address}/portfolio")

        text = (
            f"✅ **Wallet Added Successfully!**\n\n"
            f"Name: **{wallet_name}**\n"
            f"Address: `{wallet_address[:12]}...{wallet_address[-4:]}`\n"
        )

        if wallet_data and "portfolio" in wallet_data:
            portfolio = wallet_data["portfolio"]
            text += f"\n📊 **Current Portfolio:**\n"
            text += f"Total Value: ${portfolio.get('total_value_usd', 0):,.2f}\n"
            text += f"SOL Balance: {portfolio.get('sol_balance', 0):.4f}\n"
            text += f"Tokens: {portfolio.get('token_count', 0)}\n"

        text += (
            f"\n💡 **Commands:**\n"
            f"`/wallet` - View all wallets\n"
            f"`/wallet_tokens {wallet_address[:8]}...` - View tokens\n"
            f"`/wallet_pnl {wallet_address[:8]}...` - View P&L"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

    async def remove_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remove_wallet command."""
        if not self._check_auth(update):
            return

        args = context.args
        if not args or len(args) < 1:
            await update.message.reply_text(
                "❌ **Usage:**\n"
                "`/remove_wallet <address>`\n\n"
                "Get wallet addresses with `/wallet`",
                parse_mode="Markdown"
            )
            return

        wallet_address = args[0]

        response = await self._api_request(
            f"/api/v1/wallets/{wallet_address}",
            method="DELETE"
        )

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        await update.message.reply_text(
            f"✅ Wallet `{wallet_address[:12]}...` removed from tracking",
            parse_mode="Markdown"
        )

    async def wallet_tokens(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /wallet_tokens command."""
        if not self._check_auth(update):
            return

        args = context.args
        if not args or len(args) < 1:
            await update.message.reply_text(
                "❌ **Usage:**\n"
                "`/wallet_tokens <wallet_address>`\n\n"
                "Get wallet addresses with `/wallet`",
                parse_mode="Markdown"
            )
            return

        wallet_address = args[0]

        await update.message.reply_text("⏳ Fetching wallet tokens...")

        response = await self._api_request(f"/api/v1/wallets/{wallet_address}/tokens")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        tokens = response.get("tokens", [])

        if not tokens:
            await update.message.reply_text("📭 No tokens found in this wallet")
            return

        text = f"💰 **Wallet Tokens** ({len(tokens)} total)\n\n"

        # Show top 15 tokens by value
        for token in tokens[:15]:
            symbol = token.get("symbol", "UNKNOWN")
            name = token.get("name", "Unknown")
            balance = token.get("balance", 0)
            price = token.get("price", 0)
            value = token.get("value_usd", 0)

            if value > 0.01:  # Only show tokens with some value
                text += f"**{symbol}** - {name[:20]}\n"
                text += f"  Balance: {balance:,.4f}\n"
                text += f"  Price: ${price:.6f}\n"
                text += f"  Value: ${value:,.2f}\n\n"

        if len(tokens) > 15:
            text += f"_... and {len(tokens) - 15} more tokens_\n\n"

        total_value = sum(t.get("value_usd", 0) for t in tokens)
        text += f"**Total Token Value: ${total_value:,.2f}**"

        keyboard = [
            [InlineKeyboardButton("📊 View P&L", callback_data=f"wallet_pnl:{wallet_address}")],
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"wallet_tokens:{wallet_address}")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def wallet_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /wallet_pnl command."""
        if not self._check_auth(update):
            return

        args = context.args
        if not args or len(args) < 1:
            await update.message.reply_text(
                "❌ **Usage:**\n"
                "`/wallet_pnl <wallet_address>`\n\n"
                "Get wallet addresses with `/wallet`",
                parse_mode="Markdown"
            )
            return

        wallet_address = args[0]

        await update.message.reply_text("⏳ Calculating P&L...")

        response = await self._api_request(f"/api/v1/wallets/{wallet_address}/pnl")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        pnl_data = response.get("pnl", {})

        total_pnl = pnl_data.get("total_pnl", 0)
        realized_pnl = pnl_data.get("realized_pnl", 0)
        unrealized_pnl = pnl_data.get("unrealized_pnl", 0)
        win_rate = pnl_data.get("win_rate", 0)
        total_trades = pnl_data.get("total_trades", 0)
        winning_trades = pnl_data.get("winning_trades", 0)

        emoji = "🟢" if total_pnl >= 0 else "🔴"

        text = (
            f"📊 **Wallet P&L Report**\n\n"
            f"{emoji} **Total P&L:** ${total_pnl:,.2f}\n"
            f"  Realized: ${realized_pnl:,.2f}\n"
            f"  Unrealized: ${unrealized_pnl:,.2f}\n\n"
            f"🏆 **Win Rate:** {win_rate:.1f}%\n"
            f"  Winning: {winning_trades}/{total_trades} trades\n"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

    # ==================== New Token Discovery Commands ====================

    async def new_tokens(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new_tokens command."""
        if not self._check_auth(update):
            return

        await update.message.reply_text("🔍 Scanning for new token listings...")

        response = await self._api_request("/api/v1/tokens/new?limit=10")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        tokens = response.get("tokens", [])

        if not tokens:
            await update.message.reply_text("📭 No new tokens found at the moment")
            return

        text = "🔥 **New Token Listings**\n\n"

        for token in tokens[:10]:
            symbol = token.get("symbol", "UNKNOWN")
            name = token.get("name", "Unknown")[:25]
            price = token.get("price", 0)
            change = token.get("price_change_24h", 0)
            volume = token.get("volume_24h", 0)
            liquidity = token.get("liquidity", 0)
            address = token.get("address", "")

            change_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"

            text += f"**{symbol}** - {name}\n"
            text += f"  Price: ${price:.8f}\n"
            text += f"  24h: {change_emoji} {change:.2f}%\n"
            text += f"  Volume: ${volume:,.0f}\n"
            text += f"  Liquidity: ${liquidity:,.0f}\n"
            text += f"  Address: `{address[:8]}...{address[-4:]}`\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="new_tokens")],
            [InlineKeyboardButton("📊 View Trending", callback_data="trending")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def trending_tokens(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trending command."""
        if not self._check_auth(update):
            return

        await update.message.reply_text("📊 Fetching trending tokens...")

        response = await self._api_request("/api/v1/tokens/trending?limit=10")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        tokens = response.get("tokens", [])

        if not tokens:
            await update.message.reply_text("📭 No trending tokens found")
            return

        text = "📈 **Trending Tokens**\n\n"

        for i, token in enumerate(tokens[:10], 1):
            symbol = token.get("symbol", "UNKNOWN")
            price = token.get("price", 0)
            change = token.get("price_change_24h", 0)
            volume = token.get("volume_24h", 0)

            change_emoji = "🟢" if change > 0 else "🔴"

            text += f"{i}. **{symbol}**\n"
            text += f"   Price: ${price:.8f} {change_emoji} {change:.2f}%\n"
            text += f"   Volume: ${volume:,.0f}\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="trending")],
            [InlineKeyboardButton("🔥 New Tokens", callback_data="new_tokens")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def meme_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /meme_coins command."""
        if not self._check_auth(update):
            return

        await update.message.reply_text("🐕 Fetching hot meme coins...")

        response = await self._api_request("/api/v1/tokens/meme?limit=15")

        if "error" in response:
            await update.message.reply_text(f"❌ Error: {response['error']}")
            return

        tokens = response.get("tokens", [])

        if not tokens:
            await update.message.reply_text("📭 No meme coins found")
            return

        text = "🐕 **Hot Meme Coins**\n\n"

        for token in tokens[:15]:
            symbol = token.get("symbol", "UNKNOWN")
            name = token.get("name", "Unknown")[:20]
            price = token.get("price", 0)
            change = token.get("price_change_24h", 0)
            volume = token.get("volume_24h", 0)
            liquidity = token.get("liquidity", 0)

            change_emoji = "🚀" if change > 50 else "🟢" if change > 0 else "🔴"

            text += f"**{symbol}** - {name}\n"
            text += f"  ${price:.10f} {change_emoji} {change:.1f}%\n"
            text += f"  Vol: ${volume:,.0f} | Liq: ${liquidity:,.0f}\n\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="meme_coins")],
            [InlineKeyboardButton("🔥 New Tokens", callback_data="new_tokens")]
        ]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== Callback Handlers ====================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "status":
            await self.status(update, context)
        elif data == "agents":
            await self.agents(update, context)
        elif data == "signals":
            await self.signals(update, context)
        elif data == "positions":
            await self.positions(update, context)
        elif data == "models":
            await self.models(update, context)
        elif data == "dashboard":
            await self.dashboard(update, context)
        elif data == "wallet":
            await self.wallet(update, context)
        elif data == "add_wallet":
            await update.callback_query.message.reply_text(
                "💼 **Add Wallet**\n\n"
                "Use command:\n"
                "`/add_wallet <address> [name]`\n\n"
                "Example:\n"
                "`/add_wallet So111...2345 MySolWallet`",
                parse_mode="Markdown"
            )
        elif data == "new_tokens":
            await self.new_tokens(update, context)
        elif data == "trending":
            await self.trending_tokens(update, context)
        elif data == "meme_coins":
            await self.meme_coins(update, context)
        elif data.startswith("set_model:"):
            model_str = data.replace("set_model:", "")
            context.args = [model_str]
            await self.models(update, context)
        elif data.startswith("set_provider:"):
            provider = data.replace("set_provider:", "")
            context.args = [provider]
            await self.provider(update, context)
        elif data.startswith("stop_agent:"):
            agent_id = data.replace("stop_agent:", "")
            await self._send_agent_command(update, agent_id, "stop")
        elif data.startswith("start_agent:"):
            agent_id = data.replace("start_agent:", "")
            await self._send_agent_command(update, agent_id, "start")
        elif data.startswith("stop_strategy:"):
            strategy_id = data.replace("stop_strategy:", "")
            await self._send_strategy_command(update, strategy_id, "stop")
        elif data.startswith("remove_wallet:"):
            address = data.replace("remove_wallet:", "")
            context.args = [address]
            await self.remove_wallet(update, context)
        elif data.startswith("wallet_tokens:"):
            address = data.replace("wallet_tokens:", "")
            context.args = [address]
            await self.wallet_tokens(update, context)
        elif data.startswith("wallet_pnl:"):
            address = data.replace("wallet_pnl:", "")
            context.args = [address]
            await self.wallet_pnl(update, context)

    async def _send_agent_command(self, update: Update, agent_id: str, action: str) -> None:
        """Send agent control command."""
        response = await self._api_request(
            f"/api/v1/agents/{agent_id}/control",
            method="POST",
            data={"action": action}
        )

        status_text = f"✅ Agent `{agent_id}` {action}ed" if "error" not in response else f"❌ {response['error']}"

        await update.callback_query.message.reply_text(
            status_text,
            parse_mode="Markdown"
        )

    async def _send_strategy_command(self, update: Update, strategy_id: str, action: str) -> None:
        """Send strategy control command."""
        response = await self._api_request(
            f"/api/v1/strategies/{strategy_id}/control",
            method="POST",
            data={"action": action}
        )

        status_text = f"✅ Strategy `{strategy_id}` {action}ped" if "error" not in response else f"❌ {response['error']}"

        await update.callback_query.message.reply_text(
            status_text,
            parse_mode="Markdown"
        )
