"""Market data skill for fetching cryptocurrency prices and market information."""

from typing import Any, Dict, List, Optional
import aiohttp

from agents.base import BaseSkill


class MarketDataSkill(BaseSkill):
    """
    Skill for fetching cryptocurrency market data.

    Supports multiple data providers:
    - CoinGecko
    - DexScreener
    - CryptoCompare
    """

    def __init__(
        self,
        coingecko_api_key: Optional[str] = None,
        cryptocompare_api_key: Optional[str] = None,
        default_provider: str = "coingecko"
    ):
        super().__init__(
            name="market_data",
            description="Fetch cryptocurrency market data including prices, volume, and market cap",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Cryptocurrency symbol (e.g., BTC, ETH, SOL)"
                    },
                    "currency": {
                        "type": "string",
                        "description": "Quote currency (e.g., USD, EUR)",
                        "default": "usd"
                    },
                    "provider": {
                        "type": "string",
                        "description": "Data provider to use",
                        "enum": ["coingecko", "dexscreener", "cryptocompare"],
                        "default": default_provider
                    },
                    "include_market_data": {
                        "type": "boolean",
                        "description": "Include market cap, volume, etc.",
                        "default": True
                    }
                },
                "required": ["symbol"]
            }
        )

        self.coingecko_api_key = coingecko_api_key
        self.cryptocompare_api_key = cryptocompare_api_key
        self.default_provider = default_provider
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def execute(
        self,
        symbol: str,
        currency: str = "usd",
        provider: Optional[str] = None,
        include_market_data: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute market data fetch.

        Args:
            symbol: Cryptocurrency symbol (BTC, ETH, etc.)
            currency: Quote currency
            provider: Data provider override
            include_market_data: Include additional market metrics

        Returns:
            Market data dictionary
        """
        provider = provider or self.default_provider

        try:
            if provider == "coingecko":
                data = await self._fetch_coingecko(symbol, currency, include_market_data)
            elif provider == "dexscreener":
                data = await self._fetch_dexscreener(symbol, currency)
            elif provider == "cryptocompare":
                data = await self._fetch_cryptocompare(symbol, currency)
            else:
                raise ValueError(f"Unknown provider: {provider}")

            return {
                "success": True,
                "symbol": symbol,
                "currency": currency,
                "provider": provider,
                "data": data,
                "timestamp": data.get("timestamp")
            }

        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "error": str(e),
                "provider": provider
            }

    async def _fetch_coingecko(
        self,
        symbol: str,
        currency: str,
        include_market_data: bool
    ) -> Dict[str, Any]:
        """Fetch data from CoinGecko."""
        session = await self._get_session()

        # Map common symbols to CoinGecko IDs
        coin_map = {
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
            "TRX": "tron"
        }

        coin_id = coin_map.get(symbol.upper(), symbol.lower())

        headers = {}
        if self.coingecko_api_key:
            headers["x-cg-pro-api-key"] = self.coingecko_api_key

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"CoinGecko API error: {response.status}")

            data = await response.json()

            market_data = data.get("market_data", {})
            prices = market_data.get("current_price", {})
            price = prices.get(currency.lower(), 0)

            result = {
                "price": price,
                "symbol": symbol.upper(),
                "name": data.get("name"),
                "timestamp": data.get("last_updated")
            }

            if include_market_data:
                result.update({
                    "market_cap": market_data.get("market_cap", {}).get(currency.lower()),
                    "volume_24h": market_data.get("total_volume", {}).get(currency.lower()),
                    "price_change_24h": market_data.get("price_change_24h"),
                    "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
                    "high_24h": market_data.get("high_24h", {}).get(currency.lower()),
                    "low_24h": market_data.get("low_24h", {}).get(currency.lower()),
                    "circulating_supply": market_data.get("circulating_supply"),
                    "total_supply": market_data.get("total_supply"),
                    "max_supply": market_data.get("max_supply"),
                    "ath": market_data.get("ath", {}).get(currency.lower()),
                    "ath_change_percentage": market_data.get("ath_change_percentage", {}).get(currency.lower()),
                })

            return result

    async def _fetch_dexscreener(
        self,
        symbol: str,
        currency: str
    ) -> Dict[str, Any]:
        """Fetch data from DexScreener."""
        session = await self._get_session()

        # DexScreener uses pairs
        url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"

        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"DexScreener API error: {response.status}")

            data = await response.json()
            pairs = data.get("pairs", [])

            if not pairs:
                raise Exception(f"No pairs found for {symbol}")

            # Get the highest volume pair
            best_pair = max(pairs, key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0))

            return {
                "price": float(best_pair.get("priceUsd", 0)),
                "symbol": symbol.upper(),
                "dex": best_pair.get("dexId"),
                "pair": best_pair.get("pairAddress"),
                "volume_24h": float(best_pair.get("volume", {}).get("h24", 0) or 0),
                "liquidity": best_pair.get("liquidity", {}).get("usd"),
                "price_change_24h": best_pair.get("priceChange", {}).get("h24"),
                "timestamp": best_pair.get("updatedAt")
            }

    async def _fetch_cryptocompare(
        self,
        symbol: str,
        currency: str
    ) -> Dict[str, Any]:
        """Fetch data from CryptoCompare."""
        session = await self._get_session()

        headers = {}
        if self.cryptocompare_api_key:
            headers["authorization"] = f"Apikey {self.cryptocompare_api_key}"

        # Get price and full data
        fsym = symbol.upper()
        tsym = currency.upper()

        url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={fsym}&tsyms={tsym}"

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"CryptoCompare API error: {response.status}")

            data = await response.json()

            raw = data.get("RAW", {}).get(fsym, {}).get(tsym, {})
            display = data.get("DISPLAY", {}).get(fsym, {}).get(tsym, {})

            return {
                "price": raw.get("PRICE", 0),
                "symbol": symbol.upper(),
                "currency": currency.upper(),
                "market_cap": raw.get("MKTCAP"),
                "volume_24h": raw.get("TOTALVOLUME24H"),
                "volume_24h_to": raw.get("TOTALVOLUME24HTO"),
                "high_24h": raw.get("HIGH24HOUR"),
                "low_24h": raw.get("LOW24HOUR"),
                "open_24h": raw.get("OPEN24HOUR"),
                "price_change_24h": raw.get("CHANGE24HOUR"),
                "price_change_percentage_24h": raw.get("CHANGEPCT24HOUR"),
                "supply": raw.get("SUPPLY"),
                "timestamp": raw.get("LASTUPDATE")
            }

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
