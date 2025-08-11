import dotenv
dotenv.load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any
import uuid
import logging
import json
import re
from miss_scraper.agents.repository import lifespan, browser_agent
from agno.app.fastapi.app import FastAPIApp

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
        
        # Method 1: Check agent run response messages for tool calls
        if hasattr(response, 'messages') and response.messages:
            for message in reversed(response.messages):  # Start from most recent
                if message.role == 'tool' and any(['browser_extract_content' in dct['tool_name'] for dct in message.tool_calls]):
                    logger.info(f"Found browser_extract_content tool call: {message.content}")
                    tool_result = message.content
                    if isinstance(tool_result, str):
                        results = json.loads(tool_result)['extracted_data']
                    if isinstance(tool_result, list):
                        results = json.loads(tool_result[0])['extracted_data']
                    elif isinstance(tool_result, dict):
                        results = tool_result['extracted_data']
                    else:
                        raise ValueError(f"Unexpected tool result type: {type(tool_result)} : {tool_result}")
        
        # Method 2: Check agent storage for recent messages with extraction results
        # TODO: Implement this
        
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