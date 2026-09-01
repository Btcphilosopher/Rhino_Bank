"""
RHINOBANK USDT SPOT MARKET
==========================

Institutional / cypherpunk-oriented USDT spot-market core.

Design principles
-----------------
1. Internal ledger is authoritative for customer balances.
2. Blockchain transactions are external settlement evidence.
3. Every monetary movement is represented by ledger entries.
4. Decimal is used instead of float.
5. Idempotency prevents duplicate deposits/withdrawals/orders.
6. Funds are reserved before orders enter the matching system.
7. Blockchain/network-specific logic is isolated behind adapters.
8. Withdrawal approval is deliberately separated from broadcast.
9. Every state-changing operation generates an audit event.

This is an executable reference implementation, NOT a production
custody system. Production deployment requires hardened key
management, HSM/MPC custody, database transactions, reconciliation,
operational controls, regulatory/compliance controls, monitoring,
and independent security review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from enum import Enum
from hashlib import sha256
from typing import Dict, List, Optional
from uuid import uuid4


# ============================================================
# DECIMAL CONFIGURATION
# ============================================================

getcontext().prec = 50

USDT_SCALE = Decimal("0.000001")


def D(value) -> Decimal:
    return Decimal(str(value))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


# ============================================================
# ENUMS
# ============================================================

class USDTChain(str, Enum):
    ETHEREUM = "ETHEREUM"
    TRON = "TRON"
    SOLANA = "SOLANA"
    AVALANCHE = "AVALANCHE"
    ARBITRUM = "ARBITRUM"
    OPTIMISM = "OPTIMISM"


class LedgerSide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class DepositStatus(str, Enum):
    DETECTED = "DETECTED"
    CONFIRMING = "CONFIRMING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class WithdrawalStatus(str, Enum):
    REQUESTED = "REQUESTED"
    RISK_REVIEW = "RISK_REVIEW"
    APPROVED = "APPROVED"
    BROADCAST = "BROADCAST"
    CONFIRMING = "CONFIRMING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


# ============================================================
# LEDGER
# ============================================================

@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    account_id: str
    currency: str
    side: LedgerSide
    amount: Decimal
    reference: str
    description: str
    timestamp: datetime


@dataclass
class DoubleEntryLedger:

    entries: List[LedgerEntry] = field(default_factory=list)

    def post(
        self,
        account_id: str,
        currency: str,
        debit: Decimal,
        credit: Decimal,
        reference: str,
        description: str,
    ) -> None:

        debit = D(debit)
        credit = D(credit)

        if debit < 0 or credit < 0:
            raise ValueError("Ledger values cannot be negative.")

        if debit == 0 and credit == 0:
            raise ValueError("Ledger entry cannot be zero.")

        if debit > 0:

            self.entries.append(
                LedgerEntry(
                    entry_id=uid("led"),
                    account_id=account_id,
                    currency=currency,
                    side=LedgerSide.DEBIT,
                    amount=debit,
                    reference=reference,
                    description=description,
                    timestamp=utcnow(),
                )
            )

        if credit > 0:

            self.entries.append(
                LedgerEntry(
                    entry_id=uid("led"),
                    account_id=account_id,
                    currency=currency,
                    side=LedgerSide.CREDIT,
                    amount=credit,
                    reference=reference,
                    description=description,
                    timestamp=utcnow(),
                )
            )

    def balance(
        self,
        account_id: str,
        currency: str,
    ) -> Decimal:

        total = Decimal("0")

        for entry in self.entries:

            if (
                entry.account_id == account_id
                and entry.currency == currency
            ):

                if entry.side == LedgerSide.CREDIT:
                    total += entry.amount
                else:
                    total -= entry.amount

        return total


# ============================================================
# USDT BALANCE
# ============================================================

@dataclass
class USDTBalance:

    account_id: str

    settled: Decimal = Decimal("0")
    reserved: Decimal = Decimal("0")

    @property
    def available(self) -> Decimal:
        return self.settled - self.reserved

    @property
    def total(self) -> Decimal:
        return self.settled

    def credit(self, amount: Decimal) -> None:

        amount = D(amount)

        if amount <= 0:
            raise ValueError("Credit must be positive.")

        self.settled += amount

    def reserve(self, amount: Decimal) -> None:

        amount = D(amount)

        if amount <= 0:
            raise ValueError("Reserve must be positive.")

        if amount > self.available:
            raise ValueError(
                "Insufficient available USDT."
            )

        self.reserved += amount

    def release(self, amount: Decimal) -> None:

        amount = D(amount)

        if amount <= 0:
            raise ValueError("Release must be positive.")

        if amount > self.reserved:
            raise ValueError(
                "Cannot release more USDT than reserved."
            )

        self.reserved -= amount

    def debit_settled(self, amount: Decimal) -> None:

        amount = D(amount)

        if amount <= 0:
            raise ValueError("Debit must be positive.")

        if amount > self.available:
            raise ValueError(
                "Insufficient available settled USDT."
            )

        self.settled -= amount


# ============================================================
# ADDRESS REGISTRY
# ============================================================

@dataclass
class USDTAddress:

    address_id: str
    account_id: str
    chain: USDTChain
    address: str

    label: str = ""

    active: bool = True
    withdrawal_whitelisted: bool = False

    created_at: datetime = field(
        default_factory=utcnow
    )


# ============================================================
# DEPOSITS
# ============================================================

@dataclass
class USDTDeposit:

    deposit_id: str
    account_id: str

    chain: USDTChain

    tx_hash: str
    destination_address: str

    amount: Decimal

    confirmations: int = 0
    required_confirmations: int = 12

    status: DepositStatus = DepositStatus.DETECTED

    detected_at: datetime = field(
        default_factory=utcnow
    )

    confirmed_at: Optional[datetime] = None

    @property
    def confirmed(self) -> bool:

        return (
            self.confirmations
            >= self.required_confirmations
        )


# ============================================================
# WITHDRAWALS
# ============================================================

@dataclass
class USDTWithdrawal:

    withdrawal_id: str

    account_id: str

    chain: USDTChain

    destination_address: str

    amount: Decimal

    fee: Decimal

    idempotency_key: str

    status: WithdrawalStatus = (
        WithdrawalStatus.REQUESTED
    )

    tx_hash: Optional[str] = None

    requested_at: datetime = field(
        default_factory=utcnow
    )

    broadcast_at: Optional[datetime] = None

    completed_at: Optional[datetime] = None

    @property
    def total_debit(self) -> Decimal:
        return self.amount + self.fee


# ============================================================
# SPOT ORDER
# ============================================================

@dataclass
class SpotOrder:

    order_id: str

    account_id: str

    symbol: str

    side: OrderSide

    quantity: Decimal

    price: Decimal

    time_in_force: TimeInForce

    client_order_id: str

    status: OrderStatus = OrderStatus.OPEN

    filled_quantity: Decimal = Decimal("0")

    reserved_usdt: Decimal = Decimal("0")

    created_at: datetime = field(
        default_factory=utcnow
    )

    @property
    def remaining_quantity(self) -> Decimal:

        return (
            self.quantity
            - self.filled_quantity
        )

    @property
    def notional(self) -> Decimal:

        return (
            self.quantity
            * self.price
        )

    @property
    def remaining_notional(self) -> Decimal:

        return (
            self.remaining_quantity
            * self.price
        )


# ============================================================
# TRADE
# ============================================================

@dataclass(frozen=True)
class SpotTrade:

    trade_id: str

    maker_order_id: str
    taker_order_id: str

    symbol: str

    quantity: Decimal
    price: Decimal

    quote_currency: str

    executed_at: datetime = field(
        default_factory=utcnow
    )

    @property
    def notional(self) -> Decimal:

        return (
            self.quantity
            * self.price
        )


# ============================================================
# AUDIT
# ============================================================

@dataclass(frozen=True)
class AuditEvent:

    event_id: str
    event_type: str
    actor: str
    reference: str
    payload_hash: str

    timestamp: datetime = field(
        default_factory=utcnow
    )


class AuditLog:

    def __init__(self):
        self.events: List[AuditEvent] = []

    def record(
        self,
        event_type: str,
        actor: str,
        reference: str,
        payload: str,
    ):

        digest = sha256(
            payload.encode("utf-8")
        ).hexdigest()

        self.events.append(
            AuditEvent(
                event_id=uid("audit"),
                event_type=event_type,
                actor=actor,
                reference=reference,
                payload_hash=digest,
            )
        )


# ============================================================
# BLOCKCHAIN ADAPTER
# ============================================================

class BlockchainAdapter:

    """
    Interface between RhinoBank and a USDT network.

    IMPORTANT:

    This intentionally does NOT contain private keys.

    Production implementation should connect to:
        - HSM
        - MPC custody
        - institutional custodian
        - hardened signing service

    Never put private keys in this trading process.
    """

    def broadcast_usdt(
        self,
        chain: USDTChain,
        destination: str,
        amount: Decimal,
    ) -> str:

        raise NotImplementedError


class MockBlockchainAdapter(
    BlockchainAdapter
):

    def broadcast_usdt(
        self,
        chain: USDTChain,
        destination: str,
        amount: Decimal,
    ) -> str:

        material = (
            f"{chain.value}|"
            f"{destination}|"
            f"{amount}|"
            f"{uuid4()}"
        )

        return sha256(
            material.encode()
        ).hexdigest()


# ============================================================
# RISK ENGINE
# ============================================================

@dataclass
class USDTLimits:

    maximum_withdrawal: Decimal = (
        Decimal("1000000")
    )

    daily_withdrawal_limit: Decimal = (
        Decimal("5000000")
    )

    minimum_withdrawal: Decimal = (
        Decimal("10")
    )


class USDTPreTradeRisk:

    def __init__(
        self,
        limits: Optional[USDTLimits] = None,
    ):

        self.limits = (
            limits
            or USDTLimits()
        )

    def validate_withdrawal(
        self,
        amount: Decimal,
    ) -> None:

        amount = D(amount)

        if amount < self.limits.minimum_withdrawal:
            raise ValueError(
                "Withdrawal is below minimum."
            )

        if amount > self.limits.maximum_withdrawal:
            raise ValueError(
                "Withdrawal exceeds maximum."
            )


# ============================================================
# USDT SPOT MARKET
# ============================================================

class USDTSpotMarket:

    """
    Main USDT institutional market service.

    Quote currency:
        USDT

    Example symbols:
        BTC/USDT
        ETH/USDT
        SOL/USDT
        XAU/USDT
    """

    def __init__(
        self,
        blockchain: Optional[
            BlockchainAdapter
        ] = None,
    ):

        self.blockchain = (
            blockchain
            or MockBlockchainAdapter()
        )

        self.ledger = DoubleEntryLedger()

        self.audit = AuditLog()

        self.risk = USDTPreTradeRisk()

        self.balances: Dict[
            str,
            USDTBalance
        ] = {}

        self.addresses: Dict[
            str,
            USDTAddress
        ] = {}

        self.deposits: Dict[
            str,
            USDTDeposit
        ] = {}

        self.withdrawals: Dict[
            str,
            USDTWithdrawal
        ] = {}

        self.orders: Dict[
            str,
            SpotOrder
        ] = {}

        self.trades: Dict[
            str,
            SpotTrade
        ] = {}

        self.idempotency: Dict[
            str,
            str
        ] = {}

    # ========================================================
    # ACCOUNT
    # ========================================================

    def account(
        self,
        account_id: str,
    ) -> USDTBalance:

        if account_id not in self.balances:

            self.balances[account_id] = (
                USDTBalance(
                    account_id=account_id
                )
            )

        return self.balances[account_id]

    # ========================================================
    # ADDRESS
    # ========================================================

    def register_address(
        self,
        account_id: str,
        chain: USDTChain,
        address: str,
        label: str = "",
    ) -> USDTAddress:

        address = address.strip()

        if not address:
            raise ValueError(
                "Address cannot be empty."
            )

        address_id = uid("addr")

        result = USDTAddress(
            address_id=address_id,
            account_id=account_id,
            chain=chain,
            address=address,
            label=label,
        )

        self.addresses[address_id] = result

        self.audit.record(
            "USDT_ADDRESS_REGISTERED",
            account_id,
            address_id,
            f"{chain.value}:{address}",
        )

        return result

    def whitelist_address(
        self,
        address_id: str,
    ) -> None:

        if address_id not in self.addresses:
            raise KeyError(
                "Unknown address."
            )

        address = self.addresses[address_id]

        address.withdrawal_whitelisted = True

        self.audit.record(
            "USDT_ADDRESS_WHITELISTED",
            address.account_id,
            address_id,
            address.address,
        )

    # ========================================================
    # DEPOSITS
    # ========================================================

    def detect_deposit(
        self,
        account_id: str,
        chain: USDTChain,
        tx_hash: str,
        destination_address: str,
        amount,
        required_confirmations: int = 12,
    ) -> USDTDeposit:

        amount = D(amount)

        if amount <= 0:
            raise ValueError(
                "Deposit amount must be positive."
            )

        deposit_id = uid("dep")

        deposit = USDTDeposit(
            deposit_id=deposit_id,
            account_id=account_id,
            chain=chain,
            tx_hash=tx_hash,
            destination_address=destination_address,
            amount=amount,
            required_confirmations=(
                required_confirmations
            ),
        )

        self.deposits[deposit_id] = deposit

        self.audit.record(
            "USDT_DEPOSIT_DETECTED",
            account_id,
            deposit_id,
            tx_hash,
        )

        return deposit

    def update_confirmations(
        self,
        deposit_id: str,
        confirmations: int,
    ) -> USDTDeposit:

        if deposit_id not in self.deposits:
            raise KeyError(
                "Unknown deposit."
            )

        deposit = self.deposits[deposit_id]

        if confirmations < 0:
            raise ValueError(
                "Confirmations cannot be negative."
            )

        deposit.confirmations = confirmations

        if deposit.confirmed:

            if deposit.status != (
                DepositStatus.CONFIRMED
            ):

                deposit.status = (
                    DepositStatus.CONFIRMED
                )

                self._credit_deposit(
                    deposit
                )

        else:

            deposit.status = (
                DepositStatus.CONFIRMING
            )

        return deposit

    def _credit_deposit(
        self,
        deposit: USDTDeposit,
    ) -> None:

        balance = self.account(
            deposit.account_id
        )

        balance.credit(
            deposit.amount
        )

        self.ledger.post(
            account_id=deposit.account_id,
            currency="USDT",
            debit=Decimal("0"),
            credit=deposit.amount,
            reference=deposit.deposit_id,
            description="Confirmed USDT blockchain deposit",
        )

        deposit.confirmed_at = utcnow()

        self.audit.record(
            "USDT_DEPOSIT_CREDITED",
            deposit.account_id,
            deposit.deposit_id,
            str(deposit.amount),
        )

    # ========================================================
    # WITHDRAWALS
    # ========================================================

    def request_withdrawal(
        self,
        account_id: str,
        chain: USDTChain,
        destination_address: str,
        amount,
        fee,
        idempotency_key: str,
    ) -> USDTWithdrawal:

        if idempotency_key in self.idempotency:

            existing_id = (
                self.idempotency[
                    idempotency_key
                ]
            )

            return self.withdrawals[
                existing_id
            ]

        amount = D(amount)
        fee = D(fee)

        if amount <= 0:
            raise ValueError(
                "Withdrawal amount must be positive."
            )

        if fee < 0:
            raise ValueError(
                "Fee cannot be negative."
            )

        self.risk.validate_withdrawal(
            amount
        )

        # Address must be explicitly registered
        address = next(
            (
                x
                for x in self.addresses.values()
                if (
                    x.account_id == account_id
                    and x.chain == chain
                    and x.address == destination_address
                    and x.active
                    and x.withdrawal_whitelisted
                )
            ),
            None,
        )

        if address is None:
            raise PermissionError(
                "Destination address is not whitelisted."
            )

        balance = self.account(
            account_id
        )

        total = amount + fee

        if total > balance.available:
            raise ValueError(
                "Insufficient available USDT."
            )

        # Reserve before approval.
        balance.reserve(total)

        withdrawal = USDTWithdrawal(
            withdrawal_id=uid("wd"),
            account_id=account_id,
            chain=chain,
            destination_address=destination_address,
            amount=amount,
            fee=fee,
            idempotency_key=idempotency_key,
            status=WithdrawalStatus.RISK_REVIEW,
        )

        self.withdrawals[
            withdrawal.withdrawal_id
        ] = withdrawal

        self.idempotency[
            idempotency_key
        ] = withdrawal.withdrawal_id

        self.audit.record(
            "USDT_WITHDRAWAL_REQUESTED",
            account_id,
            withdrawal.withdrawal_id,
            f"{destination_address}:{amount}",
        )

        return withdrawal

    def approve_withdrawal(
        self,
        withdrawal_id: str,
        approver: str,
    ) -> None:

        withdrawal = self.withdrawals[
            withdrawal_id
        ]

        if withdrawal.status != (
            WithdrawalStatus.RISK_REVIEW
        ):
            raise ValueError(
                "Withdrawal is not awaiting approval."
            )

        withdrawal.status = (
            WithdrawalStatus.APPROVED
        )

        self.audit.record(
            "USDT_WITHDRAWAL_APPROVED",
            approver,
            withdrawal_id,
            withdrawal.destination_address,
        )

    def broadcast_withdrawal(
        self,
        withdrawal_id: str,
    ) -> str:

        withdrawal = self.withdrawals[
            withdrawal_id
        ]

        if withdrawal.status != (
            WithdrawalStatus.APPROVED
        ):
            raise ValueError(
                "Withdrawal is not approved."
            )

        tx_hash = (
            self.blockchain.broadcast_usdt(
                withdrawal.chain,
                withdrawal.destination_address,
                withdrawal.amount,
            )
        )

        withdrawal.tx_hash = tx_hash

        withdrawal.status = (
            WithdrawalStatus.BROADCAST
        )

        withdrawal.broadcast_at = utcnow()

        balance = self.account(
            withdrawal.account_id
        )

        balance.release(
            withdrawal.total_debit
        )

        balance.debit_settled(
            withdrawal.total_debit
        )

        self.ledger.post(
            account_id=withdrawal.account_id,
            currency="USDT",
            debit=withdrawal.total_debit,
            credit=Decimal("0"),
            reference=withdrawal.withdrawal_id,
            description="USDT withdrawal broadcast",
        )

        self.audit.record(
            "USDT_WITHDRAWAL_BROADCAST",
            withdrawal.account_id,
            withdrawal_id,
            tx_hash,
        )

        return tx_hash

    def complete_withdrawal(
        self,
        withdrawal_id: str,
    ) -> None:

        withdrawal = self.withdrawals[
            withdrawal_id
        ]

        if withdrawal.status not in (
            WithdrawalStatus.BROADCAST,
            WithdrawalStatus.CONFIRMING,
        ):
            raise ValueError(
                "Withdrawal cannot be completed."
            )

        withdrawal.status = (
            WithdrawalStatus.COMPLETED
        )

        withdrawal.completed_at = utcnow()

        self.audit.record(
            "USDT_WITHDRAWAL_COMPLETED",
            withdrawal.account_id,
            withdrawal_id,
            withdrawal.tx_hash or "",
        )

    # ========================================================
    # SPOT BUY
    # ========================================================

    def place_buy_order(
        self,
        account_id: str,
        symbol: str,
        quantity,
        price,
        client_order_id: str,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> SpotOrder:

        if client_order_id in self.idempotency:

            existing_id = (
                self.idempotency[
                    client_order_id
                ]
            )

            return self.orders[
                existing_id
            ]

        quantity = D(quantity)
        price = D(price)

        if quantity <= 0:
            raise ValueError(
                "Quantity must be positive."
            )

        if price <= 0:
            raise ValueError(
                "Price must be positive."
            )

        notional = quantity * price

        balance = self.account(
            account_id
        )

        if notional > balance.available:
            raise ValueError(
                "Insufficient USDT buying power."
            )

        # Reserve quote currency.
        balance.reserve(notional)

        order = SpotOrder(
            order_id=uid("ord"),
            account_id=account_id,
            symbol=symbol.upper(),
            side=OrderSide.BUY,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            reserved_usdt=notional,
        )

        self.orders[
            order.order_id
        ] = order

        self.idempotency[
            client_order_id
        ] = order.order_id

        self.audit.record(
            "SPOT_BUY_ORDER_CREATED",
            account_id,
            order.order_id,
            f"{symbol}:{quantity}:{price}",
        )

        return order

    # ========================================================
    # SPOT SELL
    # ========================================================

    def place_sell_order(
        self,
        account_id: str,
        symbol: str,
        quantity,
        price,
        client_order_id: str,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> SpotOrder:

        if client_order_id in self.idempotency:

            existing_id = (
                self.idempotency[
                    client_order_id
                ]
            )

            return self.orders[
                existing_id
            ]

        quantity = D(quantity)
        price = D(price)

        if quantity <= 0:
            raise ValueError(
                "Quantity must be positive."
            )

        if price <= 0:
            raise ValueError(
                "Price must be positive."
            )

        order = SpotOrder(
            order_id=uid("ord"),
            account_id=account_id,
            symbol=symbol.upper(),
            side=OrderSide.SELL,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
        )

        self.orders[
            order.order_id
        ] = order

        self.idempotency[
            client_order_id
        ] = order.order_id

        self.audit.record(
            "SPOT_SELL_ORDER_CREATED",
            account_id,
            order.order_id,
            f"{symbol}:{quantity}:{price}",
        )

        return order

    # ========================================================
    # EXECUTION
    # ========================================================

    def execute_trade(
        self,
        maker_order_id: str,
        taker_order_id: str,
        quantity,
        price,
    ) -> SpotTrade:

        quantity = D(quantity)
        price = D(price)

        maker = self.orders[
            maker_order_id
        ]

        taker = self.orders[
            taker_order_id
        ]

        if quantity <= 0:
            raise ValueError(
                "Trade quantity must be positive."
            )

        if quantity > maker.remaining_quantity:
            raise ValueError(
                "Trade exceeds maker quantity."
            )

        if quantity > taker.remaining_quantity:
            raise ValueError(
                "Trade exceeds taker quantity."
            )

        notional = quantity * price

        # ----------------------------------------------------
        # Identify BUY / SELL
        # ----------------------------------------------------

        buy_order = (
            maker
            if maker.side == OrderSide.BUY
            else taker
        )

        sell_order = (
            maker
            if maker.side == OrderSide.SELL
            else taker
        )

        buyer_balance = self.account(
            buy_order.account_id
        )

        seller_balance = self.account(
            sell_order.account_id
        )

        # ----------------------------------------------------
        # Buyer USDT
        # ----------------------------------------------------

        if notional > buy_order.reserved_usdt:
            raise ValueError(
                "Buyer reserved USDT is insufficient."
            )

        # Consume buyer reservation.
        buyer_balance.reserved -= notional

        buy_order.reserved_usdt -= notional

        # ----------------------------------------------------
        # Seller receives USDT
        # ----------------------------------------------------

        seller_balance.credit(
            notional
        )

        # ----------------------------------------------------
        # Ledger
        # ----------------------------------------------------

        trade_id = uid("trd")

        self.ledger.post(
            account_id=buy_order.account_id,
            currency="USDT",
            debit=notional,
            credit=Decimal("0"),
            reference=trade_id,
            description="USDT spot purchase",
        )

        self.ledger.post(
            account_id=sell_order.account_id,
            currency="USDT",
            debit=Decimal("0"),
            credit=notional,
            reference=trade_id,
            description="USDT spot sale proceeds",
        )

        # ----------------------------------------------------
        # Order state
        # ----------------------------------------------------

        maker.filled_quantity += quantity
        taker.filled_quantity += quantity

        self._update_order_status(
            maker
        )

        self._update_order_status(
            taker
        )

        # ----------------------------------------------------
        # Trade
        # ----------------------------------------------------

        trade = SpotTrade(
            trade_id=trade_id,
            maker_order_id=maker_order_id,
            taker_order_id=taker_order_id,
            symbol=maker.symbol,
            quantity=quantity,
            price=price,
            quote_currency="USDT",
        )

        self.trades[
            trade.trade_id
        ] = trade

        self.audit.record(
            "USDT_SPOT_TRADE_EXECUTED",
            "MATCHING_ENGINE",
            trade_id,
            (
                f"{maker.symbol}|"
                f"{quantity}|"
                f"{price}"
            ),
        )

        return trade

    # ========================================================
    # ORDER STATUS
    # ========================================================

    def _update_order_status(
        self,
        order: SpotOrder,
    ) -> None:

        if order.filled_quantity == 0:
            order.status = (
                OrderStatus.OPEN
            )

        elif (
            order.filled_quantity
            < order.quantity
        ):
            order.status = (
                OrderStatus.PARTIALLY_FILLED
            )

        else:

            order.status = (
                OrderStatus.FILLED
            )

            # Any remaining reservation is released.
            if order.reserved_usdt > 0:

                balance = self.account(
                    order.account_id
                )

                balance.release(
                    order.reserved_usdt
                )

                order.reserved_usdt = (
                    Decimal("0")
                )

    # ========================================================
    # CANCEL ORDER
    # ========================================================

    def cancel_order(
        self,
        order_id: str,
    ) -> None:

        order = self.orders[
            order_id
        ]

        if order.status not in (
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
        ):
            raise ValueError(
                "Order cannot be cancelled."
            )

        if order.reserved_usdt > 0:

            balance = self.account(
                order.account_id
            )

            balance.release(
                order.reserved_usdt
            )

            order.reserved_usdt = (
                Decimal("0")
            )

        order.status = (
            OrderStatus.CANCELLED
        )

        self.audit.record(
            "SPOT_ORDER_CANCELLED",
            order.account_id,
            order_id,
            order.symbol,
        )

    # ========================================================
    # ACCOUNT VIEW
    # ========================================================

    def account_snapshot(
        self,
        account_id: str,
    ) -> dict:

        balance = self.account(
            account_id
        )

        open_orders = [
            order
            for order in self.orders.values()
            if (
                order.account_id == account_id
                and order.status in (
                    OrderStatus.OPEN,
                    OrderStatus.PARTIALLY_FILLED,
                )
            )
        ]

        trades = [
            trade
            for trade in self.trades.values()
            if (
                self.orders[
                    trade.maker_order_id
                ].account_id == account_id

                or

                self.orders[
                    trade.taker_order_id
                ].account_id == account_id
            )
        ]

        return {
            "account_id": account_id,

            "USDT": {
                "total": str(balance.total),
                "settled": str(balance.settled),
                "reserved": str(balance.reserved),
                "available": str(balance.available),
            },

            "open_orders": [
                {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": str(order.quantity),
                    "filled": str(
                        order.filled_quantity
                    ),
                    "price": str(order.price),
                    "reserved_usdt": str(
                        order.reserved_usdt
                    ),
                    "status": order.status.value,
                }
                for order in open_orders
            ],

            "trades": [
                {
                    "trade_id": trade.trade_id,
                    "symbol": trade.symbol,
                    "quantity": str(
                        trade.quantity
                    ),
                    "price": str(
                        trade.price
                    ),
                    "notional": str(
                        trade.notional
                    ),
                }
                for trade in trades
            ],
        }


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    market = USDTSpotMarket()

    # --------------------------------------------------------
    # ACCOUNT A
    # --------------------------------------------------------

    alice = "RHINO-INST-001"

    # Simulate a confirmed blockchain deposit.
    deposit = market.detect_deposit(
        account_id=alice,
        chain=USDTChain.ETHEREUM,
        tx_hash="0xDEMO_TX_001",
        destination_address="0xRHINO_DEPOSIT",
        amount="1000000",
        required_confirmations=12,
    )

    market.update_confirmations(
        deposit.deposit_id,
        12,
    )

    # --------------------------------------------------------
    # WITHDRAWAL ADDRESS
    # --------------------------------------------------------

    address = market.register_address(
        account_id=alice,
        chain=USDTChain.TRON,
        address="T_RHINO_EXTERNAL_ADDRESS",
        label="Institutional Treasury",
    )

    market.whitelist_address(
        address.address_id
    )

    # --------------------------------------------------------
    # SPOT BUY
    # --------------------------------------------------------

    buy_order = market.place_buy_order(
        account_id=alice,
        symbol="BTC/USDT",
        quantity="5",
        price="60000",
        client_order_id="RHINO-BUY-001",
    )

    # --------------------------------------------------------
    # SECOND ACCOUNT
    # --------------------------------------------------------

    bob = "RHINO-INST-002"

    bob_balance = market.account(bob)

    bob_balance.credit(
        D("10")
    )

    # Seller has BTC conceptually supplied to market.
    sell_order = market.place_sell_order(
        account_id=bob,
        symbol="BTC/USDT",
        quantity="5",
        price="60000",
        client_order_id="RHINO-SELL-001",
    )

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    trade = market.execute_trade(
        maker_order_id=buy_order.order_id,
        taker_order_id=sell_order.order_id,
        quantity="5",
        price="60000",
    )

    print("\n=== TRADE ===")
    print(trade)

    # --------------------------------------------------------
    # ACCOUNT SNAPSHOT
    # --------------------------------------------------------

    print("\n=== ALICE ===")

    print(
        market.account_snapshot(alice)
    )

    print("\n=== BOB ===")

    print(
        market.account_snapshot(bob)
    )

    # --------------------------------------------------------
    # WITHDRAWAL
    # --------------------------------------------------------

    withdrawal = market.request_withdrawal(
        account_id=alice,
        chain=USDTChain.TRON,
        destination_address=address.address,
        amount="100000",
        fee="5",
        idempotency_key="RHINO-WITHDRAW-001",
    )

    market.approve_withdrawal(
        withdrawal.withdrawal_id,
        approver="RISK-OFFICER-01",
    )

    tx_hash = market.broadcast_withdrawal(
        withdrawal.withdrawal_id
    )

    market.complete_withdrawal(
        withdrawal.withdrawal_id
    )

    print("\n=== WITHDRAWAL ===")
    print(withdrawal)
    print("TX:", tx_hash)

    print("\n=== FINAL ACCOUNT ===")

    print(
        market.account_snapshot(alice)
    )
