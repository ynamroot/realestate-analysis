# Technology Stack

**Analysis Date:** 2026-03-17

## Languages

**Primary:**
- Python 3.8+ - Backend application and MCP server implementations

**Secondary:**
- JavaScript/Node.js (optional) - Legacy/alternative implementation available (see `src/` directory)
- Bash - Development scripts and deployment

## Runtime

**Environment:**
- Python 3.8+ (specified in `pyproject.toml`)
- uvicorn ASGI server for serving FastAPI application
- Node.js (for legacy implementation if used)

**Package Manager:**
- pip - Python package management
- Lockfile: present (`requirements.txt` for pip)

## Frameworks

**Core:**
- FastAPI 0.115.0+ - Web framework for REST APIs and agent communication
- Uvicorn 0.24.0+ - ASGI server implementation
- Pydantic 2.8.0+ - Data validation and settings management using BaseSettings

**Agent Communication:**
- FastMCP 2.10.6 - Model Context Protocol implementation for MCP servers
- MCP 1.12.0+ - Model Context Protocol specification compliance

**LLM Integration:**
- google-generativeai 0.8.3+ - Google Gemini API client for AI features
- openai 1.51.0+ - OpenAI API client (available but not actively used)

**Testing:**
- pytest - Test runner (configured in `pyproject.toml`)

**Build/Dev:**
- setuptools 61.0+ - Build system (configured in `pyproject.toml`)

## Key Dependencies

**Critical:**
- httpx 0.27.0+ - Async HTTP client for inter-agent communication and external APIs (used extensively in `app/agent/external_agent_adapter.py`, `app/agent/multi_agent_conversation.py`)
- python-dotenv 1.1.0+ - Environment variable loading from `.env` files
- pydantic-settings 2.5.2+ - Configuration management with type validation
- loguru 0.7.2+ - Advanced structured logging

**Infrastructure:**
- jinja2 3.1.0+ - Template engine for HTML rendering in web routes (`app/routes/web_routes.py`)
- python-multipart 0.0.6+ - Multipart form data parsing for file uploads
- dnspython 2.7.0+ - DNS resolution support for MCP services
- attrs 22.2.0+ - Class definition utilities
- jsonschema 4.20.0+ - JSON schema validation for A2A protocol messages

## Configuration

**Environment:**
- Loaded via `.env` file (UTF-8 encoded) using `python-dotenv` and Pydantic BaseSettings (`app/utils/config.py`)
- Configuration class: `Settings` in `app/utils/config.py`

**Key Environment Variables:**
- `PORT` - Server port (defaults to 8000, supports Railway dynamic port)
- `AGENT_ID` - Unique agent identifier (default: "agent-py-001")
- `AGENT_NAME` - Human-readable agent name (default: "A2A_Python_Agent")
- `ENVIRONMENT` - Environment mode (development/production)
- `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)
- `MOLIT_API_KEY` - Ministry of Land Infrastructure and Transport (MOLIT) API key
- `NAVER_CLIENT_ID` - Naver API client ID (optional)
- `NAVER_CLIENT_SECRET` - Naver API client secret (optional)
- `GEMINI_API_KEY` - Google Gemini API key for LLM features

**Build:**
- `pyproject.toml` - Modern Python project configuration with setuptools
- `render.yaml` - Render.com deployment configuration
- `railway.json` - Railway.app deployment configuration
- `Procfile` - Procfile for Heroku-style deployments
- `requirements.txt` - Frozen dependency versions for reproducible builds

## Platform Requirements

**Development:**
- Python 3.8+ interpreter
- pip package manager
- Virtual environment recommended (venv present in repo)
- Optional: Node.js for legacy JavaScript implementation

**Production:**
- Deployment targets supported:
  - Railway.app (configured via `railway.json`)
  - Render.com (configured via `render.yaml`)
  - Heroku (via `Procfile`)
  - Any server supporting Python 3.8+ and standard ASGI deployment
  - Docker-ready (via NIXPACKS builder on Railway)

**Server Requirements:**
- 30-second timeout for external HTTP requests
- Support for 100 concurrent connections (configurable)
- UTF-8 JSON response encoding enabled globally

---

*Stack analysis: 2026-03-17*
