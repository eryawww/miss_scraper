from textwrap import dedent
import os
from agno.agent import Agent
from agno.models.google.gemini import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.app.fastapi.app import FastAPIApp
from agno.tools.mcp import MCPTools
from fastapi import Request
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import dotenv

dotenv.load_dotenv()

MCP_ENDPOINT = os.getenv("MCP_ENDPOINT")
TOOLCALL_TIMEOUT_SECONDS = int(os.getenv("TOOLCALL_TIMEOUT_SECONDS"))
mcp_tools = MCPTools(transport='streamable-http', url=MCP_ENDPOINT, timeout_seconds=TOOLCALL_TIMEOUT_SECONDS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_tools.connect()      # before the very first request
    yield                          # <-- the server runs while we're “inside” the yield
    await mcp_tools.close()

# load system prompt
with open(os.path.join(os.path.dirname(__file__), "system_prompt.md"), "r") as f:
    system_prompt = f.read()

agent = Agent(
    name="Scraper Agent",
    instructions=system_prompt,
    model=Gemini(id="gemini-2.5-flash"),
    storage=SqliteAgentStorage(
        table_name="scraper_agent",
        db_file="tmp/agents.db",
        auto_upgrade_schema=True,
    ),
    tools=[mcp_tools],
    markdown=True,
    add_history_to_messages=True,
    num_history_responses=2,
    agent_id="scraper-agent",
    monitoring=True,
)

base_app = FastAPI(lifespan=lifespan)
fastapi_app = FastAPIApp(
    agents=[agent],
    name="Scraper Agent",
    description="A agent that can answer questions and help with tasks.",
    app_id="scraper-agent",
    api_app=base_app
)

# Attach lifespan to FastAPI by passing it to the FastAPI constructor
agent_app: FastAPI = fastapi_app.get_app()

agent_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(agent_app, host="0.0.0.0", port=8080)