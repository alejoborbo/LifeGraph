# LifeGraph — Claude Code instructions

LifeGraph is a personal knowledge graph that visualizes what someone works on across Google Docs, Confluence, Jira, GitHub, and Slack.

## When the user says "set up my graph" or similar

Run the full setup automatically. Do all steps — don't ask, just do it.

### Step 1: Fetch their documents via MCP

Create `scripts/mcp_output/` directory, then fetch from all available sources:

**Google Docs** — use Google Workspace MCP:
1. `mcp__datadog-google-workspace-mcp__search_files` with `query: "mimeType = 'application/vnd.google-apps.document'"`, `max_results: 100`
2. For each doc, call `mcp__datadog-google-workspace-mcp__read_document` with the document ID
3. Save results to `scripts/mcp_output/google_docs.json`:
```json
[{"id": "doc_id", "title": "Doc Title", "content": "plain text...", "url": "https://docs.google.com/document/d/...", "created_at": "2026-01-01T00:00:00Z"}]
```

**Confluence** — use Atlassian MCP:
1. `mcp__datadog-atlassian__search_content` with `cql: "type = page AND contributor = currentUser() ORDER BY lastmodified DESC"`, `max_results: 50`
2. For each page, call `mcp__datadog-atlassian__get_page` with the page ID to get body content
3. Save to `scripts/mcp_output/confluence_pages.json`:
```json
[{"id": "page_id", "title": "Page Title", "html": "<p>body html...</p>", "url": "https://...", "created_at": "2026-01-01T00:00:00Z", "author": "Author Name"}]
```
For author names: personal spaces have the person's name in `resultGlobalContainer.title`.

**Jira** — use Atlassian MCP:
1. `mcp__datadog-atlassian__search_issues` with `jql: "assignee = currentUser() OR reporter = currentUser() ORDER BY updated DESC"`, `max_results: 100`
2. Save to `scripts/mcp_output/jira_issues.json`:
```json
[{"key": "PROJ-123", "title": "Issue title", "status": "In Progress", "priority": "High", "assignee": "username", "project_name": "Project Name", "url": "https://datadoghq.atlassian.net/browse/PROJ-123", "created_at": "2026-01-01T00:00:00Z"}]
```

**GitHub** — handled automatically by `sync_mcp.py` via the `gh` CLI (no MCP needed). If the user has `gh` installed and authenticated, it just works.

**Slack** — requires a bot token. Skip unless the user has `SLACK_TOKEN` in .env.

### Step 2: Install deps and run setup

```bash
pip install -e . -q
python setup_my_graph.py
```

This imports MCP output + GitHub, extracts topics, builds the graph, and opens the UI.

### Step 3: Discover related docs by others

After the graph is built, search Confluence for pages by OTHER people that match the user's top topics. This powers the "People" tab — the silo-breaking feature.

1. Get the user's top 10 topics from the DB
2. For each topic, search Confluence: `mcp__datadog-atlassian__search_content` with `cql: "type = page AND text ~ \"topic name\" ORDER BY lastmodified DESC"`, `max_results: 10`
3. For interesting results (from personal spaces = individual authors), call `mcp__datadog-atlassian__get_page` to get content
4. Insert into DB with author info using a Python script (see previous conversations for pattern)
5. Link to existing topics, rebuild graph: `lifegraph graph`

## Architecture notes

- Backend: Python + SQLite + Click CLI
- Frontend: static HTML + D3.js in `web/index.html` (no build step)
- Graph/Timeline/Report/Projects views = personal docs only
- People view = other authors' docs that share topics with the user
- Topic extraction uses Claude API (needs ANTHROPIC_API_KEY)
- `web/graph.json` is the bridge between backend and frontend
- `lifegraph digest` sends weekly Slack notifications about new related docs (needs DIGEST_SLACK_WEBHOOK)
