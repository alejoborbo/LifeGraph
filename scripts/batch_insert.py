"""Insert document content directly into the DB. Called with JSON on stdin."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.db import init_db, upsert_document
from lifegraph.models import Document

# Load manifest for URLs and modified dates
with open(Path(__file__).parent.parent / "manifest.json") as f:
    manifest = {d["id"]: d for d in json.load(f)}


def insert_doc(file_id: str, title: str, content: str, source: str = "google-docs"):
    m = manifest.get(file_id, {})
    url = m.get("url", f"https://docs.google.com/document/d/{file_id}")
    created_at = m.get("modified")
    doc = Document(
        id=None,
        title=title,
        source=source,
        source_id=file_id,
        source_url=url,
        created_at=created_at,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        raw_text=content,
    )
    upsert_document(doc)


def main():
    """Read JSON array from stdin: [{"file_id": ..., "name": ..., "content": ..., "mimeType": ...}, ...]"""
    init_db()
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        data = [data]

    count = 0
    for item in data:
        file_id = item.get("file_id", "")
        title = item.get("name", "")
        content = item.get("content", "")
        mime = item.get("mimeType", "")

        if not content or len(content) < 10:
            print(f"  SKIP (empty): {title[:60]}")
            continue

        source = "google-slides" if "presentation" in mime else "google-docs"
        insert_doc(file_id, title, content, source)
        count += 1
        print(f"  OK: {title[:60]}")

    print(f"\nInserted {count} docs")


if __name__ == "__main__":
    main()
