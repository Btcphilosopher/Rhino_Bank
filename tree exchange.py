"""
=============================================================
RHINO TREE EXCHANGE
RTX 1.0
=============================================================

Physical spot-market engine for nursery-grown tree saplings.

Pricing dimensions:

    Species
    Age
    Height
    Stem diameter
    Root condition
    Container / bare-root status
    Health
    Provenance
    Certification
    Season
    Quantity
    Logistics
    Supply / demand

Example prices are illustrative.

This is a commodity-market software model, not a forestry
management prescription.
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


def quantity(value):
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def now():
    return datetime.now(timezone.utc)


# ============================================================
# SPECIES
# ============================================================

class TreeSpecies(Enum):

    ENGLISH_OAK = "ENGLISH_OAK"

    SESSILE_OAK = "SESSILE_OAK"

    BEECH = "BEECH"

    SILVER_BIRCH = "SILVER_BIRCH"

    ASH = "ASH"

    FIELD_MAPLE = "FIELD_MAPLE"

    SYCAMORE = "SYCAMORE"

    SCOTS_PINE = "SCOTS_PINE"

    NORWAY_SPRUCE = "NORWAY_SPRUCE"

    SITKA_SPRUCE = "SITKA_SPRUCE"

    DOUGLAS_FIR = "DOUGLAS_FIR"

    WESTERN_RED_CEDAR = "WESTERN_RED_CEDAR"

    HAWTHORN = "HAWTHORN"

    HORNBEAM = "HORNBEAM"

    WILD_CHERRY = "WILD_CHERRY"

    APPLE = "APPLE"

    PEAR = "PEAR"


class StockType(Enum):

    BARE_ROOT = "BARE_ROOT"

    ROOTBALL = "ROOTBALL"

    CONTAINER = "CONTAINER"


class Grade(Enum):

    PREMIUM = "PREMIUM"

    A = "A"

    B = "B"

    STANDARD = "STANDARD"

    REFORESTATION = "REFORESTATION"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# PROVENANCE
# ============================================================

class Provenance(Enum):

    LOCAL = "LOCAL"

    UK_NATIVE = "UK_NATIVE"

    CERTIFIED = "CERTIFIED"

    IMPORTED = "IMPORTED"

    UNKNOWN = "UNKNOWN"


# ============================================================
# TREE LOT
# ============================================================

@dataclass
class TreeLot:

    lot_id: str

    species: TreeSpecies

    grade: Grade

    stock_type: StockType

    provenance: Provenance

    nursery: str

    nursery_reference: str

    quantity: Decimal

    age_years: Decimal

    height_cm: Decimal

    stem_diameter_mm: Decimal

    root_quality: Decimal

    health_score: Decimal

    form_score: Decimal

    disease_score: Decimal

    certification: str

    harvest_or_lifting_date: str

    delivery_region: str

    delivery_window: str

    haulage_gbp_per_tree: Decimal = D("0")

    available_quantity: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity = quantity(
            self.quantity
        )

        self.available_quantity = (
            self.quantity
        )


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class TreeBenchmark:

    symbol: str

    species: TreeSpecies

    price_gbp_tree: Decimal

    source: str

    timestamp: datetime = field(
        default_factory=now
    )


# ============================================================
# SPECIES BASIS
# ============================================================

class SpeciesEngine:

    BASIS = {

        TreeSpecies.ENGLISH_OAK:
            D("0.00"),

        TreeSpecies.SESSILE_OAK:
            D("0.20"),

        TreeSpecies.BEECH:
            D("0.15"),

        TreeSpecies.SILVER_BIRCH:
            D("0.10"),

        TreeSpecies.ASH:
            D("0.05"),

        TreeSpecies.FIELD_MAPLE:
            D("0.12"),

        TreeSpecies.SYCAMORE:
            D("0.04"),

        TreeSpecies.SCOTS_PINE:
            D("0.08"),

        TreeSpecies.NORWAY_SPRUCE:
            D("0.06"),

        TreeSpecies.SITKA_SPRUCE:
            D("0.04"),

        TreeSpecies.DOUGLAS_FIR:
            D("0.15"),

        TreeSpecies.WESTERN_RED_CEDAR:
            D("0.25"),

        TreeSpecies.HAWTHORN:
            D("0.08"),

        TreeSpecies.HORNBEAM:
            D("0.14"),

        TreeSpecies.WILD_CHERRY:
            D("0.18"),

        TreeSpecies.APPLE:
            D("0.20"),

        TreeSpecies.PEAR:
            D("0.22")
    }

    def calculate(self, species):

        return self.BASIS.get(
            species,
            D("0")
        )


# ============================================================
# AGE / SIZE ENGINE
# ============================================================

class SizeEngine:

    def calculate(self, lot):

        adjustment = D("0")

        # Larger established saplings command
        # a higher physical price.

        if lot.height_cm >= D("150"):

            adjustment += D("0.35")

        elif lot.height_cm >= D("100"):

            adjustment += D("0.18")

        elif lot.height_cm >= D("60"):

            adjustment += D("0.05")

        # Stem diameter

        if lot.stem_diameter_mm >= D("25"):

            adjustment += D("0.30")

        elif lot.stem_diameter_mm >= D("15"):

            adjustment += D("0.12")

        # Age

        if lot.age_years >= D("5"):

            adjustment += D("0.25")

        elif lot.age_years >= D("3"):

            adjustment += D("0.12")

        return money(
            adjustment
        )


# ============================================================
# QUALITY ENGINE
# ============================================================

class QualityEngine:

    def calculate(self, lot):

        adjustment = D("0")

        # Grade

        grade_basis = {

            Grade.PREMIUM: D("0.50"),

            Grade.A: D("0.25"),

            Grade.B: D("0.05"),

            Grade.STANDARD: D("0"),

            Grade.REFORESTATION: D("-0.05")
        }

        adjustment += grade_basis[
            lot.grade
        ]

        # Root quality

        if lot.root_quality >= D("9"):

            adjustment += D("0.35")

        elif lot.root_quality >= D("7"):

            adjustment += D("0.15")

        elif lot.root_quality < D("5"):

            adjustment -= D("0.25")

        # Health

        if lot.health_score >= D("9"):

            adjustment += D("0.35")

        elif lot.health_score >= D("7"):

            adjustment += D("0.15")

        elif lot.health_score < D("5"):

            adjustment -= D("0.40")

        # Form

        if lot.form_score >= D("9"):

            adjustment += D("0.20")

        elif lot.form_score < D("5"):

            adjustment -= D("0.20")

        # Disease score

        if lot.disease_score < D("3"):

            adjustment -= D("0.50")

        elif lot.disease_score < D("5"):

            adjustment -= D("0.20")

        return money(
            adjustment
        )


# ============================================================
# STOCK TYPE ENGINE
# ============================================================

class StockEngine:

    BASIS = {

        StockType.BARE_ROOT:
            D("0"),

        StockType.ROOTBALL:
            D("0.30"),

        StockType.CONTAINER:
            D("0.40")
    }

    def calculate(self, stock_type):

        return self.BASIS.get(
            stock_type,
            D("0")
        )


# ============================================================
# PROVENANCE ENGINE
# ============================================================

class ProvenanceEngine:

    BASIS = {

        Provenance.LOCAL:
            D("0.12"),

        Provenance.UK_NATIVE:
            D("0.15"),

        Provenance.CERTIFIED:
            D("0.25"),

        Provenance.IMPORTED:
            D("-0.05"),

        Provenance.UNKNOWN:
            D("-0.15")
    }

    def calculate(self, provenance):

        return self.BASIS.get(
            provenance,
            D("0")
        )


# ============================================================
# SEASON ENGINE
# ============================================================

class SeasonEngine:

    def calculate(self, delivery_month):

        # Illustrative seasonal basis.

        if delivery_month in (
            11, 12, 1, 2, 3
        ):

            return D("0.10")

        if delivery_month in (
            4, 5, 10
        ):

            return D("0.05")

        return D("-0.05")


# ============================================================
# SUPPLY / DEMAND ENGINE
# ============================================================

class SupplyDemandEngine:

    def calculate(
        self,
        supply_index,
        demand_index
    ):

        adjustment = D("0")

        supply = D(supply_index)

        demand = D(demand_index)

        if supply < D("0.90"):

            adjustment += D("0.35")

        elif supply < D("0.97"):

            adjustment += D("0.15")

        elif supply > D("1.10"):

            adjustment -= D("0.30")

        elif supply > D("1.03"):

            adjustment -= D("0.12")

        if demand > D("1.10"):

            adjustment += D("0.35")

        elif demand > D("1.03"):

            adjustment += D("0.15")

        elif demand < D("0.90"):

            adjustment -= D("0.25")

        return money(
            adjustment
        )


# ============================================================
# SPOT PRICE ENGINE
# ============================================================

class TreeSpotEngine:

    def __init__(self):

        self.species = SpeciesEngine()

        self.size = SizeEngine()

        self.quality = QualityEngine()

        self.stock = StockEngine()

        self.provenance = ProvenanceEngine()

        self.season = SeasonEngine()

        self.supply_demand = (
            SupplyDemandEngine()
        )

    def calculate(
        self,
        benchmark,
        lot,
        delivery_month=11,
        supply_index=1.0,
        demand_index=1.0
    ):

        base = (
            benchmark.price_gbp_tree
        )

        species_basis = (
            self.species.calculate(
                lot.species
            )
        )

        size_basis = (
            self.size.calculate(
                lot
            )
        )

        quality_basis = (
            self.quality.calculate(
                lot
            )
        )

        stock_basis = (
            self.stock.calculate(
                lot.stock_type
            )
        )

        provenance_basis = (
            self.provenance.calculate(
                lot.provenance
            )
        )

        seasonal_basis = (
            self.season.calculate(
                delivery_month
            )
        )

        market_basis = (
            self.supply_demand.calculate(
                supply_index,
                demand_index
            )
        )

        logistics = (
            lot.haulage_gbp_per_tree
        )

        return money(

            base

            + species_basis

            + size_basis

            + quality_basis

            + stock_basis

            + provenance_basis

            + seasonal_basis

            + market_basis

            - logistics
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class TreeOrder:

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    quantity: Decimal

    price_gbp_tree: Decimal

    remaining_quantity: Decimal = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.quantity = quantity(
            self.quantity
        )

        self.remaining_quantity = (
            self.quantity
        )


# ============================================================
# TRADE
# ============================================================

@dataclass
class TreeTrade:

    trade_id: str

    lot_id: str

    buyer: str

    seller: str

    quantity: Decimal

    price_gbp_tree: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional_gbp(self):

        return money(

            self.quantity
            * self.price_gbp_tree
        )


# ============================================================
# RHINO TREE EXCHANGE
# ============================================================

class RhinoTreeExchange:

    def __init__(self):

        self.benchmarks = {}

        self.lots: Dict[
            str,
            TreeLot
        ] = {}

        self.bids: List[
            TreeOrder
        ] = []

        self.asks: List[
            TreeOrder
        ] = []

        self.trades: List[
            TreeTrade
        ] = []

        self.pricer = (
            TreeSpotEngine()
        )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    def set_benchmark(
        self,
        species,
        price_gbp_tree,
        symbol,
        source="RHINO_FORESTRY_DATA"
    ):

        self.benchmarks[
            species
        ] = TreeBenchmark(

            symbol=symbol,

            species=species,

            price_gbp_tree=D(
                price_gbp_tree
            ),

            source=source
        )

    # --------------------------------------------------------
    # REGISTER LOT
    # --------------------------------------------------------

    def register_lot(
        self,
        lot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    def spot(
        self,
        lot_id,
        delivery_month=11
    ):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.species
        )

        if benchmark is None:

            raise RuntimeError(
                "Tree benchmark unavailable"
            )

        return self.pricer.calculate(

            benchmark,

            lot,

            delivery_month
        )

    # --------------------------------------------------------
    # ORDER ENTRY
    # --------------------------------------------------------

    def submit_order(
        self,
        trader_id,
        lot_id,
        side,
        quantity,
        price_gbp_tree
    ):

        lot = self.lots[
            lot_id
        ]

        quantity_value = quantity(
            quantity
        )

        if side == Side.SELL:

            if (
                quantity_value
                >
                lot.available_quantity
            ):

                raise ValueError(
                    "Insufficient physical inventory"
                )

        order = TreeOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            quantity=quantity_value,

            price_gbp_tree=money(
                price_gbp_tree
            )
        )

        if side == Side.BUY:

            self.bids.append(
                order
            )

            self.bids.sort(

                key=lambda x: (

                    -x.price_gbp_tree,

                    x.timestamp
                )
            )

        else:

            self.asks.append(
                order
            )

            self.asks.sort(

                key=lambda x: (

                    x.price_gbp_tree,

                    x.timestamp
                )
            )

        return self.match()

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    def match(self):

        executions = []

        while self.bids and self.asks:

            bid = self.bids[0]

            ask = self.asks[0]

            if bid.lot_id != ask.lot_id:

                break

            if (
                bid.price_gbp_tree
                <
                ask.price_gbp_tree
            ):

                break

            trade_quantity = min(

                bid.remaining_quantity,

                ask.remaining_quantity
            )

            trade = TreeTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=bid.lot_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity=trade_quantity,

                price_gbp_tree=(
                    ask.price_gbp_tree
                )
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining_quantity -= (
                trade_quantity
            )

            ask.remaining_quantity -= (
                trade_quantity
            )

            lot = self.lots[
                bid.lot_id
            ]

            lot.available_quantity -= (
                trade_quantity
            )

            if bid.remaining_quantity <= 0:

                self.bids.pop(0)

            if ask.remaining_quantity <= 0:

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

            t

            for t in self.trades

            if t.lot_id == lot_id
        ]

        if not trades:

            return None

        value = sum(

            t.quantity
            * t.price_gbp_tree

            for t in trades
        )

        volume = sum(

            t.quantity

            for t in trades
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

        bids = [

            x for x in self.bids

            if x.lot_id == lot_id
        ]

        asks = [

            x for x in self.asks

            if x.lot_id == lot_id
        ]

        return {

            "market":
                "RHINO TREE EXCHANGE",

            "instrument":
                f"RTX-{lot.species.value}",

            "lot_id":
                lot.lot_id,

            "species":
                lot.species.value,

            "grade":
                lot.grade.value,

            "stock_type":
                lot.stock_type.value,

            "provenance":
                lot.provenance.value,

            "age_years":
                str(
                    lot.age_years
                ),

            "height_cm":
                str(
                    lot.height_cm
                ),

            "stem_diameter_mm":
                str(
                    lot.stem_diameter_mm
                ),

            "root_quality":
                str(
                    lot.root_quality
                ),

            "health_score":
                str(
                    lot.health_score
                ),

            "available_trees":
                str(
                    lot.available_quantity
                ),

            "spot_gbp_tree":
                str(
                    self.spot(lot_id)
                ),

            "best_bid":
                str(
                    max(
                        (
                            x.price_gbp_tree
                            for x in bids
                        ),
                        default=D("0")
                    )
                ),

            "best_ask":
                str(
                    min(
                        (
                            x.price_gbp_tree
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
        RhinoTreeExchange()
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    exchange.set_benchmark(

        TreeSpecies.ENGLISH_OAK,

        price_gbp_tree=1.20,

        symbol="RTX-OAK",

        source="RHINO_FORESTRY_DATA"
    )

    # --------------------------------------------------------
    # PHYSICAL LOT
    # --------------------------------------------------------

    lot = TreeLot(

        lot_id="RTX-OAK-001",

        species=TreeSpecies.ENGLISH_OAK,

        grade=Grade.PREMIUM,

        stock_type=StockType.CONTAINER,

        provenance=Provenance.UK_NATIVE,

        nursery="RHINO NURSERIES",

        nursery_reference="RN-OAK-2026-001",

        quantity=10000,

        age_years=3,

        height_cm=110,

        stem_diameter_mm=18,

        root_quality=9,

        health_score=9,

        form_score=8,

        disease_score=2,

        certification="CERT-UK-FORESTRY-001",

        harvest_or_lifting_date="2026-08-15",

        delivery_region="YORKSHIRE",

        delivery_window="2026-11-01/2026-11-30",

        haulage_gbp_per_tree=0.12
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    spot = exchange.spot(
        "RTX-OAK-001",
        delivery_month=11
    )

    print()
    print(
        "RHINO TREE EXCHANGE"
    )
    print(
        "==================="
    )
    print(
        "Indicative spot:",
        spot,
        "GBP/tree"
    )

    # --------------------------------------------------------
    # BUY ORDER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-FORESTRY-BUYER",

        lot_id="RTX-OAK-001",

        side=Side.BUY,

        quantity=1000,

        price_gbp_tree=2.00
    )

    # --------------------------------------------------------
    # SELL ORDER
    # --------------------------------------------------------

    trades = exchange.submit_order(

        trader_id="RHINO-NURSERY",

        lot_id="RTX-OAK-001",

        side=Side.SELL,

        quantity=1000,

        price_gbp_tree=1.95
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    snapshot = exchange.snapshot(
        "RTX-OAK-001"
    )

    print()
    print(
        "MARKET SNAPSHOT"
    )
    print(
        "==============="
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
        "============="
    )

    for trade in trades:

        print(

            trade.buyer,

            "bought",

            trade.quantity,

            "trees @",

            trade.price_gbp_tree,

            "GBP/tree",

            "| NOTIONAL:",

            trade.notional_gbp,

            "GBP"
        )
