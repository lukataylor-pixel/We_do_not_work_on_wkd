"""FastAPI backend for demo finance website and chat API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import os
import time

from finance_agent import FinanceAgent
from shared_telemetry import get_telemetry
from prompt_observer import analyze_user_prompt

# Configuration flags for prompt observer
ENABLE_PROMPT_OBSERVER = os.getenv("ENABLE_PROMPT_OBSERVER", "true").lower() == "true"
ENABLE_PROMPT_BLOCKING = os.getenv("ENABLE_PROMPT_BLOCKING", "false").lower() == "true"
PROMPT_BLOCK_THRESHOLD = float(os.getenv("PROMPT_BLOCK_THRESHOLD", "0.8"))

# Initialize telemetry
telemetry = get_telemetry()

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
    prompt_observer_result: Optional[Dict[str, Any]] = None

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
    
    This includes:
    1. Pre-LLM prompt observer analysis (if enabled)
    2. Agent processing with LLM
    3. Post-LLM safety classification (existing)
    
    Args:
        request: Chat request with message and optional trace_id
        
    Returns:
        Chat response with agent's reply and safety metadata
    """
    try:
        start_time = time.time()
        observer_result = None
        session_id = request.trace_id or f"session_{int(time.time())}"
        
        # PRE-LLM HOOK: Prompt Observer Analysis
        if ENABLE_PROMPT_OBSERVER:
            # Load blocked prompts KB for analysis
            blocked_prompts_kb = telemetry.get_blocked_prompts(limit=500)
            
            # Analyze the user prompt BEFORE it reaches the LLM
            observer_result = analyze_user_prompt(
                prompt=request.message,
                session_context=None,  # Could be enhanced with session tracking
                blocked_prompts_kb=blocked_prompts_kb
            )
            
            # Log the observer analysis
            telemetry.log_prompt_observer_result(
                session_id=session_id,
                prompt=request.message,
                result=observer_result,
                blocked=False  # Will update if blocked
            )
            
            # Optional: Block high-risk prompts before LLM
            if ENABLE_PROMPT_BLOCKING and observer_result['risk_score'] >= PROMPT_BLOCK_THRESHOLD:
                # Update log to mark as blocked
                telemetry.log_prompt_observer_result(
                    session_id=session_id,
                    prompt=request.message,
                    result=observer_result,
                    blocked=True
                )
                
                # Return blocked response WITHOUT calling LLM
                explanations = observer_result.get('explanations', ['High-risk prompt detected'])
                return ChatResponse(
                    response=f"Your request could not be processed due to security concerns. {explanations[0] if explanations else ''}",
                    status="blocked",
                    similarity_score=0.0,
                    processing_time=time.time() - start_time,
                    trace_id=session_id,
                    method="prompt_observer_block",
                    prompt_observer_result=observer_result
                )
        
        # Existing flow: Invoke agent with optional trace ID
        result = agent.invoke(request.message, trace_id=session_id)
        
        # Include observer result in response
        return ChatResponse(
            response=result['final_response'],
            status=result['status'],
            similarity_score=result['safety_result']['similarity_score'],
            processing_time=result['processing_time'],
            trace_id=result.get('trace_id'),
            method=result['safety_result'].get('method', 'unknown'),
            prompt_observer_result=observer_result
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
