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
names, XSD, `datenartVersion` strings, Testmerker, and namespace. They come from this source, read
on 2026-11-20 (kept in the git-ignored `private/` folder, never committed):

| id | document | where (inside `private/ERiC-44.3.6.0/Dokumentation/`) |
|---|---|---|
| ERiC-44.3 | ERiC 44.3.6.0 developer documentation (ELSTER developer area) | `Datenartversionmatrix.ods`; `ERiC-Entwicklerhandbuch.pdf` (Kap. 6.5 test support); `ERiC-Releasenotes.pdf`; `Datenarten/ElsterAnmeldung/UStVA/` (Jahresdokumentation, Schema, Beispiele); `Datenarten/ElsterErklaerung/EUER/` (same) |
| ERiC-44.3-run | Offline `EricBearbeiteVorgang` validation (flag `ERIC_VALIDIERE`, nothing sent) of FreiBuch-built XML with ERiC 44.3.6.0 Windows-x86_64 | run on 2026-11-20, see rows below |

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
| `Zeitraum` codes `01`–`12`, `41`–`44` | UStVA period codes: `01`–`12` monthly, `41`–`44` quarters I–IV (enumeration of field `Zeitraum`). There is no annual code in the UStVA: FreiBuch's `period=0` builds the separate annual USt return (E50, datenartVersion `USt_<year>`), whose `Zeitraum` is the year. | ERiC-44.3 `Jahresdokumentation_UStVA_2026.ods`, sheet "Felder"; ERiC-44.3-run (2025, 2026 UStVA and 2024, 2025 USt validated) | 2025–2026 | verified (2026-11-20) |

