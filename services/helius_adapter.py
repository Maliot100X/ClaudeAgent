"""Helius API adapter for Solana wallet and NFT data."""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class TokenBalance:
    """Token balance data."""
    token_address: str
    symbol: str
    name: str
    balance: float
    value_usd: float
    price: float
    decimals: int
    logo_url: Optional[str] = None


@dataclass
class Transaction:
    """Transaction data."""
    signature: str
    timestamp: datetime
    type: str  # 'transfer', 'swap', 'nft_sale', etc.
    from_address: str
    to_address: str
    amount: float
    token: str
    fee: float
    status: str


@dataclass
class WalletPortfolio:
    """Complete wallet portfolio."""
    address: str
    sol_balance: float
    sol_value_usd: float
    tokens: List[TokenBalance]
    total_value_usd: float
    token_count: int
    last_updated: datetime


class HeliusAPI:
    """
    Helius API client for Solana data.

    Helius provides the most comprehensive Solana data including:
    - Wallet token balances with USD values
    - Transaction history
    - NFT holdings
    - Token prices

    API Docs: https://docs.helius.xyz/
    """

    BASE_URL = "https://mainnet.helius-rpc.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HELIUS_API_KEY", "")
        if not self.api_key:
            logger.warning("HELIUS_API_KEY not set - wallet tracking will not work")

        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _rpc_call(self, method: str, params: List[Any]) -> Optional[Dict]:
        """Make a Helius RPC call."""
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/?api-key={self.api_key}"

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result")
                else:
                    logger.error(f"Helius RPC error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Helius RPC error: {e}")
            return None

    async def get_wallet_portfolio(self, wallet_address: str) -> Optional[WalletPortfolio]:
        """
        Get complete wallet portfolio including all tokens and values.

        This uses Helius enhanced API to get balances with USD values.
        """
        try:
            # Use the balances endpoint
            session = await self._get_session()
            url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/balances?api-key={self.api_key}"

            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Helius API error: {response.status}")
                    return None

                data = await response.json()

                # Parse SOL balance
                sol_balance = 0.0
                sol_value_usd = 0.0

                if "nativeBalance" in data:
                    sol_balance = data["nativeBalance"] / 1e9  # Convert lamports to SOL

                # Get SOL price for USD value
                sol_price = await self._get_sol_price()
                if sol_price:
                    sol_value_usd = sol_balance * sol_price

                # Parse token balances
                tokens = []
                total_token_value = 0.0

                for token in data.get("tokens", []):
                    try:
                        token_address = token.get("mint", "")
                        balance = token.get("amount", 0)
                        decimals = token.get("decimals", 9)

                        # Calculate actual balance
                        actual_balance = balance / (10 ** decimals) if decimals > 0 else balance

                        # Get token price (if available from token data)
                        price = token.get("price", 0) or 0
                        value_usd = actual_balance * price

                        token_data = TokenBalance(
                            token_address=token_address,
                            symbol=token.get("symbol", "UNKNOWN"),
                            name=token.get("name", "Unknown Token"),
                            balance=actual_balance,
                            value_usd=value_usd,
                            price=price,
                            decimals=decimals,
                            logo_url=token.get("image")
                        )

                        tokens.append(token_data)
                        total_token_value += value_usd

                    except Exception as e:
                        logger.warning(f"Error parsing token: {e}")
                        continue

                # Sort by value (highest first)
                tokens.sort(key=lambda x: x.value_usd, reverse=True)

                return WalletPortfolio(
                    address=wallet_address,
                    sol_balance=sol_balance,
                    sol_value_usd=sol_value_usd,
                    tokens=tokens,
                    total_value_usd=sol_value_usd + total_token_value,
                    token_count=len(tokens),
                    last_updated=datetime.utcnow()
                )

        except Exception as e:
            logger.error(f"Error fetching wallet portfolio: {e}")
            return None

    async def _get_sol_price(self) -> Optional[float]:
        """Get current SOL price."""
        try:
            session = await self._get_session()
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("solana", {}).get("usd")
                return None
        except Exception as e:
            logger.error(f"Error fetching SOL price: {e}")
            return None

    async def get_token_accounts(self, wallet_address: str, token_address: str) -> List[Dict]:
        """Get all token accounts for a specific token in a wallet."""
        result = await self._rpc_call(
            "getTokenAccountsByOwner",
            [
                wallet_address,
                {"mint": token_address},
                {"encoding": "jsonParsed"}
            ]
        )

        if result:
            return result.get("value", [])
        return []

    async def get_transactions(
        self,
        wallet_address: str,
        limit: int = 50,
        before: Optional[str] = None
    ) -> List[Transaction]:
        """
        Get transaction history for a wallet.

        Uses Helius parsed transactions for better data.
        """
        try:
            session = await self._get_session()
            url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions?api-key={self.api_key}"

            params = {"limit": min(limit, 100)}  # Max 100 per request
            if before:
                params["before"] = before

            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                transactions = []

                for tx in data:
                    try:
                        # Parse timestamp
                        ts = tx.get("timestamp", 0)
                        timestamp = datetime.fromtimestamp(ts) if ts else datetime.utcnow()

                        # Determine transaction type
                        tx_type = tx.get("type", "unknown")

                        # Get amount if available
                        amount = 0.0
                        token = "SOL"

                        if tx.get("nativeTransfers"):
                            for transfer in tx["nativeTransfers"]:
                                if transfer.get("fromUserAccount") == wallet_address:
                                    amount = transfer.get("amount", 0) / 1e9
                                    break
                                elif transfer.get("toUserAccount") == wallet_address:
                                    amount = transfer.get("amount", 0) / 1e9
                                    break

                        elif tx.get("tokenTransfers"):
                            for transfer in tx["tokenTransfers"]:
                                if transfer.get("fromUserAccount") == wallet_address:
                                    amount = transfer.get("tokenAmount", 0)
                                    token = transfer.get("mint", "UNKNOWN")
                                    break
                                elif transfer.get("toUserAccount") == wallet_address:
                                    amount = transfer.get("tokenAmount", 0)
                                    token = transfer.get("mint", "UNKNOWN")
                                    break

                        transaction = Transaction(
                            signature=tx.get("signature", ""),
                            timestamp=timestamp,
                            type=tx_type,
                            from_address=tx.get("feePayer", ""),
                            to_address="",
                            amount=amount,
                            token=token,
                            fee=tx.get("fee", 0) / 1e9,
                            status="success" if not tx.get("transactionError") else "failed"
                        )

                        transactions.append(transaction)

                    except Exception as e:
                        logger.warning(f"Error parsing transaction: {e}")
                        continue

                return transactions

        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []

    async def get_nft_holdings(self, wallet_address: str) -> List[Dict]:
        """Get all NFTs held by a wallet."""
        try:
            session = await self._get_session()
            url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/nfts?api-key={self.api_key}"

            async with session.get(url) as response:
                if response.status != 200:
                    return []

                return await response.json()

        except Exception as e:
            logger.error(f"Error fetching NFT holdings: {e}")
            return []

    async def get_wallet_stats(self, wallet_address: str) -> Dict[str, Any]:
        """Get wallet statistics including PnL."""
        try:
            # Get current portfolio
            portfolio = await self.get_wallet_portfolio(wallet_address)
            if not portfolio:
                return {}

            # Get transaction history (for activity)
            transactions = await self.get_transactions(wallet_address, limit=100)

            # Calculate stats
            total_transactions = len(transactions)
            successful_txs = sum(1 for tx in transactions if tx.status == "success")
            failed_txs = total_transactions - successful_txs

            # Get unique tokens traded
            tokens_traded = set()
            for tx in transactions:
                if tx.token:
                    tokens_traded.add(tx.token)

            return {
                "address": wallet_address,
                "total_value_usd": portfolio.total_value_usd,
                "sol_balance": portfolio.sol_balance,
                "token_count": portfolio.token_count,
                "total_transactions_24h": total_transactions,
                "success_rate": (successful_txs / total_transactions * 100) if total_transactions > 0 else 0,
                "unique_tokens_traded": len(tokens_traded),
                "last_updated": portfolio.last_updated.isoformat()
            }

        except Exception as e:
            logger.error(f"Error calculating wallet stats: {e}")
            return {}

    async def subscribe_to_address(
        self,
        wallet_address: str,
        webhook_url: str,
        account_addresses: Optional[List[str]] = None,
        transaction_types: Optional[List[str]] = None
    ) -> bool:
        """
        Subscribe to wallet updates via webhook.

        This sets up real-time notifications for wallet activity.
        """
        try:
            session = await self._get_session()
            url = f"https://api.helius.xyz/v0/webhooks?api-key={self.api_key}"

            payload = {
                "webhookURL": webhook_url,
                "accountAddresses": account_addresses or [wallet_address],
                "transactionTypes": transaction_types or ["ANY"],
                "webhookType": "enhanced"
            }

            async with session.post(url, json=payload) as response:
                if response.status in [200, 201]:
                    logger.info(f"Webhook subscription created for {wallet_address}")
                    return True
                else:
                    logger.error(f"Failed to create webhook: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error subscribing to address: {e}")
            return False


class HeliusWebhookHandler:
    """Handler for Helius webhook events."""

    @staticmethod
    def parse_transaction_event(event_data: Dict) -> Optional[Transaction]:
        """Parse a webhook event into a Transaction object."""
        try:
            signature = event_data.get("signature", "")
            timestamp = datetime.fromtimestamp(event_data.get("timestamp", 0))
            tx_type = event_data.get("type", "unknown")

            # Get SOL transfers
            sol_amount = 0.0
            if event_data.get("nativeTransfers"):
                for transfer in event_data["nativeTransfers"]:
                    sol_amount += transfer.get("amount", 0) / 1e9

            return Transaction(
                signature=signature,
                timestamp=timestamp,
                type=tx_type,
                from_address=event_data.get("feePayer", ""),
                to_address="",
                amount=sol_amount,
                token="SOL",
                fee=event_data.get("fee", 0) / 1e9,
                status="success" if not event_data.get("transactionError") else "failed"
            )
        except Exception as e:
            logger.error(f"Error parsing webhook event: {e}")
            return None
