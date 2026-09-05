/* ApplyJin Chrome Extension — Background service worker */

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    apiUrl: "",
    authToken: "",
  });
});

// Handle extension icon click — open popup (handled by manifest action)
