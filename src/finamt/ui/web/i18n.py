"""
Language toggle for the ``/app`` UI (German default, English optional).

Templates call ``_("German text", **args)``: the German text is the key; in English mode it is
looked up in :data:`EN`, otherwise (or when missing) the German text is used. ``args`` fill
``{name}`` placeholders after translation.

Deliberately **not** translated: official form wording that the user files in German —
Anlage EÜR line labels and review reasons from ``finamt.tax.eur``, receipt category keys, and
messages computed with dynamic parts deep in the tax code (they fall back to German).
"""

from __future__ import annotations

from collections.abc import Callable

COOKIE = "freibuch_lang"
DEFAULT = "de"
#: (code, name in its own language)
SPRACHEN: tuple[tuple[str, str], ...] = (("de", "Deutsch"), ("en", "English"))
CODES = frozenset(code for code, _name in SPRACHEN)

MONATE_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip

EN: dict[str, str] = {
    # navigation and layout
    "Hauptnavigation": "Main navigation",
    "Projekt": "Project",
    "Wechseln": "Switch",
    "Sprache": "Language",
    "Alte Oberfläche:": "Old interface:",
    "Übersicht": "Overview",
    "Belege": "Receipts",
    "UStVA": "VAT return (UStVA)",
    "EÜR": "EÜR (profit)",
    "Rechnungen": "Invoices",
    "Stammdaten": "Settings",
    # shared words
    "Art": "Type",
    "Datum": "Date",
    "Kategorie": "Category",
    "Unterkategorie": "Subcategory",
    "Rechnungsnummer": "Invoice number",
    "Brutto (€)": "Gross (€)",
    "USt-Satz (%)": "VAT rate (%)",
    "USt (€)": "VAT (€)",
    "Einfuhrumsatzsteuer (€)": "Import VAT (€)",
    "Privatanteil (%)": "Private share (%)",
    "Notiz": "Note",
    "Jahr": "Year",
    "Zeitraum": "Period",
    "ganzes Jahr": "whole year",
    "alle": "all",
    "Netto": "Net",
    "USt": "VAT",
    "Brutto": "Gross",
    "Hinweise": "Notes",
    "Speichern": "Save",
    "Gespeichert.": "Saved.",
    "gespeichert": "saved",
    "Anzeigen": "Show",
    "Filtern": "Filter",
    "Summe": "Total",
    "Grund": "Reason",
    "Finanzamt": "Tax office",
    "Ausgabe": "Expense",
    "Einnahme": "Income",
    "ZU PRÜFEN": "TO REVIEW",
    "Zu prüfen": "To review",
    "{n} Beleg(e)": "{n} receipt(s)",
    "Stammdaten öffnen": "Open settings",
    "Ändert den Namen bei allen Belegen dieses Partners.": (
        "Renames the partner on all of their receipts."
    ),
    "leer = aus Satz berechnen": "empty = computed from the rate",
    # receipts list
    "Belege hochladen": "Upload receipts",
    "Ausgabe (Eingangsrechnung)": "Expense (incoming invoice)",
    "Einnahme (Ausgangsrechnung)": "Income (outgoing invoice)",
    "Hochladen und auslesen": "Upload and read",
    "Dateien werden übertragen …": "Transferring files …",
    "Gesperrt, bis der laufende Upload fertig ist.": (
        "Locked until the running upload has finished."
    ),
    "nur zu prüfen": "only to review",
    "EÜR-Zeile": "EÜR line",
    "Keine Belege für diese Auswahl.": "No receipts for this selection.",
    "Beleg gelöscht.": "Receipt deleted.",
    "Beleg angelegt.": "Receipt added.",
    "Beleg manuell erfassen": "Add a receipt manually",
    "Ohne Datei, z. B. für Kleinbeträge oder Belege, die nur auf Papier vorliegen.": (
        "Without a file, e.g. for small amounts or paper-only receipts."
    ),
    "Anlegen": "Add",
    "Nicht angelegt:": "Not added:",
    "Bruttobetrag fehlt.": "Gross amount missing.",
    "Partner fehlt.": "Partner missing.",
    "Datum fehlt.": "Date missing.",
    # upload job
    "Upload": "Upload",
    "Belege werden ausgelesen: {n} von {gesamt} fertig": "Reading receipts: {n} of {gesamt} done",
    "Etwa eine Minute pro Beleg. Du kannst weiterarbeiten; neue Uploads sind bis zum Ende gesperrt.": (
        "About one minute per receipt. You can keep working; new uploads are locked until it ends."
    ),
    "Details": "Details",
    "Upload fertig:": "Upload finished:",
    "{n} gespeichert": "{n} saved",
    "{n} mit Hinweis oder Fehler": "{n} with a note or error",
    "Ergebnis ansehen": "See result",
    "Ausblenden": "Dismiss",
    "Datei": "File",
    "Ergebnis": "Result",
    "wartet": "waiting",
    "wird ausgelesen …": "reading …",
    "prüfen und bearbeiten": "review and edit",
    "vorhandenen Beleg öffnen": "open existing receipt",
    "Es läuft schon ein Upload. Neue Belege können erst hochgeladen werden, wenn er fertig ist.": (
        "An upload is already running. New receipts can be uploaded once it has finished."
    ),
    "Kein Upload aktiv.": "No upload running.",
    "Zur Belegliste": "To the receipt list",
    "Dateityp {typ} nicht erlaubt.": "File type {typ} not allowed.",
    "Auslesen fehlgeschlagen: {msg}": "Reading failed: {msg}",
    "Schon vorhanden (gleicher Inhalt).": "Already stored (same content).",
    "Fehler: {exc}": "Error: {exc}",
    # one receipt
    "Beleg": "Receipt",
    "Dieser Beleg zählt nicht zum Gewinn, bis die Kategorie eindeutig ist.": (
        "This receipt is not part of the profit until its category is clear."
    ),
    "kein Datum": "no date",
    "Daten": "Data",
    "Beleg wirklich löschen?": "Really delete this receipt?",
    "Beleg löschen": "Delete receipt",
    "Original": "Original",
    "Beleg-Original": "Original receipt",
    "In neuem Tab öffnen": "Open in a new tab",
    "Kein Original (manuell erfasst).": "No original (entered manually).",
    # overview
    "ELSTER-Daten fehlen:": "ELSTER data missing:",
    "Nächste UStVA": "Next VAT return",
    "Fällig am": "Due on",
    "heute": "today",
    "morgen": "tomorrow",
    "in {n} Tagen": "in {n} days",
    "Zahllast": "Payable",
    "Erstattung": "Refund",
    "Übermittelt (Telenummer {t})": "Submitted (Telenummer {t})",
    "UStVA öffnen": "Open VAT return",
    "monatlich": "monthly",
    "vierteljährlich": "quarterly",
    "mit Dauerfristverlängerung": "with permanent extension",
    "ändern": "change",
    "{w} Beleg(e) mit Warnungen, {r} Beleg(e) ohne sichere EÜR-Zeile ({jahr}).": (
        "{w} receipt(s) with warnings, {r} receipt(s) without a certain EÜR line ({jahr})."
    ),
    "Belege prüfen": "Review receipts",
    "EÜR {jahr} (bisher)": "EÜR {jahr} (so far)",
    "Einnahmen (netto)": "Income (net)",
    "Ausgaben (netto)": "Expenses (net)",
    "Gewinn": "Profit",
    "{n} Belege im Jahr {jahr}. Ohne Beträge „zu prüfen“.": (
        "{n} receipts in {jahr}. Without amounts “to review”."
    ),
    "EÜR öffnen": "Open EÜR",
    # EÜR
    "Einnahmenüberschussrechnung": "Income surplus statement (EÜR)",
    "JSON herunterladen": "Download JSON",
    "Steuernummer für die Anlage EÜR:": "Tax number for the Anlage EÜR:",
    "Abgabe unter Steuernummer": "Filed under tax number",
    "Betriebseinnahmen": "Business income",
    "Keine Einnahmen.": "No income.",
    "Betriebsausgaben": "Business expenses",
    "Keine Ausgaben.": "No expenses.",
    "Gewinn (ohne „zu prüfen“)": "Profit (without “to review”)",
    "Kleinunternehmer (§ 19 UStG): Bruttobeträge, keine Umsatzsteuer-Zeilen.": (
        "Small business (§ 19 UStG): gross amounts, no VAT lines."
    ),
    "Kategorien netto; die Umsatzsteuer steht in Kz 140 / 185, Zahlungen an und Erstattungen vom Finanzamt in Kz 186 / 141.": (
        "Categories net; VAT is in Kz 140 / 185, payments to and refunds from the tax office in "
        "Kz 186 / 141."
    ),
    "Die Zeilentexte folgen dem amtlichen Formular und bleiben deutsch.": (
        "Line texts follow the official form and stay in German."
    ),
    "Diese Belege sind nicht im Gewinn, bis du entschieden hast ({betrag} netto).": (
        "These receipts are not in the profit until you decide ({betrag} net)."
    ),
    "Nichts offen.": "Nothing open.",
    "Anlage EÜR nicht erstellt:": "Anlage EÜR not built:",
    "An ELSTER (Anlage EÜR {jahr})": "To ELSTER (Anlage EÜR {jahr})",
    "Geprüft ist nur das Formular {jahr}. Für andere Jahre wird keine Anlage EÜR erstellt (YEAR-1).": (
        "Only the {jahr} form is verified. No Anlage EÜR is built for other years (YEAR-1)."
    ),
    "Art des Betriebs": "Type of business",
    "z. B. IT-Beratung": "e.g. IT consulting",
    "Zeile 11: Grundstücke oder grundstücksgleiche Rechte entnommen oder veräußert?": (
        "Line 11: land or equivalent rights withdrawn or sold?"
    ),
    "nein": "no",
    "ja": "yes",
    "Entnahmen (€, Zeile 106)": "Withdrawals (€, line 106)",
    "Einlagen (€, Zeile 107)": "Contributions (€, line 107)",
    "Verbindliches Senden der Anlage EÜR ist in FreiBuch abgeschaltet (Entscheidung D3). Steuernummer, Hersteller-ID, Zertifikat und ERiC-Pfad kommen aus den Stammdaten:": (
        "Binding submission of the Anlage EÜR is switched off in FreiBuch (decision D3). Tax "
        "number, Hersteller-ID, certificate and ERiC path come from the settings:"
    ),
    "Name und Anschrift fehlen in den Stammdaten.": "Name and address are missing in the settings.",
    "Art des Betriebs fehlt.": "Type of business missing.",
    "Zeile 11 (Grundstücke entnommen oder veräußert) bitte beantworten.": (
        "Please answer line 11 (land withdrawn or sold)."
    ),
    "Zertifikat und PIN fehlen in den Stammdaten.": "Certificate and PIN are missing in the settings.",
    # invoices
    "Nummer": "Number",
    "Kunde": "Customer",
    "Storno zu {n}": "Cancels {n}",
    "storniert": "cancelled",
    "stornieren": "cancel",
    "Rechnung {n} stornieren? Es wird eine Rechnungskorrektur mit eigener Nummer erstellt.": (
        "Cancel invoice {n}? A correction invoice with its own number is created."
    ),
    "Keine Rechnungen in diesem Jahr.": "No invoices this year.",
    "Neue Rechnung": "New invoice",
    "Name und Anschrift für den Absender fehlen in den Stammdaten.": (
        "Name and address of the sender are missing in the settings."
    ),
    "Rechnung nicht erstellt:": "Invoice not created:",
    "Land (wenn nicht Deutschland)": "Country (if not Germany)",
    "USt-IdNr. des Kunden (optional)": "Customer's VAT ID (optional)",
    "Rechnungsdatum": "Invoice date",
    "Leistungsdatum": "Date of supply",
    "oder Leistungszeitraum von": "or period of supply from",
    "bis": "to",
    "Leistung": "Service",
    "Menge": "Quantity",
    "Einheit": "Unit",
    "Std.": "hrs",
    "Einzelpreis netto (€)": "Unit price net (€)",
    "USt-Satz": "VAT rate",
    "+ Position": "+ Line",
    "Hinweise auf der Rechnung (z. B. Zahlungsziel, Grund einer Steuerbefreiung)": (
        "Notes on the invoice (e.g. payment terms, reason for a tax exemption)"
    ),
    "Kleinunternehmer (§ 19 UStG): keine Umsatzsteuer ausweisen": (
        "Small business (§ 19 UStG): show no VAT"
    ),
    "Hinweis für Kleinunternehmer": "Small-business note",
    "Wortlaut bitte prüfen (docs/tax-rules.md, Zeile „Kleinunternehmer invoice note“).": (
        "Please check the wording (docs/tax-rules.md, row “Kleinunternehmer invoice note”)."
    ),
    "Rechnung erstellen": "Create invoice",
    "Die Nummer (JJJJ-NNNN) wird beim Erstellen fortlaufend vergeben. Die Rechnung wird als Beleg der Art „Einnahme“ mit dem Rechnungsdatum gespeichert; geht das Geld an einem anderen Tag ein, dort das Datum ändern (EÜR: Zahlungstag).": (
        "The number (YYYY-NNNN) is assigned sequentially on creation. The invoice is stored as an "
        "“Income” receipt with the invoice date; if the money arrives on another day, change the "
        "date there (EÜR: payment date)."
    ),
    "Name und Anschrift des leistenden Unternehmers fehlen.": "Supplier name and address missing.",
    "Name und Anschrift des Leistungsempfängers fehlen.": "Customer name and address missing.",
    "Steuernummer oder USt-IdNr. des leistenden Unternehmers fehlt.": (
        "Supplier tax number or VAT ID missing."
    ),
    "Mindestens eine Position ist nötig.": "At least one line is needed.",
    "Leistungsdatum oder Leistungszeitraum fehlt.": "Date or period of supply missing.",
    "Leistungszeitraum: Beginn und Ende angeben.": "Period of supply: give start and end.",
    "Positionen mit 0 %: Hinweis auf den Grund (Steuerbefreiung) fehlt.": (
        "Lines at 0 %: note on the reason (tax exemption) missing."
    ),
    "Hinweis auf die Steuerbefreiung (§ 19 UStG) fehlt.": "Note on the exemption (§ 19 UStG) missing.",
    # UStVA
    "USt-Erklärung": "Annual VAT return",
    "Umsatzsteuer-Erklärung": "Annual VAT return",
    "Umsatzsteuer-Voranmeldung": "VAT pre-return (UStVA)",
    "Jahreserklärung": "Annual return",
    "ERiC-Prüfung ohne Fehler. Nichts gesendet.": "ERiC check without errors. Nothing sent.",
    "Testfall gesendet (Testmerker; ELSTER löscht ihn).": (
        "Test case sent (test marker; ELSTER deletes it)."
    ),
    "Telenummer": "Telenummer",
    "Übermittelt.": "Submitted.",
    "Nicht übermittelt:": "Not submitted:",
    "unbekannter Fehler": "unknown error",
    "Code": "Code",
    "Live-Übermittlung ist gesperrt. Zum Senden den Server mit dieser Variable starten:": (
        "Live submission is locked. To send, start the server with this variable:"
    ),
    "Jahreswerte {jahr}": "Annual figures {jahr}",
    "Umsätze {rate} % (netto)": "Sales {rate} % (net)",
    "Umsatzsteuer {rate} %": "VAT {rate} %",
    "Vorsteuer": "Input VAT",
    "Einfuhrumsatzsteuer": "Import VAT",
    "Umsatzsteuer − Vorsteuer": "VAT − input VAT",
    "Die bereits gezahlten Vorauszahlungen (Vorauszahlungssoll) trägst du unten ein; sie werden mitgesendet.": (
        "Enter the advance payments already made (Vorauszahlungssoll) below; they are sent along."
    ),
    "Kennzahlen": "Form lines (Kennzahlen)",
    "Keine umsatzsteuerlichen Belege in diesem Zeitraum.": "No VAT receipts in this period.",
    "{n} ohne USt nicht berücksichtigt": "{n} without VAT not counted",
    "Belege ansehen": "See receipts",
    "An ELSTER": "To ELSTER",
    "Besteuerungsart": "Taxation method",
    "Vorauszahlungssoll (€)": "Advance payments made (€)",
    "Berichtigte Anmeldung": "Corrected return",
    "Mit ERiC prüfen": "Check with ERiC",
    "Testfall senden": "Send test case",
    "Rechtsverbindlich an das Finanzamt senden?": "Send legally binding to the tax office?",
    "Verbindlich senden": "Send for real",
    "Verbindliches Senden ist aus. Es wird nur angeboten, wenn der Server mit dieser Variable läuft:": (
        "Sending for real is off. It is only offered when the server runs with this variable:"
    ),
    "Steuernummer, Hersteller-ID, Zertifikat und ERiC-Pfad kommen aus den Stammdaten:": (
        "Tax number, Hersteller-ID, certificate and ERiC path come from the settings:"
    ),
    "Übermittlungen": "Submissions",
    "Zeitpunkt (UTC)": "Time (UTC)",
    "Noch keine verbindliche Übermittlung. Testfälle werden nicht gespeichert.": (
        "No binding submission yet. Test cases are not stored."
    ),
    "XML herunterladen": "Download XML",
    "Druckansicht (PDF)": "Print preview (PDF)",
    "Beim Senden die PDF-Kopie von ERiC im Archiv speichern": (
        "When sending, store ERiC's PDF copy in the archive"
    ),
    "PDF-Kopie öffnen": "Open PDF copy",
    "PDF (ERiC)": "PDF (ERiC)",
    "ERiC hat keine Druckansicht erstellt.": "ERiC did not create a print preview.",
    "Archiv": "Archive",
    "Abgegebene Erklärungen": "Submitted returns",
    "Keine archivierten Erklärungen.": "No archived returns.",
    # UStVA Kennzahl labels (ui/web/routes.py KZ_LABELS)
    "Umsätze 19 % (Bemessungsgrundlage, volle Euro)": "Sales at 19 % (tax base, whole euros)",
    "Umsätze 7 % (Bemessungsgrundlage, volle Euro)": "Sales at 7 % (tax base, whole euros)",
    "Umsätze zu anderen Steuersätzen (Bemessungsgrundlage)": "Sales at other rates (tax base)",
    "Steuer zu anderen Steuersätzen": "Tax at other rates",
    "Vorsteuer aus Rechnungen anderer Unternehmer": "Input VAT from other businesses' invoices",
    "Verbleibende Vorauszahlung (+) / Überschuss (−)": "Remaining payment (+) / surplus (−)",
    "Sollversteuerung (vereinbarte Entgelte)": "Accrual basis (agreed consideration)",
    "Istversteuerung (vereinnahmte Entgelte)": "Cash basis (received consideration)",
    "teils Soll-, teils Istversteuerung": "partly accrual, partly cash basis",
    # Stammdaten
    "Steuerpflichtige Person": "Taxpayer",
    "Gespeichertes Bundesland „{land}“ ist nicht eindeutig. Bitte unten auswählen.": (
        "The stored federal state “{land}” is ambiguous. Please choose it below."
    ),
    "Name": "Name",
    "Straße und Hausnummer": "Street and house number",
    "Adresszusatz": "Address line 2",
    "PLZ": "Postcode",
    "Ort": "City",
    "Bundesland": "Federal state",
    "bitte wählen": "please choose",
    "Steuernummer für die Umsatzsteuer": "Tax number for VAT",
    "wie auf dem Bescheid, z. B. 198/113/10010": "as on the tax assessment, e.g. 198/113/10010",
    "Für UStVA und Umsatzsteuer-Erklärung. Wer nur eine Steuernummer hat, trägt sie hier ein.": (
        "For VAT returns. If you have only one tax number, enter it here."
    ),
    "Steuernummer für die Einkommensteuer (falls eine andere)": (
        "Tax number for income tax (if different)"
    ),
    "leer = dieselbe Nummer": "empty = the same number",
    "Manche Finanzämter vergeben eine eigene Nummer für die Umsatzsteuer.": (
        "Some tax offices issue a separate number for VAT."
    ),
    "Anlage EÜR abgeben unter": "File the Anlage EÜR under",
    "Einkommensteuer-Nummer": "income tax number",
    "Umsatzsteuer-Nummer": "VAT number",
    "Nur nötig bei zwei verschiedenen Nummern. Welche gilt, steht im Schreiben des Finanzamts zur Vergabe der Nummern; im Zweifel dort nachfragen.": (
        "Only needed with two different numbers. Which one applies is in the tax office's letter "
        "assigning them; if in doubt, ask there."
    ),
    "Bitte auswählen.": "Please choose.",
    "USt-IdNr. (optional)": "VAT ID (optional)",
    "Rechtsform": "Legal form",
    "Freiberuflich": "Freelancer (freie Berufe)",
    "Voranmeldungszeitraum": "VAT return period",
    "Dauerfristverlängerung (Frist einen Monat später)": (
        "Permanent extension (deadline one month later)"
    ),
    "Welcher Zeitraum gilt, legt das Finanzamt fest (§ 18 Abs. 2 UStG).": (
        "The tax office decides which period applies (§ 18 Abs. 2 UStG)."
    ),
    "Kleinunternehmer (§ 19 UStG)": "Small business (§ 19 UStG)",
    "Jahre als Kleinunternehmer": "Years as a small business",
    "z. B. 2024, 2025": "e.g. 2024, 2025",
    "In diesen Jahren rechnet die EÜR alle Einnahmen in Kz 111 und alle Beträge brutto, ohne Umsatzsteuer-Zeilen.": (
        "In these years the EÜR puts all income in Kz 111 and all amounts gross, without VAT lines."
    ),
    "Bitte Jahreszahlen mit vier Ziffern, durch Komma getrennt.": (
        "Please enter four-digit years, separated by commas."
    ),
    "Hersteller-ID": "Hersteller-ID",
    "5 Ziffern": "5 digits",
    "Zertifikat (.pfx)": "Certificate (.pfx)",
    "noch keins": "none yet",
    "Zertifikats-PIN": "Certificate PIN",
    "Leer lassen, um die gespeicherte PIN zu behalten.": "Leave empty to keep the stored PIN.",
    "ERiC-Pfad (Ordner mit ericapi)": "ERiC path (folder with ericapi)",
    "sonst Umgebungsvariable FINAMT_ERIC_HOME": "otherwise environment variable FINAMT_ERIC_HOME",
    "Gespeichert im Projektordner, wie in der alten Oberfläche. Die PIN wird nie wieder angezeigt.": (
        "Stored in the project folder, as in the old interface. The PIN is never shown again."
    ),
    "Leer: die Umsatzsteuer-Nummer gilt für alles.": "Empty: the VAT number applies to everything.",
    "Bundesland und Steuernummer eintragen; die ELSTER-Werte werden dann berechnet.": (
        "Enter the federal state and tax number; the ELSTER values are then computed."
    ),
    "13-stellige ELSTER-Steuernummer": "13-digit ELSTER tax number",
    "Finanzamtsnr.": "Tax office no.",
    "Die Prüfziffer kontrolliert ERiC beim Prüfen oder Senden.": (
        "ERiC checks the check digit when checking or sending."
    ),
    "Bundesland fehlt.": "Federal state missing.",
    "Steuernummer fehlt.": "Tax number missing.",
    "Steuernummer darf nur Ziffern, / und Leerzeichen enthalten.": (
        "The tax number may only contain digits, / and spaces."
    ),
    "Zwei Steuernummern eingetragen: in den Stammdaten festlegen, unter welcher die Anlage EÜR abgegeben wird.": (
        "Two tax numbers entered: choose in the settings which one the Anlage EÜR is filed under."
    ),
    # projects and partners (UI-8)
    "Projekte": "Projects",
    "Neues Projekt": "New project",
    "Projekt anlegen": "Create project",
    "Projekt löschen": "Delete project",
    "Projekt „{name}“ mit allen Belegen wirklich löschen?": (
        "Really delete project “{name}” with all its receipts?"
    ),
    "Projekt angelegt.": "Project created.",
    "Projekt gelöscht.": "Project deleted.",
    "Leerer Projektordner entfernt.": "Empty project folder removed.",
    "Ordner ohne Datenbank": "Folders without a database",
    "Reste gelöschter Projekte. Sie erscheinen nicht mehr in der Projektauswahl.": (
        "Leftovers of deleted projects. They no longer appear in the project selection."
    ),
    "{n} Datei(en), bitte selbst prüfen": "{n} file(s), please check yourself",
    "leer": "empty",
    "Ordner entfernen": "Remove folder",
    "Das Standardprojekt kann nicht gelöscht werden.": "The default project can't be deleted.",
    "Partner": "Partners",
    "Partnerliste": "Partner list",
    "Projekte verwalten": "Manage projects",
    "z. B. freiberuf-2026": "e.g. freelance-2026",
    "Kleinbuchstaben, Ziffern, - und _. Jedes Projekt hat eine eigene Datenbank.": (
        "Lower-case letters, digits, - and _. Each project has its own database."
    ),
    "aktiv": "active",
    "Beim Löschen bleiben die Original-Dateien (PDFs) im Projektordner erhalten.": (
        "Deleting keeps the original files (PDFs) in the project folder."
    ),
    "USt-IdNr.": "VAT ID",
    "Zusammenführen hängt alle Belege an den gewählten Partner und löscht diesen Eintrag.": (
        "Merging moves all receipts to the chosen partner and deletes this entry."
    ),
    "Dateien": "Files",
    "Eigene Kopie": "Own copy",
    "Bescheid": "Tax assessment",
    "entfernen": "remove",
    "Hochladen": "Upload",
    "Alle Dateien im Archivordner": "All files in the archive folder",
    "Nur verbindliche Übermittlungen werden archiviert; Testfälle nicht.": (
        "Only binding submissions are archived; test cases are not."
    ),
    "geprüft": "verified",
    "als geprüft markieren": "mark as verified",
    "Umbenennen": "Rename",
    "Zusammenführen mit …": "Merge into …",
    "Zusammenführen": "Merge",
    "Keine Partner.": "No partners.",
    "Partner gespeichert.": "Partner saved.",
    "Partner zusammengeführt.": "Partners merged.",
}


Translator = Callable[..., str]


def translator(lang: str) -> Translator:
    """``_(text, **args)`` for ``lang``: English lookup with German fallback, then ``format``."""

    def _(text: str, **args) -> str:
        if not text:
            return ""
        s = EN.get(text, text) if lang == "en" else text
        if args:
            try:
                return s.format(**args)
            except (KeyError, IndexError, ValueError):
                return s
        return s

    return _


def lang_from(request) -> str:
    code = request.cookies.get(COOKIE, DEFAULT)
    return code if code in CODES else DEFAULT


def zeitraum_label(z, lang: str) -> str:
    """Label of a UStVA period (``helpers.Zeitraum``) in ``lang``."""
    if z is None:
        return ""
    if lang != "en":
        return z.label
    if getattr(z, "is_jahr", False):
        return f"Year {z.jahr}"
    if getattr(z, "month", None):
        return f"{MONATE_EN[z.month - 1]} {z.jahr}"
    return z.label  # "Q1 2025" is the same in English
