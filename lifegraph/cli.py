import click

from lifegraph.connectors.google_docs import GoogleDocsConnector
from lifegraph.db import (
    count_documents_by_source,
    get_all_topics_with_counts,
    get_documents_without_topics,
    init_db,
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
    g = build_clustered_graph(min_edge_weight=min_edge)
    with open(output, "w") as f:
        json.dump(g, f, indent=2)
    click.echo(f"Graph exported: {len(g['nodes'])} nodes, {len(g['edges'])} edges, {len(g['documents'])} docs")
    click.echo(f"Written to {output}")


if __name__ == "__main__":
    cli()
