# RHINOQUANT GBP — PYTHON STABLECOIN STATE ENGINE

```python
"""
RHINOQUANT GBP
==============

RQN = RhinoQuant GBP

Design:
    1 RQN = 1 GBP nominal target.

This module is deliberately separated from consensus.

The PoS validator should:
    - verify transaction signatures
    - verify validator authorization
    - verify nonce / replay protection
    - execute deterministic state transition
    - calculate the resulting state root
    - include the transition in the block

This module:
    - maintains RQN balances
    - controls authorised issuance
    - controls redemption
    - tracks total supply
    - tracks eligible GBP reserves
    - enforces monetary invariants
    - creates deterministic transaction receipts

Production implementation should use a Rust
deterministic state machine for consensus-critical
execution. Python is appropriate for prototyping,
testing, simulation and integration services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from enum import Enum
from hashlib import sha256
from typing import Dict, Optional
import time
import uuid


# ============================================================
# DETERMINISTIC MONEY
# ============================================================

getcontext().prec = 50

GBP_SCALE = Decimal("0.01")
RQN_SCALE = Decimal("0.000001")


def money(value) -> Decimal:
    """
    GBP monetary value.
    """
    return Decimal(str(value)).quantize(GBP_SCALE)


def rqn(value) -> Decimal:
    """
    RQN token amount.

    Six decimal places.
    """
    return Decimal(str(value)).quantize(RQN_SCALE)


# ============================================================
# TOKEN
# ============================================================

TOKEN_SYMBOL = "RQN"
REFERENCE_CURRENCY = "GBP"

TARGET_PRICE_GBP = Decimal("1.00")


# ============================================================
# TRANSACTION TYPES
# ============================================================

class TxType(str, Enum):

    TRANSFER = "TRANSFER"

    MINT = "MINT"

    BURN = "BURN"

    RESERVE_DEPOSIT = "RESERVE_DEPOSIT"

    RESERVE_WITHDRAWAL = "RESERVE_WITHDRAWAL"


# ============================================================
# ACCOUNT
# ============================================================

@dataclass
class Account:

    address: str

    balance: Decimal = Decimal("0")

    nonce: int = 0

    frozen: bool = False


# ============================================================
# RESERVE
# ============================================================

@dataclass
class Reserve:

    """
    Authoritative backing ledger.

    In production this represents reconciled GBP
    held with authorised reserve institutions.

    The blockchain should NOT pretend that an on-chain
    number automatically proves an off-chain bank balance.

    reserve_balance:
        GBP verified by the reserve/treasury system.
    """

    reserve_balance: Decimal = Decimal("0")

    verified_at: Optional[int] = None

    verification_reference: Optional[str] = None

    def deposit(self, amount):

        amount = money(amount)

        if amount <= 0:
            raise ValueError("Reserve deposit must be positive.")

        self.reserve_balance += amount

    def withdraw(self, amount):

        amount = money(amount)

        if amount <= 0:
            raise ValueError("Reserve withdrawal must be positive.")

        if amount > self.reserve_balance:
            raise ValueError(
                "Insufficient GBP reserves."
            )

        self.reserve_balance -= amount


# ============================================================
# TRANSACTION
# ============================================================

@dataclass(frozen=True)
class Transaction:

    tx_type: TxType

    sender: str

    recipient: Optional[str]

    amount: Decimal

    nonce: int

    timestamp: int

    tx_id: str

    signature: str = ""

    reserve_reference: Optional[str] = None


# ============================================================
# RECEIPT
# ============================================================

@dataclass
class Receipt:

    tx_id: str

    success: bool

    reason: str

    state_root: str

    supply_after: Decimal


# ============================================================
# RHINOQUANT STATE
# ============================================================

class RhinoQuantState:

    """
    Deterministic monetary state.

    Core invariant:

        total_supply <= eligible_gbp_reserves

    and therefore:

        every RQN is backed by at least £1
    """

    def __init__(self):

        self.accounts: Dict[str, Account] = {}

        self.total_supply = Decimal("0")

        self.reserve = Reserve()

        self.authorised_minters = set()

        self.authorised_burners = set()

        self.treasury_address = "RQN_TREASURY"

        self.paused = False

        self.processed_transactions = set()

        self.block_height = 0

        self._create_system_accounts()

    # ========================================================
    # SYSTEM ACCOUNTS
    # ========================================================

    def _create_system_accounts(self):

        self.accounts[
            self.treasury_address
        ] = Account(
            address=self.treasury_address
        )

    # ========================================================
    # ACCOUNT CREATION
    # ========================================================

    def create_account(self, address: str):

        if address in self.accounts:
            return self.accounts[address]

        account = Account(
            address=address
        )

        self.accounts[address] = account

        return account

    # ========================================================
    # AUTHORISATION
    # ========================================================

    def authorise_minter(self, address: str):

        self.authorised_minters.add(address)

    def revoke_minter(self, address: str):

        self.authorised_minters.discard(address)

    def authorise_burner(self, address: str):

        self.authorised_burners.add(address)

    def revoke_burner(self, address: str):

        self.authorised_burners.discard(address)

    # ========================================================
    # RESERVES
    # ========================================================

    def record_reserve_deposit(
        self,
        amount,
        verification_reference: str
    ):

        amount = money(amount)

        self.reserve.deposit(amount)

        self.reserve.verified_at = int(time.time())

        self.reserve.verification_reference = (
            verification_reference
        )

        self.assert_invariants()

    # ========================================================
    # MINT
    # ========================================================

    def mint(
        self,
        minter: str,
        recipient: str,
        amount
    ):

        amount = rqn(amount)

        if self.paused:
            raise ValueError(
                "RhinoQuant issuance is paused."
            )

        if minter not in self.authorised_minters:
            raise PermissionError(
                "Address is not an authorised minter."
            )

        if amount <= 0:
            raise ValueError(
                "Mint amount must be positive."
            )

        if recipient not in self.accounts:
            self.create_account(recipient)

        projected_supply = (
            self.total_supply + amount
        )

        projected_reserves = rqn(
            self.reserve.reserve_balance
        )

        if projected_supply > projected_reserves:
            raise ValueError(
                "Mint rejected: insufficient GBP backing."
            )

        self.accounts[
            recipient
        ].balance += amount

        self.total_supply += amount

        self.assert_invariants()

    # ========================================================
    # BURN
    # ========================================================

    def burn(
        self,
        burner: str,
        holder: str,
        amount
    ):

        amount = rqn(amount)

        if burner not in self.authorised_burners:
            raise PermissionError(
                "Address is not an authorised burner."
            )

        if holder not in self.accounts:
            raise ValueError(
                "Unknown holder."
            )

        account = self.accounts[holder]

        if account.balance < amount:
            raise ValueError(
                "Insufficient RQN."
            )

        account.balance -= amount

        self.total_supply -= amount

        self.assert_invariants()

    # ========================================================
    # TRANSFER
    # ========================================================

    def transfer(
        self,
        sender: str,
        recipient: str,
        amount,
        nonce: int
    ):

        amount = rqn(amount)

        if self.paused:
            raise ValueError(
                "Transfers are currently paused."
            )

        if sender not in self.accounts:
            raise ValueError(
                "Unknown sender."
            )

        if recipient not in self.accounts:
            self.create_account(recipient)

        sender_account = self.accounts[sender]

        recipient_account = self.accounts[recipient]

        if sender_account.frozen:
            raise ValueError(
                "Sender account is frozen."
            )

        if nonce != sender_account.nonce:
            raise ValueError(
                f"Invalid nonce: expected "
                f"{sender_account.nonce}, "
                f"received {nonce}"
            )

        if amount <= 0:
            raise ValueError(
                "Transfer must be positive."
            )

        if sender_account.balance < amount:
            raise ValueError(
                "Insufficient RQN balance."
            )

        sender_account.balance -= amount

        recipient_account.balance += amount

        sender_account.nonce += 1

        self.assert_invariants()

    # ========================================================
    # PAUSE
    # ========================================================

    def pause(self):

        self.paused = True

    def unpause(self):

        self.paused = False

    # ========================================================
    # SUPPLY
    # ========================================================

    def circulating_supply(self):

        return self.total_supply

    # ========================================================
    # COLLATERAL RATIO
    # ========================================================

    def collateral_ratio(self):

        if self.total_supply == 0:

            return Decimal("Infinity")

        return (
            self.reserve.reserve_balance
            / self.total_supply
        )

    # ========================================================
    # RESERVE RATIO
    # ========================================================

    def reserve_ratio(self):

        if self.total_supply == 0:

            return Decimal("Infinity")

        return (
            self.reserve.reserve_balance
            / Decimal(self.total_supply)
        )

    # ========================================================
    # INVARIANTS
    # ========================================================

    def assert_invariants(self):

        # ----------------------------------------------------
        # NO NEGATIVE SUPPLY
        # ----------------------------------------------------

        if self.total_supply < 0:
            raise RuntimeError(
                "INVARIANT FAILURE: negative supply."
            )

        # ----------------------------------------------------
        # FULL BACKING
        # ----------------------------------------------------

        if (
            self.total_supply
            > self.reserve.reserve_balance
        ):

            raise RuntimeError(
                "INVARIANT FAILURE: "
                "RQN supply exceeds GBP reserves."
            )

        # ----------------------------------------------------
        # NO NEGATIVE BALANCES
        # ----------------------------------------------------

        for account in self.accounts.values():

            if account.balance < 0:

                raise RuntimeError(
                    f"INVARIANT FAILURE: "
                    f"negative balance {account.address}"
                )

    # ========================================================
    # STATE HASH
    # ========================================================

    def state_root(self):

        records = []

        for address in sorted(self.accounts):

            account = self.accounts[address]

            records.append(
                "|".join([
                    address,
                    str(account.balance),
                    str(account.nonce),
                    str(account.frozen)
                ])
            )

        records.append(
            f"SUPPLY|{self.total_supply}"
        )

        records.append(
            f"RESERVE|{self.reserve.reserve_balance}"
        )

        records.append(
            f"PAUSED|{self.paused}"
        )

        payload = "\n".join(records)

        return sha256(
            payload.encode("utf-8")
        ).hexdigest()

    # ========================================================
    # VALIDATE TRANSACTION
    # ========================================================

    def validate_transaction(
        self,
        tx: Transaction
    ):

        if tx.tx_id in self.processed_transactions:

            raise ValueError(
                "Transaction already processed."
            )

        if tx.amount <= 0:

            raise ValueError(
                "Transaction amount must be positive."
            )

        if tx.tx_type == TxType.TRANSFER:

            account = self.accounts.get(tx.sender)

            if account is None:
                raise ValueError(
                    "Unknown sender."
                )

            if account.nonce != tx.nonce:

                raise ValueError(
                    "Invalid nonce."
                )

            if account.balance < tx.amount:

                raise ValueError(
                    "Insufficient balance."
                )

        elif tx.tx_type == TxType.MINT:

            if tx.sender not in self.authorised_minters:

                raise PermissionError(
                    "Unauthorised mint."
                )

            projected_supply = (
                self.total_supply + tx.amount
            )

            if (
                projected_supply
                > rqn(self.reserve.reserve_balance)
            ):

                raise ValueError(
                    "Mint exceeds reserve backing."
                )

        elif tx.tx_type == TxType.BURN:

            if tx.sender not in self.authorised_burners:

                raise PermissionError(
                    "Unauthorised burn."
                )

        return True

    # ========================================================
    # EXECUTE TRANSACTION
    # ========================================================

    def apply_transaction(
        self,
        tx: Transaction
    ) -> Receipt:

        try:

            self.validate_transaction(tx)

            if tx.tx_type == TxType.TRANSFER:

                self.transfer(
                    sender=tx.sender,
                    recipient=tx.recipient,
                    amount=tx.amount,
                    nonce=tx.nonce
                )

            elif tx.tx_type == TxType.MINT:

                self.mint(
                    minter=tx.sender,
                    recipient=tx.recipient,
                    amount=tx.amount
                )

            elif tx.tx_type == TxType.BURN:

                self.burn(
                    burner=tx.sender,
                    holder=tx.recipient,
                    amount=tx.amount
                )

            else:

                raise ValueError(
                    "Unsupported transaction type."
                )

            self.processed_transactions.add(
                tx.tx_id
            )

            return Receipt(
                tx_id=tx.tx_id,
                success=True,
                reason="OK",
                state_root=self.state_root(),
                supply_after=self.total_supply
            )

        except Exception as exc:

            return Receipt(
                tx_id=tx.tx_id,
                success=False,
                reason=str(exc),
                state_root=self.state_root(),
                supply_after=self.total_supply
            )


# ============================================================
# POOL / VALIDATOR ADAPTER
# ============================================================

class RhinoQuantValidatorAdapter:

    """
    Thin adapter between RhinoQuant and the PoS validator.

    Your existing validator should call:

        validate_block_transaction()
        apply_block_transaction()

    during deterministic block execution.
    """

    def __init__(
        self,
        state: RhinoQuantState
    ):

        self.state = state

    def validate_block_transaction(
        self,
        tx: Transaction
    ):

        return self.state.validate_transaction(tx)

    def apply_block_transaction(
        self,
        tx: Transaction
    ):

        return self.state.apply_transaction(tx)

    def get_state_root(self):

        return self.state.state_root()


# ============================================================
# DEMONSTRATION
# ============================================================

if __name__ == "__main__":

    state = RhinoQuantState()

    adapter = RhinoQuantValidatorAdapter(
        state
    )

    # --------------------------------------------------------
    # AUTHORISED ISSUANCE DESK
    # --------------------------------------------------------

    state.authorise_minter(
        "RHINO_MINT_AUTHORITY"
    )

    state.authorise_burner(
        "RHINO_REDEMPTION_AUTHORITY"
    )

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    state.create_account(
        "RHINO_TREASURY"
    )

    state.create_account(
        "CLIENT_001"
    )

    # --------------------------------------------------------
    # VERIFIED GBP RESERVES
    # --------------------------------------------------------

    state.record_reserve_deposit(
        amount="10000000.00",
        verification_reference="GBP-RESERVE-000001"
    )

    print(
        "GBP reserves:",
        state.reserve.reserve_balance
    )

    # --------------------------------------------------------
    # MINT 1,000,000 RQN
    # --------------------------------------------------------

    mint_tx = Transaction(
        tx_type=TxType.MINT,
        sender="RHINO_MINT_AUTHORITY",
        recipient="CLIENT_001",
        amount=rqn("1000000"),
        nonce=0,
        timestamp=int(time.time()),
        tx_id=str(uuid.uuid4())
    )

    receipt = adapter.apply_block_transaction(
        mint_tx
    )

    print(
        "Mint receipt:",
        receipt
    )

    # --------------------------------------------------------
    # CLIENT TRANSFER
    # --------------------------------------------------------

    state.create_account(
        "CLIENT_002"
    )

    transfer_tx = Transaction(
        tx_type=TxType.TRANSFER,
        sender="CLIENT_001",
        recipient="CLIENT_002",
        amount=rqn("25000"),
        nonce=0,
        timestamp=int(time.time()),
        tx_id=str(uuid.uuid4())
    )

    receipt = adapter.apply_block_transaction(
        transfer_tx
    )

    print(
        "Transfer receipt:",
        receipt
    )

    # --------------------------------------------------------
    # MARKET STATE
    # --------------------------------------------------------

    print()
    print("========== RHINOQUANT ==========")

    print(
        "Token:",
        TOKEN_SYMBOL
    )

    print(
        "Target:",
        TARGET_PRICE_GBP,
        "GBP"
    )

    print(
        "Supply:",
        state.total_supply,
        "RQN"
    )

    print(
        "GBP reserves:",
        state.reserve.reserve_balance
    )

    print(
        "Collateral ratio:",
        state.collateral_ratio()
    )

    print(
        "CLIENT_001:",
        state.accounts[
            "CLIENT_001"
        ].balance
    )

    print(
        "CLIENT_002:",
        state.accounts[
            "CLIENT_002"
        ].balance
    )

    print(
        "State root:",
        state.state_root()
    )

    # --------------------------------------------------------
    # FINAL INVARIANT CHECK
    # --------------------------------------------------------

    state.assert_invariants()

    print(
        "STATUS: MONETARY INVARIANTS VALID"
    )
```

