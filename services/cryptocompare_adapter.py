"""CryptoCompare market data adapter."""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import aiohttp

from .market_adapter_base import (
    BaseMarketAdapter,
    MarketPair,
    OHLCV,
    Ticker,
    Trade,
)


class CryptoCompareAdapter(BaseMarketAdapter):
    """
    CryptoCompare API adapter for cryptocurrency market data.

    API Docs: https://min-api.cryptocompare.com/documentation
    Rate Limit: Varies by tier (free: ~100k calls/month)
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            api_key=api_key,
            base_url="https://min-api.cryptocompare.com/data",
            rate_limit=20  # Conservative
        )

    @property
    def source_name(self) -> str:
        return "cryptocompare"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with API key."""
        headers = {}
        if self.api_key:
            headers["authorization"] = f"Apikey {self.api_key}"
        return headers

    async def fetch_markets(self) -> List[MarketPair]:
        """Fetch all available trading pairs."""
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/blockchain/list"

        async with session.get(url, headers=self._get_headers()) as response:
            if response.status != 200:
                raise Exception(f"CryptoCompare API error: {response.status}")

            data = await response.json()

            markets = []
            for symbol, info in data.get('Data', {}).items():
                markets.append(MarketPair(
                    symbol=f"{symbol}/USD",
                    base_asset=symbol,
                    quote_asset="USD",
                    market_type="spot",
                    exchange="cryptocompare",
                    is_active=info.get('partner_acquired', False)
                ))

            return markets

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Fetch current ticker data."""
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/pricemultifull"
        params = {
            "fsyms": symbol.upper(),
            "tsyms": "USD"
        }

        async with session.get(url, params=params, headers=self._get_headers()) as response:
            if response.status != 200:
                raise Exception(f"CryptoCompare API error: {response.status}")

            data = await response.json()
            raw = data.get('RAW', {}).get(symbol.upper(), {}).get('USD', {})

            return Ticker(
                symbol=symbol.upper(),
                price=raw.get('PRICE', 0),
                bid=raw.get('PRICE', 0) * 0.9995,  # Approximate
                ask=raw.get('PRICE', 0) * 1.0005,   # Approximate
                volume_24h=raw.get('VOLUME24HOURTO', 0),
                change_24h=raw.get('CHANGE24HOUR', 0),
                change_24h_pct=raw.get('CHANGEPCT24HOUR', 0),
                high_24h=raw.get('HIGH24HOUR', 0),
                low_24h=raw.get('LOW24HOUR', 0),
                timestamp=datetime.utcnow(),
                source="cryptocompare"
            )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[OHLCV]:
        """Fetch OHLCV candle data."""
        self._rate_limit_check()
        session = await self._get_session()

        # Map timeframe to CryptoCompare format
        tf_map = {
            "1m": "histominute",
            "5m": "histominute",
            "15m": "histominute",
            "30m": "histominute",
            "1h": "histohour",
            "4h": "histohour",
            "1d": "histoday"
        }

        endpoint = tf_map.get(timeframe, "histohour")
        aggregate = self._get_aggregate(timeframe)

        url = f"{self.base_url}/v2/{endpoint}"
        params = {
            "fsym": symbol.upper(),
            "tsym": "USD",
            "limit": limit,
            "aggregate": aggregate
        }

        if since:
            params["toTs"] = int(since.timestamp())

        async with session.get(url, params=params, headers=self._get_headers()) as response:
            if response.status != 200:
                raise Exception(f"CryptoCompare API error: {response.status}")

            data = await response.json()

            ohlcv_list = []
            for candle in data.get('Data', {}).get('Data', []):
                ohlcv_list.append(OHLCV(
                    timestamp=datetime.utcfromtimestamp(candle['time']),
                    open=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    volume=candle['volumefrom']
                ))

            return ohlcv_list

    def _get_aggregate(self, timeframe: str) -> int:
        """Get aggregate multiplier for timeframe."""
        aggregate_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 1,
            "4h": 4,
            "1d": 1
        }
        return aggregate_map.get(timeframe, 1)

    async def fetch_trades(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Trade]:
        """
        CryptoCompare provides trade data through a separate endpoint.
        Limited to recent trades.
        """
        self._rate_limit_check()
        session = await self._get_session()

        # This endpoint is for exchange-specific trades
        # For general market, we return empty list
        return []

    async def stream_trades(
        self,
        symbol: str,
        callback: Callable[[Trade], None]
    ) -> None:
        """
        CryptoCompare supports WebSocket streaming via their streamer API.
        """
        raise NotImplementedError("WebSocket streaming requires separate implementation")

    async def stream_tickers(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None]
    ) -> None:
        """Stream real-time tickers via WebSocket."""
        raise NotImplementedError("WebSocket streaming requires separate implementation")

    async def fetch_top_pairs(
        self,
        limit: int = 100,
        to_symbol: str = "USD"
    ) -> List[Dict[str, Any]]:
        """
        Fetch top trading pairs by volume.

        Args:
            limit: Number of pairs to fetch
            to_symbol: Quote currency

        Returns:
            List of top pairs with volume data
        """
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/top/totalvolfull"
        params = {"limit": limit, "tsym": to_symbol}

        async with session.get(url, params=params, headers=self._get_headers()) as response:
            if response.status != 200:
                raise Exception(f"CryptoCompare API error: {response.status}")

            data = await response.json()
            return data.get('Data', [])

    async def fetch_news(
        self,
        categories: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest cryptocurrency news.

        Args:
            categories: News categories to filter
            limit: Number of articles

        Returns:
            List of news articles
        """
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/v2/news/?lang=EN"

        if categories:
            url += f"&categories={','.join(categories)}"

        async with session.get(url, headers=self._get_headers()) as response:
            if response.status != 200:
                raise Exception(f"CryptoCompare API error: {response.status}")

            data = await response.json()
            return data.get('Data', [])[:limit]
