import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent

GOOGLE_CREDENTIALS_PATH = Path(
    os.getenv("GOOGLE_CREDENTIALS_PATH", PROJECT_ROOT / "credentials.json")
)
GOOGLE_TOKEN_PATH = Path(
    os.getenv("GOOGLE_TOKEN_PATH", PROJECT_ROOT / "token.json")
)
DATABASE_PATH = Path(
    os.getenv("DATABASE_PATH", PROJECT_ROOT / "lifegraph.db")
)

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

LIFEGRAPH_AUTHOR = os.getenv("LIFEGRAPH_AUTHOR", "")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Confluence
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL", "")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY", "")

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPOS = os.getenv("GITHUB_REPOS", "")  # comma-separated "owner/repo"
import json as _json
GITHUB_REPO_PROJECT_MAP = _json.loads(os.getenv("GITHUB_REPO_PROJECT_MAP", "{}"))

# Slack
SLACK_TOKEN = os.getenv("SLACK_TOKEN", "")  # xoxb-... or xoxp-...
SLACK_CHANNELS = os.getenv("SLACK_CHANNELS", "")  # comma-separated channel names or IDs
SLACK_WORKSPACE_URL = os.getenv("SLACK_WORKSPACE_URL", "")  # e.g. https://datadog.slack.com

# Digest
DIGEST_SLACK_WEBHOOK = os.getenv("DIGEST_SLACK_WEBHOOK", "")  # Incoming webhook URL
