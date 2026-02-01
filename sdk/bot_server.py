"""
Bot API Server - Controls the Python SDK Bot from Frontend
Run this server, then the frontend can start/stop the bot via API calls.

Usage:
    python bot_server.py

API Endpoints:
    GET  /status     - Get bot status
    POST /start      - Start the bot
    POST /stop       - Stop the bot
    GET  /logs       - Get recent logs
    GET  /config     - Get bot config
    POST /config     - Update bot config
"""

import os
import sys
import json
import asyncio
import threading
import logging
import re
import hashlib
from datetime import datetime
from typing import Optional
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Add parent directory for SDK import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ominis_sdk import OminisSDK, Order, ProblemType, TimeTier, OrderStatus

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# ========== Bot State ==========

class BotState:
    def __init__(self):
        self.running = False
        self.sdk: Optional[OminisSDK] = None
        self.logs = []
        self.stats = {
            'orders_accepted': 0,
            'orders_solved': 0,
            'total_earned': 0.0,
        }
        self.config = {
            'auto_accept': True,
            'auto_solve': True,
            'max_concurrent': 3,
            'poll_interval': 5.0,
            'accepted_types': [0, 1, 2, 3, 4],
        }
        self.active_orders = set()
        self.bot_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

    def add_log(self, message: str, level: str = 'info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'level': level
        }
        self.logs.append(log_entry)
        # Keep only last 100 logs
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]
        
        # Also log to console
        if level == 'error':
            logger.error(message)
        elif level == 'warning':
            logger.warning(message)
        else:
            logger.info(message)

bot_state = BotState()

# ========== Math Solver ==========

# OpenAI client (lazy init)
openai_client = None

def get_openai_client():
    global openai_client
    if openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                import openai
                openai_client = openai.OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI package not installed. Run: pip install openai")
            except Exception as e:
                logger.error(f"Failed to init OpenAI: {e}")
    return openai_client

PROBLEM_TYPE_NAMES = {
    0: "derivative",
    1: "integral", 
    2: "limit",
    3: "differential equation",
    4: "series/summation",
}

