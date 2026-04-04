/**
 * Topic extraction via Claude API.
 * Ported from lifegraph/extractor.py
 */

var SYSTEM_PROMPT = 'You are a topic extraction engine. Given a document, extract specific, concrete topics that the document discusses in depth.\n\n' +
  'Rules:\n' +
  '- Return between 2 and 10 topics per document.\n' +
  '- Topics should be specific (e.g. "Datadog Log Pipelines", "Monitor Alert Fatigue") not vague (e.g. "Technology", "Observability").\n' +
  '- Use title case for topic names.\n' +
  '- If the document is a meeting note, extract the substantive topics discussed, not meta-topics like "Meeting Notes" or "Action Items".\n' +
  '- Each topic should have a relevance score from 0.0 to 1.0 indicating how central it is to the document.\n\n' +
  'Return ONLY a JSON array, no other text. Example:\n' +
  '[{"topic": "Datadog Log Pipelines", "relevance": 0.9}, {"topic": "Log Parsing Rules", "relevance": 0.6}]';

var CLAUDE_MODEL = 'claude-sonnet-4-20250514';
var MAX_TEXT_LENGTH = 12000;

function extractTopics(title, text) {
  var apiKey = getApiKey();
  if (!apiKey) {
    throw new Error('No Anthropic API key configured. Open Settings to add one.');
  }

  // Truncate long documents
  if (text.length > MAX_TEXT_LENGTH) {
    text = text.substring(0, MAX_TEXT_LENGTH) + '\n\n[... truncated ...]';
  }

  var userMessage = 'Document title: ' + title + '\n\n' + text;

  var payload = {
    model: CLAUDE_MODEL,
    max_tokens: 1024,
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: userMessage }]
  };

  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', options);
  var code = response.getResponseCode();

  if (code !== 200) {
    var errorBody = response.getContentText();
    throw new Error('Claude API error (' + code + '): ' + errorBody.substring(0, 200));
  }

  var result = JSON.parse(response.getContentText());
  var content = result.content[0].text;

  // Strip markdown code blocks if present
  content = content.replace(/^```json?\n?/i, '').replace(/\n?```$/i, '').trim();

  return JSON.parse(content);
}
