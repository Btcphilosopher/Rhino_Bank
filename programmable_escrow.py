# RHINOBANK PROGRAMMABLE ESCROW ENGINE

```python
"""
RHINOBANK PROGRAMMABLE ESCROW / TRADE SETTLEMENT ENGINE

Design goals
------------
- Deterministic trade lifecycle
- Exact delivery deadlines
- Programmable settlement schedules
- Event-driven state transitions
- Atomic fund release
- Partial delivery support
- Automatic expiry
- Grace periods
- Settlement conditions
- Full audit trail
- Idempotent events
- No floating-point monetary arithmetic

IMPORTANT
---------
This is a financial-system engineering prototype.

Production deployment should add:
    - HSM/MPC custody
    - database transactions
    - durable event store
    - independent authorization service
    - sanctions/compliance controls
    - operational kill switch
    - reconciliation
    - formal security review
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading

from dataclasses import (
    dataclass,
    field,
)
from decimal import (
    Decimal,
    ROUND_DOWN,
)
from enum import Enum
from datetime import (
    datetime,
    timezone,
    timedelta,
)
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Set,
)


# ============================================================
# MONEY
# ============================================================

CENT = Decimal("0.01")


def money(value) -> Decimal:

    return Decimal(
        str(value)
    ).quantize(
        CENT
    )


# ============================================================
# TRADE STATES
# ============================================================

class TradeStage(str, Enum):

    CREATED = "CREATED"

    FUNDS_RESERVED = "FUNDS_RESERVED"

    ORDER_SUBMITTED = "ORDER_SUBMITTED"

    EXECUTED = "EXECUTED"

    DELIVERY_PENDING = "DELIVERY_PENDING"

    DELIVERY_PARTIAL = "DELIVERY_PARTIAL"

    DELIVERY_COMPLETE = "DELIVERY_COMPLETE"

    INSPECTION_PENDING = "INSPECTION_PENDING"

    INSPECTION_COMPLETE = "INSPECTION_COMPLETE"

    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"

    RELEASE_AUTHORIZED = "RELEASE_AUTHORIZED"

    SETTLED = "SETTLED"

    CANCELLED = "CANCELLED"

    EXPIRED = "EXPIRED"

    DISPUTED = "DISPUTED"


# ============================================================
# ESCROW EVENT
# ============================================================

@dataclass(frozen=True)
class EscrowEvent:

    event_id: str

    trade_id: str

    event_type: str

    timestamp: datetime

    payload: dict

    sequence: int

    previous_hash: str

    event_hash: str = ""


# ============================================================
# DELIVERY SCHEDULE
# ============================================================

@dataclass
class DeliverySchedule:

    """
    Programmable delivery timing.

    All times are absolute UTC datetimes.

    Example:

        execution_time + 2 hours

        deadline = execution_time + 48 hours

    """

    delivery_window_start: Optional[datetime] = None

    delivery_deadline: Optional[datetime] = None

    grace_period_seconds: int = 0

    require_full_delivery: bool = True

    allow_partial_delivery: bool = False


# ============================================================
# RELEASE POLICY
# ============================================================

@dataclass
class ReleasePolicy:

    """
    Defines precisely when escrow may release funds.
    """

    release_on_execution: bool = False

    release_on_delivery: bool = True

    release_on_inspection: bool = False

    release_after_confirmation_seconds: int = 0

    require_buyer_confirmation: bool = False

    require_seller_confirmation: bool = False

    require_risk_clearance: bool = True

    require_compliance_clearance: bool = True


# ============================================================
# TRADE
# ============================================================

@dataclass
class Trade:

    trade_id: str

    buyer_account: str

    seller_account: str

    asset: str

    currency: str

    quantity: Decimal

    unit_price: Decimal

    escrow_amount: Decimal

    created_at: datetime

    delivery: DeliverySchedule

    release_policy: ReleasePolicy

    stage: TradeStage = (
        TradeStage.CREATED
    )

    delivered_quantity: Decimal = (
        Decimal("0")
    )

    buyer_confirmed: bool = False

    seller_confirmed: bool = False

    risk_cleared: bool = False

    compliance_cleared: bool = False

    release_authorized: bool = False

    released_amount: Decimal = (
        Decimal("0")
    )

    metadata: dict = field(
        default_factory=dict
    )

    version: int = 0


# ============================================================
# ESCROW ACCOUNT
# ============================================================

@dataclass
class EscrowAccount:

    escrow_id: str

    trade_id: str

    currency: str

    balance: Decimal

    locked_at: datetime

    released: Decimal = (
        Decimal("0")
    )


# ============================================================
# ESCROW ENGINE
# ============================================================

class EscrowEngine:

    def __init__(self):

        self.trades: Dict[
            str,
            Trade
        ] = {}

        self.escrows: Dict[
            str,
            EscrowAccount
        ] = {}

        self.events: Dict[
            str,
            List[EscrowEvent]
        ] = {}

        self.processed_events: Set[
            str
        ] = set()

        self.lock = (
            threading.RLock()
        )

        self.listeners: List[
            Callable
        ] = []

    # ========================================================
    # EVENT SYSTEM
    # ========================================================

    def add_listener(
        self,
        listener: Callable,
    ):

        self.listeners.append(
            listener
        )

    def _emit(
        self,
        trade: Trade,
        event_type: str,
        payload: dict,
        now: datetime,
    ):

        history = self.events.setdefault(
            trade.trade_id,
            []
        )

        sequence = (
            len(history) + 1
        )

        previous_hash = (
            history[-1].event_hash
            if history
            else ""
        )

        body = {
            "trade_id":
                trade.trade_id,

            "event_type":
                event_type,

            "timestamp":
                now.isoformat(),

            "payload":
                payload,

            "sequence":
                sequence,

            "previous_hash":
                previous_hash,
        }

        raw = json.dumps(
            body,
            sort_keys=True,
            default=str,
        ).encode()

        event_hash = hashlib.sha256(
            raw
        ).hexdigest()

        event = EscrowEvent(
            event_id=
                secrets.token_hex(16),

            trade_id=
                trade.trade_id,

            event_type=
                event_type,

            timestamp=
                now,

            payload=
                payload,

            sequence=
                sequence,

            previous_hash=
                previous_hash,

            event_hash=
                event_hash,
        )

        history.append(
            event
        )

        for listener in self.listeners:

            listener(event)

        return event

    # ========================================================
    # CREATE TRADE
    # ========================================================

    def create_trade(
        self,
        buyer_account: str,
        seller_account: str,
        asset: str,
        currency: str,
        quantity,
        unit_price,
        delivery: DeliverySchedule,
        release_policy: ReleasePolicy,
        now: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> Trade:

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            quantity = Decimal(
                str(quantity)
            )

            unit_price = money(
                unit_price
            )

            amount = money(
                quantity *
                unit_price
            )

            trade_id = (
                "TRD-"
                + secrets.token_hex(12)
            )

            trade = Trade(

                trade_id=
                    trade_id,

                buyer_account=
                    buyer_account,

                seller_account=
                    seller_account,

                asset=
                    asset,

                currency=
                    currency,

                quantity=
                    quantity,

                unit_price=
                    unit_price,

                escrow_amount=
                    amount,

                created_at=
                    now,

                delivery=
                    delivery,

                release_policy=
                    release_policy,

                metadata=
                    metadata or {},
            )

            self.trades[
                trade_id
            ] = trade

            self.events[
                trade_id
            ] = []

            self._emit(
                trade,
                "TRADE_CREATED",
                {
                    "quantity":
                        str(quantity),

                    "unit_price":
                        str(unit_price),

                    "escrow_amount":
                        str(amount),
                },
                now,
            )

            return trade

    # ========================================================
    # RESERVE FUNDS
    # ========================================================

    def reserve_funds(
        self,
        trade_id: str,
        now: Optional[datetime] = None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            self._require_stage(
                trade,
                TradeStage.CREATED
            )

            escrow_id = (
                "ESC-"
                + secrets.token_hex(12)
            )

            escrow = EscrowAccount(

                escrow_id=
                    escrow_id,

                trade_id=
                    trade_id,

                currency=
                    trade.currency,

                balance=
                    trade.escrow_amount,

                locked_at=
                    now,
            )

            self.escrows[
                escrow_id
            ] = escrow

            trade.stage = (
                TradeStage.FUNDS_RESERVED
            )

            trade.version += 1

            self._emit(
                trade,
                "FUNDS_RESERVED",
                {
                    "escrow_id":
                        escrow_id,

                    "amount":
                        str(
                            trade.escrow_amount
                        ),
                },
                now,
            )

            return escrow

    # ========================================================
    # ORDER SUBMITTED
    # ========================================================

    def order_submitted(
        self,
        trade_id: str,
        order_id: str,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            self._require_stage(
                trade,
                TradeStage.FUNDS_RESERVED
            )

            trade.stage = (
                TradeStage.ORDER_SUBMITTED
            )

            trade.version += 1

            self._emit(
                trade,
                "ORDER_SUBMITTED",
                {
                    "order_id":
                        order_id
                },
                now,
            )

    # ========================================================
    # EXECUTION
    # ========================================================

    def execute_trade(
        self,
        trade_id: str,
        execution_id: str,
        executed_quantity,
        execution_price,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            if trade.stage not in (
                TradeStage.ORDER_SUBMITTED,
                TradeStage.FUNDS_RESERVED,
            ):

                raise RuntimeError(
                    "Trade cannot execute "
                    f"from {trade.stage}"
                )

            executed_quantity = Decimal(
                str(executed_quantity)
            )

            execution_price = money(
                execution_price
            )

            if (
                executed_quantity
                <= 0
            ):

                raise ValueError(
                    "Invalid execution quantity."
                )

            if (
                executed_quantity
                > trade.quantity
            ):

                raise ValueError(
                    "Execution exceeds "
                    "trade quantity."
                )

            trade.stage = (
                TradeStage.EXECUTED
            )

            trade.version += 1

            self._emit(
                trade,
                "TRADE_EXECUTED",
                {
                    "execution_id":
                        execution_id,

                    "executed_quantity":
                        str(
                            executed_quantity
                        ),

                    "execution_price":
                        str(
                            execution_price
                        ),

                    "executed_at":
                        now.isoformat(),
                },
                now,
            )

            # ------------------------------------------------
            # EXACT-TIME RELEASE PATH
            # ------------------------------------------------

            if (
                trade.release_policy
                .release_on_execution
            ):

                self._attempt_release(
                    trade,
                    now,
                )

            else:

                trade.stage = (
                    TradeStage.DELIVERY_PENDING
                )

                self._emit(
                    trade,
                    "DELIVERY_PENDING",
                    {},
                    now,
                )

    # ========================================================
    # DELIVERY
    # ========================================================

    def record_delivery(
        self,
        trade_id: str,
        quantity,
        delivery_reference: str,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            if trade.stage not in (
                TradeStage.DELIVERY_PENDING,
                TradeStage.DELIVERY_PARTIAL,
                TradeStage.EXECUTED,
            ):

                raise RuntimeError(
                    "Delivery cannot be "
                    f"recorded from {trade.stage}"
                )

            quantity = Decimal(
                str(quantity)
            )

            new_total = (
                trade.delivered_quantity
                + quantity
            )

            if new_total > trade.quantity:

                raise ValueError(
                    "Delivery exceeds "
                    "contract quantity."
                )

            trade.delivered_quantity = (
                new_total
            )

            if (
                new_total ==
                trade.quantity
            ):

                trade.stage = (
                    TradeStage.DELIVERY_COMPLETE
                )

                self._emit(
                    trade,
                    "DELIVERY_COMPLETE",
                    {
                        "reference":
                            delivery_reference,

                        "quantity":
                            str(quantity),

                        "total_delivered":
                            str(new_total),
                    },
                    now,
                )

            else:

                if not (
                    trade.delivery
                    .allow_partial_delivery
                ):

                    raise RuntimeError(
                        "Partial delivery "
                        "is not permitted."
                    )

                trade.stage = (
                    TradeStage.DELIVERY_PARTIAL
                )

                self._emit(
                    trade,
                    "DELIVERY_PARTIAL",
                    {
                        "reference":
                            delivery_reference,

                        "quantity":
                            str(quantity),

                        "total_delivered":
                            str(new_total),
                    },
                    now,
                )

            trade.version += 1

            # ------------------------------------------------
            # AUTOMATIC RELEASE
            # ------------------------------------------------

            self._attempt_release(
                trade,
                now,
            )

    # ========================================================
    # BUYER CONFIRMATION
    # ========================================================

    def buyer_confirm(
        self,
        trade_id: str,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            trade.buyer_confirmed = True

            trade.version += 1

            self._emit(
                trade,
                "BUYER_CONFIRMED",
                {},
                now,
            )

            self._attempt_release(
                trade,
                now,
            )

    # ========================================================
    # SELLER CONFIRMATION
    # ========================================================

    def seller_confirm(
        self,
        trade_id: str,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            trade.seller_confirmed = True

            trade.version += 1

            self._emit(
                trade,
                "SELLER_CONFIRMED",
                {},
                now,
            )

            self._attempt_release(
                trade,
                now,
            )

    # ========================================================
    # RISK CLEARANCE
    # ========================================================

    def risk_clear(
        self,
        trade_id: str,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            trade.risk_cleared = True

            trade.version += 1

            self._emit(
                trade,
                "RISK_CLEARED",
                {},
                now,
            )

            self._attempt_release(
                trade,
                now,
            )

    # ========================================================
    # COMPLIANCE CLEARANCE
    # ========================================================

    def compliance_clear(
        self,
        trade_id: str,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            trade = self._trade(
                trade_id
            )

            trade.compliance_cleared = True

            trade.version += 1

            self._emit(
                trade,
                "COMPLIANCE_CLEARED",
                {},
                now,
            )

            self._attempt_release(
                trade,
                now,
            )

    # ========================================================
    # RELEASE ENGINE
    # ========================================================

    def _attempt_release(
        self,
        trade: Trade,
        now: datetime,
    ):

        policy = (
            trade.release_policy
        )

        # --------------------------------------------
        # RISK
        # --------------------------------------------

        if (
            policy.require_risk_clearance
            and not trade.risk_cleared
        ):

            trade.stage = (
                TradeStage.SETTLEMENT_PENDING
            )

            return

        # --------------------------------------------
        # COMPLIANCE
        # --------------------------------------------

        if (
            policy.require_compliance_clearance
            and not trade.compliance_cleared
        ):

            trade.stage = (
                TradeStage.SETTLEMENT_PENDING
            )

            return

        # --------------------------------------------
        # BUYER CONFIRMATION
        # --------------------------------------------

        if (
            policy.require_buyer_confirmation
            and not trade.buyer_confirmed
        ):

            trade.stage = (
                TradeStage.SETTLEMENT_PENDING
            )

            return

        # --------------------------------------------
        # SELLER CONFIRMATION
        # --------------------------------------------

        if (
            policy.require_seller_confirmation
            and not trade.seller_confirmed
        ):

            trade.stage = (
                TradeStage.SETTLEMENT_PENDING
            )

            return

        # --------------------------------------------
        # DELIVERY
        # --------------------------------------------

        if (
            policy.release_on_delivery
            and trade.delivered_quantity
                < trade.quantity
        ):

            trade.stage = (
                TradeStage.DELIVERY_PENDING
            )

            return

        # --------------------------------------------
        # RELEASE DELAY
        # --------------------------------------------

        confirmation_time = (
            self._completion_timestamp(
                trade
            )
        )

        if confirmation_time:

            release_time = (
                confirmation_time
                + timedelta(
                    seconds=
                        policy
                        .release_after_confirmation_seconds
                )
            )

            if now < release_time:

                trade.stage = (
                    TradeStage.SETTLEMENT_PENDING
                )

                return

        # --------------------------------------------
        # AUTHORIZE
        # --------------------------------------------

        self._authorize_release(
            trade,
            now,
        )

    # ========================================================
    # RELEASE AUTHORIZATION
    # ========================================================

    def _authorize_release(
        self,
        trade: Trade,
        now: datetime,
    ):

        if trade.release_authorized:

            return

        trade.release_authorized = True

        trade.stage = (
            TradeStage.RELEASE_AUTHORIZED
        )

        trade.version += 1

        self._emit(
            trade,
            "RELEASE_AUTHORIZED",
            {
                "amount":
                    str(
                        trade.escrow_amount
                    ),

                "authorized_at":
                    now.isoformat(),
            },
            now,
        )

        self._release(
            trade,
            now,
        )

    # ========================================================
    # ACTUAL RELEASE
    # ========================================================

    def _release(
        self,
        trade: Trade,
        now: datetime,
    ):

        escrow = self._escrow_for_trade(
            trade.trade_id
        )

        if escrow is None:

            raise RuntimeError(
                "Escrow account not found."
            )

        if escrow.balance <= 0:

            raise RuntimeError(
                "Escrow has no releasable balance."
            )

        amount = escrow.balance

        escrow.balance = Decimal("0")

        escrow.released += amount

        trade.released_amount += amount

        trade.stage = (
            TradeStage.SETTLED
        )

        trade.version += 1

        self._emit(
            trade,
            "FUNDS_RELEASED",
            {
                "amount":
                    str(amount),

                "currency":
                    trade.currency,

                "released_at":
                    now.isoformat(),
            },
            now,
        )

    # ========================================================
    # EXPIRY
    # ========================================================

    def expire_due_trades(
        self,
        now=None,
    ):

        with self.lock:

            now = now or datetime.now(
                timezone.utc
            )

            expired = []

            for trade in self.trades.values():

                deadline = (
                    trade.delivery
                    .delivery_deadline
                )

                if deadline is None:

                    continue

                if (
                    now <= deadline
                ):

                    continue

                if trade.stage in (
                    TradeStage.SETTLED,
                    TradeStage.CANCELLED,
                    TradeStage.EXPIRED,
                ):

                    continue

                grace = timedelta(
                    seconds=
                        trade.delivery
                        .grace_period_seconds
                )

                if now <= deadline + grace:

                    continue

                trade.stage = (
                    TradeStage.EXPIRED
                )

                trade.version += 1

                self._emit(
                    trade,
                    "TRADE_EXPIRED",
                    {
                        "deadline":
                            deadline.isoformat(),

                        "expired_at":
                            now.isoformat(),
                    },
                    now,
                )

                expired.append(
                    trade.trade_id
                )

            return expired

    # ========================================================
    # TRADE LOOKUP
    # ========================================================

    def get_trade(
        self,
        trade_id: str,
    ):

        return self._trade(
            trade_id
        )

    def audit_log(
        self,
        trade_id: str,
    ):

        return list(
            self.events.get(
                trade_id,
                []
            )
        )

    # ========================================================
    # INTERNALS
    # ========================================================

    def _trade(
        self,
        trade_id: str,
    ) -> Trade:

        try:

            return self.trades[
                trade_id
            ]

        except KeyError:

            raise KeyError(
                f"Unknown trade: {trade_id}"
            )

    def _escrow_for_trade(
        self,
        trade_id: str,
    ):

        for escrow in (
            self.escrows.values()
        ):

            if (
                escrow.trade_id
                == trade_id
            ):

                return escrow

        return None

    @staticmethod
    def _require_stage(
        trade: Trade,
        expected: TradeStage,
    ):

        if trade.stage != expected:

            raise RuntimeError(
                f"Expected {expected}; "
                f"current state is {trade.stage}"
            )

    def _completion_timestamp(
        self,
        trade: Trade,
    ):

        events = self.events[
            trade.trade_id
        ]

        for event in reversed(events):

            if event.event_type in (
                "DELIVERY_COMPLETE",
                "TRADE_EXECUTED",
                "BUYER_CONFIRMED",
                "SELLER_CONFIRMED",
            ):

                return event.timestamp

        return None
```

