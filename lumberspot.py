"""
===============================================================
 RHINOQUANT LUMBER SPOT
 Institutional Lumber Spot Pricing & Market Data Engine
===============================================================

 Python 3.12+

 Designed for:
   - lumber mills
   - timber merchants
   - distributors
   - institutional commodity desks
   - procurement departments
   - construction companies
   - market analysts

 This is a pricing/market-data prototype.
 It does NOT execute real financial trades.

 Core architecture:

       SUPPLIERS / MILLS
              |
              v
       +---------------+
       | Market Inputs |
       +-------+-------+
               |
               v
       +---------------+
       | Normalization |
       +-------+-------+
               |
               v
       +---------------+
       | Spot Pricing  |
       |    Engine     |
       +-------+-------+
               |
       +-------+-------+
       |       |       |
       v       v       v
     VWAP    FAIR    BASIS
       |       |       |
       +-------+-------+
               |
               v
       +---------------+
       | RhinoQuant    |
       | Market API    |
       +-------+-------+
               |
               v
       Dashboard / ERP / BI

===============================================================
"""

from __future__ import annotations

import math
import sqlite3
import statistics
import threading
import uuid

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn


# =============================================================
# CONFIGURATION
# =============================================================

DATABASE = "rhinoquant_lumber.db"

MAX_HISTORY = 10_000

DEFAULT_CURRENCY = "USD"

DEFAULT_REGION = "PNW"


# =============================================================
# UTILITY FUNCTIONS
# =============================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def safe_mean(values):
    if not values:
        return 0.0
    return statistics.mean(values)


def safe_median(values):
    if not values:
        return 0.0
    return statistics.median(values)


def pct_change(old, new):
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100.0


# =============================================================
# ENUM-LIKE CONSTANTS
# =============================================================

SPECIES = {
    "SPF": "Spruce-Pine-Fir",
    "SPRUCE": "Spruce",
    "PINE": "Pine",
    "FIR": "Fir",
    "DOUGLAS_FIR": "Douglas Fir",
    "HEMLOCK": "Hemlock",
    "WESTERN_RED_CEDAR": "Western Red Cedar",
    "OAK": "Oak",
    "MAPLE": "Maple",
    "BIRCH": "Birch",
}

GRADES = {
    "STRUCTURAL": "Structural",
    "SELECT": "Select",
    "PREMIUM": "Premium",
    "UTILITY": "Utility",
    "PALLET": "Pallet",
    "INDUSTRIAL": "Industrial",
}

REGIONS = {
    "PNW": "Pacific Northwest",
    "SE": "Southeast",
    "NE": "Northeast",
    "MW": "Midwest",
    "CA": "California",
    "BC": "British Columbia",
    "EU": "Europe",
    "UK": "United Kingdom",
}


# =============================================================
# LUMBER INSTRUMENT
# =============================================================

@dataclass(frozen=True)
class LumberInstrument:

    symbol: str

    species: str

    grade: str

    thickness_in: float

    width_in: float

    length_ft: float

    region: str

    currency: str = "USD"

    unit: str = "MBF"

    def description(self) -> str:

        return (
            f"{self.species} "
            f"{self.grade} "
            f"{self.thickness_in}x{self.width_in} "
            f"{self.length_ft}ft "
            f"{self.region}"
        )


# =============================================================
# MARKET QUOTE
# =============================================================

@dataclass
class Quote:

    quote_id: str

    symbol: str

    timestamp: datetime

    bid: Optional[float]

    ask: Optional[float]

    bid_size: float

    ask_size: float

    source: str

    region: str

    delivery_location: Optional[str] = None

    freight_per_mbf: float = 0.0

    notes: str = ""


# =============================================================
# TRADE
# =============================================================

@dataclass
class LumberTrade:

    trade_id: str

    symbol: str

    timestamp: datetime

    price: float

    quantity_mbf: float

    buyer: Optional[str]

    seller: Optional[str]

    region: str

    delivery_location: Optional[str]

    source: str

    freight_per_mbf: float = 0.0


