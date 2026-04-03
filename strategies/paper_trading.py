"""Paper trading engine for strategy simulation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"


class PositionSide(Enum):
    """Position sides."""
    LONG = "long"
    SHORT = "short"


class OrderStatus(Enum):
    """Order execution status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    strategy_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.remaining_quantity == 0:
            self.remaining_quantity = self.quantity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "strategy_id": self.strategy_id
        }


@dataclass
class Position:
    """Represents a trading position."""
    position_id: str
    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    realized_pnl: float = 0.0
    entry_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_price(self, current_price: float) -> None:
        """Update position with current price and recalculate PnL."""
        self.current_price = current_price
        self.last_update = datetime.utcnow()

        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
            self.unrealized_pnl_pct = ((current_price / self.entry_price) - 1) * 100
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
            self.unrealized_pnl_pct = ((self.entry_price / current_price) - 1) * 100

    def check_stop_loss(self) -> bool:
        """Check if stop loss should be triggered."""
        if self.stop_loss is None:
            return False

        if self.side == PositionSide.LONG:
            return self.current_price <= self.stop_loss
        else:
            return self.current_price >= self.stop_loss

    def check_take_profit(self) -> bool:
        """Check if take profit should be triggered."""
        if self.take_profit is None:
            return False

        if self.side == PositionSide.LONG:
            return self.current_price >= self.take_profit
        else:
            return self.current_price <= self.take_profit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "entry_time": self.entry_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }


@dataclass
class Trade:
    """Represents a completed trade."""
    trade_id: str
    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    commission: float
    strategy_id: Optional[str] = None
    exit_reason: str = "manual"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "commission": self.commission,
            "strategy_id": self.strategy_id,
            "exit_reason": self.exit_reason
        }


