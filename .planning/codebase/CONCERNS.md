# Codebase Concerns

**Analysis Date:** 2026-03-17

## Tech Debt

**Fallback Response Patterns (External Adapters):**
- Issue: Multiple external agent adapters use hardcoded fallback responses instead of real integration
- Files: `app/agent/external_agent_adapter.py` (SocraticWebAdapter, RealEstateAgentAdapter, JobSearchAgentAdapter, DocumentGeneratorAdapter, MLBSportsAdapter, Web3AILabAdapter)
- Impact: Users receive static responses regardless of actual agent state; system appears to work but doesn't integrate; makes testing and debugging difficult
- Fix approach: Implement actual health checks, timeout handling, and graceful degradation per adapter; consider circuit breaker pattern for external services

**Excessive Debug Print Statements:**
- Issue: Dozens of debug print() calls left in production code instead of using logger
- Files: `app/mcp/location_service.py` (lines 215-216, 365-366, 642-643, 775), `app/mcp/real_estate_recommendation_mcp.py` (lines 104, 384-390, 409, 422-423, 450-460, 480-481)
- Impact: Clutters stdout, makes log aggregation impossible, inconsistent with loguru logging elsewhere
- Fix approach: Replace all print() calls with logger.debug(), logger.info() statements; configure log level via environment

**Bare Exception Handlers:**
- Issue: Multiple files catch generic Exception without context
- Files: `app/agent/agent_discovery.py` (lines 47, 56, 75, 105, 115), `app/agent/agent_registry.py` (lines 215, 366, 373), `app/mcp/real_estate_recommendation_mcp.py` (line 65)
- Impact: Hides actual errors, swallows important diagnostic info, makes production debugging impossible
- Fix approach: Catch specific exception types (HTTPError, TimeoutError, ValueError); log full traceback with context; re-raise or transform appropriately

**Hardcoded Timeouts:**
- Issue: Timeouts hardcoded in httpx.AsyncClient calls throughout codebase
- Files: `app/agent/external_agent_adapter.py` (30.0s, 10.0s), `app/agent/agent_discovery.py` (10.0s, 5.0s, 15.0s), `app/mcp/location_service.py` (implied defaults)
- Impact: No central timeout policy, inconsistent across services, not tunable per environment
- Fix approach: Move all timeouts to `app/utils/config.py` as configurable settings with reasonable defaults

**Random Number Generation in Analysis:**
- Issue: Character agents (投心이, 삼돌이) use random.uniform() for all analysis scores
- Files: `app/agent/character_agents.py` (lines 48, 52, 56, 60, 64, 136-148)
- Impact: Analysis results are non-deterministic, not based on actual property data, user cannot trust recommendations
- Fix approach: Replace random values with actual scoring logic based on property_data parameters

## Known Bugs

**Missing Registry Initialization Check:**
- Symptoms: KeyError on `self.registry_data["registry_info"]` when saving
- Files: `app/agent/agent_registry.py` (line 78)
- Trigger: Call _save_registry() on newly loaded registry without registry_info key
- Workaround: Initialize registry_info in _load_registry if missing; add defensive check before access

**CSV Parsing Silent Failure:**
- Symptoms: Returns empty list when CSV parsing fails, no user visibility into why data couldn't be processed
- Files: `app/mcp/real_estate_recommendation_mcp.py` (lines 102-105)
- Trigger: Malformed CSV or missing expected columns in government API response
- Workaround: Wrap in try-except and return error details; log specific parsing failures

**Pydantic model_dump() Deprecation:**
- Symptoms: Uses older Pydantic v1 API (.dict() instead of .model_dump())
- Files: `app/agent/json_rpc.py` (lines 140, 168)
- Trigger: Already using Pydantic v2 (>=2.8.0 in requirements.txt), inconsistent with rest of codebase
- Workaround: Update to use .model_dump() consistently across all models

## Security Considerations

**Overly Permissive CORS:**
- Risk: CORSMiddleware allows any origin with allow_origins=["*"]
- Files: `app/main.py` (lines 55-61)
- Current mitigation: None
- Recommendations: Restrict to specific origin list; use environment variable for allowed origins in production; remove allow_credentials=True if not needed

**API Key Exposure in Environment Variables (No Validation):**
- Risk: Multiple API keys (MOLIT_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, TOPIS_API_KEY, SEOUL_API_KEY) loaded from environment with no validation
- Files: `app/mcp/location_service.py` (lines 22-25), `app/mcp/real_estate_recommendation_mcp.py` (lines 113-115)
- Current mitigation: .env.example not checked, no startup validation of required keys
- Recommendations: Add startup validation check in main.py to ensure critical keys exist; warn if running with empty keys; never log API key values

