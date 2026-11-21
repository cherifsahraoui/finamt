"""
Issue and cancel invoices: number → PDF → stored ``sale`` receipt.

The receipt's date is the **invoice date**. For the EÜR (cash principle) and for
Ist-Versteuerung the payment date counts; change the receipt date when the money arrives on
another day.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from ..models import Address, Counterparty, ReceiptCategory, ReceiptData, ReceiptType
from ..storage.sqlite import SQLiteRepository
from .model import Invoice, IssuedInvoice, Party
from .numbering import format_number
from .render import pdf_text, render_pdf


def supplier_from_taxpayer(tp: dict) -> Party:
    """The supplier block from the project's taxpayer profile (Stammdaten)."""
    return Party(
        name=tp.get("name") or "",
        street=tp.get("street") or "",
        postcode=tp.get("postcode") or "",
        city=tp.get("city") or "",
        steuernummer=tp.get("tax_number") or "",
        ust_idnr=tp.get("vat_id") or "",
    )


def _receipt_for(inv: Invoice, text: str) -> ReceiptData:
    c = inv.customer
    totals = inv.rate_totals()
    r = ReceiptData(
        raw_text=f"INVOICE:{inv.number}\n{text}",
        receipt_type=ReceiptType("sale"),
        counterparty=Counterparty(
            name=c.name or None,
            vat_id=c.ust_idnr or None,
            address=Address(
                street_and_number=c.street or None,
                postcode=c.postcode or None,
                city=c.city or None,
                country=c.country or None,
            ),
        ),
        receipt_date=datetime(inv.issue_date.year, inv.issue_date.month, inv.issue_date.day),
        total_amount=inv.gross_total,
        vat_amount=inv.vat_total,
        vat_percentage=totals[0].rate if len(totals) == 1 else None,
        category=ReceiptCategory("services"),
        receipt_number=inv.number,
        description=f"{inv.title} {inv.number}",
    )
    if len(totals) > 1:
        r.vat_splits = [
            {"vat_rate": t.rate, "vat_amount": t.vat, "net_amount": t.net} for t in totals
        ]
    r.validate()
    return r


def issue_invoice(repo: SQLiteRepository, inv: Invoice, pdf_dir: Path) -> IssuedInvoice:
    """
    Check the mandatory fields, allocate the number, store the invoice, render the PDF and
    store a ``sale`` receipt with the PDF as its original. Raises ``ValueError`` (with all
    missing fields) before anything is stored.
    """
    fehler = inv.missing_fields(need_number=False)
    if fehler:
        raise ValueError("Rechnung unvollständig: " + " ".join(fehler))
    year = inv.issue_date.year

    def build(seq: int) -> dict:
        inv.number = format_number(year, seq)
        return inv.to_dict()

    repo.create_invoice(year, build)
    pdf = render_pdf(inv)
    receipt = _receipt_for(inv, pdf_text(pdf))
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{receipt.id}.pdf"
    pdf_path.write_bytes(pdf)
    repo.save(receipt)
    repo.set_invoice_receipt(inv.number, receipt.id)
    return IssuedInvoice(
        invoice=inv,
        receipt_id=receipt.id,
        pdf_path=str(pdf_path),
        warnings=list(receipt.validation_warnings),
    )


def cancel_invoice(
    repo: SQLiteRepository, number: str, pdf_dir: Path, issue_date: date | None = None
) -> IssuedInvoice:
    """Issue a Rechnungskorrektur (Storno) with its own number that cancels ``number``."""
    data = repo.get_invoice(number)
    if data is None:
        raise ValueError(f"Rechnung {number} nicht gefunden.")
    schon = repo.invoice_corrected_by(number)
    if schon:
        raise ValueError(f"Rechnung {number} ist schon durch {schon} storniert.")
    original = Invoice.from_dict(data)
    return issue_invoice(repo, original.correction(issue_date or date.today()), pdf_dir)
