# LifeGraph

Build a knowledge graph from all the documents you've written across Google Docs, Confluence, and more. Visualize your content as an interactive graph organized by topics.

## Setup

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Set up Google OAuth credentials

You need a Google Cloud project with the Docs and Drive APIs enabled:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Google Docs API** and **Google Drive API**:
   - Go to **APIs & Services > Library**
   - Search for "Google Docs API" and click **Enable**
   - Search for "Google Drive API" and click **Enable**
4. Create OAuth credentials:
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - If prompted, configure the **OAuth consent screen** first (choose "External", add your email as a test user)
   - Application type: **Desktop app**
   - Download the JSON file and save it as `credentials.json` in the project root

### 3. Authenticate

```bash
lifegraph auth
```

This opens your browser for Google OAuth consent. After approving, a `token.json` file is saved locally (gitignored).

### 4. Sync your documents

```bash
lifegraph sync google-docs
```

### 5. Check status

```bash
lifegraph status
```

## Roadmap

- [ ] Google Slides connector
- [ ] Google Sheets connector
- [ ] Confluence connector
- [ ] Topic extraction via Claude API
- [ ] Knowledge graph construction
- [ ] Interactive web visualization
