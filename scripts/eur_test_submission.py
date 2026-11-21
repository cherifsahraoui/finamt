"""Anlage EÜR check against ERiC with a fixed test case (owner step M2, task EUR-6).

Builds an Anlage EÜR 2025 for a made-up Freiberufler (income 12 000 € plus 19 % VAT,
a few expenses) and runs it through ERiC:

    uv run --env-file .env python scripts/eur_test_submission.py          # validate only, nothing sent
    uv run --env-file .env python scripts/eur_test_submission.py --send   # test submission

Safety: build_xml always sets the Testmerker, and the script refuses to run unless
FINAMT_ELSTER_STEUERNUMMER is an official ERiC test tax number (test Finanzamt 9198,
ERiC-Entwicklerhandbuch 6.5.1). Anything sent there is deleted by ELSTER.
It never files for real. Configuration comes from the environment (.env).
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal

from finamt.tax import eur_elster
from finamt.tax.elster import ElsterConfig, normalise_steuernummer
from finamt.tax.eur import EURLinie, EURReport

TEST_FINANZAMT = "9198"


def _test_report() -> EURReport:
    report = EURReport(year=eur_elster.SCHEMA_YEAR)
    income = {"112": "12000.00", "140": "2280.00"}
    expenses = {"110": "3000.00", "228": "1234.56", "185": "400.10", "186": "1500.00"}
    for kz, amount in income.items():
        report.einnahmen_lines[kz] = EURLinie("test", kz, "Testfall", Decimal(amount))
    for kz, amount in expenses.items():
        report.ausgaben_lines[kz] = EURLinie("test", kz, "Testfall", Decimal(amount))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--send", action="store_true", help="send as test case (Testmerker)")
    args = parser.parse_args()

    cfg = ElsterConfig.from_env()
    stnr = cfg.steuernummer
    if not (stnr.isdigit() and len(stnr) == 13):
        stnr = normalise_steuernummer(stnr, cfg.bundesland_kz)
    if not stnr.startswith(TEST_FINANZAMT):
        print(
            "Refusing: FINAMT_ELSTER_STEUERNUMMER is not an ERiC test tax number (9198…).",
            file=sys.stderr,
        )
        return 2
    if not (cfg.hersteller_id.isdigit() and len(cfg.hersteller_id) == 5):
        print("FINAMT_ELSTER_HERSTELLER_ID must be your 5-digit Hersteller-ID.", file=sys.stderr)
        return 2

    taxpayer = eur_elster.EURTaxpayer(
        name="Testfall FreiBuch",
        street="Testgasse 1",
        postal_code="12345",
        city="Musterstadt",
        steuernummer=stnr,
        art_des_betriebs="IT-Beratung",
        grundstuecke_entnommen=False,
    )
    xml = eur_elster.build_xml(
        _test_report(),
        taxpayer,
        entnahmen=Decimal("20000"),
        einlagen=Decimal("0"),
        hersteller_id=cfg.hersteller_id,
    )
    log_dir = os.environ.get("FINAMT_ERIC_LOG_DIR", "private/eric_logs")
    os.makedirs(log_dir, exist_ok=True)
    if args.send:
        result = eur_elster.submit(xml, mode="test", config=cfg, log_dir=log_dir)
    else:
        result = eur_elster.eric_validate(xml, log_dir=log_dir)

    mode = "test submission" if args.send else "validation (nothing sent)"
    print(f"{mode}: success={result.success}")
    if result.telenummer:
        print(f"telenummer: {result.telenummer}")
    if not result.success:
        print(f"error {result.error_code}: {result.error_message}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
