# RHINOBANK NODE — Python Institutional Runtime

```text
rhinobank-node/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── ledger.py
│   ├── usdt.py
│   ├── market.py
│   ├── risk.py
│   ├── audit.py
│   └── node.py
│
├── tests/
│   └── test_node.py
│
├── requirements.txt
├── .env.example
└── Dockerfile
```

## 1. `requirements.txt`

```text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
sqlalchemy
aiosqlite
httpx
```

---

# 2. `app/config.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    node_id: str = "rhino-node-001"

    environment: str = "development"

    host: str = "0.0.0.0"
    port: int = 8080

    database_url: str = (
        "sqlite+aiosqlite:///./rhinobank.db"
    )

    # Never store actual custody keys here.
    custody_provider: str = "mock"

    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
```

---

# 3. `app/models.py`

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc)


@dataclass
class NodeIdentity:

    node_id: str
    environment: str

    started_at: datetime = now()

    status: str = "STARTING"

    version: str = "0.1.0"


@dataclass
class Account:

    account_id: str
    institution: str

    created_at: datetime = now()

    active: bool = True


@dataclass
class USDTWallet:

    account_id: str

    settled: Decimal = Decimal("0")
    reserved: Decimal = Decimal("0")

    @property
    def available(self):

        return (
            self.settled
            - self.reserved
        )
```

---

# 4. `app/ledger.py`

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4


def uid(prefix):

    return (
        f"{prefix}_"
        f"{uuid4().hex}"
    )


def utcnow():

    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LedgerEntry:

    entry_id: str

    account_id: str

    currency: str

    debit: Decimal

    credit: Decimal

    reference: str

    timestamp: datetime


class Ledger:

    def __init__(self):

        self.entries = []

    def post(
        self,
        account_id,
        currency,
        debit,
        credit,
        reference,
    ):

        debit = Decimal(str(debit))
        credit = Decimal(str(credit))

        if debit < 0:
            raise ValueError(
                "Debit cannot be negative."
            )

        if credit < 0:
            raise ValueError(
                "Credit cannot be negative."
            )

        if debit == 0 and credit == 0:
            raise ValueError(
                "Zero-value ledger entry."
            )

        entry = LedgerEntry(
            entry_id=uid("ledger"),
            account_id=account_id,
            currency=currency,
            debit=debit,
            credit=credit,
            reference=reference,
            timestamp=utcnow(),
        )

        self.entries.append(entry)

        return entry

    def balance(
        self,
        account_id,
        currency,
    ):

        balance = Decimal("0")

        for entry in self.entries:

            if (
                entry.account_id
                == account_id
                and entry.currency
                == currency
            ):

                balance += (
                    entry.credit
                    - entry.debit
                )

        return balance
```

---

# 5. `app/risk.py`

```python
from decimal import Decimal


class RiskEngine:

    def __init__(self):

        self.maximum_order_notional = (
            Decimal("10000000")
        )

        self.maximum_withdrawal = (
            Decimal("1000000")
        )

    def check_order(
        self,
        notional,
    ):

        notional = Decimal(
            str(notional)
        )

        if notional <= 0:
            raise ValueError(
                "Invalid order notional."
            )

        if (
            notional
            > self.maximum_order_notional
        ):
            raise PermissionError(
                "Order exceeds risk limit."
            )

        return True

    def check_withdrawal(
        self,
        amount,
    ):

        amount = Decimal(
            str(amount)
        )

        if amount <= 0:
            raise ValueError(
                "Invalid withdrawal."
            )

        if (
            amount
            > self.maximum_withdrawal
        ):
            raise PermissionError(
                "Withdrawal exceeds risk limit."
            )

        return True
```

---

# 6. `app/usdt.py`

```python
from decimal import Decimal
from uuid import uuid4

from .ledger import Ledger
from .risk import RiskEngine


