"""
=============================================================
RHINO WHEY EXCHANGE
RWX 1.0
=============================================================

Physical whey spot-pricing and trading engine.

Products:

    DRY_WHEY
    WPC34
    WPC50
    WPC60
    WPC75
    WPC80
    WPI
    WHEY_PERMEATE

Pricing model:

    Market Benchmark
          +
    Protein Basis
          +
    Origin Basis
          +
    Functional Quality
          +
    Microbiology
          +
    Moisture
          +
    Lactose / Ash / Fat
          +
    Certification
          +
    Logistics
          +
    FX
          =
    RHINO WHEY SPOT

Features:

    - physical lots
    - product specifications
    - benchmark pricing
    - origin differentials
    - quality premiums / discounts
    - warehouse inventory
    - bids
    - offers
    - matching engine
    - VWAP
    - market snapshot
    - physical settlement quantities
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
# PRODUCTS
# ============================================================

class WheyProduct(Enum):

    DRY_WHEY = "DRY_WHEY"

    WPC34 = "WPC34"

    WPC50 = "WPC50"

    WPC60 = "WPC60"

    WPC75 = "WPC75"

    WPC80 = "WPC80"

    WPI = "WPI"

    WHEY_PERMEATE = "WHEY_PERMEATE"


class Processing(Enum):

    SWEET_WHEY = "SWEET_WHEY"

    ACID_WHEY = "ACID_WHEY"

    ULTRAFILTERED = "ULTRAFILTERED"

    MICROFILTERED = "MICROFILTERED"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class WheyBenchmark:

    product: WheyProduct

    price_usd_tonne: Decimal

    source: str

    timestamp: datetime = field(
        default_factory=now
    )

    def price(self):

        return money(
            self.price_usd_tonne
        )


# ============================================================
# PHYSICAL WHEY LOT
# ============================================================

@dataclass
class WheyLot:

    lot_id: str

    product: WheyProduct

    origin_country: str

    producer: str

    quantity_tonnes: Decimal

    protein_percent: Decimal

    lactose_percent: Decimal

    fat_percent: Decimal

    ash_percent: Decimal

    moisture_percent: Decimal

    microbiological_status: str

    processing: Processing

    certification: str

    functionality_score: Decimal

    solubility_percent: Decimal

    flavour_score: Decimal

    harvest_or_production_month: str

    warehouse: str

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

class WheyOriginEngine:

    """
    Illustrative origin basis.

    Production implementation should replace these
    values with validated Rhino physical-market data.
    """

    BASIS = {

        "United States": D("0"),

        "Netherlands": D("40"),

        "Germany": D("35"),

        "France": D("30"),

        "Ireland": D("45"),

        "Poland": D("20"),

        "New Zealand": D("25"),

        "Australia": D("10"),

        "United Kingdom": D("30"),

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

class WheyQualityEngine:

    """
    Converts physical characteristics into
    a $/tonne premium or discount.
    """

    def calculate(
        self,
        lot: WheyLot
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # PROTEIN
        # ----------------------------------------------------

        if lot.product == WheyProduct.WPC80:

            if lot.protein_percent >= D("82"):

                adjustment += D("150")

            elif lot.protein_percent >= D("80"):

                adjustment += D("50")

            elif lot.protein_percent < D("78"):

                adjustment -= D("250")

        elif lot.product == WheyProduct.WPI:

            if lot.protein_percent >= D("92"):

                adjustment += D("200")

            elif lot.protein_percent >= D("90"):

                adjustment += D("50")

            else:

                adjustment -= D("300")

        elif lot.product == WheyProduct.WPC34:

            if lot.protein_percent >= D("36"):

                adjustment += D("50")

            elif lot.protein_percent < D("33"):

                adjustment -= D("75")

        # ----------------------------------------------------
        # MOISTURE
        # ----------------------------------------------------

        if lot.moisture_percent <= D("4"):

            adjustment += D("25")

        elif lot.moisture_percent <= D("5"):

            adjustment += D("0")

        else:

            adjustment -= D("75")

        # ----------------------------------------------------
        # SOLUBILITY
        # ----------------------------------------------------

        if lot.solubility_percent >= D("95"):

            adjustment += D("75")

        elif lot.solubility_percent >= D("90"):

            adjustment += D("25")

        elif lot.solubility_percent < D("85"):

            adjustment -= D("100")

        # ----------------------------------------------------
        # FLAVOUR
        # ----------------------------------------------------

        if lot.flavour_score >= D("9"):

            adjustment += D("75")

        elif lot.flavour_score >= D("8"):

            adjustment += D("25")

        elif lot.flavour_score < D("6"):

            adjustment -= D("100")

        # ----------------------------------------------------
        # MICROBIOLOGY
        # ----------------------------------------------------

        if (
            lot.microbiological_status
            == "PREMIUM"
        ):

            adjustment += D("75")

        elif (
            lot.microbiological_status
            == "STANDARD"
        ):

            adjustment += D("0")

        elif (
            lot.microbiological_status
            == "FAIL"
        ):

            adjustment -= D("1000")

        # ----------------------------------------------------
        # FUNCTIONALITY
        # ----------------------------------------------------

        if lot.functionality_score >= D("95"):

            adjustment += D("100")

        elif lot.functionality_score >= D("90"):

            adjustment += D("50")

        elif lot.functionality_score < D("80"):

            adjustment -= D("100")

        # ----------------------------------------------------
        # CERTIFICATION
        # ----------------------------------------------------

        certification = (
            lot.certification.upper()
        )

        if certification == "ORGANIC":

            adjustment += D("125")

        elif certification == "GRASS_FED":

            adjustment += D("50")

        elif certification == "NON_GMO":

            adjustment += D("35")

        return money(
            adjustment
        )


# ============================================================
# SPOT ENGINE
# ============================================================

class WheySpotEngine:

    def __init__(self):

        self.origin_engine = (
            WheyOriginEngine()
        )

        self.quality_engine = (
            WheyQualityEngine()
        )

    def calculate(
        self,
        benchmark: WheyBenchmark,
        lot: WheyLot,
        fx_rate=D("1")
    ):

        benchmark_price = (
            benchmark.price()
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

            lot.freight_usd_tonne

            + lot.insurance_usd_tonne

            + lot.duty_usd_tonne
        )

        spot = (

            benchmark_price

            + origin_basis

            + quality_basis

            + logistics
        )

        return money(
            spot * D(fx_rate)
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class WheyOrder:

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
class WheyTrade:

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
# RHINO WHEY EXCHANGE
# ============================================================

class RhinoWheyExchange:

    def __init__(self):

        self.benchmarks: Dict[
            WheyProduct,
            WheyBenchmark
        ] = {}

        self.lots: Dict[
            str,
            WheyLot
        ] = {}

        self.bids: List[
            WheyOrder
        ] = []

        self.asks: List[
            WheyOrder
        ] = []

        self.trades: List[
            WheyTrade
        ] = []

        self.pricer = (
            WheySpotEngine()
        )

    # ========================================================
    # BENCHMARK
    # ========================================================

    def set_benchmark(
        self,
        product,
        price_usd_tonne,
        source="RHINO_MARKET_DATA"
    ):

        self.benchmarks[
            product
        ] = WheyBenchmark(

            product=product,

            price_usd_tonne=D(
                price_usd_tonne
            ),

            source=source
        )

    # ========================================================
    # REGISTER PHYSICAL LOT
    # ========================================================

    def register_lot(
        self,
        lot: WheyLot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # ========================================================
    # SPOT PRICE
    # ========================================================

    def spot(
        self,
        lot_id,
        fx_rate=D("1")
    ):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.product
        )

        if benchmark is None:

            raise RuntimeError(
                f"No benchmark for "
                f"{lot.product.value}"
            )

        return self.pricer.calculate(

            benchmark,

            lot,

            fx_rate
        )

    # ========================================================
    # ORDER
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
                    "Insufficient physical "
                    "whey inventory"
                )

        order = WheyOrder(

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
    # MATCH
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

            trade = WheyTrade(

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

            t.quantity_tonnes
            * t.price

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
                "RHINO WHEY EXCHANGE",

            "instrument":
                f"RWX-{lot.product.value}",

            "lot":
                lot_id,

            "product":
                lot.product.value,

            "origin":
                lot.origin_country,

            "producer":
                lot.producer,

            "protein_percent":
                str(lot.protein_percent),

            "lactose_percent":
                str(lot.lactose_percent),

            "fat_percent":
                str(lot.fat_percent),

            "moisture_percent":
                str(lot.moisture_percent),

            "functionality":
                str(lot.functionality_score),

            "solubility":
                str(lot.solubility_percent),

            "available_tonnes":
                str(lot.available_tonnes),

            "spot":
                str(
                    self.spot(lot_id)
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
                    self.vwap(lot_id)
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
        RhinoWheyExchange()
    )

    # --------------------------------------------------------
    # BENCHMARKS
    # --------------------------------------------------------

    # Illustrative values only.
    # Production system should ingest validated
    # market-data feeds.

    exchange.set_benchmark(

        WheyProduct.WPC80,

        12000,

        "RHINO_MARKET_DATA"
    )

    exchange.set_benchmark(

        WheyProduct.WPI,

        14500,

        "RHINO_MARKET_DATA"
    )

    exchange.set_benchmark(

        WheyProduct.WPC34,

        2200,

        "RHINO_MARKET_DATA"
    )

    exchange.set_benchmark(

        WheyProduct.DRY_WHEY,

        1100,

        "RHINO_MARKET_DATA"
    )

    # --------------------------------------------------------
    # PHYSICAL WPC80 LOT
    # --------------------------------------------------------

    lot = WheyLot(

        lot_id="RWX-WPC80-USA-001",

        product=WheyProduct.WPC80,

        origin_country="United States",

        producer="RHINO-DAIRY-PRODUCER-001",

        quantity_tonnes=1000,

        protein_percent=D("81.2"),

        lactose_percent=D("4.5"),

        fat_percent=D("6.5"),

        ash_percent=D("3.2"),

        moisture_percent=D("4.0"),

        microbiological_status="PREMIUM",

        processing=Processing.ULTRAFILTERED,

        certification="NON_GMO",

        functionality_score=D("94"),

        solubility_percent=D("96"),

        flavour_score=D("9"),

        harvest_or_production_month="2026-08",

        warehouse="CHICAGO-DAIRY-01",

        freight_usd_tonne=D("120"),

        insurance_usd_tonne=D("5"),

        duty_usd_tonne=D("0")
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    spot = exchange.spot(
        "RWX-WPC80-USA-001"
    )

    print()

    print(
        "RHINO WHEY EXCHANGE"
    )

    print(
        "==================="
    )

    print(
        "WPC80 spot:",
        spot,
        "USD/t"
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-NUTRITION-001",

        lot_id="RWX-WPC80-USA-001",

        side=Side.BUY,

        quantity_tonnes=100,

        price=12300
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-DAIRY-TRADER-001",

        lot_id="RWX-WPC80-USA-001",

        side=Side.SELL,

        quantity_tonnes=100,

        price=12250
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
        "RWX-WPC80-USA-001"
    )

    for key, value in snapshot.items():

        print(
            f"{key:26} {value}"
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

            "USD/t",

            "| Notional:",

            trade.notional
        )
