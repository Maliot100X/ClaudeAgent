"""Wallet tracking skill for monitoring blockchain addresses and transactions."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from agents.base import BaseSkill


class TransactionType(Enum):
    """Types of blockchain transactions."""
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SELF = "self"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


class WalletLabel(Enum):
    """Common wallet labels."""
    EXCHANGE = "exchange"
    WHALE = "whale"
    SMART_MONEY = "smart_money"
    DEVELOPER = "developer"
    CONTRACT = "contract"
    UNKNOWN = "unknown"


@dataclass
class Transaction:
    """Represents a blockchain transaction."""
    tx_hash: str
    timestamp: datetime
    from_address: str
    to_address: str
    value: float
    token: str
    tx_type: TransactionType
    gas_fee: float
    status: str
    block_number: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp.isoformat(),
            "from": self.from_address,
            "to": self.to_address,
            "value": self.value,
            "token": self.token,
            "type": self.tx_type.value,
            "gas_fee": self.gas_fee,
            "status": self.status,
            "block_number": self.block_number
        }


@dataclass
class WalletActivity:
    """Represents wallet activity summary."""
    address: str
    balance: float
    balance_usd: float
    token_balances: Dict[str, float]
    transactions_24h: int
    volume_24h: float
    net_flow_24h: float
    labels: List[str]
    risk_score: float
    last_active: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "balance": self.balance,
            "balance_usd": self.balance_usd,
            "token_balances": self.token_balances,
            "transactions_24h": self.transactions_24h,
            "volume_24h": self.volume_24h,
            "net_flow_24h": self.net_flow_24h,
            "labels": self.labels,
            "risk_score": self.risk_score,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }


class WalletTrackingSkill(BaseSkill):
    """
    Skill for tracking blockchain wallet addresses and transactions.

    Supports:
    - Ethereum (ETH) and ERC-20 tokens
    - Bitcoin (BTC)
    - Solana (SOL)
    - Multi-chain support
    """

    def __init__(
        self,
        etherscan_api_key: Optional[str] = None,
        solscan_api_key: Optional[str] = None,
        blockchain_com_api_key: Optional[str] = None
    ):
        super().__init__(
            name="wallet_tracking",
            description="Track blockchain wallet addresses, balances, and transactions",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get_balance", "get_transactions", "get_activity", "monitor"],
                        "description": "Action to perform"
                    },
                    "address": {
                        "type": "string",
                        "description": "Blockchain address to track"
                    },
                    "blockchain": {
                        "type": "string",
                        "enum": ["ethereum", "bitcoin", "solana", "polygon", "arbitrum", "optimism"],
                        "default": "ethereum"
                    },
                    "token": {
                        "type": "string",
                        "description": "Token symbol or contract address",
                        "default": "native"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of transactions to fetch",
                        "default": 50
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range for analysis",
                        "enum": ["1h", "24h", "7d", "30d"],
                        "default": "24h"
                    }
                },
                "required": ["action", "address"]
            }
        )

        self.etherscan_api_key = etherscan_api_key
        self.solscan_api_key = solscan_api_key
        self.blockchain_com_api_key = blockchain_com_api_key

        # Known exchange addresses (simplified for demo)
        self.known_exchanges = {
            "ethereum": [
                "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE",  # Binance
                "0x267be1C1D684F078cb4F0930fCd70Df39d7700a6",  # Coinbase
                "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",  # Kraken
            ],
            "bitcoin": [
                "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF",  # Old whale
            ]
        }

        # Known whale thresholds by chain
        self.whale_thresholds = {
            "ethereum": 10000,  # 10k ETH
            "bitcoin": 1000,    # 1k BTC
            "solana": 100000,   # 100k SOL
        }

    async def execute(
        self,
        action: str,
        address: str,
        blockchain: str = "ethereum",
        token: str = "native",
        limit: int = 50,
        time_range: str = "24h",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute wallet tracking action.

        Args:
            action: Action to perform
            address: Blockchain address
            blockchain: Blockchain network
            token: Token to check
            limit: Transaction limit
            time_range: Analysis time range

        Returns:
            Wallet data dictionary
        """
        try:
            if action == "get_balance":
                return await self._get_balance(address, blockchain, token)
            elif action == "get_transactions":
                return await self._get_transactions(address, blockchain, limit)
            elif action == "get_activity":
                return await self._get_activity(address, blockchain, time_range)
            elif action == "monitor":
                return await self._monitor_wallet(address, blockchain)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            return {
                "success": False,
                "address": address,
                "blockchain": blockchain,
                "error": str(e)
            }

    async def _get_balance(
        self,
        address: str,
        blockchain: str,
        token: str
    ) -> Dict[str, Any]:
        """Get wallet balance."""
        # In production: call blockchain APIs
        # For demo: simulate data

        if blockchain == "ethereum":
            if token == "native":
                balance = 45.5  # ETH
                balance_usd = balance * 3500  # Assume $3500/ETH
            else:
                # ERC-20 token
                balance = 10000
                balance_usd = balance * 1.5
        elif blockchain == "bitcoin":
            balance = 2.5  # BTC
            balance_usd = balance * 65000
        elif blockchain == "solana":
            balance = 5000  # SOL
            balance_usd = balance * 150
        else:
            balance = 0
            balance_usd = 0

        return {
            "success": True,
            "address": address,
            "blockchain": blockchain,
            "token": token,
            "balance": balance,
            "balance_usd": balance_usd,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _get_transactions(
        self,
        address: str,
        blockchain: str,
        limit: int
    ) -> Dict[str, Any]:
        """Get recent transactions."""
        # In production: fetch from blockchain explorer API
        # For demo: simulate transactions

        transactions = []

        for i in range(min(limit, 10)):  # Demo: max 10 transactions
            tx = Transaction(
                tx_hash=f"0x{''.join([str((hash(f'{address}_{i}') >> j) & 0xF) for j in range(0, 64, 4)])}",
                timestamp=datetime.utcnow() - timedelta(hours=i),
                from_address=address if i % 2 == 0 else f"0x{hash(f'other_{i}'):040x}",
                to_address=f"0x{hash(f'recipient_{i}'):040x}" if i % 2 == 0 else address,
                value=1.5 + (i * 0.5),
                token="ETH" if blockchain == "ethereum" else blockchain.upper(),
                tx_type=TransactionType.OUTGOING if i % 2 == 0 else TransactionType.INCOMING,
                gas_fee=0.002 + (i * 0.001),
                status="confirmed",
                block_number=18000000 + i
            )
            transactions.append(tx.to_dict())

        return {
            "success": True,
            "address": address,
            "blockchain": blockchain,
            "transactions": transactions,
            "count": len(transactions)
        }

    async def _get_activity(
        self,
        address: str,
        blockchain: str,
        time_range: str
    ) -> Dict[str, Any]:
        """Get wallet activity summary."""
        # Convert time range to hours
        hours_map = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}
        hours = hours_map.get(time_range, 24)

        # Get transactions
        tx_data = await self._get_transactions(address, blockchain, 100)
        transactions = tx_data.get("transactions", [])

        # Calculate metrics
        time_threshold = datetime.utcnow() - timedelta(hours=hours)

        recent_txs = [
            tx for tx in transactions
            if datetime.fromisoformat(tx['timestamp']) > time_threshold
        ]

        incoming = sum(tx['value'] for tx in recent_txs if tx['type'] == 'incoming')
        outgoing = sum(tx['value'] for tx in recent_txs if tx['type'] == 'outgoing')

        # Get balance
        balance_data = await self._get_balance(address, blockchain, "native")
        balance = balance_data.get("balance", 0)
        balance_usd = balance_data.get("balance_usd", 0)

        # Determine labels
        labels = self._classify_wallet(address, balance, blockchain)

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            address, transactions, balance, blockchain
        )

        activity = WalletActivity(
            address=address,
            balance=balance,
            balance_usd=balance_usd,
            token_balances={"native": balance},
            transactions_24h=len(recent_txs),
            volume_24h=sum(tx['value'] for tx in recent_txs),
            net_flow_24h=incoming - outgoing,
            labels=labels,
            risk_score=risk_score,
            last_active=datetime.fromisoformat(transactions[0]['timestamp']) if transactions else None
        )

        return {
            "success": True,
            "address": address,
            "blockchain": blockchain,
            "time_range": time_range,
            "activity": activity.to_dict()
        }

    async def _monitor_wallet(
        self,
        address: str,
        blockchain: str
    ) -> Dict[str, Any]:
        """Setup wallet monitoring."""
        # In production: setup webhooks or polling
        return {
            "success": True,
            "address": address,
            "blockchain": blockchain,
            "monitoring_enabled": True,
            "webhook_url": f"/api/webhooks/wallet/{blockchain}/{address}",
            "alerts": [
                "Large transactions (> 100 ETH)",
                "Exchange deposits",
                "Smart contract interactions"
            ]
        }

    def _classify_wallet(
        self,
        address: str,
        balance: float,
        blockchain: str
    ) -> List[str]:
        """Classify wallet based on characteristics."""
        labels = []

        # Check if known exchange
        if address.lower() in [a.lower() for a in self.known_exchanges.get(blockchain, [])]:
            labels.append("exchange")

        # Check whale threshold
        threshold = self.whale_thresholds.get(blockchain, 0)
        if balance >= threshold:
            labels.append("whale")

        # Check smart money indicators
        if balance > threshold * 0.1 and balance < threshold and "exchange" not in labels:
            labels.append("smart_money")

        # Check contract
        if address.startswith("0x") and len(address) == 42:
            # In production: check if address is contract
            pass

        if not labels:
            labels.append("unknown")

        return labels

    def _calculate_risk_score(
        self,
        address: str,
        transactions: List[Dict],
        balance: float,
        blockchain: str
    ) -> float:
        """Calculate wallet risk score (0-100)."""
        score = 0

        # Exchange addresses are low risk for receiving
        if any(a.lower() == address.lower() for a in self.known_exchanges.get(blockchain, [])):
            score -= 20

        # High transaction count
        if len(transactions) > 1000:
            score += 10

        # High balance volatility
        if transactions:
            values = [tx['value'] for tx in transactions[:10]]
            if values:
                avg = sum(values) / len(values)
                variance = sum((v - avg) ** 2 for v in values) / len(values)
                if variance > avg * 10:  # High variance
                    score += 15

        # New wallet (few transactions)
        if len(transactions) < 10 and balance > 0:
            score += 20

        return max(0, min(score, 100))