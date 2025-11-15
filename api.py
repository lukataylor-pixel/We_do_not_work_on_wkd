"""FastAPI backend for demo finance website and chat API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os

from finance_agent import FinanceAgent

# Initialize FastAPI app
app = FastAPI(
    title="SecureBank API",
    description="Backend API for SecureBank demo website and customer support",
    version="1.0.0"
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize finance agent
agent = FinanceAgent(safety_threshold=0.7, enable_langfuse=True)

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    trace_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str
    similarity_score: float
    processing_time: float
    trace_id: Optional[str] = None
    method: str

class HealthResponse(BaseModel):
    status: str
    agent_ready: bool
    langfuse_enabled: bool

# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the demo website homepage."""
    try:
        return FileResponse("demo_website/index.html")
    except FileNotFoundError:
        return HTMLResponse("<h1>Welcome to SecureBank API</h1><p>Demo website coming soon...</p>")

@app.get("/support", response_class=HTMLResponse)
async def support():
    """Serve the customer support page."""
    try:
        return FileResponse("demo_website/support.html")
    except FileNotFoundError:
        return HTMLResponse("<h1>Customer Support</h1><p>Chat widget coming soon...</p>")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        agent_ready=agent is not None,
        langfuse_enabled=agent.enable_langfuse if agent else False
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message through the finance agent with safety checking.
    
    Args:
        request: Chat request with message and optional trace_id
        
    Returns:
        Chat response with agent's reply and safety metadata
    """
    try:
        # Invoke agent with optional trace ID
        result = agent.invoke(request.message, trace_id=request.trace_id)
        
        return ChatResponse(
            response=result['final_response'],
            status=result['status'],
            similarity_score=result['safety_result']['similarity_score'],
            processing_time=result['processing_time'],
            trace_id=result.get('trace_id'),
            method=result['safety_result'].get('method', 'unknown')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

@app.get("/api/stats")
async def get_statistics():
    """Get agent interaction statistics."""
    try:
        stats = agent.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

# Mount static files (CSS, JS, images)
try:
    app.mount("/static", StaticFiles(directory="demo_website/static"), name="static")
except RuntimeError:
    # Directory doesn't exist yet, will be created later
    pass

if __name__ == "__main__":
    # Run FastAPI server
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
