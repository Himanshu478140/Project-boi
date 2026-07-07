# Task: Generic Browser Guide (Text-First)

## Scaffolding
- [x] Create Extension Manifest (V3)
- [x] Create Background Service Worker (WebSocket Client)
- [x] Create Content Script (DOM Distiller)
- [x] Create Python Backend (FastAPI + WebSocket)
- [x] Create CLI Client

## Implementation
- [x] Implement Logic for "Text-First" extraction (Markdown)
- [x] Integrate OpenAI (GPT-4o-mini) for answering
- [x] Add Keep-Alive Heartbeat for WebSocket
- [x] Add Robust Tab Identification (lastFocusedWindow + Fallbacks)
- [x] Add Auto-Injection for Content Script

## Verification
- [x] Verify WebSocket Connection (Green Badge)
- [x] Verify Data Flow (CLI -> Server -> Extension -> Page -> Extension -> Server -> CLI)
- [x] Verify Error Handling (Timeout Recovery)

## Visual Grounding
- [x] Plan "Implicit Highlighting" Strategy
- [x] Implement Backend Logic (Quote Extraction)
- [x] Implement Frontend Logic (Highlight Rendering)
- [x] Debug Validation & Formatting
- [x] User Fixes (Background Relay + Timeout)

## Performance Optimization
- [x] Implement Push-based Content Sync (MutationObserver)
- [x] Optimize Server Cache Strategy

## AI Backend Crawler (New)
- [ ] Setup Playwright + Proxy Manager
- [ ] Define Pydantic Models (Schema & Config)
- [ ] Implement Phase 1: Selector Engine (BeautifulSoup)
## Floating Chat Interface
- [ ] Implement Shadow DOM Overlay (`content.js + styles`)
- [ ] Connect Overlay to Background Script (Messaging)
- [ ] Handle Chat History & Streaming Responses
- [ ] Stylize UI (Glassmorphism/Modern)
