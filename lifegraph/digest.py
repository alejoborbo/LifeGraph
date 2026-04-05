"""Weekly digest — find new docs by others on your topics and notify via Slack."""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from lifegraph.config import DIGEST_SLACK_WEBHOOK
from lifegraph.db import get_all_topics_with_counts, get_connection


def get_recent_docs_by_others(days: int = 7) -> list[dict]:
    """Get documents by other authors created in the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        """SELECT d.id, d.title, d.source, d.source_url, d.created_at, d.author,
                  GROUP_CONCAT(t.name, '||') as topics
           FROM documents d
           LEFT JOIN doc_topics dt ON d.id = dt.doc_id
           LEFT JOIN topics t ON dt.topic_id = t.id
           WHERE d.author IS NOT NULL
             AND d.author != ''
             AND d.author != 'Capucine Marteau'
             AND d.created_at >= ?
           GROUP BY d.id
           ORDER BY d.created_at DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_my_topic_names() -> set[str]:
    """Get topic names from docs without author (= your docs)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT t.name
           FROM topics t
           JOIN doc_topics dt ON t.id = dt.topic_id
           JOIN documents d ON d.id = dt.doc_id
           WHERE d.author IS NULL OR d.author = '' OR d.author = 'Capucine Marteau'"""
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def build_digest(days: int = 7) -> dict:
    """Build a digest of new docs by others on your topics.

    Returns {"has_news": bool, "text": str, "slack_blocks": list, "docs": list, "by_author": dict}
    """
    recent = get_recent_docs_by_others(days)
    my_topics = get_my_topic_names()

    # Filter to docs that share at least one of your topics
    relevant = []
    for doc in recent:
        doc_topics = set((doc["topics"] or "").split("||")) - {""}
        shared = doc_topics & my_topics
        if shared:
            doc["shared_topics"] = sorted(shared)
            relevant.append(doc)

    if not relevant:
        return {
            "has_news": False,
            "text": f"No new docs on your topics in the last {days} days.",
            "slack_blocks": [],
            "docs": [],
            "by_author": {},
        }

    # Group by author
    by_author = defaultdict(list)
    for doc in relevant:
        by_author[doc["author"]].append(doc)

    # Build plain text
    lines = [f"*{len(relevant)} new doc(s) on your topics this week*\n"]
    for author, docs in sorted(by_author.items(), key=lambda x: -len(x[1])):
        lines.append(f"*{author}* ({len(docs)} doc{'s' if len(docs) > 1 else ''})")
        for doc in docs:
            topics_str = ", ".join(doc["shared_topics"][:3])
            url = doc.get("source_url", "")
            title = doc["title"]
            if url:
                lines.append(f"  - <{url}|{title}> ({topics_str})")
            else:
                lines.append(f"  - {title} ({topics_str})")
        lines.append("")

    text = "\n".join(lines)

    # Build Slack blocks
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"LifeGraph — {len(relevant)} new doc(s) on your topics"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"In the last {days} days, {len(by_author)} people published docs related to topics you work on."},
        },
        {"type": "divider"},
    ]

    for author, docs in sorted(by_author.items(), key=lambda x: -len(x[1])):
        doc_lines = []
        for doc in docs[:5]:
            topics_str = ", ".join(doc["shared_topics"][:3])
            url = doc.get("source_url", "")
            title = doc["title"]
            if url:
                doc_lines.append(f"• <{url}|{title}> — _{topics_str}_")
            else:
                doc_lines.append(f"• {title} — _{topics_str}_")

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{author}*\n" + "\n".join(doc_lines)},
        })

    return {
        "has_news": True,
        "text": text,
        "slack_blocks": blocks,
        "docs": relevant,
        "by_author": dict(by_author),
    }


def post_to_slack(webhook_url: str, blocks: list, text: str) -> bool:
    """Post digest to Slack via incoming webhook."""
    payload = {"text": text, "blocks": blocks}
    resp = requests.post(webhook_url, json=payload, timeout=10)
    return resp.status_code == 200


def run_digest(days: int = 7, post: bool = True) -> str:
    """Build and optionally post the weekly digest. Returns the text."""
    digest = build_digest(days)

    if not digest["has_news"]:
        return digest["text"]

    if post and DIGEST_SLACK_WEBHOOK:
        ok = post_to_slack(DIGEST_SLACK_WEBHOOK, digest["slack_blocks"], digest["text"])
        if ok:
            return digest["text"] + "\n(Posted to Slack)"
        else:
            return digest["text"] + "\n(Failed to post to Slack — check webhook URL)"

    return digest["text"]
