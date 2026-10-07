# MARIA — Architecture Document

This document describes the high-level architecture of MARIA and how its components communicate.

---

## Design Philosophy

1. **Modular** — Every major capability is a separate module with clean interfaces.
2. **Provider-independent** — The AI layer abstracts away specific providers.
3. **Tool-based** — Agent capabilities are expressed as tools with declared permissions.
4. **Security-first** — All sensitive actions require explicit human approval.
5. **Replaceable** — Any component can be swapped without rewriting the system.

---

## System Overview

```
                        ┌──────────────────┐
                        │     Clients      │
                        │  Web │ Android │  │
                        │  CLI │   API   │  │
                        └────────┬─────────┘
                                 │
                                 ▼
                   ┌─────────────────────────┐
                   │    API Gateway Layer     │
                   │       (FastAPI)          │
                   │  REST + WebSocket + Auth │
                   └────────────┬────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
     ┌─────────────┐   ┌──────────────┐   ┌────────────┐
     │  Agent Core │   │   Provider   │   │    Tool    │
     │             │   │    Router    │   │  Registry  │
     │ • Agent loop│   │              │   │            │
     │ • Planning  │   │ • Selection  │   │ • Discovery│
     │ • History   │   │ • Fallback   │   │ • Execution│
     │ • Context   │   │ • Load bal.  │   │ • Permissions│
     └──────┬──────┘   └──────┬───────┘   └─────┬──────┘
            │                 │                 │
     ┌──────▼──────┐   ┌──────▼───────┐   ┌─────▼──────────┐
     │   Memory    │   │  AI Provider │   │   Tools        │
     │   System    │   │  Adapters    │   │                │
     │             │   │              │   │ • FileSystem   │
     │ • SQLite    │   │ • Gemini     │   │ • Terminal     │
     │ • Vector DB │   │ • OpenAI     │   │ • Browser      │
     │ • Sessions  │   │ • Claude     │   │ • Git          │
     │             │   │ • OpenRouter │   │ • System       │
     │             │   │ • Ollama     │   │ • IDE          │
     └─────────────┘   └──────────────┘   │ • Web Research │
                                          └────────────────┘
            │                                     │
     ┌──────▼─────────────────────────────────────▼──┐
     │              Security Layer                    │
     │                                                │
     │  • Credential Vault (encrypted storage)        │
     │  • Permission Engine (per-tool, per-action)    │
     │  • Human Confirmation Gateway                  │
     │  • Audit Log                                   │
     └────────────────────────────────────────────────┘
```

---

## Component Details

### 1. API Gateway (`maria.api`)

| Aspect | Detail |
|--------|--------|
| Framework | FastAPI |
| Protocols | HTTP REST, WebSocket |
| Auth | Token-based (local), optional for single-user |
| Responsibilities | Request routing, session management, input validation |

The gateway is the single entry point for all clients. It exposes:
- `POST /api/chat` — Send a message, receive a response.
- `WS /api/chat/stream` — Real-time streaming conversation.
- `GET /api/health` — Health check.
- `GET /api/config` — Non-sensitive configuration.

### 2. Agent Core (`maria.agent`)

The agent implements a **think → plan → act → respond** loop:

1. **Receive** user message + conversation history.
2. **Send** to AI provider with available tool descriptions.
3. **Parse** the AI response for tool calls.
4. **Check permissions** for each requested tool call.
5. **Request human confirmation** if the action is sensitive.
6. **Execute** approved tool calls.
7. **Return** results to the AI for final response generation.
8. **Respond** to the user.

### 3. Provider Router (`maria.providers`)

Abstracts AI providers behind a common interface:

```python
class AIProvider(Protocol):
    async def complete(self, messages: list[Message], tools: list[Tool] | None = None) -> AIResponse: ...
    async def stream(self, messages: list[Message], tools: list[Tool] | None = None) -> AsyncIterator[AIChunk]: ...
    def supports_tools(self) -> bool: ...
    def supports_vision(self) -> bool: ...
    def model_info(self) -> ModelInfo: ...
```

The router selects the best provider/model based on:
- Task requirements (vision, tool use, language).
- User preference.
- Provider availability and cost.
- Fallback chains.

### 4. Tool Registry (`maria.tools`)

Tools are self-describing and declare their permissions:

```python
class Tool(ABC):
    name: str
    description: str
    parameters: dict              # JSON Schema
    required_permissions: list[Permission]
    risk_level: RiskLevel         # LOW, MEDIUM, HIGH, CRITICAL

    async def execute(self, params: dict, context: ToolContext) -> ToolResult: ...
```

