# FreiBuch (finamt fork) — baseline map

Snapshot of the code as of the `baseline/fable-1` branch (package version 0.26.0).
Scope of this fork: **UStVA, annual USt and EÜR for a single Freiberufler**.
Read `AGENTS.md` before changing code. Tasks: `docs/TODO.md`. Decisions: `docs/DECISIONS.md`.
Owner-only steps: `docs/MANUAL-STEPS.md`.
Tax values and their sources: `docs/tax-rules.md`.

## Package map (`src/finamt/`)

| Path | Responsibility |
|---|---|
| `__init__.py` | Public exports: `FinanceAgent`, `Config`, models, exceptions. |
| `cli.py` | Typer CLI (`finamt` entry point). |
| `models.py` | `ReceiptData`, `Counterparty`, `ReceiptItem`, `Posting`; net/VAT/business-share derivations (`net_amount`, `business_net`, `business_vat`). |
| `agents/` | Extraction: `agent.py` (`FinanceAgent.process_receipt`), `pipeline.py` (4 sequential LLM agents), `llm_backend.py`/`llm_caller.py` (mlx-lm / transformers), `prompts.py` (`RECEIPT_CATEGORIES`), `config.py` (pydantic settings, env prefix `FINAMT_`). |
| `ocr_processor.py` | PDF text extraction (PyMuPDF) with PaddleOCR / Tesseract fallback. |
| `storage/` | `sqlite.py` (`SQLiteRepository`), `project.py` (`~/.finamt/<project>/` layout), `base.py` (repository protocol), `get_repository()`. |
| `tax/ustva.py` | `generate_ustva()` → `USTVAReport` (per-rate input/output VAT; 0 %, tax-free and reverse-charge amounts from `ReceiptData.vat_treatment`). |
| `tax/zm.py` | `generate_zm(receipts, year, quarter)` → `ZMReport`: EU B2B services per customer VAT ID (ZM-1). No ELSTER/BZSt boundary yet. |
| `tax/eur.py` | `generate_eur()` → `EURReport`: EÜR lines per Anlage EÜR 2025 Kennzahl (`KZ_LABELS`, `_PURCHASE_KZ`, `_PURCHASE_SUB_KZ`); ambiguous receipts in `review_lines`, excluded from the profit. |
| `tax/elster.py` | ELSTER XML for UStVA and annual USt (E50), Kz mapping `_ustva_kennzahlen`, signer, HTTP client, ERiC client. |
| `tax/eric_wrapper.py` | ctypes bridge to the ERiC shared library (`EricSession`, `EricBuffer`, `EricCertificate`). Targets the ERiC 44 API (no transfer handle). |
| `tax/eur_elster.py` | EÜR ELSTER boundary: `build_xml` (Anlage EÜR 2025 envelope, test builds only; field table `_BEIN_FIELDS` / `_BAUS_FIELDS` in XSD order, `EURTaxpayer` for the form header), `eric_validate` (ERiC, nothing sent), `validate` (offline), `submit` (dry_run/test only). |
| `tax/safety.py` | Live-submission gate (`FINAMT_ALLOW_LIVE_SUBMISSION`). |
| `tax/bundesland.py` | The 16 Länder in one place (name, ELSTER `<Ziel>` code, Länderschlüssel 01–16, Landesnummern) and `steuernummer_info()` (13-digit ELSTER number + Finanzamtsnr., or a German error). |
| `ui/api.py` | FastAPI backend for the old web UI; calls `ui.web.register(app)` before the SPA catch-all. |
| `ui/web/` | FreiBuch's own UI under `/app` (D2): `routes.py` (pages; sending calls `post_ustva_submit` / `post_uste_submit` in-process so the live gate stays in one place), `helpers.py` (projects via `?projekt=`, German formats, periods and UStVA deadlines, `eur_zeile()` per receipt), `templates/` (Jinja2), `static/` (`app.css`, vendored `htmx.min.js`). Stores data under the old UI's metadata keys (`taxpayer`, `elster_misc`, `elster_eric_home`, `submissions`) plus `freibuch_settings` (UStVA period, Dauerfristverlängerung, `kleinunternehmer_jahre`). `uploads.py`: one background upload job at a time (in memory), shown on every page by `_upload_status.html` (htmx poll). `i18n.py`: `_()` with German keys and an English dictionary, language in the `freibuch_lang` cookie. Pages: Übersicht, Belege (+ manual entry), UStVA (+ XML download), EÜR, Rechnungen, Partner, Archiv, Projekte, Stammdaten. Taxpayer profile: `tax_number` is the Umsatzsteuer number (UStVA, USt; the old UI uses it too), optional `tax_number_est` the Einkommensteuer number, `euer_steuernummer` (`est`/`ust`) the number for the Anlage EÜR; `helpers.steuernummer_fuer(tp, zweck)` picks the right one. |
| `ui/server.py` | Uvicorn launcher (`finamt serve`). |
| `ui/static/` | **Pre-built** React bundle (no source; upstream doesn't publish it). Frozen per D2 (never edited). Served at `/legacy-ui` since UI-6 (no client-side router, so the path doesn't matter; its assets stay at `/assets/…`); deleted in CLN-5. |
| `invoicing/` | Outgoing invoices (INV-1): `model.py` (Invoice, per-rate totals, § 14 field check), `numbering.py` (`YYYY-NNNN`), `render.py` (PDF, PyMuPDF with embedded Helvetica for €/–), `service.py` (`issue_invoice` → number, PDF, sale receipt; `cancel_invoice` → Rechnungskorrektur). Numbers come from `SQLiteRepository.create_invoice` (tables `invoice_sequence`, `invoices`; number and row in one `BEGIN IMMEDIATE` transaction). |
| `utils.py`, `progress.py`, `exceptions.py` | Parsing helpers, SSE progress events, exception types. |