## UStVA Kennzahlen 2026 (USt1A-2026, used by `elster._ustva_kennzahlen`)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| whole euros / cents | "Tragen Sie bei den Bemessungsgrundlagen bitte nur Beträge in vollen Euro ein; bei den Umsatzsteuer- und Vorsteuerbeträgen ist dagegen stets auch die Eintragung von Centbeträgen erforderlich." Negative amounts carry a minus sign. | USt1A-2026 Anleitung, general notes | 2026 | verified (2026-11-18) |
| truncation | Code cuts off cents (`ROUND_DOWN`). The guide says "ohne Centbeträge" but does not say whether to round or truncate. Field format of Kz 81/86/35/21/46: `GeldBetragOhneCent`, sign allowed (Formatkennzeichen N); tax fields (Kz 36/47/62/66/67/83): `GeldBetragMitCent` with a decimal **point**. ERiC 44.3 has no plausibility rule that compares base and tax: a UStVA with net 1 000.99 € at 19 % sent as Kz 81 = `1000`, Kz 83 = `171.19` (with Kz 66 = `19.00`) validates without errors or hints. | USt1A-2026 Anleitung; ERiC-44.3 `Jahresdokumentation_UStVA_2026.ods` ("Felder", "Regeln"); ERiC-44.3-run | 2026 | ERiC-accepted (2026-11-20); the legal choice between rounding and truncation is still unsourced (D5); server-side check pending → UST-5 |
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
| Kz 62 | Einfuhrumsatzsteuer (§ 15 Abs. 1 S. 1 Nr. 2 UStG). Code writes `report.einfuhr_vat` here (cents, only if > 0); Kz 66 excludes it. | USt1A-2026 section F; § 15 Abs. 1 S. 1 Nr. 2 UStG | 2026 | verified (2026-11-20, UST-1) |
| Kz 67 | Input tax from § 13b services (§ 15 Abs. 1 S. 1 Nr. 4 UStG). | USt1A-2026 section F | 2026 | code differs → UST-4 |
| Kz 50 / Kz 37 | Extra memo lines only when a consideration became uncollectible (§ 17 Abs. 2 Nr. 1 UStG). Ordinary changes such as credit notes and discounts (§ 17 Abs. 1) are entered **in the base and tax lines themselves**, as negative amounts, in the period the change happens. Code: negative receipts stay on their rate line (Kz 81/86/35, and Kz 66 for purchase credit notes); Kz 50/37 are never written. | USt1A-2026 section I, Anleitung Zeilen 51–52 | 2026 | verified (2026-11-20, UST-2) |
| Kz 39 | Deduction of the fixed Sondervorauszahlung (usually only in the last Voranmeldung of the year). | USt1A-2026 Zeile 49 | 2026 | verified (2026-11-18) |
| Kz 83 | Remaining advance payment / surplus ("Bitte in jedem Fall ausfüllen"). Code always writes it, `0.00` for an empty period. | USt1A-2026 Zeile 50 | 2026 | verified (2026-11-20, UST-2) |
| `_USTVA_KZ_ORDER` | XML element order required by the UStVA XSD (`Umsatzsteuervoranmeldung` sequence). The code order equals the 2025 XSD exactly. The 2026 XSD drops `Kz23` and appends `Kz500` after `Kz98`; the code emits neither, so 2026 output is still in order. | ERiC-44.3 `Schema/2025/UStVA-2025.xsd`, `Schema/2026/UStVA-2026.xsd`; ERiC-44.3-run | 2025–2026 | verified (2026-11-20); update the tuple when YEAR-1 adds a field |
| Kz 09 | Five-digit Hersteller-ID of the software (mandatory, pattern `[0-9]{5}`), not a Finanzamt number. | ERiC-44.3 `Jahresdokumentation_UStVA_2026.ods` (rule `UStVA_Kz09_Pflichtfeld`) | 2026 | verified (2026-11-20) |
| E50 elements `E3003303`… | XML element names for the annual USt return. The current XML validates in ERiC 44.3 for 2024 and 2025; the individual element meanings are not yet checked row by row. | ERiC USt schema (developer login); USt-2026 for the paper lines; ERiC-44.3-run | 2023–2026 | TODO (ERiC-valid, meanings unchecked) |

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
| Testmerker `700000004` | Marks a test submission (defined in `ericdef.h`); ELSTER deletes test cases instead of processing them. Not allowed in a real filing. `eur_elster` refuses test mode without it. Used in the official UStVA 2026 and EÜR 2025 examples. | ERiC-44.3 `ERiC-Entwicklerhandbuch.pdf` Kap. 6.5.5; `Beispiele/UStVA_2026.xml`, `EUER_2025_ok.xml` | — | verified (2026-11-20) |
| Namespace `http://www.elster.de/elsterxml/schema/v11` | Envelope namespace (`<Elster>`, `TransferHeader version="11"`). | ERiC-44.3 examples, handbook Abb. 6-7 | — | verified (2026-11-20) |
| UStVA payload | Verfahren `ElsterAnmeldung`, DatenArt `UStVA`, datenartVersion `UStVA_<year>` (from 2016), root `Anmeldungssteuern version="<year>"` in namespace `http://finkonsens.de/elster/elsteranmeldung/ustva/v<year>`. | ERiC-44.3 `Datenartversionmatrix.ods`; `Beispiele/UStVA_2026.xml` | 2016– | verified (2026-11-20) |
| Hersteller-ID | Every software maker needs its own Hersteller-ID, for real **and** test cases. The demo ID `74931` is blocked: ERiC returns `610301202 ERIC_IO_TESTHERSTELLERID_GESPERRT` even for validation only. A placeholder such as `00000` passes local validation (`ERIC_VALIDIERE`, nothing sent; EÜR 2025, 2026-11-20); never send with it. | ERiC-44.3 handbook Kap. 6.5.3; ERiC-44.3-run | — | verified (2026-11-20) |
| Test tax numbers | Only Bayern has test tax numbers. They are valid for USt annual returns, EÜR and Anmeldungssteuern (UStVA), e.g. `198/113/10010` = ELSTER `9198011310010` (Finanzamt `9198`, Bundesland `09`). Anything sent to a test Finanzamt is deleted, even a real case. | ERiC-44.3 handbook Kap. 6.5.1, 6.5.4; `Finanzamtsdaten.ods` | — | verified (2026-11-20) |
| ERiC 44 API | `EricBearbeiteVorgang` takes 7 arguments; the transfer handle was removed. ERiC 44 libraries are not compatible with ERiC 43. | ERiC-44.3 `ERiC-Releasenotes.pdf` 5.2.6, 5.2.8; `include/ericapi.h` | ERiC 44+ | verified (2026-11-20); `eric_wrapper.py` adapted |
| EÜR `datenartVersion` | `EUER_<year>` (from 2015; new Nutzdaten structure from 2021), e.g. `EUER_2025`. Verfahren `ElsterErklaerung`, DatenArt `EUER`. | ERiC-44.3 `Datenartversionmatrix.ods`; `Beispiele/EUER_2025_ok.xml` | 2025 | verified (2026-11-20) |

