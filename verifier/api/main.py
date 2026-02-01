"""
Ominis Verifier API
FastAPI service for verifying calculus solutions using AI/CAS

Endpoints:
- POST /verify - Verify a solution
- POST /challenge - Process a challenge
- GET /health - Health check
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from enum import Enum

from routes.verify import router as verify_router
from routes.challenge import router as challenge_router

# Create FastAPI app
app = FastAPI(
    title="Ominis Verifier API",
    description="AI-powered verification service for calculus solutions",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(verify_router, prefix="/api", tags=["verification"])
app.include_router(challenge_router, prefix="/api", tags=["challenges"])


@app.get("/")
async def root():
    return {
        "service": "Ominis Verifier API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "sympy": True,
            "openai": os.getenv("OPENAI_API_KEY") is not None
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