Outside the package: `scripts/ustva_test_submission.py` and `scripts/eur_test_submission.py` run a
fixed UStVA / Anlage EÜR test case through ERiC (validate, or `--send` with Testmerker to the test
Finanzamt; owner step M2). `private/`
(git-ignored) holds the owner's ERiC, its documentation and the certificate. `legacy/` holds the removed KSt / E-Bilanz / Jahresabschluss code
(not packaged, not tested, not linted). `examples/`, `notebooks/`, `docs/` (Sphinx).

## Entry points

### CLI (`finamt …`, `src/finamt/cli.py`)

| Command | Purpose |
|---|---|
| `finamt --version` | Print version. |
| `finamt process FILE --input-dir DIR` | Extract one PDF (OCR + LLM), save to DB. |
| `finamt batch --input-dir DIR` | Extract all PDFs in a directory. |
| `finamt ustva --quarter Q --year Y [--input-dir DIR] [--output F]` | Print/write a quarterly UStVA report (JSON). No ELSTER submission. |
| `finamt ustva --month M` / `--suggest-period --year Y` | Monthly UStVA; monthly/quarterly hint from the prior year's tax (CLI-1). |
| `finamt eur --year Y [--kleinunternehmer] [--xml F] [--validate] [--pdf F]` | EÜR summary; exit code 1 while receipts need review (CLI-1). `--xml` / `--validate` / `--pdf`: Anlage EÜR XML, ERiC check, ERiC print preview (EUR-9, PRINT-1); need `--art-des-betriebs` and `--grundstuecke ja|nein`. |
| `finamt invoice new --file F.json` / `list` / `cancel NUMBER` | Outgoing invoices (INV-1). |
| `finamt serve [--port 8000]` | Start the web UI (`ui/server.py` → `ui/api.py`); `/` redirects to `/app`. |

### HTTP API (`src/finamt/ui/api.py`)

Every route takes an optional `?db=` path. Groups:

- Meta: `GET /health`, `GET /fx-rate`, `GET|PUT /config`.
- Projects: `GET|POST /projects`, `DELETE /projects/{name}`, `GET /databases`,
  `GET|PUT|DELETE /taxpayer`, `GET|POST|PATCH|DELETE /submissions`,
  `POST|DELETE /submissions/document`, `GET /submissions/file`, `GET /submissions/result`,
  `GET|POST /geocode-cache`.
- Receipts: `POST /receipts` (manual), `POST /receipts/upload`, `POST /receipts/upload/stream` (SSE),
  `GET /receipts`, `GET|PATCH|DELETE /receipts/{id}`, `GET /receipts/{id}/pdf`,
  `POST /receipts/{id}/counterparty`.
- Counterparties: `GET /counterparties`, `GET /counterparties/verified`,
  `GET /counterparties/{id}/defaults`, `PATCH|DELETE /counterparties/{id}`,
  `PATCH /counterparties/{id}/verify`.
- Tax: `GET /tax/ustva`, `POST /tax/ustva/submit`, `POST /tax/ustva/xml`,
  `POST /tax/uste/submit`, `POST /tax/uste/xml`.
