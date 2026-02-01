"""
Ominis Oracle Node

Listens for verification requests from the blockchain,
calls the Verifier API, and submits results back on-chain.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from web3 import Web3, AsyncWeb3
from web3.middleware import geth_poa_middleware
from eth_account import Account
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OracleNode")


@dataclass
class OracleConfig:
    """Oracle configuration"""
    rpc_url: str
    private_key: str
    verifier_contract: str
    verifier_api_url: str
    poll_interval: int = 5  # seconds
    
    @classmethod
    def from_env(cls) -> "OracleConfig":
        return cls(
            rpc_url=os.getenv("RPC_URL", ""),
            private_key=os.getenv("ORACLE_PRIVATE_KEY", ""),
            verifier_contract=os.getenv("VERIFIER_CONTRACT", ""),
            verifier_api_url=os.getenv("VERIFIER_API_URL", "http://localhost:8000"),
        )


# Minimal Verifier ABI for oracle operations
VERIFIER_ABI = [
    {
        "inputs": [{"name": "offset", "type": "uint256"}, {"name": "limit", "type": "uint256"}],
        "name": "getPendingVerifications",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getPendingVerificationsCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "orderId", "type": "uint256"},
            {"name": "isCorrect", "type": "bool"},
            {"name": "reason", "type": "string"}
        ],
        "name": "submitVerificationResult",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "orderId", "type": "uint256"},
            {"name": "challengerWon", "type": "bool"}
        ],
        "name": "resolveChallenge",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "orderId", "type": "uint256"}],
        "name": "isUnderChallenge",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderId", "type": "uint256"},
            {"indexed": False, "name": "solution", "type": "string"},
            {"indexed": False, "name": "problemType", "type": "uint8"}
        ],
        "name": "VerificationRequested",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderId", "type": "uint256"},
            {"indexed": True, "name": "challenger", "type": "address"},
            {"indexed": False, "name": "reason", "type": "string"}
        ],
        "name": "ChallengeCreated",
        "type": "event"
    }
]

# OrderBook ABI for getting problem details
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
    }
]


class OracleNode:
    """
    Oracle node that bridges on-chain verification requests
    with off-chain AI/CAS verification.
    """
    
    def __init__(self, config: OracleConfig):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        
        # Add PoA middleware for networks like Arbitrum
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        self.account = Account.from_key(config.private_key)
        self.verifier = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.verifier_contract),
            abi=VERIFIER_ABI
        )
        
        self.http_client = httpx.AsyncClient()
        self.running = False
        self.processed_orders = set()
        
    async def start(self):
        """Start the oracle node"""
        logger.info("=" * 50)
        logger.info("Ominis Oracle Node Starting")
        logger.info(f"Address: {self.account.address}")
        logger.info(f"Verifier Contract: {self.config.verifier_contract}")
        logger.info(f"API URL: {self.config.verifier_api_url}")
        logger.info("=" * 50)
        
        self.running = True
        
        # Start listeners
        await asyncio.gather(
            self._poll_pending_verifications(),
            self._listen_for_events()
        )
    
    async def stop(self):
        """Stop the oracle node"""
        logger.info("Stopping oracle node...")
        self.running = False
        await self.http_client.aclose()
    
    async def _poll_pending_verifications(self):
        """Poll for pending verification requests"""
        while self.running:
            try:
                count = self.verifier.functions.getPendingVerificationsCount().call()
                
                if count > 0:
                    logger.info(f"Found {count} pending verifications")
                    
                    # Get pending order IDs
                    order_ids = self.verifier.functions.getPendingVerifications(0, min(count, 10)).call()
                    
                    for order_id in order_ids:
                        if order_id not in self.processed_orders:
                            await self._process_verification(order_id)
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(self.config.poll_interval)
    
    async def _listen_for_events(self):
        """Listen for new verification request events"""
        # Event filter for VerificationRequested
        event_filter = self.verifier.events.VerificationRequested.create_filter(fromBlock='latest')
        challenge_filter = self.verifier.events.ChallengeCreated.create_filter(fromBlock='latest')
        
        while self.running:
            try:
                # Check for new verification requests
                for event in event_filter.get_new_entries():
                    order_id = event.args.orderId
                    logger.info(f"New verification request: Order #{order_id}")
                    await self._process_verification(order_id)
                
                # Check for new challenges
                for event in challenge_filter.get_new_entries():
                    order_id = event.args.orderId
                    logger.info(f"New challenge: Order #{order_id}")
                    await self._process_challenge(order_id)
                    
            except Exception as e:
                logger.error(f"Event listener error: {e}")
            
            await asyncio.sleep(2)
    
    async def _process_verification(self, order_id: int):
        """Process a single verification request"""
        if order_id in self.processed_orders:
            return
        
        logger.info(f"Processing verification for Order #{order_id}")
        
        try:
            # Get problem details (would need OrderBook address)
            # For now, we fetch from the API which might have indexed it
            
            # Call verification API
            response = await self.http_client.post(
                f"{self.config.verifier_api_url}/api/verify",
                json={
                    "order_id": order_id,
                    "problem": "Problem text would come from IPFS/indexer",
                    "solution": "Solution would come from SolutionManager",
                    "problem_type": 0  # Would come from order
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Submit result on-chain
                await self._submit_verification_result(
                    order_id=order_id,
                    is_correct=result["is_correct"],
                    reason=result.get("reason", "")
                )
                
                self.processed_orders.add(order_id)
                logger.info(f"Order #{order_id} verified: {result['is_correct']}")
            else:
                logger.error(f"API error for Order #{order_id}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Verification processing error: {e}")
    
    async def _process_challenge(self, order_id: int):
        """Process a challenge"""
        logger.info(f"Processing challenge for Order #{order_id}")
        
        try:
            # Call challenge API
            response = await self.http_client.post(
                f"{self.config.verifier_api_url}/api/challenge",
                json={
                    "order_id": order_id,
                    "problem": "Problem text",
                    "submitted_solution": "Solution",
                    "problem_type": 0,
                    "challenger_reason": "Reason"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Submit challenge resolution on-chain
                await self._submit_challenge_resolution(
                    order_id=order_id,
                    challenger_won=result["challenger_wins"]
                )
                
                logger.info(f"Challenge #{order_id} resolved: challenger {'won' if result['challenger_wins'] else 'lost'}")
            else:
                logger.error(f"Challenge API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Challenge processing error: {e}")
    
    async def _submit_verification_result(
        self,
        order_id: int,
        is_correct: bool,
        reason: str
    ):
        """Submit verification result to the blockchain"""
        try:
            tx = self.verifier.functions.submitVerificationResult(
                order_id,
                is_correct,
                reason
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"Verification result submitted: TX {tx_hash.hex()}")
            return receipt
            
        except Exception as e:
            logger.error(f"Failed to submit verification result: {e}")
            raise
    
    async def _submit_challenge_resolution(
        self,
        order_id: int,
        challenger_won: bool
    ):
        """Submit challenge resolution to the blockchain"""
        try:
            tx = self.verifier.functions.resolveChallenge(
                order_id,
                challenger_won
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"Challenge resolution submitted: TX {tx_hash.hex()}")
            return receipt
            
        except Exception as e:
            logger.error(f"Failed to submit challenge resolution: {e}")
            raise


async def main():
    """Main entry point"""
    from dotenv import load_dotenv
    load_dotenv()
    
    config = OracleConfig.from_env()
    
    if not config.rpc_url or not config.private_key or not config.verifier_contract:
        logger.error("Missing required environment variables!")
        logger.error("Required: RPC_URL, ORACLE_PRIVATE_KEY, VERIFIER_CONTRACT")
        sys.exit(1)
    
    oracle = OracleNode(config)
    
    try:
        await oracle.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt")
        await oracle.stop()


if __name__ == "__main__":
    asyncio.run(main())
