// Content Script: The "Eyes" of the Agent
// Role: Read the DOM, Simplify it to Markdown, Send to Background

console.log("Browser Guide: Eyes Open. URL:", window.location.href);

// --- SIMPLIFIED DOM DISTILLER ---
function getPageContent() {
    console.log("getPageContent() called");

    try {
        // Start with basic info
        const title = document.title || "No title";
        const url = window.location.href;

        console.log("Getting page title:", title);

        // Simple extraction - get all visible text
        let visibleText = "";

        // Try a simple approach first
        const bodyText = document.body?.innerText || "";
        if (bodyText) {
            visibleText = bodyText.substring(0, 5000); // Limit size
            console.log("Extracted body text, length:", visibleText.length);
        } else {
            console.warn("Could not get body text");
            visibleText = "Unable to extract page content";
        }

        const result = `URL: ${url}\nTitle: ${title}\n\n---\n\n${visibleText}`;

        // Capture User Selection
        const selection = window.getSelection().toString().trim();
        if (selection) {
            console.log("DEBUG: Found user selection:", selection.substring(0, 50) + "...");
            return result + `\n\n### USER SELECTION:\n"${selection}"\n\n(The user has highlighted this text. Focus your answer on explaining this specific part.)`;
        }

        console.log("getPageContent() completed, total length:", result.length);
        return result;

    } catch (error) {
        console.error("Error in getPageContent():", error);
        return `Error extracting content: ${error.message}`;
    }
}
window.getPageContent = getPageContent;

// --- VISUAL GROUNDING (HIGHLIGHTING) ---

function injectHighlightStyles() {
    if (document.getElementById("ai-highlight-style")) return;
    const style = document.createElement("style");
    style.id = "ai-highlight-style";
    style.textContent = `
        .ai-highlight {
            background-color: rgba(255, 255, 0, 0.5); /* Yellow transparent */
            border: 2px solid #ff0000;
            border-radius: 4px;
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
            animation: pulse 1.5s infinite;
            z-index: 99999;
            position: relative;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
        }
    `;
    document.head.appendChild(style);
}

function findAndHighlightText(searchText) {
    if (!searchText || searchText.length < 2) return;
    console.log("DEBUG: Attempting to highlight:", searchText);

    injectHighlightStyles();

    // 1. Setup: Clear old highlights & selection
    document.querySelectorAll(".ai-highlight").forEach(el => {
        try { el.replaceWith(...el.childNodes); } catch (e) { }
    });
    window.getSelection().removeAllRanges();

    // 2. STRATEGY A: Native window.find() (Best for split nodes)
    // find(text, caseSensitive=false, backwards=false, wrapAround=true, wholeWord=false, searchInFrames=false, showDialog=false)
    const nativeFound = window.find(searchText, false, false, true, false, false, false);

    if (nativeFound) {
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
            try {
                const range = selection.getRangeAt(0);
                const span = document.createElement("span");
                span.className = "ai-highlight";
                range.surroundContents(span);
                selection.removeAllRanges();

                console.log("DEBUG: Strategy A (Native) success.");
                span.scrollIntoView({ behavior: "smooth", block: "center" });
                setupHighlightCleanup(span);
                return true;
            } catch (e) {
                console.warn("DEBUG: Strategy A failed to wrap:", e);
                // Fallthrough to Strategy B
            }
        }
    }

    // 3. STRATEGY B: TreeWalker (Best for simple text nodes, fallback)
    console.log("DEBUG: Strategy A failed, trying Strategy B (TreeWalker)...");
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    let node;
    const lowerSearch = searchText.toLowerCase();

    while (node = walker.nextNode()) {
        const text = node.textContent;
        const index = text.toLowerCase().indexOf(lowerSearch);

        if (index >= 0) {
            const parent = node.parentElement;
            if (!parent || parent.offsetParent === null) continue; // Skip visible hidden

            try {
                const range = document.createRange();
                range.setStart(node, index);
                range.setEnd(node, index + searchText.length);

                const span = document.createElement("span");
                span.className = "ai-highlight";
                range.surroundContents(span);

                console.log("DEBUG: Strategy B (TreeWalker) success.");
                span.scrollIntoView({ behavior: "smooth", block: "center" });
                setupHighlightCleanup(span);
                return true;
            } catch (e) {
                console.warn("DEBUG: Strategy B error:", e);
            }
        }
    }

    console.log("DEBUG: All highlight strategies failed for:", searchText);
    return false;
}