def solve_with_gpt(problem_type: int, problem_text: str = None) -> dict:
    """
    Solve a calculus problem using ChatGPT with step-by-step explanation.
    Returns dict with 'answer' and 'steps'.
    """
    client = get_openai_client()
    if not client:
        fallback = solve_problem_fallback(problem_type)
        return {'answer': fallback, 'steps': []}
    
    type_name = PROBLEM_TYPE_NAMES.get(problem_type, "calculus")
    
    # If we don't have the actual problem text, generate a generic prompt
    if problem_text:
        prompt = f"""You are a calculus expert. Solve this {type_name} problem step by step:

{problem_text}

Format your response EXACTLY like this (use these exact markers):
STEPS:
1. [First step description] => [Result of this step]
2. [Second step description] => [Result of this step]
3. [Continue as needed] => [Result]

ANSWER: [final answer only, e.g., f'(x) = 2x + 3]

Example for derivative of f(x) = x² + 3x:
STEPS:
1. Apply power rule to x²: d/dx(x²) = 2x => 2x
2. Apply constant multiple rule to 3x: d/dx(3x) = 3 => 3
3. Sum the derivatives => 2x + 3

ANSWER: f'(x) = 2x + 3"""
    else:
        # Generic response when we don't have the problem text
        prompt = f"""You are a calculus expert. Generate a typical {type_name} problem and solve it step by step.

Format your response EXACTLY like this:
STEPS:
1. [First step description] => [Result of this step]
2. [Second step description] => [Result of this step]

ANSWER: [final answer only]"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap
            messages=[
                {"role": "system", "content": "You are a calculus solver that shows clear step-by-step work. Always use the exact format requested with STEPS: and ANSWER: markers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        logger.info(f"GPT response: {content[:200]}...")
        
        # Parse the response
        result = parse_gpt_solution(content)
        logger.info(f"Parsed: answer={result['answer']}, steps={len(result['steps'])}")
        return result
    except Exception as e:
        logger.error(f"GPT error: {e}")
        fallback = solve_problem_fallback(problem_type)
        return {'answer': fallback, 'steps': []}


def parse_gpt_solution(content: str) -> dict:
    """Parse GPT response into answer and steps."""
    result = {'answer': '', 'steps': []}
    
    # Extract answer
    answer_match = re.search(r'ANSWER:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
    if answer_match:
        result['answer'] = answer_match.group(1).strip()
    else:
        # Fallback: use last line or whole content
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        result['answer'] = lines[-1] if lines else content
    
    # Extract steps
    steps_match = re.search(r'STEPS:\s*\n([\s\S]*?)(?:ANSWER:|$)', content, re.IGNORECASE)
    if steps_match:
        steps_text = steps_match.group(1).strip()
        step_lines = re.findall(r'^\d+\.\s*(.+)', steps_text, re.MULTILINE)
        
        for i, step_line in enumerate(step_lines):
            # Parse "description => result" format
            if '=>' in step_line:
                parts = step_line.split('=>', 1)
                step_content = parts[0].strip()
                step_result = parts[1].strip() if len(parts) > 1 else ''
            else:
                step_content = step_line.strip()
                step_result = ''
            
            result['steps'].append({
                'step': i + 1,
                'content': step_content,
                'result': step_result
            })
    
    return result

def solve_problem_fallback(problem_type: int) -> dict:
    """
    Fallback solutions when GPT is not available.
    Returns dict with 'answer' and 'steps' for consistency.
    """
    fallback_data = {
        0: {
            'answer': "f'(x) = 2x + 3",
            'steps': [
                {'step': 1, 'content': 'Apply power rule to x²', 'result': '2x'},
                {'step': 2, 'content': 'Apply constant rule to 3x', 'result': '3'},
                {'step': 3, 'content': 'Combine terms', 'result': '2x + 3'}
            ]
        },
        1: {
            'answer': "F(x) = x^2/2 + C",
            'steps': [
                {'step': 1, 'content': 'Apply power rule: ∫x dx = x²/2', 'result': 'x²/2'},
                {'step': 2, 'content': 'Add constant of integration', 'result': '+ C'}
            ]
        },
        2: {
            'answer': "lim = 1",
            'steps': [
                {'step': 1, 'content': 'Direct substitution', 'result': '1'}
            ]
        },
        3: {
            'answer': "y = Ce^x + x",
            'steps': [
                {'step': 1, 'content': 'Find homogeneous solution', 'result': 'Ce^x'},
                {'step': 2, 'content': 'Find particular solution', 'result': 'x'},
                {'step': 3, 'content': 'Combine solutions', 'result': 'Ce^x + x'}
            ]
        },
        4: {
            'answer': "Sum = n(n+1)/2",
            'steps': [
                {'step': 1, 'content': 'Apply arithmetic series formula', 'result': 'n(n+1)/2'}
            ]
        },
    }
    default = {'answer': f"Solution for type {problem_type}", 'steps': []}
    return fallback_data.get(problem_type, default)

def solve_problem(problem_type: int, problem_hash: str, problem_text: str = None) -> dict:
    """
    Main solve function - tries GPT first, falls back to placeholder.
    Returns dict with 'answer' and 'steps'.
    """
    # Try GPT if API key is configured
    if os.getenv('OPENAI_API_KEY'):
        return solve_with_gpt(problem_type, problem_text)
    
    # Fallback to placeholder
    return solve_problem_fallback(problem_type)

# ========== Bot Logic ==========

def bot_loop():
    """Main bot loop running in a separate thread"""
    bot_state.add_log('[BOT] Starting bot loop...', 'info')
    
    # Initialize SDK
    private_key = os.getenv('PRIVATE_KEY')
    rpc_url = os.getenv('RPC_URL')
    core_address = os.getenv('CORE_ADDRESS')
    orderbook_address = os.getenv('ORDERBOOK_ADDRESS')
    
    if not all([private_key, rpc_url, core_address]):
        bot_state.add_log('[BOT] Missing environment variables!', 'error')
        bot_state.running = False
        return
    
    try:
        sdk = OminisSDK(
            private_key=private_key,
            rpc_url=rpc_url,
            core_address=core_address
        )
        if orderbook_address:
            sdk.set_orderbook_address(orderbook_address)
        
        bot_state.sdk = sdk
        bot_state.add_log(f'[BOT] Connected! Address: {sdk.address}', 'success')
        bot_state.add_log(f'[BOT] ETH Balance: {sdk.get_balance_eth():.4f}', 'info')
        
    except Exception as e:
        bot_state.add_log(f'[BOT] Failed to initialize SDK: {e}', 'error')
        bot_state.running = False
        return
    
    # Main loop
    while not bot_state.stop_event.is_set():
        try:
            # Run async operations in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Get open orders
            orders = loop.run_until_complete(sdk.get_open_orders(limit=20))
            bot_state.add_log(f'[BOT] Found {len(orders)} open orders', 'info')
            
            # Find eligible order
            for order in orders:
                if bot_state.stop_event.is_set():
                    break
                    
                # Skip if already processing
                if order.id in bot_state.active_orders:
                    bot_state.add_log(f'[BOT] Order #{order.id}: Already processing, skip', 'info')
                    continue
                
                # Skip own orders
                if order.issuer.lower() == sdk.address.lower():
                    bot_state.add_log(f'[BOT] Order #{order.id}: Own order (issuer={order.issuer[:10]}... == bot={sdk.address[:10]}...), skip', 'info')
                    continue
                else:
                    bot_state.add_log(f'[BOT] Order #{order.id}: Different issuer (issuer={order.issuer[:10]}... != bot={sdk.address[:10]}...), OK', 'info')
                
                # Check type filter
                if order.problem_type.value not in bot_state.config['accepted_types']:
                    bot_state.add_log(f'[BOT] Order #{order.id}: Type {order.problem_type.name} not accepted, skip', 'info')
                    continue
                
                # Check concurrent limit
                if len(bot_state.active_orders) >= bot_state.config['max_concurrent']:
                    bot_state.add_log(f'[BOT] Order #{order.id}: Concurrent limit reached, skip', 'info')
                    continue
                
                # Check time remaining
                if order.time_remaining < 60:
                    bot_state.add_log(f'[BOT] Order #{order.id}: Only {order.time_remaining}s remaining, skip', 'info')
                    continue
                
                # Process this order
                bot_state.add_log(f'[BOT] Processing order #{order.id} ({order.problem_type.name})', 'info')
                bot_state.active_orders.add(order.id)
                
                try:
                    # Step 1: Accept
                    if bot_state.config['auto_accept']:
                        bot_state.add_log(f'[BOT] Accepting order #{order.id}...', 'info')
                        receipt = loop.run_until_complete(sdk.accept_order(order.id))
                        if receipt.success:
                            bot_state.add_log(f'[BOT] Order #{order.id} accepted!', 'success')
                            bot_state.stats['orders_accepted'] += 1
                        else:
                            bot_state.add_log(f'[BOT] Failed to accept order #{order.id}', 'error')
                            continue
                    
                    # Step 2: Solve
                    if bot_state.config['auto_solve']:
                        # Try to get problem text from storage (normalize to 0x prefix)
                        raw_hash = order.problem_hash.hex().lower()
                        problem_hash = '0x' + raw_hash if not raw_hash.startswith('0x') else raw_hash
                        
                        # Debug: show what we're looking for
                        bot_state.add_log(f'[BOT] Looking for hash: {problem_hash[:18]}...', 'info')
                        bot_state.add_log(f'[BOT] Storage has {len(problem_storage)} problems: {list(problem_storage.keys())[:3]}', 'info')
                        
                        problem_text = None
                        if problem_hash in problem_storage:
                            problem_text = problem_storage[problem_hash].get('text')
                        
                        if problem_text:
                            bot_state.add_log(f'[BOT] Found problem: {problem_text[:50]}...', 'info')
                        else:
                            bot_state.add_log(f'[BOT] Problem text NOT FOUND for hash {problem_hash[:18]}', 'warning')
                        
                        bot_state.add_log(f'[BOT] Solving with {"GPT" if os.getenv("OPENAI_API_KEY") else "fallback"}...', 'info')
                        solution_data = solve_problem(order.problem_type.value, problem_hash, problem_text)
                        solution = solution_data['answer']
                        steps = solution_data.get('steps', [])
                        bot_state.add_log(f'[BOT] Solution: {solution} ({len(steps)} steps)', 'success')
                        
                        # Store solution with steps for frontend
                        store_solution_data(order.id, problem_hash, solution_data)
                        
                        # Step 3: Submit (commit + reveal)
                        # Re-check order status before submitting
                        fresh_order = loop.run_until_complete(sdk.get_order(order.id))
                        bot_state.add_log(f'[BOT] Order status: {fresh_order.status.name}, time left: {fresh_order.time_remaining}s, solver: {fresh_order.solver[:10]}...', 'info')
                        
                        if fresh_order.time_remaining < 30:
                            bot_state.add_log(f'[BOT] WARNING: Only {fresh_order.time_remaining}s left!', 'warning')
                        
                        if fresh_order.solver.lower() != sdk.address.lower():
                            bot_state.add_log(f'[BOT] ERROR: Someone else accepted! Solver={fresh_order.solver[:10]}... but we are {sdk.address[:10]}...', 'error')
                            continue
                        
                        # Check if already committed
                        if fresh_order.status.name == 'COMMITTED':
                            bot_state.add_log(f'[BOT] Order already committed, need salt to reveal (skipping)', 'warning')
                            continue
                        
                        # Generate salt and commit manually (so we can retry reveal)
                        salt = os.urandom(32)
                        
                        bot_state.add_log(f'[BOT] Step 1: Committing solution...', 'info')
                        try:
                            commit_receipt = loop.run_until_complete(
                                sdk.commit_solution(order.id, solution, salt)
                            )
                            
                            bot_state.add_log(f'[BOT] Commit TX: {commit_receipt.tx_hash}', 'info')
                            
                            # Check commit status with retries (blockchain propagation can be slow)
                            committed = commit_receipt.success
                            if not committed:
                                bot_state.add_log(f'[BOT] Commit receipt shows failure, waiting and checking...', 'warning')
                                for retry in range(5):
                                    loop.run_until_complete(asyncio.sleep(3))
                                    check_order = loop.run_until_complete(sdk.get_order(order.id))
                                    bot_state.add_log(f'[BOT] Retry {retry+1}/5: Order status = {check_order.status.name}', 'info')
                                    if check_order.status.name == 'COMMITTED':
                                        committed = True
                                        bot_state.add_log(f'[BOT] Order is COMMITTED! Proceeding to reveal...', 'success')
                                        break
                                
                                if not committed:
                                    bot_state.add_log(f'[BOT] Commit failed after retries. Check TX on Etherscan: {commit_receipt.tx_hash}', 'error')
                                    continue
                            else:
                                bot_state.add_log(f'[BOT] Commit SUCCESS!', 'success')
                                # Wait a bit for state to propagate
                                loop.run_until_complete(asyncio.sleep(3))
                            
                            bot_state.add_log(f'[BOT] Step 2: Revealing solution...', 'info')
                            reveal_receipt = loop.run_until_complete(
                                sdk.reveal_solution(order.id, solution, salt)
                            )
                            
                            if reveal_receipt.success:
                                bot_state.add_log(f'[BOT] Order #{order.id} SOLVED! TX: {reveal_receipt.tx_hash[:16]}...', 'success')
                                bot_state.stats['orders_solved'] += 1
                                bot_state.stats['total_earned'] += order.reward_in_usdc()
                            else:
                                bot_state.add_log(f'[BOT] Reveal failed! TX: {reveal_receipt.tx_hash[:16]}...', 'error')
                                
                        except Exception as submit_err:
                            bot_state.add_log(f'[BOT] Submit error: {submit_err}', 'error')
                            # Check final order status
                            try:
                                final_order = loop.run_until_complete(sdk.get_order(order.id))
                                bot_state.add_log(f'[BOT] Final order status: {final_order.status.name}', 'info')
                            except:
                                pass
                
                except Exception as e:
                    bot_state.add_log(f'[BOT] Error processing order #{order.id}: {e}', 'error')
                
                finally:
                    bot_state.active_orders.discard(order.id)
            
            loop.close()
            
        except Exception as e:
            bot_state.add_log(f'[BOT] Error in main loop: {e}', 'error')
        
        # Wait before next iteration
        bot_state.stop_event.wait(bot_state.config['poll_interval'])
    
    bot_state.add_log('[BOT] Bot stopped.', 'warning')
    bot_state.running = False

# ========== Auto-Solver for Subscription Mode ==========
# Monitors OrderAssignedToBot events and automatically solves assigned problems

from web3 import Web3

# Core contract ABI extension for OrderAssignedToBot event
CORE_EXTENDED_ABI = [
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


class AutoSolver:
    """
    Monitors OrderAssignedToBot events and automatically solves assigned problems.
    
    In subscription mode, problems are assigned directly to bots without needing
    to call acceptOrder. The bot just needs to commit and reveal the solution.
    """
    
    def __init__(self, sdk, bot_state_ref):
        self.sdk = sdk
        self.bot_state = bot_state_ref
        self.bot_address = sdk.address
        self.processed_orders = set()
        self.running = False
        self.w3 = sdk.w3
        
        # Initialize Core contract with extended ABI
        core_address = os.getenv('CORE_ADDRESS')
        if core_address:
            self.core_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(core_address),
                abi=CORE_EXTENDED_ABI
            )
        else:
            self.core_contract = None
        
        self.last_block = 0
    
    def log(self, message: str, level: str = 'info'):
        """Log message through bot_state"""
        self.bot_state.add_log(f'[AUTO-SOLVER] {message}', level)
    
    def get_order_bot(self, order_id: int) -> str:
        """Get the bot assigned to an order"""
        if not self.core_contract:
            return None
        try:
            return self.core_contract.functions.getOrderBot(order_id).call()
        except Exception as e:
            self.log(f'Error getting order bot: {e}', 'error')
            return None
    
    def get_assigned_orders_from_events(self, from_block: int = None) -> list:
        """
        Get orders assigned to this bot by scanning OrderAssignedToBot events.
        Returns list of order IDs assigned to this bot.
        """
        if not self.core_contract:
            return []
        
        try:
            if from_block is None:
                # Get recent blocks only (last ~100 blocks)
                current_block = self.w3.eth.block_number
                from_block = max(0, current_block - 100)
            
            # Create event filter for OrderAssignedToBot events where bot == our address
            # Note: web3.py uses from_block (snake_case) not fromBlock (camelCase)
            event_filter = self.core_contract.events.OrderAssignedToBot.create_filter(
                from_block=from_block,
                argument_filters={'bot': self.bot_address}
            )
            
            events = event_filter.get_all_entries()
            order_ids = [event.args.orderId for event in events]
            
            if order_ids:
                self.log(f'Found {len(order_ids)} assigned orders from events: {order_ids}', 'info')
            
            return order_ids
            
        except Exception as e:
            self.log(f'Error getting assigned orders from events: {e}', 'error')
            return []
    
    def check_order_needs_solving(self, order_id: int) -> dict:
        """
        Check if an order needs solving by this bot.
        Returns order info dict if needs solving, None otherwise.
        """
        try:
            # Skip if already processed
            if order_id in self.processed_orders:
                return None
            
            # Get order details
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            order = loop.run_until_complete(self.sdk.get_order(order_id))
            loop.close()
            
            # Check if assigned to us
            assigned_bot = self.get_order_bot(order_id)
            if not assigned_bot or assigned_bot.lower() != self.bot_address.lower():
                return None
            
            # Check order status - we can solve if OPEN (subscription mode doesn't need accept)
            # or ACCEPTED (if we somehow accepted it)
            if order.status.name not in ['OPEN', 'ACCEPTED']:
                self.log(f'Order #{order_id} status is {order.status.name}, skipping', 'info')
                return None
            
            # Check time remaining
            if order.time_remaining < 30:
                self.log(f'Order #{order_id} has only {order.time_remaining}s remaining, skipping', 'warning')
                return None
            
            return {
                'order': order,
                'assigned_bot': assigned_bot
            }
            
        except Exception as e:
            self.log(f'Error checking order #{order_id}: {e}', 'error')
            return None
    
    def solve_and_submit(self, order_id: int, order) -> bool:
        """
        Solve the problem and submit solution (commit + reveal).
        Returns True if successful.
        """
        try:
            self.log(f'Solving order #{order_id} ({order.problem_type.name})...', 'info')
            
            # Get problem hash
            raw_hash = order.problem_hash.hex().lower()
            problem_hash = '0x' + raw_hash if not raw_hash.startswith('0x') else raw_hash
            
            # Try to get problem text from storage
            problem_text = None
            if problem_hash in problem_storage:
                problem_text = problem_storage[problem_hash].get('text')
                self.log(f'Found problem text: {problem_text[:50]}...', 'info')
            else:
                self.log(f'Problem text not found for hash {problem_hash[:18]}...', 'warning')
            
            # Solve the problem
            self.log(f'Solving with {"GPT" if os.getenv("OPENAI_API_KEY") else "fallback"}...', 'info')
            solution_data = solve_problem(order.problem_type.value, problem_hash, problem_text)
            solution = solution_data['answer']
            steps = solution_data.get('steps', [])
            self.log(f'Solution: {solution} ({len(steps)} steps)', 'success')
            
            # Store solution for frontend
            store_solution_data(order_id, problem_hash, solution_data)
            
            # Generate salt for commit-reveal
            salt = os.urandom(32)
            
            # Create async loop for blockchain operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Step 1: Commit solution
                self.log(f'Committing solution for order #{order_id}...', 'info')
                commit_receipt = loop.run_until_complete(
                    self.sdk.commit_solution(order_id, solution, salt)
                )
                self.log(f'Commit TX: {commit_receipt.tx_hash}', 'info')
                
                if not commit_receipt.success:
                    # Wait and check if commit actually succeeded
                    for retry in range(3):
                        loop.run_until_complete(asyncio.sleep(3))
                        check_order = loop.run_until_complete(self.sdk.get_order(order_id))
                        if check_order.status.name == 'COMMITTED':
                            self.log(f'Commit confirmed after retry', 'success')
                            break
                    else:
                        self.log(f'Commit failed for order #{order_id}', 'error')
                        return False
                
                # Wait for commit to propagate
                loop.run_until_complete(asyncio.sleep(3))
                
                # Step 2: Reveal solution
                self.log(f'Revealing solution for order #{order_id}...', 'info')
                reveal_receipt = loop.run_until_complete(
                    self.sdk.reveal_solution(order_id, solution, salt)
                )
                
                if reveal_receipt.success:
                    self.log(f'Order #{order_id} SOLVED! TX: {reveal_receipt.tx_hash[:16]}...', 'success')
                    self.bot_state.stats['orders_solved'] += 1
                    return True
                else:
                    self.log(f'Reveal failed for order #{order_id}: {reveal_receipt.tx_hash}', 'error')
                    return False
                    
            finally:
                loop.close()
                
        except Exception as e:
            self.log(f'Error solving order #{order_id}: {e}', 'error')
            return False
    
    def run_once(self):
        """Run one iteration of checking and solving assigned orders"""
        if not self.core_contract:
            self.log('Core contract not initialized', 'error')
            return
        
        try:
            # Get assigned orders from recent events
            order_ids = self.get_assigned_orders_from_events()
            
            for order_id in order_ids:
                if not self.running:
                    break
                
                # Check if order needs solving
                order_info = self.check_order_needs_solving(order_id)
                if not order_info:
                    continue
                
                # Mark as processing
                self.processed_orders.add(order_id)
                self.bot_state.active_orders.add(order_id)
                
                try:
                    # Solve and submit
                    success = self.solve_and_submit(order_id, order_info['order'])
                    if success:
                        self.log(f'Successfully solved order #{order_id}', 'success')
                finally:
                    self.bot_state.active_orders.discard(order_id)
                    
        except Exception as e:
            self.log(f'Error in auto-solver run: {e}', 'error')
    
    def run_loop(self):
        """Main loop for auto-solver"""
        self.log('Starting auto-solver loop...', 'info')
        self.log(f'Bot address: {self.bot_address}', 'info')
        self.running = True
        
        while self.running and not self.bot_state.stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                self.log(f'Error in auto-solver loop: {e}', 'error')
            
            # Wait before next iteration
            self.bot_state.stop_event.wait(self.bot_state.config['poll_interval'])
        
        self.log('Auto-solver stopped.', 'warning')
        self.running = False


# Global auto-solver instance
auto_solver: Optional[AutoSolver] = None


def start_auto_solver():
    """Start the auto-solver in a separate thread"""
    global auto_solver
    
    if not bot_state.sdk:
        logger.error("Cannot start auto-solver: SDK not initialized")
        return False
    
    if auto_solver and auto_solver.running:
        logger.warning("Auto-solver is already running")
        return False
    
    auto_solver = AutoSolver(bot_state.sdk, bot_state)
    
    # Run in a separate thread
    solver_thread = threading.Thread(target=auto_solver.run_loop, daemon=True)
    solver_thread.start()
    
    logger.info("Auto-solver started")
    return True


# ========== API Endpoints ==========

@app.route('/status', methods=['GET'])
def get_status():
    """Get bot status"""
    return jsonify({
        'running': bot_state.running,
        'address': bot_state.sdk.address if bot_state.sdk else None,
        'stats': bot_state.stats,
        'active_orders': list(bot_state.active_orders),
        'auto_solver_running': auto_solver.running if auto_solver else False,
        'auto_solver_processed': len(auto_solver.processed_orders) if auto_solver else 0,
    })

@app.route('/start', methods=['POST'])
def start_bot():
    """Start the bot (both regular bot loop and auto-solver)"""
    if bot_state.running:
        return jsonify({'success': False, 'error': 'Bot is already running'})
    
    bot_state.running = True
    bot_state.stop_event.clear()
    
    # Start regular bot loop
    bot_state.bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_state.bot_thread.start()
    
    # Start auto-solver after a short delay (SDK needs to initialize first)
    def delayed_auto_solver_start():
        import time
        time.sleep(3)  # Wait for SDK initialization
        if bot_state.sdk:
            start_auto_solver()
    
    auto_solver_thread = threading.Thread(target=delayed_auto_solver_start, daemon=True)
    auto_solver_thread.start()
    
    return jsonify({'success': True, 'message': 'Bot started (with auto-solver)'})

@app.route('/stop', methods=['POST'])
def stop_bot():
    """Stop the bot (both regular bot loop and auto-solver)"""
    if not bot_state.running:
        return jsonify({'success': False, 'error': 'Bot is not running'})
    
    bot_state.stop_event.set()
    bot_state.running = False
    
    # Stop auto-solver
    global auto_solver
    if auto_solver:
        auto_solver.running = False
    
    return jsonify({'success': True, 'message': 'Bot stopping...'})

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent logs"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({
        'logs': bot_state.logs[-limit:]
    })

@app.route('/config', methods=['GET'])
def get_config():
    """Get bot configuration"""
    return jsonify(bot_state.config)

@app.route('/config', methods=['POST'])
def update_config():
    """Update bot configuration"""
    data = request.get_json()
    if data:
        for key in ['auto_accept', 'auto_solve', 'max_concurrent', 'poll_interval', 'accepted_types']:
            if key in data:
                bot_state.config[key] = data[key]
    
    return jsonify({'success': True, 'config': bot_state.config})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/test-gpt', methods=['POST'])
def test_gpt():
    """Test GPT connection with a sample problem"""
    data = request.get_json() or {}
    problem_type = data.get('problem_type', 0)
    problem_text = data.get('problem_text', 'Find the derivative of f(x) = x^3 + 2x^2 - 5x + 1')
    
    if not os.getenv('OPENAI_API_KEY'):
        return jsonify({
            'success': False,
            'error': 'OPENAI_API_KEY not configured'
        })
    
    try:
        result = solve_with_gpt(problem_type, problem_text)
        return jsonify({
            'success': True,
            'problem': problem_text,
            'solution': result['answer'],
            'steps': result['steps']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/gpt-status', methods=['GET'])
def gpt_status():
    """Check if GPT is configured"""
    has_key = bool(os.getenv('OPENAI_API_KEY'))
    return jsonify({
        'configured': has_key,
        'model': 'gpt-4o-mini' if has_key else None
    })


# ========== Auto-Solver API Endpoints ==========

@app.route('/assigned-orders', methods=['GET'])
def get_assigned_orders():
    """
    Get orders assigned to this bot (subscription mode).
    
    Query params:
        - from_block: Start block number (default: recent 1000 blocks)
        - include_processed: Include already processed orders (default: false)
    """
    if not auto_solver:
        return jsonify({
            'success': False,
            'error': 'Auto-solver not initialized. Start the bot first.'
        })
    
    from_block = request.args.get('from_block', type=int)
    include_processed = request.args.get('include_processed', 'false').lower() == 'true'
    
    try:
        # Get assigned orders from events
        order_ids = auto_solver.get_assigned_orders_from_events(from_block)
        
        # Filter out processed orders if requested
        if not include_processed:
            order_ids = [oid for oid in order_ids if oid not in auto_solver.processed_orders]
        
        # Get order details for each
        orders_info = []
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for order_id in order_ids:
            try:
                order = loop.run_until_complete(auto_solver.sdk.get_order(order_id))
                orders_info.append({
                    'order_id': order_id,
                    'problem_type': order.problem_type.name,
                    'status': order.status.name,
                    'time_remaining': order.time_remaining,
                    'processed': order_id in auto_solver.processed_orders
                })
            except Exception as e:
                orders_info.append({
                    'order_id': order_id,
                    'error': str(e)
                })
        
        loop.close()
        
        return jsonify({
            'success': True,
            'bot_address': auto_solver.bot_address,
            'total_assigned': len(order_ids),
            'total_processed': len(auto_solver.processed_orders),
            'orders': orders_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/solve-assigned', methods=['POST'])
def solve_assigned_order():
    """
    Manually trigger solving for an assigned order.
    
    Request body:
        - order_id: int (required)
    """
    if not auto_solver:
        return jsonify({
            'success': False,
            'error': 'Auto-solver not initialized. Start the bot first.'
        })
    
    data = request.get_json() or {}
    order_id = data.get('order_id')
    
    if order_id is None:
        return jsonify({
            'success': False,
            'error': 'order_id is required'
        })
    
    try:
        # Check if order is assigned to us
        order_info = auto_solver.check_order_needs_solving(order_id)
        
        if not order_info:
            return jsonify({
                'success': False,
                'error': f'Order #{order_id} is not assigned to this bot or already processed'
            })
        
        # Solve and submit
        success = auto_solver.solve_and_submit(order_id, order_info['order'])
        
        return jsonify({
            'success': success,
            'order_id': order_id,
            'message': 'Solution submitted successfully!' if success else 'Failed to submit solution'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/auto-solver/status', methods=['GET'])
def get_auto_solver_status():
    """Get detailed auto-solver status"""
    if not auto_solver:
        return jsonify({
            'success': True,
            'initialized': False,
            'running': False
        })
    
    return jsonify({
        'success': True,
        'initialized': True,
        'running': auto_solver.running,
        'bot_address': auto_solver.bot_address,
        'processed_count': len(auto_solver.processed_orders),
        'processed_orders': list(auto_solver.processed_orders),
        'core_contract_set': auto_solver.core_contract is not None
    })


@app.route('/auto-solver/run-once', methods=['POST'])
def run_auto_solver_once():
    """Manually trigger one iteration of the auto-solver"""
    if not auto_solver:
        return jsonify({
            'success': False,
            'error': 'Auto-solver not initialized. Start the bot first.'
        })
    
    try:
        auto_solver.run_once()
        return jsonify({
            'success': True,
            'message': 'Auto-solver iteration completed',
            'processed_count': len(auto_solver.processed_orders)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/solve', methods=['POST'])
def solve_endpoint():
    """
    Solve a problem using GPT with step-by-step explanation.
    Called by frontend's Auto Solve button.
    
    Request body:
        - problem_type: int (0=derivative, 1=integral, etc.)
        - problem_text: str (optional, the actual problem text)
        - problem_hash: str (optional, to look up stored problem)
        - order_id: int (optional, to store solution for later retrieval)
    
    Returns:
        - success: bool
        - solution: str (final answer)
        - steps: list of step objects
    """
    data = request.get_json() or {}
    problem_type = data.get('problem_type', 0)
    problem_text = data.get('problem_text')
    problem_hash = data.get('problem_hash', '')
    order_id = data.get('order_id')
    
    # Normalize hash for lookup
    if problem_hash:
        raw_hash = problem_hash.lower()
        problem_hash_normalized = '0x' + raw_hash.replace('0x', '')
    else:
        problem_hash_normalized = ''
    
    # If no problem text provided, try to get from storage
    if not problem_text and problem_hash_normalized:
        if problem_hash_normalized in problem_storage:
            problem_text = problem_storage[problem_hash_normalized].get('text')
    
    logger.info(f"Solving problem type {problem_type}: {problem_text[:50] if problem_text else 'No text'}...")
    
    try:
        result = solve_problem(problem_type, problem_hash_normalized, problem_text)
        logger.info(f"Solution: {result['answer']} ({len(result['steps'])} steps)")
        
        # Store solution if order_id provided
        if order_id is not None:
            store_solution_data(order_id, problem_hash_normalized, result)
        
        return jsonify({
            'success': True,
            'solution': result['answer'],
            'steps': result['steps'],
            'used_gpt': bool(os.getenv('OPENAI_API_KEY'))
        })
    except Exception as e:
        logger.error(f"Solve error: {e}")
        fallback = solve_problem_fallback(problem_type)
        return jsonify({
            'success': False,
            'error': str(e),
            'solution': fallback['answer'],
            'steps': fallback['steps']
        })

# ========== Problem Storage ==========
# File-based storage for problem texts (persists across restarts)

PROBLEM_STORAGE_FILE = os.path.join(os.path.dirname(__file__), 'problem_storage.json')

def load_problem_storage():
    """Load problem storage from file"""
    if os.path.exists(PROBLEM_STORAGE_FILE):
        try:
            with open(PROBLEM_STORAGE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load problem storage: {e}")
    return {}

def save_problem_storage():
    """Save problem storage to file"""
    try:
        with open(PROBLEM_STORAGE_FILE, 'w') as f:
            json.dump(problem_storage, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save problem storage: {e}")

problem_storage = load_problem_storage()  # {problem_hash: {text, type, timestamp}}
logger.info(f"Loaded {len(problem_storage)} problems from storage")


# ========== Solution Storage ==========
# File-based storage for solutions with steps (persists across restarts)

SOLUTION_STORAGE_FILE = os.path.join(os.path.dirname(__file__), 'solution_storage.json')

def load_solution_storage():
    """Load solution storage from file"""
    if os.path.exists(SOLUTION_STORAGE_FILE):
        try:
            with open(SOLUTION_STORAGE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load solution storage: {e}")
    return {}

def save_solution_storage():
    """Save solution storage to file"""
    try:
        with open(SOLUTION_STORAGE_FILE, 'w') as f:
            json.dump(solution_storage, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save solution storage: {e}")

def store_solution_data(order_id: int, problem_hash: str, solution_data: dict):
    """Store solution with steps for an order"""
    # Create a hash of the steps for verification
    steps_str = json.dumps(solution_data.get('steps', []), sort_keys=True)
    steps_hash = '0x' + hashlib.sha256(steps_str.encode()).hexdigest()
    
    solution_storage[str(order_id)] = {
        'order_id': order_id,
        'problem_hash': problem_hash,
        'answer': solution_data.get('answer', ''),
        'steps': solution_data.get('steps', []),
        'steps_hash': steps_hash,
        'timestamp': datetime.now().isoformat(),
        'verified': False,
        'verification_status': 'pending'
    }
    save_solution_storage()
    logger.info(f"Stored solution for order #{order_id}: {solution_data.get('answer', '')[:30]}...")

solution_storage = load_solution_storage()  # {order_id: {answer, steps, ...}}
logger.info(f"Loaded {len(solution_storage)} solutions from storage")

@app.route('/problems', methods=['POST'])
def store_problem():
    """Store a problem text (called by frontend when submitting)"""
    data = request.get_json()
    if not data or 'hash' not in data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Missing hash or text'})
    
    # Normalize hash: ensure 0x prefix and lowercase
    raw_hash = data['hash'].lower()
    problem_hash = '0x' + raw_hash.replace('0x', '') if not raw_hash.startswith('0x') else raw_hash
    problem_storage[problem_hash] = {
        'text': data['text'],
        'type': data.get('type', 0),
        'timestamp': datetime.now().isoformat()
    }
    save_problem_storage()  # Persist to file
    
    logger.info(f"Stored problem: {problem_hash[:18]}... = {data['text'][:50]}...")
    return jsonify({'success': True, 'hash': problem_hash})

@app.route('/problems/<problem_hash>', methods=['GET'])
def get_problem(problem_hash):
    """Get a problem text by hash"""
    # Normalize hash: ensure 0x prefix and lowercase
    raw_hash = problem_hash.lower()
    problem_hash = '0x' + raw_hash.replace('0x', '') if not raw_hash.startswith('0x') else raw_hash
    if problem_hash in problem_storage:
        return jsonify({
            'success': True,
            'problem': problem_storage[problem_hash]
        })
    return jsonify({'success': False, 'error': 'Problem not found'})

@app.route('/problems', methods=['GET'])
def list_problems():
    """List all stored problems"""
    return jsonify({
        'count': len(problem_storage),
        'problems': {k[:16]: v['text'][:50] for k, v in problem_storage.items()}
    })


# ========== Solution Storage Endpoints ==========

@app.route('/solutions/<int:order_id>/steps', methods=['POST'])
def store_solution_steps(order_id):
    """Store solution steps for an order"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'})
    
    answer = data.get('answer', '')
    steps = data.get('steps', [])
    problem_hash = data.get('problem_hash', '')
    
    if not answer:
        return jsonify({'success': False, 'error': 'Missing answer'})
    
    store_solution_data(order_id, problem_hash, {'answer': answer, 'steps': steps})
    
    return jsonify({
        'success': True,
        'order_id': order_id,
        'steps_count': len(steps)
    })