- ELSTER settings (shared by UStVA/USt despite the historical path name):
  `GET|POST /tax/ebilanz/settings`, `GET|POST /tax/ebilanz/eric-home`, `GET|POST /tax/ebilanz/cert`.
- SPA fallback `GET /{path}` serves `ui/static/`.

EÜR is not exposed by the API; the bundled UI computes its EÜR view client-side.

## Receipt flow: upload → UStVA / EÜR

1. **Input**: PDF/image via `POST /receipts/upload[/stream]`, `finamt process|batch`, or manual entry `POST /receipts`.
2. **OCR**: `OCRProcessor.extract_text_from_pdf` (PyMuPDF text layer, else PaddleOCR, else Tesseract).
3. **Dedup**: `id = sha256(raw_text)`; `SQLiteRepository.exists(id)` → duplicate result.
4. **Extraction**: `agents/pipeline.run_pipeline` → 4 LLM agents (metadata, counterparty,
   amounts, line items) → `_reconcile_vat` fixes VAT rate from amounts → `ReceiptData`.
5. **Validation**: `ReceiptData.validate()` stores warnings; receipts are always saved.
6. **Storage**: `SQLiteRepository.save()` (receipts, counterparties, items, vat_splits, postings) in
   `~/.finamt/<project>/finamt.db`; web UI uploads also keep the file under `~/.finamt/<project>/pdfs/`.
7. **UStVA**: `repo.find_by_period(start, end)` → `generate_ustva()` → `USTVAReport`
   → `elster._ustva_kennzahlen()` (Kz 81/86/35/36/66/83) → `ElsterXMLBuilder.build_ustva()`
   → `ElsterEricClient.validate_ust()/submit_ust()` (ERiC) (`ElsterClient`, direct HTTP, is not used by CLI/API).
8. **Annual USt**: same report over the year, `period=0` → `_build_ust_annual_e50()`.
9. **EÜR**: `repo.find_by_period(Jan 1, Dec 31)` → `generate_eur()` → `EURReport`
   (category/subcategory → Kennzahl, or `review_lines`) → `eur_elster.build_xml(report, taxpayer,
   entnahmen=, einlagen=, hersteller_id=)` (refuses open review lines, AfA, Kz 151, Kz 112 without
   Kz 140) → `eur_elster.eric_validate()` / `submit(mode="test")`. Live is disabled.

Money is `Decimal` throughout `tax/` (see `tests/unit/test_decimal_rule.py`).
`ReceiptData.to_dict()` emits floats for JSON only; do not feed that back into tax code.
The API takes some amounts as `float` in request models and converts them with `Decimal(str(x))`.

## Commands

```bash
uv sync --extra dev                       # install (creates .venv, Python 3.10 per .python-version)
uv run pytest                             # tests (offline; no LLM, OCR model, ERiC or network)
                                          # config: [tool.pytest.ini_options] in pyproject.toml
uv run ruff check src tests               # lint
uv run ruff format --check src tests      # format check
uv run finamt --help                      # CLI
```

## Large files (do not refactor wholesale)

| File | Lines | Responsibilities |
|---|---|---|
| `ui/api.py` | ~2.1k | All HTTP routes; project/taxpayer/submission bookkeeping; UStVA/USt submit endpoints duplicate ElsterConfig + ERiC setup inline (candidate for extraction); ELSTER settings persisted in DB metadata. |
| `tax/elster.py` | ~1.7k | ElsterConfig/env, Steuernummer normalisation, UStVA Kz mapping + XSD order, XML builder (UStVA, USt E50), RSA signer, HTTP `ElsterClient`, ERiC `ElsterEricClient`. E-Bilanz code removed (CLN-1). |
| `storage/sqlite.py` | ~1.3k | Schema + in-place migrations, receipt CRUD, counterparties (find-or-create, verify, defaults), postings, vat_splits, metadata KV store. |

## Known gaps (details in `docs/TODO.md`)

- EÜR ELSTER XML (Kennzahlen not verified), EÜR CLI/API.
- EÜR: assets > 800 € go to review (EUR-3).
- Receipts without German VAT are reported only with a `vat_treatment` (UST-3/4); otherwise a
  report warning. The annual USt (E50) refuses 0 % / tax-free / reverse-charge amounts.
- `vat_splits` are used by the UStVA for receipts without a single rate (CLN-3).
- ZM is calculated (`tax/zm.py`) but cannot be sent; invoices have no reverse-charge note yet.
- Upload jobs live in memory: a server restart drops an unfinished job (saved receipts stay).
