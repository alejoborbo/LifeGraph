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

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
