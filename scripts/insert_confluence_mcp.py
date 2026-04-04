"""Insert Confluence pages fetched via MCP into LifeGraph DB."""
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from lifegraph.connectors.confluence import _strip_html
from lifegraph.db import init_db, upsert_document
from lifegraph.models import Document

BASE_URL = "https://datadoghq.atlassian.net/wiki"

PAGES = [
    {
        "id": "6467977545",
        "title": "Datadog-Managed Monitors (Preview): Self-Improving Detection with Zero Setup",
        "created_at": "2026-03-26T17:49:22.436Z",
        "url": f"{BASE_URL}/spaces/AP/pages/6467977545/Datadog-Managed+Monitors+Preview+Self-Improving+Detection+with+Zero+Setup",
    },
    {
        "id": "5965447676",
        "title": "MCP Integration",
        "created_at": "2025-12-18T11:09:49.786Z",
        "url": f"{BASE_URL}/spaces/AP/pages/5965447676/MCP+Integration",
    },
    {
        "id": "2949383224",
        "title": "Rules Documentation",
        "created_at": "2023-04-17T09:33:15.700Z",
        "url": f"{BASE_URL}/spaces/GTMSEH/pages/2949383224/Rules+Documentation",
    },
    {
        "id": "2762998651",
        "title": "Hack-a-dog ideas",
        "created_at": "2022-12-23T08:53:15.226Z",
        "url": f"{BASE_URL}/spaces/AP/pages/2762998651/Hack-a-dog+ideas",
    },
    {
        "id": "3786637577",
        "title": "Enable restriction_policy terraform resource for monitor",
        "created_at": "2024-06-07T23:02:42.519Z",
        "url": f"{BASE_URL}/spaces/AAA/pages/3786637577/Enable+restriction_policy+terraform+resource+for+monitor",
    },
    {
        "id": "5156044936",
        "title": "AI Features and Roadmap",
        "created_at": "2025-06-01T15:32:50.801Z",
        "url": f"{BASE_URL}/spaces/GTMSEH/pages/5156044936/AI+Features+and+Roadmap",
    },
    {
        "id": "5094278215",
        "title": "Alerting AI Squad",
        "created_at": "2025-05-14T12:02:25.759Z",
        "url": f"{BASE_URL}/spaces/AP/pages/5094278215/Alerting+AI+Squad",
    },
    {
        "id": "5386142136",
        "title": "[MOPU] Evaluation & Validation",
        "created_at": "2025-08-11T08:59:15.293Z",
        "url": f"{BASE_URL}/spaces/AP/pages/5386142136/MOPU+Evaluation+Validation",
    },
    {
        "id": "5457969775",
        "title": "Linux Conference - Open source GenAI",
        "created_at": "2025-09-01T10:10:09.233Z",
        "url": f"{BASE_URL}/spaces/~63dac55b1b13d42998e196c9/pages/5457969775/Linux+Conference+-+Open+source+GenAI",
    },
    {
        "id": "5131667888",
        "title": "Automatic Monitor Creation",
        "created_at": "2025-05-25T18:33:35.925Z",
        "url": f"{BASE_URL}/spaces/~63dac55b1b13d42998e196c9/pages/5131667888/Automatic+Monitor+Creation",
    },
    {
        "id": "2839184571",
        "title": "Capucine Marteau - Overview",
        "created_at": "2023-02-06T14:56:11.073Z",
        "url": f"{BASE_URL}/spaces/~63dac55b1b13d42998e196c9/overview",
    },
    {
        "id": "396755025",
        "title": "SSH Key Setup",
        "created_at": "2020-06-10T22:20:45.295Z",
        "url": f"{BASE_URL}/spaces/EOEX/pages/396755025/SSH+Key+Setup",
    },
    {
        "id": "5265817923",
        "title": "Q2/2025 OpenTelemetry OKR July 02nd",
        "created_at": "2025-07-02T12:44:53.795Z",
        "url": f"{BASE_URL}/spaces/APM/pages/5265817923/Q2+2025+OpenTelemetry+OKR+July+02nd",
    },
    {
        "id": "4728750092",
        "title": "Invalid telemetry payload investigation",
        "created_at": "2025-02-13T14:13:21.138Z",
        "url": f"{BASE_URL}/spaces/~71202052cd050b50594fa798ed696dce3fe4bd/pages/4728750092/Invalid+telemetry+payload+investigation",
    },
    {
        "id": "5350850794",
        "title": "Damien Mehala - Promotion Addendum",
        "created_at": "2025-07-30T08:04:17.944Z",
        "url": f"{BASE_URL}/spaces/~71202052cd050b50594fa798ed696dce3fe4bd/pages/5350850794/Addendum",
    },
    {
        "id": "2991260931",
        "title": "[Product] Spring 2023 - Event Platform Updates",
        "created_at": "2023-05-10T14:01:11.419Z",
        "url": f"{BASE_URL}/spaces/~504006737/pages/2991260931",
    },
]

# HTML content for each page (stored separately to keep the metadata clean)
HTML_CONTENT = {}

def load_html_content():
    """Load HTML content from the pages.json file."""
    with open("scripts/confluence_pages_html.json", "r") as f:
        return json.load(f)


def main():
    init_db()
    html_data = load_html_content()

    count = 0
    for page in PAGES:
        html = html_data.get(page["id"], "")
        text = _strip_html(html)
        if not text.strip():
            print(f"  Skipping '{page['title']}' (empty content)")
            continue

        doc = Document(
            id=None,
            title=page["title"],
            source="confluence",
            source_id=page["id"],
            source_url=page["url"],
            created_at=page["created_at"],
            fetched_at=datetime.now(timezone.utc).isoformat(),
            raw_text=text,
        )
        upsert_document(doc)
        count += 1
        print(f"  Inserted: {page['title']}")

    print(f"\nDone! Inserted {count} Confluence pages.")


if __name__ == "__main__":
    main()
