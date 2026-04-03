"""Update document content in the DB. Reads JSON from stdin: [{"db_id": int, "content": str}, ...]"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "lifegraph.db"

def main():
    data = json.load(sys.stdin)
    conn = sqlite3.connect(str(DB_PATH))
    count = 0
    for entry in data:
        db_id = entry["db_id"]
        content = entry["content"]
        if not content or len(content) < 50:
            continue
        conn.execute("UPDATE documents SET raw_text = ? WHERE id = ?", (content, db_id))
        count += 1
    conn.commit()
    conn.close()
    print(f"Updated {count} documents")

if __name__ == "__main__":
    main()
