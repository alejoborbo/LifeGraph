"""Process all MCP result files from tmp_mcp_results/ and insert into DB."""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

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

results_dir = Path("tmp_mcp_results")
count = 0
for f in sorted(results_dir.glob("*.json")):
    data = json.loads(f.read_text())
    content = data.get("content", "")
    if not content or len(content) < 10:
        print(f"  SKIP: {data.get('name', f.name)[:50]}")
        continue
    mime = data.get("mimeType", "")
    source = "google-slides" if "presentation" in mime else "google-docs"
    insert(data["file_id"], data["name"], content, source)
    count += 1
    print(f"  OK: {data['name'][:60]}")

print(f"\nProcessed {count} files")
print("DB:", count_documents_by_source())
