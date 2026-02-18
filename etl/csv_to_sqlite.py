import pandas as pd
import sqlite3
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

now_utc = datetime.now(timezone.utc).isoformat(timespec='seconds')
DB_PATH = '../database/warehouse.db'
CSV_DIRS = [
    Path('../raw_data/')
]

def safe_table_name(name: str) -> str:
    base = Path(name).stem.lower()
    base = re.sub(r'[^a-z0-9_]', '_', base)

    if base[0].isdigit():
        base = f"t_{base}"
    return base

with sqlite3.connect(DB_PATH) as conn:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
                    table_name TEXT PRIMARY KEY,
                    source_file TEXT,
                    last_updated_utc TEXT,
                    row_count INTEGER)
    """)

    for csv_dir in CSV_DIRS:
        for csv_path in csv_dir.glob("*.csv"):
            table = safe_table_name(f"{csv_dir.name}_{csv_path.name}")
            df = pd.read_csv(csv_path)

            df.to_sql(table, conn, if_exists='replace', index=False)

            conn.execute("""
                INSERT OR REPLACE INTO metadata (table_name, source_file, last_updated_utc, row_count)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(table_name) DO UPDATE SET
                    source_file = excluded.last_updated_utc,
                    last_updated_utc = excluded.last_updated_utc,
                    row_count = excluded.row_count
            """, (table, csv_path.name, now_utc, len(df)))

        conn.commit()

print(
    f"Done. Loaded {len(list(csv_dir.glob('*.csv')))} CSV files into {DB_PATH}. "
    f"Updated on {now_utc}"
    )