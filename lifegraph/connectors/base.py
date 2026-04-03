from abc import ABC, abstractmethod

from lifegraph.models import Document


class BaseConnector(ABC):
    """Base class for all document source connectors."""

    @abstractmethod
    def authenticate(self):
        """Run the authentication flow for this source."""

    @abstractmethod
    def list_documents(self) -> list[dict]:
        """List available documents. Returns list of dicts with at least 'id' and 'title'."""

    @abstractmethod
    def fetch_content(self, doc_id: str) -> str:
        """Fetch the plain text content of a document by its source ID."""

    @abstractmethod
    def sync(self) -> int:
        """Fetch all documents and store in the database. Returns count of new/updated docs."""
