"""
====================================================================
RHINOBANK RHINOTRADE SPOT
Institutional Generic Physical Commodity Spot-Market Backend
Version 2.0
====================================================================

Generic physical commodity marketplace.

Designed for:
    - RhinoBank quants
    - commodity dealers
    - institutional buyers
    - physical suppliers
    - operations
    - risk
    - market-data teams

Examples of instruments:

    RRX-OAK
    RRX-RUBBER-TSR20
    RRX-COCOA
    RRX-COFFEE
    RRX-WHEAT
    RRX-SUGAR
    RRX-MILK
    RRX-WOOL
    RRX-POTATO
    RRX-OLIVEOIL

The same backend handles all of them.

IMPORTANT:
This is an engineering foundation. A live regulated venue would
need substantially more controls around authentication, KYC/AML,
market abuse surveillance, custody, settlement, reporting,
regulatory permissions, database HA, disaster recovery and
operational segregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


# ====================================================================
# UTILITIES
# ====================================================================

ZERO = Decimal("0")


def D(value) -> Decimal:
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def quantity(value) -> Decimal:
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def now() -> datetime:
    return datetime.now(timezone.utc)


# ====================================================================
# ENUMS
# ====================================================================

class InstrumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class ListingStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SOLD = "SOLD"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


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
    REJECTED = "REJECTED"


class AccountRole(str, Enum):
    TRADER = "TRADER"
    DEALER = "DEALER"
    QUANT = "QUANT"
    RISK = "RISK"
    OPERATIONS = "OPERATIONS"
    ADMIN = "ADMIN"


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PriceSourceType(str, Enum):
    MANUAL = "MANUAL"
    EXTERNAL = "EXTERNAL"
    FORMULA = "FORMULA"
    MARKET = "MARKET"


# ====================================================================
# PRODUCT / INSTRUMENT
# ====================================================================

@dataclass
class SpotInstrument:

    symbol: str

    commodity: str

    product_name: str

    grade: str

    description: str

    unit: str

    currency: str

    price_decimals: int

    quantity_decimals: int

    tick_size: Decimal

    minimum_quantity: Decimal

    maximum_quantity: Optional[Decimal]

    location: str

    delivery_basis: str

    delivery_terms: str

    status: InstrumentStatus

    price_source: PriceSourceType

    benchmark_symbol: Optional[str] = None

    benchmark_price: Decimal = ZERO

    price_adjustment: Decimal = ZERO

    created_by: str = ""

    created_at: datetime = field(
        default_factory=now
    )

    updated_at: datetime = field(
        default_factory=now
    )


# ====================================================================
# PRODUCT LISTING
# ====================================================================

@dataclass
class ProductListing:

    listing_id: str

    seller_account: str

    symbol: str

    title: str

    description: str

    quantity: Decimal

    remaining_quantity: Decimal

    asking_price: Decimal

    currency: str

    unit: str

    location: str

    delivery_window: str

    delivery_basis: str

    certification: str

    condition: str

    origin: str

    minimum_order_quantity: Decimal

    status: ListingStatus

    expires_at: datetime

    created_at: datetime = field(
        default_factory=now
    )

    updated_at: datetime = field(
        default_factory=now
    )


# ====================================================================
# PHYSICAL LOT
# ====================================================================

@dataclass
class PhysicalLot:

    lot_id: str

    owner_account: str

    symbol: str

    quantity: Decimal

    available_quantity: Decimal

    reserved_quantity: Decimal

    location: str

    origin: str

    delivery_window: str

    certification: str

    condition: str

    listing_id: Optional[str] = None


# ====================================================================
# ACCOUNT
# ====================================================================

@dataclass
class Account:

    account_id: str

    name: str

    role: AccountRole

    currency: str

    cash_balance: Decimal

    credit_limit: Decimal

    active: bool = True

    allowed_instruments: List[str] = field(
        default_factory=list
    )

    def buying_power(self):

        return (
            self.cash_balance
            + self.credit_limit
        )


# ====================================================================
# ORDER
# ====================================================================

@dataclass
class Order:

    order_id: str

    account_id: str

    symbol: str

    side: Side

    order_type: OrderType

    quantity: Decimal

    remaining_quantity: Decimal

    price: Optional[Decimal]

    status: OrderStatus

    listing_id: Optional[str]

    created_at: datetime

    sequence: int


# ====================================================================
# TRADE
# ====================================================================

@dataclass
class Trade:

    trade_id: str

    symbol: str

    buyer_account: str

    seller_account: str

    quantity: Decimal

    price: Decimal

    currency: str

    listing_id: Optional[str]

    buyer_order_id: str

    seller_order_id: str

    settlement_status: SettlementStatus

    executed_at: datetime

    @property
    def notional(self):

        return money(
            self.quantity * self.price
        )


# ====================================================================
# MARKET DATA
# ====================================================================

@dataclass
class Market:

    symbol: str

    reference_price: Decimal = ZERO

    last_price: Decimal = ZERO

    bid: Decimal = ZERO

    ask: Decimal = ZERO

    high: Decimal = ZERO

    low: Decimal = ZERO

    volume: Decimal = ZERO

    turnover: Decimal = ZERO

    trade_count: int = 0

    updated_at: datetime = field(
        default_factory=now
    )


# ====================================================================
# AUDIT
# ====================================================================

@dataclass
class AuditEvent:

    event_id: str

    actor: str

    event_type: str

    object_type: str

    object_id: str

    message: str

    timestamp: datetime = field(
        default_factory=now
    )


# ====================================================================
# EXCHANGE ENGINE
# ====================================================================

class RhinoTrade:

    def __init__(self):

        self.instruments: Dict[
            str, SpotInstrument
        ] = {}

        self.accounts: Dict[
            str, Account
        ] = {}

        self.listings: Dict[
            str, ProductListing
        ] = {}

        self.lots: Dict[
            str, PhysicalLot
        ] = {}

        self.orders: Dict[
            str, Order
        ] = {}

        self.trades: Dict[
            str, Trade
        ] = {}

        self.markets: Dict[
            str, Market
        ] = {}

        self.audit: List[
            AuditEvent
        ] = []

        self.sequence = 0


    # =================================================================
    # AUDIT
    # =================================================================

    def audit_event(
        self,
        actor,
        event_type,
        object_type,
        object_id,
        message
    ):

        self.audit.append(

            AuditEvent(

                event_id=str(uuid4()),

                actor=actor,

                event_type=event_type,

                object_type=object_type,

                object_id=object_id,

                message=message
            )
        )


    # =================================================================
    # ACCOUNT MANAGEMENT
    # =================================================================

    def create_account(
        self,
        account_id,
        name,
        role,
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

            account_id,

            "ACCOUNT_CREATED",

            "ACCOUNT",

            account_id,

            f"Created account {name}"
        )

        return account


    # =================================================================
    # INSTRUMENT MANAGEMENT
    # =================================================================

    def create_instrument(
        self,
        actor,
        symbol,
        commodity,
        product_name,
        grade,
        description,
        unit,
        currency,
        location,
        delivery_basis,
        delivery_terms,
        tick_size,
        minimum_quantity,
        price_source=PriceSourceType.MANUAL,
        benchmark_symbol=None,
        benchmark_price=0,
        price_adjustment=0,
        maximum_quantity=None
    ):

        account = self.accounts.get(
            actor
        )

        if account is None:

            raise ValueError(
                "Unknown actor"
            )

        if account.role not in (

            AccountRole.ADMIN,
            AccountRole.QUANT
        ):

            raise PermissionError(
                "Only QUANT or ADMIN may create instruments"
            )

        if symbol in self.instruments:

            raise ValueError(
                "Instrument already exists"
            )

        instrument = SpotInstrument(

            symbol=symbol.upper(),

            commodity=commodity,

            product_name=product_name,

            grade=grade,

            description=description,

            unit=unit,

            currency=currency,

            price_decimals=2,

            quantity_decimals=3,

            tick_size=D(tick_size),

            minimum_quantity=D(
                minimum_quantity
            ),

            maximum_quantity=(
                D(maximum_quantity)
                if maximum_quantity is not None
                else None
            ),

            location=location,

            delivery_basis=delivery_basis,

            delivery_terms=delivery_terms,

            status=InstrumentStatus.ACTIVE,

            price_source=price_source,

            benchmark_symbol=benchmark_symbol,

            benchmark_price=D(
                benchmark_price
            ),

            price_adjustment=D(
                price_adjustment
            ),

            created_by=actor
        )

        self.instruments[
            symbol.upper()
        ] = instrument

        self.markets[
            symbol.upper()
        ] = Market(
            symbol=symbol.upper(),
            reference_price=D(
                benchmark_price
            )
        )

        self.audit_event(

            actor,

            "INSTRUMENT_CREATED",

            "INSTRUMENT",

            symbol.upper(),

            f"Created {commodity} instrument"
        )

        return instrument


    # =================================================================
    # MODIFY INSTRUMENT
    # =================================================================

    def modify_instrument(
        self,
        actor,
        symbol,
        changes: Dict[str, Any]
    ):

        account = self.accounts.get(
            actor
        )

        if account is None:

            raise ValueError(
                "Unknown actor"
            )

        if account.role not in (

            AccountRole.ADMIN,
            AccountRole.QUANT
        ):

            raise PermissionError(
                "Insufficient permissions"
            )

        instrument = self.instruments.get(
            symbol
        )

        if instrument is None:

            raise ValueError(
                "Instrument not found"
            )

        protected = {
            "symbol",
            "created_at",
            "created_by"
        }

        for key, value in changes.items():

            if key in protected:

                continue

            if not hasattr(
                instrument,
                key
            ):

                continue

            if key in (
                "tick_size",
                "minimum_quantity",
                "maximum_quantity",
                "benchmark_price",
                "price_adjustment"
            ):

                value = (
                    D(value)
                    if value is not None
                    else None
                )

            setattr(
                instrument,
                key,
                value
            )

        instrument.updated_at = now()

        self.audit_event(

            actor,

            "INSTRUMENT_MODIFIED",

            "INSTRUMENT",

            symbol,

            str(changes)
        )

        return instrument


    # =================================================================
    # REFERENCE PRICE
    # =================================================================

    def set_reference_price(
        self,
        actor,
        symbol,
        price
    ):

        account = self.accounts.get(
            actor
        )

        if account is None:

            raise ValueError(
                "Unknown actor"
            )

        if account.role not in (

            AccountRole.ADMIN,
            AccountRole.QUANT
        ):

            raise PermissionError(
                "Insufficient permissions"
            )

        instrument = self.instruments[
            symbol
        ]

        instrument.benchmark_price = (
            D(price)
        )

        self.markets[
            symbol
        ].reference_price = D(price)

        self.audit_event(

            actor,

            "REFERENCE_PRICE_UPDATED",

            "INSTRUMENT",

            symbol,

            f"Reference price {price}"
        )


    # =================================================================
    # PHYSICAL INVENTORY
    # =================================================================

    def add_lot(
        self,
        owner_account,
        symbol,
        quantity_value,
        location,
        origin,
        delivery_window,
        certification="",
        condition="STANDARD"
    ):

        if owner_account not in self.accounts:

            raise ValueError(
                "Unknown account"
            )

        if symbol not in self.instruments:

            raise ValueError(
                "Unknown instrument"
            )

        amount = quantity(
            quantity_value
        )

        lot = PhysicalLot(

            lot_id=str(uuid4()),

            owner_account=owner_account,

            symbol=symbol,

            quantity=amount,

            available_quantity=amount,

            reserved_quantity=ZERO,

            location=location,

            origin=origin,

            delivery_window=delivery_window,

            certification=certification,

            condition=condition
        )

        self.lots[
            lot.lot_id
        ] = lot

        self.audit_event(

            owner_account,

            "LOT_CREATED",

            "PHYSICAL_LOT",

            lot.lot_id,

            f"{amount} units"
        )

        return lot


    # =================================================================
    # LIST PRODUCT
    # =================================================================

    def create_listing(
        self,
        seller_account,
        symbol,
        title,
        description,
        quantity_value,
        asking_price,
        location,
        delivery_window,
        delivery_basis,
        certification,
        condition,
        origin,
        minimum_order_quantity,
        expires_hours=72
    ):

        seller = self.accounts.get(
            seller_account
        )

        if seller is None:

            raise ValueError(
                "Unknown seller"
            )

        instrument = self.instruments.get(
            symbol
        )

        if instrument is None:

            raise ValueError(
                "Unknown instrument"
            )

        amount = quantity(
            quantity_value
        )

        minimum = quantity(
            minimum_order_quantity
        )

        if amount <= ZERO:

            raise ValueError(
                "Quantity must be positive"
            )

        available = sum(

            lot.available_quantity

            for lot in self.lots.values()

            if (
                lot.owner_account
                == seller_account
                and
                lot.symbol
                == symbol
            )
        )

        if available < amount:

            raise ValueError(
                "Insufficient physical inventory"
            )

        # Reserve physical inventory

        self.reserve_inventory(

            seller_account,

            symbol,

            amount
        )

        listing = ProductListing(

            listing_id=str(uuid4()),

            seller_account=seller_account,

            symbol=symbol,

            title=title,

            description=description,

            quantity=amount,

            remaining_quantity=amount,

            asking_price=money(
                asking_price
            ),

            currency=instrument.currency,

            unit=instrument.unit,

            location=location,

            delivery_window=delivery_window,

            delivery_basis=delivery_basis,

            certification=certification,

            condition=condition,

            origin=origin,

            minimum_order_quantity=minimum,

            status=ListingStatus.ACTIVE,

            expires_at=(
                now()
                + timedelta(
                    hours=expires_hours
                )
            )
        )

        self.listings[
            listing.listing_id
        ] = listing

        # Attach listing to reserved inventory

        remaining = amount

        for lot in self.lots.values():

            if (
                lot.owner_account
                == seller_account
                and
                lot.symbol
                == symbol
                and
                lot.reserved_quantity
                > ZERO
                and
                remaining > ZERO
            ):

                lot.listing_id = (
                    listing.listing_id
                )

                allocated = min(
                    lot.reserved_quantity,
                    remaining
                )

                remaining -= allocated

        self.audit_event(

            seller_account,

            "PRODUCT_LISTED",

            "LISTING",

            listing.listing_id,

            f"Listed {amount} {symbol}"
        )

        return listing


    # =================================================================
    # INVENTORY RESERVATION
    # =================================================================

    def reserve_inventory(
        self,
        account_id,
        symbol,
        amount
    ):

        remaining = quantity(
            amount
        )

        lots = [

            lot

            for lot in self.lots.values()

            if (
                lot.owner_account
                == account_id
                and
                lot.symbol
                == symbol
                and
                lot.available_quantity
                > ZERO
            )
        ]

        for lot in lots:

            allocation = min(

                lot.available_quantity,

                remaining
            )

            lot.available_quantity -= (
                allocation
            )

            lot.reserved_quantity += (
                allocation
            )

            remaining -= allocation

            if remaining <= ZERO:

                break

        if remaining > ZERO:

            raise ValueError(
                "Insufficient inventory"
            )


    # =================================================================
    # RELEASE INVENTORY
    # =================================================================

    def release_inventory(
        self,
        account_id,
        symbol,
        amount
    ):

        remaining = quantity(
            amount
        )

        for lot in self.lots.values():

            if (
                lot.owner_account
                == account_id
                and
                lot.symbol
                == symbol
                and
                lot.reserved_quantity
                > ZERO
            ):

                release = min(

                    lot.reserved_quantity,

                    remaining
                )

                lot.reserved_quantity -= (
                    release
                )

                lot.available_quantity += (
                    release
                )

                remaining -= release

                if remaining <= ZERO:

                    break


    # =================================================================
    # SEARCH LISTINGS
    # =================================================================

    def search_listings(
        self,
        symbol=None,
        location=None,
        origin=None,
        min_price=None,
        max_price=None,
        status=ListingStatus.ACTIVE
    ):

        results = []

        for listing in self.listings.values():

            if listing.status != status:

                continue

            if listing.expires_at < now():

                listing.status = (
                    ListingStatus.EXPIRED
                )

                continue

            if symbol and listing.symbol != symbol:

                continue

            if location and (
                listing.location.lower()
                != location.lower()
            ):

                continue

            if origin and (
                listing.origin.lower()
                != origin.lower()
            ):

                continue

            if (
                min_price is not None
                and
                listing.asking_price
                < D(min_price)
            ):

                continue

            if (
                max_price is not None
                and
                listing.asking_price
                > D(max_price)
            ):

                continue

            results.append(
                listing
            )

        return results


    # =================================================================
    # LISTING PURCHASE
    # =================================================================

    def buy_listing(
        self,
        buyer_account,
        listing_id,
        quantity_value
    ):

        buyer = self.accounts.get(
            buyer_account
        )

        if buyer is None:

            raise ValueError(
                "Unknown buyer"
            )

        listing = self.listings.get(
            listing_id
        )

        if listing is None:

            raise ValueError(
                "Listing not found"
            )

        if listing.status != (
            ListingStatus.ACTIVE
        ):

            raise ValueError(
                "Listing unavailable"
            )

        if listing.expires_at < now():

            listing.status = (
                ListingStatus.EXPIRED
            )

            raise ValueError(
                "Listing expired"
            )

        amount = quantity(
            quantity_value
        )

        if amount < listing.minimum_order_quantity:

            raise ValueError(
                "Below minimum order quantity"
            )

        if amount > listing.remaining_quantity:

            raise ValueError(
                "Insufficient listed quantity"
            )

        total = money(

            amount
            * listing.asking_price
        )

        if buyer.buying_power() < total:

            raise ValueError(
                "Insufficient buying power"
            )

        # ------------------------------------------------------------
        # CASH
        # ------------------------------------------------------------

        seller = self.accounts[
            listing.seller_account
        ]

        buyer.cash_balance -= total

        seller.cash_balance += total

        # ------------------------------------------------------------
        # PHYSICAL TRANSFER
        # ------------------------------------------------------------

        self.transfer_reserved_inventory(

            seller.account_id,

            buyer.account_id,

            listing.symbol,

            amount
        )

        listing.remaining_quantity -= amount

        listing.updated_at = now()

        if listing.remaining_quantity <= ZERO:

            listing.remaining_quantity = ZERO

            listing.status = (
                ListingStatus.SOLD
            )

        trade = Trade(

            trade_id=str(uuid4()),

            symbol=listing.symbol,

            buyer_account=buyer_account,

            seller_account=(
                listing.seller_account
            ),

            quantity=amount,

            price=listing.asking_price,

            currency=listing.currency,

            listing_id=listing_id,

            buyer_order_id="LISTING",

            seller_order_id="LISTING",

            settlement_status=(
                SettlementStatus.CONFIRMED
            ),

            executed_at=now()
        )

        self.trades[
            trade.trade_id
        ] = trade

        self.update_market(
            trade
        )

        self.audit_event(

            buyer_account,

            "LISTING_PURCHASED",

            "TRADE",

            trade.trade_id,

            f"Purchased {amount} {listing.symbol}"
        )

        return trade


    # =================================================================
    # TRANSFER RESERVED PHYSICAL INVENTORY
    # =================================================================

    def transfer_reserved_inventory(
        self,
        seller_account,
        buyer_account,
        symbol,
        amount
    ):

        remaining = quantity(
            amount
        )

        for lot in self.lots.values():

            if (
                lot.owner_account
                == seller_account
                and
                lot.symbol
                == symbol
                and
                lot.reserved_quantity
                > ZERO
            ):

                transfer = min(

                    lot.reserved_quantity,

                    remaining
                )

                lot.reserved_quantity -= (
                    transfer
                )

                new_lot = PhysicalLot(

                    lot_id=str(uuid4()),

                    owner_account=buyer_account,

                    symbol=symbol,

                    quantity=transfer,

                    available_quantity=transfer,

                    reserved_quantity=ZERO,

                    location=lot.location,

                    origin=lot.origin,

                    delivery_window=(
                        lot.delivery_window
                    ),

                    certification=(
                        lot.certification
                    ),

                    condition=lot.condition
                )

                self.lots[
                    new_lot.lot_id
                ] = new_lot

                remaining -= transfer

                if remaining <= ZERO:

                    break

        if remaining > ZERO:

            raise RuntimeError(
                "Physical settlement failed"
            )


    # =================================================================
    # ORDER ENTRY
    # =================================================================

    def place_order(
        self,
        account_id,
        symbol,
        side,
        quantity_value,
        price=None,
        order_type=OrderType.LIMIT,
        listing_id=None
    ):

        account = self.accounts.get(
            account_id
        )

        if account is None:

            raise ValueError(
                "Unknown account"
            )

        instrument = self.instruments.get(
            symbol
        )

        if instrument is None:

            raise ValueError(
                "Unknown instrument"
            )

        if instrument.status != (
            InstrumentStatus.ACTIVE
        ):

            raise ValueError(
                "Instrument not active"
            )

        amount = quantity(
            quantity_value
        )

        if amount < instrument.minimum_quantity:

            raise ValueError(
                "Below minimum instrument quantity"
            )

        if (
            instrument.maximum_quantity
            and
            amount
            > instrument.maximum_quantity
        ):

            raise ValueError(
                "Above maximum order quantity"
            )

        if order_type == OrderType.LIMIT:

            if price is None:

                raise ValueError(
                    "Limit order requires price"
                )

            price = money(
                price
            )

        # ------------------------------------------------------------
        # SELL
        # ------------------------------------------------------------

        if side == Side.SELL:

            available = sum(

                lot.available_quantity

                for lot in self.lots.values()

                if (
                    lot.owner_account
                    == account_id
                    and
                    lot.symbol
                    == symbol
                )
            )

            if available < amount:

                raise ValueError(
                    "Insufficient physical inventory"
                )

            self.reserve_inventory(

                account_id,

                symbol,

                amount
            )

        # ------------------------------------------------------------
        # BUY
        # ------------------------------------------------------------

        if (
            side == Side.BUY
            and
            order_type == OrderType.LIMIT
        ):

            maximum_cost = (
                amount * price
            )

            if (
                account.buying_power()
                < maximum_cost
            ):

                raise ValueError(
                    "Insufficient buying power"
                )

        self.sequence += 1

        order = Order(

            order_id=str(uuid4()),

            account_id=account_id,

            symbol=symbol,

            side=side,

            order_type=order_type,

            quantity=amount,

            remaining_quantity=amount,

            price=price,

            status=OrderStatus.OPEN,

            listing_id=listing_id,

            created_at=now(),

            sequence=self.sequence
        )

        self.orders[
            order.order_id
        ] = order

        self.match(
            symbol
        )

        return order


    # =================================================================
    # MATCH ENGINE
    # =================================================================

    def match(
        self,
        symbol
    ):

        while True:

            bids = [

                o

                for o in self.orders.values()

                if (
                    o.symbol == symbol
                    and
                    o.side == Side.BUY
                    and
                    o.status in (
                        OrderStatus.OPEN,
                        OrderStatus.PART_FILLED
                    )
                    and
                    o.price is not None
                )
            ]

            asks = [

                o

                for o in self.orders.values()

                if (
                    o.symbol == symbol
                    and
                    o.side == Side.SELL
                    and
                    o.status in (
                        OrderStatus.OPEN,
                        OrderStatus.PART_FILLED
                    )
                    and
                    o.price is not None
                )
            ]

            if not bids or not asks:

                return

            bids.sort(

                key=lambda o: (
                    -o.price,
                    o.sequence
                )
            )

            asks.sort(

                key=lambda o: (
                    o.price,
                    o.sequence
                )
            )

            bid = bids[0]

            ask = asks[0]

            if bid.price < ask.price:

                return

            trade_quantity = min(

                bid.remaining_quantity,

                ask.remaining_quantity
            )

            trade_price = ask.price

            trade = Trade(

                trade_id=str(uuid4()),

                symbol=symbol,

                buyer_account=bid.account_id,

                seller_account=ask.account_id,

                quantity=trade_quantity,

                price=trade_price,

                currency=(
                    self.instruments[
                        symbol
                    ].currency
                ),

                listing_id=(
                    ask.listing_id
                    or bid.listing_id
                ),

                buyer_order_id=bid.order_id,

                seller_order_id=ask.order_id,

                settlement_status=(
                    SettlementStatus.CONFIRMED
                ),

                executed_at=now()
            )

            self.execute_order_trade(
                trade
            )

            bid.remaining_quantity -= (
                trade_quantity
            )

            ask.remaining_quantity -= (
                trade_quantity
            )

            self.update_order(
                bid
            )

            self.update_order(
                ask
            )


    # =================================================================
    # ORDER TRADE
    # =================================================================

    def execute_order_trade(
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

        if buyer.buying_power() < notional:

            raise RuntimeError(
                "Buyer failed credit check"
            )

        buyer.cash_balance -= notional

        seller.cash_balance += notional

        self.transfer_reserved_inventory(

            seller.account_id,

            buyer.account_id,

            trade.symbol,

            trade.quantity
        )

        self.trades[
            trade.trade_id
        ] = trade

        self.update_market(
            trade
        )

        self.audit_event(

            "MATCHING_ENGINE",

            "TRADE_EXECUTED",

            "TRADE",

            trade.trade_id,

            (
                f"{trade.quantity} "
                f"{trade.symbol} @ "
                f"{trade.price}"
            )
        )


    # =================================================================
    # ORDER STATUS
    # =================================================================

    def update_order(
        self,
        order
    ):

        if order.remaining_quantity <= ZERO:

            order.remaining_quantity = ZERO

            order.status = (
                OrderStatus.FILLED
            )

        elif (
            order.remaining_quantity
            < order.quantity
        ):

            order.status = (
                OrderStatus.PART_FILLED
            )

        else:

            order.status = (
                OrderStatus.OPEN
            )


    # =================================================================
    # CANCEL ORDER
    # =================================================================

    def cancel_order(
        self,
        account_id,
        order_id
    ):

        order = self.orders.get(
            order_id
        )

        if order is None:

            raise ValueError(
                "Order not found"
            )

        if order.account_id != account_id:

            raise PermissionError(
                "Not order owner"
            )

        if order.status not in (

            OrderStatus.OPEN,
            OrderStatus.PART_FILLED

        ):

            raise ValueError(
                "Order cannot be cancelled"
            )

        remaining = (
            order.remaining_quantity
        )

        if order.side == Side.SELL:

            self.release_inventory(

                account_id,

                order.symbol,

                remaining
            )

        order.status = (
            OrderStatus.CANCELLED
        )

        self.audit_event(

            account_id,

            "ORDER_CANCELLED",

            "ORDER",

            order_id,

            "Order cancelled"
        )

        return order


    # =================================================================
    # MARKET UPDATE
    # =================================================================

    def update_market(
        self,
        trade
    ):

        market = self.markets[
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

        market.updated_at = now()


    # =================================================================
    # VWAP
    # =================================================================

    def vwap(
        self,
        symbol
    ):

        trades = [

            t

            for t in self.trades.values()

            if t.symbol == symbol
        ]

        if not trades:

            return ZERO

        volume = sum(

            t.quantity

            for t in trades
        )

        turnover = sum(

            t.notional

            for t in trades
        )

        if volume == ZERO:

            return ZERO

        return money(
            turnover / volume
        )


    # =================================================================
    # ORDER BOOK
    # =================================================================

    def order_book(
        self,
        symbol,
        depth=10
    ):

        bids = [

            o

            for o in self.orders.values()

            if (
                o.symbol == symbol
                and
                o.side == Side.BUY
                and
                o.status in (
                    OrderStatus.OPEN,
                    OrderStatus.PART_FILLED
                )
            )
        ]

        asks = [

            o

            for o in self.orders.values()

            if (
                o.symbol == symbol
                and
                o.side == Side.SELL
                and
                o.status in (
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
                        o.price
                    ),
                    "quantity": str(
                        o.remaining_quantity
                    ),
                    "order_id":
                        o.order_id
                }

                for o in bids[:depth]
            ],

            "asks": [

                {
                    "price": str(
                        o.price
                    ),
                    "quantity": str(
                        o.remaining_quantity
                    ),
                    "order_id":
                        o.order_id
                }

                for o in asks[:depth]
            ]
        }


    # =================================================================
    # MARKET SNAPSHOT
    # =================================================================

    def snapshot(
        self,
        symbol
    ):

        market = self.markets[
            symbol
        ]

        book = self.order_book(
            symbol
        )

        return {

            "symbol":
                symbol,

            "instrument":
                asdict(
                    self.instruments[
                        symbol
                    ]
                ),

            "market": {

                "reference":
                    str(
                        market.reference_price
                    ),

                "bid":
                    book["bids"][0]["price"]
                    if book["bids"]
                    else "0",

                "ask":
                    book["asks"][0]["price"]
                    if book["asks"]
                    else "0",

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
                        self.vwap(
                            symbol
                        )
                    ),

                "trades":
                    market.trade_count
            },

            "order_book":
                book
        }


# ====================================================================
# FASTAPI
# ====================================================================

app = FastAPI(

    title="RhinoTrade Spot",

    description=(
        "RhinoBank institutional "
        "physical commodity spot platform"
    ),

    version="2.0.0"
)

exchange = RhinoTrade()


# ====================================================================
# REQUEST MODELS
# ====================================================================

class AccountRequest(BaseModel):

    account_id: str

    name: str

    role: AccountRole

    currency: str = "USD"

    cash_balance: float = 0

    credit_limit: float = 0


class InstrumentRequest(BaseModel):

    actor: str

    symbol: str

    commodity: str

    product_name: str

    grade: str = ""

    description: str = ""

    unit: str

    currency: str

    location: str

    delivery_basis: str

    delivery_terms: str = ""

    tick_size: float

    minimum_quantity: float

    maximum_quantity: Optional[float] = None

    price_source: PriceSourceType = (
        PriceSourceType.MANUAL
    )

    benchmark_symbol: Optional[str] = None

    benchmark_price: float = 0

    price_adjustment: float = 0


class InstrumentUpdate(BaseModel):

    actor: str

    changes: Dict[str, Any]


class ReferencePriceRequest(BaseModel):

    actor: str

    price: float


class InventoryRequest(BaseModel):

    account_id: str

    symbol: str

    quantity: float

    location: str

    origin: str

    delivery_window: str

    certification: str = ""

    condition: str = "STANDARD"


class ListingRequest(BaseModel):

    seller_account: str

    symbol: str

    title: str

    description: str = ""

    quantity: float

    asking_price: float

    location: str

    delivery_window: str

    delivery_basis: str

    certification: str = ""

    condition: str = "STANDARD"

    origin: str = ""

    minimum_order_quantity: float = 1

    expires_hours: int = 72


class BuyListingRequest(BaseModel):

    buyer_account: str

    quantity: float


class OrderRequest(BaseModel):

    account_id: str

    symbol: str

    side: Side

    quantity: float

    price: Optional[float] = None

    order_type: OrderType = OrderType.LIMIT

    listing_id: Optional[str] = None


class CancelRequest(BaseModel):

    account_id: str


# ====================================================================
# API — ACCOUNTS
# ====================================================================

@app.post("/accounts")
def create_account(
    request: AccountRequest
):

    try:

        return asdict(

            exchange.create_account(

                request.account_id,

                request.name,

                request.role,

                request.currency,

                request.cash_balance,

                request.credit_limit
            )
        )

    except (
        ValueError,
        PermissionError
    ) as e:

        raise HTTPException(
            400,
            str(e)
        )


# ====================================================================
# API — INSTRUMENTS
# ====================================================================

@app.post("/instruments")
def create_instrument(
    request: InstrumentRequest
):

    try:

        return asdict(

            exchange.create_instrument(

                actor=request.actor,

                symbol=request.symbol,

                commodity=request.commodity,

                product_name=request.product_name,

                grade=request.grade,

                description=request.description,

                unit=request.unit,

                currency=request.currency,

                location=request.location,

                delivery_basis=request.delivery_basis,

                delivery_terms=request.delivery_terms,

                tick_size=request.tick_size,

                minimum_quantity=(
                    request.minimum_quantity
                ),

                maximum_quantity=(
                    request.maximum_quantity
                ),

                price_source=(
                    request.price_source
                ),

                benchmark_symbol=(
                    request.benchmark_symbol
                ),

                benchmark_price=(
                    request.benchmark_price
                ),

                price_adjustment=(
                    request.price_adjustment
                )
            )
        )

    except (
        ValueError,
        PermissionError
    ) as e:

        raise HTTPException(
            400,
            str(e)
        )


@app.patch(
    "/instruments/{symbol}"
)
def modify_instrument(
    symbol: str,
    request: InstrumentUpdate
):

    try:

        return asdict(

            exchange.modify_instrument(

                request.actor,

                symbol,

                request.changes
            )
        )

    except (
        ValueError,
        PermissionError
    ) as e:

        raise HTTPException(
            400,
            str(e)
        )


@app.post(
    "/instruments/{symbol}/reference-price"
)
def reference_price(
    symbol: str,
    request: ReferencePriceRequest
):

    try:

        exchange.set_reference_price(

            request.actor,

            symbol,

            request.price
        )

        return {
            "symbol": symbol,
            "reference_price":
                request.price
        }

    except (
        ValueError,
        PermissionError
    ) as e:

        raise HTTPException(
            400,
            str(e)
        )


# ====================================================================
# API — INVENTORY
# ====================================================================

@app.post("/inventory")
def add_inventory(
    request: InventoryRequest
):

    try:

        return asdict(

            exchange.add_lot(

                request.account_id,

                request.symbol,

                request.quantity,

                request.location,

                request.origin,

                request.delivery_window,

                request.certification,

                request.condition
            )
        )

    except ValueError as e:

        raise HTTPException(
            400,
            str(e)
        )


# ====================================================================
# API — PRODUCT LISTINGS
# ====================================================================

@app.post("/listings")
def create_listing(
    request: ListingRequest
):

    try:

        return asdict(

            exchange.create_listing(

                seller_account=(
                    request.seller_account
                ),

                symbol=request.symbol,

                title=request.title,

                description=request.description,

                quantity_value=request.quantity,

                asking_price=request.asking_price,

                location=request.location,

                delivery_window=(
                    request.delivery_window
                ),

                delivery_basis=(
                    request.delivery_basis
                ),

                certification=(
                    request.certification
                ),

                condition=request.condition,

                origin=request.origin,

                minimum_order_quantity=(
                    request.minimum_order_quantity
                ),

                expires_hours=(
                    request.expires_hours
                )
            )
        )

    except ValueError as e:

        raise HTTPException(
            400,
            str(e)
        )


@app.get("/listings")
def search_listings(

    symbol: Optional[str] = None,

    location: Optional[str] = None,

    origin: Optional[str] = None,

    min_price: Optional[float] = None,

    max_price: Optional[float] = None

):

    listings = exchange.search_listings(

        symbol=symbol,

        location=location,

        origin=origin,

        min_price=min_price,

        max_price=max_price
    )

    return [
        asdict(x)
        for x in listings
    ]


@app.post(
    "/listings/{listing_id}/buy"
)
def buy_listing(
    listing_id: str,
    request: BuyListingRequest
):

    try:

        return asdict(

            exchange.buy_listing(

                request.buyer_account,

                listing_id,

                request.quantity
            )
        )

    except ValueError as e:

        raise HTTPException(
            400,
            str(e)
        )


# ====================================================================
# API — ORDERS
# ====================================================================

@app.post("/orders")
def place_order(
    request: OrderRequest
):

    try:

        return asdict(

            exchange.place_order(

                account_id=request.account_id,

                symbol=request.symbol,

                side=request.side,

                quantity_value=request.quantity,

                price=request.price,

                order_type=request.order_type,

                listing_id=request.listing_id
            )
        )

    except (
        ValueError,
        RuntimeError
    ) as e:

        raise HTTPException(
            400,
            str(e)
        )


@app.delete(
    "/orders/{order_id}"
)
def cancel_order(
    order_id: str,
    request: CancelRequest
):

    try:

        return asdict(

            exchange.cancel_order(

                request.account_id,

                order_id
            )
        )

    except (
        ValueError,
        PermissionError
    ) as e:

        raise HTTPException(
            400,
            str(e)
        )


# ====================================================================
# API — MARKET DATA
# ====================================================================

@app.get(
    "/markets/{symbol}"
)
def market(
    symbol: str
):

    if symbol not in exchange.instruments:

        raise HTTPException(
            404,
            "Instrument not found"
        )

    return exchange.snapshot(
        symbol
    )


@app.get("/trades")
def trades(
    symbol: Optional[str] = None
):

    result = list(
        exchange.trades.values()
    )

    if symbol:

        result = [

            trade

            for trade in result

            if trade.symbol == symbol
        ]

    return [
        asdict(x)
        for x in result
    ]


# ====================================================================
# API — AUDIT
# ====================================================================

@app.get("/audit")
def audit(
    limit: int = Query(
        100,
        ge=1,
        le=5000
    )
):

    return [

        asdict(x)

        for x
        in exchange.audit[-limit:]
    ]


# ====================================================================
# HEALTH
# ====================================================================

@app.get("/")
def health():

    return {

        "system":
            "RHINOBANK RHINOTRADE SPOT",

        "version":
            "2.0.0",

        "status":
            "ONLINE",

        "instruments":
            len(exchange.instruments),

        "listings":
            len(exchange.listings),

        "orders":
            len(exchange.orders),

        "trades":
            len(exchange.trades)
    }


# ====================================================================
# DEVELOPMENT DATA
# ====================================================================

def seed_demo():

    # ---------------------------------------------------------------
    # QUANT
    # ---------------------------------------------------------------

    exchange.create_account(

        "RHINO-QUANT",

        "RhinoBank Quant Desk",

        AccountRole.QUANT,

        "USD",

        10_000_000
    )

    # ---------------------------------------------------------------
    # SELLER
    # ---------------------------------------------------------------

    exchange.create_account(

        "SUPPLIER-001",

        "Institutional Commodity Supplier",

        AccountRole.DEALER,

        "USD",

        500_000
    )

    # ---------------------------------------------------------------
    # BUYER
    # ---------------------------------------------------------------

    exchange.create_account(

        "BUYER-001",

        "Institutional Buyer",

        AccountRole.TRADER,

        "USD",

        5_000_000
    )

    # ---------------------------------------------------------------
    # RUBBER
    # ---------------------------------------------------------------

    exchange.create_instrument(

        actor="RHINO-QUANT",

        symbol="RRX-RUBBER-TSR20",

        commodity="Natural Rubber",

        product_name="TSR20 Natural Rubber",

        grade="TSR20",

        description=(
            "Physical TSR20 natural rubber"
        ),

        unit="TONNE",

        currency="USD",

        location="Malaysia",

        delivery_basis="FOB",

        delivery_terms="Port Klang",

        tick_size=0.50,

        minimum_quantity=5,

        price_source=PriceSourceType.EXTERNAL,

        benchmark_symbol="TSR20",

        benchmark_price=2310
    )

    # ---------------------------------------------------------------
    # COCOA
    # ---------------------------------------------------------------

    exchange.create_instrument(

        actor="RHINO-QUANT",

        symbol="RRX-COCOA",

        commodity="Cocoa",

        product_name="Cocoa Beans",

        grade="GRADE-A",

        description=(
            "Physical cocoa beans"
        ),

        unit="TONNE",

        currency="USD",

        location="Ghana",

        delivery_basis="FOB",

        delivery_terms="Main Port",

        tick_size=1,

        minimum_quantity=1,

        price_source=PriceSourceType.EXTERNAL,

        benchmark_symbol="COCOA-SPOT",

        benchmark_price=7200
    )

    # ---------------------------------------------------------------
    # COFFEE
    # ---------------------------------------------------------------

    exchange.create_instrument(

        actor="RHINO-QUANT",

        symbol="RRX-COFFEE-ARABICA",

        commodity="Coffee",

        product_name="Arabica Coffee",

        grade="SPECIALTY",

        description=(
            "Physical Arabica coffee"
        ),

        unit="TONNE",

        currency="USD",

        location="Brazil",

        delivery_basis="FOB",

        delivery_terms="Santos",

        tick_size=1,

        minimum_quantity=1,

        price_source=PriceSourceType.EXTERNAL,

        benchmark_symbol="ARABICA",

        benchmark_price=5100
    )

    # ---------------------------------------------------------------
    # PHYSICAL INVENTORY
    # ---------------------------------------------------------------

    exchange.add_lot(

        owner_account="SUPPLIER-001",

        symbol="RRX-RUBBER-TSR20",

        quantity_value=1000,

        location="Port Klang",

        origin="Malaysia",

        delivery_window="October 2026",

        certification="TSR20 CERTIFIED",

        condition="STANDARD"
    )

    exchange.add_lot(

        owner_account="SUPPLIER-001",

        symbol="RRX-COCOA",

        quantity_value=250,

        location="Tema",

        origin="Ghana",

        delivery_window="October 2026",

        certification="COCOA CERTIFIED",

        condition="STANDARD"
    )

    # ---------------------------------------------------------------
    # PRODUCT LISTING
    # ---------------------------------------------------------------

    exchange.create_listing(

        seller_account="SUPPLIER-001",

        symbol="RRX-RUBBER-TSR20",

        title="TSR20 Natural Rubber — October",

        description=(
            "Institutional physical TSR20 lot"
        ),

        quantity_value=250,

        asking_price=2325,

        location="Port Klang",

        delivery_window="October 2026",

        delivery_basis="FOB",

        certification="TSR20 CERTIFIED",

        condition="STANDARD",

        origin="Malaysia",

        minimum_order_quantity=10,

        expires_hours=168
    )


# ====================================================================
# MAIN
# ====================================================================

if __name__ == "__main__":

    seed_demo()

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