# Programmable settlement rules

The important part is that the escrow isn't hard-coded to one settlement model.

For example, **instant settlement following execution**:

```python
policy = ReleasePolicy(

    release_on_execution=True,

    release_on_delivery=False,

    require_risk_clearance=True,

    require_compliance_clearance=True,
)
```

The lifecycle becomes:

```text
ORDER
  ↓
EXECUTED
  ↓
RISK CLEAR
  ↓
COMPLIANCE CLEAR
  ↓
RELEASE AUTHORIZED
  ↓
FUNDS RELEASED
```

For a physical trade where payment occurs **only when the entire delivery is received**:

```python
policy = ReleasePolicy(

    release_on_execution=False,

    release_on_delivery=True,

    require_risk_clearance=True,

    require_compliance_clearance=True,

    require_buyer_confirmation=True,
)
```

Lifecycle:

```text
EXECUTED
   ↓
DELIVERY PENDING
   ↓
PARTIAL DELIVERY
   ↓
PARTIAL DELIVERY
   ↓
DELIVERY COMPLETE
   ↓
BUYER CONFIRMS
   ↓
RISK CLEAR
   ↓
COMPLIANCE CLEAR
   ↓
RELEASE
```

# Exact delivery timing

You can specify the delivery window down to the second:

```python
execution_time = datetime(
    2026,
    9,
    1,
    14,
    30,
    0,
    tzinfo=timezone.utc,
)

delivery = DeliverySchedule(

    delivery_window_start =
        execution_time
        + timedelta(
            seconds=30
        ),

    delivery_deadline =
        execution_time
        + timedelta(
            hours=24,
            minutes=30,
            seconds=15
        ),

    grace_period_seconds=300,

    require_full_delivery=True,

    allow_partial_delivery=False,
)
```

