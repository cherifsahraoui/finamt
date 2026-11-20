"""
Render an :class:`~finamt.invoicing.model.Invoice` as a one-page A4 PDF with PyMuPDF.

Plain layout: supplier block, customer address, title / number / dates, line table, totals per
VAT rate, notes (exemption note, correction reference), supplier tax numbers in the footer.
Long invoices continue on further pages.
"""

from __future__ import annotations

from decimal import Decimal

import fitz  # PyMuPDF

from .model import Invoice

_W, _H = fitz.paper_size("a4")
_L, _R = 56, _W - 56
# The base-14 fonts only encode Latin-1, so "€" and "–" would be lost. Embed MuPDF's built-in
# Helvetica / Helvetica-Bold instead (Unicode encoding).
_FONT, _BOLD = "fbreg", "fbbold"
_FONTS = {_FONT: fitz.Font("helv"), _BOLD: fitz.Font("hebo")}


def _new_page(doc: fitz.Document) -> fitz.Page:
    page = doc.new_page(width=_W, height=_H)
    for name, font in _FONTS.items():
        page.insert_font(fontname=name, fontbuffer=font.buffer)
    return page


def eur(d: Decimal) -> str:
    """German format: 1.234,56 €"""
    s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def _num(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return s.replace(".", ",")


class _Writer:
    def __init__(self, doc: fitz.Document) -> None:
        self.doc = doc
        self.page = _new_page(doc)
        self.y = 60.0

    def need(self, h: float) -> None:
        if self.y + h > _H - 80:
            self.page = _new_page(self.doc)
            self.y = 60.0

    def text(self, x, s, *, size=9.5, bold=False, right=False):
        font = _BOLD if bold else _FONT
        if right:
            x = x - _FONTS[font].text_length(s, fontsize=size)
        self.page.insert_text((x, self.y), s, fontname=font, fontsize=size)

    def line(self, gap=4.0):
        self.page.draw_line((_L, self.y + gap), (_R, self.y + gap), color=(0, 0, 0), width=0.5)
        self.y += gap + 10


def render_pdf(inv: Invoice) -> bytes:
    doc = fitz.open()
    w = _Writer(doc)

    # supplier (small, top) and customer address block
    w.text(_L, " · ".join(inv.supplier.address_lines()), size=7.5)
    w.y += 28
    for s in inv.customer.address_lines():
        w.text(_L, s, size=10)
        w.y += 13

    # title, number, dates (right column)
    w.y = max(w.y + 24, 190)
    w.text(_L, f"{inv.title} Nr. {inv.number}", size=14, bold=True)
    w.y += 20
    meta = [("Rechnungsdatum", f"{inv.issue_date:%d.%m.%Y}")]
    if inv.supply_period:
        a, b = inv.supply_period
        meta.append(("Leistungszeitraum", f"{a:%d.%m.%Y} – {b:%d.%m.%Y}"))
    elif inv.supply_date:
        meta.append(("Leistungsdatum", f"{inv.supply_date:%d.%m.%Y}"))
    if inv.corrects:
        meta.append(("Korrigiert Rechnung", f"Nr. {inv.corrects}"))
    for k, v in meta:
        w.text(_L, f"{k}:")
        w.text(_L + 120, v)
        w.y += 13
    w.y += 14

    # line table
    cols = (_L, _L + 30, _R - 190, _R - 120, _R - 60, _R)
    w.text(cols[0], "Pos.", bold=True)
    w.text(cols[1], "Leistung", bold=True)
    w.text(cols[3], "Menge", bold=True, right=True)
    w.text(cols[4], "Einzelpreis", bold=True, right=True)
    w.text(cols[5], "Netto", bold=True, right=True)
    if not inv.kleinunternehmer:
        w.text(cols[2], "USt", bold=True)
    w.line()
    for i, ln in enumerate(inv.lines, 1):
        w.need(16)
        w.text(cols[0], str(i))
        w.text(cols[1], ln.description[:70])
        if not inv.kleinunternehmer:
            w.text(cols[2], f"{_num(ln.vat_rate)} %")
        menge = f"{_num(ln.quantity)} {ln.unit}".strip()
        w.text(cols[3], menge, right=True)
        w.text(cols[4], eur(ln.unit_net), right=True)
        w.text(cols[5], eur(ln.net), right=True)
        w.y += 14
    w.line(0)

    # totals per rate (§ 14 Abs. 4 Nr. 7, 8)
    w.need(80)
    for t in inv.rate_totals():
        if inv.kleinunternehmer:
            w.text(cols[4], "Summe", right=True)
            w.text(cols[5], eur(t.net), right=True)
        else:
            w.text(cols[4], f"Netto {_num(t.rate)} %", right=True)
            w.text(cols[5], eur(t.net), right=True)
            w.y += 13
            w.text(cols[4], f"Umsatzsteuer {_num(t.rate)} %", right=True)
            w.text(cols[5], eur(t.vat), right=True)
        w.y += 13
    w.text(cols[4], "Gesamtbetrag", bold=True, right=True)
    w.text(cols[5], eur(inv.gross_total), bold=True, right=True)
    w.y += 26

    # notes
    notes = []
    if inv.kleinunternehmer:
        notes.append(inv.kleinunternehmer_hinweis)
    if inv.notes:
        notes.extend(inv.notes.splitlines())
    for n in notes:
        w.need(14)
        w.text(_L, n[:110])
        w.y += 13

    # footer: supplier tax numbers (§ 14 Abs. 4 Nr. 2) on every page
    fuss = []
    if inv.supplier.steuernummer:
        fuss.append(f"Steuernummer: {inv.supplier.steuernummer}")
    if inv.supplier.ust_idnr:
        fuss.append(f"USt-IdNr.: {inv.supplier.ust_idnr}")
    for page in doc:
        page.insert_text(
            (_L, _H - 40), "   ".join(fuss + [inv.supplier.name]), fontname=_FONT, fontsize=7.5
        )
    data = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return data


def pdf_text(data: bytes) -> str:
    """All text of a rendered PDF (used by tests and to store as the receipt's raw text)."""
    with fitz.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)
