"""
============================================================
RHINO HONEY EXCHANGE
Industrial Physical Honey Spot Market
============================================================

Physical commodity exchange engine for bulk industrial honey.

Features:
    - Honey lot registration
    - Floral/origin classification
    - Laboratory quality attributes
    - Quality-adjusted spot pricing
    - Bid/ask order book
    - Price/time matching
    - Physical inventory
    - Trade execution
    - Market snapshots
    - VWAP
    - Quality premiums/discounts

All monetary values use Decimal.
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
# CONFIGURATION
# ============================================================

PRICE_Q = Decimal("0.01")
WEIGHT_Q = Decimal("0.001")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(
        PRICE_Q,
        rounding=ROUND_HALF_UP
    )


def tonnes(value) -> Decimal:
    return Decimal(str(value)).quantize(
        WEIGHT_Q,
        rounding=ROUND_HALF_UP
    )


def now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# ENUMS
# ============================================================

class HoneyType(str, Enum):

    CLOVER = "CLOVER"
    ACACIA = "ACACIA"
    MANUKA = "MANUKA"
    WILDFLOWER = "WILDFLOWER"
    SUNFLOWER = "SUNFLOWER"
    ORANGE_BLOSSOM = "ORANGE_BLOSSOM"
    EUCALYPTUS = "EUCALYPTUS"
    RAPSEED = "RAPESEED"
    LINDEN = "LINDEN"
    MULTIFLORAL = "MULTIFLORAL"


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
    FAIRTRADE = "FAIRTRADE"
    ORGANIC_FAIRTRADE = "ORGANIC_FAIRTRADE"


# ============================================================
# HONEY LOT
# ============================================================

@dataclass
class HoneyLot:

    lot_id: str

    honey_type: HoneyType

    country_of_origin: str

    region: str

    producer_id: str

    harvest_date: datetime

    quantity_kg: Decimal

    # Laboratory characteristics
    moisture_percent: Decimal

    hmf_mg_kg: Decimal

    diastase_number: Decimal

    colour_mm: Decimal

    sucrose_percent: Decimal

    electrical_conductivity: Decimal

    certification: Certification = Certification.STANDARD

    storage_location: Optional[str] = None

    available_kg: Decimal = field(init=False)

    def __post_init__(self):

        self.quantity_kg = Decimal(
            str(self.quantity_kg)
        )

        self.available_kg = self.quantity_kg


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class HoneyBenchmark:

    honey_type: HoneyType

    price_per_kg: Decimal

    currency: str = "GBP"

    timestamp: datetime = field(
        default_factory=now
    )

    def update(self, price):

        self.price_per_kg = money(price)

        self.timestamp = now()


# ============================================================
# PRICING ENGINE
# ============================================================

class HoneyPricingEngine:

    """
    Theoretical spot price:

        benchmark
        × moisture adjustment
        × HMF adjustment
        × enzyme adjustment
        × colour/origin adjustment
        × certification adjustment
        × floral premium
    """

    def __init__(
        self,
        benchmarks: Dict[
            HoneyType,
            HoneyBenchmark
        ]
    ):

        self.benchmarks = benchmarks

    # --------------------------------------------------------
    # MOISTURE
    # --------------------------------------------------------

    def moisture_factor(
        self,
        lot: HoneyLot
    ) -> Decimal:

        m = lot.moisture_percent

        # Around 17-18% is treated as favourable
        if m <= Decimal("17.5"):
            return Decimal("1.04")

        if m <= Decimal("18.5"):
            return Decimal("1.00")

        if m <= Decimal("19.5"):
            return Decimal("0.96")

        if m <= Decimal("20.5"):
            return Decimal("0.90")

        return Decimal("0.80")

    # --------------------------------------------------------
    # HMF
    # --------------------------------------------------------

    def hmf_factor(
        self,
        lot: HoneyLot
    ) -> Decimal:

        hmf = lot.hmf_mg_kg

        if hmf <= Decimal("10"):
            return Decimal("1.04")

        if hmf <= Decimal("20"):
            return Decimal("1.00")

        if hmf <= Decimal("30"):
            return Decimal("0.95")

        if hmf <= Decimal("40"):
            return Decimal("0.88")

        return Decimal("0.75")

    # --------------------------------------------------------
    # DIASTASE
    # --------------------------------------------------------

    def diastase_factor(
        self,
        lot: HoneyLot
    ) -> Decimal:

        d = lot.diastase_number

        if d >= Decimal("15"):
            return Decimal("1.04")

        if d >= Decimal("10"):
            return Decimal("1.00")

        if d >= Decimal("8"):
            return Decimal("0.96")

        return Decimal("0.90")

    # --------------------------------------------------------
    # FLORAL PREMIUM
    # --------------------------------------------------------

    def floral_factor(
        self,
        lot: HoneyLot
    ) -> Decimal:

        premiums = {

            HoneyType.ACACIA:
                Decimal("1.18"),

            HoneyType.MANUKA:
                Decimal("1.30"),

            HoneyType.ORANGE_BLOSSOM:
                Decimal("1.10"),

            HoneyType.CLOVER:
                Decimal("1.02"),

            HoneyType.WILDFLOWER:
                Decimal("1.00"),

            HoneyType.SUNFLOWER:
                Decimal("0.98"),

            HoneyType.RAPESEED:
                Decimal("0.94"),

            HoneyType.EUCALYPTUS:
                Decimal("1.03"),

            HoneyType.LINDEN:
                Decimal("1.06"),

            HoneyType.MULTIFLORAL:
                Decimal("1.00")
        }

        return premiums.get(
            lot.honey_type,
            Decimal("1.00")
        )

    # --------------------------------------------------------
    # CERTIFICATION
    # --------------------------------------------------------

    def certification_factor(
        self,
        lot: HoneyLot
    ) -> Decimal:

        factors = {

            Certification.STANDARD:
                Decimal("1.00"),

            Certification.ORGANIC:
                Decimal("1.07"),

            Certification.FAIRTRADE:
                Decimal("1.04"),

            Certification.ORGANIC_FAIRTRADE:
                Decimal("1.11")
        }

        return factors[
            lot.certification
        ]

    # --------------------------------------------------------
    # COLOUR
    # --------------------------------------------------------

    def colour_factor(
        self,
        lot: HoneyLot
    ) -> Decimal:

        colour = lot.colour_mm

        # Lower colour value = lighter honey
        if colour <= Decimal("20"):
            return Decimal("1.05")

        if colour <= Decimal("40"):
            return Decimal("1.02")

        if colour <= Decimal("80"):
            return Decimal("1.00")

        if colour <= Decimal("120"):
            return Decimal("0.97")

        return Decimal("0.93")

    # --------------------------------------------------------
    # FINAL SPOT PRICE
    # --------------------------------------------------------

    def spot_price(
        self,
        lot: HoneyLot
    ) -> Decimal:

        benchmark = self.benchmarks[
            lot.honey_type
        ].price_per_kg

        price = (
            benchmark
            * self.moisture_factor(lot)
            * self.hmf_factor(lot)
            * self.diastase_factor(lot)
            * self.floral_factor(lot)
            * self.certification_factor(lot)
            * self.colour_factor(lot)
        )

        return money(
            max(price, Decimal("0.01"))
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
        default_factory=now
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
class HoneyTrade:

    trade_id: str

    lot_id: str

    buyer_id: str

    seller_id: str

    honey_type: HoneyType

    price_per_kg: Decimal

    quantity_kg: Decimal

    timestamp: datetime = field(
        default_factory=now
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

class HoneyOrderBook:

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
            HoneyTrade
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

                heappop(self.bids)

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

                heappop(self.asks)

            else:

                return order

        return None

    # --------------------------------------------------------
    # MATCHING ENGINE
    # --------------------------------------------------------

    def match(
        self,
        honey_type: HoneyType
    ):

        trades = []

        while True:

            bid = self.best_bid()
            ask = self.best_ask()

            if not bid or not ask:
                break

            bid_crosses = (
                bid.order_type == OrderType.MARKET
                or bid.price >= ask.price
            )

            ask_crosses = (
                ask.order_type == OrderType.MARKET
                or ask.price <= bid.price
            )

            if not (
                bid_crosses
                and ask_crosses
            ):

                break

            quantity = min(
                bid.remaining_kg,
                ask.remaining_kg
            )

            # Passive order determines price
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
                    "No executable price"
                )

            trade = HoneyTrade(

                trade_id=str(uuid4()),

                lot_id=self.lot_id,

                buyer_id=bid.trader_id,

                seller_id=ask.trader_id,

                honey_type=honey_type,

                price_per_kg=money(
                    execution_price
                ),

                quantity_kg=quantity
            )

            self.trades.append(
                trade
            )

            trades.append(
                trade
            )

            bid.remaining_kg -= quantity
            ask.remaining_kg -= quantity

            self.update_status(bid)
            self.update_status(ask)

        return trades

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    @staticmethod
    def update_status(
        order: Order
    ):

        if order.remaining_kg <= 0:

            order.remaining_kg = Decimal("0")

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
        ].status = OrderStatus.CANCELLED


# ============================================================
# RHINO HONEY EXCHANGE
# ============================================================

class RhinoHoneyExchange:

    def __init__(self):

        self.lots: Dict[
            str,
            HoneyLot
        ] = {}

        self.books: Dict[
            str,
            HoneyOrderBook
        ] = {}

        self.trades: List[
            HoneyTrade
        ] = []

        self.benchmarks = {

            HoneyType.CLOVER:
                HoneyBenchmark(
                    HoneyType.CLOVER,
                    Decimal("4.20")
                ),

            HoneyType.ACACIA:
                HoneyBenchmark(
                    HoneyType.ACACIA,
                    Decimal("5.80")
                ),

            HoneyType.MANUKA:
                HoneyBenchmark(
                    HoneyType.MANUKA,
                    Decimal("12.00")
                ),

            HoneyType.WILDFLOWER:
                HoneyBenchmark(
                    HoneyType.WILDFLOWER,
                    Decimal("3.90")
                ),

            HoneyType.SUNFLOWER:
                HoneyBenchmark(
                    HoneyType.SUNFLOWER,
                    Decimal("3.40")
                ),

            HoneyType.ORANGE_BLOSSOM:
                HoneyBenchmark(
                    HoneyType.ORANGE_BLOSSOM,
                    Decimal("4.80")
                ),

            HoneyType.EUCALYPTUS:
                HoneyBenchmark(
                    HoneyType.EUCALYPTUS,
                    Decimal("4.10")
                ),

            HoneyType.RAPESEED:
                HoneyBenchmark(
                    HoneyType.RAPESEED,
                    Decimal("3.20")
                ),

            HoneyType.LINDEN:
                HoneyBenchmark(
                    HoneyType.LINDEN,
                    Decimal("4.60")
                ),

            HoneyType.MULTIFLORAL:
                HoneyBenchmark(
                    HoneyType.MULTIFLORAL,
                    Decimal("3.80")
                )
        }

        self.pricing = HoneyPricingEngine(
            self.benchmarks
        )

    # --------------------------------------------------------
    # REGISTER LOT
    # --------------------------------------------------------

    def register_lot(
        self,
        lot: HoneyLot
    ):

        self.lots[
            lot.lot_id
        ] = lot

        self.books[
            lot.lot_id
        ] = HoneyOrderBook(
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

        quantity_kg = Decimal(
            str(quantity_kg)
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
                "Insufficient honey inventory"
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

            order_id=str(uuid4()),

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
        ].add(order)

        trades = self.books[
            lot_id
        ].match(
            lot.honey_type
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

        total_value = sum(
            (
                t.price_per_kg
                * t.quantity_kg
                for t in trades
            ),
            Decimal("0")
        )

        total_volume = sum(
            (
                t.quantity_kg
                for t in trades
            ),
            Decimal("0")
        )

        if total_volume == 0:

            return None

        return money(
            total_value
            / total_volume
        )

    # --------------------------------------------------------
    # MARKET SNAPSHOT
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

        return {

            "lot":
                lot_id,

            "commodity":
                lot.honey_type.value,

            "origin":
                lot.country_of_origin,

            "region":
                lot.region,

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
                        book.trades[-1]
                        .price_per_kg
                    )
                    if book.trades
                    else None
                ),

            "vwap":
                (
                    str(
                        self.vwap(
                            lot_id
                        )
                    )
                    if self.vwap(lot_id)
                    else None
                ),

            "available_kg":
                str(
                    lot.available_kg
                ),

            "moisture_percent":
                str(
                    lot.moisture_percent
                ),

            "hmf_mg_kg":
                str(
                    lot.hmf_mg_kg
                ),

            "diastase":
                str(
                    lot.diastase_number
                ),

            "certification":
                lot.certification.value,

            "timestamp":
                now().isoformat()
        }


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":

    exchange = RhinoHoneyExchange()

    # --------------------------------------------------------
    # CREATE INDUSTRIAL CLOVER HONEY LOT
    # --------------------------------------------------------

    lot = HoneyLot(

        lot_id="RHX-CLV-20260901-001",

        honey_type=HoneyType.CLOVER,

        country_of_origin="United Kingdom",

        region="East Anglia",

        producer_id="PRODUCER-UK-001",

        harvest_date=(
            now()
        ),

        quantity_kg=Decimal("25000"),

        moisture_percent=Decimal("17.4"),

        hmf_mg_kg=Decimal("8"),

        diastase_number=Decimal("16"),

        colour_mm=Decimal("25"),

        sucrose_percent=Decimal("3.2"),

        electrical_conductivity=Decimal("0.35"),

        certification=Certification.ORGANIC,

        storage_location="RHX-WAREHOUSE-01"
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # THEORETICAL PRICE
    # --------------------------------------------------------

    print(
        "\n======================================"
    )

    print(
        " RHINO HONEY EXCHANGE"
    )

    print(
        " INDUSTRIAL SPOT MARKET"
    )

    print(
        "======================================"
    )

    spot = exchange.spot_price(
        lot.lot_id
    )

    print(
        "THEORETICAL SPOT:",
        spot,
        "GBP/kg"
    )

    # --------------------------------------------------------
    # BUY ORDER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-FOODS-001",

        lot_id=lot.lot_id,

        side=Side.BUY,

        order_type=OrderType.LIMIT,

        quantity_kg=Decimal("10000"),

        price=Decimal("5.10")
    )

    # --------------------------------------------------------
    # SELL ORDER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="HONEY-PRODUCER-001",

        lot_id=lot.lot_id,

        side=Side.SELL,

        order_type=OrderType.LIMIT,

        quantity_kg=Decimal("6000"),

        price=Decimal("4.95")
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    snapshot = exchange.snapshot(
        lot.lot_id
    )

    print(
        "\nMARKET SNAPSHOT"
    )

    print(
        "--------------------------------------"
    )

    for key, value in snapshot.items():

        print(
            f"{key:25} {value}"
        )

    # --------------------------------------------------------
    # TRADE BLOTER
    # --------------------------------------------------------

    print(
        "\nTRADE BLOTTER"
    )

    print(
        "--------------------------------------"
    )

    for trade in exchange.trades:

        print(
            trade.honey_type.value,
            "|",
            trade.quantity_kg,
            "kg",
            "|",
            trade.price_per_kg,
            "GBP/kg",
            "|",
            trade.notional,
            "GBP"
        )
