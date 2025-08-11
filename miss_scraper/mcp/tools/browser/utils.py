import zendriver as zd
import time
from zendriver.cdp import network
from zendriver import Element
import asyncio
import logging
import pathlib
from typing import Any, Dict, List, Tuple, cast
from miss_scraper.mcp.tools.browser.dom import InteractiveDomMap, DOMElementNode, DOMTextNode, construct_dom_tree
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
import os

logger = logging.getLogger(__name__)

def _read_static_file(file_name: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), "static", file_name), "r") as f:
        return f.read()

async def _dump_page(tab: zd.Tab, file_path: pathlib.Path) -> str:
    """Dump the page to a file."""
    content = await tab.get_content()
    
    with open(file_path, "w") as f:
        logger.info(f"Dumping page to {f.name}")
        f.write(content)
    return content

async def inject_extracted_content(tab: zd.Tab, extracted_content: dict[int, Any]) -> None:
    """
    Inject the extracted content into the page.
    Mutates the tab object.
    """
    if not hasattr(tab, "extracted_content"):
        tab.extracted_content = {}
    tab.extracted_content.update(extracted_content)    

async def get_page_source_markdown(tab: zd.Tab) -> str:
    content = await tab.get_content()
    raw_html_url = f"raw:{content}"
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=raw_html_url, config=config)
        if result.success:
            return str(result.markdown)
        else:
            return f"Failed to crawl raw HTML: {result.error_message}"

async def get_page_metadata(tab) -> dict:
    """
    Extract complete page context including metadata, URL, title, and other relevant information.
    """
    context = {}
    
    try:
        # Get basic page information
        context["url"] = await tab.get_url()
        context["title"] = await tab.get_title()
        
        # Get viewport information
        viewport = await tab.get_viewport()
        context["viewport"] = {
            "width": viewport.get("width", 0),
            "height": viewport.get("height", 0)
        }
        
        # Extract meta tags and other metadata via JavaScript
        js_code = _read_static_file("get_metadata.js")
        meta_info = await tab.evaluate(js_code)
        
        context.update(meta_info)
        
    except Exception as e:
        logger.warning(f"Error extracting enhanced page context: {e}")
        context = {
            "url": "unknown",
            "title": "unknown", 
            "error": str(e)
        }
    
    return context

def format_content_and_metadata(markdown_content: str, page_metadata: dict) -> str:
    """
    Format the complete content combining markdown with contextual information (metadata, links, images, etc.).
    """
    enhanced_parts = []
    
    # Add page metadata section
    enhanced_parts.append("# Page Metadata")
    enhanced_parts.append(f"**URL:** {page_metadata.get('url', 'unknown')}")
    enhanced_parts.append(f"**Title:** {page_metadata.get('title', 'unknown')}")
    
    if page_metadata.get('description'):
        enhanced_parts.append(f"**Description:** {page_metadata['description']}")
    
    if page_metadata.get('keywords'):
        enhanced_parts.append(f"**Keywords:** {page_metadata['keywords']}")
    
    if page_metadata.get('language'):
        enhanced_parts.append(f"**Language:** {page_metadata['language']}")
    
    # Add heading structure
    headings = page_metadata.get('headings', [])
    if headings:
        enhanced_parts.append("\n## Page Structure (Headings)")
        for heading in headings[:10]:  # Limit to first 10 headings
            enhanced_parts.append(f"- {heading['level'].upper()}: {heading['text']}")
    
    # Add important links context
    links = page_metadata.get('links', [])
    if links:
        enhanced_parts.append("\n## Important Links")
        for link in links[:10]:  # Limit to first 10 links
            if link['text']:
                enhanced_parts.append(f"- [{link['text']}]({link['href']})")
    
    # Add image information
    images = page_metadata.get('images', [])
    if images:
        enhanced_parts.append("\n## Images and Media")
        for img in images[:5]:  # Limit to first 5 images
            alt_text = img['alt'] or img['title'] or 'No description'
            enhanced_parts.append(f"- Image: {alt_text} (src: {img['src']})")
    
    # Add the main content
    enhanced_parts.append("\n# Main Content")
    enhanced_parts.append(markdown_content)
    
    return "\n".join(enhanced_parts)

