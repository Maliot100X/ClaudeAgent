"""DexScreener market data adapter."""

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


class DexScreenerAdapter(BaseMarketAdapter):
    """
    DexScreener API adapter for DEX trading data.

    API Docs: https://docs.dexscreener.com/
    No API key required for basic usage
    Supports real-time WebSocket streaming
    """

    def __init__(self):
        super().__init__(
            api_key=None,
            base_url="https://api.dexscreener.com/latest",
            rate_limit=100  # Very permissive rate limits
        )

    @property
    def source_name(self) -> str:
        return "dexscreener"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_markets(self) -> List[MarketPair]:
        """Fetch all available pairs on DEXs."""
        self._rate_limit_check()
        session = await self._get_session()

        # DexScreener doesn't have a direct "all pairs" endpoint
        # We can get the top trending pairs
        url = "https://api.dexscreener.com/token-profiles/latest/v1"

        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"DexScreener API error: {response.status}")

            data = await response.json()

            markets = []
            # Process profiles - this gives us tokens, not pairs directly
            for profile in data:
                chain = profile.get('chainId', 'unknown')
                token = profile.get('tokenAddress', '')

                markets.append(MarketPair(
                    symbol=f"{token}/{chain}",
                    base_asset=token,
                    quote_asset=chain,
                    market_type="dex",
                    exchange="dexscreener",
                    is_active=True
                ))

            return markets

    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Fetch current ticker for a token."""
        self._rate_limit_check()
        session = await self._get_session()

        # Search for the token
        url = f"{self.base_url}/dex/search"
        params = {"q": symbol}

        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"DexScreener API error: {response.status}")

            data = await response.json()
            pairs = data.get('pairs', [])

            if not pairs:
                raise Exception(f"No pairs found for {symbol}")

            # Get the highest volume pair
            best_pair = max(pairs, key=lambda p: float(p.get('volume', {}).get('h24', 0) or 0))

            price_usd = float(best_pair.get('priceUsd', 0))
            volume_24h = float(best_pair.get('volume', {}).get('h24', 0) or 0)

            # Calculate change if available
            price_change = best_pair.get('priceChange', {})
            change_24h_pct = float(price_change.get('h24', 0)) if price_change else 0

            return Ticker(
                symbol=symbol.upper(),
                price=price_usd,
                bid=price_usd * 0.998,  # Approximate
                ask=price_usd * 1.002,   # Approximate
                volume_24h=volume_24h,
                change_24h=price_usd * (change_24h_pct / 100) if change_24h_pct else 0,
                change_24h_pct=change_24h_pct,
                high_24h=float(best_pair.get('high', {}).get('h24', 0) or price_usd),
                low_24h=float(best_pair.get('low', {}).get('h24', 0) or price_usd),
                timestamp=datetime.utcnow(),
                source="dexscreener"
            )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[OHLCV]:
        """
        OHLCV data is not directly available from DexScreener.
        Use a different provider for historical candles.
        """
        return []

    async def fetch_trades(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Trade]:
        """
        DexScreener doesn't provide individual trade history via REST API.
        Real-time trades are available via WebSocket.
        """
        return []

    async def stream_trades(
        self,
        symbol: str,
        callback: Callable[[Trade], None]

    ) -> None:
        """
        Stream real-time trades via WebSocket.

        DexScreener uses WebSocket for real-time data.
        """
        # WebSocket implementation would go here
        # ws_url = "wss://io.dexscreener.com/dex/screener/v1/pairs"
        raise NotImplementedError("WebSocket streaming requires additional implementation")

    async def stream_tickers(
        self,
        symbols: List[str],
        callback: Callable[[Ticker], None]
    ) -> None:
        """Stream real-time tickers via WebSocket."""
        raise NotImplementedError("WebSocket streaming requires additional implementation")

    async def fetch_pair_data(self, chain: str, pair_address: str) -> Dict[str, Any]:
        """
        Fetch detailed data for a specific pair.

        Args:
            chain: Blockchain chain (e.g., 'solana', 'ethereum')
            pair_address: Pair contract address

        Returns:
            Pair data dictionary
        """
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/dex/pairs/{chain}/{pair_address}"

        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"DexScreener API error: {response.status}")

            return await response.json()

    async def search_pairs(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for trading pairs.

        Args:
            query: Search query (token symbol or address)

        Returns:
            List of matching pairs
        """
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/dex/search"
        params = {"q": query}

        async with session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"DexScreener API error: {response.status}")

            data = await response.json()
            return data.get('pairs', [])

    async def fetch_token_profiles(self) -> List[Dict[str, Any]]:
        """Fetch the latest token profiles (trending tokens)."""
        self._rate_limit_check()
        session = await self._get_session()

        url = "https://api.dexscreener.com/token-profiles/latest/v1"

        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"DexScreener API error: {response.status}")

            return await response.json()

    async def get_new_tokens(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get newly listed tokens from DexScreener.
        """
        self._rate_limit_check()
        session = await self._get_session()

        url = "https://api.dexscreener.com/token-profiles/latest/v1"

        async with session.get(url) as response:
            if response.status != 200:
                return []

            data = await response.json()

            tokens = []
            for profile in data[:limit]:
                tokens.append({
                    "address": profile.get("tokenAddress", ""),
                    "chain": profile.get("chainId", ""),
                    "symbol": profile.get("symbol", "UNKNOWN"),
                    "name": profile.get("name", ""),
                    "description": profile.get("description", ""),
                    "links": profile.get("links", []),
                    "is_new": True,
                    "discovery_source": "dexscreener_latest"
                })

            return tokens

    async def get_boosted_tokens(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get boosted/promoted tokens from DexScreener.
        """
        self._rate_limit_check()
        session = await self._get_session()

        url = "https://api.dexscreener.com/token-boosts/latest/v1"

        async with session.get(url) as response:
            if response.status != 200:
                return []

            data = await response.json()

            boosted = []
            for item in data[:limit]:
                boosted.append({
                    "address": item.get("tokenAddress", ""),
                    "chain": item.get("chainId", ""),
                    "url": item.get("url", ""),
                    "total_amount": item.get("totalAmount", 0),
                    "is_boosted": True,
                    "discovery_source": "dexscreener_boosted"
                })

            return boosted

    async def get_token_pairs(self, chain: str, token_address: str) -> List[Dict[str, Any]]:
        """Get all trading pairs for a specific token."""
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/dex/tokens/{token_address}"

        async with session.get(url) as response:
            if response.status != 200:
                # Try alternative endpoint format
                url = f"https://api.dexscreener.com/token-pairs/v1/{chain}/{token_address}"
                async with session.get(url) as retry_response:
                    if retry_response.status != 200:
                        return []
                    data = await retry_response.json()
                    return data.get("pairs", []) if isinstance(data, dict) else data

            data = await response.json()
            return data.get("pairs", []) if isinstance(data, dict) else data

    async def get_solana_new_pairs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get new trading pairs on Solana specifically."""
        self._rate_limit_check()
        session = await self._get_session()

        url = "https://api.dexscreener.com/token-profiles/latest/v1"

        async with session.get(url) as response:
            if response.status != 200:
                return []

            data = await response.json()

            # Filter for Solana only
            solana_tokens = [
                t for t in data
                if t.get("chainId", "").lower() == "solana"
            ][:limit]

            return solana_tokens

    async def get_top_gainers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top gaining tokens in the last 24 hours."""
        self._rate_limit_check()
        session = await self._get_session()

        url = f"{self.base_url}/dex/trending"

        async with session.get(url) as response:
            if response.status != 200:
                return []

            data = await response.json()
            pairs = data.get("pairs", [])[:limit]

            gainers = []
            for pair in pairs:
                price_change = pair.get("priceChange", {})
                change_24h = float(price_change.get("h24", 0) or 0)

                if change_24h > 0:
                    gainers.append({
                        "address": pair.get("baseToken", {}).get("address", ""),
                        "chain": pair.get("chainId", ""),
                        "symbol": pair.get("baseToken", {}).get("symbol", "UNKNOWN"),
                        "name": pair.get("baseToken", {}).get("name", ""),
                        "price": float(pair.get("priceUsd", 0) or 0),
                        "price_change_24h": change_24h,
                        "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                        "liquidity": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                        "pair_address": pair.get("pairAddress", ""),
                        "dex": pair.get("dexId", ""),
                        "discovery_source": "dexscreener_trending"
                    })

            return sorted(gainers, key=lambda x: x["price_change_24h"], reverse=True)

    async def get_meme_coins(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for popular meme coins on Solana and other chains."""
        meme_keywords = [
            "PEPE", "DOGE", "SHIB", "WOJAK", "BONK", "FLOKI", "MEME",
            "MOON", "ELON", "WOOF", "MEOW", "POPCAT", "MOG"
        ]

        results = []
        seen = set()

        for keyword in meme_keywords[:5]:  # Limit to avoid rate limits
            try:
                pairs = await self.search_pairs(keyword)
                for pair in pairs[:3]:  # Top 3 per keyword
                    symbol = pair.get("baseToken", {}).get("symbol", "")
                    address = pair.get("baseToken", {}).get("address", "")

                    if address and address not in seen:
                        seen.add(address)
                        price_change = pair.get("priceChange", {})

                        results.append({
                            "address": address,
                            "chain": pair.get("chainId", ""),
                            "symbol": symbol,
                            "name": pair.get("baseToken", {}).get("name", ""),
                            "price": float(pair.get("priceUsd", 0) or 0),
                            "price_change_24h": float(price_change.get("h24", 0) or 0),
                            "volume_24h": float(pair.get("volume", {}).get("h24", 0) or 0),
                            "liquidity": float(pair.get("liquidity", {}).get("usd", 0) or 0),
                            "pair_address": pair.get("pairAddress", ""),
                            "discovery_source": "dexscreener_meme_search"
                        })

                if len(results) >= limit:
                    break

            except Exception as e:
                continue

        return results[:limit]

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
