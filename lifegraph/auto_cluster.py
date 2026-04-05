"""Auto-cluster topics using Claude API."""
import json

import anthropic

from lifegraph.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from lifegraph.db import get_all_topics_with_counts

SYSTEM_PROMPT = """You are a topic clustering engine. Given a list of topic names with their document counts, group them into meaningful clusters.

Rules:
- Each cluster should have a clear, concise name (2-5 words, title case)
- Group topics that are about the same concept but named differently (e.g. "Monitor Posture" and "Monitoring Posture" should be in one cluster)
- A cluster can have 1 topic (if it's unique enough) or many
- Aim for 15-40 clusters total — not too granular, not too broad
- Every topic must be assigned to exactly one cluster
- Also assign each cluster a category from: posture, automation, strategy, ux, team, teaching, code, personal, other

Return ONLY a JSON object, no other text:
{
  "clusters": {
    "Cluster Name": {
      "topics": ["Topic A", "Topic B", ...],
      "category": "posture"
    },
    ...
  }
}"""


def auto_cluster() -> dict:
    """Call Claude to cluster all topics. Returns {cluster_name: {"topics": [...], "category": str}}."""
    topics = get_all_topics_with_counts()
    if not topics:
        return {}

    topic_list = "\n".join(f"- {t['name']} ({t['doc_count']} docs)" for t in topics)

    kwargs = {}
    if ANTHROPIC_API_KEY:
        kwargs["api_key"] = ANTHROPIC_API_KEY
    client = anthropic.Anthropic(**kwargs)

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Here are {len(topics)} topics to cluster:\n\n{topic_list}"}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)
    return result.get("clusters", result)


def generate_clusters_py(clusters: dict) -> str:
    """Generate the CLUSTERS dict and CATEGORY_MAP as Python source code."""
    lines = [
        '"""Auto-generated topic clusters. Regenerate with: lifegraph auto-cluster"""\n',
        "CLUSTERS = {",
    ]

    for cluster_name, info in sorted(clusters.items()):
        topics = info["topics"] if isinstance(info, dict) else info
        lines.append(f'    "{cluster_name}": [')
        for t in sorted(topics):
            lines.append(f'        "{t}",')
        lines.append("    ],")
    lines.append("}\n")

    # Category map
    lines.append("CATEGORY_MAP = {")
    for cluster_name, info in sorted(clusters.items()):
        cat = info.get("category", "other") if isinstance(info, dict) else "other"
        lines.append(f'    "{cluster_name}": "{cat}",')
    lines.append("}")

    return "\n".join(lines)
