"""Strategy runner and management."""

from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio
import uuid

from .paper_trading import PaperTradingEngine
from .trading_strategies import BaseStrategy, MomentumStrategy, MeanReversionStrategy, BreakoutStrategy


class StrategyRunner:
    """
    Manages and runs trading strategies.

    Responsibilities:
    - Strategy lifecycle management
    - Signal processing
    - Performance tracking
    - Multi-strategy coordination
    """

    def __init__(
        self,
        engine: Optional[PaperTradingEngine] = None,
        initial_capital: float = 100000.0
    ):
        self.engine = engine or PaperTradingEngine(initial_capital=initial_capital)
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_strategy: Optional[str] = None
        self._running = False
        self._update_interval = 60  # seconds
        self._task: Optional[asyncio.Task] = None

        # Signal handlers
        self._signal_handlers: List[callable] = []

    def register_strategy(
        self,
        strategy: BaseStrategy,
        auto_activate: bool = False
    ) -> None:
        """
        Register a strategy with the runner.

        Args:
            strategy: Strategy instance
            auto_activate: Whether to activate immediately
        """
        self.strategies[strategy.strategy_id] = strategy

        if auto_activate:
            self.activate_strategy(strategy.strategy_id)

    def create_strategy(
        self,
        strategy_type: str,
        symbols: List[str],
        params: Optional[Dict] = None
    ) -> str:
        """
        Create a new strategy.

        Args:
            strategy_type: Type of strategy (momentum, mean_reversion, breakout)
            symbols: List of symbols to trade
            params: Strategy parameters

        Returns:
            Strategy ID
        """
        strategy_id = f"{strategy_type}_{uuid.uuid4().hex[:8]}"
        params = params or {}

        if strategy_type == "momentum":
            strategy = MomentumStrategy(
                strategy_id=strategy_id,
                symbols=symbols,
                engine=self.engine,
                **params
            )
        elif strategy_type == "mean_reversion":
            strategy = MeanReversionStrategy(
                strategy_id=strategy_id,
                symbols=symbols,
                engine=self.engine,
                **params
            )
        elif strategy_type == "breakout":
            strategy = BreakoutStrategy(
                strategy_id=strategy_id,
                symbols=symbols,
                engine=self.engine,
                **params
            )
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        self.register_strategy(strategy)
        return strategy_id

    def activate_strategy(self, strategy_id: str) -> bool:
        """
        Activate a strategy.

        Args:
            strategy_id: Strategy to activate

        Returns:
            True if activated
        """
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False

        # Deactivate current
        if self.active_strategy:
            current = self.strategies.get(self.active_strategy)
            if current:
                current.is_active = False

        self.active_strategy = strategy_id
        strategy.is_active = True
        return True

    def deactivate_strategy(self) -> None:
        """Deactivate the current strategy."""
        if self.active_strategy:
            strategy = self.strategies.get(self.active_strategy)
            if strategy:
                strategy.is_active = False
            self.active_strategy = None

    def on_signal(self, handler: callable) -> None:
        """
        Register a signal handler.

        Args:
            handler: Function to call when signal is generated
        """
        self._signal_handlers.append(handler)

    async def process_signal(self, signal: Dict[str, Any]) -> None:
        """
        Process a trading signal.

        Args:
            signal: Signal dictionary
        """
        # Execute via active strategy
        if self.active_strategy:
            strategy = self.strategies.get(self.active_strategy)
            if strategy:
                await strategy.on_signal(signal)

        # Notify handlers
        for handler in self._signal_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(signal)
                else:
                    handler(signal)
            except Exception as e:
                print(f"Signal handler error: {e}")

    async def analyze_market_data(self, data: Dict[str, Any]) -> None:
        """
        Analyze market data and generate signals.

        Args:
            data: Market data dictionary
        """
        for strategy in self.strategies.values():
            if strategy.is_active:
                signal = await strategy.analyze(data)
                if signal:
                    await self.process_signal(signal)

    async def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update prices and process strategy ticks.

        Args:
            prices: Current prices for all symbols
        """
        # Update engine prices
        self.engine.update_prices(prices)

        # Notify strategies
        for strategy in self.strategies.values():
            if strategy.is_active:
                await strategy.on_tick(prices)

        # Record equity periodically
        self.engine.record_equity()

    async def start(self) -> None:
        """Start the strategy runner."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

        for strategy in self.strategies.values():
            await strategy.start()

    async def stop(self) -> None:
        """Stop the strategy runner."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        for strategy in self.strategies.values():
            await strategy.stop()

    async def _run_loop(self) -> None:
        """Main runner loop."""
        while self._running:
            try:
                # Strategy maintenance tasks
                await asyncio.sleep(self._update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Runner loop error: {e}")
                await asyncio.sleep(5)

    def get_performance(self) -> Dict[str, Any]:
        """Get combined performance summary."""
        engine_performance = self.engine.get_performance_summary()

        strategy_statuses = {
            sid: s.get_status()
            for sid, s in self.strategies.items()
        }

        return {
            "engine": engine_performance,
            "strategies": strategy_statuses,
            "active_strategy": self.active_strategy,
            "running": self._running
        }

    def get_signals(
        self,
        strategy_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get generated signals."""
        if strategy_id:
            strategy = self.strategies.get(strategy_id)
            if strategy:
                return strategy.signals[-limit:]
            return []

        all_signals = []
        for strategy in self.strategies.values():
            all_signals.extend(strategy.signals)

        return sorted(all_signals, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
