/**
 * Related document lookup using graph.json from GitHub Pages.
 * Ported cluster mapping from lifegraph/clusters.py
 */

var GRAPH_URL = 'https://capmann.github.io/LifeGraph/graph.json';
var CACHE_TTL = 21600; // 6 hours in seconds

/**
 * Cluster mapping: topic name patterns -> cluster name.
 * Ported from clusters.py CLUSTERS dict.
 */
var CLUSTERS = {
  'Monitoring Posture & Coverage': [
    'Monitoring Posture', 'Monitoring Coverage', 'Monitor Posture',
    'Measuring Monitoring Posture', 'Monitoring Posture Alignment',
    'Monitoring Posture Assessment', 'Monitoring Posture Overview',
    'Coverage Metrics', 'Coverage Gap Detection', 'Monitor Coverage',
    'Baseline Coverage', 'Monitor Quality', 'Monitoring Best Practices',
    'Service Coverage Scoring', 'Posture Initiatives', 'Posture Tools',
  ],
  'Datadog-Managed Monitors': [
    'Datadog-Managed Monitors', 'Bits Monitors', 'Automatic Monitors',
    'Automatic Monitor Creation', 'Automatic Detection',
    'Monitor Lifecycle Management', 'Monitor Inheritance',
    'Monitor Packs', 'Monitor Starter Packs', 'Deterministic Monitor',
    'Managed Monitor API', 'Bulk Delete Monitors',
  ],
  'Monitor Generation & LLM': [
    'LLM Monitor Generation', 'Monitor Generation', 'LLM-Generated Monitors',
    'LLM Monitor Features', 'Monitor Message Generation',
    'LLM Evaluation Framework', 'LLM Quality Assurance',
    'AI-Powered Monitor Creation', 'Natural Language Monitor',
    'Dashboard To Monitor Conversion', 'Dashboard-to-Monitor',
    'CMD+I Monitor Creation', 'Hallucination Detection',
  ],
  'MCP & AI Tooling': [
    'MCP Tooling', 'MCP Tools', 'MCP Server', 'MCP Posture',
    'Datadog Remote MCP', 'Alerting Context for LLMs',
    'Agentic Workflows', 'AI-Powered Monitor Configuration',
    'AI In Monitoring', 'Autonomous Monitoring', 'AI-Native Monitoring',
    'AI-Assisted Detection', 'AI Detection', 'AI Initiatives', 'AI Vision',
    'Context-Aware Detection',
  ],
  'Alert Quality & Noise': [
    'Alert Fatigue', 'Alert Noise', 'Monitor Noise',
    'Alert Quality Analyzer', 'Alert Importance',
    'Monitor Relevance Scoring', 'Monitor Importance',
    'Monitor Sorting', 'Monitor Frecency', 'Contextual Alerting',
    'Signal Generation',
  ],
  'RED Metrics & Baseline Signals': [
    'RED Metrics', 'Host CPU', 'Host Monitoring', 'Kubernetes Monitoring',
    'Kubernetes Pod', 'APM Service Error', 'Error Rate Monitoring',
    'Traffic Anomaly', 'Service Tier', 'Service Health',
  ],
  'Threshold & Configuration': [
    'Threshold Recommendations', 'Monitor Configuration',
    'Monitor Creation Flow', 'Monitor Creation UX',
    'Monitor Threshold', 'Dynamic Thresholds', 'Anomaly Detection',
    'Notification Handles', 'Monitor Validation',
  ],
  'Posture.md & Living Runbook': [
    'Posture.md', 'Posture Agent', 'Living Runbook',
    'Monitoring Standards', 'Monitor Drift', 'Enterprise Monitoring Standards',
    'Proactive Coverage', 'Posture API',
  ],
  'Monitor Templates': [
    'Monitor Templates', 'Monitor Template Authoring',
    'Monitor Metadata Standards', 'User-Defined Templates',
  ],
  'Terraform & Governance': [
    'Terraform Monitor', 'Terraform Integration', 'Terraform-Based Monitoring',
    'Restriction Policies', 'GRACE Permissions', 'Monitor Access Control',
    'Monitor Governance', 'Monitor Trust', 'Monitor Creation Security',
    'Monitor Automation Control', 'Monitor Configuration Ownership',
  ],
  'Customer Research & Design Partners': [
    'Customer Research', 'Customer Interviews', 'Customer Coverage',
    'Customer Monitoring', 'Customer Outreach', 'Customer Segmentation',
    'Customer Engagement', 'Design Partner', 'Enterprise Monitor Management',
  ],
  'Customer Onboarding & Rollout': [
    'Customer Onboarding', 'Trial Org Onboarding', 'Customer Rollout',
    'Product Rollout', 'Feature Announcement', 'Feature Validation',
    'Onboarding Experience', 'Monitor Onboarding', 'Zero-Setup Monitoring',
    'Time-To-Value', 'Stack Detection',
  ],
  'Alerting Platform & Roadmap': [
    'Alerting Platform', 'Alerting Automation', 'SLO Automation',
    'Monitor Generation Roadmap', 'AI Squad',
  ],
  'Ops Manager & Cross-Team': [
    'Ops Manager', 'Cross-Team', 'Applied AI Collaboration',
    'Triage Agent', 'Critical Resource', 'Incident Prediction',
    'Monitorless Detection',
  ],
  'OKRs, Planning & Strategy': [
    'OKR Planning', 'OKR Updates', 'Q2 Planning', 'Q3-Q4 Planning',
    'Q4 OKR', 'Detection OKRs', 'Prioritization Decisions',
  ],
  'DASH Conference': [
    'DASH Conference', 'DASH Demo', 'DASH Theater',
    'Datadog Paris Summit', 'Conference Talk',
  ],
  'UX & Side Panel Design': [
    'Side Panel Design', 'UX Design', 'Signal-First UX',
    'Health Component', 'Monitor And Dashboard Packs',
    'Dashboards And Graphing', 'Software Catalog',
    'IDP and Software Catalog', 'Demo Strategy', 'Executive Dashboard',
  ],
  'AI Code Review System': [
    'AI Code Review', 'AI-Native Code Review', 'Human-in-the-Loop',
    'Code Review Prioritization', 'Code Review Scalability',
    'IDE-Integrated Review', 'IDE Agent',
  ],
  'Synthetics & Feature Monitoring': [
    'Synthetics Integration', 'Feature Coverage Monitoring',
    'OOTB Monitor', 'Synthetic Monitoring', 'Integration Monitors',
    'Infrastructure Monitoring Defaults',
  ],
  'CI/CD & Deployment Monitoring': [
    'CI/CD Monitoring', 'Automatic Rollbacks', 'Deployment Visibility',
  ],
  'Monitor Search & Metrics': [
    'Monitor Search', 'Monitor Recommendations', 'Metrics Recommendations',
    'Monitor Datasets', 'Related Metrics', 'Search Experience',
    'Monitor Query Configuration',
  ],
  'Agent Observability': [
    'Agent Observability', 'A2A Observability', 'LLM Agent Management',
    'Multi-Agent Monitoring', 'Monitor Layers Architecture',
    'Three-Layer Monitor', 'Monitor UX Design Challenges',
  ],
  '1:1 & Team Meetings': [
    '1:1 Meeting', 'Team Retrospective', 'Team Collaboration',
    'Team Leadership', 'Project Management', 'Weekly Team Sync',
    'Brainstorm Notes', 'Kickoff Meeting', 'PM Career',
    'Career Growth', 'Promotion and Career', 'Brag Document',
    'Features Shipped', 'Blog Content', 'Sales Enablement',
  ],
  'Workshops & SRE Engagement': [
    'SRE Workshop', 'Jobs-To-Be-Done', 'Workshop Notes',
    'Continuous Improvement',
  ],
  'AI Teaching & Education': [
    'AI Course Teaching', 'AI Architecture', 'RAG Architecture',
    'RAG And Fine-Tuning', 'LLM Fine-Tuning', 'AI Implementation',
    'Enterprise AI', 'AI Business', 'AI Project Lifecycle',
    'Product Management Education', 'Design Thinking',
    'ESSEC Teaching', 'Responsible AI', 'Data-Driven Strategy',
    'AI Observability',
  ],
  'Machine Learning Education': [
    'Clustering Algorithms', 'K-Means', 'DBSCAN',
    'Machine Learning Education',
  ],
  'Hackathons': [
    'Hackathon', 'GCPU Hackathon', 'Misinformation Detection',
    'Critical Thinking AI', 'NLP Fallacy', 'Cross-Source Knowledge',
    'AI Decision Context', 'Policy as Code',
  ],
  'Astrology & Charts': [
    'Astrology', 'Personality Analysis', 'Planetary House',
    'Venus In Virgo', 'Moon In Libra', 'Gemini Intellectual',
    'North Node', 'Self-Identity', 'Emotional Intelligence',
    'Spiritual Growth', 'Shadow Work', 'Venus and Relationship',
    'Career and Saturn',
  ],
  'Personal & Life': [
    'Christmas Gift', 'Personal Life', 'Personal Letter',
    'Grief And Loss', 'Family', 'Winter Activity',
    'Paris Lifestyle', 'Housing Certificate', 'Administrative Document',
    'WordPress', 'Mont Kailash', 'Web Performance',
  ],
  'Career Exploration': [
    'Job Interview', 'Mistral AI', 'Career Exploration',
  ],
};

