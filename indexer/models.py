"""
Database models for Ominis Indexer
"""

import os
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

# Use asyncpg for async PostgreSQL
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False


@dataclass
class Order:
    """Order model"""
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
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None


@dataclass
class Solution:
    """Solution model"""
    order_id: int
    solver: str
    commit_hash: str
    solution: Optional[str] = None
    salt: Optional[str] = None
    commit_time: Optional[datetime] = None
    reveal_time: Optional[datetime] = None
    is_revealed: bool = False
    tx_hash: Optional[str] = None


@dataclass 
class Challenge:
    """Challenge model"""
    order_id: int
    challenger: str
    stake: str
    reason: str
    challenge_time: datetime
    resolved: bool = False
    challenger_won: bool = False
    tx_hash: Optional[str] = None


class Database:
    """
    Database manager for Ominis Indexer.
    Uses PostgreSQL with asyncpg for async operations.
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Connect to database"""
        if not ASYNCPG_AVAILABLE:
            print("Warning: asyncpg not installed, using mock database")
            return
        
        try:
            self.pool = await asyncpg.create_pool(self.database_url)
            print("Connected to PostgreSQL")
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            print("Using in-memory mock database")
    
    async def disconnect(self):
        """Disconnect from database"""
        if self.pool:
            await self.pool.close()
    
    async def is_connected(self) -> bool:
        """Check if connected"""
        return self.pool is not None
    
    async def create_tables(self):
        """Create database tables"""
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id BIGINT PRIMARY KEY,
                    issuer VARCHAR(42) NOT NULL,
                    problem_hash VARCHAR(66) NOT NULL,
                    problem_type SMALLINT NOT NULL,
                    time_tier SMALLINT NOT NULL,
                    status SMALLINT NOT NULL DEFAULT 0,
                    reward VARCHAR(78) NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    deadline TIMESTAMP NOT NULL,
                    solver VARCHAR(42),
                    tx_hash VARCHAR(66),
                    block_number BIGINT,
                    indexed_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS solutions (
                    order_id BIGINT PRIMARY KEY REFERENCES orders(id),
                    solver VARCHAR(42) NOT NULL,
                    commit_hash VARCHAR(66) NOT NULL,
                    solution TEXT,
                    salt VARCHAR(66),
                    commit_time TIMESTAMP,
                    reveal_time TIMESTAMP,
                    is_revealed BOOLEAN DEFAULT FALSE,
                    tx_hash VARCHAR(66)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS challenges (
                    order_id BIGINT PRIMARY KEY REFERENCES orders(id),
                    challenger VARCHAR(42) NOT NULL,
                    stake VARCHAR(78) NOT NULL,
                    reason TEXT,
                    challenge_time TIMESTAMP NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    challenger_won BOOLEAN DEFAULT FALSE,
                    tx_hash VARCHAR(66)
                )
            ''')
            
            # Create indexes
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_issuer ON orders(issuer)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_solver ON orders(solver)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
            await conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)')
    
    # ============ Order Operations ============
    
    async def insert_order(self, order: Order) -> bool:
        """Insert a new order"""
        if not self.pool:
            return False
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO orders (id, issuer, problem_hash, problem_type, time_tier, 
                                   status, reward, created_at, deadline, solver, tx_hash, block_number)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    solver = EXCLUDED.solver
            ''', order.id, order.issuer, order.problem_hash, order.problem_type,
                order.time_tier, order.status, order.reward, order.created_at,
                order.deadline, order.solver, order.tx_hash, order.block_number)
        return True
    
    async def update_order_status(self, order_id: int, status: int, solver: str = None):
        """Update order status"""
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            if solver:
                await conn.execute(
                    'UPDATE orders SET status = $2, solver = $3 WHERE id = $1',
                    order_id, status, solver
                )
            else:
                await conn.execute(
                    'UPDATE orders SET status = $2 WHERE id = $1',
                    order_id, status
                )
    
    async def get_order(self, order_id: int) -> Optional[Order]:
        """Get order by ID"""
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM orders WHERE id = $1', order_id)
            if row:
                return Order(**dict(row))
        return None
    
    async def get_orders(
        self,
        status: Optional[int] = None,
        issuer: Optional[str] = None,
        solver: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Order]:
        """Get orders with filters"""
        if not self.pool:
            return []
        
        query = 'SELECT * FROM orders WHERE 1=1'
        params = []
        param_idx = 1
        
        if status is not None:
            query += f' AND status = ${param_idx}'
            params.append(status)
            param_idx += 1
        
        if issuer:
            query += f' AND issuer = ${param_idx}'
            params.append(issuer)
            param_idx += 1
        
        if solver:
            query += f' AND solver = ${param_idx}'
            params.append(solver)
            param_idx += 1
        
        query += f' ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}'
        params.extend([limit, offset])
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [Order(**dict(row)) for row in rows]
    
    async def get_order_count(self, status: Optional[int] = None) -> int:
        """Get order count"""
        if not self.pool:
            return 0
        
        async with self.pool.acquire() as conn:
            if status is not None:
                return await conn.fetchval(
                    'SELECT COUNT(*) FROM orders WHERE status = $1', status
                )
            return await conn.fetchval('SELECT COUNT(*) FROM orders')
    
    # ============ Solution Operations ============
    
    async def insert_solution(self, solution: Solution) -> bool:
        """Insert or update solution"""
        if not self.pool:
            return False
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO solutions (order_id, solver, commit_hash, solution, salt,
                                      commit_time, reveal_time, is_revealed, tx_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (order_id) DO UPDATE SET
                    solution = EXCLUDED.solution,
                    salt = EXCLUDED.salt,
                    reveal_time = EXCLUDED.reveal_time,
                    is_revealed = EXCLUDED.is_revealed
            ''', solution.order_id, solution.solver, solution.commit_hash,
                solution.solution, solution.salt, solution.commit_time,
                solution.reveal_time, solution.is_revealed, solution.tx_hash)
        return True
    
    async def get_solution(self, order_id: int) -> Optional[Solution]:
        """Get solution by order ID"""
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM solutions WHERE order_id = $1', order_id
            )
            if row:
                return Solution(**dict(row))
        return None
    
    # ============ Challenge Operations ============
    
    async def insert_challenge(self, challenge: Challenge) -> bool:
        """Insert challenge"""
        if not self.pool:
            return False
        
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO challenges (order_id, challenger, stake, reason,
                                       challenge_time, resolved, challenger_won, tx_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (order_id) DO UPDATE SET
                    resolved = EXCLUDED.resolved,
                    challenger_won = EXCLUDED.challenger_won
            ''', challenge.order_id, challenge.challenger, challenge.stake,
                challenge.reason, challenge.challenge_time, challenge.resolved,
                challenge.challenger_won, challenge.tx_hash)
        return True
    
    async def get_challenge(self, order_id: int) -> Optional[Challenge]:
        """Get challenge by order ID"""
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM challenges WHERE order_id = $1', order_id
            )
            if row:
                return Challenge(**dict(row))
        return None
    
    # ============ Stats ============
    
    async def get_stats(self) -> dict:
        """Get protocol statistics"""
        if not self.pool:
            return {}
        
        async with self.pool.acquire() as conn:
            total_orders = await conn.fetchval('SELECT COUNT(*) FROM orders')
            open_orders = await conn.fetchval(
                'SELECT COUNT(*) FROM orders WHERE status = 0'
            )
            completed_orders = await conn.fetchval(
                'SELECT COUNT(*) FROM orders WHERE status = 4'
            )
            total_challenges = await conn.fetchval('SELECT COUNT(*) FROM challenges')
            
            return {
                "total_orders": total_orders,
                "open_orders": open_orders,
                "completed_orders": completed_orders,
                "total_challenges": total_challenges
            }