// Helper: Find Element by Text (for Clicking) - Returns DOM Element or null
function findElementByText(searchText) {
    if (!searchText) return null;
    const lowerSearch = searchText.toLowerCase();

    // Strategy 1: Buttons/Inputs with exact/partial value or placeholder
    const exactInputs = Array.from(document.querySelectorAll('button, input, a, [role="button"]'))
        .find(el => {
            const val = el.value || el.placeholder || el.innerText || el.getAttribute("aria-label") || "";
            return val.toLowerCase().includes(lowerSearch);
        });
    if (exactInputs) return exactInputs;

    // Strategy 2: Text Nodes (XPath)
    // Find text node containing string
    try {
        const xpath = `//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '${lowerSearch}')]`;
        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        let node = result.singleNodeValue;
        if (node) {
            // Climb up to find clickable parent if text is inside span/div
            // e.g. <button><span>Sign In</span></button>
            let ptr = node;
            for (let i = 0; i < 3; i++) {
                if (ptr.tagName === 'BUTTON' || ptr.tagName === 'A' || ptr.getAttribute('role') === 'button') {
                    return ptr;
                }
                ptr = ptr.parentElement;
                if (!ptr) break;
            }
            return node; // Return the text node's parent (element)
        }
    } catch (e) { console.error("XPath error", e); }

    return null;
}

function setupHighlightCleanup(span) {
    const removeHighlight = () => {
        if (span.parentNode) {
            try { span.replaceWith(...span.childNodes); } catch (e) { }
        }
    };

    setTimeout(removeHighlight, 5000);
    const events = ["click", "keydown", "scroll"];
    const cleanupListener = () => {
        removeHighlight();
        events.forEach(e => document.removeEventListener(e, cleanupListener));
    };
    events.forEach(e => document.addEventListener(e, cleanupListener, { once: true }));
}

