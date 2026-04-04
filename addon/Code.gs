/**
 * LifeGraph Google Docs Add-on
 * Shows extracted topics and related documents in a sidebar.
 */

function onOpen(e) {
  DocumentApp.getUi()
    .createAddonMenu()
    .addItem('Show sidebar', 'showSidebar')
    .addItem('Settings', 'showSettings')
    .addToUi();
}

function onInstall(e) {
  onOpen(e);
}

function showSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('LifeGraph');
  DocumentApp.getUi().showSidebar(html);
}

function showSettings() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('LifeGraph');
  DocumentApp.getUi().showSidebar(html);
}

function getDocumentText() {
  var doc = DocumentApp.getActiveDocument();
  return {
    title: doc.getName(),
    body: doc.getBody().getText(),
    url: doc.getUrl()
  };
}

function getApiKey() {
  return PropertiesService.getUserProperties().getProperty('ANTHROPIC_API_KEY') || '';
}

function setApiKey(key) {
  PropertiesService.getUserProperties().setProperty('ANTHROPIC_API_KEY', key.trim());
  return true;
}
