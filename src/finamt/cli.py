"""
finamt.cli
~~~~~~~~~~~~~
Command-line interface for finamt.

Entry point registered in pyproject.toml::

    [project.scripts]
    finamt = "finamt.cli:main"

Usage examples
--------------
    finamt --version

    # Single receipt
    finamt process receipt1 --input-dir receipts/

    # Batch
    finamt batch --input-dir receipts/ --output-dir results/

    # Scan receipts into local DB, then generate Q1 UStVA report
    finamt ustva --input-dir receipts/ --quarter 1 --year 2024

    # Generate report from already-stored receipts
    finamt ustva --quarter 1 --year 2024 --output ustva_q1.json

    # Monthly UStVA, and which filing period § 18 UStG suggests for 2025
    finamt ustva --month 3 --year 2025
    finamt ustva --suggest-period --year 2025

    # EÜR for 2025 (exit code 1 while receipts need review)
    finamt eur --year 2025 --output eur_2025.json

    # Use a custom DB path
    finamt ustva --input-dir receipts/ --db /tmp/mydb.db

    # Start the web UI
    finamt serve --port 8000
"""

from __future__ import annotations

import warnings

try:
    from requests.exceptions import RequestsDependencyWarning

    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass

import json
import logging
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console

from finamt import FinanceAgent
from finamt.storage import get_repository
from finamt.storage.sqlite import DEFAULT_DB_PATH
from finamt.tax.eur import generate_eur
from finamt.tax.ustva import generate_ustva

#: § 18 Abs. 2 S. 2 UStG: monthly Voranmeldungen if the prior-year tax was more than this
#: (docs/tax-rules.md row "> 9 000 €").
MONTHLY_THRESHOLD = Decimal("9000")
#: § 18 Abs. 2 S. 3 UStG: the Finanzamt may exempt from Voranmeldungen at or below this
#: (docs/tax-rules.md row "≤ 2 000 €").
EXEMPTION_THRESHOLD = Decimal("2000")
#: § 18 Abs. 2a UStG: monthly on request if the prior-year surplus was more than this
#: (docs/tax-rules.md row "> 9 000 € surplus").
SURPLUS_THRESHOLD = Decimal("9000")

# ---------------------------------------------------------------------------
# CLI class
# ---------------------------------------------------------------------------


