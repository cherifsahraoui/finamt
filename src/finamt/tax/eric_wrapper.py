"""
finamt.tax.eric_wrapper
~~~~~~~~~~~~~~~~~~~~~~~
Self-contained Python ctypes bridge to the ERiC shared library.

Adapted from the official ERiC-43.4.6.0 Python demo
(ERiC-43.4.6.0/Darwin-universal/Beispiel/ericdemo-python/).

Usage::

    from finamt.tax.eric_wrapper import EricSession, EricBuffer, EricCertificate
    from finamt.tax.eric_wrapper import ERIC_VALIDIERE, ERIC_SENDE

    with EricSession(eric_home="/path/to/eric/lib", log_dir="/tmp/eric_logs") as eric:
        with EricBuffer(eric) as resp_buf, EricBuffer(eric) as srv_buf:
            with EricCertificate(eric, "/path/to/cert.pfx", "pin") as cert:
                rc, th = eric.bearbeite_vorgang(
                    xml_bytes,
                    datenart_version="Bilanz_6_9",
                    flags=ERIC_VALIDIERE | ERIC_SENDE,
                    crypto_params=cert.verschluesselungs_parameter,
                    response_buffer=resp_buf.handle(),
                    server_buffer=srv_buf.handle(),
                )

ERIC_HOME should point to the directory containing libericapi.dylib
(e.g. /path/to/ERiC-43.4.6.0/Darwin-universal/lib/).
Plugins are expected in <ERIC_HOME>/plugins/.
"""

from __future__ import annotations

import logging
import os
import platform
from ctypes import (
    CDLL,
    CFUNCTYPE,
    POINTER,
    Structure,
    byref,
    c_char,
    c_char_p,
    c_int,
    c_uint32,
    c_void_p,
    string_at,
)
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bearbeitungsflags
# ---------------------------------------------------------------------------

ERIC_VALIDIERE = 1 << 1  # validate only
ERIC_SENDE = 1 << 2  # transmit to ELSTER server
ERIC_DRUCKE = 1 << 5  # generate PDF print
ERIC_PRUEFE_HINWEISE = 1 << 7  # treat warnings as errors

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENCODING = "utf-8"


