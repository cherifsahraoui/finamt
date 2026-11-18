# Tax rules register

Every tax value used by code under `src/finamt/tax/` must have a row here.

- **`verified (date)`**: the cited official source was read on that date and the value matches.
- **`TODO`**: not verified. Code using it must flag it (see `AGENTS.md`).
- **`code differs`**: the source is verified, but the code doesn't follow it yet. The linked task in
  `docs/TODO.md` fixes it.

How to verify a row: read the source for the right year, compare it with the code, then set the
status with the date. If code and source disagree, set `code differs` and add a task to
`docs/TODO.md`. Do not change the code in the same commit as the register.

## Sources read on 2026-11-18

| id | document | URL |
|---|---|---|
| UStG | Umsatzsteuergesetz (current version) | https://www.gesetze-im-internet.de/ustg_1980/ (§§ 12, 13b, 14, 15, 18, 18a, 19) |
| UStDV | Umsatzsteuer-Durchführungsverordnung | https://www.gesetze-im-internet.de/ustdv_1980/ (§§ 33, 46, 48) |
| EStG | Einkommensteuergesetz | https://www.gesetze-im-internet.de/estg/ (§§ 4, 6, 11) |
| EStDV | Einkommensteuer-Durchführungsverordnung | https://www.gesetze-im-internet.de/estdv_1955/__60.html |
| USt1A-2026 | BMF-Schreiben 29.12.2025, III C 3 - S 7344/00039/007/036: Vordruckmuster USt 1 A 2026 + Anleitung USt 1 E | https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-vordruckmuster-USt-voranmeldung-2026.pdf?__blob=publicationFile&v=2 |
| EÜR-2025 | BMF-Schreiben 29.08.2025, IV C 6 - S 2142/00023/010/001: Anlage EÜR 2025 + Anleitung | https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Einkommensteuer/2025-08-29-anlage-EUER-2025.pdf?__blob=publicationFile&v=3 |
| USt-2026 | BMF-Schreiben 29.12.2025: Muster der Umsatzsteuererklärung 2026 | https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Umsatzsteuer/2025-12-29-muster-USt-erklaerung-2026.pdf?__blob=publicationFile&v=5 |

**Not publicly available** (needs the ELSTER developer login and the ERiC download): XML element
names, XSD, `datenartVersion` strings, Testmerker, and namespace. Rows that depend on them stay `TODO`
until someone checks them against the ERiC Jahresdokumentation.

## VAT rates (§ 12 UStG)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| 19 % | General rate ("19 Prozent der Bemessungsgrundlage"). Code: key `"19"` → Kz 81. | § 12 Abs. 1 UStG | current | verified (2026-11-18) |
| 7 % | Reduced rate ("ermäßigt sich auf sieben Prozent"). Code: key `"7"` → Kz 86. | § 12 Abs. 2 UStG | current | verified (2026-11-18) |
| 0 % | Rate for certain photovoltaic supplies, UStVA Kz 87. Code has no 0 % line: sales with VAT 0 are skipped by `generate_ustva`. | § 12 Abs. 3 UStG; USt1A-2026 Zeile 15 | 2026 | code differs → UST-3 |
| other rates | UStVA Kz 35 (base) / Kz 36 (tax). | USt1A-2026 Zeile 16 | 2026 | verified (2026-11-18) |

## Kleinunternehmer (§ 19 UStG)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| 25 000 € | Prior-year Gesamtumsatz must not exceed 25 000 € ("im vorangegangenen Kalenderjahr 25 000 Euro nicht überschritten"). Not used by code yet. | § 19 Abs. 1 S. 1 UStG | from 2025 | verified (2026-11-18) |
| 100 000 € | Current-year Gesamtumsatz must not exceed 100 000 €. Not used by code yet. | § 19 Abs. 1 S. 1 UStG | from 2025 | verified (2026-11-18) |
| tax-free, no VAT on invoices | Kleinunternehmer turnover is "steuerfrei". In the EÜR, all receipts go to Kz 111 at the received amount, and lines 15–17 are normally not used. | § 19 Abs. 1 UStG; EÜR-2025 Anleitung Zeile 12 | 2025 | verified (2026-11-18); code: EUR-2 |

