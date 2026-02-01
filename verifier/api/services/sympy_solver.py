"""
SymPy-based calculus solver and verifier
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum

try:
    from sympy import (
        symbols, sympify, diff, integrate, limit, 
        dsolve, series, simplify, Eq, Function,
        sin, cos, tan, exp, log, sqrt, pi, E, oo,
        parse_expr, SympifyError
    )
    from sympy.parsing.latex import parse_latex
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False


class ProblemType(IntEnum):
    DERIVATIVE = 0
    INTEGRAL = 1
    LIMIT = 2
    DIFFERENTIAL_EQ = 3
    SERIES = 4


@dataclass
class VerificationResult:
    is_correct: bool
    confidence: float
    expected_solution: Optional[str] = None
    reason: Optional[str] = None


class SympySolver:
    """
    Symbolic math solver using SymPy.
    
    Handles:
    - Derivatives
    - Integrals (definite and indefinite)
    - Limits
    - Simple differential equations
    - Series expansions
    """
    
    def __init__(self):
        if not SYMPY_AVAILABLE:
            raise ImportError("SymPy is not installed")
        
        # Common symbols
        self.x = symbols('x')
        self.y = symbols('y')
        self.t = symbols('t')
        self.n = symbols('n', integer=True)
        self.C = symbols('C')
        
    async def verify(
        self,
        problem: str,
        solution: str,
        problem_type: ProblemType
    ) -> VerificationResult:
        """
        Verify a solution against a problem.
        """
        
        try:
            # Parse the problem to extract the mathematical expression
            expr = self._parse_problem(problem)
            
            if expr is None:
                return VerificationResult(
                    is_correct=False,
                    confidence=0.0,
                    reason="Could not parse problem"
                )
            
            # Compute the expected solution
            expected = self._compute_solution(expr, problem_type, problem)
            
            if expected is None:
                return VerificationResult(
                    is_correct=False,
                    confidence=0.3,
                    reason="Could not compute expected solution"
                )
            
            # Parse the submitted solution
            submitted = self._parse_expression(solution)
            
            if submitted is None:
                return VerificationResult(
                    is_correct=False,
                    confidence=0.5,
                    expected_solution=str(expected),
                    reason="Could not parse submitted solution"
                )
            
            # Compare solutions
            is_correct = self._compare_expressions(submitted, expected, problem_type)
            
            return VerificationResult(
                is_correct=is_correct,
                confidence=0.95 if is_correct else 0.9,
                expected_solution=str(expected),
                reason="Solutions match" if is_correct else "Solutions differ"
            )
            
        except Exception as e:
            return VerificationResult(
                is_correct=False,
                confidence=0.1,
                reason=f"Verification error: {str(e)}"
            )
    
    def _parse_problem(self, problem: str) -> Optional[any]:
        """Extract mathematical expression from problem text."""
        
        # Try to find expressions in various formats
        patterns = [
            r'f\(x\)\s*=\s*(.+?)(?:\s|$|,)',  # f(x) = ...
            r'y\s*=\s*(.+?)(?:\s|$|,)',        # y = ...
            r'of\s+(.+?)(?:\s|$|as)',          # ... of ... (derivative of x^2)
            r'integrate\s+(.+?)(?:\s|$|dx)',   # integrate ...
            r'\$(.+?)\$',                       # LaTeX inline
        ]
        
        for pattern in patterns:
            match = re.search(pattern, problem, re.IGNORECASE)
            if match:
                expr_str = match.group(1).strip()
                expr = self._parse_expression(expr_str)
                if expr is not None:
                    return expr
        
        # Try parsing the whole thing as an expression
        # Remove common words
        cleaned = problem.lower()
        for word in ['find', 'the', 'derivative', 'integral', 'limit', 'of', 'as', 'x', 'approaches']:
            cleaned = cleaned.replace(word, ' ')
        cleaned = cleaned.strip()
        
        return self._parse_expression(cleaned)
    
    def _parse_expression(self, expr_str: str) -> Optional[any]:
        """Parse a string into a SymPy expression."""
        
        if not expr_str:
            return None
            
        # Clean up the expression
        expr_str = expr_str.strip()
        expr_str = expr_str.replace('^', '**')
        expr_str = expr_str.replace('×', '*')
        expr_str = expr_str.replace('÷', '/')
        
        # Handle common notation
        expr_str = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr_str)  # 2x -> 2*x
        expr_str = re.sub(r'([a-zA-Z])(\d)', r'\1*\2', expr_str)  # x2 -> x*2
        
        try:
            # Try standard parsing
            return sympify(expr_str, locals={
                'x': self.x, 'y': self.y, 't': self.t, 'n': self.n,
                'e': E, 'pi': pi, 'C': self.C
            })
        except (SympifyError, TypeError, ValueError):
            pass
        
        try:
            # Try LaTeX parsing
            return parse_latex(expr_str)
        except:
            pass
        
        return None
    
    def _compute_solution(
        self,
        expr,
        problem_type: ProblemType,
        problem: str
    ) -> Optional[any]:
        """Compute the expected solution."""
        
        try:
            if problem_type == ProblemType.DERIVATIVE:
                return diff(expr, self.x)
                
            elif problem_type == ProblemType.INTEGRAL:
                # Check if it's a definite integral
                limits = self._extract_limits(problem)
                if limits:
                    a, b = limits
                    return integrate(expr, (self.x, a, b))
                else:
                    # Indefinite integral
                    return integrate(expr, self.x)
                    
            elif problem_type == ProblemType.LIMIT:
                # Extract limit point
                point = self._extract_limit_point(problem)
                return limit(expr, self.x, point)
                
            elif problem_type == ProblemType.DIFFERENTIAL_EQ:
                # Basic ODE solving
                y = Function('y')
                return dsolve(expr, y(self.x))
                
            elif problem_type == ProblemType.SERIES:
                # Taylor series expansion
                point = self._extract_series_point(problem)
                terms = self._extract_series_terms(problem) or 5
                return series(expr, self.x, point, terms)
                
        except Exception as e:
            print(f"Computation error: {e}")
            return None
        
        return None
    
    def _compare_expressions(
        self,
        submitted,
        expected,
        problem_type: ProblemType
    ) -> bool:
        """Compare two expressions for equivalence."""
        
        try:
            # Direct equality
            if submitted == expected:
                return True
            
            # Simplified equality
            diff_expr = simplify(submitted - expected)
            if diff_expr == 0:
                return True
            
            # For integrals, allow for constant difference
            if problem_type == ProblemType.INTEGRAL:
                # Check if difference is a constant
                if diff(diff_expr, self.x) == 0:
                    return True
            
            # Check numerical equality at test points
            test_points = [0.5, 1.0, 2.0, -1.0]
            matches = 0
            
            for pt in test_points:
                try:
                    val1 = float(submitted.subs(self.x, pt).evalf())
                    val2 = float(expected.subs(self.x, pt).evalf())
                    if abs(val1 - val2) < 1e-6:
                        matches += 1
                except:
                    pass
            
            if matches >= 3:
                return True
                
        except Exception as e:
            print(f"Comparison error: {e}")
        
        return False
    
    def _extract_limits(self, problem: str) -> Optional[tuple]:
        """Extract integration limits from problem text."""
        
        # Pattern: "from a to b" or "[a, b]" or "a to b"
        patterns = [
            r'from\s+([\d.-]+)\s+to\s+([\d.-]+)',
            r'\[([\d.-]+),\s*([\d.-]+)\]',
            r'([\d.-]+)\s+to\s+([\d.-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, problem)
            if match:
                try:
                    a = float(match.group(1))
                    b = float(match.group(2))
                    return (a, b)
                except:
                    pass
        
        return None
    
    def _extract_limit_point(self, problem: str) -> any:
        """Extract the point for limit evaluation."""
        
        # Pattern: "as x approaches a" or "x -> a"
        patterns = [
            r'(?:as\s+)?x\s*(?:approaches|->|→)\s*([\d.+-]+|infinity|∞|inf)',
            r'x\s*=\s*([\d.+-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, problem, re.IGNORECASE)
            if match:
                point_str = match.group(1).lower()
                if point_str in ['infinity', '∞', 'inf', '+inf']:
                    return oo
                elif point_str == '-inf':
                    return -oo
                try:
                    return float(point_str)
                except:
                    pass
        
        return 0  # Default to 0
    
    def _extract_series_point(self, problem: str) -> float:
        """Extract the expansion point for series."""
        
        match = re.search(r'(?:around|at|about)\s*([\d.-]+)', problem, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        
        return 0  # Default to 0
    
    def _extract_series_terms(self, problem: str) -> Optional[int]:
        """Extract number of terms for series expansion."""
        
        match = re.search(r'(\d+)\s*terms?', problem, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None
