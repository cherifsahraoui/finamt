"""
finamt.tax.eur_elster
~~~~~~~~~~~~~~~~~~~~~
ELSTER boundary for the Einnahmen-Überschuss-Rechnung (Anlage EÜR).

Status
------
- ``build_xml``  — NOT IMPLEMENTED. The Anlage EÜR Kennzahlen, the ELSTER
  Verfahren/DatenArt and the ERiC ``datenartVersion`` are not verified against
  official sources yet. See ``docs/TODO.md`` → "EÜR ELSTER builder" and
  ``docs/tax-rules.md``. Do not guess field numbers.
- ``validate``   — local, offline structural check of an ELSTER envelope.
- ``submit``     — ``mode="dry_run"`` (default): validate locally, send nothing.
                   ``mode="test"``: validate + send via ERiC **with Testmerker only**.
                   ``mode="live"``: always raises ``NotImplementedError``.

ERiC
----
The ERiC library directory is read from the ``ERIC_LIBRARY_PATH`` environment
variable only (not ``FINAMT_ERIC_HOME``, not the project database).
The ctypes bridge is :mod:`finamt.tax.eric_wrapper`.
"""

from __future__ import annotations

import contextlib
import os

from lxml import etree

from .elster import NS, TESTMERKER, ElsterConfig, ElsterEricClient, SubmissionResult
from .eric_wrapper import (
    ERIC_SENDE,
    ERIC_VALIDIERE,
    EricBuffer,
    EricCertificate,
    EricError,
    EricSession,
)
from .eur import EURReport

ERIC_LIBRARY_ENV = "ERIC_LIBRARY_PATH"
MODES = ("dry_run", "test", "live")
LIVE_DISABLED_MESSAGE = "Live ELSTER submission requires a Hersteller-ID and is disabled."


def build_xml(eur_report: EURReport) -> bytes:
    """
    Build the ELSTER XML envelope for an Anlage EÜR.

    Not implemented: the mapping from :class:`~finamt.tax.eur.EURReport` to the
    official Anlage EÜR Kennzahlen (and the ELSTER DatenArt / ERiC
    ``datenartVersion``) has not been verified against official sources.
    See ``docs/TODO.md`` ("EÜR ELSTER builder") for the task and acceptance test,
    and ``docs/tax-rules.md`` for the status of each value.

    Raises
    ------
    NotImplementedError
        Always, until the Kennzahlen are verified.
    """
    raise NotImplementedError(
        "EÜR ELSTER XML builder is not implemented: Anlage EÜR Kennzahlen are not "
        "verified. See docs/TODO.md (EÜR ELSTER builder)."
    )


def _parse(xml: bytes) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    return etree.fromstring(xml, parser=parser)


def validate(xml: bytes) -> list[str]:
    """
    Check an ELSTER envelope locally. Returns a list of errors (empty = OK).

    Offline structural checks only: well-formed, no DOCTYPE, root ``Elster`` in the
    ELSTER namespace, ``TransferHeader`` with ``Verfahren`` and ``DatenArt``, and
    ``DatenTeil`` containing ``Nutzdaten``. It does **not** check Kennzahlen,
    the XSD, or plausibility rules — that is ERiC's job (``submit(mode="test")``).
    """
    if not isinstance(xml, (bytes, bytearray)) or not xml.strip():
        return ["XML is empty"]
    if b"<!DOCTYPE" in xml:
        return ["DOCTYPE declarations are not allowed"]
    try:
        root = _parse(bytes(xml))
    except etree.XMLSyntaxError as exc:
        return [f"XML is not well-formed: {exc}"]

    errors: list[str] = []
    qname = etree.QName(root)
    if qname.localname != "Elster":
        errors.append(f"Root element must be 'Elster', got '{qname.localname}'")
    if qname.namespace != NS:
        errors.append(f"Root namespace must be '{NS}', got '{qname.namespace}'")

    ns = {"e": NS}
    th = root.find("e:TransferHeader", ns)
    if th is None:
        errors.append("Missing TransferHeader")
    else:
        for tag in ("Verfahren", "DatenArt"):
            el = th.find(f"e:{tag}", ns)
            if el is None or not (el.text or "").strip():
                errors.append(f"Missing TransferHeader/{tag}")
    if root.find("e:DatenTeil", ns) is None:
        errors.append("Missing DatenTeil")
    elif root.find(".//e:DatenTeil//e:Nutzdaten", ns) is None:
        errors.append("Missing DatenTeil//Nutzdaten")
    return errors


