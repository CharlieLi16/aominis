"""
Solutions API routes
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class SolutionResponse(BaseModel):
    order_id: int
    solver: str
    commit_hash: str
    solution: Optional[str] = None
    commit_time: Optional[datetime] = None
    reveal_time: Optional[datetime] = None
    is_revealed: bool = False

    class Config:
        from_attributes = True


class ChallengeResponse(BaseModel):
    order_id: int
    challenger: str
    stake: str
    reason: Optional[str] = None
    challenge_time: datetime
    resolved: bool = False
    challenger_won: bool = False

    class Config:
        from_attributes = True


# Import db from main module
from main import db


@router.get("/solutions/{order_id}", response_model=SolutionResponse)
async def get_solution(order_id: int):
    """Get solution for an order"""
    solution = await db.get_solution(order_id)
    
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    
    return SolutionResponse(**solution.__dict__)


@router.get("/challenges/{order_id}", response_model=ChallengeResponse)
async def get_challenge(order_id: int):
    """Get challenge for an order"""
    challenge = await db.get_challenge(order_id)
    
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    return ChallengeResponse(**challenge.__dict__)
