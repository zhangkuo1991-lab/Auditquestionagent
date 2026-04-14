# AuditIQ — AI Audit Knowledge Assistant

A full-stack app with a **React** frontend and **FastAPI** backend, powered by a
multi-agent system using the **Anthropic Claude API** and a **RAG pipeline** grounded
in the official AICPA U.S. Auditing Standards — AU-C (2025).

---

## Architecture

```
User (Browser)
    │
    ▼
React Frontend (Vite · port 5173)
    │  POST /api/chat
    ▼
FastAPI Backend (Uvicorn · port 8000)
    │
    ▼
Manager Agent  ──────────────────────────────────────
    │  (claude-sonnet-4-6)                          │
    │  Decides routing via tool calls               │
    ▼                                               │
Audit Standards Agent                    [Future agents]
    │  (claude-sonnet-4-6)               e.g. Engagement Planning
    │  GAAS · AU-C 200–935 · SAS updates           │
    ▼                                               │
Manager synthesises → Response to user ◄───────────
```

---

## Architecture

```
User (Browser)
    │
    ▼
React Frontend (Vite · port 5173)
    │  POST /api/chat  |  POST /api/ingest
    ▼
FastAPI Backend (Uvicorn · port 8000)
    │
    ├── Manager Agent  (claude-sonnet-4-6)
    │       │ Routes via tool calls
    │       ▼
    ├── RAG Retriever  (BM25 · pure Python)
    │       │ Fetches top-5 relevant AU-C chunks
    │       ▼
    └── Audit Standards Agent  (claude-sonnet-4-6)
            │ Answers grounded in retrieved context
            ▼
        Response + Source citations → User
```

---

## Quick Start

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- An **Anthropic API key** (get one at https://console.anthropic.com)

---

### 2. Backend setup + RAG ingestion

```bash
cd audit-app/backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Load the .env and start the server
export $(cat .env | xargs)        # Mac/Linux
# Windows CMD:
#   set ANTHROPIC_API_KEY=your_key_here
# Windows PowerShell:
#   $env:ANTHROPIC_API_KEY="your_key_here"
# If you use a .env file, the backend now loads it automatically.

uvicorn main:app --reload --port 8000
```

The API will be running at: http://localhost:8000

**Index the PDF (run once before first use):**

The AICPA AU-C Standards PDF is already placed at `backend/data/standards/ps-au-c-sections.pdf`.
Run the ingestion script to build the BM25 index (takes ~3–5 minutes for 2046 pages):

```bash
cd audit-app/backend
python scripts/ingest.py
```

You will see progress output like:
```
📄 Ingesting: .../ps-au-c-sections.pdf
[PDF] Extracted 2046 pages.
[PDF] Created 4,200+ chunks.
[BM25] Index built. Vocabulary size: 45,000+
✅ Ingestion complete! 4,218 chunks indexed.
```

After that, every server start will auto-load the index from `backend/data/bm25_index.json`.

Alternatively, upload any PDF directly from the app's sidebar (POST /api/ingest).
API docs (auto-generated): http://localhost:8000/docs

---

### 3. Frontend setup

```bash
cd audit-app/frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The app will be running at: http://localhost:5173

---

## Project Structure

```
audit-app/
├── backend/
│   ├── main.py                        # FastAPI app + multi-agent orchestration
│   ├── agents/
│   │   ├── manager_agent.py           # Manager Agent prompt + tool definitions
│   │   └── audit_standards_agent.py  # Audit Standards Agent prompt (GAAS/AU-C)
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── src/
    │   ├── App.jsx                    # Main layout + sidebar
    │   ├── App.css
    │   ├── components/
    │   │   ├── ChatWindow.jsx         # Scrolling message list
    │   │   ├── MessageBubble.jsx      # Individual message + agent log
    │   │   └── InputBar.jsx           # Text input + quick suggestions
    │   └── index.css
    ├── index.html
    ├── package.json
    └── vite.config.js                 # Proxies /api → localhost:8000
```

---

## Adding a New Specialist Agent

1. Create `backend/agents/your_agent.py` with a `get_system_prompt()` function.
2. Add a new tool entry in `backend/agents/manager_agent.py` → `MANAGER_TOOLS`.
3. Handle the new tool name in the `process_message()` loop in `backend/main.py`.
4. The Manager Agent will automatically route questions to your new agent.

---

## API Endpoints

| Method | Path          | Description                          |
|--------|---------------|--------------------------------------|
| GET    | /api/health   | Health check                         |
| GET    | /api/agents   | Lists all available agents           |
| POST   | /api/chat     | Send a message, get agent response   |

### POST /api/chat — Request body
```json
{
  "message": "What does AU-C 315 require?",
  "history": [
    { "role": "user",      "content": "previous question" },
    { "role": "assistant", "content": "previous answer"   }
  ]
}
```

### POST /api/chat — Response
```json
{
  "response":    "...",
  "agents_used": ["Manager Agent", "Audit Standards Agent"],
  "agent_logs":  [
    { "agent": "Manager Agent",         "action": "Routing to → ask_audit_standards_agent" },
    { "agent": "Audit Standards Agent", "action": "Processing: ..." },
    { "agent": "Manager Agent",         "action": "Response ready ✓" }
  ]
}
```
