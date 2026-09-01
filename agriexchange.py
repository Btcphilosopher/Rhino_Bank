"""
=============================================================
RHINO AGRICULTURAL SPOT EXCHANGE
RASE 1.0
=============================================================

Generic physical agricultural commodity exchange.

Supports:

    - commodity registration
    - physical lots
    - quality-adjusted pricing
    - origin basis
    - warehouse inventory
    - bids / offers
    - limit orders
    - market orders
    - price-time matching
    - trade execution
    - VWAP
    - market snapshots
    - physical settlement

Illustrative implementation.

Production deployment would require:
    - authenticated users
    - database persistence
    - audit logging
    - market surveillance
    - regulatory controls
    - validated commodity specifications
    - clearing and settlement infrastructure
"""


from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from heapq import heappush, heappop
from typing import Dict, List, Optional
from uuid import uuid4


# =============================================================
# NUMERIC UTILITIES
# =============================================================

PRICE_Q = Decimal("0.01")
QUANTITY_Q = Decimal("0.001")


def money(value):

    return Decimal(
        str(value)
    ).quantize(
        PRICE_Q,
        rounding=ROUND_HALF_UP
    )


def quantity(value):

    return Decimal(
        str(value)
    ).quantize(
        QUANTITY_Q,
        rounding=ROUND_HALF_UP
    )


def now():

    return datetime.now(
        timezone.utc
    )


# =============================================================
# ENUMS
# =============================================================

class CommoditySector(Enum):

    GRAIN = "GRAIN"
    OILSEED = "OILSEED"
    SOFT = "SOFT"
    FRUIT = "FRUIT"
    VEGETABLE = "VEGETABLE"
    ANIMAL_PRODUCT = "ANIMAL_PRODUCT"
    SPECIALITY = "SPECIALITY"


class Side(Enum):

    BUY = "BUY"
    SELL"


class OrderType(Enum):

    LIMIT = "LIMIT"
    MARKET"


class OrderStatus(Enum):

    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


# =============================================================
# COMMODITY DEFINITION
# =============================================================

@dataclass
class Commodity:

    symbol: str

    name: str

    sector: CommoditySector

    base_unit: str

    currency: str = "USD"

    reference_price: Decimal = Decimal("0.00")

    # Quality fields used by pricing engine
    quality_fields: List[str] = field(
        default_factory=list
    )


# =============================================================
# PHYSICAL LOT
# =============================================================

@dataclass
class AgriculturalLot:

    lot_id: str

    commodity: Commodity

    producer_id: str

    origin_country: str

    origin_region: str

    harvest_year: str

    quantity: Decimal

    warehouse: str

    grade: str = "STANDARD"

    certification: str = "STANDARD"

    # Flexible commodity quality data
    quality: Dict[str, Decimal] = field(
        default_factory=dict
    )

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


# =============================================================
# ORDER
# =============================================================

@dataclass(order=True)
class Order:

    sort_key: tuple = field(
        init=False,
        repr=False
    )

    order_id: str

    trader_id: str

    lot_id: str

    side: Side

    order_type: OrderType

    price: Optional[Decimal]

    quantity: Decimal

    remaining: Decimal

    timestamp: datetime = field(
        default_factory=now
    )

    status: OrderStatus = (
        OrderStatus.OPEN
    )

    def __post_init__(self):

        # Highest bids first
        if self.side == Side.BUY:

            self.sort_key = (
                -self.price
                if self.price is not None
                else Decimal("0"),

                self.timestamp.timestamp()
            )

        # Lowest offers first
        else:

            self.sort_key = (
                self.price
                if self.price is not None
                else Decimal("0"),

                self.timestamp.timestamp()
            )


# =============================================================
# TRADE
# =============================================================

@dataclass
class Trade:

    trade_id: str

    commodity_symbol: str

    lot_id: str

    buyer_id: str

    seller_id: str

    price: Decimal

    quantity: Decimal

    currency: str

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional(self):

        return money(
            self.price
            * self.quantity
        )


# =============================================================
# QUALITY PRICING ENGINE
# =============================================================

