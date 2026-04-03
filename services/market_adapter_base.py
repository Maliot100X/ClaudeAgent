"""Base market data adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Callable
from enum import Enum


class MarketDataType(Enum):
    """Types of market data."""
    TICKER = "ticker"
    OHLCV = "ohlcv"
    ORDERBOOK = "orderbook"
    TRADE = "trade"
    FUNDING = "funding"
    LIQUIDATION = "liquidation"


@dataclass
class Ticker:
    """Current market ticker data."""
    symbol: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    change_24h: float
    change_24h_pct: float
    high_24h: float
    low_24h: float
    timestamp: datetime
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume_24h": self.volume_24h,
            "change_24h": self.change_24h,
            "change_24h_pct": self.change_24h_pct,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }


@dataclass
class OHLCV:
    """OHLCV candle data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }


@dataclass
class Trade:
    """Individual trade data."""
    trade_id: str
    symbol: str
    price: float
    quantity: float
    side: str  # buy or sell
    timestamp: datetime
    buyer_order_id: Optional[str] = None
    seller_order_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side,
            "timestamp": self.timestamp.isoformat(),
            "buyer_order_id": self.buyer_order_id,
            "seller_order_id": self.seller_order_id
        }


@dataclass
class MarketPair:
    """Trading pair information."""
    symbol: str
    base_asset: str
    quote_asset: str
    market_type: str  # spot, perpetual, margin
    exchange: str
    is_active: bool = True
    min_quantity: float = 0
    max_quantity: float = 0
    quantity_precision: int = 8
    price_precision: int = 8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "market_type": self.market_type,
            "exchange": self.exchange,
            "is_active": self.is_active,
            "min_quantity": self.min_quantity,
            "max_quantity": self.max_quantity,
            "quantity_precision": self.quantity_precision,
            "price_precision": self.price_precision
        }


class BaseMarketAdapter(ABC):
    """Abstract base class for market data adapters."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        rate_limit: int = 10  # requests per second
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limit = rate_limit
        self._session = None
        self._last_request_time = 0
        self._rate_limit_remaining = rate_limit

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the data source name."""
        pass

    @abstractmethod
    async def fetch_markets(self) -> List[MarketPair]:
        """
        Fetch all available trading pairs.

        Returns:
            List of market pairs
        """
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Ticker:
        """
        Fetch current ticker data for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Ticker data
        """
        pass

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[OHLCV]:
        """
        Fetch OHLCV candle data.

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch
            since: Start time for historical data

        Returns:
            List of OHLCV candles
        """
        pass

    @abstractmethod
    async def fetch_trades(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Fetch recent trades.

        Args:
            symbol: Trading pair symbol
            limit: Number of trades to fetch
            since: Start time for historical trades

        Returns:
            List of trades
        """
        pass

    @abstractmethod
    async def stream_trades(
        self,
        symbol: str,
        callback: Callable[[Trade], None]
    ) -> None:
        """
        Stream real-time trades via WebSocket.

        Args:
            symbol: Trading pair symbol
            callback: Function to call for each trade
        """
        pass

    @abstractmethod
    async def stream_tickers(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None]
    ) -> None:
        """
        Stream real-time ticker updates via WebSocket.

        Args:
            symbols: List of trading pair symbols
            callback: Function to call for each ticker update
        """
        pass

    async def close(self) -> None:
        """Close the adapter connection."""
        if self._session:
            await self._session.close()
            self._session = None

    def _rate_limit_check(self) -> None:
        """Check and enforce rate limiting."""
        import time
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < 1.0 / self.rate_limit:
            time.sleep(1.0 / self.rate_limit - time_since_last)

        self._last_request_time = time.time()

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for this exchange.
        Override in subclass if needed.

        Args:
            symbol: Raw symbol

        Returns:
            Normalized symbol
        """
        return symbol.upper()