class FinamtCLI:
    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def print_version(self) -> None:
        try:
            print(f"finamt version: {version('finamt')}")
        except Exception:
            print("finamt version: unknown")

    # ------------------------------------------------------------------
    # Single receipt
    # ------------------------------------------------------------------

    def process_receipt(
        self,
        file_stem: str,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        verbose: bool = False,
        receipt_type: str = "purchase",
        db_path: Path | None = None,
        no_db: bool = False,
    ) -> int:
        """Process one receipt PDF. DB save is automatic. Returns exit code."""
        receipt_path = Path(input_dir) / f"{file_stem}.pdf"
        if not receipt_path.exists():
            print(f"[error] File not found: {receipt_path}", file=sys.stderr)
            return 1

        if verbose:
            print(f"Processing: {receipt_path}")

        agent = FinanceAgent(db_path=None if no_db else (db_path if db_path else DEFAULT_DB_PATH))
        result = agent.process_receipt(receipt_path, receipt_type=receipt_type)

        if result.duplicate:
            d = result.data
            cp = d.counterparty.name if d and d.counterparty else "—"
            print(f"⚠  Duplicate — already in DB: {cp}  (id: {result.existing_id[:16]}…)")
            return 0

        if result.success:
            d = result.data
            cp = d.counterparty.name if d.counterparty else "—"
            print(f"✓  {str(d.receipt_type).upper()}  {cp}  {d.total_amount} EUR")
            if output_dir:
                out_dir = Path(output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / f"{file_stem}_extracted.json"
                out.write_text(result.data.to_json(), encoding="utf-8")
                print(f"   JSON → {out}")
            return 0
        else:
            print(f"✗  Extraction failed: {result.error_message}", file=sys.stderr)
            return 1

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def batch_process(
        self,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        verbose: bool = False,
        receipt_type: str = "purchase",
        db_path: Path | None = None,
        no_db: bool = False,
    ) -> int:
        """Batch-process all PDFs. DB save is automatic. Returns exit code."""
        input_dir = Path(input_dir)
        out_dir = Path(output_dir) if output_dir else None
        pdf_files = sorted(input_dir.glob("*.pdf"))

        if not pdf_files:
            print(f"No PDF files found in {input_dir.resolve()}")
            return 1

        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)

        agent = FinanceAgent(db_path=None if no_db else (db_path if db_path else DEFAULT_DB_PATH))
        results = {}

        for pdf_path in pdf_files:
            if verbose:
                print(f"Processing {pdf_path.name} ...")
            result = agent.process_receipt(pdf_path, receipt_type=receipt_type)
            results[str(pdf_path)] = result
            if out_dir:
                json_path = out_dir / f"{pdf_path.stem}_extracted.json"
                json_path.write_text(
                    json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

        self._print_batch_report(results)
        failed = sum(1 for r in results.values() if not r.success and not r.duplicate)
        return 1 if failed else 0

    def _print_batch_report(self, results: dict) -> None:
        successful = [r for r in results.values() if r.success and not r.duplicate]
        duplicates = [r for r in results.values() if r.duplicate]
        failed = [r for r in results.values() if not r.success]

        total_amount: Decimal = Decimal(0)
        total_vat: Decimal = Decimal(0)
        by_category: dict[str, Decimal] = defaultdict(Decimal)

        for result in successful:
            d = result.data
            if d.total_amount:
                total_amount += d.total_amount
            if d.vat_amount:
                total_vat += d.vat_amount
            if d.category:
                by_category[str(d.category)] += d.total_amount or Decimal(0)

        W = 50
        div = "─" * W
        hdiv = "═" * W
        rate = len(successful) / len(results) if results else 0

        print(f"\n{hdiv}")
        print(f"  {'BATCH PROCESSING REPORT':^{W - 4}}")
        print(hdiv)
        print(f"  Total receipts : {len(results)}")
        print(f"  Newly saved    : {len(successful)}")
        print(f"  Duplicates     : {len(duplicates)}")
        print(f"  Failed         : {len(failed)}")
        print(f"  Success rate   : {rate:.0%}")
        print(f"\n  {'FINANCIALS (new only)':^{W - 4}}")
        print(div)
        print(f"  Total expenses : {total_amount:.2f} EUR")
        print(f"  Total VAT      : {total_vat:.2f} EUR")
        print(f"  Net (excl.VAT) : {total_amount - total_vat:.2f} EUR")

        if by_category:
            print(f"\n  {'BY CATEGORY':^{W - 4}}")
            print(div)
            for cat, amt in sorted(by_category.items(), key=lambda x: -x[1]):
                print(f"  {cat:<22} {amt:>10.2f} EUR")

        print(f"\n  {'DETAIL':^{W - 4}}")
        print(div)
        for path, result in results.items():
            name = Path(path).name
            if result.duplicate:
                print(f"\n  ⚠  {name}  [duplicate — skipped]")
            elif result.success:
                d = result.data
                amt = f"{d.total_amount:.2f} EUR" if d.total_amount else "—"
                dt = d.receipt_date.date() if d.receipt_date else "—"
                vat = f"{d.vat_percentage}%" if d.vat_percentage else "—"
                t = f"{result.processing_time:.1f}s" if result.processing_time else ""
                cp = d.counterparty.name if d.counterparty else "—"
                print(f"\n  ✓  {name}  ({t})")
                print(f"     {str(d.receipt_type).upper():<10}  {cp}")
                print(f"     Date    : {dt}   Total: {amt}   VAT: {vat}")
                print(f"     Category: {d.category}   Items: {len(d.items)}")
            else:
                print(f"\n  ✗  {name}")
                print(f"     Error: {result.error_message}")

        print(f"\n{hdiv}\n")

    # ------------------------------------------------------------------
    # UStVA
    # ------------------------------------------------------------------

    @staticmethod
    def _quarter_bounds(quarter: int, year: int) -> tuple[date, date]:
        starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        ms, ds = starts[quarter]
        me, de = ends[quarter]
        return date(year, ms, ds), date(year, me, de)

    @staticmethod
    def _month_bounds(month: int, year: int) -> tuple[date, date]:
        start = date(year, month, 1)
        nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return start, date.fromordinal(nxt.toordinal() - 1)

    def ingest_receipts(
        self,
        input_dir: Path,
        db_path: Path | None = None,
        verbose: bool = False,
        receipt_type: str = "purchase",
    ) -> int:
        """Scan PDFs and auto-save to DB. Returns number saved."""
        pdf_files = sorted(input_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {input_dir.resolve()}")
            return 0

        agent = FinanceAgent(db_path=db_path if db_path else DEFAULT_DB_PATH)
        saved = 0
        dupes = 0

        for pdf in pdf_files:
            if verbose:
                print(f"  {pdf.name} ...", end=" ", flush=True)
            result = agent.process_receipt(pdf, receipt_type=receipt_type)
            if result.duplicate:
                dupes += 1
                if verbose:
                    print("DUPLICATE (skipped)")
            elif result.success:
                saved += 1
                if verbose:
                    d = result.data
                    cp = d.counterparty.name if d.counterparty else "unknown"
                    print(f"OK  ({cp}, {d.total_amount} EUR)")
            else:
                if verbose:
                    print(f"FAILED — {result.error_message}")

        print(f"{saved} saved, {dupes} duplicates skipped (of {len(pdf_files)} total).")
        return saved

    def run_ustva(
        self,
        quarter: int | None,
        year: int,
        db_path: Path | None = None,
        output: Path | None = None,
        output_dir: Path | None = None,
        month: int | None = None,
    ) -> int:
        """
        Generate and print a UStVA report for the given quarter or month.

        Args:
            month:      Report one month instead of a quarter (``quarter`` is ignored).
            output:     Explicit output file path. Takes priority over output_dir.
            output_dir: Directory to write an auto-named file
                        (e.g. ``ustva_q1_2024.json``, ``ustva_m03_2024.json``).
        """
        if month is not None:
            start, end = self._month_bounds(month, year)
            label, tag = f"{month:02d}/{year}", f"m{month:02d}"
        else:
            quarter = quarter or 1
            start, end = self._quarter_bounds(quarter, year)
            label, tag = f"Q{quarter} {year}", f"q{quarter}"

        with get_repository(db_path) as repo:
            receipts = list(repo.find_by_period(start, end))

        if not receipts:
            print(
                f"No receipts found for {label}.\nRun with --input-dir to scan and store PDFs first."
            )
            return 1

        report = generate_ustva(receipts, start, end)
        print(report.summary())

        # Resolve output path: explicit --output beats --output-dir auto-name
        out_path: Path | None = None
        if output:
            out_path = output
        elif output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"ustva_{tag}_{year}.json"

        if out_path:
            report.to_json(out_path)
            print(f"Report saved to {out_path}")

        return 0

    def suggest_period(self, year: int, db_path: Path | None = None) -> int:
        """
        Print which Voranmeldungszeitraum § 18 Abs. 2 / 2a UStG suggests for ``year``,
        from the tax of ``year - 1`` computed from the stored receipts. Information only.
        """
        prior = year - 1
        start, end = date(prior, 1, 1), date(prior, 12, 31)
        with get_repository(db_path) as repo:
            receipts = list(repo.find_by_period(start, end))

        if not receipts:
            print(
                f"Keine Belege für {prior} gespeichert; keine Empfehlung möglich.\n"
                "Bei Neugründung gilt § 18 Abs. 2 S. 4 bzw. S. 6 UStG: bitte selbst prüfen."
            )
            return 1

        tax = generate_ustva(receipts, start, end).net_liability
        print(f"Umsatzsteuer {prior} (aus gespeicherten Belegen): {tax:.2f} EUR")
        if tax > MONTHLY_THRESHOLD:
            print(
                f"Voranmeldungszeitraum {year}: monthly (Steuer > 9 000 €, § 18 Abs. 2 S. 2 UStG)"
            )
        else:
            print(f"Voranmeldungszeitraum {year}: quarterly (§ 18 Abs. 2 S. 1 UStG)")
            if tax <= EXEMPTION_THRESHOLD:
                print(
                    "exemption possible: Steuer ≤ 2 000 €, das Finanzamt kann von "
                    "Voranmeldungen befreien (§ 18 Abs. 2 S. 3 UStG)"
                )
        if -tax > SURPLUS_THRESHOLD:
            print("Überschuss > 9 000 €: monthly auf Antrag möglich (§ 18 Abs. 2a UStG)")
        print("Nur zur Information; maßgeblich ist die Festsetzung des Finanzamts.")
        return 0

    def run_eur(
        self,
        year: int,
        db_path: Path | None = None,
        output: Path | None = None,
        kleinunternehmer: bool = False,
    ) -> int:
        """
        Print the EÜR for ``year``. Returns 1 when receipts still need a manual
        decision (``review_lines``), so the result can't be filed by mistake.
        """
        with get_repository(db_path) as repo:
            receipts = list(repo.find_by_period(date(year, 1, 1), date(year, 12, 31)))

        if not receipts:
            print(f"No receipts found for {year}.")
            return 1

        report = generate_eur(receipts, year, kleinunternehmer=kleinunternehmer)
        print(report.summary())

        if output:
            report.to_json(output)
            print(f"Report saved to {output}")

        if report.review_lines:
            print(
                f"\n✗  {len(report.review_lines)} Beleggruppe(n) ZU PRÜFEN: "
                "nicht abgabereif, erst entscheiden."
            )
            return 1
        return 0


# ---------------------------------------------------------------------------
# Typer app
# ---------------------------------------------------------------------------

console = Console()

_ASCII_BANNER = """
[bold yellow]____________                         _____ 
___  __/__(_)____________ _______ _____  /_
__  /_ __  /__  __ \\  __ `/_  __ `__ \\  __/
_  __/ _  / _  / / / /_/ /_  / / / / / /_  
/_/    /_/  /_/ /_/\\__,_/ /_/ /_/ /_/\\__/[/bold yellow]  
"""

app = typer.Typer(
    name="finamt",
    help="finamt: process German receipts and prepare tax returns.",
    rich_markup_mode="rich",
    add_completion=False,
)

ReceiptType = typer.Option("--type", help="purchase = Eingangsrechnung; sale = Ausgangsrechnung.")
QuarterOpt = typer.Option("--quarter", help="Fiscal quarter (1–4).", show_default=True)
YearOpt = typer.Option("--year", help="Fiscal year.", show_default=True)
DbOpt = typer.Option(
    "--db", help="SQLite DB path (default: ~/.finamt/finamt.db).", show_default=False
)
VerboseOpt = typer.Option("--verbose", "-v", help="Enable verbose output.")


def _version_callback(value: bool) -> None:
    if value:
        try:
            ver = version("finamt")
        except Exception:
            ver = "unknown"
        rprint(f"finamt version [bold green]{ver}[/bold green]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show package version and exit.",
        ),
    ] = False,
) -> None:
    """finamt: process German receipts and prepare German tax returns."""
    if ctx.invoked_subcommand is None:
        rprint(_ASCII_BANNER)
        rprint(ctx.get_help())
        raise typer.Exit()


