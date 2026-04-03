import os
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from lifegraph.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH, GOOGLE_SCOPES
from lifegraph.connectors.base import BaseConnector
from lifegraph.db import upsert_document
from lifegraph.models import Document


class GoogleDocsConnector(BaseConnector):
    def __init__(self):
        self.creds: Credentials | None = None

    def authenticate(self):
        """Run OAuth2 flow or refresh existing token."""
        if GOOGLE_TOKEN_PATH.exists():
            self.creds = Credentials.from_authorized_user_file(
                str(GOOGLE_TOKEN_PATH), GOOGLE_SCOPES
            )

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not GOOGLE_CREDENTIALS_PATH.exists():
                    raise FileNotFoundError(
                        f"Google OAuth credentials not found at {GOOGLE_CREDENTIALS_PATH}. "
                        "Download them from the GCP Console (see README)."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(GOOGLE_CREDENTIALS_PATH), GOOGLE_SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            GOOGLE_TOKEN_PATH.write_text(self.creds.to_json())

    def _ensure_auth(self):
        if not self.creds or not self.creds.valid:
            self.authenticate()

    def list_documents(self) -> list[dict]:
        """List all Google Docs owned by the user via Drive API."""
        self._ensure_auth()
        service = build("drive", "v3", credentials=self.creds)

        docs = []
        page_token = None

        while True:
            response = (
                service.files()
                .list(
                    q="mimeType='application/vnd.google-apps.document'",
                    spaces="drive",
                    fields="nextPageToken, files(id, name, createdTime, webViewLink)",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            for f in response.get("files", []):
                docs.append(
                    {
                        "id": f["id"],
                        "title": f["name"],
                        "created_at": f.get("createdTime"),
                        "url": f.get("webViewLink", ""),
                    }
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return docs

    def fetch_content(self, doc_id: str) -> str:
        """Extract plain text from a Google Doc."""
        self._ensure_auth()
        service = build("docs", "v1", credentials=self.creds)
        doc = service.documents().get(documentId=doc_id).execute()

        text_parts = []
        for element in doc.get("body", {}).get("content", []):
            paragraph = element.get("paragraph")
            if paragraph:
                for run in paragraph.get("elements", []):
                    text_run = run.get("textRun")
                    if text_run:
                        text_parts.append(text_run.get("content", ""))

        return "".join(text_parts)

    def sync(self) -> int:
        """Fetch all Google Docs and store in the database."""
        self._ensure_auth()
        docs = self.list_documents()
        count = 0

        for doc_info in docs:
            try:
                content = self.fetch_content(doc_info["id"])
                if not content.strip():
                    continue

                document = Document(
                    id=None,
                    title=doc_info["title"],
                    source="google_docs",
                    source_id=doc_info["id"],
                    source_url=doc_info["url"],
                    created_at=doc_info.get("created_at"),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    raw_text=content,
                )
                upsert_document(document)
                count += 1
            except Exception as e:
                print(f"  Warning: Failed to fetch '{doc_info['title']}': {e}")

        return count
