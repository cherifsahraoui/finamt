"""UStVA check against ERiC with a fixed test case (owner step M2, task UST-5).

Builds a UStVA for a past quarter with one sale of 1 000.99 EUR net at 19 % and
runs it through ERiC:

    uv run --env-file .env python scripts/ustva_test_submission.py          # validate only, nothing sent
    uv run --env-file .env python scripts/ustva_test_submission.py --send   # test submission

Safety: the Testmerker is always set, and the script refuses to run unless
FINAMT_ELSTER_STEUERNUMMER is an official ERiC test tax number (test Finanzamt
9198, ERiC-Entwicklerhandbuch 6.5.1). Anything sent there is deleted by ELSTER.
It never files for real. Configuration comes from the environment (.env).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from decimal import Decimal

from finamt.tax.elster import ElsterConfig, ElsterEricClient
from finamt.tax.ustva import USTVALineItem, USTVAReport

TEST_FINANZAMT = "9198"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--send", action="store_true", help="send as test case (Testmerker)")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--quarter", type=int, default=1, choices=[1, 2, 3, 4])
    args = parser.parse_args()

    cfg = ElsterConfig.from_env()
    if not cfg.steuernummer.startswith(TEST_FINANZAMT):
        print(
            "Refusing: FINAMT_ELSTER_STEUERNUMMER is not an ERiC test tax number (9198…).",
            file=sys.stderr,
        )
        return 2
    if not (cfg.hersteller_id.isdigit() and len(cfg.hersteller_id) == 5):
        print("FINAMT_ELSTER_HERSTELLER_ID must be your 5-digit Hersteller-ID.", file=sys.stderr)
        return 2
    # Sender address: FINAMT_ELSTER_NAME / _STREET / _HOUSE_NUMBER / _PLZ / _CITY (read by
    # ElsterConfig.from_env). Without them, use the test-case sender of the ERiC examples:
    # the builder refuses an empty address (CLN-4).
    if not (cfg.street and cfg.postal_code and cfg.city):
        cfg.company_name = cfg.company_name or "Testfall FreiBuch"
        cfg.street, cfg.house_number = "Testgasse", "1"
        cfg.postal_code, cfg.city = "12345", "Musterstadt"

    start_month = 3 * (args.quarter - 1) + 1
    report = USTVAReport(
        period_start=date(args.year, start_month, 1),
        period_end=date(args.year, start_month + 2, 28),
    )
    report.lines["19"] = USTVALineItem(
        vat_rate=Decimal("19"),
        sale_net=Decimal("1000.99"),
        sale_vat=Decimal("190.19"),
        sale_count=1,
    )

    client = ElsterEricClient(
        cfg,
        eric_home=os.environ["ERIC_LIBRARY_PATH"],
        use_test=True,
        log_dir=os.environ.get("FINAMT_ERIC_LOG_DIR", "private/eric_logs"),
    )
    period = 40 + args.quarter
    if args.send:
        result = client.submit_ust(report, year=args.year, period=period)
    else:
        result = client.validate_ust(report, year=args.year, period=period)

    mode = "test submission" if args.send else "validation (nothing sent)"
    print(f"{mode}: success={result.success}")
    if result.telenummer:
        print(f"telenummer: {result.telenummer}")
    if not result.success:
        print(f"error {result.error_code}: {result.error_message}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
