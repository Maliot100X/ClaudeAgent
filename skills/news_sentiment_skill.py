"""News sentiment analysis skill for market sentiment evaluation."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import re

from agents.base import BaseSkill


class Sentiment(Enum):
    """Sentiment classifications."""
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    SLIGHTLY_POSITIVE = "slightly_positive"
    NEUTRAL = "neutral"
    SLIGHTLY_NEGATIVE = "slightly_negative"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class SentimentScore:
    """Represents a sentiment analysis result."""

    def __init__(
        self,
        symbol: str,
        score: float,  # -1 to 1
        sentiment: Sentiment,
        confidence: float,
        sources: List[Dict],
        keywords: List[str],
        analysis: str
    ):
        self.symbol = symbol
        self.score = score
        self.sentiment = sentiment
        self.confidence = confidence
        self.sources = sources
        self.keywords = keywords
        self.analysis = analysis
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "score": round(self.score, 3),
            "sentiment": self.sentiment.value,
            "confidence": round(self.confidence, 2),
            "sources": self.sources,
            "keywords": self.keywords,
            "analysis": self.analysis,
            "timestamp": self.timestamp.isoformat()
        }


class NewsSentimentSkill(BaseSkill):
    """
    Skill for analyzing news sentiment related to cryptocurrency assets.

    Analyzes:
    - Social media sentiment (Twitter/X, Reddit)
    - News articles
    - On-chain metrics sentiment
    - Market fear/greed indicators
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        cache_duration: int = 300  # 5 minutes
    ):
        super().__init__(
            name="news_sentiment",
            description="Analyze news and social media sentiment for cryptocurrency assets",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Asset symbol to analyze (e.g., BTC, ETH)"
                    },
                    "sources": {
                        "type": "array",
                        "description": "Sources to analyze",
                        "items": {
                            "type": "string",
                            "enum": ["twitter", "reddit", "news", "onchain", "fear_greed"]
                        },
                        "default": ["twitter", "reddit", "news", "fear_greed"]
                    },
                    "time_window": {
                        "type": "string",
                        "description": "Time window for analysis",
                        "enum": ["1h", "24h", "7d"],
                        "default": "24h"
                    },
                    "include_keywords": {
                        "type": "boolean",
                        "description": "Include trending keywords",
                        "default": True
                    }
                },
                "required": ["symbol"]
            }
        )

        self.min_confidence = min_confidence
        self.cache_duration = cache_duration

        # Sentiment lexicons
        self.positive_words = {
            'bullish', 'moon', 'pump', 'breakout', 'surge', 'rally', ' ATH',
            'adoption', 'partnership', 'upgrade', 'launch', 'mooning',
            'revolutionary', 'innovation', 'growth', 'strong', 'buy',
            'hodl', 'hold', 'diamond hands', 'all time high', 'massive',
            'explosive', 'soaring', 'moonshot', 'generational wealth',
            'institutional', 'mainstream', 'winning', 'gains', 'profits'
        }

        self.negative_words = {
            'bearish', 'dump', 'crash', 'rugpull', 'scam', 'hack', 'exploit',
            'delist', 'ban', 'regulation', 'sell', 'panic', 'fear', 'bear',
            'downtrend', 'collapse', 'bubble', 'ponzi', 'fraud', 'lawsuit',
            'investigation', 'penalty', 'fine', 'frozen', 'bankruptcy',
            'liquidation', 'margin call', 'capitulation', 'dip', 'red'
        }

        self.cryptocurrency_aliases = {
            'BTC': ['bitcoin', 'btc', 'xbt', 'satoshi', 'nakamoto'],
            'ETH': ['ethereum', 'eth', 'vitalik', 'buterin', 'ether'],
            'SOL': ['solana', 'sol', 'anatoly'],
            'ADA': ['cardano', 'ada', 'hoskinson'],
            'DOT': ['polkadot', 'dot'],
            'AVAX': ['avalanche', 'avax'],
            'MATIC': ['polygon', 'matic'],
            'LINK': ['chainlink', 'link'],
            'DOGE': ['dogecoin', 'doge'],
            'XRP': ['ripple', 'xrp'],
            'LTC': ['litecoin', 'ltc'],
            'BCH': ['bitcoin cash', 'bch'],
        }

    async def execute(
        self,
        symbol: str,
        sources: Optional[List[str]] = None,
        time_window: str = "24h",
        include_keywords: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute sentiment analysis.

        Args:
            symbol: Asset symbol
            sources: Data sources to analyze
            time_window: Analysis time window
            include_keywords: Include trending keywords

        Returns:
            Sentiment analysis result
        """
        sources = sources or ["twitter", "reddit", "news", "fear_greed"]

        try:
            # In production, this would fetch real data from APIs
            # For now, simulate analysis
            sentiment_data = await self._analyze_sentiment(
                symbol=symbol,
                sources=sources,
                time_window=time_window
            )

            # Calculate overall sentiment
            score = sentiment_data['score']
            sentiment = self._score_to_sentiment(score)
            confidence = sentiment_data['confidence']

            # Generate analysis text
            analysis = self._generate_analysis(symbol, sentiment, sentiment_data)

            result = SentimentScore(
                symbol=symbol,
                score=score,
                sentiment=sentiment,
                confidence=confidence,
                sources=sentiment_data.get('sources', []),
                keywords=sentiment_data.get('keywords', []) if include_keywords else [],
                analysis=analysis
            )

            return {
                "success": True,
                "symbol": symbol,
                "sentiment": result.to_dict(),
                "trading_implication": self._get_trading_implication(sentiment, confidence)
            }

        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "error": str(e)
            }

    async def _analyze_sentiment(
        self,
        symbol: str,
        sources: List[str],
        time_window: str
    ) -> Dict[str, Any]:
        """
        Analyze sentiment from multiple sources.

        In production, this fetches from:
        - Twitter/X API
        - Reddit API
        - News APIs (CryptoPanic, NewsAPI)
        - On-chain sentiment (Glassnode, Santiment)
        - Fear & Greed Index
        """
        source_results = []
        total_score = 0
        total_weight = 0

        for source in sources:
            if source == "fear_greed":
                # Simulate fear & greed index (0-100, 50=neutral)
                # In production: fetch from alternative.me API
                fear_greed_value = 55  # Neutral zone
                source_score = (fear_greed_value - 50) / 50  # Convert to -1 to 1
                weight = 0.3

                source_results.append({
                    "source": "fear_greed_index",
                    "score": source_score,
                    "value": fear_greed_value,
                    "classification": self._fear_greed_classification(fear_greed_value),
                    "weight": weight
                })

                total_score += source_score * weight
                total_weight += weight

            elif source in ["twitter", "reddit", "news"]:
                # Simulate social/news sentiment
                # In production: fetch and analyze actual posts/articles
                source_data = self._simulate_social_sentiment(symbol, source)
                weight = 0.25 if source == "twitter" else 0.2 if source == "reddit" else 0.25

                source_results.append({
                    "source": source,
                    "score": source_data['score'],
                    "volume": source_data['volume'],
                    "positive_mentions": source_data['positive'],
                    "negative_mentions": source_data['negative'],
                    "weight": weight
                })

                total_score += source_data['score'] * weight
                total_weight += weight

            elif source == "onchain":
                # Simulate on-chain sentiment
                source_data = self._simulate_onchain_sentiment(symbol)
                weight = 0.2

                source_results.append({
                    "source": "onchain_metrics",
                    "score": source_data['score'],
                    "metrics": source_data['metrics'],
                    "weight": weight
                })

                total_score += source_data['score'] * weight
                total_weight += weight

        # Calculate weighted average
        if total_weight > 0:
            final_score = total_score / total_weight
        else:
            final_score = 0

        # Calculate confidence based on data volume and consistency
        confidence = self._calculate_confidence(source_results)

        # Extract keywords (in production: use NLP/TF-IDF)
        keywords = self._extract_keywords(symbol)

        return {
            "score": final_score,
            "confidence": confidence,
            "sources": source_results,
            "keywords": keywords,
            "time_window": time_window
        }

    def _simulate_social_sentiment(self, symbol: str, source: str) -> Dict:
        """Simulate social media sentiment data."""
        import random

        # Deterministic "randomness" for consistent demo results
        base = hash(f"{symbol}_{source}") % 100

        volume = 1000 + (base * 50)  # Mention volume
        positive = int(volume * (0.4 + (base % 20) / 100))
        negative = int(volume * (0.3 + ((base + 10) % 20) / 100))
        neutral = volume - positive - negative

        score = (positive - negative) / volume

        return {
            "score": score,
            "volume": volume,
            "positive": positive,
            "negative": negative,
            "neutral": neutral
        }

    def _simulate_onchain_sentiment(self, symbol: str) -> Dict:
        """Simulate on-chain sentiment metrics."""
        import random

        base = hash(f"{symbol}_onchain") % 100

        # Active addresses trend
        active_addr_change = (base - 50) / 100

        # Exchange inflow/outflow
        netflow = (base - 50) / 50  # Negative = bullish (outflow)

        # Whale accumulation
        whale_score = (base % 60) / 100

        # Network growth
        network_growth = (base - 40) / 100

        # Combined score
        score = (active_addr_change * 0.2 + netflow * 0.3 +
                 whale_score * 0.3 + network_growth * 0.2)

        return {
            "score": score,
            "metrics": {
                "active_addresses_change": active_addr_change,
                "exchange_netflow": netflow,
                "whale_accumulation": whale_score,
                "network_growth": network_growth
            }
        }

    def _fear_greed_classification(self, value: int) -> str:
        """Classify fear & greed value."""
        if value <= 20:
            return "Extreme Fear"
        elif value <= 40:
            return "Fear"
        elif value <= 60:
            return "Neutral"
        elif value <= 80:
            return "Greed"
        else:
            return "Extreme Greed"

    def _score_to_sentiment(self, score: float) -> Sentiment:
        """Convert numerical score to sentiment enum."""
        if score >= 0.7:
            return Sentiment.VERY_POSITIVE
        elif score >= 0.4:
            return Sentiment.POSITIVE
        elif score >= 0.1:
            return Sentiment.SLIGHTLY_POSITIVE
        elif score > -0.1:
            return Sentiment.NEUTRAL
        elif score > -0.4:
            return Sentiment.SLIGHTLY_NEGATIVE
        elif score > -0.7:
            return Sentiment.NEGATIVE
        else:
            return Sentiment.VERY_NEGATIVE

    def _calculate_confidence(self, sources: List[Dict]) -> float:
        """Calculate confidence score based on source data."""
        if not sources:
            return 0.5

        # Factor 1: Number of sources
        source_factor = min(len(sources) / 4, 1.0) * 0.3

        # Factor 2: Data consistency
        scores = [s.get('score', 0) for s in sources]
        if scores:
            score_variance = max(scores) - min(scores)
            consistency_factor = (1 - min(score_variance, 1)) * 0.4
        else:
            consistency_factor = 0

        # Factor 3: Data volume (for social sources)
        volume_factor = 0
        for source in sources:
            if 'volume' in source:
                volume = source['volume']
                if volume > 1000:
                    volume_factor = 0.3
                    break

        return min(source_factor + consistency_factor + volume_factor, 1.0)

    def _extract_keywords(self, symbol: str) -> List[str]:
        """Extract trending keywords related to symbol."""
        # In production: use NLP/TF-IDF on actual content
        common_crypto_keywords = [
            "bull run", "altcoin season", "defi", "nft", "staking",
            "yield farming", "airdrop", "mainnet", "testnet", "dao"
        ]

        symbol_keywords = {
            'BTC': ['halving', 'lightning network', 'schnorr', 'taproot'],
            'ETH': ['eth2', 'staking', 'defi', 'l2', 'rollups', 'eip'],
            'SOL': ['solana ecosystem', 'nft marketplace', 'validator'],
            'ADA': ['cardano smart contracts', 'hydra', 'goguen'],
        }

        return symbol_keywords.get(symbol, []) + common_crypto_keywords[:5]

    def _generate_analysis(
        self,
        symbol: str,
        sentiment: Sentiment,
        sentiment_data: Dict
    ) -> str:
        """Generate human-readable analysis."""
        score = sentiment_data['score']
        sources = sentiment_data.get('sources', [])

        parts = [f"Sentiment analysis for {symbol} shows {sentiment.value.replace('_', ' ')} outlook."]

        # Add score interpretation
        if abs(score) > 0.5:
            parts.append(f"Overall sentiment score of {score:.2f} indicates strong directional bias.")
        else:
            parts.append(f"Overall sentiment score of {score:.2f} indicates mixed or neutral sentiment.")

        # Add source-specific insights
        for source in sources:
            source_name = source['source']
            if source_name == 'fear_greed_index':
                parts.append(
                    f"Fear & Greed Index at {source['value']} indicates {source['classification']}."
                )
            elif source_name in ['twitter', 'reddit']:
                parts.append(
                    f"{source_name.capitalize()} activity shows {source['positive_mentions']} positive "
                    f"vs {source['negative_mentions']} negative mentions."
                )

        return " ".join(parts)

    def _get_trading_implication(self, sentiment: Sentiment, confidence: float) -> str:
        """Generate trading implication based on sentiment."""
        if confidence < 0.5:
            return "Low confidence - wait for clearer signals"

        implications = {
            Sentiment.VERY_POSITIVE: "Strong bullish sentiment - consider long positions with tight stops",
            Sentiment.POSITIVE: "Bullish sentiment - favorable for long positions",
            Sentiment.SLIGHTLY_POSITIVE: "Mildly bullish - small long positions or hold current",
            Sentiment.NEUTRAL: "Neutral sentiment - no directional bias, range trading possible",
            Sentiment.SLIGHTLY_NEGATIVE: "Mildly bearish - reduce exposure or small short positions",
            Sentiment.NEGATIVE: "Bearish sentiment - consider short positions or exit longs",
            Sentiment.VERY_NEGATIVE: "Strong bearish sentiment - defensive positioning recommended"
        }

        return implications.get(sentiment, "No clear trading implication")