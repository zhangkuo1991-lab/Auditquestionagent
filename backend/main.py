"""
AuditIQ Backend — FastAPI Multi-Agent Server with RAG
=====================================================
Endpoints:
  POST /api/chat            — Chat (Manager + Audit Standards Agent + RAG)
  POST /api/ingest          — Upload & index a standards PDF
  GET  /api/ingest/status   — Check knowledge base status
  GET  /api/health          — Health check
  GET  /api/agents          — List available agents

Multi-agent flow:
  User message → Manager Agent → RAG Retriever → Audit Standards Agent
               → Manager synthesises → response + sources returned to frontend
"""

import os
import shutil
import tempfile
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import anthropic
from dotenv import load_dotenv

from agents.manager_agent import get_system_prompt as manager_prompt, get_tools
from agents.audit_standards_agent import get_system_prompt as audit_prompt
from rag.retriever import retriever

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="AuditIQ API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Load RAG index on startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup():
    loaded = retriever.try_load()
    if loaded:
        status = retriever.get_status()
        print(f"[Startup] RAG ready — {status['chunk_count']} chunks from '{status['source']}'")
    else:
        print("[Startup] No RAG index found. Upload a PDF at POST /api/ingest.")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []

class AgentLogEntry(BaseModel):
    agent: str
    action: str

class Source(BaseModel):
    section: str
    title: str
    pages: List[int]
    score: float

class ChatResponse(BaseModel):
    response: str
    agent_logs: List[AgentLogEntry]
    agents_used: List[str]
    sources: List[Source] = []
    rag_used: bool = False

# ---------------------------------------------------------------------------
# Specialist agent callers
# ---------------------------------------------------------------------------

def call_audit_standards_agent(question: str, rag_context: str = "") -> str:
    """Call the Audit Standards agent, optionally with RAG context."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    if rag_context:
        user_message = (
            f"{rag_context}\n\n"
            f"---\n"
            f"QUESTION: {question}\n\n"
            f"Answer based primarily on the retrieved context above. "
            f"Cite specific AU-C section numbers and paragraph references where possible."
        )
    else:
        user_message = question

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=audit_prompt(),
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Core multi-agent orchestration
# ---------------------------------------------------------------------------

def process_message(message: str, history: List[Message]) -> ChatResponse:
    """
    Multi-agent + RAG pipeline:
      1. Manager Agent receives question
      2. Manager routes via tool call
      3. RAG Retriever fetches relevant AU-C chunks
      4. Audit Standards Agent answers with retrieved context
      5. Manager synthesises final response
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    agent_logs: List[AgentLogEntry] = []
    agents_used: List[str] = ["Manager Agent"]
    all_sources: List[Dict] = []
    rag_used = False

    messages = [{"role": h.role, "content": h.content} for h in history]
    messages.append({"role": "user", "content": message})

    agent_logs.append(AgentLogEntry(agent="Manager Agent", action="Received question, deciding routing..."))

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=manager_prompt(),
        tools=get_tools(),
        messages=messages
    )

    max_iterations = 5
    iteration = 0

    while response.stop_reason == "tool_use" and iteration < max_iterations:
        iteration += 1
        tool_uses    = [b for b in response.content if b.type == "tool_use"]
        tool_results = []

        for tool_use in tool_uses:
            tool_name  = tool_use.name
            tool_input = tool_use.input

            agent_logs.append(AgentLogEntry(
                agent="Manager Agent",
                action=f"Routing to → {tool_name}"
            ))

            if tool_name == "ask_audit_standards_agent":
                sub_question = tool_input.get("question", message)

                # ── RAG retrieval ──────────────────────────────────────────
                rag_context = ""
                if retriever.is_ready:
                    agent_logs.append(AgentLogEntry(
                        agent="RAG Retriever",
                        action=f"Searching AICPA AU-C Standards for: \"{sub_question[:70]}...\""
                    ))
                    results = retriever.retrieve(sub_question, top_k=5)
                    if results:
                        rag_context = retriever.format_context(results)
                        all_sources.extend(retriever.sources_for_response(results))
                        rag_used = True
                        agent_logs.append(AgentLogEntry(
                            agent="RAG Retriever",
                            action=f"Retrieved {len(results)} relevant chunks ✓"
                        ))
                    else:
                        agent_logs.append(AgentLogEntry(
                            agent="RAG Retriever",
                            action="No strong matches — falling back to built-in knowledge"
                        ))

                # ── Call specialist ────────────────────────────────────────
                if "Audit Standards Agent" not in agents_used:
                    agents_used.append("Audit Standards Agent")

                label = "[with RAG context ✓]" if rag_context else "[knowledge-based]"
                agent_logs.append(AgentLogEntry(
                    agent="Audit Standards Agent",
                    action=f"Answering {label}: \"{sub_question[:70]}...\""
                ))

                specialist_text = call_audit_standards_agent(sub_question, rag_context)

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tool_use.id,
                    "content":     specialist_text,
                })
            else:
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tool_use.id,
                    "content":     f"Tool '{tool_name}' is not available.",
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user",      "content": tool_results})

        agent_logs.append(AgentLogEntry(
            agent="Manager Agent",
            action="Synthesising final response..."
        ))

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=manager_prompt(),
            tools=get_tools(),
            messages=messages
        )

    final_text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    ) or "Unable to generate a response. Please try again."

    agent_logs.append(AgentLogEntry(agent="Manager Agent", action="Response ready ✓"))

    # Deduplicate sources by section
    seen, unique_sources = set(), []
    for s in all_sources:
        if s["section"] not in seen:
            seen.add(s["section"])
            unique_sources.append(s)

    return ChatResponse(
        response=final_text,
        agent_logs=agent_logs,
        agents_used=agents_used,
        sources=[Source(**s) for s in unique_sources],
        rag_used=rag_used,
    )

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0", "rag_ready": retriever.is_ready}


@app.get("/api/agents")
def list_agents():
    return {
        "agents": [
            {"name": "Manager Agent",        "role": "Routes questions and synthesises responses.", "model": "claude-sonnet-4-6"},
            {"name": "Audit Standards Agent", "role": "GAAS / AU-C answers grounded in indexed PDF.", "model": "claude-sonnet-4-6", "rag": retriever.is_ready},
            {"name": "RAG Retriever",         "role": "BM25 search over AICPA AU-C Standards PDF.", "ready": retriever.is_ready},
        ]
    }


@app.get("/api/ingest/status")
def ingest_status():
    status = retriever.get_status()
    status["rag_ready"] = retriever.is_ready
    return status


@app.post("/api/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and index an AICPA AU-C Standards PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    tmp_path = tempfile.mktemp(suffix=".pdf")
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        # Save a persistent copy
        standards_dir = os.path.join(os.path.dirname(__file__), "data", "standards")
        os.makedirs(standards_dir, exist_ok=True)
        shutil.copy(tmp_path, os.path.join(standards_dir, file.filename))

        status = retriever.ingest(tmp_path, source_name=file.filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return {
        "message":     f"Indexed {status['chunk_count']} chunks from '{status['source']}'",
        "chunk_count": status["chunk_count"],
        "source":      status["source"],
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set.")
    try:
        return process_message(request.message, request.history or [])
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=503, detail="Cannot connect to Anthropic API.")
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
