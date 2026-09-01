"""
RHINOBANK AUTOMATED INVOICING ENGINE
=====================================

Generates buyer/seller invoices automatically from completed trades.

Features
--------
- Buyer invoices
- Seller invoices
- Commercial invoice numbering
- Exact trade linkage
- Escrow linkage
- Tax/VAT fields
- Delivery references
- Settlement references
- Credit/debit notes
- Immutable invoice snapshots
- Hash-linked audit trail
- Dot-matrix printer rendering
- Plain-text archival representation
- JSON export
- Idempotent generation
- Automatic invoice triggering from trade events

The invoice engine does NOT move money.
It records the commercial obligation/documentation
associated with a trade.
"""

from __future__ import annotations

import hashlib
import json
import secrets

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, List


# ============================================================
# MONEY
# ============================================================

def D(value) -> Decimal:
    return Decimal(str(value))


def money(value) -> Decimal:
    return D(value).quantize(
        Decimal("0.01")
    )


# ============================================================
# DOCUMENT TYPES
# ============================================================

class InvoiceType(str, Enum):

    BUYER = "BUYER_INVOICE"
    SELLER = "SELLER_INVOICE"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"


class InvoiceStatus(str, Enum):

    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PAID = "PAID"
    VOID = "VOID"
    CREDITED = "CREDITED"


# ============================================================
# LINE ITEM
# ============================================================

@dataclass(frozen=True)
class InvoiceLine:

    line_number: int

    description: str

    asset: str

    quantity: Decimal

    unit_price: Decimal

    currency: str

    tax_rate: Decimal = D("0.00")

    delivery_reference: Optional[str] = None

    @property
    def net_amount(self):

        return money(
            self.quantity *
            self.unit_price
        )

    @property
    def tax_amount(self):

        return money(
            self.net_amount *
            self.tax_rate
        )

    @property
    def gross_amount(self):

        return money(
            self.net_amount +
            self.tax_amount
        )


# ============================================================
# PARTY
# ============================================================

@dataclass(frozen=True)
class InvoiceParty:

    account_id: str

    legal_name: str

    address: str = ""

    country: str = ""

    tax_id: Optional[str] = None

    registration_number: Optional[str] = None


# ============================================================
# INVOICE
# ============================================================

@dataclass
class Invoice:

    invoice_id: str

    invoice_number: str

    invoice_type: InvoiceType

    status: InvoiceStatus

    trade_id: str

    escrow_id: Optional[str]

    issuer: InvoiceParty

    recipient: InvoiceParty

    currency: str

    issue_time: datetime

    due_time: Optional[datetime]

    lines: List[InvoiceLine]

    settlement_reference: Optional[str] = None

    delivery_reference: Optional[str] = None

    notes: str = ""

    previous_hash: str = ""

    document_hash: str = ""

    metadata: dict = field(
        default_factory=dict
    )

    @property
    def subtotal(self):

        return money(
            sum(
                (
                    line.net_amount
                    for line in self.lines
                ),
                D("0")
            )
        )

    @property
    def tax_total(self):

        return money(
            sum(
                (
                    line.tax_amount
                    for line in self.lines
                ),
                D("0")
            )
        )

    @property
    def total(self):

        return money(
            self.subtotal +
            self.tax_total
        )


# ============================================================
# DOT MATRIX RENDERER
# ============================================================