## Steuernummer and Land codes (`tax/bundesland.py`, `elster.normalise_steuernummer`, `elster._bundesland_ziel`)

| value | rule | legal source | year | status |
|---|---|---|---|---|
| 13-digit ELSTER Steuernummer | ERiC converts the number "im Format des Steuerbescheides" plus a 2-digit Landesnummer (= first two digits of the Bundesfinanzamtsnummer) into the 13-digit ELSTER format (`EricMakeElsterStnr`) and checks it. `normalise_steuernummer` gives the same result as ERiC for all 16 Länder (18 Finanzämter, incl. Bayern 91/92 and NRW 51/53; run 2026-11-20, cases pinned in `tests/unit/test_bundesland.py`). Baden-Württemberg numbers are printed `FFBBB/UUUUP`; ERiC rejects `FF/BBB/UUUUP` for BW. Bayern and Berlin numbers in the short form `BBB/UUUUP` need the Finanzamtsnummer; the UI asks for the long form instead. | ERiC-44.3 `include/ericapi.h` (`EricMakeElsterStnr`, `EricPruefeSteuernummer`); ERiC-44.3-run | — | verified (2026-11-20) |
| Landesnummern | First two digits of the Bundesfinanzamtsnummer per Land: SL 10, BE 11, SH 21, HH 22, NI 23, HB 24, HE 26, RP 27, BW 28, BB 30, ST 31, SN 32, MV 40, TH 41, NW 51–53 (test Finanzämter 54–56), BY 91–92. The Finanzamtsnr. is the first four digits of the 13-digit number. | ERiC-44.3 `Finanzamtsdaten.ods` (BZSt GEMFA data of 01.09.2026) | 2026-09 | verified (2026-11-20) |
| Prüfziffer | The check digit is **not** computed by FreiBuch; ERiC checks it when a return is validated or sent (`ERIC_GLOBAL_STEUERNUMMER_UNGUELTIG`). The algorithm is in `Pruefung_der_Steuer_und_Steueridentifikatsnummer.pdf` (ELSTER developer area), not read. | `include/ericapi.h` (`EricPruefeSteuernummer`) | — | TODO: only needed for an offline check |
| two Steuernummern | Some Finanzämter give a Freiberufler one number for Umsatzsteuer and another for Einkommensteuer. FreiBuch stores both (`tax_number` = USt, used for UStVA and the annual USt; `tax_number_est` = ESt). The Anlage EÜR carries exactly one number (`Vorsatz/StNr`); ERiC rule 600031 mentions a separate "Betriebssteuernummer" for an EÜR, and `E6000026` (Leitsteuernummer) is only for a new case without a number. **Which of the two numbers the EÜR is filed under is not sourced**: the EÜR-2025 Anleitung could not be read on 2026-11-20 (bundesfinanzministerium.de returned HTTP 503). Until then the owner chooses it in Stammdaten (`euer_steuernummer`), with no default. | ERiC-44.3 `Jahresdokumentation_E77_2025.ods` ("Vorsatz - Felder", "EUER - Felder" E6000026, "EUER - Regeln" 600011, 600031); EÜR-2025 (not read) | 2025 | TODO: read the EÜR-2025 Anleitung (header / Zeile 1–6) or ask the Finanzamt; then set a default or keep the choice |
| `<Ziel>` | The TransferHeader `<Ziel>` must be a `BundeslandSType` code: BB, BE, BW, BY, HB, HE, HH, MV, NI, NW, RP, SH, SL, SN, ST, TH. `_bundesland_ziel` maps the Länderschlüssel 01–16 **and** the 13-digit prefixes (5, 9, 21–41) the pre-built UI sends; before 2026-11-20 a prefix such as `9` was written as `<Ziel>9</Ziel>`. | ERiC-44.3 `ElsterBasisSchema/Schema/headerbasis_datentypen.xsd`, `th000011_extern.xsd` | — | verified (2026-11-20) |

