# Fetch my docs via MCP

Run this in Claude Code to sync your Google Docs and Confluence pages into LifeGraph.
Just paste this prompt:

---

Please fetch all my documents and save them for LifeGraph:

1. **Google Docs** — Use the Google Workspace MCP to search for my recent docs:
   - Call `mcp__datadog-google-workspace-mcp__search_files` with query `mimeType = 'application/vnd.google-apps.document'` (max 100)
   - For each doc, call `mcp__datadog-google-workspace-mcp__read_document` to get the content
   - Save the results as `scripts/mcp_output/google_docs.json` with format:
     ```json
     [{"id": "...", "title": "...", "content": "...", "url": "...", "created_at": "...", "author": "..."}]
     ```

2. **Confluence** — Use the Atlassian MCP to search for my pages:
   - Call `mcp__datadog-atlassian__search_content` with CQL `type = page AND contributor = currentUser() ORDER BY lastmodified DESC` (max 100)
   - For each result, call `mcp__datadog-atlassian__get_page` to get the body
   - Save as `scripts/mcp_output/confluence_pages.json` with format:
     ```json
     [{"id": "...", "title": "...", "html": "...", "url": "...", "created_at": "...", "author": "..."}]
     ```

3. Then run: `python scripts/sync_mcp.py`

---
