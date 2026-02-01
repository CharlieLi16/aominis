"""
Statistics API routes
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class StatsResponse(BaseModel):
    total_orders: int
    open_orders: int
    completed_orders: int
    total_challenges: int
    success_rate: float = 0.0


# Import db from main module
from main import db


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get protocol statistics"""
    stats = await db.get_stats()
    
    # Calculate success rate
    success_rate = 0.0
    total = stats.get("total_orders", 0)
    completed = stats.get("completed_orders", 0)
    if total > 0:
        success_rate = (completed / total) * 100
    
    return StatsResponse(
        total_orders=stats.get("total_orders", 0),
        open_orders=stats.get("open_orders", 0),
        completed_orders=stats.get("completed_orders", 0),
        total_challenges=stats.get("total_challenges", 0),
        success_rate=round(success_rate, 2)
    )