# ---------------------------------------------------------------------------
# process sub-command
# ---------------------------------------------------------------------------


@app.command("process")
def cmd_process(
    file: Annotated[str, typer.Argument(help="Receipt filename without the .pdf extension.")],
    input_dir: Annotated[
        Path, typer.Option("--input-dir", help="Directory containing the receipt PDF.")
    ],
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Write extracted JSON here.")
    ] = None,
    verbose: Annotated[bool, VerboseOpt] = False,
    receipt_type: Annotated[str, ReceiptType] = "purchase",
    db: Annotated[Path | None, DbOpt] = None,
    no_db: Annotated[bool, typer.Option("--no-db", help="Disable DB persistence.")] = False,
) -> None:
    """Process a single receipt PDF and extract its data."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(name)s %(message)s")

    rc = FinamtCLI().process_receipt(
        file_stem=file,
        input_dir=input_dir,
        output_dir=output_dir,
        verbose=verbose,
        receipt_type=receipt_type,
        db_path=db,
        no_db=no_db,
    )
    if rc != 0:
        raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# batch sub-command
# ---------------------------------------------------------------------------


@app.command("batch")
def cmd_batch(
    input_dir: Annotated[
        Path, typer.Option("--input-dir", help="Directory containing receipt PDFs.")
    ],
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Write extracted JSONs here.")
    ] = None,
    verbose: Annotated[bool, VerboseOpt] = False,
    receipt_type: Annotated[str, ReceiptType] = "purchase",
    db: Annotated[Path | None, DbOpt] = None,
    no_db: Annotated[bool, typer.Option("--no-db", help="Disable DB persistence.")] = False,
) -> None:
    """Batch-process all PDFs in a directory."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(name)s %(message)s")

    rc = FinamtCLI().batch_process(
        input_dir=input_dir,
        output_dir=output_dir,
        verbose=verbose,
        receipt_type=receipt_type,
        db_path=db,
        no_db=no_db,
    )
    if rc != 0:
        raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# ustva sub-command
