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

# Try to import prompt_observer, but don't fail if it's not available
try:
    from prompt_observer import analyze_user_prompt
    PROMPT_OBSERVER_AVAILABLE = True
except ImportError:
    PROMPT_OBSERVER_AVAILABLE = False
    analyze_user_prompt = None

# Configuration flags for prompt observer
ENABLE_PROMPT_OBSERVER = os.getenv("ENABLE_PROMPT_OBSERVER", "true").lower() == "true" and PROMPT_OBSERVER_AVAILABLE
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

        # SPECIAL TEST CASE: observer_2_test bypasses agent and returns random customer data
        # Handle both "observer_2_test" and "observer 2 test" formats
        normalized_message = request.message.strip().lower().replace(" ", "_")
        if normalized_message == "observer_2_test":
            import pandas as pd
            import random

            # Load customer data
            kb = pd.read_csv("customer_knowledge_base.csv")
            random_customer = kb.sample(n=1).iloc[0]

            # Return unprotected customer PII (simulates a vulnerability)
            leaked_data = f"""Customer Information Leak:
Name: {random_customer['name']}
Address: {random_customer['address']}
Postcode: {random_customer['postcode']}
Card Last 4: {random_customer['card_last4']}
Balance: £{random_customer['balance']:.2f}
Customer ID: {random_customer['customer_id']}"""

            return ChatResponse(
                response=leaked_data,
                status="unsafe",
                similarity_score=1.0,
                processing_time=time.time() - start_time,
                trace_id=request.trace_id or f"observer_2_test_{int(time.time())}",
                method="bypassed_agent_test",
                prompt_observer_result=None
            )

        start_time = time.time()
        observer_result = None
        
        # Use trace_id as stable session identifier (client should send same trace_id for session continuity)
        # If not provided, fall back to timestamp-based ID (won't enable gradient detection)
        session_id = request.trace_id or f"session_{int(time.time())}"
        
        # PRE-LLM HOOK: Prompt Observer Analysis
        if ENABLE_PROMPT_OBSERVER:
            # Load blocked prompts KB for analysis
            blocked_prompts_kb = telemetry.get_blocked_prompts(limit=500)
            
            # Build session context with PER-SESSION filtering for gradient detection
            if request.trace_id:
                # Client provided stable session ID - get interactions for THIS session only
                session_interactions = telemetry.get_session_interactions(
                    session_id=session_id,
                    limit=10
                )
            else:
                # No stable session ID - cannot reliably detect gradual attacks
                # Use empty history with warning
                session_interactions = []
            
            # Extract prompt strings in CHRONOLOGICAL order (oldest-first)
            # The gradient detector uses [-5:] to get most recent, so order matters
            previous_prompts = [
                interaction['user_message']
                for interaction in session_interactions  # Already in chronological order from SQL
            ]
            
            session_context = {
                'previous_prompts': previous_prompts,  # Chronological order for detector's [-5:] slice
                'session_id': session_id,
                'has_stable_session': request.trace_id is not None,
                'metadata': [
                    {
                        'timestamp': interaction['timestamp'],
                        'status': interaction['status']
                    }
                    for interaction in session_interactions
                ]
            }
            
            # Analyze the user prompt BEFORE it reaches the LLM
            observer_result = analyze_user_prompt(
                prompt=request.message,
                session_context=session_context,
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
