"""
=============================================================
RHINO COFFEE EXCHANGE
RCE 1.0
=============================================================

Physical coffee spot-pricing and exchange engine.

Pricing model:

    Coffee Benchmark
          +
    Origin Basis
          +
    Grade / Screen
          +
    Processing Method
          +
    Cup Quality
          +
    Defect Adjustment
          +
    Certification
          +
    Logistics
          +
    FX
          =
    RHINO COFFEE SPOT

Supports:

    - Arabica
    - Robusta
    - physical coffee lots
    - origin differentials
    - screen size
    - processing
    - defects
    - moisture
    - cup score
    - certifications
    - warehouse inventory
    - bids
    - offers
    - order matching
    - VWAP
    - market snapshots
"""


from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4


# ============================================================
# UTILITIES
# ============================================================

def D(value):
    return Decimal(str(value))


def money(value):
    return D(value).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def tonnes(value):
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def now():
    return datetime.now(timezone.utc)


# ============================================================
# COFFEE TYPES
# ============================================================

class CoffeeType(Enum):

    ARABICA = "ARABICA"

    ROBUSTA = "ROBUSTA"

    SPECIALTY_ARABICA = "SPECIALTY_ARABICA"


class ProcessingMethod(Enum):

    WASHED = "WASHED"

    NATURAL = "NATURAL"

    HONEY = "HONEY"

    PULPED_NATURAL = "PULPED_NATURAL"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class CoffeeBenchmark:

    name: str

    coffee_type: CoffeeType

    price_usd_lb: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    source: str = "MARKET_DATA"

    def price_usd_tonne(self):

        # 1 metric tonne = 2204.62262 lb

        return money(
            self.price_usd_lb
            * D("2204.62262")
        )


# ============================================================
# COFFEE LOT
# ============================================================

@dataclass
class CoffeeLot:

    lot_id: str

    coffee_type: CoffeeType

    origin_country: str

    origin_region: str

    producer: str

    quantity_tonnes: Decimal

    grade: str

    processing: ProcessingMethod

    screen_size: Decimal

    moisture_percent: Decimal

    defect_count: Decimal

    cup_score: Decimal

    certification: str

    harvest_year: int

    warehouse: str

    currency: str = "USD"

    freight_usd_tonne: Decimal = D("0")

    insurance_usd_tonne: Decimal = D("0")

    duty_usd_tonne: Decimal = D("0")

    available_tonnes: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity_tonnes = tonnes(
            self.quantity_tonnes
        )

        self.available_tonnes = (
            self.quantity_tonnes
        )


# ============================================================
# ORIGIN BASIS
# ============================================================

class CoffeeOriginEngine:

    """
    Illustrative origin differentials.

    Production values should be driven by Rhino
    market data and physical executable quotes.
    """

    BASIS = {

        "Brazil": D("0"),

        "Colombia": D("110"),

        "Ethiopia": D("180"),

        "Kenya": D("220"),

        "Guatemala": D("140"),

        "Honduras": D("90"),

        "Costa Rica": D("200"),

        "Peru": D("80"),

        "Vietnam": D("-80"),

        "Indonesia": D("20"),

        "India": D("15"),

        "Uganda": D("-60"),

    }

    def calculate(
        self,
        country
    ):

        return self.BASIS.get(
            country,
            D("0")
        )


# ============================================================
# QUALITY ENGINE
# ============================================================

