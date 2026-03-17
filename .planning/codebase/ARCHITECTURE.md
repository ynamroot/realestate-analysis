# Architecture

**Analysis Date:** 2025-03-17

## Pattern Overview

**Overall:** Multi-agent communication system with layered architecture and external agent integration.

**Key Characteristics:**
- Async-first FastAPI application for HTTP-based inter-agent communication
- Adapter pattern for integrating heterogeneous external agents
- Model-Centric Protocol (MCP) integration for real estate domain services
- Pydantic-based validation and type safety across all message layers
- JSON-RPC 2.0 support for standardized agent communication
- Streaming (SSE) support for real-time data flows

## Layers

**Presentation Layer:**
- Purpose: Web UI and HTTP API endpoints for agent interaction
- Location: `app/routes/*.py`, `app/templates/*.html`
- Contains: FastAPI route handlers, Pydantic request/response models, HTML templates
- Depends on: Agent layer, AI services, MCP clients
- Used by: Web browsers, external agents, API clients

**Agent Communication Layer:**
- Purpose: Core A2A protocol implementation, message handling, inter-agent coordination
- Location: `app/agent/a2a_agent.py`, `app/agent/json_rpc.py`, `app/agent/streaming.py`
- Contains: Agent message models, connection management, handshake protocol
- Depends on: httpx for async HTTP, Pydantic for validation, logger
- Used by: Routes, external adapters, intelligent agents

**Agent Specialization Layer:**
- Purpose: Domain-specific agent implementations and character agents
- Location: `app/agent/real_estate_agent.py`, `app/agent/character_agents.py`, `app/agent/intelligent_agent.py`
- Contains: Real estate evaluation logic, LLM-based character agents, AI-enhanced message processing
- Depends on: Base A2A agent, AI services (Gemini), MCP clients
- Used by: Routes, multi-agent collaboration system

**External Integration Layer:**
- Purpose: Adapt heterogeneous external agents to A2A protocol
- Location: `app/agent/external_agent_adapter.py`
- Contains: BaseAgentAdapter, SocraticWebAdapter, protocol-specific adapters
- Depends on: httpx, agent discovery system
- Used by: Smart agent router, collaboration system

**Registry & Discovery Layer:**
- Purpose: Dynamic agent registration, discovery, and management
- Location: `app/agent/agent_registry.py`, `app/agent/agent_discovery.py`
- Contains: Agent registry management, agent metadata (capabilities, traits, languages)
- Depends on: JSON file storage, Pydantic models
- Used by: Routes, smart router, collaboration system

**AI & Intelligence Layer:**
- Purpose: LLM integration for intelligent message optimization and analysis
- Location: `app/ai/gemini_service.py`, `app/agent/intelligent_agent.py`, `app/agent/llm_character_agents.py`
- Contains: Gemini API client, AI-enhanced message processing, LLM-based agent simulation
- Depends on: httpx, external AI APIs
- Used by: Intelligent agent, character agents, smart router

**Data & Domain Layer:**
- Purpose: Sample data generation and domain-specific models
- Location: `app/data/sample_data.py`, `app/data/region_codes.py`
- Contains: SampleDataGenerator, Korean region/location data
- Depends on: Python standard library
- Used by: Routes, agents

**MCP Integration Layer:**
- Purpose: Model-Centric Protocol implementation for real estate services
- Location: `app/mcp/*.py`
- Contains: FastMCP servers and clients, location service, real estate MCP, recommendation engine
- Depends on: FastMCP library, asyncio
- Used by: Routes, real estate agents, external integrations

**Utility Layer:**
- Purpose: Cross-cutting infrastructure concerns
- Location: `app/utils/config.py`, `app/utils/logger.py`, `app/utils/fastmcp_client.py`
- Contains: Configuration management, logging setup, MCP client wrapper
- Depends on: pydantic-settings, loguru, environment variables
- Used by: All layers

## Data Flow

**Agent-to-Agent Message Flow:**

1. Client sends message request to `/api/agent/send-message` endpoint
2. Route handler creates SendMessageRequest (validated by Pydantic)
3. Global A2AAgent instance routes to target agent using stored connection
4. Target agent URL is called with AgentMessage payload
5. Target agent's `/api/agent/message` endpoint receives message
6. Message is queued in target agent's message_queue
7. Message handler processes by type (ping, data_request, data_response, custom)
8. Response is returned to sender with status and results
9. Sender receives response and stores in intelligent_message_queue (if using IntelligentA2AAgent)

**External Agent Integration Flow:**

1. Smart agent router receives request
2. Router queries agent discovery/registry for matching agents
3. If target is external agent, ExternalAgentAdapter is instantiated
4. Adapter translates A2A message to target agent's protocol format
5. Adapter sends HTTP request with multiple fallback endpoints/formats
6. Adapter receives response and normalizes to A2A format
7. Response returned to caller

**Real Estate Analysis Streaming Flow:**

1. Client initiates `/api/smart-chat/analyze-property` with property data
2. Route creates stream via StreamManager
3. RealEstateAgent evaluates property using location analysis
4. Streaming route sends updates via SSE to client
5. Analysis steps (price, location, transport, facilities) each emit progress
6. Final investment_score and life_quality_score sent to client
7. Stream closes after completion

**LLM Character Agent Conversation Flow:**

1. Client sends prompt to character agent endpoint
2. LLMCharacterAgent intercepts (if available)
3. LLM generates character-consistent response
4. Response is streamed back via SSE
5. Client receives multi-turn conversation

**State Management:**
- Agent connections stored in-memory as Dict[agent_id, AgentConnection]
- Message queues stored in-memory as List for each agent instance
- Stream state managed by StreamManager.active_streams Dict
- Registry data persisted to JSON file (`app/data/agent_registry.json`)
- Session state not persisted (stateless design per request)

