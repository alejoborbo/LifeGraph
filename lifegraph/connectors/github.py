"""GitHub connector — fetches PRs and issues, stores them as project_links."""

import requests

from lifegraph.config import GITHUB_TOKEN, GITHUB_REPOS, GITHUB_REPO_PROJECT_MAP
from lifegraph.connectors.base import BaseConnector
from lifegraph.db import get_project_by_name, upsert_project_link


def _gh_status(item: dict, is_pr: bool) -> str:
    if is_pr and item.get("merged_at"):
        return "Merged"
    return "Open" if item["state"] == "open" else "Closed"


class GitHubConnector(BaseConnector):
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repos = [r.strip() for r in GITHUB_REPOS.split(",") if r.strip()]
        self.session = None

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
        # Validate token
        resp = self.session.get("https://api.github.com/user")
        resp.raise_for_status()
        return resp.json()["login"]

    def list_documents(self) -> list[dict]:
        return []  # GitHub items go to project_links, not documents

    def fetch_content(self, doc_id: str) -> str:
        return ""

    def sync(self) -> int:
        if not self.session:
            self.authenticate()

        count = 0
        for repo in self.repos:
            project_name = GITHUB_REPO_PROJECT_MAP.get(repo)
            project = get_project_by_name(project_name) if project_name else None
            if not project:
                print(f"  Skipping {repo}: no project mapping (set GITHUB_REPO_PROJECT_MAP)")
                continue

            count += self._sync_repo(repo, project["id"])
        return count

    def _sync_repo(self, repo: str, project_id: int) -> int:
        count = 0

        # Fetch PRs
        for item in self._paginate(f"https://api.github.com/repos/{repo}/pulls", {"state": "all"}):
            upsert_project_link(
                project_id=project_id,
                url=item["html_url"],
                source_type="github-pr",
                source_id=f"{repo}#{item['number']}",
                title=item["title"],
                status=_gh_status(item, is_pr=True),
                assignee=(item.get("assignee") or {}).get("login"),
                created_at=item["created_at"],
            )
            count += 1

        # Fetch issues (excluding PRs — GitHub API returns PRs as issues too)
        for item in self._paginate(f"https://api.github.com/repos/{repo}/issues", {"state": "all"}):
            if item.get("pull_request"):
                continue  # skip PRs already fetched above
            upsert_project_link(
                project_id=project_id,
                url=item["html_url"],
                source_type="github-issue",
                source_id=f"{repo}#{item['number']}",
                title=item["title"],
                status=_gh_status(item, is_pr=False),
                assignee=(item.get("assignee") or {}).get("login"),
                created_at=item["created_at"],
            )
            count += 1

        return count

    def _paginate(self, url: str, params: dict) -> list[dict]:
        """Paginate through GitHub API results."""
        params = {**params, "per_page": 100, "page": 1}
        all_items = []
        while True:
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            items = resp.json()
            if not items:
                break
            all_items.extend(items)
            params["page"] += 1
        return all_items
