"""Insert a batch of docs into the DB. Pass doc data as a Python list in the script."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

import json
from datetime import datetime, timezone
from lifegraph.db import init_db, upsert_document, count_documents_by_source
from lifegraph.models import Document

with open("manifest.json") as f:
    manifest = {d["id"]: d for d in json.load(f)}

init_db()

def insert(fid, title, content, mime=""):
    m = manifest.get(fid, {})
    source = "google-slides" if "presentation" in mime else "google-docs"
    doc = Document(
        id=None, title=title, source=source, source_id=fid,
        source_url=m.get("url", ""),
        created_at=m.get("modified"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_text=content,
    )
    upsert_document(doc)

def main():
    # Read the batch file
    batch_file = sys.argv[1] if len(sys.argv) > 1 else "scripts/batch_data.json"
    with open(batch_file) as f:
        docs = json.load(f)

    count = 0
    for d in docs:
        content = d.get("content", "")
        if not content or len(content) < 10:
            print(f"  SKIP: {d.get('name', '?')[:50]}")
            continue
        insert(d["file_id"], d["name"], content, d.get("mimeType", ""))
        count += 1
        print(f"  OK: {d['name'][:60]}")

    print(f"\nInserted {count} docs")
    print("DB status:", count_documents_by_source())

if __name__ == "__main__":
    main()
