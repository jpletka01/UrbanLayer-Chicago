"""scripts/backup_db.sh tells the data-health checker it ran (WS6 M2)."""

import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.data_health.probes import parse_backup_status

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_db.sh"


@pytest.mark.skipif(shutil.which("sqlite3") is None, reason="the script needs the sqlite3 binary")
def test_backup_writes_a_status_file_beside_the_database(tmp_path):
    db = tmp_path / "data" / "chicago.db"
    db.parent.mkdir()
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()
    out = subprocess.run([str(SCRIPT), str(db), str(tmp_path / "bk"), "3"], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    status = db.parent / "backup_status.json"
    body = json.loads(status.read_text())
    assert body["retained"] == 1 and body["size_bytes"] > 0 and body["newest_backup"].startswith("urbanlayer_")
    assert (tmp_path / "bk" / body["newest_backup"]).exists()
    assert not (db.parent / "backup_status.json.tmp").exists()
    # and the checker's parser accepts exactly what the script wrote
    day, info, findings = parse_backup_status(body, datetime.now(timezone.utc))
    assert findings == [] and day == datetime.now(timezone.utc).date()


@pytest.mark.skipif(shutil.which("sqlite3") is None, reason="the script needs the sqlite3 binary")
def test_a_failed_backup_does_not_refresh_the_status_file(tmp_path):
    db = tmp_path / "chicago.db"          # does not exist: the script exits before writing anything
    out = subprocess.run([str(SCRIPT), str(db), str(tmp_path / "bk")], capture_output=True, text=True, timeout=30)
    assert out.returncode != 0
    assert not (tmp_path / "backup_status.json").exists()
