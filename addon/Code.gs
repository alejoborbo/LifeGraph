/**
 * LifeGraph Google Docs Add-on
 * Shows topics and related documents from the knowledge graph.
 */

function onOpen(e) {
  DocumentApp.getUi()
    .createAddonMenu()
    .addItem('Show sidebar', 'showSidebar')
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

function getDocumentText() {
  var doc = DocumentApp.getActiveDocument();
  return {
    title: doc.getName(),
    body: doc.getBody().getText(),
    url: doc.getUrl()
  };
}
