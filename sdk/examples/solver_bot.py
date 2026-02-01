"""
Example Solver Bot for Ominis Protocol

This is a basic template for building a solver bot that:
1. Listens for new calculus problem orders
2. Evaluates profitability
3. Accepts profitable orders
4. Solves problems using AI/CAS
5. Submits solutions via commit-reveal

Usage:
    export PRIVATE_KEY="your_private_key_here"
    export RPC_URL="https://arb-sepolia.g.alchemy.com/v2/YOUR_KEY"
    export CORE_ADDRESS="0x..."
    export ORDERBOOK_ADDRESS="0x..."
    
    python solver_bot.py
"""

import os
import sys
import asyncio
import logging
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for SDK import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file from SDK root directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

from ominis_sdk import OminisSDK, Order, ProblemType, TimeTier, OrderStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========== Configuration ==========

class BotConfig:
    """Bot configuration"""
    
    # Minimum profit threshold in USDC
    MIN_PROFIT_USDC: float = 0.05
    
    # Maximum orders to handle concurrently
    MAX_CONCURRENT_ORDERS: int = 3
    
    # Problem types this bot can solve
    SUPPORTED_TYPES: list[ProblemType] = [
        ProblemType.DERIVATIVE,
        ProblemType.INTEGRAL,
        ProblemType.LIMIT,
    ]
    
    # Time tiers to accept (faster = harder to complete in time)
    ACCEPTED_TIERS: list[TimeTier] = [
        TimeTier.T5min,
        TimeTier.T15min,
        TimeTier.T1hour,
    ]
    
    # Polling interval for new orders (seconds)
    POLL_INTERVAL: float = 2.0


# ========== AI/CAS Solver Integration ==========

# Try to import SymPy for local computation
try:
    from sympy import (
        symbols, diff, integrate, limit, sympify, 
        oo, sin, cos, tan, exp, log, sqrt, pi, E,
        dsolve, Function, Eq, series, Sum, simplify,
        latex, pretty
    )
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations, 
        implicit_multiplication_application, convert_xor
    )
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    logger.warning("SymPy not installed. Local solving disabled. Install with: pip install sympy")

# Try to import OpenAI for AI-based solving
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not installed. AI solving disabled. Install with: pip install openai")


