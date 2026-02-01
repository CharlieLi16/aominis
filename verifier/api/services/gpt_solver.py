"""
GPT-4 based calculus solver and verifier
"""

import os
import json
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


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


@dataclass
class ChallengeEvaluation:
    is_valid: bool
    assessment: str


PROBLEM_TYPE_NAMES = {
    ProblemType.DERIVATIVE: "derivative",
    ProblemType.INTEGRAL: "integral",
    ProblemType.LIMIT: "limit",
    ProblemType.DIFFERENTIAL_EQ: "differential equation",
    ProblemType.SERIES: "series expansion"
}


class GPTSolver:
    """
    GPT-4 based calculus verifier.
    
    Uses GPT-4 to verify solutions when SymPy cannot handle
    the problem (e.g., complex notation, ambiguous problems).
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        if OPENAI_AVAILABLE and self.api_key:
            openai.api_key = self.api_key
    
    async def verify(
        self,
        problem: str,
        solution: str,
        problem_type: ProblemType
    ) -> VerificationResult:
        """
        Verify a solution using GPT-4.
        """
        
        if not OPENAI_AVAILABLE or not self.api_key:
            return VerificationResult(
                is_correct=False,
                confidence=0.0,
                reason="OpenAI API not available"
            )
        
        type_name = PROBLEM_TYPE_NAMES.get(problem_type, "calculus problem")
        
        prompt = f"""You are a calculus expert. Verify if the given solution to a {type_name} problem is correct.

Problem: {problem}
Submitted Solution: {solution}

Analyze the problem, solve it yourself, and compare with the submitted solution.

Respond in JSON format:
{{
    "is_correct": true/false,
    "confidence": 0.0-1.0,
    "expected_solution": "your computed solution",
    "reason": "brief explanation"
}}

Be precise. Consider equivalent forms (e.g., x^2/2 = 0.5x^2). For integrals, allow for constant differences.
"""
        
        try:
            response = await self._call_gpt(prompt)
            result = json.loads(response)
            
            return VerificationResult(
                is_correct=result.get("is_correct", False),
                confidence=min(1.0, max(0.0, result.get("confidence", 0.5))),
                expected_solution=result.get("expected_solution"),
                reason=result.get("reason")
            )
            
        except json.JSONDecodeError:
            # Try to extract answer from non-JSON response
            response_lower = response.lower()
            is_correct = "correct" in response_lower and "incorrect" not in response_lower
            
            return VerificationResult(
                is_correct=is_correct,
                confidence=0.6,
                reason=response[:200]
            )
            
        except Exception as e:
            return VerificationResult(
                is_correct=False,
                confidence=0.0,
                reason=f"GPT error: {str(e)}"
            )
    
    async def evaluate_challenge(
        self,
        problem: str,
        submitted_solution: str,
        challenger_reason: str,
        problem_type: ProblemType
    ) -> ChallengeEvaluation:
        """
        Evaluate a challenger's claim against a submitted solution.
        """
        
        if not OPENAI_AVAILABLE or not self.api_key:
            return ChallengeEvaluation(
                is_valid=False,
                assessment="OpenAI API not available"
            )
        
        type_name = PROBLEM_TYPE_NAMES.get(problem_type, "calculus problem")
        
        prompt = f"""You are a calculus expert evaluating a dispute.

Problem ({type_name}): {problem}
Submitted Solution: {submitted_solution}
Challenger's Claim: {challenger_reason}

Evaluate:
1. Is the challenger's mathematical reasoning valid?
2. Is the submitted solution actually incorrect?

Respond in JSON format:
{{
    "challenger_is_correct": true/false,
    "assessment": "brief explanation of your analysis"
}}
"""
        
        try:
            response = await self._call_gpt(prompt)
            result = json.loads(response)
            
            return ChallengeEvaluation(
                is_valid=result.get("challenger_is_correct", False),
                assessment=result.get("assessment", "")
            )
            
        except Exception as e:
            return ChallengeEvaluation(
                is_valid=False,
                assessment=f"Could not evaluate: {str(e)}"
            )
    
    async def solve(
        self,
        problem: str,
        problem_type: ProblemType
    ) -> Optional[str]:
        """
        Solve a calculus problem using GPT-4.
        """
        
        if not OPENAI_AVAILABLE or not self.api_key:
            return None
        
        type_name = PROBLEM_TYPE_NAMES.get(problem_type, "calculus problem")
        
        prompt = f"""Solve this {type_name}:

{problem}

Provide only the final answer in mathematical notation. No explanation needed.
"""
        
        try:
            response = await self._call_gpt(prompt)
            return response.strip()
        except:
            return None
    
    async def _call_gpt(self, prompt: str) -> str:
        """Make API call to GPT-4."""
        
        try:
            # Using the new OpenAI API format
            client = openai.OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert calculus mathematician. Be precise and accurate."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for more deterministic answers
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            # Fallback for older API or mock
            raise Exception(f"GPT API call failed: {str(e)}")


# Mock for testing without API key
class MockGPTSolver(GPTSolver):
    """Mock GPT solver for testing."""
    
    async def verify(
        self,
        problem: str,
        solution: str,
        problem_type: ProblemType
    ) -> VerificationResult:
        """Simple pattern-based mock verification."""
        
        # Very basic mock logic
        problem_lower = problem.lower()
        solution_lower = solution.lower()
        
        # Derivative of x^2 = 2x
        if "x^2" in problem_lower and "derivative" in problem_lower:
            is_correct = "2x" in solution_lower or "2*x" in solution_lower
            return VerificationResult(
                is_correct=is_correct,
                confidence=0.8,
                expected_solution="2x",
                reason="Mock verification"
            )
        
        # Default: assume correct with low confidence
        return VerificationResult(
            is_correct=True,
            confidence=0.5,
            reason="Mock: Unable to verify"
        )
    
    async def evaluate_challenge(
        self,
        problem: str,
        submitted_solution: str,
        challenger_reason: str,
        problem_type: ProblemType
    ) -> ChallengeEvaluation:
        """Mock challenge evaluation."""
        
        return ChallengeEvaluation(
            is_valid=False,
            assessment="Mock: Cannot evaluate challenge"
        )
