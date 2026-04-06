"""Topic clustering - merge granular topics into meaningful groups."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lifegraph.config import DATABASE_PATH

# Hand-crafted taxonomy: cluster_name -> list of topic name patterns to merge
CLUSTERS = {
    # === WORK: Monitoring Posture & Coverage ===
    "Monitoring Posture & Coverage": [
        "Monitoring Posture", "Monitoring Coverage", "Monitor Posture",
        "Monitoring Posture & Coverage",
        "Measuring Monitoring Posture", "Monitoring Posture Alignment",
        "Monitoring Posture Assessment", "Monitoring Posture Overview",
        "Monitoring Posture Blog Post", "Monitoring Posture Roadmap",
        "Monitoring Posture For SREs", "Monitoring Posture KPIs",
        "Monitoring Posture Talk", "Monitoring Posture Skill",
        "Monitoring Posture Management", "Monitor Posture Management",
        "Monitoring Posture Auto-Report", "Monitor Posture API",
        "Monitor Posture Skill", "Monitor Posture Team",
        "Monitor Posture Team Sync", "Posture Initiatives",
        "Posture Tools", "Posture x AI Alignment",
        "Coverage Metrics", "Coverage Gap Detection",
        "Monitor Coverage Assessment", "Monitor Coverage Model",
        "Monitoring Coverage Model", "Monitoring Coverage Automation",
        "Monitoring Coverage Definition", "Monitoring Coverage Gaps",
        "Coverage Computation", "Coverage For SREs",
        "Service Coverage Scoring", "Baseline Coverage",
        "Baseline Monitor Coverage", "Monitor Quality",
        "Monitor Quality Assessment", "Monitor Quality Validation",
        "Monitoring Best Practices Consulting",
        "Monitor Best Practices", "Monitor Quality",
        "Monitor Posture Team", "Intelligent Monitoring",
    ],

    "Datadog-Managed Monitors": [
        "Datadog-Managed Monitors", "Bits Monitors",
        "Automatic Monitors", "Automatic Monitor Creation",
        "Automatic Detection", "Automatic Detection Sync",
        "Monitor Lifecycle Management", "Monitor Inheritance",
        "Monitor Update Propagation", "Monitor Deletion And Lifecycle",
        "AMC Monitor Expiration", "Monitor Cleanup",
        "Deterministic Monitor Creation", "Deterministic Monitor Packs",
        "Monitor Packs", "Monitor Starter Packs",
        "Automatic Notifications", "Auto-Notifications",
        "Automatic Monitors Customer Feedback", "Managed Monitor API",
        "Bulk Delete Monitors",
    ],

    "Posture.md & Living Runbook": [
        "Posture.md", "Posture.md Configuration", "Posture Agent",
        "Living Runbook", "Living Runbook Concept",
        "Monitoring Standards Enforcement", "Monitor Drift Detection",
        "Enterprise Monitoring Standards", "Enterprise Monitoring Governance",
        "Proactive Coverage", "Posture API",
    ],

    "Monitor Generation & LLM": [
        "LLM Monitor Generation", "Monitor Generation",
        "Monitor Generation AI", "Monitor Generation Roadmap",
        "Monitor Generation Preview", "LLM-Generated Monitors",
        "LLM Monitor Features", "Monitor Message Generation",
        "Auto-Generated Monitor Messages", "Monitor Message Validation",
        "LLM Evaluation Framework", "LLM Quality Assurance",
        "LLM-as-a-Judge for Monitor Quality", "Hallucination Detection",
        "AI-Powered Monitor Creation", "Natural Language Monitor Creation",
        "Natural Language Monitor Interaction",
        "Dashboard To Monitor Conversion", "Dashboard-to-Monitor Conversion",
        "Dashboard Widget Monitors", "CMD+I Monitor Creation",
        "LLM-Powered Monitor Generation", "LLM Output Evaluation",
        "Monitor Generation Validation", "LLM As A Judge",
        "Syntactic And Semantic Validation", "Dashboard To Monitor",
    ],

    "Threshold & Configuration": [
        "Threshold Recommendations", "Monitor Configuration",
        "Monitor Configuration UX", "Monitor Creation Flow",
        "Monitor Creation UX", "Proactive Monitor Suggestions",
        "Monitor Threshold Suggestions", "Monitor Threshold Tuning",
        "Data-Driven Monitor Configuration", "Dynamic Thresholds",
        "Anomaly Detection", "Statistical Confidence for Thresholds",
        "Dynamic Evaluation Windows", "Notification Handles",
        "Monitor Validation",
    ],

    "MCP & AI Tooling": [
        "MCP Tooling", "MCP Tools for Monitoring", "MCP Server for Alerting",
        "MCP Posture Tools", "MCP Tools and AI Agents",
        "Datadog Remote MCP Server", "Alerting Context for LLMs",
        "Alerting API Design", "Agentic Workflows",
        "AI-Powered Monitor Configuration", "AI In Monitoring Posture",
        "Autonomous Monitoring", "AI-Native Monitoring Workflows",
        "AI-Assisted Detection", "AI Detection Initiatives",
        "AI Detection Pipeline", "Context-Aware Detection",
        "AI Initiatives Updates", "AI Vision",
        "MCP Server For Alerting", "Model Context Protocol",
        "Datadog MCP Server", "Claude Code Integration",
        "AI-Powered Alerting", "AI-Native Observability",
        "AI-Assisted Monitor Setup",
    ],

    "Monitor Templates": [
        "Monitor Templates", "Monitor Template Authoring",
        "Monitor Metadata Standards", "User-Defined Templates",
        "Monitor Templates for Services",
    ],

    "Alert Quality & Noise": [
        "Alert Fatigue Reduction", "Alert Noise Reduction",
        "Monitor Noise Reduction", "Anomaly Monitor Noise",
        "Alert Quality Analyzer", "Alert Importance Classification",
        "Monitor Relevance Scoring", "Monitor Importance Ranking",
        "Monitor Sorting", "Monitor Frecency Sorting",
        "Monitor Training Datasets", "Contextual Alerting",
        "Signal Generation",
    ],

    "RED Metrics & Baseline Signals": [
        "RED Metrics Monitoring", "Host CPU and Memory Monitoring",
        "Host Monitoring", "Kubernetes Monitoring",
        "Kubernetes Pod Monitoring", "APM Service Error Monitoring",
        "Error Rate Monitoring", "Traffic Anomaly Detection",
        "Service Tier Prioritization", "Service Health Assessment",
        "Service Health View", "APM Service Monitoring",
        "Kubernetes Configuration",
    ],

    "Terraform & Governance": [
        "Terraform Monitor Management", "Terraform Integration",
        "Terraform-Based Monitoring", "Restriction Policies",
        "GRACE Permissions", "GRACE (Granular Access Control)", "Monitor Access Control",
        "Monitor Permissions & RBAC", "Infrastructure As Code",
        "Monitor Governance", "Monitor Trust And Control", "Monitor Creation Security",
        "Monitor Trust and Transparency", "Monitor Automation Control",
        "Monitor Configuration Ownership",
    ],

    "Customer Research & Design Partners": [
        "Customer Research", "Customer Interviews",
        "Customer Research on Monitoring", "Customer Coverage Analysis",
        "Customer Monitoring Recommendations", "Customer Monitoring Auto-Report",
        "Customer Outreach", "Customer Segmentation",
        "Customer Engagement", "Design Partner Feedback",
        "Toyota Design Partner", "Kingfisher Customer Meeting",
        "Liberty Mutual Deep Dive", "APM Migration",
        "Enterprise Monitor Management", "Enterprise Monitoring at Scale",
    ],

    "Customer Onboarding & Rollout": [
        "Customer Onboarding", "Customer Onboarding for Monitoring",
        "Trial Org Onboarding", "Customer Rollout Strategy",
        "Product Rollout Strategy", "Feature Announcement",
        "Feature Validation", "Onboarding Experience",
        "Monitor Onboarding Flow", "Zero-Setup Monitoring Onboarding",
        "Time-To-Value Optimization", "Stack Detection",
        "Monitor Onboarding", "Trial Conversion",
    ],

    "Alerting Platform & Roadmap": [
        "Alerting Platform Strategy", "Alerting Platform Roadmap",
        "Alerting Platform AI Roadmap", "Alerting Automation",
        "SLO Automation", "Monitor Generation Roadmap",
        "AI Squad Updates",
        "Datadog AI Product Roadmap",
    ],

    "Ops Manager & Cross-Team": [
        "Ops Manager Collaboration", "Ops Manager Recommendations",
        "Ops Manager and Alerting Collaboration",
        "Cross-Team Alignment", "Cross-Team Q2 Collaboration",
        "Applied AI Collaboration", "Triage Agent",
        "Critical Resource Identification",
        "Incident Prediction and Forecasting", "Monitorless Detection",
    ],

    "OKRs, Planning & Strategy": [
        "OKR Planning", "OKR Planning Q2 2026", "OKR Updates",
        "Q2 Planning", "Q3-Q4 Planning", "Q4 OKR Planning",
        "Detection OKRs", "Prioritization Decisions",
    ],

    "DASH Conference": [
        "DASH Conference", "DASH Demo Planning", "DASH Theater Talk",
        "Datadog Paris Summit", "Conference Talk Planning",
    ],

    "UX & Side Panel Design": [
        "Side Panel Design", "UX Design", "Signal-First UX",
        "Health Component Design", "Monitor And Dashboard Packs",
        "Dashboards And Graphing", "Software Catalog Integration",
        "IDP and Software Catalog", "Service Catalog Integration", "Demo Strategy",
        "Monitor UX", "Monitor Message Editor", "VQA Testing",
        "Monitoring Posture Overview", "Executive Dashboards",
        "Executive Dashboard Monitors",
    ],

    # === WORK: Non-monitoring ===
    "AI Code Review System": [
        "AI Code Review", "AI-Native Code Review",
        "Human-in-the-Loop AI", "Human-in-the-Loop for AI Code",
        "Code Review Prioritization", "Code Review Scalability",
        "IDE-Integrated Review", "IDE-Integrated Review Workflow",
        "Feedback Loop Tracking", "AI-Generated Code Oversight",
        "IDE Agent Integration",
    ],

    "Synthetics & Feature Monitoring": [
        "Synthetics Integration", "Feature Coverage Monitoring",
        "OOTB Monitor Recommendations", "Synthetic Monitoring Coverage",
        "Integration Monitors OOTB", "Infrastructure Monitoring Defaults",
    ],

    "Sensitive Data Scanner": [
        "Sensitive Data Scanner", "PII Detection Rules",
        "AI/ML-Powered Detection", "Regex Pattern Matching",
        "Data Security & Privacy",
        "Compliance (GDPR, HIPAA, PCI-DSS)",
    ],

    "Datadog AI Products": [
        "Bits AI SRE", "Watchdog Anomaly Detection",
        "Natural Language Querying", "Event Management AIOps",
        "Incident AI", "Open Source GenAI",
        "LLM Evaluation", "AI Agent Evaluation",
    ],

    "OpenTelemetry": [
        "OpenTelemetry Integration", "DDOT Collector",
        "OTel Semantic Conventions", "APM Trace Intake",
        "Metric Equivalence",
    ],

    "Event Platform & Streaming": [
        "Event Store (Husky)", "Kafka Streaming Platform",
        "Full-Text Search", "Log Management",
        "CIDR Network Querying", "Reference Tables",
    ],

    "APM & Tracing": [
        "Telemetry Payload Validation", "JSON Schema Validation",
        "APM Tracer Quality", "Cross-Language Tracer Testing",
        "System Tests", "RUM Auto-Injection",
        "APM Service Discovery", "Libdatadog",
    ],

    "Engineering Culture": [
        "Engineering Onboarding", "SSH Key Management",
        "GitHub Configuration", "Developer Environment Setup",
        "Engineering Promotion", "Cross-Team Technical Leadership",
        "Developer Tooling", "Conference Talks",
    ],

    "CI/CD & Deployment Monitoring": [
        "CI/CD Monitoring", "Automatic Rollbacks", "Deployment Visibility",
        "CI/CD Improvements", "Alerting Platform Infrastructure",
    ],

    "Monitor Search & Metrics": [
        "Monitor Search And Retrieval", "Monitor Recommendations",
        "Metrics Recommendations", "Monitor Datasets", "Related Metrics",
        "Search Experience", "Monitor Query Configuration",
    ],

    "Agent Observability": [
        "Agent Observability", "A2A Observability", "LLM Agent Management",
        "Multi-Agent Monitoring Architecture",
        "Monitor Layers Architecture", "Three-Layer Monitor Model",
        "Monitor UX Design Challenges",
    ],

    # === WORK: Meetings & Team ===
    "1:1 & Team Meetings": [
        "1:1 Meeting Notes", "Team Retrospective", "Team Collaboration",
        "Team Leadership", "Project Management", "Weekly Team Sync",
        "NYC Team Meetup", "Brainstorm Notes", "Kickoff Meeting",
        "PM Career Development", "PM Career Growth", "Product Management",
        "Career Development",
        "Career Growth to Senior PM", "Promotion and Career Growth",
        "Team Organization", "Brag Document", "Features Shipped",
        "Blog Content on Monitoring", "Sales Enablement for Monitoring",
        "Cost Risk Management",
    ],

    "Workshops & SRE Engagement": [
        "SRE Workshop", "Jobs-To-Be-Done Framework",
        "Workshop Notes", "Continuous Improvement Feedback Loops",
    ],

    # === TEACHING ===
    "AI Teaching & Education": [
        "AI Course Teaching", "AI Architecture Teaching",
        "AI Architecture Fundamentals", "RAG Architecture",
        "RAG And Fine-Tuning", "LLM Fine-Tuning",
        "AI Implementation Risks", "Enterprise AI Implementation",
        "Enterprise AI Strategy", "AI Business Strategy",
        "AI Project Lifecycle", "Product Management Education",
        "Design Thinking", "AI Business Presentation",
        "ESSEC Teaching", "Responsible AI Implementation",
        "Data-Driven Strategy", "AI Observability",
    ],

    "Machine Learning Education": [
        "Clustering Algorithms", "K-Means And DBSCAN",
        "Machine Learning Education",
    ],

    "Hackathons": [
        "Hackathon Ideas", "Hackathon Project", "Hackathon Project Ideas", "Hackathon Projects",
        "GCPU Hackathon", "Misinformation Detection",
        "Critical Thinking AI", "NLP Fallacy Detection",
        "Cross-Source Knowledge Synthesis", "AI Decision Context Builder",
        "Policy as Code for Alerting",
    ],

    # === PERSONAL ===
    "Astrology & Charts": [
        "Astrology Charts", "Astrology Chart Interpretation",
        "Personality Analysis", "Planetary House Placements",
        "Venus In Virgo Analysis", "Moon In Libra Analysis",
        "Gemini Intellectual Traits", "North Node Sagittarius",
        "North Node Sagittarius Analysis", "North Node Aquarius Analysis",
        "Self-Identity and Authenticity", "Emotional Intelligence",
        "Spiritual Growth", "Spiritual Transformation and Growth",
        "Shadow Work and Psychology", "Venus and Relationship Astrology",
        "Career and Saturn Astrology",
    ],

    "Personal & Life": [
        "Christmas Gift Ideas", "Personal Life", "Personal Letter",
        "Grief And Loss", "Family", "Winter Activity Ideas",
        "Paris Lifestyle", "Housing Certificate", "Administrative Document",
        "WordPress Site Maintenance", "Mont Kailash Website",
        "Web Performance Optimization",
    ],

    "Career Exploration": [
        "Job Interview Prep", "Mistral AI", "Career Exploration",
    ],
}


def build_clustered_graph(min_edge_weight: int = 2) -> dict:
    """Build a graph with clustered topics."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row

    # Get all topics and their docs
    topics = conn.execute("""
        SELECT t.id, t.name, dt.doc_id, dt.relevance
        FROM topics t
        JOIN doc_topics dt ON t.id = dt.topic_id
    """).fetchall()

    # Load auto-generated clusters if available, fallback to hand-crafted
    active_clusters = CLUSTERS
    auto_categories = {}
    auto_path = Path(DATABASE_PATH).parent / "auto_clusters.json"
    if auto_path.exists():
        try:
            import json
            auto_data = json.loads(auto_path.read_text())
            active_clusters = {}
            for name, info in auto_data.items():
                if isinstance(info, dict):
                    active_clusters[name] = info["topics"]
                    auto_categories[name] = info.get("category", "other")
                else:
                    active_clusters[name] = info
            print(f"  Using auto-generated clusters ({len(active_clusters)} clusters)")
        except Exception as e:
            print(f"  Warning: failed to load auto_clusters.json: {e}, using hand-crafted")

    # Build topic_name -> cluster mapping
    topic_to_cluster = {}
    for cluster, patterns in active_clusters.items():
        for pat in patterns:
            topic_to_cluster[pat] = cluster

    # Map each topic to a cluster, collecting doc_ids
    from collections import defaultdict
    cluster_docs = defaultdict(lambda: defaultdict(float))  # cluster -> doc_id -> max_relevance

    unclustered = set()
    for t in topics:
        cluster = topic_to_cluster.get(t["name"])
        if cluster:
            cluster_docs[cluster][t["doc_id"]] = max(
                cluster_docs[cluster][t["doc_id"]], t["relevance"]
            )
        else:
            unclustered.add(t["name"])

    if unclustered:
        print(f"  Warning: {len(unclustered)} unclustered topics: {sorted(unclustered)[:10]}...")

    # Build nodes
    nodes = []
    cluster_id_map = {}
    # Build doc date lookup for trends
    doc_dates = {}
    date_rows = conn.execute("SELECT id, created_at FROM documents WHERE created_at IS NOT NULL").fetchall()
    for r in date_rows:
        doc_dates[r["id"]] = r["created_at"][:7] if r["created_at"] else None  # "2026-03"

    for i, (cluster, docs) in enumerate(sorted(cluster_docs.items(), key=lambda x: -len(x[1]))):
        cid = i + 1
        cluster_id_map[cluster] = cid

        # Compute monthly trend
        from collections import Counter as Ctr
        month_counts = Ctr()
        for did in docs:
            m = doc_dates.get(did)
            if m:
                month_counts[m] += 1
        # Build sorted monthly array (last 12 months)
        if month_counts:
            all_months = sorted(month_counts.keys())
            trend = [{"month": m, "count": month_counts[m]} for m in all_months[-12:]]
        else:
            trend = []

        nodes.append({
            "id": cid,
            "name": cluster,
            "doc_count": len(docs),
            "doc_ids": sorted(docs.keys()),
            "category": auto_categories.get(cluster) or _get_category(cluster),
            "trend": trend,
        })

    # Build edges (co-occurrence)
    from collections import Counter
    edge_counter = Counter()
    edge_doc_sets = defaultdict(set)

    # doc -> set of cluster_ids
    doc_clusters = defaultdict(set)
    for node in nodes:
        for did in node["doc_ids"]:
            doc_clusters[did].add(node["id"])

    for did, cids in doc_clusters.items():
        cid_list = sorted(cids)
        for i, c1 in enumerate(cid_list):
            for c2 in cid_list[i + 1:]:
                edge_counter[(c1, c2)] += 1
                edge_doc_sets[(c1, c2)].add(did)

    edges = []
    for (c1, c2), weight in edge_counter.items():
        if weight >= min_edge_weight:
            edges.append({
                "source": c1,
                "target": c2,
                "weight": weight,
                "doc_ids": sorted(edge_doc_sets[(c1, c2)]),
            })

    # Documents
    all_doc_ids = set()
    for node in nodes:
        all_doc_ids.update(node["doc_ids"])

    documents = []
    if all_doc_ids:
        rows = conn.execute("""
            SELECT id, title, source, source_url, created_at, raw_text, author
            FROM documents WHERE id IN ({})
        """.format(",".join("?" * len(all_doc_ids))), list(all_doc_ids)).fetchall()
        documents = []
        for r in rows:
            d = dict(r)
            raw = d.pop("raw_text", "") or ""
            d["snippet"] = raw[:200].replace("\n", " ").strip()
            documents.append(d)

    # Projects
    project_rows = conn.execute("""
        SELECT p.*, COUNT(pd.doc_id) as doc_count,
               MIN(d.created_at) as first_activity,
               MAX(d.created_at) as last_activity
        FROM projects p
        LEFT JOIN project_documents pd ON p.id = pd.project_id
        LEFT JOIN documents d ON pd.doc_id = d.id
        GROUP BY p.id
        ORDER BY last_activity DESC NULLS LAST
    """).fetchall()

    projects = []
    for r in project_rows:
        p = dict(r)
        # Get doc_ids for this project
        pd_rows = conn.execute(
            "SELECT doc_id, role FROM project_documents WHERE project_id = ?",
            (p["id"],)
        ).fetchall()
        p["doc_ids"] = [row["doc_id"] for row in pd_rows]

        # Count artifact types
        roles = [row["role"] for row in pd_rows]
        from collections import Counter as C
        role_counts = dict(C(roles))
        p["artifacts"] = role_counts

        # Get linked external items (Jira tickets, etc.)
        link_rows = conn.execute(
            "SELECT source_type, source_id, title, status, priority, url FROM project_links WHERE project_id = ?",
            (p["id"],)
        ).fetchall()
        p["links"] = [dict(lr) for lr in link_rows]
        projects.append(p)

    conn.close()

    # Cached AI summaries
    from lifegraph.db import get_all_summaries
    summaries = get_all_summaries()

    return {
        "nodes": sorted(nodes, key=lambda x: -x["doc_count"]),
        "edges": edges,
        "documents": documents,
        "projects": projects,
        "summaries": summaries,
    }


def _get_category(cluster_name: str) -> str:
    """Assign a high-level category for coloring."""
    categories = {
        "posture": ["Monitoring Posture", "Posture.md", "RED Metrics", "Alert Quality"],
        "automation": ["Datadog-Managed", "Monitor Generation", "Threshold", "MCP", "Monitor Templates"],
        "strategy": ["OKR", "DASH", "Alerting Platform", "Ops Manager", "Customer Research", "Customer Onboarding", "Terraform"],
        "ux": ["UX", "Side Panel", "Synthetics", "Monitor Search", "Agent Observability", "Sensitive Data"],
        "team": ["1:1", "Workshop", "CI/CD", "Engineering Culture"],
        "teaching": ["Teaching", "Education", "Machine Learning", "Hackathon", "Datadog AI Products"],
        "personal": ["Astrology", "Personal", "Career Exploration"],
        "code": ["Code Review", "OpenTelemetry", "Event Platform", "APM"],
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw.lower() in cluster_name.lower():
                return cat
    return "other"
