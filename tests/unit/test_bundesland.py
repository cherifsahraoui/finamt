"""
Tests for finamt.tax.bundesland and the ELSTER <Ziel> mapping.

The expected 13-digit numbers were produced by ERiC 44.3 ``EricMakeElsterStnr`` on
2026-11-20 (see docs/tax-rules.md, "Steuernummer and Land codes"). No ERiC is needed here.
"""

from __future__ import annotations

import pytest

from finamt.tax.bundesland import BUNDESLAENDER, bundesland_by_name, steuernummer_info
from finamt.tax.elster import _BL_STRUCTURE, _bundesland_ziel

# BundeslandSType codes for the 16 Länder (headerbasis_datentypen.xsd, ERiC 44.3)
XSD_LAND_CODES = {
    "BB", "BE", "BW", "BY", "HB", "HE", "HH", "MV",
    "NI", "NW", "RP", "SH", "SL", "SN", "ST", "TH",
}  # fmt: skip

# (Land, Steuernummer as on the Bescheid, ERiC result)
ERIC_CASES = [
    ("Baden-Württemberg", "93123/45671", "2893012345671"),
    ("Bayern", "101/123/45677", "9101012345677"),
    ("Bayern", "201/123/45672", "9201012345672"),
    ("Berlin", "13/123/45673", "1113012345673"),
    ("Brandenburg", "046/123/45673", "3046012345673"),
    ("Bremen", "60/123/45672", "2460012345672"),
    ("Hamburg", "17/123/45671", "2217012345671"),
    ("Hessen", "001/123/45678", "2601012345678"),
    ("Mecklenburg-Vorpommern", "079/123/45674", "4079012345674"),
    ("Niedersachsen", "17/123/08154", "2317012308154"),
    ("Nordrhein-Westfalen", "103/1234/5672", "5103012345672"),
    ("Nordrhein-Westfalen", "305/1234/4564", "5305012344564"),
    ("Rheinland-Pfalz", "01/123/45677", "2701012345677"),
    ("Saarland", "010/123/45670", "1010012345670"),
    ("Sachsen", "202/123/08154", "3202012308154"),
    ("Sachsen-Anhalt", "102/123/45674", "3102012345674"),
    ("Schleswig-Holstein", "11/123/45677", "2111012345677"),
    ("Thüringen", "151/123/45679", "4151012345679"),
]


class TestBundeslaender:
    def test_sixteen_unique_laender(self):
        assert len(BUNDESLAENDER) == 16
        assert len({b.name for b in BUNDESLAENDER}) == 16
        assert {b.kuerzel for b in BUNDESLAENDER} == XSD_LAND_CODES

    def test_every_kz_known_to_elster_tables(self):
        for land in BUNDESLAENDER:
            assert land.kz in _BL_STRUCTURE
            assert _bundesland_ziel(land.kz) == land.kuerzel

    def test_lookup_by_name_or_code(self):
        assert bundesland_by_name("nordrhein-westfalen").kuerzel == "NW"
        assert bundesland_by_name(" BY ").name == "Bayern"
        assert bundesland_by_name("Atlantis") is None
        assert bundesland_by_name("") is None


class TestZiel:
    @pytest.mark.parametrize("prefix", sorted({s[0] for s in _BL_STRUCTURE.values()}))
    def test_13_digit_prefix_maps_to_xsd_code(self, prefix):
        # The pre-built UI sends these prefixes as bundesland_kz.
        assert _bundesland_ziel(prefix) in XSD_LAND_CODES

    @pytest.mark.parametrize("kz", [f"{i:02d}" for i in range(1, 17)])
    def test_laenderschluessel_maps_to_xsd_code(self, kz):
        assert _bundesland_ziel(kz) in XSD_LAND_CODES

    def test_prefix_and_schluessel_agree(self):
        for land in BUNDESLAENDER:
            prefix = _BL_STRUCTURE[land.kz][0]
            assert _bundesland_ziel(prefix) == land.kuerzel


class TestSteuernummerInfo:
    @pytest.mark.parametrize("land_name,raw,expected", ERIC_CASES)
    def test_matches_eric(self, land_name, raw, expected):
        info = steuernummer_info(raw, bundesland_by_name(land_name))
        assert info.fehler is None
        assert info.elster13 == expected
        assert info.finanzamt_nr == expected[:4]

    def test_official_test_number(self):
        # ERiC handbook Kap. 6.5.4: 198/113/10010 = 9198011310010 (test Finanzamt 9198)
        info = steuernummer_info("198/113/10010", bundesland_by_name("Bayern"))
        assert info.elster13 == "9198011310010"
        assert info.finanzamt_nr == "9198"

    def test_13_digit_input_kept(self):
        info = steuernummer_info("9198 0 123 45678".replace(" ", ""), bundesland_by_name("Bayern"))
        assert info.elster13 == "9198012345678"
        assert info.finanzamt_nr == "9198"

    def test_wrong_digit_count_names_the_problem(self):
        info = steuernummer_info("123/4567", bundesland_by_name("Bayern"))
        assert info.elster13 is None
        assert "7 Ziffern" in info.fehler
        assert "11" in info.fehler

    def test_13_digit_number_of_other_land(self):
        info = steuernummer_info("2893012345671", bundesland_by_name("Bayern"))
        assert "2893" in info.fehler
        assert "Bayern" in info.fehler

    def test_missing_land(self):
        assert steuernummer_info("101/123/45677", None).fehler == "Bundesland fehlt."

    def test_missing_number(self):
        assert steuernummer_info("  ", bundesland_by_name("Berlin")).fehler == "Steuernummer fehlt."

    def test_letters_rejected(self):
        assert (
            "nur Ziffern" in steuernummer_info("12/abc/4567", bundesland_by_name("Berlin")).fehler
        )
