# External Integrations

**Analysis Date:** 2026-03-17

## APIs & External Services

**Real Estate Data:**
- Ministry of Land Infrastructure and Transport (MOLIT) - Korean public real estate transaction data
  - SDK/Client: httpx (async HTTP client)
  - Base URL: `http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc`
  - Auth: Query parameter `serviceKey` with `MOLIT_API_KEY`
  - Endpoints implemented in `app/mcp/fastmcp_realestate.py`:
    - `/getRTMSDataSvcAptTradeDev` - Apartment transaction prices
    - `/getRTMSDataSvcOffiTradeDev` - Office trade prices
    - `/getRTMSDataSvcRHTradeDev` - Row house trade prices
  - Response format: XML, parsed to JSON in `app/mcp/fastmcp_realestate.py`

**LLM & AI Services:**
- Google Gemini API - LLM-powered agent features
  - SDK/Client: google-generativeai 0.8.3+
  - Auth: API key via `GEMINI_API_KEY` environment variable
  - Usage: `app/agent/llm_character_agents.py` uses `genai.GenerativeModel('gemini-1.5-flash')`
  - Features:
    - Property information extraction from user messages
    - Character agent responses (투심이, 삼돌이 agents)
    - Code analysis and documentation generation
    - Data analysis and insights
  - Client initialization: `genai.configure(api_key=GEMINI_API_KEY)`

- OpenAI API - Alternative LLM service (installed but not actively integrated)
  - SDK/Client: openai 1.51.0+
  - Auth: Via environment configuration
  - Status: Available for future use

**Gemini CLI Tool:**
- Gemini Command Line Interface - Direct AI interaction
  - Integration: `app/ai/gemini_service.py` wraps CLI as subprocess
  - Detection: Runtime check via `gemini --version` command
  - Features:
    - `chat()` - Free-form conversations with context
    - `analyze_code()` - Code review and analysis
    - `analyze_data()` - Business data pattern analysis
    - `generate_docs()` - Automatic documentation
    - `suggest_improvements()` - Improvement recommendations
    - `translate()` - Multi-language translation
  - Timeout: 30 seconds per request
  - Falls back gracefully if CLI not available

**Naver Services (Optional):**
- Naver Cloud Platform (NCP)
  - Auth: `NAVER_CLIENT_ID` and `NAVER_CLIENT_SECRET` environment variables
  - Status: Configured but optional (no active usage found in current implementation)

## Data Storage

**Databases:**
- Not detected - Application uses in-memory data structures
- Sample data generation: `app/data/sample_data.py` generates Korean business data
- No persistent database configured (ORM not present)

**File Storage:**
- Local filesystem only - Web routes serve static files from templates
- Template storage: `app/routes/web_routes.py` uses Jinja2Templates for HTML rendering
- No cloud storage integration detected

**Caching:**
- Not explicitly configured - No cache middleware detected
- In-memory storage via Python objects and Pydantic models
- Message queueing in agent connections managed by `app/agent/a2a_agent.py`

## Authentication & Identity

**Auth Provider:**
- Custom implementation via A2A protocol
- Agent authentication: Handshake mechanism in `app/routes/agent_routes.py`
  - Endpoint: `POST /api/agent/handshake`
  - Validation: Source agent ID and name verification
- No OAuth2, JWT, or external identity provider integration
- API key authentication for external services (MOLIT, Gemini) via environment variables

## Monitoring & Observability

**Error Tracking:**
- Not detected - No external error tracking service integrated

**Logs:**
- loguru-based logging (`app/utils/logger.py`)
- Structured logging to console
- Log level configurable via `LOG_LEVEL` environment variable
- Request/response logging middleware in `app/main.py`:
  - Logs all HTTP requests with unique request IDs (UUID)
  - Logs response time in seconds
  - Logs status codes

**Health Monitoring:**
- Health check endpoint: `GET /health`
- Returns agent status, ID, name, and current timestamp
- Used for deployment health checks (Render.com configured with `healthcheckPath: "/health"`)

## CI/CD & Deployment

