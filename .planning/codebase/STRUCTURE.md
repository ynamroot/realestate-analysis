# Codebase Structure

**Analysis Date:** 2025-03-17

## Directory Layout

```
A2A-MCP-RealEstate/
├── app/                           # Main Python application
│   ├── agent/                     # Core agent implementations
│   │   ├── __init__.py
│   │   ├── a2a_agent.py          # Base A2A agent class
│   │   ├── intelligent_agent.py  # AI-enhanced agent
│   │   ├── agent_registry.py     # Agent registry management
│   │   ├── agent_discovery.py    # Agent discovery service
│   │   ├── character_agents.py   # Character-based agents
│   │   ├── llm_character_agents.py # LLM-powered character agents
│   │   ├── real_estate_agent.py  # Real estate evaluation agents
│   │   ├── external_agent_adapter.py # External agent integration
│   │   ├── smart_agent_router.py # Intelligent agent routing
│   │   ├── collaboration.py      # Multi-agent collaboration
│   │   ├── multi_agent_conversation.py # Conversation management
│   │   ├── json_rpc.py           # JSON-RPC 2.0 implementation
│   │   └── streaming.py          # SSE streaming support
│   │
│   ├── mcp/                       # Model-Centric Protocol integration
│   │   ├── __init__.py
│   │   ├── fastmcp_realestate.py # Real estate MCP server
│   │   ├── location_service.py   # Location analysis MCP
│   │   ├── real_estate_mcp.py    # Real estate tools
│   │   ├── real_estate_recommendation_mcp.py # Recommendation engine
│   │   ├── real_estate_server.py # MCP server setup
│   │   └── fastmcp_example.py    # Example MCP usage
│   │
│   ├── routes/                    # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── agent_routes.py       # Agent communication endpoints
│   │   ├── agent_registry_routes.py # Registry management endpoints
│   │   ├── character_routes.py   # Character agent endpoints
│   │   ├── collaboration_routes.py # Collaboration endpoints
│   │   ├── conversation_routes.py # Conversation management endpoints
│   │   ├── smart_chat_routes.py  # Smart chat/analysis endpoints
│   │   ├── data_routes.py        # Sample data endpoints
│   │   ├── ai_routes.py          # AI service endpoints
│   │   ├── mcp_routes.py         # MCP integration endpoints
│   │   ├── web_routes.py         # Web UI routes
│   │   └── review_routes.py      # Property review endpoints
│   │
│   ├── ai/                        # AI service integration
│   │   ├── __init__.py
│   │   └── gemini_service.py     # Google Gemini API client
│   │
│   ├── data/                      # Sample data and configuration
│   │   ├── __init__.py
│   │   ├── sample_data.py        # Sample data generators
│   │   ├── region_codes.py       # Korean region/location codes
│   │   └── agent_registry.json   # Agent registry file (persisted)
│   │
│   ├── utils/                     # Utility modules
│   │   ├── __init__.py
│   │   ├── config.py             # Configuration management
│   │   ├── logger.py             # Logging setup
│   │   ├── fastmcp_client.py     # FastMCP client wrapper
│   │   ├── mcp_client.py         # MCP client implementation
│   │   ├── proper_mcp_client.py  # Alternative MCP client
│   │   └── true_mcp_client.py    # True MCP client implementation
│   │
│   ├── templates/                 # HTML UI templates
│   │   ├── base.html             # Base template
│   │   ├── index.html            # Home page
│   │   ├── chat.html             # Chat interface
│   │   ├── agent_chat.html       # Agent-specific chat
│   │   ├── agent_test.html       # Agent testing UI
│   │   ├── agent_result.html     # Agent results display
│   │   ├── compare.html          # Agent comparison view
│   │   ├── map_view.html         # Map visualization
│   │   ├── mcp_test.html         # MCP testing interface
│   │   ├── mcp_result.html       # MCP results display
│   │   └── error.html            # Error page
│   │
│   └── main.py                    # FastAPI application entry point
│
├── src/                           # Node.js/Alternative implementation (minimal)
│   ├── index.js                   # Entry point
│   ├── agent/                     # Agent directory
│   ├── data/                      # Data directory
│   ├── routes/                    # Routes directory
│   └── utils/                     # Utils directory
│
├── tests/                         # Test files
├── docs/                          # Documentation
├── examples/                      # Example scripts
├── scripts/                       # Utility scripts
│
├── pyproject.toml                 # Python project metadata
├── requirements.txt               # Python dependencies
├── CLAUDE.md                      # Developer guidance
├── .env                           # Environment variables (not committed)
└── .planning/codebase/           # Generated analysis documents
    ├── ARCHITECTURE.md
    └── STRUCTURE.md
```