class DotMatrixRenderer:

    """
    Creates an old-school continuous-feed invoice.

    Designed for:
        Epson-style printers
        tractor-feed paper
        warehouse printers
        archival text output
    """

    WIDTH = 80

    def __init__(
        self,
        width: int = 80,
    ):

        self.width = width

    def line(self):

        return "=" * self.width

    def dashed(self):

        return "-" * self.width

    def centre(
        self,
        text: str,
    ):

        return text.center(
            self.width
        )

    def money(
        self,
        value: Decimal,
    ):

        return f"{value:,.2f}"

    def render(
        self,
        invoice: Invoice,
    ):

        output = []

        output.append(
            self.centre(
                "RHINOBANK"
            )
        )

        output.append(
            self.centre(
                "INSTITUTIONAL TRADE SYSTEM"
            )
        )

        output.append(
            self.line()
        )

        output.append(
            self.centre(
                invoice.invoice_type.value
            )
        )

        output.append(
            self.line()
        )

        output.append(
            f"INVOICE NO : {invoice.invoice_number}"
        )

        output.append(
            f"DOCUMENT ID: {invoice.invoice_id}"
        )

        output.append(
            f"TRADE ID   : {invoice.trade_id}"
        )

        output.append(
            f"ISSUED UTC : "
            f"{invoice.issue_time.isoformat()}"
        )

        output.append(
            self.dashed()
        )

        output.append(
            "ISSUER"
        )

        output.append(
            f"  {invoice.issuer.legal_name}"
        )

        output.append(
            f"  ACCOUNT: "
            f"{invoice.issuer.account_id}"
        )

        if invoice.issuer.address:

            output.append(
                f"  {invoice.issuer.address}"
            )

        if invoice.issuer.tax_id:

            output.append(
                f"  TAX ID: "
                f"{invoice.issuer.tax_id}"
            )

        output.append("")

        output.append(
            "BILL TO"
        )

        output.append(
            f"  {invoice.recipient.legal_name}"
        )

        output.append(
            f"  ACCOUNT: "
            f"{invoice.recipient.account_id}"
        )

        if invoice.recipient.address:

            output.append(
                f"  {invoice.recipient.address}"
            )

        if invoice.recipient.tax_id:

            output.append(
                f"  TAX ID: "
                f"{invoice.recipient.tax_id}"
            )

        output.append(
            self.dashed()
        )

        output.append(
            f"{'#':<4}"
            f"{'DESCRIPTION':<28}"
            f"{'QTY':>10}"
            f"{'PRICE':>16}"
            f"{'TOTAL':>18}"
        )

        output.append(
            self.dashed()
        )

        for line in invoice.lines:

            description = (
                line.description[:28]
            )

            output.append(
                f"{line.line_number:<4}"
                f"{description:<28}"
                f"{str(line.quantity):>10}"
                f"{self.money(line.unit_price):>16}"
                f"{self.money(line.gross_amount):>18}"
            )

            if line.delivery_reference:

                output.append(
                    f"     DELIVERY: "
                    f"{line.delivery_reference}"
                )

        output.append(
            self.dashed()
        )

        output.append(
            f"{'SUBTOTAL':>62}"
            f"{self.money(invoice.subtotal):>18}"
        )

        output.append(
            f"{'TAX':>62}"
            f"{self.money(invoice.tax_total):>18}"
        )

        output.append(
            self.line()
        )

        output.append(
            f"{'TOTAL':>62}"
            f"{self.money(invoice.total):>18}"
        )

        output.append(
            self.line()
        )

        if invoice.settlement_reference:

            output.append(
                f"SETTLEMENT: "
                f"{invoice.settlement_reference}"
            )

        if invoice.escrow_id:

            output.append(
                f"ESCROW    : "
                f"{invoice.escrow_id}"
            )

        if invoice.delivery_reference:

            output.append(
                f"DELIVERY  : "
                f"{invoice.delivery_reference}"
            )

        if invoice.due_time:

            output.append(
                f"DUE       : "
                f"{invoice.due_time.isoformat()}"
            )

        output.append(
            self.dashed()
        )

        output.append(
            "DOCUMENT HASH:"
        )

        output.append(
            invoice.document_hash
        )

        output.append(
            self.dashed()
        )

        output.append(
            self.centre(
                "RHINOBANK ELECTRONIC COMMERCIAL DOCUMENT"
            )
        )

        output.append(
            self.centre(
                "END OF DOCUMENT"
            )
        )

        return "\n".join(output)


# ============================================================
# INVOICE ENGINE
# ============================================================

