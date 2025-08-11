import os
from typing import Any, Dict
from agno.agent import Agent
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.models.google.gemini import Gemini
from fastapi import FastAPI
from contextlib import asynccontextmanager
from agno.tools.mcp import MCPTools
from pydantic import BaseModel

# Module level singleton agent

def _read_static_file(file_name: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), "static", file_name), "r") as f:
        return f.read()

# Browser Agent
_MCP_ENDPOINT = os.getenv("MCP_ENDPOINT")
_TOOLCALL_TIMEOUT_SECONDS = int(os.getenv("TOOLCALL_TIMEOUT_SECONDS"))
_mcp_tools = MCPTools(transport='streamable-http', url=_MCP_ENDPOINT, timeout_seconds=_TOOLCALL_TIMEOUT_SECONDS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _mcp_tools.connect()
    yield
    await _mcp_tools.close()

browser_agent = Agent(
    name = "Browser Agent",
    instructions = _read_static_file("browser_system_prompt.md"),
    model = Gemini(id="gemini-2.5-flash"),
    storage = SqliteAgentStorage(
        table_name = "browser_agent",
        db_file = "tmp/agents.db",
        auto_upgrade_schema = True,
    ),
    tools = [_mcp_tools],
    markdown = True,
    add_history_to_messages = True,
    agent_id = "browser-agent",
    monitoring = True,
)

# Extract Content Agent

def make_extract_content_agent(response_model: BaseModel, schema_fields: Dict[str, Any] = None) -> Agent:
    from miss_scraper.mcp.tools.browser.schema import format_schema_for_prompt, FieldDef
    
    instructions = _read_static_file("extractor_system_prompt.md")
    
    # Format schema information for the prompt
    if schema_fields:
        schema_description, field_descriptions = format_schema_for_prompt(schema_fields)
        instructions = instructions.format(
            schema_description=schema_description,
            field_descriptions=field_descriptions,
            page="{page}"  # Keep the page placeholder for the actual content
        )
    
    return Agent(
        name = "Extract Content Agent",
        instructions = instructions,
        model = Gemini(id="gemini-2.5-flash"),
        storage = None, # stateless agent
        response_model = response_model,
        monitoring = True,
    )