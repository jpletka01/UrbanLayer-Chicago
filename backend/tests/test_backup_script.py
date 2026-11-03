"""WS6 M8: the nightly backup also mirrors the stored report originals, append-only.

Runs scripts/backup_db.sh for real against a temp database and a temp reports directory (the script needs the
sqlite3 command; the test is skipped where it is missing).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_db.sh"
pytestmark = pytest.mark.skipif(shutil.which("sqlite3") is None, reason="sqlite3 CLI not installed")


def run(db: Path, backups: Path) -> str:
    out = subprocess.run(["bash", str(SCRIPT), str(db), str(backups), "3"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout


def make_db(path: Path) -> None:
    subprocess.run(["sqlite3", str(path), "create table t(x); insert into t values (1);"], check=True)


def test_originals_are_mirrored_next_to_the_database_backup(tmp_path):
    data, backups = tmp_path / "data", tmp_path / "backups"
    (data / "reports" / "7").mkdir(parents=True)
    make_db(data / "chicago.db")
    (data / "reports" / "7" / "1.pdf").write_bytes(b"%PDF original")
    out = run(data / "chicago.db", backups)
    assert "Report originals mirrored: 1 PDFs" in out
    assert (backups / "reports" / "7" / "1.pdf").read_bytes() == b"%PDF original"
    assert list(backups.glob("urbanlayer_*.db"))  # the database backup is unchanged


def test_the_mirror_is_append_only_a_damaged_original_never_replaces_its_good_copy(tmp_path):
    data, backups = tmp_path / "data", tmp_path / "backups"
    (data / "reports" / "7").mkdir(parents=True)
    make_db(data / "chicago.db")
    pdf = data / "reports" / "7" / "1.pdf"
    pdf.write_bytes(b"%PDF original")
    run(data / "chicago.db", backups)
    pdf.write_bytes(b"%PDF damaged")           # the live copy goes bad
    (data / "reports" / "8").mkdir()
    (data / "reports" / "8" / "2.pdf").write_bytes(b"%PDF second")
    run(data / "chicago.db", backups)
    assert (backups / "reports" / "7" / "1.pdf").read_bytes() == b"%PDF original"   # kept
    assert (backups / "reports" / "8" / "2.pdf").read_bytes() == b"%PDF second"     # new ones still arrive
    pdf.unlink()                                  # and a deleted live file is not deleted from the mirror
    run(data / "chicago.db", backups)
    assert (backups / "reports" / "7" / "1.pdf").exists()


def test_no_reports_directory_is_not_an_error_and_leaves_an_empty_mirror(tmp_path):
    """Before the first purchase there is nothing to mirror, but the mirror dir exists, so the off-box pull of
    ./reports/ (scripts/pull_backups.sh) reads an empty folder instead of failing every run."""
    data, backups = tmp_path / "data", tmp_path / "backups"
    data.mkdir()
    make_db(data / "chicago.db")
    out = run(data / "chicago.db", backups)
    assert "mirrored" not in out and (backups / "reports").is_dir() and not any((backups / "reports").iterdir())


def make_listing_db(path: Path, listed: list[str]) -> None:
    rows = "; ".join(f"insert into report_renders values ('original', '{p}')" for p in listed)
    subprocess.run(["sqlite3", str(path), f"create table report_renders(kind text, pdf_path text); {rows};"], check=True)


def test_a_deleted_accounts_original_leaves_the_mirror(tmp_path):
    """Decision Item 63 (Jack, 2026-11-03): account deletion removes the PDF and its row; the mirror follows."""
    data, backups = tmp_path / "data", tmp_path / "backups"
    for rel in ("7/1.pdf", "8/2.pdf"):
        (data / "reports" / rel).parent.mkdir(parents=True, exist_ok=True)
        (data / "reports" / rel).write_bytes(b"%PDF")
    make_listing_db(data / "chicago.db", ["7/1.pdf", "8/2.pdf"])
    run(data / "chicago.db", backups)
    assert (backups / "reports" / "8" / "2.pdf").exists()
    # account 8 is deleted: its PDF and its render row go
    (data / "reports" / "8" / "2.pdf").unlink()
    subprocess.run(["sqlite3", str(data / "chicago.db"), "delete from report_renders where pdf_path = '8/2.pdf';"], check=True)
    out = run(data / "chicago.db", backups)
    assert "removed from the mirror: 1" in out
    assert not (backups / "reports" / "8").exists()
    assert (backups / "reports" / "7" / "1.pdf").exists()


def test_a_prune_larger_than_the_cap_removes_nothing(tmp_path):
    data, backups = tmp_path / "data", tmp_path / "backups"
    (data / "reports" / "7").mkdir(parents=True)
    for i in range(12):
        (data / "reports" / "7" / f"{i}.pdf").write_bytes(b"%PDF")
    make_listing_db(data / "chicago.db", [f"7/{i}.pdf" for i in range(12)])
    run(data / "chicago.db", backups)
    subprocess.run(["sqlite3", str(data / "chicago.db"), "delete from report_renders;"], check=True)
    out = subprocess.run(["bash", str(SCRIPT), str(data / "chicago.db"), str(backups), "3"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0
    assert "nothing pruned" in out.stderr
    assert len(list((backups / "reports" / "7").glob("*.pdf"))) == 12
