"""
finamt.tax.assets
~~~~~~~~~~~~~~~~~
Asset register and yearly depreciation (AfA) for the EÜR (task EUR-3, decision D11).

Two methods:

``linear``
    Straight-line AfA over a useful life that **the owner supplies** per asset (§ 7 Abs. 1 EStG,
    useful life from the official AfA tables). No table values are hard-coded here: a value
    nobody verified would be a guess. First and last year are pro rata temporis by whole
    months, counting the month of acquisition (§ 7 Abs. 1 S. 4 EStG).

``computer_one_year``
    One-year useful life for computer hardware (incl. peripherals) and operating / application
    software (BMF letter of 22.02.2022, IV C 3 - S 2190/21/10002 :025, Rz. 1–5; it replaced
    the letter of 26.02.2021). Using it is optional (Rz. 1, 1.2). It is an ordinary § 7 Abs. 1
    AfA, **not** a Sofortabschreibung (Rz. 1.1), so it goes to Kz 130 / 131 and Anlage AVEÜR,
    not to GWG Kz 132. Rz. 1.4: the full cost may be written off in the acquisition year
    (the monthly split of § 7 Abs. 1 S. 4 EStG is not objected to). The asset must be in the
    Bestandsverzeichnis (Rz. 1.2), which is what the register is. Applies to Wirtschaftsjahre
    ending after 31.12.2020; older assets may switch (Rz. 6). The category check (Rz. 2–5,
    including the EU 617/2013 condition of Rz. 4) is the owner's call when adding the asset.

Kennzahl: tangible assets (hardware, furniture) → Kz 130, intangible assets (purchased
software) → Kz 131. Anlage AVEÜR is not built yet (EUR-3b); until then the EÜR XML refuses
AfA lines.

Not implemented: Sammelposten (§ 6 Abs. 2a EStG, Kz 137), disposals / Restwert, Teilwert,
degressive or special AfA.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

LINEAR = "linear"
COMPUTER_ONE_YEAR = "computer_one_year"
METHODS = (LINEAR, COMPUTER_ONE_YEAR)

KZ_TANGIBLE = "130"
KZ_INTANGIBLE = "131"

_CENT = Decimal("0.01")


def _r(d: Decimal) -> Decimal:
    return d.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Asset:
    """One depreciable asset.

    ``cost`` is the business cost basis: net of deductible VAT for a regular taxpayer, gross
    for a Kleinunternehmer, already reduced by the private-use share.
    ``receipt_id`` links the purchase receipt, so it is not also sent to review.
    """

    description: str
    acquisition_date: date
    cost: Decimal
    method: str = LINEAR
    useful_life_years: int | None = None
    intangible: bool = False
    receipt_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.cost, Decimal):
            raise TypeError("cost must be a Decimal")
        if self.cost <= 0:
            raise ValueError("cost must be positive")
        if self.method not in METHODS:
            raise ValueError(f"method must be one of {METHODS}, got {self.method!r}")
        if self.method == LINEAR and (self.useful_life_years is None or self.useful_life_years < 1):
            raise ValueError(
                "linear AfA needs useful_life_years >= 1 (from the official AfA table)"
            )

    @property
    def kz(self) -> str:
        return KZ_INTANGIBLE if self.intangible else KZ_TANGIBLE

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "acquisition_date": self.acquisition_date.isoformat(),
            "cost": str(self.cost),
            "method": self.method,
            "useful_life_years": self.useful_life_years,
            "intangible": self.intangible,
            "receipt_id": self.receipt_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Asset:
        return cls(
            description=d["description"],
            acquisition_date=date.fromisoformat(d["acquisition_date"]),
            cost=Decimal(str(d["cost"])),
            method=d.get("method", LINEAR),
            useful_life_years=d.get("useful_life_years"),
            intangible=bool(d.get("intangible", False)),
            receipt_id=d.get("receipt_id"),
        )


def afa_for_year(asset: Asset, year: int) -> Decimal:
    """AfA of ``asset`` booked in ``year`` (0 before the acquisition year or once written off)."""
    first = asset.acquisition_date.year
    if year < first:
        return Decimal("0")
    if asset.method == COMPUTER_ONE_YEAR:
        return _r(asset.cost) if year == first else Decimal("0")

    life = asset.useful_life_years or 1
    months_total = life * 12
    start_month = asset.acquisition_date.month  # month of acquisition counts fully
    months_before = 0 if year == first else 12 - start_month + 1 + (year - first - 1) * 12
    if months_before >= months_total:
        return Decimal("0")
    months_in_year = min(
        12 - start_month + 1 if year == first else 12, months_total - months_before
    )
    yearly = asset.cost / Decimal(life)
    booked_before = _r(yearly * Decimal(months_before) / Decimal(12))
    booked_through = _r(yearly * Decimal(months_before + months_in_year) / Decimal(12))
    if months_before + months_in_year == months_total:
        booked_through = _r(asset.cost)  # no rounding remainder: the cost is written off fully
    return _r(booked_through - booked_before)


def restwert(asset: Asset, year: int) -> Decimal:
    """Book value at 31 December of ``year`` (before the acquisition year: 0)."""
    if year < asset.acquisition_date.year:
        return Decimal("0")
    total = sum(
        (afa_for_year(asset, y) for y in range(asset.acquisition_date.year, year + 1)),
        Decimal("0"),
    )
    return _r(asset.cost - total)