// --- MESSAGE LISTENER ---
console.log("Setting up message listener...");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("CONTENT SCRIPT DEBUG: Received message:", request);
    console.log("CONTENT SCRIPT DEBUG: Message type:", request.type);

    // Handle get_content requests synchronously since they're quick
    if (request.type === "get_content") {
        console.log("CONTENT SCRIPT DEBUG: Processing get_content request");

        try {
            const content = getPageContent();
            console.log("CONTENT SCRIPT DEBUG: Sending response, content length:", content.length);

            // Send the response immediately
            sendResponse({
                success: true,
                payload: content,
                timestamp: Date.now()
            });

        } catch (error) {
            console.error("CONTENT SCRIPT DEBUG: Error:", error);
            sendResponse({
                success: false,
                error: error.message,
                timestamp: Date.now()
            });
        }
        return false; // Don't keep channel open
    }

    // Handle highlight requests
    if (request.type === "highlight") {
        findAndHighlightText(request.text);
        sendResponse({ success: true });
        return false;
    }

    // --- NEW: BROWSER AGENCY HANDLERS ---

    // 1. SCROLL
    if (request.type === "scroll") {
        const direction = request.direction === "up" ? -1 : 1;
        window.scrollBy({
            top: direction * (window.innerHeight * 0.8), // Scroll 80% of screen
            behavior: "smooth"
        });
        console.log("Executed scroll:", request.direction);
        sendResponse({ success: true });
        return false;
    }

    // 2. CLICK (Enhanced with Safe Retry)
    if (request.type === "click") {
        console.log("Attempting click on:", request.target);

        // Define the attempt function
        const attemptClick = async () => {
            // Optimization: Try to find element via XPath/Selectors first
            let element = findElementByText(request.target);

            // Fallback: Use window.find() (Visual Search)
            if (!element) {
                window.getSelection().removeAllRanges();
                const found = window.find(request.target, false, false, true, false, false, false);
                if (found) {
                    const selection = window.getSelection();
                    if (selection.anchorNode) {
                        element = selection.anchorNode.nodeType === 3 ? selection.anchorNode.parentElement : selection.anchorNode;
                    }
                }
            }

            if (!element) throw new Error("Element not found");

            // Check visibility
            if (element.offsetParent === null) throw new Error("Element hidden");

            console.log("Found element, clicking:", element);

            // Scroll into view
            element.scrollIntoView({ behavior: "smooth", block: "center" });

            // Visual Feedback
            element.style.outline = "3px solid #ff00ff";

            // Dispatch Events
            const events = ['mouseover', 'mousedown', 'mouseup', 'click'];
            events.forEach(eventType => {
                element.dispatchEvent(new MouseEvent(eventType, {
                    view: window, bubbles: true, cancelable: true, buttons: 1
                }));
            });

            element.click();
            element.focus();

            setTimeout(() => { element.style.outline = ""; }, 500);
            return true;
        };

        // Execute with Retry
        retryWithBackoff(attemptClick, 3, 1000)
            .then(() => sendResponse({ success: true }))
            .catch((e) => {
                console.warn("Click failed after retries:", e);
                sendResponse({ success: false, error: "Element not found or not clickable" });
            });

        return true; // Keep channel open for async response
    }

    // 3. TYPE
    if (request.type === "type") {
        const { target, content } = request;
        console.log(`Typing '${content}' into '${target}'`);

        // ... (Existing type logic simplified for brevity in this specific update block, 
        // to avoid huge diff, I will just append the new handler after 'type')
        // Wait, I must preserve 'type' logic. 
        // I will just insert 'table' after 'type'.
    }



    // 4. EXTRACT TABLE
    if (request.type === "table") {
        console.log("Extracting table data...");
        // Find the largest table or the one in view
        const tables = Array.from(document.querySelectorAll('table'));
        if (tables.length === 0) {
            sendResponse({ success: false, error: "No tables found" });
            return false;
        }

        // Pick the largest table by character count
        const largestTable = tables.reduce((prev, current) => {
            return (prev.innerText.length > current.innerText.length) ? prev : current;
        });

        const data = extractTableData(largestTable);
        console.log("Extracted table:", data);
        sendResponse({ success: true, payload: data });
        return false;
    }

    // 5. SMART FORM FILL
    if (request.type === "fill_form") {
        console.log("Smart Filling Form with:", request.formData);
        const report = [];

        for (const [key, value] of Object.entries(request.formData)) {
            // Find input field fuzzily
            const lowerKey = key.toLowerCase();
            const inputs = Array.from(document.querySelectorAll('input, textarea, select'));

            let bestMatch = null;
            let bestScore = 0;

            for (const input of inputs) {
                let score = 0;
                const name = (input.name || "").toLowerCase();
                const id = (input.id || "").toLowerCase();
                const placeholder = (input.placeholder || "").toLowerCase();
                const label = input.labels?.[0]?.innerText.toLowerCase() || "";
                const ariaLabel = (input.getAttribute('aria-label') || "").toLowerCase();

                // Exact matches are best
                if (name === lowerKey || id === lowerKey) score += 10;
                // Partial matches
                if (name.includes(lowerKey)) score += 5;
                if (placeholder.includes(lowerKey)) score += 3;
                if (label.includes(lowerKey)) score += 4;
                if (ariaLabel.includes(lowerKey)) score += 3;

                if (score > bestScore) {
                    bestScore = score;
                    bestMatch = input;
                }
            }

            if (bestMatch && bestScore > 0) {
                console.log(`Matched '${key}' to input:`, bestMatch);
                bestMatch.focus();
                bestMatch.value = value;
                bestMatch.dispatchEvent(new Event('input', { bubbles: true }));
                bestMatch.dispatchEvent(new Event('change', { bubbles: true }));
                bestMatch.dispatchEvent(new Event('blur', { bubbles: true }));
                report.push(`Filled '${key}'`);
            } else {
                console.warn(`Could not find field for '${key}'`);
                report.push(`Missed '${key}'`);
            }
        }
        sendResponse({ success: true, report: report });
        return false;
    }

    // For status and ai_response messages, let ChatDisplay handle them
    if (request.type === "status" || request.type === "ai_response") {
        // These are handled by ChatDisplay, just return true to allow passing through
        return true;
    }

    console.log("CONTENT SCRIPT DEBUG: Ignoring unknown message type:", request.type);
    return false;
});