## Anlage EÜR 2025 XML (datenartVersion `EUER_2025`, for EUR-4)

Facts for the EÜR ELSTER builder (EUR-4). Names and formats only; the XSD and documentation stay in
`private/`. Source: ERiC-44.3 `Datenarten/ElsterErklaerung/EUER/Jahresdokumentation/Jahresdokumentation_E77_2025.ods`
(sheets "Allg. Information", "EUER - Felder", "EUER - Kennzahlen", "EUER - Regeln"),
`Schema/2025/E77-2025.xsd`, `Beispiele/EUER_2025_ok.xml`. All rows verified (2026-11-20); the official
example validates offline in ERiC 44.3 (ERiC-44.3-run).

| value | rule |
|---|---|
| payload root | `<E77 xmlns="http://finkonsens.de/elster/elstererklaerung/euer/e77/v2025" version="2025">` inside `Nutzdaten`. Children: `EUER` (the form; mandatory), optional `AVEUER`, `SZ`, `SE`, `AVSE`, `ER`, `LuF`, then `Vorsatz` (mandatory). |
| `Vorsatz` | `Unterfallart` = `77`, `Vorgang` = `01`, `StNr` (13 digits, pattern `[0-9]{4}0[0-9]{8}`), `Zeitraum` (year), `AbsName` (max 45), `AbsStr` (max 30), `AbsPlz` (5 digits), `AbsOrt` (max 29), `Copyright` (max 50), `OrdNrArt` = `S`, `Rueckuebermittlung/Bescheid`, in this order. `Bescheid` is **mandatory** (rule 10438) and must be `2` = no: the EÜR cannot request a notice (rule 600044). |
| `NutzdatenHeader` | `Empfaenger id="F"` = the 4-digit Finanzamt number (first 4 digits of `StNr`). |
| decimal separator | **comma** (`10,00`), unlike the UStVA (decimal point). |
| format `P` | amount with 2 decimals, sign allowed, 0 allowed. |
| format `%` | amount with 2 decimals, no sign, 0 allowed. |
| `EUER/Allg` | `E6000016` name, `E6000023` street, `E6000024` PLZ, `E6000025` Ort, `E6000026` StNr, `E6000017` Art des Betriebs, `E6000602` Rechtsform, `E6000603` Einkunftsart, `E6000604`, `E6000019` (see example and "EUER - Felder" for the code lists). |
| Anlage AVEÜR | Not always required, but ERiC raises **errors** (e.g. rules 606840, 606846, 606847, 607901, 607902) when AfA lines Kz 130/131/136 are filled without the matching AVEÜR totals, or the values differ. When EUR-3 produces AfA, EUR-4 must also send `AVEUER`. |

