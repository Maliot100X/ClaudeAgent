"""Strategy backtesting skill for testing trading strategies on historical data."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np

from agents.base import BaseSkill


class StrategyType(Enum):
    """Supported strategy types."""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend_following"
    CUSTOM = "custom"


@dataclass
class BacktestResult:
    """Results of a backtest."""
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    total_return: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_trade_return: float
    profit_factor: float
    trades: List[Dict]
    equity_curve: List[Dict]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "period": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat()
            },
            "capital": {
                "initial": self.initial_capital,
                "final": self.final_equity,
                "return": self.total_return,
                "return_pct": round(self.total_return_pct, 2)
            },
            "metrics": {
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "max_drawdown": self.max_drawdown,
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "win_rate": round(self.win_rate, 2),
                "avg_trade_return": round(self.avg_trade_return, 4),
                "profit_factor": round(self.profit_factor, 2)
            },
            "trades": self.trades,
            "equity_curve": self.equity_curve
        }


class StrategyBacktestSkill(BaseSkill):
    """
    Skill for backtesting trading strategies on historical data.

    Supports multiple strategy types with configurable parameters.
    """

    def __init__(
        self,
        default_initial_capital: float = 10000.0,
        default_commission: float = 0.001  # 0.1%
    ):
        super().__init__(
            name="strategy_backtest",
            description="Backtest trading strategies on historical price data with performance metrics",
            parameters={
                "type": "object",
                "properties": {
                    "strategy_type": {
                        "type": "string",
                        "enum": ["momentum", "mean_reversion", "breakout", "trend_following", "custom"],
                        "description": "Type of strategy to backtest"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair symbol"
                    },
                    "historical_data": {
                        "type": "array",
                        "description": "Historical OHLCV data",
                        "items": {
                            "type": "object",
                            "properties": {
                                "timestamp": {"type": "string"},
                                "open": {"type": "number"},
                                "high": {"type": "number"},
                                "low": {"type": "number"},
                                "close": {"type": "number"},
                                "volume": {"type": "number"}
                            }
                        }
                    },
                    "initial_capital": {
                        "type": "number",
                        "description": "Starting capital",
                        "default": default_initial_capital
                    },
                    "strategy_params": {
                        "type": "object",
                        "description": "Strategy-specific parameters"
                    },
                    "commission": {
                        "type": "number",
                        "description": "Commission per trade (0.001 = 0.1%)",
                        "default": default_commission
                    }
                },
                "required": ["strategy_type", "symbol", "historical_data"]
            }
        )

        self.default_initial_capital = default_initial_capital
        self.default_commission = default_commission

    async def execute(
        self,
        strategy_type: str,
        symbol: str,
        historical_data: List[Dict],
        initial_capital: float = None,
        strategy_params: Optional[Dict] = None,
        commission: float = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute backtest.

        Args:
            strategy_type: Type of strategy
            symbol: Trading symbol
            historical_data: OHLCV data list
            initial_capital: Starting capital
            strategy_params: Strategy parameters
            commission: Trading commission

        Returns:
            Backtest results
        """
        initial_capital = initial_capital or self.default_initial_capital
        commission = commission or self.default_commission
        strategy_params = strategy_params or {}

        try:
            if not historical_data or len(historical_data) < 20:
                return {
                    "success": False,
                    "error": "Insufficient historical data (minimum 20 candles required)"
                }

            # Convert to DataFrame
            df = self._prepare_data(historical_data)

            if df.empty:
                return {
                    "success": False,
                    "error": "Failed to process historical data"
                }

            # Generate signals based on strategy
            signals = self._generate_signals(
                df,
                StrategyType(strategy_type),
                strategy_params
            )

            # Run backtest simulation
            result = self._run_backtest(
                df=df,
                signals=signals,
                symbol=symbol,
                strategy_name=strategy_type,
                initial_capital=initial_capital,
                commission=commission
            )

            return {
                "success": True,
                "symbol": symbol,
                "strategy": strategy_type,
                "backtest": result.to_dict()
            }

        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "strategy": strategy_type,
                "error": str(e)
            }

    def _prepare_data(self, historical_data: List[Dict]) -> pd.DataFrame:
        """Prepare historical data for backtesting."""
        df = pd.DataFrame(historical_data)

        # Ensure required columns
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        # Ensure numeric types
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Calculate indicators
        df['returns'] = df['close'].pct_change()
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(14).mean()

        # Volume moving average
        df['volume_sma'] = df['volume'].rolling(window=20).mean()

        return df

    def _generate_signals(
        self,
        df: pd.DataFrame,
        strategy_type: StrategyType,
        params: Dict
    ) -> pd.Series:
        """Generate trading signals based on strategy type."""
        signals = pd.Series(index=df.index, data=0)  # 0 = hold, 1 = buy, -1 = sell

        if strategy_type == StrategyType.MOMENTUM:
            signals = self._momentum_strategy(df, params)
        elif strategy_type == StrategyType.MEAN_REVERSION:
            signals = self._mean_reversion_strategy(df, params)
        elif strategy_type == StrategyType.BREAKOUT:
            signals = self._breakout_strategy(df, params)
        elif strategy_type == StrategyType.TREND_FOLLOWING:
            signals = self._trend_following_strategy(df, params)

        return signals

    def _momentum_strategy(
        self,
        df: pd.DataFrame,
        params: Dict
    ) -> pd.Series:
        """Momentum-based strategy using MACD and RSI."""
        signals = pd.Series(index=df.index, data=0)

        rsi_buy = params.get("rsi_buy_threshold", 60)
        rsi_sell = params.get("rsi_sell_threshold", 40)

        # Buy: MACD bullish crossover + RSI > threshold
        buy_condition = (
            (df['macd'] > df['macd_signal']) &
            (df['macd'].shift(1) <= df['macd_signal'].shift(1)) &
            (df['rsi'] > rsi_buy)
        )

        # Sell: MACD bearish crossover + RSI < threshold
        sell_condition = (
            (df['macd'] < df['macd_signal']) &
            (df['macd'].shift(1) >= df['macd_signal'].shift(1)) &
            (df['rsi'] < rsi_sell)
        )

        signals[buy_condition] = 1
        signals[sell_condition] = -1

        return signals

    def _mean_reversion_strategy(
        self,
        df: pd.DataFrame,
        params: Dict
    ) -> pd.Series:
        """Mean reversion using Bollinger Bands."""
        signals = pd.Series(index=df.index, data=0)

        bb_threshold = params.get("bb_threshold", 0.05)

        # Buy: Price near lower band
        buy_condition = (
            (df['close'] <= df['bb_lower'] * (1 + bb_threshold)) &
            (df['rsi'] < 30)
        )

        # Sell: Price near upper band
        sell_condition = (
            (df['close'] >= df['bb_upper'] * (1 - bb_threshold)) &
            (df['rsi'] > 70)
        )

        signals[buy_condition] = 1
        signals[sell_condition] = -1

        return signals

    def _breakout_strategy(
        self,
        df: pd.DataFrame,
        params: Dict
    ) -> pd.Series:
        """Breakout strategy using price levels."""
        signals = pd.Series(index=df.index, data=0)

        lookback = params.get("lookback_period", 20)
        volume_confirm = params.get("volume_confirmation", True)

        # Calculate high/low channels
        df['highest_high'] = df['high'].rolling(window=lookback).max()
        df['lowest_low'] = df['low'].rolling(window=lookback).min()

        # Breakout buy
        buy_condition = df['close'] > df['highest_high'].shift(1)
        if volume_confirm:
            buy_condition = buy_condition & (df['volume'] > df['volume_sma'] * 1.2)

        # Breakdown sell
        sell_condition = df['close'] < df['lowest_low'].shift(1)
        if volume_confirm:
            sell_condition = sell_condition & (df['volume'] > df['volume_sma'] * 1.2)

        signals[buy_condition] = 1
        signals[sell_condition] = -1

        return signals

    def _trend_following_strategy(
        self,
        df: pd.DataFrame,
        params: Dict
    ) -> pd.Series:
        """Trend following using moving averages."""
        signals = pd.Series(index=df.index, data=0)

        # Golden cross (buy)
        buy_condition = (
            (df['sma_20'] > df['sma_50']) &
            (df['sma_20'].shift(1) <= df['sma_50'].shift(1))
        )

        # Death cross (sell)
        sell_condition = (
            (df['sma_20'] < df['sma_50']) &
            (df['sma_20'].shift(1) >= df['sma_50'].shift(1))
        )

        signals[buy_condition] = 1
        signals[sell_condition] = -1

        return signals

    def _run_backtest(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        symbol: str,
        strategy_name: str,
        initial_capital: float,
        commission: float
    ) -> BacktestResult:
        """Run backtest simulation."""
        capital = initial_capital
        position = 0.0  # Amount of base asset held
        trades = []
        equity_curve = []

        entry_price = 0.0
        entry_time = None

        for timestamp, row in df.iterrows():
            signal = signals.loc[timestamp]
            price = row['close']

            # Record equity
            current_equity = capital + (position * price)
            equity_curve.append({
                "timestamp": timestamp.isoformat(),
                "equity": current_equity,
                "price": price
            })

            # Process signal
            if signal == 1 and position == 0:  # Buy
                # Calculate position size (use 95% of capital)
                position_value = capital * 0.95
                position = position_value / price
                commission_cost = position_value * commission

                capital -= position_value + commission_cost
                entry_price = price
                entry_time = timestamp

            elif signal == -1 and position > 0:  # Sell
                # Close position
                position_value = position * price
                commission_cost = position_value * commission

                capital += position_value - commission_cost

                # Record trade
                pnl = (price - entry_price) * position - (commission_cost * 2)
                pnl_pct = ((price / entry_price) - 1) * 100

                trades.append({
                    "entry_time": entry_time.isoformat() if entry_time else None,
                    "exit_time": timestamp.isoformat(),
                    "entry_price": entry_price,
                    "exit_price": price,
                    "position_size": position,
                    "pnl": pnl,
                    "pnl_pct": round(pnl_pct, 2),
                    "type": "long"
                })

                position = 0
                entry_price = 0

        # Close any remaining position at final price
        final_price = df['close'].iloc[-1]
        final_equity = capital + (position * final_price)

        if position > 0:
            position_value = position * final_price
            commission_cost = position_value * commission
            capital += position_value - commission_cost

            pnl = (final_price - entry_price) * position - commission_cost
            pnl_pct = ((final_price / entry_price) - 1) * 100

            trades.append({
                "entry_time": entry_time.isoformat() if entry_time else None,
                "exit_time": df.index[-1].isoformat(),
                "entry_price": entry_price,
                "exit_price": final_price,
                "position_size": position,
                "pnl": pnl,
                "pnl_pct": round(pnl_pct, 2),
                "type": "long",
                "note": "Position closed at end of backtest"
            })

        # Calculate metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t['pnl'] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        total_pnl = sum(t['pnl'] for t in trades)
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Calculate returns
        total_return = final_equity - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        # Calculate Sharpe ratio
        equity_df = pd.DataFrame(equity_curve)
        if len(equity_df) > 1:
            equity_returns = equity_df['equity'].pct_change().dropna()
            if len(equity_returns) > 0 and equity_returns.std() != 0:
                sharpe_ratio = (equity_returns.mean() / equity_returns.std()) * np.sqrt(365)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # Calculate max drawdown
        peak = equity_df['equity'].expanding(min_periods=1).max()
        drawdown = (equity_df['equity'] - peak) / peak
        max_drawdown = drawdown.min()
        max_drawdown_pct = max_drawdown * 100

        avg_trade_return = total_pnl / total_trades if total_trades > 0 else 0

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=df.index[0],
            end_date=df.index[-1],
            initial_capital=initial_capital,
            final_equity=final_equity,
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_trade_return=avg_trade_return,
            profit_factor=profit_factor,
            trades=trades,
            equity_curve=equity_curve
        )