class QualityPricingEngine:

    """
    Generic quality-adjustment model.

    Base price
        × grade
        × quality factors
        × origin basis
        × certification basis

    Individual commodities can override this model.
    """

    GRADE_FACTORS = {

        "PREMIUM": Decimal("1.12"),
        "CHOICE": Decimal("1.07"),
        "STANDARD": Decimal("1.00"),
        "LOW": Decimal("0.90"),
        "REJECT": Decimal("0.70")
    }

    CERTIFICATION_FACTORS = {

        "STANDARD": Decimal("1.00"),
        "ORGANIC": Decimal("1.05"),
        "SUSTAINABLE": Decimal("1.03"),
        "FAIR_TRADE": Decimal("1.04"),
        "PDO": Decimal("1.08"),
        "PGI": Decimal("1.05")
    }

    def calculate(
        self,
        lot: AgriculturalLot
    ):

        price = (
            lot.commodity.reference_price
        )

        # Grade
        price *= self.GRADE_FACTORS.get(
            lot.grade.upper(),
            Decimal("1.00")
        )

        # Certification
        price *= self.CERTIFICATION_FACTORS.get(
            lot.certification.upper(),
            Decimal("1.00")
        )

        # Generic quality score
        #
        # Each score is assumed to run
        # from 0 to 10.
        #
        # A score of 5 is neutral.

        for field_name, score in (
            lot.quality.items()
        ):

            score = Decimal(
                str(score)
            )

            factor = (
                Decimal("0.90")
                + (
                    score
                    / Decimal("10")
                    * Decimal("0.20")
                )
            )

            price *= factor

        return money(
            max(
                price,
                Decimal("0.01")
            )
        )


# =============================================================
# ORDER BOOK
# =============================================================

class OrderBook:

    def __init__(
        self,
        lot_id
    ):

        self.lot_id = lot_id

        self.bids = []
        self.asks = []

        self.orders = {}

        self.trades = []

    # ---------------------------------------------------------
    # ADD ORDER
    # ---------------------------------------------------------

    def add(
        self,
        order
    ):

        self.orders[
            order.order_id
        ] = order

        if order.side == Side.BUY:

            heappush(
                self.bids,
                order
            )

        else:

            heappush(
                self.asks,
                order
            )

    # ---------------------------------------------------------
    # BEST BID
    # ---------------------------------------------------------

    def best_bid(self):

        while self.bids:

            order = self.bids[0]

            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELLED
            ):

                heappop(
                    self.bids
                )

            else:

                return order

        return None

    # ---------------------------------------------------------
    # BEST ASK
    # ---------------------------------------------------------

    def best_ask(self):

        while self.asks:

            order = self.asks[0]

            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELLED
            ):

                heappop(
                    self.asks
                )

            else:

                return order

        return None

    # ---------------------------------------------------------
    # MATCH
    # ---------------------------------------------------------

    def match(
        self,
        lot: AgriculturalLot
    ):

        executions = []

        while True:

            bid = self.best_bid()
            ask = self.best_ask()

            if not bid or not ask:

                break

            bid_crosses = (

                bid.order_type
                == OrderType.MARKET

                or bid.price >= ask.price
            )

            ask_crosses = (

                ask.order_type
                == OrderType.MARKET

                or ask.price <= bid.price
            )

            if not (
                bid_crosses
                and ask_crosses
            ):

                break

            trade_quantity = min(

                bid.remaining,

                ask.remaining
            )

            # Price established by
            # earlier resting order.

            if (
                bid.timestamp
                <= ask.timestamp
            ):

                execution_price = (
                    ask.price
                    if ask.price is not None
                    else bid.price
                )

            else:

                execution_price = (
                    bid.price
                    if bid.price is not None
                    else ask.price
                )

            if execution_price is None:

                raise ValueError(
                    "Execution price unavailable"
                )

            trade = Trade(

                trade_id=str(
                    uuid4()
                ),

                commodity_symbol=(
                    lot.commodity.symbol
                ),

                lot_id=lot.lot_id,

                buyer_id=bid.trader_id,

                seller_id=ask.trader_id,

                price=money(
                    execution_price
                ),

                quantity=quantity(
                    trade_quantity
                ),

                currency=(
                    lot.commodity.currency
                )
            )

            self.trades.append(
                trade
            )

            executions.append(
                trade
            )

            bid.remaining -= (
                trade_quantity
            )

            ask.remaining -= (
                trade_quantity
            )

            self.update_status(
                bid
            )

            self.update_status(
                ask
            )

        return executions

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    @staticmethod
    def update_status(
        order
    ):

        if order.remaining <= 0:

            order.remaining = (
                Decimal("0")
            )

            order.status = (
                OrderStatus.FILLED
            )

        elif order.remaining < order.quantity:

            order.status = (
                OrderStatus.PARTIALLY_FILLED
            )


# =============================================================
# RHINO AGRICULTURAL EXCHANGE
# =============================================================

