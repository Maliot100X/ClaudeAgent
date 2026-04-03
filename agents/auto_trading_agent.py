"""
Auto-trading agent with winning strategies for Solana tokens.
Monitors new listings, applies strategies, and posts signals to Telegram.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from services.birdeye_adapter import BirdeyeAdapter
from services.helius_adapter import HeliusAPI, WalletPortfolio
from services.dexscreener_adapter import DexScreenerAdapter
from telegram.bot import TelegramBot
from telegram.formatters import MessageFormatters
from skills.signal_generation_skill import SignalGenerationSkill, Signal, SignalType, SignalStrength
from skills.risk_analysis_skill import RiskAnalysisSkill, RiskLevel

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Types of trading strategies."""
    MOMENTUM = "momentum"              # Trend following
    BREAKOUT = "breakout"              # Price breakout
    SENTIMENT = "sentiment"            # Social sentiment
    NEW_LISTING = "new_listing"        # Fresh token launch
    GRADUATION = "graduation"          # Graduating to higher market cap
    MEAN_REVERSION = "mean_reversion"  # Price correction
    ARBITRAGE = "arbitrage"            # Cross-DEX arbitrage


@dataclass
class Position:
    """Paper trading position."""
    token_address: str
    symbol: str
    entry_price: float
    size_usd: float
    strategy: StrategyType
    entry_time: datetime
    stop_loss: float
    take_profit: float
    pnl_pct: float = 0.0
    status: str = "open"


@dataclass
class StrategyResult:
    """Result of strategy analysis."""
    should_trade: bool
    direction: str  # "buy", "sell", "hold"
    confidence: float
    position_size_usd: float
    stop_loss_pct: float
    take_profit_pct: float
    reason: str
    risk_level: RiskLevel