@app.route('/solutions/<int:order_id>/steps', methods=['GET'])
def get_solution_steps(order_id):
    """Get solution steps for an order"""
    order_key = str(order_id)
    if order_key not in solution_storage:
        return jsonify({'success': False, 'error': 'Solution not found'})
    
    solution = solution_storage[order_key]
    return jsonify({
        'success': True,
        'order_id': order_id,
        'answer': solution.get('answer', ''),
        'steps': solution.get('steps', []),
        'steps_hash': solution.get('steps_hash', ''),
        'timestamp': solution.get('timestamp', ''),
        'verified': solution.get('verified', False),
        'verification_status': solution.get('verification_status', 'pending')
    })


@app.route('/solutions/<int:order_id>', methods=['GET'])
def get_solution(order_id):
    """Get full solution data for an order"""
    order_key = str(order_id)
    if order_key not in solution_storage:
        return jsonify({'success': False, 'error': 'Solution not found'})
    
    return jsonify({
        'success': True,
        'solution': solution_storage[order_key]
    })


@app.route('/solutions', methods=['GET'])
def list_solutions():
    """List all stored solutions"""
    return jsonify({
        'count': len(solution_storage),
        'solutions': {
            k: {
                'answer': v.get('answer', '')[:50],
                'steps_count': len(v.get('steps', [])),
                'verified': v.get('verified', False)
            }
            for k, v in solution_storage.items()
        }
    })


