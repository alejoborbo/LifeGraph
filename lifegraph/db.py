import sqlite3
from datetime import datetime, timezone
from typing import Optional

from lifegraph.config import DATABASE_PATH
from lifegraph.models import Document, Project

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

CREATE_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    category TEXT,
    description TEXT,
    parent_id INTEGER REFERENCES projects(id),
    start_date TEXT,
    end_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_PROJECT_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS project_documents (
    project_id INTEGER NOT NULL REFERENCES projects(id),
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    role TEXT DEFAULT 'reference',
    added_at TEXT NOT NULL,
    PRIMARY KEY (project_id, doc_id)
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
    conn.execute(CREATE_PROJECTS_TABLE)
    conn.execute(CREATE_PROJECT_DOCUMENTS_TABLE)
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


def get_work_summary(start_date: str, end_date: str) -> list[dict]:
    """Get documents with their topics in a date range, for the work report."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT d.id, d.title, d.source, d.source_url, d.created_at,
               GROUP_CONCAT(t.name, '||') as topics
        FROM documents d
        LEFT JOIN doc_topics dt ON d.id = dt.doc_id
        LEFT JOIN topics t ON dt.topic_id = t.id
        WHERE d.created_at >= ? AND d.created_at <= ?
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """,
        (start_date, end_date),
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


# ── Project queries ──────────────────────────────────────


def create_project(project: Project) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    cur = conn.execute(
        """INSERT OR IGNORE INTO projects
           (name, status, category, description, parent_id, start_date, end_date, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project.name, project.status, project.category, project.description,
         project.parent_id, project.start_date, project.end_date,
         project.created_at or now, project.updated_at or now),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def get_project_by_name(name: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_projects() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, COUNT(pd.doc_id) as doc_count,
               MAX(d.created_at) as last_activity
        FROM projects p
        LEFT JOIN project_documents pd ON p.id = pd.project_id
        LEFT JOIN documents d ON pd.doc_id = d.id
        GROUP BY p.id
        ORDER BY last_activity DESC NULLS LAST
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_project_status(project_id: int, status: str):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
        (status, now, project_id),
    )
    conn.commit()
    conn.close()


def link_doc_to_project(project_id: int, doc_id: int, role: str = "reference"):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO project_documents (project_id, doc_id, role, added_at) VALUES (?, ?, ?, ?)",
        (project_id, doc_id, role, now),
    )
    conn.commit()
    conn.close()


def get_project_documents(project_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT d.id, d.title, d.source, d.source_url, d.created_at, pd.role
        FROM documents d
        JOIN project_documents pd ON d.id = pd.doc_id
        WHERE pd.project_id = ?
        ORDER BY d.created_at DESC
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project_doc_ids(project_id: int) -> list[int]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT doc_id FROM project_documents WHERE project_id = ?",
        (project_id,),
    ).fetchall()
    conn.close()
    return [r["doc_id"] for r in rows]
