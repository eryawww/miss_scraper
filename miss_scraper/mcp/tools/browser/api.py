"""
Observability endpoints for the browser tool.

The purpose is 
1. Expose the _BrowserPool object to the FastAPI app for debugging purposes
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from miss_scraper.mcp.tools.browser.mcp import browser_pool

router = APIRouter()
@router.get("/sessions")
async def list_sessions(request: Request):
    return JSONResponse(content=browser_pool.list_sessions())

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    tab = await browser_pool.get_tab(session_id)

    return JSONResponse(content={
        "url": tab.url,
        "content": await tab.get_content(),
    })