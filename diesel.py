"""
=============================================================
RHINO DIESEL EXCHANGE
RDX 1.0
=============================================================

Physical diesel spot market.

Instruments:

    ULSD_10PPM
    ULSD_15PPM
    DIESEL_50PPM
    MARINE_DIESEL
    RED_DIESEL
    BIODIESEL_BLEND

Pricing:

    benchmark
      + location basis
      + quality basis
      + refinery/supply basis
      + freight
      + storage
      + duty/tax
      + FX

The example benchmark values are illustrative.
A production system should consume licensed/authorised
market-data feeds.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List
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


def volume(value):
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def now():
    return datetime.now(timezone.utc)


# ============================================================
# PRODUCT TYPES
# ============================================================

class DieselProduct(Enum):

    ULSD_10PPM = "ULSD_10PPM"

    ULSD_15PPM = "ULSD_15PPM"

    DIESEL_50PPM = "DIESEL_50PPM"

    MARINE_DIESEL = "MARINE_DIESEL"

    RED_DIESEL = "RED_DIESEL"

    BIODIESEL_BLEND = "BIODIESEL_BLEND"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# DELIVERY LOCATIONS
# ============================================================

class DeliveryPoint(Enum):

    ROTTERDAM = "ROTTERDAM"

    ARA = "ARA"

    ANTWERP = "ANTWERP"

    HAMBURG = "HAMBURG"

    MILFORD_HAVEN = "MILFORD_HAVEN"

    IMMIN = "IMMIN"

    SINGAPORE = "SINGAPORE"

    US_GULF = "US_GULF"

    NEW_YORK_HARBOR = "NEW_YORK_HARBOR"

    LOS_ANGELES = "LOS_ANGELES"


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class DieselBenchmark:

    name: str

    product: DieselProduct

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
# PHYSICAL DIESEL LOT
# ============================================================

@dataclass
class DieselLot:

    lot_id: str

    product: DieselProduct

    delivery_point: DeliveryPoint

    seller: str

    quantity_m3: Decimal

    sulphur_ppm: Decimal

    cetane_number: Decimal

    density_kg_m3: Decimal

    flash_point_c: Decimal

    cold_filter_plugging_point_c: Decimal

    bio_component_percent: Decimal

    refinery: str

    production_month: str

    warehouse: str

    freight_usd_tonne: Decimal = D("0")

    storage_usd_tonne: Decimal = D("0")

    duty_usd_tonne: Decimal = D("0")

    tax_usd_tonne: Decimal = D("0")

    available_m3: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity_m3 = volume(
            self.quantity_m3
        )

        self.available_m3 = (
            self.quantity_m3
        )


# ============================================================
# LOCATION BASIS
# ============================================================

class DieselLocationEngine:

    """
    Illustrative location differentials.

    Replace with live physical-market assessments
    in production.
    """

    BASIS = {

        DeliveryPoint.ROTTERDAM:
            D("0"),

        DeliveryPoint.ARA:
            D("5"),

        DeliveryPoint.ANTWERP:
            D("7"),

        DeliveryPoint.HAMBURG:
            D("15"),

        DeliveryPoint.MILFORD_HAVEN:
            D("18"),

        DeliveryPoint.SINGAPORE:
            D("12"),

        DeliveryPoint.US_GULF:
            D("-25"),

        DeliveryPoint.NEW_YORK_HARBOR:
            D("-10"),

        DeliveryPoint.LOS_ANGELES:
            D("25"),

    }

    def calculate(
        self,
        point
    ):

        return self.BASIS.get(
            point,
            D("0")
        )


# ============================================================
# QUALITY ENGINE
# ============================================================

class DieselQualityEngine:

    def calculate(
        self,
        lot: DieselLot
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # SULPHUR
        # ----------------------------------------------------

        if lot.sulphur_ppm <= D("10"):

            adjustment += D("12")

        elif lot.sulphur_ppm <= D("15"):

            adjustment += D("5")

        elif lot.sulphur_ppm <= D("50"):

            adjustment -= D("20")

        else:

            adjustment -= D("100")

        # ----------------------------------------------------
        # CETANE
        # ----------------------------------------------------

        if lot.cetane_number >= D("55"):

            adjustment += D("20")

        elif lot.cetane_number >= D("51"):

            adjustment += D("5")

        elif lot.cetane_number < D("48"):

            adjustment -= D("30")

        # ----------------------------------------------------
        # FLASH POINT
        # ----------------------------------------------------

        if lot.flash_point_c >= D("60"):

            adjustment += D("5")

        elif lot.flash_point_c < D("55"):

            adjustment -= D("20")

        # ----------------------------------------------------
        # DENSITY
        # ----------------------------------------------------

        if (
            lot.density_kg_m3 >= D("820")
            and
            lot.density_kg_m3 <= D("845")
        ):

            adjustment += D("5")

        # ----------------------------------------------------
        # BIO COMPONENT
        # ----------------------------------------------------

        if lot.bio_component_percent > D("0"):

            adjustment += (
                lot.bio_component_percent
                * D("2")
            )

        return money(
            adjustment
        )


# ============================================================
# SUPPLY ENGINE
# ============================================================

class DieselSupplyEngine:

    """
    Models short-term physical tightness.

    supply_factor:

        > 1 = tighter market
        < 1 = looser market
    """

    def calculate(
        self,
        refinery_availability,
        inventory_days,
        import_pressure
    ):

        adjustment = D("0")

        if refinery_availability < D("85"):

            adjustment += D("35")

        elif refinery_availability > D("95"):

            adjustment -= D("20")

        if inventory_days < D("10"):

            adjustment += D("40")

        elif inventory_days > D("25"):

            adjustment -= D("25")

        if import_pressure < D("1"):

            adjustment += D("20")

        elif import_pressure > D("1.5"):

            adjustment -= D("20")

        return money(
            adjustment
        )


# ============================================================
# SPOT ENGINE
# ============================================================

class DieselSpotEngine:

    def __init__(self):

        self.location_engine = (
            DieselLocationEngine()
        )

        self.quality_engine = (
            DieselQualityEngine()
        )

        self.supply_engine = (
            DieselSupplyEngine()
        )

    def calculate(
        self,
        benchmark,
        lot,
        refinery_availability=95,
        inventory_days=20,
        import_pressure=1.2
    ):

        benchmark_price = (
            benchmark.price()
        )

        location_basis = (
            self.location_engine.calculate(
                lot.delivery_point
            )
        )

        quality_basis = (
            self.quality_engine.calculate(
                lot
            )
        )

        supply_basis = (
            self.supply_engine.calculate(

                D(refinery_availability),

                D(inventory_days),

                D(import_pressure)
            )
        )

        logistics = (

            lot.freight_usd_tonne

            + lot.storage_usd_tonne

            + lot.duty_usd_tonne

            + lot.tax_usd_tonne
        )

        return money(

            benchmark_price

            + location_basis

            + quality_basis

            + supply_basis

            + logistics
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class DieselOrder:

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    quantity_m3: Decimal

    price_usd_tonne: Decimal

    remaining_m3: Decimal = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.quantity_m3 = volume(
            self.quantity_m3
        )

        self.remaining_m3 = (
            self.quantity_m3
        )


# ============================================================
# TRADE
# ============================================================

@dataclass
class DieselTrade:

    trade_id: str

    lot_id: str

    buyer: str

    seller: str

    quantity_m3: Decimal

    price_usd_tonne: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional_usd(self):

        # Approximate conversion for demonstration.
        # Production settlement should use actual
        # measured density and contractual conversion.

        return money(
            self.quantity_m3
            * self.price_usd_tonne
        )


# ============================================================
# RHINO DIESEL EXCHANGE
# ============================================================

class RhinoDieselExchange:

    def __init__(self):

        self.benchmarks: Dict[
            DieselProduct,
            DieselBenchmark
        ] = {}

        self.lots: Dict[
            str,
            DieselLot
        ] = {}

        self.bids: List[
            DieselOrder
        ] = []

        self.asks: List[
            DieselOrder
        ] = []

        self.trades: List[
            DieselTrade
        ] = []

        self.pricer = (
            DieselSpotEngine()
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
        ] = DieselBenchmark(

            name="RHINO_DIESEL_BENCHMARK",

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
        lot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # ========================================================
    # SPOT PRICE
    # ========================================================

    def spot(
        self,
        lot_id
    ):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.product
        )

        if benchmark is None:

            raise RuntimeError(
                "Diesel benchmark unavailable"
            )

        return self.pricer.calculate(

            benchmark,

            lot
        )

    # ========================================================
    # ORDER ENTRY
    # ========================================================

    def submit_order(
        self,
        trader_id,
        lot_id,
        side,
        quantity_m3,
        price_usd_tonne
    ):

        lot = self.lots[
            lot_id
        ]

        quantity = volume(
            quantity_m3
        )

        if side == Side.SELL:

            if quantity > lot.available_m3:

                raise ValueError(
                    "Insufficient physical diesel"
                )

        order = DieselOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            quantity_m3=quantity,

            price_usd_tonne=money(
                price_usd_tonne
            )
        )

        if side == Side.BUY:

            self.bids.append(
                order
            )

            self.bids.sort(
                key=lambda x: (
                    -x.price_usd_tonne,
                    x.timestamp
                )
            )

        else:

            self.asks.append(
                order
            )

            self.asks.sort(
                key=lambda x: (
                    x.price_usd_tonne,
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

            if bid.lot_id != ask.lot_id:

                break

            if (
                bid.price_usd_tonne
                <
                ask.price_usd_tonne
            ):

                break

            quantity = min(

                bid.remaining_m3,

                ask.remaining_m3
            )

            trade = DieselTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=bid.lot_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity_m3=quantity,

                price_usd_tonne=(
                    ask.price_usd_tonne
                )
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining_m3 -= quantity

            ask.remaining_m3 -= quantity

            lot = self.lots[
                bid.lot_id
            ]

            lot.available_m3 -= quantity

            if bid.remaining_m3 <= 0:

                self.bids.pop(0)

            if ask.remaining_m3 <= 0:

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

            t.quantity_m3
            * t.price_usd_tonne

            for t in trades
        )

        quantity = sum(

            t.quantity_m3

            for t in trades
        )

        if quantity == 0:

            return None

        return money(
            value / quantity
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
                "RHINO DIESEL EXCHANGE",

            "instrument":
                f"RDX-{lot.product.value}",

            "delivery":
                lot.delivery_point.value,

            "available_m3":
                str(lot.available_m3),

            "sulphur_ppm":
                str(lot.sulphur_ppm),

            "cetane":
                str(lot.cetane_number),

            "density":
                str(lot.density_kg_m3),

            "bio_component":
                str(lot.bio_component_percent),

            "spot_usd_tonne":
                str(self.spot(lot_id)),

            "best_bid":
                str(
                    max(
                        (
                            x.price_usd_tonne
                            for x in bids
                        ),
                        default=D("0")
                    )
                ),

            "best_ask":
                str(
                    min(
                        (
                            x.price_usd_tonne
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
        RhinoDieselExchange()
    )

    # --------------------------------------------------------
    # ILLUSTRATIVE BENCHMARK
    # --------------------------------------------------------

    exchange.set_benchmark(

        DieselProduct.ULSD_10PPM,

        850,

        "RHINO_MARKET_DATA"
    )

    # --------------------------------------------------------
    # PHYSICAL LOT
    # --------------------------------------------------------

    lot = DieselLot(

        lot_id="RDX-ARA-ULSD-001",

        product=DieselProduct.ULSD_10PPM,

        delivery_point=DeliveryPoint.ARA,

        seller="RHINO-REFINER-001",

        quantity_m3=5000,

        sulphur_ppm=10,

        cetane_number=53,

        density_kg_m3=835,

        flash_point_c=62,

        cold_filter_plugging_point_c=-10,

        bio_component_percent=7,

        refinery="RHINO-REFINERY-EU-01",

        production_month="2026-09",

        warehouse="ROTTERDAM-TANK-07",

        freight_usd_tonne=12,

        storage_usd_tonne=4,

        duty_usd_tonne=0,

        tax_usd_tonne=0
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    spot = exchange.spot(
        "RDX-ARA-ULSD-001"
    )

    print()

    print(
        "RHINO DIESEL EXCHANGE"
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
    # BUY
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-FUEL-BUYER-001",

        lot_id="RDX-ARA-ULSD-001",

        side=Side.BUY,

        quantity_m3=500,

        price_usd_tonne=900
    )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-REFINER-001",

        lot_id="RDX-ARA-ULSD-001",

        side=Side.SELL,

        quantity_m3=500,

        price_usd_tonne=890
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
        "RDX-ARA-ULSD-001"
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

            trade.quantity_m3,

            "m3 @",

            trade.price_usd_tonne,

            "USD/t",

            "| Notional:",

            trade.notional_usd
        )
