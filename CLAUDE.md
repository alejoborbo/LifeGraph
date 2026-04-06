# LifeGraph — Claude Code instructions

LifeGraph is a personal knowledge graph that visualizes what someone works on across Google Docs, Confluence, Jira, GitHub, and Slack.

## When the user says "set up my graph" or similar

Do everything automatically. Don't ask — just do it, step by step.

### Step 1: Install

```bash
pip install -e . -q 2>/dev/null
```

### Step 2: Fetch documents

Try each source. If an MCP isn't available, skip it and move on — don't fail.

Create `scripts/mcp_output/` directory first: `mkdir -p scripts/mcp_output`

**Google Docs** (try Google Workspace MCP):
- Try calling `mcp__datadog-google-workspace-mcp__search_files` with `query: "mimeType = 'application/vnd.google-apps.document'"`, `max_results: 100`
- If the MCP isn't available, tell the user: "Google Workspace MCP not configured. To add it, see the MCP setup section in README.md"
- If it works: for each doc, call `mcp__datadog-google-workspace-mcp__read_document` with the document ID
- Save to `scripts/mcp_output/google_docs.json`: `[{"id": "...", "title": "...", "content": "...", "url": "...", "created_at": "..."}]`

**Google Slides** (same MCP):
- Search with `query: "mimeType = 'application/vnd.google-apps.presentation'"`, `max_results: 50`
- For each, call `mcp__datadog-google-workspace-mcp__get_file_content`
- Save to `scripts/mcp_output/google_slides.json`

**Confluence** (try Atlassian MCP):
- Try calling `mcp__datadog-atlassian__search_content` with `cql: "type = page AND contributor = currentUser() ORDER BY lastmodified DESC"`, `max_results: 50`
- If the MCP isn't available, tell the user: "Atlassian MCP not configured. To add it, see the MCP setup section in README.md"
- If it works: for each page, call `mcp__datadog-atlassian__get_page` to get the body
- Save to `scripts/mcp_output/confluence_pages.json`: `[{"id": "...", "title": "...", "html": "...", "url": "...", "created_at": "...", "author": "..."}]`

**Jira** (same Atlassian MCP):
- `mcp__datadog-atlassian__search_issues` with `jql: "assignee = currentUser() OR reporter = currentUser() ORDER BY updated DESC"`, `max_results: 100`
- Save to `scripts/mcp_output/jira_issues.json`

**GitHub** — no MCP needed, handled by `sync_mcp.py` via the `gh` CLI.

### Step 3: Import, extract topics, build graph

```bash
python scripts/sync_mcp.py
```

Then extract topics. Try the API first, fall back to doing it yourself:

```bash
lifegraph extract --limit 50
```

If that fails (no ANTHROPIC_API_KEY), YOU extract topics yourself:
1. Read documents: `from lifegraph.db import get_documents_without_topics; docs = get_documents_without_topics()`
2. For each doc, decide 2-10 specific topics with relevance 0.0-1.0
3. Save to `scripts/mcp_output/topics.json`: `[{"doc_id": 123, "topics": [{"topic": "Name", "relevance": 0.9}]}]`
4. Run: `python scripts/extract_topics_inline.py`

Then build and serve:
```bash
lifegraph graph
lifegraph serve
```

### Step 4: Discover related docs by others

After the graph is built, search for content by OTHER people on the user's topics.

**Confluence** (if MCP available): search each top topic across all spaces, fetch pages with author info.
**GitHub**: `lifegraph sync github-discover --top-topics 10`

## When the user says "prep me for my meeting with X"

Look up X in the graph data and provide a briefing:
1. Read `web/graph.json`
2. Find the person in the documents (match by author name)
3. List shared topics, their recent docs, and suggest talking points

## Architecture notes

- Backend: Python + SQLite + Click CLI
- Frontend: static HTML + D3.js in `web/index.html` (no build step)
- Graph/Timeline/Report/Projects views = personal docs only
- People view = other authors' docs that share topics with the user
- Insights view = time allocation, topic momentum, impact, meeting prep
- `web/graph.json` is the bridge between backend and frontend
