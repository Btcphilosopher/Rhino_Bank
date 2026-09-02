# RHINOBANK COPPER SPOT MARKET — PYTHON CORE

```python
"""
RHINOBANK COPPER SPOT MARKET
============================

Institutional-style prototype for a physical/financial copper spot market.

Core components:
    - Limit order book
    - Continuous price/time matching
    - Market orders
    - Limit orders
    - Account balances
    - Copper inventory
    - Cash settlement
    - Trading fees
    - Position/P&L tracking
    - Market data
    - Risk limits
    - Trade tape
    - VWAP
    - Mid-price
    - Order cancellation

NOT production financial infrastructure.
For production use, add:
    - persistent database
    - FIX/API gateway
    - authentication
    - cryptographic audit trail
    - double-entry ledger
    - KYC/AML
    - regulatory controls
    - hardware/security controls
    - exchange connectivity
    - disaster recovery
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from enum import Enum
from collections import defaultdict, deque
from typing import Dict, List, Optional
import heapq
import itertools
import time
import uuid


# ============================================================
# PRECISION
# ============================================================

getcontext().prec = 28

D = Decimal


# ============================================================
# MARKET CONFIGURATION
# ============================================================

COPPER_SYMBOL = "CU-SPOT"
CURRENCY = "USD"

# One contract/order unit = one metric tonne
UNIT = "MT"

# Example fee: 5 basis points
TRADING_FEE_BPS = D("0.0005")

# Risk limits
MAX_ORDER_NOTIONAL = D("10_000_000")
MAX_POSITION_MT = D("5_000")


# ============================================================
# ENUMS
# ============================================================

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


# ============================================================
# ORDER
# ============================================================

@dataclass
class Order:
    trader_id: str
    side: Side
    quantity: Decimal
    order_type: OrderType
    price: Optional[Decimal] = None

    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_ns: int = field(default_factory=time.time_ns)

    remaining: Decimal = field(init=False)
    filled: Decimal = field(default=D("0"))
    status: OrderStatus = field(default=OrderStatus.NEW)

    def __post_init__(self):
        self.quantity = D(self.quantity)
        self.remaining = self.quantity

        if self.price is not None:
            self.price = D(self.price)

    def fill(self, quantity: Decimal):
        quantity = D(quantity)

        self.remaining -= quantity
        self.filled += quantity

        if self.remaining <= 0:
            self.remaining = D("0")
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED


# ============================================================
# TRADE
# ============================================================

@dataclass
class Trade:
    trade_id: str
    symbol: str

    buyer: str
    seller: str

    price: Decimal
    quantity: Decimal

    timestamp_ns: int

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


# ============================================================
# ACCOUNT
# ============================================================

@dataclass
class Account:
    trader_id: str

    cash_usd: Decimal = D("0")
    copper_mt: Decimal = D("0")

    realized_pnl: Decimal = D("0")
    fees_paid: Decimal = D("0")

    def deposit_cash(self, amount):
        self.cash_usd += D(amount)

    def deposit_copper(self, amount):
        self.copper_mt += D(amount)


# ============================================================
# PRICE LEVEL
# ============================================================

@dataclass
class PriceLevel:
    price: Decimal

    # FIFO queue
    orders: deque = field(default_factory=deque)


# ============================================================
# ORDER BOOK
# ============================================================

class OrderBook:

    def __init__(self):
        self.bids: Dict[Decimal, PriceLevel] = {}
        self.asks: Dict[Decimal, PriceLevel] = {}

    # --------------------------------------------------------
    # ADD
    # --------------------------------------------------------

    def add(self, order: Order):

        if order.order_type != OrderType.LIMIT:
            raise ValueError("Only limit orders can rest in the book.")

        book = self.bids if order.side == Side.BUY else self.asks

        if order.price not in book:
            book[order.price] = PriceLevel(order.price)

        book[order.price].orders.append(order)

    # --------------------------------------------------------
    # REMOVE
    # --------------------------------------------------------

    def remove(self, order: Order):

        book = self.bids if order.side == Side.BUY else self.asks

        level = book.get(order.price)

        if not level:
            return

        try:
            level.orders.remove(order)
        except ValueError:
            return

        if not level.orders:
            del book[order.price]

    # --------------------------------------------------------
    # BEST BID
    # --------------------------------------------------------

    def best_bid(self):

        if not self.bids:
            return None

        return max(self.bids.keys())

    # --------------------------------------------------------
    # BEST ASK
    # --------------------------------------------------------

    def best_ask(self):

        if not self.asks:
            return None

        return min(self.asks.keys())

    # --------------------------------------------------------
    # MID
    # --------------------------------------------------------

    def mid_price(self):

        bid = self.best_bid()
        ask = self.best_ask()

        if bid is None or ask is None:
            return None

        return (bid + ask) / D("2")

    # --------------------------------------------------------
    # DEPTH
    # --------------------------------------------------------

    def depth(self, levels=10):

        bids = sorted(
            self.bids.items(),
            key=lambda x: x[0],
            reverse=True
        )[:levels]

        asks = sorted(
            self.asks.items(),
            key=lambda x: x[0]
        )[:levels]

        return {
            "bids": [
                {
                    "price": price,
                    "quantity": sum(
                        order.remaining
                        for order in level.orders
                    )
                }
                for price, level in bids
            ],

            "asks": [
                {
                    "price": price,
                    "quantity": sum(
                        order.remaining
                        for order in level.orders
                    )
                }
                for price, level in asks
            ]
        }


# ============================================================
# RISK ENGINE
# ============================================================

class RiskEngine:

    def __init__(self):

        self.max_order_notional = MAX_ORDER_NOTIONAL
        self.max_position_mt = MAX_POSITION_MT

    def check_order(
        self,
        account: Account,
        order: Order,
        reference_price: Decimal
    ):

        price = order.price or reference_price

        notional = price * order.quantity

        if notional > self.max_order_notional:
            raise ValueError(
                f"Order exceeds notional limit: "
                f"${notional:,.2f}"
            )

        if order.side == Side.BUY:

            if account.cash_usd < notional:
                raise ValueError(
                    "Insufficient USD cash."
                )

        else:

            if account.copper_mt < order.quantity:
                raise ValueError(
                    "Insufficient copper inventory."
                )

        return True


# ============================================================
# MARKET
# ============================================================

class CopperSpotMarket:

    def __init__(self):

        self.symbol = COPPER_SYMBOL

        self.order_book = OrderBook()

        self.accounts: Dict[str, Account] = {}

        self.orders: Dict[str, Order] = {}

        self.trades: List[Trade] = []

        self.trade_sequence = itertools.count(1)

        self.risk = RiskEngine()

    # ========================================================
    # ACCOUNT MANAGEMENT
    # ========================================================

    def create_account(
        self,
        trader_id: str,
        cash_usd=0,
        copper_mt=0
    ):

        account = Account(
            trader_id=trader_id,
            cash_usd=D(cash_usd),
            copper_mt=D(copper_mt)
        )

        self.accounts[trader_id] = account

        return account

    # ========================================================
    # SUBMIT ORDER
    # ========================================================

    def submit_order(self, order: Order):

        if order.trader_id not in self.accounts:
            raise ValueError("Unknown trader.")

        account = self.accounts[order.trader_id]

        reference = (
            self.order_book.mid_price()
            or D("9500")
        )

        self.risk.check_order(
            account,
            order,
            reference
        )

        self.orders[order.order_id] = order

        if order.order_type == OrderType.MARKET:

            self._execute_market_order(order)

        else:

            self._execute_limit_order(order)

        return order

    # ========================================================
    # LIMIT ORDER
    # ========================================================

    def _execute_limit_order(self, incoming: Order):

        while incoming.remaining > 0:

            if incoming.side == Side.BUY:

                best_ask = self.order_book.best_ask()

                if best_ask is None:
                    break

                if incoming.price < best_ask:
                    break

                price = best_ask
                level = self.order_book.asks[price]

            else:

                best_bid = self.order_book.best_bid()

                if best_bid is None:
                    break

                if incoming.price > best_bid:
                    break

                price = best_bid
                level = self.order_book.bids[price]

            if not level.orders:
                continue

            resting = level.orders[0]

            quantity = min(
                incoming.remaining,
                resting.remaining
            )

            self._execute_trade(
                incoming,
                resting,
                price,
                quantity
            )

            if resting.remaining <= 0:

                level.orders.popleft()

                if not level.orders:
                    if incoming.side == Side.BUY:
                        del self.order_book.asks[price]
                    else:
                        del self.order_book.bids[price]

        if incoming.remaining > 0:

            self.order_book.add(incoming)

        return incoming

    # ========================================================
    # MARKET ORDER
    # ========================================================

    def _execute_market_order(self, incoming: Order):

        while incoming.remaining > 0:

            if incoming.side == Side.BUY:

                best = self.order_book.best_ask()

                if best is None:
                    break

                level = self.order_book.asks[best]

            else:

                best = self.order_book.best_bid()

                if best is None:
                    break

                level = self.order_book.bids[best]

            if not level.orders:
                continue

            resting = level.orders[0]

            quantity = min(
                incoming.remaining,
                resting.remaining
            )

            self._execute_trade(
                incoming,
                resting,
                best,
                quantity
            )

            if resting.remaining <= 0:

                level.orders.popleft()

                if not level.orders:

                    if incoming.side == Side.BUY:
                        del self.order_book.asks[best]
                    else:
                        del self.order_book.bids[best]

        return incoming

    # ========================================================
    # TRADE SETTLEMENT
    # ========================================================

    def _execute_trade(
        self,
        incoming: Order,
        resting: Order,
        price: Decimal,
        quantity: Decimal
    ):

        if incoming.side == Side.BUY:

            buyer = self.accounts[incoming.trader_id]
            seller = self.accounts[resting.trader_id]

        else:

            buyer = self.accounts[resting.trader_id]
            seller = self.accounts[incoming.trader_id]

        gross_value = price * quantity

        buyer_fee = gross_value * TRADING_FEE_BPS
        seller_fee = gross_value * TRADING_FEE_BPS

        total_buyer_cost = gross_value + buyer_fee

        seller_proceeds = gross_value - seller_fee

        # ----------------------------------------------------
        # CASH SETTLEMENT
        # ----------------------------------------------------

        buyer.cash_usd -= total_buyer_cost
        seller.cash_usd += seller_proceeds

        # ----------------------------------------------------
        # COPPER SETTLEMENT
        # ----------------------------------------------------

        buyer.copper_mt += quantity
        seller.copper_mt -= quantity

        # ----------------------------------------------------
        # FEES
        # ----------------------------------------------------

        buyer.fees_paid += buyer_fee
        seller.fees_paid += seller_fee

        # ----------------------------------------------------
        # ORDER STATE
        # ----------------------------------------------------

        incoming.fill(quantity)
        resting.fill(quantity)

        # ----------------------------------------------------
        # TRADE RECORD
        # ----------------------------------------------------

        trade = Trade(
            trade_id=f"T{next(self.trade_sequence):012d}",
            symbol=self.symbol,
            buyer=buyer.trader_id,
            seller=seller.trader_id,
            price=price,
            quantity=quantity,
            timestamp_ns=time.time_ns()
        )

        self.trades.append(trade)

    # ========================================================
    # CANCEL
    # ========================================================

    def cancel_order(self, order_id: str):

        order = self.orders.get(order_id)

        if not order:
            raise ValueError("Unknown order.")

        if order.status == OrderStatus.FILLED:
            raise ValueError("Order already filled.")

        self.order_book.remove(order)

        order.status = OrderStatus.CANCELLED

        return order

    # ========================================================
    # MARKET DATA
    # ========================================================

    def ticker(self):

        best_bid = self.order_book.best_bid()
        best_ask = self.order_book.best_ask()
        mid = self.order_book.mid_price()

        last_trade = (
            self.trades[-1]
            if self.trades
            else None
        )

        return {
            "symbol": self.symbol,
            "currency": CURRENCY,
            "unit": UNIT,

            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,

            "last_price":
                last_trade.price
                if last_trade
                else None,

            "last_quantity":
                last_trade.quantity
                if last_trade
                else None,

            "trade_count": len(self.trades)
        }

    # ========================================================
    # VWAP
    # ========================================================

    def vwap(self):

        if not self.trades:
            return None

        total_value = sum(
            trade.price * trade.quantity
            for trade in self.trades
        )

        total_volume = sum(
            trade.quantity
            for trade in self.trades
        )

        if total_volume == 0:
            return None

        return total_value / total_volume

    # ========================================================
    # RECENT TRADES
    # ========================================================

    def tape(self, n=20):

        return self.trades[-n:]

    # ========================================================
    # ACCOUNT
    # ========================================================

    def account_state(self, trader_id):

        account = self.accounts[trader_id]

        return {
            "trader": trader_id,
            "cash_usd": account.cash_usd,
            "copper_mt": account.copper_mt,
            "fees_paid": account.fees_paid,
            "realized_pnl": account.realized_pnl
        }


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    market = CopperSpotMarket()

    # --------------------------------------------------------
    # RHINOBANK MARKET-MAKING DESK
    # --------------------------------------------------------

    market.create_account(
        "RHINO_MARKET_MAKER",
        cash_usd="100000000",
        copper_mt="10000"
    )

    # --------------------------------------------------------
    # INDUSTRIAL BUYER
    # --------------------------------------------------------

    market.create_account(
        "INDUSTRIAL_BUYER_001",
        cash_usd="100000000",
        copper_mt="0"
    )

    # --------------------------------------------------------
    # MARKET MAKER POSTS ASK
    # --------------------------------------------------------

    ask = Order(
        trader_id="RHINO_MARKET_MAKER",
        side=Side.SELL,
        quantity=D("500"),
        price=D("9500"),
        order_type=OrderType.LIMIT
    )

    market.submit_order(ask)

    # --------------------------------------------------------
    # MARKET MAKER POSTS BID
    # --------------------------------------------------------

    bid = Order(
        trader_id="RHINO_MARKET_MAKER",
        side=Side.BUY,
        quantity=D("500"),
        price=D("9450"),
        order_type=OrderType.LIMIT
    )

    market.submit_order(bid)

    # --------------------------------------------------------
    # INDUSTRIAL BUYER CROSSES THE ASK
    # --------------------------------------------------------

    buy = Order(
        trader_id="INDUSTRIAL_BUYER_001",
        side=Side.BUY,
        quantity=D("100"),
        price=D("9500"),
        order_type=OrderType.LIMIT
    )

    market.submit_order(buy)

    # --------------------------------------------------------
    # DISPLAY MARKET
    # --------------------------------------------------------

    print("\n=== RHINOBANK COPPER SPOT ===")

    print(market.ticker())

    print("\n=== ORDER BOOK ===")

    print(market.order_book.depth())

    print("\n=== VWAP ===")

    print(market.vwap())

    print("\n=== TRADE TAPE ===")

    for trade in market.tape():
        print(
            trade.trade_id,
            trade.price,
            trade.quantity,
            trade.buyer,
            trade.seller
        )

    print("\n=== ACCOUNTS ===")

    print(
        market.account_state(
            "RHINO_MARKET_MAKER"
        )
    )

    print(
        market.account_state(
            "INDUSTRIAL_BUYER_001"
        )
    )
```