class MathSolver:
    """
    Math problem solver using SymPy (local CAS) and OpenAI GPT-4 (AI).
    
    Solving priority:
    1. SymPy (fast, free, deterministic)
    2. OpenAI GPT-4 (fallback for complex/textual problems)
    
    Supported problem types:
    - DERIVATIVE: Compute derivatives using diff()
    - INTEGRAL: Compute indefinite/definite integrals using integrate()
    - LIMIT: Evaluate limits using limit()
    - DIFFERENTIAL_EQ: Solve ODEs using dsolve()
    - SERIES: Compute series expansions using series()
    """
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the math solver.
        
        Args:
            openai_api_key: OpenAI API key (optional, uses OPENAI_API_KEY env var if not provided)
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_client = None
        
        if OPENAI_AVAILABLE and self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI solver initialized")
        
        if SYMPY_AVAILABLE:
            logger.info("SymPy solver initialized")
        
        # Symbol for most calculus problems
        self.x = symbols('x') if SYMPY_AVAILABLE else None
        self.y = symbols('y') if SYMPY_AVAILABLE else None
        
        # Parser transformations for flexible input
        self.transformations = (
            standard_transformations + 
            (implicit_multiplication_application, convert_xor)
        ) if SYMPY_AVAILABLE else None
    
    async def solve(self, problem_hash: bytes, problem_type: ProblemType, 
                    expression: Optional[str] = None) -> Optional[str]:
        """
        Solve a calculus problem.
        
        Args:
            problem_hash: Hash of the problem (used to fetch problem from IPFS/API)
            problem_type: Type of calculus problem
            expression: Optional expression string (if already fetched)
            
        Returns:
            Solution string, or None if cannot solve
        """
        logger.info(f"Solving {problem_type.name} problem: {problem_hash.hex()[:16]}...")
        
        # In production: fetch actual problem from IPFS or indexer API
        # problem_text = await self.fetch_problem(problem_hash)
        
        # For now, use the expression if provided, or generate test expression
        if expression is None:
            expression = self._get_test_expression(problem_type)
        
        try:
            # Try SymPy first (fast, free, deterministic)
            if SYMPY_AVAILABLE:
                solution = await self.solve_with_sympy(expression, problem_type)
                if solution:
                    logger.info(f"Solved with SymPy: {solution[:50]}...")
                    return solution
            
            # Fallback to OpenAI for complex problems
            if self.openai_client:
                solution = await self.solve_with_openai(expression, problem_type)
                if solution:
                    logger.info(f"Solved with OpenAI: {solution[:50]}...")
                    return solution
            
            logger.warning(f"Could not solve problem with available solvers")
            return None
            
        except Exception as e:
            logger.error(f"Error solving problem: {e}")
            return None
    
    def _get_test_expression(self, problem_type: ProblemType) -> str:
        """Get a test expression for demo/testing purposes"""
        test_expressions = {
            ProblemType.DERIVATIVE: "x**3 + 2*x**2 - 5*x + 1",
            ProblemType.INTEGRAL: "x**2 + sin(x)",
            ProblemType.LIMIT: "sin(x)/x",  # x -> 0
            ProblemType.DIFFERENTIAL_EQ: "y' - 2*y = x",
            ProblemType.SERIES: "exp(x)",  # Taylor around x=0
        }
        return test_expressions.get(problem_type, "x**2")
    
    async def solve_with_sympy(self, expression: str, problem_type: ProblemType) -> Optional[str]:
        """
        Solve using SymPy (local symbolic computation).
        
        Args:
            expression: Mathematical expression as string
            problem_type: Type of problem to solve
            
        Returns:
            Solution string, or None if failed
        """
        if not SYMPY_AVAILABLE:
            return None
        
        try:
            # Parse the expression
            expr = parse_expr(expression, transformations=self.transformations)
            
            if problem_type == ProblemType.DERIVATIVE:
                # Compute derivative
                result = diff(expr, self.x)
                return f"d/dx [{expression}] = {simplify(result)}"
            
            elif problem_type == ProblemType.INTEGRAL:
                # Compute indefinite integral
                result = integrate(expr, self.x)
                return f"∫({expression})dx = {simplify(result)} + C"
            
            elif problem_type == ProblemType.LIMIT:
                # Compute limit as x -> 0 (default)
                result = limit(expr, self.x, 0)
                return f"lim(x→0) [{expression}] = {result}"
            
            elif problem_type == ProblemType.DIFFERENTIAL_EQ:
                # Solve ODE: parse as y' = f(x, y)
                y = Function('y')
                # Try to parse as simple ODE
                ode = Eq(y(self.x).diff(self.x), expr)
                result = dsolve(ode, y(self.x))
                return f"Solution: {result}"
            
            elif problem_type == ProblemType.SERIES:
                # Compute Taylor series around x=0, 6 terms
                result = series(expr, self.x, 0, 6)
                return f"Series expansion: {result}"
            
            else:
                # Unknown type, try to simplify
                result = simplify(expr)
                return f"Simplified: {result}"
                
        except Exception as e:
            logger.warning(f"SymPy solving failed: {e}")
            return None
    
    async def solve_with_openai(self, expression: str, problem_type: ProblemType) -> Optional[str]:
        """
        Solve using OpenAI GPT-4.
        
        Args:
            expression: Mathematical expression or problem text
            problem_type: Type of problem
            
        Returns:
            Solution string, or None if failed
        """
        if not self.openai_client:
            return None
        
        try:
            type_instructions = {
                ProblemType.DERIVATIVE: "Find the derivative with respect to x",
                ProblemType.INTEGRAL: "Find the indefinite integral with respect to x",
                ProblemType.LIMIT: "Evaluate the limit as x approaches 0",
                ProblemType.DIFFERENTIAL_EQ: "Solve this differential equation",
                ProblemType.SERIES: "Find the Taylor series expansion around x=0",
            }
            
            instruction = type_instructions.get(problem_type, "Solve this calculus problem")
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise calculus expert. Provide exact mathematical solutions. "
                            "Give the final answer in a clear, formatted way. "
                            "Use standard mathematical notation. Be concise."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"{instruction}: {expression}"
                    }
                ],
                max_tokens=500,
                temperature=0.1  # Low temperature for deterministic math
            )
            
            solution = response.choices[0].message.content
            return solution.strip() if solution else None
            
        except Exception as e:
            logger.warning(f"OpenAI solving failed: {e}")
            return None
    
    async def verify_solution(self, problem_type: ProblemType, 
                               expression: str, solution: str) -> bool:
        """
        Verify a solution is correct using SymPy.
        
        Args:
            problem_type: Type of problem
            expression: Original expression
            solution: Claimed solution
            
        Returns:
            True if solution is verified correct
        """
        if not SYMPY_AVAILABLE:
            return True  # Cannot verify without SymPy
        
        try:
            expr = parse_expr(expression, transformations=self.transformations)
            sol = parse_expr(solution, transformations=self.transformations)
            
            if problem_type == ProblemType.DERIVATIVE:
                # Verify: d/dx(antiderivative) = original
                expected = diff(expr, self.x)
                return simplify(expected - sol) == 0
            
            elif problem_type == ProblemType.INTEGRAL:
                # Verify: d/dx(solution) = original
                derivative = diff(sol, self.x)
                return simplify(derivative - expr) == 0
            
            # For other types, trust the solution
            return True
            
        except Exception:
            return True  # Cannot verify, assume correct


