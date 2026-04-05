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

CREATE_PROJECT_LINKS_TABLE = """
CREATE TABLE IF NOT EXISTS project_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    status TEXT,
    priority TEXT,
    assignee TEXT,
    created_at TEXT,
    fetched_at TEXT NOT NULL,
    UNIQUE(project_id, source_type, source_id)
)
"""

CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, raw_text, source,
    content='documents',
    content_rowid='id'
)
"""

CREATE_FTS_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
        INSERT INTO documents_fts(rowid, title, raw_text, source)
        VALUES (new.id, new.title, new.raw_text, new.source);
    END""",
    """CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
        INSERT INTO documents_fts(documents_fts, rowid, title, raw_text, source)
        VALUES('delete', old.id, old.title, old.raw_text, old.source);
    END""",
    """CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
        INSERT INTO documents_fts(documents_fts, rowid, title, raw_text, source)
        VALUES('delete', old.id, old.title, old.raw_text, old.source);
        INSERT INTO documents_fts(rowid, title, raw_text, source)
        VALUES (new.id, new.title, new.raw_text, new.source);
    END""",
]


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
    conn.execute(CREATE_PROJECT_LINKS_TABLE)
    # FTS5
    try:
        conn.execute(CREATE_FTS_TABLE)
        for trigger in CREATE_FTS_TRIGGERS:
            conn.execute(trigger)
    except Exception:
        pass  # FTS5 not available — search will fall back to LIKE
    # Migrations
    _migrate_projects_phase(conn)
    _migrate_summaries(conn)
    conn.commit()
    conn.close()


def _migrate_projects_phase(conn):
    """Add phase column to projects if missing."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()]
    if "phase" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN phase TEXT DEFAULT 'Planning'")


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


# ── Project links (Jira, GitHub, etc.) ──────────────────


def upsert_project_link(
    project_id: int, url: str, source_type: str, source_id: str,
    title: str, status: str = None, priority: str = None,
    assignee: str = None, created_at: str = None,
):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO project_links
           (project_id, url, source_type, source_id, title, status, priority, assignee, created_at, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id, source_type, source_id) DO UPDATE SET
               title = excluded.title, status = excluded.status,
               priority = excluded.priority, assignee = excluded.assignee,
               fetched_at = excluded.fetched_at
        """,
        (project_id, url, source_type, source_id, title, status,
         priority, assignee, created_at, now),
    )
    conn.commit()
    conn.close()


def get_project_links(project_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM project_links WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_project_links() -> dict[int, list[dict]]:
    """Return {project_id: [links]} for all projects."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM project_links ORDER BY created_at DESC").fetchall()
    conn.close()
    from collections import defaultdict
    result = defaultdict(list)
    for r in rows:
        result[r["project_id"]].append(dict(r))
    return dict(result)


# ── Full-text search ──────────────────────────────────────


def rebuild_fts():
    """Rebuild the FTS5 index from the documents table."""
    conn = get_connection()
    conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()


def _has_fts() -> bool:
    """Check if FTS5 table exists."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='documents_fts'"
    ).fetchone()
    conn.close()
    return row is not None


def search_documents(
    query: str,
    source: str = None,
    project_id: int = None,
    limit: int = 20,
) -> list[dict]:
    """Full-text search across documents. Falls back to LIKE if FTS5 unavailable."""
    conn = get_connection()

    if _has_fts():
        # FTS5 search with BM25 ranking
        sql = """
            SELECT d.id, d.title, d.source, d.source_url, d.created_at,
                   snippet(documents_fts, 1, '**', '**', '...', 32) as snippet,
                   bm25(documents_fts) as rank
            FROM documents_fts
            JOIN documents d ON d.id = documents_fts.rowid
        """
        params = []
        wheres = ["documents_fts MATCH ?"]
        params.append(query)

        if source:
            wheres.append("d.source = ?")
            params.append(source)
        if project_id:
            wheres.append("d.id IN (SELECT doc_id FROM project_documents WHERE project_id = ?)")
            params.append(project_id)

        sql += " WHERE " + " AND ".join(wheres)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
    else:
        # Fallback: LIKE search
        sql = """
            SELECT d.id, d.title, d.source, d.source_url, d.created_at,
                   SUBSTR(d.raw_text, 1, 200) as snippet
            FROM documents d
        """
        params = []
        wheres = ["(d.title LIKE ? OR d.raw_text LIKE ?)"]
        like = f"%{query}%"
        params.extend([like, like])

        if source:
            wheres.append("d.source = ?")
            params.append(source)
        if project_id:
            wheres.append("d.id IN (SELECT doc_id FROM project_documents WHERE project_id = ?)")
            params.append(project_id)

        sql += " WHERE " + " AND ".join(wheres)
        sql += " ORDER BY d.created_at DESC LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_project_links(query: str, source_type: str = None) -> list[dict]:
    """Search project links (Jira/GitHub) by title."""
    conn = get_connection()
    sql = """
        SELECT pl.*, p.name as project_name
        FROM project_links pl
        JOIN projects p ON p.id = pl.project_id
        WHERE pl.title LIKE ?
    """
    params = [f"%{query}%"]
    if source_type:
        sql += " AND pl.source_type LIKE ?"
        params.append(f"%{source_type}%")
    sql += " ORDER BY pl.created_at DESC LIMIT 20"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_projects(query: str = None, status: str = None) -> list[dict]:
    """Search projects by name or filter by status."""
    conn = get_connection()
    sql = """
        SELECT p.*, COUNT(pd.doc_id) as doc_count
        FROM projects p
        LEFT JOIN project_documents pd ON p.id = pd.project_id
    """
    wheres = []
    params = []
    if query:
        wheres.append("p.name LIKE ?")
        params.append(f"%{query}%")
    if status:
        wheres.append("p.status = ?")
        params.append(status)
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " GROUP BY p.id ORDER BY p.name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Phase / heuristics ────────────────────────────────────


def _migrate_summaries(conn):
    """Create summaries table if missing."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(start_date, end_date)
        )
    """)


def save_summary(start_date: str, end_date: str, text: str):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO summaries (start_date, end_date, text, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(start_date, end_date) DO UPDATE SET
               text = excluded.text, created_at = excluded.created_at""",
        (start_date, end_date, text, now),
    )
    conn.commit()
    conn.close()


def get_all_summaries() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT start_date, end_date, text FROM summaries ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [{"start": r["start_date"], "end": r["end_date"], "text": r["text"]} for r in rows]


def update_project_phase(project_id: int, phase: str):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "UPDATE projects SET phase = ?, updated_at = ? WHERE id = ?",
        (phase, now, project_id),
    )
    conn.commit()
    conn.close()
