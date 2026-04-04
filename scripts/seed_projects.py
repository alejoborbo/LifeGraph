"""Seed projects from the existing CLUSTERS mapping.

Each cluster becomes a project, with documents linked based on
the same topic-matching logic used by build_clustered_graph.
"""
import sys

sys.path.insert(0, ".")

from lifegraph.clusters import CLUSTERS, _get_category
from lifegraph.db import (
    create_project,
    get_connection,
    init_db,
    link_doc_to_project,
    get_project_by_name,
)
from lifegraph.models import Project


def main():
    init_db()
    conn = get_connection()

    # Load all topics and their doc links
    rows = conn.execute("""
        SELECT t.name as topic_name, dt.doc_id
        FROM topics t
        JOIN doc_topics dt ON t.id = dt.topic_id
    """).fetchall()

    # Build topic_name -> cluster mapping
    topic_to_cluster = {}
    for cluster, patterns in CLUSTERS.items():
        for pat in patterns:
            topic_to_cluster[pat] = cluster

    # Collect doc_ids per cluster
    from collections import defaultdict
    cluster_docs = defaultdict(set)
    for row in rows:
        cluster = topic_to_cluster.get(row["topic_name"])
        if cluster:
            cluster_docs[cluster].add(row["doc_id"])

    # Get earliest doc date per cluster for start_date
    doc_dates = {}
    date_rows = conn.execute("SELECT id, created_at FROM documents").fetchall()
    for r in date_rows:
        if r["created_at"]:
            doc_dates[r["id"]] = r["created_at"]
    conn.close()

    created = 0
    linked = 0
    for cluster_name, doc_ids in sorted(cluster_docs.items()):
        # Skip if project already exists
        if get_project_by_name(cluster_name):
            print(f"  Exists: {cluster_name}")
            project = get_project_by_name(cluster_name)
            pid = project["id"]
        else:
            # Compute start_date from earliest doc
            dates = [doc_dates[did] for did in doc_ids if did in doc_dates]
            start_date = min(dates) if dates else None

            project = Project(
                id=None,
                name=cluster_name,
                status="active",
                category=_get_category(cluster_name),
                start_date=start_date,
            )
            pid = create_project(project)
            created += 1
            print(f"  Created: {cluster_name} ({len(doc_ids)} docs)")

        # Link documents
        for doc_id in doc_ids:
            link_doc_to_project(pid, doc_id)
            linked += 1

    print(f"\nDone! {created} projects created, {linked} doc links added.")


if __name__ == "__main__":
    main()
