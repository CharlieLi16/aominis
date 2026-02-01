# Calculus Instant Solver Protocol

A decentralized marketplace where students post calculus problems with time-based pricing, and solvers compete to deliver verified correct answers within the deadline.

## Core Concept

**Time = SKU**: Faster delivery costs more.

| Tier | Deadline | Price |
|------|----------|-------|
| T2min | 2 minutes | ~$3.99 |
| T5min | 5 minutes | ~$1.99 |
| T10min | 10 minutes | ~$0.99 |

## Why Not Just Use GPT?

GPT gives you "a possible answer". This protocol gives you:
- **Verified correctness**: Mathematical verification, not guesswork
- **SLA guarantee**: Deadline or refund
- **Accountability**: Wrong answers get slashed

> "GPT gives you ideas. We give you answers you can submit."

## Architecture

```
CalcSolverCore.sol          <- Main coordinator
├── interfaces/
│   └── ICalcSolver.sol     <- Structs & interfaces  
├── modules/
│   ├── OrderBook.sol       <- Problem order management
│   ├── SolutionManager.sol <- Commit-reveal submission
│   ├── Verifier.sol        <- Mathematical verification
│   └── Escrow.sol          <- Fund locking & settlement
```

## Flow

1. **Issuer posts problem** → Locks reward
2. **Solver accepts order** → Locks bond, clock starts
3. **Solver commits hash** → `hash(solution || salt)` (anti-MEV)
4. **Solver reveals solution** → Verification
5. **Settlement** → Reward to solver OR refund to issuer

## Cost Model

Target: **$0.01 per problem**

| Component | Cost |
|-----------|------|
| AI inference | $0.005 |
| CAS verification | $0.0005 |
| L2 gas (batch) | $0.001 |
| Retry buffer | $0.0005 |
| **Total** | **~$0.007** |

## Supported Problem Types (v1)

- **Indefinite Integral**: ∫f(x)dx → F(x), verified by d/dx F(x) == f(x)
- **Definite Integral**: ∫[a,b]f(x)dx → value, numerical verification
- **Derivative**: f(x) → f'(x), symbolic verification
- **Limit**: lim(x→c) f(x) → value, numerical/symbolic verification

## Development

### Contracts

```bash
cd calcsolver/contracts
# TODO: Add compilation instructions
```

### Simulation

```bash
cd calcsolver/simulation
pip install -r ../requirements.txt
python calc_solver_simulation.py
```

## Status

**Skeleton implementation** - All files contain structure and comments for understanding. Fill in the `TODO` sections to complete.

## Key Design Decisions

1. **Commit-reveal**: Prevents MEV/frontrunning of solutions
2. **Optimistic verification**: Assume correct, allow challenge
3. **Bond/slash**: Economic security, not just trust
4. **Auto-verification**: No subjective human judgment
5. **AI-native**: 90% AI solvers, humans as fallback

## Related

- MOVI Protocol (same repo): Review validation with similar patterns
- Truebit: Verifiable computation market
- Polymarket: Prediction market (similar binary outcome structure)
