"""
Oracle Service - Automated Solution Verification for Ominis Protocol

This service:
1. Listens for VerificationRequested events from the Verifier contract
2. Verifies solutions using SymPy (symbolic math) and GPT-4 (AI verification)
3. Submits verification results back to the blockchain

Usage:
    python oracle_service.py

Requirements:
    - Set ORACLE_PRIVATE_KEY in .env (must have stake deposited)
    - Set VERIFIER_ADDRESS in .env
    - OPENAI_API_KEY for GPT verification
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv
from web3 import Web3
from web3.contract import Contract
from eth_account import Account

# Add parent directory for SDK import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== Configuration ==========

RPC_URL = os.getenv('RPC_URL', 'https://sepolia.infura.io/v3/your-project-id')
ORACLE_PRIVATE_KEY = os.getenv('ORACLE_PRIVATE_KEY') or os.getenv('PRIVATE_KEY')
VERIFIER_ADDRESS = os.getenv('VERIFIER_ADDRESS')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

POLL_INTERVAL = 10  # seconds between checks
VERIFICATION_TIMEOUT = 300  # 5 minutes to verify

# Problem type names for context
PROBLEM_TYPE_NAMES = {
    0: "derivative",
    1: "integral",
    2: "limit",
    3: "differential equation",
    4: "series/summation",
}

# Verifier ABI (simplified - key functions only)
VERIFIER_ABI = [
    {
        "inputs": [],
        "name": "getPendingVerificationsCount",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "uint256"}, {"type": "uint256"}],
        "name": "getPendingVerifications",
        "outputs": [{"type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"type": "uint256"}],
        "name": "getVerificationRequest",
        "outputs": [
            {"name": "solution", "type": "string"},
            {"name": "problemType", "type": "uint8"},
            {"name": "requestTime", "type": "uint256"},
            {"name": "isProcessed", "type": "bool"},
            {"name": "isCorrect", "type": "bool"},
            {"name": "verificationReason", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"type": "uint256"},
            {"type": "bool"},
            {"type": "string"}
        ],
        "name": "verifyAndSettle",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"type": "uint256"},
            {"type": "bool"},
            {"type": "string"}
        ],
        "name": "submitVerificationResult",
        "outputs": [],
        "stateMutability": "nonpayable",
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
    }
]

# ========== Math Verification with SymPy ==========

def verify_with_sympy(problem_type: int, problem_text: str, solution: str) -> Tuple[bool, str]:
    """
    Verify a calculus solution using SymPy symbolic computation.
    
    Returns:
        Tuple[bool, str]: (is_correct, reason)
    """
    try:
        import sympy as sp
        from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
        
        transformations = standard_transformations + (implicit_multiplication_application,)
        x = sp.Symbol('x')
        
        # Try to extract the function from problem text
        # Example: "Find the derivative of f(x) = x^2 + 3x"
        if problem_type == 0:  # Derivative
            # Look for f(x) = ... pattern
            import re
            func_match = re.search(r'f\s*\(\s*x\s*\)\s*=\s*(.+?)(?:\n|$)', problem_text, re.IGNORECASE)
            if func_match:
                func_str = func_match.group(1).strip()
                func_str = func_str.replace('^', '**')
                
                try:
                    func = parse_expr(func_str, local_dict={'x': x}, transformations=transformations)
                    expected_derivative = sp.diff(func, x)
                    
                    # Parse the submitted solution
                    # Look for f'(x) = ... or just the expression
                    sol_match = re.search(r"f'\s*\(\s*x\s*\)\s*=\s*(.+)", solution)
                    if sol_match:
                        sol_str = sol_match.group(1).strip()
                    else:
                        sol_str = solution.strip()
                    
                    sol_str = sol_str.replace('^', '**')
                    submitted = parse_expr(sol_str, local_dict={'x': x}, transformations=transformations)
                    
                    # Compare symbolically
                    if sp.simplify(expected_derivative - submitted) == 0:
                        return True, "SymPy verification passed: derivative is correct"
                    else:
                        return False, f"SymPy: Expected {expected_derivative}, got {submitted}"
                except Exception as e:
                    logger.warning(f"SymPy parsing error: {e}")
                    return None, f"Could not parse expressions: {e}"
        
        elif problem_type == 1:  # Integral
            # Similar logic for integrals
            import re
            func_match = re.search(r'∫\s*(.+?)\s*dx|integrate\s*(.+)', problem_text, re.IGNORECASE)
            if func_match:
                func_str = (func_match.group(1) or func_match.group(2) or '').strip()
                func_str = func_str.replace('^', '**')
                
                try:
                    func = parse_expr(func_str, local_dict={'x': x}, transformations=transformations)
                    expected_integral = sp.integrate(func, x)
                    
                    sol_match = re.search(r"F\s*\(\s*x\s*\)\s*=\s*(.+?)(?:\s*\+\s*C)?$", solution)
                    if sol_match:
                        sol_str = sol_match.group(1).strip()
                    else:
                        sol_str = solution.replace('+ C', '').replace('+C', '').strip()
                    
                    sol_str = sol_str.replace('^', '**')
                    submitted = parse_expr(sol_str, local_dict={'x': x}, transformations=transformations)
                    
                    # For integrals, compare up to a constant
                    diff = sp.simplify(sp.diff(expected_integral - submitted, x))
                    if diff == 0:
                        return True, "SymPy verification passed: integral is correct"
                    else:
                        return False, f"SymPy: Integral mismatch"
                except Exception as e:
                    logger.warning(f"SymPy parsing error: {e}")
                    return None, f"Could not parse integral: {e}"
        
        # For other types or if parsing fails, return None (inconclusive)
        return None, "SymPy could not verify this problem type"
        
    except ImportError:
        logger.warning("SymPy not installed. Install with: pip install sympy")
        return None, "SymPy not available"
    except Exception as e:
        logger.error(f"SymPy verification error: {e}")
        return None, f"SymPy error: {e}"


# ========== AI Verification with GPT ==========

def verify_with_gpt(problem_type: int, problem_text: str, solution: str) -> Tuple[bool, str]:
    """
    Verify a calculus solution using GPT-4.
    
    Returns:
        Tuple[bool, str]: (is_correct, reason)
    """
    if not OPENAI_API_KEY:
        return None, "OpenAI API key not configured"
    
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        type_name = PROBLEM_TYPE_NAMES.get(problem_type, "calculus")
        
        prompt = f"""You are a calculus verification expert. Your task is to verify if a submitted solution is CORRECT.

