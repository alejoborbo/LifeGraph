# LifeGraph

Build a knowledge graph from all the documents you've written across Google Docs, Confluence, and more. Visualize your content as an interactive graph organized by topics.

![LifeGraph](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## How it works

1. **Connect** your Google Docs (more connectors coming)
2. **Extract** topics from each document using Claude
3. **Visualize** an interactive knowledge graph in your browser -- topics are nodes, shared documents are edges

## Quick start

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

Edit `.env` and fill in:
- **`ANTHROPIC_API_KEY`** -- get one at [console.anthropic.com](https://console.anthropic.com/)
- **Google OAuth credentials** -- see below

### 3. Set up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Enable the **Google Docs API** and **Google Drive API** (APIs & Services > Library)
4. Create OAuth credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Configure the **OAuth consent screen** if prompted (choose "External", add your email as a test user)
   - Application type: **Desktop app**
   - Download the JSON file and save it as `credentials.json` in the project root

### 4. Run the pipeline

```bash
# Authenticate with Google (opens browser)
lifegraph auth

# Sync your Google Docs
lifegraph sync google-docs

# Extract topics using Claude
lifegraph extract

# Generate the graph
lifegraph graph

# Open the visualization
open web/index.html
```

### 5. Explore

Open `web/index.html` in your browser. You can:
- **Hover** over nodes to see connections
- **Click** a topic to see its documents
- **Search** topics with the search bar
- **Drag** nodes to rearrange the layout
- **Zoom** and pan to explore

## CLI reference

| Command | Description |
|---|---|
| `lifegraph auth` | Authenticate with Google |
| `lifegraph sync google-docs` | Fetch all your Google Docs |
| `lifegraph extract` | Extract topics from documents using Claude |
| `lifegraph extract --limit N` | Process only N documents |
| `lifegraph topics` | List all extracted topics |
| `lifegraph graph` | Export the knowledge graph to `web/graph.json` |
| `lifegraph graph --min-edge N` | Set minimum co-occurrence threshold (default: 2) |
| `lifegraph status` | Show document counts by source |

## Roadmap

- [ ] Google Slides connector
- [ ] Google Sheets connector
- [ ] Confluence connector
- [ ] Hosted web app (no local setup needed)
