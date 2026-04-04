/**
 * Look up the current document in graph.json and find its topics + related docs.
 * No Claude API needed -- everything comes from the pre-built graph.
 */

var GRAPH_URL = 'https://capmann.github.io/LifeGraph/graph.json';
var CACHE_TTL = 21600; // 6 hours

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

function getCategory(name) {
  var lower = name.toLowerCase();
  for (var cat in CATEGORY_KEYWORDS) {
    var keywords = CATEGORY_KEYWORDS[cat];
    for (var i = 0; i < keywords.length; i++) {
      if (lower.indexOf(keywords[i].toLowerCase()) !== -1) return cat;
    }
  }
  return 'other';
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

  // CacheService has 100KB limit per value
  if (text.length < 100000) {
    cache.put('graph_json', text, CACHE_TTL);
  }

  return JSON.parse(text);
}

/**
 * Find the current document in the graph by title matching.
 * Returns {topics: [{name, category, docCount}], relatedDocs: [{title, url, source, created_at, sharedTopics}]}
 */
function lookupDocument(docTitle) {
  var graph = fetchGraphData();
  if (!graph) return { topics: [], relatedDocs: [] };

  // Build doc map
  var docMap = {};
  for (var d = 0; d < graph.documents.length; d++) {
    docMap[graph.documents[d].id] = graph.documents[d];
  }

  // Find this doc in the graph by title (fuzzy: case-insensitive, trim whitespace)
  var titleLower = docTitle.toLowerCase().trim();
  var matchedDoc = null;
  for (var d = 0; d < graph.documents.length; d++) {
    if (graph.documents[d].title.toLowerCase().trim() === titleLower) {
      matchedDoc = graph.documents[d];
      break;
    }
  }

  if (!matchedDoc) {
    // Try partial match
    for (var d = 0; d < graph.documents.length; d++) {
      var graphTitle = graph.documents[d].title.toLowerCase().trim();
      if (graphTitle.indexOf(titleLower) !== -1 || titleLower.indexOf(graphTitle) !== -1) {
        matchedDoc = graph.documents[d];
        break;
      }
    }
  }

  if (!matchedDoc) {
    return { topics: [], relatedDocs: [] };
  }

  // Find which graph nodes (clusters) contain this doc
  var matchedNodes = [];
  for (var n = 0; n < graph.nodes.length; n++) {
    var node = graph.nodes[n];
    var docIds = node.doc_ids || [];
    if (docIds.indexOf(matchedDoc.id) !== -1) {
      matchedNodes.push(node);
    }
  }

  // Build topics list
  var topics = [];
  for (var i = 0; i < matchedNodes.length; i++) {
    topics.push({
      name: matchedNodes[i].name,
      category: getCategory(matchedNodes[i].name),
      docCount: matchedNodes[i].doc_count
    });
  }
  topics.sort(function(a, b) { return b.docCount - a.docCount; });

  // Collect related doc IDs from matched nodes + connected nodes
  var matchedNodeIds = {};
  for (var i = 0; i < matchedNodes.length; i++) {
    matchedNodeIds[matchedNodes[i].id] = true;
  }

  var relatedDocIds = {};
  // Docs from same topics
  for (var i = 0; i < matchedNodes.length; i++) {
    var ids = matchedNodes[i].doc_ids || [];
    for (var k = 0; k < ids.length; k++) {
      if (ids[k] !== matchedDoc.id) {
        if (!relatedDocIds[ids[k]]) relatedDocIds[ids[k]] = [];
        relatedDocIds[ids[k]].push(matchedNodes[i].name);
      }
    }
  }

  // Docs from connected topics (one hop, weight >= 3)
  for (var e = 0; e < graph.edges.length; e++) {
    var edge = graph.edges[e];
    var sourceMatched = !!matchedNodeIds[edge.source];
    var targetMatched = !!matchedNodeIds[edge.target];
    if ((sourceMatched || targetMatched) && edge.weight >= 3) {
      var connectedId = sourceMatched ? edge.target : edge.source;
      var connectedNode = null;
      for (var n = 0; n < graph.nodes.length; n++) {
        if (graph.nodes[n].id === connectedId) { connectedNode = graph.nodes[n]; break; }
      }
      if (connectedNode) {
        var ids = connectedNode.doc_ids || [];
        for (var k = 0; k < ids.length; k++) {
          if (ids[k] !== matchedDoc.id) {
            if (!relatedDocIds[ids[k]]) relatedDocIds[ids[k]] = [];
            if (relatedDocIds[ids[k]].indexOf(connectedNode.name) === -1) {
              relatedDocIds[ids[k]].push(connectedNode.name);
            }
          }
        }
      }
    }
  }

  // Build related docs list
  var relatedDocs = [];
  for (var docId in relatedDocIds) {
    var doc = docMap[docId];
    if (!doc) continue;
    relatedDocs.push({
      title: doc.title,
      url: doc.source_url || '',
      source: doc.source || '',
      created_at: doc.created_at || '',
      sharedTopics: relatedDocIds[docId]
    });
  }

  relatedDocs.sort(function(a, b) { return b.sharedTopics.length - a.sharedTopics.length; });

  return {
    topics: topics,
    relatedDocs: relatedDocs.slice(0, 30)
  };
}
