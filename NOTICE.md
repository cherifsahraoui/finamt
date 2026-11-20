# NOTICE

This repository (**FreiBuch**) is a fork of **finamt** by Space Octahedron GmbH / Yauheniya Varabyova.

- Upstream: https://github.com/spaceoctahedron/finamt
- Forked from upstream version: 0.26.0
- License: GNU Affero General Public License v3.0 (see `LICENSE`, unchanged).
  All modifications in this fork are released under the same license.

## Purpose of the fork

A free, local tool for a single German Freiberufler: Umsatzsteuer-Voranmeldung (UStVA),
annual Umsatzsteuererklärung (USt) and Einnahmen-Überschuss-Rechnung (EÜR), with receipts
as input. KSt, GewSt, E-Bilanz, Jahresabschluss and Einkommensteuer are out of scope.

## Changes relative to upstream

- Project renamed to **FreiBuch** (repository name, README and docs prose). The Python package
  `finamt`, the `finamt` CLI command, the `~/.finamt/` data folder and the `FINAMT_*` environment
  variables are unchanged.

Branch `baseline/fable-1`:

### Scope cut
- Moved (unchanged) to `legacy/`, outside the package, tests and lint:
  - `src/finamt/tax/kst.py` → `legacy/finamt_tax/kst.py`
  - `src/finamt/tax/bilanz.py` → `legacy/finamt_tax/bilanz.py`
  - `src/finamt/tax/ebilanz.py` → `legacy/finamt_tax/ebilanz.py`
  - `tests/unit/test_kst.py`, `test_bilanz.py`, `test_ebilanz.py` → `legacy/tests/`
  - `scripts/validate_xbrl.py` → `legacy/scripts/validate_xbrl.py`
- `src/finamt/tax/__init__.py`: removed `KStReport` / `generate_kst` exports; added
  `EURReport`, `EURLinie`, `generate_eur`.
- `src/finamt/ui/api.py`: removed routes `POST /tax/kst/submit`, `POST /tax/kst/xml`,
  `POST /tax/ebilanz/xbrl`, `POST /tax/ebilanz/envelope`, `POST /tax/ebilanz/submit` and the
  imports of `bilanz` / `ebilanz`. Kept `/tax/ebilanz/settings|eric-home|cert`
  because UStVA/USt use them.
- `src/finamt/tax/elster.py`: removed `ElsterXMLBuilder.build_kst` and
  `ElsterEricClient.validate_kst / submit_kst / _run_kst`. The E-Bilanz envelope code
  (`EBilanzEnvelopeBuilder`, `*_ebilanz` methods) is still there but nothing in the CLI or API
  uses it (documented in `docs/BASELINE.md`, removal tracked in `docs/TODO.md`).
- CLI: it had no KSt/GewSt/E-Bilanz commands, so nothing changed.
- Web UI: the repo only ships a pre-built bundle (`src/finamt/ui/static/`), with no frontend
  source. The bundle was **not** edited. It already hides KSt, GewSt and Jahresabschluss when
  the taxpayer Rechtsform is "Freiberuflich". If they are shown anyway, their backend routes
  now return 404.
- `pyproject.toml`: removed the `arelle-release` dev dependency (only used by
  `validate_xbrl.py`); `uv.lock` updated. Ruff excludes `legacy/`.

### Safety
- `src/finamt/tax/safety.py` (new): live (non-test) ELSTER submission is disabled unless
  `FINAMT_ALLOW_LIVE_SUBMISSION=1` is set. Checked where data is sent:
  `ElsterClient._post`, `ElsterEricClient._run_ust` and `_run` (when `send=True` and
  `use_test=False`). `POST /tax/ustva/submit` and `POST /tax/uste/submit` return HTTP 403 for
  `use_test=false` without `validate_only`. Validation and test-mode submissions are not affected.
- `.gitignore`: added ERiC, certificate, database, ELSTER payload and model patterns.
- `.env.example`: placeholders in place of the upstream example Steuernummer / Hersteller-ID;
  documented `ERIC_LIBRARY_PATH` and `FINAMT_ALLOW_LIVE_SUBMISSION`.