| Risk Level | Behavior |
|------------|----------|
| LOW | Auto-approved (e.g., read a file listing) |
| MEDIUM | Logged, may auto-approve based on policy |
| HIGH | Requires human confirmation |
| CRITICAL | Always requires human confirmation + reason |

### 5. Memory System (`maria.memory`)

- **Short-term:** In-memory conversation buffer (current session).
- **Medium-term:** SQLite-backed conversation history.
- **Long-term:** Vector embeddings for semantic search across past conversations.

### 6. Security Layer (`maria.security`)

- **Credential Vault:** Encrypted storage for API keys. Never in source code. BYOK model.
- **Permission Engine:** Tools declare required permissions. The engine checks grants.
- **Human Confirmation:** Interactive approval for HIGH/CRITICAL actions.
- **Audit Log:** All tool executions and permission decisions are logged.

See [SECURITY.md](SECURITY.md) for full details.

---

## Communication Patterns

### Client ↔ Server

- **Synchronous:** REST API for simple request/response.
- **Streaming:** WebSocket for real-time chat with token-by-token streaming.
- **Remote:** Encrypted WebSocket between Android client and PC server (future).

### Internal

- Components communicate through **Python async function calls** — no message bus needed at this scale.
- The agent core orchestrates all interactions.
- Dependency injection via Pydantic settings and factory functions.

---

## Data Flow: Chat Message

```
User types message
       │
       ▼
  API Gateway validates input
       │
       ▼
  Agent Core receives message
       │
       ▼
  Agent loads conversation history from Memory
       │
       ▼
  Agent sends (history + message + tools) to Provider Router
       │
       ▼
  Provider Router selects AI provider and sends request
       │
       ▼
  AI responds (text and/or tool calls)
       │
       ├── If tool calls:
       │     │
       │     ▼
       │   Permission Engine checks each tool call
       │     │
       │     ├── Approved → Tool executes → Result sent back to AI
       │     └── Denied → User informed
       │
       ▼
  Final response returned to user
       │
       ▼
  Conversation saved to Memory
```

---

## Directory Structure

```
maria/
├── maria/                   # Main Python package
│   ├── __init__.py
│   ├── __main__.py          # Entry point: python -m maria
│   ├── config.py            # Pydantic settings
│   ├── agent/               # Agent core
│   │   ├── __init__.py
│   │   ├── core.py          # Agent loop
│   │   └── context.py       # Conversation context
│   ├── providers/           # AI provider adapters
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract provider interface
│   │   ├── router.py        # Model routing logic
│   │   ├── gemini.py
│   │   ├── openai.py
│   │   ├── claude.py
│   │   ├── openrouter.py
│   │   └── ollama.py
│   ├── tools/               # Tool implementations
│   │   ├── __init__.py
│   │   ├── base.py          # Abstract tool class
│   │   ├── registry.py      # Tool discovery and registration
│   │   ├── filesystem.py
│   │   ├── terminal.py
│   │   ├── browser.py
│   │   ├── git.py
│   │   └── system.py
│   ├── memory/              # Memory and persistence
│   │   ├── __init__.py
│   │   ├── store.py         # SQLite conversation store
│   │   └── vector.py        # Vector memory (future)
│   ├── security/            # Security subsystem
│   │   ├── __init__.py
│   │   ├── credentials.py   # Encrypted credential storage
│   │   ├── permissions.py   # Permission engine
│   │   ├── confirmation.py  # Human-in-the-loop
│   │   └── audit.py         # Audit logging
│   └── api/                 # FastAPI server
│       ├── __init__.py
│       ├── server.py        # FastAPI app
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── chat.py
│       │   └── health.py
│       └── websocket.py     # WebSocket handler
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_agent/
│   ├── test_providers/
│   ├── test_tools/
│   ├── test_memory/
│   └── test_security/
├── docs/                    # Additional documentation
├── scripts/                 # Utility scripts
├── .env.example             # Environment variable template
├── .gitignore
├── pyproject.toml           # Project metadata and dependencies
├── requirements.txt         # Pinned dependencies
├── README.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── SECURITY.md
└── LICENSE
```

---

## Future Architecture Considerations

- **Plugin system:** Third-party tools loaded at runtime.
- **Multi-agent:** Specialized sub-agents for coding, research, etc.
- **Distributed:** PC and Android as separate nodes in a mesh.
- **Offline-first:** Local models (Ollama) for privacy-sensitive tasks.

---

*This document will evolve as MARIA grows. Each phase may introduce architectural refinements.*
