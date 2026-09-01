"""
=============================================================
RHINO INTERMODAL FREIGHT EXCHANGE
RIFE 1.0
=============================================================

Physical intermodal container spot pricing engine.

Supports:

    - container equipment
    - port-to-port ocean rates
    - trucking
    - rail
    - terminal handling
    - bunker/fuel
    - congestion
    - security/canal surcharges
    - equipment imbalance
    - FX
    - complete-door-to-door spot price
    - route comparison
    - market orders
    - bids / offers
    - VWAP
    - trade execution

This is a pricing/exchange foundation.
Production deployment requires authenticated market
participants, validated data feeds, contracts, risk,
settlement and regulatory controls.
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


def now():
    return datetime.now(timezone.utc)


# ============================================================
# ENUMS
# ============================================================

class Equipment(Enum):

    DV20 = "20DV"

    DV40 = "40DV"

    HC40 = "40HC"

    HC45 = "45HC"

    REEFER40 = "40REEFER"


class TransportMode(Enum):

    TRUCK = "TRUCK"

    RAIL = "RAIL"

    OCEAN = "OCEAN"


class Side(Enum):

    BUY = "BUY"

    SELL = "SELL"


# ============================================================
# PORT
# ============================================================

@dataclass
class Port:

    code: str

    name: str

    country: str

    region: str

    congestion_index: Decimal = D("0")


# ============================================================
# ROUTE
# ============================================================

@dataclass
class Route:

    route_id: str

    origin: Port

    destination: Port

    distance_km: Decimal

    ocean_days: int

    equipment: Equipment


# ============================================================
# FREIGHT COMPONENT
# ============================================================

@dataclass
class FreightComponent:

    name: str

    amount: Decimal

    currency: str = "USD"


# ============================================================
# PHYSICAL SHIPMENT
# ============================================================

@dataclass
class Shipment:

    shipment_id: str

    route: Route

    equipment: Equipment

    cargo_weight_tonnes: Decimal

    shipper: str

    consignee: str

    origin_postcode: Optional[str] = None

    destination_postcode: Optional[str] = None

    origin_trucking: Decimal = D("0")

    destination_trucking: Decimal = D("0")

    origin_rail: Decimal = D("0")

    destination_rail: Decimal = D("0")

    origin_terminal: Decimal = D("0")

    destination_terminal: Decimal = D("0")

    ocean_rate: Decimal = D("0")

    bunker_surcharge: Decimal = D("0")

    congestion_surcharge: Decimal = D("0")

    security_surcharge: Decimal = D("0")

    canal_surcharge: Decimal = D("0")

    equipment_surcharge: Decimal = D("0")

    other_surcharges: Decimal = D("0")

    currency: str = "USD"


# ============================================================
# MARKET RATE
# ============================================================

@dataclass
class MarketRate:

    route_id: str

    equipment: Equipment

    carrier: str

    rate: Decimal

    currency: str

    valid_from: datetime

    valid_until: datetime

    source: str


# ============================================================
# PRICE ENGINE
# ============================================================

class IntermodalPriceEngine:

    """
    Calculates a complete intermodal spot price.
    """

    def calculate(
        self,
        shipment: Shipment,
        fx_rate: Decimal = D("1")
    ):

        components = [

            shipment.ocean_rate,

            shipment.origin_trucking,

            shipment.destination_trucking,

            shipment.origin_rail,

            shipment.destination_rail,

            shipment.origin_terminal,

            shipment.destination_terminal,

            shipment.bunker_surcharge,

            shipment.congestion_surcharge,

            shipment.security_surcharge,

            shipment.canal_surcharge,

            shipment.equipment_surcharge,

            shipment.other_surcharges,
        ]

        total = sum(
            components,
            D("0")
        )

        return money(
            total * D(fx_rate)
        )


# ============================================================
# MARKET BOOK
# ============================================================

@dataclass
class FreightOrder:

    order_id: str

    trader_id: str

    route_id: str

    equipment: Equipment

    side: Side

    quantity: int

    price: Decimal

    remaining: int = field(
        init=False
    )

    timestamp: datetime = field(
        default_factory=now
    )

    def __post_init__(self):

        self.remaining = self.quantity


# ============================================================
# TRADE
# ============================================================

@dataclass
class FreightTrade:

    trade_id: str

    route_id: str

    equipment: Equipment

    buyer: str

    seller: str

    quantity: int

    price: Decimal

    currency: str

    timestamp: datetime = field(
        default_factory=now
    )

    @property
    def notional(self):

        return money(
            self.quantity
            * self.price
        )


# ============================================================
# RHINO INTERMODAL EXCHANGE
# ============================================================

class RhinoIntermodalExchange:

    def __init__(self):

        self.routes: Dict[
            str,
            Route
        ] = {}

        self.market_rates: List[
            MarketRate
        ] = []

        self.bids: List[
            FreightOrder
        ] = []

        self.asks: List[
            FreightOrder
        ] = []

        self.trades: List[
            FreightTrade
        ] = []

        self.pricer = (
            IntermodalPriceEngine()
        )

    # --------------------------------------------------------
    # REGISTER ROUTE
    # --------------------------------------------------------

    def register_route(
        self,
        route: Route
    ):

        self.routes[
            route.route_id
        ] = route

    # --------------------------------------------------------
    # ADD MARKET RATE
    # --------------------------------------------------------

    def add_market_rate(
        self,
        rate: MarketRate
    ):

        self.market_rates.append(
            rate
        )

    # --------------------------------------------------------
    # MARKET MEDIAN
    # --------------------------------------------------------

    def market_median(
        self,
        route_id,
        equipment
    ):

        rates = [

            r.rate

            for r in self.market_rates

            if (
                r.route_id
                == route_id
                and r.equipment
                == equipment
            )
        ]

        if not rates:

            return None

        rates.sort()

        middle = len(rates) // 2

        if len(rates) % 2:

            return money(
                rates[middle]
            )

        return money(
            (
                rates[middle - 1]
                + rates[middle]
            )
            / 2
        )

    # --------------------------------------------------------
    # SUBMIT ORDER
    # --------------------------------------------------------

    def submit_order(
        self,
        trader_id,
        route_id,
        equipment,
        side,
        quantity,
        price
    ):

        order = FreightOrder(

            order_id=str(
                uuid4()
            ),

            trader_id=trader_id,

            route_id=route_id,

            equipment=equipment,

            side=side,

            quantity=quantity,

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
    # MATCHING
    # --------------------------------------------------------

    def match(self):

        executions = []

        while self.bids and self.asks:

            bid = self.bids[0]

            ask = self.asks[0]

            if (
                bid.route_id
                != ask.route_id
            ):

                break

            if (
                bid.equipment
                != ask.equipment
            ):

                break

            if bid.price < ask.price:

                break

            quantity = min(
                bid.remaining,
                ask.remaining
            )

            trade = FreightTrade(

                trade_id=str(
                    uuid4()
                ),

                route_id=bid.route_id,

                equipment=bid.equipment,

                buyer=bid.trader_id,

                seller=ask.trader_id,

                quantity=quantity,

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
        route_id,
        equipment
    ):

        trades = [

            trade

            for trade in self.trades

            if (
                trade.route_id
                == route_id
                and trade.equipment
                == equipment
            )
        ]

        if not trades:

            return None

        value = sum(

            (
                trade.price
                * trade.quantity
            )

            for trade in trades
        )

        volume = sum(

            trade.quantity

            for trade in trades
        )

        if volume == 0:

            return None

        return money(
            value / volume
        )

    # --------------------------------------------------------
    # SPOT QUOTE
    # --------------------------------------------------------

    def spot_quote(
        self,
        shipment: Shipment,
        fx_rate=D("1")
    ):

        return self.pricer.calculate(
            shipment,
            fx_rate
        )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    def snapshot(
        self,
        route_id,
        equipment
    ):

        bids = [

            b for b in self.bids

            if (
                b.route_id == route_id
                and b.equipment == equipment
            )
        ]

        asks = [

            a for a in self.asks

            if (
                a.route_id == route_id
                and a.equipment == equipment
            )
        ]

        median = self.market_median(
            route_id,
            equipment
        )

        return {

            "market":
                "RHINO INTERMODAL "
                "FREIGHT EXCHANGE",

            "route":
                route_id,

            "equipment":
                equipment.value,

            "market_median":
                str(median)
                if median
                else None,

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
                        route_id,
                        equipment
                    )
                    or D("0")
                ),

            "timestamp":
                now().isoformat()
        }


# ============================================================
# EXAMPLE
# ============================================================

if __name__ == "__main__":

    exchange = (
        RhinoIntermodalExchange()
    )

    # --------------------------------------------------------
    # PORTS
    # --------------------------------------------------------

    shanghai = Port(

        code="CNSHA",

        name="Shanghai",

        country="China",

        region="Asia"
    )

    rotterdam = Port(

        code="NLRTM",

        name="Rotterdam",

        country="Netherlands",

        region="Europe"
    )

    # --------------------------------------------------------
    # ROUTE
    # --------------------------------------------------------

    route = Route(

        route_id="SHA-RTM",

        origin=shanghai,

        destination=rotterdam,

        distance_km=D("20500"),

        ocean_days=30,

        equipment=Equipment.HC40
    )

    exchange.register_route(
        route
    )

    # --------------------------------------------------------
    # MARKET DATA
    # --------------------------------------------------------

    exchange.add_market_rate(

        MarketRate(

            route_id="SHA-RTM",

            equipment=Equipment.HC40,

            carrier="CARRIER-A",

            rate=D("4200"),

            currency="USD",

            valid_from=now(),

            valid_until=now(),

            source="MARKET"
        )
    )

    exchange.add_market_rate(

        MarketRate(

            route_id="SHA-RTM",

            equipment=Equipment.HC40,

            carrier="CARRIER-B",

            rate=D("4350"),

            currency="USD",

            valid_from=now(),

            valid_until=now(),

            source="MARKET"
        )
    )

    exchange.add_market_rate(

        MarketRate(

            route_id="SHA-RTM",

            equipment=Equipment.HC40,

            carrier="CARRIER-C",

            rate=D("4275"),

            currency="USD",

            valid_from=now(),

            valid_until=now(),

            source="MARKET"
        )
    )

    # --------------------------------------------------------
    # PHYSICAL SHIPMENT
    # --------------------------------------------------------

    shipment = Shipment(

        shipment_id="SHIP-001",

        route=route,

        equipment=Equipment.HC40,

        cargo_weight_tonnes=D("18"),

        shipper="RHINO-CLIENT-001",

        consignee="RHINO-CLIENT-002",

        origin_trucking=D("350"),

        destination_trucking=D("475"),

        origin_terminal=D("125"),

        destination_terminal=D("145"),

        ocean_rate=D("4275"),

        bunker_surcharge=D("180"),

        congestion_surcharge=D("120"),

        security_surcharge=D("65"),

        canal_surcharge=D("0"),

        equipment_surcharge=D("50")
    )

    # --------------------------------------------------------
    # SPOT PRICE
    # --------------------------------------------------------

    spot = exchange.spot_quote(
        shipment
    )

    print()
    print(
        "RHINO INTERMODAL "
        "FREIGHT EXCHANGE"
    )

    print(
        "=============================="
    )

    print(
        "Route:",
        route.origin.code,
        "→",
        route.destination.code
    )

    print(
        "Equipment:",
        shipment.equipment.value
    )

    print(
        "Spot price:",
        spot,
        "USD"
    )

    # --------------------------------------------------------
    # ORDER BOOK
    # --------------------------------------------------------

    exchange.submit_order(

        trader_id="RHINO-SHIPPER",

        route_id="SHA-RTM",

        equipment=Equipment.HC40,

        side=Side.BUY,

        quantity=100,

        price=4500
    )

    exchange.submit_order(

        trader_id="RHINO-CARRIER",

        route_id="SHA-RTM",

        equipment=Equipment.HC40,

        side=Side.SELL,

        quantity=100,

        price=4450
    )

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    print()

    snapshot = exchange.snapshot(

        "SHA-RTM",

        Equipment.HC40
    )

    for key, value in snapshot.items():

        print(
            f"{key:20} {value}"
        )

    # --------------------------------------------------------
    # TRADES
    # --------------------------------------------------------

    print()

    print(
        "TRADE BLOTTER"
    )

    print(
        "=============="
    )

    for trade in exchange.trades:

        print(

            trade.route_id,

            trade.equipment.value,

            trade.quantity,

            "@",

            trade.price,

            "USD"
        )
