import click

from lifegraph.connectors.google_docs import GoogleDocsConnector
from lifegraph.db import (
    count_documents_by_source,
    get_all_projects,
    get_all_topics_with_counts,
    get_documents_without_topics,
    get_project_by_name,
    get_project_documents,
    get_work_summary,
    init_db,
    rebuild_fts,
    search_documents,
    search_project_links,
    search_projects,
    update_project_phase,
    update_project_status,
)
from lifegraph.extractor import process_document
from lifegraph.graph import export_graph_json
from lifegraph.clusters import build_clustered_graph


@click.group()
def cli():
    """LifeGraph - Build a knowledge graph from your documents."""
    init_db()


@cli.command()
def auth():
    """Authenticate with Google (opens browser for OAuth consent)."""
    connector = GoogleDocsConnector()
    try:
        connector.authenticate()
        click.echo("Successfully authenticated with Google!")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.group()
def sync():
    """Sync documents from a source."""


@sync.command("google-docs")
def sync_google_docs():
    """Fetch all Google Docs and store them locally."""
    connector = GoogleDocsConnector()
    click.echo("Authenticating with Google...")
    connector.authenticate()

    click.echo("Fetching documents...")
    count = connector.sync()
    click.echo(f"Done! Synced {count} document(s).")


@sync.command("confluence")
def sync_confluence():
    """Fetch all Confluence pages and store them locally."""
    from lifegraph.connectors.confluence import ConfluenceConnector

    connector = ConfluenceConnector()
    click.echo("Authenticating with Confluence...")
    try:
        connector.authenticate()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo("Fetching pages...")
    count = connector.sync()
    click.echo(f"Done! Synced {count} page(s).")


