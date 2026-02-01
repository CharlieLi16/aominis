# Ominis SDK

Python SDK for building solver bots on the Ominis Calculus Solver Protocol.

## Installation

```bash
cd ominis/sdk
pip install -r requirements.txt
```

## Quick Start

```python
from ominis_sdk import OminisSDK, Order

# Initialize SDK
sdk = OminisSDK(
    private_key="0x...",
    rpc_url="https://arb-sepolia.g.alchemy.com/v2/YOUR_KEY",
    core_address="0x..."
)
sdk.set_orderbook_address("0x...")

# Get open orders
orders = await sdk.get_open_orders()

# Accept an order
await sdk.accept_order(order_id=1)

# Submit solution (handles commit-reveal automatically)
await sdk.submit_solution(order_id=1, solution="f'(x) = 2x")
```

## Running the Example Bot

```bash
# Set environment variables
export PRIVATE_KEY="your_private_key"
export RPC_URL="https://arb-sepolia.g.alchemy.com/v2/YOUR_KEY"
export CORE_ADDRESS="0x..."
export ORDERBOOK_ADDRESS="0x..."

# Run the bot
python examples/solver_bot.py
```

## SDK Features

### Order Management

```python
# Get all open orders
orders = await sdk.get_open_orders(limit=100)

# Get specific order
order = await sdk.get_order(order_id=1)

# Check order properties
print(order.is_open)           # True/False
print(order.time_remaining)    # Seconds until deadline
print(order.reward_in_usdc())  # Reward in USDC
```

### Solution Submission

The protocol uses a commit-reveal pattern to prevent frontrunning:

```python
import os

# Manual commit-reveal
salt = os.urandom(32)
await sdk.commit_solution(order_id, solution, salt)
await sdk.reveal_solution(order_id, solution, salt)

# Or use the convenience method
await sdk.submit_solution(order_id, solution)
```

### Event Listening

```python
# Listen for new orders (polling-based)
async for order in sdk.listen_new_orders(poll_interval=2.0):
    print(f"New order: {order.id}")
    if sdk.estimate_profit(order) > 0.05:
        await sdk.accept_order(order.id)
```

### Profit Estimation

```python
profit = sdk.estimate_profit(order)
print(f"Estimated profit: ${profit:.4f} USDC")
```

## Problem Types

| Type | Description |
|------|-------------|
| `DERIVATIVE` | Find derivatives |
| `INTEGRAL` | Compute integrals |
| `LIMIT` | Evaluate limits |
| `DIFFERENTIAL_EQ` | Solve differential equations |
| `SERIES` | Series and sequences |

## Time Tiers

| Tier | Deadline | Typical Reward |
|------|----------|----------------|
| `T2min` | 2 minutes | $1.50+ |
| `T5min` | 5 minutes | $1.00+ |
| `T15min` | 15 minutes | $0.75+ |
| `T1hour` | 1 hour | $0.50+ |

## Building Your Solver

The example bot includes a `MathSolver` placeholder. Implement your own using:

### Option 1: OpenAI GPT-4

```python
import openai

async def solve_with_openai(problem_text: str) -> str:
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a calculus expert. Provide exact solutions."},
            {"role": "user", "content": problem_text}
        ]
    )
    return response.choices[0].message.content
```

### Option 2: SymPy (Local)

```python
from sympy import symbols, diff, integrate, sympify

def solve_derivative(expression: str) -> str:
    x = symbols('x')
    expr = sympify(expression)
    result = diff(expr, x)
    return str(result)
```

### Option 3: Wolfram Alpha

```python
import wolframalpha

def solve_with_wolfram(query: str) -> str:
    client = wolframalpha.Client("YOUR_APP_ID")
    res = client.query(query)
    return next(res.results).text
```

## Network Configuration

Default configuration is for Arbitrum Sepolia testnet. For mainnet:

```python
sdk = OminisSDK(
    private_key="0x...",
    rpc_url="https://arb1.arbitrum.io/rpc",  # Arbitrum One mainnet
    core_address="0x..."  # Mainnet contract address
)
```

## Security Notes

- **Never commit your private key** - use environment variables
- **Test on testnet first** - use Arbitrum Sepolia before mainnet
- **Monitor gas costs** - adjust `MIN_PROFIT_USDC` based on gas prices
- **Handle errors gracefully** - network issues can cause transaction failures

## License

MIT
