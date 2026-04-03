"""Risk analysis skill for evaluating trading risks."""

from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

from agents.base import BaseSkill


class RiskLevel(Enum):
    """Risk severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class RiskAssessment:
    """Represents a risk assessment."""

    def __init__(
        self,
        symbol: str,
        risk_level: RiskLevel,
        risk_score: float,
        factors: List[Dict],
        recommendations: List[str],
        position_size_adjustment: float = 1.0
    ):
        self.id = f"risk_{symbol}_{datetime.utcnow().timestamp()}"
        self.symbol = symbol
        self.risk_level = risk_level
        self.risk_score = risk_score  # 0-100
        self.factors = factors
        self.recommendations = recommendations
        self.position_size_adjustment = position_size_adjustment
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "risk_level": self.risk_level.value,
            "risk_score": round(self.risk_score, 2),
            "factors": self.factors,
            "recommendations": self.recommendations,
            "position_size_adjustment": self.position_size_adjustment,
            "timestamp": self.timestamp.isoformat()
        }


class RiskAnalysisSkill(BaseSkill):
    """
    Skill for analyzing trading risks.

    Evaluates:
    - Market volatility
    - Liquidity risk
    - Correlation risk
    - Drawdown risk
    - News/sentiment risk
    - Technical risk factors
    """

    def __init__(
        self,
        max_position_size_pct: float = 10.0,
        max_portfolio_risk: float = 2.0
    ):
        super().__init__(
            name="risk_analysis",
            description="Analyze trading risks and provide risk assessments with position sizing recommendations",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Asset symbol to analyze"
                    },
                    "position_size": {
                        "type": "number",
                        "description": "Proposed position size in USD"
                    },
                    "portfolio_value": {
                        "type": "number",
                        "description": "Total portfolio value in USD"
                    },
                    "market_data": {
                        "type": "object",
                        "description": "Market data including volatility, volume, etc."
                    },
                    "existing_positions": {
                        "type": "array",
                        "description": "List of existing portfolio positions",
                        "items": {"type": "object"}
                    },
                    "signal_strength": {
                        "type": "number",
                        "description": "Strength of trading signal (0-1)"
                    }
                },
                "required": ["symbol"]
            }
        )

        self.max_position_size_pct = max_position_size_pct
        self.max_portfolio_risk = max_portfolio_risk

    async def execute(
        self,
        symbol: str,
        position_size: float = 0,
        portfolio_value: float = 100000,
        market_data: Optional[Dict] = None,
        existing_positions: Optional[List[Dict]] = None,
        signal_strength: float = 0.5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute risk analysis.

        Args:
            symbol: Asset symbol
            position_size: Proposed position size
            portfolio_value: Total portfolio value
            market_data: Market data dictionary
            existing_positions: Current portfolio positions
            signal_strength: Signal confidence (0-1)

        Returns:
            Risk assessment dictionary
        """
        market_data = market_data or {}
        existing_positions = existing_positions or []

        try:
            # Analyze risk factors
            factors = []
            risk_score = 0

            # 1. Volatility Risk (0-25 points)
            volatility_score, vol_factor = self._analyze_volatility(market_data)
            risk_score += volatility_score
            if vol_factor:
                factors.append(vol_factor)

            # 2. Liquidity Risk (0-20 points)
            liquidity_score, liq_factor = self._analyze_liquidity(market_data)
            risk_score += liquidity_score
            if liq_factor:
                factors.append(liq_factor)

            # 3. Concentration Risk (0-20 points)
            concentration_score, conc_factor = self._analyze_concentration(
                symbol, position_size, portfolio_value, existing_positions
            )
            risk_score += concentration_score
            if conc_factor:
                factors.append(conc_factor)

            # 4. Market Risk (0-15 points)
            market_score, market_factor = self._analyze_market_conditions(market_data)
            risk_score += market_score
            if market_factor:
                factors.append(market_factor)

            # 5. Signal Quality Risk (0-10 points)
            signal_score, signal_factor = self._analyze_signal_quality(signal_strength)
            risk_score += signal_score
            if signal_factor:
                factors.append(signal_factor)

            # 6. Drawdown Risk (0-10 points)
            drawdown_score, dd_factor = self._analyze_drawdown(market_data)
            risk_score += drawdown_score
            if dd_factor:
                factors.append(dd_factor)

            # Determine risk level
            risk_level = self._get_risk_level(risk_score)

            # Calculate position size adjustment
            position_adjustment = self._calculate_position_adjustment(
                risk_score, signal_strength
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                risk_level, factors, position_size, portfolio_value
            )

            # Create assessment
            assessment = RiskAssessment(
                symbol=symbol,
                risk_level=risk_level,
                risk_score=risk_score,
                factors=factors,
                recommendations=recommendations,
                position_size_adjustment=position_adjustment
            )

            return {
                "success": True,
                "symbol": symbol,
                "assessment": assessment.to_dict(),
                "approved": risk_level not in [RiskLevel.CRITICAL, RiskLevel.HIGH],
                "max_position_size": (portfolio_value * self.max_position_size_pct / 100) * position_adjustment
            }

        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "error": str(e)
            }

    def _analyze_volatility(
        self,
        market_data: Dict
    ) -> tuple:
        """Analyze volatility risk."""
        volatility_24h = market_data.get("volatility_24h", 0)
        atr_percent = market_data.get("atr_percent", 0)

        score = 0
        factor = None

        if volatility_24h > 15 or atr_percent > 10:
            score = 25
            factor = {
                "type": "volatility",
                "severity": "high",
                "description": f"Extreme volatility detected ({volatility_24h:.1f}% / 24h, {atr_percent:.1f}% ATR)",
                "impact": "High probability of large adverse moves"
            }
        elif volatility_24h > 8 or atr_percent > 5:
            score = 15
            factor = {
                "type": "volatility",
                "severity": "medium",
                "description": f"Elevated volatility ({volatility_24h:.1f}% / 24h, {atr_percent:.1f}% ATR)",
                "impact": "Increased risk of stop hits"
            }
        elif volatility_24h > 5 or atr_percent > 3:
            score = 5
            factor = {
                "type": "volatility",
                "severity": "low",
                "description": f"Moderate volatility ({volatility_24h:.1f}% / 24h)",
                "impact": "Normal market conditions"
            }

        return score, factor

    def _analyze_liquidity(
        self,
        market_data: Dict
    ) -> tuple:
        """Analyze liquidity risk."""
        volume_24h = market_data.get("volume_24h", 0)
        market_cap = market_data.get("market_cap", 0)
        bid_ask_spread = market_data.get("bid_ask_spread", 0)

        score = 0
        factor = None

        # Volume to market cap ratio
        volume_ratio = (volume_24h / market_cap * 100) if market_cap > 0 else 0

        if volume_ratio < 2 or bid_ask_spread > 1:
            score = 20
            factor = {
                "type": "liquidity",
                "severity": "high",
                "description": f"Low liquidity (volume/MCap: {volume_ratio:.1f}%, spread: {bid_ask_spread:.2f}%)",
                "impact": "High slippage risk, difficult exit"
            }
        elif volume_ratio < 5 or bid_ask_spread > 0.5:
            score = 10
            factor = {
                "type": "liquidity",
                "severity": "medium",
                "description": f"Moderate liquidity (volume/MCap: {volume_ratio:.1f}%, spread: {bid_ask_spread:.2f}%)",
                "impact": "Some slippage expected on larger orders"
            }

        return score, factor

    def _analyze_concentration(
        self,
        symbol: str,
        position_size: float,
        portfolio_value: float,
        existing_positions: List[Dict]
    ) -> tuple:
        """Analyze concentration risk."""
        if portfolio_value <= 0:
            return 0, None

        # Calculate current exposure to this symbol
        symbol_exposure = position_size
        for pos in existing_positions:
            if pos.get("symbol") == symbol:
                symbol_exposure += pos.get("value", 0)

        concentration_pct = (symbol_exposure / portfolio_value) * 100

        score = 0
        factor = None

        if concentration_pct > self.max_position_size_pct * 1.5:
            score = 20
            factor = {
                "type": "concentration",
                "severity": "high",
                "description": f"Extreme concentration ({concentration_pct:.1f}% of portfolio)",
                "impact": "Portfolio overly exposed to single asset"
            }
        elif concentration_pct > self.max_position_size_pct:
            score = 12
            factor = {
                "type": "concentration",
                "severity": "medium",
                "description": f"High concentration ({concentration_pct:.1f}% of portfolio)",
                "impact": "Position exceeds recommended maximum"
            }
        elif concentration_pct > self.max_position_size_pct * 0.7:
            score = 5
            factor = {
                "type": "concentration",
                "severity": "low",
                "description": f"Approaching concentration limit ({concentration_pct:.1f}% of portfolio)",
                "impact": "Monitor for further increases"
            }

        return score, factor

    def _analyze_market_conditions(
        self,
        market_data: Dict
    ) -> tuple:
        """Analyze overall market conditions."""
        score = 0
        factor = None

        # Check for extreme conditions
        price_change_24h = abs(market_data.get("price_change_percentage_24h", 0))
        price_change_7d = abs(market_data.get("price_change_percentage_7d", 0))

        if price_change_24h > 20 or price_change_7d > 50:
            score = 15
            factor = {
                "type": "market_conditions",
                "severity": "high",
                "description": f"Extreme market movement (24h: {price_change_24h:.1f}%, 7d: {price_change_7d:.1f}%)",
                "impact": "Possible market manipulation or black swan event"
            }
        elif price_change_24h > 10:
            score = 8
            factor = {
                "type": "market_conditions",
                "severity": "medium",
                "description": f"Significant market movement ({price_change_24h:.1f}% / 24h)",
                "impact": "Momentum may continue or reverse sharply"
            }

        return score, factor

    def _analyze_signal_quality(
        self,
        signal_strength: float
    ) -> tuple:
        """Analyze signal quality risk."""
        score = 0
        factor = None

        if signal_strength < 0.5:
            score = 10
            factor = {
                "type": "signal_quality",
                "severity": "high",
                "description": f"Weak signal strength ({signal_strength:.2f})",
                "impact": "Low confidence in trade setup"
            }
        elif signal_strength < 0.7:
            score = 5
            factor = {
                "type": "signal_quality",
                "severity": "medium",
                "description": f"Moderate signal strength ({signal_strength:.2f})",
                "impact": "Consider waiting for stronger confirmation"
            }

        return score, factor

    def _analyze_drawdown(
        self,
        market_data: Dict
    ) -> tuple:
        """Analyze drawdown risk."""
        score = 0
        factor = None

        ath = market_data.get("ath", 0)
        current_price = market_data.get("price", 0)

        if ath > 0 and current_price > 0:
            drawdown = ((ath - current_price) / ath) * 100

            if drawdown > 50:
                score = 10
                factor = {
                    "type": "drawdown",
                    "severity": "medium",
                    "description": f"Asset in deep drawdown ({drawdown:.1f}% from ATH)",
                    "impact": "Potential value trap, may indicate structural issues"
                }
            elif drawdown > 80:
                score = 10
                factor = {
                    "type": "drawdown",
                    "severity": "high",
                    "description": f"Extreme drawdown ({drawdown:.1f}% from ATH)",
                    "impact": "High risk of further decline or project failure"
                }

        return score, factor

    def _get_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level from score."""
        if risk_score >= 70:
            return RiskLevel.CRITICAL
        elif risk_score >= 50:
            return RiskLevel.HIGH
        elif risk_score >= 30:
            return RiskLevel.MEDIUM
        elif risk_score >= 15:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def _calculate_position_adjustment(
        self,
        risk_score: float,
        signal_strength: float
    ) -> float:
        """Calculate position size adjustment based on risk."""
        # Base adjustment on risk score
        if risk_score >= 70:
            base_adjustment = 0.0
        elif risk_score >= 50:
            base_adjustment = 0.3
        elif risk_score >= 30:
            base_adjustment = 0.6
        elif risk_score >= 15:
            base_adjustment = 0.85
        else:
            base_adjustment = 1.0

        # Adjust for signal strength
        signal_multiplier = 0.5 + (signal_strength * 0.5)

        return min(base_adjustment * signal_multiplier, 1.0)

    def _generate_recommendations(
        self,
        risk_level: RiskLevel,
        factors: List[Dict],
        position_size: float,
        portfolio_value: float
    ) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []

        if risk_level == RiskLevel.CRITICAL:
            recommendations.append("DO NOT ENTER POSITION - Risk level critical")
            recommendations.append("Review market conditions before considering any trades")
        elif risk_level == RiskLevel.HIGH:
            recommendations.append("Reduce position size by at least 50%")
            recommendations.append("Set tighter stop losses")
            recommendations.append("Consider waiting for better entry")
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.append("Use reduced position size (70-85% of planned)")
            recommendations.append("Monitor risk factors closely")
        elif risk_level == RiskLevel.LOW:
            recommendations.append("Standard position sizing acceptable")
            recommendations.append("Maintain normal risk management")
        else:
            recommendations.append("Favorable conditions for entry")
            recommendations.append("Can increase position size if desired")

        # Factor-specific recommendations
        for factor in factors:
            if factor["type"] == "volatility" and factor["severity"] == "high":
                recommendations.append("Widen stop losses to account for volatility")
            elif factor["type"] == "liquidity":
                recommendations.append("Use limit orders only - avoid market orders")
            elif factor["type"] == "concentration":
                recommendations.append("Consider diversifying into other assets")
            elif factor["type"] == "drawdown":
                recommendations.append("Research fundamental reasons for drawdown")

        return recommendations
