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


def test_no_reports_directory_is_not_an_error_and_makes_no_mirror(tmp_path):
    data, backups = tmp_path / "data", tmp_path / "backups"
    data.mkdir()
    make_db(data / "chicago.db")
    out = run(data / "chicago.db", backups)
    assert "mirrored" not in out and not (backups / "reports").exists()