class RhinoAgriculturalExchange:

    def __init__(self):

        self.commodities = {}

        self.lots = {}

        self.order_books = {}

        self.trades = []

        self.pricing = (
            QualityPricingEngine()
        )

    # ---------------------------------------------------------
    # REGISTER COMMODITY
    # ---------------------------------------------------------

    def register_commodity(
        self,
        commodity
    ):

        self.commodities[
            commodity.symbol
        ] = commodity

    # ---------------------------------------------------------
    # REGISTER PHYSICAL LOT
    # ---------------------------------------------------------

    def register_lot(
        self,
        lot
    ):

        if (
            lot.commodity.symbol
            not in self.commodities
        ):

            raise ValueError(
                "Commodity not registered"
            )

        self.lots[
            lot.lot_id
        ] = lot

        self.order_books[
            lot.lot_id
        ] = OrderBook(
            lot.lot_id
        )

    # ---------------------------------------------------------
    # THEORETICAL SPOT
    # ---------------------------------------------------------

    def theoretical_spot(
        self,
        lot_id
    ):

        lot = self.lots[
            lot_id
        ]

        return self.pricing.calculate(
            lot
        )

    # ---------------------------------------------------------
    # SUBMIT ORDER
    # ---------------------------------------------------------

    def submit_order(
        self,
        trader_id,
        lot_id,
        side,
        order_type,
        quantity_value,
        price=None
    ):

        lot = self.lots[
            lot_id
        ]

        quantity_value = quantity(
            quantity_value
        )

        if quantity_value <= 0:

            raise ValueError(
                "Quantity must be positive"
            )

        # Sellers must have physical
        # inventory.

        if (
            side == Side.SELL
            and quantity_value
            > lot.available_quantity
        ):

            raise ValueError(
                "Insufficient inventory"
            )

        if (
            order_type == OrderType.LIMIT
            and (
                price is None
                or price <= 0
            )
        ):

            raise ValueError(
                "Limit order requires price"
            )

        order = Order(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            lot_id=lot_id,

            side=side,

            order_type=order_type,

            price=(
                money(price)
                if price is not None
                else None
            ),

            quantity=quantity_value,

            remaining=quantity_value
        )

        book = self.order_books[
            lot_id
        ]

        book.add(
            order
        )

        executions = book.match(
            lot
        )

        for trade in executions:

            lot.available_quantity -= (
                trade.quantity
            )

        self.trades.extend(
            executions
        )

        return order

    # ---------------------------------------------------------
    # VWAP
    # ---------------------------------------------------------

    def vwap(
        self,
        lot_id
    ):

        trades = self.order_books[
            lot_id
        ].trades

        if not trades:

            return None

        total_value = sum(

            (
                trade.price
                * trade.quantity

                for trade in trades
            ),

            Decimal("0")
        )

        total_volume = sum(

            (
                trade.quantity

                for trade in trades
            ),

            Decimal("0")
        )

        if total_volume == 0:

            return None

        return money(
            total_value
            / total_volume
        )

    # ---------------------------------------------------------
    # MARKET SNAPSHOT
    # ---------------------------------------------------------

    def snapshot(
        self,
        lot_id
    ):

        lot = self.lots[
            lot_id
        ]

        book = self.order_books[
            lot_id
        ]

        bid = book.best_bid()
        ask = book.best_ask()

        last = (
            book.trades[-1]
            if book.trades
            else None
        )

        vwap = self.vwap(
            lot_id
        )

        return {

            "symbol":
                lot.commodity.symbol,

            "commodity":
                lot.commodity.name,

            "sector":
                lot.commodity.sector.value,

            "origin":
                lot.origin_country,

            "region":
                lot.origin_region,

            "crop_year":
                lot.harvest_year,

            "warehouse":
                lot.warehouse,

            "grade":
                lot.grade,

            "theoretical_spot":
                str(
                    self.theoretical_spot(
                        lot_id
                    )
                ),

            "best_bid":
                (
                    str(bid.price)
                    if bid
                    else None
                ),

            "best_ask":
                (
                    str(ask.price)
                    if ask
                    else None
                ),

            "last":
                (
                    str(last.price)
                    if last
                    else None
                ),

            "vwap":
                (
                    str(vwap)
                    if vwap
                    else None
                ),

            "available_quantity":
                str(
                    lot.available_quantity
                ),

            "unit":
                lot.commodity.base_unit,

            "currency":
                lot.commodity.currency,

            "timestamp":
                now().isoformat()
        }


# =============================================================
# DEMONSTRATION
# =============================================================

