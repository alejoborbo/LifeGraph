#!/usr/bin/env python3
"""One-command LifeGraph setup.

Usage:
    python setup_my_graph.py

For Datadog employees: just open this repo in Claude Code and say "set up my graph".
Claude will fetch your docs via MCP and run this script automatically.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MCP_OUTPUT = ROOT / "scripts" / "mcp_output"


def run(cmd, **kwargs):
    print(f"\n→ {cmd}")
    return subprocess.run(cmd, shell=True, cwd=str(ROOT), **kwargs)


def main():
    print("=" * 60)
    print("  LifeGraph Setup")
    print("=" * 60)

    # 1. Install deps
    try:
        import lifegraph  # noqa
    except ImportError:
        print("\nInstalling dependencies...")
        run(f"{sys.executable} -m pip install -e . -q")

    # 2. Init DB
    print("\nInitializing database...")
    from lifegraph.db import init_db
    init_db()

    # 3. Import MCP output if available
    mcp_files = list(MCP_OUTPUT.glob("*.json")) if MCP_OUTPUT.exists() else []
    if mcp_files:
        print(f"\nImporting {len(mcp_files)} MCP output file(s)...")
        run(f"{sys.executable} scripts/sync_mcp.py")

    # 4. Import inline topics if available
    topics_file = MCP_OUTPUT / "topics.json"
    if topics_file.exists():
        print("\nImporting extracted topics...")
        run(f"{sys.executable} scripts/extract_topics_inline.py")

    # 5. Import auto-clusters if available
    clusters_file = MCP_OUTPUT / "clusters.json"
    if clusters_file.exists():
        print("\nImporting auto-clusters...")
        run(f"{sys.executable} scripts/auto_cluster_inline.py")

    # 6. Check doc count
    from lifegraph.db import count_documents_by_source
    counts = count_documents_by_source()
    total = sum(counts.values())

    if total == 0:
        print("\n" + "=" * 60)
        print("  No documents found.")
        print()
        print("  If you're in Claude Code, make sure MCP servers are configured:")
        print("    - Google Workspace MCP (for Google Docs/Slides)")
        print("    - Atlassian MCP (for Confluence/Jira)")
        print("  See README.md for setup instructions.")
        print()
        print("  Then say: 'set up my graph'")
        print("=" * 60)
        return

    print(f"\n{total} documents: {counts}")

    # 7. Extract topics if needed (try API, it's OK if it fails)
    from lifegraph.db import get_documents_without_topics
    pending = get_documents_without_topics()
    if pending:
        print(f"\n{len(pending)} document(s) need topic extraction...")
        result = run("lifegraph extract --limit 50")
        if result.returncode != 0:
            print("\nTopic extraction via API failed (no ANTHROPIC_API_KEY).")
            print("That's OK — Claude Code can extract topics inline.")
            print("If you're in Claude Code, it will handle this automatically.")

    # 8. Build graph
    print("\nBuilding knowledge graph...")
    run("lifegraph graph")

    # 9. Check if we have topics
    from lifegraph.db import get_all_topics_with_counts
    topic_count = len(get_all_topics_with_counts())
    if topic_count == 0:
        print("\nNo topics extracted yet. The graph will be empty.")
        print("Claude Code will extract topics and rebuild the graph.")
    else:
        print(f"\n{topic_count} topics in the graph.")

    # 10. Launch
    print("\n" + "=" * 60)
    print("  Done! Starting server...")
    print("  Open http://localhost:8042")
    print("=" * 60 + "\n")

    try:
        import webbrowser
        webbrowser.open("http://localhost:8042")
    except Exception:
        pass

    os.execvp(sys.executable, [sys.executable, "-m", "lifegraph.cli", "serve"])


if __name__ == "__main__":
    main()
