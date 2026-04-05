"""AI-powered work summary using Claude API."""

from datetime import datetime, timedelta, timezone

import anthropic

from lifegraph.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from lifegraph.db import (
    get_all_projects,
    get_project_documents,
    get_project_links,
    get_work_summary,
    save_summary,
)

SUMMARY_PROMPT = """You are a concise work summary writer. You'll receive a structured dump of someone's recent work activity: documents they wrote or updated (Google Docs, Confluence, Slack threads), Jira tickets, and GitHub items — all grouped by project.

Write a clear, natural-language summary of what they accomplished and what's in progress. The summary should be:
- Grouped by project (use ### headings)
- 2-4 bullet points per active project: what was done, key decisions, blockers
- Skip projects with no meaningful activity
- End with a brief "Focus areas" section listing the top 2-3 priorities
- Use markdown formatting
- Be specific: mention document names, ticket IDs, concrete outcomes
- Keep it under 500 words total
- Tone: professional but not stiff — like an update you'd post in Slack

Do NOT just list document titles. Synthesize what the work was about."""


def gather_activity(start_date: str, end_date: str) -> str:
    """Gather all activity in a date range into a structured text block."""
    docs = get_work_summary(start_date, end_date + "T23:59:59")
    all_projects = get_all_projects()

    # Build doc_id -> doc lookup
    doc_by_id = {}
    for d in docs:
        doc_by_id[d["id"]] = d

    lines = []
    lines.append(f"Period: {start_date} to {end_date}")
    lines.append(f"Total documents: {len(docs)}\n")

    # For each project, find which docs and links fall in this period
    for p in all_projects:
        p_docs = get_project_documents(p["id"])
        period_docs = [
            d for d in p_docs
            if d["id"] in doc_by_id
        ]

        p_links = get_project_links(p["id"])
        # Include links created in the period, or all if no date
        period_links = [
            l for l in p_links
            if not l.get("created_at") or (start_date <= l["created_at"][:10] <= end_date)
        ]

        if not period_docs and not period_links:
            continue

        lines.append(f"## Project: {p['name']} (status: {p['status']}, phase: {p.get('phase', '?')})")

        if period_docs:
            lines.append("Documents:")
            for d in period_docs:
                date = d["created_at"][:10] if d.get("created_at") else "?"
                snippet = ""
                # Get snippet from work summary data
                full = doc_by_id.get(d["id"])
                if full and full.get("topics"):
                    snippet = f" [topics: {full['topics']}]"
                lines.append(f"  - [{d['source']}] {d['title']} ({date}){snippet}")

        if period_links:
            lines.append("Tickets/PRs:")
            for l in period_links:
                lines.append(
                    f"  - [{l['source_type']}] {l.get('source_id', '?')} — "
                    f"{l['title']} (status: {l.get('status', '?')})"
                )

        lines.append("")

    # Also list uncategorized docs (not in any project)
    all_project_doc_ids = set()
    for p in all_projects:
        for d in get_project_documents(p["id"]):
            all_project_doc_ids.add(d["id"])

    uncategorized = [d for d in docs if d["id"] not in all_project_doc_ids]
    if uncategorized:
        lines.append("## Uncategorized work")
        for d in uncategorized:
            date = d["created_at"][:10] if d.get("created_at") else "?"
            lines.append(f"  - [{d['source']}] {d['title']} ({date})")
        lines.append("")

    return "\n".join(lines)


def generate_summary(start_date: str, end_date: str) -> str:
    """Generate an AI-powered work summary for a date range."""
    activity = gather_activity(start_date, end_date)

    if not activity.strip() or "Total documents: 0" in activity:
        return f"No activity found between {start_date} and {end_date}."

    kwargs = {}
    if ANTHROPIC_API_KEY:
        kwargs["api_key"] = ANTHROPIC_API_KEY
    client = anthropic.Anthropic(**kwargs)

    start_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime("%b %-d, %Y")
    end_fmt = datetime.strptime(end_date, "%Y-%m-%d").strftime("%b %-d, %Y")

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=SUMMARY_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a work summary for {start_fmt} – {end_fmt}.\n\n"
                    f"Here is all the activity data:\n\n{activity}"
                ),
            }
        ],
    )

    result = message.content[0].text.strip()

    # Cache the summary for the frontend
    save_summary(start_date, end_date, result)

    return result
