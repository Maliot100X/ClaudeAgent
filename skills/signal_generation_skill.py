"""Signal generation skill for creating trading signals."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import asyncio

from agents.base import BaseSkill


class SignalType(Enum):
    """Types of trading signals."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    NEUTRAL = "neutral"


class SignalStrength(Enum):
    """Strength level of signals."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


class Signal:
    """Represents a trading signal."""

    def __init__(
        self,
        symbol: str,
        signal_type: SignalType,
        strength: SignalStrength,
        price: float,
        reasoning: str,
        metadata: Optional[Dict] = None
    ):
        self.id = f"{symbol}_{datetime.utcnow().timestamp()}"
        self.symbol = symbol
        self.signal_type = signal_type
        self.strength = strength
        self.price = price
        self.reasoning = reasoning
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
        self.confidence = 0.0  # Calculated

    def to_dict(self) -> Dict[str, Any]:
        """Convert signal to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "type": self.signal_type.value,
            "strength": self.strength.name,
            "strength_value": self.strength.value,
            "price": self.price,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "metadata": self.metadata
        }


class SignalGenerationSkill(BaseSkill):
    """
    Skill for generating trading signals based on market data and analysis.

    Generates signals using:
    - Price action analysis
    - Technical indicators
    - Market sentiment
    - Multi-timeframe confluence
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        generate_reasoning: bool = True
    ):
        super().__init__(
            name="signal_generation",
            description="Generate trading signals based on market analysis and technical indicators",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair symbol (e.g., BTC, ETH)"
                    },
                    "price": {
                        "type": "number",
                        "description": "Current price of the asset"
                    },
                    "indicators": {
                        "type": "object",
                        "description": "Technical indicator values (RSI, MACD, etc.)"
                    },
                    "market_data": {
                        "type": "object",
                        "description": "Additional market context"
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Analysis timeframe",
                        "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                        "default": "1h"
                    }
                },
                "required": ["symbol", "price"]
            }
        )

        self.min_confidence = min_confidence
        self.generate_reasoning = generate_reasoning

    async def execute(
        self,
        symbol: str,
        price: float,
        indicators: Optional[Dict] = None,
        market_data: Optional[Dict] = None,
        timeframe: str = "1h",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate trading signal.

        Args:
            symbol: Asset symbol
            price: Current price
            indicators: Technical indicators
            market_data: Additional market data
            timeframe: Analysis timeframe

        Returns:
            Signal data dictionary
        """
        indicators = indicators or {}
        market_data = market_data or {}

        try:
            # Calculate signal using technical analysis
            signal, strength, reasoning = await self._calculate_signal(
                symbol=symbol,
                price=price,
                indicators=indicators,
                market_data=market_data,
                timeframe=timeframe
            )

            # Create signal object
            signal_obj = Signal(
                symbol=symbol,
                signal_type=signal,
                strength=strength,
                price=price,
                reasoning=reasoning,
                metadata={
                    "indicators": indicators,
                    "market_data": market_data,
                    "timeframe": timeframe
                }
            )

            # Calculate confidence
            signal_obj.confidence = self._calculate_confidence(
                signal, strength, indicators
            )

            # Check minimum confidence
            if signal_obj.confidence < self.min_confidence:
                return {
                    "success": False,
                    "symbol": symbol,
                    "reason": f"Confidence {signal_obj.confidence:.2f} below threshold {self.min_confidence}",
                    "signal": None
                }

            return {
                "success": True,
                "symbol": symbol,
                "signal": signal_obj.to_dict(),
                "action_required": signal in [SignalType.BUY, SignalType.STRONG_BUY, SignalType.SELL, SignalType.STRONG_SELL]
            }

        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "error": str(e),
                "signal": None
            }

    async def _calculate_signal(
        self,
        symbol: str,
        price: float,
        indicators: Dict,
        market_data: Dict,
        timeframe: str
    ) -> tuple:
        """
        Calculate trading signal using technical analysis.

        Returns:
            Tuple of (SignalType, SignalStrength, reasoning)
        """
        # Extract key indicators
        rsi = indicators.get("rsi", 50)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        bb_position = indicators.get("bb_position", 0.5)  # Bollinger Bands position (0-1)
        volume_ratio = indicators.get("volume_ratio", 1.0)  # Volume vs average
        ema_alignment = indicators.get("ema_alignment", 0)  # EMA trend alignment
        support_distance = indicators.get("support_distance", 0)  # Distance to support
        resistance_distance = indicators.get("resistance_distance", 0)  # Distance to resistance

        # Price change data
        price_change_24h = market_data.get("price_change_percentage_24h", 0)

        # Scoring system
        buy_score = 0
        sell_score = 0
        reasoning_parts = []

        # RSI analysis
        if rsi < 30:
            buy_score += 2
            reasoning_parts.append(f"RSI oversold at {rsi:.1f}")
        elif rsi < 40:
            buy_score += 1
            reasoning_parts.append(f"RSI approaching oversold at {rsi:.1f}")
        elif rsi > 70:
            sell_score += 2
            reasoning_parts.append(f"RSI overbought at {rsi:.1f}")
        elif rsi > 60:
            sell_score += 1
            reasoning_parts.append(f"RSI approaching overbought at {rsi:.1f}")

        # MACD analysis
        if macd > macd_signal and macd > 0:
            buy_score += 2
            reasoning_parts.append("MACD bullish crossover with positive momentum")
        elif macd > macd_signal:
            buy_score += 1
            reasoning_parts.append("MACD bullish crossover")
        elif macd < macd_signal and macd < 0:
            sell_score += 2
            reasoning_parts.append("MACD bearish crossover with negative momentum")
        elif macd < macd_signal:
            sell_score += 1
            reasoning_parts.append("MACD bearish crossover")

        # Bollinger Bands
        if bb_position < 0.1:
            buy_score += 2
            reasoning_parts.append("Price at lower Bollinger Band (potential bounce)")
        elif bb_position > 0.9:
            sell_score += 2
            reasoning_parts.append("Price at upper Bollinger Band (potential reversal)")

        # Volume analysis
        if volume_ratio > 1.5:
            if buy_score > sell_score:
                buy_score += 1
                reasoning_parts.append(f"High volume ({volume_ratio:.1f}x average) supporting bullish move")
            elif sell_score > buy_score:
                sell_score += 1
                reasoning_parts.append(f"High volume ({volume_ratio:.1f}x average) supporting bearish move")

        # EMA alignment
        if ema_alignment > 0.5:
            buy_score += 1
            reasoning_parts.append("Bullish EMA alignment")
        elif ema_alignment < -0.5:
            sell_score += 1
            reasoning_parts.append("Bearish EMA alignment")

        # Support/Resistance
        if support_distance > 0 and support_distance < 2:  # Within 2%
            buy_score += 1
            reasoning_parts.append(f"Near support level ({support_distance:.1f}% away)")
        if resistance_distance > 0 and resistance_distance < 2:
            sell_score += 1
            reasoning_parts.append(f"Near resistance level ({resistance_distance:.1f}% away)")

        # Price momentum
        if price_change_24h < -10:
            buy_score += 1
            reasoning_parts.append(f"Oversold bounce potential (down {price_change_24h:.1f}% in 24h)")
        elif price_change_24h > 10:
            sell_score += 1
            reasoning_parts.append(f"Overextended (up {price_change_24h:.1f}% in 24h)")

        # Determine signal
        if buy_score >= 5:
            signal = SignalType.STRONG_BUY
            strength = SignalStrength.VERY_STRONG if buy_score >= 7 else SignalStrength.STRONG
        elif buy_score >= 3:
            signal = SignalType.BUY
            strength = SignalStrength.MODERATE if buy_score >= 4 else SignalStrength.WEAK
        elif sell_score >= 5:
            signal = SignalType.STRONG_SELL
            strength = SignalStrength.VERY_STRONG if sell_score >= 7 else SignalStrength.STRONG
        elif sell_score >= 3:
            signal = SignalType.SELL
            strength = SignalStrength.MODERATE if sell_score >= 4 else SignalStrength.WEAK
        else:
            signal = SignalType.HOLD
            strength = SignalStrength.WEAK

        # Build reasoning
        if not reasoning_parts:
            reasoning = f"No clear signals. Buy score: {buy_score}, Sell score: {sell_score}. Neutral stance."
        else:
            direction = "bullish" if buy_score > sell_score else "bearish" if sell_score > buy_score else "neutral"
            reasoning = f"{direction.capitalize()} signals detected ({buy_score} buy vs {sell_score} sell): " + "; ".join(reasoning_parts)

        return signal, strength, reasoning

    def _calculate_confidence(
        self,
        signal: SignalType,
        strength: SignalStrength,
        indicators: Dict
    ) -> float:
        """
        Calculate confidence score for the signal.

        Returns:
            Confidence score 0-1
        """
        base_confidence = 0.5

        # Signal type contribution
        if signal in [SignalType.STRONG_BUY, SignalType.STRONG_SELL]:
            base_confidence += 0.2
        elif signal in [SignalType.BUY, SignalType.SELL]:
            base_confidence += 0.1

        # Strength contribution
        strength_multiplier = {
            SignalStrength.WEAK: 0.05,
            SignalStrength.MODERATE: 0.1,
            SignalStrength.STRONG: 0.15,
            SignalStrength.VERY_STRONG: 0.2
        }
        base_confidence += strength_multiplier.get(strength, 0)

        # Indicator quality bonus
        indicator_count = len([v for v in indicators.values() if v is not None])
        if indicator_count >= 5:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    async def batch_generate(
        self,
        symbols: List[str],
        prices: List[float],
        indicators_list: List[Dict],
        market_data_list: List[Dict],
        timeframe: str = "1h"
    ) -> List[Dict]:
        """
        Generate signals for multiple symbols.

        Args:
            symbols: List of symbols
            prices: List of prices
            indicators_list: List of indicator dicts
            market_data_list: List of market data dicts
            timeframe: Analysis timeframe

        Returns:
            List of signal results
        """
        tasks = [
            self.execute(
                symbol=symbol,
                price=price,
                indicators=indicators,
                market_data=market_data,
                timefraME=timeframe
            )
            for symbol, price, indicators, market_data in zip(
                symbols, prices, indicators_list, market_data_list
            )
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            result if not isinstance(result, Exception) else {
                "success": False,
                "error": str(result)
            }
            for result in results
        ]
