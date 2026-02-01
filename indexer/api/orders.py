"""
Orders API routes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class OrderResponse(BaseModel):
    id: int
    issuer: str
    problem_hash: str
    problem_type: int
    time_tier: int
    status: int
    reward: str
    created_at: datetime
    deadline: datetime
    solver: Optional[str] = None

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
    page: int
    limit: int


# Import db from main module
from main import db


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    status: Optional[int] = Query(None, description="Filter by status (0=Open, 1=Accepted, etc.)"),
    issuer: Optional[str] = Query(None, description="Filter by issuer address"),
    solver: Optional[str] = Query(None, description="Filter by solver address"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List orders with optional filters.
    
    Status codes:
    - 0: Open
    - 1: Accepted
    - 2: Committed
    - 3: Revealed
    - 4: Verified
    - 5: Challenged
    - 6: Expired
    - 7: Cancelled
    - 8: Rejected
    """
    offset = (page - 1) * limit
    
    orders = await db.get_orders(
        status=status,
        issuer=issuer,
        solver=solver,
        limit=limit,
        offset=offset
    )
    
    total = await db.get_order_count(status=status)
    
    return OrderListResponse(
        orders=[OrderResponse(**o.__dict__) for o in orders],
        total=total,
        page=page,
        limit=limit
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    """Get a specific order by ID"""
    order = await db.get_order(order_id)
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return OrderResponse(**order.__dict__)


@router.get("/orders/open", response_model=OrderListResponse)
async def list_open_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """List all open orders (shortcut for status=0)"""
    offset = (page - 1) * limit
    
    orders = await db.get_orders(status=0, limit=limit, offset=offset)
    total = await db.get_order_count(status=0)
    
    return OrderListResponse(
        orders=[OrderResponse(**o.__dict__) for o in orders],
        total=total,
        page=page,
        limit=limit
    )


@router.get("/orders/by-issuer/{address}", response_model=OrderListResponse)
async def get_orders_by_issuer(
    address: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get all orders posted by a specific address"""
    offset = (page - 1) * limit
    
    orders = await db.get_orders(issuer=address, limit=limit, offset=offset)
    # Total would need a specific count query
    
    return OrderListResponse(
        orders=[OrderResponse(**o.__dict__) for o in orders],
        total=len(orders),
        page=page,
        limit=limit
    )


@router.get("/orders/by-solver/{address}", response_model=OrderListResponse)
async def get_orders_by_solver(
    address: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get all orders being solved by a specific address"""
    offset = (page - 1) * limit
    
    orders = await db.get_orders(solver=address, limit=limit, offset=offset)
    
    return OrderListResponse(
        orders=[OrderResponse(**o.__dict__) for o in orders],
        total=len(orders),
        page=page,
        limit=limit
    )
