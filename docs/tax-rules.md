# Tax rules register

Every tax value used by code under `src/finamt/tax/` must have a row here.
**Status `verified`** = a human or agent read the cited official source for that year and the
code matches it. Anything else is **`TODO`**, and code using it must not be relied on.

> As of this baseline, **no row is verified**. The official hosts (gesetze-im-internet.de,
> bundesfinanzministerium.de, formulare-bfinv.de) could not be reached from the build
> environment, and the ELSTER/ERiC developer documentation needs a login. The "expected"
> numbers below come from upstream code comments or general knowledge, not from a source
> read for this register. Verify each one before relying on it, then change its status and add
> the date and what you checked.

How to verify a row: open the URL, find the paragraph for the given year, compare with the code
location named in the rule, set status to `verified (YYYY-MM-DD, <who>)`. If code and source
disagree, open a TODO in `docs/TODO.md`. Do not change the code in the same commit as the register.

## VAT rates (UStG)

| value | rule | legal source (URL) | year | status |
|---|---|---|---|---|
| 19 % | General rate. Code: `ustva.py` groups by `vat_percentage`, key `"19"` → `USTVAReport.line_19` → Kz 81 (`elster._ustva_kennzahlen`). | § 12 Abs. 1 UStG — https://www.gesetze-im-internet.de/ustg_1980/__12.html | 2024–2026 | TODO |
| 7 % | Reduced rate. Code: key `"7"` → `line_7` → Kz 86. | § 12 Abs. 2 UStG — https://www.gesetze-im-internet.de/ustg_1980/__12.html | 2024–2026 | TODO |
| other rate (≠ 19, 7) | Any other non-zero rate goes to Kz 35 (base) / Kz 36 (tax). | UStVA form / Anleitung (BMF, formulare-bfinv.de) | 2024–2026 | TODO |
| 0 % / no VAT | Receipts with `vat_amount` 0 or missing are **skipped** by `generate_ustva` (not reported, e.g. tax-free or reverse-charge sales). Behaviour, not a legal value. | § 4, § 13b UStG — https://www.gesetze-im-internet.de/ustg_1980/ | — | TODO (gap, see TODO.md) |

## Kleinunternehmer (§ 19 UStG)

| value | rule | legal source (URL) | year | status |
|---|---|---|---|---|
| Prior-year turnover limit (expected 25 000 €) | Below the limit, VAT is not charged. **Not used by code**: there is no Kleinunternehmer mode. | § 19 Abs. 1 UStG — https://www.gesetze-im-internet.de/ustg_1980/__19.html | from 2025 | TODO |
| Current-year turnover limit (expected 100 000 €, exceeded → regular taxation immediately) | Not used by code. | § 19 Abs. 1 UStG (same URL) | from 2025 | TODO |
| Limits before 2025 (expected 22 000 € / 50 000 € forecast) | Not used by code. | § 19 Abs. 1 UStG a.F. | ≤ 2024 | TODO |
| Kleinbetragsrechnung limit (expected 250 €) | Not used by code (relevant for invoice generation). | § 33 UStDV — https://www.gesetze-im-internet.de/ustdv_1980/__33.html | 2024–2026 | TODO |

## UStVA periods and deadlines (§ 18 UStG)

| value | rule | legal source (URL) | year | status |
|---|---|---|---|---|
| Quarter (Kalendervierteljahr) | Default Voranmeldungszeitraum. Code: CLI `finamt ustva --quarter`, API `quarter`. | § 18 Abs. 2 S. 1 UStG — https://www.gesetze-im-internet.de/ustg_1980/__18.html | 2024–2026 | TODO |
| Month if prior-year tax > threshold (expected 7 500 €; possibly 9 000 € from 2025) | Code accepts `month` in the API; no rule chooses the period automatically. | § 18 Abs. 2 S. 2 UStG (same URL) | 2024–2026 | TODO |
| Exemption from Voranmeldungen below threshold (expected 1 000 €; possibly 2 000 € from 2025) | Not used by code. | § 18 Abs. 2 S. 3 UStG (same URL) | 2024–2026 | TODO |
| Neugründer: monthly in the first two years (suspension period to verify) | Not used by code. | § 18 Abs. 2 S. 4–6 UStG (same URL) | 2021–2026 | TODO |
| Deadline: 10th day after period end | Not used by code. | § 18 Abs. 1 S. 1 UStG (same URL) | 2024–2026 | TODO |
| Dauerfristverlängerung (+1 month; Sondervorauszahlung 1/11 for monthly filers) | Annual USt E50 element `vorauszahlungssoll` in `ElsterConfig`. | §§ 46–48 UStDV — https://www.gesetze-im-internet.de/ustdv_1980/__46.html | 2024–2026 | TODO |
| ELSTER `Zeitraum` codes: `01`–`12` months, `41`–`44` quarters, annual `period=0` | Code: `ElsterXMLBuilder.build_ustva` (`str(period).zfill(2)`). | ELSTER UStVA schema / ERiC Jahresdokumentation (developer portal, login) | 2024–2026 | TODO |