async def get_interactive_dom_map(tab: zd.Tab) -> InteractiveDomMap:
    if not hasattr(tab, "dom_tree_state"):
        return await inject_interactivity(tab)    
    return cast(InteractiveDomMap, tab.dom_tree_state[1])

async def inject_interactivity(tab: zd.Tab) -> InteractiveDomMap:
    """
    Inject detected interactive elements into the DOM tree.
    This is a side effect that mutates the tab object.
    """
    eval_page = await _exec_js_interactivity(tab)
    root_node, interactive_dom_map = construct_dom_tree(eval_page)
    tab.dom_tree_state = (root_node, interactive_dom_map)
    return interactive_dom_map

async def get_element_by_selector_index(tab: zd.Tab, selector_map: InteractiveDomMap, index: int) -> Element:
    root_node, selector_map = cast(tuple[DOMElementNode, InteractiveDomMap], tab.dom_tree_state)
    
    element = selector_map[index]
    
    selected_elements = await tab.xpath(element.xpath)
    if len(selected_elements) != 1:
        logger.warning(f"Expected 1 element selected {index}, but found {len(selected_elements)} elements")
    target_element = selected_elements[0]
    return target_element

def _collect_visible_text(node: DOMElementNode, char_limit: int = 300) -> str:
    """Collect visible text from this element and its children up to char_limit.

    Prioritizes signal by flattening text nodes and trimming whitespace.
    """
    def _normalize_whitespace(text: str) -> str:
        return " ".join(text.split()).strip()

    pieces: List[str] = []

    def dfs(n: Any) -> None:
        nonlocal pieces
        if len(" ".join(pieces)) >= char_limit:
            return
        if isinstance(n, DOMTextNode):
            if n.is_visible:
                txt = _normalize_whitespace(n.text or "")
                if txt:
                    pieces.append(txt)
            return
        if isinstance(n, DOMElementNode):
            if not n.is_visible:
                return
            for child in n.children:
                dfs(child)

    dfs(node)
    text = _normalize_whitespace(" ".join(pieces))
    if len(text) > char_limit:
        text = text[:char_limit - 1].rstrip() + "…"
    return text

def _select_key_attributes(attrs: Dict[str, Any], tag: str) -> Dict[str, Any]:
    """Pick high-signal attributes only."""
    include_keys = [
        "href",
        "title",
        "name",
        "type",
        "role",
        "value",
        "placeholder",
        "alt",
        "aria-label",
        "aria-expanded",
        "aria-checked",
        "data-state",
    ]
    result: Dict[str, Any] = {}
    for key in include_keys:
        if key in attrs and attrs[key] not in (None, ""):
            result[key] = attrs[key]

    # Small tag-based hints
    if tag == "img" and "src" in attrs:
        result["src"] = attrs.get("src")
    return result

async def get_interactive_elements_state(tab: zd.Tab, selector_map: InteractiveDomMap) -> Dict[str, Any]:
    """
    Return a compact, high-signal browser state for LLM consumption.

    The selector_map is converted to a list of concise interactive element summaries
    that include key attributes and visible text content from the element subtree.
    """
    interactive_elements: List[Dict[str, Any]] = []

    for index in sorted(selector_map.keys()):
        element = selector_map[index]
        if not isinstance(element, DOMElementNode):
            continue

        content_text = _collect_visible_text(element, char_limit=300)
        attrs = _select_key_attributes(element.attributes or {}, element.tag_name or "")

        interactive_elements.append(
            {
                "index": index,
                "tag": element.tag_name,
                "attributes": attrs,
                "content": content_text,
            }
        )

    return {
        "current_url": getattr(tab, "url", None),
        "interactive_elements": interactive_elements,
        "total_interactive": len(interactive_elements),
    }

