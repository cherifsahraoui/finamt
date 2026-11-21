"""
finamt.tax.bundesland
~~~~~~~~~~~~~~~~~~~~~
The 16 Länder in one place, and the Steuernummer → 13-digit ELSTER format check
used by the web UI (Stammdaten page) and the submission pages.

Sources (see docs/tax-rules.md, section "Steuernummer and Land codes"):

- ``kuerzel``: ELSTER ``<Ziel>`` codes, ``BundeslandSType`` in
  ``headerbasis_datentypen.xsd`` (ERiC 44.3 ElsterBasisSchema).
- ``landesnummern``: first two digits of the Bundesfinanzamtsnummern, per Land, from
  ``Finanzamtsdaten.ods`` (ERiC 44.3; BZSt GEMFA data of 01.09.2026), including test
  Finanzämter.
- The conversion itself is :func:`finamt.tax.elster.normalise_steuernummer`, checked against
  ERiC's ``EricMakeElsterStnr`` for all 16 Länder (2026-11-20).

The Prüfziffer (check digit) is **not** checked here; ERiC checks it when a return is
validated or sent.
"""

from __future__ import annotations

from dataclasses import dataclass

from finamt.tax.elster import _BL_STRUCTURE, normalise_steuernummer


@dataclass(frozen=True)
class Bundesland:
    name: str  # full German name; stored in the taxpayer profile field ``state``
    kuerzel: str  # ELSTER <Ziel> code
    kz: str  # Länderschlüssel 01–16; key into elster._BUNDESLAND_ZIEL / _BL_STRUCTURE
    landesnummern: tuple[str, ...]  # first 2 digits of the 13-digit Steuernummer


# Alphabetical, as shown in the dropdown.
BUNDESLAENDER: tuple[Bundesland, ...] = (
    Bundesland("Baden-Württemberg", "BW", "08", ("28",)),
    Bundesland("Bayern", "BY", "09", ("91", "92")),
    Bundesland("Berlin", "BE", "11", ("11",)),
    Bundesland("Brandenburg", "BB", "12", ("30",)),
    Bundesland("Bremen", "HB", "04", ("24",)),
    Bundesland("Hamburg", "HH", "02", ("22",)),
    Bundesland("Hessen", "HE", "06", ("26",)),
    Bundesland("Mecklenburg-Vorpommern", "MV", "13", ("40",)),
    Bundesland("Niedersachsen", "NI", "03", ("23",)),
    Bundesland("Nordrhein-Westfalen", "NW", "05", ("51", "52", "53", "54", "55", "56")),
    Bundesland("Rheinland-Pfalz", "RP", "07", ("27",)),
    Bundesland("Saarland", "SL", "10", ("10",)),
    Bundesland("Sachsen", "SN", "14", ("32",)),
    Bundesland("Sachsen-Anhalt", "ST", "15", ("31",)),
    Bundesland("Schleswig-Holstein", "SH", "01", ("21",)),
    Bundesland("Thüringen", "TH", "16", ("41",)),
)


def bundesland_by_name(value: str | None) -> Bundesland | None:
    """Find a Land by its full name or ELSTER code (case-insensitive). ``None`` if unknown."""
    if not value:
        return None
    v = value.strip().lower()
    for land in BUNDESLAENDER:
        if v in (land.name.lower(), land.kuerzel.lower()):
            return land
    return None


@dataclass(frozen=True)
class SteuernummerInfo:
    """Result of :func:`steuernummer_info`. Either ``elster13`` is set, or ``fehler``."""

    elster13: str | None = None
    finanzamt_nr: str | None = None
    fehler: str | None = None


def _local_length(land: Bundesland) -> int:
    """Number of digits of the Steuernummer as printed on the Bescheid, for this Land."""
    prefix, fa_offset, fa_len = _BL_STRUCTURE[land.kz]
    rest = 13 - len(prefix) - fa_len - 1
    return fa_offset + fa_len + rest


def steuernummer_info(raw: str | None, land: Bundesland | None) -> SteuernummerInfo:
    """
    Convert a Steuernummer (as on the Bescheid, or already 13 digits) to the ELSTER format.

    Returns a German error message naming the wrong input instead of guessing.
    """
    if land is None:
        return SteuernummerInfo(fehler="Bundesland fehlt.")
    if not raw or not raw.strip():
        return SteuernummerInfo(fehler="Steuernummer fehlt.")
    if any(c.isalpha() for c in raw):
        return SteuernummerInfo(
            fehler="Steuernummer darf nur Ziffern, / und Leerzeichen enthalten."
        )
    digits = "".join(c for c in raw if c.isdigit())

    if len(digits) == 13:
        elster13 = digits
    else:
        expected = _local_length(land)
        if len(digits) != expected:
            return SteuernummerInfo(
                fehler=(
                    f"Steuernummer hat {len(digits)} Ziffern; für {land.name} sind {expected} "
                    "nötig (so wie auf dem Steuerbescheid, mit Finanzamtsnummer) "
                    "oder die 13-stellige ELSTER-Steuernummer."
                )
            )
        elster13 = normalise_steuernummer(digits, land.kz)

    if elster13[:2] not in land.landesnummern:
        return SteuernummerInfo(
            fehler=(
                f"Finanzamtsnummer {elster13[:4]} gehört nicht zu {land.name}. "
                "Bundesland oder Steuernummer prüfen."
            )
        )
    return SteuernummerInfo(elster13=elster13, finanzamt_nr=elster13[:4])


__all__ = [
    "BUNDESLAENDER",
    "Bundesland",
    "SteuernummerInfo",
    "bundesland_by_name",
    "steuernummer_info",
]
