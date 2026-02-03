#!/usr/bin/env python3
"""
Test script for the Math Solver

Run this to verify SymPy integration works before running the full bot.

Usage:
    python test_solver.py
"""

import asyncio
import sys
import os

# Add sdk directory to path
SDK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sdk')
sys.path.insert(0, SDK_DIR)

from ominis_sdk import ProblemType

# Import the solver from examples
sys.path.insert(0, os.path.join(SDK_DIR, 'examples'))

async def test_solver():
    """Test the math solver with various problem types"""
    
    # Import here to avoid import errors if dependencies missing
    try:
        from examples.solver_bot import MathSolver, SYMPY_AVAILABLE, OPENAI_AVAILABLE
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure to install dependencies: pip install -r requirements.txt")
        return False
    
    print("=" * 60)
    print("Ominis Math Solver Test")
    print("=" * 60)
    print(f"SymPy available: {SYMPY_AVAILABLE}")
    print(f"OpenAI available: {OPENAI_AVAILABLE}")
    print("=" * 60)
    
    if not SYMPY_AVAILABLE:
        print("\nWARNING: SymPy not installed. Install with: pip install sympy")
        return False
    
    solver = MathSolver()
    
    # Test cases
    test_cases = [
        (ProblemType.DERIVATIVE, "x**3 + 2*x**2 - 5*x + 1"),
        (ProblemType.DERIVATIVE, "sin(x) * cos(x)"),
        (ProblemType.DERIVATIVE, "exp(x) * x**2"),
        (ProblemType.INTEGRAL, "x**2"),
        (ProblemType.INTEGRAL, "sin(x)"),
        (ProblemType.INTEGRAL, "1/(1 + x**2)"),
        (ProblemType.LIMIT, "sin(x)/x"),
        (ProblemType.LIMIT, "(exp(x) - 1)/x"),
        (ProblemType.SERIES, "exp(x)"),
        (ProblemType.SERIES, "sin(x)"),
    ]
    
    passed = 0
    failed = 0
    
    for problem_type, expression in test_cases:
        print(f"\n[{problem_type.name}] {expression}")
        print("-" * 40)
        
        try:
            # Create a dummy hash for testing
            problem_hash = bytes(32)
            
            # Solve using SymPy directly
            result = await solver.solve_with_sympy(expression, problem_type)
            
            if result:
                print(f"  Result: {result}")
                passed += 1
            else:
                print(f"  FAILED: No result")
                failed += 1
                
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(test_solver())
    sys.exit(0 if success else 1)
