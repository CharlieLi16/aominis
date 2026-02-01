"""Check if contracts are on Sepolia Ethereum mainnet"""
from web3 import Web3

# Sepolia Ethereum mainnet RPC
sepolia_rpc = "https://rpc.sepolia.org"
core_address = "0x05465FEd0ba03A012c87Ac215c249EeA48aEcFd0"
orderbook_address = "0x9D662B02759C89748A0Cd1e40dab7925b267f0bb"

w3 = Web3(Web3.HTTPProvider(sepolia_rpc))

print(f"Checking Sepolia Ethereum mainnet...")
print(f"Connected: {w3.is_connected()}")
print(f"Chain ID: {w3.eth.chain_id}")

print(f"\nCore at {core_address}:")
code = w3.eth.get_code(Web3.to_checksum_address(core_address))
print(f"  Has code: {len(code) > 0} (bytecode length: {len(code)})")

print(f"\nOrderBook at {orderbook_address}:")
code = w3.eth.get_code(Web3.to_checksum_address(orderbook_address))
print(f"  Has code: {len(code) > 0} (bytecode length: {len(code)})")
