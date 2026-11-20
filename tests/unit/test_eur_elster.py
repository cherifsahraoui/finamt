"""
tests/unit/test_eur_elster.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
EÜR ELSTER boundary: Anlage EÜR 2025 XML builder (golden XML, refusals), local
validation, ERiC validation and submit modes.

Offline: ERiC is replaced by fakes. The one test that loads the real library
(``TestRealEric``) skips unless ERIC_LIBRARY_PATH and FINAMT_ELSTER_HERSTELLER_ID are set.
"""

from __future__ import annotations

import os
from dataclasses import replace
from decimal import Decimal

import pytest
from lxml import etree

from finamt.tax import eur_elster
from finamt.tax.elster import NS, TESTMERKER, ElsterConfig
from finamt.tax.eur import EURLinie, EURReport
from finamt.tax.safety import LIVE_SUBMISSION_ENV

# Read at import: the autouse fixture below clears ERIC_LIBRARY_PATH for every test.
_REAL_ERIC_PATH = os.environ.get(eur_elster.ERIC_LIBRARY_ENV, "").strip()
_REAL_HERSTELLER_ID = os.environ.get("FINAMT_ELSTER_HERSTELLER_ID", "").strip()

E77 = eur_elster.E77_NS
TAXPAYER = eur_elster.EURTaxpayer(
    name="Testfall FreiBuch",
    street="Testgasse 1",
    postal_code="12345",
    city="Musterstadt",
    steuernummer="9198011310010",  # official ERiC test tax number (test Finanzamt 9198)
    art_des_betriebs="IT-Beratung",
    grundstuecke_entnommen=False,
)


def _envelope(*, testmerker: bool = True, nutzdaten: bool = True) -> bytes:
    tm = f"<Testmerker>{TESTMERKER}</Testmerker>" if testmerker else ""
    nd = "<Nutzdaten><X/></Nutzdaten>" if nutzdaten else ""
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Elster xmlns="{NS}">'
        f"<TransferHeader><Verfahren>V</Verfahren><DatenArt>D</DatenArt>{tm}</TransferHeader>"
        f"<DatenTeil><Nutzdatenblock>{nd}</Nutzdatenblock></DatenTeil>"
        f"</Elster>"
    ).encode()


def _cfg() -> ElsterConfig:
    return ElsterConfig(
        cert_path="/nonexistent/test.pfx",
        cert_password="secret",
        steuernummer="21/815/08150",
        finanzamt_nr="2181",
        bundesland_kz="21",
    )


def _report(income: dict[str, str], expenses: dict[str, str], year: int = 2025) -> EURReport:
    r = EURReport(year=year)
    for kz, amount in income.items():
        r.einnahmen_lines[kz] = EURLinie(category=kz, kz=kz, label="x", net_amount=Decimal(amount))
    for kz, amount in expenses.items():
        r.ausgaben_lines[kz] = EURLinie(category=kz, kz=kz, label="x", net_amount=Decimal(amount))
    return r


def _golden_report() -> EURReport:
    """Fixed report with VAT lines (as EUR-2 will produce) and a non-deductible gift."""
    return _report(
        {"112": "12000.00", "140": "2280.00", "103": "500.50"},
        {
            "110": "3000.00",
            "228": "1234.56",
            "185": "400.10",
            "186": "1500.00",
            "164": "60.00",
            "174": "35.00",
        },
    )


def _build(report: EURReport, **kwargs) -> bytes:
    kwargs.setdefault("entnahmen", Decimal("20000"))
    kwargs.setdefault("einlagen", Decimal("1500"))
    kwargs.setdefault("hersteller_id", "12345")
    taxpayer = kwargs.pop("taxpayer", TAXPAYER)
    return eur_elster.build_xml(report, taxpayer, **kwargs)


def _canonical(xml: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=True)
    return etree.tostring(etree.fromstring(xml, parser), method="c14n")


def _e77_text(xml: bytes, path: str) -> str | None:
    steps = "/".join(f"e:{p}" for p in path.split("/"))
    el = etree.fromstring(xml).find(f".//e:E77/{steps}", {"e": E77})
    return None if el is None else el.text


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(eur_elster.ERIC_LIBRARY_ENV, raising=False)
    monkeypatch.delenv("FINAMT_ERIC_HOME", raising=False)


@pytest.fixture
def no_eric(monkeypatch):
    """Fail the test if ERiC would be loaded."""

    def _boom(*_a, **_k):
        raise AssertionError("ERiC must not be loaded in this test")

    monkeypatch.setattr(eur_elster, "EricSession", _boom)


