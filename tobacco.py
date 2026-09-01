"""
============================================================
RHINO TOBACCO EXCHANGE
RTX 1.0
============================================================

Institutional physical spot-market engine for raw tobacco
leaf.

NOT a finished-tobacco, cigarette, nicotine or retail system.

Markets:
    - Flue-cured Virginia
    - Burley
    - Oriental
    - Dark air-cured

Features:
    - Tobacco lot registry
    - Quality-adjusted pricing
    - Origin basis
    - Crop-year basis
    - Grade model
    - Order books
    - Price/time matching
    - Physical inventory
    - Trade blotter
    - VWAP
    - Market snapshots

Numerical premiums are illustrative software parameters.
Production deployment requires validated market data and
applicable regulatory/compliance controls.
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
# UTILITIES
# ============================================================

PRICE_Q = Decimal("0.01")
WEIGHT_Q = Decimal("0.001")


def money(value):
    return Decimal(str(value)).quantize(
        PRICE_Q,
        rounding=ROUND_HALF_UP
    )


def weight(value):
    return Decimal(str(value)).quantize(
        WEIGHT_Q,
        rounding=ROUND_HALF_UP
    )


def utc_now():
    return datetime.now(timezone.utc)


# ============================================================
# ENUMS
# ============================================================

class TobaccoType(str, Enum):

    FLUE_CURED = "FLUE_CURED"
    BURLEY = "BURLEY"
    ORIENTAL = "ORIENTAL"
    DARK_AIR_CURED = "DARK_AIR_CURED"


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
    SUSTAINABLE = "SUSTAINABLE"
    TRACEABLE = "TRACEABLE"
    ORGANIC = "ORGANIC"


# ============================================================
# TOBACCO LOT
# ============================================================

@dataclass
class TobaccoLot:

    lot_id: str

    tobacco_type: TobaccoType

    origin_country: str
    origin_region: str

    producer_id: str

    crop_year: str

    quantity_kg: Decimal

    # --------------------------------------------------------
    # PHYSICAL / AGRONOMIC QUALITY
    # --------------------------------------------------------

    stalk_position: str

    leaf_grade: str

    colour_score: Decimal

    maturity_score: Decimal

    body_score: Decimal

    elasticity_score: Decimal

    aroma_score: Decimal

    uniformity_percent: Decimal

    damage_percent: Decimal

    foreign_material_percent: Decimal

    moisture_percent: Decimal

    # --------------------------------------------------------
    # CHEMISTRY
    # --------------------------------------------------------

    nicotine_percent: Decimal

    reducing_sugars_percent: Decimal

    total_nitrogen_percent: Decimal

    # --------------------------------------------------------
    # COMMERCIAL
    # --------------------------------------------------------

    certification: Certification = (
        Certification.STANDARD
    )

    warehouse: Optional[str] = None

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
class TobaccoBenchmark:

    tobacco_type: TobaccoType

    origin_country: str

    price_per_kg: Decimal

    currency: str = "USD"

    timestamp: datetime = field(
        default_factory=utc_now
    )

    def update(self, price):

        self.price_per_kg = money(price)

        self.timestamp = utc_now()


# ============================================================
# PRICING ENGINE
# ============================================================

class TobaccoPricingEngine:

    """
    Quality-adjusted physical spot model.

    Base price
       × grade
       × colour
       × maturity
       × body
       × elasticity
       × uniformity
       × damage
       × moisture
       × origin
       × crop-year
       × certification
    """

    def __init__(
        self,
        benchmarks: Dict[
            tuple,
            TobaccoBenchmark
        ]
    ):

        self.benchmarks = benchmarks

    # --------------------------------------------------------
    # LEAF GRADE
    # --------------------------------------------------------

    def grade_factor(
        self,
        lot: TobaccoLot
    ):

        grade = lot.leaf_grade.upper()

        factors = {

            "CHOICE": Decimal("1.12"),
            "FINE": Decimal("1.08"),
            "GOOD": Decimal("1.04"),
            "FAIR": Decimal("1.00"),
            "LOW": Decimal("0.90"),
            "POOR": Decimal("0.78"),
        }

        return factors.get(
            grade,
            Decimal("1.00")
        )

    # --------------------------------------------------------
    # COLOUR
    # --------------------------------------------------------

    def colour_factor(
        self,
        lot: TobaccoLot
    ):

        score = lot.colour_score

        if score >= Decimal("9"):
            return Decimal("1.10")

        if score >= Decimal("7"):
            return Decimal("1.05")

        if score >= Decimal("5"):
            return Decimal("1.00")

        if score >= Decimal("3"):
            return Decimal("0.92")

        return Decimal("0.84")

    # --------------------------------------------------------
    # MATURITY
    # --------------------------------------------------------

    def maturity_factor(
        self,
        lot: TobaccoLot
    ):

        score = lot.maturity_score

        if score >= Decimal("9"):
            return Decimal("1.08")

        if score >= Decimal("7"):
            return Decimal("1.04")

        if score >= Decimal("5"):
            return Decimal("1.00")

        if score >= Decimal("3"):
            return Decimal("0.92")

        return Decimal("0.85")

    # --------------------------------------------------------
    # BODY
    # --------------------------------------------------------

    def body_factor(
        self,
        lot: TobaccoLot
    ):

        score = lot.body_score

        return (
            Decimal("0.90")
            + score * Decimal("0.02")
        )

    # --------------------------------------------------------
    # ELASTICITY
    # --------------------------------------------------------

    def elasticity_factor(
        self,
        lot: TobaccoLot
    ):

        score = lot.elasticity_score

        return (
            Decimal("0.90")
            + score * Decimal("0.02")
        )

    # --------------------------------------------------------
    # UNIFORMITY
    # --------------------------------------------------------

    def uniformity_factor(
        self,
        lot: TobaccoLot
    ):

        u = lot.uniformity_percent

        if u >= Decimal("90"):
            return Decimal("1.08")

        if u >= Decimal("80"):
            return Decimal("1.04")

        if u >= Decimal("70"):
            return Decimal("1.00")

        if u >= Decimal("60"):
            return Decimal("0.94")

        return Decimal("0.88")

    # --------------------------------------------------------
    # DAMAGE
    # --------------------------------------------------------

    def damage_factor(
        self,
        lot: TobaccoLot
    ):

        d = lot.damage_percent

        if d <= Decimal("5"):
            return Decimal("1.03")

        if d <= Decimal("10"):
            return Decimal("1.00")

        if d <= Decimal("20"):
            return Decimal("0.94")

        if d <= Decimal("30"):
            return Decimal("0.85")

        return Decimal("0.70")

    # --------------------------------------------------------
    # MOISTURE
    # --------------------------------------------------------

    def moisture_factor(
        self,
        lot: TobaccoLot
    ):

        m = lot.moisture_percent

        # Illustrative optimum band
        if Decimal("11") <= m <= Decimal("14"):
            return Decimal("1.04")

        if Decimal("9") <= m <= Decimal("16"):
            return Decimal("1.00")

        if Decimal("7") <= m <= Decimal("18"):
            return Decimal("0.94")

        return Decimal("0.85")

    # --------------------------------------------------------
    # ORIGIN BASIS
    # --------------------------------------------------------

    def origin_factor(
        self,
        lot: TobaccoLot
    ):

        factors = {

            "BRAZIL": Decimal("1.00"),
            "USA": Decimal("1.05"),
            "ZIMBABWE": Decimal("1.07"),
            "MALAWI": Decimal("1.04"),
            "TURKEY": Decimal("1.08"),
            "GREECE": Decimal("1.06"),
            "ITALY": Decimal("1.03"),
            "ARGENTINA": Decimal("0.96"),
            "MOZAMBIQUE": Decimal("0.98"),
        }

        return factors.get(
            lot.origin_country.upper(),
            Decimal("1.00")
        )

    # --------------------------------------------------------
    # CROP YEAR
    # --------------------------------------------------------

    def crop_year_factor(
        self,
        lot: TobaccoLot
    ):

        try:

            year = int(
                lot.crop_year[:4]
            )

            age = utc_now().year - year

        except Exception:

            age = 0

        if age <= 0:
            return Decimal("1.04")

        if age == 1:
            return Decimal("1.02")

        if age == 2:
            return Decimal("1.00")

        if age == 3:
            return Decimal("0.96")

        return Decimal("0.92")

    # --------------------------------------------------------
    # CERTIFICATION
    # --------------------------------------------------------

    def certification_factor(
        self,
        lot: TobaccoLot
    ):

        factors = {

            Certification.STANDARD:
                Decimal("1.00"),

            Certification.SUSTAINABLE:
                Decimal("1.03"),

            Certification.TRACEABLE:
                Decimal("1.02"),

            Certification.ORGANIC:
                Decimal("1.06"),
        }

        return factors[
            lot.certification
        ]

    # --------------------------------------------------------
    # FINAL PRICE
    # --------------------------------------------------------

    def spot_price(
        self,
        lot: TobaccoLot
    ):

        key = (
            lot.tobacco_type,
            lot.origin_country.upper()
        )

        benchmark = self.benchmarks.get(
            key
        )

        if benchmark is None:

            raise ValueError(
                f"No benchmark for {key}"
            )

        price = (

            benchmark.price_per_kg

            * self.grade_factor(lot)

            * self.colour_factor(lot)

            * self.maturity_factor(lot)

            * self.body_factor(lot)

            * self.elasticity_factor(lot)

            * self.uniformity_factor(lot)

            * self.damage_factor(lot)

            * self.moisture_factor(lot)

            * self.origin_factor(lot)

            * self.crop_year_factor(lot)

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
class TobaccoTrade:

    trade_id: str

    lot_id: str

    buyer_id: str

    seller_id: str

    tobacco_type: TobaccoType

    origin_country: str

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

class TobaccoOrderBook:

    def __init__(
        self,
        lot_id
    ):

        self.lot_id = lot_id

        self.bids: List[Order] = []
        self.asks: List[Order] = []

        self.orders = {}

        self.trades: List[
            TobaccoTrade
        ] = []

    # --------------------------------------------------------
    # ADD
    # --------------------------------------------------------

    def add(
        self,
        order
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
        lot: TobaccoLot
    ):

        trades = []

        while True:

            bid = self.best_bid()
            ask = self.best_ask()

            if not bid or not ask:
                break

            bid_crosses = (

                bid.order_type
                == OrderType.MARKET

                or bid.price >= ask.price
            )

            ask_crosses = (

                ask.order_type
                == OrderType.MARKET

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

            # Passive order establishes price.
            if bid.timestamp <= ask.timestamp:

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
                    "No execution price"
                )

            trade = TobaccoTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=self.lot_id,

                buyer_id=bid.trader_id,

                seller_id=ask.trader_id,

                tobacco_type=(
                    lot.tobacco_type
                ),

                origin_country=(
                    lot.origin_country
                ),

                price_per_kg=money(
                    execution_price
                ),

                quantity_kg=weight(
                    quantity
                )
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
    def update_status(order):

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
        order_id
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
# RHINO TOBACCO EXCHANGE
# ============================================================

class RhinoTobaccoExchange:

    def __init__(self):

        self.lots = {}

        self.books = {}

        self.trades = []

        # ----------------------------------------------------
        # Illustrative benchmark universe
        # ----------------------------------------------------

        self.benchmarks = {

            (
                TobaccoType.FLUE_CURED,
                "BRAZIL"
            ):
                TobaccoBenchmark(
                    TobaccoType.FLUE_CURED,
                    "BRAZIL",
                    Decimal("4.20")
                ),

            (
                TobaccoType.FLUE_CURED,
                "ZIMBABWE"
            ):
                TobaccoBenchmark(
                    TobaccoType.FLUE_CURED,
                    "ZIMBABWE",
                    Decimal("4.80")
                ),

            (
                TobaccoType.BURLEY,
                "BRAZIL"
            ):
                TobaccoBenchmark(
                    TobaccoType.BURLEY,
                    "BRAZIL",
                    Decimal("3.60")
                ),

            (
                TobaccoType.BURLEY,
                "USA"
            ):
                TobaccoBenchmark(
                    TobaccoType.BURLEY,
                    "USA",
                    Decimal("4.10")
                ),

            (
                TobaccoType.BURLEY,
                "MALAWI"
            ):
                TobaccoBenchmark(
                    TobaccoType.BURLEY,
                    "MALAWI",
                    Decimal("3.90")
                ),

            (
                TobaccoType.ORIENTAL,
                "TURKEY"
            ):
                TobaccoBenchmark(
                    TobaccoType.ORIENTAL,
                    "TURKEY",
                    Decimal("5.20")
                ),

            (
                TobaccoType.ORIENTAL,
                "GREECE"
            ):
                TobaccoBenchmark(
                    TobaccoType.ORIENTAL,
                    "GREECE",
                    Decimal("5.00")
                ),

            (
                TobaccoType.DARK_AIR_CURED,
                "ITALY"
            ):
                TobaccoBenchmark(
                    TobaccoType.DARK_AIR_CURED,
                    "ITALY",
                    Decimal("3.80")
                )
        }

        self.pricing = (
            TobaccoPricingEngine(
                self.benchmarks
            )
        )

    # --------------------------------------------------------
    # REGISTER
    # --------------------------------------------------------

    def register_lot(
        self,
        lot: TobaccoLot
    ):

        self.lots[
            lot.lot_id
        ] = lot

        self.books[
            lot.lot_id
        ] = TobaccoOrderBook(
            lot.lot_id
        )

    # --------------------------------------------------------
    # SPOT PRICE
    # --------------------------------------------------------

    def spot_price(
        self,
        lot_id
    ):

        return self.pricing.spot_price(
            self.lots[lot_id]
        )

    # --------------------------------------------------------
    # SUBMIT ORDER
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
                "Insufficient physical tobacco"
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
        lot_id
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
    # MARKET SNAPSHOT
    # --------------------------------------------------------

    def snapshot(
        self,
        lot_id
    ):

        lot = self.lots[
            lot_id
        ]

        book = self.books[
            lot_id
        ]

        bid = book.best_bid()
        ask = book.best_ask()

        last = (

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

            "type":
                lot.tobacco_type.value,

            "origin":
                lot.origin_country,

            "region":
                lot.origin_region,

            "crop":
                lot.crop_year,

            "grade":
                lot.leaf_grade,

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
                        last.price_per_kg
                    )
                    if last
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

            "colour_score":
                str(
                    lot.colour_score
                ),

            "maturity_score":
                str(
                    lot.maturity_score
                ),

            "body_score":
                str(
                    lot.body_score
                ),

            "uniformity":
                str(
                    lot.uniformity_percent
                ),

            "damage":
                str(
                    lot.damage_percent
                ),

            "moisture":
                str(
                    lot.moisture_percent
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
        RhinoTobaccoExchange()
    )

    # --------------------------------------------------------
    # BRAZILIAN FLUE-CURED LOT
    # --------------------------------------------------------

    lot = TobaccoLot(

        lot_id="RTX-FC-BR-2026-001",

        tobacco_type=(
            TobaccoType.FLUE_CURED
        ),

        origin_country="Brazil",

        origin_region="Rio Grande do Sul",

        producer_id="BR-LEAF-001",

        crop_year="2026",

        quantity_kg=Decimal(
            "50000"
        ),

        stalk_position="UPPER",

        leaf_grade="CHOICE",

        colour_score=Decimal(
            "8.5"
        ),

        maturity_score=Decimal(
            "8.0"
        ),

        body_score=Decimal(
            "8.0"
        ),

        elasticity_score=Decimal(
            "8.5"
        ),

        aroma_score=Decimal(
            "8.0"
        ),

        uniformity_percent=Decimal(
            "91"
        ),

        damage_percent=Decimal(
            "4"
        ),

        foreign_material_percent=Decimal(
            "0.2"
        ),

        moisture_percent=Decimal(
            "12.5"
        ),

        nicotine_percent=Decimal(
            "2.1"
        ),

        reducing_sugars_percent=Decimal(
            "18.5"
        ),

        total_nitrogen_percent=Decimal(
            "1.7"
        ),

        certification=(
            Certification.TRACEABLE
        ),

        warehouse="RHINO-BRAZIL-01"
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    print()
    print(
        "=========================================="
    )

    print(
        " RHINO TOBACCO EXCHANGE"
    )

    print(
        " RTX — RAW LEAF SPOT MARKET"
    )

    print(
        "=========================================="
    )

    print(
        "THEORETICAL SPOT:",
        exchange.spot_price(
            lot.lot_id
        ),
        "USD/kg"
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-MANUFACTURER-001",

        lot_id=lot.lot_id,

        side=Side.BUY,

        order_type=OrderType.LIMIT,

        quantity_kg=Decimal(
            "20000"
        ),

        price=Decimal(
            "5.15"
        )
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="BRAZIL-LEAF-001",

        lot_id=lot.lot_id,

        side=Side.SELL,

        order_type=OrderType.LIMIT,

        quantity_kg=Decimal(
            "12000"
        ),

        price=Decimal(
            "5.00"
        )
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    print()
    print(
        "MARKET SNAPSHOT"
    )

    print(
        "------------------------------------------"
    )

    for key, value in exchange.snapshot(
        lot.lot_id
    ).items():

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

            trade.tobacco_type.value,
            "|",
            trade.origin_country,
            "|",
            trade.quantity_kg,
            "kg @",
            trade.price_per_kg,
            "USD/kg",
            "| NOTIONAL:",
            trade.notional,
            "USD"
        )
