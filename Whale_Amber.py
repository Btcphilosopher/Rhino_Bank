"""
RHINOBANK // WHALE AMBER
Institutional physical-amber spot pricing engine.

This is a pricing/valuation prototype.

It does NOT claim to represent an official amber benchmark.
Production pricing requires authenticated market data,
independent appraisal, provenance controls and appropriate
benchmark governance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from enum import Enum
from statistics import median
from typing import List
import hashlib
import math


getcontext().prec = 40

D = Decimal


# ============================================================
# ENUMS
# ============================================================

class Origin(str, Enum):

    BALTIC = "BALTIC"

    DOMINICAN = "DOMINICAN"

    MEXICAN = "MEXICAN"

    BURMITE = "BURMITE"

    INDONESIAN = "INDONESIAN"

    OTHER = "OTHER"


class Colour(str, Enum):

    YELLOW = "YELLOW"

    GOLD = "GOLD"

    COGNAC = "COGNAC"

    RED = "RED"

    WHITE = "WHITE"

    BLUE = "BLUE"

    GREEN = "GREEN"

    BLACK = "BLACK"


class Treatment(str, Enum):

    NATURAL = "NATURAL"

    HEAT_TREATED = "HEAT_TREATED"

    PRESSED = "PRESSED"

    RECONSTRUCTED = "RECONSTRUCTED"

    UNKNOWN = "UNKNOWN"


class Liquidity(str, Enum):

    HIGH = "HIGH"

    MEDIUM = "MEDIUM"

    LOW = "LOW"

    VERY_LOW = "VERY_LOW"


# ============================================================
# AMBER LOT
# ============================================================

@dataclass
class AmberLot:

    lot_id: str

    origin: Origin

    colour: Colour

    treatment: Treatment

    weight_grams: D

    clarity: D

    transparency: D

    inclusion_score: D

    provenance_score: D

    condition_score: D

    certification_score: D

    liquidity: Liquidity

    timestamp: datetime

    currency: str = "USD"


# ============================================================
# MARKET OBSERVATION
# ============================================================

@dataclass
class MarketObservation:

    source: str

    lot: AmberLot

    price_total: D

    timestamp: datetime

    transaction: bool

    verified: bool

    volume_grams: D

    source_reliability: D = D("1.0")

    @property
    def price_per_gram(self) -> D:

        return (
            self.price_total /
            self.lot.weight_grams
        )


# ============================================================
# MARKET QUALITY
# ============================================================

@dataclass
class PricePoint:

    price: D

    weight: D

    reliability: D


# ============================================================
# WHALE PRICE ENGINE
# ============================================================

class WhaleAmberPricingEngine:

    """
    Institutional reference-price calculator.

    The engine combines:

        observed transaction prices
        verified offers
        quality adjustments
        provenance
        rarity
        liquidity
        robust median statistics
        outlier rejection
    """

    def __init__(self):

        self.observations: List[
            MarketObservation
        ] = []


    def add_observation(
        self,
        observation: MarketObservation
    ):

        if observation.lot.weight_grams <= 0:
            raise ValueError(
                "Invalid amber weight"
            )

        if observation.price_total <= 0:
            raise ValueError(
                "Invalid amber price"
            )

        self.observations.append(
            observation
        )


    # --------------------------------------------------------
    # QUALITY SCORE
    # --------------------------------------------------------

    def quality_multiplier(
        self,
        lot: AmberLot
    ) -> D:

        score = (

            lot.clarity
            * D("0.18")

            +

            lot.transparency
            * D("0.14")

            +

            lot.inclusion_score
            * D("0.24")

            +

            lot.provenance_score
            * D("0.18")

            +

            lot.condition_score
            * D("0.10")

            +

            lot.certification_score
            * D("0.16")

        )

        # Score expected approximately 0-100.
        #
        # Convert to a controlled multiplier.

        multiplier = (

            D("0.70")
            +
            score / D("100")

        )

        return multiplier


    # --------------------------------------------------------
    # ORIGIN MULTIPLIER
    # --------------------------------------------------------

    def origin_multiplier(
        self,
        origin: Origin
    ) -> D:

        return {

            Origin.BALTIC:
                D("1.00"),

            Origin.DOMINICAN:
                D("1.15"),

            Origin.MEXICAN:
                D("1.05"),

            Origin.BURMITE:
                D("1.30"),

            Origin.INDONESIAN:
                D("0.90"),

            Origin.OTHER:
                D("0.80"),

        }[origin]


    # --------------------------------------------------------
    # COLOUR
    # --------------------------------------------------------

    def colour_multiplier(
        self,
        colour: Colour
    ) -> D:

        return {

            Colour.YELLOW:
                D("0.90"),

            Colour.GOLD:
                D("1.00"),

            Colour.COGNAC:
                D("1.08"),

            Colour.RED:
                D("1.20"),

            Colour.WHITE:
                D("1.10"),

            Colour.BLUE:
                D("1.60"),

            Colour.GREEN:
                D("1.35"),

            Colour.BLACK:
                D("0.95"),

        }[colour]


    # --------------------------------------------------------
    # TREATMENT
    # --------------------------------------------------------

    def treatment_multiplier(
        self,
        treatment: Treatment
    ) -> D:

        return {

            Treatment.NATURAL:
                D("1.00"),

            Treatment.HEAT_TREATED:
                D("0.82"),

            Treatment.PRESSED:
                D("0.55"),

            Treatment.RECONSTRUCTED:
                D("0.30"),

            Treatment.UNKNOWN:
                D("0.60"),

        }[treatment]


    # --------------------------------------------------------
    # LARGE-LOT / WHALE PREMIUM
    # --------------------------------------------------------

    def whale_multiplier(
        self,
        grams: D
    ) -> D:

        """
        Large exceptional pieces are not assumed to have
        linear value.

        This function creates a configurable size premium.
        """

        if grams < D("100"):
            return D("1.00")

        if grams < D("250"):
            return D("1.05")

        if grams < D("500"):
            return D("1.12")

        if grams < D("1000"):
            return D("1.20")

        if grams < D("2500"):
            return D("1.35")

        if grams < D("5000"):
            return D("1.55")

        return D("1.80")


    # --------------------------------------------------------
    # LIQUIDITY
    # --------------------------------------------------------

    def liquidity_discount(
        self,
        liquidity: Liquidity
    ) -> D:

        return {

            Liquidity.HIGH:
                D("1.00"),

            Liquidity.MEDIUM:
                D("0.98"),

            Liquidity.LOW:
                D("0.94"),

            Liquidity.VERY_LOW:
                D("0.88"),

        }[liquidity]


    # --------------------------------------------------------
    # FAIR VALUE
    # --------------------------------------------------------

    def adjusted_value(
        self,
        lot: AmberLot,
        observed_price_per_gram: D
    ) -> D:

        multiplier = (

            self.quality_multiplier(lot)

            *

            self.origin_multiplier(
                lot.origin
            )

            *

            self.colour_multiplier(
                lot.colour
            )

            *

            self.treatment_multiplier(
                lot.treatment
            )

            *

            self.whale_multiplier(
                lot.weight_grams
            )

            *

            self.liquidity_discount(
                lot.liquidity
            )

        )

        return (
            observed_price_per_gram
            * multiplier
        )


    # --------------------------------------------------------
    # OUTLIER FILTER
    # --------------------------------------------------------

    def reject_outliers(
        self,
        prices: List[D]
    ) -> List[D]:

        if len(prices) < 4:
            return prices

        sorted_prices = sorted(prices)

        med = D(
            str(
                median(
                    sorted_prices
                )
            )
        )

        deviations = [

            abs(p - med) / med

            for p in sorted_prices

        ]

        median_deviation = D(
            str(
                median(deviations)
            )
        )

        if median_deviation == 0:
            return sorted_prices

        threshold = (
            median_deviation
            * D("6")
        )

        return [

            p for p, deviation
            in zip(
                sorted_prices,
                deviations
            )

            if deviation <= threshold

        ]


    # --------------------------------------------------------
    # REFERENCE PRICE
    # --------------------------------------------------------

    def calculate_reference_price(
        self
    ) -> D:

        if not self.observations:

            raise RuntimeError(
                "No amber market observations"
            )

        points = []

        for observation in self.observations:

            base =
                observation.price_per_gram

            adjusted =
                self.adjusted_value(
                    observation.lot,
                    base
                )

            weight = (

                observation.volume_grams
                *

                observation.source_reliability

                *

                (
                    D("1.25")
                    if observation.verified
                    else D("0.70")
                )

                *

                (
                    D("1.20")
                    if observation.transaction
                    else D("0.75")
                )

            )

            points.append(
                PricePoint(
                    price=adjusted,
                    weight=weight,
                    reliability=
                        observation.source_reliability
                )
            )


        raw_prices = [
            p.price
            for p in points
        ]

        accepted =
            self.reject_outliers(
                raw_prices
            )


        filtered = [

            p for p in points

            if p.price in accepted

        ]


        numerator = sum(

            p.price * p.weight

            for p in filtered

        )

        denominator = sum(

            p.weight

            for p in filtered

        )

        if denominator == 0:

            raise RuntimeError(
                "Insufficient price weight"
            )

        return (
            numerator /
            denominator
        )


# ============================================================
# SPOT QUOTE
# ============================================================

@dataclass
class WhaleSpotQuote:

    symbol: str

    reference_price: D

    bid: D

    ask: D

    spread: D

    timestamp: datetime

    confidence: D

    quote_id: str


# ============================================================
# SPOT MARKET
# ============================================================

class WhaleAmberSpotMarket:

    def __init__(
        self,
        engine: WhaleAmberPricingEngine
    ):

        self.engine = engine


    def quote(
        self,
        spread_bps: D = D("75")
    ) -> WhaleSpotQuote:

        reference =
            self.engine.calculate_reference_price()


        spread_fraction = (
            spread_bps /
            D("10000")
        )


        bid = (
            reference
            *
            (
                D("1")
                -
                spread_fraction / D("2")
            )
        )


        ask = (
            reference
            *
            (
                D("1")
                +
                spread_fraction / D("2")
            )
        )


        confidence =
            self.calculate_confidence()


        raw_id = (
            f"WHAL-AMBER:"
            f"{reference}:"
            f"{datetime.utcnow().isoformat()}"
        )


        quote_id = hashlib.sha256(
            raw_id.encode()
        ).hexdigest()[:24]


        return WhaleSpotQuote(

            symbol="WHAL/USD",

            reference_price=
                reference,

            bid=bid,

            ask=ask,

            spread=
                ask - bid,

            timestamp=
                datetime.utcnow(),

            confidence=
                confidence,

            quote_id=
                quote_id

        )


    def calculate_confidence(
        self
    ) -> D:

        n =
            len(
                self.engine.observations
            )

        if n == 0:
            return D("0")

        confidence =
            D(str(
                min(
                    1.0,
                    math.log10(
                        n + 1
                    ) / 2
                )
            ))

        return confidence


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":

    engine =
        WhaleAmberPricingEngine()


    # --------------------------------------------------------
    # Example institutional lots
    # --------------------------------------------------------

    lot_a = AmberLot(

        lot_id="AMB-BAL-0001",

        origin=Origin.BALTIC,

        colour=Colour.COGNAC,

        treatment=Treatment.NATURAL,

        weight_grams=D("750"),

        clarity=D("82"),

        transparency=D("78"),

        inclusion_score=D("70"),

        provenance_score=D("91"),

        condition_score=D("95"),

        certification_score=D("94"),

        liquidity=Liquidity.MEDIUM,

        timestamp=datetime.utcnow()

    )


    lot_b = AmberLot(

        lot_id="AMB-DOM-0007",

        origin=Origin.DOMINICAN,

        colour=Colour.BLUE,

        treatment=Treatment.NATURAL,

        weight_grams=D("1100"),

        clarity=D("94"),

        transparency=D("92"),

        inclusion_score=D("86"),

        provenance_score=D("97"),

        condition_score=D("96"),

        certification_score=D("98"),

        liquidity=Liquidity.LOW,

        timestamp=datetime.utcnow()

    )


    # --------------------------------------------------------
    # Market observations
    # --------------------------------------------------------

    engine.add_observation(

        MarketObservation(

            source="RHINO-DEALER-01",

            lot=lot_a,

            price_total=D("48000"),

            timestamp=datetime.utcnow(),

            transaction=True,

            verified=True,

            volume_grams=D("750"),

            source_reliability=D("0.98")

        )

    )


    engine.add_observation(

        MarketObservation(

            source="RHINO-AUCTION-03",

            lot=lot_b,

            price_total=D("165000"),

            timestamp=datetime.utcnow(),

            transaction=True,

            verified=True,

            volume_grams=D("1100"),

            source_reliability=D("0.96")

        )

    )


    engine.add_observation(

        MarketObservation(

            source="RHINO-DEALER-04",

            lot=lot_a,

            price_total=D("51000"),

            timestamp=datetime.utcnow(),

            transaction=False,

            verified=True,

            volume_grams=D("750"),

            source_reliability=D("0.90")

        )

    )


    # --------------------------------------------------------
    # Generate quote
    # --------------------------------------------------------

    market =
        WhaleAmberSpotMarket(
            engine
        )


    quote =
        market.quote(
            spread_bps=D("85")
        )


    print()
    print("======================================")
    print(" RHINOBANK // WHALE AMBER SPOT")
    print("======================================")
    print()
    print(
        "REFERENCE :",
        quote.reference_price
    )
    print(
        "BID       :",
        quote.bid
    )
    print(
        "ASK       :",
        quote.ask
    )
    print(
        "SPREAD    :",
        quote.spread
    )
    print(
        "CONFIDENCE:",
        quote.confidence
    )
    print(
        "QUOTE ID  :",
        quote.quote_id
    )