# Golden output for _golden_report(). It validates in ERiC 44.3.6.0 (validation only,
# 2026-11-20). Whitespace does not matter: the test compares canonical XML.
GOLDEN_XML = b"""<?xml version='1.0' encoding='UTF-8'?>
<Elster xmlns="http://www.elster.de/elsterxml/schema/v11">
  <TransferHeader version="11">
    <Verfahren>ElsterErklaerung</Verfahren>
    <DatenArt>EUER</DatenArt>
    <Vorgang>send-Auth</Vorgang>
    <Testmerker>700000004</Testmerker>
    <HerstellerID>12345</HerstellerID>
    <DatenLieferant>Testfall FreiBuch</DatenLieferant>
    <Datei>
      <Verschluesselung>CMSEncryptedData</Verschluesselung>
      <Kompression>GZIP</Kompression>
      <TransportSchluessel/>
    </Datei>
  </TransferHeader>
  <DatenTeil>
    <Nutzdatenblock>
      <NutzdatenHeader version="11">
        <NutzdatenTicket>1</NutzdatenTicket>
        <Empfaenger id="F">9198</Empfaenger>
        <Hersteller>
          <ProduktName>finamt</ProduktName>
          <ProduktVersion>0.1</ProduktVersion>
        </Hersteller>
      </NutzdatenHeader>
      <Nutzdaten>
        <E77 xmlns="http://finkonsens.de/elster/elstererklaerung/euer/e77/v2025" version="2025">
          <EUER>
            <Allg>
              <E6000016>Testfall FreiBuch</E6000016>
              <E6000023>Testgasse 1</E6000023>
              <E6000024>12345</E6000024>
              <E6000025>Musterstadt</E6000025>
              <E6000017>IT-Beratung</E6000017>
              <E6000602>140</E6000602>
              <E6000603>3</E6000603>
              <E6000604>1</E6000604>
              <E6000019>2</E6000019>
            </Allg>
            <BEin>
              <USt_StPflicht><Sum><E6000401>12000,00</E6000401></Sum></USt_StPflicht>
              <USt_StFrei><Sum><E6000501>500,50</E6000501></Sum></USt_StFrei>
              <USt_Vereinnahmt_Unentgeltl>
                <Sum><E6000601>2280,00</E6000601></Sum>
              </USt_Vereinnahmt_Unentgeltl>
              <GesamtSum><E6001201>14780,50</E6001201></GesamtSum>
            </BEin>
            <BAus>
              <Fremdleistung><Sum><E6001701>3000,00</E6001701></Sum></Fremdleistung>
              <Sonst_unbeschraenkt>
                <EDV><Sum><E6004405>1234,56</E6004405></Sum></EDV>
                <Vorsteuer><Sum><E6005001>400,10</E6005001></Sum></Vorsteuer>
                <USt><Sum><E6005101>1500,00</E6005101></Sum></USt>
              </Sonst_unbeschraenkt>
              <Beschr_abziehbar>
                <Nicht_abziehbar>
                  <Geschenke><Sum><E6004001>60,00</E6004001></Sum></Geschenke>
                </Nicht_abziehbar>
                <Abziehbar>
                  <Geschenke><Sum><E6004002>35,00</E6004002></Sum></Geschenke>
                </Abziehbar>
              </Beschr_abziehbar>
              <Summe_BAus><E6005301>6169,66</E6005301></Summe_BAus>
            </BAus>
            <Ermittlung_Gewinn>
              <Uebertrag>
                <E6005501>14780,50</E6005501>
                <E6005601>6169,66</E6005601>
              </Uebertrag>
              <Korrektur_GuV><E6006801>8610,84</E6006801></Korrektur_GuV>
              <Stpfl_GuV>
                <E6007002>8610,84</E6007002>
                <E6007202>8610,84</E6007202>
              </Stpfl_GuV>
            </Ermittlung_Gewinn>
            <Zus_Angabe_EinzelUntern>
              <Entnahme_Einlage>
                <Entnahme><Sum><E6006601>20000,00</E6006601></Sum></Entnahme>
                <Einlage><Sum><E6006701>1500,00</E6006701></Sum></Einlage>
              </Entnahme_Einlage>
            </Zus_Angabe_EinzelUntern>
          </EUER>
          <Vorsatz>
            <Unterfallart>77</Unterfallart>
            <Vorgang>01</Vorgang>
            <StNr>9198011310010</StNr>
            <Zeitraum>2025</Zeitraum>
            <AbsName>Testfall FreiBuch</AbsName>
            <AbsStr>Testgasse 1</AbsStr>
            <AbsPlz>12345</AbsPlz>
            <AbsOrt>Musterstadt</AbsOrt>
            <Copyright>(c) FreiBuch contributors, AGPL-3.0</Copyright>
            <OrdNrArt>S</OrdNrArt>
            <Rueckuebermittlung><Bescheid>2</Bescheid></Rueckuebermittlung>
          </Vorsatz>
        </E77>
      </Nutzdaten>
    </Nutzdatenblock>
  </DatenTeil>
</Elster>
"""


