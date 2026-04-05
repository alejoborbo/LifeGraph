# LifeGraph — Claude Code instructions

LifeGraph is a personal knowledge graph that visualizes what someone works on across Google Docs, Confluence, Jira, GitHub, and Slack.

## When the user says "set up my graph" or similar

Run the full setup automatically. Do all steps — don't ask, just do it.

### Step 1: Install

```bash
pip install -e . -q
```

### Step 2: Fetch documents via MCP

Create `scripts/mcp_output/` directory, then fetch from all available sources:

**Google Docs** — use Google Workspace MCP:
1. `mcp__datadog-google-workspace-mcp__search_files` with `query: "mimeType = 'application/vnd.google-apps.document'"`, `max_results: 100`
2. For each doc, call `mcp__datadog-google-workspace-mcp__read_document` with the document ID
3. Save results to `scripts/mcp_output/google_docs.json`:
```json
[{"id": "doc_id", "title": "Doc Title", "content": "plain text...", "url": "https://docs.google.com/document/d/...", "created_at": "2026-01-01T00:00:00Z"}]
```

**Google Slides** — use Google Workspace MCP:
1. `mcp__datadog-google-workspace-mcp__search_files` with `query: "mimeType = 'application/vnd.google-apps.presentation'"`, `max_results: 100`
2. For each presentation, call `mcp__datadog-google-workspace-mcp__get_file_content` with the file ID (exports as text)
3. Save results to `scripts/mcp_output/google_slides.json` (same format as google_docs.json)

**Confluence** — use Atlassian MCP:
1. `mcp__datadog-atlassian__search_content` with `cql: "type = page AND contributor = currentUser() ORDER BY lastmodified DESC"`, `max_results: 50`
2. For each page, call `mcp__datadog-atlassian__get_page` with the page ID to get body content
3. Save to `scripts/mcp_output/confluence_pages.json`:
```json
[{"id": "page_id", "title": "Page Title", "html": "<p>body html...</p>", "url": "https://...", "created_at": "2026-01-01T00:00:00Z", "author": "Author Name"}]
```

**Jira** — use Atlassian MCP:
1. `mcp__datadog-atlassian__search_issues` with `jql: "assignee = currentUser() OR reporter = currentUser() ORDER BY updated DESC"`, `max_results: 100`
2. Save to `scripts/mcp_output/jira_issues.json`:
```json
[{"key": "PROJ-123", "title": "Issue title", "status": "In Progress", "priority": "High", "assignee": "username", "project_name": "Project Name", "url": "https://datadoghq.atlassian.net/browse/PROJ-123", "created_at": "2026-01-01T00:00:00Z"}]
```

**GitHub** — handled automatically by `sync_mcp.py` via the `gh` CLI (no MCP needed).

### Step 3: Import into DB

```bash
python scripts/sync_mcp.py
```

### Step 4: Extract topics (YOU do this — no API key needed)

For each document in the DB that doesn't have topics yet, extract 2-10 specific topics with relevance scores. Do this yourself (you ARE the LLM) instead of calling the Anthropic API.

1. Read documents without topics:
```python
from lifegraph.db import get_documents_without_topics
docs = get_documents_without_topics()
```

2. For each document, decide on 2-10 specific topics (e.g. "Datadog Log Pipelines", "Monitor Alert Fatigue") with relevance 0.0-1.0. Topics should be specific, not vague.

3. Save to `scripts/mcp_output/topics.json`:
```json
[{"doc_id": 123, "topics": [{"topic": "Specific Topic Name", "relevance": 0.9}, ...]}, ...]
```

4. Run: `python scripts/extract_topics_inline.py`

### Step 5: Auto-cluster topics (YOU do this too)

Group all topic names into 15-40 meaningful clusters. Save to `scripts/mcp_output/clusters.json`:
```json
{"clusters": {"Cluster Name": {"topics": ["Topic A", "Topic B"], "category": "posture"}, ...}}
```
Categories: posture, automation, strategy, ux, team, teaching, code, personal, other

Then run: `python scripts/auto_cluster_inline.py`

### Step 6: Build and serve

```bash
lifegraph graph
lifegraph serve
```

### Step 7: Discover related docs by others

Search Confluence for pages by OTHER people that match the user's top topics. This powers the "People" tab.

1. Get top topics from DB
2. For each, search Confluence across all spaces
3. Insert results with author info
4. Rebuild graph: `lifegraph graph`

## When the user says "prep me for my meeting with X" or similar

Look up X in the People data and provide a briefing:
1. Read graph.json to find the person
2. List shared topics, their recent docs, and suggested talking points
3. The Insights view also has a Meeting Prep feature in the UI

## Architecture notes

- Backend: Python + SQLite + Click CLI
- Frontend: static HTML + D3.js in `web/index.html` (no build step)
- Graph/Timeline/Report/Projects views = personal docs only
- People view = other authors' docs that share topics with the user
- No API key needed — Claude Code handles topic extraction and clustering directly
- `web/graph.json` is the bridge between backend and frontend