## UStVA periods and deadlines (§ 18 UStG, UStDV)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| quarter | Default Voranmeldungszeitraum is the Kalendervierteljahr. CLI `--quarter`, API `quarter`. | § 18 Abs. 2 S. 1 UStG | current | verified (2026-11-18) |
| > 9 000 € | Monthly if prior-year tax was more than 9 000 €. No code chooses the period automatically. | § 18 Abs. 2 S. 2 UStG | current | verified (2026-11-18); code: CLI-1 |
| ≤ 2 000 € | Finanzamt may exempt from Voranmeldungen if prior-year tax was not more than 2 000 €. | § 18 Abs. 2 S. 3 UStG | current | verified (2026-11-18) |
| > 9 000 € surplus | May opt for monthly if prior-year surplus in the taxpayer's favour was more than 9 000 €. | § 18 Abs. 2a UStG | current | verified (2026-11-18) |
| new business | Monthly in the year of starting and the following year (S. 4). For 2021–2026, S. 4 is replaced by a projection: the actual tax is converted to an annual figure, or the expected tax of the starting year is used. | § 18 Abs. 2 S. 4 and S. 6 UStG | 2021–2026 | verified (2026-11-18) |
| 10th day | Voranmeldung due by the 10th day after the period ends, electronically. | § 18 Abs. 1 S. 1 UStG | current | verified (2026-11-18) |
| +1 month | Dauerfristverlängerung on application. Monthly filers pay a Sondervorauszahlung (§ 47 UStDV, not read). UStVA Kz 39 deducts it. | § 46 UStDV; § 48 Abs. 1 UStDV; USt1A-2026 Zeile 49 | current | verified (2026-11-18); § 47 TODO |
| `Zeitraum` codes `01`–`12`, `41`–`44`, annual `0` | ELSTER period codes used in `build_ustva`. | ERiC UStVA schema (developer login) | — | TODO |

## UStVA Kennzahlen 2026 (USt1A-2026, used by `elster._ustva_kennzahlen`)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| whole euros / cents | "Tragen Sie bei den Bemessungsgrundlagen bitte nur Beträge in vollen Euro ein; bei den Umsatzsteuer- und Vorsteuerbeträgen ist dagegen stets auch die Eintragung von Centbeträgen erforderlich." Negative amounts carry a minus sign. | USt1A-2026 Anleitung, general notes | 2026 | verified (2026-11-18) |
| truncation | Code cuts off cents (`ROUND_DOWN`). The guide says "ohne Centbeträge" but does not say whether to round or truncate. | ERiC plausibility rules (developer login) | 2026 | TODO → UST-5 |
| Kz 81 | Taxable supplies at 19 %, base without VAT. | USt1A-2026 Zeile 13 | 2026 | verified (2026-11-18) |
| Kz 86 | Taxable supplies at 7 %, base. | USt1A-2026 Zeile 14 | 2026 | verified (2026-11-18) |
| Kz 87 | Taxable supplies at 0 %, base. Not produced by code. | USt1A-2026 Zeile 15 | 2026 | code differs → UST-3 |
| Kz 35 / 36 | Other rates: base / tax. | USt1A-2026 Zeile 16 | 2026 | verified (2026-11-18) |
| Kz 41 | Tax-free intra-EU supplies of goods to buyers with a VAT ID. Not produced by code. | USt1A-2026 | 2026 | verified (2026-11-18) |
| Kz 48 | Tax-free supplies without input-tax deduction, e.g. § 19 Abs. 1 UStG. | USt1A-2026 | 2026 | verified (2026-11-18) |
| Kz 46 / 47 | Recipient owes the tax (§ 13b Abs. 1): services from an EU business, base / tax. Not produced by code. | USt1A-2026 section D; § 13b Abs. 1, 5 UStG | 2026 | code differs → UST-4 |
| Kz 84 / 85 | Other § 13b services (Abs. 2 Nr. 1, 2, 4–12), base / tax. | USt1A-2026 section D | 2026 | verified (2026-11-18) |
| Kz 60 | Supplier's taxable supplies where the recipient owes the tax under § 13b Abs. 5. | USt1A-2026 section E | 2026 | verified (2026-11-18) |
| Kz 21 | Non-taxable services under § 18b S. 1 Nr. 2 UStG (B2B services to EU businesses). This is the usual case for a freelancer billing EU clients. Not produced by code. | USt1A-2026 section E | 2026 | code differs → UST-4 |
| Kz 45 | Other non-taxable supplies (place of supply not in Germany). | USt1A-2026 section E | 2026 | verified (2026-11-18) |
| Kz 66 | Input tax from invoices of other businesses (§ 15 Abs. 1 S. 1 Nr. 1 UStG). | USt1A-2026 section F | 2026 | verified (2026-11-18) |
| Kz 61 | Input tax from intra-EU acquisitions. | USt1A-2026 section F | 2026 | verified (2026-11-18) |
| Kz 62 | Einfuhrumsatzsteuer (§ 15 Abs. 1 S. 1 Nr. 2 UStG). **Code adds it to Kz 66.** | USt1A-2026 section F; § 15 Abs. 1 S. 1 Nr. 2 UStG | 2026 | code differs → UST-1 |
| Kz 67 | Input tax from § 13b services (§ 15 Abs. 1 S. 1 Nr. 4 UStG). | USt1A-2026 section F | 2026 | code differs → UST-4 |
| Kz 50 / Kz 37 | Reductions under § 17 (credit notes, bad debts) contained in the base lines / in input tax. | USt1A-2026 section I | 2026 | code differs → UST-2 |
| Kz 39 | Deduction of the fixed Sondervorauszahlung (usually only in the last Voranmeldung of the year). | USt1A-2026 Zeile 49 | 2026 | verified (2026-11-18) |
| Kz 83 | Remaining advance payment / surplus ("Bitte in jedem Fall ausfüllen"). Code omits Kz 83 for an empty period; the form says always fill it in. | USt1A-2026 Zeile 50 | 2026 | code differs → UST-2 |
| `_USTVA_KZ_ORDER` | XML element order required by the UStVA XSD. | ERiC UStVA schema (developer login) | 2025 | TODO |
| E50 elements `E3003303`… | XML element names for the annual USt return. | ERiC USt schema (developer login); USt-2026 for the paper lines | 2023–2026 | TODO |