class TestFormatAmount:
    @pytest.mark.parametrize(
        ("amount", "signed", "expected"),
        [
            ("10", True, "10,00"),
            ("1234.5", True, "1234,50"),
            ("0.005", True, "0,01"),  # ROUND_HALF_UP
            ("-12.34", True, "-12,34"),
            ("0", False, "0,00"),
            ("-0.001", True, "0,00"),  # never "-0,00"
            ("0.5", False, "0,50"),
        ],
    )
    def test_decimal_comma(self, amount, signed, expected):
        assert eur_elster.format_amount(Decimal(amount), signed=signed) == expected

    def test_unsigned_rejects_negative(self):
        with pytest.raises(ValueError, match="negative"):
            eur_elster.format_amount(Decimal("-1"), signed=False)

    def test_more_than_12_digits(self):
        with pytest.raises(ValueError, match="12 digits"):
            eur_elster.format_amount(Decimal("1000000000000"))

    def test_only_decimal(self):
        with pytest.raises(TypeError):
            eur_elster.format_amount(10)  # type: ignore[arg-type]


class TestBuildXmlGolden:
    def test_matches_golden_xml(self):
        assert _canonical(_build(_golden_report())) == _canonical(GOLDEN_XML)

    def test_passes_local_checks(self):
        xml = _build(_golden_report())
        assert eur_elster.validate(xml) == []
        assert eur_elster.has_testmerker(xml)

    def test_dry_run_accepts_it(self, no_eric):
        assert eur_elster.submit(_build(_golden_report())).success is True

    def test_deterministic(self):
        assert _build(_golden_report()) == _build(_golden_report())


