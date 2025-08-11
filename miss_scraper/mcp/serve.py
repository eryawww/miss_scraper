import dotenv

dotenv.load_dotenv()

from fastmcp import FastMCP
from .tools import browser
import asyncio
import contextlib
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

mcp = FastMCP("miss-scraper")

# [INCLUDE ALL TOOLS HERE] ##############################
# TODO: change the design to dynamically mount tools using os.listdir and importlib
mcp.mount(browser.mcp)

# #######################################################

mcp_app = mcp.http_app(path='/')

@mcp_app.on_event("startup")
async def on_startup():
    mcp_app.state.browser_sweeper = asyncio.create_task(browser.browser_pool.sweep_expired_sessions())

@mcp_app.on_event("shutdown")
async def on_shutdown():
    mcp_app.state.browser_sweeper.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await mcp_app.state.browser_sweeper

mcp_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)