## UStVA Kennzahlen and rounding (`elster._ustva_kennzahlen`)

| value | rule | legal source (URL) | year | status |
|---|---|---|---|---|
| Kz 81 | Base for 19 % sales, **whole euros, truncated** (`ROUND_DOWN`). Only written if > 0. | UStVA Vordruck + Anleitung (BMF-Schreiben, https://www.formulare-bfinv.de) | 2024–2026 | TODO (verify truncation vs. rounding) |
| Kz 86 | Base for 7 % sales, whole euros, truncated. Only if > 0. | same | 2024–2026 | TODO |
| Kz 35 / Kz 36 | Other rates: base whole euros truncated / tax with cents, accumulated over rates. | same | 2024–2026 | TODO |
| Kz 66 | Deductible input tax, cents. Code also adds Einfuhrumsatzsteuer here (not Kz 62). | same; § 15 UStG — https://www.gesetze-im-internet.de/ustg_1980/__15.html | 2024–2026 | TODO (check Kz 62) |
| Kz 83 | Remaining advance payment / surplus, cents; omitted for an empty period. | same | 2024–2026 | TODO |
| XSD element order `_USTVA_KZ_ORDER` | Element sequence required by the UStVA schema. | ERiC UStVA schema (developer portal) | 2025 | TODO |
| Annual USt E50 elements `E3003303/04`, `E3004401/02`, `E3006001`, `E3006201`, `E3006401`, `E3006901`, `E3009201`, `E3009801`, `E3009901`, `E3010201` | Mapping in `ElsterXMLBuilder._build_ust_annual_e50`; bases whole euros truncated, tax with cents. | ERiC USt E50 schema / Anlage USt 2A (developer portal, BMF) | 2023–2025 | TODO |

## EÜR (`eur.py`)

| value | rule | legal source (URL) | year | status |
|---|---|---|---|---|
| Method | Cash basis (Zufluss/Abfluss), profit = income − expenses. Code assumes `receipt_date` = payment date. | § 4 Abs. 3 EStG — https://www.gesetze-im-internet.de/estg/__4.html; § 11 EStG — https://www.gesetze-im-internet.de/estg/__11.html | 2024–2026 | TODO |
| Filing obligation | Anlage EÜR by electronic data transmission (official data set). | § 60 Abs. 4 EStDV — https://www.gesetze-im-internet.de/estdv_1955/__60.html | 2024–2026 | TODO |
| Income Kz 111 | Code maps `services`, `consulting`, `products`, `licensing` sales → "111". Upstream comment calls it "USt-pflichtige Betriebseinnahmen". **Suspected wrong**: on recent forms 111 may be the Kleinunternehmer line and 112 the taxable one. | Anlage EÜR + Anleitung (BMF-Schreiben, https://www.formulare-bfinv.de) | 2024 | TODO |
| Income Kz 112 | Code maps `other` sales → "112" ("steuerfrei/nicht steuerbar"). Suspected wrong (see above). | same | 2024 | TODO |
| Expense Kz 140 | `equipment` → "140" (AfA/GWG). Suspected wrong; 140 may be "vereinnahmte Umsatzsteuer". | same; § 6 Abs. 2/2a EStG (GWG 800 €, Sammelposten) — https://www.gesetze-im-internet.de/estg/__6.html | 2024 | TODO |
| Expense Kz 145 | `material`, `software`, `telecommunication` (and dead key `internet`) → "145". | Anlage EÜR | 2024 | TODO |
| Expense Kz 165 | `travel` → "165". | Anlage EÜR | 2024 | TODO |
| Expense Kz 172 | `insurance` → "172". | Anlage EÜR | 2024 | TODO |
| Expense Kz 176 | `utilities`, `other`, dead key `taxes`, and every unmapped category (`car`, `office`, `financial`, `marketing`, `donations`, `public_fees`, `tax_settlement`, `capital_movement`) → "176". | Anlage EÜR | 2024 | TODO |
| Expense Kz 183 | `education` → "183". | Anlage EÜR | 2024 | TODO |
| VAT in EÜR | Code excludes VAT from income and expenses (net method). Under § 4 Abs. 3 EStG, collected USt and paid Vorsteuer / USt payments to the Finanzamt are usually income/expenses in their own Kennzahlen. | Anlage EÜR Anleitung; § 4 Abs. 3 EStG | 2024 | TODO (design question, see TODO.md) |
| ELSTER DatenArt / `datenartVersion` for Anlage EÜR | Not set anywhere. `eur_elster.submit(mode="test")` requires the caller to pass `datenart_version`. | ERiC Jahresdokumentation (developer portal) | 2024–2025 | TODO |

## ELSTER constants (`elster.py`)

| value | rule | legal source (URL) | year | status |
|---|---|---|---|---|
| Testmerker `700000004` | Marks a test submission; `eur_elster` refuses test mode without it. | ERiC/ELSTER developer documentation (login) | — | TODO |
| Namespace `http://www.elster.de/elsterxml/schema/v11` | Envelope namespace. | ERiC developer documentation | — | TODO |