## Directory Purposes

**app/agent/:**
- Purpose: Core multi-agent communication framework with A2A protocol
- Contains: Base agent class, specialized agents, adapters, registry, discovery
- Key files: `a2a_agent.py` (foundation), `external_agent_adapter.py` (integration)

**app/mcp/:**
- Purpose: Real estate domain-specific Model-Centric Protocol implementation
- Contains: FastMCP servers, location analysis, recommendation engine
- Key files: `fastmcp_realestate.py` (server setup), `location_service.py` (location MCP)

**app/routes/:**
- Purpose: HTTP endpoint definitions for all system features
- Contains: FastAPI route handlers with Pydantic request/response models
- Key files: `agent_routes.py` (core communication), `smart_chat_routes.py` (analysis)

**app/ai/:**
- Purpose: External AI service integration (Google Gemini)
- Contains: API client wrapper, request/response handling
- Key files: `gemini_service.py` (service wrapper)

**app/data/:**
- Purpose: Domain-specific data, samples, and lookup tables
- Contains: Sample data generators, region codes, persistent registry
- Key files: `sample_data.py` (generators), `agent_registry.json` (persisted agents)

**app/utils/:**
- Purpose: Cross-cutting infrastructure and helper utilities
- Contains: Configuration, logging, MCP client wrappers
- Key files: `config.py` (Pydantic settings), `logger.py` (loguru setup)

**app/templates/:**
- Purpose: HTML user interfaces for testing and interaction
- Contains: Jinja2 templates for web UI
- Key files: `agent_chat.html` (chat UI), `agent_test.html` (testing tools)

## Key File Locations

**Entry Points:**
- `app/main.py`: FastAPI application initialization, route registration, lifespan handler
- `app/routes/agent_routes.py`: `/api/agent/message` endpoint (core agent communication)
- `app/routes/smart_chat_routes.py`: `/api/smart-chat/analyze-property` endpoint (real estate analysis)
- `app/routes/web_routes.py`: `/web/*` endpoints (HTML UI serving)

**Configuration:**
- `app/utils/config.py`: Pydantic Settings for PORT, AGENT_ID, AGENT_NAME, ENVIRONMENT
- `.env`: Environment variables (PORT, AGENT_ID, LOG_LEVEL)
- `pyproject.toml`: Project metadata, dependencies, script definitions

**Core Logic:**
- `app/agent/a2a_agent.py`: AgentMessage model, connection management, message routing
- `app/agent/agent_registry.py`: RegistryAgent model, registry persistence (JSON)
- `app/agent/external_agent_adapter.py`: BaseAgentAdapter, SocraticWebAdapter, protocol handling
- `app/agent/intelligent_agent.py`: IntelligentA2AAgent, AI message optimization
- `app/agent/real_estate_agent.py`: RealEstateAgent base, investment/life quality scoring
- `app/agent/json_rpc.py`: JsonRpcProcessor, JsonRpcRequest/JsonRpcResponse models

**Testing:**
- `app/templates/agent_test.html`: Interactive agent testing UI
- `app/templates/mcp_test.html`: MCP endpoint testing interface
- `examples/`: Example scripts (if present, check for ai_workflow_demo.py, test_ai_endpoints.py)

## Naming Conventions

