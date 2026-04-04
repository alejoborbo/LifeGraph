"""Insert a single doc. Usage: python insert_one.py <file_id> <content_file>"""
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
    print(f"  OK: {title[:60]}")

if __name__ == "__main__":
    fid = sys.argv[1]
    content_file = sys.argv[2]
    with open(content_file) as f:
        data = json.load(f)
    title = data.get("name", "")
    content = data.get("content", "")
    mime = data.get("mimeType", "")
    source = "google-slides" if "presentation" in mime else "google-docs"
    insert(fid, title, content, source)
    print("DB status:", count_documents_by_source())