if __name__ == "__main__":

    exchange = (
        RhinoAgriculturalExchange()
    )

    # ---------------------------------------------------------
    # WHEAT
    # ---------------------------------------------------------

    wheat = Commodity(

        symbol="RASE-WHT",

        name="Milling Wheat",

        sector=CommoditySector.GRAIN,

        base_unit="tonne",

        currency="USD",

        reference_price=Decimal(
            "245.00"
        ),

        quality_fields=[
            "protein",
            "test_weight",
            "falling_number"
        ]
    )

    exchange.register_commodity(
        wheat
    )

    wheat_lot = AgriculturalLot(

        lot_id="WHT-UK-2026-001",

        commodity=wheat,

        producer_id="FARM-001",

        origin_country="United Kingdom",

        origin_region="East Anglia",

        harvest_year="2026",

        quantity=Decimal(
            "500"
        ),

        warehouse="RHINO-WH-01",

        grade="PREMIUM",

        certification="STANDARD",

        quality={

            "protein": Decimal("8.5"),

            "test_weight": Decimal("8.8"),

            "falling_number": Decimal("8.0")
        }
    )

    exchange.register_lot(
        wheat_lot
    )

    # ---------------------------------------------------------
    # COFFEE
    # ---------------------------------------------------------

    coffee = Commodity(

        symbol="RASE-CFE",

        name="Arabica Coffee",

        sector=CommoditySector.SOFT,

        base_unit="kg",

        currency="USD",

        reference_price=Decimal(
            "6.20"
        ),

        quality_fields=[
            "cup_score",
            "bean_uniformity",
            "defect_score"
        ]
    )

    exchange.register_commodity(
        coffee
    )

    coffee_lot = AgriculturalLot(

        lot_id="CFE-BR-2026-001",

        commodity=coffee,

        producer_id="COFFEE-001",

        origin_country="Brazil",

        origin_region="Minas Gerais",

        harvest_year="2026",

        quantity=Decimal(
            "25000"
        ),

        warehouse="RHINO-BR-01",

        grade="CHOICE",

        certification="SUSTAINABLE",

        quality={

            "cup_score": Decimal("8.5"),

            "bean_uniformity": Decimal("8.0"),

            "defect_score": Decimal("9.0")
        }
    )

    exchange.register_lot(
        coffee_lot
    )

    # ---------------------------------------------------------
    # OLIVE OIL
    # ---------------------------------------------------------

    olive_oil = Commodity(

        symbol="RASE-EVOO",

        name="Extra Virgin Olive Oil",

        sector=CommoditySector.SPECIALITY,

        base_unit="kg",

        currency="EUR",

        reference_price=Decimal(
            "6.80"
        ),

        quality_fields=[
            "sensory_score",
            "acidity",
            "peroxide"
        ]
    )

    exchange.register_commodity(
        olive_oil
    )

    oil_lot = AgriculturalLot(

        lot_id="EVOO-ES-2026-001",

        commodity=olive_oil,

        producer_id="OLIVE-001",

        origin_country="Spain",

        origin_region="Andalusia",

        harvest_year="2026",

        quantity=Decimal(
            "100000"
        ),

        warehouse="RHINO-ES-01",

        grade="PREMIUM",

        certification="ORGANIC",

        quality={

            "sensory_score":
                Decimal("9.0"),

            "acidity":
                Decimal("9.5"),

            "peroxide":
                Decimal("9.0")
        }
    )

    exchange.register_lot(
        oil_lot
    )

    # ---------------------------------------------------------
    # DISPLAY MARKETS
    # ---------------------------------------------------------

    print()
    print(
        "=================================================="
    )

    print(
        "        RHINO AGRICULTURAL EXCHANGE"
    )

    print(
        "        RASE — PHYSICAL SPOT MARKET"
    )

    print(
        "=================================================="
    )

    for lot_id in [
        wheat_lot.lot_id,
        coffee_lot.lot_id,
        oil_lot.lot_id
    ]:

        print()

        snapshot = (
            exchange.snapshot(
                lot_id
            )
        )

        for key, value in snapshot.items():

            print(
                f"{key:24} {value}"
            )

        print(
            "--------------------------------------------------"
        )

    # ---------------------------------------------------------
    # WHEAT TRADE
    # ---------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-FOOD-001",

        lot_id=wheat_lot.lot_id,

        side=Side.BUY,

        order_type=OrderType.LIMIT,

        quantity_value=100,

        price=Decimal("252.00")
    )

    exchange.submit_order(

        trader_id="FARM-001",

        lot_id=wheat_lot.lot_id,

        side=Side.SELL,

        order_type=OrderType.LIMIT,

        quantity_value=100,

        price=Decimal("250.00")
    )

    # ---------------------------------------------------------
    # TRADE REPORT
    # ---------------------------------------------------------

    print()
    print(
        "TRADE BLOTTER"
    )

    print(
        "=================================================="
    )

    for trade in exchange.trades:

        print(

            trade.commodity_symbol,
            "|",

            trade.quantity,
            "|",

            trade.price,
            trade.currency,

            "| NOTIONAL:",

            trade.notional
        )
