"""GitHub connector — fetches PRs, issues, and reviews for the authenticated user."""

import requests

from lifegraph.config import GITHUB_TOKEN, GITHUB_REPO_PROJECT_MAP
from lifegraph.connectors.base import BaseConnector
from lifegraph.db import get_all_projects, get_project_by_name, upsert_project_link

API = "https://api.github.com"


def _gh_status(item: dict) -> str:
    if item.get("pull_request") and item.get("pull_request", {}).get("merged_at"):
        return "Merged"
    return "Open" if item["state"] == "open" else "Closed"


def _repo_from_url(url: str) -> str:
    """Extract 'owner/repo' from a GitHub API URL."""
    # https://api.github.com/repos/owner/repo -> owner/repo
    parts = url.rstrip("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


class GitHubConnector(BaseConnector):
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.session = None
        self.username = None

    def authenticate(self):
        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN not set. Create a personal access token at "
                "https://github.com/settings/tokens and add it to .env"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        })
        resp = self.session.get(f"{API}/user")
        resp.raise_for_status()
        self.username = resp.json()["login"]
        return self.username

    def list_documents(self) -> list[dict]:
        return []

    def fetch_content(self, doc_id: str) -> str:
        return ""

    def sync(self) -> int:
        if not self.session:
            self.authenticate()

        count = 0

        # 1. PRs authored
        print("  Fetching your PRs...")
        prs = self._search(f"author:{self.username} type:pr sort:updated")
        for item in prs:
            count += self._store_item(item, "github-pr")
        print(f"    {len(prs)} PRs found")

        # 2. Issues authored
        print("  Fetching your issues...")
        issues = self._search(f"author:{self.username} type:issue sort:updated")
        for item in issues:
            count += self._store_item(item, "github-issue")
        print(f"    {len(issues)} issues found")

        # 3. PRs you reviewed
        print("  Fetching PRs you reviewed...")
        reviews = self._search(f"reviewed-by:{self.username} type:pr sort:updated")
        for item in reviews:
            count += self._store_item(item, "github-review")
        print(f"    {len(reviews)} reviews found")

        return count

    def _search(self, query: str, max_pages: int = 5) -> list[dict]:
        """Search GitHub issues/PRs using the search API."""
        items = []
        page = 1
        while page <= max_pages:
            resp = self.session.get(f"{API}/search/issues", params={
                "q": query, "per_page": 100, "page": page,
            })
            if resp.status_code == 403:
                print(f"    Rate limited, stopping at {len(items)} results")
                break
            resp.raise_for_status()
            data = resp.json()
            items.extend(data.get("items", []))
            if len(items) >= data.get("total_count", 0):
                break
            page += 1
        return items

    def _store_item(self, item: dict, source_type: str) -> int:
        """Store a GitHub item as a project_link. Returns 1 if stored, 0 if skipped."""
        repo = _repo_from_url(item["repository_url"])
        source_id = f"{repo}#{item['number']}"

        # Find matching project
        project_id = self._match_project(repo, item)
        if not project_id:
            return 0

        upsert_project_link(
            project_id=project_id,
            url=item["html_url"],
            source_type=source_type,
            source_id=source_id,
            title=item["title"],
            status=_gh_status(item),
            assignee=(item.get("assignee") or {}).get("login"),
            created_at=item["created_at"],
        )
        return 1

    def _match_project(self, repo: str, item: dict) -> int | None:
        """Try to match a GitHub item to a LifeGraph project."""
        # 1. Explicit mapping from config
        project_name = GITHUB_REPO_PROJECT_MAP.get(repo)
        if project_name:
            p = get_project_by_name(project_name)
            if p:
                return p["id"]

        # 2. Fuzzy match: check if any project name appears in the repo name,
        #    PR title, or labels
        text = f"{repo} {item['title']} {' '.join(l['name'] for l in item.get('labels', []))}".lower()
        projects = get_all_projects()
        best = None
        best_score = 0
        for p in projects:
            # Match keywords from project name
            keywords = [w.lower() for w in p["name"].split() if len(w) > 3]
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best = p

        if best and best_score >= 1:
            return best["id"]

        return None
