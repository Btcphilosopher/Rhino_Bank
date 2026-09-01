"""
=============================================================
RHINO COCAINE INTELLIGENCE
RCI 1.0
=============================================================

Research / intelligence analytics platform.

Purpose:
    Analyse publicly reported indicators relating to the
    illicit cocaine market.

DATA TYPES
----------
    Price
    Purity
    Seizures
    Prevalence
    Treatment
    Market-risk indicators

IMPORTANT
---------
This is an intelligence/analytics system.

It does NOT:
    - facilitate drug purchases
    - match buyers and sellers
    - execute transactions
    - optimise trafficking
    - identify operational trafficking routes
    - provide procurement functionality

Example observations below are synthetic.
Production data should be loaded from authoritative
public datasets such as UNODC.

=============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from statistics import mean
from typing import Dict, List, Optional
from uuid import uuid4


# ============================================================
# UTILITIES
# ============================================================

def D(value) -> Decimal:
    return Decimal(str(value))


def dec(value, places=2) -> Decimal:
    quantum = Decimal("1." + ("0" * places))
    return D(value).quantize(
        quantum,
        rounding=ROUND_HALF_UP
    )


def utc_now():
    return datetime.now(timezone.utc)


# ============================================================
# ENUMERATIONS
# ============================================================

class IndicatorType(Enum):

    PRICE = "PRICE"
    PURITY = "PURITY"
    SEIZURE = "SEIZURE"
    PREVALENCE = "PREVALENCE"
    TREATMENT = "TREATMENT"


class MarketLevel(Enum):

    RETAIL = "RETAIL"
    WHOLESALE = "WHOLESALE"
    REGIONAL = "REGIONAL"


class RiskLevel(Enum):

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


# ============================================================
# DATA OBSERVATION
# ============================================================

@dataclass
class Observation:

    observation_id: str

    country: str

    region: str

    year: int

    indicator: IndicatorType

    value: Decimal

    unit: str

    market_level: Optional[MarketLevel] = None

    source: str = "SYNTHETIC"

    source_reference: Optional[str] = None

    recorded_at: datetime = field(
        default_factory=utc_now
    )


# ============================================================
# DATA STORE
# ============================================================

class RCIDataStore:

    def __init__(self):

        self.observations: List[
            Observation
        ] = []

    def add(
        self,
        country: str,
        region: str,
        year: int,
        indicator: IndicatorType,
        value,
        unit: str,
        market_level=None,
        source="SYNTHETIC",
        source_reference=None
    ):

        observation = Observation(

            observation_id=str(
                uuid4()
            ),

            country=country,

            region=region,

            year=year,

            indicator=indicator,

            value=D(value),

            unit=unit,

            market_level=market_level,

            source=source,

            source_reference=source_reference
        )

        self.observations.append(
            observation
        )

        return observation

    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    def query(
        self,
        country=None,
        region=None,
        year=None,
        indicator=None,
        market_level=None
    ):

        result = self.observations

        if country:

            result = [
                x for x in result
                if x.country == country
            ]

        if region:

            result = [
                x for x in result
                if x.region == region
            ]

        if year:

            result = [
                x for x in result
                if x.year == year
            ]

        if indicator:

            result = [
                x for x in result
                if x.indicator == indicator
            ]

        if market_level:

            result = [
                x for x in result
                if x.market_level == market_level
            ]

        return result


# ============================================================
# TIME SERIES ENGINE
# ============================================================

class TimeSeriesEngine:

    def __init__(self, store):

        self.store = store

    def series(
        self,
        country,
        indicator,
        market_level=None
    ):

        observations = self.store.query(

            country=country,

            indicator=indicator,

            market_level=market_level
        )

        observations.sort(
            key=lambda x: x.year
        )

        return [

            (x.year, x.value)

            for x in observations
        ]

    # --------------------------------------------------------
    # YEAR-ON-YEAR CHANGE
    # --------------------------------------------------------

    def yoy_change(
        self,
        country,
        indicator,
        market_level=None
    ):

        series = self.series(
            country,
            indicator,
            market_level
        )

        if len(series) < 2:

            return None

        previous = series[-2][1]

        current = series[-1][1]

        if previous == 0:

            return None

        return dec(
            ((current - previous) / previous)
            * D("100")
        )

    # --------------------------------------------------------
    # CAGR
    # --------------------------------------------------------

    def cagr(
        self,
        country,
        indicator,
        market_level=None
    ):

        series = self.series(
            country,
            indicator,
            market_level
        )

        if len(series) < 2:

            return None

        first_year, first = series[0]

        last_year, last = series[-1]

        years = last_year - first_year

        if years <= 0 or first <= 0:

            return None

        result = (

            (last / first)
            ** (D("1") / D(years))
            - D("1")
        ) * D("100")

        return dec(result)


# ============================================================
# VOLATILITY ENGINE
# ============================================================

class VolatilityEngine:

    @staticmethod
    def percentage_changes(values):

        changes = []

        for i in range(1, len(values)):

            previous = D(values[i - 1])

            current = D(values[i])

            if previous == 0:

                continue

            changes.append(

                ((current - previous) / previous)
                * D("100")
            )

        return changes

    @classmethod
    def volatility(cls, values):

        changes = cls.percentage_changes(
            values
        )

        if len(changes) < 2:

            return D("0")

        avg = mean(
            float(x)
            for x in changes
        )

        variance = mean(

            (
                float(x) - avg
            ) ** 2

            for x in changes
        )

        return dec(
            variance ** 0.5
        )


# ============================================================
# MARKET INDICATOR ENGINE
# ============================================================

class IndicatorEngine:

    def __init__(self, store):

        self.store = store

    def latest(
        self,
        country,
        indicator,
        market_level=None
    ):

        observations = self.store.query(

            country=country,

            indicator=indicator,

            market_level=market_level
        )

        if not observations:

            return None

        return max(
            observations,
            key=lambda x: x.year
        )

    def average(
        self,
        region,
        indicator,
        year=None
    ):

        observations = self.store.query(

            region=region,

            indicator=indicator,

            year=year
        )

        if not observations:

            return None

        return dec(
            mean(
                float(x.value)
                for x in observations
            )
        )


# ============================================================
# RISK MODEL
# ============================================================

class RiskEngine:

    """
    High-level analytical risk score.

    This is NOT an operational trafficking model.

    It combines:
        price movement
        purity movement
        seizure movement
        prevalence movement

    into a broad research indicator.
    """

    def calculate(
        self,
        price_change,
        purity_change,
        seizure_change,
        prevalence_change
    ):

        score = D("50")

        # Price volatility / movement

        if price_change > D("10"):

            score += D("10")

        elif price_change < D("-10"):

            score += D("5")

        # Purity

        if purity_change > D("10"):

            score += D("10")

        elif purity_change < D("-10"):

            score -= D("5")

        # Seizures

        if seizure_change > D("15"):

            score += D("10")

        elif seizure_change < D("-15"):

            score -= D("5")

        # Prevalence

        if prevalence_change > D("10"):

            score += D("10")

        elif prevalence_change < D("-10"):

            score -= D("5")

        score = max(
            D("0"),
            min(D("100"), score)
        )

        return dec(score)

    @staticmethod
    def level(score):

        if score >= D("80"):

            return RiskLevel.VERY_HIGH

        if score >= D("60"):

            return RiskLevel.HIGH

        if score >= D("40"):

            return RiskLevel.MODERATE

        return RiskLevel.LOW


# ============================================================
# REGIONAL ANALYTICS
# ============================================================

class RegionalAnalytics:

    def __init__(self, store):

        self.store = store

    def country_rankings(
        self,
        region,
        indicator,
        year
    ):

        observations = self.store.query(

            region=region,

            indicator=indicator,

            year=year
        )

        observations.sort(

            key=lambda x: x.value,

            reverse=True
        )

        return [

            {
                "country":
                    x.country,

                "value":
                    x.value,

                "unit":
                    x.unit
            }

            for x in observations
        ]

    def regional_average(
        self,
        region,
        indicator,
        year
    ):

        values = [

            x.value

            for x in self.store.query(

                region=region,

                indicator=indicator,

                year=year
            )
        ]

        if not values:

            return None

        return dec(
            mean(
                float(x)
                for x in values
            )
        )


# ============================================================
# RCI TERMINAL
# ============================================================

class RCITerminal:

    def __init__(self):

        self.store = RCIDataStore()

        self.timeseries = (
            TimeSeriesEngine(
                self.store
            )
        )

        self.indicators = (
            IndicatorEngine(
                self.store
            )
        )

        self.regions = (
            RegionalAnalytics(
                self.store
            )
        )

        self.risk = RiskEngine()

    # --------------------------------------------------------
    # INGEST
    # --------------------------------------------------------

    def ingest(self, **kwargs):

        return self.store.add(
            **kwargs
        )

    # --------------------------------------------------------
    # COUNTRY DASHBOARD
    # --------------------------------------------------------

    def country_dashboard(
        self,
        country
    ):

        price = self.indicators.latest(

            country,

            IndicatorType.PRICE,

            MarketLevel.RETAIL
        )

        purity = self.indicators.latest(

            country,

            IndicatorType.PURITY
        )

        seizures = self.indicators.latest(

            country,

            IndicatorType.SEIZURE
        )

        prevalence = self.indicators.latest(

            country,

            IndicatorType.PREVALENCE
        )

        price_change = (

            self.timeseries.yoy_change(

                country,

                IndicatorType.PRICE,

                MarketLevel.RETAIL
            )

            or D("0")
        )

        purity_change = (

            self.timeseries.yoy_change(

                country,

                IndicatorType.PURITY
            )

            or D("0")
        )

        seizure_change = (

            self.timeseries.yoy_change(

                country,

                IndicatorType.SEIZURE
            )

            or D("0")
        )

        prevalence_change = (

            self.timeseries.yoy_change(

                country,

                IndicatorType.PREVALENCE
            )

            or D("0")
        )

        score = self.risk.calculate(

            price_change,

            purity_change,

            seizure_change,

            prevalence_change
        )

        return {

            "country":
                country,

            "price":
                str(
                    price.value
                    if price
                    else "N/A"
                ),

            "price_change_yoy":
                str(price_change),

            "purity":
                str(
                    purity.value
                    if purity
                    else "N/A"
                ),

            "purity_change_yoy":
                str(purity_change),

            "reported_seizures":
                str(
                    seizures.value
                    if seizures
                    else "N/A"
                ),

            "seizure_change_yoy":
                str(seizure_change),

            "prevalence":
                str(
                    prevalence.value
                    if prevalence
                    else "N/A"
                ),

            "prevalence_change_yoy":
                str(prevalence_change),

            "risk_score":
                str(score),

            "risk_level":
                self.risk.level(
                    score
                ).value,

            "generated_at":
                utc_now().isoformat()
        }


# ============================================================
# SYNTHETIC DEMONSTRATION DATA
# ============================================================

def load_demo_data(
    terminal: RCITerminal
):

    countries = {

        "United Kingdom":
            "Western Europe",

        "France":
            "Western Europe",

        "Spain":
            "Western Europe",

        "Netherlands":
            "Western Europe",

        "United States":
            "North America"
    }

    years = [
        2022,
        2023,
        2024,
        2025
    ]

    for country, region in countries.items():

        for i, year in enumerate(years):

            # --------------------------------------------
            # SYNTHETIC PRICE SERIES
            # --------------------------------------------

            base_price = {

                "United Kingdom": 100,
                "France": 95,
                "Spain": 85,
                "Netherlands": 92,
                "United States": 110
            }[country]

            price = (
                base_price
                * (1 + (i * 0.035))
            )

            terminal.ingest(

                country=country,

                region=region,

                year=year,

                indicator=IndicatorType.PRICE,

                value=price,

                unit="INDEX",

                market_level=MarketLevel.RETAIL
            )

            # --------------------------------------------
            # SYNTHETIC PURITY
            # --------------------------------------------

            purity = {

                "United Kingdom": 55,
                "France": 58,
                "Spain": 62,
                "Netherlands": 60,
                "United States": 68
            }[country]

            purity *= (
                1 + (i * 0.02)
            )

            terminal.ingest(

                country=country,

                region=region,

                year=year,

                indicator=IndicatorType.PURITY,

                value=purity,

                unit="PERCENT"
            )

            # --------------------------------------------
            # SYNTHETIC SEIZURES
            # --------------------------------------------

            seizure = {

                "United Kingdom": 1200,
                "France": 1800,
                "Spain": 4500,
                "Netherlands": 3800,
                "United States": 6200
            }[country]

            seizure *= (
                1 + (i * 0.08)
            )

            terminal.ingest(

                country=country,

                region=region,

                year=year,

                indicator=IndicatorType.SEIZURE,

                value=seizure,

                unit="KG_EQUIVALENT"
            )

            # --------------------------------------------
            # SYNTHETIC PREVALENCE
            # --------------------------------------------

            prevalence = {

                "United Kingdom": 2.1,
                "France": 1.9,
                "Spain": 3.0,
                "Netherlands": 2.4,
                "United States": 2.7
            }[country]

            prevalence *= (
                1 + (i * 0.015)
            )

            terminal.ingest(

                country=country,

                region=region,

                year=year,

                indicator=IndicatorType.PREVALENCE,

                value=prevalence,

                unit="PERCENT"
            )


# ============================================================
# REPORT GENERATOR
# ============================================================

class RCIReport:

    def __init__(
        self,
        terminal: RCITerminal
    ):

        self.terminal = terminal

    def country_report(
        self,
        country
    ):

        dashboard = (
            self.terminal.country_dashboard(
                country
            )
        )

        print()
        print("=" * 60)
        print("RHINO COCAINE INTELLIGENCE")
        print("=" * 60)

        for key, value in dashboard.items():

            print(
                f"{key:25} {value}"
            )

        print("=" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    rci = RCITerminal()

    load_demo_data(
        rci
    )

    report = RCIReport(
        rci
    )

    report.country_report(
        "United Kingdom"
    )

    print()

    print(
        "WESTERN EUROPE — 2025"
    )

    print(
        "====================="
    )

    rankings = (
        rci.regions.country_rankings(

            "Western Europe",

            IndicatorType.SEIZURE,

            2025
        )
    )

    for row in rankings:

        print(
            f"{row['country']:20}"
            f"{row['value']:>12}"
            f" {row['unit']}"
        )
