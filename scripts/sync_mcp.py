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
import subprocess
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


def ingest_google_slides():
    """Ingest Google Slides from MCP output."""
    path = OUTPUT_DIR / "google_slides.json"
    if not path.exists():
        return 0
    slides = json.loads(path.read_text())
    count = 0
    for d in slides:
        text = d.get("content", "")
        if not text or len(text) < 50:
            continue
        doc = Document(
            id=None,
            title=d["title"],
            source="google_slides",
            source_id=d["id"],
            source_url=d.get("url", f"https://docs.google.com/presentation/d/{d['id']}"),
            created_at=d.get("created_at") or d.get("modifiedTime"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_text=text,
            author=d.get("author"),
        )
        upsert_document(doc)
        count += 1
        print(f"  [slides] {d['title'][:60]}")
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


def ingest_jira():
    """Ingest Jira issues from MCP output."""
    path = OUTPUT_DIR / "jira_issues.json"
    if not path.exists():
        return 0

    from lifegraph.db import get_all_projects, create_project, upsert_project_link
    from lifegraph.models import Project

    issues = json.loads(path.read_text())
    count = 0
    for issue in issues:
        key = issue.get("key", "")
        title = issue.get("title", issue.get("summary", ""))
        status = issue.get("status", "")
        priority = issue.get("priority", "")
        assignee = issue.get("assignee", "")
        url = issue.get("url", "")
        project_name = issue.get("project_name", issue.get("project", ""))
        created_at = issue.get("created_at", issue.get("created", ""))

        # Find or create a matching LifeGraph project
        from lifegraph.db import get_project_by_name
        project = get_project_by_name(project_name)
        if not project:
            # Try fuzzy match
            projects = get_all_projects()
            matches = [p for p in projects if project_name.lower() in p["name"].lower()
                       or any(w.lower() in p["name"].lower() for w in project_name.split() if len(w) > 3)]
            if matches:
                project = matches[0]

        if not project:
            continue

        upsert_project_link(
            project_id=project["id"],
            url=url,
            source_type="jira",
            source_id=key,
            title=title,
            status=status,
            priority=priority,
            assignee=assignee,
            created_at=created_at,
        )
        count += 1
        print(f"  [jira] {key}: {title[:50]}")
    return count


def ingest_github():
    """Sync GitHub via `gh` CLI if available (no token config needed)."""
    # Check if gh CLI is available and authenticated
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0

    # Get username
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        return 0
    username = result.stdout.strip()
    if not username:
        return 0

    print(f"  [github] Authenticated as {username}")

    # Get token and use the existing GitHub connector
    token_result = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
    )
    if token_result.returncode != 0:
        return 0

    import os
    os.environ["GITHUB_TOKEN"] = token_result.stdout.strip()

    # Reload config and run connector
    import importlib
    import lifegraph.config
    lifegraph.config.GITHUB_TOKEN = token_result.stdout.strip()

    from lifegraph.connectors.github import GitHubConnector
    connector = GitHubConnector()
    try:
        connector.authenticate()
        count = connector.sync()
        print(f"  [github] Linked {count} items to projects")
        return count
    except Exception as e:
        print(f"  [github] Error: {e}")
        return 0


def main():
    init_db()
    OUTPUT_DIR.mkdir(exist_ok=True)

    total = 0
    total += ingest_google_docs()
    total += ingest_google_slides()
    total += ingest_confluence()
    total += ingest_jira()
    total += ingest_github()

    if total == 0:
        print("No MCP output files found in scripts/mcp_output/")
        print("Ask Claude Code to fetch your docs and save them there.")
        print("See README.md for the quick start guide.")
    else:
        print(f"\nSynced {total} items from MCP output + GitHub.")
        print("DB status:", count_documents_by_source())
        print("\nNext steps:")
        print("  lifegraph extract      # Extract topics with Claude")
        print("  lifegraph graph        # Build the knowledge graph")
        print("  lifegraph serve        # View at http://localhost:8042")


if __name__ == "__main__":
    main()