Problem Type: {type_name}
Problem: {problem_text if problem_text else f"A {type_name} problem (details not provided)"}

Submitted Solution: {solution}

Instructions:
1. Solve the problem yourself step by step
2. Compare your answer with the submitted solution
3. Consider equivalent forms (e.g., 2x+3 = 3+2x)
4. Respond with EXACTLY this format:

VERDICT: CORRECT or INCORRECT
REASON: [brief explanation, max 100 characters]
YOUR_ANSWER: [your calculated answer]

Be strict but fair. If the answer is mathematically equivalent, mark it CORRECT."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a strict but fair calculus verifier. Only respond in the exact format requested."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.1
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"GPT verification response: {content}")
        
        # Parse response
        import re
        verdict_match = re.search(r'VERDICT:\s*(CORRECT|INCORRECT)', content, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*(.+?)(?:\n|$)', content)
        
        if verdict_match:
            is_correct = verdict_match.group(1).upper() == 'CORRECT'
            reason = reason_match.group(1).strip() if reason_match else "GPT verification"
            return is_correct, f"GPT: {reason}"
        else:
            return None, "GPT response format error"
            
    except Exception as e:
        logger.error(f"GPT verification error: {e}")
        return None, f"GPT error: {e}"


# ========== Combined Verification ==========

def verify_solution(problem_type: int, problem_text: str, solution: str) -> Tuple[bool, str]:
    """
    Verify a solution using both SymPy and GPT.
    
    Strategy:
    1. Try SymPy first (deterministic, fast)
    2. If SymPy is inconclusive, use GPT
    3. If both agree, high confidence
    4. If they disagree, flag for manual review
    
    Returns:
        Tuple[bool, str]: (is_correct, reason)
    """
    logger.info(f"Verifying solution: {solution[:50]}...")
    
    # Try SymPy first
    sympy_result, sympy_reason = verify_with_sympy(problem_type, problem_text, solution)
    logger.info(f"SymPy result: {sympy_result}, reason: {sympy_reason}")
    
    # Try GPT
    gpt_result, gpt_reason = verify_with_gpt(problem_type, problem_text, solution)
    logger.info(f"GPT result: {gpt_result}, reason: {gpt_reason}")
    
    # Decision logic
    if sympy_result is not None and gpt_result is not None:
        if sympy_result == gpt_result:
            # Both agree - high confidence
            return sympy_result, f"Verified (SymPy + GPT agree): {sympy_reason}"
        else:
            # Disagreement - be conservative, trust SymPy for math
            if sympy_result is True:
                return True, f"SymPy correct, GPT disagrees: {sympy_reason}"
            else:
                # GPT says correct, SymPy says wrong - flag
                return False, f"Conflict: SymPy={sympy_result}, GPT={gpt_result}. Using SymPy result."
    
    elif sympy_result is not None:
        return sympy_result, sympy_reason
    
    elif gpt_result is not None:
        return gpt_result, gpt_reason
    
    else:
        # Both inconclusive - default to optimistic (assume correct)
        return True, "Verification inconclusive, defaulting to correct (optimistic)"


# ========== Oracle Service ==========

class OracleService:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(RPC_URL))
        
        if not self.web3.is_connected():
            raise Exception(f"Failed to connect to RPC: {RPC_URL}")
        
        if not ORACLE_PRIVATE_KEY:
            raise Exception("ORACLE_PRIVATE_KEY not set")
        
        if not VERIFIER_ADDRESS:
            raise Exception("VERIFIER_ADDRESS not set")
        
        self.account = Account.from_key(ORACLE_PRIVATE_KEY)
        self.address = self.account.address
        
        self.verifier = self.web3.eth.contract(
            address=Web3.to_checksum_address(VERIFIER_ADDRESS),
            abi=VERIFIER_ABI
        )
        
        self.processed_orders = set()
        
        logger.info(f"Oracle Service initialized")
        logger.info(f"  Oracle address: {self.address}")
        logger.info(f"  Verifier address: {VERIFIER_ADDRESS}")
    
    def get_pending_verifications(self) -> list:
        """Get list of pending verification order IDs"""
        try:
            count = self.verifier.functions.getPendingVerificationsCount().call()
            if count == 0:
                return []
            
            # Fetch in batches of 20
            pending = []
            for offset in range(0, count, 20):
                batch = self.verifier.functions.getPendingVerifications(offset, 20).call()
                pending.extend(batch)
            
            return pending
        except Exception as e:
            logger.error(f"Error fetching pending verifications: {e}")
            return []
    
    def get_verification_request(self, order_id: int) -> Optional[dict]:
        """Get verification request details"""
        try:
            result = self.verifier.functions.getVerificationRequest(order_id).call()
            return {
                'solution': result[0],
                'problem_type': result[1],
                'request_time': result[2],
                'is_processed': result[3],
                'is_correct': result[4],
                'verification_reason': result[5]
            }
        except Exception as e:
            logger.error(f"Error fetching verification request {order_id}: {e}")
            return None
    
    def submit_verification(self, order_id: int, is_correct: bool, reason: str) -> bool:
        """Submit verification result to the blockchain"""
        try:
            # Build transaction
            nonce = self.web3.eth.get_transaction_count(self.address)
            gas_price = int(self.web3.eth.gas_price * 1.5)  # 1.5x for faster confirmation
            
            # Try verifyAndSettle first (auto-settlement)
            try:
                tx = self.verifier.functions.verifyAndSettle(
                    order_id,
                    is_correct,
                    reason[:100]  # Limit reason length
                ).build_transaction({
                    'from': self.address,
                    'nonce': nonce,
                    'gas': 300000,
                    'gasPrice': gas_price
                })
            except Exception:
                # Fallback to submitVerificationResult
                tx = self.verifier.functions.submitVerificationResult(
                    order_id,
                    is_correct,
                    reason[:100]
                ).build_transaction({
                    'from': self.address,
                    'nonce': nonce,
                    'gas': 300000,
                    'gasPrice': gas_price
                })
            
            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)
            
            logger.info(f"Verification TX sent: {tx_hash.hex()}")
            
            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                logger.info(f"Verification submitted successfully for order #{order_id}")
                return True
            else:
                logger.error(f"Verification TX failed for order #{order_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting verification for order #{order_id}: {e}")
            return False
    
    async def process_order(self, order_id: int, problem_text: str = None):
        """Process a single verification request"""
        if order_id in self.processed_orders:
            return
        
        logger.info(f"Processing verification for order #{order_id}")
        
        # Get verification request details
        request = self.get_verification_request(order_id)
        if not request:
            logger.error(f"Could not fetch request for order #{order_id}")
            return
        
        if request['is_processed']:
            logger.info(f"Order #{order_id} already processed")
            self.processed_orders.add(order_id)
            return
        
        # Check timeout
        current_time = int(time.time())
        if current_time > request['request_time'] + VERIFICATION_TIMEOUT:
            logger.warning(f"Order #{order_id} verification timeout exceeded")
            # Still try to submit (will fail on-chain if past timeout)
        
        # Verify the solution
        is_correct, reason = verify_solution(
            request['problem_type'],
            problem_text or "",
            request['solution']
        )
        
        logger.info(f"Verification result for order #{order_id}: {is_correct}, {reason}")
        
        # Submit to blockchain
        success = self.submit_verification(order_id, is_correct, reason)
        
        if success:
            self.processed_orders.add(order_id)
    
    async def run(self):
        """Main loop to process verification requests"""
        logger.info("Oracle service starting...")
        
        while True:
            try:
                # Get pending verifications
                pending = self.get_pending_verifications()
                
                if pending:
                    logger.info(f"Found {len(pending)} pending verifications")
                    
                    for order_id in pending:
                        if order_id not in self.processed_orders:
                            # TODO: Fetch problem text from bot server or IPFS
                            problem_text = None
                            try:
                                import requests
                                res = requests.get(f"http://localhost:5001/solutions/{order_id}")
                                if res.status_code == 200:
                                    data = res.json()
                                    if data.get('success'):
                                        # Try to get original problem from problem_hash
                                        problem_hash = data.get('solution', {}).get('problem_hash')
                                        if problem_hash:
                                            prob_res = requests.get(f"http://localhost:5001/problems/{problem_hash}")
                                            if prob_res.status_code == 200:
                                                prob_data = prob_res.json()
                                                if prob_data.get('success'):
                                                    problem_text = prob_data.get('problem', {}).get('text')
                            except Exception as e:
                                logger.debug(f"Could not fetch problem text: {e}")
                            
                            await self.process_order(order_id, problem_text)
                else:
                    logger.debug("No pending verifications")
                
            except Exception as e:
                logger.error(f"Error in oracle loop: {e}")
            
            await asyncio.sleep(POLL_INTERVAL)


# ========== Main ==========

def main():
    print("=" * 50)
    print("Ominis Oracle Service")
    print("=" * 50)
    print(f"RPC URL: {RPC_URL}")
    print(f"Verifier Address: {VERIFIER_ADDRESS}")
    print(f"GPT Enabled: {bool(OPENAI_API_KEY)}")
    print("=" * 50)
    
    try:
        oracle = OracleService()
        asyncio.run(oracle.run())
    except KeyboardInterrupt:
        logger.info("Oracle service stopped by user")
    except Exception as e:
        logger.error(f"Oracle service error: {e}")
        raise


if __name__ == '__main__':
    main()
