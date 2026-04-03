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

CREATE_TOPICS_TABLE = """
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
)
"""

CREATE_DOC_TOPICS_TABLE = """
CREATE TABLE IF NOT EXISTS doc_topics (
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    relevance REAL DEFAULT 1.0,
    PRIMARY KEY (doc_id, topic_id)
)
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(CREATE_DOCUMENTS_TABLE)
    conn.execute(CREATE_TOPICS_TABLE)
    conn.execute(CREATE_DOC_TOPICS_TABLE)
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


def get_or_create_topic(name: str) -> int:
    conn = get_connection()
    row = conn.execute("SELECT id FROM topics WHERE name = ?", (name,)).fetchone()
    if row:
        topic_id = row["id"]
    else:
        cur = conn.execute(
            "INSERT INTO topics (name, created_at) VALUES (?, ?)",
            (name, datetime.now(timezone.utc).isoformat()),
        )
        topic_id = cur.lastrowid
        conn.commit()
    conn.close()
    return topic_id


def link_doc_topic(doc_id: int, topic_id: int, relevance: float = 1.0):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO doc_topics (doc_id, topic_id, relevance) VALUES (?, ?, ?)",
        (doc_id, topic_id, relevance),
    )
    conn.commit()
    conn.close()


def get_documents_without_topics() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT d.id, d.title, d.raw_text FROM documents d
           WHERE d.id NOT IN (SELECT DISTINCT doc_id FROM doc_topics)
           ORDER BY d.id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_topics_with_counts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.id, t.name, COUNT(dt.doc_id) as doc_count
           FROM topics t LEFT JOIN doc_topics dt ON t.id = dt.topic_id
           GROUP BY t.id ORDER BY doc_count DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
