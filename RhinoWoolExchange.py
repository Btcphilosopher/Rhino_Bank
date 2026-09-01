from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from heapq import heappop, heappush
from typing import Dict, List, Optional
from uuid import uuid4


# ============================================================
# CONFIGURATION
# ============================================================

PRICE_QUANTUM = Decimal("0.01")
KG_QUANTUM = Decimal("0.001")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(
        PRICE_QUANTUM,
        rounding=ROUND_HALF_UP
    )


def quantity(value) -> Decimal:
    return Decimal(str(value)).quantize(
        KG_QUANTUM,
        rounding=ROUND_HALF_UP
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# ENUMS
# ============================================================

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class WoolType(str, Enum):
    MERINO = "MERINO"
    CROSSBRED = "CROSSBRED"
    FINE = "FINE"
    MEDIUM = "MEDIUM"
    COARSE = "COARSE"


# ============================================================
# WOOL LOT
# ============================================================

@dataclass
class WoolLot:
    lot_id: str

    origin: str
    wool_type: WoolType

    # Technical wool characteristics
    micron: Decimal
    staple_length_mm: Decimal
    yield_percent: Decimal
    tensile_strength_nkt: Decimal
    colour_grade: str

    # Commercial information
    quantity_kg: Decimal
    currency: str = "GBP"

    created_at: datetime = field(default_factory=now_utc)

    def quality_score(self) -> Decimal:
        """
        Simplified quality model.

        Higher score = higher commercial quality.
        This should eventually be replaced by a calibrated
        statistical pricing model trained on actual auction data.
        """

        micron_score = max(
            Decimal("0"),
            Decimal("100") - abs(self.micron - Decimal("19")) * Decimal("4")
        )

        yield_score = min(
            Decimal("100"),
            self.yield_percent
        )

        staple_score = min(
            Decimal("100"),
            self.staple_length_mm * Decimal("2")
        )

        strength_score = min(
            Decimal("100"),
            self.tensile_strength_nkt * Decimal("10")
        )

        score = (
            micron_score * Decimal("0.40")
            + yield_score * Decimal("0.25")
            + staple_score * Decimal("0.20")
            + strength_score * Decimal("0.15")
        )

        return score.quantize(Decimal("0.01"))


# ============================================================
# BENCHMARK PRICE
# ============================================================

@dataclass
class Benchmark:
    """
    Market benchmark used as the starting point for
    quality-adjusted spot pricing.
    """

    name: str
    price_per_kg: Decimal
    currency: str = "GBP"
    timestamp: datetime = field(default_factory=now_utc)

    def update(self, new_price):
        self.price_per_kg = money(new_price)
        self.timestamp = now_utc()


# ============================================================
# SPOT PRICING ENGINE
# ============================================================

class WoolSpotPricingEngine:

    def __init__(self, benchmark: Benchmark):

        self.benchmark = benchmark

    def calculate_quality_adjustment(
        self,
        lot: WoolLot
    ) -> Decimal:

        score = lot.quality_score()

        # 50 = neutral
        adjustment = (score - Decimal("50")) / Decimal("100")

        return adjustment

    def calculate_spot_price(
        self,
        lot: WoolLot
    ) -> Decimal:

        benchmark = self.benchmark.price_per_kg

        quality_adjustment = self.calculate_quality_adjustment(lot)

        price = benchmark * (
            Decimal("1") + quality_adjustment
        )

        return money(max(price, Decimal("0.01")))


# ============================================================
# ORDERS
# ============================================================

@dataclass(order=True)
class Order:

    sort_index: tuple = field(init=False, repr=False)

    order_id: str
    trader_id: str
    lot_id: str
    side: Side
    order_type: OrderType

    price: Optional[Decimal]
    quantity_kg: Decimal

    remaining_kg: Decimal

    timestamp: datetime = field(default_factory=now_utc)

    status: OrderStatus = OrderStatus.OPEN

    def __post_init__(self):

        # Buy orders:
        # highest price first.
        #
        # Sell orders:
        # lowest price first.

        if self.side == Side.BUY:

            self.sort_index = (
                -self.price if self.price else Decimal("0"),
                self.timestamp.timestamp()
            )

        else:

            self.sort_index = (
                self.price if self.price else Decimal("0"),
                self.timestamp.timestamp()
            )


# ============================================================
# TRADE
# ============================================================

@dataclass
class Trade:

    trade_id: str

    lot_id: str

    buyer_id: str
    seller_id: str

    price_per_kg: Decimal
    quantity_kg: Decimal

    timestamp: datetime = field(default_factory=now_utc)

    @property
    def notional(self) -> Decimal:

        return money(
            self.price_per_kg *
            self.quantity_kg
        )


# ============================================================
# ORDER BOOK
# ============================================================

class OrderBook:

    def __init__(self, lot_id: str):

        self.lot_id = lot_id

        self.bids: List[Order] = []
        self.asks: List[Order] = []

        self.orders: Dict[str, Order] = {}

        self.trades: List[Trade] = []

    # --------------------------------------------------------
    # ADD ORDER
    # --------------------------------------------------------

    def add_order(self, order: Order):

        if order.lot_id != self.lot_id:
            raise ValueError("Order belongs to different wool lot")

        self.orders[order.order_id] = order

        if order.side == Side.BUY:
            heappush(self.bids, order)

        else:
            heappush(self.asks, order)

    # --------------------------------------------------------
    # BEST BID
    # --------------------------------------------------------

    def best_bid(self) -> Optional[Order]:

        while self.bids:

            order = self.bids[0]

            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELLED
            ):
                heappop(self.bids)
                continue

            return order

        return None

    # --------------------------------------------------------
    # BEST ASK
    # --------------------------------------------------------

    def best_ask(self) -> Optional[Order]:

        while self.asks:

            order = self.asks[0]

            if order.status in (
                OrderStatus.FILLED,
                OrderStatus.CANCELLED
            ):
                heappop(self.asks)
                continue

            return order

        return None

    # --------------------------------------------------------
    # MATCH ENGINE
    # --------------------------------------------------------

    def match(self) -> List[Trade]:

        generated_trades = []

        while True:

            bid = self.best_bid()
            ask = self.best_ask()

            if not bid or not ask:
                break

            # Market orders have no price restriction.
            bid_crosses = (
                bid.order_type == OrderType.MARKET
                or bid.price >= ask.price
            )

            ask_crosses = (
                ask.order_type == OrderType.MARKET
                or ask.price <= bid.price
            )

            if not (bid_crosses and ask_crosses):
                break

            traded_quantity = min(
                bid.remaining_kg,
                ask.remaining_kg
            )

            # Price-time priority.
            #
            # Passive order establishes execution price.
            if bid.timestamp <= ask.timestamp:
                trade_price = (
                    ask.price
                    if ask.price is not None
                    else bid.price
                )
            else:
                trade_price = (
                    bid.price
                    if bid.price is not None
                    else ask.price
                )

            if trade_price is None:
                raise ValueError(
                    "Cannot execute trade without a price"
                )

            trade = Trade(
                trade_id=str(uuid4()),
                lot_id=self.lot_id,
                buyer_id=bid.trader_id,
                seller_id=ask.trader_id,
                price_per_kg=money(trade_price),
                quantity_kg=quantity(traded_quantity)
            )

            self.trades.append(trade)
            generated_trades.append(trade)

            bid.remaining_kg -= traded_quantity
            ask.remaining_kg -= traded_quantity

            self._update_status(bid)
            self._update_status(ask)

        return generated_trades

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    @staticmethod
    def _update_status(order: Order):

        if order.remaining_kg <= 0:

            order.remaining_kg = Decimal("0")
            order.status = OrderStatus.FILLED

        elif order.remaining_kg < order.quantity_kg:

            order.status = OrderStatus.PARTIALLY_FILLED

        else:

            order.status = OrderStatus.OPEN

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    def cancel_order(
        self,
        order_id: str
    ):

        if order_id not in self.orders:
            raise KeyError("Unknown order")

        order = self.orders[order_id]

        if order.status == OrderStatus.FILLED:
            raise ValueError("Filled order cannot be cancelled")

        order.status = OrderStatus.CANCELLED


