"""
Verification endpoint for Ominis Verifier API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from enum import IntEnum

import sys
sys.path.append('..')
from services.sympy_solver import SympySolver
from services.gpt_solver import GPTSolver

router = APIRouter()


class ProblemType(IntEnum):
    DERIVATIVE = 0
    INTEGRAL = 1
    LIMIT = 2
    DIFFERENTIAL_EQ = 3
    SERIES = 4


class VerifyRequest(BaseModel):
    order_id: int
    problem: str  # The problem statement (LaTeX or plain text)
    solution: str  # The submitted solution
    problem_type: ProblemType
    
    class Config:
        json_schema_extra = {
            "example": {
                "order_id": 123,
                "problem": "Find the derivative of f(x) = x^2 + 3x",
                "solution": "2x + 3",
                "problem_type": 0
            }
        }


class VerifyResponse(BaseModel):
    order_id: int
    is_correct: bool
    confidence: float  # 0.0 to 1.0
    method: str  # Which verification method was used
    expected_solution: Optional[str] = None
    reason: Optional[str] = None


# Initialize solvers
sympy_solver = SympySolver()
gpt_solver = GPTSolver()


@router.post("/verify", response_model=VerifyResponse)
async def verify_solution(request: VerifyRequest):
    """
    Verify a calculus solution.
    
    Uses a multi-stage verification approach:
    1. Try SymPy (symbolic computation) first - fast and deterministic
    2. If SymPy can't verify, use GPT-4 - handles complex/ambiguous cases
    """
    
    try:
        # Stage 1: Try SymPy verification
        sympy_result = await sympy_solver.verify(
            problem=request.problem,
            solution=request.solution,
            problem_type=request.problem_type
        )
        
        if sympy_result.confidence >= 0.9:
            return VerifyResponse(
                order_id=request.order_id,
                is_correct=sympy_result.is_correct,
                confidence=sympy_result.confidence,
                method="sympy",
                expected_solution=sympy_result.expected_solution,
                reason=sympy_result.reason
            )
        
        # Stage 2: Use GPT-4 for complex cases
        gpt_result = await gpt_solver.verify(
            problem=request.problem,
            solution=request.solution,
            problem_type=request.problem_type
        )
        
        # Combine results if both available
        if sympy_result.confidence > 0 and gpt_result.confidence > 0:
            # Both agree
            if sympy_result.is_correct == gpt_result.is_correct:
                combined_confidence = min(1.0, (sympy_result.confidence + gpt_result.confidence) / 1.5)
                return VerifyResponse(
                    order_id=request.order_id,
                    is_correct=sympy_result.is_correct,
                    confidence=combined_confidence,
                    method="sympy+gpt",
                    expected_solution=sympy_result.expected_solution or gpt_result.expected_solution,
                    reason=f"Both methods agree: {gpt_result.reason}"
                )
            else:
                # Disagreement - use higher confidence one
                if sympy_result.confidence > gpt_result.confidence:
                    return VerifyResponse(
                        order_id=request.order_id,
                        is_correct=sympy_result.is_correct,
                        confidence=sympy_result.confidence * 0.8,  # Reduce confidence due to disagreement
                        method="sympy (disputed)",
                        expected_solution=sympy_result.expected_solution,
                        reason=f"SymPy result, but GPT disagrees"
                    )
                else:
                    return VerifyResponse(
                        order_id=request.order_id,
                        is_correct=gpt_result.is_correct,
                        confidence=gpt_result.confidence * 0.8,
                        method="gpt (disputed)",
                        expected_solution=gpt_result.expected_solution,
                        reason=f"GPT result, but SymPy disagrees"
                    )
        
        # Return GPT result if SymPy failed
        return VerifyResponse(
            order_id=request.order_id,
            is_correct=gpt_result.is_correct,
            confidence=gpt_result.confidence,
            method="gpt",
            expected_solution=gpt_result.expected_solution,
            reason=gpt_result.reason
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/verify/sympy", response_model=VerifyResponse)
async def verify_with_sympy(request: VerifyRequest):
    """Verify using only SymPy (for testing)"""
    
    result = await sympy_solver.verify(
        problem=request.problem,
        solution=request.solution,
        problem_type=request.problem_type
    )
    
    return VerifyResponse(
        order_id=request.order_id,
        is_correct=result.is_correct,
        confidence=result.confidence,
        method="sympy",
        expected_solution=result.expected_solution,
        reason=result.reason
    )


@router.post("/verify/gpt", response_model=VerifyResponse)
async def verify_with_gpt(request: VerifyRequest):
    """Verify using only GPT-4 (for testing)"""
    
    result = await gpt_solver.verify(
        problem=request.problem,
        solution=request.solution,
        problem_type=request.problem_type
    )
    
    return VerifyResponse(
        order_id=request.order_id,
        is_correct=result.is_correct,
        confidence=result.confidence,
        method="gpt",
        expected_solution=result.expected_solution,
        reason=result.reason
    )
