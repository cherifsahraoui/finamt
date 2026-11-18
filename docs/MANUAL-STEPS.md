# Manual steps for the owner

Some steps can't be done by an AI agent: they need your ELSTER developer login, your
certificate, or a decision only you can make. This runbook covers each one, in order. Every
step says what it unblocks in [TODO.md](TODO.md) and what to hand back to the agent.

Never commit anything from these steps. ERiC, certificates, `.env`, databases and generated XML
are git-ignored; keep them outside the repository anyway.

| # | Step | When | Unblocks | Time |
|---|---|---|---|---|
| M1 | [Set up ELSTER developer access, Hersteller-ID and ERiC](#m1-elster-developer-setup) | once | everything ELSTER | 30 min (+ waiting for the Hersteller-ID) |
| M2 | [Configure finamt (`.env`) and check that ERiC loads](#m2-configure-finamt) | once | M3 | 15 min |
| M3 | [First UStVA validation and test submission](#m3-first-ustva-test-submission) | once, then yearly | UST-5 | 30 min |
| M4 | [Collect the EÜR schema facts from ERiC](#m4-collect-the-eür-schema-facts-from-eric) | once per tax year | EUR-4 | 30–60 min |
| M5 | [Decide how assets above 800 € are depreciated](#m5-decide-asset-depreciation) | once | EUR-3 | 10 min |
| M6 | [File for real (live)](#m6-file-for-real) | every period | — | 10 min per filing |
| M7 | [Yearly form check](#m7-yearly-form-check) | each autumn/winter | YEAR-1 | agent does it; 5 min for you |
| M8 | [Optional: ask upstream for the web UI source](#m8-optional-ask-upstream-for-the-ui-source) | optional | UI decision | 5 min |

---

## M1: ELSTER developer setup

ELSTER's own steps for developers (elster.de → Benutzergruppen → Entwickler) are: register as a
Hersteller/Entwickler, get developer-area access from the Bayerisches Landesamt für Steuern,
download ERiC in the developer area, and **apply for a Hersteller-ID** under "Anträge und
Formulare". You already have the developer account. Check the rest:

1. **Log in** to the developer area: https://www.elster.de/elsterweb/entwickler/login
2. **Hersteller-ID**: if you don't have one yet, apply for it in the developer area under
   *Anträge und Formulare*. Note the number; it goes into `FINAMT_ELSTER_HERSTELLER_ID`. Do not
   use the ID that was in the upstream `.env.example`; it belongs to another manufacturer.
3. **Download ERiC** for the machine you file from (Linux x86-64, macOS or Windows). Unpack it
   **outside** the repository, for example:
   ```bash
   mkdir -p ~/elster && cd ~/elster && unzip ~/Downloads/ERiC-*.zip
   ```
   Find the folder that contains `libericapi.so` (Linux), `libericapi.dylib` (macOS) or
   `ericapi.dll` (Windows), plus a `plugins` folder:
   ```bash
   find ~/elster -name 'libericapi.*' -o -name 'ericapi.dll'
   ```
   That folder is your **ERiC lib path**. Upstream used `ERiC-43.4.6.0/Darwin-universal/lib`.
4. While you are in the developer area, also download the **ERiC documentation /
   Jahresdokumentation** for the current tax year. M4 needs it.
5. **Your ELSTER certificate**: the `.pfx` file from your *Mein ELSTER* account (the
   "Zertifikatsdatei" you log in with) and its PIN. Copy it to a private place:
   ```bash
   mkdir -p ~/.finamt/default && cp ~/path/to/your-cert.pfx ~/.finamt/default/elster_cert.pfx
   chmod 600 ~/.finamt/default/elster_cert.pfx
   ```
   If the developer area offers **test certificates** and test tax numbers, prefer them for M3.

**Hand back**: nothing; just tell the agent "M1 done".

## M2: Configure finamt

1. In the repository root:
   ```bash
   cp .env.example .env
   chmod 600 .env
   ```
2. Fill in `.env` (no quotes needed):
   ```ini
   ERIC_LIBRARY_PATH=/home/<you>/elster/ERiC-<version>/<platform>/lib
   FINAMT_ERIC_HOME=/home/<you>/elster/ERiC-<version>/<platform>/lib   # same folder; web UI reads this until CFG-1
   FINAMT_ELSTER_CERT_PATH=~/.finamt/default/elster_cert.pfx
   FINAMT_ELSTER_CERT_PASSWORD=<your certificate PIN>
   FINAMT_ELSTER_STEUERNUMMER=<your 13-digit ELSTER tax number, digits only>
   FINAMT_ELSTER_FINANZAMT_NR=<4-digit Finanzamt number = first 4 digits of the 13-digit number>
   FINAMT_ELSTER_BUNDESLAND_KZ=<2-digit Bundesland code>
   FINAMT_ELSTER_HERSTELLER_ID=<your Hersteller-ID>
   FINAMT_ALLOW_LIVE_SUBMISSION=0
   ```
   The 13-digit ELSTER tax number is the "bundeseinheitliche Steuernummer"; your Finanzamt letter
   shows the regional format, and ELSTER shows the 13-digit form.
   Prefer `.env` over typing the PIN into the web UI: the UI stores the PIN in the project database.
3. **Check that ERiC loads** (no network, nothing is sent):
   ```bash
   set -a; . ./.env; set +a
   uv run python -c "
   import os
   from finamt.tax.eric_wrapper import EricSession
   with EricSession(os.environ['ERIC_LIBRARY_PATH']):
       print('ERiC OK')
   "
   ```
   `ERiC OK` means the library and plugins were found. An `OSError` means the path is wrong, or
   the ERiC build doesn't match your OS or CPU.

**Hand back**: "M2 done, ERiC OK" (or the error text). Never paste the PIN or the certificate.

## M3: First UStVA test submission

Goal: prove the UStVA path works with your ERiC and certificate, and answer the open rounding
question (UST-5). Use a **past** quarter. With the Testmerker, the submission is a test and not a
filing.

Start the server with your `.env` loaded:
```bash
set -a; . ./.env; set +a
uv run finamt serve
```

**Option A, web UI**: open http://127.0.0.1:8000 and:
1. In the taxpayer profile, set Rechtsform to **Freiberuflich** and enter your name and address.
2. In **ELSTER-DATEN**, check the ERiC path and Hersteller-ID. The certificate comes from `.env`.
3. Add one manual sale receipt in the quarter with a net amount **with cents**, for example 1 000.99 €
   at 19 %.
4. Open the UStVA for that quarter. Keep **"Testmodus (nicht rechtswirksam)" ticked**, then validate
   and send.

**Option B, terminal** (reproducible; a second terminal while the server runs):
```bash
DB=$HOME/.finamt/default/finamt.db
API=http://127.0.0.1:8000

# 1. a test receipt with cents in the base
curl -s -X POST "$API/receipts?db=$DB" -H 'Content-Type: application/json' \
  -d '{"date":"2025-02-10","vendor":"Testkunde","receipt_type":"sale","category":"services","net_amount":1000.99,"vat_percentage":19}'

# 2. look at the XML finamt would send (nothing is sent)
curl -s -X POST "$API/tax/ustva/xml?db=$DB" -H 'Content-Type: application/json' \
  -d '{"year":2025,"quarter":1,"use_test":true}' > /tmp/ustva-q1-test.xml
grep -o '<Kz[0-9]*>[^<]*</Kz[0-9]*>\|<Testmerker>[^<]*</Testmerker>' /tmp/ustva-q1-test.xml

# 3. ERiC validation only (uses the certificate, sends nothing)
curl -s -X POST "$API/tax/ustva/submit?db=$DB" -H 'Content-Type: application/json' \
  -d '{"year":2025,"quarter":1,"use_test":true,"validate_only":true}'

# 4. test submission (Testmerker set, not a filing)
curl -s -X POST "$API/tax/ustva/submit?db=$DB" -H 'Content-Type: application/json' \
  -d '{"year":2025,"quarter":1,"use_test":true}'
```
Step 2 should show `Kz81` = `1000` (cents cut off), `Kz83` = `190.19`, and `Testmerker` = `700000004`.

Afterwards, delete the test receipt (web UI, or `DELETE /receipts/{id}`).

**Hand back** to the agent (UST-5):
- whether validation and the test submission succeeded, and the `telenummer` if there was one;
- the full error or hint text from ERiC if anything failed (remove your tax number from it first);
- whether ERiC complained about the base `1000` for a net of 1 000.99.

The agent then records the result in `docs/tax-rules.md` (rows "truncation", `_USTVA_KZ_ORDER`) and
updates decision D5.

## M4: Collect the EÜR schema facts from ERiC

EUR-4 (sending the EÜR via ELSTER) is blocked only by facts that are in the ERiC documentation
behind your login. These facts (names and strings, not whole files) are needed for
interoperability. Do **not** copy whole XSD or documentation files into the repository.

1. Search your unpacked ERiC and its documentation:
   ```bash
   cd ~/elster
   find . -iname '*eur*' | grep -iv 'euro' | head -50          # EÜR schema, examples, docs
   grep -rhoE '\b(EUER|UStVA|USt)_20[0-9]{2}\b' . 2>/dev/null | sort -u   # datenartVersion strings
   ```
   The second command also prints `UStVA_<year>` and `USt_<year>`: finamt already uses those
   strings, which confirms you are looking in the right place.
2. Write the answers into a private file **outside** the repo, e.g. `~/elster/eur-facts-2025.md`:
   - **datenartVersion** for the Anlage EÜR 2025 (the string passed to ERiC);
   - **Verfahren** and **DatenArt** for the TransferHeader (for UStVA they are
     `ElsterAnmeldung` / `UStVA`);
   - the **root element and namespace** of the EÜR payload (Nutzdaten);
   - for each Kennzahl in `docs/tax-rules.md` → "Anlage EÜR 2025 Kennzahlen": the **XML element
     name** and its format (cents? sign?);
   - whether **Anlage AVEÜR** must be sent with it (the BMF letter says it is a necessary part when
     you have fixed assets);
   - the path of an **example XML** for the EÜR in the ERiC package, if there is one.
3. Hand it to the agent in one of two ways:
   - **Paste** the facts file into the chat; or
   - run Claude Code **locally** on your machine, where `~/elster` exists, and tell it:
     "ERiC docs are in ~/elster, read them for EUR-4, don't copy files into the repo".

The agent records the values in `docs/tax-rules.md` (status `verified`, source "ERiC <version>
Jahresdokumentation") and starts EUR-4. Repeat this step every tax year: new ERiC, new strings.

## M5: Decide asset depreciation

Equipment above 800 € net currently goes to "ZU PRÜFEN" and is not counted. Tell the agent which
option to build (EUR-3):

- **A. Write off over the useful life (AfA)**, straight-line per the official AfA tables. Standard
  and always correct.
- **B. Sammelposten** (pool) for assets over 250 € and up to 1 000 € net, written off over 5 years
  (§ 6 Abs. 2a EStG, verified).
- **C. One-year write-off for computer hardware and software**, per BMF guidance (the agent must
  verify the current BMF letter before building it).

Say for example "M5: use C for computers, A for everything else". The agent verifies the sources
and builds it.

## M6: File for real

Do this for each UStVA, the annual USt, and later the EÜR.

1. **Deadline**: UStVA by the 10th day after the period (§ 18 Abs. 1 UStG); +1 month with a
   Dauerfristverlängerung (§ 46 UStDV).
2. Make sure all receipts for the period are in and reviewed in the web UI. For the EÜR, the
   "ZU PRÜFEN" list must be empty or deliberately decided.
3. Compare the Kennzahlen with your own check (step 2 of M3 shows them).
4. Run a **validation** and a **test submission** first (M3, steps 3–4).
5. Turn on live filing **only for this one server run**:
   ```bash
   set -a; . ./.env; set +a
   FINAMT_ALLOW_LIVE_SUBMISSION=1 uv run finamt serve
   ```
   In the UI, **untick** "Testmodus" and send. Or with curl, `"use_test": false`.
6. Save the `telenummer` / ELSTER receipt (the UI records live submissions under *Submissions*).
7. **Stop the server.** Live filing is off again, because `.env` keeps `FINAMT_ALLOW_LIVE_SUBMISSION=0`.

Corrections: send again with `"is_berichtigung": true` (UStVA).

## M7: Yearly form check

The BMF publishes new forms each year (Anlage EÜR around August–September, UStVA around
December). Tell an agent "do YEAR-1 for <year>". It downloads the BMF letters, compares every
Kennzahl and updates the mapping. Your part: review its summary of what changed, and do M4 again
with the new ERiC.

## M8: Optional: ask upstream for the UI source

The web UI ships only as a compiled bundle. The upstream authors own the copyright, so they don't
have to publish the source, but you can ask. Send a short message to the contact address in the
upstream README, for example:

> Hello, I use finamt (AGPL-3.0) for my own freelance bookkeeping and maintain a fork limited to
> UStVA/USt/EÜR. The repository contains only the built web UI (`src/finamt/ui/static/`). Could
> you share the frontend source (React/Vite project), under AGPL-3.0 like the rest of finamt?
> Thank you!

If you get it, tell the agent so it can revisit decision D2. If not, nothing is blocked: the plan in
D2 and the UI tasks in [TODO.md](TODO.md) work without it.
