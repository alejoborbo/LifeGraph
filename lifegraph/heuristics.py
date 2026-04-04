"""Auto-compute project phase (Planning / Building / Shipped) from artifact types."""

from lifegraph.db import get_all_projects, get_project_documents, get_project_links


def compute_project_phase(project_id: int) -> str:
    """Return 'Planning', 'Building', or 'Shipped' based on artifact signals."""
    docs = get_project_documents(project_id)
    links = get_project_links(project_id)

    planning = 0
    building = 0
    shipped = 0

    for doc in docs:
        role = doc.get("role", "reference")
        if role in ("spec", "rfc", "design-doc", "meeting-notes", "reference"):
            planning += 1
        if role in ("implementation", "pr-description"):
            building += 1
        if role in ("launch", "announcement", "runbook", "post-mortem"):
            shipped += 1

    for link in links:
        st = link.get("source_type", "")
        status = (link.get("status") or "").lower()
        if "github-pr" in st and status == "merged":
            shipped += 2  # strong shipped signal
        elif "github-pr" in st and status == "open":
            building += 1
        elif "github-issue" in st and status == "open":
            building += 1
        elif status in ("done", "closed", "merged"):
            shipped += 1
        elif status in ("in progress", "in review"):
            building += 1
        else:
            planning += 1

    if shipped >= 2:
        return "Shipped"
    if building >= 1:
        return "Building"
    return "Planning"


def compute_all_phases() -> dict[int, str]:
    """Return {project_id: phase} for all projects."""
    projects = get_all_projects()
    return {p["id"]: compute_project_phase(p["id"]) for p in projects}