**Files:**
- `*_agent.py`: Agent implementations (e.g., `real_estate_agent.py`, `intelligent_agent.py`)
- `*_routes.py`: FastAPI route modules (e.g., `agent_routes.py`, `smart_chat_routes.py`)
- `*_service.py`: Service/client wrappers (e.g., `gemini_service.py`)
- `*_mcp.py`: MCP-related implementations (e.g., `real_estate_mcp.py`)

**Directories:**
- `agent/`: Agent implementations (lowercase plural not used; singular per component)
- `routes/`: All FastAPI route modules together
- `mcp/`: All MCP-related code
- `utils/`: Utilities and helpers (not organized by function, kept flat)

**Classes:**
- `*Agent`: Agents (e.g., `A2AAgent`, `RealEstateAgent`, `IntelligentA2AAgent`)
- `*Adapter`: External adapters (e.g., `SocraticWebAdapter`, `BaseAgentAdapter`)
- `*Manager`: Managers for collections (e.g., `StreamManager`)
- `*Processor`: Processors for data (e.g., `JsonRpcProcessor`)
- `*Request`/`*Response`: Pydantic models for validation (e.g., `HandshakeRequest`)

**Functions:**
- `async def`: All I/O operations are async
- `_private_methods()`: Methods prefixed with `_` are internal/private
- `get_*()`: Getter functions (e.g., `get_user_data()`)
- `handle_*()`: Message/request handlers (e.g., `_handle_ping()`)

## Where to Add New Code

**New Feature (Agent Domain):**
- Primary code: `app/agent/domain_agent.py` (extend A2AAgent or RealEstateAgent)
- Routes: `app/routes/domain_routes.py` (new route file if significant)
- Registry: Update `app/data/agent_registry.json` with agent metadata
- MCP tools: `app/mcp/domain_mcp.py` (if domain-specific tools needed)

**New HTTP Endpoint:**
- Add to existing route file in `app/routes/` (e.g., add to `agent_routes.py`)
- Define request model (Pydantic): `class NewRequest(BaseModel):`
- Implement handler: `@router.post("/path")\nasync def handler(request: NewRequest):`
- Register in `app/main.py`: `app.include_router(domain_routes.router, prefix="/api/domain")`

**New External Agent Integration:**
- Extend `BaseAgentAdapter` in `app/agent/external_agent_adapter.py`
- Implement `send_message()` and `get_agent_info()` methods
- Register protocol translation and fallback formats
- Use in `smart_agent_router.py` when target agent type detected

**New MCP Tool/Service:**
- Create new file: `app/mcp/new_service_mcp.py`
- Extend FastMCP server with `@server.tool()` decorated functions
- Implement request/response handling
- Add client wrapper in `app/utils/fastmcp_client.py`
- Expose via `app/routes/mcp_routes.py`

**Utilities/Helpers:**
- Add to `app/utils/` (keep flat, no subdirectories)
- Import in relevant modules or add to route handler file
- Document in docstring with purpose and usage example

**Web UI/Templates:**
- Add `.html` file to `app/templates/`
- Serve via route in `app/routes/web_routes.py` (use `templates.TemplateResponse`)
- Reference static assets (CSS/JS) from template with `/static/` path (if needed)

## Special Directories

**app/data/:**
- Purpose: Holds persisted configuration (agent_registry.json) and reference data
- Generated: `agent_registry.json` is generated/updated at runtime
- Committed: Yes (with initial seed data; updates via API)

**app/templates/:**
- Purpose: Jinja2 templates for web UI
- Generated: No
- Committed: Yes (checked into git)

**venv/:**
- Purpose: Virtual environment for development
- Generated: Yes (via `python -m venv venv`)
- Committed: No (in .gitignore)

**.planning/codebase/:**
- Purpose: Generated analysis documents (ARCHITECTURE.md, STRUCTURE.md)
- Generated: Yes (via /gsd:map-codebase command)
- Committed: Yes (documentation files)

---

*Structure analysis: 2025-03-17*