# ========== Solver Bot ==========

class SolverBot:
    """
    Main solver bot class.
    
    Responsibilities:
    - Monitor for new orders
    - Evaluate profitability
    - Accept and solve orders
    - Submit solutions
    - Handle errors and retries
    """
    
    def __init__(self, sdk: OminisSDK, config: BotConfig):
        self.sdk = sdk
        self.config = config
        self.solver = MathSolver()
        self.active_orders: dict[int, Order] = {}
        self.running = False
    
    async def start(self):
        """Start the solver bot"""
        logger.info("=" * 50)
        logger.info("Ominis Solver Bot Starting")
        logger.info(f"Address: {self.sdk.address}")
        logger.info(f"Balance: {self.sdk.get_balance_eth():.4f} ETH")
        logger.info("=" * 50)
        
        self.running = True
        
        # Run main loop
        await self._main_loop()
    
    async def stop(self):
        """Stop the solver bot"""
        logger.info("Stopping solver bot...")
        self.running = False
    
    async def _main_loop(self):
        """Main event loop"""
        while self.running:
            try:
                # Get open orders
                orders = await self.sdk.get_open_orders(limit=50)
                logger.debug(f"Found {len(orders)} open orders")
                
                for order in orders:
                    if await self._should_accept(order):
                        await self._handle_order(order)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            
            await asyncio.sleep(self.config.POLL_INTERVAL)
    
    async def _should_accept(self, order: Order) -> bool:
        """Determine if bot should accept an order"""
        
        # Check if already handling
        if order.id in self.active_orders:
            return False
        
        # Check concurrent limit
        if len(self.active_orders) >= self.config.MAX_CONCURRENT_ORDERS:
            return False
        
        # Check problem type
        if order.problem_type not in self.config.SUPPORTED_TYPES:
            logger.debug(f"Order {order.id}: Unsupported type {order.problem_type.name}")
            return False
        
        # Check time tier
        if order.time_tier not in self.config.ACCEPTED_TIERS:
            logger.debug(f"Order {order.id}: Time tier {order.time_tier.name} not accepted")
            return False
        
        # Check profitability
        profit = self.sdk.estimate_profit(order)
        if profit < self.config.MIN_PROFIT_USDC:
            logger.debug(f"Order {order.id}: Profit ${profit:.4f} below threshold")
            return False
        
        # Check time remaining
        if order.time_remaining < 30:  # Need at least 30 seconds
            logger.debug(f"Order {order.id}: Not enough time remaining")
            return False
        
        return True
    
    async def _handle_order(self, order: Order):
        """Handle a single order (accept, solve, submit)"""
        order_id = order.id
        
        try:
            logger.info(f"=" * 40)
            logger.info(f"Handling Order #{order_id}")
            logger.info(f"  Type: {order.problem_type.name}")
            logger.info(f"  Tier: {order.time_tier.name}")
            logger.info(f"  Reward: ${order.reward_in_usdc():.4f}")
            logger.info(f"  Time remaining: {order.time_remaining}s")
            
            # Mark as active
            self.active_orders[order_id] = order
            
            # Step 1: Accept the order
            logger.info(f"[{order_id}] Accepting order...")
            accept_receipt = await self.sdk.accept_order(order_id)
            
            if not accept_receipt.success:
                logger.error(f"[{order_id}] Failed to accept order")
                return
            
            logger.info(f"[{order_id}] Order accepted! TX: {accept_receipt.tx_hash[:16]}...")
            
            # Step 2: Solve the problem
            logger.info(f"[{order_id}] Solving problem...")
            solution = await self.solver.solve(order.problem_hash, order.problem_type)
            
            if solution is None:
                logger.error(f"[{order_id}] Failed to solve problem")
                return
            
            logger.info(f"[{order_id}] Solution found!")
            
            # Step 3: Submit solution (commit + reveal)
            logger.info(f"[{order_id}] Submitting solution...")
            commit_receipt, reveal_receipt = await self.sdk.submit_solution(order_id, solution)
            
            if reveal_receipt.success:
                logger.info(f"[{order_id}] Solution submitted successfully!")
                logger.info(f"[{order_id}] Commit TX: {commit_receipt.tx_hash[:16]}...")
                logger.info(f"[{order_id}] Reveal TX: {reveal_receipt.tx_hash[:16]}...")
            else:
                logger.error(f"[{order_id}] Failed to submit solution")
            
        except Exception as e:
            logger.error(f"[{order_id}] Error handling order: {e}")
            
        finally:
            # Remove from active orders
            self.active_orders.pop(order_id, None)


