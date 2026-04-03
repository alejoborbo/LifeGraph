import click

from lifegraph.connectors.google_docs import GoogleDocsConnector
from lifegraph.db import count_documents_by_source, init_db


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


if __name__ == "__main__":
    cli()
