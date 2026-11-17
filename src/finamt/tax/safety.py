"""
finamt.tax.safety
~~~~~~~~~~~~~~~~~
Guard against accidental live (legally binding) ELSTER submissions.

Live submission means: transmitting to ELSTER without the Testmerker
(``use_test=False`` together with sending). It is disabled unless the
environment variable ``FINAMT_ALLOW_LIVE_SUBMISSION`` is exactly ``"1"``.

Test submissions (Testmerker set) and local / ERiC validation are never blocked.
"""

from __future__ import annotations

import os

LIVE_SUBMISSION_ENV = "FINAMT_ALLOW_LIVE_SUBMISSION"


class LiveSubmissionDisabledError(RuntimeError):
    """Raised when a live ELSTER submission is attempted without explicit opt-in."""


def live_submission_allowed() -> bool:
    """Return True only if ``FINAMT_ALLOW_LIVE_SUBMISSION`` is set to ``"1"``."""
    return os.environ.get(LIVE_SUBMISSION_ENV, "").strip() == "1"


def require_live_submission_allowed() -> None:
    """Raise :class:`LiveSubmissionDisabledError` unless live submission is enabled."""
    if not live_submission_allowed():
        raise LiveSubmissionDisabledError(
            "Live ELSTER submission is disabled. Use test mode, or set "
            f"{LIVE_SUBMISSION_ENV}=1 to file a legally binding return."
        )
