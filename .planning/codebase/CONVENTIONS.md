# Coding Conventions

**Analysis Date:** 2026-03-17

## Naming Patterns

**Files:**
- Snake_case: `a2a_agent.py`, `agent_routes.py`, `agent_discovery.py`
- Module grouping by responsibility: `agent/`, `routes/`, `utils/`, `data/`, `mcp/`
- Clear purpose in filename: `external_agent_adapter.py`, `intelligent_agent.py`, `json_rpc.py`

**Functions:**
- Snake_case with action verbs: `async def connect()`, `async def send_message()`, `async def receive_message()`
- Private methods prefixed with underscore: `async def _optimize_message_with_ai()`, `async def _extract_content_from_response()`
- Async operations are explicitly named with `async def`

**Classes:**
- PascalCase: `A2AAgent`, `AgentMessage`, `BaseAgentAdapter`, `RealEstateAgent`
- Model classes use Pydantic BaseModel: `AgentMessage(BaseModel)`, `AgentConnection(BaseModel)`
- Abstract base classes inherit from ABC: `class RealEstateAgent(ABC):`
- Adapter pattern classes: `BaseAgentAdapter`, `SocraticWebAdapter`

**Variables:**
- Snake_case: `agent_id`, `target_agent_id`, `message_type`, `payload`
- Descriptive names: `connections`, `message_queue`, `intelligent_message_queue`, `confidence_score`
- Boolean prefixes: `ai_enabled`, `gemini_available`
- Dictionary keys: Snake_case in API payloads, Korean descriptive in domain models

**Type Hints:**
- Full typing annotations on all functions: `def connect(self, target_agent_url: str, target_agent_id: str) -> bool:`
- Optional types explicitly marked: `Optional[Dict]`, `Optional[str]`, `Optional[datetime]`
- Union types for flexible parameters: `Union[Dict[str, Any], List[Any]]`
- Generic types with full specification: `Dict[str, Any]`, `List[Dict]`, `Dict[str, AgentConnection]`

## Code Style

**Formatting:**
- PEP 8 compliant (4-space indentation)
- Line length appears to follow standard (~88-100 characters, implied)
- No linting configuration detected (`.pylintrc`, `.flake8` absent)
- No enforced code formatter detected

**Imports:**
- Organized in groups: stdlib → third-party → local imports
- Group 1 (stdlib): `import uuid`, `import asyncio`, `import json`, `from datetime import datetime`
- Group 2 (third-party): `from fastapi import`, `from pydantic import`, `import httpx`, `from loguru import logger`
- Group 3 (local): `from app.agent.a2a_agent import`, `from app.utils.logger import logger`
- Each group separated by blank line
- Imports are explicit, not wildcard (no `from module import *`)

**Path Aliases:**
- Project structure uses absolute imports: `from app.agent.a2a_agent import A2AAgent`
- Relative imports within modules: `from ..utils.config import settings`
- No import aliases configured in pyproject.toml or setup.cfg

## Code Structure

**Docstrings:**
- Module-level docstrings present: `"""A2A Agent Core Implementation"""`
- Korean docstrings for Korean context: `"""에이전트 메시지 모델"""`, `"""다른 에이전트와 연결 설정"""`
- Single-line docstrings with triple quotes: `"""메시지 전송"""`
- No function argument documentation observed (no Args/Returns style)
- Classes documented: `"""A2A 에이전트 핵심 클래스"""`

**Comments:**
- Code comments are sparse but used for clarity
- Inline comments explain complex logic: `# 요청 데이터 파싱`, `# 배치 요청 처리`
- TODO/FIXME comments not observed in main source files

## Error Handling

**Patterns:**
- Try-except blocks around external API calls:
  ```python
  try:
      response = await self.client.post(...)
      if response.status_code == 200:
          # Handle success
      else:
          logger.error(f"Failed: {response.status_code}")
          return False
  except Exception as e:
      logger.error(f"Error: {str(e)}")
      return False
  ```