**Hosting:**
- Railway.app (primary - via `railway.json`)
  - Builder: NIXPACKS (automatic Python environment setup)
  - Health check path: `/health`
  - Health check timeout: 300 seconds
  - Restart policy: ON_FAILURE
  - Start command: `python runner.py`

- Render.com (alternative - via `render.yaml`)
  - Environment: Python
  - Plan: Free tier
  - Build command: `pip install -r requirements.txt`
  - Start command: `python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Environment variables configured in deployment

- Heroku-compatible (via `Procfile`)
  - Start command: Uses procfile convention

**CI Pipeline:**
- Not detected - No GitHub Actions or other CI service configured
- Manual deployment via platform integrations

## Environment Configuration

**Required env vars:**
- `MOLIT_API_KEY` - Ministry of Land Infrastructure and Transport API key (from https://www.data.go.kr/)
- `GEMINI_API_KEY` - Google Gemini API key for LLM features

**Optional env vars:**
- `NAVER_CLIENT_ID` - Naver Cloud Platform client ID (from https://www.ncloud.com/)
- `NAVER_CLIENT_SECRET` - Naver Cloud Platform client secret
- `PORT` - Server port (default: 8000)
- `AGENT_ID` - Agent identifier (default: "agent-py-001")
- `AGENT_NAME` - Agent display name (default: "A2A_Python_Agent")
- `LOG_LEVEL` - Logging level (default: "INFO")
- `ENVIRONMENT` - Environment mode (default: "development")

**Secrets location:**
- `.env` file (git-ignored, see `.gitignore`)
- Environment variables in deployment platform (Railway, Render)
- Never committed to repository

## Webhooks & Callbacks

**Incoming:**
- Agent-to-agent handshake: `POST /api/agent/handshake` - Agents discover and register with each other
- Agent message receiving: `POST /api/agent/message` - Receive messages from other agents
- Agent data requests: `POST /api/agent/data-request` - Request data from this agent
- Smart routing: `POST /api/smart-chat/route` - Route messages to appropriate agent

**Outgoing:**
- Inter-agent HTTP communication via httpx async client (`app/agent/a2a_agent.py`)
- External agent adapter pattern supports multiple agent communication styles:
  - Standard A2A protocol
  - REST API style requests
  - JSON-RPC style communication (implemented in `app/agent/json_rpc.py`)
- Agent discovery broadcasts to known registry endpoints

## Model Context Protocol (MCP) Integration

**MCP Servers:**
- Real Estate MCP Server (`app/mcp/fastmcp_realestate.py`)
  - Tools: `get_apartment_trade()`, `get_officetel_trade()`, `get_row_house_trade()`
  - Data source: MOLIT API via fastmcp wrapper
  - Client access: `app/utils/fastmcp_client.py` for MCP tool invocation

- Location Service MCP Server (`app/mcp/location_service.py`)
  - Purpose: Provide location-based real estate analysis
  - Integration: Called via fastmcp client in character agents

**MCP Client:**
- fastmcp_client module (`app/utils/fastmcp_client.py`)
- Functions:
  - `call_real_estate_mcp_tool()` - Query real estate data
  - `call_location_mcp_tool()` - Get location information
- Manages MCP server lifecycle and cleanup via `cleanup_mcp_clients()`

## External Agent Communication

**External Agent Adapters:**
- Base adapter pattern: `app/agent/external_agent_adapter.py`
- Implementations:
  - **SocraticWebAdapter** - Web3 AI Tutor agent communication
    - Tries multiple endpoints: `/api/chat`, `/chat`, `/api/message`, `/api/a2a/message`
    - Tries multiple request formats for compatibility
    - Normalizes responses from different API styles
  - **RealEstateAgentAdapter** - Real estate specific agents
  - **EducationAgentAdapter** - Education domain agents
  - **EmploymentAdapterAdapter** - Employment/career agents

**JSON-RPC Protocol:**
- Full JSON-RPC 2.0 implementation in `app/agent/json_rpc.py`
- Request/response models with proper error handling
- Supports batched requests
- Methods: `ping`, `get_capabilities`, `get_status`
- Custom method registration for extensibility

---

*Integration audit: 2026-03-17*