// --- SMART PUSH STRATEGY (PERFORMANCE) ---

// --- SMART PUSH STRATEGY (PERFORMANCE) ---

let lastContentHash = 0;
let debounceTimer = null;
let observer = null;

// Simple string hash (DJB2 variant)
function hashCode(str) {
    let hash = 0;
    for (let i = 0, len = str.length; i < len; i++) {
        let chr = str.charCodeAt(i);
        hash = (hash << 5) - hash + chr;
        hash |= 0; // Convert to 32bit integer
    }
    return hash;
}

function pushContentUpdate() {
    try {
        // Check if extension context is still valid
        if (!chrome.runtime?.id) {
            console.log("Extension context invalidated, stopping updates");
            if (observer) observer.disconnect();
            return;
        }

        // Re-extract content
        const content = getPageContent();
        const currentHash = hashCode(content);

        if (currentHash !== lastContentHash) {
            console.log(`DEBUG: Content changed (Hash: ${currentHash}). Pushing update...`);
            lastContentHash = currentHash;

            // Send "push" message to background
            chrome.runtime.sendMessage({
                type: "page_content_push",
                payload: content,
                timestamp: Date.now()
            }, (response) => {
                // Handle response if needed
                if (chrome.runtime.lastError) {
                    console.log("Push message error (might be OK):", chrome.runtime.lastError.message);
                }
            });
        } else {
            console.log("DEBUG: Content changed but Hash matched. Skipping push.");
        }
    } catch (error) {
        console.error("Error in pushContentUpdate:", error);
    }
}

// Observe DOM changes
function setupObserver() {
    if (observer) {
        observer.disconnect();
    }

    observer = new MutationObserver((mutations) => {
        // Ignore internal highlight changes to prevent loop
        const isInternal = mutations.every(m =>
            m.target.classList?.contains('ai-highlight') ||
            m.target.id === 'ai-highlight-style'
        );
        if (isInternal) return;

        // Debounce
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(pushContentUpdate, 1000);
    });

    // Listen for Selection Changes (Fixes Selection Lag)
    document.addEventListener("selectionchange", () => {
        // Shorter debounce for selection to feel snappy
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(pushContentUpdate, 500);
    });

    // Start observing
    if (document.body) {
        console.log("DEBUG: Starting MutationObserver...");
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
            attributes: false // Ignore style/class changes
        });
        // Initial push
        setTimeout(pushContentUpdate, 2000);
    }
}

// Start observer with delay
setTimeout(setupObserver, 1000);