- JSON parsing with specific exception handling:
  ```python
  try:
      request_data = json.loads(request_data)
  except json.JSONDecodeError as e:
      return self._create_error_response(None, -32700, "Parse error", str(e))
  except Exception as e:
      logger.error(f"Unexpected error: {e}")
      return self._create_error_response(None, -32603, "Internal error", str(e))
  ```

- Graceful degradation for optional features:
  ```python
  try:
      ai_response = await gemini_service.chat(prompt)
  except Exception as e:
      logger.error(f"Smart message sending failed: {e}")
      return await self.send_message(target_agent_id, message_type, payload)
  ```

- Explicit HTTP exception raising:
  ```python
  raise HTTPException(
      status_code=500,
      detail=f"Failed to process message: {str(e)}"
  )
  ```

- JSON-RPC error responses with standard error codes:
  - Parse error: -32700
  - Invalid Request: -32600
  - Internal error: -32603

## Logging

**Framework:** Loguru

**Usage Pattern:**
- Module-level logger import: `from app.utils.logger import logger`
- Bound logger for agent context: `self.logger = logger.bind(agent=agent_name)`
- Consistent log levels:
  - `logger.info()` for lifecycle events
  - `logger.error()` for exceptions
  - `logger.debug()` for detailed operations

**Patterns:**
```python
logger.info(f"A2A Agent initialized: {self.agent_name} ({self.agent_id})")
logger.info(f"Connected to agent {target_agent_id} at {target_agent_url}")
logger.error(f"Connection error to {target_agent_url}: {str(e)}")
logger.info(f"Request {request_id}: {request.method} {request.url}")
logger.debug(f"Registered RPC method: {name}")
```

**Configuration:** `app/utils/logger.py`
- Color-coded console output with timestamp
- File logging in production with rotation and compression
- Configurable log level from settings

## Async Programming

**Patterns:**
- All async methods explicitly declared: `async def connect()`, `async def send_message()`
- Async context managers for resource management:
  ```python
  async with httpx.AsyncClient(timeout=30.0) as client:
      response = await client.post(...)
  ```

- Task gathering for parallel execution:
  ```python
  tasks = [self._process_single_request(req) for req in requests]
  responses = await asyncio.gather(*tasks, return_exceptions=True)
  ```

- No blocking operations in async functions

## Pydantic Models

**Patterns:**
- BaseModel inheritance for data validation
- Field annotations with types: `id: str`, `source_agent_id: str`
- Optional fields with defaults: `last_ping: Optional[datetime] = None`
- Field descriptions in JSON-RPC models: `Field(default="2.0", description="JSON-RPC version")`
- Model serialization: `message.model_dump()`

## Function Design

**Parameters:**
- Explicit type annotations required
- Default values for optional parameters: `agent_id: str = None`, `agent_name: str = None`
- Dictionary payloads use `Dict[str, Any]` type
- Optional return types explicitly marked: `-> Optional[Dict]`, `-> bool`

**Return Values:**
- Most async methods return `Optional[Dict]` or `Optional[str]`
- Boolean returns for connection/status operations: `-> bool`
- Dict returns for responses: `Dict[str, Any]`
- Many functions return response dictionaries matching API contracts

## Module Organization

**Exports:**
- No explicit `__all__` definitions observed
- Modules import and use classes directly: `from app.agent.a2a_agent import A2AAgent`
- Router modules create module-level instances: `router = APIRouter()`

**Barrel Files:**
- Not extensively used
- Agent subpackage has `__init__.py` but minimal exports

## Configuration Management

**Pattern:**
- Pydantic Settings in `app/utils/config.py`
- Environment variables via `.env` file
- Settings class as singleton: `settings = Settings()`
- Defaults provided for development: `port: int = int(os.getenv("PORT", 8000))`

## Code Quality Observations

**Strengths:**
- Consistent naming conventions across codebase
- Strong typing with Optional and Union types
- Structured error handling with logging
- Clear separation of concerns (agents, routes, utils, data)
- Async-first architecture

**Areas Without Strong Convention:**
- No linting configuration (pylint, flake8)
- No code formatter configuration (black)
- Minimal docstring detail (no Args/Returns format)
- Sparse inline comments in complex logic
- No type checking configuration (mypy)

---

*Convention analysis: 2026-03-17*