class TestBuildXmlContent:
    def test_non_deductible_gifts_not_in_total(self):
        xml = _build(_report({}, {"183": "100.00", "164": "40.00", "165": "30.00"}))
        assert _e77_text(xml, "EUER/BAus/Summe_BAus/E6005301") == "100,00"
        assert _e77_text(xml, "EUER/Ermittlung_Gewinn/Stpfl_GuV/E6007202") == "-100,00"

    def test_loss_is_negative(self):
        xml = _build(_report({"103": "100.00"}, {"183": "5000.00"}))
        assert _e77_text(xml, "EUER/BEin/GesamtSum/E6001201") == "100,00"
        assert _e77_text(xml, "EUER/Ermittlung_Gewinn/Korrektur_GuV/E6006801") == "-4900,00"
        assert _e77_text(xml, "EUER/Ermittlung_Gewinn/Stpfl_GuV/E6007002") == "-4900,00"

    def test_empty_report_sends_totals_and_profit_lines(self):
        xml = _build(_report({}, {}), entnahmen=Decimal("0"), einlagen=Decimal("0"))
        for path in (
            "EUER/BEin/GesamtSum/E6001201",
            "EUER/BAus/Summe_BAus/E6005301",
            "EUER/Ermittlung_Gewinn/Uebertrag/E6005501",
            "EUER/Ermittlung_Gewinn/Uebertrag/E6005601",
            "EUER/Ermittlung_Gewinn/Korrektur_GuV/E6006801",
            "EUER/Ermittlung_Gewinn/Stpfl_GuV/E6007002",
            "EUER/Ermittlung_Gewinn/Stpfl_GuV/E6007202",
            "EUER/Zus_Angabe_EinzelUntern/Entnahme_Einlage/Entnahme/Sum/E6006601",
            "EUER/Zus_Angabe_EinzelUntern/Entnahme_Einlage/Einlage/Sum/E6006701",
        ):
            assert _e77_text(xml, path) == "0,00", path

    def test_zero_kennzahl_left_out(self):
        xml = _build(_report({"103": "100.00"}, {"183": "0.00"}))
        assert _e77_text(xml, "EUER/BAus/Sonst_unbeschraenkt") is None

    def test_kz_147_allowed_when_covered_by_einlagen(self):
        xml = _build(_report({}, {"147": "300.00"}), einlagen=Decimal("300"))
        path = "EUER/BAus/KFZ_u_Fahrtkosten/Fahrtkosten_Nutzungseinlage/Sum/E6006103"
        assert _e77_text(xml, path) == "300,00"

    def test_kz_234_at_the_limit_is_built(self):
        xml = _build(_report({}, {"234": "2050.00"}))
        path = "EUER/BAus/Sonst_unbeschraenkt/Schuldzins_Uebrige/Sum/E6004303"
        assert _e77_text(xml, path) == "2050,00"

    def test_envelope_facts(self):
        root = etree.fromstring(_build(_golden_report()))
        ns = {"e": NS}
        assert root.findtext("e:TransferHeader/e:Verfahren", namespaces=ns) == "ElsterErklaerung"
        assert root.findtext("e:TransferHeader/e:DatenArt", namespaces=ns) == "EUER"
        e77 = root.find(f".//{{{E77}}}E77")
        assert e77.get("version") == "2025"
        assert [etree.QName(c).localname for c in e77] == ["EUER", "Vorsatz"]
        assert eur_elster.DATENART_VERSION == "EUER_2025"

    def test_element_order_follows_field_table(self):
        """With every buildable Kennzahl filled, leaves appear in field-table (XSD) order."""
        skip = eur_elster._AFA_KZ | eur_elster._NEEDS_SPLIT_KZ
        income = {kz: "1.00" for kz, _p, _s in eur_elster._BEIN_FIELDS}
        expenses = {kz: "1.00" for kz, _p, _s in eur_elster._BAUS_FIELDS if kz not in skip}
        xml = _build(_report(income, expenses))
        expected = [
            path.rsplit("/", 1)[1]
            for kz, path, _s in (*eur_elster._BEIN_FIELDS, *eur_elster._BAUS_FIELDS)
            if kz in income or kz in expenses
        ]
        sent = [
            etree.QName(el).localname
            for el in etree.fromstring(xml).iter(f"{{{E77}}}*")
            if etree.QName(el).localname in expected
        ]
        assert sent == expected


class TestBuildXmlRefusals:
    def test_review_lines(self):
        r = _golden_report()
        r.review_lines["donations"] = EURLinie(category="donations", kz="review", label="x")
        with pytest.raises(ValueError, match="ZU PRÜFEN"):
            _build(r)

    def test_wrong_year(self):
        with pytest.raises(ValueError, match="2024"):
            _build(_report({"103": "1.00"}, {}, year=2024))

    def test_schema_year_must_match_form_year(self, monkeypatch):
        monkeypatch.setattr(eur_elster, "FORM_YEAR", 2026)
        with pytest.raises(ValueError, match="schema"):
            _build(_report({"103": "1.00"}, {}, year=2026))

    @pytest.mark.parametrize("kz", ["130", "131", "132", "136", "137"])
    def test_afa_not_built(self, kz):
        with pytest.raises(NotImplementedError, match="AVEÜR"):
            _build(_report({}, {kz: "500.00"}))

    def test_kz_151_needs_zeile_42(self):
        with pytest.raises(NotImplementedError, match="Kz 153"):
            _build(_report({}, {"151": "100.00"}))

    def test_kz_234_above_limit(self):
        with pytest.raises(NotImplementedError, match="Anlage SZ"):
            _build(_report({}, {"234": "2050.01"}))

    def test_kz_112_without_vat_line(self):
        with pytest.raises(ValueError, match="EUR-2"):
            _build(_report({"112": "1000.00"}, {}))

    def test_unknown_kennzahl(self):
        with pytest.raises(ValueError, match="999"):
            _build(_report({"999": "1.00"}, {}))

    def test_negative_amount_in_unsigned_field(self):
        with pytest.raises(ValueError, match="negative"):
            _build(_report({}, {"186": "-10.00"}))

    def test_einlagen_below_kz_147(self):
        with pytest.raises(ValueError, match="147"):
            _build(_report({}, {"147": "300.00"}), einlagen=Decimal("299.99"))

    def test_negative_entnahmen(self):
        with pytest.raises(ValueError, match="negative"):
            _build(_golden_report(), entnahmen=Decimal("-1"))

    @pytest.mark.parametrize("hid", ["", "1234", "123456", "abcde"])
    def test_bad_hersteller_id(self, hid):
        with pytest.raises(ValueError, match="Hersteller-ID"):
            _build(_golden_report(), hersteller_id=hid)

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("name", "", "name"),
            ("name", "x" * 46, "name"),
            ("street", "x" * 31, "street"),
            ("city", "", "city"),
            ("art_des_betriebs", "x" * 26, "art_des_betriebs"),
            ("postal_code", "1234", "postal_code"),
            ("steuernummer", "198/113/10010", "steuernummer"),
            ("steuernummer", "9198111310010", "steuernummer"),  # 5th digit must be 0
            ("rechtsform", "350", "rechtsform"),  # GmbH: not a sole proprietor
            ("einkunftsart", "1", "einkunftsart"),
            ("betriebsinhaber", "4", "betriebsinhaber"),
        ],
    )
    def test_bad_taxpayer(self, field, value, match):
        with pytest.raises(ValueError, match=match):
            _build(_golden_report(), taxpayer=replace(TAXPAYER, **{field: value}))

    def test_live_build_disabled_even_with_flag(self, monkeypatch):
        monkeypatch.setenv(LIVE_SUBMISSION_ENV, "1")
        with pytest.raises(NotImplementedError) as exc:
            _build(_golden_report(), test=False)
        assert str(exc.value) == eur_elster.LIVE_DISABLED_MESSAGE