def _enc(value: bytes | str | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return value.encode(_ENCODING)


def _dec(value: bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(_ENCODING)
    raise TypeError(f"Expected bytes, got {type(value)}")


def _lib_name(name: str) -> str:
    sys = platform.system()
    if sys == "Windows":
        return name + ".dll"
    if sys == "Darwin":
        return "lib" + name + ".dylib"
    return "lib" + name + ".so"


# ---------------------------------------------------------------------------
# ctypes type definitions
# ---------------------------------------------------------------------------

# Callback function types (CFUNCTYPE works on macOS/Linux; WINFUNCTYPE on Windows)
_FuncType = CFUNCTYPE  # platform check done at import time

EricLogCallback = _FuncType(None, c_char_p, c_int, c_char_p, c_void_p)
EricFortschrittCallback = _FuncType(None, c_uint32, c_uint32, c_uint32, c_void_p)
EricPdfCallback = _FuncType(c_int, c_char_p, c_void_p, c_uint32, c_void_p)

EricZertifikatHandle = c_uint32
EricTransferHandle = c_uint32


class _EricRueckgabepufferHandle(c_void_p):
    pass


class _eric_druck_parameter_t(Structure):
    _fields_ = [
        ("version", c_uint32),
        ("vorschau", c_uint32),
        ("duplexDruck", c_uint32),
        ("pdfName", c_char_p),
        ("fussText", c_char_p),
        ("pdfCallback", EricPdfCallback),
        ("pdfCallbackBenutzerdaten", c_void_p),
    ]


#: eric_druck_parameter_t.version — "muss derzeit 4 sein" (ERiC 44.3 API-Referenz, eric_types.h).
DRUCK_PARAMETER_VERSION = 4


def _pdf_path_bytes(path: str | os.PathLike) -> bytes:
    """
    pdfName as ERiC expects it: Windows ANSI code page ("mbcs"); elsewhere the file-system
    encoding (ERiC 44.3 API-Referenz, eric_druck_parameter_t::pdfName). macOS would need the
    decomposed UTF-8 form, which FreiBuch doesn't support yet.
    """
    s = os.fspath(path)
    return s.encode("mbcs") if os.name == "nt" else os.fsencode(s)


def make_druck_parameter(
    pdf_path: str | os.PathLike, *, vorschau: bool, fuss_text: str | None = None
) -> _eric_druck_parameter_t:
    """
    Print parameters for ``EricBearbeiteVorgang`` (Entwicklerhandbuch 44.3, Tabelle 6-2):
    ``vorschau=True`` with VALIDIERE + DRUCKE (EBV-2, preview, nothing sent);
    ``vorschau=False`` with VALIDIERE + SENDE + DRUCKE (EBV-4 / EBV-6). ERiC writes the PDF
    to ``pdf_path`` (no callback). The returned structure keeps the encoded path alive.
    """
    p = _eric_druck_parameter_t()
    p.version = DRUCK_PARAMETER_VERSION
    p.vorschau = 1 if vorschau else 0
    p.duplexDruck = 0
    p._pdf_name = _pdf_path_bytes(pdf_path)  # keep a reference for the call's lifetime
    p.pdfName = p._pdf_name
    p._fuss = fuss_text.encode(_ENCODING) if fuss_text else None
    p.fussText = p._fuss
    p.pdfCallback = EricPdfCallback()  # NULL: ERiC writes the file itself
    p.pdfCallbackBenutzerdaten = None
    return p


class _eric_verschluesselungs_parameter_t(Structure):
    _fields_ = [
        ("version", c_uint32),
        ("zertifikatHandle", EricZertifikatHandle),
        ("pin", c_char_p),
    ]


# ---------------------------------------------------------------------------
# Library loader
# ---------------------------------------------------------------------------


def _load_library(home_dir: str) -> CDLL:
    lib_path = os.path.join(home_dir, _lib_name("ericapi"))
    lib = CDLL(lib_path)

    class _Str(c_char_p):
        @classmethod
        def from_param(cls, obj):
            return c_char_p(_enc(obj))

    S = _Str

    # fmt: off
    _funcs = [
        # name,                            restype,                          argtypes
        ("EricInitialisiere",              c_int,    [S, S]),
        ("EricBeende",                     c_int,    None),
        # ERiC >= 44: no transferHandle argument any more (Releasenotes 5.2.6, ERIC-36021)
        ("EricBearbeiteVorgang",           c_int,    [S, S, c_uint32,
                                                       POINTER(_eric_druck_parameter_t),
                                                       POINTER(_eric_verschluesselungs_parameter_t),
                                                       _EricRueckgabepufferHandle,
                                                       _EricRueckgabepufferHandle]),
        ("EricCheckXML",                   c_int,    [S, S, _EricRueckgabepufferHandle]),
        ("EricGetHandleToCertificate",     c_int,    [POINTER(EricZertifikatHandle),
                                                       POINTER(c_uint32), S]),
        ("EricCloseHandleToCertificate",   c_int,    [EricZertifikatHandle]),
        ("EricHoleZertifikatEigenschaften",c_int,    [EricZertifikatHandle, S,
                                                       _EricRueckgabepufferHandle]),
        ("EricGetErrormessagesFromXMLAnswer", c_int, [S,
                                                       _EricRueckgabepufferHandle,
                                                       _EricRueckgabepufferHandle,
                                                       _EricRueckgabepufferHandle,
                                                       _EricRueckgabepufferHandle]),
        ("EricHoleFehlerText",             c_int,    [c_int, _EricRueckgabepufferHandle]),
        ("EricRueckgabepufferErzeugen",    _EricRueckgabepufferHandle, None),
        ("EricRueckgabepufferFreigeben",   c_int,    [_EricRueckgabepufferHandle]),
        ("EricRueckgabepufferInhalt",      POINTER(c_char),   [_EricRueckgabepufferHandle]),
        ("EricRueckgabepufferLaenge",      c_uint32, [_EricRueckgabepufferHandle]),
        ("EricSystemCheck",                c_int,    None),
        ("EricVersion",                    c_int,    [_EricRueckgabepufferHandle]),
        ("EricRegistriereLogCallback",     c_int,    [EricLogCallback, c_uint32, c_void_p]),
    ]
    # fmt: on

    for name, restype, argtypes in _funcs:
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = argtypes

    return lib


# ---------------------------------------------------------------------------
# Core session
# ---------------------------------------------------------------------------


class EricError(Exception):
    def __init__(self, code: int, message: str = ""):
        self.code = code
        super().__init__(f"ERiC error {code}: {message}")


class EricSession:
    """
    Context manager that initialises / tears down the ERiC library.

    Parameters
    ----------
    eric_home:
        Path to the directory containing libericapi.dylib (and plugins/).
    log_dir:
        Optional path for ERiC log files.  Pass None to disable.
    """

    def __init__(self, eric_home: str, log_dir: str | None = None) -> None:
        self._home = str(Path(eric_home).resolve())
        self._log_dir = str(Path(log_dir).resolve()) if log_dir else None
        self._lib: CDLL | None = None
        self._log_cb = None  # keep alive

    # ------------------------------------------------------------------
    # context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> EricSession:
        self._lib = _load_library(self._home)
        if self._log_dir:
            Path(self._log_dir).mkdir(parents=True, exist_ok=True)
        rc = self._lib.EricInitialisiere(_enc(self._home), _enc(self._log_dir))
        if rc != 0:
            raise EricError(rc, "EricInitialisiere failed")
        logger.debug("ERiC initialised from %s", self._home)
        return self

    def __exit__(self, *_) -> None:
        if self._lib is not None:
            try:
                self._lib.EricBeende()
            except Exception:
                pass
            self._lib = None

    # ------------------------------------------------------------------
    # buffer helpers
    # ------------------------------------------------------------------

    def _buf_create(self) -> _EricRueckgabepufferHandle:
        h = self._lib.EricRueckgabepufferErzeugen()
        if h is None:
            raise EricError(0, "Could not create return buffer")
        return h

    def _buf_free(self, h: _EricRueckgabepufferHandle) -> None:
        self._lib.EricRueckgabepufferFreigeben(h)

    def _buf_read(self, h: _EricRueckgabepufferHandle) -> bytes:
        length = self._lib.EricRueckgabepufferLaenge(h)
        if length == 0:
            return b""
        ptr = self._lib.EricRueckgabepufferInhalt(h)
        return string_at(ptr, length)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def bearbeite_vorgang(
        self,
        xml_bytes: bytes,
        datenart_version: str,
        flags: int,
        crypto_params: _eric_verschluesselungs_parameter_t | None = None,
        response_buffer: _EricRueckgabepufferHandle | None = None,
        server_buffer: _EricRueckgabepufferHandle | None = None,
        druck_params: _eric_druck_parameter_t | None = None,
    ) -> tuple[int, int | None]:
        """
        Call EricBearbeiteVorgang.

        Returns
        -------
        (eric_return_code, None)
            The second element is always None: ERiC 44 removed the transfer
            handle (Releasenotes 5.2.6, ERIC-36021). The transfer ticket is in
            the server response. The tuple shape is kept for existing callers.
        """
        cp_ref: POINTER | None = None
        if crypto_params is not None:
            cp_ref = byref(crypto_params)
        dp_ref = byref(druck_params) if druck_params is not None else None

        rc = self._lib.EricBearbeiteVorgang(
            _enc(xml_bytes if isinstance(xml_bytes, bytes) else xml_bytes.encode()),
            _enc(datenart_version),
            c_uint32(flags),
            dp_ref,  # druck_parameter: NULL unless a PDF is requested (ERIC_DRUCKE)
            cp_ref,
            response_buffer,
            server_buffer,
        )
        return rc, None

    def get_error_text(self, code: int) -> str:
        h = self._buf_create()
        try:
            self._lib.EricHoleFehlerText(c_int(code), h)
            return self._buf_read(h).decode(_ENCODING, errors="replace")
        finally:
            self._buf_free(h)

    def get_error_messages_from_response(self, xml_answer: bytes) -> dict:
        """Parse ELSTER server response XML for error/transfer-ticket info."""
        ticket_buf = self._buf_create()
        rc_th_buf = self._buf_create()
        err_th_buf = self._buf_create()
        ndh_buf = self._buf_create()
        try:
            self._lib.EricGetErrormessagesFromXMLAnswer(
                _enc(xml_answer), ticket_buf, rc_th_buf, err_th_buf, ndh_buf
            )
            return {
                "transfer_ticket": self._buf_read(ticket_buf).decode(_ENCODING, errors="replace"),
                "return_code_th": self._buf_read(rc_th_buf).decode(_ENCODING, errors="replace"),
                "error_text_th": self._buf_read(err_th_buf).decode(_ENCODING, errors="replace"),
                "ndh_xml": self._buf_read(ndh_buf).decode(_ENCODING, errors="replace"),
            }
        finally:
            for b in (ticket_buf, rc_th_buf, err_th_buf, ndh_buf):
                self._buf_free(b)

    def load_certificate(self, path: str, pin: str) -> tuple[int, int]:
        """
        Load a PKCS#12 certificate.

        Returns
        -------
        (handle, pin_support_info)
        """
        h_token = EricZertifikatHandle(0)
        pin_support = c_uint32(0)
        rc = self._lib.EricGetHandleToCertificate(byref(h_token), byref(pin_support), _enc(path))
        if rc != 0:
            raise EricError(rc, f"Cannot load certificate: {path}")
        return h_token.value, pin_support.value

    def close_certificate(self, handle: int) -> None:
        self._lib.EricCloseHandleToCertificate(EricZertifikatHandle(handle))

    def make_verschluesselungs_parameter(
        self, handle: int, pin: str
    ) -> _eric_verschluesselungs_parameter_t:
        p = _eric_verschluesselungs_parameter_t()
        p.version = 3
        p.zertifikatHandle = EricZertifikatHandle(handle)
        p.pin = _enc(pin)
        return p


# ---------------------------------------------------------------------------
# Context manager helpers
# ---------------------------------------------------------------------------


class EricBuffer:
    """RAII wrapper for an EricRueckgabepuffer."""

    def __init__(self, session: EricSession) -> None:
        self._session = session
        self._handle: _EricRueckgabepufferHandle | None = None

    def __enter__(self) -> EricBuffer:
        self._handle = self._session._buf_create()
        return self

    def __exit__(self, *_) -> None:
        if self._handle is not None:
            self._session._buf_free(self._handle)
            self._handle = None

    def handle(self) -> _EricRueckgabepufferHandle:
        assert self._handle is not None, "Buffer not open"
        return self._handle

    def content(self) -> bytes:
        assert self._handle is not None, "Buffer not open"
        return self._session._buf_read(self._handle)


class EricCertificate:
    """RAII wrapper for an ERiC certificate handle."""

    def __init__(self, session: EricSession, path: str, pin: str) -> None:
        self._session = session
        self._path = path
        self._pin = pin
        self._handle: int | None = None
        self.verschluesselungs_parameter: _eric_verschluesselungs_parameter_t | None = None

    def __enter__(self) -> EricCertificate:
        h, _ = self._session.load_certificate(self._path, self._pin)
        self._handle = h
        self.verschluesselungs_parameter = self._session.make_verschluesselungs_parameter(
            h, self._pin
        )
        return self

    def __exit__(self, *_) -> None:
        if self._handle is not None:
            self._session.close_certificate(self._handle)
            self._handle = None
            self.verschluesselungs_parameter = None
