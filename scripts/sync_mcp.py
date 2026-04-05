#!/usr/bin/env python3
"""Sync documents into LifeGraph from MCP tool output files.

Usage — run from Claude Code:
  1. Claude Code fetches docs via MCP tools and writes JSON to scripts/mcp_output/
  2. Then run: python scripts/sync_mcp.py

This avoids needing API tokens or OAuth — the MCPs handle auth.
"""
import json
import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.db import init_db, upsert_document, count_documents_by_source
from lifegraph.models import Document

OUTPUT_DIR = Path(__file__).parent / "mcp_output"


def strip_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ingest_google_docs():
    """Ingest Google Docs from MCP output."""
    path = OUTPUT_DIR / "google_docs.json"
    if not path.exists():
        return 0
    docs = json.loads(path.read_text())
    count = 0
    for d in docs:
        text = d.get("content", "")
        if not text or len(text) < 50:
            continue
        doc = Document(
            id=None,
            title=d["title"],
            source="google_docs",
            source_id=d["id"],
            source_url=d.get("url", f"https://docs.google.com/document/d/{d['id']}"),
            created_at=d.get("created_at") or d.get("modifiedTime"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_text=text,
            author=d.get("author"),
        )
        upsert_document(doc)
        count += 1
        print(f"  [gdoc] {d['title'][:60]}")
    return count


def ingest_confluence():
    """Ingest Confluence pages from MCP output."""
    path = OUTPUT_DIR / "confluence_pages.json"
    if not path.exists():
        return 0
    pages = json.loads(path.read_text())
    count = 0
    for p in pages:
        raw = p.get("html", "") or p.get("content", "")
        text = strip_html(raw) if "<" in raw else raw
        if not text or len(text) < 50:
            continue
        doc = Document(
            id=None,
            title=p["title"],
            source="confluence",
            source_id=str(p["id"]),
            source_url=p.get("url", ""),
            created_at=p.get("created_at") or p.get("createdAt"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_text=text,
            author=p.get("author"),
        )
        upsert_document(doc)
        count += 1
        print(f"  [confluence] {p['title'][:60]}")
    return count


def main():
    init_db()
    OUTPUT_DIR.mkdir(exist_ok=True)

    total = 0
    total += ingest_google_docs()
    total += ingest_confluence()

    if total == 0:
        print("No MCP output files found in scripts/mcp_output/")
        print("Ask Claude Code to fetch your docs and save them there.")
        print("See README.md for the quick start guide.")
    else:
        print(f"\nSynced {total} documents from MCP output.")
        print("DB status:", count_documents_by_source())
        print("\nNext steps:")
        print("  lifegraph extract      # Extract topics with Claude")
        print("  lifegraph graph        # Build the knowledge graph")
        print("  lifegraph serve        # View at http://localhost:8042")


if __name__ == "__main__":
    main()
