"""Insert docs from JSON on stdin. Each line is a JSON object with file_id, name, content, mimeType."""
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

def insert(fid, title, content, source="google-docs"):
    m = manifest.get(fid, {})
    doc = Document(
        id=None, title=title, source=source, source_id=fid,
        source_url=m.get("url", ""),
        created_at=m.get("modified"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_text=content,
    )
    upsert_document(doc)

if __name__ == "__main__":
    raw = sys.stdin.read()
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]

    count = 0
    for d in data:
        content = d.get("content", "")
        if not content or len(content) < 10:
            print(f"  SKIP: {d.get('name', '?')[:50]}")
            continue
        mime = d.get("mimeType", "")
        source = "google-slides" if "presentation" in mime else "google-docs"
        insert(d["file_id"], d["name"], content, source)
        count += 1
        print(f"  OK: {d['name'][:60]}")

    print(f"\nInserted {count} docs")
    print("DB:", count_documents_by_source())
