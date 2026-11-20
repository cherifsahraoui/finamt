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
