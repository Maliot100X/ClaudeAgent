"""Trading strategy implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

from .paper_trading import PaperTradingEngine, OrderSide, OrderType, PositionSide


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(
        self,
        strategy_id: str,
        name: str,
        symbols: List[str],
        engine: PaperTradingEngine
    ):
        self.strategy_id = strategy_id
        self.name = name
        self.symbols = symbols
        self.engine = engine
        self.is_active = False
        self.params: Dict[str, Any] = {}
        self.signals: List[Dict] = []

    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze market data and generate trading signals.

        Args:
            data: Market data dictionary

        Returns:
            Signal dictionary or None
        """
        pass

    @abstractmethod
    async def on_tick(self, prices: Dict[str, float]) -> None:
        """
        Called on each price update.

        Args:
            prices: Current prices for tracked symbols
        """
        pass

    async def start(self) -> None:
        """Start the strategy."""
        self.is_active = True

    async def stop(self) -> None:
        """Stop the strategy."""
        self.is_active = False

    def get_status(self) -> Dict[str, Any]:
        """Get strategy status."""
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "symbols": self.symbols,
            "is_active": self.is_active,
            "params": self.params,
            "signals_generated": len(self.signals)
        }


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based trading strategy.

    Enters positions when price shows strong directional momentum
    using RSI and MACD indicators.
    """

    def __init__(
        self,
        strategy_id: str,
        symbols: List[str],
        engine: PaperTradingEngine,
        rsi_period: int = 14,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        position_size_pct: float = 10.0,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float = 15.0
    ):
        super().__init__(
            strategy_id=strategy_id,
            name="momentum",
            symbols=symbols,
            engine=engine
        )

        self.params = {
            "rsi_period": rsi_period,
            "rsi_overbought": rsi_overbought,
            "rsi_oversold": rsi_oversold,
            "macd_fast": macd_fast,
            "macd_slow": macd_slow,
            "macd_signal": macd_signal,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct
        }

        self.price_history: Dict[str, List[float]] = {s: [] for s in symbols}
        self.rsi_values: Dict[str, float] = {}
        self.macd_values: Dict[str, Dict] = {}

    async def analyze(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze data and generate momentum signals."""
        symbol = data.get("symbol")
        if not symbol or symbol not in self.symbols:
            return None

        price = data.get("price", 0)
        indicators = data.get("indicators", {})

        rsi = indicators.get("rsi", 50)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)

        signal = None
        strength = 0
        reasoning = []

        # RSI momentum
        if rsi > self.params["rsi_overbought"]:
            signal = "sell"
            strength += 2
            reasoning.append(f"RSI overbought at {rsi:.1f}")
        elif rsi < self.params["rsi_oversold"]:
            signal = "buy"
            strength += 2
            reasoning.append(f"RSI oversold at {rsi:.1f}")

        # MACD momentum
        if macd > macd_signal and macd > 0:
            if signal == "buy":
                strength += 2
                reasoning.append("MACD bullish crossover with momentum")
            elif signal is None:
                signal = "buy"
                strength += 1
                reasoning.append("MACD bullish crossover")
        elif macd < macd_signal and macd < 0:
            if signal == "sell":
                strength += 2
                reasoning.append("MACD bearish crossover with momentum")
            elif signal is None:
                signal = "sell"
                strength += 1
                reasoning.append("MACD bearish crossover")

        if signal and strength >= 2:
            result = {
                "symbol": symbol,
                "signal": signal,
                "strength": strength,
                "price": price,
                "reasoning": "; ".join(reasoning),
                "indicators": {"rsi": rsi, "macd": macd, "macd_signal": macd_signal}
            }
            self.signals.append(result)
            return result

        return None

    async def on_tick(self, prices: Dict[str, float]) -> None:
        """Process price tick."""
        if not self.is_active:
            return

        # Update price history
        for symbol, price in prices.items():
            if symbol in self.price_history:
                self.price_history[symbol].append(price)
                # Keep limited history
                if len(self.price_history[symbol]) > 100:
                    self.price_history[symbol] = self.price_history[symbol][-100:]

        # Check positions for exits
        for symbol, position in list(self.engine.positions.items()):
            if position.symbol in self.symbols:
                current_price = prices.get(position.symbol)
                if not current_price:
                    continue

                # Check stop loss / take profit
                if position.check_stop_loss() or position.check_take_profit():
                    # Risk management will handle the exit
                    pass

    async def on_signal(self, signal: Dict[str, Any]) -> None:
        """Execute trade based on signal."""
        symbol = signal["symbol"]
        direction = signal["signal"]
        price = signal["price"]

        # Calculate position size
        position_value = self.engine.total_equity * (self.params["position_size_pct"] / 100)
        quantity = position_value / price

        if direction == "buy":
            # Check if we already have a position
            existing = self.engine.get_position(symbol)
            if existing:
                return  # Already long

            # Submit buy order
            order = self.engine.submit_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=quantity,
                strategy_id=self.strategy_id
            )
            self.engine.execute_order(order.order_id, price)

            # Set risk levels
            stop_loss = price * (1 - self.params["stop_loss_pct"] / 100)
            take_profit = price * (1 + self.params["take_profit_pct"] / 100)
            self.engine.set_stop_loss(symbol, stop_loss)
            self.engine.set_take_profit(symbol, take_profit)

        elif direction == "sell":
            # Check if we have a position to close
            existing = self.engine.get_position(symbol)
            if existing and existing.side == PositionSide.LONG:
                order = self.engine.submit_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=existing.quantity,
                    strategy_id=self.strategy_id
                )
                self.engine.execute_order(order.order_id, price)


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Bollinger Bands.

    Buys when price touches lower band, sells when price
    touches upper band.
    """

    def __init__(
        self,
        strategy_id: str,
        symbols: List[str],
        engine: PaperTradingEngine,
        bb_period: int = 20,
        bb_std: float = 2.0,
        bb_threshold: float = 0.05,
        position_size_pct: float = 8.0,
        stop_loss_pct: float = 3.0,
        take_profit_pct: float = 8.0
    ):
        super().__init__(
            strategy_id=strategy_id,
            name="mean_reversion",
            symbols=symbols,
            engine=engine
        )

        self.params = {
            "bb_period": bb_period,
            "bb_std": bb_std,
            "bb_threshold": bb_threshold,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct
        }

        self.bollinger_data: Dict[str, Dict] = {}

    async def analyze(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze for mean reversion signals."""
        symbol = data.get("symbol")
        if not symbol or symbol not in self.symbols:
            return None

        price = data.get("price", 0)
        indicators = data.get("indicators", {})

        # Bollinger Bands
        bb_upper = indicators.get("bb_upper", price * 1.02)
        bb_lower = indicators.get("bb_lower", price * 0.98)
        bb_middle = indicators.get("bb_middle", price)

        # Calculate position within bands (0 = lower, 1 = upper)
        band_width = bb_upper - bb_lower
        if band_width > 0:
            position = (price - bb_lower) / band_width
        else:
            position = 0.5

        signal = None
        reasoning = []
        strength = 0

        # Buy signal: near lower band
        if position < self.params["bb_threshold"]:
            signal = "buy"
            strength = 3
            reasoning.append(f"Price at lower Bollinger Band ({position*100:.1f}% of range)")

            # Extra confirmation if RSI is low
            rsi = indicators.get("rsi", 50)
            if rsi < 40:
                strength += 1
                reasoning.append(f"RSI confirmation at {rsi:.1f}")

        # Sell signal: near upper band
        elif position > (1 - self.params["bb_threshold"]):
            signal = "sell"
            strength = 3
            reasoning.append(f"Price at upper Bollinger Band ({position*100:.1f}% of range)")

            rsi = indicators.get("rsi", 50)
            if rsi > 60:
                strength += 1
                reasoning.append(f"RSI confirmation at {rsi:.1f}")

        if signal:
            result = {
                "symbol": symbol,
                "signal": signal,
                "strength": strength,
                "price": price,
                "reasoning": "; ".join(reasoning),
                "indicators": {
                    "bb_position": position,
                    "bb_width": band_width / bb_middle if bb_middle else 0,
                    "rsi": indicators.get("rsi", 50)
                }
            }
            self.signals.append(result)
            return result

        return None

    async def on_tick(self, prices: Dict[str, float]) -> None:
        """Process price tick."""
        pass  # Analysis is event-driven

    async def on_signal(self, signal: Dict[str, Any]) -> None:
        """Execute mean reversion trade."""
        symbol = signal["symbol"]
        direction = signal["signal"]
        price = signal["price"]

        position_value = self.engine.total_equity * (self.params["position_size_pct"] / 100)
        quantity = position_value / price

        if direction == "buy":
            existing = self.engine.get_position(symbol)
            if existing:
                return

            order = self.engine.submit_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=quantity,
                strategy_id=self.strategy_id
            )
            self.engine.execute_order(order.order_id, price)

            # Tight stops for mean reversion
            stop_loss = price * (1 - self.params["stop_loss_pct"] / 100)
            take_profit = price * (1 + self.params["take_profit_pct"] / 100)
            self.engine.set_stop_loss(symbol, stop_loss)
            self.engine.set_take_profit(symbol, take_profit)

        elif direction == "sell":
            existing = self.engine.get_position(symbol)
            if existing and existing.side == PositionSide.LONG:
                order = self.engine.submit_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=existing.quantity,
                    strategy_id=self.strategy_id
                )
                self.engine.execute_order(order.order_id, price)


