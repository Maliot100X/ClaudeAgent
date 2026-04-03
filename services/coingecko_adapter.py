"""CoinGecko market data adapter."""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
import aiohttp

from .market_adapter_base import (
    BaseMarketAdapter,
    MarketPair,
    OHLCV,
    Ticker,
    Trade,
)


class CoinGeckoAdapter(BaseMarketAdapter):
    """
    CoinGecko API adapter for cryptocurrency market data.

    API Docs: https://docs.coingecko.com/
    Rate Limit: 10-30 calls/minute (free), 500 calls/minute (paid)
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            api_key=api_key,
            base_url="https://api.coingecko.com/api/v3",
            rate_limit=10  # Conservative for free tier
        )

        self.coin_map = {}  # Cache for symbol -> coin_id mapping

    @property
    def source_name(self) -> str:
        return "coingecko"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_markets(self) -> List[MarketPair]:
        """Fetch all available coins/markets."""
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/coins/list"
        headers = {}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"CoinGecko API error: {response.status}")

            data = await response.json()

            markets = []
            for coin in data:
                self.coin_map[coin['symbol'].upper()] = coin['id']
                markets.append(MarketPair(
                    symbol=f"{coin['symbol'].upper()}/USD",
                    base_asset=coin['symbol'].upper(),
                    quote_asset="USD",
                    market_type="spot",
                    exchange="coingecko",
                    is_active=True
                ))

            return markets

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Fetch current ticker data."""
        self._rate_limit_check()
        session = await self._get_session()

        coin_id = await self._get_coin_id(symbol)

        url = f"{self.base_url}/coins/{coin_id}"
        params = {"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"}

        headers = {}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key

        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"CoinGecko API error: {response.status}")

            data = await response.json()
            market_data = data.get('market_data', {})

            return Ticker(
                symbol=symbol.upper(),
                price=market_data.get('current_price', {}).get('usd', 0),
                bid=market_data.get('current_price', {}).get('usd', 0) * 0.999,  # Simulated
                ask=market_data.get('current_price', {}).get('usd', 0) * 1.001,  # Simulated
                volume_24h=market_data.get('total_volume', {}).get('usd', 0),
                change_24h=market_data.get('price_change_24h_in_currency', {}).get('usd', 0),
                change_24h_pct=market_data.get('price_change_percentage_24h', 0),
                high_24h=market_data.get('high_24h', {}).get('usd', 0),
                low_24h=market_data.get('low_24h', {}).get('usd', 0),
                timestamp=datetime.utcnow(),
                source="coingecko"
            )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[OHLCV]:
        """Fetch OHLCV data."""
        self._rate_limit_check()
        session = await self._get_session()

        coin_id = await self._get_coin_id(symbol)

        # Map timeframe to days
        days_map = {"1h": 1, "4h": 1, "1d": 30, "1w": 365}
        days = days_map.get(timeframe, 1)

        url = f"{self.base_url}/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": days}

        headers = {}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key

        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"CoinGecko API error: {response.status}")

            data = await response.json()

            ohlcv_list = []
            for candle in data:
                # CoinGecko OHLC format: [timestamp, open, high, low, close]
                ohlcv_list.append(OHLCV(
                    timestamp=datetime.utcfromtimestamp(candle[0] / 1000),
                    open=candle[1],
                    high=candle[2],
                    low=candle[3],
                    close=candle[4],
                    volume=0  # Not provided in this endpoint
                ))

            return ohlcv_list[-limit:] if len(ohlcv_list) > limit else ohlcv_list

    async def fetch_trades(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Trade]:
        """
        CoinGecko doesn't provide individual trades.
        Return empty list - use DexScreener for trade data.
        """
        return []

    async def stream_trades(
        self,
        symbol: str,
        callback: Callable[[Trade], None]
    ) -> None:
        """
        CoinGecko doesn't support real-time trade streaming.
        """
        raise NotImplementedError("CoinGecko does not support real-time trade streaming")

    async def stream_tickers(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None]
    ) -> None:
        """
        CoinGecko doesn't support real-time ticker streaming.
        """
        raise NotImplementedError("CoinGecko does not support real-time ticker streaming")

    async def _get_coin_id(self, symbol: str) -> str:
        """Get CoinGecko coin ID from symbol."""
        # Common symbol mappings
        symbol_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "ADA": "cardano",
            "DOT": "polkadot",
            "AVAX": "avalanche-2",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "AAVE": "aave",
            "DOGE": "dogecoin",
            "SHIB": "shiba-inu",
            "XRP": "ripple",
            "LTC": "litecoin",
            "BCH": "bitcoin-cash",
            "ATOM": "cosmos",
            "ALGO": "algorand",
            "VET": "vechain",
            "FIL": "filecoin",
            "TRX": "tron",
            "ETC": "ethereum-classic",
            "XLM": "stellar",
            "NEAR": "near",
            "APT": "aptos",
            "OP": "optimism",
            "ARB": "arbitrum"
        }

        return symbol_map.get(symbol.upper(), symbol.lower())

    async def fetch_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch comprehensive market data for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Complete market data dictionary
        """
        self._rate_limit_check()
        session = await self._get_session()

        coin_id = await self._get_coin_id(symbol)

        url = f"{self.base_url}/coins/{coin_id}"
        params = {"localization": "false", "tickers": "true", "market_data": "true"}

        headers = {}
        if self.api_key:
            headers["x-cg-pro-api-key"] = self.api_key

        async with session.get(url, params=params, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"CoinGecko API error: {response.status}")

            data = await response.json()
            market_data = data.get('market_data', {})

            return {
                "symbol": symbol.upper(),
                "name": data.get('name'),
                "price": market_data.get('current_price', {}).get('usd'),
                "market_cap": market_data.get('market_cap', {}).get('usd'),
                "volume_24h": market_data.get('total_volume', {}).get('usd'),
                "price_change_24h": market_data.get('price_change_24h'),
                "price_change_percentage_24h": market_data.get('price_change_percentage_24h'),
                "price_change_percentage_7d": market_data.get('price_change_percentage_7d'),
                "price_change_percentage_30d": market_data.get('price_change_percentage_30d'),
                "high_24h": market_data.get('high_24h', {}).get('usd'),
                "low_24h": market_data.get('low_24h', {}).get('usd'),
                "ath": market_data.get('ath', {}).get('usd'),
                "ath_change_percentage": market_data.get('ath_change_percentage', {}).get('usd'),
                "ath_date": market_data.get('ath_date', {}).get('usd'),
                "circulating_supply": market_data.get('circulating_supply'),
                "total_supply": market_data.get('total_supply'),
                "max_supply": market_data.get('max_supply'),
                "last_updated": data.get('last_updated'),
                "source": "coingecko"
            }
