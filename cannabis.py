"""
=============================================================
RHINO CANNABIS EXCHANGE
RCX 1.0
=============================================================

Physical spot-market infrastructure for a regulated
Colorado cannabis business.

Markets:

    HEMP_FLOWER
    HEMP_BIOMASS
    THC_FLOWER
    THC_BIOMASS
    THC_TRIM
    CONCENTRATE

The engine is deliberately designed around:

    - batch-level inventory
    - regulatory status
    - laboratory testing
    - cannabinoid composition
    - quality
    - origin
    - storage
    - logistics
    - licensed counterparties
    - order books
    - settlement

Illustrative pricing only.

Production deployment requires integration with
the applicable Colorado licensing, traceability,
testing, tax and reporting systems.
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


def qty(value):
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def now():
    return datetime.now(timezone.utc)


# ============================================================
# PRODUCT TYPES
# ============================================================

class CannabisProduct(Enum):

    HEMP_FLOWER = "HEMP_FLOWER"

    HEMP_BIOMASS = "HEMP_BIOMASS"

    THC_FLOWER = "THC_FLOWER"

    THC_BIOMASS = "THC_BIOMASS"

    THC_TRIM = "THC_TRIM"

    CONCENTRATE = "CONCENTRATE"


class CannabisMarket(Enum):

    NON_INToxicating = "HEMP"

    REGULATED_THC = "THC"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


class Grade(Enum):

    PREMIUM = "PREMIUM"

    A = "A"

    B = "B"

    PROCESSING = "PROCESSING"

    BIOMASS = "BIOMASS"


# ============================================================
# REGULATORY STATUS
# ============================================================

class RegulatoryStatus(Enum):

    VERIFIED = "VERIFIED"

    PENDING_TEST = "PENDING_TEST"

    QUARANTINED = "QUARANTINED"

    REJECTED = "REJECTED"

    RELEASED = "RELEASED"


# ============================================================
# LABORATORY CERTIFICATE
# ============================================================

@dataclass
class LabCertificate:

    certificate_id: str

    laboratory: str

    tested_at: datetime

    thc_percent: Decimal

    cbd_percent: Decimal

    cbg_percent: Decimal

    moisture_percent: Decimal

    pesticides_pass: bool

    heavy_metals_pass: bool

    microbial_pass: bool

    residual_solvents_pass: bool

    certificate_valid: bool

    def passes(self):

        return (

            self.certificate_valid

            and self.pesticides_pass

            and self.heavy_metals_pass

            and self.microbial_pass

            and self.residual_solvents_pass
        )


# ============================================================
# PHYSICAL BATCH
# ============================================================

@dataclass
class CannabisBatch:

    batch_id: str

    product: CannabisProduct

    market: CannabisMarket

    strain_or_variety: str

    grade: Grade

    producer: str

    producer_license: str

    origin: str

    destination: str

    quantity_kg: Decimal

    harvest_date: str

    storage_type: str

    moisture_percent: Decimal

    terpene_score: Decimal

    visual_quality_score: Decimal

    lab: LabCertificate

    regulatory_status: RegulatoryStatus

    traceability_id: str

    available_kg: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity_kg = qty(
            self.quantity_kg
        )

        self.available_kg = (
            self.quantity_kg
        )


# ============================================================
# MARKET BENCHMARK
# ============================================================

@dataclass
class CannabisBenchmark:

    symbol: str

    product: CannabisProduct

    price_usd_kg: Decimal

    source: str

    timestamp: datetime = field(
        default_factory=now
    )


# ============================================================
# QUALITY ENGINE
# ============================================================

class CannabisQualityEngine:

    def calculate(
        self,
        batch: CannabisBatch
    ):

        adjustment = D("0")

        # ----------------------------------------------------
        # GRADE
        # ----------------------------------------------------

        grade_basis = {

            Grade.PREMIUM: D("250"),

            Grade.A: D("125"),

            Grade.B: D("25"),

            Grade.PROCESSING: D("-50"),

            Grade.BIOMASS: D("-100")
        }

        adjustment += grade_basis[
            batch.grade
        ]

        # ----------------------------------------------------
        # TERPENES
        # ----------------------------------------------------

        if batch.terpene_score >= D("9"):

            adjustment += D("175")

        elif batch.terpene_score >= D("7"):

            adjustment += D("90")

        elif batch.terpene_score < D("4"):

            adjustment -= D("100")

        # ----------------------------------------------------
        # VISUAL QUALITY
        # ----------------------------------------------------

        if batch.visual_quality_score >= D("9"):

            adjustment += D("100")

        elif batch.visual_quality_score >= D("7"):

            adjustment += D("50")

        elif batch.visual_quality_score < D("5"):

            adjustment -= D("100")

        # ----------------------------------------------------
        # MOISTURE
        # ----------------------------------------------------

        if batch.moisture_percent > D("14"):

            adjustment -= D("150")

        elif batch.moisture_percent < D("8"):

            adjustment -= D("75")

        return money(
            adjustment
        )


# ============================================================
# CANNABINOID VALUE ENGINE
# ============================================================

class CannabinoidEngine:

    def calculate(
        self,
        batch: CannabisBatch
    ):

        # This represents a market-value component,
        # not a recommendation for consumption.

        thc_value = (
            batch.lab.thc_percent
            * D("8")
        )

        cbd_value = (
            batch.lab.cbd_percent
            * D("3")
        )

        cbg_value = (
            batch.lab.cbg_percent
            * D("2")
        )

        return money(

            thc_value

            + cbd_value

            + cbg_value
        )


# ============================================================
# REGULATORY ENGINE
# ============================================================

class RegulatoryEngine:

    def validate(
        self,
        batch: CannabisBatch
    ):

        if not batch.producer_license:

            raise ValueError(
                "Producer licence missing"
            )

        if not batch.traceability_id:

            raise ValueError(
                "Traceability identifier missing"
            )

        if not batch.lab.passes():

            raise ValueError(
                "Laboratory certificate failed"
            )

        if batch.regulatory_status not in (

            RegulatoryStatus.VERIFIED,

            RegulatoryStatus.RELEASED
        ):

            raise ValueError(
                "Batch is not eligible for trading"
            )

        return True


# ============================================================
# SPOT PRICING ENGINE
# ============================================================

class CannabisSpotEngine:

    def __init__(self):

        self.quality = (
            CannabisQualityEngine()
        )

        self.cannabinoids = (
            CannabinoidEngine()
        )

        self.regulatory = (
            RegulatoryEngine()
        )

    def calculate(
        self,
        benchmark: CannabisBenchmark,
        batch: CannabisBatch,
        supply_index=1.0,
        demand_index=1.0
    ):

        self.regulatory.validate(
            batch
        )

        base = benchmark.price_usd_kg

        quality_basis = (
            self.quality.calculate(
                batch
            )
        )

        cannabinoid_basis = (
            self.cannabinoids.calculate(
                batch
            )
        )

        market_basis = D("0")

        if D(supply_index) < D("0.90"):

            market_basis += D("150")

        elif D(supply_index) > D("1.10"):

            market_basis -= D("150")

        if D(demand_index) > D("1.10"):

            market_basis += D("175")

        elif D(demand_index) < D("0.90"):

            market_basis -= D("125")

        return money(

            base

            + quality_basis

            + cannabinoid_basis

            + market_basis
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class CannabisOrder:

    order_id: str

    trader_id: str

    batch_id: str

    side: Side

    quantity_kg: Decimal

    price_usd_kg: Decimal

    remaining_kg: Decimal = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.quantity_kg = qty(
            self.quantity_kg
        )

        self.remaining_kg = (
            self.quantity_kg
        )


# ============================================================
# TRADE
# ============================================================

@dataclass
class CannabisTrade:

    trade_id: str

    batch_id: str

    buyer: str

    seller: str

    quantity_kg: Decimal

    price_usd_kg: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional_usd(self):

        return money(
            self.quantity_kg
            * self.price_usd_kg
        )


# ============================================================
# RHINO CANNABIS EXCHANGE
# ============================================================

class RhinoCannabisExchange:

    def __init__(self):

        self.benchmarks: Dict[
            CannabisProduct,
            CannabisBenchmark
        ] = {}

        self.batches: Dict[
            str,
            CannabisBatch
        ] = {}

        self.bids: List[
            CannabisOrder
        ] = []

        self.asks: List[
            CannabisOrder
        ] = []

        self.trades: List[
            CannabisTrade
        ] = []

        self.pricer = (
            CannabisSpotEngine()
        )

    # ========================================================
    # BENCHMARK
    # ========================================================

    def set_benchmark(
        self,
        product,
        price_usd_kg,
        symbol,
        source="RHINO_MARKET_DATA"
    ):

        self.benchmarks[
            product
        ] = CannabisBenchmark(

            symbol=symbol,

            product=product,

            price_usd_kg=D(
                price_usd_kg
            ),

            source=source
        )

    # ========================================================
    # REGISTER BATCH
    # ========================================================

    def register_batch(
        self,
        batch
    ):

        # Verify before accepting inventory.

        RegulatoryEngine().validate(
            batch
        )

        self.batches[
            batch.batch_id
        ] = batch

    # ========================================================
    # SPOT
    # ========================================================

    def spot(
        self,
        batch_id
    ):

        batch = self.batches[
            batch_id
        ]

        benchmark = self.benchmarks.get(
            batch.product
        )

        if benchmark is None:

            raise RuntimeError(
                "Benchmark unavailable"
            )

        return self.pricer.calculate(

            benchmark,

            batch
        )

    # ========================================================
    # ORDER ENTRY
    # ========================================================

    def submit_order(
        self,
        trader_id,
        batch_id,
        side,
        quantity_kg,
        price_usd_kg
    ):

        batch = self.batches[
            batch_id
        ]

        RegulatoryEngine().validate(
            batch
        )

        quantity = qty(
            quantity_kg
        )

        if side == Side.SELL:

            if quantity > batch.available_kg:

                raise ValueError(
                    "Insufficient inventory"
                )

        order = CannabisOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            batch_id=batch_id,

            side=side,

            quantity_kg=quantity,

            price_usd_kg=money(
                price_usd_kg
            )
        )

        if side == Side.BUY:

            self.bids.append(
                order
            )

            self.bids.sort(

                key=lambda x: (

                    -x.price_usd_kg,

                    x.timestamp
                )
            )

        else:

            self.asks.append(
                order
            )

            self.asks.sort(

                key=lambda x: (

                    x.price_usd_kg,

                    x.timestamp
                )
            )

        return self.match()

    # ========================================================
    # MATCHING
    # ========================================================

    def match(self):

        executions = []

        while self.bids and self.asks:

            bid = self.bids[0]

            ask = self.asks[0]

            if bid.batch_id != ask.batch_id:

                break

            if (
                bid.price_usd_kg
                <
                ask.price_usd_kg
            ):

                break

            quantity = min(

                bid.remaining_kg,

                ask.remaining_kg
            )

            trade = CannabisTrade(

                trade_id=str(
                    uuid4()
                ),

                batch_id=bid.batch_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity_kg=quantity,

                price_usd_kg=(
                    ask.price_usd_kg
                )
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining_kg -= (
                quantity
            )

            ask.remaining_kg -= (
                quantity
            )

            batch = self.batches[
                bid.batch_id
            ]

            batch.available_kg -= (
                quantity
            )

            if bid.remaining_kg <= 0:

                self.bids.pop(0)

            if ask.remaining_kg <= 0:

                self.asks.pop(0)

        return executions

    # ========================================================
    # VWAP
    # ========================================================

    def vwap(
        self,
        batch_id
    ):

        trades = [

            trade

            for trade in self.trades

            if trade.batch_id == batch_id
        ]

        if not trades:

            return None

        value = sum(

            t.quantity_kg
            * t.price_usd_kg

            for t in trades
        )

        quantity = sum(

            t.quantity_kg

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
        batch_id
    ):

        batch = self.batches[
            batch_id
        ]

        bids = [

            x

            for x in self.bids

            if x.batch_id == batch_id
        ]

        asks = [

            x

            for x in self.asks

            if x.batch_id == batch_id
        ]

        return {

            "market":
                "RHINO CANNABIS EXCHANGE",

            "product":
                batch.product.value,

            "market_type":
                batch.market.value,

            "strain":
                batch.strain_or_variety,

            "grade":
                batch.grade.value,

            "origin":
                batch.origin,

            "available_kg":
                str(
                    batch.available_kg
                ),

            "THC_percent":
                str(
                    batch.lab.thc_percent
                ),

            "CBD_percent":
                str(
                    batch.lab.cbd_percent
                ),

            "CBG_percent":
                str(
                    batch.lab.cbg_percent
                ),

            "terpene_score":
                str(
                    batch.terpene_score
                ),

            "lab":
                batch.lab.laboratory,

            "regulatory_status":
                batch.regulatory_status.value,

            "spot_usd_kg":
                str(
                    self.spot(batch_id)
                ),

            "best_bid":
                str(
                    max(
                        (
                            x.price_usd_kg
                            for x in bids
                        ),
                        default=D("0")
                    )
                ),

            "best_ask":
                str(
                    min(
                        (
                            x.price_usd_kg
                            for x in asks
                        ),
                        default=D("0")
                    )
                ),

            "vwap":
                str(
                    self.vwap(batch_id)
                    or D("0")
                ),

            "traceability_id":
                batch.traceability_id,

            "timestamp":
                now().isoformat()
        }


# ============================================================
# EXAMPLE
# ============================================================

if __name__ == "__main__":

    exchange = (
        RhinoCannabisExchange()
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    exchange.set_benchmark(

        CannabisProduct.THC_FLOWER,

        price_usd_kg=5000,

        symbol="RCX-THCF",

        source="RHINO_MARKET_DATA"
    )

    # --------------------------------------------------------
    # LAB CERTIFICATE
    # --------------------------------------------------------

    lab = LabCertificate(

        certificate_id="LAB-2026-0001",

        laboratory="COLORADO-LAB-01",

        tested_at=now(),

        thc_percent=D("22.4"),

        cbd_percent=D("0.8"),

        cbg_percent=D("1.1"),

        moisture_percent=D("11.0"),

        pesticides_pass=True,

        heavy_metals_pass=True,

        microbial_pass=True,

        residual_solvents_pass=True,

        certificate_valid=True
    )

    # --------------------------------------------------------
    # PHYSICAL BATCH
    # --------------------------------------------------------

    batch = CannabisBatch(

        batch_id="RCX-CO-THC-0001",

        product=CannabisProduct.THC_FLOWER,

        market=CannabisMarket.REGULATED_THC,

        strain_or_variety="COLORADO-BATCH-A",

        grade=Grade.PREMIUM,

        producer="RHINO-COLORADO-CULTIVATION",

        producer_license="CO-LICENSE-EXAMPLE",

        origin="COLORADO",

        destination="LICENSED-PROCESSOR",

        quantity_kg=100,

        harvest_date="2026-08-25",

        storage_type="CONTROLLED",

        moisture_percent=D("11"),

        terpene_score=D("8.5"),

        visual_quality_score=D("9"),

        lab=lab,

        regulatory_status=RegulatoryStatus.RELEASED,

        traceability_id="TRACE-CO-2026-0001"
    )

    exchange.register_batch(
        batch
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    print(
        "RHINO CANNABIS SPOT:",
        exchange.spot(
            "RCX-CO-THC-0001"
        ),
        "USD/kg"
    )

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="LICENSED-BUYER-001",

        batch_id="RCX-CO-THC-0001",

        side=Side.BUY,

        quantity_kg=10,

        price_usd_kg=6500
    )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    trades = exchange.submit_order(

        trader_id="RHINO-CULTIVATION-001",

        batch_id="RCX-CO-THC-0001",

        side=Side.SELL,

        quantity_kg=10,

        price_usd_kg=6400
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    snapshot = exchange.snapshot(
        "RCX-CO-THC-0001"
    )

    print()

    print(
        "RHINO CANNABIS MARKET"
    )

    print(
        "====================="
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

            trade.quantity_kg,

            "kg @",

            trade.price_usd_kg,

            "USD/kg",

            "NOTIONAL:",

            trade.notional_usd
        )