### ERiC 44 (task ERIC-1, 2026-11-20)
- `src/finamt/tax/eric_wrapper.py`: `EricBearbeiteVorgang` is called with 7 arguments. ERiC 44
  removed the transfer-handle parameter (ERiC Releasenotes 5.2.6); upstream's 8-argument call,
  written for ERiC 43, fails with `610001526` on ERiC 44. `bearbeite_vorgang` still returns
  `(rc, None)`. ERiC 43 is no longer supported.
- `scripts/ustva_test_submission.py` (new): validates, or sends as a test case, a fixed UStVA with
  ERiC. It always sets the Testmerker and refuses any tax number outside the test Finanzamt 9198.

### EÜR ELSTER boundary
- `src/finamt/tax/eur_elster.py` (new): `build_xml` (raises `NotImplementedError` until the
  Kennzahlen are verified, see `docs/TODO.md`), `validate` (offline structural check),
  `submit(xml, mode="dry_run"|"test")`. Test mode requires the Testmerker in the XML and reads
  the ERiC directory from `ERIC_LIBRARY_PATH` only. `mode="live"` raises `NotImplementedError`.

### Own web UI under /app (tasks UI-1, UI-2, UI-3, UI-4, UI-7, 2026-11-20)
- New package `src/finamt/ui/web/` (FastAPI + Jinja2 templates, no build step): overview, receipts
  (list, upload through the upstream agent pipeline, edit, delete), UStVA / annual USt preview and
  sending (reuses the upstream submit functions in-process), EÜR, Stammdaten.
- `src/finamt/ui/api.py`: one call `register(app)` before the SPA catch-all. The upstream UI at `/`
  and all upstream API routes are unchanged.
- `src/finamt/ui/web/static/htmx.min.js`: htmx 2.0.4 by Big Sky Software, **Zero-Clause BSD**
  licence (no conditions), from the npm package `htmx.org@2.0.4`.
- `pyproject.toml`: `jinja2` declared (was only a transitive dependency). `MANIFEST.in` ships the
  new templates and static files.
- New `src/finamt/tax/bundesland.py`: the 16 Länder and the Steuernummer check for the new UI.

### Two Steuernummern (2026-11-20)
- New UI only: the taxpayer profile can hold a separate Einkommensteuer number (`tax_number_est`)
  next to the Umsatzsteuer number (`tax_number`, unchanged, still used by the upstream UI), and the
  owner's choice which one the Anlage EÜR is filed under (`euer_steuernummer`). UStVA and the annual
  USt always use `tax_number`.

### ELSTER <Ziel> for 13-digit prefixes (2026-11-20)
- `src/finamt/tax/elster.py` (`_BUNDESLAND_ZIEL`): the upstream UI sends the prefix of the 13-digit
  Steuernummer (e.g. `9` for Bayern) as `bundesland_kz`; upstream wrote it unchanged into
  `<Ziel>`, which the ELSTER schema does not allow. The prefixes now map to the Länder codes.
  `tests/unit/test_elster.py::TestBundeslandZiel::test_all_16_states_present` now counts distinct
  Länder instead of dictionary entries. Comment on the Baden-Württemberg Steuernummer format fixed.

### UStVA import VAT (task UST-1, 2026-11-20)
- `src/finamt/tax/elster.py` (`_ustva_kennzahlen`): upstream added Einfuhrumsatzsteuer into
  Kz 66. It now goes to its own line, Kz 62 (USt1A-2026 section F); Kz 66 holds only input tax
  from invoices. Kz 83 has the same value as before.

### UStVA credit notes and Kz 83 (task UST-2, 2026-11-20)
- `src/finamt/tax/ustva.py` (`generate_ustva`): upstream skipped receipts with negative VAT, so
  credit notes were lost. They now stay on their rate line as negative amounts (§ 17 Abs. 1 UStG,
  USt1A-2026 Anleitung).
- `src/finamt/tax/elster.py` (`_ustva_kennzahlen`): Kz 81/86/35 and Kz 66 are written whenever
  non-zero, including negative; Kz 83 is always written, `0.00` for an empty period (upstream
  omitted it).