@app.route('/solutions/<int:order_id>/verify', methods=['POST'])
def update_verification_status(order_id):
    """Update verification status for a solution (called by Oracle)"""
    order_key = str(order_id)
    if order_key not in solution_storage:
        return jsonify({'success': False, 'error': 'Solution not found'})
    
    data = request.get_json() or {}
    is_verified = data.get('verified', False)
    status = data.get('status', 'verified' if is_verified else 'failed')
    reason = data.get('reason', '')
    
    solution_storage[order_key]['verified'] = is_verified
    solution_storage[order_key]['verification_status'] = status
    solution_storage[order_key]['verification_reason'] = reason
    solution_storage[order_key]['verification_time'] = datetime.now().isoformat()
    save_solution_storage()
    
    logger.info(f"Order #{order_id} verification: {status} - {reason}")
    
    return jsonify({
        'success': True,
        'order_id': order_id,
        'verified': is_verified,
        'status': status
    })


# ========== Webhook Endpoints (Platform Push Mode) ==========

# Solution status tracking for webhook submissions
webhook_solution_status = {}  # {order_id: {status, solution, tx_hash, ...}}

def init_sdk_if_needed():
    """Initialize SDK if not already running"""
    if bot_state.sdk:
        return bot_state.sdk
    
    private_key = os.getenv('PRIVATE_KEY')
    rpc_url = os.getenv('RPC_URL')
    core_address = os.getenv('CORE_ADDRESS')
    
    if not all([private_key, rpc_url, core_address]):
        logger.error("[WEBHOOK] Missing environment variables for SDK")
        return None
    
    try:
        sdk = OminisSDK(
            private_key=private_key,
            rpc_url=rpc_url,
            core_address=core_address
        )
        orderbook_address = os.getenv('ORDERBOOK_ADDRESS')
        if orderbook_address:
            sdk.set_orderbook_address(orderbook_address)
        
        bot_state.sdk = sdk
        logger.info(f"[WEBHOOK] SDK initialized, address: {sdk.address}")
        return sdk
    except Exception as e:
        logger.error(f"[WEBHOOK] Failed to init SDK: {e}")
        return None


