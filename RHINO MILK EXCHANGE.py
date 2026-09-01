"""
=============================================================
RHINO MILK EXCHANGE
RMX 1.0
=============================================================

Physical milk spot-pricing and trading engine.

Products:

    RAW_MILK
    ORGANIC_MILK
    A2_MILK
    HIGH_PROTEIN_MILK
    CREAM
    SKIM_MILK

Pricing:

    Benchmark
      + butterfat value
      + protein value
      + other-solids value
      + quality
      + location
      + logistics
      + supply/demand
      + certification
      =
    RHINO MILK SPOT

All example prices are illustrative.
Production deployment should use validated,
licensed market-data sources and applicable
milk-marketing regulations.
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
        Decimal("0.0001"),
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
# MILK PRODUCTS
# ============================================================

class MilkProduct(Enum):

    RAW_MILK = "RAW_MILK"

    ORGANIC_MILK = "ORGANIC_MILK"

    A2_MILK = "A2_MILK"

    HIGH_PROTEIN_MILK = "HIGH_PROTEIN_MILK"

    CREAM = "CREAM"

    SKIM_MILK = "SKIM_MILK"


class MilkClass(Enum):

    CLASS_I = "CLASS_I"

    CLASS_II = "CLASS_II"

    CLASS_III = "CLASS_III"

    CLASS_IV = "CLASS_IV"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# MILK BENCHMARK
# ============================================================

@dataclass
class MilkBenchmark:

    name: str

    milk_class: MilkClass

    price_usd_cwt: Decimal

    source: str

    timestamp: datetime = field(
        default_factory=now
    )

    def price_per_kg(self):

        # 1 US cwt = 45.3592 kg

        return money(
            self.price_usd_cwt
            / D("45.3592")
        )


# ============================================================
# PHYSICAL MILK LOT
# ============================================================

@dataclass
class MilkLot:

    lot_id: str

    product: MilkProduct

    milk_class: MilkClass

    origin_region: str

    producer: str

    quantity_litres: Decimal

    fat_percent: Decimal

    true_protein_percent: Decimal

    lactose_percent: Decimal

    other_solids_percent: Decimal

    somatic_cell_count: Decimal

    bacteria_count: Decimal

    temperature_c: Decimal

    antibiotic_status: str

    organic_certified: bool

    a2_certified: bool

    production_date: str

    collection_point: str

    destination: str

    haulage_usd_litre: Decimal = D("0")

    chilling_usd_litre: Decimal = D("0")

    storage_usd_litre: Decimal = D("0")

    available_litres: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity_litres = volume(
            self.quantity_litres
        )

        self.available_litres = (
            self.quantity_litres
        )


# ============================================================
# COMPONENT PRICES
# ============================================================

@dataclass
class MilkComponents:

    butterfat_usd_lb: Decimal

    protein_usd_lb: Decimal

    other_solids_usd_lb: Decimal

    nonfat_solids_usd_lb: Decimal


# ============================================================
# REGIONAL BASIS
# ============================================================

class MilkLocationEngine:

    """
    Illustrative regional basis.

    Replace with actual physical-market
    assessments in production.
    """

    BASIS = {

        "NORTH_EAST": D("0.000"),

        "MIDWEST": D("-0.002"),

        "SOUTH_EAST": D("0.004"),

        "WEST": D("-0.001"),

        "SOUTH_WEST": D("0.003"),

        "NORTH_WEST": D("0.001"),

        "YORKSHIRE": D("0.002"),

        "EAST_ANGlia": D("0.003"),

        "WEST_COUNTRY": D("0.001"),

        "SCOTLAND": D("0.004"),

    }

    def calculate(
        self,
        region
    ):

        return self.BASIS.get(
            region.upper(),
            D("0")
        )


# ============================================================
# QUALITY ENGINE
# ============================================================

class MilkQualityEngine:

    def calculate(
        self,
        lot: MilkLot
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # BUTTERFAT
        # ----------------------------------------------------

        if lot.fat_percent >= D("4.2"):

            adjustment += D("0.006")

        elif lot.fat_percent >= D("3.8"):

            adjustment += D("0.003")

        elif lot.fat_percent < D("3.2"):

            adjustment -= D("0.004")

        # ----------------------------------------------------
        # PROTEIN
        # ----------------------------------------------------

        if lot.true_protein_percent >= D("3.5"):

            adjustment += D("0.005")

        elif lot.true_protein_percent >= D("3.2"):

            adjustment += D("0.002")

        elif lot.true_protein_percent < D("3.0"):

            adjustment -= D("0.004")

        # ----------------------------------------------------
        # SOMATIC CELL COUNT
        # ----------------------------------------------------

        if lot.somatic_cell_count <= D("150000"):

            adjustment += D("0.004")

        elif lot.somatic_cell_count <= D("250000"):

            adjustment += D("0.001")

        elif lot.somatic_cell_count <= D("400000"):

            adjustment -= D("0.003")

        else:

            adjustment -= D("0.010")

        # ----------------------------------------------------
        # BACTERIA
        # ----------------------------------------------------

        if lot.bacteria_count <= D("10000"):

            adjustment += D("0.003")

        elif lot.bacteria_count <= D("50000"):

            adjustment += D("0")

        else:

            adjustment -= D("0.006")

        # ----------------------------------------------------
        # ANTIBIOTICS
        # ----------------------------------------------------

        if lot.antibiotic_status.upper() == "PASS":

            adjustment += D("0")

        else:

            # In a real exchange this should generally
            # be an eligibility / rejection condition,
            # not simply a price discount.

            raise ValueError(
                "Milk lot failed antibiotic compliance"
            )

        # ----------------------------------------------------
        # ORGANIC
        # ----------------------------------------------------

        if lot.organic_certified:

            adjustment += D("0.025")

        # ----------------------------------------------------
        # A2
        # ----------------------------------------------------

        if lot.a2_certified:

            adjustment += D("0.015")

        return money(
            adjustment
        )


# ============================================================
# COMPONENT VALUE ENGINE
# ============================================================

class MilkComponentEngine:

    def calculate(
        self,
        lot: MilkLot,
        components: MilkComponents
    ):

        # Approximate component contribution
        # per litre for demonstration.

        fat_value = (
            lot.fat_percent
            / D("100")
            * components.butterfat_usd_lb
            * D("0.453592")
        )

        protein_value = (
            lot.true_protein_percent
            / D("100")
            * components.protein_usd_lb
            * D("0.453592")
        )

        solids_value = (
            lot.other_solids_percent
            / D("100")
            * components.other_solids_usd_lb
            * D("0.453592")
        )

        return money(
            fat_value
            + protein_value
            + solids_value
        )


# ============================================================
# SUPPLY / DEMAND
# ============================================================

class MilkSupplyEngine:

    def calculate(
        self,
        supply_index,
        processor_demand,
        inventory_index
    ):

        adjustment = D("0")

        if supply_index < D("0.95"):

            adjustment += D("0.006")

        elif supply_index > D("1.05"):

            adjustment -= D("0.005")

        if processor_demand > D("1.05"):

            adjustment += D("0.004")

        elif processor_demand < D("0.95"):

            adjustment -= D("0.004")

        if inventory_index > D("1.10"):

            adjustment -= D("0.003")

        elif inventory_index < D("0.90"):

            adjustment += D("0.003")

        return money(
            adjustment
        )


# ============================================================
# SPOT ENGINE
# ============================================================

class MilkSpotEngine:

    def __init__(self):

        self.location_engine = (
            MilkLocationEngine()
        )

        self.quality_engine = (
            MilkQualityEngine()
        )

        self.component_engine = (
            MilkComponentEngine()
        )

        self.supply_engine = (
            MilkSupplyEngine()
        )

    def calculate(
        self,
        benchmark,
        lot,
        components,
        supply_index=1.0,
        processor_demand=1.0,
        inventory_index=1.0
    ):

        benchmark_price = (
            benchmark.price_per_kg()
            / D("1000")
        )

        component_value = (
            self.component_engine.calculate(
                lot,
                components
            )
        )

        quality_basis = (
            self.quality_engine.calculate(
                lot
            )
        )

        location_basis = (
            self.location_engine.calculate(
                lot.origin_region
            )
        )

        supply_basis = (
            self.supply_engine.calculate(
                D(supply_index),
                D(processor_demand),
                D(inventory_index)
            )
        )

        logistics = (

            lot.haulage_usd_litre

            + lot.chilling_usd_litre

            + lot.storage_usd_litre
        )

        return money(

            benchmark_price

            + component_value

            + quality_basis

            + location_basis

            + supply_basis

            - logistics
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class MilkOrder:

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    quantity_litres: Decimal

    price_usd_litre: Decimal

    remaining_litres: Decimal = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.quantity_litres = volume(
            self.quantity_litres
        )

        self.remaining_litres = (
            self.quantity_litres
        )


# ============================================================
# TRADE
# ============================================================

@dataclass
class MilkTrade:

    trade_id: str

    lot_id: str

    buyer: str

    seller: str

    quantity_litres: Decimal

    price_usd_litre: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional_usd(self):

        return money(
            self.quantity_litres
            * self.price_usd_litre
        )


# ============================================================
# RHINO MILK EXCHANGE
# ============================================================

class RhinoMilkExchange:

    def __init__(self):

        self.benchmarks: Dict[
            MilkClass,
            MilkBenchmark
        ] = {}

        self.lots: Dict[
            str,
            MilkLot
        ] = {}

        self.bids: List[
            MilkOrder
        ] = []

        self.asks: List[
            MilkOrder
        ] = []

        self.trades: List[
            MilkTrade
        ] = []

        self.components = MilkComponents(

            butterfat_usd_lb=D("2.00"),

            protein_usd_lb=D("2.50"),

            other_solids_usd_lb=D("0.40"),

            nonfat_solids_usd_lb=D("1.30")
        )

        self.pricer = (
            MilkSpotEngine()
        )

    # ========================================================
    # BENCHMARK
    # ========================================================

    def set_benchmark(
        self,
        milk_class,
        price_usd_cwt,
        source="RHINO_MARKET_DATA"
    ):

        self.benchmarks[
            milk_class
        ] = MilkBenchmark(

            name="RHINO_MILK_BENCHMARK",

            milk_class=milk_class,

            price_usd_cwt=D(
                price_usd_cwt
            ),

            source=source
        )

    # ========================================================
    # COMPONENTS
    # ========================================================

    def set_components(
        self,
        butterfat,
        protein,
        other_solids,
        nonfat_solids
    ):

        self.components = MilkComponents(

            butterfat_usd_lb=D(
                butterfat
            ),

            protein_usd_lb=D(
                protein
            ),

            other_solids_usd_lb=D(
                other_solids
            ),

            nonfat_solids_usd_lb=D(
                nonfat_solids
            )
        )

    # ========================================================
    # REGISTER LOT
    # ========================================================

    def register_lot(
        self,
        lot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # ========================================================
    # SPOT
    # ========================================================

    def spot(
        self,
        lot_id
    ):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.milk_class
        )

        if benchmark is None:

            raise RuntimeError(
                "Milk benchmark unavailable"
            )

        return self.pricer.calculate(

            benchmark,

            lot,

            self.components
        )

    # ========================================================
    # ORDER
    # ========================================================

    def submit_order(
        self,
        trader_id,
        lot_id,
        side,
        quantity_litres,
        price_usd_litre
    ):

        lot = self.lots[
            lot_id
        ]

        quantity = volume(
            quantity_litres
        )

        if side == Side.SELL:

            if quantity > lot.available_litres:

                raise ValueError(
                    "Insufficient milk inventory"
                )

        order = MilkOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            quantity_litres=quantity,

            price_usd_litre=money(
                price_usd_litre
            )
        )

        if side == Side.BUY:

            self.bids.append(
                order
            )

            self.bids.sort(
                key=lambda x: (
                    -x.price_usd_litre,
                    x.timestamp
                )
            )

        else:

            self.asks.append(
                order
            )

            self.asks.sort(
                key=lambda x: (
                    x.price_usd_litre,
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

            if (
                bid.price_usd_litre
                <
                ask.price_usd_litre
            ):

                break

            quantity = min(

                bid.remaining_litres,

                ask.remaining_litres
            )

            trade = MilkTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=bid.lot_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity_litres=quantity,

                price_usd_litre=(
                    ask.price_usd_litre
                )
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining_litres -= (
                quantity
            )

            ask.remaining_litres -= (
                quantity
            )

            lot = self.lots[
                bid.lot_id
            ]

            lot.available_litres -= (
                quantity
            )

            if bid.remaining_litres <= 0:

                self.bids.pop(0)

            if ask.remaining_litres <= 0:

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

            t.quantity_litres
            * t.price_usd_litre

            for t in trades
        )

        quantity = sum(

            t.quantity_litres

            for t in trades
        )

        if quantity == 0:

            return None

        return money(
            value / quantity
        )

    # ========================================================
    # SNAPSHOT
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
                "RHINO MILK EXCHANGE",

            "instrument":
                f"RMX-{lot.product.value}",

            "class":
                lot.milk_class.value,

            "region":
                lot.origin_region,

            "available_litres":
                str(lot.available_litres),

            "fat":
                str(lot.fat_percent),

            "protein":
                str(lot.true_protein_percent),

            "lactose":
                str(lot.lactose_percent),

            "somatic_cell_count":
                str(lot.somatic_cell_count),

            "temperature":
                str(lot.temperature_c),

            "spot":
                str(
                    self.spot(lot_id)
                ),

            "best_bid":
                str(
                    max(
                        (
                            x.price_usd_litre
                            for x in bids
                        ),
                        default=D("0")
                    )
                ),

            "best_ask":
                str(
                    min(
                        (
                            x.price_usd_litre
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
        RhinoMilkExchange()
    )

    # --------------------------------------------------------
    # ILLUSTRATIVE BENCHMARK
    # --------------------------------------------------------

    exchange.set_benchmark(

        MilkClass.CLASS_III,

        16.50,

        "RHINO_MARKET_DATA"
    )

    # --------------------------------------------------------
    # COMPONENT PRICES
    # --------------------------------------------------------

    exchange.set_components(

        butterfat=2.00,

        protein=2.50,

        other_solids=0.40,

        nonfat_solids=1.30
    )

    # --------------------------------------------------------
    # PHYSICAL LOT
    # --------------------------------------------------------

    lot = MilkLot(

        lot_id="RMX-YORK-001",

        product=MilkProduct.RAW_MILK,

        milk_class=MilkClass.CLASS_III,

        origin_region="YORKSHIRE",

        producer="RHINO-DAIRY-FARM-001",

        quantity_litres=100000,

        fat_percent=4.1,

        true_protein_percent=3.45,

        lactose_percent=4.8,

        other_solids_percent=5.6,

        somatic_cell_count=150000,

        bacteria_count=10000,

        temperature_c=3.8,

        antibiotic_status="PASS",

        organic_certified=False,

        a2_certified=False,

        production_date="2026-09-01",

        collection_point="YORKSHIRE-TANK-01",

        destination="RHINO-DAIRY-PLANT-01",

        haulage_usd_litre=D("0.004"),

        chilling_usd_litre=D("0.001"),

        storage_usd_litre=D("0.000")
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    spot = exchange.spot(
        "RMX-YORK-001"
    )

    print()

    print(
        "RHINO MILK EXCHANGE"
    )

    print(
        "==================="
    )

    print(
        "Indicative spot:",
        spot,
        "USD/litre"
    )

    # --------------------------------------------------------
    # BUYER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-DAIRY-PROCESSOR",

        lot_id="RMX-YORK-001",

        side=Side.BUY,

        quantity_litres=20000,

        price_usd_litre=0.42
    )

    # --------------------------------------------------------
    # SELLER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-FARMER-001",

        lot_id="RMX-YORK-001",

        side=Side.SELL,

        quantity_litres=20000,

        price_usd_litre=0.415
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
        "RMX-YORK-001"
    )

    for key, value in snapshot.items():

        print(
            f"{key:28} {value}"
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

            trade.quantity_litres,

            "litres @",

            trade.price_usd_litre,

            "USD/litre",

            "| Notional:",

            trade.notional_usd
        )