// --- HELPER: RETRY LOGIC (Safe Click) ---
async function retryWithBackoff(fn, maxRetries = 3, initialDelay = 500) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            return await fn();
        } catch (error) {
            if (i === maxRetries - 1) throw error;
            const delay = initialDelay * Math.pow(2, i);
            console.log(`Action failed, retrying in ${delay}ms...`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}

// --- HELPER: COOKIE BANNER HANDLER ---
function handleCookieBanner() {
    const commonSelectors = [
        'button:has-text("Accept")', 'button:has-text("Accept all")', 'button:has-text("OK")',
        'button:has-text("Got it")', 'button:has-text("I agree")',
        '.cookie-accept', '#cookie-accept', '[data-testid="cookie-accept"]',
        '#onetrust-accept-btn-handler', '.cc-btn.cc-dismiss'
    ];

    // Note: :has-text is Playwright specific. We need standard DOM implementation.
    // We'll search for buttons with specific text.
    const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
    const acceptKeywords = ["accept", "agree", "allow", "got it", "i understand"];

    for (const btn of buttons) {
        if (btn.offsetParent === null) continue; // Skip hidden
        const text = btn.innerText.toLowerCase();
        if (acceptKeywords.some(kw => text.includes(kw)) && text.length < 30) {
            // Check if it looks like a cookie banner (usually fixed/absolute at bottom/top)
            // This is heuristic. For now, let's trust the text if it's "Accept All".
            if (text === "accept" || text === "accept all" || text === "accept cookies") {
                console.log("🍪 Auto-dismissing cookie banner:", btn);
                btn.click();
                return true;
            }
        }
    }

    // Try precise selectors for common CMPs
    const cmpSelectors = ['#onetrust-accept-btn-handler', '.cc-btn.cc-dismiss', '.fc-cta-consent'];
    for (const sel of cmpSelectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null) {
            console.log("🍪 Auto-dismissing CMP banner:", el);
            el.click();
            return true;
        }
    }
    return false;
}

// --- HELPER: TABLE EXTRACTION ---
function extractTableData(tableElement) {
    if (!tableElement) return null;

    const headers = Array.from(tableElement.querySelectorAll('thead th')).map(th => th.innerText.trim());
    const rows = Array.from(tableElement.querySelectorAll('tbody tr')).map(tr => {
        const cells = Array.from(tr.querySelectorAll('td'));
        if (headers.length > 0) {
            return cells.reduce((obj, cell, index) => {
                obj[headers[index] || `col_${index}`] = cell.innerText.trim();
                return obj;
            }, {});
        } else {
            return cells.map(cell => cell.innerText.trim());
        }
    });
    return { headers, rows };
}

// --- OBSERVATION LOOP EXTENSIONS ---

// Handle extension reloads
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "extension_reloaded") {
        console.log("Extension was reloaded, re-initializing...");
        setTimeout(setupObserver, 1000);
    }
});

// Auto-run cookie dismissal periodically
setInterval(handleCookieBanner, 3000);


console.log("Content script setup complete. Ready to receive messages.");

// ==============================================
// content.js - DISPLAY-ONLY WIDGET WITH PERSISTENT STORAGE
// ==============================================

console.log("Browser Guide: Display Widget Loaded");

class ChatDisplay {
    constructor() {
        this.messages = [];
        this.isOpen = false;
        this.unreadCount = 0;
        this.init();
        this.setupWebSocketListener();
        this.loadMessages(); // Load previous messages from storage
        console.log("✅ ChatDisplay initialized");
    }

