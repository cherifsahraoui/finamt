"""
tests/test_cli_inprocess.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In-process tests for FinamtCLI with FinanceAgent fully mocked.
"""

from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from finamt.cli import FinamtCLI, app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _success_result(
    mocker,
    *,
    cp_name="Test GmbH",
    amount=119,
    vat=19,
    category="software",
    items=None,
    receipt_type="purchase",
    receipt_date=None,
    vat_pct=19,
    proc_time=1.0,
):
    r = mocker.Mock()
    r.success = True
    r.duplicate = False
    r.data.receipt_type.__str__ = lambda self: receipt_type
    r.data.counterparty.name = cp_name
    r.data.total_amount = Decimal(str(amount))
    r.data.vat_amount = Decimal(str(vat))
    r.data.vat_percentage = vat_pct
    r.data.category = category
    r.data.items = items or []
    r.data.receipt_date = receipt_date
    r.processing_time = proc_time
    r.data.to_json.return_value = '{"vendor": "Test GmbH"}'
    r.to_dict.return_value = {"success": True}
    return r


def _fail_result(mocker):
    r = mocker.Mock()
    r.success = False
    r.duplicate = False
    r.error_message = "OCR failed"
    r.to_dict.return_value = {"success": False}
    return r


def _dup_result(mocker, cp_name="Test GmbH"):
    r = mocker.Mock()
    r.success = True
    r.duplicate = True
    r.existing_id = "abc123xyz"
    r.data.counterparty.name = cp_name
    r.to_dict.return_value = {"duplicate": True}
    return r


# ---------------------------------------------------------------------------
# print_version
# ---------------------------------------------------------------------------


class TestPrintVersion:
    def test_version_printed(self, capsys):
        FinamtCLI().print_version()
        assert "finamt version" in capsys.readouterr().out

    def test_version_fallback_when_package_missing(self, mocker, capsys):
        mocker.patch("finamt.cli.version", side_effect=Exception("not installed"))
        FinamtCLI().print_version()
        assert "unknown" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# process_receipt
# ---------------------------------------------------------------------------


