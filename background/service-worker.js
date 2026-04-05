// Opens the side panel when the extension icon is clicked on arxiv.org
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

// When a tab navigates to an arXiv abstract page, enable the action and
// forward the detected paper metadata to the sidebar.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "PAPER_DETECTED") {
    // Store the current paper so the sidebar can retrieve it on load.
    chrome.storage.session.set({ currentPaper: message.paper });

    // If the sidebar is already open, push the update directly.
    chrome.runtime.sendMessage({ type: "PAPER_UPDATED", paper: message.paper })
      .catch(() => {
        // Sidebar not open yet — that's fine, it will read from storage on open.
      });

    sendResponse({ ok: true });
  }
});
