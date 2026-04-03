import sqlite3
from datetime import datetime, timezone
from typing import Optional

from lifegraph.config import DATABASE_PATH
from lifegraph.models import Document

CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT,
    created_at TEXT,
    fetched_at TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    UNIQUE(source, source_id)
)
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(CREATE_DOCUMENTS_TABLE)
    conn.commit()
    conn.close()


def upsert_document(doc: Document):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO documents (title, source, source_id, source_url, created_at, fetched_at, raw_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, source_id) DO UPDATE SET
            title = excluded.title,
            fetched_at = excluded.fetched_at,
            raw_text = excluded.raw_text
        """,
        (
            doc.title,
            doc.source,
            doc.source_id,
            doc.source_url,
            doc.created_at,
            doc.fetched_at,
            doc.raw_text,
        ),
    )
    conn.commit()
    conn.close()


def document_exists(source: str, source_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM documents WHERE source = ? AND source_id = ?",
        (source, source_id),
    ).fetchone()
    conn.close()
    return row is not None


def count_documents_by_source() -> dict[str, int]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM documents GROUP BY source"
    ).fetchall()
    conn.close()
    return {row["source"]: row["cnt"] for row in rows}
