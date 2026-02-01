"""
Blockchain event listener for Ominis Indexer
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from web3 import Web3
from web3.middleware import geth_poa_middleware

from models import Database, Order, Solution, Challenge

logger = logging.getLogger("EventListener")


# Event ABIs
CORE_EVENTS_ABI = [
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
            {"indexed": True, "name": "solver", "type": "address"},
            {"indexed": False, "name": "commitHash", "type": "bytes32"}
        ],
        "name": "SolutionCommitted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderId", "type": "uint256"},
            {"indexed": True, "name": "solver", "type": "address"},
            {"indexed": False, "name": "solution", "type": "string"}
        ],
        "name": "SolutionRevealed",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderId", "type": "uint256"},
            {"indexed": True, "name": "challenger", "type": "address"},
            {"indexed": False, "name": "stake", "type": "uint256"}
        ],
        "name": "ChallengeSubmitted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderId", "type": "uint256"},
            {"indexed": False, "name": "challengerWon", "type": "bool"},
            {"indexed": False, "name": "winner", "type": "address"}
        ],
        "name": "ChallengeResolved",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderId", "type": "uint256"}
        ],
        "name": "OrderExpired",
        "type": "event"
    }
]


class EventListener:
    """
    Listens to blockchain events and indexes them to database.
    """
    
    def __init__(
        self,
        rpc_url: str,
        core_contract: str,
        database: Database,
        start_block: int = 0,
        on_new_event: Optional[Callable] = None
    ):
        self.rpc_url = rpc_url
        self.core_contract = Web3.to_checksum_address(core_contract)
        self.database = database
        self.start_block = start_block
        self.on_new_event = on_new_event
        
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        self.contract = self.w3.eth.contract(
            address=self.core_contract,
            abi=CORE_EVENTS_ABI
        )
        
        self.running = False
        self.last_processed_block = start_block
        
    async def start(self):
        """Start listening for events"""
        self.running = True
        logger.info(f"Starting event listener from block {self.start_block}")
        
        # First, catch up on historical events
        await self._sync_historical_events()
        
        # Then listen for new events
        await self._listen_for_new_events()
    
    async def stop(self):
        """Stop the listener"""
        self.running = False
        logger.info("Event listener stopped")
    
    async def _sync_historical_events(self):
        """Sync historical events from start_block to current"""
        current_block = self.w3.eth.block_number
        
        if self.last_processed_block >= current_block:
            return
        
        logger.info(f"Syncing historical events from {self.last_processed_block} to {current_block}")
        
        # Process in chunks
        chunk_size = 1000
        from_block = self.last_processed_block
        
        while from_block < current_block and self.running:
            to_block = min(from_block + chunk_size, current_block)
            
            await self._process_block_range(from_block, to_block)
            
            from_block = to_block + 1
            self.last_processed_block = to_block
            
            # Small delay to not overwhelm RPC
            await asyncio.sleep(0.1)
        
        logger.info(f"Historical sync complete. At block {self.last_processed_block}")
    
    async def _listen_for_new_events(self):
        """Listen for new events in real-time"""
        logger.info("Listening for new events...")
        
        while self.running:
            try:
                current_block = self.w3.eth.block_number
                
                if current_block > self.last_processed_block:
                    await self._process_block_range(
                        self.last_processed_block + 1,
                        current_block
                    )
                    self.last_processed_block = current_block
                
            except Exception as e:
                logger.error(f"Error listening for events: {e}")
            
            await asyncio.sleep(2)  # Poll every 2 seconds
    
    async def _process_block_range(self, from_block: int, to_block: int):
        """Process events in a block range"""
        try:
            # Get all events in range
            events = []
            
            # ProblemPosted
            problem_events = self.contract.events.ProblemPosted.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('ProblemPosted', e) for e in problem_events])
            
            # OrderAccepted
            accepted_events = self.contract.events.OrderAccepted.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('OrderAccepted', e) for e in accepted_events])
            
            # SolutionCommitted
            commit_events = self.contract.events.SolutionCommitted.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('SolutionCommitted', e) for e in commit_events])
            
            # SolutionRevealed
            reveal_events = self.contract.events.SolutionRevealed.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('SolutionRevealed', e) for e in reveal_events])
            
            # ChallengeSubmitted
            challenge_events = self.contract.events.ChallengeSubmitted.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('ChallengeSubmitted', e) for e in challenge_events])
            
            # Process each event
            for event_type, event in events:
                await self._handle_event(event_type, event)
                
        except Exception as e:
            logger.error(f"Error processing blocks {from_block}-{to_block}: {e}")
    
    async def _handle_event(self, event_type: str, event):
        """Handle a specific event"""
        try:
            block = self.w3.eth.get_block(event.blockNumber)
            timestamp = datetime.fromtimestamp(block.timestamp)
            tx_hash = event.transactionHash.hex()
            
            if event_type == 'ProblemPosted':
                await self._handle_problem_posted(event, timestamp, tx_hash)
                
            elif event_type == 'OrderAccepted':
                await self._handle_order_accepted(event, timestamp, tx_hash)
                
            elif event_type == 'SolutionCommitted':
                await self._handle_solution_committed(event, timestamp, tx_hash)
                
            elif event_type == 'SolutionRevealed':
                await self._handle_solution_revealed(event, timestamp, tx_hash)
                
            elif event_type == 'ChallengeSubmitted':
                await self._handle_challenge_submitted(event, timestamp, tx_hash)
            
            # Broadcast to websockets
            if self.on_new_event:
                await self.on_new_event(event_type, {
                    'orderId': event.args.orderId,
                    'txHash': tx_hash,
                    'timestamp': timestamp.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling {event_type}: {e}")
    
    async def _handle_problem_posted(self, event, timestamp, tx_hash):
        """Handle ProblemPosted event"""
        order = Order(
            id=event.args.orderId,
            issuer=event.args.issuer,
            problem_hash='',  # Would need to get from contract
            problem_type=event.args.problemType,
            time_tier=event.args.timeTier,
            status=0,  # OPEN
            reward=str(event.args.reward),
            created_at=timestamp,
            deadline=timestamp,  # Would calculate from tier
            tx_hash=tx_hash,
            block_number=event.blockNumber
        )
        await self.database.insert_order(order)
        logger.info(f"Indexed ProblemPosted #{event.args.orderId}")
    
    async def _handle_order_accepted(self, event, timestamp, tx_hash):
        """Handle OrderAccepted event"""
        await self.database.update_order_status(
            event.args.orderId,
            status=1,  # ACCEPTED
            solver=event.args.solver
        )
        logger.info(f"Indexed OrderAccepted #{event.args.orderId}")
    
    async def _handle_solution_committed(self, event, timestamp, tx_hash):
        """Handle SolutionCommitted event"""
        solution = Solution(
            order_id=event.args.orderId,
            solver=event.args.solver,
            commit_hash=event.args.commitHash.hex(),
            commit_time=timestamp,
            tx_hash=tx_hash
        )
        await self.database.insert_solution(solution)
        await self.database.update_order_status(event.args.orderId, status=2)
        logger.info(f"Indexed SolutionCommitted #{event.args.orderId}")
    
    async def _handle_solution_revealed(self, event, timestamp, tx_hash):
        """Handle SolutionRevealed event"""
        # Update existing solution
        existing = await self.database.get_solution(event.args.orderId)
        if existing:
            existing.solution = event.args.solution
            existing.reveal_time = timestamp
            existing.is_revealed = True
            await self.database.insert_solution(existing)
        
        await self.database.update_order_status(event.args.orderId, status=3)
        logger.info(f"Indexed SolutionRevealed #{event.args.orderId}")
    
    async def _handle_challenge_submitted(self, event, timestamp, tx_hash):
        """Handle ChallengeSubmitted event"""
        challenge = Challenge(
            order_id=event.args.orderId,
            challenger=event.args.challenger,
            stake=str(event.args.stake),
            reason='',
            challenge_time=timestamp,
            tx_hash=tx_hash
        )
        await self.database.insert_challenge(challenge)
        await self.database.update_order_status(event.args.orderId, status=5)
        logger.info(f"Indexed ChallengeSubmitted #{event.args.orderId}")