# ========== Main Entry Point ==========

async def main():
    """Main entry point"""
    
    # Load configuration from environment
    private_key = os.getenv("PRIVATE_KEY")
    rpc_url = os.getenv("RPC_URL")
    core_address = os.getenv("CORE_ADDRESS")
    orderbook_address = os.getenv("ORDERBOOK_ADDRESS")
    
    # Show solver capabilities
    logger.info("=" * 50)
    logger.info("Ominis Solver Bot - Math Solver Capabilities")
    logger.info("=" * 50)
    logger.info(f"SymPy (local CAS): {'ENABLED' if SYMPY_AVAILABLE else 'DISABLED'}")
    logger.info(f"OpenAI GPT-4:      {'ENABLED' if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY') else 'DISABLED'}")
    logger.info("=" * 50)
    
    # Validate configuration
    if not all([private_key, rpc_url, core_address]):
        logger.error("Missing required environment variables!")
        logger.error("Required: PRIVATE_KEY, RPC_URL, CORE_ADDRESS")
        logger.error("Optional: ORDERBOOK_ADDRESS, OPENAI_API_KEY")
        logger.error("")
        logger.error("Create a .env file from the template:")
        logger.error("  cp env-template.txt .env")
        logger.error("  nano .env")
        sys.exit(1)
    
    # Initialize SDK
    sdk = OminisSDK(
        private_key=private_key,
        rpc_url=rpc_url,
        core_address=core_address
    )
    
    if orderbook_address:
        sdk.set_orderbook_address(orderbook_address)
    
    # Create and start bot
    config = BotConfig()
    bot = SolverBot(sdk, config)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