/**
 * Category assignment. Ported from clusters.py _get_category().
 */
var CATEGORY_KEYWORDS = {
  posture: ['Monitoring Posture', 'Posture.md', 'RED Metrics', 'Alert Quality'],
  automation: ['Datadog-Managed', 'Monitor Generation', 'Threshold', 'MCP', 'Monitor Templates'],
  strategy: ['OKR', 'DASH', 'Alerting Platform', 'Ops Manager', 'Customer Research', 'Customer Onboarding', 'Terraform'],
  ux: ['UX', 'Side Panel', 'Synthetics', 'Monitor Search', 'Agent Observability'],
  team: ['1:1', 'Workshop', 'CI/CD'],
  teaching: ['Teaching', 'Education', 'Machine Learning', 'Hackathon'],
  personal: ['Astrology', 'Personal', 'Career Exploration'],
  code: ['Code Review'],
};

function getCategory(clusterName) {
  var lower = clusterName.toLowerCase();
  for (var cat in CATEGORY_KEYWORDS) {
    var keywords = CATEGORY_KEYWORDS[cat];
    for (var i = 0; i < keywords.length; i++) {
      if (lower.indexOf(keywords[i].toLowerCase()) !== -1) {
        return cat;
      }
    }
  }
  return 'other';
}

/**
 * Map an extracted topic name to a cluster name using substring matching.
 */