class TestValidate:
    def test_minimal_envelope_ok(self):
        assert eur_elster.validate(_envelope()) == []

    @pytest.mark.parametrize("xml", [b"", b"   ", "<Elster/>"])
    def test_empty_or_not_bytes(self, xml):
        assert eur_elster.validate(xml) != []

    def test_not_well_formed(self):
        errors = eur_elster.validate(b"<Elster><open></Elster>")
        assert any("well-formed" in e for e in errors)

    def test_doctype_rejected(self):
        xml = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Elster>&e;</Elster>'
        assert eur_elster.validate(xml) == ["DOCTYPE declarations are not allowed"]

    def test_wrong_root_and_namespace(self):
        errors = eur_elster.validate(b"<Foo/>")
        assert any("'Elster'" in e for e in errors)
        assert any("namespace" in e for e in errors)

    def test_missing_nutzdaten(self):
        errors = eur_elster.validate(_envelope(nutzdaten=False))
        assert errors == ["Missing DatenTeil//Nutzdaten"]

    def test_missing_transfer_header_fields(self):
        xml = f'<Elster xmlns="{NS}"><TransferHeader/><DatenTeil/></Elster>'.encode()
        errors = eur_elster.validate(xml)
        assert "Missing TransferHeader/Verfahren" in errors
        assert "Missing TransferHeader/DatenArt" in errors
        assert "Missing DatenTeil//Nutzdaten" in errors


