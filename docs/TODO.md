# TODO

Small, independent tasks. Each has a goal, the files involved, an acceptance test and a status
(`open`, `blocked`, `done`). Pick one, keep the change to that task, follow `AGENTS.md`.
Tax values must be verified in `docs/tax-rules.md` **before** code depends on them.

---

## 1. EÜR ELSTER builder (Kennzahlen mapping)

- **Goal**: implement `finamt.tax.eur_elster.build_xml(eur_report) -> bytes` producing a valid
  ELSTER envelope for the Anlage EÜR of a Freiberufler.
- **Blocked by**: task 2 (verified Kennzahlen) and the ERiC Jahresdokumentation for the EÜR
  (Verfahren, DatenArt, `datenartVersion`, XSD, element names). Get these from the ELSTER
  developer portal; record them in `docs/tax-rules.md` with status `verified`.
- **Files**: `src/finamt/tax/eur_elster.py`, `src/finamt/tax/eur.py` (only if the mapping changes),
  `tests/unit/test_eur_elster.py`, `docs/tax-rules.md`.
- **Acceptance test**:
  - `build_xml(report)` output passes `validate()` and carries the Testmerker when built for test.
  - A unit test with a fixed `EURReport` asserts every emitted Kennzahl/element value
    (golden XML or element-by-element), Decimal formatting and element order.
  - Manual: `submit(xml, mode="test", datenart_version=…)` with a real ERiC returns success
    (record the date in tax-rules.md). Never automated in CI.
  - Remove the `NotImplementedError` test, keep the live-mode test.
- **Status**: blocked

## 2. Verify the EÜR category → Kennzahl mapping

- **Goal**: make `_EXPENSE_MAPPING` / `_INCOME_MAPPING` in `eur.py` match the official Anlage EÜR
  of the target year. The current upstream numbers (111, 112, 140, 145, 165, 172, 176, 183) are
  suspected wrong (see tax-rules.md). Also decide the lines for the categories that are not mapped
  today: `car`, `office`, `financial`, `marketing`, `donations`, `public_fees`, `licensing`
  (purchase), `tax_settlement`, `capital_movement`; remove the dead keys `internet` and `taxes`.
- **Files**: `src/finamt/tax/eur.py`, `tests/unit/test_eur.py`, `docs/tax-rules.md`.
- **Acceptance test**: one test per category asserting its Kennzahl; every Kennzahl row in
  tax-rules.md is `verified` with the form year; `capital_movement` (Privatentnahme/-einlage,
  loans) does not change `gewinn`.
- **Status**: open

## 3. VAT inside the EÜR and Kleinunternehmer mode

- **Goal**: decide and implement how USt flows into the EÜR (collected USt, paid Vorsteuer, USt
  paid to / refunded by the Finanzamt as separate Kennzahlen) and add a Kleinunternehmer option
  where purchase VAT is an expense.
- **Files**: `src/finamt/tax/eur.py`, `tests/unit/test_eur_edge_cases.py`.
- **Acceptance test**: the strict `xfail`
  `TestKleinunternehmer::test_purchase_vat_counts_as_expense_for_kleinunternehmer` passes with the
  new option (remove the marker); existing tests still pass for the default.
- **Status**: open (needs verified rules)

## 4. Invoice generation (§ 14 UStG)

- **Goal**: create outgoing invoices (PDF and stored as `sale` receipts) with all mandatory
  fields, gapless sequential numbering and VAT lines per rate.
- **Files**: new `src/finamt/invoicing/` (model, numbering, renderer), `storage/sqlite.py`
  (invoice number sequence table only), tests in `tests/unit/test_invoicing.py`.
- **Acceptance test**: generated invoice contains every § 14 Abs. 4 UStG field listed (and
  verified) in tax-rules.md; numbers are unique and gapless under concurrent creation; per-rate
  net/VAT/gross sum to the total with Decimal rounding; the Kleinunternehmer note is printed when
  that mode is on; small-amount invoice rules (§ 33 UStDV) covered.
- **Status**: open

## 5. Reverse-charge flag (§ 13b UStG)

- **Goal**: mark receipts as reverse charge (supplier abroad / EU services) so UStVA reports them
  in the correct Kennzahlen instead of skipping them (purchases: tax owed and deducted at once;
  sales: reported without German VAT).
- **Files**: `src/finamt/models.py`, `storage/sqlite.py` (column + migration),
  `src/finamt/tax/ustva.py`, `src/finamt/tax/elster.py` (`_ustva_kennzahlen`, `_USTVA_KZ_ORDER`),
  tests.
- **Acceptance test**: a reverse-charge purchase produces the verified Kennzahlen with a zero
  net effect; a reverse-charge EU sale appears in its Kennzahl; existing UStVA tests unchanged.
- **Status**: open (Kennzahlen to verify first)

## 6. ZM builder for EU sales (§ 18a UStG)

