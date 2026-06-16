"""Isolated PDF render worker.

WeasyPrint's ``write_pdf()`` is the heaviest single step of report generation
(cairo/pango laying out the ~18-page, image-embedded feasibility report).
Measured in isolation it peaks ~118 MB (2026-06-16 prod) — modest on its own,
but run inline in the long-lived uvicorn worker it allocates against the resident
baseline (citywide discovery index + ML models) and leaves glibc-retained memory
that never returns to the OS, so its footprint ratchets the worker's RSS up
across requests. (A 6.8 GB OOM-kill was observed on this box; its trigger was the
worker's *accumulated* footprint under load, not a single render — reports were
in fact hanging upstream on the reranker and rarely reached write_pdf at all.)

Running ``write_pdf`` in a SHORT-LIVED CHILD PROCESS contains all of that:

* **Fresh address space, fully reclaimed on exit.** This — not the kill
  heuristics below — is the real protection. It flattens both the per-render
  WeasyPrint peak *and* the cross-request glibc retention (memory the long-lived
  worker frees but never returns to the OS, so its RSS only ratchets up).
* **No discovery import.** This module imports nothing from the FastAPI app or
  the ``backend.discovery`` package, and ``weasyprint`` is imported only inside
  the child entry point — so spawning the child does NOT re-load the ~3 GB parcel
  index. (``python -m backend.report_render`` only pulls the empty ``backend``
  package init + this module.)
* **oom_score_adj = 1000** makes the child the *preferred* OOM victim if the box
  is pushed over the edge. Preferred, NOT guaranteed: under a hard global OOM the
  kernel can still pick another task. Read it as "the child dies first in the
  common case," never as "the parent can't die."
* **A coarse RLIMIT_AS backstop** caps runaway virtual memory. It is deliberately
  generous: RLIMIT_AS limits *virtual* address space, which for WeasyPrint
  (mmapped fonts/libs) runs well above its RSS — a tight cap would false-kill
  legitimate renders.
* **A parent-side wall-clock timeout** stops a hung render from holding the
  report semaphore forever; the request fails cleanly while the worker stays up.

Parent entry point: ``await render_pdf(html, ...)``.
Child entry point: ``python -m backend.report_render <in_html> <out_pdf>``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# How the parent launches the child. A module-level constant so tests can swap in
# a fake child (this package's only render dep, weasyprint, isn't installed in the
# unit-test environment). The repo root is the parent of the ``backend`` package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHILD_ENTRY = [sys.executable, "-m", "backend.report_render"]

# Env var carrying the RLIMIT_AS cap from parent → child.
_RLIMIT_AS_ENV = "REPORT_RENDER_RLIMIT_AS"


class PdfRenderError(RuntimeError):
    """The isolated render child failed (timeout, nonzero exit, or no output).

    The caller turns this into a clean 5xx while the uvicorn worker stays up.
    """


async def render_pdf(
    html: str,
    *,
    timeout_s: float,
    rlimit_as_bytes: int = 0,
) -> bytes:
    """Render ``html`` to PDF bytes in an isolated child process.

    The HTML (which embeds ~30 MB of base64 map rasters) crosses the boundary via
    a temp file in / a temp file out — too large for argv or a single pipe write,
    and cheap on disk. Raises :class:`PdfRenderError` on timeout, nonzero exit, or
    a missing/invalid output file.
    """
    # mkdtemp creates the dir mode 0700 (owner-only, per the stdlib contract), so
    # the in.html / out.pdf inside it — which carry sensitive parcel/owner data —
    # are not readable by any other user. Keep it a private mkdtemp dir; don't move
    # these to a shared /tmp path.
    tmpdir = tempfile.mkdtemp(prefix="report_render_")
    in_path = os.path.join(tmpdir, "in.html")
    out_path = os.path.join(tmpdir, "out.pdf")
    try:
        with open(in_path, "w", encoding="utf-8") as fh:
            fh.write(html)

        env = dict(os.environ)
        if rlimit_as_bytes > 0:
            env[_RLIMIT_AS_ENV] = str(rlimit_as_bytes)

        try:
            proc = await asyncio.create_subprocess_exec(
                *_CHILD_ENTRY, in_path, out_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_REPO_ROOT),
                env=env,
            )
        except OSError as exc:
            # Spawn itself failed before any child ran — bad interpreter path,
            # cwd/exec perms, or fork/thread limits. A distinct outcome from a child
            # that started and exited nonzero; surface it as PdfRenderError (→ 503)
            # rather than letting the OSError escape as an unhandled 500.
            raise PdfRenderError(f"PDF render failed to spawn: {exc}") from exc

        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise PdfRenderError(
                f"PDF render exceeded {timeout_s:.0f}s budget"
            ) from None

        if proc.returncode != 0:
            tail = (stderr or b"").decode("utf-8", "replace").strip()[-2000:]
            raise PdfRenderError(
                f"PDF render child exited {proc.returncode}: {tail or '(no stderr)'}"
            )

        try:
            with open(out_path, "rb") as fh:
                pdf = fh.read()
        except OSError as exc:
            raise PdfRenderError(f"PDF render produced no output: {exc}") from exc

        if not pdf.startswith(b"%PDF"):
            raise PdfRenderError("PDF render produced invalid output (not a PDF)")
        return pdf
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _child_main(in_path: str, out_path: str) -> int:
    """Child entry point: become the preferred OOM victim, cap VM, render, write.

    Imports ``weasyprint`` *only here* so the parent's import of this module stays
    free of the heavy cairo/pango stack.
    """
    # Volunteer as the preferred OOM victim. An unprivileged process may *raise*
    # its own oom_score_adj (toward more-killable); only lowering needs privilege.
    try:
        with open("/proc/self/oom_score_adj", "w") as fh:
            fh.write("1000")
    except OSError:
        pass  # non-Linux / restricted /proc — isolation still holds, just no hint.

    # Coarse virtual-memory backstop. Generous on purpose (see module docstring:
    # RLIMIT_AS caps VM, not RSS). Set before importing weasyprint so a runaway
    # import is also bounded; the cap must comfortably exceed a real render's VM.
    rlimit_as = int(os.environ.get(_RLIMIT_AS_ENV, "0") or "0")
    if rlimit_as > 0:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (rlimit_as, rlimit_as))
        except (ValueError, OSError):
            pass

    from weasyprint import HTML

    with open(in_path, "r", encoding="utf-8") as fh:
        html = fh.read()
    pdf = HTML(string=html).write_pdf()
    with open(out_path, "wb") as fh:
        fh.write(pdf)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python -m backend.report_render <in_html> <out_pdf>", file=sys.stderr)
        sys.exit(2)
    sys.exit(_child_main(sys.argv[1], sys.argv[2]))
