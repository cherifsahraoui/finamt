# finamt (Freiberufler fork)

A free, local, open-source tool for **one German Freiberufler** to do their own VAT and
EÜR without a paid bookkeeping subscription such as Accountable:

**receipts in → UStVA → annual Umsatzsteuererklärung → EÜR → ELSTER**

Everything runs on your own machine. Receipts, the database and your ELSTER certificate never
leave it, except for the ELSTER submission itself.

> This is a fork of [spaceoctahedron/finamt](https://github.com/spaceoctahedron/finamt)
> (AGPL-3.0), cut down to the Freiberufler use case. What changed is listed in [NOTICE.md](NOTICE.md).
> It is not tax advice; see the [disclaimer](#disclaimer).

## What it does today

| Task | Status | How |
|---|---|---|
| Read receipts and invoices (PDF/scan) with OCR + a local LLM | ✅ works | `finamt process`, `finamt batch`, web UI |
| Store receipts, de-duplicate, categorise | ✅ works | local SQLite in `~/.finamt/<project>/` |
| UStVA calculation (quarterly) | ✅ works | `finamt ustva --quarter Q --year Y` |
| UStVA calculation (monthly) | ✅ in the web UI / API | CLI flag planned (CLI-1) |
| UStVA / annual USt **submission** via ELSTER (ERiC) | ✅ works in test mode; live needs an explicit switch | web UI (`finamt serve`) |
| EÜR calculation with Anlage EÜR 2025 Kennzahlen | ✅ works (VAT lines still missing, EUR-2) | Python API, see below |
| EÜR submission via ELSTER | ⛔ not yet (EUR-4, needs ERiC docs) | — |
| Credit notes, 0 % and reverse-charge sales in the UStVA | ⛔ not yet (UST-2 … UST-4) | — |
| Writing invoices (§ 14 UStG) | ⛔ not yet (INV-1) | — |
| Zusammenfassende Meldung for EU clients | ⛔ not yet (ZM-1) | — |
| Kleinunternehmer (§ 19 UStG) mode | ⛔ not yet (EUR-2) | — |

Out of scope: KSt, GewSt, E-Bilanz, Jahresabschluss, Einkommensteuer. The upstream code for
these lives in [`legacy/`](legacy/README.md) and is not installed.

## Roadmap

The work is split into small tasks that an AI agent (or a person) can pick up one at a time.
The full list, with steps and tests, is in **[docs/TODO.md](docs/TODO.md)**. The next steps:

1. **UST-1**: import VAT on its own UStVA line (Kz 62)
2. **UST-2**: credit notes in the UStVA; always send Kz 83
3. **EUR-2**: VAT lines and Kleinunternehmer mode in the EÜR
4. **CLI-1**: `finamt eur`, monthly UStVA, filing-period hint
5. **UST-3 / UST-4**: 0 % sales and reverse charge for EU clients
6. **INV-1**: outgoing invoices with gapless numbering
7. **ZM-1**: Zusammenfassende Meldung
8. **EUR-4**: EÜR submission via ELSTER (needs the ERiC EÜR schema from the developer portal)

Decisions that shape the project (CLI first, no live filing by default, …) are in
[docs/DECISIONS.md](docs/DECISIONS.md).

## Install

Python 3.10–3.13. From source:

```bash
git clone https://github.com/cherifsahraoui/finamt.git
cd finamt
uv sync --extra dev          # or: python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
uv run finamt --help
```

On first use, OCR and LLM models are downloaded from HuggingFace (about 4 GB, cached in
`~/.cache/huggingface/hub`). Tesseract is an optional OCR fallback:
`sudo apt-get install tesseract-ocr tesseract-ocr-deu` or `brew install tesseract tesseract-lang`.

## A year with finamt

1. **Collect receipts.** Drop incoming invoices (`--type purchase`) and your own outgoing invoices
   (`--type sale`) into a folder and read them in:
   ```bash
   finamt batch --input-dir ~/belege/2025-q1 --type purchase
   finamt batch --input-dir ~/rechnungen/2025-q1 --type sale
   ```
   Or use the web UI: `finamt serve`, then upload, review and correct.
2. **UStVA** every quarter (or month, if your prior-year VAT was over 9 000 €, § 18 Abs. 2 UStG),
   due on the 10th day after the period:
   ```bash
   finamt ustva --quarter 1 --year 2025 --output ustva_q1_2025.json
   ```
   Submit from the web UI in **test mode** first. Live filing needs `FINAMT_ALLOW_LIVE_SUBMISSION=1`
   (see [Safety](#safety)).
3. **Annual USt** from the web UI (Umsatzsteuererklärung).
4. **EÜR** for the year (Python until `finamt eur` exists):
   ```python
   from datetime import date
   from finamt.storage import get_repository
   from finamt.tax import generate_eur

   with get_repository() as repo:
       receipts = list(repo.find_by_period(date(2025, 1, 1), date(2025, 12, 31)))
   report = generate_eur(receipts, 2025)
   print(report.summary())          # Kennzahlen per Anlage EÜR 2025 + "ZU PRÜFEN" list
   ```
   Anything finamt can't classify safely (assets over 800 €, meals, gifts, donations, tax
   payments, private deposits/withdrawals) appears under **ZU PRÜFEN** and is *not* counted until
   you decide. Until EÜR submission exists, copy the Kennzahlen into ELSTER by hand.

## Categories and EÜR lines

Each receipt has a category and an optional subcategory. For purchases, they decide the Anlage EÜR
2025 line (Kennzahl). The values are verified in [docs/tax-rules.md](docs/tax-rules.md).

| Category | Subcategories | EÜR Kz (purchase) |
|---|---|---|
| `services` | `freelance` `consulting` `legal` `accounting` `notary` | 110 Fremdleistungen; legal/accounting/notary → 194 |
| `products` | `physical_goods` `digital_goods` `merchandise` `samples` | 100 |
| `material` | `consumables` `raw_materials` `packaging` `merchandise` | 100; consumables → 229; packaging → 227 |
| `equipment` | `low_value_asset` `computer` `machinery` `furniture` `tools` | 132 GWG up to 800 € net; above → review (AfA) |
| `software` | `subscriptions` `pay_as_you_go` `licenses` `hosting` `domains` | 228 EDV-Kosten |
| `licensing` | `software_licenses` `media_licenses` `other_ip` | 183 |
| `telecommunication` | `phone` `internet` `bundled` | 280 |
| `travel` | `transport` `accommodation` `meals` `per_diem` `incidental` | 221; transport → 146; meals/per_diem → review |
| `car` | `fuel` `parking` `garage` `repair` `maintenance` `insurance` `leasing` `rental` | 146; leasing → 144; insurance → 145 |
| `education` | `courses` `books` `conferences` `certifications` | 281; books → 229 |
| `utilities` | `electricity` `heating` `water` `waste` | 151 |
| `insurance` | `liability` `health` `vehicle` `property` | 223; vehicle → 145; property → 151; health → review |
| `financial` | `bank_fees` `interest` `loan_costs` `payment_fees` | 183; interest/loan_costs → 234 |
| `office` | `rent` `coworking` `storage` `cleaning` `security` | 150; cleaning/security → 151 |
| `marketing` | `advertising` `print_media` `trade_fairs` `sponsorship` `gifts` | 224; gifts → review |
| `donations` | `charitable` `political` `church` | review |
| `public_fees` | `broadcasting_fee` `ihk_hwk` `berufsgenossenschaft` `other_public_fee` | 223 |
| `tax_settlement` | `vat_refund` `vat_payment` `income_tax` `trade_tax` `other_tax` | review (Kz 186/141 in EUR-2) |
| `capital_movement` | `owner_equity` `shareholder_loan` `withdrawal` | review (not a business income/expense) |
| `other` | `membership_fees` `sundry` | 183; membership_fees → 223 |

Sales: taxable → Kz 112, 0 % / tax-free → Kz 103, sale of equipment → Kz 102.

## Safety

- **No live filing by default.** Anything legally binding sent to ELSTER needs
  `FINAMT_ALLOW_LIVE_SUBMISSION=1` in your local environment. Test submissions (Testmerker) and
  validation always work. EÜR live submission is disabled completely for now.
- **Secrets stay local.** Certificates (`.pfx`), `.env`, databases, ERiC libraries and model files are
  git-ignored. Put real values only in `.env` (template: [.env.example](.env.example)).
- **Verified numbers only.** Every rate, threshold and Kennzahl the code uses is listed with its
  official source in [docs/tax-rules.md](docs/tax-rules.md). Anything unverified is marked `TODO`.

## ELSTER setup

1. Get an ELSTER certificate (`.pfx`) for your Steuernummer at elster.de.
2. With an ELSTER developer account, download **ERiC** and unpack it outside this repository.
3. Copy `.env.example` to `.env`. Set both `FINAMT_ERIC_HOME` (read by the web UI today) and
   `ERIC_LIBRARY_PATH` (the future single setting, CFG-1) to the ERiC `lib` folder. Then fill in the
   certificate path and PIN, Steuernummer, Finanzamt number, Bundesland and your Hersteller-ID.
4. Start `finamt serve` and submit a UStVA in test mode.

## For contributors and AI agents

Start with **[AGENTS.md](AGENTS.md)**: commands, hard rules and the definition of done. Then take the
first `ready` card in [docs/TODO.md](docs/TODO.md). Code map: [docs/BASELINE.md](docs/BASELINE.md).

```bash
uv run pytest                          # offline: no LLM, OCR model, ERiC or network
uv run ruff check src tests
uv run ruff format --check src tests
```

## How it reads receipts

OCR (PyMuPDF text layer, PaddleOCR, Tesseract fallback) followed by four small local-LLM agents:

| Agent | Extracts |
|---|---|
| 1 | receipt number, date, category |
| 2 | counterparty (name, VAT ID, Steuernummer, address) |
| 3 | total, VAT rate, VAT amount |
| 4 | line items |

Models: `mistral:7b` (default) or `qwen2.5:7b-instruct-q4_K_M`, via mlx-lm on Apple Silicon or
transformers elsewhere. Settings are in `.env` (`FINAMT_AGENT_*`, `FINAMT_OCR_*`).

## License and credits

AGPL-3.0, see [LICENSE](LICENSE). Based on finamt by Yauheniya Varabyova / Space Octahedron GmbH
([upstream](https://github.com/spaceoctahedron/finamt)); the changes in this fork are listed in
[NOTICE.md](NOTICE.md). Third-party components: PaddleOCR, Tesseract, HuggingFace transformers
(Apache-2.0), mlx-lm (MIT). LLM models are downloaded on first use and are subject to their own licenses.
The ELSTER ERiC library is not distributed with this project.

## Disclaimer

This software helps prepare German VAT and EÜR data. It is **not tax, legal or accounting advice**.
OCR and LLM extraction can be wrong, and Kennzahlen change every year. Check every figure before
submitting anything to the Finanzamt; for binding advice, ask a Steuerberater. The authors accept no
liability for incorrect filings.