class AutoTradingAgent:
    """
    Autonomous trading agent that:
    1. Monitors new tokens from Birdeye/DexScreener
    2. Analyzes with multiple strategies
    3. Generates trading signals
    4. Posts to Telegram channel
    5. Tracks paper trading positions
    """

    def __init__(
        self,
        telegram_bot: Optional[TelegramBot] = None,
        channel_id: Optional[str] = None
    ):
        self.birdeye = BirdeyeAdapter()
        self.helius = HeliusAPI()
        self.dexscreener = DexScreenerAdapter()
        self.telegram_bot = telegram_bot
        self.channel_id = channel_id or "-1003703092807"
        self.signal_skill = SignalGenerationSkill()
        self.risk_skill = RiskAnalysisSkill()
        self.formatters = MessageFormatters()

        # Paper trading state
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
        self.portfolio_value = 10000.0  # Start with $10k USD

        # Strategy configuration
        self.active_strategies = [
            StrategyType.MOMENTUM,
            StrategyType.BREAKOUT,
            StrategyType.NEW_LISTING,
            StrategyType.SENTIMENT,
        ]
        self.min_confidence = 0.7
        self.max_position_size = 1000.0  # Max $1k per trade
        self.min_liquidity = 10000.0     # Min $10k liquidity
        self.min_volume_24h = 5000.0     # Min $5k daily volume

    async def initialize(self):
        """Initialize all services."""
        logger.info("Initializing AutoTradingAgent...")

        # Test connections
        try:
            portfolio = await self.helius.get_wallet_portfolio(
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            )
            if portfolio:
                logger.info("Helius API: Connected ✓")
        except Exception as e:
            logger.warning(f"Helius API test failed: {e}")

        logger.info("AutoTradingAgent initialized")

    async def run_new_token_monitor(self):
        """Monitor for new token listings and analyze them."""
        logger.info("Starting new token monitor...")

        while True:
            try:
                # Get new tokens from multiple sources
                new_tokens = await self._fetch_new_tokens()
                logger.info(f"Found {len(new_tokens)} new tokens to analyze")

                for token in new_tokens:
                    await self._analyze_and_signal(token)

                    # Small delay between tokens
                    await asyncio.sleep(2)

                # Wait before next scan
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in new token monitor: {e}")
                await asyncio.sleep(30)

    async def _fetch_new_tokens(self) -> List[Dict]:
        """Fetch new tokens from all sources."""
        tokens = []
        seen_addresses = set()

        # Source 1: Birdeye new listings
        try:
            birdeye_tokens = await self.birdeye.get_new_listings(limit=20)
            for t in birdeye_tokens:
                addr = t.get("address", "")
                if addr and addr not in seen_addresses:
                    seen_addresses.add(addr)
                    tokens.append({
                        **t,
                        "discovery_source": "birdeye"
                    })
        except Exception as e:
            logger.warning(f"Birdeye new listings failed: {e}")

        # Source 2: DexScreener new pairs
        try:
            dexscreener_tokens = await self.dexscreener.get_solana_new_pairs(limit=20)
            for t in dexscreener_tokens:
                addr = t.get("tokenAddress", "")
                if addr and addr not in seen_addresses:
                    seen_addresses.add(addr)
                    tokens.append({
                        "address": addr,
                        "symbol": t.get("symbol", "UNKNOWN"),
                        "name": t.get("name", "Unknown"),
                        "chain": t.get("chainId", "solana"),
                        "discovery_source": "dexscreener"
                    })
        except Exception as e:
            logger.warning(f"DexScreener new pairs failed: {e}")

        return tokens

    async def _analyze_and_signal(self, token: Dict):
        """Analyze a token and generate trading signal."""
        address = token.get("address")
        symbol = token.get("symbol", "UNKNOWN")

        logger.info(f"Analyzing {symbol} ({address[:12]}...)...")

        # Skip if we already have a position
        if address in self.positions:
            return

        # Gather data
        price_data = await self._get_price_data(address)
        risk_assessment = await self._assess_risk(address, price_data)

        # Run strategies
        results = []
        for strategy in self.active_strategies:
            result = await self._run_strategy(strategy, address, price_data, risk_assessment)
            if result and result.should_trade:
                results.append(result)

        if not results:
            return

        # Combine strategy results
        best_result = max(results, key=lambda r: r.confidence)

        if best_result.confidence >= self.min_confidence:
            # Generate signal
            signal = Signal(
                type=SignalType.BUY if best_result.direction == "buy" else SignalType.SELL,
                symbol=symbol,
                confidence=min(best_result.confidence * 100, 99),
                message=best_result.reason,
                timestamp=datetime.utcnow(),
                metadata={
                    "token_address": address,
                    "strategy": best_result,
                    "price_data": price_data,
                    "risk_level": risk_assessment.level.value if risk_assessment else "unknown"
                }
            )

            # Execute paper trade
            await self._execute_paper_trade(signal, best_result)

            # Send to Telegram
            await self._send_signal_to_telegram(signal, token, best_result)

    async def _get_price_data(self, token_address: str) -> Dict:
        """Get comprehensive price data for a token."""
        data = {
            "price": 0.0,
            "volume_24h": 0.0,
            "liquidity": 0.0,
            "price_change_24h": 0.0,
            "holders": 0,
            "market_cap": 0.0
        }

        # Try Birdeye
        try:
            price_info = await self.birdeye.get_token_price(token_address)
            if price_info:
                data["price"] = price_info.get("price", 0)
                data["volume_24h"] = price_info.get("volume_24h", 0)
                data["liquidity"] = price_info.get("liquidity", 0)
                data["price_change_24h"] = price_info.get("price_change_24h", 0)
        except Exception as e:
            logger.debug(f"Birdeye price failed: {e}")

        # Try DexScreener as backup
        if data["price"] == 0:
            try:
                pairs = await self.dexscreener.get_token_pairs("solana", token_address)
                if pairs:
                    best_pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))
                    data["price"] = float(best_pair.get("priceUsd", 0) or 0)
                    data["volume_24h"] = float(best_pair.get("volume", {}).get("h24", 0) or 0)
                    data["liquidity"] = float(best_pair.get("liquidity", {}).get("usd", 0) or 0)
            except Exception as e:
                logger.debug(f"DexScreener price failed: {e}")

        return data

    async def _assess_risk(self, address: str, price_data: Dict) -> Any:
        """Assess trading risk for a token."""
        return self.risk_skill.analyze(
            symbol=address[:8],
            price=price_data.get("price", 0),
            volume_24h=price_data.get("volume_24h", 0),
            liquidity=price_data.get("liquidity", 0),
            price_change_24h=price_data.get("price_change_24h", 0),
            is_new_listing=True
        )

    async def _run_strategy(
        self,
        strategy: StrategyType,
        address: str,
        price_data: Dict,
        risk_assessment: Any
    ) -> Optional[StrategyResult]:
        """Run a specific trading strategy."""

        if strategy == StrategyType.NEW_LISTING:
            return await self._new_listing_strategy(address, price_data, risk_assessment)
        elif strategy == StrategyType.MOMENTUM:
            return await self._momentum_strategy(address, price_data, risk_assessment)
        elif strategy == StrategyType.BREAKOUT:
            return await self._breakout_strategy(address, price_data, risk_assessment)
        elif strategy == StrategyType.SENTIMENT:
            return await self._sentiment_strategy(address, price_data, risk_assessment)

        return None

    async def _new_listing_strategy(
        self,
        address: str,
        price_data: Dict,
        risk_assessment: Any
    ) -> Optional[StrategyResult]:
        """Strategy for newly listed tokens."""
        liquidity = price_data.get("liquidity", 0)
        volume = price_data.get("volume_24h", 0)
        price = price_data.get("price", 0)

        # Skip if no liquidity
        if liquidity < self.min_liquidity:
            return None

        # Skip if no volume
        if volume < self.min_volume_24h:
            return None

        # Calculate confidence based on metrics
        confidence = 0.5

        # Higher liquidity = higher confidence
        if liquidity > 50000:
            confidence += 0.15
        elif liquidity > 100000:
            confidence += 0.25

        # Higher volume = higher confidence
        if volume > 50000:
            confidence += 0.15
        elif volume > 100000:
            confidence += 0.25

        # Check risk
        if risk_assessment and risk_assessment.level == RiskLevel.LOW:
            confidence += 0.1
        elif risk_assessment and risk_assessment.level == RiskLevel.HIGH:
            confidence -= 0.2

        if confidence >= self.min_confidence:
            return StrategyResult(
                should_trade=True,
                direction="buy",
                confidence=confidence,
                position_size_usd=min(self.max_position_size, self.portfolio_value * 0.1),
                stop_loss_pct=5.0,    # 5% stop loss
                take_profit_pct=20.0, # 20% take profit
                reason=f"New listing with ${liquidity:,.0f} liquidity and ${volume:,.0f} volume",
                risk_level=risk_assessment.level if risk_assessment else RiskLevel.MEDIUM
            )

        return None

    async def _momentum_strategy(
        self,
        address: str,
        price_data: Dict,
        risk_assessment: Any
    ) -> Optional[StrategyResult]:
        """Momentum/trend following strategy."""
        price_change = price_data.get("price_change_24h", 0)
        volume = price_data.get("volume_24h", 0)

        # Look for strong upward momentum
        if price_change > 10 and volume > 10000:
            confidence = 0.6 + min(price_change / 100, 0.3)

            if confidence >= self.min_confidence:
                return StrategyResult(
                    should_trade=True,
                    direction="buy",
                    confidence=confidence,
                    position_size_usd=min(self.max_position_size * 0.7, self.portfolio_value * 0.07),
                    stop_loss_pct=7.0,
                    take_profit_pct=15.0,
                    reason=f"Strong momentum: +{price_change:.1f}% in 24h with ${volume:,.0f} volume",
                    risk_level=risk_assessment.level if risk_assessment else RiskLevel.MEDIUM
                )

        return None

    async def _breakout_strategy(
        self,
        address: str,
        price_data: Dict,
        risk_assessment: Any
    ) -> Optional[StrategyResult]:
        """Price breakout strategy."""
        # This would need historical price data
        # Simplified version
        return None

    async def _sentiment_strategy(
        self,
        address: str,
        price_data: Dict,
        risk_assessment: Any
    ) -> Optional[StrategyResult]:
        """Social sentiment based strategy."""
        # This would integrate LunarCrush
        # Simplified version
        return None

    async def _execute_paper_trade(self, signal: Signal, result: StrategyResult):
        """Execute a paper trading position."""
        address = signal.metadata.get("token_address")
        price_data = signal.metadata.get("price_data", {})
        current_price = price_data.get("price", 0)

        if not current_price or not address:
            return

        # Calculate position
        size_usd = min(result.position_size_usd, self.portfolio_value * 0.1)
        token_amount = size_usd / current_price if current_price > 0 else 0

        position = Position(
            token_address=address,
            symbol=signal.symbol,
            entry_price=current_price,
            size_usd=size_usd,
            strategy=StrategyType.NEW_LISTING,
            entry_time=datetime.utcnow(),
            stop_loss=current_price * (1 - result.stop_loss_pct / 100),
            take_profit=current_price * (1 + result.take_profit_pct / 100)
        )

        self.positions[address] = position
        self.portfolio_value -= size_usd

        logger.info(f"Paper trade executed: {signal.symbol} at ${current_price:.6f}, size: ${size_usd:.2f}")

    async def _send_signal_to_telegram(self, signal: Signal, token: Dict, result: StrategyResult):
        """Send trading signal to Telegram channel."""
        if not self.telegram_bot or not self.channel_id:
            return

        # Build signal message
        price_data = signal.metadata.get("price_data", {})
        risk_level = signal.metadata.get("risk_level", "unknown")

        emoji_map = {
            "buy": "🟢",
            "sell": "🔴",
            "hold": "⚪️"
        }

        message = f"""
{emoji_map.get(result.direction, "📊")} **TRADING SIGNAL: {signal.symbol}**

**Action:** {result.direction.upper()}
**Confidence:** {result.confidence*100:.0f}%
**Risk Level:** {risk_level.upper()}

**Position Details:**
💰 Size: ${result.position_size_usd:.2f}
🛑 Stop Loss: {result.stop_loss_pct:.1f}%
🎯 Take Profit: {result.take_profit_pct:.1f}%

**Token Info:**
🔗 Address: `{token.get('address', 'N/A')[:20]}...`
💵 Price: ${price_data.get('price', 0):.6f}
📊 24h Volume: ${price_data.get('volume_24h', 0):,.0f}
💧 Liquidity: ${price_data.get('liquidity', 0):,.0f}
📈 24h Change: {price_data.get('price_change_24h', 0):+.2f}%

**Strategy:** {result.reason}

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
        """

        try:
            from telegram import Bot
            bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
            await bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            logger.info(f"Signal sent to Telegram: {signal.symbol}")
        except Exception as e:
            logger.error(f"Failed to send Telegram signal: {e}")

    async def check_positions(self):
        """Monitor open positions for stop loss / take profit."""
        logger.info("Checking positions...")

        for address, position in list(self.positions.items()):
            if position.status != "open":
                continue

            try:
                # Get current price
                price_data = await self._get_price_data(address)
                current_price = price_data.get("price", 0)

                if current_price == 0:
                    continue

                # Calculate P&L
                pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
                position.pnl_pct = pnl_pct

                # Check stop loss
                if current_price <= position.stop_loss:
                    await self._close_position(address, current_price, "stop_loss", pnl_pct)

                # Check take profit
                elif current_price >= position.take_profit:
                    await self._close_position(address, current_price, "take_profit", pnl_pct)

            except Exception as e:
                logger.error(f"Error checking position {address}: {e}")

    async def _close_position(self, address: str, exit_price: float, reason: str, pnl_pct: float):
        """Close a paper trading position."""
        position = self.positions.get(address)
        if not position:
            return

        position.status = "closed"

        # Calculate final P&L
        exit_value = position.size_usd * (1 + pnl_pct / 100)
        self.portfolio_value += exit_value

        # Record trade
        self.trade_history.append({
            "symbol": position.symbol,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "size_usd": position.size_usd,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "duration_hours": (datetime.utcnow() - position.entry_time).total_seconds() / 3600,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Send close notification
        emoji = "✅" if pnl_pct > 0 else "❌"
        message = f"""
{emoji} **POSITION CLOSED: {position.symbol}**

**Exit Reason:** {reason.upper()}
**P&L:** {pnl_pct:+.2f}%
**Exit Price:** ${exit_price:.6f}
**Entry Price:** ${position.entry_price:.6f}
**Duration:** {(datetime.utcnow() - position.entry_time).total_seconds() / 3600:.1f} hours

💰 Portfolio Value: ${self.portfolio_value:,.2f}
        """

        try:
            from telegram import Bot
            bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
            await bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send close notification: {e}")

        logger.info(f"Position closed: {position.symbol} with {pnl_pct:+.2f}% P&L")

    def get_portfolio_summary(self) -> Dict:
        """Get paper trading portfolio summary."""
        open_positions = [p for p in self.positions.values() if p.status == "open"]
        closed_trades = [t for t in self.trade_history]

        winning_trades = [t for t in closed_trades if t["pnl_pct"] > 0]
        losing_trades = [t for t in closed_trades if t["pnl_pct"] <= 0]

        total_return = ((self.portfolio_value - 10000) / 10000) * 100

        return {
            "total_value": self.portfolio_value,
            "starting_value": 10000.0,
            "total_return_pct": total_return,
            "open_positions": len(open_positions),
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(closed_trades) * 100 if closed_trades else 0,
            "total_trades": len(closed_trades) + len(open_positions)
        }


class TradingStrategyService:
    """Service wrapper for running the auto-trading agent."""

    def __init__(self):
        self.agent = AutoTradingAgent()
        self._running = False
        self._tasks = []

    async def start(self):
        """Start the trading service."""
        await self.agent.initialize()
        self._running = True

        # Start monitoring tasks
        self._tasks = [
            asyncio.create_task(self.agent.run_new_token_monitor()),
            asyncio.create_task(self._position_monitor_loop())
        ]

        logger.info("Trading strategy service started")

    async def stop(self):
        """Stop the trading service."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Trading strategy service stopped")

    async def _position_monitor_loop(self):
        """Background loop to check positions."""
        while self._running:
            try:
                await self.agent.check_positions()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(10)

    async def health_check(self) -> Dict:
        """Health check for the service."""
        return {
            "service": "trading_strategy",
            "running": self._running,
            "portfolio": self.agent.get_portfolio_summary(),
            "timestamp": datetime.utcnow().isoformat()
        }


# Run standalone
if __name__ == "__main__":
    import os
    service = TradingStrategyService()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        asyncio.run(service.stop())
