#!/usr/bin/env python3
"""Extract topics from documents using pre-computed results from Claude Code.

Usage: Claude Code extracts topics and saves to scripts/mcp_output/topics.json,
then this script links them in the DB. No API key needed — Claude Code is the LLM.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lifegraph.db import init_db, get_or_create_topic, link_doc_topic, get_connection

OUTPUT = Path(__file__).parent / "mcp_output" / "topics.json"


def main():
    init_db()

    if not OUTPUT.exists():
        print("No topics.json found. Ask Claude Code to extract topics first.")
        return

    data = json.loads(OUTPUT.read_text())
    # Expected format: [{"doc_id": 123, "topics": [{"topic": "Name", "relevance": 0.9}, ...]}]

    count = 0
    for entry in data:
        doc_id = entry["doc_id"]
        for t in entry.get("topics", []):
            name = t["topic"].strip()
            relevance = float(t.get("relevance", 1.0))
            if not name:
                continue
            topic_id = get_or_create_topic(name)
            link_doc_topic(doc_id, topic_id, relevance)
            count += 1

    print(f"Linked {count} topic assignments across {len(data)} documents.")


if __name__ == "__main__":
    main()