## Invoices (§ 14 UStG, § 33 UStDV)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| mandatory fields | (1) full name and address of supplier and recipient; (2) Steuernummer or USt-IdNr; (3) issue date; (4) unique sequential invoice number; (5) quantity and type of goods / scope and type of service; (6) date of supply; (7) consideration split by tax rate and exemption, plus any agreed reduction; (8) tax rate and tax amount, or a note on the exemption; (9) retention note in § 14b cases; (10) "Gutschrift" if issued by the recipient. | § 14 Abs. 4 S. 1 UStG | current | verified (2026-11-18) |
| 250 € | Kleinbetragsrechnung: up to 250 € total, reduced fields (supplier name and address, date, goods or service, gross amount with tax rate). Does not apply to § 3c, § 6a, § 13b supplies. | § 33 UStDV | current | verified (2026-11-18) |

## Zusammenfassende Meldung (§ 18a UStG)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| quarterly, 25th day | B2B services under § 3a Abs. 2 to EU recipients who owe the tax: ZM by the 25th day after the end of each quarter, to the BZSt. | § 18a Abs. 2 UStG | current | verified (2026-11-18) |
| monthly, 50 000 € | Intra-EU supplies of goods: monthly by the 25th day; quarterly allowed if not more than 50 000 € per quarter. | § 18a Abs. 1 UStG | current | verified (2026-11-18) |

## EÜR method (§ 4 Abs. 3, § 11 EStG, § 60 EStDV)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| profit | Profit = Betriebseinnahmen − Betriebsausgaben. Pass-through items (durchlaufende Posten) are excluded. | § 4 Abs. 3 S. 1–2 EStG | current | verified (2026-11-18) |
| cash basis | Income counts in the year received, expenses in the year paid. Regularly recurring items paid or received shortly before or after the turn of the year (10 days, per the EÜR guide) count in the year they belong to. Code uses `receipt_date` as the payment date; the 10-day rule is not implemented. | § 11 Abs. 1 S. 1–2, Abs. 2 S. 1–2 EStG | current | verified (2026-11-18); 10-day rule TODO |
| electronic | Anlage EÜR must be sent electronically in the official data set; paper only on hardship application. | § 60 Abs. 4 EStDV | current | verified (2026-11-18) |
| 800 € GWG | Movable assets up to 800 € net (excluding Vorsteuer) may be fully expensed in the year of purchase. | § 6 Abs. 2 S. 1 EStG | current | verified (2026-11-18) |
| 250 / 1 000 € pool | Optional Sammelposten for assets over 250 € and up to 1 000 € net, written off over 5 years. Not implemented. | § 6 Abs. 2a EStG | current | verified (2026-11-18) |
| VAT is income/expense | VAT collected (Kz 140), VAT refunded by the FA (Kz 141), Vorsteuer paid (Kz 185) and USt paid to the FA (Kz 186) are Betriebseinnahmen / -ausgaben in the year of payment. **Code excludes VAT from the profit (net method).** | EÜR-2025 Anleitung Zeile 17, 18; form lines 17, 18, 57, 58 | 2025 | code differs → EUR-2 |

## Anlage EÜR 2025 Kennzahlen (EÜR-2025 form, used by `eur.py`)

Labels shortened. Where the line number is given, it is the 2025 form line.