class TestSubmitModes:
    def test_default_mode_is_dry_run(self, no_eric):
        result = eur_elster.submit(_envelope())
        assert result.success is True
        assert "dry_run" in result.raw_response

    def test_dry_run_reports_validation_errors(self, no_eric):
        result = eur_elster.submit(b"<Foo/>", mode="dry_run")
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"

    def test_live_always_raises(self, monkeypatch, no_eric):
        monkeypatch.setenv(LIVE_SUBMISSION_ENV, "1")
        with pytest.raises(NotImplementedError) as exc:
            eur_elster.submit(_envelope(), mode="live")
        assert str(exc.value) == (
            "Live ELSTER submission requires a Hersteller-ID and is disabled."
        )

    def test_unknown_mode(self, no_eric):
        with pytest.raises(ValueError):
            eur_elster.submit(_envelope(), mode="production")

    def test_test_mode_requires_testmerker(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        result = eur_elster.submit(
            _envelope(testmerker=False), mode="test", datenart_version="X", config=_cfg()
        )
        assert result.success is False
        assert result.error_code == "TESTMERKER_MISSING"

    def test_test_mode_rejects_empty_datenart_version(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        with pytest.raises(ValueError, match="datenart_version"):
            eur_elster.submit(_envelope(), mode="test", datenart_version="", config=_cfg())

    def test_test_mode_reads_only_eric_library_path(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv("FINAMT_ERIC_HOME", str(tmp_path))  # must be ignored
        result = eur_elster.submit(_envelope(), mode="test", datenart_version="X", config=_cfg())
        assert result.success is False
        assert result.error_code == "ERIC_LIBRARY_PATH_MISSING"

    def test_test_mode_missing_library_fails_gracefully(self, monkeypatch, tmp_path):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        result = eur_elster.submit(_envelope(), mode="test", datenart_version="X", config=_cfg())
        assert result.success is False
        assert result.error_code == "ERIC_LOAD_ERROR"


class _FakeBuffer:
    def __init__(self, session, content=b""):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def handle(self):
        return None

    def content(self):
        return self._content


class _FakeCert:
    verschluesselungs_parameter = object()

    def __init__(self, *_a, **_k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def _fake_session(calls: dict):
    class _FakeSession:
        def __init__(self, eric_home, log_dir=None):
            calls["eric_home"] = eric_home

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def bearbeite_vorgang(self, **kwargs):
            calls.update(kwargs)
            return 0, None

    return _FakeSession


class TestSubmitTestModeWithFakeEric:
    def test_sends_with_validate_and_send_flags(self, monkeypatch, tmp_path):
        calls: dict = {}
        server = b"<Elster><TransferHeader><TransferTicket>TT1</TransferTicket></TransferHeader></Elster>"
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        monkeypatch.setattr(eur_elster, "EricSession", _fake_session(calls))
        monkeypatch.setattr(eur_elster, "EricCertificate", _FakeCert)
        buffers = iter([b"", server])
        monkeypatch.setattr(eur_elster, "EricBuffer", lambda s: _FakeBuffer(s, next(buffers)))

        xml = _envelope()
        result = eur_elster.submit(xml, mode="test", datenart_version="DV_TEST", config=_cfg())

        assert result.success is True
        assert calls["eric_home"] == str(tmp_path)
        assert calls["xml_bytes"] == xml
        assert calls["datenart_version"] == "DV_TEST"
        assert calls["flags"] == eur_elster.ERIC_VALIDIERE | eur_elster.ERIC_SENDE

    def test_default_datenart_version_is_euer_2025(self, monkeypatch, tmp_path):
        calls: dict = {}
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        monkeypatch.setattr(eur_elster, "EricSession", _fake_session(calls))
        monkeypatch.setattr(eur_elster, "EricCertificate", _FakeCert)
        monkeypatch.setattr(eur_elster, "EricBuffer", lambda s: _FakeBuffer(s))
        eur_elster.submit(_build(_golden_report()), mode="test", config=_cfg())
        assert calls["datenart_version"] == "EUER_2025"


class TestEricValidate:
    def test_needs_eric_library_path(self, no_eric):
        result = eur_elster.eric_validate(_build(_golden_report()))
        assert result.success is False
        assert result.error_code == "ERIC_LIBRARY_PATH_MISSING"

    def test_local_errors_stop_before_eric(self, monkeypatch, tmp_path, no_eric):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        result = eur_elster.eric_validate(b"<Foo/>")
        assert result.error_code == "VALIDATION_ERROR"

    def test_validates_only_and_sends_nothing(self, monkeypatch, tmp_path):
        calls: dict = {}

        def _no_cert(*_a, **_k):
            raise AssertionError("no certificate is loaded for validation")

        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, str(tmp_path))
        monkeypatch.setattr(eur_elster, "EricSession", _fake_session(calls))
        monkeypatch.setattr(eur_elster, "EricCertificate", _no_cert)
        monkeypatch.setattr(eur_elster, "EricBuffer", lambda s: _FakeBuffer(s, b"<Erfolg/>"))

        xml = _build(_golden_report())
        result = eur_elster.eric_validate(xml)

        assert result.success is True
        assert calls["flags"] == eur_elster.ERIC_VALIDIERE
        assert calls["crypto_params"] is None
        assert calls["datenart_version"] == "EUER_2025"
        assert calls["xml_bytes"] == xml


@pytest.mark.skipif(
    not (_REAL_ERIC_PATH and _REAL_HERSTELLER_ID),
    reason="needs the local ERiC library (ERIC_LIBRARY_PATH) and the owner's "
    "FINAMT_ELSTER_HERSTELLER_ID; validation only, nothing is sent",
)
class TestRealEric:
    def test_golden_report_validates_in_eric(self, monkeypatch, tmp_path):
        monkeypatch.setenv(eur_elster.ERIC_LIBRARY_ENV, _REAL_ERIC_PATH)
        xml = _build(_golden_report(), hersteller_id=_REAL_HERSTELLER_ID)
        result = eur_elster.eric_validate(xml, log_dir=str(tmp_path))
        assert result.success, f"{result.error_code}: {result.error_message}"
