"""
Ominis Protocol SDK - Python SDK for Solver Bots

This SDK allows solver bots to interact with the Ominis Calculus Solver Protocol.
It provides methods for:
- Listening to new problem orders
- Accepting orders
- Submitting solutions (commit-reveal pattern)
- Monitoring order status
"""

import os
import json
import asyncio
from typing import List, Optional, AsyncIterator, Dict, Any
from dataclasses import dataclass
from enum import IntEnum
from web3 import Web3, AsyncWeb3
from web3.contract import Contract
from eth_account import Account
from eth_account.signers.local import LocalAccount


class ProblemType(IntEnum):
    """Types of calculus problems supported"""
    DERIVATIVE = 0
    INTEGRAL = 1
    LIMIT = 2
    DIFFERENTIAL_EQ = 3
    SERIES = 4


class TimeTier(IntEnum):
    """Time tiers with different pricing"""
    T2min = 0   # 2 minutes - fastest, most expensive
    T5min = 1   # 5 minutes
    T15min = 2  # 15 minutes
    T1hour = 3  # 1 hour - cheapest


class OrderStatus(IntEnum):
    """Order lifecycle states"""
    OPEN = 0
    ACCEPTED = 1
    COMMITTED = 2
    REVEALED = 3
    VERIFIED = 4
    CHALLENGED = 5
    EXPIRED = 6
    CANCELLED = 7


@dataclass
class Order:
    """Represents a problem order on the protocol"""
    id: int
    issuer: str
    problem_hash: bytes
    problem_type: ProblemType
    time_tier: TimeTier
    status: OrderStatus
    reward: int
    created_at: int
    deadline: int
    solver: Optional[str] = None
    
    @property
    def is_open(self) -> bool:
        return self.status == OrderStatus.OPEN
    
    @property
    def time_remaining(self) -> int:
        """Seconds remaining until deadline"""
        import time
        return max(0, self.deadline - int(time.time()))
    
    def reward_in_usdc(self) -> float:
        """Convert reward from wei to USDC (6 decimals)"""
        return self.reward / 1e6


@dataclass
class TxReceipt:
    """Transaction receipt wrapper"""
    tx_hash: str
    block_number: int
    gas_used: int
    status: bool
    
    @property
    def success(self) -> bool:
        return self.status