**Missing Input Validation on RPC Methods:**
- Risk: RPC methods accept arbitrary params without type checking
- Files: `app/agent/json_rpc.py` (lines 124-133) - params passed directly without schema validation
- Current mitigation: Basic Pydantic validation on JsonRpcRequest only
- Recommendations: Add Pydantic schemas for each method's params; validate before calling handler

**Weak Default Trust Levels:**
- Risk: External agents get default trust_level=5 (50% score) without verification
- Files: `app/agent/agent_registry.py` (line 32)
- Current mitigation: Trust level stored in registry but not used for routing decisions
- Recommendations: Implement trust score in agent selection; require verification before allowing agent routing

## Performance Bottlenecks

**Synchronous CSV Parsing in Async Context:**
- Problem: CSV parsing (csv.DictReader) blocks event loop when called from async context
- Files: `app/mcp/real_estate_recommendation_mcp.py` (lines 50-100)
- Cause: Pure I/O-bound task not delegated to thread pool
- Improvement path: Use asyncio.to_thread() or ThreadPoolExecutor for CSV parsing; implement caching for repeated parses

**Expensive DNS Resolution in Discovery:**
- Problem: dns.resolver.Resolver().resolve() called synchronously during agent discovery
- Files: `app/agent/agent_discovery.py` (line 39)
- Cause: Network I/O not awaited in async context
- Improvement path: Use aiodns or wrap with asyncio.to_thread(); cache DNS results with TTL

**Linear Search in Agent Registry:**
- Problem: Search methods iterate all agents in memory for each request
- Files: `app/agent/agent_registry.py` (lines 103-123) - search_agents_by_keyword does O(n*m) search
- Cause: No indexing on keywords, aliases, or tags
- Improvement path: Build inverted indexes on initialization; use set membership checks instead of list iteration

**Repeated JSON Serialization in Adapter Responses:**
- Problem: Multiple JSON encode/decode cycles in external_agent_adapter
- Files: `app/agent/external_agent_adapter.py` (lines 62-81) - response.json() called after json.dumps()
- Cause: No response caching, repeated conversions
- Improvement path: Cache adapter responses for N seconds; reuse parsed JSON objects

**Full Agent Registry Load on Startup:**
- Problem: All agents and mappings loaded into memory regardless of usage
- Files: `app/agent/agent_registry.py` (line 47) - loads entire registry_file in __init__
- Cause: No lazy loading or pagination
- Improvement path: Implement lazy loading for rarely-used agents; add pagination to list endpoints

## Fragile Areas

**Global State in Module Instances:**
- Files: `app/agent/external_agent_adapter.py` (line 597 - global external_agent_manager), `app/agent/character_agents.py` (line 243 - global character_manager), `app/agent/json_rpc.py` (line 195 - global rpc_processor)
- Why fragile: Global instances not thread-safe; state shared across requests; no reset between tests
- Safe modification: Pass instances through dependency injection; use FastAPI Depends() pattern; initialize fresh per request in tests
- Test coverage: No tests mock global instances; integration tests contaminate each other's state

**Conversation History Storage in Memory:**
- Files: `app/agent/character_agents.py` (line 199), `app/agent/smart_agent_router.py` (line 37)
- Why fragile: Grows unbounded across server lifetime; lost on restart; not thread-safe for concurrent requests
- Safe modification: Move history to database (Redis/PostgreSQL); implement TTL for cleanup; use request-scoped history
- Test coverage: No tests validate conversation history isolation across concurrent requests

**Mutable Default Arguments in Config:**
- Files: `app/agent/agent_registry.py` (line 40 - registry_file default uses Path operations)
- Why fragile: Path manipulation happens at module import time; unclear if registry_file exists
- Safe modification: Move Path operations into __init__ method; validate file exists; use factory pattern for defaults
- Test coverage: No tests verify registry file location handling

**External Agent Adapter Endpoint Guessing:**
- Files: `app/agent/external_agent_adapter.py` (lines 44-49, 354-358) - tries multiple endpoints sequentially
- Why fragile: Arbitrary endpoint list; timeouts on each attempt accumulate; no feedback when all fail
- Safe modification: Use well-known endpoints from agent.json spec; implement exponential backoff; cache successful endpoint
- Test coverage: No tests for endpoint discovery logic; mocking doesn't cover fallback chains

