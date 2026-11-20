# AGENTS.md — working on FreiBuch (fork of finamt)

Read this first. Then:

- `docs/TODO.md`: the **task board**. Take the first `ready` task unless the owner names one, and
  follow its card (goal, verified rules, files, steps, tests, done-when).
- `docs/DECISIONS.md`: settled questions. Follow them; don't reopen them.
- `docs/tax-rules.md`: every tax value with its official source and status.
- `docs/BASELINE.md`: code map, entry points, receipt flow.
- `docs/MANUAL-STEPS.md`: steps only the owner can do (ELSTER login, certificate, decisions).
  When a card is blocked on the owner, point them to the matching step (M1–M6).

**Scope**: a free, local tool for one German Freiberufler: UStVA (monthly/quarterly), annual
USt and EÜR, with receipts as input. **Out of scope**: KSt, GewSt, E-Bilanz, Jahresabschluss,
Einkommensteuer. Code for those lives in `legacy/` and must not be imported.

## Commands

```bash
uv sync --extra dev                    # install into .venv (Python from .python-version)
uv run pytest                          # all tests, offline
uv run pytest tests/unit/test_eur.py   # one file
uv run ruff check src tests            # lint (must pass)
uv run ruff format --check src tests   # format (must pass); `ruff format src tests` to fix
uv run finamt --help                   # CLI: process, batch, ustva, serve
uv run finamt serve --no-browser       # web UI on http://127.0.0.1:8000
```

Without uv: `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`, then
run the same commands without `uv run`.

## Hard rules

1. **License**: keep `LICENSE` (AGPL-3.0) unchanged. Record every change to upstream behaviour
   or files in `NOTICE.md`.
2. **No secrets or personal data in git**: no ERiC libraries, ELSTER certificates (`.pfx`), `.env`,
   `.db` files, model weights, generated ELSTER XML or real receipts. `.gitignore` covers these;
   check `git status` before every commit. Only `.env.example` with placeholders is committed.
3. **No invented tax values**: every rate, threshold, Kennzahl, rounding rule or deadline used
   by code needs a row in `docs/tax-rules.md` with an official source. If you cannot verify it,
   mark it `TODO` there and say so in your report. Do not guess ELSTER field numbers.
4. **Tests run offline**: no LLM, no OCR model download, no ERiC, no network. Mock them. A test
   that truly needs one of them gets `pytest.mark.skip(reason=...)`; never delete it.
5. **Money is `Decimal`** in `src/finamt/tax/`: never `float`, never float literals
   (`tests/unit/test_decimal_rule.py` enforces this). Build Decimals from strings: `Decimal("0.19")`.
6. **No live submission by default**: live ELSTER filing needs
   `FINAMT_ALLOW_LIVE_SUBMISSION=1` (`src/finamt/tax/safety.py`). EÜR live mode is disabled
   completely. Never set that flag in tests, CI or code; never remove the gate.
7. **Do not refactor the large files** (`ui/api.py`, `tax/elster.py`, `storage/sqlite.py`)
   wholesale. Make the smallest change the task needs; describe structure changes in
   `docs/BASELINE.md`.
8. **Small commits**, one concern each, with a message that says what and why. Do not commit to
   `main` directly. **One work branch, not one per task**: keep committing new tasks to the
   current work branch. Start a new branch only when there is none (e.g. the last one was merged
   into `main`), from up-to-date `main`, named after its start date: `work/YYYY-MM-DD`.

## Where to add things

- **New tax form** (e.g. ZM):
  1. Add the verified values to `docs/tax-rules.md` (or TODO rows) and a task to `docs/TODO.md`.
  2. Calculation: `src/finamt/tax/<form>.py` with a `generate_<form>(receipts, …) -> <Form>Report`
     dataclass (Decimal fields, `to_dict`, `to_json`, `summary`), like `eur.py` / `ustva.py`.
  3. ELSTER boundary: `src/finamt/tax/<form>_elster.py` with `build_xml`, `validate`,
     `submit(xml, mode="dry_run"|"test")`, copying the pattern and safety checks of
     `eur_elster.py` (Testmerker required in test mode, live raises).
  4. Export it from `src/finamt/tax/__init__.py`.
  5. Tests in `tests/unit/test_<form>.py` and `tests/unit/test_<form>_elster.py`.
  6. Optional entry points: a command in `cli.py`, a route in `ui/api.py` (small, near the
     existing `/tax/...` routes).
- **New receipt category**: `agents/prompts.py` (`RECEIPT_CATEGORIES`), then its EÜR line in
  `tax/eur.py` (verified Kennzahl only), README category table, tests.
- **DB column**: `storage/sqlite.py` schema + the in-place migration list near the top of
  `SQLiteRepository`; test in `tests/integration/test_storage.py`.

## How to flag uncertainty

- In code: a comment `# TODO(verify): <what> — see docs/tax-rules.md` next to the value, and
  raise `NotImplementedError` rather than emitting a guessed ELSTER field.
- In `docs/tax-rules.md`: status `TODO` and what is missing (source, year, the exact question).
- In `docs/TODO.md`: a task with goal, files, acceptance test, status.
- In your final report: list each unverified value and each open question. Do not present a
  TODO value as fact.
- Tests that pin known-wrong or missing behaviour: `pytest.mark.xfail(strict=True, reason=...)`
  pointing to the TODO entry.

## Definition of done

- [ ] `uv run pytest` passes offline (skips and xfails have a reason).
- [ ] `uv run ruff check src tests` and `uv run ruff format --check src tests` pass.
- [ ] New or changed tax values are in `docs/tax-rules.md` with source and status.
- [ ] `docs/BASELINE.md`, `NOTICE.md` updated if structure or upstream behaviour changed.
- [ ] The task card in `docs/TODO.md` is marked `done (date)` and the board is updated.
- [ ] No secrets, ERiC files, certificates, databases, models or personal data staged
      (`git status`, `git diff --cached --stat`).
- [ ] Live ELSTER submission still impossible without `FINAMT_ALLOW_LIVE_SUBMISSION=1`
      (`tests/unit/test_safety.py`, `tests/unit/test_eur_elster.py` pass).
- [ ] Commits are small and each message explains the change.
