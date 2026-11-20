# Task board

Tasks for AI agents and contributors, in the order they should be done. Each task is a
self-contained card: goal, verified rules, files, steps, tests and a done-when checklist.

## How to work a task

1. Take the **first task with status `ready`** in the board below, unless the owner names another.
2. Read `AGENTS.md`, `docs/DECISIONS.md`, and the rows of `docs/tax-rules.md` the card links to.
   Only use tax values whose status is `verified`. If you need one that is not, stop and add a
   `TODO` row instead of guessing.
3. Work on the current work branch (see `AGENTS.md` rule 8); don't open a branch per task.
   Make small commits: tests and code for the task, then docs (`NOTICE.md`, this file).
4. When done, set the card status to `done (YYYY-MM-DD)`, move the next card to `ready` if its
   dependencies are met, and update the board.
5. If a card is `blocked` on the owner, don't work around it: point the owner to the matching step
   in [MANUAL-STEPS.md](MANUAL-STEPS.md) (M1–M6) and pick the next `ready` card.

Status values: `ready` (can start now), `waiting` (depends on another task), `blocked`
(needs the owner), `done`.
Size: **S** under 100 changed lines, **M** a few hundred, **L** several sessions.

## Board

| # | ID | Task | Size | Status | Depends on |
|---|---|---|---|---|---|
| 1 | EUR-1 | EÜR Kennzahlen per Anlage EÜR 2025 | M | done (2026-11-18) | — |
| 2 | UST-1 | UStVA: import VAT in Kz 62, not Kz 66 | S | done (2026-11-20) | — |
| 3 | UST-2 | UStVA: credit notes in the base lines; always send Kz 83 | S | done (2026-11-20) | — |
| 4 | EUR-2 | EÜR: VAT lines (140/141/185/186) and Kleinunternehmer mode | M | done (2026-11-20) | — |
| 5 | CLI-1 | CLI: `finamt eur`, `finamt ustva --month`, period hint | M | done (2026-11-20) | — |
| 6 | UST-3 | UStVA: 0 % rate (Kz 87) and tax-free sales (Kz 48) | S | done (2026-11-20) | UST-2 (done) |
| 7 | UST-4 | Reverse charge: flag + Kz 21 / 46 / 47 / 67 / 60 | L | done (2026-11-20) | UST-2 (done) |
| 8 | INV-1 | Outgoing invoices (§ 14 UStG) with gapless numbering | L | done (2026-11-20) | — |
| 9 | ZM-1 | Zusammenfassende Meldung (§ 18a UStG) calculation | M | done (2026-11-20) | UST-4 (done) |
| 10 | EUR-3 | Assets above 800 €: AfA / Sammelposten (Anlage AVEÜR) | M | blocked | owner: [M3](MANUAL-STEPS.md#m3-decide-asset-depreciation) |
| 11 | EUR-5 | EÜR: 10-day rule for recurring payments (§ 11 EStG) | S | blocked | source for the 10-day window (tax-rules.md "cash basis") |
| 12 | CFG-1 | One ERiC path setting (`ERIC_LIBRARY_PATH`) | S | done (2026-11-20) | — |
| 13 | EUR-4 | EÜR ELSTER XML builder | L | done (2026-11-20) | — |
| 14 | UST-5 | Check Kz rounding and XML with a real ERiC test submission | S | blocked | ERiC validation done; test send needs owner: [M1–M2](MANUAL-STEPS.md#m2-first-test-submission) |
| 15 | CLN-1 | Remove the remaining E-Bilanz code from `elster.py` | S | ready | — |
| 16 | CLN-2 | Small fixes: `finamt.__all__`, `tests/pytest.ini` | S | ready | — |
| 17 | CLN-3 | Use `vat_splits` for mixed-rate receipts in UStVA/EÜR | M | ready | UST-2 (done) |
| 18 | DOC-1 | Bring `readme/README_de.md` in line with `README.md` | S | ready | — |
| 19 | YEAR-1 | Yearly: verify the new Anlage EÜR / UStVA forms | S | waiting | new BMF forms published ([M5](MANUAL-STEPS.md#m5-yearly-update)) |
| 20 | UI-1 | New UI skeleton under `/app` (Jinja2 + htmx), receipt list | M | done (2026-11-20) | — |
| 21 | UI-2 | UI: receipt upload, edit, review warnings | M | done (2026-11-20) | — |
| 22 | UI-3 | UI: UStVA / USt preview, validate, test, live | M | done (2026-11-20) | figures improve with UST-2 |
| 23 | UI-4 | UI: EÜR year view with "ZU PRÜFEN" list | S | done (2026-11-20) | VAT lines come with EUR-2 |
| 24 | UI-5 | UI: invoices | M | done (2026-11-20) | INV-1 (done) |
| 25 | UI-6 | Serve the new UI at `/`, retire the compiled bundle | M | done (2026-11-20) | UI-5, UI-8, owner OK (2026-11-20) |
| 26 | ERIC-1 | ERiC 44 API: `EricBearbeiteVorgang` without transfer handle | S | done (2026-11-20) | — |
| 27 | CLN-4 | No "—" placeholder in the UStVA sender address (ERiC rejects it) | S | ready | — |
| 28 | EUR-6 | EÜR test submission with the owner's Hersteller-ID | S | blocked | owner: [M1–M2](MANUAL-STEPS.md#m2-first-test-submission) |
| 29 | EUR-7 | EÜR XML: Kz 151 needs the Zeile 42 split (Kz 153) | S | ready | owner input on the split |
| 30 | UI-7 | UI: Stammdaten and ELSTER settings (Bundesland dropdown) | M | done (2026-11-20) | — |
| 31 | UI-8 | UI: the old UI's remaining features (manual entry, projects, partners, XML) | M | done (2026-11-20) | — |
| 32 | CLN-5 | Remove old UI, rename project to FreiBuch (fork of finamt) | L | waiting | UI-6 (done); one release with `/legacy-ui` first |
| 33 | EUR-8 | Kleinunternehmer flag per year in Stammdaten, used by the EÜR page | S | done (2026-11-20) | — |
| 34 | UI-9 | Uploads as a background job; progress on every page; one at a time | S | done (2026-11-20) | owner bug report |
| 35 | UI-10 | Language switch DE/EN for `/app` | M | done (2026-11-20) | owner request |
| 36 | INV-2 | Verify the § 19 invoice note (§ 34a UStDV) and the invoice VAT rounding source | S | ready | — |
| 37 | PRINT-1 | Official print PDF (ERiC) for UStVA, annual USt and EÜR, kept in the archive | M | done (2026-11-20) | — |
| 38 | EUR-9 | EÜR: ERiC check, XML download and test send from the web UI and CLI | M | done (2026-11-20) | — |

---

## UStVA

### UST-1: import VAT in Kz 62, not Kz 66

- **Status**: done (2026-11-20) · **Size**: S
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

- **Status**: done (2026-11-20) · **Size**: S
- **Result**: negative receipts stay on their rate line; Kz 81/86/35 and Kz 66 are written
  when non-zero (negatives with a minus, Kz 66 too, so Kz 83 matches the lines); Kz 83 is always
  written. Tests in `tests/unit/test_ustva.py` and `TestUstvaKennzahlen`.
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

- **Status**: done (2026-11-20) · **Size**: S
- **Result**: one receipt field `vat_treatment` (`zero_rate`, `tax_free`, `reverse_charge`),
  shared with UST-4 instead of a second flag; set in the receipt form ("USt-Behandlung").
  Base = `total_amount`. A sale without VAT and without a reason adds a report warning; a receipt
  with a treatment that still shows VAT is refused with a warning. Tests:
  `tests/unit/test_ustva_special.py`.
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

- **Status**: done (2026-11-20) · **Size**: L
- **Result**: `ReceiptData.reverse_charge` is a property over `vat_treatment` (see UST-3).
  The Kennzahl follows the counterparty's VAT ID prefix, else a two-letter country code:
  sale → Kz 21 (EU), Kz 60 (DE), Kz 45 (non-EU); purchase → Kz 46/47 (EU) or Kz 84/85 (DE,
  non-EU), Kz 67 = tax × business share. Unknown counterparty country → warning, not reported.
  EÜR: such sales → Kz 103. The annual USt (E50) raises `NotImplementedError` while any of these
  amounts is present (E50 fields unverified). Open: the EU prefix list's `GB` / `XI` handling
  (tax-rules.md row "EU VAT ID prefixes"); the reverse-charge note on invoices (INV-1) is not
  added yet.
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

- **Status**: blocked on the owner for the last step · **Size**: S
- **Done on 2026-11-20**: `ElsterEricClient.validate_ust` with ERiC 44.3.6.0 (Windows x86-64) on a
  UStVA with net 1 000.99 € at 19 %: valid for 2025 and 2026 (Kz 81 = `1000`, Kz 83 = `171.19`),
  no hints. Annual USt (E50) valid for 2024 and 2025. Recorded in tax-rules.md ("truncation",
  `_USTVA_KZ_ORDER`, `Zeitraum`).
- **Open**: one **test submission** (Testmerker, test tax number) to see whether the ELSTER server
  accepts it. Needs the owner's Hersteller-ID and certificate PIN:
  [MANUAL-STEPS.md M1–M2](MANUAL-STEPS.md#m2-first-test-submission). The owner hands back the result.
- **Done when**: server result recorded in tax-rules.md row "truncation"; decision D5 updated if needed.

---

## EÜR

### EUR-1: Kennzahlen per Anlage EÜR 2025

- **Status**: done (2026-11-18). Mapping in `src/finamt/tax/eur.py`, tests in
  `tests/unit/test_eur_mapping.py`, review list for ambiguous receipts.

### EUR-2: VAT lines and Kleinunternehmer mode

- **Status**: done (2026-11-20) · **Size**: M
- **Result**: `generate_eur(receipts, year, kleinunternehmer=False)`. Regelbesteuerung: Kz 140 /
  Kz 185 come from the lines' VAT (`EURReport.kz140_ust_vereinnahmt`, `kz185_vorsteuer`, also in
  `kz_totals()`); `vat_payment` → Kz 186 and `vat_refund` → Kz 141 at the total amount; `gewinn` =
  `total_betriebseinnahmen − total_betriebsausgaben`. Kleinunternehmer: sales → Kz 111, all amounts
  gross from `total_amount`, GWG limit compared with the gross cost (conservative: more review).
  EÜR page shows the VAT lines. Tests: `tests/unit/test_eur_vat.py`. Wiring the flag: EUR-8.
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
- **Owner steps**: [MANUAL-STEPS.md M3](MANUAL-STEPS.md#m3-decide-asset-depreciation).
- **Owner action**: confirm the depreciation approach (straight-line over the useful life from the
  official AfA tables, or the 1-year rule for computer hardware/software per BMF guidance). An agent
  may then fetch and verify the sources (§ 7 EStG, BMF AfA tables) and add rows to tax-rules.md.
- **Goal**: equipment over 800 € net currently goes to review. Build a small asset register
  (purchase date, cost, useful life) and post the yearly AfA to Kz 130, or optionally a
  Sammelposten (Kz 137, § 6 Abs. 2a).
- **Files**: new `src/finamt/tax/assets.py`, `eur.py`, storage table, tests.
- **EÜR XML** (`eur_elster.build_xml`) refuses Kz 130/131/132/136/137 until this card is done; AfA
  lines then also need Anlage AVEÜR. Found 2026-11-20: Kz 132 (GWG) alone passes ERiC without
  AVEÜR, so GWG could be unblocked separately if the owner wants (tax-rules.md).

### EUR-4: EÜR ELSTER XML builder

- **Status**: done (2026-11-20) · **Size**: L
- **Result**: `eur_elster.build_xml(report, taxpayer, entnahmen=, einlagen=, hersteller_id=)` builds
  the Anlage EÜR 2025 envelope (test builds only, Testmerker). Kz 159 / 199 and the profit lines
  (Zeilen 76, 77, 92, 95, 97) are computed; Entnahmen / Einlagen (Zeilen 106/107) are arguments
  because ERiC requires them for sole proprietors. `eric_validate(xml)` runs ERiC without sending.
  Facts and ERiC rule numbers: tax-rules.md → "Anlage EÜR 2025: lines and rules used by …".
- **Refuses** (so nothing invalid or guessed is built): open `review_lines`; `year != FORM_YEAR`;
  Kz 112 without Kz 140 (ERiC rule 600240); AfA / GWG Kz 130/131/132/136/137 (EUR-3); Kz 151 (EUR-7);
  Kz 234 above 2 050 € (needs Anlage SZ); `test=False` (live disabled, D3).
- **Checked**: XSD and ERiC 44.3 validation (nothing sent) for the golden report and four other
  reports, with a placeholder Hersteller-ID. Tests: `tests/unit/test_eur_elster.py` (golden XML,
  refusals; `TestRealEric` skips without `ERIC_LIBRARY_PATH` and `FINAMT_ELSTER_HERSTELLER_ID`).
- **Follow-ups**: EUR-6 (owner's server test), EUR-7 (Kz 151 / Zeile 42).

### EUR-6: EÜR test submission (owner)

- **Note (2026-11-20)**: with two Steuernummern, send the EÜR test under the number chosen in
  Stammdaten ("Anlage EÜR abgeben unter"); which one is right is still a `TODO` in tax-rules.md
  (row "two Steuernummern"). `scripts/eur_test_submission.py` reads `FINAMT_ELSTER_STEUERNUMMER`.

- **Status**: blocked on the owner · **Size**: S
- **Owner steps**: [MANUAL-STEPS.md M1–M2](MANUAL-STEPS.md#m2-first-test-submission), steps 3–4
  (`scripts/eur_test_submission.py`, then `--send`). Needs the owner's Hersteller-ID and certificate.
- **Done when**: the server result (success, telenummer or error) is recorded in tax-rules.md row
  "server acceptance" of the Anlage EÜR 2025 section.

### EUR-7: Kz 151 needs the Zeile 42 split (Kz 153)

- **Status**: ready · **Size**: S
- **Goal**: ERiC rule 600522 requires Zeile 41 (Kz 151, sonstige Grundstücksaufwendungen) and
  Zeile 42 (Kz 153, "in Zeile 41 enthaltene Erhaltungsaufwendungen") together. `eur.py` maps
  utilities, cleaning, security and property insurance to Kz 151, so `build_xml` refuses such reports.
- **Verified rules**: tax-rules.md rows "Kz 153 (Zeile 42)".
- **Steps**: decide with the owner how to know the maintenance share (a receipt subcategory such as
  `maintenance`, or a report field); add Kz 153
  (`BAus/Raumkosten_u_sonst/Davon_Erhalt_Grundstueck/Sum/E6004015`) to `_BAUS_FIELDS` right after
  Kz 151 (XSD order). It is a "davon" line: keep it out of the Kz 199 total (not in rule 600614).
  Send it whenever Kz 151 is sent (0 only when the owner confirms there is none). Don't guess the split.
- **Tests**: Kz 151 with Kz 153 builds and validates; Kz 151 without a Kz 153 decision still refuses.

### EUR-5: 10-day rule for recurring payments

- **Status**: blocked (2026-11-20) · **Size**: S
- **Blocked on**: a source for the window. § 11 Abs. 1 S. 2 EStG (read 2026-11-20) only says
  "kurze Zeit"; the 10 days and the "due and paid" condition come from H 11 EStH / the EÜR guide,
  which could not be read (esth.bundesfinanzministerium.de and bundesfinanzministerium.de returned
  HTTP 503). Read one of them, update tax-rules.md row "cash basis", then set this card to ready.
- **Goal**: regularly recurring income and expenses paid within 10 days around 1 January belong to the
  year they relate to (§ 11 Abs. 1 S. 2, Abs. 2 S. 2 EStG; EÜR guide). Typical case: the December
  UStVA payment made on 10 January.
- **Steps**: add an optional `service_period` (year/month) to receipts or a `recurring` flag; in
  `generate_eur`, move qualifying receipts that are both **due and paid** within 10 days before or
  after 1 January (EÜR guide, Zeile 18) to the year they relate to. Show the move in the
  summary.
- **Tests**: VAT payment for December dated 10 Jan of the next year counts in the earlier year;
  dated 11 Jan does not.

### EUR-8: Kleinunternehmer flag per year

- **Status**: done (2026-11-20): years in Stammdaten (`freibuch_settings.kleinunternehmer_jahre`); EÜR page, overview, JSON and the invoice form use them. The UStVA-page note (no UStVA for such a year) is still open and needs a verified rule first · **Size**: S
- **Goal**: decision D7 wants a per-year flag in the taxpayer profile. `generate_eur` has
  `kleinunternehmer=` since EUR-2, but every caller still uses Regelbesteuerung.
- **Verified rules**: tax-rules.md section "Kleinunternehmer (§ 19 UStG)".
- **Files**: `src/finamt/ui/web/` (Stammdaten form: list of years with § 19; EÜR page and
  overview pass the flag), `tests/unit/test_web_ui.py`; later CLI-1's `finamt eur`.
- **Steps**: store the years in the taxpayer metadata (new field, e.g. `kleinunternehmer_jahre`,
  without breaking the old UI's `GET /taxpayer`); `/app/euer?jahr=Y` calls
  `generate_eur(..., kleinunternehmer=Y in jahre)`; the UStVA page shows a note that no UStVA is
  due for such a year (§ 19 Abs. 1 UStG; check the exact rule in tax-rules.md first).
- **Tests**: a year flagged → EÜR page shows Kz 111 and no Kz 140/185; unflagged → unchanged.

### PRINT-1: official print PDF for UStVA, annual USt and EÜR

- **Status**: done (2026-11-20) · **Size**: M
- **Result**: rules verified from the ERiC 44.3 docs (tax-rules.md "ERiC printing"). `pdf_path` on `ElsterEricClient.validate_ust/submit_ust` and `eur_elster.eric_validate/submit`; `api.py` field `pdf` (preview to a temp file, or the copy in `submitted_returns/` recorded as `pdf_filename`); buttons on `/app/ustva` and `/app/euer`; `finamt eur --pdf`. Real ERiC run: previews for UStVA, USt and EÜR 2025 (dummy Hersteller-ID, nothing sent). The copy after a real send is untested until M1–M2.
- **Goal**: a human-readable copy of every return in the official ELSTER layout, without any
  template file in the repo: ERiC renders it. Today the archive (`/app/archiv`) keeps only the
  sent XML.
- **Found**: `tax/eric_wrapper.py` already defines `ERIC_DRUCKE` (bit 5) and
  `_eric_druck_parameter_t` (`version`, `vorschau`, `duplexDruck`, `pdfName`, `fussText`,
  `pdfCallback`), but every call passes `None` as print parameter.
- **Verify first (D10)**: in `private/ERiC-44.3.6.0/Dokumentation/` (developer handbook) check
  how `EricBearbeiteVorgang` prints: which `version` of the print parameters ERiC 44 expects,
  whether printing works together with validate-only and with send, what `vorschau` changes
  (watermark "Vorschau" for unsent / test cases?), and whether the PDF comes through `pdfName` or
  the callback. Record the answers in tax-rules.md (new section "ERiC printing"). Don't guess.
- **Steps**:
  1. `eric_wrapper.bearbeite_vorgang(..., druck_pdf: Path | None = None)`: when set, add
     `ERIC_DRUCKE` and fill the print parameters as the handbook says.
  2. UStVA and annual USt (`ElsterEricClient.submit_ustva` / `submit_ust` / `validate_ust`):
     optional `pdf_path`; on a successful binding send, store the PDF in `submitted_returns/`
     next to the XML and record `pdf_filename` in the submission (same metadata as today).
  3. EÜR (`eur_elster.eric_validate` / `submit`): same option.
  4. Web UI: a "Druckansicht (PDF)" button next to "XML herunterladen" on `/app/ustva` (preview,
     nothing sent); the archive lists `pdf_filename`. EÜR comes with EUR-9.
  5. CLI: `--pdf F` on the commands that call ERiC.
- **Tests** (offline, fake ERiC as in `tests/unit/test_eric_wrapper.py`): the flag and the print
  parameters are passed only when asked; the PDF path is stored in the submission record; a
  failed send stores no PDF. A real-ERiC test skips without `ERIC_LIBRARY_PATH`.
- **Done when**: tests pass; tax-rules "ERiC printing" rows verified; README feature table.

### EUR-9: EÜR check, XML download and test send from the web UI and CLI

- **Status**: done (2026-11-20) · **Size**: M
- **Result**: "An ELSTER" section on `/app/euer` (check, XML, preview, test send; no live), `finamt eur --xml / --validate / --pdf`. ERiC path: `ERIC_LIBRARY_PATH`, else Stammdaten (`eur_elster` got an optional `eric_home`).
- **Goal**: the Anlage EÜR XML builder (EUR-4) is only reachable from Python
  (`finamt.tax.eur_elster`). Give it the same buttons the UStVA has.
- **Steps**:
  1. `/app/euer`: "Mit ERiC prüfen", "XML herunterladen", "Testfall senden" (Testmerker). Take the
     taxpayer data from Stammdaten (`helpers.steuernummer_fuer(tp, "euer")`), the Hersteller-ID
     and certificate as the UStVA page does; Entnahmen / Einlagen (Zeilen 106/107) as two input
     fields, because ERiC requires them (tax-rules.md, EUR-4 section).
  2. Show `build_xml`'s refusals as messages (open ZU PRÜFEN lines, AfA / EUR-3, Kz 151 / EUR-7,
     Kz 234 above 2 050 €) instead of an error page.
  3. CLI: `finamt eur --year Y --xml F` and `--validate` (ERiC, nothing sent).
  4. Live sending stays disabled for the EÜR (D3, `eur_elster` raises); no live button.
- **Tests**: TestClient with a fake ERiC: check, XML download, test send call `eur_elster` with
  the Stammdaten values; refusals are shown; no live button even with the live flag set
  (patched check, never the env var).
- **Depends**: nothing to build; a real test send still needs the owner (EUR-6, M1–M2).

### INV-2: verify the open invoice rules

- **Status**: ready · **Size**: S
- **Goal**: two `TODO` rows in tax-rules.md ("Kleinunternehmer invoice note", "invoice VAT
  rounding"). Read § 34a UStDV (from 2025) and the UStAE on rounding; update the rows to
  `verified` with the source, and change `invoicing.KLEINUNTERNEHMER_HINWEIS` or the rounding in
  `invoicing/model.py` only if the source requires it.
- **Tests**: adjust `tests/unit/test_invoicing.py` if a value changes.

---

## CLI and configuration

### CLI-1: `finamt eur`, monthly UStVA, period hint

- **Status**: done (2026-11-20) · **Size**: M
- **Result**: all three steps, plus `finamt eur --kleinunternehmer` (EUR-2's mode). Thresholds are
  `Decimal` constants in `cli.py` pointing to tax-rules.md. Tests: `TestCliEur`,
  `TestCliUstvaMonth`, `TestCliSuggestPeriod` in `tests/e2e/test_cli_inprocess.py`.
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

- **Status**: done (2026-11-20) · **Size**: S
- **Result**: `ui/api.py::_eric_home` (both routes): `ERIC_LIBRARY_PATH`, then
  `FINAMT_ERIC_HOME` with a `DeprecationWarning`, then the path saved in Stammdaten. The saved
  path is not deprecated: the new UI's Stammdaten page writes it. Tests: `tests/unit/test_eric_path.py`.
- **Goal**: D4. The UStVA/USt submit routes read `ERIC_LIBRARY_PATH` first, then the legacy
  `FINAMT_ERIC_HOME` / project DB value with a deprecation warning.
- **Files**: `src/finamt/ui/api.py` (only the two `eric_home = …` blocks), `.env.example`, tests.

### ERIC-1: ERiC 44 API

- **Status**: done (2026-11-20)
- ERiC 44 removed the transfer-handle argument of `EricBearbeiteVorgang` (Releasenotes 5.2.6).
  The wrapper passed 8 arguments, so with ERiC 44 every validation or submission failed with
  `610001526` ("Parameter NULL"). `eric_wrapper.py` now passes 7; `bearbeite_vorgang` still
  returns `(rc, None)` so callers are unchanged. ERiC 43 is no longer supported (its libraries are
  not compatible with 44 anyway, Releasenotes 5.2.8). Test: `tests/unit/test_eric_wrapper.py`.

---

## Invoices and ZM

### INV-1: outgoing invoices (§ 14 UStG)

- **Status**: done (2026-11-20) · **Size**: L
- **Result**: `finamt.invoicing` (model, numbering, render, service), storage tables `invoice_sequence` / `invoices`, CLI `finamt invoice new|list|cancel`. Cancellations are a "Rechnungskorrektur (Storno)" with their own number, never "Gutschrift". The reverse-charge note waits for UST-4. Open checks: INV-2. Tests: `tests/unit/test_invoicing.py`.
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

- **Status**: done (2026-11-20) · **Size**: M
- **Result**: `tax/zm.py` (`generate_zm`, `ZMReport`, `ZMLine`), exported from `finamt.tax`;
  tests `tests/unit/test_zm.py`. Same receipts as UStVA Kz 21 (reverse charge, EU customer).
  Open before a `zm_elster.py`: ZM amount format and the weekend rule (tax-rules.md TODO rows).
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

- **Status**: ready · **Size**: M
- **Goal**: `ReceiptData.vat_splits` (per-rate net/VAT) are stored but ignored. Tax code puts a
  receipt without a single `vat_percentage` on rate `"unknown"`, which no Kennzahl uses.
- **Steps**: in `generate_ustva`, when `vat_splits` is present, add each split to its rate line;
  when the rate is unknown and there are no splits, add a report warning.

### CLN-4: no "—" placeholder in the UStVA sender address

- **Status**: ready · **Size**: S
- **Found**: 2026-11-20 with ERiC 44.3. `ElsterXMLBuilder.build_ustva` writes `"—"` into
  `Anmeldungssteuern/DatenLieferant/Strasse` and `Ort` when the config has no address (always the
  case with `ElsterConfig.from_env()`). ERiC rejects it: `610001002`, FehlerID
  `ZeichenNichtImZeichensatz`.
- **Goal**: raise a clear `ValueError` ("sender address missing") before calling ERiC, instead of a
  placeholder; optionally read the address from `FINAMT_ELSTER_NAME/STREET/HOUSE_NUMBER/PLZ/CITY`.
- **Files**: `src/finamt/tax/elster.py` (only the `DatenLieferant` block of `build_ustva`), tests;
  then drop the workaround in `scripts/ustva_test_submission.py`.

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
  (`routes.py`, `helpers.py`, `templates/*.html`, `static/`). Jinja2 and the vendored htmx 2.0.4
  (0BSD, see `NOTICE.md`) are in place. **No Node/npm build.**
- Pages call the library directly (`generate_ustva`, `generate_eur`, the repository); don't call
  the HTTP API from Python.
- German labels; amounts formatted with `Decimal`; no float maths in templates.
- Never edit `src/finamt/ui/static/` (the old bundle) or the existing `/tax/...` routes.
- **Look (D2)**: match the old finamt UI. One hand-written `ui/web/static/app.css` with CSS
  variables, no Tailwind or other build step. Tokens taken from the bundle: background white,
  text black with muted greys (black at 70 / 50 / 40 % opacity), accent amber (amber-50
  `oklch(98.7% .022 95.277)` for panels, amber-200/300 `oklch(92.4% .12 95.746)` /
  `oklch(87.9% .169 91.605)` for borders, amber-400 `oklch(82.8% .189 84.429)` for focus),
  green for OK, red for errors. Small monospace text (11–12 px) for figures and inputs, system
  sans-serif for headings; 1 px `black/20` input borders, 2 px black frames around cards, small
  radius. Amounts right-aligned. Don't copy files out of the bundle.
- **Layout (D2)**: a left navigation (Übersicht, Belege, UStVA, EÜR, Rechnungen, Stammdaten),
  an overview that shows what is due next and how many receipts need review. Ideas like these
  may follow Accountable; its name, logo, colours, icons and texts may not.
- Each page gets a TestClient test that checks status 200 and the key values in the HTML.
- The live-submission gate stays: show the "live" button only if
  `finamt.tax.safety.live_submission_allowed()` is true, and keep the 403 on the backend.

### UI-1: skeleton and receipt list

- **Status**: done (2026-11-20) · **Size**: M
- **Goal**: `/app` shows a base layout (navigation: Belege, UStVA, EÜR, Rechnungen), a project
  selector (projects from `storage.project.list_projects`), and a read-only receipt list filtered by
  year, period, type and category, with the validation warnings.
- **Files**: `src/finamt/ui/web/` (new), `src/finamt/ui/api.py` (one `app.include_router(...)` line
  placed **before** the SPA catch-all route), `tests/unit/test_web_ui.py`.
- **Note**: Jinja2 is installed only as a transitive dependency today; add `jinja2` to the
  dependencies in `pyproject.toml` (and `uv.lock`).
- **Done when**: `/app` and `/app/belege` render for an empty and a filled temp DB; the old UI at `/`
  still works.

### UI-2: receipt upload, edit and review

- **Status**: done (2026-11-20) · **Size**: M
- **Goal**: upload PDFs (reuse the agent pipeline the existing upload route uses; mock it in tests),
  edit date, type, category, subcategory, amounts and VAT, delete; show which EÜR line a receipt lands on.

### UI-3: UStVA and annual USt

- **Status**: done (2026-11-20); the page shows what `generate_ustva` /
  `_ustva_kennzahlen` produce, so UST-2 … UST-4 show up there without UI changes · **Size**: M
- **Goal**: choose month or quarter; show the Kennzahlen preview from `_ustva_kennzahlen`; buttons
  for validate, test submission and (only when allowed) live, using `ElsterEricClient`; list past
  submissions from the project metadata.

### UI-4: EÜR year view

- **Status**: done (2026-11-20); the VAT lines (Kz 140/141/185/186) appear once
  EUR-2 adds them to `EURReport` · **Size**: S
- **Goal**: Kennzahlen table for a year, the "ZU PRÜFEN" list with links to edit each receipt in
  UI-2, and a JSON download (`EURReport.to_json`).

### UI-5: invoices

- **Status**: done (2026-11-20): list, create form, PDF, cancel · **Size**: M
- **Goal**: create, list and download invoices built by INV-1.

### UI-6: switch over

- **Status**: done (2026-11-20): `/` redirects to `/app`; bundle at `/legacy-ui` (no client-side router, assets keep `/assets/…`). Deleting the bundle and the `/tax/ebilanz/*` routes moves to CLN-5 after one release · **Size**: M
- **Note**: the old bundle loads its assets from `/assets/...`; keep that mount when it moves to
  `/legacy-ui`.
- **Goal**: serve the new UI at `/`, move the old bundle to `/legacy-ui` for one release, then delete
  it together with the `/tax/ebilanz/*` settings routes it needed. Record it in `NOTICE.md`.

### UI-8: the old UI's remaining features

- **Status**: done (2026-11-20): all five items (`/app/belege` manual entry, `/app/projekte`, `/app/partner`, XML button on `/app/ustva`, `/app/archiv`) · **Size**: M
- **Goal**: what the old UI at `/` still does and `/app` doesn't, so UI-6 can retire it:
  1. manual receipt entry without a file (`POST /receipts` logic: build a `ReceiptData`, `repo.save`);
  2. create and delete projects (`validate_project_name`, `resolve_project(...).create_dirs()`);
  3. partner list: rename, mark verified, merge (repository `list_all_counterparties`,
     `set_counterparty_verified`, `relink_counterparty`);
  4. download the UStVA / USt XML before sending (`ElsterXMLBuilder.build_ustva`, like `/tax/ustva/xml`);
  5. the archive of submitted returns (`submitted_returns/`, `/submissions/document`).
- **Files**: `src/finamt/ui/web/`, `tests/unit/test_web_ui.py`.
- **Done when**: each item has a page or form with a TestClient test; the old UI is no longer needed.

### UI-7: Stammdaten and ELSTER settings

- **Status**: done (2026-11-20). Street and house number stay one
  field (`street`), as in the old UI. The Prüfziffer is left to ERiC (tax-rules row
  "Prüfziffer") · **Size**: M
- **Goal**: one page `/app/stammdaten` where the owner enters everything ELSTER needs, without
  free-text guessing. Today the old UI has a free-text Bundesland field; it shows
  "Bundesland erforderlich" until the text matches one of its patterns.
- **Fields**:
  - Taxpayer: name, street, house number, postcode, city, **Bundesland as a `<select>` of the
    16 Länder** (full German names), Steuernummer as printed on the Bescheid, Rechtsform
    (Freiberuflich preselected), USt-IdNr (optional).
  - Shown read-only, computed on the server after save or with htmx on change: the 13-digit
    ELSTER Steuernummer, the Finanzamtsnr. (4 digits) and the Länderkennzeichen. When they can't be
    computed, say which input is wrong ("Steuernummer hat nicht 3 Teile", not
    "Bundesland erforderlich").
  - ELSTER: Hersteller-ID, certificate upload (`.pfx`) and PIN, ERiC library path
    (`ERIC_LIBRARY_PATH`, D4 / CFG-1). Never show the stored PIN back; show "gespeichert".
- **Compatibility**: store the taxpayer under the same metadata key and field names the old UI
  uses (`_TAXPAYER_KEY` in `ui/api.py`, field `state` for the Bundesland), and the ELSTER settings
  where `/tax/ebilanz/settings`, `/tax/ebilanz/cert` and `/tax/ebilanz/eric-home` keep them, so both
  UIs work side by side until UI-6. Save `state` as the full German name (e.g. `Nordrhein-Westfalen`);
  the old UI recognises those. Call the repository directly, not the HTTP routes.
- **Tax rules first (AGENTS rule 3)**: the Steuernummer → 13-digit conversion (per-Land prefix,
  digit layout, Bayern/NRW special cases) has no row in `docs/tax-rules.md` yet. Add one with the
  official source (the ERiC documentation of its Steuernummer functions, or the BZSt/ELSTER table);
  if it can't be verified, mark it `TODO` and compute nothing from it. Reuse
  `normalise_steuernummer` in `tax/elster.py`; move the 16-Land list to one place that both the
  dropdown and the conversion use.
- **Files**: `src/finamt/ui/web/` (route + `templates/stammdaten.html`),
  `tests/unit/test_web_ui.py`, `docs/tax-rules.md`.
- **Tests**: page renders for an empty DB; the select has exactly 16 options; saving a known test
  Steuernummer (e.g. the ELSTER test Finanzamt 9198 numbers) shows the expected 13-digit number;
  a malformed Steuernummer shows the field error; the PIN is not in the HTML; the saved profile is
  readable by `GET /taxpayer` (old UI).
- **Done when**: tests pass; the page is linked in the navigation; tax-rules row added.

---

## Clean-up: Project rename and final UI transition

### CLN-5: Remove old UI, rename to FreiBuch (fork of finamt)

- **Status**: waiting (UI-6) · **Size**: L
- **Goal**: finalize the FreiBuch fork by removing the old React SPA, retiring the unused legacy code,
  and renaming the project from finamt to freibuch throughout the codebase, with mention of finamt
  for license attribution only.
- **Context**: FreiBuch is a fork of finamt (AGPL-3.0, see LICENSE). The old SPA bundle under
  `/` and `src/finamt/ui/static/` is no longer needed after the new server-rendered UI replaces it.
- **Files** (scope):
  - **Remove**: `src/finamt/ui/static/` (old React bundle, Vite build outputs); `frontend/` directory
    if present (old npm project); any legacy code in `legacy/` that is not referenced.
  - **Rename package**: `finamt` → `freibuch` throughout; keep all functional imports and APIs.
    Update `pyproject.toml` (name, scripts, entry point). Check CLI references (`finamt` command
    becomes `freibuch` or stays as an alias if backward-compatibility is desired).
  - **Update references**: `README.md`, docs, comments: replace "finamt" with "FreiBuch" except in:
    - License and attribution sections (keep "finamt" and the AGPL license reference).
    - Historical notes in `NOTICE.md` (record that finamt became FreiBuch).
    - Any mention of the upstream (note it as a fork of finamt).
  - **Config and resources**: `docs/BASELINE.md`, `AGENTS.md`, `docs/tax-rules.md` (references to file
    paths or package names), database config (`src/finamt/storage/project.py` paths like
    `~/.freibuch/` instead of `~/.finamt/`), any environment variable docs (`FREIBUCH_*` instead of
    `FINAMT_*`, with a deprecation warning for old `FINAMT_*` vars).
- **Steps**:
  1. Delete `src/finamt/ui/static/` and `frontend/` (if it exists).
  2. Rename the package: `src/finamt/` → `src/freibuch/`; update all imports and `pyproject.toml`.
  3. Update all public docs, README, and inline comments to use "FreiBuch".
  4. Update `NOTICE.md` to record the fork and package name change.
  5. Update paths in storage and config to `~/.freibuch/`; add a deprecation warning for old `~/.finamt/`
     so users' existing DBs continue to work.
  6. Run all tests (they should still pass after import updates).
  7. Verify the CLI works (`freibuch --help`).
- **Tests**: all existing tests should pass with the new package name; storage migration test covers
  backward-compat for old `~/.finamt/` paths.
- **Done when**: all tests pass; `freibuch --help` works; no reference to "finamt" except in LICENSE,
  NOTICE.md (historical record), and attribution comments; `git log` shows the final commit; the
  project is fully branded as FreiBuch.
