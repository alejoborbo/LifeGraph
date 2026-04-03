"""Add a single doc to the DB from stdin content."""
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.db import init_db, upsert_document
from lifegraph.models import Document

init_db()

data = json.load(sys.stdin)
doc = Document(
    id=None,
    title=data["name"],
    source="google-slides" if "presentation" in data.get("mimeType", "") else "google-docs",
    source_id=data["file_id"],
    source_url=f"https://docs.google.com/document/d/{data['file_id']}",
    created_at=None,
    fetched_at=datetime.now(timezone.utc).isoformat(),
    raw_text=data["content"],
)
upsert_document(doc)
print(f"OK: {doc.title[:60]}")
