"""
RHINOBANK WHISKY EXCHANGE
Institutional B2B physical-whisky marketplace.

Architecture:

    Asset Registry
          |
    Market Data
          |
    Order Book
          |
    Matching Engine
          |
    Trade
          |
    Escrow
          |
    Warehouse Transfer
          |
    Settlement
          |
    Audit Ledger
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
import hashlib
import uuid


D = Decimal


# ============================================================
# ENUMS
# ============================================================

class AssetType(Enum):

    CASK = "CASK"
    BOTTLE = "BOTTLE"
    CASE = "CASE"
    BULK = "BULK"


class Side(Enum):

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(Enum):

    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class VerificationStatus(Enum):

    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


# ============================================================
# WHISKY ASSET
# ============================================================

@dataclass
class WhiskyAsset:

    asset_id: str

    asset_type: AssetType

    distillery: str

    whisky_type: str

    distillation_year: Optional[int]

    age_years: Optional[Decimal]

    cask_type: Optional[str]

    cask_number: Optional[str]

    volume_litres: Decimal

    abv: Decimal

    warehouse: str

    warehousekeeper: str

    owner_account: str

    provenance_score: Decimal

    verification: VerificationStatus

    insured: bool

    currency: str = "GBP"

    created_at: datetime = field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )


# ============================================================
# B2B ACCOUNT
# ============================================================

@dataclass
class ExchangeAccount:

    account_id: str

    legal_name: str

    jurisdiction: str

    verified: bool

    permissions: set[str]

    cash_balance: Decimal = D("0")

    reserved_cash: Decimal = D("0")


# ============================================================
# ORDER
# ============================================================

@dataclass
class Order:

    order_id: str

    account_id: str

    asset_id: str

    side: Side

    order_type: OrderType

    price: Decimal

    quantity: Decimal

    remaining: Decimal

    timestamp: datetime

    status: OrderStatus = OrderStatus.OPEN

    warehouse_verified: bool = False


# ============================================================
# TRADE
# ============================================================

@dataclass
class Trade:

    trade_id: str

    buy_order: str

    sell_order: str

    asset_id: str

    price: Decimal

    quantity: Decimal

    buyer: str

    seller: str

    timestamp: datetime

    settlement_status: str = "PENDING"


# ============================================================
# ORDER BOOK
# ============================================================

class OrderBook:

    def __init__(self, asset_id: str):

        self.asset_id = asset_id

        self.bids: List[Order] = []

        self.asks: List[Order] = []


    def add(self, order: Order):

        if order.side == Side.BUY:

            self.bids.append(order)

            self.bids.sort(
                key=lambda x: (
                    -x.price,
                    x.timestamp
                )
            )

        else:

            self.asks.append(order)

            self.asks.sort(
                key=lambda x: (
                    x.price,
                    x.timestamp
                )
            )


    def best_bid(self):

        return (
            self.bids[0]
            if self.bids
            else None
        )


    def best_ask(self):

        return (
            self.asks[0]
            if self.asks
            else None
        )


# ============================================================
# EXCHANGE
# ============================================================

class RhinoWhiskyExchange:

    def __init__(self):

        self.accounts: Dict[
            str,
            ExchangeAccount
        ] = {}

        self.assets: Dict[
            str,
            WhiskyAsset
        ] = {}

        self.books: Dict[
            str,
            OrderBook
        ] = {}

        self.orders: Dict[
            str,
            Order
        ] = {}

        self.trades: Dict[
            str,
            Trade
        ] = {}


    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    def register_account(
        self,
        account: ExchangeAccount
    ):

        if account.account_id in self.accounts:

            raise ValueError(
                "Account already exists"
            )

        self.accounts[
            account.account_id
        ] = account


    # --------------------------------------------------------
    # ASSET
    # --------------------------------------------------------

    def register_asset(
        self,
        asset: WhiskyAsset
    ):

        if not asset.insured:

            raise ValueError(
                "Asset must be insured"
            )

        if (
            asset.verification
            != VerificationStatus.VERIFIED
        ):

            raise ValueError(
                "Asset not verified"
            )

        self.assets[
            asset.asset_id
        ] = asset

        self.books[
            asset.asset_id
        ] = OrderBook(
            asset.asset_id
        )


    # --------------------------------------------------------
    # ORDER
    # --------------------------------------------------------

    def submit_order(
        self,
        account_id: str,
        asset_id: str,
        side: Side,
        price: Decimal,
        quantity: Decimal
    ) -> Order:

        account = self.accounts[
            account_id
        ]

        asset = self.assets[
            asset_id
        ]


        if not account.verified:

            raise PermissionError(
                "Institution not verified"
            )


        if (
            asset.verification
            != VerificationStatus.VERIFIED
        ):

            raise ValueError(
                "Asset verification failed"
            )


        if quantity <= 0:

            raise ValueError(
                "Invalid quantity"
            )


        if price <= 0:

            raise ValueError(
                "Invalid price"
            )


        order = Order(

            order_id =
                str(uuid.uuid4()),

            account_id =
                account_id,

            asset_id =
                asset_id,

            side =
                side,

            order_type =
                OrderType.LIMIT,

            price =
                price,

            quantity =
                quantity,

            remaining =
                quantity,

            timestamp =
                datetime.now(timezone.utc),

            warehouse_verified =
                True

        )


        self.orders[
            order.order_id
        ] = order


        self.books[
            asset_id
        ].add(order)


        self.match(
            asset_id
        )


        return order


    # --------------------------------------------------------
    # MATCHING
    # --------------------------------------------------------

    def match(
        self,
        asset_id: str
    ):

        book =
            self.books[
                asset_id
            ]


        while (

            book.bids
            and
            book.asks

        ):

            bid =
                book.bids[0]

            ask =
                book.asks[0]


            if bid.price < ask.price:

                break


            quantity = min(
                bid.remaining,
                ask.remaining
            )


            execution_price =
                ask.price


            self.execute_trade(

                bid,
                ask,

                execution_price,

                quantity

            )


            bid.remaining -= quantity

            ask.remaining -= quantity


            if bid.remaining == 0:

                bid.status =
                    OrderStatus.FILLED

                book.bids.pop(0)

            else:

                bid.status =
                    OrderStatus.PARTIAL


            if ask.remaining == 0:

                ask.status =
                    OrderStatus.FILLED

                book.asks.pop(0)

            else:

                ask.status =
                    OrderStatus.PARTIAL


    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    def execute_trade(
        self,
        bid: Order,
        ask: Order,
        price: Decimal,
        quantity: Decimal
    ):

        buyer =
            self.accounts[
                bid.account_id
            ]

        seller =
            self.accounts[
                ask.account_id
            ]


        notional =
            price * quantity


        if buyer.cash_balance < notional:

            raise RuntimeError(
                "Insufficient buying power"
            )


        buyer.cash_balance -= notional

        seller.cash_balance += notional


        trade = Trade(

            trade_id =
                hashlib.sha256(
                    (
                        bid.order_id
                        +
                        ask.order_id
                        +
                        str(datetime.now())
                    ).encode()
                ).hexdigest(),

            buy_order =
                bid.order_id,

            sell_order =
                ask.order_id,

            asset_id =
                bid.asset_id,

            price =
                price,

            quantity =
                quantity,

            buyer =
                buyer.account_id,

            seller =
                seller.account_id,

            timestamp =
                datetime.now(timezone.utc),

            settlement_status =
                "EXECUTED"

        )


        self.trades[
            trade.trade_id
        ] = trade


        print(
            f"[TRADE] "
            f"{trade.asset_id} "
            f"{quantity} "
            f"@ £{price}"
        )