| value | rule | legal source | year | status |
|---|---|---|---|---|
| Kz 111 | Z. 12 Betriebseinnahmen als umsatzsteuerlicher Kleinunternehmer (§ 19 Abs. 1 UStG) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 112 | Z. 15 Umsatzsteuerpflichtige Betriebseinnahmen (ohne 0 %) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 103 | Z. 16 Umsatzsteuerfreie / nicht steuerbare Betriebseinnahmen, 0 %, § 13b | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 140 | Z. 17 Vereinnahmte Umsatzsteuer | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 141 | Z. 18 Vom Finanzamt erstattete Umsatzsteuer | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 102 | Z. 19 Veräußerung oder Entnahme von Anlagevermögen | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 106 / 108 | Z. 20 Private Kfz-Nutzung / Z. 21 sonstige Entnahmen | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 159 | Z. 23 Summe Betriebseinnahmen | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 100 | Z. 27 Waren, Rohstoffe und Hilfsstoffe | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 110 | Bezogene Fremdleistungen | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 130 / 131 / 136 | AfA bewegliche WG / immaterielle WG / Grundstücke (from Anlage AVEÜR) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 132 | Aufwendungen für GWG nach § 6 Abs. 2 EStG | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 137 | Auflösung Sammelposten § 6 Abs. 2a EStG | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 150 | Miete/Pacht für Geschäftsräume | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 151 | Sonstige Aufwendungen für betrieblich genutzte Grundstücke | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 280 | Aufwendungen für Telekommunikation | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 221 | Übernachtungs- und Reisenebenkosten bei Geschäftsreisen (meals → Z. 64, travel costs → Z. 68 ff., per Anleitung Z. 44) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 281 | Fortbildungskosten (ohne Reisekosten) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 194 | Rechts- und Steuerberatung, Buchführung | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 222 | Miete/Leasing bewegliche WG (ohne Kfz) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 223 | Beiträge, Gebühren, Abgaben, Versicherungen (ohne Gebäude/Kfz) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 228 | Laufende EDV-Kosten | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 229 | Arbeitsmittel (Bürobedarf, Porto, Fachliteratur) | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 227 | Kosten für Verpackung und Transport | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 224 | Werbekosten | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 232 / 234 | Schuldzinsen Anlagevermögen / übrige Schuldzinsen | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 185 | Gezahlte, nach § 15 UStG abziehbare Vorsteuerbeträge | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 186 | An das Finanzamt gezahlte Umsatzsteuer | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 183 | Übrige unbeschränkt abziehbare Betriebsausgaben | EÜR-2025 | 2025 | verified (2026-11-18) |
| Kz 164 / 174 | Geschenke: nicht abziehbar / abziehbar | EÜR-2025 Z. 62 | 2025 | verified (2026-11-18) |
| Kz 165 / 175 | Bewirtungsaufwendungen: nicht abziehbar / abziehbar | EÜR-2025 Z. 63 | 2025 | verified (2026-11-18) |
| Kz 171 | Verpflegungsmehraufwendungen | EÜR-2025 Z. 64 | 2025 | verified (2026-11-18) |
| Kz 144 / 145 / 146 | Kfz: Leasing / Steuern, Versicherungen, Maut / sonstige tatsächliche Fahrtkosten (repairs, fuel, flights, public transport) | EÜR-2025 Z. 68–70 | 2025 | verified (2026-11-18) |
| Kz 147 | Fahrtkosten für nicht betriebliche Fahrzeuge (Nutzungseinlage) | EÜR-2025 Z. 71 | 2025 | verified (2026-11-18) |
| Kz 176 | Mindestens abziehbare Fahrtkosten (Entfernungspauschale) | EÜR-2025 Z. 73 | 2025 | verified (2026-11-18) |
| Kz 199 | Summe Betriebsausgaben | EÜR-2025 Z. 75 | 2025 | verified (2026-11-18) |
| years ≠ 2025 | Kennzahlen can change every year. `eur.py` warns for other years. | Anlage EÜR of that year | 2026+ | TODO each year |
| category → Kz | How finamt receipt categories map to these Kennzahlen is a **classification choice**, not a legal value: see `_PURCHASE_KZ` in `eur.py`. Items that need a human decision go to `review_lines`. | EÜR-2025 Anleitung | 2025 | verified mapping targets; choices documented in code |

## ELSTER / ERiC constants (`elster.py`, `eur_elster.py`)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| Testmerker `700000004` | Marks a test submission; `eur_elster` refuses test mode without it. | ERiC developer documentation (login) | — | TODO |
| Namespace `http://www.elster.de/elsterxml/schema/v11` | Envelope namespace. | ERiC developer documentation | — | TODO |
| EÜR `datenartVersion` | Not public. `eur_elster.submit(mode="test")` requires it as an argument. | ERiC Jahresdokumentation (login) | 2025 | TODO → EUR-4 |
