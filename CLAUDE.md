# LifeGraph — Claude Code instructions

LifeGraph is a personal knowledge graph that visualizes what someone works on across Google Docs, Confluence, Slack, and GitHub.

## When the user says "set up my graph" or similar

Run the full setup automatically:

### Step 1: Fetch their documents via MCP

Create `scripts/mcp_output/` directory, then:

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

For Confluence author names: personal spaces have the person's name in `resultGlobalContainer.title`. For shared spaces, the `authorId` from `get_page` is an opaque ID — use the space owner name when available.

### Step 2: Run setup

```bash
python setup_my_graph.py
```

This installs deps, imports the MCP output, extracts topics, builds the graph, and opens the UI.

### Step 3 (optional): Discover related docs by others

Search Confluence for pages related to the user's top topics (from other authors), and insert them with author info. This powers the "People" tab.

## Architecture notes

- Backend: Python + SQLite + Click CLI
- Frontend: static HTML + D3.js in `web/index.html` (no build step)
- Graph/Timeline/Report/Projects views = personal docs only
- People view = other authors' docs that share topics with the user — this is the silo-breaking feature
- Topic extraction uses Claude API (needs ANTHROPIC_API_KEY)
- `web/graph.json` is the bridge between backend and frontend
