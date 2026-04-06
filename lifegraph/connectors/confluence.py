"""Confluence connector - fetches pages via REST API."""
import html
import re
import sys
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
        next_url = (
            f"{self.base_url}/wiki/rest/api/content/search"
            f"?cql={cql}&limit=50&expand=history.createdBy"
        )

        while next_url:
            sys.stderr.write(
                f"\r  Listing pages... {len(pages)} found"
            )
            sys.stderr.flush()

            resp = self.session.get(next_url)
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                history = page.get("history", {})
                created = history.get("createdDate", "")
                author = (
                    history.get("createdBy", {}).get("displayName", "")
                    or history.get("createdBy", {}).get("username", "")
                )
                pages.append({
                    "id": page["id"],
                    "title": page["title"],
                    "created_at": created,
                    "author": author,
                    "url": f"{self.base_url}/wiki{page.get('_links', {}).get('webui', '')}",
                })

            # Follow next link if available
            next_path = data.get("_links", {}).get("next")
            if next_path:
                base = data.get("_links", {}).get("base", self.base_url)
                next_url = f"{base}{next_path}"
            else:
                next_url = None

        sys.stderr.write(f"\r  Listing pages... {len(pages)} found\n")
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
        total = len(pages)
        count = 0

        for i, page in enumerate(pages, 1):
            title = page["title"]
            truncated = (title[:40] + "...") if len(title) > 40 else title
            sys.stderr.write(
                f"\r  [{i}/{total}] Fetching: {truncated:<43}"
            )
            sys.stderr.flush()

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
                    author=page.get("author"),
                )
                upsert_document(doc)
                count += 1
            except Exception as e:
                sys.stderr.write(f"\n  Warning: failed '{title}': {e}\n")

        sys.stderr.write("\n")
        return count

    def search_pages(self, cql: str, max_results: int = 50) -> list[dict]:
        """Search for pages using CQL, returning metadata with author."""
        self._ensure_auth()

        pages = []
        start = 0
        limit = min(max_results, 50)

        while len(pages) < max_results:
            resp = self.session.get(
                f"{self.base_url}/wiki/rest/api/content/search",
                params={
                    "cql": cql,
                    "start": start,
                    "limit": limit,
                    "expand": "history.createdBy",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                history = page.get("history", {})
                created = history.get("createdDate", "")
                author = (
                    history.get("createdBy", {}).get("displayName", "")
                    or history.get("createdBy", {}).get("username", "")
                )
                space = page.get("_expandable", {}).get("space", "")
                space_key = space.split("/")[-1] if space else ""
                pages.append({
                    "id": page["id"],
                    "title": page["title"],
                    "created_at": created,
                    "author": author,
                    "space": space_key,
                    "url": f"{self.base_url}/wiki{page.get('_links', {}).get('webui', '')}",
                })

            if data.get("size", 0) < limit:
                break
            start += limit

        return pages[:max_results]