| Kz | element path under `EUER/` | format | form line |
|---|---|---|---|
| 111 | `BEin/Kleinunternehmer/Sum/E6000101` | P | 12 |
| 112 | `BEin/USt_StPflicht/Sum/E6000401` | P | 15 |
| 103 | `BEin/USt_StFrei/Sum/E6000501` | P | 16 |
| 140 | `BEin/USt_Vereinnahmt_Unentgeltl/Sum/E6000601` | P | 17 |
| 141 | `BEin/USt_Erstattet_Verrechnet/Sum/E6000701` | % | 18 |
| 102 | `BEin/Anlagevermoegen/Sum/E6000801` | P | 19 |
| 106 | `BEin/Nutzung_Priv_Kfz/Sum/E6000901` | % | 20 |
| 108 | `BEin/Entnahme_Sonst/Sum/E6001001` | % | 21 |
| 159 | `BEin/GesamtSum/E6001201` | P | 23 |
| 100 | `BAus/Ware_Rohstoff_Hilfsstoff/Sum/E6001601` | P | 27 |
| 110 | `BAus/Fremdleistung/Sum/E6001701` | P | 29 |
| 136 | `BAus/AfA/E6001901` | % | 31 |
| 131 | `BAus/AfA/E6002001` | % | 32 |
| 130 | `BAus/AfA/E6002101` | P | 33 |
| 132 | `BAus/AfA/Wirtschaftsgut_geringwertig/Sum/E6002301` | % | 36 |
| 137 | `BAus/AfA/Weitere_Angabe/E6003302` | % | 37 |
| 150 | `BAus/Raumkosten_u_sonst/Miete_Pacht/Sum/E6003201` | P | 39 |
| 151 | `BAus/Raumkosten_u_sonst/Sonst_Aufw_betr_Grund/Sum/E6003301` | P | 41 |
| 280 | `BAus/Sonst_unbeschraenkt/Kommunikation/Sum/E6003901` | P | 43 |
| 221 | `BAus/Sonst_unbeschraenkt/Auswertstaetigkeit/Sum/E6004004` | P | 44 |
| 281 | `BAus/Sonst_unbeschraenkt/Fortbildung/Sum/E6004003` | P | 45 |
| 194 | `BAus/Sonst_unbeschraenkt/Rechtsberatung_StB_Buchf/Sum/E6004801` | P | 46 |
| 222 | `BAus/Sonst_unbeschraenkt/Miete_Leasing_bewegl_WG/Sum/E6004304` | P | 47 |
| 223 | `BAus/Sonst_unbeschraenkt/Beitrag_Gebuehr_Abgabe_Versicherung/Sum/E6004402` | P | 49 |
| 228 | `BAus/Sonst_unbeschraenkt/EDV/Sum/E6004405` | P | 50 |
| 229 | `BAus/Sonst_unbeschraenkt/Arbeitsmittel/Sum/E6004408` | P | 51 |
| 227 | `BAus/Sonst_unbeschraenkt/Verpackung_Transport/Sum/E6004414` | P | 53 |
| 224 | `BAus/Sonst_unbeschraenkt/Werbung/Sum/E6004501` | P | 54 |
| 232 | `BAus/Sonst_unbeschraenkt/Schuldzins_AnlageVerm/Sum/E6004202` | P | 55 |
| 234 | `BAus/Sonst_unbeschraenkt/Schuldzins_Uebrige/Sum/E6004303` | P | 56 |
| 185 | `BAus/Sonst_unbeschraenkt/Vorsteuer/Sum/E6005001` | P | 57 |
| 186 | `BAus/Sonst_unbeschraenkt/USt/Sum/E6005101` | % | 58 |
| 183 | `BAus/Sonst_unbeschraenkt/Sonst_unbeschr_abziehbar/Sum/E6004901` | P | 60 |
| 164 | `BAus/Beschr_abziehbar/Nicht_abziehbar/Geschenke/Sum/E6004001` | % | 62 |
| 174 | `BAus/Beschr_abziehbar/Abziehbar/Geschenke/Sum/E6004002` | P | 62 |
| 165 | `BAus/Beschr_abziehbar/Nicht_abziehbar/Bewirtung/Sum/E6004101` | % | 63 |
| 175 | `BAus/Beschr_abziehbar/Abziehbar/Bewirtung/Sum/E6004102` | P | 63 |
| 171 | `BAus/Beschr_abziehbar/Abziehbar/Verpflegung/Sum/E6005002` | % | 64 |
| 144 | `BAus/KFZ_u_Fahrtkosten/Leasing/Sum/E6005801` | P | 68 |
| 145 | `BAus/KFZ_u_Fahrtkosten/Steuer_Versicherung_Maut/Sum/E6005903` | P | 69 |
| 146 | `BAus/KFZ_u_Fahrtkosten/Sonst/Sum/E6006003` | P | 70 |
| 147 | `BAus/KFZ_u_Fahrtkosten/Fahrtkosten_Nutzungseinlage/Sum/E6006103` | % | 71 |
| 176 | `BAus/KFZ_u_Fahrtkosten/Entfernungspausch_Familienheimfahrt/Sum/E6003702` | % | 73 |
| 199 | `BAus/Summe_BAus/E6005301` | P | 75 |

