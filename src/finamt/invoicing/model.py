"""
Outgoing invoices (§ 14 UStG) — data model, totals and the mandatory-field check.

Rules used (docs/tax-rules.md):
  - § 14 Abs. 4 S. 1 UStG: mandatory fields 1–10 (row "mandatory fields", verified).
  - § 33 UStDV: Kleinbetragsrechnung up to 250 € gross with reduced fields (row "250 €", verified).
  - § 12 Abs. 1 / Abs. 2 UStG: 19 % / 7 % (verified); 0 % needs a note on the reason.
  - § 19 UStG: a Kleinunternehmer shows no VAT and adds a note (row "tax-free, no VAT on
    invoices", verified). The exact wording of that note is a TODO (row "Kleinunternehmer
    invoice note"), so the text is a setting with a default the owner should check.
  - VAT per rate: commercial rounding (half up) of net × rate — TODO(verify), see
    docs/tax-rules.md row "invoice VAT rounding".

A cancellation is a *Rechnungskorrektur / Storno* with its own number and negative amounts;
it is **not** a "Gutschrift", which in § 14 Abs. 4 Nr. 10 means self-billing by the recipient.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")

#: § 33 UStDV: invoices up to this gross amount may use the reduced fields.
KLEINBETRAG_GRENZE = Decimal("250")
#: VAT rates an invoice line may use (§ 12 Abs. 1, 2 UStG; 0 % only with a note).
ERLAUBTE_SAETZE = (Decimal("19"), Decimal("7"), Decimal("0"))
#: TODO(verify): wording of the § 19 note — see docs/tax-rules.md ("Kleinunternehmer invoice note").
KLEINUNTERNEHMER_HINWEIS = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."


def _r(d: Decimal) -> Decimal:
    # TODO(verify): rounding of the VAT per rate — see docs/tax-rules.md
    return d.quantize(_CENT, rounding=ROUND_HALF_UP)


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


@dataclass
class Party:
    """Supplier or customer: name, address, tax numbers."""

    name: str = ""
    street: str = ""
    postcode: str = ""
    city: str = ""
    country: str = ""
    steuernummer: str = ""
    ust_idnr: str = ""

    @property
    def has_address(self) -> bool:
        return bool(self.name.strip() and self.street.strip() and self.city.strip())

    def address_lines(self) -> list[str]:
        lines = [self.name, self.street, f"{self.postcode} {self.city}".strip()]
        if self.country:
            lines.append(self.country)
        return [x for x in lines if x and x.strip()]


@dataclass
class InvoiceLine:
    description: str
    quantity: Decimal
    unit_net: Decimal  # net unit price in EUR
    vat_rate: Decimal  # percent, e.g. Decimal("19")
    unit: str = ""  # e.g. "Std.", "Stück"

    def __post_init__(self) -> None:
        self.quantity = _d(self.quantity)
        self.unit_net = _d(self.unit_net)
        self.vat_rate = _d(self.vat_rate)

    @property
    def net(self) -> Decimal:
        return _r(self.quantity * self.unit_net)


@dataclass
class RateTotal:
    rate: Decimal
    net: Decimal
    vat: Decimal

    @property
    def gross(self) -> Decimal:
        return self.net + self.vat


@dataclass
class Invoice:
    supplier: Party
    customer: Party
    issue_date: date
    lines: list[InvoiceLine]
    supply_date: date | None = None
    supply_period: tuple[date, date] | None = None
    number: str = ""
    notes: str = ""
    kleinunternehmer: bool = False
    kleinunternehmer_hinweis: str = KLEINUNTERNEHMER_HINWEIS
    corrects: str | None = None  # number of the invoice this one cancels / corrects
    corrects_date: date | None = None

    # ------------------------------------------------------------------
    # Totals (Decimal, rounded per rate line)
    # ------------------------------------------------------------------

    def rate_totals(self) -> list[RateTotal]:
        nets: dict[Decimal, Decimal] = {}
        for ln in self.lines:
            rate = Decimal("0") if self.kleinunternehmer else ln.vat_rate.normalize()
            nets[rate] = nets.get(rate, Decimal("0")) + ln.net
        return [
            RateTotal(rate=rate, net=_r(net), vat=_r(net * rate / Decimal("100")))
            for rate, net in sorted(nets.items(), reverse=True)
        ]

    @property
    def net_total(self) -> Decimal:
        return sum((t.net for t in self.rate_totals()), Decimal("0"))

    @property
    def vat_total(self) -> Decimal:
        return sum((t.vat for t in self.rate_totals()), Decimal("0"))

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.vat_total

    @property
    def is_correction(self) -> bool:
        return bool(self.corrects)

    @property
    def title(self) -> str:
        return "Rechnungskorrektur (Storno)" if self.is_correction else "Rechnung"

    @property
    def is_kleinbetrag(self) -> bool:
        """§ 33 UStDV: gross amount up to 250 €."""
        return abs(self.gross_total) <= KLEINBETRAG_GRENZE

    # ------------------------------------------------------------------
    # § 14 Abs. 4 check
    # ------------------------------------------------------------------

    def missing_fields(self, *, need_number: bool = True) -> list[str]:
        """German messages for every missing mandatory item (empty list = complete)."""
        fehler: list[str] = []
        s, c = self.supplier, self.customer
        # Nr. 1: name and address of supplier (always) and customer (not for Kleinbetrag)
        if not s.has_address:
            fehler.append("Name und Anschrift des leistenden Unternehmers fehlen.")
        if not self.is_kleinbetrag and not c.has_address:
            fehler.append("Name und Anschrift des Leistungsempfängers fehlen.")
        # Nr. 2: Steuernummer or USt-IdNr of the supplier (not for Kleinbetrag, § 33 UStDV)
        if not self.is_kleinbetrag and not (s.steuernummer.strip() or s.ust_idnr.strip()):
            fehler.append("Steuernummer oder USt-IdNr. des leistenden Unternehmers fehlt.")
        # Nr. 3: issue date
        if not self.issue_date:
            fehler.append("Ausstellungsdatum fehlt.")
        # Nr. 4: sequential number (assigned when the invoice is issued)
        if need_number and not self.number:
            fehler.append("Rechnungsnummer fehlt.")
        # Nr. 5: quantity and description
        if not self.lines:
            fehler.append("Mindestens eine Position ist nötig.")
        for i, ln in enumerate(self.lines, 1):
            if not ln.description.strip():
                fehler.append(f"Position {i}: Beschreibung der Leistung fehlt.")
            if ln.quantity == 0:
                fehler.append(f"Position {i}: Menge fehlt.")
            if not self.kleinunternehmer and ln.vat_rate not in ERLAUBTE_SAETZE:
                fehler.append(f"Position {i}: Steuersatz {ln.vat_rate} % ist nicht vorgesehen.")
        # Nr. 6: date or period of the supply (not for Kleinbetrag)
        if not self.is_kleinbetrag and not (self.supply_date or self.supply_period):
            fehler.append("Leistungsdatum oder Leistungszeitraum fehlt.")
        if self.supply_period and self.supply_period[0] > self.supply_period[1]:
            fehler.append("Leistungszeitraum: Beginn liegt nach dem Ende.")
        # Nr. 8: tax rate and amount, or a note on the exemption
        if self.kleinunternehmer:
            if any(ln.vat_rate != 0 for ln in self.lines):
                fehler.append(
                    "Kleinunternehmer (§ 19 UStG): keine Umsatzsteuer ausweisen, "
                    "alle Positionen mit 0 %."
                )
            if not self.kleinunternehmer_hinweis.strip():
                fehler.append("Hinweis auf die Steuerbefreiung (§ 19 UStG) fehlt.")
        elif any(ln.vat_rate == 0 for ln in self.lines) and not self.notes.strip():
            fehler.append("Positionen mit 0 %: Hinweis auf den Grund (Steuerbefreiung) fehlt.")
        return fehler

    # ------------------------------------------------------------------
    # Serialisation (stored as JSON in the invoices table)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "supplier": asdict(self.supplier),
            "customer": asdict(self.customer),
            "issue_date": self.issue_date.isoformat(),
            "supply_date": self.supply_date.isoformat() if self.supply_date else None,
            "supply_period": [d.isoformat() for d in self.supply_period]
            if self.supply_period
            else None,
            "lines": [
                {
                    "description": ln.description,
                    "quantity": str(ln.quantity),
                    "unit_net": str(ln.unit_net),
                    "vat_rate": str(ln.vat_rate),
                    "unit": ln.unit,
                }
                for ln in self.lines
            ],
            "notes": self.notes,
            "kleinunternehmer": self.kleinunternehmer,
            "kleinunternehmer_hinweis": self.kleinunternehmer_hinweis,
            "corrects": self.corrects,
            "corrects_date": self.corrects_date.isoformat() if self.corrects_date else None,
            "totals": [
                {"rate": str(t.rate), "net": str(t.net), "vat": str(t.vat)}
                for t in self.rate_totals()
            ],
            "net_total": str(self.net_total),
            "vat_total": str(self.vat_total),
            "gross_total": str(self.gross_total),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Invoice:
        def dt(v):
            return date.fromisoformat(v) if v else None

        period = d.get("supply_period")
        return cls(
            supplier=Party(**d.get("supplier") or {}),
            customer=Party(**d.get("customer") or {}),
            issue_date=dt(d["issue_date"]),
            supply_date=dt(d.get("supply_date")),
            supply_period=(dt(period[0]), dt(period[1])) if period else None,
            lines=[
                InvoiceLine(
                    description=ln.get("description", ""),
                    quantity=Decimal(str(ln.get("quantity", "0"))),
                    unit_net=Decimal(str(ln.get("unit_net", "0"))),
                    vat_rate=Decimal(str(ln.get("vat_rate", "19"))),
                    unit=ln.get("unit", ""),
                )
                for ln in d.get("lines") or []
            ],
            number=d.get("number") or "",
            notes=d.get("notes") or "",
            kleinunternehmer=bool(d.get("kleinunternehmer")),
            kleinunternehmer_hinweis=d.get("kleinunternehmer_hinweis") or KLEINUNTERNEHMER_HINWEIS,
            corrects=d.get("corrects"),
            corrects_date=dt(d.get("corrects_date")),
        )

    def correction(self, issue_date: date) -> Invoice:
        """A cancellation of this invoice: same parties and lines, negative quantities."""
        if not self.number:
            raise ValueError("Nur eine ausgestellte Rechnung (mit Nummer) kann storniert werden.")
        if self.is_correction:
            raise ValueError("Eine Rechnungskorrektur kann nicht erneut storniert werden.")
        return Invoice(
            supplier=self.supplier,
            customer=self.customer,
            issue_date=issue_date,
            supply_date=self.supply_date,
            supply_period=self.supply_period,
            lines=[
                InvoiceLine(ln.description, -ln.quantity, ln.unit_net, ln.vat_rate, ln.unit)
                for ln in self.lines
            ],
            notes=f"Storno der Rechnung Nr. {self.number} vom {self.issue_date:%d.%m.%Y}.",
            kleinunternehmer=self.kleinunternehmer,
            kleinunternehmer_hinweis=self.kleinunternehmer_hinweis,
            corrects=self.number,
            corrects_date=self.issue_date,
        )


@dataclass
class IssuedInvoice:
    """Result of issuing: the numbered invoice, its stored receipt and PDF path."""

    invoice: Invoice
    receipt_id: str
    pdf_path: str
    warnings: list[str] = field(default_factory=list)
