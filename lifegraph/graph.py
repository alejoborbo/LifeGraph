"""Build a knowledge graph from doc-topic relationships."""
import json
import sqlite3
from collections import defaultdict

from lifegraph.config import DATABASE_PATH, LIFEGRAPH_AUTHOR


def build_graph(min_docs: int = 2, min_edge_weight: int = 1) -> dict:
    """Build a graph where nodes are topics and edges connect topics that co-occur in documents.

    Args:
        min_docs: minimum number of documents a topic must appear in to be included.
        min_edge_weight: minimum co-occurrence count to create an edge.

    Returns:
        {"nodes": [...], "edges": [...], "documents": [...]}
    """
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row

    # Get all topics with their doc counts
    topics = conn.execute("""
        SELECT t.id, t.name, COUNT(dt.doc_id) as doc_count
        FROM topics t
        JOIN doc_topics dt ON t.id = dt.topic_id
        GROUP BY t.id
        HAVING doc_count >= ?
        ORDER BY doc_count DESC
    """, (min_docs,)).fetchall()

    topic_ids = {t["id"] for t in topics}
    topic_map = {t["id"]: {"id": t["id"], "name": t["name"], "doc_count": t["doc_count"]} for t in topics}

    # Get all doc-topic links for included topics
    doc_topics = conn.execute("""
        SELECT dt.doc_id, dt.topic_id, dt.relevance
        FROM doc_topics dt
        WHERE dt.topic_id IN ({})
    """.format(",".join("?" * len(topic_ids))), list(topic_ids)).fetchall()

    # Build doc -> topics mapping
    docs_by_topic = defaultdict(set)
    topics_by_doc = defaultdict(set)
    for dt in doc_topics:
        docs_by_topic[dt["topic_id"]].add(dt["doc_id"])
        topics_by_doc[dt["doc_id"]].add(dt["topic_id"])

    # Compute co-occurrence edges
    edge_weights = defaultdict(int)
    edge_docs = defaultdict(set)
    for doc_id, topic_set in topics_by_doc.items():
        topic_list = sorted(topic_set)
        for i, t1 in enumerate(topic_list):
            for t2 in topic_list[i + 1:]:
                pair = (min(t1, t2), max(t1, t2))
                edge_weights[pair] += 1
                edge_docs[pair].add(doc_id)

    # Build edges
    edges = []
    for (t1, t2), weight in edge_weights.items():
        if weight >= min_edge_weight and t1 in topic_ids and t2 in topic_ids:
            edges.append({
                "source": t1,
                "target": t2,
                "weight": weight,
                "doc_ids": sorted(edge_docs[(t1, t2)]),
            })

    # Get document metadata
    doc_ids_used = set()
    for dt in doc_topics:
        doc_ids_used.add(dt["doc_id"])

    documents = []
    if doc_ids_used:
        rows = conn.execute("""
            SELECT id, title, source, source_url, created_at, raw_text, author
            FROM documents
            WHERE id IN ({})
        """.format(",".join("?" * len(doc_ids_used))), list(doc_ids_used)).fetchall()
        documents = []
        for r in rows:
            d = dict(r)
            raw = d.pop("raw_text", "") or ""
            d["snippet"] = raw[:200].replace("\n", " ").strip()
            documents.append(d)

    conn.close()

    # Attach doc_ids to each node
    for tid, topic in topic_map.items():
        topic["doc_ids"] = sorted(docs_by_topic.get(tid, set()))

    # Nodes
    nodes = sorted(topic_map.values(), key=lambda x: -x["doc_count"])

    result = {
        "nodes": nodes,
        "edges": edges,
        "documents": documents,
    }
    if LIFEGRAPH_AUTHOR:
        result["author"] = LIFEGRAPH_AUTHOR
    return result


def export_graph_json(path: str, **kwargs):
    """Build graph and write to JSON file."""
    graph = build_graph(**kwargs)
    with open(path, "w") as f:
        json.dump(graph, f, indent=2)
    return graph