## Key Abstractions

**A2AAgent:**
- Purpose: Core agent implementation with async HTTP communication
- Examples: `app/agent/a2a_agent.py` (base), `app/agent/intelligent_agent.py` (AI-enhanced), `app/agent/real_estate_agent.py` (specialized)
- Pattern: Inheritance-based specialization with method override for domain-specific behavior

**AgentMessage:**
- Purpose: Strongly-typed message envelope for inter-agent communication
- Examples: All agent routes use AgentMessage for validation
- Pattern: Pydantic BaseModel for automatic validation, serialization, documentation

**BaseAgentAdapter:**
- Purpose: Abstract adapter for integrating external (non-A2A) agents
- Examples: `SocraticWebAdapter` (Web3 Socratic tutor), can extend for other external agents
- Pattern: Abstract base class with multiple protocol implementations

**StreamManager:**
- Purpose: Manage real-time SSE streams for asynchronous data delivery
- Examples: `app/agent/streaming.py` provides global `stream_manager` instance
- Pattern: Singleton pattern with asyncio.Queue for message buffering

**AgentRegistry:**
- Purpose: Central catalog of all agents with metadata and capabilities
- Examples: `app/agent/agent_registry.py` manages JSON-persisted registry
- Pattern: Singleton-style manager with JSON file as backing store

**JsonRpcProcessor:**
- Purpose: Handle JSON-RPC 2.0 protocol requests with extensible method registry
- Examples: `app/agent/json_rpc.py` provides protocol implementation
- Pattern: Method registry pattern with middleware support for cross-cutting concerns

## Entry Points

**FastAPI Application Entry:**
- Location: `app/main.py`
- Triggers: `uvicorn app.main:app` or `python -m app.main`
- Responsibilities:
  - FastAPI app initialization with lifespan handler
  - CORS and middleware setup (UTF-8 JSON, request logging)
  - Route registration across all domains
  - Health check endpoint
  - Logging of startup information

**Agent Communication Entry:**
- Location: `/api/agent/message` route in `app/routes/agent_routes.py`
- Triggers: Incoming HTTP POST from another agent
- Responsibilities:
  - Receive and validate AgentMessage
  - Route to global agent instance for message processing
  - Dispatch to message type handlers (ping, data_request, etc.)
  - Return response to sender

**Real Estate Analysis Entry:**
- Location: `/api/smart-chat/analyze-property` route in `app/routes/smart_chat_routes.py`
- Triggers: HTTP request with property data and coordinates
- Responsibilities:
  - Create streaming response
  - Invoke real estate agents (investment + life quality)
  - Stream analysis progress to client
  - Return final evaluation scores

**MCP Server Entry:**
- Location: `app/mcp/*.py` (fastmcp_realestate.py, location_service.py, etc.)
- Triggers: FastMCP client requests
- Responsibilities:
  - Provide real estate-specific tools and data
  - Implement location analysis services
  - Handle recommendation engine calls

## Error Handling

**Strategy:** Exception-based with try-catch at route layer, logging at all layers, HTTP status codes for API errors.

**Patterns:**

**Message Handling Errors:**
```python
# In agent_routes.py
try:
    response = await agent.receive_message(message.model_dump())
except Exception as e:
    logger.error(f"Error processing message: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")
```

**Connection Failures:**
```python
# In a2a_agent.py - connect method
try:
    response = await self.client.post(...)
    if response.status_code != 200:
        logger.error(f"Failed to connect: {response.status_code}")
        return False
except Exception as e:
    logger.error(f"Connection error: {str(e)}")
    return False
```

**Adapter Protocol Fallback:**
- External adapter tries multiple endpoints and request formats
- Falls back to generated default response if all attempts fail
- Logs debug messages for each failed attempt

**Stream Error Recovery:**
```python
# In streaming.py
except Exception as e:
    logger.error(f"Stream generator error: {e}")
    yield self._format_sse_message("error", {"message": str(e)})
finally:
    # Always cleanup stream
    if stream_id in self.active_streams:
        await self.close_stream(stream_id)
```

**AI Service Degradation:**
```python
# In intelligent_agent.py
if self.ai_enabled:
    optimized_payload = await self._optimize_message_with_ai(...)
else:
    optimized_payload = payload  # Fallback to unoptimized
```

## Cross-Cutting Concerns

**Logging:**
- Implementation: Loguru-based via `app/utils/logger.py`
- Usage: All layers use `logger.info()`, `logger.error()`, `logger.debug()`
- Binding: Agents use `logger.bind(agent=agent_name)` for contextual logging

**Validation:**
- Implementation: Pydantic BaseModel (v2) with Field validators
- Patterns: Every HTTP request uses request model (HandshakeRequest, MessageRequest, etc.)
- Custom validators used for specific domain logic

**Authentication:**
- Current: None implemented (open API)
- Assumption: Agents run in trusted network
- Future: Consider bearer token or API key validation

**Async/Concurrency:**
- Pattern: All I/O operations (httpx, stream writing) are async
- Requirement: asyncio.Queue for stream buffering, async context managers for lifecycle
- Gotcha: Ensure all handler functions are `async def`

**Configuration:**
- Location: `app/utils/config.py`
- Pattern: Pydantic Settings with environment variable fallback
- Critical vars: PORT, AGENT_ID, AGENT_NAME, ENVIRONMENT

**MCP Client Lifecycle:**
- Location: `app/utils/fastmcp_client.py`
- Pattern: Global client instances created at startup, cleanup on shutdown
- Called in: lifespan context manager of FastAPI app

---

*Architecture analysis: 2025-03-17*