So the contract is explicitly:

```text
EXECUTION
2026-09-01 14:30:00.000 UTC

DELIVERY OPENS
2026-09-01 14:30:30.000 UTC

DELIVERY DEADLINE
2026-09-02 15:00:15.000 UTC

GRACE PERIOD
5 minutes

HARD EXPIRY
2026-09-02 15:05:15.000 UTC
```

# Example: complete trade

```python
from datetime import (
    datetime,
    timezone,
    timedelta,
)

engine = EscrowEngine()

execution_time = datetime(
    2026,
    9,
    1,
    14,
    30,
    0,
    tzinfo=timezone.utc,
)

delivery = DeliverySchedule(

    delivery_window_start =
        execution_time,

    delivery_deadline =
        execution_time
        + timedelta(
            hours=2
        ),

    grace_period_seconds=60,

    allow_partial_delivery=False,
)

policy = ReleasePolicy(

    release_on_execution=False,

    release_on_delivery=True,

    require_buyer_confirmation=False,

    require_seller_confirmation=False,

    require_risk_clearance=True,

    require_compliance_clearance=True,

    release_after_confirmation_seconds=0,
)

trade = engine.create_trade(

    buyer_account=
        "RHINO-INST-001",

    seller_account=
        "RHINO-INST-002",

    asset=
        "PHYSICAL-COPPER",

    currency=
        "USDT",

    quantity=
        "1000",

    unit_price=
        "12.50",

    delivery=
        delivery,

    release_policy=
        policy,

    now=
        execution_time,
)

engine.reserve_funds(
    trade.trade_id,
    execution_time,
)

engine.order_submitted(
    trade.trade_id,
    "ORDER-001",
    execution_time,
)

engine.execute_trade(
    trade.trade_id,
    "EXEC-001",
    executed_quantity="1000",
    execution_price="12.50",
    now=execution_time,
)

# Risk and compliance approve
engine.risk_clear(
    trade.trade_id,
    execution_time,
)

engine.compliance_clear(
    trade.trade_id,
    execution_time,
)

# Physical delivery arrives
delivery_time = (
    execution_time
    + timedelta(
        minutes=45
    )
)

engine.record_delivery(
    trade.trade_id,
    quantity="1000",
    delivery_reference=
        "WAREHOUSE-RECEIPT-001",
    now=delivery_time,
)

print(
    trade.stage
)

print(
    trade.released_amount
)
```

