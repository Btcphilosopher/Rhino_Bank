"""
============================================================
RHINO RUBBER EXCHANGE
RRX 1.0
============================================================

Physical natural-rubber spot-pricing engine.

Supported grades:
    RSS3
    RSS4
    TSR20
    SMR20
    SMR10
    STR20
    SIR20
    LATEX

Pricing dimensions:
    grade
    origin
    quality
    moisture
    dirt
    ash
    PRI
    delivery basis
    freight
    FX
    supply
    demand
    benchmark

The benchmark layer can ingest published physical-market
observations and exchange/reference prices.

Illustrative values are used in the demo.
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


def now():
    return datetime.now(timezone.utc)


# ============================================================
# RUBBER GRADES
# ============================================================

class RubberGrade(Enum):

    RSS3 = "RSS3"
    RSS4 = "RSS4"

    TSR20 = "TSR20"

    SMR5 = "SMR5"
    SMR10 = "SMR10"
    SMR20 = "SMR20"

    STR20 = "STR20"

    SIR20 = "SIR20"

    LATEX = "LATEX"


# ============================================================
# DELIVERY BASIS
# ============================================================

class DeliveryBasis(Enum):

    FOB = "FOB"
    CIF = "CIF"
    CFR = "CFR"
    EX_WAREHOUSE = "EX_WAREHOUSE"


# ============================================================
# ORIGIN
# ============================================================

class Origin(Enum):

    THAILAND = "THAILAND"
    MALAYSIA = "MALAYSIA"
    INDONESIA = "INDONESIA"
    VIETNAM = "VIETNAM"
    INDIA = "INDIA"
    IVORY_COAST = "IVORY_COAST"
    SRI_LANKA = "SRI_LANKA"


# ============================================================
# BENCHMARK
# ============================================================

@dataclass
class RubberBenchmark:

    symbol: str

    grade: RubberGrade

    price_usd_kg: Decimal

    basis: DeliveryBasis

    origin: Origin

    source: str

    timestamp: datetime = field(
        default_factory=now
    )


# ============================================================
# PHYSICAL LOT
# ============================================================

@dataclass
class RubberLot:

    lot_id: str

    grade: RubberGrade

    origin: Origin

    quantity_tonnes: Decimal

    delivery_basis: DeliveryBasis

    delivery_port: str

    delivery_month: int

    moisture_pct: Decimal

    dirt_pct: Decimal

    ash_pct: Decimal

    volatile_matter_pct: Decimal

    nitrogen_pct: Decimal

    pri: Decimal

    quality_grade: str

    certification: str

    producer: str

    warehouse: str

    freight_usd_tonne: Decimal = D("0")

    insurance_usd_tonne: Decimal = D("0")

    available_tonnes: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.available_tonnes = (
            D(self.quantity_tonnes)
        )


# ============================================================
# QUALITY ENGINE
# ============================================================

class RubberQualityEngine:

    def calculate(self, lot):

        adjustment = D("0")

        # ----------------------------------------------------
        # MOISTURE
        # ----------------------------------------------------

        if lot.moisture_pct <= D("0.30"):
            adjustment += D("0.025")

        elif lot.moisture_pct <= D("0.50"):
            adjustment += D("0.010")

        elif lot.moisture_pct > D("0.80"):
            adjustment -= D("0.035")

        # ----------------------------------------------------
        # DIRT
        # ----------------------------------------------------

        if lot.dirt_pct <= D("0.05"):
            adjustment += D("0.025")

        elif lot.dirt_pct > D("0.20"):
            adjustment -= D("0.030")

        # ----------------------------------------------------
        # ASH
        # ----------------------------------------------------

        if lot.ash_pct <= D("0.50"):
            adjustment += D("0.015")

        elif lot.ash_pct > D("0.80"):
            adjustment -= D("0.020")

        # ----------------------------------------------------
        # PRI
        # ----------------------------------------------------

        if lot.pri >= D("80"):
            adjustment += D("0.040")

        elif lot.pri >= D("70"):
            adjustment += D("0.015")

        elif lot.pri < D("60"):
            adjustment -= D("0.040")

        return adjustment


# ============================================================
# GRADE BASIS
# ============================================================

class GradeEngine:

    BASIS = {

        RubberGrade.RSS3:
            D("0.18"),

        RubberGrade.RSS4:
            D("0.08"),

        RubberGrade.TSR20:
            D("0.00"),

        RubberGrade.SMR5:
            D("0.12"),

        RubberGrade.SMR10:
            D("0.06"),

        RubberGrade.SMR20:
            D("0.02"),

        RubberGrade.STR20:
            D("0.01"),

        RubberGrade.SIR20:
            D("-0.03"),

        RubberGrade.LATEX:
            D("0.15")
    }

    def calculate(self, grade):

        return self.BASIS.get(
            grade,
            D("0")
        )


# ============================================================
# ORIGIN BASIS
# ============================================================

class OriginEngine:

    BASIS = {

        Origin.THAILAND:
            D("0.02"),

        Origin.MALAYSIA:
            D("0.04"),

        Origin.INDONESIA:
            D("0.00"),

        Origin.VIETNAM:
            D("0.01"),

        Origin.INDIA:
            D("-0.02"),

        Origin.IVORY_COAST:
            D("-0.03"),

        Origin.SRI_LANKA:
            D("0.01")
    }

    def calculate(self, origin):

        return self.BASIS.get(
            origin,
            D("0")
        )


# ============================================================
# MARKET BALANCE
# ============================================================

class SupplyDemandEngine:

    def calculate(
        self,
        supply_index,
        demand_index
    ):

        supply = D(supply_index)
        demand = D(demand_index)

        adjustment = D("0")

        # Tight supply

        if supply < D("0.90"):

            adjustment += D("0.10")

        elif supply < D("0.97"):

            adjustment += D("0.04")

        # Excess supply

        elif supply > D("1.10"):

            adjustment -= D("0.10")

        elif supply > D("1.03"):

            adjustment -= D("0.04")

        # Strong demand

        if demand > D("1.10"):

            adjustment += D("0.10")

        elif demand > D("1.03"):

            adjustment += D("0.04")

        # Weak demand

        elif demand < D("0.90"):

            adjustment -= D("0.08")

        return adjustment


# ============================================================
# SPOT PRICER
# ============================================================

class RubberSpotPricer:

    def __init__(self):

        self.quality = (
            RubberQualityEngine()
        )

        self.grade = (
            GradeEngine()
        )

        self.origin = (
            OriginEngine()
        )

        self.supply_demand = (
            SupplyDemandEngine()
        )

    def calculate(
        self,
        benchmark,
        lot,
        supply_index=1.0,
        demand_index=1.0
    ):

        base = benchmark.price_usd_kg

        grade_basis = (
            self.grade.calculate(
                lot.grade
            )
        )

        origin_basis = (
            self.origin.calculate(
                lot.origin
            )
        )

        quality_basis = (
            self.quality.calculate(
                lot
            )
        )

        market_basis = (
            self.supply_demand.calculate(
                supply_index,
                demand_index
            )
        )

        logistics = (
            lot.freight_usd_tonne
            + lot.insurance_usd_tonne
        ) / D("1000")

        price = (

            base

            + grade_basis

            + origin_basis

            + quality_basis

            + market_basis

            + logistics
        )

        return money(price)


# ============================================================
# RRX EXCHANGE
# ============================================================

class RhinoRubberExchange:

    def __init__(self):

        self.benchmarks = {}

        self.lots = {}

        self.pricer = (
            RubberSpotPricer()
        )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    def set_benchmark(
        self,
        symbol,
        grade,
        price_usd_kg,
        basis,
        origin,
        source
    ):

        self.benchmarks[
            grade
        ] = RubberBenchmark(

            symbol=symbol,

            grade=grade,

            price_usd_kg=D(
                price_usd_kg
            ),

            basis=basis,

            origin=origin,

            source=source
        )

    # --------------------------------------------------------
    # REGISTER PHYSICAL LOT
    # --------------------------------------------------------

    def register_lot(
        self,
        lot
    ):

        self.lots[
            lot.lot_id
        ] = lot

    # --------------------------------------------------------
    # SPOT PRICE
    # --------------------------------------------------------

    def spot_price(
        self,
        lot_id,
        supply_index=1.0,
        demand_index=1.0
    ):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.grade
        )

        if benchmark is None:

            raise RuntimeError(
                f"No benchmark for {lot.grade.value}"
            )

        return self.pricer.calculate(

            benchmark,

            lot,

            supply_index,

            demand_index
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

        spot = self.spot_price(
            lot_id
        )

        return {

            "exchange":
                "RHINO RUBBER EXCHANGE",

            "instrument":
                f"RRX-{lot.grade.value}",

            "grade":
                lot.grade.value,

            "origin":
                lot.origin.value,

            "quantity_tonnes":
                str(
                    lot.available_tonnes
                ),

            "delivery_basis":
                lot.delivery_basis.value,

            "delivery_port":
                lot.delivery_port,

            "delivery_month":
                lot.delivery_month,

            "spot_usd_kg":
                str(spot),

            "spot_usd_tonne":
                str(
                    money(
                        spot * D("1000")
                    )
                ),

            "quality":
                lot.quality_grade,

            "pri":
                str(lot.pri),

            "moisture_pct":
                str(lot.moisture_pct),

            "dirt_pct":
                str(lot.dirt_pct),

            "producer":
                lot.producer,

            "timestamp":
                now().isoformat()
        }


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    rrx = RhinoRubberExchange()

    # --------------------------------------------------------
    # BENCHMARKS
    # --------------------------------------------------------

    rrx.set_benchmark(

        symbol="RRX-TSR20",

        grade=RubberGrade.TSR20,

        price_usd_kg=2.31,

        basis=DeliveryBasis.FOB,

        origin=Origin.MALAYSIA,

        source="PHYSICAL_MARKET_REFERENCE"
    )

    rrx.set_benchmark(

        symbol="RRX-RSS3",

        grade=RubberGrade.RSS3,

        price_usd_kg=2.73,

        basis=DeliveryBasis.FOB,

        origin=Origin.THAILAND,

        source="PHYSICAL_MARKET_REFERENCE"
    )

    rrx.set_benchmark(

        symbol="RRX-SMR20",

        grade=RubberGrade.SMR20,

        price_usd_kg=2.44,

        basis=DeliveryBasis.FOB,

        origin=Origin.MALAYSIA,

        source="PHYSICAL_MARKET_REFERENCE"
    )

    # --------------------------------------------------------
    # PHYSICAL TSR20 LOT
    # --------------------------------------------------------

    lot = RubberLot(

        lot_id="RRX-TSR20-001",

        grade=RubberGrade.TSR20,

        origin=Origin.MALAYSIA,

        quantity_tonnes=500,

        delivery_basis=DeliveryBasis.FOB,

        delivery_port="PORT KLANG",

        delivery_month=10,

        moisture_pct=0.40,

        dirt_pct=0.08,

        ash_pct=0.45,

        volatile_matter_pct=0.80,

        nitrogen_pct=0.40,

        pri=82,

        quality_grade="TSR20",

        certification="MALAYSIAN_STANDARD",

        producer="RHINO RUBBER SUPPLY",

        warehouse="PORT KLANG",

        freight_usd_tonne=0,

        insurance_usd_tonne=0
    )

    rrx.register_lot(
        lot
    )

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    spot = rrx.spot_price(
        "RRX-TSR20-001",

        supply_index=0.96,

        demand_index=1.05
    )

    print()
    print("=" * 60)
    print("RHINO RUBBER EXCHANGE")
    print("=" * 60)

    print(
        "TSR20 SPOT:",
        spot,
        "USD/kg"
    )

    print(
        "TSR20 SPOT:",
        money(
            spot * D("1000")
        ),
        "USD/tonne"
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    print()

    snapshot = rrx.snapshot(
        "RRX-TSR20-001"
    )

    for key, value in snapshot.items():

        print(
            f"{key:25} {value}"
        )
