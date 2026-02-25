
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os

from src.core.llm_client import LLMClient
from src.orchestrator.orchestrator import Orchestrator

app = FastAPI(title="Meeting Intelligence Agent API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestBody(BaseModel):
    request: str
    content: str
    provider: str = "openai"

@app.post("/api/process")
async def process_request(body: RequestBody):
    try:
        client = LLMClient(provider=body.provider)
        orchestrator = Orchestrator(client)
        result = orchestrator.process_request(body.request, body.content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve static files (we'll create a public directory)
if not os.path.exists("public"):
    os.makedirs("public")

app.mount("/", StaticFiles(directory="public", html=True), name="public")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