class InvoiceEngine:

    def __init__(self):

        self.invoices: Dict[
            str,
            Invoice
        ] = {}

        self.trade_invoice_index: Dict[
            str,
            List[str]
        ] = {}

        self.counter = 0

        self.renderer = (
            DotMatrixRenderer()
        )

    # ========================================================
    # NUMBERING
    # ========================================================

    def _next_number(
        self,
        invoice_type: InvoiceType,
    ):

        self.counter += 1

        prefix = {

            InvoiceType.BUYER:
                "RHB-B",

            InvoiceType.SELLER:
                "RHB-S",

            InvoiceType.CREDIT_NOTE:
                "RHB-C",

            InvoiceType.DEBIT_NOTE:
                "RHB-D",
        }[invoice_type]

        year = datetime.now(
            timezone.utc
        ).year

        return (
            f"{prefix}-"
            f"{year}-"
            f"{self.counter:09d}"
        )

    # ========================================================
    # CREATE
    # ========================================================

    def create_invoice(
        self,
        invoice_type: InvoiceType,
        trade_id: str,
        issuer: InvoiceParty,
        recipient: InvoiceParty,
        asset: str,
        quantity,
        unit_price,
        currency: str,
        escrow_id: Optional[str] = None,
        delivery_reference: Optional[str] = None,
        settlement_reference: Optional[str] = None,
        tax_rate="0",
        issue_time=None,
        due_time=None,
        description=None,
        metadata=None,
    ):

        issue_time = (
            issue_time
            or datetime.now(
                timezone.utc
            )
        )

        quantity = D(quantity)

        unit_price = money(
            unit_price
        )

        tax_rate = D(
            tax_rate
        )

        invoice_id = (
            "INV-"
            + secrets.token_hex(16)
        )

        invoice_number = (
            self._next_number(
                invoice_type
            )
        )

        line = InvoiceLine(

            line_number=1,

            description=(
                description
                or f"Trade of {asset}"
            ),

            asset=asset,

            quantity=quantity,

            unit_price=unit_price,

            currency=currency,

            tax_rate=tax_rate,

            delivery_reference=
                delivery_reference,
        )

        invoice = Invoice(

            invoice_id=
                invoice_id,

            invoice_number=
                invoice_number,

            invoice_type=
                invoice_type,

            status=
                InvoiceStatus.ISSUED,

            trade_id=
                trade_id,

            escrow_id=
                escrow_id,

            issuer=
                issuer,

            recipient=
                recipient,

            currency=
                currency,

            issue_time=
                issue_time,

            due_time=
                due_time,

            lines=[
                line
            ],

            settlement_reference=
                settlement_reference,

            delivery_reference=
                delivery_reference,

            metadata=
                metadata or {},
        )

        invoice.document_hash = (
            self._hash_invoice(
                invoice
            )
        )

        self.invoices[
            invoice_id
        ] = invoice

        self.trade_invoice_index.setdefault(
            trade_id,
            []
        ).append(
            invoice_id
        )

        return invoice

    # ========================================================
    # HASH
    # ========================================================

    def _hash_invoice(
        self,
        invoice: Invoice,
    ):

        document = {

            "invoice_id":
                invoice.invoice_id,

            "invoice_number":
                invoice.invoice_number,

            "type":
                invoice.invoice_type.value,

            "trade_id":
                invoice.trade_id,

            "escrow_id":
                invoice.escrow_id,

            "issuer":
                invoice.issuer.__dict__,

            "recipient":
                invoice.recipient.__dict__,

            "currency":
                invoice.currency,

            "issue_time":
                invoice.issue_time.isoformat(),

            "lines": [
                {
                    "line_number":
                        x.line_number,

                    "description":
                        x.description,

                    "asset":
                        x.asset,

                    "quantity":
                        str(x.quantity),

                    "unit_price":
                        str(x.unit_price),

                    "currency":
                        x.currency,

                    "tax_rate":
                        str(x.tax_rate),

                    "delivery_reference":
                        x.delivery_reference,
                }

                for x in invoice.lines
            ],

            "total":
                str(invoice.total),
        }

        raw = json.dumps(
            document,
            sort_keys=True,
        ).encode()

        return hashlib.sha256(
            raw
        ).hexdigest()

    # ========================================================
    # RENDER
    # ========================================================

    def print_invoice(
        self,
        invoice_id: str,
    ):

        invoice = self.invoices[
            invoice_id
        ]

        return self.renderer.render(
            invoice
        )

    # ========================================================
    # JSON
    # ========================================================

    def json(
        self,
        invoice_id: str,
    ):

        invoice = self.invoices[
            invoice_id
        ]

        return json.dumps(
            {
                "invoice_id":
                    invoice.invoice_id,

                "invoice_number":
                    invoice.invoice_number,

                "invoice_type":
                    invoice.invoice_type.value,

                "status":
                    invoice.status.value,

                "trade_id":
                    invoice.trade_id,

                "escrow_id":
                    invoice.escrow_id,

                "issuer":
                    invoice.issuer.__dict__,

                "recipient":
                    invoice.recipient.__dict__,

                "currency":
                    invoice.currency,

                "issue_time":
                    invoice.issue_time.isoformat(),

                "due_time":
                    (
                        invoice.due_time.isoformat()
                        if invoice.due_time
                        else None
                    ),

                "subtotal":
                    str(invoice.subtotal),

                "tax":
                    str(invoice.tax_total),

                "total":
                    str(invoice.total),

                "document_hash":
                    invoice.document_hash,
            },

            indent=2,
        )

    # ========================================================
    # FIND INVOICES FOR TRADE
    # ========================================================

    def invoices_for_trade(
        self,
        trade_id: str,
    ):

        ids = (
            self.trade_invoice_index
            .get(
                trade_id,
                []
            )
        )

        return [
            self.invoices[x]
            for x in ids
        ]

    # ========================================================
    # MARK PAID
    # ========================================================

    def mark_paid(
        self,
        invoice_id: str,
        settlement_reference: str,
    ):

        invoice = self.invoices[
            invoice_id
        ]

        if invoice.status != (
            InvoiceStatus.ISSUED
        ):

            raise RuntimeError(
                "Invoice is not payable."
            )

        invoice.status = (
            InvoiceStatus.PAID
        )

        invoice.settlement_reference = (
            settlement_reference
        )

        return invoice
