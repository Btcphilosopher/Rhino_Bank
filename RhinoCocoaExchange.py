"""
=============================================================
RHINO COCOA EXCHANGE
RCX 1.0
=============================================================

Physical cocoa spot-pricing and market engine.

Core model:

    Cocoa Benchmark
          +
    Origin Basis
          +
    Quality Premium / Discount
          +
    Certification
          +
    Fermentation / Bean Quality
          +
    Logistics
          +
    FX
          =
    RHINO COCOA SPOT

Also provides:

    - physical cocoa lots
    - bids / offers
    - order book
    - trade matching
    - VWAP
    - market snapshots
    - origin differentials
    - physical availability
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
# COCOA TYPES
# ============================================================

class CocoaType(Enum):

    COCOA_BEANS = "COCOA_BEANS"

    ORGANIC = "ORGANIC"

    CERTIFIED = "CERTIFIED"

    SINGLE_ORIGIN = "SINGLE_ORIGIN"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# COCOA BENCHMARK
# ============================================================

@dataclass
class CocoaBenchmark:

    name: str

    price_usd_tonne: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    source: str = "MARKET_DATA"

    def price(self):

        return money(
            self.price_usd_tonne
        )


# ============================================================
# PHYSICAL COCOA LOT
# ============================================================

@dataclass
class CocoaLot:

    lot_id: str

    cocoa_type: CocoaType

    origin_country: str

    origin_region: str

    producer: str

    quantity_tonnes: Decimal

    bean_grade: str

    fermentation_percent: Decimal

    moisture_percent: Decimal

    bean_count_per_100g: Decimal

    mould_percent: Decimal

    slate_percent: Decimal

    broken_beans_percent: Decimal

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
# ORIGIN BASIS ENGINE
# ============================================================

class CocoaOriginEngine:

    """
    Illustrative physical-origin differentials.

    In production, these should be populated from
    Rhino market data and executable physical quotes.
    """

    BASIS = {

        "Ivory Coast": D("0"),

        "Ghana": D("75"),

        "Nigeria": D("-20"),

        "Cameroon": D("-15"),

        "Ecuador": D("90"),

        "Brazil": D("35"),

        "Indonesia": D("20"),

        "Peru": D("80"),

        "Dominican Republic": D("100"),

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

class CocoaQualityEngine:

    """
    Calculates physical cocoa premium/discount.

    Higher fermentation quality generally receives
    a premium.

    Excess moisture, mould, slate and broken beans
    generate discounts.
    """

    def calculate(
        self,
        lot: CocoaLot
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # FERMENTATION
        # ----------------------------------------------------

        if lot.fermentation_percent >= D("85"):

            adjustment += D("70")

        elif lot.fermentation_percent >= D("75"):

            adjustment += D("35")

        elif lot.fermentation_percent < D("65"):

            adjustment -= D("50")

        # ----------------------------------------------------
        # MOISTURE
        # ----------------------------------------------------

        if lot.moisture_percent <= D("7.5"):

            adjustment += D("10")

        elif lot.moisture_percent <= D("8"):

            adjustment += D("0")

        elif lot.moisture_percent <= D("9"):

            adjustment -= D("20")

        else:

            adjustment -= D("60")

        # ----------------------------------------------------
        # MOULD
        # ----------------------------------------------------

        if lot.mould_percent <= D("1"):

            adjustment += D("5")

        elif lot.mould_percent <= D("2"):

            adjustment -= D("10")

        else:

            adjustment -= D("50")

        # ----------------------------------------------------
        # SLATE
        # ----------------------------------------------------

        if lot.slate_percent <= D("3"):

            adjustment += D("5")

        elif lot.slate_percent <= D("5"):

            adjustment -= D("10")

        else:

            adjustment -= D("35")

        # ----------------------------------------------------
        # BROKEN BEANS
        # ----------------------------------------------------

        if lot.broken_beans_percent > D("5"):

            adjustment -= D("15")

        # ----------------------------------------------------
        # ORGANIC
        # ----------------------------------------------------

        if lot.cocoa_type == CocoaType.ORGANIC:

            adjustment += D("100")

        # ----------------------------------------------------
        # CERTIFICATION
        # ----------------------------------------------------

        certification = (
            lot.certification.upper()
        )

        if certification == "FAIRTRADE":

            adjustment += D("50")

        elif certification == "RAINFOREST":

            adjustment += D("25")

        return money(
            adjustment
        )


# ============================================================
# COCOA SPOT ENGINE
# ============================================================

class CocoaSpotEngine:

    def __init__(self):

        self.origin_engine = (
            CocoaOriginEngine()
        )

        self.quality_engine = (
            CocoaQualityEngine()
        )

    def calculate(
        self,
        benchmark: CocoaBenchmark,
        lot: CocoaLot,
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

        quality_adjustment = (
            self.quality_engine.calculate(
                lot
            )
        )

        logistics = (

            D(lot.freight_usd_tonne)

            + D(lot.insurance_usd_tonne)

            + D(lot.duty_usd_tonne)
        )

        usd_price = (

            benchmark_price

            + origin_basis

            + quality_adjustment

            + logistics
        )

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
class CocoaOrder:

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
class CocoaTrade:

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
# RHINO COCOA EXCHANGE
# ============================================================

class RhinoCocoaExchange:

    def __init__(self):

        self.benchmark: Optional[
            CocoaBenchmark
        ] = None

        self.lots: Dict[
            str,
            CocoaLot
        ] = {}

        self.bids: List[
            CocoaOrder
        ] = []

        self.asks: List[
            CocoaOrder
        ] = []

        self.trades: List[
            CocoaTrade
        ] = []

        self.pricer = (
            CocoaSpotEngine()
        )

    # ========================================================
    # BENCHMARK
    # ========================================================

    def set_benchmark(
        self,
        price_usd_tonne,
        source="MARKET_DATA"
    ):

        self.benchmark = (
            CocoaBenchmark(

                name="RHINO_COCOA_BENCHMARK",

                price_usd_tonne=D(
                    price_usd_tonne
                ),

                source=source
            )
        )

    # ========================================================
    # REGISTER LOT
    # ========================================================

    def register_lot(
        self,
        lot: CocoaLot
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

        if self.benchmark is None:

            raise RuntimeError(
                "Cocoa benchmark unavailable"
            )

        lot = self.lots[
            lot_id
        ]

        return self.pricer.calculate(

            self.benchmark,

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
                    "Insufficient physical cocoa"
                )

        order = CocoaOrder(

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
    # MATCH ENGINE
    # ========================================================

    def match(self):

        executions = []

        while self.bids and self.asks:

            bid = self.bids[0]

            ask = self.asks[0]

            # Physical lot must match

            if bid.lot_id != ask.lot_id:

                break

            # Market does not cross

            if bid.price < ask.price:

                break

            quantity = min(

                bid.remaining,

                ask.remaining
            )

            trade = CocoaTrade(

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
                "RHINO COCOA EXCHANGE",

            "instrument":
                "RCX-COCOA",

            "lot":
                lot_id,

            "origin":
                lot.origin_country,

            "region":
                lot.origin_region,

            "type":
                lot.cocoa_type.value,

            "grade":
                lot.bean_grade,

            "harvest":
                lot.harvest_year,

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
        RhinoCocoaExchange()
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    # Illustrative benchmark value.
    # Production system should receive a validated
    # external market-data feed.

    market.set_benchmark(
        price_usd_tonne=7200,
        source="RHINO_MARKET_DATA"
    )

    # --------------------------------------------------------
    # PHYSICAL LOT
    # --------------------------------------------------------

    IvoryCoast = CocoaLot(

        lot_id="RCX-CIV-001",

        cocoa_type=CocoaType.COCOA_BEANS,

        origin_country="Ivory Coast",

        origin_region="San-Pedro",

        producer="RHINO-COCOA-PRODUCER-CIV",

        quantity_tonnes=2500,

        bean_grade="GRADE_1",

        fermentation_percent=82,

        moisture_percent=7.2,

        bean_count_per_100g=95,

        mould_percent=0.5,

        slate_percent=2.0,

        broken_beans_percent=2.5,

        certification="RAINFOREST",

        harvest_year=2026,

        warehouse="SAN-PEDRO-01",

        freight_usd_tonne=85,

        insurance_usd_tonne=4,

        duty_usd_tonne=0
    )

    market.register_lot(
        IvoryCoast
    )

    # --------------------------------------------------------
    # INDICATIVE PRICE
    # --------------------------------------------------------

    print()

    print(
        "RHINO COCOA EXCHANGE"
    )

    print(
        "===================="
    )

    spot = market.indicative_spot(
        "RCX-CIV-001"
    )

    print(
        "Indicative physical spot:",
        spot,
        "USD/t"
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    market.submit_order(

        trader_id="RHINO-CHOCOLATE-001",

        lot_id="RCX-CIV-001",

        side=Side.BUY,

        quantity_tonnes=250,

        price=7310
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    market.submit_order(

        trader_id="RHINO-TRADER-001",

        lot_id="RCX-CIV-001",

        side=Side.SELL,

        quantity_tonnes=250,

        price=7295
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

    snapshot = market.snapshot(
        "RCX-CIV-001"
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

    for trade in market.trades:

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