class BreakoutStrategy(BaseStrategy):
    """
    Breakout strategy using price levels.

    Enters long on resistance breakout, short on support breakdown.
    """

    def __init__(
        self,
        strategy_id: str,
        symbols: List[str],
        engine: PaperTradingEngine,
        lookback_period: int = 20,
        volume_confirm: bool = True,
        min_volume_ratio: float = 1.2,
        position_size_pct: float = 12.0,
        stop_loss_pct: float = 4.0,
        take_profit_pct: float = 20.0
    ):
        super().__init__(
            strategy_id=strategy_id,
            name="breakout",
            symbols=symbols,
            engine=engine
        )

        self.params = {
            "lookback_period": lookback_period,
            "volume_confirm": volume_confirm,
            "min_volume_ratio": min_volume_ratio,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct
        }

        self.price_history: Dict[str, List[float]] = {s: [] for s in symbols}
        self.volume_history: Dict[str, List[float]] = {s: [] for s in symbols}

    async def analyze(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze for breakout signals."""
        symbol = data.get("symbol")
        if not symbol or symbol not in self.symbols:
            return None

        price = data.get("price", 0)
        volume = data.get("volume", 0)
        indicators = data.get("indicators", {})

        period = self.params["lookback_period"]

        # Update history
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)

        if len(self.price_history[symbol]) < period:
            return None

        # Keep only lookback period
        self.price_history[symbol] = self.price_history[symbol][-period:]
        self.volume_history[symbol] = self.volume_history[symbol][-period:]

        # Calculate levels
        highest_high = max(self.price_history[symbol])
        lowest_low = min(self.price_history[symbol])
        avg_volume = sum(self.volume_history[symbol][:-1]) / (len(self.volume_history[symbol]) - 1) if len(self.volume_history[symbol]) > 1 else volume

        signal = None
        strength = 0
        reasoning = []

        # Breakout above resistance
        if price > highest_high * 0.995:  # Within 0.5% of high
            signal = "buy"
            strength = 3
            reasoning.append(f"Price breaking above {period}-period high")

            # Volume confirmation
            if self.params["volume_confirm"]:
                volume_ratio = volume / avg_volume if avg_volume > 0 else 1
                if volume_ratio >= self.params["min_volume_ratio"]:
                    strength += 1
                    reasoning.append(f"Volume confirmation ({volume_ratio:.1f}x average)")

        # Breakdown below support
        elif price < lowest_low * 1.005:  # Within 0.5% of low
            signal = "sell"
            strength = 3
            reasoning.append(f"Price breaking below {period}-period low")

            if self.params["volume_confirm"]:
                volume_ratio = volume / avg_volume if avg_volume > 0 else 1
                if volume_ratio >= self.params["min_volume_ratio"]:
                    strength += 1
                    reasoning.append(f"Volume confirmation ({volume_ratio:.1f}x average)")

        if signal and strength >= 3:
            result = {
                "symbol": symbol,
                "signal": signal,
                "strength": strength,
                "price": price,
                "reasoning": "; ".join(reasoning),
                "levels": {
                    "highest_high": highest_high,
                    "lowest_low": lowest_low,
                    "range": highest_high - lowest_low
                }
            }
            self.signals.append(result)
            return result

        return None

    async def on_tick(self, prices: Dict[str, float]) -> None:
        """Process price tick."""
        pass

    async def on_signal(self, signal: Dict[str, Any]) -> None:
        """Execute breakout trade."""
        symbol = signal["symbol"]
        direction = signal["signal"]
        price = signal["price"]
        levels = signal.get("levels", {})

        position_value = self.engine.total_equity * (self.params["position_size_pct"] / 100)
        quantity = position_value / price

        if direction == "buy":
            existing = self.engine.get_position(symbol)
            if existing:
                return

            order = self.engine.submit_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=quantity,
                strategy_id=self.strategy_id
            )
            self.engine.execute_order(order.order_id, price)

            # Set risk levels based on breakout range
            range_size = levels.get("range", price * 0.05)
            stop_loss = price - (range_size * 0.5)  # Half the range below entry
            take_profit = price + (range_size * 2)   # 2x range above entry

            self.engine.set_stop_loss(symbol, max(stop_loss, price * 0.96))
            self.engine.set_take_profit(symbol, min(take_profit, price * 1.20))

        elif direction == "sell":
            existing = self.engine.get_position(symbol)
            if existing and existing.side == PositionSide.LONG:
                order = self.engine.submit_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=existing.quantity,
                    strategy_id=self.strategy_id
                )
                self.engine.execute_order(order.order_id, price)
