"""Wallet management API routes."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallets", tags=["wallets"])


# In-memory storage for now (should use database in production)
# Structure: {address: {"name": str, "chain": str, "added_at": datetime}}
tracked_wallets = {}


class WalletCreate(BaseModel):
    address: str
    name: Optional[str] = "Unnamed"
    chain: Optional[str] = "solana"


class WalletResponse(BaseModel):
    address: str
    name: str
    chain: str
    total_value_usd: float = 0.0
    sol_balance: float = 0.0
    token_count: int = 0
    added_at: str


class TokenInfo(BaseModel):
    token_address: str
    symbol: str
    name: str
    balance: float
    price: float
    value_usd: float
    decimals: int


class WalletPnL(BaseModel):
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_rate: float
    total_trades: int
    winning_trades: int


@router.get("", response_model=dict)
async def get_wallets():
    """Get all tracked wallets with basic info."""
    wallets = []

    for address, data in tracked_wallets.items():
        # Fetch current portfolio data
        portfolio = await _fetch_wallet_portfolio(address)

        wallet_info = {
            "address": address,
            "name": data.get("name", "Unnamed"),
            "chain": data.get("chain", "solana"),
            "total_value_usd": portfolio.get("total_value_usd", 0),
            "sol_balance": portfolio.get("sol_balance", 0),
            "token_count": portfolio.get("token_count", 0),
            "added_at": data.get("added_at", datetime.utcnow().isoformat())
        }
        wallets.append(wallet_info)

    return {"wallets": wallets}


@router.post("")
async def add_wallet(wallet: WalletCreate):
    """Add a wallet to tracking."""
    address = wallet.address.strip()

    if not address or len(address) < 20:
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    if address in tracked_wallets:
        raise HTTPException(status_code=400, detail="Wallet already tracked")

    tracked_wallets[address] = {
        "name": wallet.name or "Unnamed",
        "chain": wallet.chain or "solana",
        "added_at": datetime.utcnow().isoformat()
    }

    logger.info(f"Added wallet {address[:12]}... for tracking")

    return {
        "success": True,
        "message": f"Wallet {address[:12]}... added successfully",
        "wallet": {
            "address": address,
            "name": wallet.name,
            "chain": wallet.chain
        }
    }


@router.delete("/{address}")
async def remove_wallet(address: str):
    """Remove a wallet from tracking."""
    if address not in tracked_wallets:
        raise HTTPException(status_code=404, detail="Wallet not found")

    del tracked_wallets[address]
    logger.info(f"Removed wallet {address[:12]}... from tracking")

    return {
        "success": True,
        "message": f"Wallet {address[:12]}... removed successfully"
    }


@router.get("/{address}/portfolio")
async def get_wallet_portfolio(address: str):
    """Get wallet portfolio with token balances."""
    portfolio = await _fetch_wallet_portfolio(address)
    return {"portfolio": portfolio}


@router.get("/{address}/tokens")
async def get_wallet_tokens(address: str):
    """Get all tokens in a wallet."""
    tokens = await _fetch_wallet_tokens(address)
    return {"tokens": tokens}


@router.get("/{address}/pnl")
async def get_wallet_pnl(address: str):
    """Get wallet P&L (requires historical data)."""
    # This would need historical data - simplified version
    pnl = await _calculate_wallet_pnl(address)
    return {"pnl": pnl}


async def _fetch_wallet_portfolio(address: str) -> dict:
    """Fetch wallet portfolio from Helius or Birdeye."""
    try:
        import aiohttp

        # Try Helius first
        helius_key = os.getenv("HELIUS_API_KEY", "")
        if helius_key:
            url = f"https://api.helius.xyz/v0/addresses/{address}/balances?api-key={helius_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Parse response
                        sol_balance = 0.0
                        if "nativeBalance" in data:
                            sol_balance = data["nativeBalance"] / 1e9

                        # Get SOL price
                        sol_price = await _get_sol_price()
                        sol_value = sol_balance * sol_price if sol_price else 0

                        # Count tokens with value
                        token_count = 0
                        total_token_value = 0.0

                        for token in data.get("tokens", []):
                            balance = token.get("amount", 0)
                            decimals = token.get("decimals", 9)
                            price = token.get("price", 0) or 0

                            actual_balance = balance / (10 ** decimals) if decimals > 0 else balance
                            value = actual_balance * price

                            if value > 0.01:  # Only count tokens with value
                                token_count += 1
                                total_token_value += value

                        return {
                            "address": address,
                            "total_value_usd": sol_value + total_token_value,
                            "sol_balance": sol_balance,
                            "sol_value_usd": sol_value,
                            "token_count": token_count,
                            "token_value_usd": total_token_value,
                            "last_updated": datetime.utcnow().isoformat()
                        }

        # Fallback: Try Birdeye
        birdeye_key = os.getenv("BIRDEYE_API_KEY", "")
        if birdeye_key:
            url = f"https://public-api.birdeye.so/wallet/v2/current-net-worth?wallet={address}"
            headers = {"X-API-KEY": birdeye_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success") and "data" in data:
                            items = data["data"].get("items", [])
                            total_value = sum(float(item.get("valueUsd", 0) or 0) for item in items)

                            return {
                                "address": address,
                                "total_value_usd": total_value,
                                "sol_balance": 0,  # Would need separate call
                                "sol_value_usd": 0,
                                "token_count": len(items),
                                "token_value_usd": total_value,
                                "last_updated": datetime.utcnow().isoformat()
                            }

        # Return empty portfolio if no data source available
        return {
            "address": address,
            "total_value_usd": 0,
            "sol_balance": 0,
            "sol_value_usd": 0,
            "token_count": 0,
            "token_value_usd": 0,
            "last_updated": datetime.utcnow().isoformat(),
            "note": "No API key configured for wallet data"
        }

    except Exception as e:
        logger.error(f"Error fetching wallet portfolio: {e}")
        return {
            "address": address,
            "total_value_usd": 0,
            "sol_balance": 0,
            "sol_value_usd": 0,
            "token_count": 0,
            "token_value_usd": 0,
            "error": str(e),
            "last_updated": datetime.utcnow().isoformat()
        }


async def _fetch_wallet_tokens(address: str) -> list:
    """Fetch all tokens in a wallet."""
    try:
        import aiohttp

        # Try Helius
        helius_key = os.getenv("HELIUS_API_KEY", "")
        if helius_key:
            url = f"https://api.helius.xyz/v0/addresses/{address}/balances?api-key={helius_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tokens = []

                        for token in data.get("tokens", []):
                            balance = token.get("amount", 0)
                            decimals = token.get("decimals", 9)
                            price = token.get("price", 0) or 0

                            actual_balance = balance / (10 ** decimals) if decimals > 0 else balance
                            value = actual_balance * price

                            if value > 0.001:  # Include low value tokens too
                                tokens.append({
                                    "token_address": token.get("mint", ""),
                                    "symbol": token.get("symbol", "UNKNOWN"),
                                    "name": token.get("name", "Unknown"),
                                    "balance": actual_balance,
                                    "price": price,
                                    "value_usd": value,
                                    "decimals": decimals,
                                    "logo_url": token.get("image")
                                })

                        # Sort by value
                        tokens.sort(key=lambda x: x["value_usd"], reverse=True)
                        return tokens

        # Fallback: Try Birdeye
        birdeye_key = os.getenv("BIRDEYE_API_KEY", "")
        if birdeye_key:
            url = f"https://public-api.birdeye.so/wallet/v2/current-net-worth?wallet={address}"
            headers = {"X-API-KEY": birdeye_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success") and "data" in data:
                            items = data["data"].get("items", [])
                            tokens = []

                            for item in items:
                                balance = float(item.get("balance", 0) or 0)
                                price = float(item.get("priceUsd", 0) or 0)
                                value = float(item.get("valueUsd", 0) or 0)

                                if value > 0.001:
                                    tokens.append({
                                        "token_address": item.get("address", ""),
                                        "symbol": item.get("symbol", "UNKNOWN"),
                                        "name": item.get("name", "Unknown"),
                                        "balance": balance,
                                        "price": price,
                                        "value_usd": value,
                                        "decimals": item.get("decimals", 9)
                                    })

                            tokens.sort(key=lambda x: x["value_usd"], reverse=True)
                            return tokens

        return []

    except Exception as e:
        logger.error(f"Error fetching wallet tokens: {e}")
        return []


async def _get_sol_price() -> Optional[float]:
    """Get current SOL price from CoinGecko."""
    try:
        import aiohttp

        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("solana", {}).get("usd")
        return None
    except Exception as e:
        logger.error(f"Error fetching SOL price: {e}")
        return None


async def _calculate_wallet_pnl(address: str) -> dict:
    """
    Calculate wallet P&L.
    This is simplified - real implementation would need transaction history.
    """
    try:
        # Try to get transactions and calculate P&L
        # This is a placeholder - real implementation would analyze trade history

        return {
            "total_pnl": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "note": "PnL calculation requires historical transaction data"
        }

    except Exception as e:
        logger.error(f"Error calculating P&L: {e}")
        return {
            "total_pnl": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "error": str(e)
        }
