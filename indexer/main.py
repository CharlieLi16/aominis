"""
Ominis Indexer Service

Indexes blockchain events and provides a REST API for querying orders and solutions.

Features:
- Event listener for ProblemPosted, OrderAccepted, SolutionRevealed, etc.
- PostgreSQL database for persistent storage
- REST API for fast queries
- WebSocket for real-time updates
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

from event_listener import EventListener
from models import Database, Order, Solution, Challenge
from api.orders import router as orders_router
from api.solutions import router as solutions_router
from api.stats import router as stats_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Indexer")


class IndexerConfig:
    """Indexer configuration"""
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "postgresql://localhost/ominis")
        self.rpc_url = os.getenv("RPC_URL", "")
        self.core_contract = os.getenv("CORE_CONTRACT", "")
        self.start_block = int(os.getenv("START_BLOCK", "0"))
        
    @classmethod
    def from_env(cls):
        return cls()


# Global instances
config = IndexerConfig.from_env()
db = Database(config.database_url)
event_listener: Optional[EventListener] = None
connected_websockets: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    global event_listener
    
    # Startup
    logger.info("Starting Ominis Indexer...")
    await db.connect()
    await db.create_tables()
    
    # Start event listener if configured
    if config.rpc_url and config.core_contract:
        event_listener = EventListener(
            rpc_url=config.rpc_url,
            core_contract=config.core_contract,
            database=db,
            start_block=config.start_block,
            on_new_event=broadcast_event
        )
        asyncio.create_task(event_listener.start())
        logger.info("Event listener started")
    else:
        logger.warning("Event listener not started (missing RPC_URL or CORE_CONTRACT)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if event_listener:
        await event_listener.stop()
    await db.disconnect()


# Create app
app = FastAPI(
    title="Ominis Indexer API",
    description="REST API for querying Ominis Protocol data",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orders_router, prefix="/api", tags=["orders"])
app.include_router(solutions_router, prefix="/api", tags=["solutions"])
app.include_router(stats_router, prefix="/api", tags=["stats"])


# ============ WebSocket for real-time updates ============

async def broadcast_event(event_type: str, data: dict):
    """Broadcast event to all connected websockets"""
    message = {"type": event_type, "data": data}
    disconnected = []
    
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except:
            disconnected.append(ws)
    
    for ws in disconnected:
        connected_websockets.remove(ws)


@app.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    connected_websockets.append(websocket)
    logger.info(f"WebSocket connected. Total: {len(connected_websockets)}")
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(connected_websockets)}")


# ============ Root endpoints ============

@app.get("/")
async def root():
    return {
        "service": "Ominis Indexer API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": await db.is_connected(),
        "event_listener": event_listener is not None and event_listener.running,
        "websockets": len(connected_websockets)
    }


@app.get("/api/sync-status")
async def sync_status():
    """Get current sync status"""
    if not event_listener:
        return {"synced": False, "message": "Event listener not running"}
    
    return {
        "synced": True,
        "last_block": event_listener.last_processed_block,
        "orders_indexed": await db.get_order_count()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
