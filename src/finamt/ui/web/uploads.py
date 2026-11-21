"""
Background receipt uploads for the ``/app`` UI.

Reading a receipt (OCR + LLM) takes about a minute per file. Running it inside the POST
request meant the progress vanished as soon as the user opened another page. Instead the
POST stores the files and starts **one** job in a background thread; every page shows its
progress (``_upload_status.html``), and a new upload is refused while a job runs.

The state lives in memory: FreiBuch is a local, single-process, single-user server. After a
restart an unfinished job is gone (receipts already saved stay saved).
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Status values of one file.
WARTET, LAEUFT, FERTIG = "wartet", "läuft", "fertig"


@dataclass
class UploadItem:
    name: str
    path: Path | None  # temp file; None when the file was rejected before the job
    status: str = WARTET
    receipt_id: str | None = None
    fehler: str = ""  # German message template, translated in the page
    fehler_args: dict = field(default_factory=dict)


@dataclass
class UploadJob:
    id: str
    projekt: str
    typ: str
    items: list[UploadItem]
    started: datetime = field(default_factory=datetime.now)
    finished: datetime | None = None

    @property
    def running(self) -> bool:
        return self.finished is None

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.status == FERTIG)

    @property
    def ok_count(self) -> int:
        return sum(1 for i in self.items if i.status == FERTIG and i.receipt_id and not i.fehler)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.items if i.status == FERTIG and i.fehler)


#: process(path, receipt_type) -> (receipt_id or None, error template or "", template args)
Processor = Callable[[Path, str], tuple[str | None, str, dict]]

_lock = threading.Lock()
_job: UploadJob | None = None  # the running job, or the last finished one until dismissed


def _spawn(fn: Callable[[], None]) -> None:
    """Start ``fn`` in the background. Tests replace this to run inline or not at all."""
    threading.Thread(target=fn, name="freibuch-upload", daemon=True).start()


def current() -> UploadJob | None:
    return _job


def busy() -> bool:
    job = _job
    return job is not None and job.running


def start(projekt: str, typ: str, items: list[UploadItem], process: Processor) -> UploadJob | None:
    """Start a job, or return None when another one is still running."""
    global _job
    with _lock:
        if _job is not None and _job.running:
            return None
        job = UploadJob(id=uuid.uuid4().hex[:12], projekt=projekt, typ=typ, items=items)
        _job = job
    _spawn(lambda: _run(job, process))
    return job


def _run(job: UploadJob, process: Processor) -> None:
    try:
        for item in job.items:
            if item.status == FERTIG:  # rejected up front
                continue
            item.status = LAEUFT
            try:
                item.receipt_id, item.fehler, item.fehler_args = process(item.path, job.typ)
            except Exception as exc:  # noqa: BLE001 — show any pipeline error to the user
                item.fehler, item.fehler_args = "Fehler: {exc}", {"exc": str(exc)}
            finally:
                if item.path is not None:
                    item.path.unlink(missing_ok=True)
                item.status = FERTIG
    finally:
        job.finished = datetime.now()


def dismiss(job_id: str) -> None:
    """Hide a finished job's results. A running job can't be dismissed."""
    global _job
    with _lock:
        if _job is not None and _job.id == job_id and not _job.running:
            _job = None


def reset() -> None:
    """Forget all state (tests)."""
    global _job
    with _lock:
        _job = None
