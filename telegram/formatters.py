"""Message formatters for Telegram bot."""

from datetime import datetime
from typing import Dict, List, Any


class MessageFormatters:
    """Format data for Telegram messages."""

    @staticmethod
    def format_status(data: dict) -> str:
        """Format system status."""
        health = data.get("status", "unknown")
        components = data.get("components", {})

        emoji = "✅" if health == "healthy" else "⚠️" if health == "degraded" else "❌"

        lines = [
            f"{emoji} **System Status: {health.upper()}**",
            "",
            "📊 **Components:**"
        ]

        for name, status in components.items():
            comp_emoji = "✅" if status == "healthy" else "❌"
            lines.append(f"{comp_emoji} {name}: {status}")

        # Add timestamp
        lines.append("")
        lines.append(f"🕐 Last update: {datetime.utcnow().strftime('%H:%M:%S')} UTC")

        return "\n".join(lines)

    @staticmethod
    def format_agents(data: dict) -> str:
        """Format agents list."""
        agents = data.get("agents", [])

        if not agents:
            return "🤖 **No active agents**\n\nUse /run_strategy to start trading."

        lines = [f"🤖 **Active Agents ({len(agents)})**", ""]

        for agent in agents:
            status_emoji = "🟢" if agent.get("is_active") else "🔴"
            agent_id = agent.get("agent_id", "unknown")[:8]
            name = agent.get("name", "Unknown")
            agent_type = agent.get("type", "generic")

            lines.append(f"{status_emoji} **{name}** (`{agent_id}`)")
            lines.append(f"   Type: {agent_type}")

            if "last_action" in agent:
                lines.append(f"   Last action: {agent['last_action']}")
            if "skills_count" in agent:
                lines.append(f"   Skills: {agent['skills_count']}")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_models(data: dict) -> str:
        """Format available models."""
        providers = data.get("providers", {})
        current = data.get("current_provider", "unknown")

        lines = ["🧠 **Available AI Models**", ""]

        for provider_name, models in providers.items():
            is_current = " ⭐" if provider_name == current else ""
            lines.append(f"**{provider_name}{is_current}**")

            for model in models[:5]:  # Limit to 5 models per provider
                model_id = model.get("id", "unknown")
                lines.append(f"  • {model_id}")

            if len(models) > 5:
                lines.append(f"  ... and {len(models) - 5} more")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_provider(data: dict) -> str:
        """Format current provider info."""
        provider = data.get("provider", "unknown")
        model = data.get("model", "unknown")

        return f"""
🔧 **Current Provider Configuration**

Provider: **{provider}**
Model: `{model}`

Use `/provider <name>` to switch providers.
Available: fireworks, openai, gemini, ollama
        """

    @staticmethod
    def format_strategies(data: dict) -> str:
        """Format strategies list."""
        strategies = data.get("strategies", [])
        active = data.get("active_strategy")

        if not strategies:
            return "📈 **No strategies configured**\n\nUse /run_strategy to start."

        lines = [f"📈 **Trading Strategies ({len(strategies)})**", ""]

        for strat in strategies:
            strat_id = strat.get("strategy_id", "unknown")
            is_active = strat_id == active
            status_emoji = "🟢" if is_active else "⚪️"

            lines.append(f"{status_emoji} **{strat.get('name', 'Unknown')}**")
            lines.append(f"   ID: `{strat_id}`")
            lines.append(f"   Symbols: {', '.join(strat.get('symbols', []))}")
            lines.append(f"   Active: {strat.get('is_active', False)}")
            lines.append(f"   Signals: {strat.get('signals_generated', 0)}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_signals(data: dict) -> str:
        """Format trading signals."""
        signals = data.get("signals", [])

        if not signals:
            return "📊 **No signals generated yet**\n\nWaiting for market opportunities..."

        lines = [f"📊 **Recent Signals ({len(signals)})**", ""]

        for signal in signals[:10]:  # Show last 10
            signal_type = signal.get("signal", "unknown").upper()
            symbol = signal.get("symbol", "unknown")
            price = signal.get("price", 0)
            strength = signal.get("strength", 0)

            # Emoji based on signal type
            if "BUY" in signal_type:
                emoji = "🟢"
            elif "SELL" in signal_type:
                emoji = "🔴"
            else:
                emoji = "⚪️"

            # Strength stars
            stars = "⭐" * min(strength, 5)

            lines.append(f"{emoji} **{signal_type}** {symbol} @ ${price:,.2f}")
            lines.append(f"   Strength: {stars}")

            if "reasoning" in signal:
                reasoning = signal["reasoning"][:60]
                lines.append(f"   Reason: {reasoning}...")

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_positions(data: dict) -> str:
        """Format trading positions."""
        positions = data.get("positions", [])
        summary = data.get("summary", {})

        lines = ["💰 **Paper Trading Positions**", ""]

        # Summary
        equity = summary.get("total_equity", 0)
        cash = summary.get("cash", 0)
        pnl = summary.get("total_return", 0)
        pnl_pct = summary.get("total_return_pct", 0)

        pnl_emoji = "🟢" if pnl >= 0 else "🔴"

        lines.append(f"**Portfolio Value:** ${equity:,.2f}")
        lines.append(f"**Cash:** ${cash:,.2f}")
        lines.append(f"{pnl_emoji} **P&L:** ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        lines.append("")

        if not positions:
            lines.append("*No open positions*")
        else:
            lines.append(f"**Open Positions ({len(positions)}):**")
            lines.append("")

            for pos in positions:
                symbol = pos.get("symbol", "unknown")
                side = pos.get("side", "unknown")
                entry = pos.get("entry_price", 0)
                current = pos.get("current_price", 0)
                qty = pos.get("quantity", 0)
                unrealized = pos.get("unrealized_pnl", 0)
                unrealized_pct = pos.get("unrealized_pnl_pct", 0)

                lines.append(f"📈 **{symbol}** ({side.upper()})")
                lines.append(f"   Qty: {qty:.4f}")
                lines.append(f"   Entry: ${entry:,.2f} | Current: ${current:,.2f}")

                pnl_emoji = "🟢" if unrealized >= 0 else "🔴"
                lines.append(f"   {pnl_emoji} Unrealized: ${unrealized:,.2f} ({unrealized_pct:+.2f}%)")

                if pos.get("stop_loss"):
                    lines.append(f"   🛑 SL: ${pos['stop_loss']:,.2f}")
                if pos.get("take_profit"):
                    lines.append(f"   🎯 TP: ${pos['take_profit']:,.2f}")

                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_performance(data: dict) -> str:
        """Format trading performance."""
        engine = data.get("engine", {})
        strategies = data.get("strategies", {})

        lines = ["📈 **Trading Performance**", ""]

        # Engine stats
        total_trades = engine.get("total_trades", 0)
        winning = engine.get("winning_trades", 0)
        losing = engine.get("losing_trades", 0)
        win_rate = engine.get("win_rate", 0) * 100
        commissions = engine.get("total_commissions", 0)
        realized = engine.get("realized_pnl", 0)

        lines.append("**Overall Statistics:**")
        lines.append(f"Total Trades: {total_trades}")
        lines.append(f"Winning: {winning} | Losing: {losing}")
        lines.append(f"Win Rate: {win_rate:.1f}%")
        lines.append(f"Commissions: ${commissions:,.2f}")
        lines.append(f"Realized P&L: ${realized:,.2f}")
        lines.append("")

        # Strategy stats
        if strategies:
            lines.append("**Strategy Performance:**")
            for strat_id, status in strategies.items():
                lines.append(f"• {status.get('name', 'Unknown')}: {status.get('signals_generated', 0)} signals")

        return "\n".join(lines)

    @staticmethod
    def format_logs(data: dict) -> str:
        """Format system logs."""
        logs = data.get("logs", [])

        if not logs:
            return "📋 No logs available"

        lines = ["📋 **System Logs**", ""]

        for log in logs[-20:]:  # Last 20 entries
            timestamp = log.get("timestamp", "unknown")
            level = log.get("level", "INFO")
            message = log.get("message", "")

            # Emoji for log level
            level_emoji = {
                "DEBUG": "🔍",
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "CRITICAL": "🚨"
            }.get(level, "📝")

            lines.append(f"{level_emoji} [{timestamp}] {message}")

        return "\n".join(lines)

    @staticmethod
    def truncate(text: str, max_length: int = 4096) -> str:
        """Truncate text to fit Telegram message limit."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."
