# NOTICE

This repository is a fork of **finamt** by Space Octahedron GmbH / Yauheniya Varabyova.

- Upstream: https://github.com/spaceoctahedron/finamt
- Forked from upstream version: 0.26.0
- License: GNU Affero General Public License v3.0 (see `LICENSE`, unchanged).
  All modifications in this fork are released under the same license.

## Purpose of the fork

A free, local tool for a single German Freiberufler: Umsatzsteuer-Voranmeldung (UStVA),
annual Umsatzsteuererklärung (USt) and Einnahmen-Überschuss-Rechnung (EÜR), with receipts
as input. KSt, GewSt, E-Bilanz, Jahresabschluss and Einkommensteuer are out of scope.

## Changes relative to upstream

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

### EÜR ELSTER boundary
- `src/finamt/tax/eur_elster.py` (new): `build_xml` (raises `NotImplementedError` until the
  Kennzahlen are verified, see `docs/TODO.md`), `validate` (offline structural check),
  `submit(xml, mode="dry_run"|"test")`. Test mode requires the Testmerker in the XML and reads
  the ERiC directory from `ERIC_LIBRARY_PATH` only. `mode="live"` raises `NotImplementedError`.

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
  `legacy/README.md`.
- `README.md`: fork notice; TODO section rewritten for the fork's scope; E-Bilanz removed from
  the feature list. `readme/README_de.md` is unchanged.
