"""
tests/unit/test_aveuer.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Anlage AVEÜR built from the asset register (EUR-3b, decision D11). Offline: the XML is
checked against the element names and sums in docs/tax-rules.md ("Anlage AVEÜR 2025").
ERiC validation of the same XML is in test_eur_elster.py::TestRealEric (skipped without
ERIC_LIBRARY_PATH).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from lxml import etree

from finamt.tax import eur_elster
from finamt.tax.assets import COMPUTER_ONE_YEAR, LINEAR, Asset
from finamt.tax.eur import generate_eur

NS = {"e": eur_elster.E77_NS, "t": eur_elster.NS}

TAXPAYER = eur_elster.EURTaxpayer(
    name="Testfall FreiBuch",
    street="Testgasse 1",
    postal_code="12345",
    city="Musterstadt",
    steuernummer="9198011310010",  # official ERiC test tax number (test Finanzamt 9198)
    art_des_betriebs="IT-Beratung",
    grundstuecke_entnommen=False,
)


def _register() -> list[Asset]:
    return [
        Asset("Büro-Möbel", date(2025, 3, 1), Decimal("2400.00"), LINEAR, useful_life_years=10),
        Asset("Laptop", date(2025, 5, 3), Decimal("1499.00"), COMPUTER_ONE_YEAR),
        Asset(
            "Buchhaltungs-Software",
            date(2025, 1, 10),
            Decimal("1200.50"),
            LINEAR,
            useful_life_years=3,
            intangible=True,
        ),
    ]


def _build(report, assets=()) -> etree._Element:
    xml = eur_elster.build_xml(
        report,
        TAXPAYER,
        entnahmen=Decimal("0"),
        einlagen=Decimal("0"),
        hersteller_id="12345",
        assets=assets,
    )
    return etree.fromstring(xml)


def _text(root, path: str) -> str | None:
    el = root.find(path, NS)
    return None if el is None else el.text


def _euer_afa(root, kz_path: str) -> str | None:
    return _text(root, f".//e:EUER/e:BAus/e:AfA/e:{kz_path}")


class TestAnlageAveuer:
    def test_sums_equal_the_eur_afa_lines(self):
        assets = _register()
        report = generate_eur([], 2025, assets=assets)
        root = _build(report, assets)

        # Software 1200.50 / 3 years, full year → 400.17 (Kz 131); the furniture 2400 / 10 for
        # 10 months = 200.00 plus the laptop 1499.00 (one-year life) → 1699.00 (Kz 130).
        assert _euer_afa(root, "E6002001") == "400,17"
        assert _text(root, ".//e:AVEUER/e:Immaterielle_WG/e:Sum/e:E6007227") == "400,17"
        assert _euer_afa(root, "E6002101") == "1699,00"
        assert _text(root, ".//e:AVEUER/e:Bewegliche_WG/e:GesamtSum/e:E6007372") == "1699,00"
        assert _text(root, ".//e:AVEUER/e:Bewegliche_WG/e:Andere/e:Sum/e:E6007361") == "1699,00"

    def test_einz_rows_follow_the_roll_forward(self):
        assets = _register()
        root = _build(generate_eur([], 2025, assets=assets), assets)
        rows = root.findall(".//e:AVEUER/e:Bewegliche_WG/e:Andere/e:Einz", NS)
        assert len(rows) == 2
        intangible = root.findall(".//e:AVEUER/e:Immaterielle_WG/e:Einz", NS)
        assert len(intangible) == 1
        names = {
            "intangible": ("E6007246", "E6007247", "E6007248", "E6007250"),
            "tangible": ("E6007354", "E6007356", "E6007360", "E6007364"),
        }
        for kind, group in (("intangible", intangible), ("tangible", rows)):
            beg, zug, afa, end = names[kind]
            for einz in group:
                values = {
                    c.tag.split("}")[1]: Decimal(c.text.replace(",", "."))
                    for c in einz
                    if c.tag.split("}")[1] in (beg, zug, afa, end)
                }
                assert values[beg] + values[zug] - values[afa] == values[end], values

    def test_second_year_starts_from_the_book_value(self):
        # 1200 over 5 years, bought 1 July 2023: 2023 = 120, 2024 = 240, 2025 = 240.
        asset = Asset("Drucker", date(2023, 7, 1), Decimal("1200.00"), LINEAR, useful_life_years=5)
        report = generate_eur([], 2025, assets=[asset])
        root = _build(report, [asset])
        assert _euer_afa(root, "E6002101") == "240,00"
        einz = root.find(".//e:AVEUER/e:Bewegliche_WG/e:Andere/e:Einz", NS)
        assert _text(einz, "e:E6007354") == "840,00"  # Buchwert zu Beginn
        assert _text(einz, "e:E6007356") == "0,00"  # no Zugang in 2025
        assert _text(einz, "e:E6007360") == "240,00"  # AfA
        assert _text(einz, "e:E6007364") == "600,00"  # Buchwert am Ende

    def test_element_order_and_position(self):
        assets = _register()
        root = _build(generate_eur([], 2025, assets=assets), assets)
        e77 = root.find(".//e:E77", NS)
        order = [etree.QName(c).localname for c in e77]
        assert order == ["EUER", "AVEUER", "Vorsatz"]
        aveuer = e77.find("e:AVEUER", NS)
        assert [etree.QName(c).localname for c in aveuer] == ["Immaterielle_WG", "Bewegliche_WG"]
        bewegliche = aveuer.find("e:Bewegliche_WG", NS)
        assert [etree.QName(c).localname for c in bewegliche] == ["Andere", "GesamtSum"]

    def test_no_aveuer_without_assets(self):
        root = _build(generate_eur([], 2025))
        assert root.find(".//e:AVEUER", NS) is None

    def test_assets_bought_later_or_written_off_are_left_out(self):
        future = Asset("Zukunft", date(2026, 2, 1), Decimal("900.00"), LINEAR, useful_life_years=3)
        old = Asset("Alt", date(2010, 1, 1), Decimal("900.00"), LINEAR, useful_life_years=3)
        assets = [future, old]
        root = _build(generate_eur([], 2025, assets=assets), assets)
        assert root.find(".//e:AVEUER", NS) is None
        assert _euer_afa(root, "E6002101") is None

    def test_register_without_report_lines_is_refused(self):
        assets = _register()
        report = generate_eur([], 2025)  # built without the register
        with pytest.raises(ValueError, match="asset register"):
            _build(report, assets)

    def test_report_with_afa_but_no_register_is_refused(self):
        report = generate_eur([], 2025, assets=_register())
        with pytest.raises(ValueError, match="asset register"):
            _build(report, ())

    def test_blank_description_is_refused(self):
        asset = Asset("   ", date(2025, 5, 3), Decimal("500.00"), COMPUTER_ONE_YEAR)
        report = generate_eur([], 2025, assets=[asset])
        with pytest.raises(ValueError, match="asset description"):
            _build(report, [asset])

    def test_live_build_still_refused(self):
        assets = _register()
        report = generate_eur([], 2025, assets=assets)
        with pytest.raises(NotImplementedError):
            eur_elster.build_xml(
                report,
                TAXPAYER,
                entnahmen=Decimal("0"),
                einlagen=Decimal("0"),
                hersteller_id="12345",
                test=False,
                assets=assets,
            )


class TestAssetsCli:
    """`finamt assets add / list` writes to and reads from the project DB (tmp_path here)."""

    @pytest.fixture
    def db(self, tmp_path):
        return tmp_path / "assets.db"

    def _run(self, *args):
        from typer.testing import CliRunner

        from finamt.cli import app

        return CliRunner().invoke(app, list(args))

    def test_add_then_list(self, db):
        added = self._run(
            "assets",
            "add",
            "--description",
            "Laptop",
            "--acquired",
            "2025-05-03",
            "--cost",
            "1499.00",
            "--method",
            "computer_one_year",
            "--db",
            str(db),
        )
        assert added.exit_code == 0, added.output
        assert "Kz 130" in added.output

        listed = self._run("assets", "list", "--db", str(db))
        assert listed.exit_code == 0, listed.output
        assert "1499.00 EUR" in listed.output and "Laptop" in listed.output

    def test_invalid_cost_is_refused(self, db):
        result = self._run(
            "assets",
            "add",
            "--description",
            "Laptop",
            "--acquired",
            "2025-05-03",
            "--cost",
            "1,5",
            "--method",
            "computer_one_year",
            "--db",
            str(db),
        )
        assert result.exit_code == 1

    def test_linear_without_life_is_refused(self, db):
        result = self._run(
            "assets",
            "add",
            "--description",
            "Schreibtisch",
            "--acquired",
            "2025-05-03",
            "--cost",
            "800.00",
            "--db",
            str(db),
        )
        assert result.exit_code == 1