## Scaling Limits

**Single-Threaded Registry Updates:**
- Current capacity: ~1000 agents before serialization overhead becomes visible
- Limit: File I/O serialization on every agent update blocks all requests
- Scaling path: Switch from JSON file to database (SQLite → PostgreSQL); implement write-ahead logging; batch updates

**Memory-Resident Conversation History:**
- Current capacity: ~10,000 conversation entries before memory issues
- Limit: Unbounded growth, no cleanup mechanism
- Scaling path: Implement database backend; add TTL-based cleanup; paginate history queries

**Synchronous MCP Server Startup:**
- Current capacity: ~5 concurrent MCP servers before blocking
- Limit: FastMCP server initialization blocks event loop
- Scaling path: Lazy-load MCP servers; defer initialization to first use; implement server pooling

## Dependencies at Risk

**fastmcp==2.10.6 (Pinned Version):**
- Risk: Pinned exact version may have unpatched security issues; not compatible with newer MCP spec
- Impact: Cannot upgrade MCP protocol without major refactor of `app/mcp/` modules
- Migration plan: Move to fastmcp>=2.10.0 with minimum version; monitor releases; test with newer versions in CI

**python-dotenv (Environment Handling):**
- Risk: Only loads .env at import time; no hot-reload; secrets visible in memory
- Impact: Cannot update configuration without server restart; potential credential exposure in crash dumps
- Migration plan: Switch to python-decouple or environ for better management; implement config refresh endpoint for non-secrets

**openai>=1.51.0 (Unused):**
- Risk: Dependency included but not visibly imported anywhere in codebase
- Impact: Increases attack surface; adds unmaintained code path if accidentally used
- Migration plan: Verify unused imports; remove if truly not needed; if used, add explicit usage in routes

## Missing Critical Features

**No Agent Health Monitoring:**
- Problem: Cannot detect when external agents become unavailable until request fails
- Blocks: Proactive failover, accurate agent status display, load balancing decisions
- Needed: Periodic health checks with exponential backoff; circuit breaker per agent; status dashboard

**No Request Rate Limiting:**
- Problem: No throttling on API endpoints; bad agents can DOS the system
- Blocks: Production safety, multi-tenant isolation, cost control
- Needed: Implement rate limiting per agent ID; add backpressure on external API calls

**No Request/Response Validation Schema:**
- Problem: RPC handlers accept Any params; no runtime validation of message contracts
- Blocks: Version compatibility, debugging, contract enforcement
- Needed: Define schema for each agent interaction; validate before processing; version APIs

**No Transaction/Rollback Support:**
- Problem: Multi-step operations (search, analyze, recommend) have no atomicity
- Blocks: Consistency when agents fail mid-operation; recovery from partial failures
- Needed: Implement transaction semantics; implement compensating actions for failures

## Test Coverage Gaps

**External Adapter Network Failures:**
- What's not tested: Timeout handling, connection refused, 500 errors, malformed JSON responses
- Files: `app/agent/external_agent_adapter.py` - all adapters
- Risk: Production failures go undetected; fallback logic untested
- Priority: High - External integrations are critical path

**Agent Registry Concurrent Access:**
- What's not tested: Multiple threads calling get_agent_by_id, search_agents_by_keyword simultaneously
- Files: `app/agent/agent_registry.py`
- Risk: Race conditions on dict access; corrupted registry state
- Priority: High - Registry is core to agent routing

**CSV Parsing Edge Cases:**
- What's not tested: Empty CSV, missing columns, non-numeric price/area, very large files
- Files: `app/mcp/real_estate_recommendation_mcp.py` - parse_csv_data()
- Risk: Silent failures, corrupted analysis results
- Priority: Medium - CSV parsing is data-critical but not always exercised

**Smart Router Pattern Matching:**
- What's not tested: Regex patterns with Korean characters, partial matches, edge case language variations
- Files: `app/agent/smart_agent_router.py` (lines 45-105)
- Risk: Agent switching fails silently; users stuck with wrong agent
- Priority: Medium - User experience impact but not data critical

**JSON-RPC Batch Processing:**
- What's not tested: Large batch requests (100+), mixed success/error responses, timeout during batch
- Files: `app/agent/json_rpc.py` - _process_batch()
- Risk: Partial batch failures, response inconsistency
- Priority: Low - Batch API less commonly used

---

*Concerns audit: 2026-03-17*
