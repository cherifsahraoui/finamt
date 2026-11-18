"""
finamt.tax
~~~~~~~~~~~~~
Tax computation modules for a single Freiberufler.

In scope:
  - ``ustva``       — Umsatzsteuer-Voranmeldung (UStVA) and annual USt figures
  - ``eur``         — Einnahmen-Überschuss-Rechnung (EÜR, § 4 Abs. 3 EStG)
  - ``elster``      — ELSTER XML for UStVA / USt (E50) and ERiC submission
  - ``eur_elster``  — EÜR ELSTER boundary (XML builder not implemented yet)
  - ``safety``      — live-submission gate (FINAMT_ALLOW_LIVE_SUBMISSION)

Out of scope (moved to ``legacy/``, see NOTICE.md): KSt, GewSt, E-Bilanz,
Jahresabschluss. Einkommensteuer is not implemented.
"""

from .eur import EURLinie, EURReport, generate_eur
from .ustva import USTVALineItem, USTVAReport, generate_ustva

__all__ = [
    "USTVAReport",
    "USTVALineItem",
    "generate_ustva",
    "EURReport",
    "EURLinie",
    "generate_eur",
]