class OminisSDK:
    """
    SDK for solver bots to interact with Ominis protocol.
    
    Usage:
        sdk = OminisSDK(
            private_key=os.getenv("PRIVATE_KEY"),
            rpc_url="https://arb-sepolia.g.alchemy.com/v2/YOUR_KEY",
            core_address="0x..."
        )
        
        # Listen for new orders
        async for order in sdk.listen_new_orders():
            if sdk.estimate_profit(order) > 0.01:
                await sdk.accept_order(order.id)
    """
    
    # Contract ABIs (minimal - only needed functions)
    CORE_ABI = [
        {
            "inputs": [{"name": "orderId", "type": "uint256"}],
            "name": "acceptOrder",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "orderId", "type": "uint256"},
                {"name": "commitHash", "type": "bytes32"}
            ],
            "name": "commitSolution",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "orderId", "type": "uint256"},
                {"name": "solution", "type": "string"},
                {"name": "salt", "type": "bytes32"}
            ],
            "name": "revealSolution",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "orderId", "type": "uint256"},
                {"indexed": True, "name": "issuer", "type": "address"},
                {"indexed": False, "name": "problemType", "type": "uint8"},
                {"indexed": False, "name": "timeTier", "type": "uint8"},
                {"indexed": False, "name": "reward", "type": "uint256"}
            ],
            "name": "ProblemPosted",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "orderId", "type": "uint256"},
                {"indexed": True, "name": "solver", "type": "address"}
            ],
            "name": "OrderAccepted",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "orderId", "type": "uint256"},
                {"indexed": True, "name": "bot", "type": "address"},
                {"indexed": False, "name": "targetType", "type": "uint8"}
            ],
            "name": "OrderAssignedToBot",
            "type": "event"
        },
        {
            "inputs": [{"name": "orderId", "type": "uint256"}],
            "name": "getOrderBot",
            "outputs": [{"name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    ORDERBOOK_ABI = [
        {
            "inputs": [{"name": "orderId", "type": "uint256"}],
            "name": "getOrder",
            "outputs": [
                {
                    "components": [
                        {"name": "id", "type": "uint256"},
                        {"name": "issuer", "type": "address"},
                        {"name": "problemHash", "type": "bytes32"},
                        {"name": "problemType", "type": "uint8"},
                        {"name": "timeTier", "type": "uint8"},
                        {"name": "status", "type": "uint8"},
                        {"name": "reward", "type": "uint256"},
                        {"name": "createdAt", "type": "uint256"},
                        {"name": "deadline", "type": "uint256"},
                        {"name": "solver", "type": "address"}
                    ],
                    "name": "",
                    "type": "tuple"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "offset", "type": "uint256"},
                {"name": "limit", "type": "uint256"}
            ],
            "name": "getOpenOrders",
            "outputs": [
                {
                    "components": [
                        {"name": "id", "type": "uint256"},
                        {"name": "issuer", "type": "address"},
                        {"name": "problemHash", "type": "bytes32"},
                        {"name": "problemType", "type": "uint8"},
                        {"name": "timeTier", "type": "uint8"},
                        {"name": "status", "type": "uint8"},
                        {"name": "reward", "type": "uint256"},
                        {"name": "createdAt", "type": "uint256"},
                        {"name": "deadline", "type": "uint256"},
                        {"name": "solver", "type": "address"}
                    ],
                    "name": "",
                    "type": "tuple[]"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "orderCount",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "openOrderCount",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "timeTier", "type": "uint8"}],
            "name": "getTierPrice",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def __init__(
        self,
        private_key: str,
        rpc_url: str,
        core_address: str,
        orderbook_address: Optional[str] = None,
        gas_price_gwei: Optional[float] = None
    ):
        """
        Initialize the SDK.
        
        Args:
            private_key: Hex-encoded private key for signing transactions
            rpc_url: RPC URL for the network (e.g., Arbitrum)
            core_address: Address of the CalcSolverCore contract
            orderbook_address: Address of the OrderBook contract (optional, can be read from Core)
            gas_price_gwei: Optional fixed gas price in gwei
        """
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account: LocalAccount = Account.from_key(private_key)
        self.address = self.account.address
        
        self.core_address = Web3.to_checksum_address(core_address)
        self.core: Contract = self.w3.eth.contract(
            address=self.core_address,
            abi=self.CORE_ABI
        )
        
        # OrderBook address (can be set later or read from Core)
        self._orderbook_address = orderbook_address
        self._orderbook: Optional[Contract] = None
        
        self.gas_price_gwei = gas_price_gwei
        
    @property
    def orderbook(self) -> Contract:
        """Get OrderBook contract (lazy initialization)"""
        if self._orderbook is None:
            if self._orderbook_address is None:
                raise ValueError("OrderBook address not set. Call set_orderbook_address() first.")
            self._orderbook = self.w3.eth.contract(
                address=Web3.to_checksum_address(self._orderbook_address),
                abi=self.ORDERBOOK_ABI
            )
        return self._orderbook
    
    def set_orderbook_address(self, address: str):
        """Set the OrderBook contract address"""
        self._orderbook_address = Web3.to_checksum_address(address)
        self._orderbook = None  # Reset to force reinitialization
    
    # ========== Order Management ==========
    
    async def get_order(self, order_id: int) -> Order:
        """
        Get order details by ID.
        
        Args:
            order_id: The order ID
            
        Returns:
            Order object with all details
        """
        raw = self.orderbook.functions.getOrder(order_id).call()
        return Order(
            id=raw[0],
            issuer=raw[1],
            problem_hash=raw[2],
            problem_type=ProblemType(raw[3]),
            time_tier=TimeTier(raw[4]),
            status=OrderStatus(raw[5]),
            reward=raw[6],
            created_at=raw[7],
            deadline=raw[8],
            solver=raw[9] if raw[9] != "0x" + "0" * 40 else None
        )
    
    async def get_open_orders(self, limit: int = 100) -> List[Order]:
        """
        Get all currently open orders.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of open Order objects
        """
        # Use the contract's getOpenOrders for efficiency
        raw_orders = self.orderbook.functions.getOpenOrders(0, limit).call()
        orders = []
        
        for raw in raw_orders:
            try:
                order = Order(
                    id=raw[0],
                    issuer=raw[1],
                    problem_hash=raw[2],
                    problem_type=ProblemType(raw[3]),
                    time_tier=TimeTier(raw[4]),
                    status=OrderStatus(raw[5]),
                    reward=raw[6],
                    created_at=raw[7],
                    deadline=raw[8],
                    solver=raw[9] if raw[9] != "0x" + "0" * 40 else None
                )
                orders.append(order)
            except Exception:
                continue
                
        return orders
    
    async def get_tier_price(self, tier: TimeTier) -> int:
        """
        Get current price for a time tier.
        
        Args:
            tier: TimeTier enum value
            
        Returns:
            Price in payment token units (e.g., USDC with 6 decimals)
        """
        return self.orderbook.functions.getTierPrice(tier.value).call()
    
    async def accept_order(self, order_id: int) -> TxReceipt:
        """
        Accept an open order to become its solver.
        
        Args:
            order_id: The order ID to accept
            
        Returns:
            Transaction receipt
        """
        tx = self.core.functions.acceptOrder(order_id).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 200000,
            'gasPrice': self._get_gas_price()
        })
        
        return await self._send_transaction(tx)
    
    # ========== Solution Submission ==========
    
    def compute_commit_hash(self, solution: str, salt: bytes) -> bytes:
        """
        Compute the commit hash for a solution.
        
        Args:
            solution: The solution string
            salt: 32 bytes of random salt
            
        Returns:
            32-byte commit hash
        """
        return Web3.solidity_keccak(
            ['string', 'bytes32'],
            [solution, salt]
        )
    
    async def commit_solution(self, order_id: int, solution: str, salt: bytes) -> TxReceipt:
        """
        Commit a solution hash (first step of commit-reveal).
        
        Args:
            order_id: The order ID
            solution: The solution string
            salt: 32 bytes of random salt (save this for reveal!)
            
        Returns:
            Transaction receipt
        """
        commit_hash = self.compute_commit_hash(solution, salt)
        
        tx = self.core.functions.commitSolution(order_id, commit_hash).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 250000,  # Increased from 150000 - commit needs ~175k gas
            'gasPrice': self._get_gas_price()
        })
        
        return await self._send_transaction(tx)
    
    async def reveal_solution(self, order_id: int, solution: str, salt: bytes) -> TxReceipt:
        """
        Reveal a previously committed solution.
        
        Args:
            order_id: The order ID
            solution: The original solution string
            salt: The same salt used in commit
            
        Returns:
            Transaction receipt
        """
        tx = self.core.functions.revealSolution(order_id, solution, salt).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 500000,  # Increased from 300000 - reveal can use ~300k+ gas
            'gasPrice': self._get_gas_price()
        })
        
        return await self._send_transaction(tx)
    
    async def submit_solution(self, order_id: int, solution: str) -> tuple[TxReceipt, TxReceipt]:
        """
        Submit a complete solution (commit + reveal with automatic salt).
        
        This is a convenience method that handles the commit-reveal pattern.
        For time-sensitive orders, you may want to call commit_solution and
        reveal_solution separately.
        
        Args:
            order_id: The order ID
            solution: The solution string
            
        Returns:
            Tuple of (commit_receipt, reveal_receipt)
        """
        salt = os.urandom(32)
        
        commit_receipt = await self.commit_solution(order_id, solution, salt)
        if not commit_receipt.success:
            raise Exception(f"Commit failed: {commit_receipt.tx_hash}")
        
        # Wait a bit for commit to be mined
        await asyncio.sleep(2)
        
        reveal_receipt = await self.reveal_solution(order_id, solution, salt)
        return commit_receipt, reveal_receipt
    
    # ========== Event Listening ==========
    
    async def listen_new_orders(self, poll_interval: float = 2.0) -> AsyncIterator[Order]:
        """
        Listen for new problem orders.
        
        This is a polling-based implementation. For production, consider
        using WebSocket subscriptions.
        
        Args:
            poll_interval: Seconds between polls
            
        Yields:
            New Order objects as they are posted
        """
        event_filter = self.core.events.ProblemPosted.create_filter(fromBlock='latest')
        
        while True:
            try:
                events = event_filter.get_new_entries()
                for event in events:
                    order_id = event.args.orderId
                    order = await self.get_order(order_id)
                    yield order
            except Exception as e:
                print(f"Error polling events: {e}")
            
            await asyncio.sleep(poll_interval)
    
    async def wait_for_acceptance(self, order_id: int, timeout: float = 60.0) -> bool:
        """
        Wait for an order to be accepted (by any solver).
        
        Args:
            order_id: The order ID to watch
            timeout: Maximum seconds to wait
            
        Returns:
            True if accepted, False if timeout
        """
        start = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start < timeout:
            order = await self.get_order(order_id)
            if order.status != OrderStatus.OPEN:
                return True
            await asyncio.sleep(1)
        
        return False
    
    # ========== Subscription Mode / Bot Assignment ==========
    
    def get_order_bot(self, order_id: int) -> Optional[str]:
        """
        Get the bot assigned to an order (subscription mode).
        
        Args:
            order_id: The order ID
            
        Returns:
            Bot address if assigned, None otherwise
        """
        try:
            bot_address = self.core.functions.getOrderBot(order_id).call()
            # Check if it's the zero address
            if bot_address == "0x" + "0" * 40:
                return None
            return bot_address
        except Exception:
            return None
    
    async def listen_assigned_orders(
        self, 
        bot_address: str = None,
        poll_interval: float = 2.0,
        from_block: int = None
    ) -> AsyncIterator[int]:
        """
        Listen for orders assigned to a specific bot (subscription mode).
        
        In subscription mode, users can assign problems directly to bots
        via postProblemWithSubscription, triggering OrderAssignedToBot events.
        
        Args:
            bot_address: Bot address to filter for (defaults to self.address)
            poll_interval: Seconds between polls
            from_block: Block number to start from (defaults to 'latest')
            
        Yields:
            Order IDs assigned to the bot
        """
        if bot_address is None:
            bot_address = self.address
        
        bot_address = Web3.to_checksum_address(bot_address)
        
        # Create event filter
        if from_block is None:
            from_block = 'latest'
        
        event_filter = self.core.events.OrderAssignedToBot.create_filter(
            fromBlock=from_block,
            argument_filters={'bot': bot_address}
        )
        
        while True:
            try:
                events = event_filter.get_new_entries()
                for event in events:
                    yield event.args.orderId
            except Exception as e:
                print(f"Error polling assigned orders: {e}")
            
            await asyncio.sleep(poll_interval)
    
    def get_assigned_orders_batch(
        self, 
        bot_address: str = None,
        from_block: int = 0,
        to_block: int = None
    ) -> List[int]:
        """
        Get all orders assigned to a bot in a block range (batch query).
        
        Args:
            bot_address: Bot address to filter for (defaults to self.address)
            from_block: Start block (default 0)
            to_block: End block (default latest)
            
        Returns:
            List of order IDs assigned to the bot
        """
        if bot_address is None:
            bot_address = self.address
        
        bot_address = Web3.to_checksum_address(bot_address)
        
        if to_block is None:
            to_block = self.w3.eth.block_number
        
        try:
            event_filter = self.core.events.OrderAssignedToBot.create_filter(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={'bot': bot_address}
            )
            
            events = event_filter.get_all_entries()
            return [event.args.orderId for event in events]
        except Exception as e:
            print(f"Error getting assigned orders: {e}")
            return []
    
    # ========== Utilities ==========
    
    def estimate_profit(self, order: Order, gas_cost_gwei: float = 0.1) -> float:
        """
        Estimate profit for solving an order.
        
        Args:
            order: The order to evaluate
            gas_cost_gwei: Estimated gas cost per gwei
            
        Returns:
            Estimated profit in USDC
        """
        reward_usdc = order.reward_in_usdc()
        
        # Estimate gas costs (accept + commit + reveal ≈ 500k gas)
        estimated_gas = 500000
        gas_price = self._get_gas_price()
        gas_cost_eth = (estimated_gas * gas_price) / 1e18
        
        # Assume ETH price ~$3000 for rough estimate
        gas_cost_usdc = gas_cost_eth * 3000
        
        return reward_usdc - gas_cost_usdc
    
    def get_balance(self) -> int:
        """Get ETH balance of the solver account"""
        return self.w3.eth.get_balance(self.address)
    
    def get_balance_eth(self) -> float:
        """Get ETH balance in human-readable format"""
        return self.get_balance() / 1e18
    
    # ========== Oracle Staking Methods ==========
    
    def set_verifier_address(self, address: str):
        """Set the Verifier contract address for Oracle operations"""
        self.verifier_address = Web3.to_checksum_address(address)
        # Load Verifier ABI
        verifier_abi = [
            {
                "inputs": [{"type": "uint256"}, {"type": "address"}],
                "name": "depositOracleStake",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"type": "uint256"}, {"type": "address"}],
                "name": "withdrawOracleStake",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"type": "address"}],
                "name": "getOracleStake",
                "outputs": [{"type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"type": "address"}],
                "name": "isOracleAuthorized",
                "outputs": [{"type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "minOracleStake",
                "outputs": [{"type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "verificationTimeout",
                "outputs": [{"type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        self.verifier = self.w3.eth.contract(
            address=self.verifier_address,
            abi=verifier_abi
        )
    
    async def deposit_oracle_stake(self, amount_usdc: float) -> TxReceipt:
        """
        Deposit stake to become an authorized Oracle.
        
        Args:
            amount_usdc: Amount of USDC to stake (human readable, e.g., 1000.0)
        
        Returns:
            Transaction receipt
        """
        if not hasattr(self, 'verifier'):
            raise ValueError("Verifier address not set. Call set_verifier_address first.")
        
        amount_wei = int(amount_usdc * 1e6)  # USDC has 6 decimals
        
        # First approve USDC transfer to Verifier
        if hasattr(self, 'usdc'):
            approve_tx = self.usdc.functions.approve(
                self.verifier_address,
                amount_wei
            ).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': 100000,
                'gasPrice': self._get_gas_price()
            })
            await self._send_transaction(approve_tx)
        
        # Deposit stake
        tx = self.verifier.functions.depositOracleStake(
            amount_wei,
            self.usdc.address if hasattr(self, 'usdc') else self.core_address
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 200000,
            'gasPrice': self._get_gas_price()
        })
        
        return await self._send_transaction(tx)
    
    async def withdraw_oracle_stake(self, amount_usdc: float) -> TxReceipt:
        """
        Withdraw Oracle stake.
        
        Args:
            amount_usdc: Amount of USDC to withdraw
        
        Returns:
            Transaction receipt
        """
        if not hasattr(self, 'verifier'):
            raise ValueError("Verifier address not set. Call set_verifier_address first.")
        
        amount_wei = int(amount_usdc * 1e6)
        
        tx = self.verifier.functions.withdrawOracleStake(
            amount_wei,
            self.usdc.address if hasattr(self, 'usdc') else self.core_address
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 200000,
            'gasPrice': self._get_gas_price()
        })
        
        return await self._send_transaction(tx)
    
    def get_oracle_stake(self, oracle_address: str = None) -> float:
        """Get Oracle's current stake in USDC"""
        if not hasattr(self, 'verifier'):
            raise ValueError("Verifier address not set. Call set_verifier_address first.")
        
        address = oracle_address or self.address
        stake_wei = self.verifier.functions.getOracleStake(address).call()
        return stake_wei / 1e6
    
    def is_oracle_authorized(self, oracle_address: str = None) -> bool:
        """Check if an Oracle is authorized (has sufficient stake)"""
        if not hasattr(self, 'verifier'):
            raise ValueError("Verifier address not set. Call set_verifier_address first.")
        
        address = oracle_address or self.address
        return self.verifier.functions.isOracleAuthorized(address).call()
    
    def get_min_oracle_stake(self) -> float:
        """Get minimum stake required to be an Oracle"""
        if not hasattr(self, 'verifier'):
            raise ValueError("Verifier address not set. Call set_verifier_address first.")
        
        return self.verifier.functions.minOracleStake().call() / 1e6
    
    def get_verification_timeout(self) -> int:
        """Get the verification timeout in seconds"""
        if not hasattr(self, 'verifier'):
            raise ValueError("Verifier address not set. Call set_verifier_address first.")
        
        return self.verifier.functions.verificationTimeout().call()
    
    # ========== Internal Methods ==========
    
    def _get_gas_price(self) -> int:
        """Get gas price to use for transactions (with 1.5x multiplier for faster mining)"""
        if self.gas_price_gwei:
            return int(self.gas_price_gwei * 1e9)
        # Add 50% buffer to ensure faster mining
        return int(self.w3.eth.gas_price * 1.5)
    
    async def _send_transaction(self, tx: Dict[str, Any]) -> TxReceipt:
        """Sign and send a transaction"""
        import logging
        logger = logging.getLogger(__name__)
        
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info(f"Transaction sent: {tx_hash.hex()}")
        
        # Wait with timeout
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            logger.info(f"Receipt received: status={receipt.status}, gasUsed={receipt.gasUsed}")
        except Exception as e:
            logger.error(f"Transaction timeout or error: {e}")
            # Return failed receipt if timeout
            return TxReceipt(
                tx_hash=tx_hash.hex(),
                block_number=0,
                gas_used=0,
                status=False
            )
        
        success = receipt.status == 1
        logger.info(f"Transaction result: success={success}")
        
        return TxReceipt(
            tx_hash=receipt.transactionHash.hex(),
            block_number=receipt.blockNumber,
            gas_used=receipt.gasUsed,
            status=success
        )


# ========== Helper Functions ==========

def generate_salt() -> bytes:
    """Generate random 32-byte salt for commit-reveal"""
    return os.urandom(32)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load SDK configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


# ========== Example Usage ==========

if __name__ == "__main__":
    # Example: Print SDK info
    print("Ominis SDK v0.1.0")
    print("=" * 40)
    print("Supported Problem Types:")
    for pt in ProblemType:
        print(f"  - {pt.name} ({pt.value})")
    print("\nTime Tiers:")
    for tt in TimeTier:
        print(f"  - {tt.name} ({tt.value})")
