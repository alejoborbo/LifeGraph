"""Confluence connector - fetches pages via REST API."""
import html
import re
from datetime import datetime, timezone

import requests

from lifegraph.config import (
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_EMAIL,
    CONFLUENCE_SPACE_KEY,
    CONFLUENCE_URL,
)
from lifegraph.connectors.base import BaseConnector
from lifegraph.db import upsert_document
from lifegraph.models import Document


def _strip_html(raw: str) -> str:
    """Strip HTML tags and decode entities to get plain text."""
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class ConfluenceConnector(BaseConnector):
    """Connector for Confluence Cloud and Data Center."""

    def __init__(self):
        self.base_url = CONFLUENCE_URL.rstrip("/")
        self.email = CONFLUENCE_EMAIL
        self.token = CONFLUENCE_API_TOKEN
        self.space_key = CONFLUENCE_SPACE_KEY
        self.session = None

    def authenticate(self):
        if not self.base_url:
            raise ValueError(
                "CONFLUENCE_URL is not set. Add it to your .env file."
            )
        if not self.token:
            raise ValueError(
                "CONFLUENCE_API_TOKEN is not set. Add it to your .env file."
            )

        self.session = requests.Session()

        # Cloud uses basic auth (email + API token)
        # Data Center uses bearer token (personal access token)
        if "atlassian.net" in self.base_url:
            if not self.email:
                raise ValueError(
                    "CONFLUENCE_EMAIL is required for Atlassian Cloud."
                )
            self.session.auth = (self.email, self.token)
        else:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

        # Validate credentials
        resp = self.session.get(
            f"{self.base_url}/wiki/rest/api/user/current"
        )
        if resp.status_code == 401:
            raise ValueError("Authentication failed. Check your credentials.")
        resp.raise_for_status()

    def _ensure_auth(self):
        if self.session is None:
            self.authenticate()

    def list_documents(self) -> list[dict]:
        self._ensure_auth()

        cql = 'type=page'
        if self.space_key:
            cql += f' AND space="{self.space_key}"'
        cql += ' ORDER BY lastmodified DESC'

        pages = []
        start = 0
        limit = 50

        while True:
            resp = self.session.get(
                f"{self.base_url}/wiki/rest/api/content/search",
                params={"cql": cql, "start": start, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                created = page.get("history", {}).get("createdDate", "")
                pages.append({
                    "id": page["id"],
                    "title": page["title"],
                    "created_at": created,
                    "url": f"{self.base_url}/wiki{page.get('_links', {}).get('webui', '')}",
                })

            # Pagination
            if data.get("size", 0) < limit:
                break
            start += limit

        return pages

    def fetch_content(self, page_id: str) -> str:
        self._ensure_auth()

        resp = self.session.get(
            f"{self.base_url}/wiki/rest/api/content/{page_id}",
            params={"expand": "body.storage"},
        )
        resp.raise_for_status()
        data = resp.json()

        body_html = data.get("body", {}).get("storage", {}).get("value", "")
        return _strip_html(body_html)

    def sync(self) -> int:
        self._ensure_auth()

        pages = self.list_documents()
        count = 0

        for page in pages:
            try:
                text = self.fetch_content(page["id"])
                if not text.strip():
                    continue

                doc = Document(
                    id=None,
                    title=page["title"],
                    source="confluence",
                    source_id=page["id"],
                    source_url=page["url"],
                    created_at=page.get("created_at"),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    raw_text=text,
                )
                upsert_document(doc)
                count += 1
            except Exception as e:
                print(f"  Warning: failed to sync '{page['title']}': {e}")

        return count
