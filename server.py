"""SSE streaming server for the agent system.

Provides a FastAPI-based server with Server-Sent Events (SSE) streaming
for real-time chat interactions with the agent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Module-level agent reference, set during startup
_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create agent on startup."""
    from dotenv import load_dotenv

    load_dotenv()

    # Import and create agent
    from agent import _build_registry
    from agents.config import AgentConfig
    from agents.orchestrator import create_orchestrator

    config = AgentConfig()
    registry = _build_registry()
    global _agent
    _agent = create_orchestrator(config=config, registry=registry)

    logger.info("Agent initialized successfully")
    yield
    logger.info("Server shutting down")


app = FastAPI(
    title="Agent Chat",
    description="Multi-agent system with SSE streaming",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class ChatRequest(BaseModel):
    """Chat message request."""
    message: str
    thread_id: str | None = None


class ChatState(BaseModel):
    """SSE event payload."""
    type: str  # "token" | "tool_call" | "tool_result" | "subagent" | "done" | "error"
    content: str = ""
    data: dict = {}


# --- Streaming ---

async def stream_chat(message: str, thread_id: str) -> AsyncGenerator[str, None]:
    """Stream agent responses as SSE events.

    Uses LangGraph's astream with messages stream_mode to get real-time
    token-by-token output, tool calls, and sub-agent events.

    Args:
        message: The user's message.
        thread_id: Conversation thread ID for state persistence.

    Yields:
        SSE-formatted event strings.
    """
    if _agent is None:
        yield _sse_event("error", "Agent not initialized")
        return

    try:
        config = {"configurable": {"thread_id": thread_id}}

        # Use LangGraph v2 streaming with multiple modes
        async for chunk in _agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
            version="v2",
        ):
            chunk_type = chunk.get("type", "")
            ns = chunk.get("ns", ())  # namespace for subgraph identification
            data = chunk.get("data")

            if chunk_type == "messages":
                # Token-level streaming from LLM
                msg_chunk, metadata = data
                if msg_chunk.content:
                    # Determine source (orchestrator or subagent)
                    source = "orchestrator"
                    node = metadata.get("langgraph_node", "")
                    if ns:
                        # This is from a sub-agent graph
                        source = f"subagent:{ns[0]}" if ns else "subagent"
                    yield _sse_event("token", msg_chunk.content, {"source": source, "node": node})

            elif chunk_type == "updates":
                # Node-level updates (includes tool calls, sub-agent dispatch)
                for node_name, update in data.items():
                    if not isinstance(update, dict):
                        continue
                    messages = update.get("messages", [])
                    # Unwrap LangGraph Overwrite / Send wrappers if present
                    if not isinstance(messages, list):
                        # Could be a single Message, Overwrite, Send, etc.
                        try:
                            # Overwrite objects may have a .values or .content attribute
                            if hasattr(messages, "values"):
                                messages = messages.values
                            elif hasattr(messages, "content"):
                                messages = [messages]
                            else:
                                messages = list(messages)
                        except (TypeError, AttributeError):
                            continue
                    for msg in messages:
                        msg_type = getattr(msg, "type", None)

                        if msg_type == "tool":
                            # Tool execution result
                            tool_name = getattr(msg, "name", "unknown")
                            content = str(getattr(msg, "content", ""))[:500]
                            yield _sse_event("tool_result", content, {"tool": tool_name})

                        elif msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
                            # Tool call dispatch
                            for tc in msg.tool_calls:
                                yield _sse_event("tool_call", "", {
                                    "tool": tc.get("name", ""),
                                    "args": json.dumps(tc.get("args", {}), ensure_ascii=False)[:200],
                                })

            # Send heartbeat to keep connection alive
            yield ": heartbeat\n\n"

        yield _sse_event("done", "Response complete")

    except Exception as e:
        logger.exception("Error during streaming")
        yield _sse_event("error", str(e))


def _sse_event(event_type: str, content: str = "", data: dict | None = None) -> str:
    """Format an SSE event string."""
    payload = ChatState(type=event_type, content=content, data=data or {})
    return f"event: {event_type}\ndata: {payload.model_dump_json()}\n\n"


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def chat_page():
    """Serve the chat UI."""
    html_path = Path(__file__).parent / "static" / "chat.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Agent Chat</h1><p>chat.html not found. Run: python -m server</p>")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Stream chat responses via SSE."""
    thread_id = request.thread_id or str(uuid.uuid4())
    return StreamingResponse(
        stream_chat(request.message, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "agent_ready": _agent is not None}


@app.get("/api/config")
async def get_config():
    """Return agent configuration info (safe subset)."""
    from agents.config import AgentConfig
    cfg = AgentConfig()
    return {
        "primary_model": cfg.primary_model,
        "subagent_model": cfg.subagent_model,
        "routing_strategy": cfg.routing_strategy,
    }


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