@app.route('/webhook/problem', methods=['POST'])
def receive_problem_webhook():
    """
    Receive problem push from platform (Webhook mode).
    Platform calls this when a user selects this bot.
    
    Immediately solves the problem and submits to chain (commit + reveal).
    
    Request body:
        - order_id: int (required)
        - problem_hash: str
        - problem_text: str (required)
        - problem_type: int
        - submit_to_chain: bool (default: true)
    
    Returns:
        - success: bool
        - solution: str
        - steps: list
        - commit_tx: str (if submitted)
        - reveal_tx: str (if submitted)
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'})
    
    order_id = data.get('order_id')
    problem_hash = data.get('problem_hash', '')
    problem_text = data.get('problem_text', '')
    problem_type = data.get('problem_type', 0)
    submit_to_chain = data.get('submit_to_chain', True)
    
    logger.info(f"[WEBHOOK] Received problem #{order_id} (type={problem_type}, submit={submit_to_chain})")
    
    if not problem_text:
        return jsonify({
            'success': False,
            'error': 'Problem text required'
        })
    
    if order_id is None:
        return jsonify({
            'success': False,
            'error': 'order_id required'
        })
    
    # Update status
    webhook_solution_status[order_id] = {
        'status': 'solving',
        'started_at': datetime.now().isoformat()
    }
    
    # Store problem for solving
    normalized_hash = '0x' + problem_hash.lower().replace('0x', '')
    problem_storage[normalized_hash] = {
        'text': problem_text,
        'type': problem_type,
        'timestamp': datetime.now().isoformat()
    }
    save_problem_storage()
    
    # Solve the problem immediately
    try:
        solution_data = solve_problem(problem_type, normalized_hash, problem_text)
        solution = solution_data['answer']
        steps = solution_data.get('steps', [])
        
        # Store solution
        store_solution_data(order_id, normalized_hash, solution_data)
        
        logger.info(f"[WEBHOOK] Solved #{order_id}: {solution}")
        
        webhook_solution_status[order_id]['status'] = 'solved'
        webhook_solution_status[order_id]['solution'] = solution
        
        result = {
            'success': True,
            'order_id': order_id,
            'solution': solution,
            'steps': steps,
            'solved_at': datetime.now().isoformat()
        }
        
        # Submit to chain if requested
        if submit_to_chain:
            sdk = init_sdk_if_needed()
            if not sdk:
                result['chain_error'] = 'SDK not available'
                webhook_solution_status[order_id]['status'] = 'solved_not_submitted'
                return jsonify(result)
            
            try:
                # Generate salt for commit-reveal
                salt = os.urandom(32)
                
                # Commit solution
                webhook_solution_status[order_id]['status'] = 'committing'
                logger.info(f"[WEBHOOK] Committing solution for #{order_id}...")
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                commit_receipt = loop.run_until_complete(
                    sdk.commit_solution(order_id, solution, salt)
                )
                result['commit_tx'] = commit_receipt.tx_hash
                logger.info(f"[WEBHOOK] Commit TX: {commit_receipt.tx_hash}")
                
                if not commit_receipt.success:
                    # Wait and check if commit actually succeeded
                    for retry in range(3):
                        loop.run_until_complete(asyncio.sleep(3))
                        check_order = loop.run_until_complete(sdk.get_order(order_id))
                        if check_order.status.name == 'COMMITTED':
                            logger.info(f"[WEBHOOK] Commit confirmed after retry")
                            break
                    else:
                        result['chain_error'] = 'Commit may have failed'
                        webhook_solution_status[order_id]['status'] = 'commit_failed'
                        loop.close()
                        return jsonify(result)
                
                # Wait for commit to propagate
                loop.run_until_complete(asyncio.sleep(2))
                
                # Reveal solution
                webhook_solution_status[order_id]['status'] = 'revealing'
                logger.info(f"[WEBHOOK] Revealing solution for #{order_id}...")
                
                reveal_receipt = loop.run_until_complete(
                    sdk.reveal_solution(order_id, solution, salt)
                )
                result['reveal_tx'] = reveal_receipt.tx_hash
                logger.info(f"[WEBHOOK] Reveal TX: {reveal_receipt.tx_hash}")
                
                loop.close()
                
                if reveal_receipt.success:
                    webhook_solution_status[order_id]['status'] = 'completed'
                    webhook_solution_status[order_id]['reveal_tx'] = reveal_receipt.tx_hash
                    logger.info(f"[WEBHOOK] Order #{order_id} COMPLETED!")
                    bot_state.stats['orders_solved'] += 1
                else:
                    webhook_solution_status[order_id]['status'] = 'reveal_failed'
                    result['chain_error'] = 'Reveal may have failed'
                    
            except Exception as chain_err:
                logger.error(f"[WEBHOOK] Chain submission error: {chain_err}")
                result['chain_error'] = str(chain_err)
                webhook_solution_status[order_id]['status'] = 'chain_error'
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"[WEBHOOK] Error solving #{order_id}: {e}")
        webhook_solution_status[order_id]['status'] = 'error'
        webhook_solution_status[order_id]['error'] = str(e)
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/webhook/status', methods=['GET'])
def webhook_status():
    """Check if this bot accepts webhook pushes"""
    return jsonify({
        'webhook_enabled': True,
        'bot_name': os.getenv('BOT_NAME', 'Ominis Platform Bot'),
        'supported_types': [0, 1, 2, 3, 4],  # All problem types
        'is_premium': False,
        'status': 'online' if bot_state.running else 'standby'
    })


@app.route('/webhook/solution-status/<int:order_id>', methods=['GET'])
def get_webhook_solution_status(order_id):
    """
    Get the status of a webhook-triggered solution.
    
    Status values:
        - pending: Not started
        - solving: GPT is working on the problem
        - solved: Solution found, not yet submitted
        - committing: Submitting commit transaction
        - revealing: Submitting reveal transaction
        - completed: Successfully submitted to chain
        - commit_failed: Commit transaction failed
        - reveal_failed: Reveal transaction failed
        - chain_error: Error during chain submission
        - error: General error
    """
    if order_id not in webhook_solution_status:
        # Check if solution exists in storage (may have been solved by polling bot)
        order_key = str(order_id)
        if order_key in solution_storage:
            return jsonify({
                'success': True,
                'order_id': order_id,
                'status': 'completed',
                'solution': solution_storage[order_key].get('answer', ''),
                'source': 'storage'
            })
        return jsonify({
            'success': False,
            'order_id': order_id,
            'status': 'not_found',
            'error': 'No webhook submission found for this order'
        })
    
    status_info = webhook_solution_status[order_id]
    return jsonify({
        'success': True,
        'order_id': order_id,
        'status': status_info.get('status', 'unknown'),
        'solution': status_info.get('solution'),
        'reveal_tx': status_info.get('reveal_tx'),
        'error': status_info.get('error'),
        'started_at': status_info.get('started_at')
    })


# ========== Bot Registration Endpoints ==========

BOT_REGISTRATION_FILE = os.path.join(os.path.dirname(__file__), 'bot_registration.json')

def load_bot_registration():
    """Load bot registration data"""
    if os.path.exists(BOT_REGISTRATION_FILE):
        try:
            with open(BOT_REGISTRATION_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load bot registration: {e}")
    return {}

def save_bot_registration(data):
    """Save bot registration data"""
    try:
        with open(BOT_REGISTRATION_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save bot registration: {e}")

bot_registration = load_bot_registration()


@app.route('/bot/register', methods=['POST'])
def register_bot():
    """
    Register this bot with the platform.
    
    Request body:
        - name: str
        - description: str
        - webhook_url: str (optional)
        - is_premium: bool
        - supported_types: list[int]
    """
    data = request.get_json() or {}
    
    name = data.get('name', 'Ominis Bot')
    description = data.get('description', 'AI-powered calculus solver')
    webhook_url = data.get('webhook_url', '')
    is_premium = data.get('is_premium', False)
    supported_types = data.get('supported_types', [0, 1, 2, 3, 4])
    
    # Get bot address from SDK
    private_key = os.getenv('PRIVATE_KEY')
    if private_key:
        from eth_account import Account
        account = Account.from_key(private_key)
        bot_address = account.address
    else:
        bot_address = '0x0000000000000000000000000000000000000000'
    
    registration_data = {
        'name': name,
        'description': description,
        'webhook_url': webhook_url,
        'is_premium': is_premium,
        'supported_types': supported_types,
        'bot_address': bot_address,
        'registered_at': datetime.now().isoformat(),
        'is_active': True
    }
    
    bot_registration.update(registration_data)
    save_bot_registration(bot_registration)
    
    logger.info(f"Bot registered: {name} ({bot_address})")
    
    return jsonify({
        'success': True,
        'registration': registration_data
    })


@app.route('/bot/profile', methods=['GET'])
def get_bot_profile():
    """Get this bot's registration profile"""
    if not bot_registration:
        return jsonify({
            'success': False,
            'error': 'Bot not registered'
        })
    
    return jsonify({
        'success': True,
        'profile': bot_registration
    })


