"""Ingest ALL tool results from ALL Claude conversation sessions into the DB."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

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


def process_file(filepath):
    """Try to parse a tool result file and extract doc content."""
    try:
        with open(filepath) as f:
            raw = f.read().strip()
        if not raw:
            return None
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    # get_file_content result format
    if isinstance(data, dict) and "file_id" in data and "content" in data:
        mime = data.get("mimeType", "")
        source = "google-slides" if "presentation" in mime else "google-docs"
        return (data["file_id"], data.get("name", ""), data["content"], source)

    # read_document result format
    if isinstance(data, dict) and "documentId" in data and "tabs" in data:
        texts = []
        for tab in data.get("tabs", []):
            body = tab.get("documentTab", {}).get("body", {})
            for element in body.get("content", []):
                para = element.get("paragraph", {})
                for el in para.get("elements", []):
                    text_run = el.get("textRun", {})
                    content = text_run.get("content", "")
                    if content:
                        texts.append(content)
        text = "".join(texts).strip()
        return (data["documentId"], data.get("title", ""), text, "google-docs")

    return None


def main():
    base = os.path.expanduser(
        "~/.claude/projects/-Users-capucine-marteau-Documents-Perso-LifeGraph/"
    )

    result_files = []
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".txt") and "tool-results" in root:
                result_files.append(os.path.join(root, f))

    print(f"Found {len(result_files)} tool result files")

    count = 0
    seen = set()
    for filepath in sorted(result_files):
        result = process_file(filepath)
        if result is None:
            continue
        file_id, title, content, source = result
        if not content or len(content) < 50:
            continue
        if file_id in seen:
            continue
        seen.add(file_id)

        insert(file_id, title, content, source)
        count += 1
        print(f"  OK: {title[:60]}")

    print(f"\nInserted {count} docs from tool results")
    print("DB:", count_documents_by_source())


if __name__ == "__main__":
    main()
