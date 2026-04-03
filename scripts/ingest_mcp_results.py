"""Ingest docs from persisted MCP tool results into the SQLite DB."""
import json
import glob
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.db import init_db, upsert_document, count_documents_by_source
from lifegraph.models import Document

# Load manifest for URLs
with open(Path(__file__).parent.parent / "manifest.json") as f:
    manifest = {d["id"]: d for d in json.load(f)}


def extract_text_from_docs_json(data):
    """Extract plain text from Google Docs API JSON (read_document result)."""
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
                person = el.get("person", {})
                if person:
                    props = person.get("personProperties", {})
                    texts.append(props.get("name", ""))
            # Also extract table content
            table = element.get("table", {})
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for cell_content in cell.get("content", []):
                        cell_para = cell_content.get("paragraph", {})
                        for cel in cell_para.get("elements", []):
                            tr = cel.get("textRun", {})
                            if tr.get("content"):
                                texts.append(tr["content"])
    return "".join(texts).strip()


def process_file(filepath):
    """Process a single MCP result file and return (file_id, title, content, source) or None."""
    with open(filepath) as f:
        data = json.load(f)

    # get_file_content result
    if isinstance(data, dict) and "file_id" in data and "content" in data:
        mime = data.get("mimeType", "")
        source = "google-slides" if "presentation" in mime else "google-docs"
        return (data["file_id"], data["name"], data["content"], source)

    # read_document result
    if isinstance(data, dict) and "documentId" in data and "tabs" in data:
        text = extract_text_from_docs_json(data)
        return (data["documentId"], data["title"], text, "google-docs")

    return None


def main():
    results_dir = os.path.expanduser(
        "~/.claude/projects/-Users-capucine-marteau-Documents-Perso-LifeGraph/"
    )
    # Find all tool result dirs
    result_files = []
    for root, dirs, files in os.walk(results_dir):
        for f in files:
            if f.endswith(".txt") and "tool-results" in root:
                result_files.append(os.path.join(root, f))

    init_db()
    count = 0

    for filepath in sorted(result_files):
        result = process_file(filepath)
        if result is None:
            continue

        file_id, title, content, source = result
        if not content or len(content) < 50:
            continue

        m = manifest.get(file_id, {})
        url = m.get("url", f"https://docs.google.com/document/d/{file_id}")

        doc = Document(
            id=None,
            title=title,
            source=source,
            source_id=file_id,
            source_url=url,
            created_at=m.get("modified"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_text=content,
        )
        upsert_document(doc)
        count += 1
        print(f"  OK: {title[:60]}")

    print(f"\nInserted {count} docs from persisted results")
    print("DB status:", count_documents_by_source())


if __name__ == "__main__":
    main()
