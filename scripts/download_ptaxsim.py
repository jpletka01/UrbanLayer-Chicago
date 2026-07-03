#!/usr/bin/env python3
"""Download and decompress the PTAXSIM SQLite database from CCAO's S3 bucket."""

import bz2
import shutil
import sys
import urllib.request
from pathlib import Path

URL = "https://ccao-data-public-us-east-1.s3.amazonaws.com/ptaxsim/ptaxsim-2024.0.0.db.bz2"
DEST = Path(__file__).resolve().parent.parent / "backend" / "data" / "ptaxsim.db"
BZ2_PATH = DEST.with_suffix(".db.bz2")


def main():
    if DEST.exists():
        print(f"PTAXSIM database already exists at {DEST}")
        print(f"  Size: {DEST.stat().st_size / 1e6:.1f} MB")
        print("Delete it first if you want to re-download.")
        return

    DEST.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading PTAXSIM database (~1 GB compressed)...")
    print(f"  From: {URL}")
    print(f"  To:   {BZ2_PATH}")

    def progress(count, block_size, total_size):
        pct = count * block_size * 100 / total_size
        mb = count * block_size / 1e6
        sys.stdout.write(f"\r  {pct:.1f}% ({mb:.0f} MB)")
        sys.stdout.flush()

    urllib.request.urlretrieve(URL, BZ2_PATH, reporthook=progress)
    print()

    print("Decompressing...")
    # bz2.open (not a raw BZ2Decompressor): CCAO publishes a MULTI-STREAM bz2
    # (parallel bzip2), and a single BZ2Decompressor raises "EOFError: End of
    # stream already reached" at the first stream boundary — hit on the prod
    # seeding 2026-07-03. bz2.open transparently chains streams.
    with bz2.open(BZ2_PATH, "rb") as f_in, open(DEST, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out, 1 << 20)

    BZ2_PATH.unlink()
    print(f"Done. Database at {DEST} ({DEST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
