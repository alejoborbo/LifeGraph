"""Topic extraction using Claude API."""
import json

import anthropic

from lifegraph.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from lifegraph.db import get_or_create_topic, link_doc_topic

SYSTEM_PROMPT = """You are a topic extraction engine. Given a document, extract specific, concrete topics that the document discusses in depth.

Rules:
- Return between 2 and 10 topics per document.
- Topics should be specific (e.g. "Datadog Log Pipelines", "Monitor Alert Fatigue") not vague (e.g. "Technology", "Observability").
- Use title case for topic names.
- If the document is a meeting note, extract the substantive topics discussed, not meta-topics like "Meeting Notes" or "Action Items".
- Each topic should have a relevance score from 0.0 to 1.0 indicating how central it is to the document.

Return ONLY a JSON array, no other text. Example:
[{"topic": "Datadog Log Pipelines", "relevance": 0.9}, {"topic": "Log Parsing Rules", "relevance": 0.6}]"""

MAX_TEXT_CHARS = 12000


def extract_topics(title: str, text: str) -> list[dict]:
    """Call Claude API to extract topics from a document.

    Returns list of {"topic": str, "relevance": float}.
    """
    # Support both direct API key and gateway-based auth (e.g. Datadog AI gateway)
    kwargs = {}
    if ANTHROPIC_API_KEY:
        kwargs["api_key"] = ANTHROPIC_API_KEY
    client = anthropic.Anthropic(**kwargs)

    # Truncate very long docs to save tokens
    truncated = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        truncated += "\n\n[... truncated ...]"

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Document title: {title}\n\n{truncated}",
            }
        ],
    )

    raw = message.content[0].text.strip()
    # Handle markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)


def process_document(doc_id: int, title: str, text: str) -> list[str]:
    """Extract topics for a document and store them in the DB.

    Returns list of topic names that were linked.
    """
    topics = extract_topics(title, text)
    linked = []

    for t in topics:
        name = t["topic"].strip()
        relevance = float(t.get("relevance", 1.0))
        if not name:
            continue
        topic_id = get_or_create_topic(name)
        link_doc_topic(doc_id, topic_id, relevance)
        linked.append(name)

    return linked