class USDTService:

    def __init__(
        self,
        ledger: Ledger,
        risk: RiskEngine,
    ):

        self.ledger = ledger
        self.risk = risk

        self.wallets = {}

        self.deposits = {}
        self.withdrawals = {}

    # --------------------------------------------------------
    # WALLET
    # --------------------------------------------------------

    def wallet(
        self,
        account_id,
    ):

        if account_id not in self.wallets:

            self.wallets[account_id] = {
                "settled": Decimal("0"),
                "reserved": Decimal("0"),
            }

        return self.wallets[account_id]

    # --------------------------------------------------------
    # CREDIT
    # --------------------------------------------------------

    def credit(
        self,
        account_id,
        amount,
        reference,
    ):

        amount = Decimal(
            str(amount)
        )

        if amount <= 0:
            raise ValueError(
                "Amount must be positive."
            )

        wallet = self.wallet(
            account_id
        )

        wallet["settled"] += amount

        self.ledger.post(
            account_id,
            "USDT",
            Decimal("0"),
            amount,
            reference,
        )

        return {
            "account_id": account_id,
            "currency": "USDT",
            "amount": str(amount),
            "reference": reference,
        }

    # --------------------------------------------------------
    # RESERVE
    # --------------------------------------------------------

    def reserve(
        self,
        account_id,
        amount,
    ):

        amount = Decimal(
            str(amount)
        )

        wallet = self.wallet(
            account_id
        )

        available = (
            wallet["settled"]
            - wallet["reserved"]
        )

        if amount > available:

            raise ValueError(
                "Insufficient USDT."
            )

        wallet["reserved"] += amount

    # --------------------------------------------------------
    # RELEASE
    # --------------------------------------------------------

    def release(
        self,
        account_id,
        amount,
    ):

        amount = Decimal(
            str(amount)
        )

        wallet = self.wallet(
            account_id
        )

        if amount > wallet["reserved"]:

            raise ValueError(
                "Invalid USDT release."
            )

        wallet["reserved"] -= amount

    # --------------------------------------------------------
    # WITHDRAW
    # --------------------------------------------------------

    def withdraw(
        self,
        account_id,
        amount,
        destination,
    ):

        amount = Decimal(
            str(amount)
        )

        self.risk.check_withdrawal(
            amount
        )

        wallet = self.wallet(
            account_id
        )

        if amount > (
            wallet["settled"]
            - wallet["reserved"]
        ):

            raise ValueError(
                "Insufficient available USDT."
            )

        wallet["settled"] -= amount

        withdrawal_id = (
            f"wd_{uuid4().hex}"
        )

        self.withdrawals[
            withdrawal_id
        ] = {
            "withdrawal_id":
                withdrawal_id,

            "account_id":
                account_id,

            "amount":
                str(amount),

            "destination":
                destination,

            "status":
                "QUEUED",
        }

        self.ledger.post(
            account_id,
            "USDT",
            amount,
            Decimal("0"),
            withdrawal_id,
        )

        return self.withdrawals[
            withdrawal_id
        ]

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    def snapshot(
        self,
        account_id,
    ):

        wallet = self.wallet(
            account_id
        )

        available = (
            wallet["settled"]
            - wallet["reserved"]
        )

        return {
            "currency": "USDT",

            "settled":
                str(wallet["settled"]),

            "reserved":
                str(wallet["reserved"]),

            "available":
                str(available),
        }
```

---

# 7. `app/market.py`

```python
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from .usdt import USDTService
from .risk import RiskEngine


class Side(str, Enum):

    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:

    order_id: str

    account_id: str

    symbol: str

    side: Side

    quantity: Decimal

    price: Decimal

    filled: Decimal = Decimal("0")

    status: str = "OPEN"

    @property
    def notional(self):

        return (
            self.quantity
            * self.price
        )


