"""Tests for CR/LF scrubbing on log records (backend/log_safety.py).

Guards against log FORGERY: a user-controlled value containing a newline that
renders as an extra, authentic-looking log line.
"""

import io
import logging

import pytest

from backend.log_safety import NoCRLFFilter, install


@pytest.fixture
def logger_and_buffer():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    log = logging.getLogger(f"test_log_safety_{id(buf)}")
    log.handlers = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False
    install(log)
    return log, buf


def test_escapes_a_forged_line_in_an_interpolated_arg(logger_and_buffer):
    log, buf = logger_and_buffer
    log.info("geocode failed for %s", "123 Main\nINFO: admin login succeeded")
    out = buf.getvalue()
    assert "\\n" in out
    # The forged text survives as readable content but cannot start its own line.
    assert "\nINFO: admin login succeeded" not in out
    assert len(out.strip().splitlines()) == 1


def test_escapes_carriage_returns(logger_and_buffer):
    log, buf = logger_and_buffer
    log.info("value=%s", "a\rb")
    assert "\\r" in buf.getvalue()


def test_escapes_the_message_itself_not_just_args(logger_and_buffer):
    log, buf = logger_and_buffer
    log.info("multi\nline literal")
    assert len(buf.getvalue().strip().splitlines()) == 1


def test_handles_dict_style_interpolation(logger_and_buffer):
    log, buf = logger_and_buffer
    log.info("addr %(a)s", {"a": "x\ny"})
    assert "\\n" in buf.getvalue()


def test_leaves_clean_messages_untouched(logger_and_buffer):
    log, buf = logger_and_buffer
    log.info("parcel %s resolved to %s", "1601 N Milwaukee", "14313320180000")
    assert buf.getvalue().strip() == "parcel 1601 N Milwaukee resolved to 14313320180000"


def test_leaves_non_string_args_alone(logger_and_buffer):
    """Numbers and exceptions must pass through untouched — traceback rendering
    depends on the exception object, not a scrubbed copy."""
    log, buf = logger_and_buffer
    log.info("count=%d ratio=%.2f err=%s", 42, 1.5, ValueError("boom"))
    assert buf.getvalue().strip() == "count=42 ratio=1.50 err=boom"


def test_exception_tracebacks_still_render(logger_and_buffer):
    log, buf = logger_and_buffer
    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        log.exception("failed while doing %s", "work")
    out = buf.getvalue()
    assert "Traceback (most recent call last)" in out
    assert "RuntimeError: kaboom" in out


def test_filter_never_drops_records(logger_and_buffer):
    log, buf = logger_and_buffer
    for i in range(5):
        log.info("msg %d", i)
    assert len(buf.getvalue().strip().splitlines()) == 5


def test_install_is_idempotent():
    """Startup can run more than once (reload, tests); filters must not stack."""
    handler = logging.StreamHandler(io.StringIO())
    log = logging.getLogger("test_log_safety_idempotent")
    log.handlers = [handler]
    for _ in range(3):
        install(log)
    assert sum(isinstance(f, NoCRLFFilter) for f in handler.filters) == 1
