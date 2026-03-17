# Testing Patterns

**Analysis Date:** 2026-03-17

## Test Framework

**Runner:**
- Pytest configured in `pyproject.toml`
- Test discovery: `python_files = ["test_*.py", "*_test.py"]`
- Test paths: `testpaths = ["tests"]`

**Run Commands:**
```bash
pytest                  # Run all tests
pytest tests/           # Run tests directory
pytest -v              # Verbose output
pytest --tb=short      # Short traceback format
pytest -s              # Show print statements
```

**Assertion Library:**
- Standard Python `assert` statements

**Test Client:**
- FastAPI TestClient available via `from fastapi.testclient import TestClient`
- Async test support through pytest-asyncio (via anyio in dependencies)

## Test File Organization

**Location:**
- Separate `tests/` directory at project root
- Pattern: `tests/test_{module}.py`

**Actual Test Files:**
- `tests/test_mcp.py` - MCP (Model Context Protocol) integration tests
- `tests/test_fastmcp.py` - FastMCP server tests
- `examples/test_ai_endpoints.py` - AI endpoints integration tests

**Naming:**
- Prefix: `test_` for test files
- Method names describe what is tested: `async def test_mcp_endpoints():`

## Test Structure

**Module-Level Tests (`test_mcp.py`):**
```python
#!/usr/bin/env python3
"""
한국 부동산 가격 조회 MCP 서버 테스트 스크립트
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta

async def test_mcp_endpoints():
    """MCP 엔드포인트 테스트"""

    async with httpx.AsyncClient() as client:
        # 1. Setup
        BASE_URL = "http://localhost:8080"

        # 2. Test execution
        response = await client.get(f"{BASE_URL}/api/mcp/status")
        if response.status_code == 200:
            data = response.json()
            # 3. Assertions (print-based validation)
            print(f"✅ 상태: {data['success']}")
        else:
            print(f"❌ 오류: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_mcp_endpoints())
```

**Pattern Characteristics:**
- Entry point defined with `if __name__ == "__main__"`
- Async test functions: `async def test_mcp_endpoints():`
- Event loop usage: `asyncio.run(test_function())`
- HTTP client: `httpx.AsyncClient()`
- Assertion via print statements and status checks

**Integration Test Pattern (`test_fastmcp.py`):**
```python
async def check_environment():
    """환경 확인"""
    print("🔍 환경 확인:")

    # Python 버전 확인
    python_version = sys.version.split()[0]
    print(f"   Python 버전: {python_version}")

    # FastMCP 설치 확인
    try:
        import fastmcp
        print(f"   FastMCP 버전: {fastmcp.__version__}")
    except ImportError:
        print("   ❌ FastMCP가 설치되지 않았습니다")
        return False

    return True
```

**Pattern Characteristics:**
- Environment validation before tests
- Try-except for optional dependency checking
- Subprocess execution for module tests

## Test Coverage

**Current State:**
- Limited test suite in `tests/` directory
- Tests are primarily integration/manual tests
- No unit test coverage observed for core agent classes
- Manual testing scripts in `examples/` directory

**Test Files Present:**
- `tests/test_mcp.py` (181 lines) - Real Estate MCP server endpoints
- `tests/test_fastmcp.py` (132 lines) - FastMCP server verification
- `examples/test_ai_endpoints.py` (182 lines) - AI endpoint integration tests

**Missing Coverage:**
- Unit tests for `app/agent/a2a_agent.py`
- Unit tests for `app/agent/external_agent_adapter.py`
- Unit tests for `app/routes/` modules
- Unit tests for `app/utils/` modules
- Mock-based tests

## Testing Patterns Observed

**1. Async Testing Pattern:**
```python
async def test_mcp_endpoints():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/mcp/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 상태: {data['success']}")
```

**Usage:**
- Used for HTTP-based integration tests
- Verifies real endpoint behavior
- No mocking of HTTP client

**2. Manual Verification Pattern:**
```python
# Environment check
try:
    import fastmcp
    print(f"FastMCP 버전: {fastmcp.__version__}")
except ImportError:
    print("❌ FastMCP가 설치되지 않았습니다")
    return False
```

**Usage:**
- Pre-test environment validation
- Dependency availability checking
- Clear error messaging for debugging

**3. Subprocess Testing Pattern:**
```python
result = subprocess.run(
    ["python", "app/mcp/fastmcp_realestate.py", "--help"],
    capture_output=True,
    text=True,
    timeout=10,
    cwd=Path(__file__).parent
)

if result.returncode == 0:
    print(f"✅ 성공")
else:
    print(f"❌ 오류: {result.stderr}")
```

**Usage:**
- Tests module execution
- Captures stdout/stderr
- Handles timeouts
- Works directory context

**4. HTTP Integration Testing Pattern:**
```python
test_data = {
    "lawd_cd": "11680",  # 서울 강남구
    "deal_ymd": last_month
}

response = await client.post(
    f"{BASE_URL}/api/mcp/apartment/trade",
    json=test_data
)

if response.status_code == 200:
    data = response.json()
    if data['success'] and data['data']:
        items = data['data'].get('items', [])
        print(f"📊 조회 건수: {total_count}건")
```

