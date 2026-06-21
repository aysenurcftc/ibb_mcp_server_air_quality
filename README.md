# IBB Air Quality MCP Server

MCP (Model Context Protocol) server for Istanbul Metropolitan Municipality (IBB) Air Quality Open Data API.
Built with FastMCP + Redis cache + Docker.

## Quick Start

```bash
git clone https://github.com/YOUR_ORG/ibb-mcp-server.git
cd ibb-mcp-server
cp .env.example .env
docker compose up -d
```

---

## Claude Desktop Setup

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ibb": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ibb-mcp-server", "ibb-mcp"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "REDIS_URL": "redis://localhost:6379/0",
        "CACHE_TTL": "60",
        "IBB_HAVA_KALITESI_BASE_URL": "https://api.ibb.gov.tr/havakalitesi/OpenDataPortalHandler"
      }
    }
  }
}
```

> **Windows note:** Use double backslashes in the path: `C:\\Users\\name\\projects\\ibb-mcp-server`

> **Redis note:** Run `docker compose up -d` before opening Claude Desktop so Redis is available on `localhost:6379`.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `get_air_quality_stations` | List all IBB air quality monitoring stations in Istanbul |
| `get_air_quality_measurements` | Get PM10, SO2, O3, NO2, CO readings for a station and date range (max 7 days) |
| `get_station_latest_status` | Get the latest reading for a station from the last 24 hours |
| `air_quality_health_check` | Check API and Redis connection status |

**Example queries:**
- "List air quality stations in Istanbul"
- "What is the current air quality at Maslak station?"
- "Get PM10 readings for Esenler station from January 15 to January 16, 2024"

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CACHE_TTL` | `60` | Cache duration in seconds |
| `IBB_HAVA_KALITESI_BASE_URL` | `https://api.ibb.gov.tr/...` | IBB API base URL |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `MCP_PORT` | `8000` | Port for HTTP mode |

---

## Developer Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
# Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

uv sync

# Run in HTTP mode (for testing)
# macOS/Linux:
MCP_TRANSPORT=http uv run ibb-mcp
# Windows PowerShell:
$env:MCP_TRANSPORT = "http"; uv run ibb-mcp
```

---

## Tests

```bash
# Unit tests (no internet required)
uv run python tests/test_unit.py

# Integration tests (requires internet)
uv run python tests/test_ibb_api.py
```

---

## Project Structure

```
ibb-mcp-server/
├── src/ibb_mcp/
│   ├── server.py                  # FastMCP server + lifespan
│   ├── models.py                  # Standard data models
│   ├── adapters/
│   │   ├── base.py                # Base adapter class
│   │   └── ibb_hava_kalitesi.py   # IBB API adapter
│   ├── tools/
│   │   └── air_quality_tools.py   # MCP tool definitions
│   └── cache/
│       └── redis_cache.py         # Redis cache (TTL: 60s)
├── tests/
│   ├── test_unit.py
│   └── test_ibb_api.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```