def has_testmerker(xml: bytes) -> bool:
    """True if the envelope's TransferHeader carries the ELSTER Testmerker."""
    try:
        root = _parse(bytes(xml))
    except etree.XMLSyntaxError:
        return False
    el = root.find(f"{{{NS}}}TransferHeader/{{{NS}}}Testmerker")
    return el is not None and (el.text or "").strip() == TESTMERKER


def submit(
    xml: bytes,
    mode: str = "dry_run",
    *,
    datenart_version: str | None = None,
    config: ElsterConfig | None = None,
    log_dir: str | None = None,
) -> SubmissionResult:
    """
    Validate and optionally transmit an EÜR envelope.

    Parameters
    ----------
    xml:
        ELSTER envelope bytes (from ``build_xml`` once implemented).
    mode:
        ``"dry_run"`` (default): local validation only, nothing leaves the machine.
        ``"test"``: ERiC validate + send to ELSTER **test** processing. The XML must
        carry the Testmerker, otherwise the call is refused.
        ``"live"``: raises ``NotImplementedError``.
    datenart_version:
        ERiC ``datenartVersion`` for the Anlage EÜR. Required in test mode. The
        correct value is not verified yet (see docs/tax-rules.md), so there is no default.
    config:
        ``ElsterConfig`` with certificate path and PIN. Defaults to
        ``ElsterConfig.from_env()`` in test mode.
    log_dir:
        Optional ERiC log directory.
    """
    if mode == "live":
        raise NotImplementedError(LIVE_DISABLED_MESSAGE)
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES[:2]}, got {mode!r}")

    errors = validate(xml)
    if errors:
        return SubmissionResult(
            success=False, error_code="VALIDATION_ERROR", error_message="; ".join(errors)
        )

    if mode == "dry_run":
        return SubmissionResult(
            success=True, raw_response="dry_run: validated locally, nothing was sent"
        )

    # mode == "test"
    if not has_testmerker(xml):
        return SubmissionResult(
            success=False,
            error_code="TESTMERKER_MISSING",
            error_message=f"Test mode requires TransferHeader/Testmerker={TESTMERKER}.",
        )
    if not datenart_version:
        raise ValueError(
            "datenart_version is required in test mode (the Anlage EÜR value is not "
            "verified yet, see docs/tax-rules.md)."
        )
    eric_home = os.environ.get(ERIC_LIBRARY_ENV, "").strip()
    if not eric_home:
        return SubmissionResult(
            success=False,
            error_code="ERIC_LIBRARY_PATH_MISSING",
            error_message=f"Set {ERIC_LIBRARY_ENV} to the ERiC lib directory.",
        )
    cfg = config or ElsterConfig.from_env()
    return _eric_send(xml, eric_home, datenart_version, cfg, log_dir)


def _eric_send(
    xml: bytes,
    eric_home: str,
    datenart_version: str,
    cfg: ElsterConfig,
    log_dir: str | None,
) -> SubmissionResult:
    """Validate + send via ERiC. Only reached in test mode (Testmerker checked)."""
    rc = 0
    response_xml = b""
    server_xml = b""
    eric_text = ""
    try:
        with EricSession(eric_home, log_dir=log_dir) as eric:
            with EricBuffer(eric) as resp_buf, EricBuffer(eric) as srv_buf:
                with EricCertificate(eric, str(cfg.cert_path), cfg.cert_password) as cert:
                    rc, _th = eric.bearbeite_vorgang(
                        xml_bytes=xml,
                        datenart_version=datenart_version,
                        flags=ERIC_VALIDIERE | ERIC_SENDE,
                        crypto_params=cert.verschluesselungs_parameter,
                        response_buffer=resp_buf.handle(),
                        server_buffer=srv_buf.handle(),
                    )
                    response_xml = resp_buf.content()
                    server_xml = srv_buf.content()
                    if rc != 0:
                        with contextlib.suppress(Exception):
                            eric_text = eric.get_error_text(rc)
    except EricError as exc:
        return SubmissionResult(success=False, error_code=str(exc.code), error_message=str(exc))
    except OSError as exc:
        return SubmissionResult(
            success=False,
            error_code="ERIC_LOAD_ERROR",
            error_message=f"Could not load ERiC library from {eric_home}: {exc}",
        )

    if rc != 0:
        return SubmissionResult(
            success=False,
            error_code=str(rc),
            error_message=ElsterEricClient._extract_eric_error(
                rc, response_xml, server_xml, eric_text
            ),
            raw_response=(response_xml + server_xml).decode("utf-8", errors="replace"),
        )
    return SubmissionResult(
        success=True,
        telenummer=ElsterEricClient._extract_telenummer(server_xml),
        raw_response=server_xml.decode("utf-8", errors="replace"),
    )
