"""Backs up the database, then drops the unused `bypass` column that a pre-release 1.3.2 build added.

Optional: the 1.3.2 app opens such a database as it is (schema 11 is a no-op migration), and nothing
reads the column. Usage: python tidy-database.py <database file>   (the backend must be stopped)
"""

import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1])
if not db.is_file():
    sys.exit(f"No database at {db}")
conn = sqlite3.connect(db)
conn.execute("PRAGMA busy_timeout=5000")
columns = [r[1] for r in conn.execute("PRAGMA table_info(responder)")]
if "bypass" not in columns:
    print("Nothing to do: the responder table has no bypass column.")
    sys.exit(0)
backup = db.with_name(db.name + ".pre-1.3.2.bak")
if backup.exists():
    sys.exit(f"{backup.name} already exists; move it away first so a backup is never overwritten.")
out = sqlite3.connect(backup)
conn.backup(out)
out.close()
print(f"Backup written: {backup.name}")
conn.execute("BEGIN IMMEDIATE")
conn.execute("ALTER TABLE responder DROP COLUMN bypass")
conn.execute("COMMIT")
print("Dropped responder.bypass. Schema version is unchanged (11).")