class PaperTradingEngine:
    """
    Paper trading engine for strategy simulation.

    Simulates:
    - Order execution
    - Position tracking
    - PnL calculation
    - Risk management (stop loss, take profit)
    - Trade history
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.001,  # 0.1%
        slippage: float = 0.0005,  # 0.05%
        enable_stop_loss: bool = True,
        enable_take_profit: bool = True
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.enable_stop_loss = enable_stop_loss
        self.enable_take_profit = enable_take_profit

        # Portfolio state
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.equity_history: List[Dict[str, Any]] = []

        # Performance tracking
        self.total_commissions = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    @property
    def total_equity(self) -> float:
        """Calculate total equity (cash + positions)."""
        positions_value = sum(
            pos.unrealized_pnl + (pos.entry_price * pos.quantity)
            for pos in self.positions.values()
        )
        return self.cash + positions_value

    @property
    def total_return(self) -> float:
        """Calculate total return."""
        return self.total_equity - self.initial_capital

    @property
    def total_return_pct(self) -> float:
        """Calculate total return percentage."""
        if self.initial_capital == 0:
            return 0
        return (self.total_return / self.initial_capital) * 100

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0
        return self.winning_trades / self.total_trades

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        strategy_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Order:
        """
        Submit a new order.

        Args:
            symbol: Trading pair symbol
            side: Buy or sell
            order_type: Order type
            quantity: Order quantity
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            strategy_id: ID of strategy submitting order
            metadata: Additional order metadata

        Returns:
            Created order
        """
        order_id = str(uuid.uuid4())

        order = Order(
            order_id=order_id,
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            strategy_id=strategy_id,
            metadata=metadata or {}
        )

        self.orders[order_id] = order

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self.orders.get(order_id)
        if not order:
            return False

        if order.status in [OrderStatus.PENDING, OrderStatus.OPEN]:
            order.status = OrderStatus.CANCELLED
            return True

        return False

    def execute_order(
        self,
        order_id: str,
        execution_price: float,
        filled_quantity: Optional[float] = None
    ) -> bool:
        """
        Execute an order at given price.

        Args:
            order_id: Order to execute
            execution_price: Execution price
            filled_quantity: Amount filled (default: full quantity)

        Returns:
            True if executed successfully
        """
        order = self.orders.get(order_id)
        if not order:
            return False

        if order.status not in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL]:
            return False

        fill_qty = filled_quantity or order.remaining_quantity
        fill_value = fill_qty * execution_price
        commission = fill_value * self.commission_rate

        # Update order
        order.filled_quantity += fill_qty
        order.remaining_quantity -= fill_qty
        order.commission += commission
        order.avg_fill_price = (
            (order.avg_fill_price * (order.filled_quantity - fill_qty) +
             execution_price * fill_qty) / order.filled_quantity
        )

        if order.remaining_quantity <= 0:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow()
        else:
            order.status = OrderStatus.PARTIAL

        # Update portfolio
        self.total_commissions += commission

        if order.side == OrderSide.BUY:
            self._process_buy(order, fill_qty, execution_price, commission)
        else:
            self._process_sell(order, fill_qty, execution_price, commission)

        return True

    def _process_buy(
        self,
        order: Order,
        quantity: float,
        price: float,
        commission: float
    ) -> None:
        """Process a buy execution."""
        cost = quantity * price + commission

        if self.cash < cost:
            # Insufficient funds - reject
            order.status = OrderStatus.REJECTED
            return

        self.cash -= cost
        symbol = order.symbol

        # Update or create position
        if symbol in self.positions:
            pos = self.positions[symbol]
            # Average down/up
            total_qty = pos.quantity + quantity
            pos.entry_price = (
                (pos.entry_price * pos.quantity + price * quantity) / total_qty
            )
            pos.quantity = total_qty
            pos.last_update = datetime.utcnow()
        else:
            # Create new position
            self.positions[symbol] = Position(
                position_id=str(uuid.uuid4()),
                symbol=symbol,
                side=PositionSide.LONG,
                entry_price=price,
                quantity=quantity,
                current_price=price,
                entry_time=datetime.utcnow()
            )

    def _process_sell(
        self,
        order: Order,
        quantity: float,
        price: float,
        commission: float
    ) -> None:
        """Process a sell execution."""
        proceeds = quantity * price - commission
        self.cash += proceeds

        symbol = order.symbol
        position = self.positions.get(symbol)

        if not position:
            # Short selling (not fully implemented in basic version)
            return

        # Calculate realized PnL
        if position.side == PositionSide.LONG:
            entry_value = quantity * position.entry_price
            exit_value = quantity * price
            realized_pnl = exit_value - entry_value - commission

            # Create trade record
            trade = Trade(
                trade_id=str(uuid.uuid4()),
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=quantity,
                entry_price=position.entry_price,
                exit_price=price,
                entry_time=position.entry_time,
                exit_time=datetime.utcnow(),
                pnl=realized_pnl,
                pnl_pct=((price / position.entry_price) - 1) * 100,
                commission=commission,
                strategy_id=order.strategy_id
            )

            self.trades.append(trade)
            self.total_trades += 1

            if realized_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1

            # Update position
            position.quantity -= quantity
            position.realized_pnl += realized_pnl

            if position.quantity <= 0:
                del self.positions[symbol]

    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update position prices and check risk levels.

        Args:
            prices: Dictionary of symbol -> price
        """
        for symbol, position in list(self.positions.items()):
            if symbol in prices:
                position.update_price(prices[symbol])

                # Check stop loss
                if self.enable_stop_loss and position.check_stop_loss():
                    self._trigger_stop_loss(symbol, position)

                # Check take profit
                if self.enable_take_profit and position.check_take_profit():
                    self._trigger_take_profit(symbol, position)

    def _trigger_stop_loss(self, symbol: str, position: Position) -> None:
        """Trigger stop loss for a position."""
        if position.stop_loss:
            order = self.submit_order(
                symbol=symbol,
                side=OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=position.quantity,
                strategy_id="risk_management"
            )

            self.execute_order(order.order_id, position.stop_loss)

            # Mark as stop loss exit
            if self.trades:
                self.trades[-1].exit_reason = "stop_loss"

    def _trigger_take_profit(self, symbol: str, position: Position) -> None:
        """Trigger take profit for a position."""
        if position.take_profit:
            order = self.submit_order(
                symbol=symbol,
                side=OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=position.quantity,
                strategy_id="risk_management"
            )

            self.execute_order(order.order_id, position.take_profit)

            # Mark as take profit exit
            if self.trades:
                self.trades[-1].exit_reason = "take_profit"

    def set_stop_loss(self, symbol: str, stop_price: float) -> bool:
        """Set stop loss for a position."""
        position = self.positions.get(symbol)
        if not position:
            return False

        position.stop_loss = stop_price
        return True

    def set_take_profit(self, symbol: str, take_price: float) -> bool:
        """Set take profit for a position."""
        position = self.positions.get(symbol)
        if not position:
            return False

        position.take_profit = take_price
        return True

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol.upper())

    def get_all_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.positions.values())

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        symbol: Optional[str] = None
    ) -> List[Order]:
        """Get orders, optionally filtered."""
        orders = list(self.orders.values())

        if status:
            orders = [o for o in orders if o.status == status]

        if symbol:
            orders = [o for o in orders if o.symbol == symbol.upper()]

        return orders

    def get_trades(
        self,
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> List[Trade]:
        """Get completed trades."""
        trades = self.trades

        if symbol:
            trades = [t for t in trades if t.symbol == symbol.upper()]

        if strategy_id:
            trades = [t for t in trades if t.strategy_id == strategy_id]

        return trades

    def record_equity(self) -> None:
        """Record current equity value."""
        self.equity_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "equity": self.total_equity,
            "cash": self.cash,
            "positions_value": self.total_equity - self.cash
        })

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        return {
            "initial_capital": self.initial_capital,
            "current_equity": self.total_equity,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "cash": self.cash,
            "positions_value": self.total_equity - self.cash,
            "open_positions": len(self.positions),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_commissions": self.total_commissions,
            "unrealized_pnl": sum(p.unrealized_pnl for p in self.positions.values()),
            "realized_pnl": sum(p.realized_pnl for p in self.positions.values())
        }

    def reset(self) -> None:
        """Reset the engine to initial state."""
        self.cash = self.initial_capital
        self.positions.clear()
        self.orders.clear()
        self.trades.clear()
        self.equity_history.clear()
        self.total_commissions = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