class TestProcessReceipt:
    def test_success(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        assert FinamtCLI().process_receipt("r", tmp_path) == 0

    def test_success_with_verbose(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        FinamtCLI().process_receipt("r", tmp_path, verbose=True)
        assert "Processing" in capsys.readouterr().out

    def test_success_writes_json_to_output_dir(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        out_dir = tmp_path / "out"
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        rc = FinamtCLI().process_receipt("r", tmp_path, output_dir=out_dir)
        assert rc == 0
        assert (out_dir / "r_extracted.json").exists()

    def test_missing_file_returns_1(self, tmp_path):
        assert FinamtCLI().process_receipt("ghost", tmp_path) == 1

    def test_failure_returns_1(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _fail_result(mocker)
        assert FinamtCLI().process_receipt("r", tmp_path) == 1
        assert "failed" in capsys.readouterr().err.lower()

    def test_duplicate_returns_0(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _dup_result(mocker)
        assert FinamtCLI().process_receipt("r", tmp_path) == 0
        assert "Duplicate" in capsys.readouterr().out

    def test_no_db_flag(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        FinamtCLI().process_receipt("r", tmp_path, no_db=True)
        mock_cls.assert_called_once_with(db_path=None)

    def test_explicit_db_path(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        db = tmp_path / "custom.db"
        FinamtCLI().process_receipt("r", tmp_path, db_path=db)
        mock_cls.assert_called_once_with(db_path=db)

    def test_sale_type(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_instance = mocker.patch("finamt.cli.FinanceAgent").return_value
        mock_instance.process_receipt.return_value = _success_result(mocker, receipt_type="sale")
        FinamtCLI().process_receipt("r", tmp_path, receipt_type="sale")
        mock_instance.process_receipt.assert_called_once_with(
            tmp_path / "r.pdf", receipt_type="sale"
        )


# ---------------------------------------------------------------------------
# batch_process
# ---------------------------------------------------------------------------


class TestBatchProcess:
    def test_success_two_pdfs(self, mocker, tmp_path, capsys):
        for name in ("a.pdf", "b.pdf"):
            (tmp_path / name).write_text("x")
        res = _success_result(mocker, receipt_date=datetime(2024, 3, 15))
        mocker.patch("finamt.cli.FinanceAgent").return_value.process_receipt.return_value = res
        rc = FinamtCLI().batch_process(tmp_path)
        out = capsys.readouterr().out
        assert rc == 0
        assert "BATCH PROCESSING REPORT" in out

    def test_no_pdfs_returns_1(self, tmp_path):
        assert FinamtCLI().batch_process(tmp_path) == 1

    def test_failure_counted_in_report(self, mocker, tmp_path, capsys):
        (tmp_path / "bad.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _fail_result(mocker)
        rc = FinamtCLI().batch_process(tmp_path)
        assert rc == 1
        assert "✗" in capsys.readouterr().out

    def test_duplicate_in_batch(self, mocker, tmp_path, capsys):
        (tmp_path / "dup.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _dup_result(mocker)
        rc = FinamtCLI().batch_process(tmp_path)
        assert rc == 0
        assert "duplicate" in capsys.readouterr().out.lower()

    def test_writes_json_output(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        out_dir = tmp_path / "out"
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        FinamtCLI().batch_process(tmp_path, output_dir=out_dir)
        assert (out_dir / "r_extracted.json").exists()

    def test_verbose_mode(self, mocker, tmp_path, capsys):
        (tmp_path / "v.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        FinamtCLI().batch_process(tmp_path, verbose=True)
        assert "Processing" in capsys.readouterr().out

    def test_no_db_flag(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        FinamtCLI().batch_process(tmp_path, no_db=True)
        mock_cls.assert_called_once_with(db_path=None)

    def test_report_has_category_breakdown(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(
            mocker, category="software", amount=100, vat=19
        )
        FinamtCLI().batch_process(tmp_path)
        assert "software" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# ingest_receipts
# ---------------------------------------------------------------------------


class TestIngestReceipts:
    def test_no_pdfs(self, tmp_path, capsys):
        count = FinamtCLI().ingest_receipts(tmp_path)
        assert count == 0
        assert "No PDF" in capsys.readouterr().out

    def test_success_increments_saved(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        count = FinamtCLI().ingest_receipts(tmp_path)
        assert count == 1
        assert "saved" in capsys.readouterr().out

    def test_duplicate_increments_dupes(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _dup_result(mocker)
        count = FinamtCLI().ingest_receipts(tmp_path)
        assert count == 0
        out = capsys.readouterr().out
        assert "duplicate" in out.lower()

    def test_failure_not_counted(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _fail_result(mocker)
        count = FinamtCLI().ingest_receipts(tmp_path)
        assert count == 0

    def test_verbose_ok(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(
            mocker, receipt_date=datetime(2024, 1, 1)
        )
        FinamtCLI().ingest_receipts(tmp_path, verbose=True)
        assert "OK" in capsys.readouterr().out

    def test_verbose_duplicate(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _dup_result(mocker)
        FinamtCLI().ingest_receipts(tmp_path, verbose=True)
        assert "DUPLICATE" in capsys.readouterr().out

    def test_verbose_failed(self, mocker, tmp_path, capsys):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _fail_result(mocker)
        FinamtCLI().ingest_receipts(tmp_path, verbose=True)
        assert "FAILED" in capsys.readouterr().out

    def test_explicit_db_path(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        db = tmp_path / "custom.db"
        FinamtCLI().ingest_receipts(tmp_path, db_path=db)
        mock_cls.assert_called_once_with(db_path=db)


# ---------------------------------------------------------------------------
# _quarter_bounds
# ---------------------------------------------------------------------------


class TestQuarterBounds:
    @pytest.mark.parametrize(
        "q,start,end",
        [
            (1, (2024, 1, 1), (2024, 3, 31)),
            (2, (2024, 4, 1), (2024, 6, 30)),
            (3, (2024, 7, 1), (2024, 9, 30)),
            (4, (2024, 10, 1), (2024, 12, 31)),
        ],
    )
    def test_quarter_bounds(self, q, start, end):
        from datetime import date

        s, e = FinamtCLI._quarter_bounds(q, 2024)
        assert s == date(*start)
        assert e == date(*end)


# ---------------------------------------------------------------------------
# run_ustva
# ---------------------------------------------------------------------------


class TestRunUstva:
    def _mock_report(self, mocker):
        report = mocker.Mock()
        report.summary.return_value = "UStVA Q1 2024 summary"
        return report

    def test_no_receipts_returns_1(self, mocker, tmp_path, capsys):
        mocker.patch("finamt.cli.get_repository").__enter__ = mocker.Mock(
            return_value=mocker.Mock(find_by_period=mocker.Mock(return_value=[]))
        )
        # Patch via context manager protocol
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        rc = FinamtCLI().run_ustva(quarter=1, year=2024, db_path=tmp_path / "finamt.db")
        assert rc == 1
        assert "No receipts" in capsys.readouterr().out

    def test_generates_report(self, mocker, tmp_path, capsys):
        mock_receipt = mocker.Mock()
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[mock_receipt]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        mocker.patch("finamt.cli.generate_ustva", return_value=self._mock_report(mocker))

        rc = FinamtCLI().run_ustva(quarter=1, year=2024)
        assert rc == 0
        assert "UStVA" in capsys.readouterr().out

    def test_saves_to_explicit_output(self, mocker, tmp_path, capsys):
        mock_receipt = mocker.Mock()
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[mock_receipt]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        report = self._mock_report(mocker)
        mocker.patch("finamt.cli.generate_ustva", return_value=report)

        out_file = tmp_path / "report.json"
        FinamtCLI().run_ustva(quarter=2, year=2024, output=out_file)
        report.to_json.assert_called_once_with(out_file)

    def test_saves_to_output_dir(self, mocker, tmp_path, capsys):
        mock_receipt = mocker.Mock()
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[mock_receipt]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        report = self._mock_report(mocker)
        mocker.patch("finamt.cli.generate_ustva", return_value=report)

        out_dir = tmp_path / "reports"
        FinamtCLI().run_ustva(quarter=3, year=2024, output_dir=out_dir)
        assert out_dir.is_dir()
        report.to_json.assert_called_once_with(out_dir / "ustva_q3_2024.json")


# ---------------------------------------------------------------------------
# Typer CLI integration (replaces TestBuildParser)
# ---------------------------------------------------------------------------


class TestTyperCLI:
    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Usage" in result.output

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "finamt version" in result.output

    def test_process_with_file_and_input_dir(self, mocker, tmp_path):
        (tmp_path / "r1.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        result = runner.invoke(app, ["process", "r1", "--input-dir", str(tmp_path)])
        assert result.exit_code == 0

    def test_batch_with_input_dir(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        result = runner.invoke(app, ["batch", "--input-dir", str(tmp_path)])
        assert result.exit_code == 0

    def test_type_sale(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker, receipt_type="sale")
        result = runner.invoke(
            app, ["process", "r", "--input-dir", str(tmp_path), "--type", "sale"]
        )
        assert result.exit_code == 0

    def test_ustva_quarter_and_year(self, mocker):
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        result = runner.invoke(app, ["ustva", "--quarter", "2", "--year", "2023"])
        assert result.exit_code == 1  # no receipts → non-zero

    def test_serve_args(self, mocker):
        mock_launch = mocker.patch("finamt.ui.server.launch")
        result = runner.invoke(app, ["serve", "--no-browser", "--port", "9000"])
        assert result.exit_code == 0
        mock_launch.assert_called_once()

    def test_db_option(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        db = str(tmp_path / "custom.db")
        result = runner.invoke(app, ["batch", "--input-dir", str(tmp_path), "--db", db])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# main() / app dispatch (via Typer CliRunner)
# ---------------------------------------------------------------------------


class TestMain:
    def test_version_flag_exits_0(self, mocker):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "finamt version" in result.output

    def test_no_args_shows_help_exits_0(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Usage" in result.output

    def test_single_receipt_dispatch(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        result = runner.invoke(app, ["process", "r", "--input-dir", str(tmp_path)])
        assert result.exit_code == 0

    def test_batch_dispatch(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        result = runner.invoke(app, ["batch", "--input-dir", str(tmp_path)])
        assert result.exit_code == 0

    def test_ustva_dispatch_no_receipts(self, mocker):
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        result = runner.invoke(app, ["ustva", "--quarter", "1", "--year", "2024"])
        assert result.exit_code == 1

    def test_ustva_dispatch_with_ingest(self, mocker, tmp_path):
        """finamt ustva --input-dir triggers ingest then UStVA."""
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock(find_by_period=MagicMock(return_value=[]))
        cm.__exit__.return_value = False
        mocker.patch("finamt.cli.get_repository", return_value=cm)
        mocker.patch("finamt.cli.FinanceAgent")
        result = runner.invoke(
            app, ["ustva", "--input-dir", str(tmp_path), "--quarter", "1", "--year", "2024"]
        )
        assert result.exit_code == 1  # no receipts in DB → 1

    def test_verbose_enables_logging(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mocker.patch(
            "finamt.cli.FinanceAgent"
        ).return_value.process_receipt.return_value = _success_result(mocker)
        with patch("logging.basicConfig") as mock_log:
            runner.invoke(app, ["process", "r", "--input-dir", str(tmp_path), "--verbose"])
            mock_log.assert_called_once()

    def test_serve_dispatch(self, mocker):
        mock_launch = mocker.patch("finamt.ui.server.launch")
        result = runner.invoke(app, ["serve", "--no-browser"])
        assert result.exit_code == 0
        mock_launch.assert_called_once()

    def test_serve_dispatch_with_port_and_log_level(self, mocker):
        mock_launch = mocker.patch("finamt.ui.server.launch")
        result = runner.invoke(
            app, ["serve", "--port", "9000", "--log-level", "debug", "--no-browser"]
        )
        assert result.exit_code == 0
        call_kwargs = mock_launch.call_args
        assert call_kwargs.kwargs.get("port") == 9000 or call_kwargs.args[1] == 9000

    def test_no_db_flag_passed_through(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        runner.invoke(app, ["process", "r", "--input-dir", str(tmp_path), "--no-db"])
        mock_cls.assert_called_once_with(db_path=None)

    def test_db_flag_passed_through(self, mocker, tmp_path):
        (tmp_path / "r.pdf").write_text("x")
        db = str(tmp_path / "custom.db")
        mock_cls = mocker.patch("finamt.cli.FinanceAgent")
        mock_cls.return_value.process_receipt.return_value = _success_result(mocker)
        runner.invoke(app, ["process", "r", "--input-dir", str(tmp_path), "--db", db])
        mock_cls.assert_called_once_with(db_path=Path(db))


# ---------------------------------------------------------------------------
# CLI-1: eur, ustva --month, ustva --suggest-period (real temp DB, no OCR/LLM)
# ---------------------------------------------------------------------------


def _stored(
    *,
    total: str,
    vat: str | None,
    pct: str | None,
    when: datetime,
    typ: str = "sale",
    cat: str = "services",
    sub: str | None = None,
):
    import uuid

    from finamt.models import Counterparty, ReceiptCategory, ReceiptData, ReceiptType

    return ReceiptData(
        raw_text=f"cli {uuid.uuid4()}",
        receipt_type=ReceiptType(typ),
        counterparty=Counterparty(name="Kunde GmbH"),
        receipt_date=when,
        total_amount=Decimal(total),
        vat_amount=Decimal(vat) if vat is not None else None,
        vat_percentage=Decimal(pct) if pct is not None else None,
        category=ReceiptCategory(cat),
        subcategory=sub,
    )


def _db_with(tmp_path, *receipts) -> str:
    from finamt.storage.sqlite import SQLiteRepository

    db = tmp_path / "cli.db"
    with SQLiteRepository(db_path=db) as repo:
        for r in receipts:
            repo.save(r)
    return str(db)


class TestCliEur:
    def test_help_lists_eur(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "eur" in result.output

    def test_prints_summary_and_exits_0(self, tmp_path):
        db = _db_with(
            tmp_path,
            _stored(total="1190.00", vat="190.00", pct="19", when=datetime(2025, 3, 1)),
            _stored(
                total="119.00",
                vat="19.00",
                pct="19",
                when=datetime(2025, 4, 1),
                typ="purchase",
                cat="software",
            ),
        )
        out = tmp_path / "eur.json"
        result = runner.invoke(app, ["eur", "--year", "2025", "--db", db, "--output", str(out)])
        assert result.exit_code == 0, result.output
        assert "Einnahmen-Überschuss-Rechnung" in result.output
        assert "Kz 140" in result.output
        import json

        assert json.loads(out.read_text(encoding="utf-8"))["gewinn"] == "1071.00"

    def test_review_lines_give_nonzero_exit(self, tmp_path):
        db = _db_with(
            tmp_path,
            _stored(
                total="500.00",
                vat=None,
                pct=None,
                when=datetime(2025, 5, 1),
                typ="purchase",
                cat="donations",
            ),
        )
        result = runner.invoke(app, ["eur", "--year", "2025", "--db", db])
        assert result.exit_code == 1
        assert "ZU PRÜFEN" in result.output

    def test_no_receipts(self, tmp_path):
        result = runner.invoke(app, ["eur", "--year", "2025", "--db", str(tmp_path / "e.db")])
        assert result.exit_code == 1
        assert "No receipts" in result.output

    def test_kleinunternehmer_flag(self, tmp_path):
        db = _db_with(
            tmp_path, _stored(total="1000.00", vat=None, pct=None, when=datetime(2025, 3, 1))
        )
        result = runner.invoke(app, ["eur", "--year", "2025", "--db", db, "--kleinunternehmer"])
        assert result.exit_code == 0, result.output
        assert "Kz 111" in result.output


class TestCliUstvaMonth:
    def test_month_selects_only_that_month(self, tmp_path):
        db = _db_with(
            tmp_path,
            _stored(total="1190.00", vat="190.00", pct="19", when=datetime(2025, 2, 10)),
            _stored(total="238.00", vat="38.00", pct="19", when=datetime(2025, 3, 10)),
        )
        out_dir = tmp_path / "out"
        result = runner.invoke(
            app,
            ["ustva", "--month", "2", "--year", "2025", "--db", db, "--output-dir", str(out_dir)],
        )
        assert result.exit_code == 0, result.output
        assert "2025-02-01 bis 2025-02-28" in result.output
        assert "190.00" in result.output
        assert (out_dir / "ustva_m02_2025.json").exists()

    def test_december_bounds(self):
        assert FinamtCLI._month_bounds(12, 2024) == (
            datetime(2024, 12, 1).date(),
            datetime(2024, 12, 31).date(),
        )

    def test_quarter_and_month_exclusive(self, tmp_path):
        result = runner.invoke(
            app, ["ustva", "--quarter", "1", "--month", "2", "--db", str(tmp_path / "x.db")]
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output

    def test_month_out_of_range(self, tmp_path):
        result = runner.invoke(app, ["ustva", "--month", "13", "--db", str(tmp_path / "x.db")])
        assert result.exit_code != 0

    def test_default_is_q1(self, tmp_path):
        db = _db_with(
            tmp_path, _stored(total="119.00", vat="19.00", pct="19", when=datetime(2025, 1, 5))
        )
        result = runner.invoke(app, ["ustva", "--year", "2025", "--db", db])
        assert result.exit_code == 0, result.output
        assert "2025-01-01 bis 2025-03-31" in result.output


class TestCliSuggestPeriod:
    def _run(self, tmp_path, *receipts):
        db = _db_with(tmp_path, *receipts)
        return runner.invoke(app, ["ustva", "--suggest-period", "--year", "2025", "--db", db])

    def test_monthly_above_9000(self, tmp_path):
        # 9 000.01 € tax in 2024 → monthly
        r = _stored(total="56368.48", vat="9000.01", pct=None, when=datetime(2024, 6, 1))
        result = self._run(tmp_path, r)
        assert result.exit_code == 0, result.output
        assert "9000.01" in result.output
        assert "monthly" in result.output

    def test_exactly_9000_is_quarterly(self, tmp_path):
        r = _stored(total="56368.47", vat="9000.00", pct=None, when=datetime(2024, 6, 1))
        result = self._run(tmp_path, r)
        assert "quarterly" in result.output
        assert "monthly" not in result.output
        assert "exemption" not in result.output

    def test_exemption_at_2000(self, tmp_path):
        r = _stored(total="12526.32", vat="2000.00", pct=None, when=datetime(2024, 6, 1))
        result = self._run(tmp_path, r)
        assert "quarterly" in result.output
        assert "exemption possible" in result.output

    def test_large_surplus_mentions_2a(self, tmp_path):
        r = _stored(
            total="66368.47",
            vat="10000.00",
            pct=None,
            when=datetime(2024, 6, 1),
            typ="purchase",
            cat="software",
        )
        result = self._run(tmp_path, r)
        assert "18 Abs. 2a" in result.output

    def test_uses_prior_year_only(self, tmp_path):
        r = _stored(total="119000.00", vat="19000.00", pct=None, when=datetime(2025, 6, 1))
        result = self._run(tmp_path, r)
        assert result.exit_code == 1
        assert "Keine Belege für 2024" in result.output


# ---------------------------------------------------------------------------
# INV-1: finamt invoice new / list / cancel
# ---------------------------------------------------------------------------


class TestCliInvoice:
    def _setup(self, tmp_path):
        import json

        from finamt.storage.sqlite import SQLiteRepository

        db = tmp_path / "inv" / "finamt.db"
        with SQLiteRepository(db_path=db) as repo:
            repo.set_metadata(
                "taxpayer",
                {
                    "name": "Erika Muster",
                    "street": "Teststraße 1",
                    "postcode": "80331",
                    "city": "München",
                    "tax_number": "143/123/45678",
                },
            )
        f = tmp_path / "rechnung.json"
        f.write_text(
            json.dumps(
                {
                    "customer": {
                        "name": "Kunde GmbH",
                        "street": "Hauptstraße 5",
                        "postcode": "10115",
                        "city": "Berlin",
                    },
                    "issue_date": "2025-03-31",
                    "supply_date": "2025-03-31",
                    "lines": [
                        {
                            "description": "Beratung",
                            "quantity": "2",
                            "unit_net": "500",
                            "vat_rate": "19",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return db, f

    def test_new_list_cancel(self, tmp_path):
        db, f = self._setup(tmp_path)
        result = runner.invoke(app, ["invoice", "new", "--file", str(f), "--db", str(db)])
        assert result.exit_code == 0, result.output
        assert "Rechnung 2025-0001: 1190.00 EUR" in result.output
        result = runner.invoke(app, ["invoice", "list", "--db", str(db)])
        assert "2025-0001" in result.output and "Kunde GmbH" in result.output
        result = runner.invoke(app, ["invoice", "cancel", "2025-0001", "--db", str(db)])
        assert result.exit_code == 0, result.output
        assert "storniert 2025-0001" in result.output
        assert list((db.parent / "pdfs").glob("*.pdf"))

    def test_incomplete_invoice_fails(self, tmp_path):
        import json

        db, f = self._setup(tmp_path)
        data = json.loads(f.read_text(encoding="utf-8"))
        data["customer"] = {"name": "Nur Name"}
        f.write_text(json.dumps(data), encoding="utf-8")
        result = runner.invoke(app, ["invoice", "new", "--file", str(f), "--db", str(db)])
        assert result.exit_code == 1
        assert "Leistungsempfängers fehlen" in result.output
