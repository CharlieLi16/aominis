#!/usr/bin/env python3
"""
Test suite for parse_gpt_solution function.
Run with: python test_parse_gpt.py
"""

import re

# Copy of parse_gpt_solution for testing (or import from bot_server)
def parse_gpt_solution(content: str) -> dict:
    """Parse GPT response into answer and steps."""
    result = {'answer': '', 'steps': []}
    
    # Extract answer: capture everything after ANSWER: to end of content (multi-line / LaTeX safe)
    answer_match = re.search(r'ANSWER:\s*([\s\S]*)', content, re.IGNORECASE)
    if answer_match:
        result['answer'] = answer_match.group(1).strip()
    else:
        # Fallback: use last line or whole content
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        result['answer'] = lines[-1] if lines else content
    
    # Extract steps
    steps_match = re.search(r'STEPS:\s*\n([\s\S]*?)(?:ANSWER:|$)', content, re.IGNORECASE)
    if steps_match:
        steps_text = steps_match.group(1).strip()
        step_lines = re.findall(r'^\d+\.\s*(.+)', steps_text, re.MULTILINE)
        
        for i, step_line in enumerate(step_lines):
            # Parse "description => result" format
            if '=>' in step_line:
                parts = step_line.split('=>', 1)
                step_content = parts[0].strip()
                step_result = parts[1].strip() if len(parts) > 1 else ''
            else:
                step_content = step_line.strip()
                step_result = ''
            
            result['steps'].append({
                'step': i + 1,
                'content': step_content,
                'result': step_result
            })
    
    return result


# ==================== TEST CASES ====================

