"""
Invoice numbers: ``YYYY-NNNN``, gapless and unique per year (§ 14 Abs. 4 S. 1 Nr. 4 UStG:
"fortlaufende Nummer … die zur Identifizierung der Rechnung einmalig vergeben wird").

Numbers are allocated by :meth:`SQLiteRepository.create_invoice` in the same transaction that
stores the invoice, so a number is never skipped or reused. A cancelled invoice keeps its
number; the cancellation (Rechnungskorrektur) gets the next one.
"""

from __future__ import annotations

import re

_FORMAT = re.compile(r"^(\d{4})-(\d{4,})$")


def format_number(year: int, seq: int) -> str:
    if not 1 <= seq:
        raise ValueError("sequence must start at 1")
    return f"{year}-{seq:04d}"


def parse_number(number: str) -> tuple[int, int]:
    m = _FORMAT.match(number or "")
    if not m:
        raise ValueError(f"Keine Rechnungsnummer im Format JJJJ-NNNN: {number!r}")
    return int(m.group(1)), int(m.group(2))
