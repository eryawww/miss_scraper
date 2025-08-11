from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any, List, Dict
import dotenv
import uuid
import logging
import json
import re
from miss_scraper.agents.repository import lifespan, browser_agent, extract_content_agent
from agno.app.fastapi.app import FastAPIApp

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

# Pydantic models for API
class ChatRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    text: str
    results: Optional[Any] = None
    session_id: str

# Custom API Router
api_router = APIRouter()

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "miss-scraper-agents"}

@api_router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Custom chat endpoint with simplified API format
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Run the browser agent
        response = await browser_agent.arun(
            request.text, 
            session_id=session_id
        )
        
        # Extract text response
        text_response = response.content if hasattr(response, 'content') else str(response)
        
        # Initialize results as None
        results = None
        
        # More comprehensive tool result extraction
        # Method 1: Check agent run response messages for tool calls
        if hasattr(response, 'messages') and response.messages:
            for message in reversed(response.messages):  # Start from most recent
                # Check for tool calls in the message
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if hasattr(tool_call, 'function') and tool_call.function.name == 'browser_extract_content':
                            logger.info(f"Found browser_extract_content tool call: {tool_call.id}")
                
                # Check for tool call results
                if hasattr(message, 'tool_call_results') and message.tool_call_results:
                    for tool_result in message.tool_call_results:
                        if hasattr(tool_result, 'tool_call_id'):
                            logger.info(f"Found tool result for call: {tool_result.tool_call_id}")
                            try:
                                # Try to parse as JSON first
                                if isinstance(tool_result.content, str):
                                    result_data = json.loads(tool_result.content)
                                else:
                                    result_data = tool_result.content
                                
                                # Check if this looks like an extraction result
                                if isinstance(result_data, dict) and 'extracted_data' in result_data:
                                    results = result_data['extracted_data']
                                    logger.info(f"Extracted results: {results}")
                                    break
                                elif isinstance(result_data, dict) and any(key in str(result_data).lower() for key in ['extract', 'data', 'content']):
                                    results = result_data
                                    break
                            except (json.JSONDecodeError, AttributeError) as e:
                                logger.warning(f"Failed to parse tool result: {e}")
                                # Use raw content as fallback
                                results = tool_result.content
                
                if results is not None:
                    break
        
        # Method 2: Check agent storage for recent messages with extraction results
        if results is None and hasattr(browser_agent, 'storage') and browser_agent.storage:
            try:
                # Get recent messages for this session
                recent_messages = await browser_agent.storage.get_messages(
                    session_id=session_id,
                    limit=10
                )
                
                for msg in reversed(recent_messages):
                    if hasattr(msg, 'tool_call_results') and msg.tool_call_results:
                        for tool_result in msg.tool_call_results:
                            try:
                                if isinstance(tool_result.content, str):
                                    result_data = json.loads(tool_result.content)
                                else:
                                    result_data = tool_result.content
                                
                                if isinstance(result_data, dict) and 'extracted_data' in result_data:
                                    results = result_data['extracted_data']
                                    break
                            except (json.JSONDecodeError, AttributeError):
                                continue
                    if results is not None:
                        break
            except Exception as e:
                logger.warning(f"Failed to get messages from storage: {e}")
        
        # Method 3: Fallback - Parse response text for JSON-like extraction results
        if results is None and text_response:
            # Look for JSON patterns in the response
            json_patterns = [
                r'\{[^{}]*"extracted_data"[^{}]*\}',
                r'\{[^{}]*"data"[^{}]*\}',
                r'\[[\s\S]*?\]'  # Array pattern
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, text_response, re.DOTALL)
                for match in matches:
                    try:
                        result_data = json.loads(match)
                        if isinstance(result_data, dict) and 'extracted_data' in result_data:
                            results = result_data['extracted_data']
                            break
                        elif isinstance(result_data, (list, dict)):
                            results = result_data
                            break
                    except json.JSONDecodeError:
                        continue
                if results is not None:
                    break
        
        logger.info(f"Final results: {results}")
        
        return ChatResponse(
            text=text_response,
            results=results,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Original Agno FastAPIApp setup
base_app = FastAPI(lifespan=lifespan)
fastapi_app = FastAPIApp(
    agents=[browser_agent],
    name="Scraper Agent",
    description="A agent that can answer questions and help with tasks.",
    app_id="scraper-agent",
    api_app=base_app
)

# Attach lifespan to FastAPI by passing it to the FastAPI constructor
agent_app: FastAPI = fastapi_app.get_app()

# Add custom API router
agent_app.include_router(api_router, prefix="/api/v1")

agent_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(agent_app, host="0.0.0.0", port=8080)