TEST_CASES = [
    {
        "name": "Simple derivative",
        "input": """STEPS:
1. Apply power rule to x² => 2x
2. Apply constant rule to 3x => 3
3. Sum the results => 2x + 3

ANSWER: f'(x) = 2x + 3""",
        "expected_answer": "f'(x) = 2x + 3",
        "expected_steps_count": 3,
    },
    
    {
        "name": "Multi-line LaTeX matrix (identity matrix case)",
        "input": """STEPS:
1. Define a 3x3 identity matrix, which has 1s on the diagonal and 0s elsewhere => Identity matrix

ANSWER: 
\\[
\\begin{bmatrix}
1 & 0 & 0 \\\\
0 & 1 & 0 \\\\
0 & 0 & 1
\\end{bmatrix}
\\]""",
        "expected_answer": """\\[
\\begin{bmatrix}
1 & 0 & 0 \\\\
0 & 1 & 0 \\\\
0 & 0 & 1
\\end{bmatrix}
\\]""",
        "expected_steps_count": 1,
    },
    
    {
        "name": "Inline LaTeX answer",
        "input": """STEPS:
1. Integrate x² using power rule => x³/3
2. Add constant of integration => + C

ANSWER: \\( \\frac{x^3}{3} + C \\)""",
        "expected_answer": "\\( \\frac{x^3}{3} + C \\)",
        "expected_steps_count": 2,
    },
    
    {
        "name": "Answer with newline after colon",
        "input": """STEPS:
1. First step => result1

ANSWER:
The solution is x = 5""",
        "expected_answer": "The solution is x = 5",
        "expected_steps_count": 1,
    },
    
    {
        "name": "No STEPS section (fallback)",
        "input": """Here is the solution:
The derivative of x² is 2x.

ANSWER: 2x""",
        "expected_answer": "2x",
        "expected_steps_count": 0,
    },
    
    {
        "name": "No ANSWER marker (fallback to last line)",
        "input": """STEPS:
1. Apply rule => done

The final answer is 42""",
        "expected_answer": "The final answer is 42",
        "expected_steps_count": 1,
    },
    
    {
        "name": "Complex linear algebra with free variables",
        "input": """STEPS:
1. Row reduce R1 - 2*R2 => [1 0 2 | 3]
2. Continue to RREF => Matrix in reduced form
3. Identify free variable z => z is free

ANSWER: Infinitely many solutions: x = 3 - 2z, y = 1 + z, z = t (free parameter)""",
        "expected_answer": "Infinitely many solutions: x = 3 - 2z, y = 1 + z, z = t (free parameter)",
        "expected_steps_count": 3,
    },
    
    {
        "name": "Answer with special characters",
        "input": """STEPS:
1. Calculate => ∫ f(x) dx

ANSWER: F(x) = x³/3 + C, where C ∈ ℝ""",
        "expected_answer": "F(x) = x³/3 + C, where C ∈ ℝ",
        "expected_steps_count": 1,
    },
    
    {
        "name": "Multi-line answer with explanation",
        "input": """STEPS:
1. Solve the system => unique solution

ANSWER: 
x = 1
y = 2
z = 3

This is a unique solution because the matrix has full rank.""",
        "expected_answer": """x = 1
y = 2
z = 3

This is a unique solution because the matrix has full rank.""",
        "expected_steps_count": 1,
    },
    
    {
        "name": "Case insensitive ANSWER",
        "input": """STEPS:
1. Step one => result

answer: lowercase answer marker""",
        "expected_answer": "lowercase answer marker",
        "expected_steps_count": 1,
    },
    
    {
        "name": "Steps without => separator",
        "input": """STEPS:
1. First step description
2. Second step description
3. Third step description

ANSWER: final result""",
        "expected_answer": "final result",
        "expected_steps_count": 3,
    },
    
    {
        "name": "Empty content",
        "input": "",
        "expected_answer": "",
        "expected_steps_count": 0,
    },
    
    {
        "name": "Real GPT response with code block in answer",
        "input": """STEPS:
1. The identity matrix I_n has 1s on main diagonal => Definition
2. For 3x3: diagonal entries are (1,1), (2,2), (3,3) => I₃

ANSWER: 
```
| 1  0  0 |
| 0  1  0 |
| 0  0  1 |
```""",
        "expected_answer": """```
| 1  0  0 |
| 0  1  0 |
| 0  0  1 |
```""",
        "expected_steps_count": 2,
    },
    
    {
        "name": "Multi-part problem (a)(b) with matrices",
        "input": """STEPS:

**(a)**  
1. Start with the original matrix => given
2. Row reduce R2 - 4*R1 => elimination
3. Continue to RREF => final form

**(b)**
4. Start with second matrix => given
5. Row reduce => RREF

ANSWER:
**(a)** Infinitely many solutions. The RREF is:
\\[
\\begin{pmatrix}
1 & 0 & -1 & -2 \\\\
0 & 1 & 2 & 3 \\\\
0 & 0 & 0 & 0
\\end{pmatrix}
\\]
Free variable: x₃. Solution: x₁ = -2 + x₃, x₂ = 3 - 2x₃, x₃ free.

**(b)** Inconsistent (no solution). The RREF shows a row [0 0 0 | 1].""",
        "expected_answer": """**(a)** Infinitely many solutions. The RREF is:
\\[
\\begin{pmatrix}
1 & 0 & -1 & -2 \\\\
0 & 1 & 2 & 3 \\\\
0 & 0 & 0 & 0
\\end{pmatrix}
\\]
Free variable: x₃. Solution: x₁ = -2 + x₃, x₂ = 3 - 2x₃, x₃ free.

**(b)** Inconsistent (no solution). The RREF shows a row [0 0 0 | 1].""",
        "expected_steps_count": 5,
    },
    
    {
        "name": "GPT response with embedded ANSWER in steps (edge case)",
        "input": """STEPS:
1. First we need to find the ANSWER to part a => start
2. Continue solving => done

ANSWER: The final result is 42""",
        "expected_answer": "The final result is 42",
        "expected_steps_count": 2,
    },
]


def run_tests():
    """Run all test cases and report results."""
    print("=" * 60)
    print("Testing parse_gpt_solution()")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_CASES, 1):
        name = test["name"]
        result = parse_gpt_solution(test["input"])
        
        # Check answer
        answer_ok = result["answer"] == test["expected_answer"]
        
        # Check steps count
        steps_ok = len(result["steps"]) == test["expected_steps_count"]
        
        if answer_ok and steps_ok:
            print(f"\n✅ Test {i}: {name}")
            passed += 1
        else:
            print(f"\n❌ Test {i}: {name}")
            failed += 1
            
            if not answer_ok:
                print(f"   Expected answer: {repr(test['expected_answer'][:80])}...")
                print(f"   Got answer:      {repr(result['answer'][:80])}...")
            
            if not steps_ok:
                print(f"   Expected steps: {test['expected_steps_count']}")
                print(f"   Got steps:      {len(result['steps'])}")
        
        # Show parsed data for debugging
        print(f"   → Answer length: {len(result['answer'])} chars")
        print(f"   → Steps count: {len(result['steps'])}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(TEST_CASES)} tests")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
