# LifeGraph

Build a knowledge graph from everything you work on — Google Docs, Confluence, Slack, GitHub, Jira — and visualize it as an interactive graph organized by topics and projects.

![LifeGraph](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## How it works

1. **Connect** your sources (Google Docs, Confluence, Slack, GitHub)
2. **Extract** topics from each document using Claude
3. **Visualize** an interactive knowledge graph — topics are nodes, shared documents are edges
4. **Track projects** with auto-computed phases (Planning → Building → Shipped)
5. **Search** everything with full-text search across all sources
6. **Generate AI summaries** of your work for any time period

## Quick start

```bash
git clone https://github.com/capmann/LifeGraph.git
cd LifeGraph
pip install -e .
cp .env.example .env
```

Edit `.env` — you just need two things to start:
1. **`ANTHROPIC_API_KEY`** — get one at [console.anthropic.com](https://console.anthropic.com/)
2. **At least one source** — Confluence is the easiest (just an API token)

Then run:

```bash
lifegraph sync
```

That's it. One command. It:
1. **Downloads docs** from all configured sources (Confluence, GitHub, etc.)
2. **Calls Claude API** to extract topics from each document
3. **Stores everything in SQLite** (docs, topics, doc↔topic links)
4. **Builds the graph** for the web UI

To view it: `lifegraph serve` (or `lifegraph setup` to sync + serve in one shot).

### Source setup

You don't need all of them — start with one and add more later.

| Source | What to add in `.env` | How to get it |
|--------|----------------------|---------------|
| Confluence | `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN` | [Generate API token](https://id.atlassian.com/manage-profile/security/api-tokens) |
| GitHub | `GITHUB_TOKEN` | `gh auth token` or [create token](https://github.com/settings/tokens) |
| Google Docs | `GOOGLE_CREDENTIALS_PATH` | [GCP Console](https://console.cloud.google.com/) OAuth credentials → `lifegraph auth` |
| Slack | `SLACK_TOKEN`, `SLACK_CHANNELS` | [Create Slack app](https://api.slack.com/apps) with `channels:history` scope |

> **Datadog employees**: Use `CONFLUENCE_URL=https://datadoghq.atlassian.net`. For GitHub, most of you have `gh` installed — just run `gh auth login` and skip the token.

### Using with Claude Code (optional)

If you have Claude Code with MCP servers (Google Workspace, Atlassian), you can open this folder and say **"set up my graph"** — Claude will fetch docs via MCP. But `lifegraph setup` works standalone without Claude Code.

---

## Full setup (non-Datadog / manual)

### 1. Install

```bash
git clone https://github.com/capmann/LifeGraph.git
cd LifeGraph
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in the services you want to connect (you don't need all of them — start with one):

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key from [console.anthropic.com](https://console.anthropic.com/) |
| `GOOGLE_CREDENTIALS_PATH` | For Google Docs | OAuth credentials JSON (see below) |
| `CONFLUENCE_URL` | For Confluence | Your Confluence base URL |
| `CONFLUENCE_EMAIL` | For Confluence | Your email |
| `CONFLUENCE_API_TOKEN` | For Confluence | API token from [Atlassian](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `SLACK_TOKEN` | For Slack | Bot token (see below) |
| `SLACK_CHANNELS` | For Slack | Comma-separated channel names to sync |
| `SLACK_WORKSPACE_URL` | For Slack | e.g. `https://yourteam.slack.com` |
| `GITHUB_TOKEN` | For GitHub | Personal access token (or use `gh auth token`) |

### 3. Set up your connectors

<details>
<summary><strong>Google Docs</strong></summary>

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Enable the **Google Docs API** and **Google Drive API** (APIs & Services > Library)
4. Create OAuth credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Configure the **OAuth consent screen** if prompted (choose "External", add your email as a test user)
   - Application type: **Desktop app**
   - Download the JSON file and save it as `credentials.json` in the project root

```bash
lifegraph auth                 # Opens browser for OAuth
lifegraph sync google-docs     # Fetches all your docs
```
</details>

<details>
<summary><strong>Confluence</strong></summary>

1. Generate an API token at [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Add to `.env`: `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`
3. Optionally set `CONFLUENCE_SPACE_KEY` to limit to one space

```bash
lifegraph sync confluence
```
</details>

<details>
<summary><strong>Slack</strong></summary>

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps) — choose "From a manifest" and paste:

```json
{
  "display_information": { "name": "LifeGraph" },
  "oauth_config": {
    "scopes": {
      "bot": ["channels:history", "channels:read", "groups:history", "groups:read", "users:read"]
    }
  },
  "settings": { "org_deploy_enabled": false, "socket_mode_enabled": false }
}
```

2. Install to your workspace, copy the Bot User OAuth Token
3. Add to `.env`: `SLACK_TOKEN`, `SLACK_CHANNELS`, `SLACK_WORKSPACE_URL`

```bash
lifegraph sync slack                    # Sync all configured channels
lifegraph sync slack --channel general  # Sync a single channel
```

Slack threads become searchable documents — each thread (parent + replies) is stored as one document.
</details>

<details>
<summary><strong>GitHub</strong></summary>

Uses GitHub's search API to fetch all PRs you authored, issues you opened, and PRs you reviewed — across all repos you have access to.

1. Create a token at [github.com/settings/tokens](https://github.com/settings/tokens) or use the GitHub CLI:

```bash
export GITHUB_TOKEN=$(gh auth token)
```

2. Add `GITHUB_TOKEN` to `.env`

```bash
lifegraph sync github
```

GitHub items are automatically matched to LifeGraph projects by keywords in the PR/issue title. You can also set explicit mappings in `.env`:

```
GITHUB_REPO_PROJECT_MAP={"DataDog/web-ui": "Monitoring Posture & Coverage"}
```
</details>

### 4. Sync, extract, visualize

```bash
# Sync at least one source first (pick any)
lifegraph sync google-docs
# or: lifegraph sync confluence
# or: lifegraph sync slack
# or: lifegraph sync github

# Extract topics from all documents using Claude
lifegraph extract

# Create projects from topic clusters
python scripts/seed_projects.py

# Auto-detect project phases (Planning/Building/Shipped)
lifegraph compute-phases

# Build the knowledge graph
lifegraph graph

# Rebuild full-text search index
lifegraph rebuild-fts

# Start the local server and open the UI
lifegraph serve
# Open http://localhost:8042
```

You can re-run these commands anytime to pull in new data. Each `sync` is incremental — it only adds or updates changed documents.

### 5. Explore

The web UI has 6 views:

- **Graph** — Interactive force-directed graph of topic clusters. Click nodes to see documents, hover to highlight connections. Use source filters (Google Docs, Confluence, etc.) to highlight nodes by source. Use category filters to focus on specific areas.
- **Timeline** — Documents plotted by date and topic.
- **Report** — Documents grouped by topic category for a date range. Switch to **Summary** mode for an AI-written work update.
- **Projects** — Card grid with status badges, phase indicators, doc counts, Jira tickets, and GitHub items.
- **People** — Discover who across your org is working on similar topics. Shows authors from Confluence and GitHub with shared topic overlap, suggested connections, and meeting prep.
- **Insights** — Time allocation (weekly output chart), topic momentum (trending up/down), your reach (how many people work on your topics), and meeting prep (type a name, get a full briefing).

## CLI reference

| Command | Description |
|---|---|
| `lifegraph setup` | **One-command setup**: sync, extract, build, serve |
| `lifegraph sync google-docs` | Fetch all your Google Docs |
| `lifegraph sync confluence` | Fetch Confluence pages |
| `lifegraph sync confluence-discover` | Discover Confluence pages by others on your topics |
| `lifegraph sync github-discover` | Discover GitHub PRs/issues by others (DataDog org) |
| `lifegraph sync slack` | Fetch Slack threads as documents |
| `lifegraph sync github` | Fetch your PRs, issues, and reviews |
| `lifegraph extract` | Extract topics using Claude |
| `lifegraph auto-cluster` | Auto-cluster topics using Claude |
| `lifegraph graph` | Build the knowledge graph |
| `lifegraph serve` | Start local web server |
| `lifegraph digest` | Weekly digest: new docs by others on your topics |
| `lifegraph search "query"` | Full-text search across all documents |
| `lifegraph summary --days 7` | Generate an AI work summary |
| `lifegraph projects` | List all projects |
| `lifegraph project "name"` | Show project details |
| `lifegraph set-status "name" shipped` | Update project status |
| `lifegraph compute-phases` | Auto-compute project phases |
| `lifegraph topics` | List all extracted topics |
| `lifegraph status` | Show document counts by source |
| `lifegraph rebuild-fts` | Rebuild full-text search index |

## Auto-sync with GitHub Actions

A GitHub Action runs daily at 6am UTC to sync all sources, extract topics, rebuild the graph, and redeploy to GitHub Pages. You can also trigger it manually from the Actions tab.

To enable it, add these secrets in your repo (**Settings > Secrets and variables > Actions**):

| Secret | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for topic extraction |
| `GH_SYNC_TOKEN` | For GitHub | Personal access token (needs `repo` scope) |
| `GOOGLE_TOKEN_JSON` | For Google Docs | Contents of your `token.json` after first `lifegraph auth` |
| `GOOGLE_CREDENTIALS_JSON` | For Google Docs | Contents of your `credentials.json` |
| `CONFLUENCE_URL` | For Confluence | Your Confluence base URL |
| `CONFLUENCE_EMAIL` | For Confluence | Your email |
| `CONFLUENCE_API_TOKEN` | For Confluence | API token |
| `CONFLUENCE_SPACE_KEY` | For Confluence | Optional space filter |
| `SLACK_TOKEN` | For Slack | Bot token |
| `SLACK_CHANNELS` | For Slack | Comma-separated channel names |
| `SLACK_WORKSPACE_URL` | For Slack | e.g. `https://yourteam.slack.com` |

Only add the secrets for connectors you use — the action skips any that aren't configured. To get your Google token, run `lifegraph auth` locally first, then paste the contents of `token.json` as the `GOOGLE_TOKEN_JSON` secret.

## Architecture

```
Google Docs ─┐
Confluence ──┤
Slack ───────┼──→ SQLite DB ──→ Claude API ──→ Topics ──→ graph.json ──→ D3.js UI
GitHub ──────┤       ↑                                        ↑
Jira ────────┘   FTS5 index                            AI summaries
```

- **Backend**: Python + SQLite + Click CLI
- **Frontend**: Static HTML + D3.js (no build step)
- **AI**: Claude API for topic extraction and work summaries
- **Search**: SQLite FTS5 with BM25 ranking
