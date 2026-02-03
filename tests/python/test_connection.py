"""Quick test to debug contract connection issues"""
import os
import sys
from dotenv import load_dotenv
from web3 import Web3

# Load .env from sdk directory
SDK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sdk')
load_dotenv(os.path.join(SDK_DIR, '.env'))

# Config
rpc_url = os.getenv("RPC_URL")
core_address = os.getenv("CORE_ADDRESS")
orderbook_address = os.getenv("ORDERBOOK_ADDRESS")

print(f"RPC URL: {rpc_url}")
print(f"Core Address: {core_address}")
print(f"OrderBook Address: {orderbook_address}")

# Connect
w3 = Web3(Web3.HTTPProvider(rpc_url))
print(f"\nConnected: {w3.is_connected()}")
print(f"Chain ID: {w3.eth.chain_id}")
print(f"Block Number: {w3.eth.block_number}")

# Test OrderBook
ORDERBOOK_ABI = [
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
        "inputs": [],
        "name": "core",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
]

print(f"\n--- Testing OrderBook at {orderbook_address} ---")
try:
    orderbook = w3.eth.contract(
        address=Web3.to_checksum_address(orderbook_address),
        abi=ORDERBOOK_ABI
    )
    
    # Check if contract exists
    code = w3.eth.get_code(Web3.to_checksum_address(orderbook_address))
    print(f"Contract has code: {len(code) > 0} (bytecode length: {len(code)})")
    
    # Test calls
    print(f"OrderBook.core(): {orderbook.functions.core().call()}")
    print(f"OrderBook.orderCount(): {orderbook.functions.orderCount().call()}")
    print(f"OrderBook.openOrderCount(): {orderbook.functions.openOrderCount().call()}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test Core
CORE_ABI = [
    {
        "inputs": [],
        "name": "orderBook",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
]

print(f"\n--- Testing Core at {core_address} ---")
try:
    core = w3.eth.contract(
        address=Web3.to_checksum_address(core_address),
        abi=CORE_ABI
    )
    
    code = w3.eth.get_code(Web3.to_checksum_address(core_address))
    print(f"Contract has code: {len(code) > 0} (bytecode length: {len(code)})")
    
    print(f"Core.orderBook(): {core.functions.orderBook().call()}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
