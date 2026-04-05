#!/usr/bin/env python3
"""Apply auto-generated clusters from Claude Code.

Usage: Claude Code generates clusters and saves to scripts/mcp_output/clusters.json,
then this script copies it to auto_clusters.json. No API key needed.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.config import DATABASE_PATH

INPUT = Path(__file__).parent / "mcp_output" / "clusters.json"
OUTPUT = Path(DATABASE_PATH).parent / "auto_clusters.json"


def main():
    if not INPUT.exists():
        print("No clusters.json found. Ask Claude Code to cluster topics first.")
        return

    data = json.loads(INPUT.read_text())
    clusters = data.get("clusters", data)

    with open(OUTPUT, "w") as f:
        json.dump(clusters, f, indent=2)

    print(f"Saved {len(clusters)} clusters to {OUTPUT}")
    for name, info in sorted(clusters.items()):
        topics = info["topics"] if isinstance(info, dict) else info
        cat = info.get("category", "?") if isinstance(info, dict) else "?"
        print(f"  [{cat}] {name}: {len(topics)} topics")

    print("\nRun 'lifegraph graph' to rebuild with new clusters.")


if __name__ == "__main__":
    main()
