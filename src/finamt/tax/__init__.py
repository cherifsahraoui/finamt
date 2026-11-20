"""
finamt.tax
~~~~~~~~~~~~~
Tax computation modules for a single Freiberufler.

In scope:
  - ``ustva``       — Umsatzsteuer-Voranmeldung (UStVA) and annual USt figures
  - ``assets``      — asset register and AfA for the EÜR (EUR-3)
  - ``eur``         — Einnahmen-Überschuss-Rechnung (EÜR, § 4 Abs. 3 EStG)
  - ``elster``      — ELSTER XML for UStVA / USt (E50) and ERiC submission
  - ``zm``          — Zusammenfassende Meldung (§ 18a UStG), calculation only
  - ``eur_elster``  — Anlage EÜR 2025 ELSTER XML (test builds), ERiC validation, submit
  - ``safety``      — live-submission gate (FINAMT_ALLOW_LIVE_SUBMISSION)

Out of scope (moved to ``legacy/``, see NOTICE.md): KSt, GewSt, E-Bilanz,
Jahresabschluss. Einkommensteuer is not implemented.
"""

from .assets import Asset, afa_for_year
from .eur import EURLinie, EURReport, generate_eur
from .ustva import USTVALineItem, USTVAReport, generate_ustva
from .zm import ZMLine, ZMReport, generate_zm

__all__ = [
    "Asset",
    "afa_for_year",
    "USTVAReport",
    "USTVALineItem",
    "generate_ustva",
    "EURReport",
    "EURLinie",
    "generate_eur",
    "ZMReport",
    "ZMLine",
    "generate_zm",
]