- **Goal**: Zusammenfassende Meldung for intra-EU B2B services/supplies: aggregate by customer
  USt-IdNr per period and build the ELSTER payload (dry-run / test only, like `eur_elster`).
- **Depends on**: task 5 (reverse-charge flag) and counterparty VAT IDs.
- **Files**: new `src/finamt/tax/zm.py`, `src/finamt/tax/zm_elster.py`, tests.
- **Acceptance test**: aggregation per VAT ID and period with Decimal sums; invalid/missing VAT IDs
  reported as errors; live mode raises like `eur_elster.submit`.
- **Status**: open

## 7. Verify the UStVA rounding rule

- **Goal**: confirm whether Kz 81/86/35 bases are truncated to whole euros (current
  `ROUND_DOWN`) and that tax amounts keep cents; confirm Kz 35 accumulation over several rates.
- **Files**: `src/finamt/tax/elster.py` (`_ustva_kennzahlen`), `tests/unit/test_elster.py`,
  `docs/tax-rules.md`.
- **Acceptance test**: tax-rules.md rows for Kz 81/86/35/36 are `verified`; tests for x.99 €
  bases and negative bases match the verified rule.
- **Status**: open

## 8. README update

- **Goal**: README TODO section reflects this fork's scope and the real state of EÜR.
- **Files**: `README.md`.
- **Acceptance test**: no out-of-scope items listed as features; EÜR calculation checked,
  EÜR ELSTER builder unchecked.
- **Status**: done (baseline/fable-1). The German `readme/README_de.md` is not updated yet.

## 9. UStVA: credit notes, 0 % and unknown-rate receipts

- **Goal**: `generate_ustva` skips receipts with `vat_amount <= 0` (credit notes, tax-free
  sales) and puts receipts without `vat_percentage` under `"unknown"`, which no Kennzahl uses.
  Report them correctly or surface them as warnings.
- **Files**: `src/finamt/tax/ustva.py`, `src/finamt/tax/elster.py`, tests.
- **Acceptance test**: a credit note reduces Kz 81 and Kz 66 as the verified rule requires; an
  `unknown`-rate receipt raises a visible warning instead of silently vanishing.
- **Status**: open

## 10. Einfuhrumsatzsteuer: Kz 62 vs Kz 66

- **Goal**: `_ustva_kennzahlen` adds `einfuhr_vat` into Kz 66; `ustva.py` comments say line 62.
  Verify and fix.
- **Files**: `src/finamt/tax/elster.py`, `tests/unit/test_elster.py`, `docs/tax-rules.md`.
- **Acceptance test**: a receipt with `einfuhr_vat` produces the verified Kennzahl only.
- **Status**: open

## 11. Remove the remaining E-Bilanz code from `elster.py`

- **Goal**: delete `EBilanzEnvelopeBuilder`, `ElsterEricClient.validate_ebilanz / submit_ebilanz /
  _run / export_ebilanz_xml` and their tests in `tests/unit/test_elster.py`; keep `_run_ust`.
- **Files**: `src/finamt/tax/elster.py`, `tests/unit/test_elster.py`, `tests/unit/test_safety.py`,
  `NOTICE.md`.
- **Acceptance test**: tests pass; `grep -i ebilanz src/finamt/tax` finds nothing except the
  settings-route comment in `api.py`.
- **Status**: open

## 12. CLI for EÜR and monthly UStVA

- **Goal**: `finamt eur --year Y [--output F]` (calls `generate_eur`) and
  `finamt ustva --month M`.
- **Files**: `src/finamt/cli.py`, `tests/e2e/test_cli_inprocess.py`.
- **Acceptance test**: in-process CLI tests with a temp DB and stored receipts (no OCR/LLM).
- **Status**: open

## 13. One ERiC path setting

- **Goal**: the UI/UStVA path reads `FINAMT_ERIC_HOME` or the project DB; `eur_elster` reads
  `ERIC_LIBRARY_PATH` only. Pick one documented source.
- **Files**: `src/finamt/ui/api.py`, `src/finamt/tax/eur_elster.py`, `.env.example`, `AGENTS.md`.
- **Acceptance test**: tests prove the chosen variable is used and the other is ignored.
- **Status**: open (decision for the owner)

## 14. Small fixes found during the baseline

- `finamt.__all__` lists `build_extraction_prompt`, which does not exist, so `from finamt import *`
  raises `AttributeError`. Files: `src/finamt/__init__.py`. Test: star import succeeds. Status: open.
- `tests/pytest.ini` sets `testpaths = src/tests` (wrong path); it is only used when pytest runs
  from `tests/`. Remove it or fix it. Status: open.
- The frontend source is not in the repo, so the KSt/GewSt/Jahresabschluss panels stay in the
  bundle (hidden for "Freiberuflich"). Get the source to remove them. Status: blocked.
- `ReceiptData.vat_splits` are stored but ignored by tax code (mixed-rate receipts). Status: open.
