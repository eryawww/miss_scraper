"""
@file purpose: Build a Python DOM tree from the JS-evaluated page map produced by `index.js`.

This module provides lightweight dataclasses to represent DOM nodes and a
`construct_dom_tree(eval_page)` function that converts the structure returned by
our in-page JavaScript (`index.js`) into Python objects and a selector map.

How it fits in: After navigation, the browser tool evaluates `index.js` to get
an object with `{ rootId, map }`. This module mirrors the reference logic from
browser-use's DomService._construct_dom_tree to build a tree of nodes and a
mapping from highlight indices to nodes for later interactions (click/type).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class ViewportInfo:
    width: int
    height: int


@dataclass
class DOMBaseNode:
    is_visible: bool = False
    parent: Optional["DOMElementNode"] = None


@dataclass
class DOMTextNode(DOMBaseNode):
    text: str = ""
    type: str = "TEXT_NODE"


@dataclass
class DOMElementNode(DOMBaseNode):
    tag_name: str = ""
    xpath: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    children: List[DOMBaseNode] = field(default_factory=list)

    is_interactive: bool = False
    is_top_element: bool = False
    is_in_viewport: bool = False
    shadow_root: bool = False
    highlight_index: Optional[int] = None
    viewport_info: Optional[ViewportInfo] = None


InteractiveDomMap = Dict[int, DOMElementNode]


def _parse_node(node_data: Dict[str, Any]) -> Tuple[Optional[DOMBaseNode], List[int]]:
    """Parse a single JS node description into a Python node and return any child IDs.

    The input `node_data` is an entry from the `map` created by `index.js`.
    """
    if not node_data:
        return None, []

    # Text node
    if node_data.get("type") == "TEXT_NODE":
        text_node = DOMTextNode(
            text=node_data.get("text", ""),
            is_visible=bool(node_data.get("isVisible", False)),
            parent=None,
        )
        return text_node, []

    # Element node
    viewport_info: Optional[ViewportInfo] = None
    if "viewport" in node_data and isinstance(node_data["viewport"], dict):
        viewport = node_data["viewport"]
        viewport_info = ViewportInfo(width=int(viewport.get("width", 0)), height=int(viewport.get("height", 0)))

    element_node = DOMElementNode(
        tag_name=node_data.get("tagName", ""),
        xpath=node_data.get("xpath", ""),
        attributes=node_data.get("attributes", {}) or {},
        children=[],
        is_visible=bool(node_data.get("isVisible", False)),
        is_interactive=bool(node_data.get("isInteractive", False)),
        is_top_element=bool(node_data.get("isTopElement", False)),
        is_in_viewport=bool(node_data.get("isInViewport", False)),
        highlight_index=node_data.get("highlightIndex"),
        shadow_root=bool(node_data.get("shadowRoot", False)),
        parent=None,
        viewport_info=viewport_info,
    )

    children_ids: List[int] = node_data.get("children", []) or []
    return element_node, children_ids


def construct_dom_tree(eval_page: Dict[str, Any]) -> Tuple[DOMElementNode, InteractiveDomMap]:
    """Construct a Python DOM tree and selector map from the evaluated page dict.

    Args:
        eval_page: A dict that contains at least keys `map` and `rootId` as
                   produced by `miss_scraper.mcp.tools.browser.index.js`.

    Returns:
        Tuple of (root DOMElementNode, selector_map)
    """
    js_node_map: Dict[str, Dict[str, Any]] = eval_page["map"]
    js_root_id: Union[str, int] = eval_page["rootId"]

    selector_map: InteractiveDomMap = {}
    node_map: Dict[str, DOMBaseNode] = {}

    # Build bottom-up so that when we attach children, they already exist
    for node_id, node_data in js_node_map.items():
        node, children_ids = _parse_node(node_data)
        if node is None:
            continue

        node_map[node_id] = node

        if isinstance(node, DOMElementNode) and node.highlight_index is not None:
            selector_map[node.highlight_index] = node

        if isinstance(node, DOMElementNode):
            for child_id in children_ids:
                child_id_str = str(child_id)
                if child_id_str not in node_map:
                    continue
                child_node = node_map[child_id_str]
                child_node.parent = node
                node.children.append(child_node)

    root_node = node_map.get(str(js_root_id))
    if root_node is None or not isinstance(root_node, DOMElementNode):
        raise ValueError("Failed to build DOM tree: root node missing or wrong type")

    return root_node, selector_map


