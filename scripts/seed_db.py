"""Seed the SQLite DB from collected MCP content."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.db import init_db, upsert_document
from lifegraph.models import Document


def seed(collected_path: str):
    init_db()
    with open(collected_path) as f:
        docs = json.load(f)

    for d in docs:
        doc = Document(
            id=None,
            title=d["name"],
            source=d["source"],
            source_id=d["file_id"],
            source_url=d["url"],
            created_at=d.get("modified"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_text=d["content"],
        )
        upsert_document(doc)
        print(f"  ✓ {doc.title[:60]}")

    print(f"\nSeeded {len(docs)} documents.")


if __name__ == "__main__":
    seed(sys.argv[1] if len(sys.argv) > 1 else "collected.json")
