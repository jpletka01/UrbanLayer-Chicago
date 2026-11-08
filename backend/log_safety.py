"""Newline scrubbing for log records.

CodeQL flags ~23 `py/log-injection` sites: user-controlled strings (a typed
address, a chat message, a Stripe id, a zoning query) reaching `log.*` calls. The
risk is log FORGERY — an attacker embeds CR/LF in the value and writes what looks
like an additional, authentic log line, muddying an incident timeline or hiding
activity from anyone grepping the output.

Fixed centrally with one filter rather than at each call site. Editing 23 call
sites would be churn that the 24th new one silently escapes; a filter on the root
handlers covers every logger in the process, including third-party ones we don't
control, and cannot be forgotten.

Escapes rather than strips, so the value stays readable and no information is
lost: a literal "a\\nb" logs as `a\\nb` on one line.
"""

from __future__ import annotations

import logging

_TRANSLATE = {ord("\r"): "\\r", ord("\n"): "\\n"}


def _scrub(value):
    # Only str is a forgery vector. Anything else is left completely alone —
    # notably exceptions, whose formatting/traceback rendering must not change.
    if isinstance(value, str):
        return value.translate(_TRANSLATE)
    return value


class NoCRLFFilter(logging.Filter):
    """Escape CR/LF in a record's message and its interpolation args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _scrub(record.msg)
        args = record.args
        if args:
            # %-style logging passes either a tuple or a single mapping.
            if isinstance(args, dict):
                record.args = {k: _scrub(v) for k, v in args.items()}
            else:
                record.args = tuple(_scrub(a) for a in args)
        return True  # a filter that scrubs, never one that drops


LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"


def configure(level: int = logging.INFO) -> None:
    """Give the root logger a stderr handler and let the app's own loggers (``backend.*``) log at ``level``.

    Uvicorn configures only its own loggers, so before this the root logger had no handler: the app's
    warnings reached stderr through Python's last-resort handler (WARNING and up, no filters), every
    ``log.info`` line (the Profile's ``scorecard timings``, Item 81) was dropped, and :func:`install` found
    no handler to protect. Libraries stay at the root's WARNING. Idempotent; call before :func:`install`.
    """
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    logging.getLogger("backend").setLevel(level)


def install(logger: logging.Logger | None = None) -> None:
    """Attach the filter to every handler on the root (or given) logger.

    Handlers, not the logger: a filter on a logger only sees records logged
    directly to it, while a handler filter sees everything that propagates up —
    which is how library loggers reach us.

    Idempotent, so repeated startup calls (reload, tests) can't stack filters.
    """
    root = logger or logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, NoCRLFFilter) for f in handler.filters):
            handler.addFilter(NoCRLFFilter())