function topicToCluster(topicName) {
  var lower = topicName.toLowerCase();
  for (var cluster in CLUSTERS) {
    var patterns = CLUSTERS[cluster];
    for (var i = 0; i < patterns.length; i++) {
      if (lower.indexOf(patterns[i].toLowerCase()) !== -1 ||
          patterns[i].toLowerCase().indexOf(lower) !== -1) {
        return cluster;
      }
    }
  }
  return null;
}

/**
 * Fetch and cache graph.json from GitHub Pages.
 */
function fetchGraphData() {
  var cache = CacheService.getUserCache();
  var cached = cache.get('graph_json');

  if (cached) {
    return JSON.parse(cached);
  }

  var response = UrlFetchApp.fetch(GRAPH_URL, { muteHttpExceptions: true });
  if (response.getResponseCode() !== 200) {
    return null;
  }

  var text = response.getContentText();

  // CacheService has 100KB limit per value. Chunk if needed.
  if (text.length < 100000) {
    cache.put('graph_json', text, CACHE_TTL);
  }

  return JSON.parse(text);
}

/**
 * Find related documents given extracted topics.
 * Returns array of {title, url, source, created_at, sharedTopics, category}
 */
function findRelatedDocs(extractedTopics) {
  var graph = fetchGraphData();
  if (!graph) return [];

  // Map extracted topics to cluster names
  var matchedClusters = {};
  for (var i = 0; i < extractedTopics.length; i++) {
    var topicName = extractedTopics[i].topic;
    var cluster = topicToCluster(topicName);
    if (cluster) {
      matchedClusters[cluster] = true;
    }
  }

  // Also try direct name matching against graph nodes
  for (var i = 0; i < extractedTopics.length; i++) {
    var topicLower = extractedTopics[i].topic.toLowerCase();
    for (var j = 0; j < graph.nodes.length; j++) {
      var nodeLower = graph.nodes[j].name.toLowerCase();
      if (topicLower.indexOf(nodeLower) !== -1 || nodeLower.indexOf(topicLower) !== -1) {
        matchedClusters[graph.nodes[j].name] = true;
      }
    }
  }

  // Find matching node IDs and collect doc IDs
  var matchedNodeIds = {};
  var docIds = {};
  for (var j = 0; j < graph.nodes.length; j++) {
    var node = graph.nodes[j];
    if (matchedClusters[node.name]) {
      matchedNodeIds[node.id] = node;
      var ids = node.doc_ids || [];
      for (var k = 0; k < ids.length; k++) {
        if (!docIds[ids[k]]) docIds[ids[k]] = [];
        docIds[ids[k]].push(node.name);
      }
    }
  }

  // Also include docs from connected nodes (one hop)
  for (var e = 0; e < graph.edges.length; e++) {
    var edge = graph.edges[e];
    var sourceMatched = !!matchedNodeIds[edge.source];
    var targetMatched = !!matchedNodeIds[edge.target];
    if (sourceMatched || targetMatched) {
      var connectedNode = sourceMatched
        ? graph.nodes.find(function(n) { return n.id === edge.target; })
        : graph.nodes.find(function(n) { return n.id === edge.source; });
      if (connectedNode && edge.weight >= 3) {
        var ids = connectedNode.doc_ids || [];
        for (var k = 0; k < ids.length; k++) {
          if (!docIds[ids[k]]) docIds[ids[k]] = [];
          if (docIds[ids[k]].indexOf(connectedNode.name) === -1) {
            docIds[ids[k]].push(connectedNode.name);
          }
        }
      }
    }
  }

  // Build doc map
  var docMap = {};
  for (var d = 0; d < graph.documents.length; d++) {
    docMap[graph.documents[d].id] = graph.documents[d];
  }

  // Build results
  var results = [];
  for (var docId in docIds) {
    var doc = docMap[docId];
    if (!doc) continue;
    results.push({
      title: doc.title,
      url: doc.source_url || '',
      source: doc.source || '',
      created_at: doc.created_at || '',
      sharedTopics: docIds[docId],
    });
  }

  // Sort by number of shared topics (most relevant first)
  results.sort(function(a, b) { return b.sharedTopics.length - a.sharedTopics.length; });

  return results.slice(0, 30);
}
