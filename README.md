# LifeGraph

A personal knowledge graph that connects everything you work on — docs, pages, PRs, threads — and shows you who else is working on the same topics.

## How it works

```
Your docs (Confluence, Google Docs, GitHub, Slack)
        ↓
   Download via API
        ↓
   Claude extracts topics from each doc
        ↓
   Store doc ↔ topic links in SQLite
        ↓
   Interactive graph in your browser
```

One command does the whole pipeline: `lifegraph sync`

## Get started

### 1. Install

```bash
git clone https://github.com/capmann/LifeGraph.git
cd LifeGraph
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` in any text editor. You need:

- **`ANTHROPIC_API_KEY`** — get one at [console.anthropic.com](https://console.anthropic.com/). This is how LifeGraph understands your documents.
- **At least one source** — start with whichever is easiest for you:

<details>
<summary><b>Confluence</b> (easiest — just need an API token)</summary>

1. Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**, give it a name, copy it
3. In `.env`, fill in:
```
CONFLUENCE_URL=https://yourcompany.atlassian.net
CONFLUENCE_EMAIL=you@company.com
CONFLUENCE_API_TOKEN=paste-your-token-here
```
</details>

<details>
<summary><b>GitHub</b> (quick if you have the GitHub CLI)</summary>

If you have `gh` installed (most developers do), just run `gh auth login` — LifeGraph picks it up automatically.

Otherwise, create a token at [github.com/settings/tokens](https://github.com/settings/tokens) and add to `.env`:
```
GITHUB_TOKEN=ghp_your-token-here
```
</details>

<details>
<summary><b>Google Docs</b> (needs a Google Cloud project)</summary>

1. Go to [Google Cloud Console](https://console.cloud.google.com/), create a project
2. Enable **Google Docs API** and **Google Drive API**
3. Create OAuth credentials (Desktop app), download as `credentials.json`
4. Run `lifegraph auth` (opens browser for login)
</details>

<details>
<summary><b>Slack</b> (needs a Slack app)</summary>

1. Create app at [api.slack.com/apps](https://api.slack.com/apps) with scopes: `channels:history`, `channels:read`, `users:read`
2. Install to workspace, copy Bot token
3. In `.env`:
```
SLACK_TOKEN=xoxb-your-token
SLACK_CHANNELS=channel1,channel2
SLACK_WORKSPACE_URL=https://yourteam.slack.com
```
</details>

### 3. Run

```bash
lifegraph sync
```

This single command:
1. **Downloads** all your docs from configured sources
2. **Sends each doc to Claude** to extract topics (e.g. "API Design", "Monitor Coverage")
3. **Stores** documents, topics, and doc↔topic links in a local SQLite database
4. **Builds** the knowledge graph

Then view it:

```bash
lifegraph serve
```

Open [localhost:8042](http://localhost:8042) in your browser.

### 4. Keep it fresh

Run `lifegraph sync` anytime to pull new docs and update topics. It's incremental — only processes what's new.

## What you'll see

**6 views** in the web UI:

- **Graph** — Your topics as an interactive network. Click a node to see related docs. Use source filters (Confluence, GitHub, etc.) to highlight by source.
- **Timeline** — Your documents plotted over time.
- **Report** — What you worked on in a date range, grouped by topic.
- **Projects** — Track initiatives with status, Jira tickets, and GitHub PRs.
- **People** — Who else is working on your topics? Suggests people you should talk to.
- **Insights** — Weekly output, topic trends, time allocation, and meeting prep.

## Discover who's working on similar topics

After your graph is built, find related work by others:

```bash
lifegraph sync confluence-discover   # Search Confluence for pages by others on your topics
lifegraph sync github-discover       # Search GitHub (DataDog org) for related PRs/issues
```

This populates the **People** and **Insights** tabs.

## All commands

| Command | What it does |
|---|---|
| `lifegraph sync` | Full pipeline: download docs → extract topics → build graph |
| `lifegraph serve` | Open the web UI |
| `lifegraph setup` | sync + serve in one shot |
| `lifegraph sync confluence` | Sync just Confluence |
| `lifegraph sync github` | Sync just GitHub |
| `lifegraph sync confluence-discover` | Find related Confluence pages by others |
| `lifegraph sync github-discover` | Find related GitHub items by others |
| `lifegraph search "query"` | Search across all your documents |
| `lifegraph digest` | Weekly summary of new related docs (posts to Slack if configured) |
| `lifegraph summary --days 7` | AI-written summary of your recent work |

## Architecture

```
Confluence ──┐
Google Docs ──┤                    ┌──────────┐
Slack ────────┼── download docs ──→│ SQLite   │──→ graph.json ──→ D3.js UI
GitHub ───────┤                    │ (docs,   │
Google Slides ┘                    │  topics, │
                                   │  links)  │
              Claude API ─────────→│          │
              (topic extraction)   └──────────┘
```

- **Backend**: Python, SQLite, Click CLI
- **Frontend**: Static HTML + D3.js (no build step, no framework)
- **AI**: Claude API for topic extraction and summaries
