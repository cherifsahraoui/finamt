# Task board

Tasks for AI agents and contributors, in the order they should be done. Each task is a
self-contained card: goal, verified rules, files, steps, tests and a done-when checklist.

## How to work a task

1. Take the **first task with status `ready`** in the board below, unless the owner names another.
2. Read `AGENTS.md`, `docs/DECISIONS.md`, and the rows of `docs/tax-rules.md` the card links to.
   Only use tax values whose status is `verified`. If you need one that is not, stop and add a
   `TODO` row instead of guessing.
3. Make small commits: tests and code for the task, then docs (`NOTICE.md`, this file).
4. When done, set the card status to `done (YYYY-MM-DD)`, move the next card to `ready` if its
   dependencies are met, and update the board.
5. If a card is `blocked` on the owner, don't work around it: point the owner to the matching step
   in [MANUAL-STEPS.md](MANUAL-STEPS.md) (M1–M8) and pick the next `ready` card.

Status values: `ready` (can start now), `waiting` (depends on another task), `blocked`
(needs the owner), `done`.
Size: **S** under 100 changed lines, **M** a few hundred, **L** several sessions.

## Board

| # | ID | Task | Size | Status | Depends on |
|---|---|---|---|---|---|
| 1 | EUR-1 | EÜR Kennzahlen per Anlage EÜR 2025 | M | done (2026-11-18) | — |
| 2 | UST-1 | UStVA: import VAT in Kz 62, not Kz 66 | S | **ready** | — |
| 3 | UST-2 | UStVA: credit notes in the base lines; always send Kz 83 | S | ready | — |
| 4 | EUR-2 | EÜR: VAT lines (140/141/185/186) and Kleinunternehmer mode | M | ready | — |
| 5 | CLI-1 | CLI: `finamt eur`, `finamt ustva --month`, period hint | M | ready | — |
| 6 | UST-3 | UStVA: 0 % rate (Kz 87) and tax-free sales (Kz 48) | S | ready | UST-2 |
| 7 | UST-4 | Reverse charge: flag + Kz 21 / 46 / 47 / 67 / 60 | L | waiting | UST-2 |
| 8 | INV-1 | Outgoing invoices (§ 14 UStG) with gapless numbering | L | ready | — |
| 9 | ZM-1 | Zusammenfassende Meldung (§ 18a UStG) calculation | M | waiting | UST-4 |
| 10 | EUR-3 | Assets above 800 €: AfA / Sammelposten (Anlage AVEÜR) | M | blocked | owner: [M5](MANUAL-STEPS.md#m5-decide-asset-depreciation) |
| 11 | EUR-5 | EÜR: 10-day rule for recurring payments (§ 11 EStG) | S | ready | EUR-2 |
| 12 | CFG-1 | One ERiC path setting (`ERIC_LIBRARY_PATH`) | S | ready | — |
| 13 | EUR-4 | EÜR ELSTER XML builder | L | blocked | owner: [M4](MANUAL-STEPS.md#m4-collect-the-eür-schema-facts-from-eric) |
| 14 | UST-5 | Check Kz rounding and XML with a real ERiC test submission | S | blocked | owner: [M1–M3](MANUAL-STEPS.md#m3-first-ustva-test-submission) |
| 15 | CLN-1 | Remove the remaining E-Bilanz code from `elster.py` | S | ready | — |
| 16 | CLN-2 | Small fixes: `finamt.__all__`, `tests/pytest.ini` | S | ready | — |
| 17 | CLN-3 | Use `vat_splits` for mixed-rate receipts in UStVA/EÜR | M | ready | UST-2 |
| 18 | DOC-1 | Bring `readme/README_de.md` in line with `README.md` | S | ready | — |
| 19 | YEAR-1 | Yearly: verify the new Anlage EÜR / UStVA forms | S | waiting | new BMF forms published ([M7](MANUAL-STEPS.md#m7-yearly-form-check)) |
| 20 | UI-1 | New UI skeleton under `/app` (Jinja2 + htmx), receipt list | M | waiting | EUR-2, CLI-1 |
| 21 | UI-2 | UI: receipt upload, edit, review warnings | M | waiting | UI-1 |
| 22 | UI-3 | UI: UStVA / USt preview, validate, test, live | M | waiting | UI-1, UST-2 |
| 23 | UI-4 | UI: EÜR year view with "ZU PRÜFEN" list | S | waiting | UI-1, EUR-2 |
| 24 | UI-5 | UI: invoices | M | waiting | UI-1, INV-1 |
| 25 | UI-6 | Serve the new UI at `/`, retire the compiled bundle | S | waiting | UI-2 … UI-4, owner OK |

---

## UStVA

### UST-1: import VAT in Kz 62, not Kz 66

- **Status**: ready · **Size**: S
- **Goal**: `_ustva_kennzahlen` adds `report.einfuhr_vat` into Kz 66. On the 2026 form,
  Einfuhrumsatzsteuer has its own line, Kz 62.
- **Verified rules**: tax-rules.md → "UStVA Kennzahlen 2026" rows Kz 66 and Kz 62.
- **Files**: `src/finamt/tax/elster.py` (`_ustva_kennzahlen` only), `tests/unit/test_elster.py`.
- **Steps**:
  1. Kz 66 = `sum(purchase_vat)` only. Kz 62 = `report.einfuhr_vat` (cents), written only if > 0.
  2. Kz 83 stays `output − (Kz 66 + Kz 62)`, unchanged in value.
  3. `Kz62` is already in `_USTVA_KZ_ORDER`; don't reorder.
- **Tests**: a report with only import VAT 50.00 → `{"Kz62": "50.00", "Kz83": "-50.00"}` and no Kz 66;
  a report with both → Kz 66 excludes the import VAT; Kz 83 unchanged versus today.
- **Done when**: tests pass; tax-rules row Kz 62 status → `verified`; NOTICE.md entry.
- **Out of scope**: the annual USt (E50) already uses a separate element for import VAT.

### UST-2: credit notes in the base lines; always send Kz 83

- **Status**: ready · **Size**: S
- **Goal**: `generate_ustva` skips receipts with `vat_amount <= 0`, so credit notes vanish.
  The official guide says § 17 Abs. 1 changes go into the base and tax lines themselves, as
  negative amounts, in the period of the change. Also, Kz 83 must always be sent ("Bitte in
  jedem Fall ausfüllen").
- **Verified rules**: tax-rules.md rows "whole euros / cents" (negative sign), Kz 50 / Kz 37, Kz 83.
- **Files**: `src/finamt/tax/ustva.py`, `src/finamt/tax/elster.py` (`_ustva_kennzahlen`),
  `tests/unit/test_ustva.py`, `tests/unit/test_elster.py`.
- **Steps**:
  1. In `generate_ustva`, treat `vat_amount < 0` like `> 0` (it lands on its rate line with
     negative net and VAT). Keep skipping `vat_amount == 0` / `None` until UST-3.
  2. In `_ustva_kennzahlen`, write Kz 81/86/35 when the base is non-zero, including negative.
     Format negatives with a leading minus.
  3. Always write Kz 83, including `"0.00"` for an empty period.
  4. Don't produce Kz 50/37: they are only for uncollectible amounts.
- **Tests**: invoice 1190/190 plus credit note −595/−95 at 19 % in one quarter → Kz 81 = 500,
  Kz 83 = 95.00; a period with only a credit note → Kz 81 = −500; an empty report → Kz 83 = "0.00".
  Update `tests/unit/test_elster.py::TestUstvaKennzahlen::test_empty_report_no_kz`, which expects
  `{}` today; it becomes `{"Kz83": "0.00"}`.
- **Done when**: tests pass; tax-rules rows Kz 50/37 and Kz 83 → `verified`; NOTICE.md entry.
- **Open check**: the negative-number truncation direction falls under UST-5.

### UST-3: 0 % rate (Kz 87) and tax-free sales (Kz 48)

- **Status**: ready after UST-2 · **Size**: S
- **Goal**: sales with VAT 0 are skipped today. Report 0 %-rate sales (§ 12 Abs. 3) in Kz 87 and
  tax-free sales without input-tax deduction in Kz 48.
- **Verified rules**: tax-rules.md rows 0 %, Kz 87, Kz 48.
- **Files**: `ustva.py`, `elster.py` (`_ustva_kennzahlen`), tests.
- **Steps**: add a receipt flag or subcategory that says *why* VAT is 0: `zero_rate` → Kz 87,
  `tax_free` → Kz 48, `reverse_charge` → UST-4, unknown → warning in the report (not reported).
  Don't infer it from the amount alone.
- **Tests**: one per case; an unknown-reason 0 % sale produces a warning and no Kennzahl.
- **Done when**: tests pass; NOTICE.md entry.

### UST-4: reverse charge flag and Kennzahlen

- **Status**: waiting (UST-2) · **Size**: L
- **Goal**: a freelancer billing EU business clients reports those sales in **Kz 21**
  (§ 18b S. 1 Nr. 2). Services bought from EU businesses (e.g. software subscriptions) are reported
  in **Kz 46 / 47** with the same tax deducted in **Kz 67**. German § 13b supplier cases go to Kz 60.
- **Verified rules**: tax-rules.md rows Kz 21, 45, 46/47, 60, 67, 84/85; § 13b Abs. 1, 5 UStG.
- **Files**: `models.py` (field `reverse_charge: bool`), `storage/sqlite.py` (column + migration
  entry), `ustva.py`, `elster.py` (`_ustva_kennzahlen`), `eur.py` (sales → Kz 103),
  `tests/integration/test_storage.py`, unit tests.
- **Steps**:
  1. Add `reverse_charge: bool = False` to `ReceiptData` and persist it (see AGENTS.md, "DB column").
  2. Sale + reverse_charge → Kz 21 base (whole euros), no output VAT.
  3. Purchase + reverse_charge → Kz 46 base; Kz 47 tax = base × rate (rate from the receipt, else
     19 %); Kz 67 = the same tax. Net effect on Kz 83 is zero.
  4. EÜR: reverse-charge sales → Kz 103.
- **Tests**: EU sale 1000 € → Kz 21 = 1000, Kz 83 unchanged; EU purchase 100 € → Kz 46 = 100,
  Kz 47 = 19.00, Kz 67 = 19.00; storage round-trip of the flag.
- **Done when**: tests pass; tax-rules rows → `verified`; README feature list updated; NOTICE.md.

### UST-5: check rounding and XML with ERiC (owner)

- **Status**: blocked (needs the owner's ERiC library and certificate) · **Size**: S
- **Owner steps**: [MANUAL-STEPS.md M1–M3](MANUAL-STEPS.md#m3-first-ustva-test-submission). The
  owner hands back the ERiC result and messages.
- **Goal**: run `ElsterEricClient.validate_ust` and one test submission for a UStVA with cents in
  the bases. Confirm whether truncation is accepted and whether ERiC reports plausibility hints.
- **Done when**: result recorded in tax-rules.md rows "truncation" and `_USTVA_KZ_ORDER`; decision
  D5 updated if needed.

---

## EÜR

### EUR-1: Kennzahlen per Anlage EÜR 2025

- **Status**: done (2026-11-18). Mapping in `src/finamt/tax/eur.py`, tests in
  `tests/unit/test_eur_mapping.py`, review list for ambiguous receipts.

### EUR-2: VAT lines and Kleinunternehmer mode

- **Status**: ready · **Size**: M
- **Goal**: make the EÜR profit match the official form (D6) and support Kleinunternehmer (D7).
- **Verified rules**: tax-rules.md rows "VAT is income/expense", Kz 111, 112, 140, 141, 185, 186,
  Kleinunternehmer.
- **Files**: `src/finamt/tax/eur.py`, `tests/unit/test_eur*.py`.
- **Steps**:
  1. Add `kleinunternehmer: bool = False` to `generate_eur(...)` and to `EURReport`.
  2. Regelbesteuerung: add income line Kz 140 = sum of sale VAT; expense line Kz 185 = sum of
     purchase VAT (business share); `tax_settlement` purchases with subcategory `vat_payment` →
     Kz 186; sales with subcategory `vat_refund` → Kz 141. Other `tax_settlement` items stay in review.
  3. `gewinn` = all income Kennzahlen − all expense Kennzahlen, VAT included.
  4. Kleinunternehmer: every sale → Kz 111 at the gross amount received; purchases count at
     **gross** (no Kz 185); no Kz 112/140.
  5. Update the summary text (drop the "Nettomethode" warning) and the module docstring.
- **Tests**: remove the strict xfail
  `TestKleinunternehmer::test_purchase_vat_counts_as_expense_for_kleinunternehmer` and make it pass;
  1190/190 sale + 119/19 purchase + 171 VAT paid to the FA → Kz 112 = 1000, 140 = 190, 185 = 19,
  186 = 171, gewinn = 1000 + 190 − 100 − 19 − 171 = 900; Kleinunternehmer 1000 sale + 119 purchase
  → Kz 111 = 1000, expenses 119, gewinn 881. Update existing gewinn assertions that assumed the net method.
- **Done when**: tests pass; tax-rules row "VAT is income/expense" → `verified`; NOTICE.md;
  README status table.

### EUR-3: assets above 800 € (AfA / Sammelposten)

- **Status**: blocked · **Size**: M
- **Owner steps**: [MANUAL-STEPS.md M5](MANUAL-STEPS.md#m5-decide-asset-depreciation).
- **Owner action**: confirm the depreciation approach (straight-line over the useful life from the
  official AfA tables, or the 1-year rule for computer hardware/software per BMF guidance). An agent
  may then fetch and verify the sources (§ 7 EStG, BMF AfA tables) and add rows to tax-rules.md.
- **Goal**: equipment over 800 € net currently goes to review. Build a small asset register
  (purchase date, cost, useful life) and post the yearly AfA to Kz 130, or optionally a
  Sammelposten (Kz 137, § 6 Abs. 2a).
- **Files**: new `src/finamt/tax/assets.py`, `eur.py`, storage table, tests.

### EUR-4: EÜR ELSTER XML builder

- **Status**: blocked (D10: needs the ERiC EÜR XSD, element names and `datenartVersion`) · **Size**: L
- **Owner steps**: [MANUAL-STEPS.md M4](MANUAL-STEPS.md#m4-collect-the-eür-schema-facts-from-eric).
  The owner hands back a facts list (datenartVersion, Verfahren/DatenArt, root element, element
  name per Kennzahl, AVEÜR requirement), or runs an agent locally next to the ERiC docs.
- **Goal**: implement `finamt.tax.eur_elster.build_xml(report)` for the Anlage EÜR.
- **Files**: `src/finamt/tax/eur_elster.py`, `tests/unit/test_eur_elster.py`, `docs/tax-rules.md`.
- **Steps**: map `EURReport.kz_totals()` (plus the EUR-2 lines and Kz 159 / 199 totals) to the XSD
  elements; reuse the envelope pattern of `ElsterXMLBuilder.build_ustva`; Testmerker in test builds.
  Refuse to build if `review_lines` is not empty or `year != FORM_YEAR`.
- **Tests**: golden XML for a fixed report; `validate()` passes; refusal cases; keep the live-mode test.
- **Done when**: plus one manual `submit(mode="test")` by the owner, recorded in tax-rules.md.

### EUR-5: 10-day rule for recurring payments

- **Status**: ready after EUR-2 · **Size**: S
- **Goal**: regularly recurring income and expenses paid within 10 days around 1 January belong to the
  year they relate to (§ 11 Abs. 1 S. 2, Abs. 2 S. 2 EStG; EÜR guide). Typical case: the December
  UStVA payment made on 10 January.
- **Steps**: add an optional `service_period` (year/month) to receipts or a `recurring` flag; in
  `generate_eur`, move qualifying receipts that are both **due and paid** within 10 days before or
  after 1 January (EÜR guide, Zeile 18) to the year they relate to. Show the move in the
  summary.
- **Tests**: VAT payment for December dated 10 Jan of the next year counts in the earlier year;
  dated 11 Jan does not.

---

## CLI and configuration

### CLI-1: `finamt eur`, monthly UStVA, period hint

- **Status**: ready · **Size**: M
- **Goal**: the CLI is the main interface (D2). Add the missing commands.
- **Files**: `src/finamt/cli.py`, `tests/e2e/test_cli_inprocess.py`.
- **Steps**:
  1. `finamt eur --year Y [--output F] [--db P]` → prints `EURReport.summary()`; non-zero exit code if
     `review_lines` is not empty, so it can't be filed by mistake.
  2. `finamt ustva --month M` (mutually exclusive with `--quarter`).
  3. `finamt ustva --suggest-period --year Y`: compute the prior year's tax and print "monthly" if
     > 9 000 €, "quarterly" otherwise, and "exemption possible" if ≤ 2 000 € (§ 18 Abs. 2 UStG,
     verified). Information only.
- **Tests**: in-process CLI tests with a temp DB of stored receipts (no OCR, no LLM).
- **Done when**: `finamt --help` lists `eur`; README usage section updated.

### CFG-1: one ERiC path setting

- **Status**: ready · **Size**: S
- **Goal**: D4. The UStVA/USt submit routes read `ERIC_LIBRARY_PATH` first, then the legacy
  `FINAMT_ERIC_HOME` / project DB value with a deprecation warning.
- **Files**: `src/finamt/ui/api.py` (only the two `eric_home = …` blocks), `.env.example`, tests.

---

## Invoices and ZM

### INV-1: outgoing invoices (§ 14 UStG)

- **Status**: ready · **Size**: L
- **Goal**: create invoices like Accountable does: PDF plus a stored `sale` receipt, with every
  mandatory field and gapless numbering.
- **Verified rules**: tax-rules.md → "Invoices" rows (§ 14 Abs. 4 fields 1–10, § 33 UStDV 250 €).
- **Files**: new `src/finamt/invoicing/` (`model.py`, `numbering.py`, `render.py`),
  `storage/sqlite.py` (invoice sequence table + migration), CLI command `finamt invoice new`, tests
  in `tests/unit/test_invoicing.py`.
- **Steps**:
  1. Model: supplier and customer (name, address, Steuernummer or USt-IdNr), issue date, supply date
     or period, line items (quantity, description, net unit price, VAT rate), notes.
  2. Numbering: format `YYYY-NNNN`, allocated in a DB transaction; never reused, even if an invoice
     is cancelled (cancellations are credit notes with their own number).
  3. Totals: net per VAT rate, VAT per rate, gross. Decimal, rounded per rate line.
  4. Special texts: Kleinunternehmer note (§ 19), reverse-charge note (after UST-4).
  5. Render PDF with PyMuPDF (already a dependency); store it as a `sale` receipt.
- **Tests**: every § 14 Abs. 4 field present; numbers gapless and unique under two concurrent
  allocations; per-rate totals sum to the gross; a credit note references the original invoice.
- **Done when**: tests pass; README feature list; NOTICE.md.

### ZM-1: Zusammenfassende Meldung

- **Status**: waiting (UST-4) · **Size**: M
- **Goal**: aggregate EU B2B service sales (reverse charge) per customer USt-IdNr and quarter;
  due on the 25th day after the quarter (§ 18a Abs. 2, verified).
- **Files**: new `src/finamt/tax/zm.py` (+ later `zm_elster.py` in the `eur_elster.py` pattern), tests.
- **Tests**: sums per VAT ID and quarter; missing VAT ID → error entry; credit notes reduce the sum.

---

## Clean-up and docs

### CLN-1: remove the remaining E-Bilanz code

- **Status**: ready · **Size**: S
- **Files**: `src/finamt/tax/elster.py` (`EBilanzEnvelopeBuilder`, `validate_ebilanz`,
  `submit_ebilanz`, `_run`, `export_ebilanz_xml`), `tests/unit/test_elster.py`
  (`TestEBilanzEnvelopeBuilder`, the `validate_ebilanz` test), `tests/unit/test_safety.py`
  (`test_live_ebilanz_submit_blocked`), `NOTICE.md`, `docs/BASELINE.md`.
- **Done when**: `grep -ri ebilanz src/finamt/tax` is empty; tests pass.

### CLN-2: small fixes

- **Status**: ready · **Size**: S
- `src/finamt/__init__.py`: `__all__` lists `build_extraction_prompt`, which is not imported, so
  `from finamt import *` raises. Remove it from `__all__`. Test: star import works.
- `tests/pytest.ini`: `testpaths = src/tests` is wrong and only used when pytest runs from `tests/`.
  Delete the file; `pyproject.toml` holds the config.

### CLN-3: mixed-rate receipts

- **Status**: ready after UST-2 · **Size**: M
- **Goal**: `ReceiptData.vat_splits` (per-rate net/VAT) are stored but ignored. Tax code puts a
  receipt without a single `vat_percentage` on rate `"unknown"`, which no Kennzahl uses.
- **Steps**: in `generate_ustva`, when `vat_splits` is present, add each split to its rate line;
  when the rate is unknown and there are no splits, add a report warning.

### DOC-1: German README

- **Status**: ready · **Size**: S · Rewrite `readme/README_de.md` to match `README.md`.

### YEAR-1: yearly form check

- **Status**: waiting (new forms are usually published Aug–Dec)
- **Steps**: download the new BMF letters (Anlage EÜR, UStVA Vordruckmuster), compare every
  Kennzahl row in tax-rules.md, update `FORM_YEAR` in `eur.py` only if nothing changed or after
  adapting the mapping, add rows for the new year.

## Web UI (decision D2)

Shared rules for all UI cards:
- Server-rendered pages: FastAPI routes under `/app` in a new package `src/finamt/ui/web/`
  (`routes.py`, `templates/*.html`, `static/`). Jinja2 is already a dependency; add one vendored
  htmx file and record its licence in `NOTICE.md`. **No Node/npm build.**
- Pages call the library directly (`generate_ustva`, `generate_eur`, the repository); don't call
  the HTTP API from Python.
- German labels; amounts formatted with `Decimal`; no float maths in templates.
- Never edit `src/finamt/ui/static/` (the old bundle) or the existing `/tax/...` routes.
- Each page gets a TestClient test that checks status 200 and the key values in the HTML.
- The live-submission gate stays: show the "live" button only if
  `finamt.tax.safety.live_submission_allowed()` is true, and keep the 403 on the backend.

### UI-1: skeleton and receipt list

- **Status**: waiting (EUR-2, CLI-1) · **Size**: M
- **Goal**: `/app` shows a base layout (navigation: Belege, UStVA, EÜR, Rechnungen), a project
  selector (projects from `storage.project.list_projects`), and a read-only receipt list filtered by
  year, period, type and category, with the validation warnings.
- **Files**: `src/finamt/ui/web/` (new), `src/finamt/ui/api.py` (one `app.include_router(...)` line
  placed **before** the SPA catch-all route), `tests/unit/test_web_ui.py`.
- **Done when**: `/app` and `/app/belege` render for an empty and a filled temp DB; the old UI at `/`
  still works.

### UI-2: receipt upload, edit and review

- **Status**: waiting (UI-1) · **Size**: M
- **Goal**: upload PDFs (reuse the agent pipeline the existing upload route uses; mock it in tests),
  edit date, type, category, subcategory, amounts and VAT, delete; show which EÜR line a receipt lands on.

### UI-3: UStVA and annual USt

- **Status**: waiting (UI-1, UST-2) · **Size**: M
- **Goal**: choose month or quarter; show the Kennzahlen preview from `_ustva_kennzahlen`; buttons
  for validate, test submission and (only when allowed) live, using `ElsterEricClient`; list past
  submissions from the project metadata.

### UI-4: EÜR year view

- **Status**: waiting (UI-1, EUR-2) · **Size**: S
- **Goal**: Kennzahlen table for a year, the "ZU PRÜFEN" list with links to edit each receipt in
  UI-2, and a JSON download (`EURReport.to_json`).

### UI-5: invoices

- **Status**: waiting (UI-1, INV-1) · **Size**: M
- **Goal**: create, list and download invoices built by INV-1.

### UI-6: switch over

- **Status**: waiting (UI-2 … UI-4, owner OK) · **Size**: S
- **Goal**: serve the new UI at `/`, move the old bundle to `/legacy-ui` for one release, then delete
  it together with the `/tax/ebilanz/*` settings routes it needed. Record it in `NOTICE.md`.
