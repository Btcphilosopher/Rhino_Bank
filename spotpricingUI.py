"""
===============================================================
RHINOTRADE SPOT
Generic Institutional Physical Spot-Market Engine
Version 1.0
===============================================================

Commodity-agnostic spot trading backend.

Supports:

    Instruments
    Physical inventory
    Market data
    Bid / ask order books
    Buy / sell orders
    Price-time priority matching
    Trade execution
    VWAP
    Accounts
    Credit limits
    Settlement
    Audit events
    REST API

This is a software-engine prototype. Production deployment
would additionally require hardened authentication, persistent
database transactions, regulatory controls, reconciliation,
KYC/AML, market surveillance, and operational controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# ============================================================
# UTILITIES
# ============================================================

ZERO = Decimal("0")


def D(value) -> Decimal:
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def qty(value) -> Decimal:
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def timestamp() -> datetime:
    return datetime.now(timezone.utc)


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

    OPEN = "OPEN"
    PART_FILLED = "PART_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class SettlementStatus(str, Enum):

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class AccountRole(str, Enum):

    TRADER = "TRADER"
    DEALER = "DEALER"
    ADMIN = "ADMIN"
    RISK = "RISK"
    OPERATIONS = "OPERATIONS"


# ============================================================
# INSTRUMENT
# ============================================================

@dataclass
class Instrument:

    symbol: str

    commodity: str

    grade: str

    unit: str

    currency: str

    location: str

    delivery_basis: str

    active: bool = True

    description: str = ""


# ============================================================
# PHYSICAL INVENTORY
# ============================================================

@dataclass
class InventoryLot:

    lot_id: str

    owner_account: str

    symbol: str

    quantity: Decimal

    location: str

    delivery_window: str

    certification: str = ""

    available: Decimal = field(
        init=False
    )

    reserved: Decimal = field(
        default=ZERO
    )

    def __post_init__(self):

        self.quantity = qty(
            self.quantity
        )

        self.available = self.quantity


# ============================================================
# ACCOUNT
# ============================================================

@dataclass
class Account:

    account_id: str

    name: str

    role: AccountRole

    currency: str = "USD"

    cash_balance: Decimal = ZERO

    credit_limit: Decimal = ZERO

    active: bool = True

    def buying_power(self):

        return (
            self.cash_balance
            + self.credit_limit
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class Order:

    order_id: str

    account_id: str

    symbol: str

    side: Side

    order_type: OrderType

    quantity: Decimal

    price: Optional[Decimal]

    remaining: Decimal

    status: OrderStatus

    created_at: datetime = field(
        default_factory=timestamp
    )

    sequence: int = 0


# ============================================================
# TRADE
# ============================================================

@dataclass
class Trade:

    trade_id: str

    symbol: str

    buyer_account: str

    seller_account: str

    quantity: Decimal

    price: Decimal

    buyer_order_id: str

    seller_order_id: str

    settlement_status: SettlementStatus = (
        SettlementStatus.PENDING
    )

    executed_at: datetime = field(
        default_factory=timestamp
    )

    @property
    def notional(self):

        return money(
            self.quantity
            * self.price
        )


# ============================================================
# MARKET DATA
# ============================================================

@dataclass
class MarketData:

    symbol: str

    reference_price: Decimal = ZERO

    last_price: Decimal = ZERO

    previous_close: Decimal = ZERO

    high: Decimal = ZERO

    low: Decimal = ZERO

    volume: Decimal = ZERO

    turnover: Decimal = ZERO

    trade_count: int = 0

    updated_at: datetime = field(
        default_factory=timestamp
    )


# ============================================================
# AUDIT EVENT
# ============================================================

@dataclass
class AuditEvent:

    event_id: str

    event_type: str

    actor: str

    object_id: str

    message: str

    created_at: datetime = field(
        default_factory=timestamp
    )


# ============================================================
# TRADE ENGINE
# ============================================================

class SpotExchange:

    def __init__(self):

        self.instruments: Dict[
            str, Instrument
        ] = {}

        self.accounts: Dict[
            str, Account
        ] = {}

        self.inventory: Dict[
            str, InventoryLot
        ] = {}

        self.orders: Dict[
            str, Order
        ] = {}

        self.trades: Dict[
            str, Trade
        ] = {}

        self.market_data: Dict[
            str, MarketData
        ] = {}

        self.audit: List[
            AuditEvent
        ] = []

        self.sequence = 0

    # ========================================================
    # AUDIT
    # ========================================================

    def audit_event(
        self,
        event_type,
        actor,
        object_id,
        message
    ):

        self.audit.append(

            AuditEvent(

                event_id=str(uuid4()),

                event_type=event_type,

                actor=actor,

                object_id=object_id,

                message=message
            )
        )

    # ========================================================
    # ACCOUNT
    # ========================================================

    def create_account(
        self,
        account_id,
        name,
        role=AccountRole.TRADER,
        currency="USD",
        cash_balance=0,
        credit_limit=0
    ):

        if account_id in self.accounts:

            raise ValueError(
                "Account already exists"
            )

        account = Account(

            account_id=account_id,

            name=name,

            role=role,

            currency=currency,

            cash_balance=D(
                cash_balance
            ),

            credit_limit=D(
                credit_limit
            )
        )

        self.accounts[
            account_id
        ] = account

        self.audit_event(

            "ACCOUNT_CREATED",

            account_id,

            account_id,

            f"Account {name} created"
        )

        return account

    # ========================================================
    # INSTRUMENT
    # ========================================================

    def create_instrument(
        self,
        symbol,
        commodity,
        grade,
        unit,
        currency,
        location,
        delivery_basis,
        description=""
    ):

        if symbol in self.instruments:

            raise ValueError(
                "Instrument already exists"
            )

        instrument = Instrument(

            symbol=symbol,

            commodity=commodity,

            grade=grade,

            unit=unit,

            currency=currency,

            location=location,

            delivery_basis=delivery_basis,

            description=description
        )

        self.instruments[
            symbol
        ] = instrument

        self.market_data[
            symbol
        ] = MarketData(
            symbol=symbol
        )

        return instrument

    # ========================================================
    # INVENTORY
    # ========================================================

    def add_inventory(
        self,
        owner_account,
        symbol,
        quantity,
        location,
        delivery_window,
        certification=""
    ):

        if owner_account not in self.accounts:

            raise ValueError(
                "Unknown account"
            )

        if symbol not in self.instruments:

            raise ValueError(
                "Unknown instrument"
            )

        lot = InventoryLot(

            lot_id=str(uuid4()),

            owner_account=owner_account,

            symbol=symbol,

            quantity=qty(
                quantity
            ),

            location=location,

            delivery_window=delivery_window,

            certification=certification
        )

        self.inventory[
            lot.lot_id
        ] = lot

        self.audit_event(

            "INVENTORY_ADDED",

            owner_account,

            lot.lot_id,

            f"{quantity} units added"
        )

        return lot

    # ========================================================
    # INVENTORY AVAILABLE
    # ========================================================

    def available_inventory(
        self,
        account_id,
        symbol
    ):

        return sum(

            lot.available

            for lot in self.inventory.values()

            if (
                lot.owner_account
                == account_id
                and
                lot.symbol
                == symbol
            )
        )

    # ========================================================
    # RESERVE INVENTORY
    # ========================================================

    def reserve_inventory(
        self,
        account_id,
        symbol,
        quantity
    ):

        remaining = qty(
            quantity
        )

        lots = [

            lot

            for lot in self.inventory.values()

            if (
                lot.owner_account
                == account_id
                and
                lot.symbol
                == symbol
                and
                lot.available > ZERO
            )
        ]

        for lot in lots:

            allocation = min(
                lot.available,
                remaining
            )

            lot.available -= allocation
            lot.reserved += allocation

            remaining -= allocation

            if remaining <= ZERO:

                break

        if remaining > ZERO:

            raise ValueError(
                "Insufficient physical inventory"
            )

    # ========================================================
    # BEST BID
    # ========================================================

    def best_bid(
        self,
        symbol
    ):

        bids = [

            order

            for order in self.orders.values()

            if (
                order.symbol == symbol
                and
                order.side == Side.BUY
                and
                order.status in (
                    OrderStatus.OPEN,
                    OrderStatus.PART_FILLED
                )
                and
                order.price is not None
            )
        ]

        if not bids:

            return None

        return max(
            bids,
            key=lambda x: (
                x.price,
                -x.sequence
            )
        )

    # ========================================================
    # BEST ASK
    # ========================================================

    def best_ask(
        self,
        symbol
    ):

        asks = [

            order

            for order in self.orders.values()

            if (
                order.symbol == symbol
                and
                order.side == Side.SELL
                and
                order.status in (
                    OrderStatus.OPEN,
                    OrderStatus.PART_FILLED
                )
                and
                order.price is not None
            )
        ]

        if not asks:

            return None

        return min(
            asks,
            key=lambda x: (
                x.price,
                x.sequence
            )
        )

    # ========================================================
    # PLACE ORDER
    # ========================================================

    def place_order(
        self,
        account_id,
        symbol,
        side,
        quantity,
        price=None,
        order_type=OrderType.LIMIT
    ):

        if account_id not in self.accounts:

            raise ValueError(
                "Unknown account"
            )

        if symbol not in self.instruments:

            raise ValueError(
                "Unknown instrument"
            )

        account = self.accounts[
            account_id
        ]

        if not account.active:

            raise ValueError(
                "Account disabled"
            )

        quantity = qty(
            quantity
        )

        if quantity <= ZERO:

            raise ValueError(
                "Quantity must be positive"
            )

        if order_type == OrderType.LIMIT:

            if price is None:

                raise ValueError(
                    "Limit orders require price"
                )

            price = money(price)

        # ----------------------------------------------------
        # SELL = PHYSICAL INVENTORY CHECK
        # ----------------------------------------------------

        if side == Side.SELL:

            available = (
                self.available_inventory(
                    account_id,
                    symbol
                )
            )

            if available < quantity:

                raise ValueError(
                    "Insufficient physical inventory"
                )

            self.reserve_inventory(

                account_id,

                symbol,

                quantity
            )

        # ----------------------------------------------------
        # BUY = CREDIT CHECK
        # ----------------------------------------------------

        if (
            side == Side.BUY
            and
            order_type == OrderType.LIMIT
        ):

            required = (
                quantity * price
            )

            if (
                account.buying_power()
                < required
            ):

                raise ValueError(
                    "Insufficient buying power"
                )

        self.sequence += 1

        order = Order(

            order_id=str(
                uuid4()
            ),

            account_id=account_id,

            symbol=symbol,

            side=side,

            order_type=order_type,

            quantity=quantity,

            price=price,

            remaining=quantity,

            status=OrderStatus.OPEN,

            sequence=self.sequence
        )

        self.orders[
            order.order_id
        ] = order

        self.audit_event(

            "ORDER_CREATED",

            account_id,

            order.order_id,

            f"{side.value} {quantity} {symbol}"
        )

        self.match(
            symbol
        )

        return order

    # ========================================================
    # MATCHING ENGINE
    # ========================================================

    def match(
        self,
        symbol
    ):

        while True:

            bid = self.best_bid(
                symbol
            )

            ask = self.best_ask(
                symbol
            )

            if bid is None or ask is None:

                break

            # No crossing market

            if bid.price < ask.price:

                break

            trade_quantity = min(

                bid.remaining,

                ask.remaining
            )

            # Price-time execution:
            # resting order price wins.

            trade_price = ask.price

            trade = Trade(

                trade_id=str(
                    uuid4()
                ),

                symbol=symbol,

                buyer_account=(
                    bid.account_id
                ),

                seller_account=(
                    ask.account_id
                ),

                quantity=trade_quantity,

                price=trade_price,

                buyer_order_id=(
                    bid.order_id
                ),

                seller_order_id=(
                    ask.order_id
                )
            )

            self.execute_trade(
                trade
            )

            bid.remaining -= (
                trade_quantity
            )

            ask.remaining -= (
                trade_quantity
            )

            self.update_order_status(
                bid
            )

            self.update_order_status(
                ask
            )

    # ========================================================
    # EXECUTION
    # ========================================================

    def execute_trade(
        self,
        trade
    ):

        buyer = self.accounts[
            trade.buyer_account
        ]

        seller = self.accounts[
            trade.seller_account
        ]

        notional = trade.notional

        # ----------------------------------------------------
        # CASH
        # ----------------------------------------------------

        if buyer.buying_power() < notional:

            raise RuntimeError(
                "Buyer credit check failed"
            )

        buyer.cash_balance -= notional

        seller.cash_balance += notional

        # ----------------------------------------------------
        # PHYSICAL DELIVERY
        # ----------------------------------------------------

        self.transfer_physical_inventory(

            seller.account_id,

            buyer.account_id,

            trade.symbol,

            trade.quantity
        )

        trade.settlement_status = (
            SettlementStatus.CONFIRMED
        )

        self.trades[
            trade.trade_id
        ] = trade

        # ----------------------------------------------------
        # MARKET DATA
        # ----------------------------------------------------

        market = self.market_data[
            trade.symbol
        ]

        market.last_price = (
            trade.price
        )

        if market.high == ZERO:

            market.high = trade.price

        else:

            market.high = max(
                market.high,
                trade.price
            )

        if market.low == ZERO:

            market.low = trade.price

        else:

            market.low = min(
                market.low,
                trade.price
            )

        market.volume += (
            trade.quantity
        )

        market.turnover += (
            trade.notional
        )

        market.trade_count += 1

        market.updated_at = timestamp()

        self.audit_event(

            "TRADE_EXECUTED",

            "MATCHING_ENGINE",

            trade.trade_id,

            (
                f"{trade.quantity} {trade.symbol} "
                f"@ {trade.price}"
            )
        )

    # ========================================================
    # TRANSFER PHYSICAL
    # ========================================================

    def transfer_physical_inventory(
        self,
        seller_account,
        buyer_account,
        symbol,
        quantity
    ):

        remaining = qty(
            quantity
        )

        lots = [

            lot

            for lot in self.inventory.values()

            if (
                lot.owner_account
                == seller_account
                and
                lot.symbol
                == symbol
                and
                lot.reserved > ZERO
            )
        ]

        for lot in lots:

            transfer = min(
                lot.reserved,
                remaining
            )

            lot.reserved -= transfer

            new_lot = InventoryLot(

                lot_id=str(uuid4()),

                owner_account=(
                    buyer_account
                ),

                symbol=symbol,

                quantity=transfer,

                location=lot.location,

                delivery_window=(
                    lot.delivery_window
                ),

                certification=(
                    lot.certification
                )
            )

            self.inventory[
                new_lot.lot_id
            ] = new_lot

            remaining -= transfer

            if remaining <= ZERO:

                break

        if remaining > ZERO:

            raise RuntimeError(
                "Physical transfer failed"
            )

    # ========================================================
    # ORDER STATUS
    # ========================================================

    def update_order_status(
        self,
        order
    ):

        if order.remaining <= ZERO:

            order.remaining = ZERO

            order.status = (
                OrderStatus.FILLED
            )

        elif order.remaining < order.quantity:

            order.status = (
                OrderStatus.PART_FILLED
            )

        else:

            order.status = (
                OrderStatus.OPEN
            )

    # ========================================================
    # CANCEL
    # ========================================================

    def cancel_order(
        self,
        order_id,
        account_id
    ):

        if order_id not in self.orders:

            raise ValueError(
                "Order not found"
            )

        order = self.orders[
            order_id
        ]

        if order.account_id != account_id:

            raise PermissionError(
                "Cannot cancel another account's order"
            )

        if order.status not in (

            OrderStatus.OPEN,

            OrderStatus.PART_FILLED

        ):

            raise ValueError(
                "Order cannot be cancelled"
            )

        order.status = (
            OrderStatus.CANCELLED
        )

        # Return remaining physical inventory

        if order.side == Side.SELL:

            self.release_inventory(

                account_id,

                order.symbol,

                order.remaining
            )

        self.audit_event(

            "ORDER_CANCELLED",

            account_id,

            order_id,

            "Order cancelled"
        )

        return order

    # ========================================================
    # RELEASE INVENTORY
    # ========================================================

    def release_inventory(
        self,
        account_id,
        symbol,
        amount
    ):

        remaining = qty(
            amount
        )

        lots = [

            lot

            for lot in self.inventory.values()

            if (
                lot.owner_account
                == account_id
                and
                lot.symbol
                == symbol
                and
                lot.reserved > ZERO
            )
        ]

        for lot in lots:

            release = min(

                lot.reserved,

                remaining
            )

            lot.reserved -= release
            lot.available += release

            remaining -= release

            if remaining <= ZERO:

                break

    # ========================================================
    # ORDER BOOK
    # ========================================================

    def order_book(
        self,
        symbol,
        depth=10
    ):

        bids = [

            order

            for order in self.orders.values()

            if (
                order.symbol == symbol
                and
                order.side == Side.BUY
                and
                order.status in (
                    OrderStatus.OPEN,
                    OrderStatus.PART_FILLED
                )
            )
        ]

        asks = [

            order

            for order in self.orders.values()

            if (
                order.symbol == symbol
                and
                order.side == Side.SELL
                and
                order.status in (
                    OrderStatus.OPEN,
                    OrderStatus.PART_FILLED
                )
            )
        ]

        bids.sort(

            key=lambda x: (
                -x.price,
                x.sequence
            )
        )

        asks.sort(

            key=lambda x: (
                x.price,
                x.sequence
            )
        )

        return {

            "bids": [

                {
                    "price": str(
                        x.price
                    ),

                    "quantity": str(
                        x.remaining
                    ),

                    "order_id":
                        x.order_id
                }

                for x in bids[:depth]
            ],

            "asks": [

                {
                    "price": str(
                        x.price
                    ),

                    "quantity": str(
                        x.remaining
                    ),

                    "order_id":
                        x.order_id
                }

                for x in asks[:depth]
            ]
        }

    # ========================================================
    # VWAP
    # ========================================================

    def vwap(
        self,
        symbol
    ):

        trades = [

            trade

            for trade in self.trades.values()

            if trade.symbol == symbol
        ]

        if not trades:

            return None

        volume = sum(

            trade.quantity

            for trade in trades
        )

        turnover = sum(

            trade.notional

            for trade in trades
        )

        if volume == ZERO:

            return None

        return money(
            turnover / volume
        )

    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    def market_snapshot(
        self,
        symbol
    ):

        if symbol not in self.instruments:

            raise ValueError(
                "Unknown instrument"
            )

        market = self.market_data[
            symbol
        ]

        bid = self.best_bid(
            symbol
        )

        ask = self.best_ask(
            symbol
        )

        return {

            "symbol":
                symbol,

            "commodity":
                self.instruments[
                    symbol
                ].commodity,

            "reference_price":
                str(
                    market.reference_price
                ),

            "bid":
                str(
                    bid.price
                    if bid
                    else ZERO
                ),

            "ask":
                str(
                    ask.price
                    if ask
                    else ZERO
                ),

            "last":
                str(
                    market.last_price
                ),

            "high":
                str(
                    market.high
                ),

            "low":
                str(
                    market.low
                ),

            "volume":
                str(
                    market.volume
                ),

            "turnover":
                str(
                    market.turnover
                ),

            "vwap":
                str(
                    self.vwap(symbol)
                    or ZERO
                ),

            "trades":
                market.trade_count,

            "timestamp":
                market.updated_at.isoformat()
        }


# ============================================================
# API
# ============================================================

app = FastAPI(
    title="RhinoTrade Spot API",
    version="1.0.0"
)

exchange = SpotExchange()


# ============================================================
# API REQUEST MODELS
# ============================================================

class InstrumentRequest(BaseModel):

    symbol: str
    commodity: str
    grade: str
    unit: str
    currency: str
    location: str
    delivery_basis: str
    description: str = ""


class AccountRequest(BaseModel):

    account_id: str
    name: str
    role: AccountRole = AccountRole.TRADER
    currency: str = "USD"
    cash_balance: float = 0
    credit_limit: float = 0


class InventoryRequest(BaseModel):

    account_id: str
    symbol: str
    quantity: float
    location: str
    delivery_window: str
    certification: str = ""


class OrderRequest(BaseModel):

    account_id: str
    symbol: str
    side: Side
    quantity: float
    price: Optional[float] = None
    order_type: OrderType = OrderType.LIMIT


# ============================================================
# API ROUTES
# ============================================================

@app.get("/")
def root():

    return {

        "system":
            "RHINOTRADE SPOT",

        "version":
            "1.0.0",

        "status":
            "ONLINE"
    }


@app.post("/accounts")
def api_create_account(
    request: AccountRequest
):

    try:

        account = exchange.create_account(

            account_id=request.account_id,

            name=request.name,

            role=request.role,

            currency=request.currency,

            cash_balance=request.cash_balance,

            credit_limit=request.credit_limit
        )

        return asdict(account)

    except ValueError as error:

        raise HTTPException(
            400,
            str(error)
        )


@app.post("/instruments")
def api_create_instrument(
    request: InstrumentRequest
):

    try:

        instrument = exchange.create_instrument(

            symbol=request.symbol,

            commodity=request.commodity,

            grade=request.grade,

            unit=request.unit,

            currency=request.currency,

            location=request.location,

            delivery_basis=request.delivery_basis,

            description=request.description
        )

        return asdict(instrument)

    except ValueError as error:

        raise HTTPException(
            400,
            str(error)
        )


@app.post("/inventory")
def api_add_inventory(
    request: InventoryRequest
):

    try:

        lot = exchange.add_inventory(

            owner_account=request.account_id,

            symbol=request.symbol,

            quantity=request.quantity,

            location=request.location,

            delivery_window=request.delivery_window,

            certification=request.certification
        )

        return asdict(lot)

    except ValueError as error:

        raise HTTPException(
            400,
            str(error)
        )


@app.post("/orders")
def api_place_order(
    request: OrderRequest
):

    try:

        order = exchange.place_order(

            account_id=request.account_id,

            symbol=request.symbol,

            side=request.side,

            quantity=request.quantity,

            price=request.price,

            order_type=request.order_type
        )

        return asdict(order)

    except (
        ValueError,
        PermissionError
    ) as error:

        raise HTTPException(
            400,
            str(error)
        )


@app.delete(
    "/orders/{order_id}"
)
def api_cancel_order(
    order_id: str,
    account_id: str
):

    try:

        order = exchange.cancel_order(

            order_id,

            account_id
        )

        return asdict(order)

    except (
        ValueError,
        PermissionError
    ) as error:

        raise HTTPException(
            400,
            str(error)
        )


@app.get(
    "/markets/{symbol}"
)
def api_market(
    symbol: str
):

    try:

        return {

            "market":
                exchange.market_snapshot(
                    symbol
                ),

            "order_book":
                exchange.order_book(
                    symbol
                )
        }

    except ValueError as error:

        raise HTTPException(
            404,
            str(error)
        )


@app.get("/trades")
def api_trades():

    return [

        asdict(trade)

        for trade
        in exchange.trades.values()
    ]


@app.get("/audit")
def api_audit():

    return [

        asdict(event)

        for event
        in exchange.audit
    ]


# ============================================================
# DEMO MARKET
# ============================================================

def demo():

    # --------------------------------------------------------
    # ACCOUNTS
    # --------------------------------------------------------

    exchange.create_account(

        "RHINO-BUYER",

        "Institutional Buyer",

        AccountRole.TRADER,

        "USD",

        cash_balance=5_000_000
    )

    exchange.create_account(

        "RHINO-SELLER",

        "Physical Commodity Supplier",

        AccountRole.DEALER,

        "USD",

        cash_balance=100_000
    )

    # --------------------------------------------------------
    # GENERIC COMMODITY
    # --------------------------------------------------------

    exchange.create_instrument(

        symbol="RRX-COMMODITY",

        commodity="Natural Rubber",

        grade="TSR20",

        unit="TONNE",

        currency="USD",

        location="Malaysia",

        delivery_basis="FOB",

        description=(
            "Physical natural rubber TSR20"
        )
    )

    # --------------------------------------------------------
    # SELLER INVENTORY
    # --------------------------------------------------------

    exchange.add_inventory(

        owner_account="RHINO-SELLER",

        symbol="RRX-COMMODITY",

        quantity=1000,

        location="Port Klang",

        delivery_window="October 2026",

        certification="PHYSICAL-CERTIFIED"
    )

    # --------------------------------------------------------
    # SELL ORDER
    # --------------------------------------------------------

    exchange.place_order(

        account_id="RHINO-SELLER",

        symbol="RRX-COMMODITY",

        side=Side.SELL,

        quantity=250,

        price=2315
    )

    # --------------------------------------------------------
    # BUY ORDER
    # --------------------------------------------------------

    exchange.place_order(

        account_id="RHINO-BUYER",

        symbol="RRX-COMMODITY",

        side=Side.BUY,

        quantity=100,

        price=2320
    )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RHINOTRADE SPOT")
    print("=" * 70)

    print(
        exchange.market_snapshot(
            "RRX-COMMODITY"
        )
    )

    print()
    print("ORDER BOOK")

    print(
        exchange.order_book(
            "RRX-COMMODITY"
        )
    )

    print()
    print("TRADES")

    for trade in exchange.trades.values():

        print(

            trade.trade_id,

            trade.quantity,

            trade.symbol,

            "@",

            trade.price,

            trade.notional
        )


# ============================================================
# RUN DEMO
# ============================================================

if __name__ == "__main__":

    demo()

    # Production API:
    #
    # uvicorn rhino_trade:app
