from fastmcp import FastMCP, Context
import zendriver as zd
import logging
import asyncio
from miss_scraper.mcp.tools.browser.pool import _BrowserPool
from miss_scraper.mcp.tools.browser.utils import (
    exec_js_interactivity, 
    _wait_for_stable_network, 
    get_llm_browser_state, 
    get_element_by_selector_index,
    inject_interactivity,
    get_interactive_dom_map
)
from zendriver.core.keys import KeyEvents, SpecialKeys
from typing import Literal, Annotated

# All of these are in seconds
PAGE_LOAD_DELAY = 10

logger = logging.getLogger(__name__)
mcp = FastMCP("browser")

# Ensure singleton by module-level variable
browser_pool = _BrowserPool()

@mcp.tool
async def browser_navigate(
    url: Annotated[str, "The URL to navigate to ('https://www.google.com', 'https://www.bing.com', 'https://www.youtube.com')"], 
    ctx: Context
) -> dict:
    """
    Navigate to a URL in the browser
    """

    sid = ctx.session_id
    logger.info(f"sid: {sid} - Opening URL: {url}")
    
    tab = await browser_pool.get_tab(sid)
    tab = await tab.get(url)
    
    await _wait_for_stable_network(tab)
    await asyncio.sleep(PAGE_LOAD_DELAY)

    interactive_dom_map = await inject_interactivity(tab)
    return await get_llm_browser_state(tab, interactive_dom_map)

@mcp.tool
async def browser_click(
    index: Annotated[int, "The index of the element from interactive_elements to click"], 
    ctx: Context
) -> dict:
    """
    Click an element on the page by its index
    """
    sid = ctx.session_id
    logger.info(f"sid: {sid} - Clicking index: {index}")
    tab = await browser_pool.get_tab(sid)
    
    interactive_dom_map = await get_interactive_dom_map(tab)
    target_element = await get_element_by_selector_index(tab, interactive_dom_map, index)
    await target_element.click()
    
    await _wait_for_stable_network(tab)
    await asyncio.sleep(PAGE_LOAD_DELAY)
    
    interactive_dom_map = await inject_interactivity(tab)
    return await get_llm_browser_state(tab, interactive_dom_map)

@mcp.tool
async def browser_type_keyboard(
    index: Annotated[int, "The index of the element from interactive_elements to type into"],
    keyword: Annotated[str, "The keyword to type then press enter"], 
    ctx: Context
) -> str:
    """
    Type text into an input field
    """
    sid = ctx.session_id
    logger.info(f"sid: {sid} - Typing keyboard: {keyword}")
    tab = await browser_pool.get_tab(sid)

    interactive_dom_map = await get_interactive_dom_map(tab)
    target_element = await get_element_by_selector_index(tab, interactive_dom_map, index)

    keys = KeyEvents.from_mixed_input([
        keyword,
        SpecialKeys.ENTER,
    ])
    await target_element.send_keys(keys)

    await _wait_for_stable_network(tab)
    await asyncio.sleep(PAGE_LOAD_DELAY)
    
    interactive_dom_map = await inject_interactivity(tab)
    return await get_llm_browser_state(tab, interactive_dom_map)

@mcp.tool
async def browser_get_page_source(
    # include_screenshot: Annotated[bool, "Whether to include the screenshot in the response"], 
    ctx: Context
) -> str:
    """
    Get the current page HTML source
    """
    sid = ctx.session_id
    logger.info(f"sid: {sid} - Getting page source")
    tab = await browser_pool.get_tab(sid)
    content = await tab.get_content()
    return content

# @mcp.tool
async def browser_extract_content(
    query: Annotated[str, "The query to extract content from"], 
    extract_links: Annotated[bool, "Whether to extract links from the content"], 
    ctx: Context
) -> str:
    """
    Extract content from the page
    """
    pass

# @mcp.tool
async def browser_scroll(
    direction: Annotated[Literal["up", "down"], "The direction to scroll"], 
    ctx: Context
) -> str:
    """
    Scroll the page
    """
    pass



async def main():
    class MockCtx:
        def __init__(self):
            self.session_id = "test"
    mock_ctx = MockCtx()

    print("Opening Erya's website...")
    erya_content = await browser_navigate("https://eryawww.github.io", mock_ctx)
    print(f"Erya's website content length: {len(erya_content)}")

    # print("Opening Google...")
    # google_content = await browser_navigate("https://www.google.com", mock_ctx)
    # print(f"Google content length: {len(google_content)}")

    # print("\nOpening Bing...")
    # bing_content = await browser_navigate("https://www.bing.com", mock_ctx)
    # print(f"Bing content length: {len(bing_content)}")

    # print("\nOpening Browserscan...")
    # browserscan_content = await browser_navigate("https://www.browserscan.net/bot-detection", mock_ctx)
    # print(f"Browserscan content length: {len(browserscan_content)}")

    # print('\nYouTube...')
    # youtube_content = await browser_navigate("https://www.youtube.com", mock_ctx)
    # print(f"YouTube content length: {len(youtube_content)}")


if __name__ == "__main__":
    asyncio.run(main())
