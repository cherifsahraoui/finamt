# legacy/ — removed from the finamt fork

Code that is **out of scope** for this fork (single Freiberufler: UStVA, USt, EÜR).
It was moved here unchanged from upstream `spaceoctahedron/finamt` 0.26.0 so it can be
consulted or restored. It is:

- not part of the installed package (`setuptools` only packages `src/`),
- not collected by pytest (`testpaths = ["tests"]`),
- excluded from ruff (`extend-exclude` in `pyproject.toml`),
- **not maintained**. Imports such as `from ..models import …` or `finamt.tax.kst` no longer resolve.

| File | Original path | Topic |
|---|---|---|
| `finamt_tax/kst.py` | `src/finamt/tax/kst.py` | Körperschaftsteuer (KSt 1 / E30) |
| `finamt_tax/bilanz.py` | `src/finamt/tax/bilanz.py` | Jahresabschluss (Bilanz + GuV, § 267a HGB) |
| `finamt_tax/ebilanz.py` | `src/finamt/tax/ebilanz.py` | E-Bilanz XBRL (§ 5b EStG) |
| `tests/test_kst.py`, `tests/test_bilanz.py`, `tests/test_ebilanz.py` | `tests/unit/` | their tests |
| `scripts/validate_xbrl.py` | `scripts/` | Arelle XBRL validator for E-Bilanz |

Also removed (deleted, recoverable from git history before the scope-cut commit):
the API routes `/tax/kst/submit`, `/tax/kst/xml`, `/tax/ebilanz/xbrl`,
`/tax/ebilanz/envelope`, `/tax/ebilanz/submit` in `src/finamt/ui/api.py`, and the
KSt methods `ElsterXMLBuilder.build_kst`, `ElsterEricClient.validate_kst/submit_kst/_run_kst`
in `src/finamt/tax/elster.py`. GewSt never had backend code (UI bundle only).

Do not import anything from here. To restore a feature, move it back into `src/`,
fix the imports and tests, and record the change in `NOTICE.md`.
