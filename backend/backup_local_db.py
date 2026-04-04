#!/usr/bin/env python3
"""Create timestamped backups for backend/local.db.

Usage:
  python3 backend/backup_local_db.py
  python3 backend/backup_local_db.py --keep 30
  python3 backend/backup_local_db.py --output-dir /path/to/backups
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Backup backend/local.db safely.")
    ap.add_argument(
        "--db-path",
        default=str(root / "local.db"),
        help="Path to the SQLite database file.",
    )
    ap.add_argument(
        "--output-dir",
        default=str(root / "backups"),
        help="Directory to store timestamped backup files.",
    )
    ap.add_argument(
        "--keep",
        type=int,
        default=14,
        help="How many most recent backups to keep (default: 14).",
    )
    return ap.parse_args()


def prune_backups(output_dir: Path, keep: int) -> int:
    if keep < 1:
        return 0
    backups = sorted(output_dir.glob("local-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for old_file in backups[keep:]:
        old_file.unlink(missing_ok=True)
        removed += 1
    return removed


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not db_path.is_file():
        print(f"❌ 找不到資料庫：{db_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = output_dir / f"local-{ts}.db"
    tmp_path = output_dir / f".local-{ts}.tmp"

    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(str(tmp_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    tmp_path.replace(backup_path)
    removed = prune_backups(output_dir, args.keep)

    print(f"✅ SQLite 備份完成：{backup_path}")
    if removed:
        print(f"🧹 已刪除 {removed} 個舊備份")
    print(f"📁 備份目錄：{output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