The result is:

```text
TradeStage.SETTLED

12500.00
```

# Exact-time automatic settlement

For RhinoBank, I'd add a scheduler around the engine rather than having the application continuously poll.

```python
class EscrowScheduler:

    def __init__(
        self,
        engine: EscrowEngine,
    ):

        self.engine = engine

    def tick(
        self,
        now: datetime,
    ):

        expired = (
            self.engine
            .expire_due_trades(
                now
            )
        )

        return {
            "expired":
                expired,

            "checked_at":
                now.isoformat(),
        }
```

Then the production infrastructure can invoke:

```text
00:00:00
00:00:01
00:00:02
...
```

or, preferably, use a durable job/event system to wake the settlement process exactly when a scheduled event becomes eligible.

# Event-driven integration

The escrow engine can publish events to the rest of RhinoBank:

```python
def rhino_event_bus(
    event: EscrowEvent,
):

    print(
        event.event_type,
        event.trade_id,
        event.sequence,
    )


engine.add_listener(
    rhino_event_bus
)
```

You then get:

```text
TRADE_CREATED
       ↓
FUNDS_RESERVED
       ↓
ORDER_SUBMITTED
       ↓
TRADE_EXECUTED
       ↓
DELIVERY_PENDING
       ↓
DELIVERY_COMPLETE
       ↓
RISK_CLEARED
       ↓
COMPLIANCE_CLEARED
       ↓
RELEASE_AUTHORIZED
       ↓
FUNDS_RELEASED
       ↓
SETTLED
```

Every transition is recorded in a **hash-linked audit chain**:

```text
EVENT 001
  hash A
    ↓
EVENT 002
  previous_hash = A
  hash B
    ↓
EVENT 003
  previous_hash = B
  hash C
    ↓
EVENT 004
  previous_hash = C
  hash D
```

That gives the RhinoBank audit system a tamper-evident history of **what happened, in what order, and at what exact UTC timestamp**.

For a production RhinoBank implementation, I would take this one step further and make the next layer a **declarative settlement DSL** — e.g. `EXECUTION + 30 SEC`, `DELIVERY + 5 MIN`, `RELEASE WHEN 100% DELIVERED AND RISK=GREEN`, `TIMEOUT 24H`, `PARTIAL_RELEASE 25% @ 50% DELIVERY` — compiled into deterministic settlement policies. That would make the escrow system programmable rather than requiring Python code changes for every new trade type.

