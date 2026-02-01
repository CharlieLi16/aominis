"""
Challenge processing endpoint for Ominis Verifier API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from enum import IntEnum

router = APIRouter()


class ProblemType(IntEnum):
    DERIVATIVE = 0
    INTEGRAL = 1
    LIMIT = 2
    DIFFERENTIAL_EQ = 3
    SERIES = 4


class ChallengeRequest(BaseModel):
    order_id: int
    problem: str
    submitted_solution: str
    problem_type: ProblemType
    challenger_reason: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "order_id": 123,
                "problem": "Find the limit of sin(x)/x as x approaches 0",
                "submitted_solution": "0",
                "problem_type": 2,
                "challenger_reason": "The correct answer is 1, not 0"
            }
        }


class ChallengeResponse(BaseModel):
    order_id: int
    challenger_wins: bool
    confidence: float
    correct_solution: Optional[str] = None
    analysis: str


@router.post("/challenge", response_model=ChallengeResponse)
async def process_challenge(request: ChallengeRequest):
    """
    Process a challenge against a submitted solution.
    
    This performs more thorough verification than normal,
    since a challenge is a dispute that needs careful resolution.
    """
    
    from services.sympy_solver import SympySolver
    from services.gpt_solver import GPTSolver
    
    sympy_solver = SympySolver()
    gpt_solver = GPTSolver()
    
    try:
        # Get both verifications
        sympy_result = await sympy_solver.verify(
            problem=request.problem,
            solution=request.submitted_solution,
            problem_type=request.problem_type
        )
        
        gpt_result = await gpt_solver.verify(
            problem=request.problem,
            solution=request.submitted_solution,
            problem_type=request.problem_type
        )
        
        # For challenges, we also ask GPT to evaluate the challenger's claim
        challenger_evaluation = await gpt_solver.evaluate_challenge(
            problem=request.problem,
            submitted_solution=request.submitted_solution,
            challenger_reason=request.challenger_reason,
            problem_type=request.problem_type
        )
        
        # Decision logic for challenges
        # We're more conservative here - both methods should agree
        
        analysis_parts = []
        
        if sympy_result.confidence > 0.5:
            analysis_parts.append(f"SymPy says: {'correct' if sympy_result.is_correct else 'incorrect'} (confidence: {sympy_result.confidence:.2f})")
        
        if gpt_result.confidence > 0.5:
            analysis_parts.append(f"GPT-4 says: {'correct' if gpt_result.is_correct else 'incorrect'} (confidence: {gpt_result.confidence:.2f})")
        
        analysis_parts.append(f"Challenger's argument: {challenger_evaluation.assessment}")
        
        # Determine outcome
        # Challenger wins if the solution is incorrect
        solution_is_incorrect = False
        confidence = 0.5
        
        # Strong agreement that solution is wrong
        if (not sympy_result.is_correct and sympy_result.confidence > 0.8 and
            not gpt_result.is_correct and gpt_result.confidence > 0.8):
            solution_is_incorrect = True
            confidence = 0.95
        # Strong agreement that solution is correct
        elif (sympy_result.is_correct and sympy_result.confidence > 0.8 and
              gpt_result.is_correct and gpt_result.confidence > 0.8):
            solution_is_incorrect = False
            confidence = 0.95
        # SymPy is confident, GPT uncertain or agrees
        elif sympy_result.confidence > 0.9:
            solution_is_incorrect = not sympy_result.is_correct
            confidence = sympy_result.confidence * 0.9
        # GPT is confident, SymPy uncertain
        elif gpt_result.confidence > 0.9:
            solution_is_incorrect = not gpt_result.is_correct
            confidence = gpt_result.confidence * 0.85
        # Neither confident - consider challenger's argument
        elif challenger_evaluation.is_valid:
            solution_is_incorrect = True
            confidence = 0.7
            analysis_parts.append("Challenger's mathematical argument appears valid")
        else:
            # Default to original solution being correct (benefit of doubt)
            solution_is_incorrect = False
            confidence = 0.6
            analysis_parts.append("Insufficient evidence to overturn solution")
        
        correct_solution = sympy_result.expected_solution or gpt_result.expected_solution
        
        return ChallengeResponse(
            order_id=request.order_id,
            challenger_wins=solution_is_incorrect,
            confidence=confidence,
            correct_solution=correct_solution,
            analysis=" | ".join(analysis_parts)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Challenge processing failed: {str(e)}")


@router.get("/challenge/{order_id}")
async def get_challenge_status(order_id: int):
    """Get the status of a challenge (placeholder for database lookup)"""
    
    # In production, this would query a database
    return {
        "order_id": order_id,
        "status": "pending",
        "message": "Challenge status lookup not implemented yet"
    }