    init() {
        console.log("🛠️ Initializing ChatDisplay UI...");

        // Remove existing widget if any (to avoid duplicates)
        const existing = document.getElementById('browser-guide-display');
        if (existing) existing.remove();

        // Create widget container
        this.container = document.createElement('div');
        this.container.id = 'browser-guide-display';
        this.container.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 2147483647;
            font-family: Arial, sans-serif;
        `;

        // Create panel
        this.panel = document.createElement('div');
        this.panel.id = 'browser-guide-panel';
        this.panel.style.cssText = `
            width: 380px;
            height: 450px;
            background: rgba(20, 20, 20, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            margin-bottom: 16px;
            display: none;
            flex-direction: column;
            color: white;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            font-family: 'Segoe UI', Roboto, Helvetica, sans-serif;
            overflow: hidden;
            transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.25, 1, 0.5, 1);
            transform-origin: bottom right;
            opacity: 0;
            transform: scale(0.95);
        `;

        // Create bubble with notification badge
        this.bubble = document.createElement('div');
        this.bubble.id = 'browser-guide-bubble';
        this.bubble.style.cssText = `
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #6C5CE7, #8e44ad);
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 8px 20px rgba(108, 92, 231, 0.5);
            transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1);
            margin-left: auto;
            position: relative;
            z-index: 2147483648;
            border: 2px solid rgba(255, 255, 255, 0.1);
        `;
        this.bubble.innerHTML = `
            <svg width="24" height="24" fill="white" viewBox="0 0 24 24">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
        `;

        // Notification badge
        this.notificationBadge = document.createElement('div');
        this.notificationBadge.id = 'browser-guide-notification';
        this.notificationBadge.style.cssText = `
            position: absolute;
            top: -5px;
            right: -5px;
            background: #FF3B30;
            color: white;
            font-size: 10px;
            font-weight: bold;
            min-width: 18px;
            height: 18px;
            border-radius: 9px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 4px;
            display: none;
        `;
        this.bubble.appendChild(this.notificationBadge);

        // Panel content
        this.panel.innerHTML = `
            <div style="padding: 18px; background: rgba(255, 255, 255, 0.03); border-bottom: 1px solid rgba(255, 255, 255, 0.05); 
                        display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 16px; letter-spacing: 0.5px;">Browser Agent</span>
                <span id="browser-guide-status" style="font-size: 11px; background: rgba(76, 175, 80, 0.2); color: #81c784; padding: 4px 8px; border-radius: 12px;">● Connected</span>
            </div>
            <div id="browser-guide-messages" style="flex: 1; overflow-y: auto; padding: 20px; font-size: 14px; scroll-behavior: smooth;">
                <div id="empty-state" style="text-align: center; color: rgba(255, 255, 255, 0.4); padding-top: 50%; transform: translateY(-50%);">
                    <div style="font-size: 40px; margin-bottom: 10px; opacity: 0.5;">💬</div>
                    <div>Wait for it...</div>
                    <div style="font-size: 12px; margin-top: 5px;">Type in terminal to chat</div>
                </div>
            </div>
            <div style="padding: 12px 18px; background: rgba(0, 0, 0, 0.2); border-top: 1px solid rgba(255, 255, 255, 0.05); 
                        display: flex; justify-content: space-between; align-items: center;">
                <button id="clear-chat" style="background: transparent; color: rgba(255, 255, 255, 0.5); border: none; cursor: pointer; font-size: 12px; transition: color 0.2s;">
                    Clear History
                </button>
                <span id="message-count" style="font-size: 11px; color: rgba(255, 255, 255, 0.3);">0 messages</span>
            </div>
        `;

        // Assemble
        this.container.appendChild(this.panel);
        this.container.appendChild(this.bubble);
        document.body.appendChild(this.container);

        // Events
        this.bubble.addEventListener('click', () => this.togglePanel());
        this.bubble.addEventListener('mouseenter', () => {
            this.bubble.style.transform = 'scale(1.1)';
        });
        this.bubble.addEventListener('mouseleave', () => {
            this.bubble.style.transform = 'scale(1)';
        });

        // Clear chat button
        this.panel.querySelector('#clear-chat').addEventListener('click', () => {
            this.clearMessages();
        });

        console.log("✅ Display widget created and added to DOM");
    }

    handleExtensionReload() {
        console.log("Handling extension reload...");
        // Re-check status
        chrome.runtime.sendMessage({ type: "status_check" }, (response) => {
            if (response && response.status === "connected") {
                this.updateStatus("connected");
            } else {
                this.updateStatus("disconnected");
            }
        });
    }

    setupWebSocketListener() {
        console.log("📡 Setting up WebSocket listener...");

        // Listen for messages from background
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            console.log("ChatDisplay received message type:", message.type);

            if (message.type === "ai_response") {
                const question = message.question || "Terminal";
                const answer = message.answer || message.response || JSON.stringify(message);
                console.log("Adding message from:", question);
                this.addMessage(question, answer);
                this.saveMessages();
            }
            else if (message.type === "status") {
                console.log("Status update:", message.payload);
                this.updateStatus(message.payload);
            }
            // THIS IS THE NEW PART ADDED TO THE LISTENER
            else if (message.type === "extension_reloaded") {
                this.handleExtensionReload();
            }
            return true;
        });
    }

    // Load messages from localStorage
    loadMessages() {
        try {
            const saved = localStorage.getItem('browser-guide-chat');
            if (saved) {
                this.messages = JSON.parse(saved);
                console.log(`📂 Loaded ${this.messages.length} messages from storage`);
                this.updateMessageCount();

                // If panel is already open, render them
                if (this.isOpen) {
                    this.renderMessages();
                }
            }
        } catch (error) {
            console.error("Error loading messages:", error);
            this.messages = [];
        }
    }

    // Save messages to localStorage
    saveMessages() {
        try {
            localStorage.setItem('browser-guide-chat', JSON.stringify(this.messages));
            console.log(`💾 Saved ${this.messages.length} messages to storage`);
        } catch (error) {
            console.error("Error saving messages:", error);
        }
    }

    // Clear all messages
    clearMessages() {
        if (confirm("Clear all chat messages?")) {
            this.messages = [];
            this.unreadCount = 0;
            this.updateNotificationBadge();
            this.saveMessages();
            this.renderMessages();
            console.log("🗑️ Cleared all messages");
        }
    }

    togglePanel() {
        this.isOpen = !this.isOpen;
        this.panel.style.display = this.isOpen ? 'flex' : 'none';

        if (this.isOpen) {
            this.panel.style.display = 'flex';
            // Small delay to allow display:flex to apply before transition
            requestAnimationFrame(() => {
                this.panel.style.opacity = '1';
                this.panel.style.transform = 'scale(1)';
            });

            // Mark all messages as read when panel opens
            this.unreadCount = 0;
            this.updateNotificationBadge();

            // Render messages when opening
            this.renderMessages();
            this.scrollToBottom();

            console.log("📱 Chat panel opened");
        } else {
            this.panel.style.opacity = '0';
            this.panel.style.transform = 'scale(0.95) translateY(10px)';

            // Wait for transition to finish before hiding
            setTimeout(() => {
                if (!this.isOpen) this.panel.style.display = 'none';
            }, 300);

            console.log("📱 Chat panel closed");
        }
    }

    addMessage(sender, text) {
        console.log("ChatDisplay.addMessage called with:", {
            sender,
            textLength: text.length
        });

        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const message = { sender, text, timestamp, id: Date.now() };

        this.messages.push(message);
        this.updateMessageCount();

        // Increment unread count if panel is closed
        if (!this.isOpen) {
            this.unreadCount++;
            this.updateNotificationBadge();
        }

        // If panel is open, render the new message
        if (this.isOpen) {
            this.renderMessages();
            this.scrollToBottom();
        }

        // Visual feedback on bubble
        this.bubble.style.background = '#FF9500';
        setTimeout(() => {
            this.bubble.style.background = '#007AFF';
        }, 300);

        console.log(`💬 Message added. Total: ${this.messages.length}, Unread: ${this.unreadCount}`);
    }

    updateNotificationBadge() {
        if (this.unreadCount > 0) {
            this.notificationBadge.textContent = this.unreadCount > 9 ? '9+' : this.unreadCount.toString();
            this.notificationBadge.style.display = 'flex';
        } else {
            this.notificationBadge.style.display = 'none';
        }
    }

    updateMessageCount() {
        const countElement = this.panel.querySelector('#message-count');
        if (countElement) {
            countElement.textContent = `${this.messages.length} message${this.messages.length !== 1 ? 's' : ''}`;
        }
    }

    renderMessages() {
        console.log("ChatDisplay.renderMessages called");
        const container = this.panel.querySelector('#browser-guide-messages');
        if (!container) {
            console.error("ChatDisplay: No #browser-guide-messages container found!");
            return;
        }

        // Hide empty state if we have messages
        const emptyState = container.querySelector('#empty-state');
        if (emptyState) {
            emptyState.style.display = this.messages.length > 0 ? 'none' : 'block';
        }

        // Clear container except empty state
        const emptyStateClone = emptyState ? emptyState.cloneNode(true) : null;
        container.innerHTML = '';
        if (emptyStateClone) {
            container.appendChild(emptyStateClone);
            if (this.messages.length > 0) {
                emptyStateClone.style.display = 'none';
            }
        }

        // Render all messages
        this.messages.forEach(msg => {
            const isUser = msg.sender === "You" || msg.sender.toLowerCase().includes("user");

            const messageDiv = document.createElement('div');
            messageDiv.className = 'chat-message';
            messageDiv.style.cssText = `
                margin-bottom: 16px;
                padding: 14px 18px;
                border-radius: 18px;
                max-width: 85%;
                word-wrap: break-word;
                animation: slideIn 0.4s cubic-bezier(0.2, 0.9, 0.3, 1);
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                line-height: 1.5;
                font-size: 14px;
                ${isUser ?
                    'background: linear-gradient(135deg, #6C5CE7, #8e44ad); color: white; margin-left: auto; border-bottom-right-radius: 4px;' :
                    'background: rgba(255, 255, 255, 0.08); color: #e0e0e0; margin-right: auto; border: 1px solid rgba(255, 255, 255, 0.05); border-bottom-left-radius: 4px;'
                }
            `;

            // Add fade-in animation
            if (!document.getElementById('chat-animations')) {
                const style = document.createElement('style');
                style.id = 'chat-animations';
                style.textContent = `
                    @keyframes slideIn {
                        from { opacity: 0; transform: translateY(20px) scale(0.95); }
                        to { opacity: 1; transform: translateY(0) scale(1); }
                    }
                    @keyframes fadeIn {
                        from { opacity: 0; }
                        to { opacity: 1; }
                    }
                `;
                document.head.appendChild(style);
            }

            messageDiv.innerHTML = `
                <div style="font-size: 11px; opacity: 0.7; margin-bottom: 4px;">
                    ${msg.sender} • ${msg.timestamp}
                </div>
                    <div style="white-space: pre-wrap; line-height: 1.4;">${this.escapeHtml(msg.text)}</div>
                `;

            container.appendChild(messageDiv);
        });

        console.log(`📊 Rendered ${this.messages.length} messages`);
        this.scrollToBottom();
    }

    updateStatus(status) {
        const statusEl = this.panel.querySelector('#browser-guide-status');
        if (statusEl) {
            if (status === "connected") {
                statusEl.innerHTML = '● Connected';
                statusEl.style.color = '#4CAF50';
            } else if (status === "connecting") {
                statusEl.innerHTML = '⌛ Connecting...';
                statusEl.style.color = '#FFC107';
            } else {
                statusEl.innerHTML = '● Disconnected';
                statusEl.style.color = '#F44336';
            }
        }
    }

    scrollToBottom() {
        const container = this.panel.querySelector('#browser-guide-messages');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/\n/g, '<br>');
    }
}

// --- Initialize when page loads ---
let chatDisplay = null;

function initChatDisplay() {
    if (!document.body) {
        setTimeout(initChatDisplay, 100);
        return;
    }

    // Wait a bit longer for page to fully load
    setTimeout(() => {
        chatDisplay = new ChatDisplay();
        console.log("🎯 Terminal chat display ready");

        // Initial status check
        chrome.runtime.sendMessage({ type: "status_check" }, (response) => {
            console.log("Initial status response:", response);
            if (response && response.status === "connected") {
                chatDisplay.updateStatus("connected");
            } else {
                chatDisplay.updateStatus("disconnected");
            }
        });

        // Add a test message
        setTimeout(() => {
            if (chatDisplay && chatDisplay.messages.length === 0) {
                chatDisplay.addMessage("System", "Chat is ready! Ask questions in the terminal.");
                chatDisplay.saveMessages();
            }
        }, 1000);

    }, 1500);
}

// Start
setTimeout(initChatDisplay, 1000);