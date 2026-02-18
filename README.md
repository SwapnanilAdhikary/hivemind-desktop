# Unified AI Agent Platform

A centralized desktop platform that monitors Gmail, WhatsApp, Instagram, and Discord messages, with AI-powered auto-reply capabilities, real-time agent tracing, and self-evolving tool creation.

## Architecture

- **Electron Desktop App** -- React + TypeScript + TailwindCSS dashboard with React Flow graph visualization
- **Python Backend** -- FastAPI + LangGraph orchestrator + LangChain for LLM integration
- **WhatsApp Bridge** -- Node.js Baileys service for WhatsApp Web protocol
- **Dual LLM Support** -- Ollama (local models) and cloud APIs (OpenAI, Anthropic) with automatic fallback

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Ollama (optional, for local models) -- [install from ollama.com](https://ollama.com)
- Redis (optional, for message queue)

### 1. Install Dependencies

```bash
# Backend (Python)
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Frontend (Node.js)
cd ../frontend
npm install

# WhatsApp Bridge (Node.js)
cd ../whatsapp-bridge
npm install
```

### 2. Configure Environment

Copy `.env` and fill in your credentials:

```
OPENAI_API_KEY=sk-...          # or leave empty for Ollama-only
DISCORD_BOT_TOKEN=...          # from Discord Developer Portal
INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...
```

For Gmail, download `credentials.json` from Google Cloud Console (Gmail API) and place it at `credentials/gmail_credentials.json`.

### 3. Run the Platform

Start each service in a separate terminal:

```bash
# Terminal 1: Python backend
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Frontend (dev mode)
cd frontend
npm run dev

# Terminal 3: WhatsApp bridge (optional)
cd whatsapp-bridge
npm run dev

# Terminal 4: Electron desktop app
cd frontend
npm run electron:dev
```

Or just use the frontend in your browser at `http://localhost:5173`.

## Features

### Activity Feed
Real-time cross-platform message feed showing all incoming messages with urgency levels and AI-suggested actions.

### Agent Trace Viewer
Chronological log of every LangGraph node execution with input/output state, timing, and decision reasoning.

### Decision Graph
Interactive React Flow visualization of the LangGraph orchestrator, with real-time execution highlighting.

### Conversation Panel
View and reply to messages from any platform. AI drafts replies that you can edit before sending.

### Tool Registry
- **Manual tools** -- Register Python functions manually
- **AI-generated tools** -- Describe what you need in natural language; the AI creates, validates (static + LLM safety review), and registers the tool
- Tools persist across sessions and can be enabled/disabled/deleted from the dashboard

### LLM Router
- Configure per-task LLM routing (e.g., Ollama for classification, cloud API for complex replies)
- Automatic fallback chain if primary provider is unavailable
- Supports: Ollama (any model), OpenAI (GPT-4o, etc.), Anthropic (Claude)

## Project Structure

```
├── backend/              # Python FastAPI + LangGraph
│   └── app/
│       ├── agents/       # Platform-specific agents + orchestrator
│       ├── integrations/ # API clients (Gmail, Discord, Instagram, WhatsApp)
│       ├── llm/          # LLM router + provider configs
│       ├── tools/        # Dynamic tool registry + AI tool creator
│       ├── tracing/      # Execution tracing system
│       ├── db/           # SQLAlchemy models + async database
│       └── websocket/    # Real-time WebSocket manager
├── frontend/             # React + TypeScript + Vite
│   └── src/
│       ├── components/   # Dashboard, ActivityFeed, NodeGraph, etc.
│       ├── stores/       # Zustand state management
│       └── hooks/        # WebSocket hook
├── electron/             # Electron main process
├── whatsapp-bridge/      # Node.js Baileys WhatsApp bridge
└── .env                  # Environment configuration
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | System health + LLM provider status |
| GET | `/api/llm/models` | Available models by provider |
| POST | `/api/messages/incoming` | Submit a message for agent processing |
| GET | `/api/messages` | List stored messages |
| POST | `/api/messages/reply` | Send a generic reply |
| POST | `/api/platforms/{platform}/reply` | Send reply via specific platform |
| GET | `/api/traces` | List agent execution traces |
| GET | `/api/traces/{run_id}` | Get trace details for a run |
| GET | `/api/tools` | List registered tools |
| POST | `/api/tools` | Register a tool manually |
| POST | `/api/tools/create` | AI-generate a new tool |
| POST | `/api/tools/execute` | Execute a registered tool |
| GET | `/api/graph/definition` | Get orchestrator graph for visualization |
| GET | `/api/platforms/status` | Get platform connection status |
| WS | `/ws` | Real-time event stream |
