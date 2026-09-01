"""
=============================================================
RHINO POTATO EXCHANGE
RPX 1.0
=============================================================

Physical potato spot-market engine.

Products:

    FRESH_POTATO
    CHIPPING_POTATO
    CRISPING_POTATO
    STARCH_POTATO
    SEED_POTATO
    ORGANIC_POTATO

Pricing:

    benchmark
      + variety basis
      + quality basis
      + grade/size basis
      + storage basis
      + regional basis
      + logistics
      + supply/demand
      =
    RHINO POTATO SPOT PRICE

All example prices are illustrative.

A production system should use validated market
assessments, laboratory data, inspection records,
contract specifications and authorised market-data
feeds.
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


def weight(value):
    return D(value).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP
    )


def now():
    return datetime.now(timezone.utc)


# ============================================================
# POTATO PRODUCTS
# ============================================================

class PotatoProduct(Enum):

    FRESH_POTATO = "FRESH_POTATO"

    CHIPPING_POTATO = "CHIPPING_POTATO"

    CRISPING_POTATO = "CRISPING_POTATO"

    STARCH_POTATO = "STARCH_POTATO"

    SEED_POTATO = "SEED_POTATO"

    ORGANIC_POTATO = "ORGANIC_POTATO"


class PotatoGrade(Enum):

    PREMIUM = "PREMIUM"

    CLASS_1 = "CLASS_1"

    CLASS_2 = "CLASS_2"

    PROCESSING = "PROCESSING"

    FEED = "FEED"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# DELIVERY POINT
# ============================================================

class DeliveryPoint(Enum):

    YORKSHIRE = "YORKSHIRE"

    LINCOLNSHIRE = "LINCOLNSHIRE"

    NORFOLK = "NORFOLK"

    CAMBRIDGESHIRE = "CAMBRIDGESHIRE"

    EAST_ANGILIA = "EAST_ANGILIA"

    SCOTLAND = "SCOTLAND"

    EAST_MIDLANDS = "EAST_MIDLANDS"

    WEST_MIDLANDS = "WEST_MIDLANDS"

    SOUTH_WEST = "SOUTH_WEST"

    NORTH_WEST = "NORTH_WEST"

    ROTTERDAM = "ROTTERDAM"


# ============================================================
# POTATO BENCHMARK
# ============================================================

@dataclass
class PotatoBenchmark:

    name: str

    product: PotatoProduct

    price_gbp_tonne: Decimal

    source: str

    timestamp: datetime = field(
        default_factory=now
    )

    def price(self):

        return money(
            self.price_gbp_tonne
        )


# ============================================================
# PHYSICAL POTATO LOT
# ============================================================

@dataclass
class PotatoLot:

    lot_id: str

    product: PotatoProduct

    variety: str

    grade: PotatoGrade

    origin: DeliveryPoint

    producer: str

    quantity_tonnes: Decimal

    average_size_mm: Decimal

    minimum_size_mm: Decimal
    maximum_size_mm: Decimal

    dry_matter_percent: Decimal

    skin_finish_score: Decimal

    bruising_percent: Decimal

    greening_percent: Decimal

    rot_percent: Decimal

    defect_percent: Decimal

    sugar_index: Decimal

    storage_type: str

    storage_months: Decimal

    harvest_date: str

    delivery_window: str

    destination: str

    haulage_gbp_tonne: Decimal = D("0")

    storage_gbp_tonne: Decimal = D("0")

    insurance_gbp_tonne: Decimal = D("0")

    organic_certified: bool = False

    available_tonnes: Decimal = field(
        init=False
    )

    def __post_init__(self):

        self.quantity_tonnes = weight(
            self.quantity_tonnes
        )

        self.available_tonnes = (
            self.quantity_tonnes
        )


# ============================================================
# REGIONAL BASIS ENGINE
# ============================================================

class PotatoLocationEngine:

    """
    Illustrative location differentials.

    Production implementation should derive these
    from actual freight, regional supply and physical
    market assessments.
    """

    BASIS = {

        DeliveryPoint.YORKSHIRE:
            D("0"),

        DeliveryPoint.LINCOLNSHIRE:
            D("4"),

        DeliveryPoint.NORFOLK:
            D("6"),

        DeliveryPoint.CAMBRIDGESHIRE:
            D("5"),

        DeliveryPoint.EAST_ANGILIA:
            D("5"),

        DeliveryPoint.SCOTLAND:
            D("12"),

        DeliveryPoint.EAST_MIDLANDS:
            D("3"),

        DeliveryPoint.WEST_MIDLANDS:
            D("8"),

        DeliveryPoint.SOUTH_WEST:
            D("10"),

        DeliveryPoint.NORTH_WEST:
            D("7"),

        DeliveryPoint.ROTTERDAM:
            D("15"),
    }

    def calculate(self, location):

        return self.BASIS.get(
            location,
            D("0")
        )


# ============================================================
# VARIETY ENGINE
# ============================================================

class PotatoVarietyEngine:

    """
    Variety basis.

    Values are illustrative.
    """

    BASIS = {

        "MARIS PIPER": D("0"),

        "AGRIA": D("12"),

        "MARKIES": D("10"),

        "FONTANE": D("8"),

        "INNOVATOR": D("15"),

        "RUSSET BURBANK": D("20"),

        "KING EDWARD": D("18"),

        "JAZZY": D("14"),

    }

    def calculate(self, variety):

        return self.BASIS.get(
            variety.upper(),
            D("0")
        )


# ============================================================
# QUALITY ENGINE
# ============================================================

class PotatoQualityEngine:

    def calculate(self, lot: PotatoLot):

        adjustment = D("0")

        # ----------------------------------------------------
        # DRY MATTER
        # ----------------------------------------------------

        if lot.dry_matter_percent >= D("23"):

            adjustment += D("18")

        elif lot.dry_matter_percent >= D("21"):

            adjustment += D("10")

        elif lot.dry_matter_percent >= D("19"):

            adjustment += D("3")

        else:

            adjustment -= D("12")

        # ----------------------------------------------------
        # SKIN FINISH
        # ----------------------------------------------------

        if lot.skin_finish_score >= D("9"):

            adjustment += D("10")

        elif lot.skin_finish_score >= D("7"):

            adjustment += D("4")

        elif lot.skin_finish_score < D("5"):

            adjustment -= D("10")

        # ----------------------------------------------------
        # BRUISING
        # ----------------------------------------------------

        if lot.bruising_percent <= D("1"):

            adjustment += D("5")

        elif lot.bruising_percent <= D("3"):

            adjustment += D("0")

        elif lot.bruising_percent <= D("5"):

            adjustment -= D("8")

        else:

            adjustment -= D("20")

        # ----------------------------------------------------
        # GREENING
        # ----------------------------------------------------

        if lot.greening_percent <= D("1"):

            adjustment += D("2")

        elif lot.greening_percent <= D("3"):

            adjustment -= D("3")

        else:

            adjustment -= D("15")

        # ----------------------------------------------------
        # ROT
        # ----------------------------------------------------

        if lot.rot_percent > D("1"):

            adjustment -= D("30")

        elif lot.rot_percent > D("0.5"):

            adjustment -= D("12")

        # ----------------------------------------------------
        # DEFECTS
        # ----------------------------------------------------

        if lot.defect_percent > D("5"):

            adjustment -= D("15")

        elif lot.defect_percent > D("2"):

            adjustment -= D("5")

        # ----------------------------------------------------
        # PROCESSING SUGAR INDEX
        # ----------------------------------------------------

        if lot.product in (
            PotatoProduct.CHIPPING_POTATO,
            PotatoProduct.CRISPING_POTATO
        ):

            if lot.sugar_index <= D("1"):

                adjustment += D("12")

            elif lot.sugar_index <= D("2"):

                adjustment += D("5")

            else:

                adjustment -= D("15")

        return money(
            adjustment
        )


# ============================================================
# SIZE ENGINE
# ============================================================

class PotatoSizeEngine:

    def calculate(self, lot: PotatoLot):

        adjustment = D("0")

        if lot.grade == PotatoGrade.PREMIUM:

            adjustment += D("8")

        if (
            lot.minimum_size_mm >= D("45")
            and
            lot.maximum_size_mm <= D("80")
        ):

            adjustment += D("5")

        if lot.average_size_mm < D("40"):

            adjustment -= D("8")

        if lot.average_size_mm > D("90"):

            adjustment -= D("6")

        return money(
            adjustment
        )


# ============================================================
# STORAGE ENGINE
# ============================================================

class PotatoStorageEngine:

    def calculate(self, lot: PotatoLot):

        adjustment = D("0")

        storage = lot.storage_type.upper()

        if storage == "CONTROLLED":

            adjustment += D("8")

        elif storage == "REFRIGERATED":

            adjustment += D("10")

        elif storage == "AMBIENT":

            adjustment += D("0")

        elif storage == "POOR":

            adjustment -= D("12")

        # Longer storage introduces a deterioration risk.

        if lot.storage_months > D("6"):

            adjustment -= D("8")

        elif lot.storage_months > D("4"):

            adjustment -= D("3")

        return money(
            adjustment
        )


# ============================================================
# SUPPLY / DEMAND ENGINE
# ============================================================

class PotatoSupplyEngine:

    def calculate(
        self,
        crop_supply_index,
        processor_demand_index,
        inventory_index
    ):

        adjustment = D("0")

        # Tight crop

        if crop_supply_index < D("0.90"):

            adjustment += D("20")

        elif crop_supply_index < D("0.97"):

            adjustment += D("8")

        elif crop_supply_index > D("1.10"):

            adjustment -= D("18")

        elif crop_supply_index > D("1.03"):

            adjustment -= D("7")

        # Processor demand

        if processor_demand_index > D("1.10"):

            adjustment += D("15")

        elif processor_demand_index > D("1.03"):

            adjustment += D("7")

        elif processor_demand_index < D("0.90"):

            adjustment -= D("12")

        # Inventory

        if inventory_index < D("0.90"):

            adjustment += D("10")

        elif inventory_index > D("1.10"):

            adjustment -= D("10")

        return money(
            adjustment
        )


# ============================================================
# SPOT PRICING ENGINE
# ============================================================

class PotatoSpotEngine:

    def __init__(self):

        self.location_engine = (
            PotatoLocationEngine()
        )

        self.variety_engine = (
            PotatoVarietyEngine()
        )

        self.quality_engine = (
            PotatoQualityEngine()
        )

        self.size_engine = (
            PotatoSizeEngine()
        )

        self.storage_engine = (
            PotatoStorageEngine()
        )

        self.supply_engine = (
            PotatoSupplyEngine()
        )

    def calculate(
        self,
        benchmark,
        lot,
        crop_supply_index=1.0,
        processor_demand_index=1.0,
        inventory_index=1.0
    ):

        benchmark_price = benchmark.price()

        variety_basis = (
            self.variety_engine.calculate(
                lot.variety
            )
        )

        location_basis = (
            self.location_engine.calculate(
                lot.origin
            )
        )

        quality_basis = (
            self.quality_engine.calculate(
                lot
            )
        )

        size_basis = (
            self.size_engine.calculate(
                lot
            )
        )

        storage_basis = (
            self.storage_engine.calculate(
                lot
            )
        )

        supply_basis = (
            self.supply_engine.calculate(

                D(crop_supply_index),

                D(processor_demand_index),

                D(inventory_index)
            )
        )

        logistics = (

            lot.haulage_gbp_tonne

            + lot.storage_gbp_tonne

            + lot.insurance_gbp_tonne
        )

        return money(

            benchmark_price

            + variety_basis

            + location_basis

            + quality_basis

            + size_basis

            + storage_basis

            + supply_basis

            - logistics
        )


# ============================================================
# ORDER
# ============================================================

@dataclass
class PotatoOrder:

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    quantity_tonnes: Decimal

    price_gbp_tonne: Decimal

    remaining_tonnes: Decimal = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.quantity_tonnes = weight(
            self.quantity_tonnes
        )

        self.remaining_tonnes = (
            self.quantity_tonnes
        )


# ============================================================
# TRADE
# ============================================================

@dataclass
class PotatoTrade:

    trade_id: str

    lot_id: str

    buyer: str

    seller: str

    quantity_tonnes: Decimal

    price_gbp_tonne: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional_gbp(self):

        return money(
            self.quantity_tonnes
            * self.price_gbp_tonne
        )


# ============================================================
# RHINO POTATO EXCHANGE
# ============================================================

class RhinoPotatoExchange:

    def __init__(self):

        self.benchmarks: Dict[
            PotatoProduct,
            PotatoBenchmark
        ] = {}

        self.lots: Dict[
            str,
            PotatoLot
        ] = {}

        self.bids: List[
            PotatoOrder
        ] = []

        self.asks: List[
            PotatoOrder
        ] = []

        self.trades: List[
            PotatoTrade
        ] = []

        self.pricer = (
            PotatoSpotEngine()
        )

    # ========================================================
    # BENCHMARK
    # ========================================================

    def set_benchmark(
        self,
        product,
        price_gbp_tonne,
        source="RHINO_MARKET_DATA"
    ):

        self.benchmarks[
            product
        ] = PotatoBenchmark(

            name="RHINO_POTATO_BENCHMARK",

            product=product,

            price_gbp_tonne=D(
                price_gbp_tonne
            ),

            source=source
        )

    # ========================================================
    # REGISTER LOT
    # ========================================================

    def register_lot(self, lot):

        if lot.organic_certified:

            lot.product = (
                PotatoProduct.ORGANIC_POTATO
            )

        self.lots[
            lot.lot_id
        ] = lot

    # ========================================================
    # SPOT PRICE
    # ========================================================

    def spot(self, lot_id):

        lot = self.lots[
            lot_id
        ]

        benchmark = self.benchmarks.get(
            lot.product
        )

        if benchmark is None:

            raise RuntimeError(
                "Potato benchmark unavailable"
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
        quantity_tonnes,
        price_gbp_tonne
    ):

        lot = self.lots[
            lot_id
        ]

        quantity = weight(
            quantity_tonnes
        )

        if side == Side.SELL:

            if quantity > lot.available_tonnes:

                raise ValueError(
                    "Insufficient physical potato inventory"
                )

        order = PotatoOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            quantity_tonnes=quantity,

            price_gbp_tonne=money(
                price_gbp_tonne
            )
        )

        if side == Side.BUY:

            self.bids.append(order)

            self.bids.sort(

                key=lambda x: (
                    -x.price_gbp_tonne,
                    x.timestamp
                )
            )

        else:

            self.asks.append(order)

            self.asks.sort(

                key=lambda x: (
                    x.price_gbp_tonne,
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
                bid.price_gbp_tonne
                <
                ask.price_gbp_tonne
            ):

                break

            quantity = min(

                bid.remaining_tonnes,

                ask.remaining_tonnes
            )

            trade = PotatoTrade(

                trade_id=str(
                    uuid4()
                ),

                lot_id=bid.lot_id,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity_tonnes=quantity,

                price_gbp_tonne=(
                    ask.price_gbp_tonne
                )
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining_tonnes -= (
                quantity
            )

            ask.remaining_tonnes -= (
                quantity
            )

            lot = self.lots[
                bid.lot_id
            ]

            lot.available_tonnes -= (
                quantity
            )

            if bid.remaining_tonnes <= 0:

                self.bids.pop(0)

            if ask.remaining_tonnes <= 0:

                self.asks.pop(0)

        return executions

    # ========================================================
    # VWAP
    # ========================================================

    def vwap(self, lot_id):

        trades = [

            trade

            for trade in self.trades

            if trade.lot_id == lot_id
        ]

        if not trades:

            return None

        total_value = sum(

            trade.quantity_tonnes
            * trade.price_gbp_tonne

            for trade in trades
        )

        total_quantity = sum(

            trade.quantity_tonnes

            for trade in trades
        )

        if total_quantity == 0:

            return None

        return money(
            total_value
            / total_quantity
        )

    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    def snapshot(self, lot_id):

        lot = self.lots[
            lot_id
        ]

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
                "RHINO POTATO EXCHANGE",

            "instrument":
                f"RPX-{lot.product.value}",

            "variety":
                lot.variety,

            "grade":
                lot.grade.value,

            "origin":
                lot.origin.value,

            "available_tonnes":
                str(
                    lot.available_tonnes
                ),

            "average_size_mm":
                str(
                    lot.average_size_mm
                ),

            "dry_matter":
                str(
                    lot.dry_matter_percent
                ),

            "bruising":
                str(
                    lot.bruising_percent
                ),

            "greening":
                str(
                    lot.greening_percent
                ),

            "rot":
                str(
                    lot.rot_percent
                ),

            "storage":
                lot.storage_type,

            "spot_gbp_tonne":
                str(
                    self.spot(lot_id)
                ),

            "best_bid":
                str(
                    max(
                        (
                            x.price_gbp_tonne
                            for x in bids
                        ),
                        default=D("0")
                    )
                ),

            "best_ask":
                str(
                    min(
                        (
                            x.price_gbp_tonne
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
        RhinoPotatoExchange()
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    exchange.set_benchmark(

        PotatoProduct.FRESH_POTATO,

        280,

        "RHINO_MARKET_DATA"
    )

    # --------------------------------------------------------
    # PHYSICAL LOT
    # --------------------------------------------------------

    lot = PotatoLot(

        lot_id="RPX-YORK-001",

        product=PotatoProduct.FRESH_POTATO,

        variety="Maris Piper",

        grade=PotatoGrade.PREMIUM,

        origin=DeliveryPoint.YORKSHIRE,

        producer="RHINO-FARM-001",

        quantity_tonnes=500,

        average_size_mm=62,

        minimum_size_mm=45,

        maximum_size_mm=80,

        dry_matter_percent=22.5,

        skin_finish_score=8.5,

        bruising_percent=1.0,

        greening_percent=0.5,

        rot_percent=0.1,

        defect_percent=1.5,

        sugar_index=0.8,

        storage_type="CONTROLLED",

        storage_months=1,

        harvest_date="2026-08-25",

        delivery_window="2026-09-01/2026-09-07",

        destination="RHINO-POTATO-PROCESSOR",

        haulage_gbp_tonne=12,

        storage_gbp_tonne=4,

        insurance_gbp_tonne=1,

        organic_certified=False
    )

    exchange.register_lot(
        lot
    )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    print()

    print(
        "RHINO POTATO EXCHANGE"
    )

    print(
        "====================="
    )

    print(
        "Indicative spot:",
        exchange.spot(
            "RPX-YORK-001"
        ),
        "GBP/t"
    )

    # --------------------------------------------------------
    # BUY ORDER
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-PROCESSOR-001",

        lot_id="RPX-YORK-001",

        side=Side.BUY,

        quantity_tonnes=100,

        price_gbp_tonne=350
    )

    # --------------------------------------------------------
    # SELL ORDER
    # --------------------------------------------------------

    trades = exchange.submit_order(

        trader_id="RHINO-FARM-001",

        lot_id="RPX-YORK-001",

        side=Side.SELL,

        quantity_tonnes=100,

        price_gbp_tonne=345
    )

    # --------------------------------------------------------
    # MARKET SNAPSHOT
    # --------------------------------------------------------

    print()

    print(
        "MARKET SNAPSHOT"
    )

    print(
        "================"
    )

    snapshot = exchange.snapshot(
        "RPX-YORK-001"
    )

    for key, value in snapshot.items():

        print(
            f"{key:26} {value}"
        )

    # --------------------------------------------------------
    # TRADES
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

            trade.quantity_tonnes,

            "tonnes @",

            trade.price_gbp_tonne,

            "GBP/t",

            "| Notional:",

            trade.notional_gbp,

            "GBP"
        )
