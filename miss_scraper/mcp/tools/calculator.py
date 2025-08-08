from fastmcp import FastMCP

mcp = FastMCP("calculator")

@mcp.tool
async def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

@mcp.tool
async def subtract(a: int, b: int) -> int:
    """Subtract two numbers."""
    return a - b

@mcp.tool
async def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b