class SpotMarket:

    def __init__(
        self,
        usdt: USDTService,
        risk: RiskEngine,
    ):

        self.usdt = usdt
        self.risk = risk

        self.orders = {}

    def place_order(
        self,
        account_id,
        symbol,
        side,
        quantity,
        price,
    ):

        quantity = Decimal(
            str(quantity)
        )

        price = Decimal(
            str(price)
        )

        notional = (
            quantity
            * price
        )

        self.risk.check_order(
            notional
        )

        # BUY orders reserve USDT.
        if side == Side.BUY:

            self.usdt.reserve(
                account_id,
                notional
            )

        order = Order(
            order_id=
                f"ord_{uuid4().hex}",

            account_id=
                account_id,

            symbol=
                symbol.upper(),

            side=
                side,

            quantity=
                quantity,

            price=
                price,
        )

        self.orders[
            order.order_id
        ] = order

        return order

    def cancel_order(
        self,
        order_id,
    ):

        order = self.orders[
            order_id
        ]

        if order.status != "OPEN":

            raise ValueError(
                "Order is not open."
            )

        if order.side == Side.BUY:

            self.usdt.release(
                order.account_id,
                order.notional
            )

        order.status = "CANCELLED"

        return order
```

---

# 8. `app/node.py`

```python
from datetime import datetime, timezone

from .config import settings
from .ledger import Ledger
from .risk import RiskEngine
from .usdt import USDTService
from .market import SpotMarket
from .models import NodeIdentity


class RhinoNode:

    def __init__(self):

        self.identity = NodeIdentity(
            node_id=settings.node_id,
            environment=settings.environment,
        )

        self.ledger = Ledger()

        self.risk = RiskEngine()

        self.usdt = USDTService(
            ledger=self.ledger,
            risk=self.risk,
        )

        self.market = SpotMarket(
            usdt=self.usdt,
            risk=self.risk,
        )

        self.accounts = {}

        self.identity.status = (
            "ONLINE"
        )

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    def create_account(
        self,
        account_id,
        institution,
    ):

        if account_id in self.accounts:

            raise ValueError(
                "Account already exists."
            )

        self.accounts[
            account_id
        ] = {
            "account_id":
                account_id,

            "institution":
                institution,

            "active":
                True,
        }

        return self.accounts[
            account_id
        ]

    # --------------------------------------------------------
    # NODE STATUS
    # --------------------------------------------------------

    def health(self):

        return {
            "node_id":
                self.identity.node_id,

            "environment":
                self.identity.environment,

            "status":
                self.identity.status,

            "version":
                self.identity.version,

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "services": {

                "ledger":
                    "ONLINE",

                "usdt":
                    "ONLINE",

                "spot_market":
                    "ONLINE",

                "risk":
                    "ONLINE",
            },
        }
```

---

# 9. `app/main.py`

```python
from fastapi import FastAPI, HTTPException

from pydantic import BaseModel

from .node import RhinoNode
from .market import Side


app = FastAPI(
    title="RhinoBank Node",
    version="0.1.0",
    description=(
        "Institutional RhinoBank "
        "financial node."
    ),
)


node = RhinoNode()


# ============================================================
# REQUEST MODELS
# ============================================================

class AccountRequest(BaseModel):

    account_id: str

    institution: str


class DepositRequest(BaseModel):

    account_id: str

    amount: str

    reference: str


class WithdrawalRequest(BaseModel):

    account_id: str

    amount: str

    destination: str


class OrderRequest(BaseModel):

    account_id: str

    symbol: str

    side: str

    quantity: str

    price: str


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return node.health()


# ============================================================
# NODE INFO
# ============================================================

@app.get("/node")
async def node_info():

    return {
        "node_id":
            node.identity.node_id,

        "status":
            node.identity.status,

        "version":
            node.identity.version,
    }


# ============================================================
# ACCOUNTS
# ============================================================

@app.post("/accounts")
async def create_account(
    request: AccountRequest
):

    try:

        return node.create_account(
            request.account_id,
            request.institution,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )


# ============================================================
# USDT DEPOSIT
# ============================================================

