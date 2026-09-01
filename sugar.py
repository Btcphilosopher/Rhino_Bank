"""
=============================================================
RHINO SUGAR EXCHANGE
RSE 1.0

Physical sugar spot-price engine.

Features:
    - raw sugar benchmark
    - white sugar benchmark
    - origin basis
    - quality adjustment
    - freight adjustment
    - FX conversion
    - import/export costs
    - physical lots
    - spot bids/offers
    - indicative spot
    - executable spot
    - VWAP
    - trade ledger
=============================================================
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4
from datetime import datetime, timezone


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
# SUGAR TYPES
# ============================================================

class SugarType(Enum):

    RAW_CANE = "RAW_CANE"

    WHITE = "WHITE"

    REFINED = "REFINED"

    ORGANIC = "ORGANIC"


class Side(Enum):

    BUY = "BUY"

    SELL"


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class SugarBenchmark:

    name: str

    price_usd_lb: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    def price_usd_tonne(self):

        # 1 metric tonne = 2204.62262 lb

        return money(
            self.price_usd_lb
            * D("2204.62262")
        )


# ============================================================
# PHYSICAL SUGAR LOT
# ============================================================

@dataclass
class SugarLot:

    lot_id: str

    sugar_type: SugarType

    origin_country: str

    origin_region: str

    producer: str

    quantity_tonnes: Decimal

    polarization: Decimal

    moisture: Decimal

    colour_icu: Decimal

    grade: str

    certification: str

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

class OriginBasisEngine:

    """
    Illustrative regional basis.

    Production basis should ultimately be
    supplied by Rhino's market-data layer.
    """

    BASIS = {

        "Brazil": D("0.00"),

        "India": D("8.00"),

        "Thailand": D("3.50"),

        "Australia": D("6.00"),

        "Mexico": D("4.00"),

        "South Africa": D("5.00"),

        "United Kingdom": D("35.00"),

        "France": D("34.00"),

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

class SugarQualityEngine:

    """
    Calculates a physical premium/discount.

    Polarization:
        higher = better raw sugar quality

    Moisture:
        lower = better

    Colour:
        lower ICUMSA = whiter product
    """

    def calculate(
        self,
        lot: SugarLot
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # POLARIZATION
        # ----------------------------------------------------

        if lot.polarization >= D("99"):

            adjustment += D("8")

        elif lot.polarization >= D("98"):

            adjustment += D("4")

        elif lot.polarization < D("96"):

            adjustment -= D("8")

        # ----------------------------------------------------
        # MOISTURE
        # ----------------------------------------------------

        if lot.moisture <= D("0.05"):

            adjustment += D("2")

        elif lot.moisture > D("0.10"):

            adjustment -= D("3")

        # ----------------------------------------------------
        # WHITE SUGAR COLOUR
        # ----------------------------------------------------

        if (
            lot.sugar_type
            in (
                SugarType.WHITE,
                SugarType.REFINED
            )
        ):

            if lot.colour_icu <= D("45"):

                adjustment += D("8")

            elif lot.colour_icu <= D("100"):

                adjustment += D("3")

            elif lot.colour_icu > D("150"):

                adjustment -= D("6")

        # ----------------------------------------------------
        # CERTIFICATION
        # ----------------------------------------------------

        certification = (
            lot.certification.upper()
        )

        if certification == "ORGANIC":

            adjustment += D("12")

        elif certification == "RAINFOREST":

            adjustment += D("4")

        return money(
            adjustment
        )


# ============================================================
# SPOT PRICE ENGINE
# ============================================================

class SugarSpotEngine:

    def __init__(self):

        self.origin_engine = (
            OriginBasisEngine()
        )

        self.quality_engine = (
            SugarQualityEngine()
        )

    def calculate(
        self,
        benchmark: SugarBenchmark,
        lot: SugarLot,
        fx_rate: Decimal = D("1")
    ):

        # Benchmark → $/tonne

        benchmark_price = (
            benchmark.price_usd_tonne()
        )

        # Origin basis

        origin_basis = (
            self.origin_engine.calculate(
                lot.origin_country
            )
        )

        # Quality premium

        quality_basis = (
            self.quality_engine.calculate(
                lot
            )
        )

        # Physical logistics

        logistics = (

            D(lot.freight_usd_tonne)

            + D(lot.insurance_usd_tonne)

            + D(lot.duty_usd_tonne)
        )

        # Final physical price

        usd_price = (

            benchmark_price

            + origin_basis

            + quality_basis

            + logistics
        )

        # FX conversion

        local_price = (
            usd_price * D(fx_rate)
        )

        return money(
            local_price
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class SugarOrder:

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
class SugarTrade:

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
# SUGAR MARKET
# ============================================================

class RhinoSugarExchange:

    def __init__(self):

        self.benchmark = None

        self.lots: Dict[
            str,
            SugarLot
        ] = {}

        self.bids: List[
            SugarOrder
        ] = []

        self.asks: List[
            SugarOrder
        ] = []

        self.trades: List[
            SugarTrade
        ] = []

        self.pricer = (
            SugarSpotEngine()
        )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    def set_benchmark(
        self,
        price_usd_lb
    ):

        self.benchmark = (
            SugarBenchmark(
                name="RAW_SUGAR_BENCHMARK",
                price_usd_lb=D(
                    price_usd_lb
                )
            )
        )

    # --------------------------------------------------------
    # REGISTER LOT
    # --------------------------------------------------------

    def register_lot(
        self,
        lot: SugarLot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # --------------------------------------------------------
    # INDICATIVE SPOT
    # --------------------------------------------------------

    def indicative_spot(
        self,
        lot_id,
        fx_rate=D("1")
    ):

        if not self.benchmark:

            raise RuntimeError(
                "Sugar benchmark unavailable"
            )

        lot = self.lots[
            lot_id
        ]

        return self.pricer.calculate(

            self.benchmark,

            lot,

            fx_rate
        )

    # --------------------------------------------------------
    # SUBMIT ORDER
    # --------------------------------------------------------

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

        qty = tonnes(
            quantity_tonnes
        )

        if side == Side.SELL:

            if qty > lot.available_tonnes:

                raise ValueError(
                    "Insufficient physical sugar"
                )

        order = SugarOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            quantity_tonnes=qty,

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


    # --------------------------------------------------------
    # MATCH ENGINE
    # --------------------------------------------------------

    def match(self):

        executions = []

        while self.bids and self.asks:

            bid = self.bids[0]

            ask = self.asks[0]

            # Different lots cannot match

            if bid.lot_id != ask.lot_id:

                break

            # No crossing market

            if bid.price < ask.price:

                break

            quantity = min(
                bid.remaining,
                ask.remaining
            )

            execution_price = (
                ask.price
            )

            lot = self.lots[
                bid.lot_id
            ]

            trade = SugarTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=lot.lot_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity_tonnes=quantity,

                price=execution_price,

                currency=lot.currency
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining -= quantity

            ask.remaining -= quantity

            lot.available_tonnes -= (
                quantity
            )

            if bid.remaining <= 0:

                self.bids.pop(0)

            if ask.remaining <= 0:

                self.asks.pop(0)

        return executions

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------

    def vwap(
        self,
        lot_id
    ):

        trades = [

            trade

            for trade in self.trades

            if trade.lot_id == lot_id
        ]

        if not trades:

            return None

        value = sum(

            trade.quantity_tonnes
            * trade.price

            for trade in trades
        )

        volume = sum(

            trade.quantity_tonnes

            for trade in trades
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

        indicative = (
            self.indicative_spot(
                lot_id
            )
        )

        bids = [

            order

            for order in self.bids

            if order.lot_id == lot_id
        ]

        asks = [

            order

            for order in self.asks

            if order.lot_id == lot_id
        ]

        return {

            "market":
                "RHINO SUGAR EXCHANGE",

            "instrument":
                "RSE-SUGAR",

            "lot":
                lot_id,

            "type":
                lot.sugar_type.value,

            "origin":
                lot.origin_country,

            "region":
                lot.origin_region,

            "available_tonnes":
                str(
                    lot.available_tonnes
                ),

            "indicative_spot":
                str(
                    indicative
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

    market = (
        RhinoSugarExchange()
    )

    # Current benchmark would normally
    # come from a market-data provider.
    #
    # Example value only.

    market.set_benchmark(
        "18.20"
    )

    brazil_sugar = SugarLot(

        lot_id="RSE-BRA-001",

        sugar_type=SugarType.RAW_CANE,

        origin_country="Brazil",

        origin_region="Sao Paulo",

        producer="RHINO-PRODUCER-BR",

        quantity_tonnes=5000,

        polarization=96,

        moisture=0.06,

        colour_icu=1000,

        grade="RAW_96",

        certification="STANDARD",

        warehouse="SANTOS-01",

        freight_usd_tonne=18,

        insurance_usd_tonne=1.5,

        duty_usd_tonne=0
    )

    market.register_lot(
        brazil_sugar
    )

    # --------------------------------------------------------
    # INDICATIVE SPOT
    # --------------------------------------------------------

    print()
    print(
        "RHINO SUGAR EXCHANGE"
    )

    print(
        "===================="
    )

    print(
        "Indicative spot:",
        market.indicative_spot(
            "RSE-BRA-001"
        )
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    market.submit_order(

        trader_id="RHINO-FOOD-001",

        lot_id="RSE-BRA-001",

        side=Side.BUY,

        quantity_tonnes=500,

        price=money("1050")
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    market.submit_order(

        trader_id="RHINO-MILL-001",

        lot_id="RSE-BRA-001",

        side=Side.SELL,

        quantity_tonnes=500,

        price=money("1045")
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print()

    print(
        "MARKET SNAPSHOT"
    )

    print(
        "================"
    )

    snapshot = market.snapshot(
        "RSE-BRA-001"
    )

    for key, value in snapshot.items():

        print(
            f"{key:24} {value}"
        )

    print()

    print(
        "TRADE BLOTTTER"
    )

    print(
        "=============="
    )

    for trade in market.trades:

        print(
            trade.buyer,
            "bought",
            trade.quantity_tonnes,
            "t @",
            trade.price,
            trade.currency
        )