Each `…/Sum` context also has `…/Einz` siblings (up to 99 single entries) in the XSD; the example
sends only `Sum`. Element **order** inside each context follows `E77-2025.xsd`; the table above is in
that order (checked by walking the XSD, 2026-11-20). `eur_elster.py` emits only `Sum`.

### Anlage EÜR 2025: lines and rules used by `eur_elster.build_xml` (EUR-4)

Source as above, plus ERiC-44.3-run: XML built by `build_xml` validates against
`elster11_E77_2025_extern.xsd` and in ERiC 44.3.6.0 (`ERIC_VALIDIERE`, nothing sent, placeholder
Hersteller-ID) for income-only, loss, empty and 33-Kennzahl reports, 2026-11-20. "Rule" = ERiC
rule number in sheet "EUER - Regeln"; all are of type *Fehler* (error) unless stated.

| value | rule / element | form line | source | status |
|---|---|---|---|---|
| `Allg` (mandatory fields) | `E6000016` name (rule 600035), `E6000017` Art des Betriebs, max 25 (600010), `E6000602` Rechtsform (600065), `E6000603` Einkunftsart (600078), `E6000604` Betriebsinhaber (600079), `E6000019` Grundstücke entnommen/veräußert (`1` ja, `2` nein). Optional and not sent: `E6000011` Vorname, `E6000404` W-IdNr., `E6000026` Leitsteuernummer (only needed for a new case without StNr, rule 600011), `E6000502` Betrieb beendet. | 1–11 | "EUER - Felder", "EUER - Regeln" | verified (2026-11-20) |
| Rechtsform codes for one person | Code list `RECHTSFORM_EUER_V2_TID`: `110`, `120`, `130`, **`140` Angehörige(r) der freien Berufe**, `150`, `160`, `190`. Einkunftsart `3` = Selbständige Arbeit (`2` Gewerbebetrieb). Betriebsinhaber `1` = steuerpflichtige Person; any other value gives hint 600031. | 7–9 | "Benutzerdefinierte Typen"; `E77-2025.xsd` enumerations | verified (2026-11-20) |
| Kz 159 total | `E6001201` = sum of all Betriebseinnahmen lines (rule 600271). | 23 | rule 600271 | verified (2026-11-20) |
| Kz 199 total | `E6005301` = sum of the Betriebsausgaben lines (rule 600614). **Kz 164 and Kz 165** (non-deductible gifts / entertainment, left column of lines 62/63) are **not** part of it. | 75 | rule 600614 | verified (2026-11-20) |
| Zeile 76 / 77 | `Ermittlung_Gewinn/Uebertrag/E6005501` = Kz 159 (rules 604029/604030), `…/E6005601` = Kz 199 (604039/604040). Format P. | 76, 77 | "EUER - Felder"; rules | verified (2026-11-20) |
| Zeile 92 | `Ermittlung_Gewinn/Korrektur_GuV/E6006801` "Korrigierter Gewinn/Verlust", mandatory for non-corporations (600640). Equals line 76 − 77 when lines 78–91 are empty (600648). Format P. | 92 | rules 600640, 600648 | verified (2026-11-20) |
| Zeile 95, Kz 293 | `Ermittlung_Gewinn/Stpfl_GuV/E6007002`, mandatory (600641), = line 92 + the correction amounts of lines 93/94 (600644). Format P. | 95 | "EUER - Kennzahlen"; rules | verified (2026-11-20) |
| Zeile 96, Kz 271 | `…/Stpfl_GuV/E6007102` Hinzurechnung § 4 Abs. 4a EStG (format %). Not sent by `build_xml` (only relevant with Schuldzinsen above 2 050 €, which it refuses). | 96 | as above | verified (2026-11-20) |
| Zeile 97, Kz 219 | `…/Stpfl_GuV/E6007202` "Steuerpflichtiger Gewinn/Verlust", mandatory (600642), = line 95 + line 96 (600645). Format P. | 97 | as above | verified (2026-11-20) |
| Zeilen 106 / 107, Kz 122 / 123 | `Zus_Angabe_EinzelUntern/Entnahme_Einlage/Entnahme/Sum/E6006601` (Entnahmen incl. Sach-, Leistungs- und Nutzungsentnahmen) and `…/Einlage/Sum/E6006701` (Einlagen). Format %. For Rechtsform group TID **both are mandatory** (600904, "zwingend einzutragen (§ 4 Absatz 4a Satz 6 EStG)"); `0,00` is accepted. Einlagen must not be lower than Kz 147 (600903). Not derived from receipts: `build_xml` takes them as arguments. | 106, 107 | rules 600903, 600904; ERiC-44.3-run | verified (2026-11-20) |
| Kz 153 (Zeile 42) | `BAus/Raumkosten_u_sonst/Davon_Erhalt_Grundstueck/Sum/E6004015` "in Zeile 41 enthaltene Erhaltungsaufwendungen". Lines 41 (Kz 151) and 42 must be sent **together** (600522). The report has no such split, so `build_xml` refuses Kz 151. | 42 | rule 600522; ERiC-44.3-run | verified (2026-11-20); code: EUR-7 |
| Kz 112 needs Kz 140 | Taxable income (Kz 112, `E6000401`) ≠ 0 without the collected-VAT line (Kz 140, `E6000601`) is an error (600240). `build_xml` refuses it until EUR-2 adds the VAT lines. | 15, 17 | rule 600240; ERiC-44.3-run | verified (2026-11-20) |
| Schuldzinsen limit `2050.00` | For sole proprietors, Kz 234 (`E6004303`) above 2 050,00 € requires Anlage SZ (600068) and Entnahmen ≥ Kz 106 + 108 (600902). `build_xml` refuses it (`SCHULDZINSEN_LIMIT`). | 56 | rules 600068, 600902 | verified (2026-11-20) |
| Kz 132 (GWG) without AVEÜR | Kz 132 alone (no AfA lines, no `AVEUER`) passes ERiC 44.3 validation; no EÜR or AVEÜR rule ties it to Anlage AVEÜR. `build_xml` still refuses Kz 132 until EUR-3 is decided. | 36 | ERiC-44.3-run (2026-11-20); "AVEUER - Regeln" | verified (2026-11-20) |
| Copyright text | `Vorsatz/Copyright` is the software maker's notice; FreiBuch sends `(c) FreiBuch contributors, AGPL-3.0`. | — | "Vorsatz - Felder" | verified (2026-11-20) |
| `NutzdatenTicket` | 1–32 characters, unique per delivery; with one Nutzdatenblock the schema suggests "1". FreiBuch sends `1`. `TransferTicket` is left out (optional). | — | `ElsterBasisSchema/Schema/headerbasis_datentypen.xsd`, `th000011_extern.xsd` | verified (2026-11-20) |
| server acceptance | One `submit(mode="test")` with the owner's Hersteller-ID and certificate (`scripts/eur_test_submission.py --send`). | — | — | TODO → EUR-6 (owner, MANUAL-STEPS M2) |