# =============================================================
# MARKET SNAPSHOT
# =============================================================

@dataclass
class MarketSnapshot:

    symbol: str

    timestamp: datetime

    bid: Optional[float]

    ask: Optional[float]

    mid: Optional[float]

    last: Optional[float]

    vwap: Optional[float]

    high: Optional[float]

    low: Optional[float]

    volume_mbf: float

    trade_count: int

    spread: Optional[float]

    fair_value: Optional[float]

    volatility: float


# =============================================================
# DATABASE
# =============================================================

class Database:

    def __init__(self, path=DATABASE):

        self.path = path

        self.lock = threading.Lock()

        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False
        )

        self._create_tables()


    def _create_tables(self):

        with self.lock:

            cur = self.connection.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    quote_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    timestamp TEXT,
                    bid REAL,
                    ask REAL,
                    bid_size REAL,
                    ask_size REAL,
                    source TEXT,
                    region TEXT,
                    delivery_location TEXT,
                    freight_per_mbf REAL,
                    notes TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    timestamp TEXT,
                    price REAL,
                    quantity_mbf REAL,
                    buyer TEXT,
                    seller TEXT,
                    region TEXT,
                    delivery_location TEXT,
                    source TEXT,
                    freight_per_mbf REAL
                )
            """)

            self.connection.commit()


    def insert_quote(self, quote: Quote):

        with self.lock:

            self.connection.execute(
                """
                INSERT INTO quotes VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quote.quote_id,
                    quote.symbol,
                    quote.timestamp.isoformat(),
                    quote.bid,
                    quote.ask,
                    quote.bid_size,
                    quote.ask_size,
                    quote.source,
                    quote.region,
                    quote.delivery_location,
                    quote.freight_per_mbf,
                    quote.notes,
                )
            )

            self.connection.commit()


    def insert_trade(self, trade: LumberTrade):

        with self.lock:

            self.connection.execute(
                """
                INSERT INTO trades VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.trade_id,
                    trade.symbol,
                    trade.timestamp.isoformat(),
                    trade.price,
                    trade.quantity_mbf,
                    trade.buyer,
                    trade.seller,
                    trade.region,
                    trade.delivery_location,
                    trade.source,
                    trade.freight_per_mbf,
                )
            )

            self.connection.commit()


# =============================================================
# MARKET BOOK
# =============================================================

class MarketBook:

    def __init__(self):

        self.quotes = defaultdict(list)

        self.trades = defaultdict(
            lambda: deque(maxlen=MAX_HISTORY)
        )

        self.lock = threading.RLock()


    def add_quote(self, quote: Quote):

        with self.lock:

            self.quotes[quote.symbol].append(quote)

            # Keep most recent 500 quotes
            self.quotes[quote.symbol] = \
                self.quotes[quote.symbol][-500:]


    def add_trade(self, trade: LumberTrade):

        with self.lock:

            self.trades[
                trade.symbol
            ].append(trade)


    def latest_quote(self, symbol):

        with self.lock:

            quotes = self.quotes.get(symbol)

            if not quotes:
                return None

            return quotes[-1]


    def latest_trade(self, symbol):

        with self.lock:

            trades = self.trades.get(symbol)

            if not trades:
                return None

            return trades[-1]


    def recent_trades(
        self,
        symbol,
        hours=24
    ):

        cutoff = utc_now() - timedelta(hours=hours)

        with self.lock:

            return [
                t for t in self.trades.get(symbol, [])
                if t.timestamp >= cutoff
            ]


# =============================================================
# SPOT PRICING ENGINE
# =============================================================

class SpotPricingEngine:

    def __init__(self, book: MarketBook):

        self.book = book


    def calculate_vwap(
        self,
        symbol,
        hours=24
    ):

        trades = self.book.recent_trades(
            symbol,
            hours
        )

        if not trades:
            return None

        total_value = sum(
            t.price * t.quantity_mbf
            for t in trades
        )

        total_volume = sum(
            t.quantity_mbf
            for t in trades
        )

        if total_volume <= 0:
            return None

        return total_value / total_volume


    def last_price(self, symbol):

        trade = self.book.latest_trade(symbol)

        if trade is None:
            return None

        return trade.price


    def high_low(
        self,
        symbol,
        hours=24
    ):

        trades = self.book.recent_trades(
            symbol,
            hours
        )

        if not trades:
            return None, None

        prices = [
            t.price
            for t in trades
        ]

        return max(prices), min(prices)


    def volume(
        self,
        symbol,
        hours=24
    ):

        trades = self.book.recent_trades(
            symbol,
            hours
        )

        return sum(
            t.quantity_mbf
            for t in trades
        )


    def fair_value(self, symbol):

        quote = self.book.latest_quote(symbol)

        last = self.last_price(symbol)

        vwap = self.calculate_vwap(
            symbol
        )

        values = []

        if quote:

            if quote.bid is not None:
                values.append(quote.bid)

            if quote.ask is not None:
                values.append(quote.ask)

        if last is not None:
            values.append(last)

        if vwap is not None:
            values.append(vwap)

        if not values:
            return None

        return safe_mean(values)


    def volatility(
        self,
        symbol,
        hours=168
    ):

        trades = self.book.recent_trades(
            symbol,
            hours
        )

        if len(trades) < 2:
            return 0.0

        prices = [
            t.price
            for t in trades
        ]

        returns = []

        for i in range(1, len(prices)):

            if prices[i - 1] <= 0:
                continue

            returns.append(
                math.log(
                    prices[i] /
                    prices[i - 1]
                )
            )

        if len(returns) < 2:
            return 0.0

        return statistics.stdev(
            returns
        ) * math.sqrt(252)


    def snapshot(self, symbol):

        quote = \
            self.book.latest_quote(symbol)

        last = \
            self.last_price(symbol)

        vwap = \
            self.calculate_vwap(symbol)

        high, low = \
            self.high_low(symbol)

        volume = \
            self.volume(symbol)

        fair = \
            self.fair_value(symbol)

        spread = None

        if quote:

            if (
                quote.bid is not None
                and
                quote.ask is not None
            ):

                spread = \
                    quote.ask - quote.bid

        return MarketSnapshot(

            symbol=symbol,

            timestamp=utc_now(),

            bid=(
                quote.bid
                if quote else None
            ),

            ask=(
                quote.ask
                if quote else None
            ),

            mid=(
                (
                    quote.bid +
                    quote.ask
                ) / 2
                if quote
                and quote.bid is not None
                and quote.ask is not None
                else None
            ),

            last=last,

            vwap=vwap,

            high=high,

            low=low,

            volume_mbf=volume,

            trade_count=len(
                self.book.recent_trades(symbol)
            ),

            spread=spread,

            fair_value=fair,

            volatility=self.volatility(symbol)
        )


# =============================================================
# FREIGHT ENGINE
# =============================================================

class FreightEngine:

    """
    Converts mill-origin pricing into delivered spot pricing.
    """

    def delivered_price(
        self,
        mill_price,
        freight_per_mbf
    ):

        return (
            mill_price +
            freight_per_mbf
        )


    def reverse_origin_price(
        self,
        delivered_price,
        freight_per_mbf
    ):

        return (
            delivered_price -
            freight_per_mbf
        )


    def calculate_basis(
        self,
        origin_price,
        delivered_price
    ):

        return (
            delivered_price -
            origin_price
        )


# =============================================================
# PRODUCT NORMALIZATION
# =============================================================

class LumberNormalizer:

    """
    Converts physical descriptions into standardized
    RhinoQuant instruments.
    """

    STANDARD_LENGTHS = [
        6,
        8,
        10,
        12,
        14,
        16,
        20
    ]


    def normalize_dimension(
        self,
        thickness,
        width
    ):

        return (
            round(thickness, 3),
            round(width, 3)
        )


    def symbol(
        self,
        species,
        grade,
        thickness,
        width,
        length,
        region
    ):

        species_code = species.upper()

        grade_code = grade.upper()

        return (
            f"LMBR."
            f"{species_code}."
            f"{grade_code}."
            f"{thickness:g}X"
            f"{width:g}."
            f"{length:g}."
            f"{region.upper()}"
        )


# =============================================================
# PRICE ADJUSTMENT ENGINE
# =============================================================

class PriceAdjustmentEngine:

    """
    Adjusts comparable lumber transactions to a common
    specification.
    """

    def __init__(self):

        self.species_adjustments = {}

        self.grade_adjustments = {}

        self.length_adjustments = {}


    def set_species_basis(
        self,
        species,
        basis
    ):

        self.species_adjustments[
            species
        ] = basis


    def set_grade_basis(
        self,
        grade,
        basis
    ):

        self.grade_adjustments[
            grade
        ] = basis


    def set_length_basis(
        self,
        length,
        basis
    ):

        self.length_adjustments[
            length
        ] = basis


    def adjusted_price(
        self,
        base_price,
        species,
        grade,
        length
    ):

        return (
            base_price
            +
            self.species_adjustments.get(
                species,
                0.0
            )
            +
            self.grade_adjustments.get(
                grade,
                0.0
            )
            +
            self.length_adjustments.get(
                length,
                0.0
            )
        )


# =============================================================
# MARKET STATISTICS
# =============================================================

class MarketStatistics:

    def __init__(
        self,
        book
    ):

        self.book = book


    def moving_average(
        self,
        symbol,
        periods=20
    ):

        trades = list(
            self.book.trades.get(symbol, [])
        )

        if len(trades) < periods:
            return None

        prices = [
            t.price
            for t in trades[-periods:]
        ]

        return safe_mean(prices)


    def price_change(
        self,
        symbol,
        periods=20
    ):

        trades = list(
            self.book.trades.get(symbol, [])
        )

        if len(trades) < periods + 1:
            return None

        old = trades[-periods - 1].price

        new = trades[-1].price

        return pct_change(
            old,
            new
        )


    def trend(
        self,
        symbol,
        periods=20
    ):

        change = self.price_change(
            symbol,
            periods
        )

        if change is None:
            return "UNKNOWN"

        if change > 1.0:
            return "BULLISH"

        if change < -1.0:
            return "BEARISH"

        return "NEUTRAL"


# =============================================================
# INVENTORY
# =============================================================

@dataclass
class InventoryPosition:

    symbol: str

    quantity_mbf: float

    average_cost: float

    location: str


class InventoryEngine:

    def __init__(self):

        self.positions = {}

        self.lock = threading.RLock()


    def receive(
        self,
        symbol,
        quantity,
        cost,
        location
    ):

        with self.lock:

            key = (
                symbol,
                location
            )

            existing = \
                self.positions.get(key)

            if existing is None:

                self.positions[key] = \
                    InventoryPosition(
                        symbol,
                        quantity,
                        cost,
                        location
                    )

                return

            old_value = (
                existing.quantity_mbf *
                existing.average_cost
            )

            new_value = (
                quantity * cost
            )

            total_quantity = (
                existing.quantity_mbf +
                quantity
            )

            existing.average_cost = (
                (
                    old_value +
                    new_value
                )
                /
                total_quantity
            )

            existing.quantity_mbf = \
                total_quantity


    def remove(
        self,
        symbol,
        quantity,
        location
    ):

        with self.lock:

            key = (
                symbol,
                location
            )

            position = \
                self.positions.get(key)

            if position is None:
                raise ValueError(
                    "No inventory position"
                )

            if quantity > \
               position.quantity_mbf:

                raise ValueError(
                    "Insufficient inventory"
                )

            position.quantity_mbf -= quantity


    def get(
        self,
        symbol,
        location
    ):

        return self.positions.get(
            (
                symbol,
                location
            )
        )


# =============================================================
# PRICE ALERTS
# =============================================================

@dataclass
class PriceAlert:

    alert_id: str

    symbol: str

    condition: str

    threshold: float

    triggered: bool = False


class AlertEngine:

    def __init__(self):

        self.alerts = {}

        self.lock = threading.RLock()


    def create(
        self,
        symbol,
        condition,
        threshold
    ):

        alert = PriceAlert(

            alert_id=new_id("alert"),

            symbol=symbol,

            condition=condition,

            threshold=threshold
        )

        with self.lock:
            self.alerts[
                alert.alert_id
            ] = alert

        return alert


    def evaluate(
        self,
        symbol,
        price
    ):

        triggered = []

        with self.lock:

            for alert in self.alerts.values():

                if alert.symbol != symbol:
                    continue

                if alert.triggered:
                    continue

                condition = \
                    alert.condition.upper()

                if (
                    condition == "ABOVE"
                    and
                    price >= alert.threshold
                ):

                    alert.triggered = True

                    triggered.append(alert)

                elif (
                    condition == "BELOW"
                    and
                    price <= alert.threshold
                ):

                    alert.triggered = True

                    triggered.append(alert)

        return triggered


# =============================================================
# MARKET DATA SERVICE
# =============================================================

class MarketDataService:

    def __init__(self):

        self.db = Database()

        self.book = MarketBook()

        self.pricing = \
            SpotPricingEngine(
                self.book
            )

        self.freight = \
            FreightEngine()

        self.normalizer = \
            LumberNormalizer()

        self.adjustments = \
            PriceAdjustmentEngine()

        self.statistics = \
            MarketStatistics(
                self.book
            )

        self.inventory = \
            InventoryEngine()

        self.alerts = \
            AlertEngine()


    def add_quote(
        self,
        symbol,
        bid,
        ask,
        bid_size,
        ask_size,
        source,
        region,
        delivery_location=None,
        freight=0.0
    ):

        quote = Quote(

            quote_id=new_id("quote"),

            symbol=symbol,

            timestamp=utc_now(),

            bid=bid,

            ask=ask,

            bid_size=bid_size,

            ask_size=ask_size,

            source=source,

            region=region,

            delivery_location=delivery_location,

            freight_per_mbf=freight
        )

        self.book.add_quote(quote)

        self.db.insert_quote(quote)

        return quote


    def add_trade(
        self,
        symbol,
        price,
        quantity,
        buyer,
        seller,
        region,
        source,
        delivery_location=None,
        freight=0.0
    ):

        trade = LumberTrade(

            trade_id=new_id("trade"),

            symbol=symbol,

            timestamp=utc_now(),

            price=price,

            quantity_mbf=quantity,

            buyer=buyer,

            seller=seller,

            region=region,

            delivery_location=delivery_location,

            source=source,

            freight_per_mbf=freight
        )

        self.book.add_trade(trade)

        self.db.insert_trade(trade)

        self.alerts.evaluate(
            symbol,
            price
        )

        return trade


# =============================================================
# FASTAPI
# =============================================================

app = FastAPI(
    title="RhinoQuant Lumber Spot",
    version="1.0.0"
)

engine = MarketDataService()


# =============================================================
# API MODELS
# =============================================================

class QuoteRequest(BaseModel):

    symbol: str

    bid: Optional[float] = None

    ask: Optional[float] = None

    bid_size: float = 0.0

    ask_size: float = 0.0

    source: str

    region: str

    delivery_location: Optional[str] = None

    freight_per_mbf: float = 0.0


class TradeRequest(BaseModel):

    symbol: str

    price: float = Field(gt=0)

    quantity_mbf: float = Field(gt=0)

    buyer: Optional[str] = None

    seller: Optional[str] = None

    region: str

    source: str

    delivery_location: Optional[str] = None

    freight_per_mbf: float = 0.0


class InventoryRequest(BaseModel):

    symbol: str

    quantity_mbf: float = Field(gt=0)

    cost: float = Field(gt=0)

    location: str


class AlertRequest(BaseModel):

    symbol: str

    condition: str

    threshold: float


# =============================================================
# API ROUTES
# =============================================================

@app.get("/")
def root():

    return {
        "system": "RhinoQuant Lumber Spot",
        "status": "online",
        "version": "1.0.0"
    }


@app.post("/market/quote")
def submit_quote(
    request: QuoteRequest
):

    quote = engine.add_quote(

        symbol=request.symbol,

        bid=request.bid,

        ask=request.ask,

        bid_size=request.bid_size,

        ask_size=request.ask_size,

        source=request.source,

        region=request.region,

        delivery_location=
            request.delivery_location,

        freight=
            request.freight_per_mbf
    )

    return asdict(quote)


@app.post("/market/trade")
def submit_trade(
    request: TradeRequest
):

    trade = engine.add_trade(

        symbol=request.symbol,

        price=request.price,

        quantity=request.quantity_mbf,

        buyer=request.buyer,

        seller=request.seller,

        region=request.region,

        source=request.source,

        delivery_location=
            request.delivery_location,

        freight=
            request.freight_per_mbf
    )

    return asdict(trade)


@app.get("/market/{symbol}")
def market_snapshot(
    symbol: str
):

    snapshot = \
        engine.pricing.snapshot(
            symbol
        )

    return asdict(snapshot)


@app.get("/market/{symbol}/trades")
def recent_trades(
    symbol: str,
    hours: int = 24
):

    trades = \
        engine.book.recent_trades(
            symbol,
            hours
        )

    return [
        asdict(t)
        for t in trades
    ]


@app.get("/market/{symbol}/analytics")
def analytics(
    symbol: str
):

    snapshot = \
        engine.pricing.snapshot(
            symbol
        )

    return {

        "symbol": symbol,

        "snapshot": asdict(
            snapshot
        ),

        "moving_average_20":
            engine.statistics.moving_average(
                symbol,
                20
            ),

        "moving_average_50":
            engine.statistics.moving_average(
                symbol,
                50
            ),

        "price_change_20":
            engine.statistics.price_change(
                symbol,
                20
            ),

        "trend":
            engine.statistics.trend(
                symbol,
                20
            )
    }


@app.post("/inventory/receive")
def receive_inventory(
    request: InventoryRequest
):

    engine.inventory.receive(

        request.symbol,

        request.quantity_mbf,

        request.cost,

        request.location
    )

    return {
        "status": "received",
        "symbol": request.symbol
    }


@app.get("/inventory/{symbol}")
def inventory(
    symbol: str,
    location: str
):

    position = \
        engine.inventory.get(
            symbol,
            location
        )

    if position is None:

        raise HTTPException(
            status_code=404,
            detail="Inventory not found"
        )

    return asdict(position)


@app.post("/alerts")
def create_alert(
    request: AlertRequest
):

    alert = engine.alerts.create(

        request.symbol,

        request.condition,

        request.threshold
    )

    return asdict(alert)


# =============================================================
# SAMPLE MARKET DATA
# =============================================================

def load_demo_market():

    symbol = (
        "LMBR."
        "SPF."
        "STRUCTURAL."
        "2X4."
        "16."
        "PNW"
    )

    # Example indicative quote
    engine.add_quote(

        symbol=symbol,

        bid=385.0,

        ask=395.0,

        bid_size=120.0,

        ask_size=180.0,

        source="DEMO_MILL_A",

        region="PNW"
    )

    # Example physical transactions

    demo_trades = [

        (388.0, 20.0),

        (391.0, 35.0),

        (389.5, 40.0),

        (394.0, 25.0),

        (392.5, 50.0),

        (396.0, 30.0),

        (393.0, 45.0),

    ]

    for price, quantity in demo_trades:

        engine.add_trade(

            symbol=symbol,

            price=price,

            quantity=quantity,

            buyer="DEMO_BUYER",

            seller="DEMO_MILL",

            region="PNW",

            source="DEMO"
        )


# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":

    load_demo_market()

    print()
    print("=" * 65)
    print(" RHINOQUANT LUMBER SPOT")
    print("=" * 65)
    print()
    print("Market-data engine running")
    print()
    print("API:")
    print("http://127.0.0.1:8000")
    print()
    print("Swagger:")
    print("http://127.0.0.1:8000/docs")
    print()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
