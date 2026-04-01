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
    type: str  # "token" | "thinking" | "tool_call" | "tool_result" | "agent_plan" | "agent_token" | "agent_result" | "done" | "error"
    content: str = ""
    data: dict = {}


# --- Streaming ---

async def stream_chat(message: str, thread_id: str) -> AsyncGenerator[str, None]:
    """Stream agent responses as SSE events.

    Uses LangGraph's astream with messages stream_mode to get real-time
    token-by-token output, tool calls, and sub-agent events.

    Event types:
        - token: Final reply token from orchestrator
        - thinking: Extended-thinking / think_tool content
        - tool_call: Tool invocation dispatched
        - tool_result: Tool execution result
        - agent_plan: Sub-agent dispatch (with name + description)
        - agent_token: Token from a sub-agent's output stream
        - agent_result: Sub-agent completed, returns final answer
        - done: Response complete
        - error: Error occurred

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
        logger.info("━━━ stream_chat START ━━━ thread=%s message=%.200s", thread_id, message)

        # State to track subgraph depth for agent lifecycle detection
        prev_ns_depth = 0
        task_id_to_name: dict[str, str] = {}  # task_id → subagent_type mapping

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
            current_depth = len(ns)

            logger.debug(
                "chunk: type=%s ns=%s depth=%s→%s",
                chunk_type, ns, prev_ns_depth, current_depth,
            )

            if chunk_type == "messages":
                # Token-level streaming from LLM
                msg_chunk, metadata = data
                if not msg_chunk.content:
                    continue

                node = metadata.get("langgraph_node", "")
                is_subagent = bool(ns)

                # Build a meaningful source label
                if is_subagent:
                    # Try to resolve sub-agent name from ns task_id
                    # ns elements look like "tools:uuid" or "agent:uuid"
                    parts = ns[0].split(":", 1)
                    tid = parts[1] if len(parts) > 1 else ns[0]
                    source = task_id_to_name.get(tid, f"subagent:{tid}")
                else:
                    source = "orchestrator"

                # Decide the event type: subagent tokens become "agent_token"
                # (streamed content for the sub-agent's output panel).
                evt_type = "agent_token" if is_subagent else "token"

                # msg_chunk.content may be a string (normal token) or a
                # list of content blocks (Claude extended thinking, DeepSeek
                # reasoning_content, etc.).  Walk through the blocks and
                # emit appropriate events.
                content = msg_chunk.content
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        block_type = block.get("type", "")
                        if block_type == "thinking":
                            text = block.get("thinking", "")
                            if text:
                                logger.debug("→ thinking event: source=%s len=%d", source, len(text))
                                yield _sse_event(
                                    "thinking", text, {"source": source, "node": node}
                                )
                        elif block_type == "text":
                            text = block.get("text", "")
                            if text:
                                logger.debug("→ %s event: source=%s len=%d", evt_type, source, len(text))
                                yield _sse_event(
                                    evt_type, text, {"source": source, "node": node}
                                )
                        # Fallback: any block with a recognizable text key
                        elif "thinking" in block:
                            text = block["thinking"]
                            if isinstance(text, str) and text:
                                yield _sse_event(
                                    "thinking", text, {"source": source, "node": node}
                                )
                        elif "text" in block:
                            text = block["text"]
                            if isinstance(text, str) and text:
                                yield _sse_event(
                                    evt_type, text, {"source": source, "node": node}
                                )
                elif isinstance(content, str) and content:
                    yield _sse_event(evt_type, content, {"source": source, "node": node})

            elif chunk_type == "updates":
                # Node-level updates (includes tool calls, sub-agent dispatch)
                for node_name, update in data.items():
                    if not isinstance(update, dict):
                        continue
                    messages = update.get("messages", [])
                    logger.debug("  update node=%s messages_count=%s", node_name, len(messages) if isinstance(messages, list) else type(messages).__name__)
                    # Unwrap LangGraph Overwrite / Send wrappers if present
                    if not isinstance(messages, list):
                        try:
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
                            logger.info("  ← tool_result: %s content_len=%d", tool_name, len(content))
                            if tool_name == "think_tool":
                                yield _sse_event("thinking", content, {"source": "think_tool", "node": tool_name})
                            else:
                                yield _sse_event("tool_result", content, {"tool": tool_name})

                        elif msg_type == "AIMessage" and hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tc_name = tc.get("name", "")
                                logger.info("  → tool_call: %s ns=%s", tc_name, ns)
                                if tc_name == "think_tool":
                                    args = tc.get("args", {})
                                    reflection = args.get("reflection", "")
                                    if isinstance(reflection, dict):
                                        parts = []
                                        for k, v in reflection.items():
                                            parts.append(f"{k}: {v}")
                                        reflection = "\n".join(parts)
                                    yield _sse_event(
                                        "thinking",
                                        str(reflection)[:1000] if reflection else "Reasoning...",
                                        {"source": "think_tool", "node": tc_name},
                                    )
                                elif tc_name == "task":
                                    # Sub-agent dispatch — extract name & description
                                    args = tc.get("args", {})
                                    subagent_type = args.get("subagent_type", "unknown")
                                    description = args.get("description", "")
                                    logger.info("  ★ agent_plan: %s desc=%.100s", subagent_type, description)
                                    # Get the task_id from ns for name mapping
                                    parts = ns[0].split(":", 1) if ns else []
                                    tid = parts[1] if len(parts) > 1 else ""
                                    if tid:
                                        task_id_to_name[tid] = subagent_type
                                    yield _sse_event("agent_plan", description, {
                                        "name": subagent_type,
                                        "description": description,
                                        "args": json.dumps(args, ensure_ascii=False)[:300],
                                    })
                                else:
                                    yield _sse_event("tool_call", "", {
                                        "tool": tc_name,
                                        "args": json.dumps(tc.get("args", {}), ensure_ascii=False)[:200],
                                    })

            # Detect sub-agent lifecycle transitions via ns depth
            if current_depth == 0 and prev_ns_depth > 0:
                # Exited a sub-agent — emit agent_result
                # Try to find the agent name from the previous ns
                if prev_ns_depth > 0 and ns == ():
                    # The last message token from the sub-agent was already
                    # sent as agent_token events. Send a completion marker.
                    # We can't easily get the name here, so look at most recent
                    # task_id_to_name entry.
                    last_agent = next(reversed(task_id_to_name.values()), "unknown")
                    logger.info("  ★ agent_result: %s", last_agent)
                    yield _sse_event("agent_result", "", {"name": last_agent})

            prev_ns_depth = current_depth

            # Send heartbeat to keep connection alive
            yield ": heartbeat\n\n"

        logger.info("━━━ stream_chat END ━━━ thread=%s", thread_id)
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
    import os

    load_dotenv()

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
