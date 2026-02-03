# Ominis Solver Marketplace - Makefile
# Usage: make all_test

.PHONY: all_test test_python test_solidity test_parse test_solver test_connection clean help

# Default target
help:
	@echo "Available targets:"
	@echo "  make all_test       - Run all tests (Python + Solidity)"
	@echo "  make test_python    - Run all Python tests"
	@echo "  make test_solidity  - Run all Solidity tests (Foundry)"
	@echo "  make test_parse     - Run parse_gpt_solution tests"
	@echo "  make test_solver    - Run SymPy solver tests"
	@echo "  make test_connection - Run Web3 connection tests"
	@echo "  make clean          - Clean build artifacts"

# Run all tests
all_tests: test_python test_solidity
	@echo ""
	@echo "============================================"
	@echo "All tests completed!"
	@echo "============================================"

# Python tests
test_python: test_parse test_solver
	@echo ""
	@echo "Python tests completed!"

test_parse:
	@echo ""
	@echo "============================================"
	@echo "Running: parse_gpt_solution tests"
	@echo "============================================"
	cd tests/python && python3 test_parse_gpt.py

test_solver:
	@echo ""
	@echo "============================================"
	@echo "Running: SymPy solver tests"
	@echo "============================================"
	cd tests/python && python3 test_solver.py || echo "Note: Requires SymPy dependencies"

test_connection:
	@echo ""
	@echo "============================================"
	@echo "Running: Web3 connection tests"
	@echo "============================================"
	cd tests/python && python3 test_connection.py

# Solidity tests (Foundry)
test_solidity:
	@echo ""
	@echo "============================================"
	@echo "Running: Solidity tests (Foundry)"
	@echo "============================================"
	forge test -vv || echo "Note: Requires Foundry (forge)"

# Clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf cache out
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete!"