@app.post("/usdt/deposit")
async def deposit(
    request: DepositRequest
):

    try:

        return node.usdt.credit(
            request.account_id,
            request.amount,
            request.reference,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# USDT BALANCE
# ============================================================

@app.get(
    "/accounts/{account_id}/usdt"
)
async def usdt_balance(
    account_id: str
):

    return node.usdt.snapshot(
        account_id
    )


# ============================================================
# USDT WITHDRAWAL
# ============================================================

@app.post("/usdt/withdraw")
async def withdraw(
    request: WithdrawalRequest
):

    try:

        return node.usdt.withdraw(
            request.account_id,
            request.amount,
            request.destination,
        )

    except (ValueError, PermissionError) as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# SPOT ORDER
# ============================================================

@app.post("/spot/orders")
async def place_order(
    request: OrderRequest
):

    try:

        side = Side(
            request.side.upper()
        )

        order = node.market.place_order(
            account_id=
                request.account_id,

            symbol=
                request.symbol,

            side=
                side,

            quantity=
                request.quantity,

            price=
                request.price,
        )

        return {
            "order_id":
                order.order_id,

            "account_id":
                order.account_id,

            "symbol":
                order.symbol,

            "side":
                order.side.value,

            "quantity":
                str(order.quantity),

            "price":
                str(order.price),

            "notional":
                str(order.notional),

            "status":
                order.status,
        }

    except (
        ValueError,
        PermissionError,
    ) as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# CANCEL ORDER
# ============================================================

@app.delete(
    "/spot/orders/{order_id}"
)
async def cancel_order(
    order_id: str
):

    try:

        order = node.market.cancel_order(
            order_id
        )

        return {
            "order_id":
                order.order_id,

            "status":
                order.status,
        }

    except (
        ValueError,
        KeyError,
    ) as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
```

---

# 10. `.env.example`

```text
RHINO_NODE_ID=rhino-node-001

ENVIRONMENT=development

HOST=0.0.0.0

PORT=8080

DATABASE_URL=sqlite+aiosqlite:///./rhinobank.db

CUSTODY_PROVIDER=mock

LOG_LEVEL=INFO
```

---

# 11. `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir \
    -r requirements.txt

COPY app ./app

EXPOSE 8080

CMD [
    "uvicorn",
    "app.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8080"
]
```

---

# 12. Run the RhinoBank node

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8080
```

The node will expose:

```text
http://localhost:8080/health
```

and the interactive API:

```text
http://localhost:8080/docs
```

---

# 13. Example API workflow

Create an institutional account:

```bash
curl -X POST \
  http://localhost:8080/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "RHINO-INST-001",
    "institution": "RhinoBank Capital"
  }'
```

Credit USDT:

```bash
curl -X POST \
  http://localhost:8080/usdt/deposit \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "RHINO-INST-001",
    "amount": "1000000",
    "reference": "USDT-DEPOSIT-001"
  }'
```

Check balance:

```bash
curl \
  http://localhost:8080/accounts/RHINO-INST-001/usdt
```

Place a BTC/USDT order:

```bash
curl -X POST \
  http://localhost:8080/spot/orders \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "RHINO-INST-001",
    "symbol": "BTC/USDT",
    "side": "BUY",
    "quantity": "5",
    "price": "60000"
  }'
```

The node then has the basic flow:

```text
                    RHINOBANK NODE
                          │
             ┌────────────┴────────────┐
             │                         │
          REST API                NODE CONTROL
             │                         │
       ┌─────┼──────┐                  │
       │     │      │                  │
      USDT  SPOT   ACCOUNTS          HEALTH
       │     │      │
       │     │      │
       └─────┼──────┘
             │
        RISK ENGINE
             │
        DOUBLE ENTRY
          LEDGER
             │
       PERSISTENCE LAYER
```

The next production step should be to replace the in-memory dictionaries with **PostgreSQL and transactional database operations**, then put the node behind mTLS/API authentication and split the matching engine from the API process.

For a real institutional deployment, I would also **not put blockchain private keys on this node**. The node should issue authenticated custody instructions to an HSM/MPC/custodian service, while independently monitoring the blockchain and reconciling the custody balance against the RhinoBank internal ledger.

