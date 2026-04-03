"""QuickNode Solana RPC adapter for real-time blockchain operations."""

import os
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import aiohttp
import websockets

logger = logging.getLogger(__name__)


@dataclass
class SolanaAccount:
    """Solana account data."""
    address: str
    lamports: int
    owner: str
    executable: bool
    rent_epoch: int
    data: Any


@dataclass
class TokenAccount:
    """Token account data."""
    address: str
    mint: str
    owner: str
    amount: int
    decimals: int
    ui_amount: float


@dataclass
class TransactionSignature:
    """Transaction signature info."""
    signature: str
    slot: int
    err: Optional[dict]
    memo: Optional[str]
    block_time: Optional[int]


@dataclass
class SlotInfo:
    """Current slot information."""
    slot: int
    parent: int
    root: int
    timestamp: datetime


class QuickNodeAdapter:
    """
    QuickNode Solana RPC adapter.

    Provides high-performance Solana blockchain access via QuickNode RPC:
    - Account balance queries
    - Token account enumeration
    - Transaction history
    - Real-time WebSocket subscriptions
    - Program account monitoring
    """

    def __init__(
        self,
        http_url: Optional[str] = None,
        ws_url: Optional[str] = None
    ):
        self.http_url = http_url or os.getenv("QUICKNODE_HTTP_URL")
        self.ws_url = ws_url or os.getenv("QUICKNODE_WS_URL")

        if not self.http_url:
            logger.warning("QUICKNODE_HTTP_URL not set - QuickNode features disabled")

        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Dict[str, int] = {}
        self.callbacks: Dict[str, Callable] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session

    async def close(self):
        """Close connections."""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.ws_connection:
            await self.ws_connection.close()

    async def _rpc_call(self, method: str, params: List[Any] = None) -> Optional[Dict]:
        """Make a QuickNode RPC call."""
        if not self.http_url:
            return None

        try:
            session = await self._get_session()
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params or []
            }

            async with session.post(self.http_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result")
                else:
                    logger.error(f"QuickNode RPC error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"QuickNode RPC error: {e}")
            return None

    async def get_slot(self) -> Optional[SlotInfo]:
        """Get current Solana slot."""
        result = await self._rpc_call("getSlot")
        if result is not None:
            return SlotInfo(
                slot=result,
                parent=0,  # Would need getBlock for parent
                root=0,
                timestamp=datetime.utcnow()
            )
        return None

    async def get_balance(self, wallet_address: str, commitment: str = "confirmed") -> Optional[int]:
        """Get SOL balance for wallet."""
        result = await self._rpc_call(
            "getBalance",
            [wallet_address, {"commitment": commitment}]
        )
        if result is not None:
            return result.get("value", 0)
        return None

    async def get_token_accounts(
        self,
        wallet_address: str,
        mint: Optional[str] = None,
        program_id: str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    ) -> List[TokenAccount]:
        """Get all token accounts for a wallet."""
        filters = {"programId": program_id}
        if mint:
            filters = {"mint": mint}

        result = await self._rpc_call(
            "getTokenAccountsByOwner",
            [
                wallet_address,
                filters,
                {"encoding": "jsonParsed", "commitment": "confirmed"}
            ]
        )

        if not result:
            return []

        accounts = []
        for acc in result.get("value", []):
            try:
                parsed = acc.get("account", {}).get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                amount = int(info.get("tokenAmount", {}).get("amount", 0))
                decimals = int(info.get("tokenAmount", {}).get("decimals", 0))
                ui_amount = info.get("tokenAmount", {}).get("uiAmount", 0)

                accounts.append(TokenAccount(
                    address=acc.get("pubkey", ""),
                    mint=info.get("mint", ""),
                    owner=info.get("owner", ""),
                    amount=amount,
                    decimals=decimals,
                    ui_amount=ui_amount
                ))
            except Exception as e:
                logger.warning(f"Error parsing token account: {e}")
                continue

        return accounts

    async def get_signatures_for_address(
        self,
        address: str,
        limit: int = 10,
        before: Optional[str] = None,
        until: Optional[str] = None
    ) -> List[TransactionSignature]:
        """Get transaction signatures for an address."""
        params = [address, {"limit": limit}]
        if before:
            params[1]["before"] = before
        if until:
            params[1]["until"] = until

        result = await self._rpc_call("getSignaturesForAddress", params)
        if not result:
            return []

        signatures = []
        for sig in result:
            signatures.append(TransactionSignature(
                signature=sig.get("signature", ""),
                slot=sig.get("slot", 0),
                err=sig.get("err"),
                memo=sig.get("memo"),
                block_time=sig.get("blockTime")
            ))

        return signatures

    async def get_transaction(self, signature: str) -> Optional[Dict]:
        """Get detailed transaction info."""
        return await self._rpc_call(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
        )

    async def get_block_time(self, slot: int) -> Optional[int]:
        """Get timestamp for a slot."""
        return await self._rpc_call("getBlockTime", [slot])

    async def get_latest_blockhash(self, commitment: str = "confirmed") -> Optional[str]:
        """Get latest blockhash for transactions."""
        result = await self._rpc_call(
            "getLatestBlockhash",
            [{"commitment": commitment}]
        )
        if result:
            return result.get("value", {}).get("blockhash")
        return None

    async def is_blockhash_valid(self, blockhash: str) -> bool:
        """Check if a blockhash is still valid."""
        result = await self._rpc_call(
            "isBlockhashValid",
            [blockhash, {"commitment": "processed"}]
        )
        if result is not None:
            return result.get("value", False)
        return False

    async def get_account_info(self, address: str) -> Optional[SolanaAccount]:
        """Get detailed account information."""
        result = await self._rpc_call(
            "getAccountInfo",
            [address, {"encoding": "base64"}]
        )
        if not result or not result.get("value"):
            return None

        value = result["value"]
        return SolanaAccount(
            address=address,
            lamports=value.get("lamports", 0),
            owner=value.get("owner", ""),
            executable=value.get("executable", False),
            rent_epoch=value.get("rentEpoch", 0),
            data=value.get("data")
        )

    async def get_program_accounts(
        self,
        program_id: str,
        filters: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Get all accounts owned by a program."""
        config = {"encoding": "base64", "commitment": "confirmed"}
        if filters:
            config["filters"] = filters

        result = await self._rpc_call("getProgramAccounts", [program_id, config])
        if not result:
            return []

        return result

    async def get_fee_for_message(self, message: str) -> Optional[int]:
        """Estimate fee for a transaction message."""
        result = await self._rpc_call("getFeeForMessage", [message])
        if result:
            return result.get("value")
        return None

    async def send_transaction(
        self,
        signed_transaction: str,
        skip_preflight: bool = False,
        max_retries: int = 0
    ) -> Optional[str]:
        """Send a signed transaction."""
        config = {
            "skipPreflight": skip_preflight,
            "maxRetries": max_retries,
            "encoding": "base64"
        }

        result = await self._rpc_call(
            "sendTransaction",
            [signed_transaction, config]
        )
        if result:
            return result
        return None

    async def simulate_transaction(self, signed_transaction: str) -> Optional[Dict]:
        """Simulate a transaction without sending."""
        result = await self._rpc_call(
            "simulateTransaction",
            [signed_transaction, {"encoding": "base64"}]
        )
        return result

    async def subscribe_account(
        self,
        address: str,
        callback: Callable[[Dict], None],
        commitment: str = "confirmed"
    ) -> bool:
        """Subscribe to account changes via WebSocket."""
        if not self.ws_url:
            logger.error("WebSocket URL not configured")
            return False

        try:
            self.callbacks[address] = callback

            if not self.ws_connection:
                self.ws_connection = await websockets.connect(self.ws_url)
                asyncio.create_task(self._ws_listener())

            subscribe_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "accountSubscribe",
                "params": [address, {"commitment": commitment, "encoding": "jsonParsed"}]
            }

            await self.ws_connection.send(str(subscribe_msg).replace("'", '"'))
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to account {address}: {e}")
            return False

    async def unsubscribe_account(self, address: str) -> bool:
        """Unsubscribe from account changes."""
        if address not in self.subscriptions:
            return False

        try:
            if self.ws_connection:
                unsubscribe_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "accountUnsubscribe",
                    "params": [self.subscriptions[address]]
                }
                await self.ws_connection.send(str(unsubscribe_msg).replace("'", '"'))
                del self.subscriptions[address]
                del self.callbacks[address]
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe from account {address}: {e}")
            return False

    async def _ws_listener(self):
        """Listen for WebSocket messages."""
        while self.ws_connection:
            try:
                message = await self.ws_connection.recv()
                data = eval(message)  # Safe since we control the source

                if "method" in data and data["method"] == "accountNotification":
                    params = data.get("params", {})
                    subscription_id = params.get("subscription")

                    # Find address by subscription ID
                    for addr, sub_id in self.subscriptions.items():
                        if sub_id == subscription_id:
                            if addr in self.callbacks:
                                self.callbacks[addr](params.get("result", {}))
                            break

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

    async def get_multiple_accounts(
        self,
        addresses: List[str],
        encoding: str = "jsonParsed"
    ) -> List[Optional[SolanaAccount]]:
        """Get multiple accounts at once."""
        result = await self._rpc_call(
            "getMultipleAccounts",
            [addresses, {"encoding": encoding}]
        )

        if not result or not result.get("value"):
            return [None] * len(addresses)

        accounts = []
        for i, value in enumerate(result["value"]):
            if value:
                accounts.append(SolanaAccount(
                    address=addresses[i],
                    lamports=value.get("lamports", 0),
                    owner=value.get("owner", ""),
                    executable=value.get("executable", False),
                    rent_epoch=value.get("rentEpoch", 0),
                    data=value.get("data")
                ))
            else:
                accounts.append(None)

        return accounts

    async def get_minimum_balance_for_rent_exemption(
        self,
        data_size: int,
        commitment: str = "confirmed"
    ) -> Optional[int]:
        """Get minimum balance for rent exemption."""
        result = await self._rpc_call(
            "getMinimumBalanceForRentExemption",
            [data_size, {"commitment": commitment}]
        )
        return result

    async def get_inflation_reward(
        self,
        addresses: List[str],
        epoch: Optional[int] = None
    ) -> List[Dict]:
        """Get inflation rewards for addresses."""
        params = [addresses]
        if epoch:
            params.append({"epoch": epoch})

        result = await self._rpc_call("getInflationReward", params)
        if not result:
            return []
        return result

    async def get_cluster_nodes(self) -> List[Dict]:
        """Get information about all cluster nodes."""
        result = await self._rpc_call("getClusterNodes")
        if not result:
            return []
        return result

    async def get_epoch_info(self) -> Optional[Dict]:
        """Get information about current epoch."""
        return await self._rpc_call("getEpochInfo")

    async def get_supply(self) -> Optional[Dict]:
        """Get information about current supply."""
        return await self._rpc_call("getSupply")

    async def get_version(self) -> Optional[Dict]:
        """Get version info for the node."""
        return await self._rpc_call("getVersion")
