"""Birdeye API integration for Solana token data and wallet tracking."""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class TokenData:
    """Token data structure."""
    address: str
    symbol: str
    name: str
    price: float
    price_change_24h: float
    volume_24h: float
    market_cap: float
    liquidity: float
    decimals: int
    holders: int
    is_verified: bool


@dataclass
class WalletToken:
    """Wallet token holding."""
    token_address: str
    symbol: str
    name: str
    balance: float
    value_usd: float
    price: float
    decimals: int


class BirdeyeAPI:
    """Birdeye API client for Solana data."""

    BASE_URL = "https://public-api.birdeye.so"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BIRDEYE_API_KEY")
        if not self.api_key:
            logger.warning("BIRDEYE_API_KEY not set - Birdeye API will not work")

        self.headers = {
            "X-API-KEY": self.api_key,
            "accept": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_token_price(self, token_address: str) -> Optional[float]:
        """Get current price of a token."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/defi/price"
            params = {"address": token_address}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        return float(data["data"]["value"])
                else:
                    logger.error(f"Birdeye API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching token price: {e}")
            return None

    async def get_token_overview(self, token_address: str) -> Optional[Dict]:
        """Get comprehensive token overview."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/defi/token_overview"
            params = {"address": token_address}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        return data["data"]
                return None
        except Exception as e:
            logger.error(f"Error fetching token overview: {e}")
            return None

    async def get_new_listings(self, limit: int = 20) -> List[TokenData]:
        """Get newly listed tokens - KEY for finding new coins!"""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/defi/v2/tokens/new_listing"
            params = {
                "limit": limit,
                "meme_platform_enabled": "true"
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and "items" in data:
                        tokens = []
                        for item in data["items"]:
                            token = TokenData(
                                address=item.get("address", ""),
                                symbol=item.get("symbol", "UNKNOWN"),
                                name=item.get("name", ""),
                                price=float(item.get("price", 0) or 0),
                                price_change_24h=float(item.get("price_change_24h", 0) or 0),
                                volume_24h=float(item.get("volume_24h", 0) or 0),
                                market_cap=float(item.get("market_cap", 0) or 0),
                                liquidity=float(item.get("liquidity", 0) or 0),
                                decimals=item.get("decimals", 9),
                                holders=item.get("holders", 0),
                                is_verified=item.get("verified", False)
                            )
                            tokens.append(token)
                        return tokens
                return []
        except Exception as e:
            logger.error(f"Error fetching new listings: {e}")
            return []

    async def get_trending_tokens(self, limit: int = 20) -> List[TokenData]:
        """Get trending/meme tokens."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/defi/token_trending"
            params = {"limit": limit, "sort_by": "volume_24h"}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        tokens = []
                        for item in data.get("data", []):
                            token = TokenData(
                                address=item.get("address", ""),
                                symbol=item.get("symbol", "UNKNOWN"),
                                name=item.get("name", ""),
                                price=float(item.get("price", 0) or 0),
                                price_change_24h=float(item.get("price_change_24h", 0) or 0),
                                volume_24h=float(item.get("volume_24h", 0) or 0),
                                market_cap=float(item.get("market_cap", 0) or 0),
                                liquidity=float(item.get("liquidity", 0) or 0),
                                decimals=item.get("decimals", 9),
                                holders=item.get("holders", 0),
                                is_verified=item.get("verified", False)
                            )
                            tokens.append(token)
                        return tokens
                return []
        except Exception as e:
            logger.error(f"Error fetching trending tokens: {e}")
            return []

    async def get_wallet_tokens(self, wallet_address: str) -> List[WalletToken]:
        """Get all tokens in a wallet with their values."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/wallet/v2/current-net-worth"
            params = {"wallet": wallet_address}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        tokens = []
                        for item in data.get("data", {}).get("items", []):
                            token = WalletToken(
                                token_address=item.get("address", ""),
                                symbol=item.get("symbol", "UNKNOWN"),
                                name=item.get("name", ""),
                                balance=float(item.get("balance", 0) or 0),
                                value_usd=float(item.get("valueUsd", 0) or 0),
                                price=float(item.get("priceUsd", 0) or 0),
                                decimals=item.get("decimals", 9)
                            )
                            tokens.append(token)
                        return tokens
                return []
        except Exception as e:
            logger.error(f"Error fetching wallet tokens: {e}")
            return []

    async def get_wallet_pnl(self, wallet_address: str) -> Optional[Dict]:
        """Get wallet P&L summary."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/wallet/v2/pnl-summary"
            params = {"wallet": wallet_address}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        return data["data"]
                return None
        except Exception as e:
            logger.error(f"Error fetching wallet PnL: {e}")
            return None

    async def get_meme_coins(self) -> List[TokenData]:
        """Get meme coins specifically."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/defi/v3/token/meme/list"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        tokens = []
                        for item in data.get("data", []):
                            token = TokenData(
                                address=item.get("address", ""),
                                symbol=item.get("symbol", "UNKNOWN"),
                                name=item.get("name", ""),
                                price=float(item.get("price", 0) or 0),
                                price_change_24h=float(item.get("price_change_24h", 0) or 0),
                                volume_24h=float(item.get("volume_24h", 0) or 0),
                                market_cap=float(item.get("market_cap", 0) or 0),
                                liquidity=float(item.get("liquidity", 0) or 0),
                                decimals=item.get("decimals", 9),
                                holders=item.get("holders", 0),
                                is_verified=item.get("verified", False)
                            )
                            tokens.append(token)
                        return tokens
                return []
        except Exception as e:
            logger.error(f"Error fetching meme coins: {e}")
            return []

    async def get_token_security(self, token_address: str) -> Optional[Dict]:
        """Get token security analysis (rugpull risk, etc)."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/defi/token_security"
            params = {"address": token_address}

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        return data["data"]
                return None
        except Exception as e:
            logger.error(f"Error fetching token security: {e}")
            return None