@sync.command("confluence-discover")
@click.option("--spaces", default=None, help="Comma-separated space keys to search (default: all).")
@click.option("--max-pages", default=100, help="Max pages to sync per topic query.")
@click.option("--top-topics", default=10, help="Number of top topics to search for.")
def sync_confluence_discover(spaces, max_pages, top_topics):
    """Discover Confluence pages by others related to your topics."""
    from lifegraph.connectors.confluence import ConfluenceConnector

    connector = ConfluenceConnector()
    click.echo("Authenticating with Confluence...")
    try:
        connector.authenticate()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Get top topics from existing graph
    topics = get_all_topics_with_counts()
    if not topics:
        click.echo("No topics extracted yet. Run 'lifegraph extract' first.")
        raise SystemExit(1)

    search_topics = topics[:top_topics]
    click.echo(f"Searching Confluence for pages related to your top {len(search_topics)} topics...")

    from datetime import datetime, timezone
    from lifegraph.models import Document
    from lifegraph.db import upsert_document, document_exists

    total = 0
    seen_ids = set()

    for t in search_topics:
        # Build CQL query: search for topic name in title or text
        topic_name = t["name"]
        cql = f'type=page AND (title ~ "{topic_name}" OR text ~ "{topic_name}")'
        if spaces:
            space_list = " OR ".join(f'space="{s.strip()}"' for s in spaces.split(","))
            cql += f" AND ({space_list})"
        cql += " ORDER BY lastmodified DESC"

        click.echo(f"  Searching: {topic_name}...", nl=False)

        try:
            pages = connector.search_pages(cql, max_results=max_pages // top_topics)
        except Exception as e:
            click.echo(f" error: {e}")
            continue

        count = 0
        for page in pages:
            if page["id"] in seen_ids:
                continue
            seen_ids.add(page["id"])

            try:
                text = connector.fetch_content(page["id"])
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
                pass  # skip individual page errors silently

        click.echo(f" {count} page(s)")
        total += count

    click.echo(f"\nDone! Discovered {total} page(s) across {len(search_topics)} topics.")
    click.echo("Run 'lifegraph extract' to extract topics from new pages.")


@sync.command("github-discover")
@click.option("--top-topics", default=5, help="Number of top topics to search for.")
@click.option("--max-results", default=50, help="Max results per topic query.")
def sync_github_discover(top_topics, max_results):
    """Discover GitHub PRs/issues by others related to your topics."""
    import subprocess
    from datetime import datetime, timezone
    from lifegraph.db import upsert_document, document_exists
    from lifegraph.models import Document

    # Check gh CLI
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            click.echo("Error: gh CLI not authenticated. Run 'gh auth login'.", err=True)
            raise SystemExit(1)
    except FileNotFoundError:
        click.echo("Error: gh CLI not found. Install it: https://cli.github.com", err=True)
        raise SystemExit(1)

    topics = get_all_topics_with_counts()
    if not topics:
        click.echo("No topics yet. Run 'lifegraph extract' first.")
        raise SystemExit(1)

    search_topics = topics[:top_topics]
    click.echo(f"Searching GitHub for PRs/issues related to your top {len(search_topics)} topics...")

    total = 0
    seen = set()
    per_topic = max(max_results // top_topics, 5)

    for t in search_topics:
        topic = t["name"]
        click.echo(f"  Searching: {topic}...", nl=False)

        try:
            result = subprocess.run(
                ["gh", "search", "issues", topic, "--owner=DataDog",
                 "--limit", str(per_topic), "--json",
                 "number,title,url,author,repository,state,createdAt,body"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                click.echo(" error")
                continue

            import json
            items = json.loads(result.stdout)
        except Exception as e:
            click.echo(f" error: {e}")
            continue

        count = 0
        for item in items:
            repo = item.get("repository", {}).get("nameWithOwner", "")
            number = item.get("number", "")
            source_id = f"gh-discover:{repo}#{number}"
            if source_id in seen or document_exists("github", source_id):
                continue
            seen.add(source_id)

            author = item.get("author", {}).get("login", "")
            body = (item.get("body") or "")[:2000]

            doc = Document(
                id=None,
                title=f"[{repo}] {item.get('title', '')}",
                source="github",
                source_id=source_id,
                source_url=item.get("url", ""),
                created_at=item.get("createdAt"),
                fetched_at=datetime.now(timezone.utc).isoformat(),
                raw_text=f"{item.get('title', '')}\n\n{body}",
                author=author,
            )
            upsert_document(doc)
            count += 1

        click.echo(f" {count} item(s)")
        total += count

    click.echo(f"\nDone! Discovered {total} GitHub item(s).")
    click.echo("Run 'lifegraph extract' then 'lifegraph graph' to update.")


@sync.command("slack")
@click.option("--channel", default=None, help="Sync a single channel (name or ID) instead of all configured.")
def sync_slack(channel):
    """Fetch threads from Slack channels and store as documents."""
    from lifegraph.connectors.slack import SlackConnector

    connector = SlackConnector()
    if channel:
        connector.channel_filter = [channel]
    click.echo("Authenticating with Slack...")
    try:
        user = connector.authenticate()
        click.echo(f"Authenticated as {user}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Syncing channels...")
    count = connector.sync()
    click.echo(f"Done! Synced {count} thread(s).")


@sync.command("github")
def sync_github():
    """Fetch your PRs, issues, and reviews from GitHub."""
    from lifegraph.connectors.github import GitHubConnector

    connector = GitHubConnector()
    click.echo("Authenticating with GitHub...")
    try:
        user = connector.authenticate()
        click.echo(f"Authenticated as {user}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo("Syncing your GitHub activity...")
    count = connector.sync()
    click.echo(f"Done! Linked {count} item(s) to projects.")


@cli.command()
def status():
    """Show the number of documents stored by source."""
    counts = count_documents_by_source()
    if not counts:
        click.echo("No documents synced yet. Run 'lifegraph sync google-docs' to get started.")
        return

    click.echo("Documents by source:")
    total = 0
    for source, count in sorted(counts.items()):
        click.echo(f"  {source}: {count}")
        total += count
    click.echo(f"  Total: {total}")


@cli.command()
@click.option("--limit", default=0, help="Max documents to process (0 = all).")
def extract(limit):
    """Extract topics from documents using Claude API."""
    docs = get_documents_without_topics()
    if not docs:
        click.echo("All documents already have topics extracted.")
        return

    if limit:
        docs = docs[:limit]

    click.echo(f"Extracting topics for {len(docs)} document(s)...")

    for i, doc in enumerate(docs, 1):
        click.echo(f"  [{i}/{len(docs)}] {doc['title'][:60]}...", nl=False)
        try:
            topics = process_document(doc["id"], doc["title"], doc["raw_text"])
            click.echo(f" -> {len(topics)} topics")
        except Exception as e:
            click.echo(f" ERROR: {e}", err=True)

    click.echo("Done!")


@cli.command()
def topics():
    """List all extracted topics and their document counts."""
    all_topics = get_all_topics_with_counts()
    if not all_topics:
        click.echo("No topics extracted yet. Run 'lifegraph extract' first.")
        return

    click.echo(f"{'Topic':<50} Docs")
    click.echo("-" * 56)
    for t in all_topics:
        click.echo(f"  {t['name']:<48} {t['doc_count']}")
    click.echo(f"\nTotal: {len(all_topics)} topics")


@cli.command()
@click.option("--min-edge", default=2, help="Minimum co-occurrence for an edge.")
@click.option("--output", default="web/graph.json", help="Output JSON path.")
def graph(min_edge, output):
    """Export the clustered knowledge graph as JSON for visualization."""
    import json, os
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    # Load previous graph for diff
    prev_node_names = set()
    prev_doc_ids = set()
    prev_edge_keys = set()
    if os.path.exists(output):
        try:
            with open(output) as f:
                prev = json.load(f)
            prev_node_names = {n["name"] for n in prev.get("nodes", [])}
            prev_doc_ids = {d["id"] for d in prev.get("documents", [])}
            prev_edge_keys = {f"{e['source']}-{e['target']}" for e in prev.get("edges", [])}
        except Exception:
            pass

    g = build_clustered_graph(min_edge_weight=min_edge)

    # Compute diff
    new_nodes = [n["name"] for n in g["nodes"] if n["name"] not in prev_node_names]
    new_docs = [d["id"] for d in g["documents"] if d["id"] not in prev_doc_ids]
    new_edges = [e for e in g["edges"] if f"{e['source']}-{e['target']}" not in prev_edge_keys]

    # Mark new items in the graph data
    for n in g["nodes"]:
        n["is_new"] = n["name"] not in prev_node_names
    for d in g["documents"]:
        d["is_new"] = d["id"] not in prev_doc_ids

    g["diff"] = {
        "new_nodes": len(new_nodes),
        "new_docs": len(new_docs),
        "new_edges": len(new_edges),
        "node_names": new_nodes[:10],
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    with open(output, "w") as f:
        json.dump(g, f, indent=2)

    click.echo(f"Graph exported: {len(g['nodes'])} nodes, {len(g['edges'])} edges, {len(g['documents'])} docs")
    if new_nodes or new_docs:
        click.echo(f"What's new: {len(new_nodes)} topics, {len(new_docs)} docs, {len(new_edges)} connections")
    click.echo(f"Written to {output}")


@cli.command()
@click.option("--days", default=30, help="Number of days to look back.")
@click.option("--since", "since_date", default=None, help="Start date (YYYY-MM-DD).")
@click.option("--until", "until_date", default=None, help="End date (YYYY-MM-DD).")
@click.option("--format", "fmt", type=click.Choice(["plain", "markdown"]), default="plain")
def report(days, since_date, until_date, fmt):
    """Show a summary of what you worked on in a date range."""
    from datetime import datetime, timedelta

    if since_date:
        start = since_date
    else:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    if until_date:
        end = until_date
    else:
        end = datetime.now().strftime("%Y-%m-%d")

    docs = get_work_summary(start, end + "T23:59:59")

    if not docs:
        click.echo(f"No documents found between {start} and {end}.")
        return

    # Group docs by topic cluster -> category
    # Import cluster mapping for category assignment
    from lifegraph.clusters import CLUSTERS, _get_category

    # Build reverse map: topic name -> cluster
    topic_to_cluster = {}
    for cluster, patterns in CLUSTERS.items():
        for pat in patterns:
            topic_to_cluster[pat] = cluster

    # Group docs by cluster
    from collections import defaultdict
    cluster_docs = defaultdict(list)
    uncategorized = []

    for doc in docs:
        topic_names = (doc["topics"] or "").split("||")
        placed = False
        for tname in topic_names:
            tname = tname.strip()
            cluster = topic_to_cluster.get(tname)
            if cluster:
                cluster_docs[cluster].append(doc)
                placed = True
                break
        if not placed:
            uncategorized.append(doc)

    # Group clusters by category
    cat_clusters = defaultdict(list)
    for cluster in cluster_docs:
        cat = _get_category(cluster)
        cat_clusters[cat].append(cluster)

    cat_labels = {
        "posture": "Posture & Coverage",
        "automation": "Automation & AI",
        "strategy": "Strategy & Planning",
        "ux": "UX & Design",
        "team": "Team & Meetings",
        "teaching": "Teaching & Education",
        "personal": "Personal",
        "code": "Code & Engineering",
        "other": "Other",
    }

    # Format dates for header
    start_fmt = datetime.strptime(start, "%Y-%m-%d").strftime("%b %-d, %Y")
    end_fmt = datetime.strptime(end, "%Y-%m-%d").strftime("%b %-d, %Y")

    if fmt == "markdown":
        click.echo(f"# What I worked on: {start_fmt} - {end_fmt} ({len(docs)} documents)\n")
    else:
        click.echo(f"What I worked on: {start_fmt} - {end_fmt} ({len(docs)} documents)\n")

    # Print by category
    cat_order = ["posture", "automation", "strategy", "ux", "team", "teaching", "code", "personal", "other"]
    for cat in cat_order:
        clusters = cat_clusters.get(cat, [])
        if not clusters:
            continue

        total = sum(len(cluster_docs[c]) for c in clusters)
        label = cat_labels.get(cat, cat.upper())

        if fmt == "markdown":
            click.echo(f"## {label} ({total} docs)\n")
        else:
            click.echo(f"{label.upper()} ({total} docs)")

        for cluster in sorted(clusters, key=lambda c: -len(cluster_docs[c])):
            if fmt == "markdown":
                click.echo(f"**{cluster}**")
            else:
                click.echo(f"  {cluster}")

            for doc in cluster_docs[cluster]:
                date_str = ""
                if doc["created_at"]:
                    try:
                        date_str = datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00")).strftime("%b %-d")
                    except (ValueError, TypeError):
                        pass

                if fmt == "markdown":
                    url = doc.get("source_url", "")
                    if url:
                        click.echo(f"- [{doc['title']}]({url}) ({date_str})")
                    else:
                        click.echo(f"- {doc['title']} ({date_str})")
                else:
                    click.echo(f"    - {doc['title']} ({date_str})")

            click.echo()

    if uncategorized:
        if fmt == "markdown":
            click.echo(f"## Uncategorized ({len(uncategorized)} docs)\n")
        else:
            click.echo(f"UNCATEGORIZED ({len(uncategorized)} docs)")
        for doc in uncategorized:
            date_str = ""
            if doc["created_at"]:
                try:
                    date_str = datetime.fromisoformat(doc["created_at"]).strftime("%b %-d")
                except (ValueError, TypeError):
                    pass
            if fmt == "markdown":
                click.echo(f"- {doc['title']} ({date_str})")
            else:
                click.echo(f"    - {doc['title']} ({date_str})")
        click.echo()


@cli.command()
def projects():
    """List all projects with status and doc count."""
    all_projects = get_all_projects()
    if not all_projects:
        click.echo("No projects yet. Run: python scripts/seed_projects.py")
        return

    status_colors = {
        "active": "blue", "shipped": "green", "blocked": "yellow",
        "idea": "white", "abandoned": "red",
    }

    # Group by category
    from collections import defaultdict
    by_cat = defaultdict(list)
    for p in all_projects:
        by_cat[p["category"] or "other"].append(p)

    for cat in sorted(by_cat.keys()):
        projs = by_cat[cat]
        click.echo(click.style(f"\n{cat.upper()}", fg="cyan", bold=True))
        for p in projs:
            status = p["status"]
            color = status_colors.get(status, "white")
            last = p["last_activity"][:10] if p["last_activity"] else "—"
            click.echo(
                f"  [{click.style(status, fg=color)}] "
                f"{p['name']} ({p['doc_count']} docs, last: {last})"
            )


@cli.command("project")
@click.argument("name")
def project_show(name):
    """Show details for a project by name (partial match)."""
    # Find by partial match
    all_projects = get_all_projects()
    matches = [p for p in all_projects if name.lower() in p["name"].lower()]
    if not matches:
        click.echo(f"No project matching '{name}'")
        return
    p = matches[0]
    click.echo(f"\n{click.style(p['name'], bold=True)}")
    click.echo(f"  Status:   {p['status']}")
    click.echo(f"  Category: {p['category'] or '—'}")
    click.echo(f"  Docs:     {p['doc_count']}")
    click.echo(f"  Started:  {(p['start_date'] or '—')[:10]}")
    click.echo(f"  Last:     {(p['last_activity'] or '—')[:10]}")

    docs = get_project_documents(p["id"])
    if docs:
        click.echo(f"\n  Documents:")
        for d in docs[:15]:
            date = d["created_at"][:10] if d["created_at"] else ""
            click.echo(f"    - {d['title']} ({d['source']}, {date})")
        if len(docs) > 15:
            click.echo(f"    ... and {len(docs) - 15} more")


@cli.command("set-status")
@click.argument("name")
@click.argument("status", type=click.Choice(["idea", "active", "blocked", "shipped", "abandoned"]))
def set_status(name, status):
    """Set the status of a project."""
    p = get_project_by_name(name)
    if not p:
        # Try partial match
        all_projects = get_all_projects()
        matches = [pr for pr in all_projects if name.lower() in pr["name"].lower()]
        if not matches:
            click.echo(f"No project matching '{name}'")
            return
        p = matches[0]
    update_project_status(p["id"], status)
    click.echo(f"Updated '{p['name']}' -> {status}")


@cli.command()
@click.option("--port", default=8042, help="Port to serve on.")
def serve(port):
    """Start the local LifeGraph web server."""
    from lifegraph.server import main
    main(port=port)


@cli.command()
@click.option("--days", default=7, help="Number of days to look back.")
@click.option("--since", "since_date", default=None, help="Start date (YYYY-MM-DD).")
@click.option("--until", "until_date", default=None, help="End date (YYYY-MM-DD).")
@click.option("--copy", is_flag=True, help="Copy the result to clipboard.")
def summary(days, since_date, until_date, copy):
    """Generate an AI-powered summary of your recent work."""
    from datetime import datetime, timedelta
    from lifegraph.summarizer import generate_summary

    if since_date:
        start = since_date
    else:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = until_date or datetime.now().strftime("%Y-%m-%d")

    click.echo(f"Generating summary for {start} to {end}...")
    result = generate_summary(start, end)
    click.echo()
    click.echo(result)

    if copy:
        try:
            import subprocess
            subprocess.run(["pbcopy"], input=result.encode(), check=True)
            click.echo("\n(Copied to clipboard)")
        except Exception:
            pass


@cli.command()
@click.argument("query")
@click.option("--source", type=click.Choice(["google-docs", "google-slides", "confluence", "slack", "github"]), default=None)
@click.option("--project", default=None, help="Filter to a project name (partial match).")
@click.option("--limit", default=20)
def search(query, source, project, limit):
    """Full-text search across documents, projects, and tickets.

    Prefix syntax: jira:query, github:query, status:blocked, confluence:query
    """
    # Handle prefix syntax
    prefix_map = {"jira:": "jira", "github:": "github", "confluence:": "confluence"}
    for prefix, src in prefix_map.items():
        if query.lower().startswith(prefix):
            remainder = query[len(prefix):].strip()
            if prefix in ("jira:", "github:"):
                results = search_project_links(remainder, source_type=src)
                if not results:
                    click.echo("No matching tickets found.")
                    return
                for r in results:
                    click.echo(
                        f"  [{r['source_type']}] {r['source_id']} — {r['title']}"
                        f"  ({r.get('status', '?')}) in {r['project_name']}"
                    )
                return
            else:
                source = src
                query = remainder
                break

    # Handle status: prefix
    if query.lower().startswith("status:"):
        status = query.split(":")[1].strip()
        results = search_projects(status=status)
        if not results:
            click.echo(f"No projects with status '{status}'.")
            return
        for p in results:
            phase = p.get("phase") or ""
            click.echo(f"  [{p['status']}] {p['name']} ({p['doc_count']} docs){' — ' + phase if phase else ''}")
        return

    # Resolve project name to ID
    project_id = None
    if project:
        all_projects = get_all_projects()
        matches = [p for p in all_projects if project.lower() in p["name"].lower()]
        if matches:
            project_id = matches[0]["id"]

    # Document search
    results = search_documents(query, source=source, project_id=project_id, limit=limit)
    if not results:
        click.echo("No documents found.")
        return

    click.echo(f"Found {len(results)} document(s):\n")
    for r in results:
        date = r["created_at"][:10] if r.get("created_at") else ""
        snippet = (r.get("snippet") or "")[:120].replace("\n", " ")
        click.echo(f"  {r['title']}")
        click.echo(f"    {r['source']} · {date}")
        if snippet:
            click.echo(f"    {snippet}")
        click.echo()


@cli.command("rebuild-fts")
def rebuild_fts_cmd():
    """Rebuild the full-text search index (run once after upgrade)."""
    rebuild_fts()
    click.echo("FTS index rebuilt.")


@cli.command()
@click.option("--days", default=7, help="Number of days to look back.")
@click.option("--no-slack", is_flag=True, help="Print only, don't post to Slack.")
def digest(days, no_slack):
    """Weekly digest: new docs by others on your topics."""
    from lifegraph.digest import run_digest

    click.echo(f"Building digest for the last {days} days...\n")
    result = run_digest(days=days, post=not no_slack)
    click.echo(result)


@cli.command("auto-cluster")
def auto_cluster_cmd():
    """Auto-cluster topics using Claude (replaces hand-crafted clusters)."""
    from lifegraph.auto_cluster import auto_cluster
    import json
    from pathlib import Path
    from lifegraph.config import DATABASE_PATH

    click.echo("Sending topics to Claude for clustering...")
    try:
        clusters = auto_cluster()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    out_path = Path(DATABASE_PATH).parent / "auto_clusters.json"
    with open(out_path, "w") as f:
        json.dump(clusters, f, indent=2)

    click.echo(f"Generated {len(clusters)} clusters -> {out_path}")
    for name, info in sorted(clusters.items()):
        topics = info["topics"] if isinstance(info, dict) else info
        cat = info.get("category", "?") if isinstance(info, dict) else "?"
        click.echo(f"  [{cat}] {name}: {len(topics)} topics")

    click.echo(f"\nRun 'lifegraph graph' to rebuild with new clusters.")


@cli.command("compute-phases")
def compute_phases():
    """Auto-compute project phases (Planning/Building/Shipped) from artifacts."""
    from lifegraph.heuristics import compute_all_phases

    phases = compute_all_phases()
    projects = {p["id"]: p for p in get_all_projects()}
    changed = 0
    for pid, phase in phases.items():
        old = projects[pid].get("phase") or "?"
        update_project_phase(pid, phase)
        name = projects[pid]["name"]
        if old != phase:
            click.echo(f"  {name}: {old} -> {phase}")
            changed += 1
        else:
            click.echo(f"  {name}: {phase} (unchanged)")
    click.echo(f"\nUpdated {len(phases)} projects ({changed} changed).")


if __name__ == "__main__":
    cli()
