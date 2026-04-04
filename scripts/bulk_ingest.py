"""Bulk ingest: insert all remaining manifest docs with whatever content we have.
For docs where we have persisted MCP results, use the full content.
For other docs, insert with source/metadata so the DB at least knows about them.
Then fetch remaining docs content via the MCP tool results directory."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

from lifegraph.db import init_db, upsert_document, count_documents_by_source
from lifegraph.models import Document
import sqlite3
from lifegraph.config import DATABASE_PATH

init_db()

with open("manifest.json") as f:
    manifest_list = json.load(f)
    manifest = {d["id"]: d for d in manifest_list}

# Get current DB state
conn = sqlite3.connect(str(DATABASE_PATH))
existing = {}
for row in conn.execute("SELECT source_id, LENGTH(raw_text) as l FROM documents").fetchall():
    existing[row[0]] = row[1]
conn.close()

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

# Step 1: Process ALL persisted tool results
base = os.path.expanduser(
    "~/.claude/projects/-Users-capucine-marteau-Documents-Perso-LifeGraph/"
)
result_files = []
for root, dirs, files in os.walk(base):
    for f in files:
        if f.endswith(".txt") and "tool-results" in root:
            result_files.append(os.path.join(root, f))

persisted_count = 0
for filepath in result_files:
    try:
        with open(filepath) as f:
            raw = f.read().strip()
        if not raw:
            continue
        data = json.loads(raw)
        if isinstance(data, dict) and "file_id" in data and "content" in data:
            content = data["content"]
            if content and len(content) >= 50:
                fid = data["file_id"]
                # Only update if we have better content
                if fid not in existing or existing[fid] < len(content):
                    mime = data.get("mimeType", "")
                    source = "google-slides" if "presentation" in mime else "google-docs"
                    insert(fid, data.get("name", ""), content, source)
                    existing[fid] = len(content)
                    persisted_count += 1
                    print(f"  PERSISTED: {data.get('name', '')[:50]}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        continue

# Also process tmp_mcp_results if they exist
tmp_dir = Path("tmp_mcp_results")
if tmp_dir.exists():
    for f in tmp_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            content = data.get("content", "")
            if content and len(content) >= 50:
                fid = data["file_id"]
                if fid not in existing or existing[fid] < len(content):
                    mime = data.get("mimeType", "")
                    source = "google-slides" if "presentation" in mime else "google-docs"
                    insert(fid, data.get("name", ""), content, source)
                    existing[fid] = len(content)
                    persisted_count += 1
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

print(f"\nInserted/updated {persisted_count} docs from persisted results")

# Step 2: For all manifest entries not yet in DB, insert metadata (with empty content placeholder)
# This ensures the DB knows about all docs
metadata_count = 0
for entry in manifest_list:
    fid = entry["id"]
    if fid not in existing:
        source = entry.get("source", "google-docs")
        insert(fid, entry["name"], "[content not yet fetched]", source)
        existing[fid] = 0
        metadata_count += 1

print(f"Inserted {metadata_count} metadata-only entries")
print("\nFinal DB status:", count_documents_by_source())

# Summary
conn = sqlite3.connect(str(DATABASE_PATH))
total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
with_content = conn.execute("SELECT COUNT(*) FROM documents WHERE LENGTH(raw_text) > 100").fetchone()[0]
print(f"Total: {total}, With real content: {with_content}")
conn.close()