class CoffeeQualityEngine:

    """
    Converts physical characteristics into a
    premium / discount per tonne.
    """

    def calculate(
        self,
        lot: CoffeeLot
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # CUP QUALITY
        # ----------------------------------------------------

        if lot.cup_score >= D("90"):

            adjustment += D("700")

        elif lot.cup_score >= D("85"):

            adjustment += D("450")

        elif lot.cup_score >= D("82"):

            adjustment += D("250")

        elif lot.cup_score >= D("80"):

            adjustment += D("100")

        elif lot.cup_score < D("78"):

            adjustment -= D("150")

        # ----------------------------------------------------
        # SCREEN SIZE
        # ----------------------------------------------------

        if lot.screen_size >= D("18"):

            adjustment += D("80")

        elif lot.screen_size >= D("17"):

            adjustment += D("40")

        elif lot.screen_size < D("15"):

            adjustment -= D("50")

        # ----------------------------------------------------
        # MOISTURE
        # ----------------------------------------------------

        if (
            lot.moisture_percent
            >= D("10")
            and
            lot.moisture_percent
            <= D("12")
        ):

            adjustment += D("20")

        elif lot.moisture_percent > D("12"):

            adjustment -= D("100")

        elif lot.moisture_percent < D("9"):

            adjustment -= D("40")

        # ----------------------------------------------------
        # DEFECTS
        # ----------------------------------------------------

        if lot.defect_count <= D("5"):

            adjustment += D("50")

        elif lot.defect_count <= D("10"):

            adjustment += D("10")

        elif lot.defect_count <= D("20"):

            adjustment -= D("50")

        else:

            adjustment -= D("150")

        # ----------------------------------------------------
        # PROCESSING
        # ----------------------------------------------------

        if (
            lot.processing
            == ProcessingMethod.NATURAL
        ):

            adjustment += D("35")

        elif (
            lot.processing
            == ProcessingMethod.HONEY
        ):

            adjustment += D("45")

        # ----------------------------------------------------
        # SPECIALTY
        # ----------------------------------------------------

        if (
            lot.coffee_type
            == CoffeeType.SPECIALTY_ARABICA
        ):

            adjustment += D("150")

        # ----------------------------------------------------
        # CERTIFICATION
        # ----------------------------------------------------

        cert = lot.certification.upper()

        if cert == "ORGANIC":

            adjustment += D("100")

        elif cert == "FAIRTRADE":

            adjustment += D("60")

        elif cert == "RAINFOREST":

            adjustment += D("35")

        return money(
            adjustment
        )


# ============================================================
# SPOT PRICING ENGINE
# ============================================================

class CoffeeSpotEngine:

    def __init__(self):

        self.origin_engine = (
            CoffeeOriginEngine()
        )

        self.quality_engine = (
            CoffeeQualityEngine()
        )

    def calculate(
        self,
        benchmark: CoffeeBenchmark,
        lot: CoffeeLot,
        fx_rate=D("1")
    ):

        benchmark_price = (
            benchmark.price_usd_tonne()
        )

        origin_basis = (
            self.origin_engine.calculate(
                lot.origin_country
            )
        )

        quality_basis = (
            self.quality_engine.calculate(
                lot
            )
        )

        logistics = (

            D(lot.freight_usd_tonne)

            + D(lot.insurance_usd_tonne)

            + D(lot.duty_usd_tonne)
        )

        spot_usd = (

            benchmark_price

            + origin_basis

            + quality_basis

            + logistics
        )

        return money(
            spot_usd
            * D(fx_rate)
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class CoffeeOrder:

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    quantity_tonnes: Decimal

    price: Decimal

    remaining: Decimal = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.quantity_tonnes = tonnes(
            self.quantity_tonnes
        )

        self.remaining = (
            self.quantity_tonnes
        )


# ============================================================
# TRADE
# ============================================================

@dataclass
class CoffeeTrade:

    trade_id: str

    lot_id: str

    buyer: str

    seller: str

    quantity_tonnes: Decimal

    price: Decimal

    currency: str

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional(self):

        return money(
            self.quantity_tonnes
            * self.price
        )


# ============================================================
# RHINO COFFEE EXCHANGE
# ============================================================

class RhinoCoffeeExchange:

    def __init__(self):

        self.benchmarks: Dict[
            CoffeeType,
            CoffeeBenchmark
        ] = {}

        self.lots: Dict[
            str,
            CoffeeLot
        ] = {}

        self.bids: List[
            CoffeeOrder
        ] = []

        self.asks: List[
            CoffeeOrder
        ] = []

        self.trades: List[
            CoffeeTrade
        ] = []

        self.pricer = (
            CoffeeSpotEngine()
        )

    # ========================================================
    # SET BENCHMARK
    # ========================================================

    def set_benchmark(
        self,
        coffee_type,
        price_usd_lb,
        source="MARKET_DATA"
    ):

        self.benchmarks[
            coffee_type
        ] = CoffeeBenchmark(

            name="RHINO_COFFEE_BENCHMARK",

            coffee_type=coffee_type,

            price_usd_lb=D(
                price_usd_lb
            ),

            source=source
        )

    # ========================================================
    # REGISTER LOT
    # ========================================================

    def register_lot(
        self,
        lot: CoffeeLot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # ========================================================
    # INDICATIVE SPOT
    # ========================================================

    def indicative_spot(
        self,
        lot_id,
        fx_rate=D("1")
    ):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.coffee_type
        )

        if benchmark is None:

            raise RuntimeError(
                "Coffee benchmark unavailable"
            )

        return self.pricer.calculate(

            benchmark,

            lot,

            fx_rate
        )

    # ========================================================
    # SUBMIT ORDER
    # ========================================================

    def submit_order(
        self,
        trader_id,
        lot_id,
        side,
        quantity_tonnes,
        price
    ):

        lot = self.lots[
            lot_id
        ]

        quantity = tonnes(
            quantity_tonnes
        )

        if side == Side.SELL:

            if quantity > lot.available_tonnes:

                raise ValueError(
                    "Insufficient physical coffee"
                )

        order = CoffeeOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            quantity_tonnes=quantity,

            price=money(price)
        )

        if side == Side.BUY:

            self.bids.append(
                order
            )

            self.bids.sort(
                key=lambda x: (
                    -x.price,
                    x.timestamp
                )
            )

        else:

            self.asks.append(
                order
            )

            self.asks.sort(
                key=lambda x: (
                    x.price,
                    x.timestamp
                )
            )

        return self.match()

    # ========================================================
    # MATCHING ENGINE
    # ========================================================

    def match(self):

        executions = []

        while self.bids and self.asks:

            bid = self.bids[0]

            ask = self.asks[0]

            if bid.lot_id != ask.lot_id:

                break

            if bid.price < ask.price:

                break

            quantity = min(

                bid.remaining,

                ask.remaining
            )

            trade = CoffeeTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=bid.lot_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity_tonnes=quantity,

                price=ask.price,

                currency="USD"
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining -= quantity

            ask.remaining -= quantity

            lot = self.lots[
                bid.lot_id
            ]

            lot.available_tonnes -= (
                quantity
            )

            if bid.remaining <= 0:

                self.bids.pop(0)

            if ask.remaining <= 0:

                self.asks.pop(0)

        return executions

    # ========================================================
    # VWAP
    # ========================================================

    def vwap(
        self,
        lot_id
    ):

        trades = [

            t

            for t in self.trades

            if t.lot_id == lot_id
        ]

        if not trades:

            return None

        value = sum(

            t.price
            * t.quantity_tonnes

            for t in trades
        )

        volume = sum(

            t.quantity_tonnes

            for t in trades
        )

        if volume == 0:

            return None

        return money(
            value / volume
        )

    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    def snapshot(
        self,
        lot_id
    ):

        lot = self.lots[
            lot_id
        ]

        bids = [

            x

            for x in self.bids

            if x.lot_id == lot_id
        ]

        asks = [

            x

            for x in self.asks

            if x.lot_id == lot_id
        ]

        return {

            "market":
                "RHINO COFFEE EXCHANGE",

            "instrument":
                "RCE-COFFEE",

            "lot":
                lot_id,

            "coffee_type":
                lot.coffee_type.value,

            "origin":
                lot.origin_country,

            "region":
                lot.origin_region,

            "processing":
                lot.processing.value,

            "grade":
                lot.grade,

            "screen":
                str(lot.screen_size),

            "cup_score":
                str(lot.cup_score),

            "available_tonnes":
                str(lot.available_tonnes),

            "spot":
                str(
                    self.indicative_spot(
                        lot_id
                    )
                ),

            "best_bid":
                str(
                    max(
                        (
                            x.price
                            for x in bids
                        ),
                        default=D("0")
                    )
                ),

            "best_ask":
                str(
                    min(
                        (
                            x.price
                            for x in asks
                        ),
                        default=D("0")
                    )
                ),

            "vwap":
                str(
                    self.vwap(
                        lot_id
                    )
                    or D("0")
                ),

            "timestamp":
                now().isoformat()
        }


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    exchange = (
        RhinoCoffeeExchange()
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    # Illustrative value only.
    # Production system should use a validated market feed.

    exchange.set_benchmark(

        CoffeeType.ARABICA,

        price_usd_lb=D("3.20"),

        source="MARKET_DATA"
    )

    exchange.set_benchmark(

        CoffeeType.ROBUSTA,

        price_usd_lb=D("2.40"),

        source="MARKET_DATA"
    )

    # --------------------------------------------------------
    # COLOMBIAN ARABICA LOT
    # --------------------------------------------------------

    lot = CoffeeLot(

        lot_id="RCE-COL-001",

        coffee_type=CoffeeType.ARABICA,

        origin_country="Colombia",

        origin_region="Huila",

        producer="RHINO-COFFEE-PRODUCER-COL",

        quantity_tonnes=500,

        grade="SUPREMO",

        processing=ProcessingMethod.WASHED,

        screen_size=D("17"),

        moisture_percent=D("10.5"),

        defect_count=D("4"),

        cup_score=D("86"),

        certification="RAINFOREST",

        harvest_year=2026,

        warehouse="BUENAVENTURA-01",

        freight_usd_tonne=D("140"),

        insurance_usd_tonne=D("5"),

        duty_usd_tonne=D("0")
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    spot = exchange.indicative_spot(
        "RCE-COL-001"
    )

    print()

    print(
        "RHINO COFFEE EXCHANGE"
    )

    print(
        "====================="
    )

    print(
        "Indicative spot:",
        spot,
        "USD/t"
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-ROASTER-001",

        lot_id="RCE-COL-001",

        side=Side.BUY,

        quantity_tonnes=50,

        price=7600
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-COFFEE-TRADER-001",

        lot_id="RCE-COL-001",

        side=Side.SELL,

        quantity_tonnes=50,

        price=7550
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    print()

    print(
        "MARKET SNAPSHOT"
    )

    print(
        "================"
    )

    snapshot = exchange.snapshot(
        "RCE-COL-001"
    )

    for key, value in snapshot.items():

        print(
            f"{key:24} {value}"
        )

    # --------------------------------------------------------
    # TRADE BLOTTER
    # --------------------------------------------------------

    print()

    print(
        "TRADE BLOTTER"
    )

    print(
        "============="
    )

    for trade in exchange.trades:

        print(

            trade.buyer,

            "bought",

            trade.quantity_tonnes,

            "t @",

            trade.price,

            trade.currency,

            "| Notional:",

            trade.notional
        )
