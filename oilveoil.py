"""
============================================================
RHINO OLIVE OIL EXCHANGE
ROOX 1.0
============================================================

Institutional physical spot-market engine for bulk olive oil.

Designed around:

    - Extra Virgin Olive Oil
    - Virgin Olive Oil
    - Lampante
    - Refined Olive Oil
    - Olive Oil blends
    - Olive-pomace markets

Core systems:

    Market data
    Quality engine
    Origin basis
    Harvest basis
    Spot pricing
    Order books
    Matching engine
    Physical inventory
    Trade blotter
    VWAP
    Market snapshots

IMPORTANT:
The numerical premiums/discounts below are illustrative
software parameters, not live market quotations.

Production deployment should use validated laboratory,
market and regulatory data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from heapq import heappush, heappop
from typing import Dict, List, Optional
from uuid import uuid4


# ============================================================
# NUMERIC UTILITIES
# ============================================================

PRICE_Q = Decimal("0.01")
WEIGHT_Q = Decimal("0.001")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(
        PRICE_Q,
        rounding=ROUND_HALF_UP
    )


def weight(value) -> Decimal:
    return Decimal(str(value)).quantize(
        WEIGHT_Q,
        rounding=ROUND_HALF_UP
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# OIL CATEGORIES
# ============================================================

class OilGrade(str, Enum):

    EXTRA_VIRGIN = "EXTRA_VIRGIN"
    VIRGIN = "VIRGIN"
    LAMPANTE = "LAMPANTE"
    REFINED = "REFINED"
    OLIVE_OIL_BLEND = "OLIVE_OIL_BLEND"
    POMACE = "POMACE"


class Origin(str, Enum):

    SPAIN = "SPAIN"
    ITALY = "ITALY"
    GREECE = "GREECE"
    PORTUGAL = "PORTUGAL"
    TURKEY = "TURKEY"
    TUNISIA = "TUNISIA"
    MOROCCO = "MOROCCO"
    CROATIA = "CROATIA"


class Side(str, Enum):

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):

    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class Certification(str, Enum):

    STANDARD = "STANDARD"
    ORGANIC = "ORGANIC"
    PDO = "PDO"
    PGI = "PGI"
    ORGANIC_PDO = "ORGANIC_PDO"


# ============================================================
# OLIVE OIL LOT
# ============================================================

@dataclass
class OliveOilLot:

    lot_id: str

    grade: OilGrade

    origin: Origin

    region: str

    producer_id: str

    harvest_year: str

    quantity_kg: Decimal

    # --------------------------------------------------------
    # LABORATORY / QUALITY
    # --------------------------------------------------------

    free_acidity_percent: Decimal

    peroxide_value: Decimal

    k232: Decimal

    k270: Decimal

    delta_k: Decimal

    oleic_acid_percent: Decimal

    moisture_percent: Decimal

    impurities_percent: Decimal

    # --------------------------------------------------------
    # SENSORY
    # --------------------------------------------------------

    fruitiness_score: Decimal

    bitterness_score: Decimal

    pungency_score: Decimal

    sensory_defect_score: Decimal

    # --------------------------------------------------------
    # COMMERCIAL
    # --------------------------------------------------------

    certification: Certification = (
        Certification.STANDARD
    )

    storage_location: Optional[str] = None

    available_kg: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity_kg = weight(
            self.quantity_kg
        )

        self.available_kg = (
            self.quantity_kg
        )


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class OliveOilBenchmark:

    grade: OilGrade

    origin: Origin

    price_per_kg: Decimal

    currency: str = "EUR"

    timestamp: datetime = field(
        default_factory=utc_now
    )

    def update(self, price):

        self.price_per_kg = money(
            price
        )

        self.timestamp = utc_now()


# ============================================================
# PRICING ENGINE
# ============================================================

class OliveOilPricingEngine:

    """
    Theoretical price:

        benchmark
          × grade factor
          × acidity factor
          × peroxide factor
          × sensory factor
          × origin basis
          × harvest basis
          × certification factor

    This is an illustrative model.
    """

    def __init__(
        self,
        benchmarks: Dict[
            tuple,
            OliveOilBenchmark
        ]
    ):

        self.benchmarks = benchmarks

    # --------------------------------------------------------
    # GRADE
    # --------------------------------------------------------

    def grade_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        factors = {

            OilGrade.EXTRA_VIRGIN:
                Decimal("1.00"),

            OilGrade.VIRGIN:
                Decimal("0.82"),

            OilGrade.LAMPANTE:
                Decimal("0.58"),

            OilGrade.REFINED:
                Decimal("0.66"),

            OilGrade.OLIVE_OIL_BLEND:
                Decimal("0.70"),

            OilGrade.POMACE:
                Decimal("0.42")
        }

        return factors[
            lot.grade
        ]

    # --------------------------------------------------------
    # ACIDITY
    # --------------------------------------------------------

    def acidity_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        acidity = (
            lot.free_acidity_percent
        )

        if acidity <= Decimal("0.20"):
            return Decimal("1.10")

        if acidity <= Decimal("0.30"):
            return Decimal("1.06")

        if acidity <= Decimal("0.50"):
            return Decimal("1.03")

        if acidity <= Decimal("0.80"):
            return Decimal("1.00")

        if acidity <= Decimal("1.50"):
            return Decimal("0.96")

        if acidity <= Decimal("2.00"):
            return Decimal("0.90")

        return Decimal("0.80")

    # --------------------------------------------------------
    # PEROXIDE
    # --------------------------------------------------------

    def peroxide_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        pv = lot.peroxide_value

        if pv <= Decimal("8"):
            return Decimal("1.06")

        if pv <= Decimal("12"):
            return Decimal("1.03")

        if pv <= Decimal("20"):
            return Decimal("1.00")

        if pv <= Decimal("25"):
            return Decimal("0.94")

        return Decimal("0.85")

    # --------------------------------------------------------
    # SENSORY
    # --------------------------------------------------------

    def sensory_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        score = (

            lot.fruitiness_score
            * Decimal("0.45")

            + lot.bitterness_score
            * Decimal("0.15")

            + lot.pungency_score
            * Decimal("0.15")

            - lot.sensory_defect_score
            * Decimal("0.25")
        )

        if score >= Decimal("7"):
            return Decimal("1.12")

        if score >= Decimal("5"):
            return Decimal("1.06")

        if score >= Decimal("3"):
            return Decimal("1.00")

        if score >= Decimal("1"):
            return Decimal("0.92")

        return Decimal("0.82")

    # --------------------------------------------------------
    # ORIGIN BASIS
    # --------------------------------------------------------

    def origin_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        factors = {

            Origin.ITALY:
                Decimal("1.08"),

            Origin.GREECE:
                Decimal("1.05"),

            Origin.SPAIN:
                Decimal("1.00"),

            Origin.PORTUGAL:
                Decimal("1.02"),

            Origin.CROATIA:
                Decimal("1.08"),

            Origin.TUNISIA:
                Decimal("0.95"),

            Origin.MOROCCO:
                Decimal("0.96"),

            Origin.TURKEY:
                Decimal("0.97")
        }

        return factors[
            lot.origin
        ]

    # --------------------------------------------------------
    # HARVEST BASIS
    # --------------------------------------------------------

    def harvest_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        try:

            year = int(
                lot.harvest_year.split("-")[0]
            )

            current = utc_now().year

            age = current - year

        except Exception:

            age = 0

        if age <= 0:
            return Decimal("1.06")

        if age == 1:
            return Decimal("1.02")

        if age == 2:
            return Decimal("0.98")

        if age == 3:
            return Decimal("0.92")

        return Decimal("0.85")

    # --------------------------------------------------------
    # CERTIFICATION
    # --------------------------------------------------------

    def certification_factor(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        factors = {

            Certification.STANDARD:
                Decimal("1.00"),

            Certification.ORGANIC:
                Decimal("1.05"),

            Certification.PDO:
                Decimal("1.08"),

            Certification.PGI:
                Decimal("1.05"),

            Certification.ORGANIC_PDO:
                Decimal("1.12")
        }

        return factors[
            lot.certification
        ]

    # --------------------------------------------------------
    # FINAL PRICE
    # --------------------------------------------------------

    def spot_price(
        self,
        lot: OliveOilLot
    ) -> Decimal:

        key = (
            lot.grade,
            lot.origin
        )

        benchmark = self.benchmarks.get(
            key
        )

        if benchmark is None:

            raise ValueError(
                f"No benchmark for "
                f"{lot.grade}/{lot.origin}"
            )

        price = (

            benchmark.price_per_kg

            * self.grade_factor(lot)

            * self.acidity_factor(lot)

            * self.peroxide_factor(lot)

            * self.sensory_factor(lot)

            * self.origin_factor(lot)

            * self.harvest_factor(lot)

            * self.certification_factor(lot)
        )

        return money(
            max(
                price,
                Decimal("0.01")
            )
        )


# ============================================================
# ORDER
# ============================================================

@dataclass(order=True)
class Order:

    sort_index: tuple = field(
        init=False,
        repr=False
    )

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    order_type: OrderType

    price: Optional[Decimal]

    quantity_kg: Decimal

    remaining_kg: Decimal

    timestamp: datetime = field(
        default_factory=utc_now
    )

    status: OrderStatus = (
        OrderStatus.OPEN
    )

    def __post_init__(self):

        if self.side == Side.BUY:

            self.sort_index = (

                -self.price
                if self.price is not None
                else Decimal("0"),

                self.timestamp.timestamp()
            )

        else:

            self.sort_index = (

                self.price
                if self.price is not None
                else Decimal("0"),

                self.timestamp.timestamp()
            )


# ============================================================
# TRADE
# ============================================================

@dataclass
class OliveOilTrade:

    trade_id: str

    lot_id: str

    buyer_id: str

    seller_id: str

    grade: OilGrade

    origin: Origin

    price_per_kg: Decimal

    quantity_kg: Decimal

    timestamp: datetime = field(
        default_factory=utc_now
    )

    @property
    def notional(self):

        return money(
            self.price_per_kg
            * self.quantity_kg
        )


# ============================================================
# ORDER BOOK
# ============================================================

class OliveOilOrderBook:

    def __init__(
        self,
        lot_id: str
    ):

        self.lot_id = lot_id

        self.bids: List[Order] = []
        self.asks: List[Order] = []

        self.orders: Dict[
            str,
            Order
        ] = {}

        self.trades: List[
            OliveOilTrade
        ] = []

    # --------------------------------------------------------
    # ADD
    # --------------------------------------------------------

    def add(
        self,
        order: Order
    ):

        self.orders[
            order.order_id
        ] = order

        if order.side == Side.BUY:

            heappush(
                self.bids,
                order
            )

        else:

            heappush(
                self.asks,
                order
            )

    # --------------------------------------------------------
    # BEST BID
    # --------------------------------------------------------

    def best_bid(self):

        while self.bids:

            order = self.bids[0]

            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELLED
            ):

                heappop(
                    self.bids
                )

            else:

                return order

        return None

    # --------------------------------------------------------
    # BEST ASK
    # --------------------------------------------------------

    def best_ask(self):

        while self.asks:

            order = self.asks[0]

            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELLED
            ):

                heappop(
                    self.asks
                )

            else:

                return order

        return None

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    def match(
        self,
        lot: OliveOilLot
    ):

        trades = []

        while True:

            bid = self.best_bid()
            ask = self.best_ask()

            if not bid or not ask:
                break

            buy_crosses = (

                bid.order_type
                == OrderType.MARKET

                or bid.price >= ask.price
            )

            sell_crosses = (

                ask.order_type
                == OrderType.MARKET

                or ask.price <= bid.price
            )

            if not (
                buy_crosses
                and sell_crosses
            ):

                break

            traded_quantity = min(

                bid.remaining_kg,

                ask.remaining_kg
            )

            # Price-time priority
            if (
                bid.timestamp
                <= ask.timestamp
            ):

                execution_price = (

                    ask.price
                    if ask.price is not None
                    else bid.price
                )

            else:

                execution_price = (

                    bid.price
                    if bid.price is not None
                    else ask.price
                )

            if execution_price is None:

                raise ValueError(
                    "Cannot execute trade"
                )

            trade = OliveOilTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=self.lot_id,

                buyer_id=bid.trader_id,

                seller_id=ask.trader_id,

                grade=lot.grade,

                origin=lot.origin,

                price_per_kg=money(
                    execution_price
                ),

                quantity_kg=weight(
                    traded_quantity
                )
            )

            trades.append(
                trade
            )

            self.trades.append(
                trade
            )

            bid.remaining_kg -= (
                traded_quantity
            )

            ask.remaining_kg -= (
                traded_quantity
            )

            self.update_status(
                bid
            )

            self.update_status(
                ask
            )

        return trades

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    @staticmethod
    def update_status(
        order: Order
    ):

        if order.remaining_kg <= 0:

            order.remaining_kg = (
                Decimal("0")
            )

            order.status = (
                OrderStatus.FILLED
            )

        elif (
            order.remaining_kg
            < order.quantity_kg
        ):

            order.status = (
                OrderStatus.PARTIALLY_FILLED
            )

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    def cancel(
        self,
        order_id: str
    ):

        if order_id not in self.orders:

            raise KeyError(
                "Unknown order"
            )

        self.orders[
            order_id
        ].status = (
            OrderStatus.CANCELLED
        )


# ============================================================
# RHINO OLIVE OIL EXCHANGE
# ============================================================

class RhinoOliveOilExchange:

    def __init__(self):

        self.lots: Dict[
            str,
            OliveOilLot
        ] = {}

        self.books: Dict[
            str,
            OliveOilOrderBook
        ] = {}

        self.trades: List[
            OliveOilTrade
        ] = []

        # ----------------------------------------------------
        # Illustrative benchmarks
        # ----------------------------------------------------

        self.benchmarks = {

            (
                OilGrade.EXTRA_VIRGIN,
                Origin.SPAIN
            ):
                OliveOilBenchmark(
                    OilGrade.EXTRA_VIRGIN,
                    Origin.SPAIN,
                    Decimal("6.80")
                ),

            (
                OilGrade.EXTRA_VIRGIN,
                Origin.ITALY
            ):
                OliveOilBenchmark(
                    OilGrade.EXTRA_VIRGIN,
                    Origin.ITALY,
                    Decimal("7.60")
                ),

            (
                OilGrade.EXTRA_VIRGIN,
                Origin.GREECE
            ):
                OliveOilBenchmark(
                    OilGrade.EXTRA_VIRGIN,
                    Origin.GREECE,
                    Decimal("7.20")
                ),

            (
                OilGrade.EXTRA_VIRGIN,
                Origin.PORTUGAL
            ):
                OliveOilBenchmark(
                    OilGrade.EXTRA_VIRGIN,
                    Origin.PORTUGAL,
                    Decimal("6.90")
                ),

            (
                OilGrade.VIRGIN,
                Origin.SPAIN
            ):
                OliveOilBenchmark(
                    OilGrade.VIRGIN,
                    Origin.SPAIN,
                    Decimal("5.30")
                ),

            (
                OilGrade.LAMPANTE,
                Origin.SPAIN
            ):
                OliveOilBenchmark(
                    OilGrade.LAMPANTE,
                    Origin.SPAIN,
                    Decimal("3.40")
                ),

            (
                OilGrade.REFINED,
                Origin.SPAIN
            ):
                OliveOilBenchmark(
                    OilGrade.REFINED,
                    Origin.SPAIN,
                    Decimal("4.00")
                )
        }

        self.pricing = (
            OliveOilPricingEngine(
                self.benchmarks
            )
        )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    def register_lot(
        self,
        lot: OliveOilLot
    ):

        self.lots[
            lot.lot_id
        ] = lot

        self.books[
            lot.lot_id
        ] = OliveOilOrderBook(
            lot.lot_id
        )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    def spot_price(
        self,
        lot_id: str
    ):

        return self.pricing.spot_price(
            self.lots[lot_id]
        )

    # --------------------------------------------------------
    # ORDER
    # --------------------------------------------------------

    def submit_order(
        self,
        trader_id: str,
        lot_id: str,
        side: Side,
        order_type: OrderType,
        quantity_kg: Decimal,
        price: Optional[Decimal] = None
    ):

        lot = self.lots[
            lot_id
        ]

        quantity_kg = weight(
            quantity_kg
        )

        if quantity_kg <= 0:

            raise ValueError(
                "Quantity must be positive"
            )

        if (
            side == Side.SELL
            and quantity_kg
            > lot.available_kg
        ):

            raise ValueError(
                "Insufficient physical inventory"
            )

        if (
            order_type == OrderType.LIMIT
            and (
                price is None
                or price <= 0
            )
        ):

            raise ValueError(
                "Limit order requires price"
            )

        order = Order(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            order_type=order_type,

            price=(
                money(price)
                if price is not None
                else None
            ),

            quantity_kg=quantity_kg,

            remaining_kg=quantity_kg
        )

        self.books[
            lot_id
        ].add(
            order
        )

        trades = self.books[
            lot_id
        ].match(
            lot
        )

        for trade in trades:

            lot.available_kg -= (
                trade.quantity_kg
            )

        self.trades.extend(
            trades
        )

        return order

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------

    def vwap(
        self,
        lot_id: str
    ):

        trades = self.books[
            lot_id
        ].trades

        if not trades:
            return None

        value = sum(

            (
                t.price_per_kg
                * t.quantity_kg

                for t in trades
            ),

            Decimal("0")
        )

        volume = sum(

            (
                t.quantity_kg

                for t in trades
            ),

            Decimal("0")
        )

        if volume == 0:
            return None

        return money(
            value / volume
        )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    def snapshot(
        self,
        lot_id: str
    ):

        lot = self.lots[
            lot_id
        ]

        book = self.books[
            lot_id
        ]

        bid = book.best_bid()
        ask = book.best_ask()

        last_trade = (

            book.trades[-1]

            if book.trades

            else None
        )

        vwap = self.vwap(
            lot_id
        )

        return {

            "instrument":
                lot_id,

            "grade":
                lot.grade.value,

            "origin":
                lot.origin.value,

            "region":
                lot.region,

            "harvest":
                lot.harvest_year,

            "theoretical_spot":
                str(
                    self.spot_price(
                        lot_id
                    )
                ),

            "best_bid":
                (
                    str(bid.price)
                    if bid
                    else None
                ),

            "best_ask":
                (
                    str(ask.price)
                    if ask
                    else None
                ),

            "last_trade":
                (
                    str(
                        last_trade.price_per_kg
                    )
                    if last_trade
                    else None
                ),

            "vwap":
                (
                    str(vwap)
                    if vwap
                    else None
                ),

            "available_kg":
                str(
                    lot.available_kg
                ),

            "free_acidity":
                str(
                    lot.free_acidity_percent
                ),

            "peroxide_value":
                str(
                    lot.peroxide_value
                ),

            "fruitiness":
                str(
                    lot.fruitiness_score
                ),

            "sensory_defects":
                str(
                    lot.sensory_defect_score
                ),

            "certification":
                lot.certification.value,

            "timestamp":
                utc_now().isoformat()
        }


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    exchange = (
        RhinoOliveOilExchange()
    )

    # --------------------------------------------------------
    # SAMPLE SPANISH EVOO LOT
    # --------------------------------------------------------

    lot = OliveOilLot(

        lot_id="ROOX-EVOO-ES-2026-001",

        grade=OilGrade.EXTRA_VIRGIN,

        origin=Origin.SPAIN,

        region="Andalusia",

        producer_id="OLIVE-PRODUCER-001",

        harvest_year="2025-2026",

        quantity_kg=Decimal(
            "100000"
        ),

        free_acidity_percent=Decimal(
            "0.22"
        ),

        peroxide_value=Decimal(
            "7.8"
        ),

        k232=Decimal(
            "1.55"
        ),

        k270=Decimal(
            "0.12"
        ),

        delta_k=Decimal(
            "0.001"
        ),

        oleic_acid_percent=Decimal(
            "76.2"
        ),

        moisture_percent=Decimal(
            "0.10"
        ),

        impurities_percent=Decimal(
            "0.03"
        ),

        fruitiness_score=Decimal(
            "7.5"
        ),

        bitterness_score=Decimal(
            "5.5"
        ),

        pungency_score=Decimal(
            "6.0"
        ),

        sensory_defect_score=Decimal(
            "0"
        ),

        certification=(
            Certification.ORGANIC
        ),

        storage_location=(
            "SEVILLE-BULK-TANK-04"
        )
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT PRICE
    # --------------------------------------------------------

    print()
    print(
        "=========================================="
    )
    print(
        " RHINO OLIVE OIL EXCHANGE"
    )
    print(
        " ROOX — PHYSICAL SPOT MARKET"
    )
    print(
        "=========================================="
    )

    spot = exchange.spot_price(
        lot.lot_id
    )

    print(
        "THEORETICAL SPOT:",
        spot,
        "EUR/kg"
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-FOOD-001",

        lot_id=lot.lot_id,

        side=Side.BUY,

        order_type=OrderType.LIMIT,

        quantity_kg=Decimal(
            "25000"
        ),

        price=Decimal(
            "7.60"
        )
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="ANDALUSIA-OIL-001",

        lot_id=lot.lot_id,

        side=Side.SELL,

        order_type=OrderType.LIMIT,

        quantity_kg=Decimal(
            "15000"
        ),

        price=Decimal(
            "7.45"
        )
    )

    # --------------------------------------------------------
    # MARKET SNAPSHOT
    # --------------------------------------------------------

    print()
    print(
        "MARKET SNAPSHOT"
    )
    print(
        "------------------------------------------"
    )

    snapshot = exchange.snapshot(
        lot.lot_id
    )

    for key, value in snapshot.items():

        print(
            f"{key:25} {value}"
        )

    # --------------------------------------------------------
    # TRADE BLOTTER
    # --------------------------------------------------------

    print()
    print(
        "TRADE BLOTTER"
    )
    print(
        "------------------------------------------"
    )

    for trade in exchange.trades:

        print(

            trade.grade.value,
            "|",
            trade.origin.value,
            "|",
            trade.quantity_kg,
            "kg @",
            trade.price_per_kg,
            "EUR/kg",
            "| NOTIONAL:",
            trade.notional,
            "EUR"
        )