@app.route('/bot/profile', methods=['PUT'])
def update_bot_profile():
    """Update bot profile"""
    data = request.get_json() or {}
    
    if 'name' in data:
        bot_registration['name'] = data['name']
    if 'description' in data:
        bot_registration['description'] = data['description']
    if 'webhook_url' in data:
        bot_registration['webhook_url'] = data['webhook_url']
    if 'is_premium' in data:
        bot_registration['is_premium'] = data['is_premium']
    if 'supported_types' in data:
        bot_registration['supported_types'] = data['supported_types']
    if 'is_active' in data:
        bot_registration['is_active'] = data['is_active']
    
    bot_registration['updated_at'] = datetime.now().isoformat()
    save_bot_registration(bot_registration)
    
    return jsonify({
        'success': True,
        'profile': bot_registration
    })


@app.route('/bot/stats', methods=['GET'])
def get_bot_stats():
    """Get bot statistics"""
    total_solved = len(solution_storage)
    verified_count = sum(1 for s in solution_storage.values() if s.get('verified', False))
    
    return jsonify({
        'success': True,
        'stats': {
            'total_solved': total_solved,
            'verified_count': verified_count,
            'success_rate': (verified_count / total_solved * 100) if total_solved > 0 else 0,
            'orders_accepted': bot_state.stats.get('orders_accepted', 0),
            'total_earned': bot_state.stats.get('total_earned', 0),
            'is_running': bot_state.running
        }
    })


# ========== Main ==========

if __name__ == '__main__':
    print("=" * 50)
    print("Ominis Bot API Server")
    print("=" * 50)
    print(f"RPC URL: {os.getenv('RPC_URL', 'Not set')}")
    print(f"Core Address: {os.getenv('CORE_ADDRESS', 'Not set')}")
    print(f"Bot Name: {bot_registration.get('name', 'Not registered')}")
    print("=" * 50)
    print("Starting server on http://localhost:5001")
    print("Webhook endpoint: /webhook/problem")
    print("=" * 50)
    
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