**Usage:**
- Tests real API endpoints with real data
- Validates response structure
- Iterates over result collections for spot-checking

## Mocking

**Framework:** Not explicitly configured

**Current Approach:**
- Integration tests use real services
- No mocks for HTTP clients or external dependencies
- Direct calls to actual endpoints

**What IS Mocked:**
- Not explicitly using mock library
- Some fallback patterns in adapter code:
  ```python
  if self.ai_enabled:
      optimized_payload = await self._optimize_message_with_ai(message_type, payload)
  else:
      optimized_payload = payload  # Fallback when AI unavailable
  ```

**What IS NOT Mocked:**
- HTTP requests (real httpx.AsyncClient)
- Database operations (if any)
- External services (Gemini API, etc.)
- File system operations

## Fixtures and Factories

**Test Data:**
- Hardcoded in test functions
- Example: `test_data = {"lawd_cd": "11680", "deal_ymd": last_month}`
- Date calculations: `last_month = (datetime.now() - timedelta(days=30)).strftime("%Y%m")`
- No pytest fixtures detected
- No factory boy or similar factories

**Location:**
- Test data inline within test functions
- Sample data module available: `app/data/sample_data.py`

## Test Execution Strategy

**Integration Testing Focus:**
- Tests verify end-to-end flows
- Real API endpoints are called
- Real external dependencies are required
- Tests require server running on localhost

**Test Server Requirements:**
- Base URL: `http://localhost:8080` (test_mcp.py)
- Base URL: `http://localhost:28000` (test_ai_endpoints.py)
- Server must be running before tests execute

**Example Test Execution:**
```bash
# Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 28000

# In another terminal
python examples/test_ai_endpoints.py
```

## Assertion Patterns

**Print-Based Assertions:**
```python
if response.status_code == 200:
    data = response.json()
    print(f"✅ 상태: {data['success']}")
else:
    print(f"❌ 오류: {response.status_code}")
```

**Status Code Checks:**
```python
if response.status_code == 200:
    # Success path
else:
    print(f"❌ HTTP 오류: {response.status_code}")
```

**Response Structure Validation:**
```python
if data['success'] and data['data']:
    items = data['data'].get('items', [])
    total_count = data['data'].get('total_count', 0)
    # Validate items
```

**Exception Handling:**
```python
try:
    response = await client.get(url)
    # Process response
except Exception as e:
    print(f"❌ 연결 오류: {e}")
```

## Error Testing

**Pattern:**
Not explicitly tested with error cases

**Current Behavior:**
- Tests focus on happy path
- Exception handling tested indirectly through try-except
- Network errors caught and reported
- HTTP error codes checked but not thoroughly tested

## Test Output Format

**Success Indicators:**
- Emoji prefixes: `✅` for success, `❌` for error
- Descriptive messages in Korean
- Print-based output
- No structured test reports (no pytest fixtures)

**Example Output:**
```
=== 한국 부동산 가격 조회 MCP 서버 테스트 ===

1. MCP 서버 상태 확인
   ✅ 상태: True
   📝 메시지: MCP server is running
   🔑 API 키 설정: False
   🛠️  사용 가능한 도구: get_regions, search_apartments, ...
```

## Async Testing Support

**Framework:** pytest with asyncio support
- anyio installed (provides pytest_plugin)
- AsyncClient available from httpx
- asyncio.run() for standalone scripts

**Pattern:**
```python
async def test_async_operation():
    """Async test function"""
    result = await some_async_function()
    assert result is not None
```

## Test Dependency Management

**Dependencies Present:**
- `httpx>=0.25.2` - Async HTTP client for integration tests
- `pytest` configured but version not locked in requirements.txt
- `anyio` for async test support

**Missing Dependencies:**
- `pytest-asyncio` - Formal async test support
- `pytest-mock` or `unittest.mock` - Mocking framework
- `faker` or similar - Test data generation
- `pytest-cov` - Coverage reporting

## Configuration

**pytest.ini (in pyproject.toml):**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
```

**Missing Configurations:**
- `conftest.py` - No pytest configuration hooks
- `pytest.ini` - No separate pytest config file
- Test markers not defined
- Fixtures not centralized

## Common Test Issues Observed

**1. Server Dependency:**
- Tests require running server
- No test database or in-memory testing
- Network calls are real

**2. Manual Assertion:**
- Print-based validation instead of assert
- Difficult to integrate with CI/CD
- No structured test output

**3. Limited Coverage:**
- Only integration tests present
- No unit tests for core logic
- No isolated component testing

## Improvement Opportunities

**Priority 1:**
- Add `conftest.py` with pytest fixtures
- Convert manual tests to pytest format with assert statements
- Add test markers (unit, integration, slow)
- Implement test coverage measurement

**Priority 2:**
- Add mock fixtures for external services
- Create test factories for agent/message data
- Implement fixture for test server (pytest-servers or similar)
- Add parametrized tests for multiple scenarios

**Priority 3:**
- Add pytest-asyncio for proper async test support
- Implement CI/CD integration for test runs
- Add performance benchmarks
- Document test execution requirements

---

*Testing analysis: 2026-03-17*
