"""Parent-side orchestration tests for the isolated PDF render worker.

These exercise `render_pdf()`'s contract — success passthrough, and clean
`PdfRenderError` on timeout / nonzero exit / missing or invalid output — without
the real WeasyPrint child (cairo/pango isn't installed in the unit-test env). We
swap `_CHILD_ENTRY` for a tiny inline Python child that simulates each outcome.
The child receives (in_path, out_path) as its trailing argv, same as the real one.
"""

import os
import sys

import pytest

import backend.report_render as rr
from backend.report_render import PdfRenderError, render_pdf


def _fake_child(script: str) -> list[str]:
    """A `_CHILD_ENTRY` that runs `script` via `python -c`. argv[1]/argv[2] are the
    in/out paths render_pdf appends."""
    return [sys.executable, "-c", script]


@pytest.mark.asyncio
async def test_render_pdf_returns_child_output(monkeypatch):
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        _fake_child("import sys; open(sys.argv[2], 'wb').write(b'%PDF-1.4 ok\\n')"),
    )
    out = await render_pdf("<html><body>hi</body></html>", timeout_s=10)
    assert out.startswith(b"%PDF")
    assert out == b"%PDF-1.4 ok\n"


@pytest.mark.asyncio
async def test_render_pdf_passes_html_to_child(monkeypatch):
    # Child copies its input HTML through to the output, proving the temp-file
    # hand-off carries the parent's HTML into the isolated process.
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        _fake_child(
            "import sys;"
            "html=open(sys.argv[1]).read();"
            "open(sys.argv[2],'wb').write(b'%PDF-1.4 '+html.encode())"
        ),
    )
    out = await render_pdf("MARKER-123", timeout_s=10)
    assert b"MARKER-123" in out


@pytest.mark.asyncio
async def test_render_pdf_timeout_raises(monkeypatch):
    monkeypatch.setattr(rr, "_CHILD_ENTRY", _fake_child("import time; time.sleep(30)"))
    with pytest.raises(PdfRenderError, match="exceeded"):
        await render_pdf("<html></html>", timeout_s=0.3)


@pytest.mark.asyncio
async def test_render_pdf_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        _fake_child("import sys; sys.stderr.write('boom'); sys.exit(3)"),
    )
    with pytest.raises(PdfRenderError, match="exited 3"):
        await render_pdf("<html></html>", timeout_s=10)


@pytest.mark.asyncio
async def test_render_pdf_missing_output_raises(monkeypatch):
    # Child exits 0 but writes nothing → no output file.
    monkeypatch.setattr(rr, "_CHILD_ENTRY", _fake_child("import sys; sys.exit(0)"))
    with pytest.raises(PdfRenderError, match="no output"):
        await render_pdf("<html></html>", timeout_s=10)


@pytest.mark.asyncio
async def test_render_pdf_invalid_output_raises(monkeypatch):
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        _fake_child("import sys; open(sys.argv[2],'wb').write(b'NOT-A-PDF')"),
    )
    with pytest.raises(PdfRenderError, match="invalid output"):
        await render_pdf("<html></html>", timeout_s=10)


@pytest.mark.asyncio
async def test_render_pdf_spawn_failure_raises(monkeypatch):
    # The spawn itself fails (interpreter path doesn't exist) — a DISTINCT failure
    # mode from a child that ran and exited nonzero. Must surface as a clean
    # PdfRenderError (→ 503), never an unhandled OSError (→ 500) or a hang.
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        ["/nonexistent/python-xyz", "-m", "backend.report_render"],
    )
    with pytest.raises(PdfRenderError, match="failed to spawn"):
        await render_pdf("<html></html>", timeout_s=10)


@pytest.mark.asyncio
async def test_render_pdf_cleans_tempdir_on_failure(monkeypatch):
    # No /tmp leak when the child exits nonzero: the in.html / out.pdf temp dir is
    # removed on the failure path too.
    seen = {}
    real_mkdtemp = rr.tempfile.mkdtemp
    monkeypatch.setattr(
        rr.tempfile, "mkdtemp",
        lambda *a, **k: seen.setdefault("dir", real_mkdtemp(*a, **k)),
    )
    monkeypatch.setattr(rr, "_CHILD_ENTRY", _fake_child("import sys; sys.exit(5)"))
    with pytest.raises(PdfRenderError):
        await render_pdf("<html></html>", timeout_s=10)
    assert seen["dir"] and not os.path.exists(seen["dir"])


@pytest.mark.asyncio
async def test_render_pdf_cleans_tempdir_on_timeout(monkeypatch):
    # The concern that can't be unit-tested any other way: on the timeout/kill()
    # path, BOTH temp files (HTML in, partial PDF out) are cleaned up — no leak.
    seen = {}
    real_mkdtemp = rr.tempfile.mkdtemp
    monkeypatch.setattr(
        rr.tempfile, "mkdtemp",
        lambda *a, **k: seen.setdefault("dir", real_mkdtemp(*a, **k)),
    )
    # Child writes a partial out.pdf, then hangs past the budget → parent kills it.
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        _fake_child(
            "import sys,time; open(sys.argv[2],'wb').write(b'partial'); time.sleep(30)"
        ),
    )
    with pytest.raises(PdfRenderError, match="exceeded"):
        await render_pdf("<html></html>", timeout_s=0.3)
    assert seen["dir"] and not os.path.exists(seen["dir"])


@pytest.mark.asyncio
async def test_render_pdf_tempdir_is_owner_only(monkeypatch):
    # Sensitive parcel/owner data lives in the temp files; confirm the containing
    # dir is mode 0700 so no other user can read them.
    seen = {}
    real_mkdtemp = rr.tempfile.mkdtemp

    def _spy(*a, **k):
        d = real_mkdtemp(*a, **k)
        seen["mode"] = os.stat(d).st_mode & 0o777
        return d

    monkeypatch.setattr(rr.tempfile, "mkdtemp", _spy)
    monkeypatch.setattr(
        rr, "_CHILD_ENTRY",
        _fake_child("import sys; open(sys.argv[2],'wb').write(b'%PDF-1.4 ok')"),
    )
    await render_pdf("<html></html>", timeout_s=10)
    assert seen["mode"] == 0o700


@pytest.mark.asyncio
async def test_render_pdf_forwards_rlimit_env(monkeypatch):
    # When a cap is set, the child sees it in the environment; when 0, it doesn't.
    script = (
        "import os,sys;"
        "open(sys.argv[2],'wb').write(b'%PDF-1.4 '+os.environ.get('REPORT_RENDER_RLIMIT_AS','none').encode())"
    )
    monkeypatch.setattr(rr, "_CHILD_ENTRY", _fake_child(script))
    out = await render_pdf("<html></html>", timeout_s=10, rlimit_as_bytes=1234567)
    assert b"1234567" in out

    out2 = await render_pdf("<html></html>", timeout_s=10, rlimit_as_bytes=0)
    assert b"none" in out2
