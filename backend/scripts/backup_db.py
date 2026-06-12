"""Back up the parts-library SQLite database.

Uses SQLite's online backup API, so it's safe to run while the app is
serving requests. Keeps the most recent ``--keep`` backups in the
destination directory and deletes older ones.

Usage:
    python backup_db.py /path/to/backup/dir [--keep 14]
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "parts.db"


def backup(destination_dir: Path, keep: int) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest_path = destination_dir / f"parts-{timestamp}.db"

    source = sqlite3.connect(DB_PATH)
    target = sqlite3.connect(dest_path)
    with target:
        source.backup(target)
    target.close()
    source.close()

    backups = sorted(destination_dir.glob("parts-*.db"))
    for old in backups[:-keep]:
        old.unlink()

    return dest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="directory to write backups into")
    parser.add_argument("--keep", type=int, default=14, help="number of backups to retain (default: 14)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        sys.exit(f"Database not found at {DB_PATH}")

    dest_path = backup(args.destination, args.keep)
    print(f"Backed up {DB_PATH} -> {dest_path}")


if __name__ == "__main__":
    main()