# ============================================================
# EXCHANGE
# ============================================================

class RhinoWoolExchange:

    def __init__(self):

        self.lots: Dict[str, WoolLot] = {}

        self.books: Dict[str, OrderBook] = {}

        self.trades: List[Trade] = []

        self.pricing_engine = WoolSpotPricingEngine(
            Benchmark(
                name="RHINO WOOL SPOT",
                price_per_kg=Decimal("6.50")
            )
        )

    # --------------------------------------------------------
    # REGISTER LOT
    # --------------------------------------------------------

    def register_lot(
        self,
        lot: WoolLot
    ):

        self.lots[lot.lot_id] = lot

        self.books[lot.lot_id] = OrderBook(
            lot.lot_id
        )

    # --------------------------------------------------------
    # GET SPOT PRICE
    # --------------------------------------------------------

    def spot_price(
        self,
        lot_id: str
    ) -> Decimal:

        if lot_id not in self.lots:
            raise KeyError("Unknown wool lot")

        return self.pricing_engine.calculate_spot_price(
            self.lots[lot_id]
        )

    # --------------------------------------------------------
    # SUBMIT ORDER
    # --------------------------------------------------------

    def submit_order(
        self,
        trader_id: str,
        lot_id: str,
        side: Side,
        order_type: OrderType,
        quantity_kg: Decimal,
        price: Optional[Decimal] = None
    ) -> Order:

        if lot_id not in self.lots:
            raise KeyError("Unknown wool lot")

        if quantity_kg <= 0:
            raise ValueError(
                "Quantity must be positive"
            )

        if order_type == OrderType.LIMIT:

            if price is None or price <= 0:
                raise ValueError(
                    "Limit orders require positive price"
                )

        order = Order(
            order_id=str(uuid4()),
            trader_id=trader_id,
            lot_id=lot_id,
            side=side,
            order_type=order_type,
            price=money(price) if price else None,
            quantity_kg=quantity(quantity_kg),
            remaining_kg=quantity(quantity_kg)
        )

        self.books[lot_id].add_order(order)

        new_trades = self.books[lot_id].match()

        self.trades.extend(new_trades)

        return order

    # --------------------------------------------------------
    # MARKET SNAPSHOT
    # --------------------------------------------------------

    def market_snapshot(
        self,
        lot_id: str
    ) -> dict:

        book = self.books[lot_id]

        bid = book.best_bid()
        ask = book.best_ask()

        spot = self.spot_price(lot_id)

        return {
            "lot_id": lot_id,

            "spot_price": str(spot),

            "best_bid": (
                str(bid.price)
                if bid and bid.price
                else None
            ),

            "best_ask": (
                str(ask.price)
                if ask and ask.price
                else None
            ),

            "bid_quantity_kg": (
                str(bid.remaining_kg)
                if bid
                else "0"
            ),

            "ask_quantity_kg": (
                str(ask.remaining_kg)
                if ask
                else "0"
            ),

            "last_trade": (
                str(book.trades[-1].price_per_kg)
                if book.trades
                else None
            ),

            "timestamp": now_utc().isoformat()
        }


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    exchange = RhinoWoolExchange()

    # --------------------------------------------------------
    # Example wool lot
    # --------------------------------------------------------

    lot = WoolLot(
        lot_id="UK-MERINO-0001",

        origin="Yorkshire, UK",

        wool_type=WoolType.MERINO,

        micron=Decimal("18.5"),

        staple_length_mm=Decimal("75"),

        yield_percent=Decimal("78"),

        tensile_strength_nkt=Decimal("40"),

        colour_grade="AA",

        quantity_kg=Decimal("25000")
    )

    exchange.register_lot(lot)

    # --------------------------------------------------------
    # Calculate theoretical spot price
    # --------------------------------------------------------

    print(
        "THEORETICAL SPOT:",
        exchange.spot_price(lot.lot_id),
        "GBP/kg"
    )

    # --------------------------------------------------------
    # Buyer
    # --------------------------------------------------------

    exchange.submit_order(
        trader_id="RHINO-TEXTILES-001",
        lot_id=lot.lot_id,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity_kg=Decimal("5000"),
        price=Decimal("7.25")
    )

    # --------------------------------------------------------
    # Seller
    # --------------------------------------------------------

    exchange.submit_order(
        trader_id="YORKSHIRE-WOOL-001",
        lot_id=lot.lot_id,
        side=Side.SELL,
        order_type=OrderType.LIMIT,
        quantity_kg=Decimal("3000"),
        price=Decimal("7.10")
    )

    # --------------------------------------------------------
    # Market state
    # --------------------------------------------------------

    snapshot = exchange.market_snapshot(
        lot.lot_id
    )

    print("\nMARKET SNAPSHOT")

    for key, value in snapshot.items():
        print(f"{key:20} {value}")

    # --------------------------------------------------------
    # Trades
    # --------------------------------------------------------

    print("\nEXECUTED TRADES")

    for trade in exchange.trades:

        print(
            trade.trade_id,
            trade.quantity_kg,
            "kg @",
            trade.price_per_kg,
            "GBP/kg",
            "NOTIONAL:",
            trade.notional
        )
