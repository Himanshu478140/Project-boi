// Background Service Worker
// Responsibilities: Hold WebSocket connection, Relay messages

// 1. ADD THIS AT THE START
console.log("🔧 Background script started");

let socket = null;
const SERVER_URL = "ws://localhost:8000/ws/client";
// New: Track active tabs
let activeTabs = new Set();

function connect() {
    if (socket && socket.readyState === WebSocket.OPEN) return;

    console.log("🔌 Connecting to server...");
    socket = new WebSocket(SERVER_URL);

    socket.onopen = () => {
        console.log("✅ Connected to server");
        chrome.action.setBadgeText({ text: "ON" });
        chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });

        chrome.tabs.query({}, (tabs) => {
            tabs.forEach(tab => {
                if (tab.id) {
                    try {
                        // 1. Notify of connection
                        chrome.tabs.sendMessage(tab.id, {
                            type: "status",
                            payload: "connected"
                        });

                        // 2. Signal reload (so content script re-hooks observers)
                        chrome.tabs.sendMessage(tab.id, {
                            type: "extension_reloaded"
                        });
                    } catch (e) { }
                }
            });
        });
    };

    // 2. REPLACE the old socket.onmessage with your NEW version here:
    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log("📨 Received from server:", data);

            let relayMessage = data;

            if (data.question && data.answer && data.type === "ai_response") {
                relayMessage = data;
            }
            else if (data.question && data.answer) {
                relayMessage = {
                    type: "ai_response",
                    question: data.question,
                    answer: data.answer
                };
            }

            // --- BROWSER NAVIGATION HANDLERS (Execute in Background) ---

            // 1. GOTO URL
            if (data.type === "goto") {
                console.log("Navigating to:", data.url);
                chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                    if (tabs[0]) {
                        chrome.tabs.update(tabs[0].id, { url: data.url });
                    }
                });
                return; // Don't relay
            }

            // 2. BACK
            if (data.type === "back") {
                console.log("Navigating Back");
                chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                    if (tabs[0]) {
                        chrome.tabs.goBack(tabs[0].id);
                    }
                });
                return;
            }

            // 3. RELOAD
            if (data.type === "reload") {
                console.log("Reloading Page");
                chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                    if (tabs[0]) {
                        chrome.tabs.reload(tabs[0].id);
                    }
                });
                return;
            }

            // 4. NEW TAB
            if (data.type === "new_tab") {
                console.log("Opening New Tab");
                chrome.tabs.create({ url: data.url || "chrome://newtab" });
                return;
            }

            // 5. CLOSE TAB
            if (data.type === "close_tab") {
                console.log("Closing Current Tab");
                chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                    if (tabs[0]) {
                        chrome.tabs.remove(tabs[0].id);
                    }
                });
                return;
            }

            chrome.tabs.query({}, (tabs) => {
                tabs.forEach(tab => {
                    if (tab.id) {
                        try {
                            console.log("📤 Relaying to tab:", tab.id, relayMessage.type);
                            // New: Added response callback and lastError check
                            chrome.tabs.sendMessage(tab.id, relayMessage, (response) => {
                                if (chrome.runtime.lastError) {
                                    // console.log("Could not send to tab", tab.id, chrome.runtime.lastError.message);
                                    return;
                                }

                                // FIX: Forward response back to server (Crucial for get_content)
                                if (response && response.success && response.payload) {
                                    // console.log("📥 Received content response from tab", tab.id);
                                    if (socket && socket.readyState === WebSocket.OPEN) {
                                        socket.send(JSON.stringify({
                                            type: "page_content",
                                            payload: response.payload
                                        }));
                                    }
                                }
                            });
                        } catch (e) {
                            console.log("Error sending to tab", tab.id, e.message);
                        }
                    }
                });
            });

        } catch (error) {
            console.error("Error parsing message:", error);
        }
    };

    socket.onclose = () => {
        console.log("❌ Disconnected");
        chrome.action.setBadgeText({ text: "OFF" });
        chrome.action.setBadgeBackgroundColor({ color: "#F44336" });

        chrome.tabs.query({}, (tabs) => {
            tabs.forEach(tab => {
                if (tab.id) {
                    try {
                        chrome.tabs.sendMessage(tab.id, {
                            type: "status",
                            payload: "disconnected"
                        });
                    } catch (e) { }
                }
            });
        });

        setTimeout(connect, 3000);
    };

    socket.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}

// 3. LISTENERS (Keep existing, add new tab tracker)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "page_content_push" && socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
    }

    if (message.type === "status_check") {
        const status = (socket && socket.readyState === WebSocket.OPEN) ? "connected" : "disconnected";
        sendResponse({ status: status });
    }

    if (message.type === "connect") {
        connect();
        sendResponse({ status: "connecting" });
    }
    return true;
});

// 4. ADD THIS AT THE END: Track tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.active) {
        console.log("Tab updated:", tabId);
        // Notify content script extension is ready
        setTimeout(() => {
            try {
                chrome.tabs.sendMessage(tabId, {
                    type: "status",
                    payload: (socket && socket.readyState === WebSocket.OPEN) ? "connected" : "disconnected"
                });
            } catch (e) { }
        }, 1000);
    }
});

// Start connection
connect();