### EÜR VAT lines and Kleinunternehmer mode (task EUR-2, 2026-11-20)
- `src/finamt/tax/eur.py`: upstream computed the profit by the net method (VAT left out).
  It now follows the official Anlage EÜR (decision D6): sale VAT → Kz 140, purchase VAT
  → Kz 185, `tax_settlement`/`vat_payment` → Kz 186, `tax_settlement`/`vat_refund` → Kz 141, all
  part of `gewinn`. New `kleinunternehmer=True` (decision D7): sales → Kz 111 at gross,
  purchases at gross, no VAT lines; the GWG limit is then compared with the gross cost.
  `EURReport` gained `kleinunternehmer`, `kz140_ust_vereinnahmt`, `kz185_vorsteuer`,
  `total_betriebseinnahmen`, `total_betriebsausgaben`; the summary drops the net-method warning.
- `src/finamt/ui/web/templates/euer.html`: shows Kz 140/185 and the totals including VAT.

### Web UI: background uploads, language switch, UI-8, invoices, start page (2026-11-20)
- `src/finamt/ui/web/` (FreiBuch's own code): uploads run as one background job whose progress
  stays on every page (owner bug report); DE/EN switch (`i18n.py`); manual entry, projects,
  partners, XML download and an archive page (UI-8); invoices page (UI-5); Kleinunternehmer
  years in Stammdaten (EUR-8).
- `src/finamt/ui/api.py` (upstream file, UI-6): `/` redirects to `/app`; the upstream bundle is
  served unchanged at `/legacy-ui` instead of `/`; unknown paths return 404 instead of the SPA.
  The bundle itself is not modified.

### ERiC print PDF and EÜR in the UI (PRINT-1, EUR-9, 2026-11-20)
- `src/finamt/tax/eric_wrapper.py` (upstream file): `make_druck_parameter()`; `bearbeite_vorgang`
  passes print parameters (upstream always passed NULL).
- `src/finamt/tax/elster.py` (upstream file): `ElsterEricClient.validate_ust` / `submit_ust` take
  an optional `pdf_path`; a print error after an accepted send is reported as sent with a warning.
- `src/finamt/ui/api.py` (upstream file): the UStVA / USt submit requests take `pdf`; the copy is
  stored next to the XML and recorded as `pdf_filename`.
- `src/finamt/tax/eur_elster.py`, `src/finamt/ui/web/`, `src/finamt/cli.py` (FreiBuch's own code):
  print preview, EÜR check / XML / test send in the UI and CLI.

### Project folders without a database (bug fix, 2026-11-20)
- `src/finamt/storage/project.py` (upstream file): `list_projects(with_db_only=True)` skips
  folders without `finamt.db`. Upstream's default (every folder) is unchanged, so the old UI
  behaves as before. The new UI no longer offers such leftovers as projects (deleting one said
  "Project … not found") and removes them from the Projekte page if they are empty.

### 0 %, tax-free and reverse-charge receipts (tasks UST-3, UST-4, 2026-11-20)
- `src/finamt/models.py` (upstream file): new `ReceiptData.vat_treatment` (`zero_rate`,
  `tax_free`, `reverse_charge` or None) and a `reverse_charge` property; in `to_dict`.
- `src/finamt/storage/sqlite.py` (upstream file): column `receipts.vat_treatment` (in-place
  migration), saved, read and updatable.
- `src/finamt/tax/ustva.py` (upstream file): such receipts go to Kz 87 / 48 / 21 / 45 / 60 and
  Kz 46/47 / 84/85 + Kz 67 instead of being skipped; new `warnings` for receipts that cannot be
  reported. `total_output_vat` / `total_input_vat` include the § 13b tax.
- `src/finamt/tax/elster.py` (upstream file): `_ustva_kennzahlen` writes those Kennzahlen; the
  annual USt build refuses reports with them (E50 fields unverified).
- `src/finamt/tax/eur.py`: such sales go to Kz 103.
- Web UI: "USt-Behandlung" select on the receipt form; UStVA page lists the warnings.

### One ERiC path setting (task CFG-1, 2026-11-20)
- `src/finamt/ui/api.py` (upstream file): `POST /tax/ustva/submit` and `POST /tax/uste/submit`
  read `ERIC_LIBRARY_PATH` first. Upstream's `FINAMT_ERIC_HOME` still works but warns
  (`DeprecationWarning`); the 400 error names `ERIC_LIBRARY_PATH`.

### Zusammenfassende Meldung (task ZM-1, 2026-11-20)
- New `src/finamt/tax/zm.py` (FreiBuch's own code), exported from `finamt.tax`: ZM sums per
  customer VAT ID and quarter. No submission yet.

### Outgoing invoices (task INV-1, 2026-11-20)
- New package `src/finamt/invoicing/` and CLI group `finamt invoice` (FreiBuch's own code).
- `src/finamt/storage/sqlite.py` (upstream file): new tables `invoice_sequence` and `invoices`
  (in-place migration) and the methods `create_invoice`, `get_invoice`, `list_invoices`,
  `set_invoice_receipt`, `invoice_corrected_by`.

### CLI: EÜR, monthly UStVA, filing-period hint (task CLI-1, 2026-11-20)
- `src/finamt/cli.py`: new command `finamt eur` (exit code 1 while receipts need review);
  `finamt ustva` gained `--month` and `--suggest-period`. Upstream's `--quarter` default (1) is
  kept when neither is given.

### EÜR ELSTER XML (task EUR-4, 2026-11-20)
- `src/finamt/tax/eur_elster.py`: `build_xml(report, taxpayer, *, entnahmen, einlagen,
  hersteller_id, test=True)` builds the Anlage EÜR 2025 envelope (datenartVersion `EUER_2025`)
  instead of raising; new `EURTaxpayer`, `format_amount` and `eric_validate` (ERiC validation, no
  sending). Only test builds (Testmerker); `test=False` raises. `submit()` now defaults
  `datenart_version` to `EUER_2025`.
- `scripts/eur_test_submission.py` (new): validates, or sends as a test case, a fixed EÜR with
  ERiC; refuses any tax number outside the test Finanzamt 9198.

### EÜR Kennzahlen (task EUR-1)
- `src/finamt/tax/eur.py`: the upstream category → Kennzahl mapping did not match the official
  Anlage EÜR (e.g. 111 is the Kleinunternehmer line, 140 is collected VAT, 145 is Kfz taxes,
  176 is the commuting allowance). Replaced it with a mapping verified against the
  Anlage EÜR 2025 (BMF-Schreiben 29.08.2025), including subcategory overrides.
  Sales: taxable → 112, 0 % → 103, sale of equipment → 102.
- New `review_lines`: receipts that need a human decision (assets above 800 € net, meals,
  gifts, donations, health insurance, tax payments, capital movements, sales with unknown VAT)
  are listed with a reason and no longer counted in the profit. Upstream counted them in
  Kz 176 / 112.
- New report fields `form_year`, `warnings` (for years other than 2025), `total_review_netto`.
- `tests/unit/test_eur.py`: three tests that asserted the old Kennzahlen (165, 183, 176) now
  assert the verified ones (221, 281, 183). New `tests/unit/test_eur_mapping.py`.

### Tests
- Added `tests/unit/test_safety.py`, `tests/unit/test_eur_elster.py`,
  `tests/unit/test_decimal_rule.py` (no `float` in `src/finamt/tax/`) and
  `tests/unit/test_eur_edge_cases.py`. No existing test was changed or removed except the moves
  listed under "Scope cut".

### Style
- `src/finamt/ui/api.py`: one line reformatted by `ruff format` (no behaviour change).

### Documentation
- New: `AGENTS.md`, `NOTICE.md`, `docs/BASELINE.md`, `docs/tax-rules.md`, `docs/TODO.md`,
  `docs/DECISIONS.md`, `docs/MANUAL-STEPS.md`, `legacy/README.md`.
- `docs/tax-rules.md`: values verified on 2026-11-18 against gesetze-im-internet.de and the BMF
  form letters (UStVA 2026, Anlage EÜR 2025).
- `README.md`: rewritten for the fork's goal (free Freiberufler VAT + EÜR tool): status table,
  roadmap, yearly workflow, category → EÜR Kennzahl table, safety and ELSTER setup. Upstream
  PyPI/badge/commercial-licensing sections removed; upstream credited under "License and credits".
  `readme/README_de.md` is unchanged (DOC-1).
