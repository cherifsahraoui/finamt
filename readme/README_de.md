# FreiBuch

Ein freies, lokales Open-Source-Werkzeug, mit dem **ein deutscher Freiberufler** Umsatzsteuer und
EÜR selbst erledigt, ohne ein bezahltes Buchhaltungs-Abo wie Accountable:

**Belege rein → UStVA → Umsatzsteuererklärung → EÜR → ELSTER**

Alles läuft auf dem eigenen Rechner. Belege, Datenbank und ELSTER-Zertifikat verlassen ihn nie,
außer bei der ELSTER-Übermittlung selbst.

> FreiBuch ist ein Fork von [spaceoctahedron/finamt](https://github.com/spaceoctahedron/finamt)
> (AGPL-3.0), zugeschnitten auf Freiberufler. Was geändert wurde, steht in [NOTICE.md](../NOTICE.md).
> Python-Paket, CLI-Befehl `finamt`, Datenordner `~/.finamt/` und die `FINAMT_*`-Einstellungen
> heißen vorerst noch wie im Original; die Befehle unten lauten deshalb `finamt`.
> Keine Steuerberatung; siehe [Haftungsausschluss](#haftungsausschluss).

## Was es heute kann

| Aufgabe | Stand | Wie |
|---|---|---|
| Belege und Rechnungen (PDF/Scan) mit OCR + lokalem LLM lesen | ✅ funktioniert | `finamt process`, `finamt batch`, Web-UI |
| Belege speichern, Duplikate erkennen, kategorisieren | ✅ funktioniert | lokale SQLite in `~/.finamt/<projekt>/` |
| UStVA berechnen (vierteljährlich) | ✅ funktioniert | `finamt ustva --quarter Q --year Y` |
| UStVA berechnen (monatlich) | ✅ funktioniert | `finamt ustva --month M --year Y` |
| Monatlich oder vierteljährlich? (§ 18 Abs. 2 UStG) | ✅ Hinweis aus der Vorjahressteuer | `finamt ustva --suggest-period --year Y` |
| UStVA / Umsatzsteuererklärung über ELSTER (ERiC) **übermitteln** | ✅ von ERiC 44.3 geprüft; Testmodus; Echtbetrieb nur mit ausdrücklichem Schalter ([M2](../docs/MANUAL-STEPS.md#m2-first-test-submission), [M4](../docs/MANUAL-STEPS.md#m4-file-for-real)) | Web-UI `/app/ustva` (`finamt serve`) oder API |
| EÜR mit den Kennzahlen der Anlage EÜR 2025 | ✅ funktioniert, mit USt-Zeilen (Kz 140/141/185/186) | `finamt eur --year Y`, Web-UI `/app/euer` |
| EÜR über ELSTER übermitteln | 🧪 ERiC-Prüfung, XML-Download und Testversand; Echtbetrieb abgeschaltet (D3); ein Testversand durch den Eigentümer fehlt noch (EUR-6) | Web-UI `/app/euer`, `finamt eur --validate / --xml` |
| Amtliches PDF (ERiC-Druck) von UStVA, USt-Erklärung und EÜR | ✅ Vorschau vor dem Senden; Kopie nach dem Senden im Archiv (PRINT-1) | Web-UI „Druckansicht (PDF)“, `finamt eur --pdf` |
| Gutschriften in der UStVA (negative Bemessungsgrundlage und Steuer) | ✅ funktioniert (UST-2) | — |
| 0 %, steuerfreie und Reverse-Charge-Belege in der UStVA (Kz 87, 48, 21, 45, 60, 46/47, 84/85, 67) | ✅ UStVA und EÜR (UST-3, UST-4); die USt-Erklärung lehnt sie vorerst ab | Belegformular „USt-Behandlung“ |
| Rechnungen schreiben (§ 14 UStG), lückenlose Nummern, PDF, Storno | ✅ funktioniert (INV-1) | Web-UI `/app/rechnungen`, `finamt invoice new --file F.json` |
| Zusammenfassende Meldung für EU-Kunden | 🧮 nur Berechnung (ZM-1); noch kein Versand | `finamt.tax.generate_zm` |
| Kleinunternehmer (§ 19 UStG) | ✅ EÜR und Rechnungen; Jahre in den Stammdaten (EUR-8) | Web-UI, `finamt eur --kleinunternehmer` |

Nicht enthalten: KSt, GewSt, E-Bilanz, Jahresabschluss, Einkommensteuer. Der Original-Code dafür
liegt in [`legacy/`](../legacy/README.md) und wird nicht installiert.

## Fahrplan

Die Arbeit ist in kleine Aufgaben aufgeteilt, die ein KI-Agent (oder ein Mensch) einzeln
übernehmen kann. Die vollständige Liste mit Schritten und Tests steht in
**[docs/TODO.md](../docs/TODO.md)**. Als Nächstes:

1. **EUR-6 / EUR-7**: EÜR-Testversand durch den Eigentümer; Kz 151 braucht die Aufteilung nach Zeile 42

Grundsatzentscheidungen (CLI zuerst, kein Echtversand per Voreinstellung, …) stehen in
[docs/DECISIONS.md](../docs/DECISIONS.md).

## Installation

Python 3.10–3.13. Aus dem Quellcode:

```bash
git clone https://github.com/cherifsahraoui/FreiBuch.git
cd FreiBuch
uv sync --extra dev          # oder: python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
uv run finamt --help
```

Beim ersten Einsatz werden OCR- und LLM-Modelle von HuggingFace geladen und in
`~/.cache/huggingface/hub` zwischengespeichert. Tesseract ist ein optionaler OCR-Ersatz:
`sudo apt-get install tesseract-ocr tesseract-ocr-deu` oder `brew install tesseract tesseract-lang`.

### Windows mit einer NVIDIA-GPU der GTX-10-Serie

Das normale PyTorch-Paket für Windows kann CPU-only sein. Auf Pascal-GPUs wie der GTX 1070/1070 Ti
nach dem Einrichten des Projekts den CUDA-12.6-Build von PyTorch und `bitsandbytes` installieren:

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install --upgrade "torch==2.7.1" --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install "bitsandbytes>=0.43.0"
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU fallback')"
```

Die Prüfung sollte `True` und den GPU-Namen ausgeben. Beide Installationen nach einem späteren
`uv sync` wiederholen, denn er kann den CPU-only-Build zurückholen und `bitsandbytes` entfernen.

## Ein Jahr mit FreiBuch

1. **Belege sammeln.** Eingangsrechnungen (`--type purchase`) und eigene Ausgangsrechnungen
   (`--type sale`) in einen Ordner legen und einlesen:
   ```bash
   finamt batch --input-dir ~/belege/2025-q1 --type purchase
   finamt batch --input-dir ~/rechnungen/2025-q1 --type sale
   ```
   Oder in der Web-UI: `finamt serve`, dann hochladen, prüfen und korrigieren.
2. **UStVA** jedes Quartal (oder jeden Monat, wenn die Vorjahressteuer über 9 000 € lag,
   § 18 Abs. 2 UStG), fällig am 10. Tag nach Ablauf des Zeitraums:
   ```bash
   finamt ustva --suggest-period --year 2025          # monatlich oder vierteljährlich?
   finamt ustva --quarter 1 --year 2025 --output ustva_q1_2025.json
   finamt ustva --month 3 --year 2025                 # Monatszahler
   ```
   Zuerst aus der Web-UI im **Testmodus** senden. Für die echte Abgabe
   [M4](../docs/MANUAL-STEPS.md#m4-file-for-real) folgen (Echtbetrieb braucht
   `FINAMT_ALLOW_LIVE_SUBMISSION=1`).
3. **Umsatzsteuererklärung** aus der Web-UI.
4. **EÜR** für das Jahr (Kennzahlen der Anlage EÜR 2025 plus die Liste „ZU PRÜFEN“):
   ```bash
   finamt eur --year 2025 --output eur_2025.json      # mit --kleinunternehmer bei § 19 UStG
   ```
   Der Befehl endet mit Code 1, solange noch etwas unter ZU PRÜFEN steht.
5. **Rechnungen** in der Web-UI (Rechnungen) oder per CLI; die nächste Nummer (`2025-0001`, …)
   wird beim Anlegen vergeben, das PDF als Einnahme-Beleg gespeichert:
   ```bash
   finamt invoice new --file rechnung.json   # Kunde, Daten, Positionen; Absender aus den Stammdaten
   finamt invoice list --year 2025
   finamt invoice cancel 2025-0001            # Rechnungskorrektur mit eigener Nummer
   ```
   Was FreiBuch nicht sicher einordnen kann (Anlagegüter über 800 €, Bewirtung, Geschenke, Spenden,
   Steuerzahlungen, Einlagen/Entnahmen), steht unter **ZU PRÜFEN** und zählt *nicht*, bis du
   entscheidest. Solange die EÜR nicht übermittelt werden kann, die Kennzahlen von Hand in ELSTER
   übertragen.

## Kategorien und EÜR-Zeilen

Jeder Beleg hat eine Kategorie und optional eine Unterkategorie. Bei Ausgaben bestimmen sie die
Zeile (Kennzahl) der Anlage EÜR 2025. Die Werte sind in [docs/tax-rules.md](../docs/tax-rules.md)
mit Quelle belegt.

| Kategorie | Unterkategorien | EÜR-Kz (Ausgabe) |
|---|---|---|
| `services` | `freelance` `consulting` `legal` `accounting` `notary` | 110 Fremdleistungen; legal/accounting/notary → 194 |
| `products` | `physical_goods` `digital_goods` `merchandise` `samples` | 100 |
| `material` | `consumables` `raw_materials` `packaging` `merchandise` | 100; consumables → 229; packaging → 227 |
| `equipment` | `low_value_asset` `computer` `machinery` `furniture` `tools` | 132 GWG bis 800 € netto; darüber → Prüfung (AfA) |
| `software` | `subscriptions` `pay_as_you_go` `licenses` `hosting` `domains` | 228 EDV-Kosten |
| `licensing` | `software_licenses` `media_licenses` `other_ip` | 183 |
| `telecommunication` | `phone` `internet` `bundled` | 280 |
| `travel` | `transport` `accommodation` `meals` `per_diem` `incidental` | 221; transport → 146; meals/per_diem → Prüfung |
| `car` | `fuel` `parking` `garage` `repair` `maintenance` `insurance` `leasing` `rental` | 146; leasing → 144; insurance → 145 |
| `education` | `courses` `books` `conferences` `certifications` | 281; books → 229 |
| `utilities` | `electricity` `heating` `water` `waste` | 151 |
| `insurance` | `liability` `health` `vehicle` `property` | 223; vehicle → 145; property → 151; health → Prüfung |
| `financial` | `bank_fees` `interest` `loan_costs` `payment_fees` | 183; interest/loan_costs → 234 |
| `office` | `rent` `coworking` `storage` `cleaning` `security` | 150; cleaning/security → 151 |
| `marketing` | `advertising` `print_media` `trade_fairs` `sponsorship` `gifts` | 224; gifts → Prüfung |
| `donations` | `charitable` `political` `church` | Prüfung |
| `public_fees` | `broadcasting_fee` `ihk_hwk` `berufsgenossenschaft` `other_public_fee` | 223 |
| `tax_settlement` | `vat_refund` `vat_payment` `income_tax` `trade_tax` `other_tax` | `vat_payment` → Kz 186, `vat_refund` → Kz 141; andere Steuern: Prüfung |
| `capital_movement` | `owner_equity` `shareholder_loan` `withdrawal` | Prüfung (keine Betriebseinnahme/-ausgabe) |
| `other` | `membership_fees` `sundry` | 183; membership_fees → 223 |

Einnahmen: steuerpflichtig → Kz 112, 0 % / steuerfrei → Kz 103, Verkauf von Anlagegütern → Kz 102.

## Sicherheit

- **Kein Echtversand per Voreinstellung.** Alles rechtlich Verbindliche an ELSTER braucht
  `FINAMT_ALLOW_LIVE_SUBMISSION=1` in der eigenen Umgebung. Testübermittlungen (Testmerker) und
  Prüfungen gehen immer. Der Echtversand der EÜR ist vorerst ganz abgeschaltet.
- **Geheimnisse bleiben lokal.** Zertifikate (`.pfx`), `.env`, Datenbanken, ERiC-Bibliotheken und
  Modelldateien sind von git ausgeschlossen. Echte Werte nur in `.env` eintragen (Vorlage:
  [.env.example](../.env.example)).
- **Nur belegte Zahlen.** Jeder Steuersatz, Schwellenwert und jede Kennzahl im Code steht mit
  amtlicher Quelle in [docs/tax-rules.md](../docs/tax-rules.md). Unbelegtes ist als `TODO` markiert.

## ELSTER-Einrichtung und andere Handarbeit

Manche Schritte brauchen dich (ELSTER-Entwicklerzugang, Zertifikat oder eine Entscheidung). Sie
stehen Schritt für Schritt in **[docs/MANUAL-STEPS.md](../docs/MANUAL-STEPS.md)**:

| Schritt | Was |
|---|---|
| M1 | Hersteller-ID und Zertifikats-PIN in `.env` eintragen |
| M2 | Erste Testübermittlung (`scripts/ustva_test_submission.py`) |
| M3 | Entscheiden, wie Anlagegüter über 800 € abgeschrieben werden |
| M4 | Echt abgeben (live), mit Checkliste |
| M5 | Jährliches Update: neues ERiC, Dokumentation und Formulare nach `private/` laden |
| M6 | Optional: beim Original-Projekt nach dem Quellcode der Web-UI fragen |

ERiC selbst gehört in den von git ausgeschlossenen Ordner `private/`. Den **Windows-x86-64**-Build
mit dem 64-Bit-Python aus `.venv` verwenden, und ERiC **44 oder neuer** (die API von ERiC 43 wird
nicht mehr unterstützt). Der Pfad zur ERiC-Bibliothek steht in `ERIC_LIBRARY_PATH`.

## Zur Web-UI

`finamt serve` öffnet **FreiBuchs eigene Oberfläche** unter `http://127.0.0.1:8000/` (sie liegt unter
`/app`, [Entscheidung D2](../docs/DECISIONS.md)); standardmäßig Deutsch, Englisch über den
DE/EN-Schalter in der Seitenleiste:

- **Übersicht**: nächste UStVA-Frist, zu prüfende Belege.
- **Belege**: Hochladen (wird im Hintergrund gelesen; der Fortschritt bleibt auf jeder Seite
  sichtbar, ein zweiter Upload wartet, bis der erste fertig ist), Erfassung ohne Datei, Bearbeiten,
  Löschen, EÜR-Zeile je Beleg.
- **UStVA** und Umsatzsteuererklärung: Kennzahlen, ERiC-Prüfung, Testversand, XML-Download; Echtversand
  nur mit `FINAMT_ALLOW_LIVE_SUBMISSION=1`.
- **EÜR** mit der Liste „zu prüfen“; **Rechnungen** (anlegen, PDF, stornieren); **Partner**
  (umbenennen, bestätigen, zusammenführen); **Archiv** (abgegebene Erklärungen, eigene Kopie,
  Bescheid); **Projekte**.
- **Stammdaten**: Bundesland-Auswahl, die die 13-stellige ELSTER-Steuernummer bildet,
  Voranmeldungszeitraum, Kleinunternehmer-Jahre, ELSTER-Zertifikat.

Serverseitig gerendert, ohne Build-Schritt (`src/finamt/ui/web/`). Die Oberfläche des Originals (ein
kompiliertes Bundle ohne veröffentlichten Quellcode) bleibt für ein Release unter `/legacy-ui`
erreichbar; beide lesen und schreiben dieselben Daten.

## Für Mitwirkende und KI-Agenten

Zuerst **[AGENTS.md](../AGENTS.md)** lesen: Befehle, feste Regeln und die Definition of Done. Dann die
erste `ready`-Karte in [docs/TODO.md](../docs/TODO.md) nehmen. Code-Übersicht:
[docs/BASELINE.md](../docs/BASELINE.md).

```bash
uv run pytest                          # offline: kein LLM, OCR-Modell, ERiC oder Netzwerk
uv run ruff check src tests
uv run ruff format --check src tests
```

## Wie Belege gelesen werden

OCR (Textebene über PyMuPDF, PaddleOCR, Tesseract als Ersatz), danach vier kleine lokale LLM-Agenten:

| Agent | Liest aus |
|---|---|
| 1 | Belegnummer, Datum, Kategorie |
| 2 | Geschäftspartner (Name, USt-IdNr, Steuernummer, Adresse) |
| 3 | Gesamtbetrag, USt-Satz, USt-Betrag |
| 4 | Positionen |

Modelle: `mistral:7b` (Standard) oder `qwen2.5:7b-instruct-q4_K_M`, über mlx-lm auf Apple Silicon,
sonst über transformers. Einstellungen in `.env` (`FINAMT_AGENT_*`, `FINAMT_OCR_*`).

## Lizenz und Dank

AGPL-3.0, siehe [LICENSE](../LICENSE). Basiert auf finamt von Yauheniya Varabyova / Space Octahedron
GmbH ([Original](https://github.com/spaceoctahedron/finamt)); die Änderungen dieses Forks stehen in
[NOTICE.md](../NOTICE.md). Fremdkomponenten: PaddleOCR, Tesseract, HuggingFace transformers
(Apache-2.0), mlx-lm (MIT). LLM-Modelle werden beim ersten Einsatz geladen und unterliegen eigenen
Lizenzen. Die ELSTER-Bibliothek ERiC wird nicht mit diesem Projekt verteilt.

## Haftungsausschluss

Diese Software hilft, Umsatzsteuer- und EÜR-Daten vorzubereiten. Sie ist **keine Steuer-, Rechts-
oder Buchhaltungsberatung**. OCR und LLM können sich irren, und Kennzahlen ändern sich jedes Jahr.
Jede Zahl vor der Abgabe beim Finanzamt prüfen; verbindliche Auskunft gibt ein Steuerberater. Die
Autoren haften nicht für fehlerhafte Erklärungen.
