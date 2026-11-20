# Manual steps for the owner

This file lists only what an agent **cannot** do for you: things that need your ELSTER login, your
certificate PIN, a decision, or a legally binding filing. Everything else is done or is a task in
[TODO.md](TODO.md).

Never commit anything from these steps. `private/`, `.env`, certificates, ERiC, databases and
generated XML are git-ignored.

| # | Step | When | Unblocks | Your time |
|---|---|---|---|---|
| M1 | [Put your Hersteller-ID and certificate PIN into `.env`](#m1-hersteller-id-and-certificate-pin) | when available (**pending**, see below) | M2; ERiC validation of real data; all sending. Not needed for coding or tests | 5 min (+ waiting for the Hersteller-ID) |
| M2 | [First test submission](#m2-first-test-submission) | once | UST-5 | 5 min |
| M3 | [Decide how assets above 800 € are depreciated](#m3-decide-asset-depreciation) | once | EUR-3 | 10 min |
| M4 | [File for real (live)](#m4-file-for-real) | every period | — | 10 min per filing |
| M5 | [Yearly update: new ERiC and forms](#m5-yearly-update) | yearly | YEAR-1 | 10 min |
| M6 | [Optional: ask upstream for the web UI source](#m6-optional-ask-upstream-for-the-ui-source) | optional | UI decision | 5 min |

## Pending requests

| Request | Requested | Status | Blocks | What the agent does meanwhile |
|---|---|---|---|---|
| Hersteller-ID for FreiBuch (M1) | 2026-11-20 | **pending**, owner to apply in the developer area and report back | M2 (UST-5 server test), EUR-4 ERiC validation, all sending | Works on EUR-4, EUR-3 and other offline tasks. ERiC validation tests skip with a reason until the ID is in `.env` |

When the owner has the ID: put it in `.env` (M1), then tell the agent "M1 done". The agent then
runs the ERiC validation tests and updates this table.

## Already done by an agent (2026-11-20)

- ERiC **44.3.6.0, Windows x86-64** extracted to `private/ERiC-44.3.6.0/Windows-x86_64/`. The 64-bit
  build matches the 64-bit Python in `.venv`. The documentation is in `private/ERiC-44.3.6.0/Dokumentation/`.
- `.venv` installed (`uv sync --extra dev`); all tests pass.
- `.env` created with all paths and the official ERiC **test tax number**. ERiC loads (`ERiC OK`)
  and your certificate file opens. Only two placeholders are left for you (M1).
- FreiBuch's UStVA (2025, 2026) and annual USt (2024, 2025) XML **validate** in ERiC 44.3.
  Nothing was sent.
- The EÜR schema facts (old step "collect the EÜR facts") are recorded in
  [tax-rules.md](tax-rules.md#anlage-eür-2025-xml-datenartversion-euer_2025-for-eur-4); EUR-4 is ready.
- ERiC 44 changed its API; FreiBuch was adapted (task ERIC-1).

### What is in `private/`

| file or folder | content | keep? |
|---|---|---|
| `<your-cert>.pfx` | your ELSTER certificate (*Mein ELSTER* login file) | **yes**; `.env` points to it |
| `ERiC-44.3.6.0/Windows-x86_64/` | ERiC library (`dll/ericapi.dll` + `dll/plugins/`), extracted from the `.jar` | **yes** |
| `ERiC-44.3.6.0/Dokumentation/` | developer handbook, release notes, per form: XSD schema, Jahresdokumentation (`.ods`: fields, Kennzahlen, rules), example XML; `Datenartversionmatrix.ods`, `Finanzamtsdaten.ods` (incl. test Finanzämter) | **yes**, agents read it |
| `ERiC-44.3.6.0/Windows-x86_64/Beispiel/ericdemo-python/test-softidnr-pse.pfx` | official ELSTER **test certificate**, PIN `123456` (public, from the ERiC docs), valid until 2028-07-10 | yes; fallback for M2 |
| `Vordrucke/2026/` (from `Vordrucke_2026_ERiC-44.3.6.0.zip`) | official 2026 form PDFs: `USt1A_2026.pdf`, `USt1H_2026.pdf` (UStVA), USt 2 A delta (annual USt); also forms out of scope (KapESt, LSt, § 50a) | yes, for YEAR-1 |
| `Vordrucke/VZ_unabhaengig/` (from `Vordrucke_VZ_unabhaengig_…zip`) | KSt, Grundsteuer, FsE, InvSt, USt-Vergütung forms | out of scope; can delete |
| `GrundsteuerBY_Musterbescheide.zip` | Bavarian property tax sample notices | out of scope; can delete |
| `*.jar`, `*.zip` | the original downloads | extracted already; can delete to save ~650 MB |
| `eric_logs/` | ERiC log files of the checks | can delete any time |

### Two facts that changed the plan

- **Your own Hersteller-ID is required for real ERiC validation and for any sending, including
  tests.** The demo ID `74931` from older docs is blocked: ERiC refuses it already during validation
  (`610301202`). Coding and the offline test suite don't need it, so you can add it later.
  Do not use a made-up ID to send anything.
- **Use the test tax number for every test.** Only Bayern has them; they work for UStVA, USt and
  EÜR. `.env` uses `9198011310010` (198/113/10010, test Finanzamt 9198). ELSTER deletes everything
  sent to a test Finanzamt, even a case without Testmerker, so a mistake can't become a filing.

If `uv` is not found in your terminal, use `py -m uv` instead of `uv` in the commands below.

---

## M1: Hersteller-ID and certificate PIN

1. **Hersteller-ID** (5 digits): log in to the developer area
   (https://www.elster.de/elsterweb/entwickler/login). If you don't have one yet, apply under
   *Anträge und Formulare*. It is per product, so apply for "FreiBuch". Wait for the number.
2. Open `.env` in the repository root and replace the two placeholders:
   ```ini
   FINAMT_ELSTER_CERT_PASSWORD=<YOUR-CERTIFICATE-PIN>
   FINAMT_ELSTER_HERSTELLER_ID=<YOUR-HERSTELLER-ID>
   ```
   No quotes. Leave the other lines alone. If you ever edit a path, use forward slashes
   (`C:/Users/...`): with backslashes, `uv run --env-file` silently loads nothing.
3. Check in *Mein ELSTER* when your certificate expires, and renew it in time.

**Hand back**: "M1 done". Never paste the PIN.

## M2: First test submission

Proves that the ELSTER server accepts FreiBuch's UStVA (task UST-5). It sends a fixed test case:
Q1 2025, one sale of 1 000.99 € net at 19 %, with the Testmerker, to the test Finanzamt. It is not
a filing. The script refuses to run with a real tax number.

From the repository root in PowerShell:
```powershell
uv run --env-file .env python scripts/ustva_test_submission.py          # 1. validate, nothing sent
uv run --env-file .env python scripts/ustva_test_submission.py --send   # 2. test submission
```
Step 1 should print `success=True`. Step 2 should print `success=True` and a `telenummer`.

If step 2 fails with a certificate error, try the ERiC test certificate once: in `.env` set
`FINAMT_ELSTER_CERT_PATH` to `…/private/ERiC-44.3.6.0/Windows-x86_64/Beispiel/ericdemo-python/test-softidnr-pse.pfx`
and `FINAMT_ELSTER_CERT_PASSWORD=123456`, run step 2 again, then switch both lines back.

**Hand back** (UST-5): the printed lines (`success`, `telenummer`, error text). Remove nothing;
they contain only the test tax number.

## M3: Decide asset depreciation

Equipment above 800 € net currently goes to "ZU PRÜFEN" and is not counted. Tell the agent which
option to build (EUR-3):

- **A. Write off over the useful life (AfA)**, straight-line per the official AfA tables. Standard
  and always correct.
- **B. Sammelposten** (pool) for assets over 250 € and up to 1 000 € net, written off over 5 years
  (§ 6 Abs. 2a EStG, verified).
- **C. One-year write-off for computer hardware and software**, per BMF guidance (the agent must
  verify the current BMF letter before building it).

Say for example "M3: use C for computers, A for everything else". The agent verifies the sources
and builds it. With any AfA, the EÜR must also send Anlage AVEÜR (ERiC enforces it).

## M4: File for real

Do this for each UStVA, the annual USt, and later the EÜR.

1. **Deadline**: UStVA by the 10th day after the period (§ 18 Abs. 1 UStG); +1 month with a
   Dauerfristverlängerung (§ 46 UStDV).
2. Make sure all receipts for the period are in and reviewed in the web UI. For the EÜR, the
   "ZU PRÜFEN" list must be empty or deliberately decided.
3. In `.env`, replace the three test tax number lines with **your** values (see the comment block
   there): 13-digit ELSTER tax number, its first 4 digits, your 2-digit Bundesland code. Your
   Finanzamt letter shows the regional format; *Mein ELSTER* shows the 13-digit one.
4. Validate first: `uv run finamt serve`, open http://127.0.0.1:8000, open the period and click
   validate with **"Testmodus (nicht rechtswirksam)" ticked**. Compare the Kennzahlen with your
   own check.
5. Turn on live filing **only for this one server run** (PowerShell):
   ```powershell
   $env:FINAMT_ALLOW_LIVE_SUBMISSION = "1"; uv run finamt serve
   ```
   In the UI, **untick** "Testmodus" and send.
6. Save the `telenummer` / ELSTER receipt (the UI records live submissions under *Submissions*).
7. **Close that PowerShell window.** Live filing is off again, because `.env` keeps
   `FINAMT_ALLOW_LIVE_SUBMISSION=0`. Put the test tax number lines back into `.env` if you want to
   run tests later.

Corrections: send again as a Berichtigung (`"is_berichtigung": true`, UStVA Kz 10).

## M5: Yearly update

ELSTER publishes a new ERiC each year, and the BMF publishes new forms (Anlage EÜR around
August–September, UStVA around December).

1. In the developer area, download into `private/`: the **Windows x86-64** ERiC `.jar` (not
   `Windows-x86`, which is 32-bit), the **Dokumentation** `.zip`, and the **Vordrucke_<year>** `.zip`.
2. Tell an agent: "do YEAR-1 for <year>, new ERiC is in private/". It extracts them, updates the
   `.env` paths, checks every Kennzahl and XML fact, and re-runs the ERiC validation.
3. Review its summary of what changed.

## M6: Optional: ask upstream for the UI source

The web UI ships only as a compiled bundle. The upstream authors own the copyright, so they don't
have to publish the source, but you can ask. Send a short message to the contact address in the
upstream README, for example:

> Hello, I use finamt (AGPL-3.0) for my own freelance bookkeeping and maintain a fork (FreiBuch) limited to
> UStVA/USt/EÜR. The repository contains only the built web UI (`src/finamt/ui/static/`). Could
> you share the frontend source (React/Vite project), under AGPL-3.0 like the rest of finamt?
> Thank you!

If you get it, tell the agent so it can revisit decision D2. If not, nothing is blocked: the plan in
D2 and the UI tasks in [TODO.md](TODO.md) work without it.