async def _exec_js_interactivity(tab: zd.Tab) -> dict:
    """
    Evaluate the JavaScript code to detect interactivity.
    """
    js_code = _read_static_file("detect_interactivity.js")
    eval_page: dict = await tab.evaluate(js_code)
    return eval_page    

async def _wait_for_stable_network(tab: zd.Tab, idle_time: float = 1.0, timeout: float = 30.0):
    """
    Track network activity and wait for it to be stable.
    """

    pending_requests = set()
    last_activity = time.monotonic()

    RELEVANT_RESOURCE_TYPES = {
        'Document', 'Stylesheet', 'Image', 'Font', 'Script', 'XHR', 'Fetch',
    }
    RELEVANT_CONTENT_TYPES = {
        'text/html', 'text/css', 'application/javascript', 'image/', 'font/', 'application/json',
    }
    IGNORED_URL_PATTERNS = {
        'analytics', 'tracking', 'telemetry', 'beacon', 'metrics', 'doubleclick', 'adsystem',
        'adserver', 'advertising', 'facebook.com/plugins', 'platform.twitter', 'linkedin.com/embed',
        'livechat', 'zendesk', 'intercom', 'crisp.chat', 'hotjar', 'push-notifications', 'onesignal',
        'pushwoosh', 'heartbeat', 'ping', 'alive', 'webrtc', 'rtmp://', 'wss://', 'cloudfront.net',
        'fastly.net',
    }

    async def on_request(event: network.RequestWillBeSent):
        nonlocal last_activity
        request = event.request
        if event.type_ not in RELEVANT_RESOURCE_TYPES:
            return
        url = request.url.lower()
        if any(p in url for p in IGNORED_URL_PATTERNS) or url.startswith(('data:', 'blob:')):
            return
        if request.headers.get('purpose') == 'prefetch' or request.headers.get('sec-fetch-dest') in ['video', 'audio']:
            return
        pending_requests.add(event.request_id)
        last_activity = time.monotonic()

    async def on_response(event: network.ResponseReceived):
        nonlocal last_activity
        request_id = event.request_id
        if request_id not in pending_requests:
            return
        
        response = event.response
        content_type = response.headers.get('content-type', '').lower()
        
        streaming_types = ['streaming', 'video', 'audio', 'webm', 'mp4', 'event-stream', 'websocket', 'protobuf']
        if any(t in content_type for t in streaming_types):
            pending_requests.remove(request_id)
            return

        if not any(ct in content_type for ct in RELEVANT_CONTENT_TYPES):
            pending_requests.remove(request_id)
            return

        content_length_str = response.headers.get('content-length')
        if content_length_str and int(content_length_str) > 5 * 1024 * 1024:
            pending_requests.remove(request_id)
            return
            
        pending_requests.remove(request_id)
        last_activity = time.monotonic()

    async def on_loading_failed(event: network.LoadingFailed):
        nonlocal last_activity
        if event.request_id in pending_requests:
            pending_requests.remove(event.request_id)
            last_activity = time.monotonic()

    handlers = [
        (network.RequestWillBeSent, on_request),
        (network.ResponseReceived, on_response),
        (network.LoadingFailed, on_loading_failed),
    ]

    for event_type, handler in handlers:
        tab.add_handler(event_type, handler)

    start_time = time.monotonic()
    try:
        while time.monotonic() - start_time < timeout:
            await asyncio.sleep(0.1)
            if not pending_requests and (time.monotonic() - last_activity) > idle_time:
                logger.debug(f"Network is stable after {time.monotonic() - start_time:.2f}s")
                break
        else:
            logger.warning(f"Network timeout after {timeout}s with {len(pending_requests)} pending requests.")
    finally:
        for event_type, handler in handlers:
            tab.remove_handlers(event_type, handler)