# ---------------------------------------------------------------------------


@app.command("ustva")
def cmd_ustva(
    quarter: Annotated[int | None, QuarterOpt] = None,
    year: Annotated[int, YearOpt] = date.today().year,
    month: Annotated[
        int | None,
        typer.Option("--month", min=1, max=12, help="Month (1–12) instead of a quarter."),
    ] = None,
    suggest_period: Annotated[
        bool,
        typer.Option(
            "--suggest-period",
            help="Suggest monthly/quarterly filing for --year from the prior year's tax.",
        ),
    ] = False,
    input_dir: Annotated[
        Path | None, typer.Option("--input-dir", help="Scan & ingest PDFs before reporting.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", help="Write JSON report to this path.")
    ] = None,
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Auto-named JSON written here.")
    ] = None,
    verbose: Annotated[bool, VerboseOpt] = False,
    receipt_type: Annotated[str, ReceiptType] = "purchase",
    db: Annotated[Path | None, DbOpt] = None,
) -> None:
    """Generate a UStVA (VAT pre-return) report for a quarter (default Q1) or a month."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(name)s %(message)s")
    if quarter is not None and month is not None:
        raise typer.BadParameter("--quarter and --month are mutually exclusive.")
    if quarter is not None and not 1 <= quarter <= 4:
        raise typer.BadParameter("--quarter must be 1–4.")

    cli = FinamtCLI()
    if suggest_period:
        rc = cli.suggest_period(year=year, db_path=db)
        if rc != 0:
            raise typer.Exit(code=rc)
        return
    if input_dir:
        cli.ingest_receipts(
            input_dir=input_dir,
            db_path=db,
            verbose=verbose,
            receipt_type=receipt_type,
        )
    rc = cli.run_ustva(
        quarter=quarter,
        year=year,
        db_path=db,
        output=output,
        output_dir=output_dir,
        month=month,
    )
    if rc != 0:
        raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# eur sub-command
# ---------------------------------------------------------------------------


@app.command("eur")
def cmd_eur(
    year: Annotated[int, YearOpt] = date.today().year - 1,
    output: Annotated[
        Path | None, typer.Option("--output", help="Write JSON report to this path.")
    ] = None,
    kleinunternehmer: Annotated[
        bool,
        typer.Option("--kleinunternehmer", help="§ 19 UStG: gross amounts, sales on Kz 111."),
    ] = False,
    db: Annotated[Path | None, DbOpt] = None,
) -> None:
    """EÜR (Anlage EÜR Kennzahlen) for a year; exit code 1 while receipts need review."""
    rc = FinamtCLI().run_eur(
        year=year, db_path=db, output=output, kleinunternehmer=kleinunternehmer
    )
    if rc != 0:
        raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# invoice sub-commands (INV-1)
# ---------------------------------------------------------------------------

invoice_app = typer.Typer(help="Outgoing invoices (§ 14 UStG) with gapless numbers.")
app.add_typer(invoice_app, name="invoice")


def _pdf_dir_for(db_path: Path) -> Path:
    from finamt.storage.project import layout_from_db_path

    try:
        return layout_from_db_path(db_path).pdfs_dir
    except Exception:  # noqa: BLE001 — a DB outside a project folder
        return db_path.parent / "pdfs"


@invoice_app.command("new")
def cmd_invoice_new(
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            help="JSON: customer, issue_date, supply_date or supply_period, lines, notes. "
            "The supplier comes from the project's Stammdaten unless given.",
        ),
    ],
    db: Annotated[Path | None, DbOpt] = None,
) -> None:
    """Issue an invoice: next number, PDF, and a stored sale receipt."""
    from finamt.invoicing import Invoice, issue_invoice, supplier_from_taxpayer

    db_path = db or DEFAULT_DB_PATH
    data = json.loads(file.read_text(encoding="utf-8"))
    with get_repository(db_path) as repo:
        if not data.get("supplier"):
            data["supplier"] = vars(supplier_from_taxpayer(repo.get_metadata("taxpayer") or {}))
        data.setdefault("issue_date", date.today().isoformat())
        try:
            inv = Invoice.from_dict(data)
            res = issue_invoice(repo, inv, _pdf_dir_for(Path(db_path)))
        except ValueError as exc:
            print(f"✗  {exc}", file=sys.stderr)
            raise typer.Exit(code=1) from exc
    print(f"✓  {inv.title} {inv.number}: {inv.gross_total:.2f} EUR → {res.pdf_path}")


@invoice_app.command("list")
def cmd_invoice_list(
    year: Annotated[int | None, YearOpt] = None,
    db: Annotated[Path | None, DbOpt] = None,
) -> None:
    """List issued invoices, newest first."""
    with get_repository(db or DEFAULT_DB_PATH) as repo:
        rows = repo.list_invoices(year)
    if not rows:
        print("Keine Rechnungen.")
        return
    for r in rows:
        corr = f"  (storniert {r['corrects']})" if r.get("corrects") else ""
        kunde = (r.get("customer") or {}).get("name") or "—"
        print(f"{r['number']}  {r['issue_date']}  {kunde:<30} {r['gross_total']:>12} EUR{corr}")


@invoice_app.command("cancel")
def cmd_invoice_cancel(
    number: Annotated[str, typer.Argument(help="Invoice number, e.g. 2025-0001.")],
    db: Annotated[Path | None, DbOpt] = None,
) -> None:
    """Cancel an invoice with a Rechnungskorrektur (Storno) under its own number."""
    from finamt.invoicing import cancel_invoice

    db_path = db or DEFAULT_DB_PATH
    with get_repository(db_path) as repo:
        try:
            res = cancel_invoice(repo, number, _pdf_dir_for(Path(db_path)))
        except ValueError as exc:
            print(f"✗  {exc}", file=sys.stderr)
            raise typer.Exit(code=1) from exc
    print(f"✓  {res.invoice.title} {res.invoice.number} storniert {number} → {res.pdf_path}")


# ---------------------------------------------------------------------------
# serve sub-command
# ---------------------------------------------------------------------------


@app.command("serve")
def cmd_serve(
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port number.")] = 8000,
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Do not open the browser.")
    ] = False,
    reload: Annotated[bool, typer.Option("--reload", help="Enable hot-reload (dev mode).")] = False,
    log_level: Annotated[str, typer.Option("--log-level", help="Uvicorn log level.")] = "warning",
) -> None:
    """Start the finamt web UI server."""
    from finamt.ui.server import launch

    launch(
        host=host,
        port=port,
        reload=reload,
        open_browser=not no_browser,
        log_level=log_level,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
