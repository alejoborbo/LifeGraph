#!/usr/bin/env python3
"""One-command LifeGraph setup.

Usage:
    python setup_my_graph.py

This script:
1. Installs dependencies
2. Looks for MCP output files (from Claude Code) and imports them
3. Extracts topics using Claude API
4. Builds the knowledge graph
5. Opens the UI in your browser

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
    # 1. Install deps (if not already)
    print("=" * 60)
    print("  LifeGraph Setup")
    print("=" * 60)

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
        print(f"\nFound {len(mcp_files)} MCP output file(s), importing...")
        run(f"{sys.executable} scripts/sync_mcp.py")
    else:
        print("\nNo MCP output found in scripts/mcp_output/")
        print("If you're in Claude Code, ask Claude to fetch your docs first.")
        print("Otherwise, set up connectors in .env (see README).")

    # 4. Check how many docs we have
    from lifegraph.db import count_documents_by_source
    counts = count_documents_by_source()
    total = sum(counts.values())

    if total == 0:
        print("\nNo documents yet. Set up at least one source:")
        print("  - In Claude Code: say 'fetch my Google Docs and Confluence pages'")
        print("  - Or manually: cp .env.example .env && edit .env")
        return

    print(f"\n{total} documents in DB: {counts}")

    # 5. Extract topics
    from lifegraph.db import get_documents_without_topics
    pending = get_documents_without_topics()
    if pending:
        print(f"\nExtracting topics for {len(pending)} document(s)...")
        result = run("lifegraph extract")
        if result.returncode != 0:
            print("Topic extraction failed — do you have ANTHROPIC_API_KEY set?")
            print("Set it: export ANTHROPIC_API_KEY=sk-ant-...")
    else:
        print("\nAll documents already have topics.")

    # 6. Build graph
    print("\nBuilding knowledge graph...")
    run("lifegraph graph")

    # 7. Launch
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
