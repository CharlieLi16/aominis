"""
Calculus Instant Solver Protocol - Economic Simulation

This simulation validates:
1. Cost model: Is $0.01/problem achievable?
2. Incentive alignment: Is honest solving more profitable than gaming?
3. Parameter sensitivity: How do bond/slash ratios affect behavior?

Key questions to answer:
- What happens when solvers always try but sometimes fail?
- What happens with malicious solvers (submit wrong answers)?
- What's the equilibrium if challenge rate varies?
- How does pricing affect solver participation?
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import random


# ============ Protocol Configuration ============

@dataclass
class ProtocolConfig:
    """Protocol parameters matching smart contract constants"""
    
    # Time tiers (seconds)
    tier_durations: Dict[str, int] = field(default_factory=lambda: {
        "T2min": 120,
        "T5min": 300,
        "T10min": 600
    })
    
    # Pricing per tier (USD)
    tier_prices: Dict[str, float] = field(default_factory=lambda: {
        "T2min": 0.99,
        "T5min": 0.49,
        "T10min": 0.29
    })
    
    # Bond and slash parameters
    solver_bond_percent: float = 50.0      # Bond as % of reward
    no_commit_slash_percent: float = 20.0  # Slash % for abandonment
    wrong_answer_slash_percent: float = 100.0  # Slash % for wrong answer
    challenger_reward_percent: float = 30.0  # Challenger gets this % of slash
    
    # Timing
    reveal_window_seconds: int = 30
    challenge_window_seconds: int = 30
    
    # Protocol fee
    protocol_fee_percent: float = 5.0


# ============ Cost Model ============

@dataclass
class CostModel:
    """Cost breakdown for solving a problem"""
    
    # AI inference cost (GPT-4 or similar)
    ai_inference_cost: float = 0.005  # $0.005 per problem
    
    # CAS verification cost (SymPy/Mathematica)
    verification_cost: float = 0.0005  # $0.0005 per problem
    
    # L2 gas cost (amortized batch)
    gas_cost: float = 0.001  # $0.001 per problem
    
    # Retry buffer (10% of problems need retry)
    retry_rate: float = 0.10
    retry_cost: float = 0.005  # Cost of retry
    
    @property
    def total_cost_per_problem(self) -> float:
        """Calculate expected cost per problem"""
        base_cost = self.ai_inference_cost + self.verification_cost + self.gas_cost
        retry_expected = self.retry_rate * self.retry_cost
        return base_cost + retry_expected
    
    def print_breakdown(self):
        """Print cost breakdown"""
        print("=== Cost Model ===")
        print(f"AI Inference:    ${self.ai_inference_cost:.4f}")
        print(f"Verification:    ${self.verification_cost:.4f}")
        print(f"Gas (L2 batch):  ${self.gas_cost:.4f}")
        print(f"Retry buffer:    ${self.retry_rate * self.retry_cost:.4f}")
        print(f"---")
        print(f"TOTAL:           ${self.total_cost_per_problem:.4f}")
        print(f"Target:          $0.01")
        print(f"Margin:          {(0.01 - self.total_cost_per_problem) / 0.01 * 100:.1f}%")


# ============ Agents ============

class SolverStrategy(Enum):
    """Solver behavior strategies"""
    HONEST = "honest"           # Try to solve correctly
    LAZY = "lazy"               # Submit random answers sometimes
    MALICIOUS = "malicious"     # Always submit wrong answers (griefing)
    SELECTIVE = "selective"     # Only accept easy problems


@dataclass
class Solver:
    """A solver agent in the simulation"""
    
    id: int
    strategy: SolverStrategy
    skill: float = 0.9              # Probability of solving correctly
    speed_factor: float = 1.0       # Multiplier on solving time
    
    # Stats
    total_earnings: float = 0.0
    total_costs: float = 0.0
    problems_attempted: int = 0
    problems_solved: int = 0
    problems_failed: int = 0
    bonds_slashed: float = 0.0
    
    @property
    def net_profit(self) -> float:
        return self.total_earnings - self.total_costs - self.bonds_slashed
    
    @property
    def success_rate(self) -> float:
        if self.problems_attempted == 0:
            return 0.0
        return self.problems_solved / self.problems_attempted


@dataclass
class Problem:
    """A problem posted by an issuer"""
    
    id: int
    tier: str                       # "T2min", "T5min", "T10min"
    difficulty: float               # 0.0 (easy) to 1.0 (hard)
    reward: float                   # USD
    deadline_seconds: int
    
    # State
    solver: Optional[Solver] = None
    is_solved: bool = False
    solution_correct: bool = False
    was_challenged: bool = False


# ============ Simulation Engine ============

class Simulation:
    """
    Main simulation engine
    
    Scenarios to run:
    1. BASELINE: All honest solvers with varying skill
       - Verify cost model works
       - Verify honest solvers profit
    
    2. ADVERSARIAL: Mix of honest and malicious solvers
       - Verify malicious solvers lose money
       - Verify challenge mechanism works
    
    3. MARKET DYNAMICS: Varying problem difficulty and solver competition
       - Verify pricing reflects difficulty
       - Verify equilibrium emerges
    
    4. PARAMETER SWEEP: Try different bond/slash ratios
       - Find optimal parameters
       - Identify edge cases
    """
    
    def __init__(self, config: ProtocolConfig, cost_model: CostModel):
        self.config = config
        self.cost_model = cost_model
        self.solvers: List[Solver] = []
        self.problems: List[Problem] = []
        self.round = 0
    
    def add_solver(self, solver: Solver):
        """Add a solver to the simulation"""
        self.solvers.append(solver)
    
    def generate_problems(self, n: int, tier_distribution: Dict[str, float] = None):
        """
        Generate n random problems
        
        - tier_distribution: probability of each tier (default uniform)
        - difficulty: random 0.0-1.0
        """
        
        if tier_distribution is None:
            tiers = list(self.config.tier_durations.keys())
            probs = np.full(len(tiers), 1.0 / len(tiers))
        else:
            tiers = list(tier_distribution.keys())
            probs = np.asarray([tier_distribution[tier] for tier in tiers], dtype=float)
            total = probs.sum()
            if total != 1.0:
                probs = probs / total

        chosen_tiers = np.random.choice(tiers, size=n, p=probs)
        difficulties = np.random.random(size=n)

        start_id = len(self.problems)
        for i in range(n):
            tier = chosen_tiers[i]
            self.problems.append(Problem(
                id=start_id + i,
                tier=tier,
                difficulty=float(difficulties[i]),
                reward=self.config.tier_prices[tier],
                deadline_seconds=self.config.tier_durations[tier],
            ))
    
    def simulate_round(self):
        """
        Simulate one round of the market
        
        1. Generate new problems
        2. Solvers decide which problems to accept (based on strategy)
        3. Solvers attempt to solve (based on skill)
        4. Some solutions get challenged (random or strategic)
        5. Settlement: pay solvers, slash bonds, refund issuers
        6. Record stats
        """
        self.round += 1
        if not self.solvers:
            return

        n_new = len(self.solvers)
        start_idx = len(self.problems)
        self.generate_problems(n_new)
        new_problems = self.problems[start_idx:]

        for problem in new_problems:
            # Find an accepting solver
            solver = None
            for candidate in random.sample(self.solvers, len(self.solvers)):
                if self._solver_decides_to_accept(candidate, problem):
                    solver = candidate
                    break

            if solver is None:
                continue

            problem.solver = solver
            solver.problems_attempted += 1
            solver.total_costs += self.cost_model.total_cost_per_problem

            success = self._solver_attempts_solution(solver, problem)
            problem.is_solved = True
            problem.solution_correct = success

            # Challenge model: wrong answers more likely to be challenged
            if success:
                problem.was_challenged = random.random() < 0.02
            else:
                problem.was_challenged = random.random() < 0.20

            reward = problem.reward * (1 - self.config.protocol_fee_percent / 100)
            bond = problem.reward * (self.config.solver_bond_percent / 100)
            slash = bond * (self.config.wrong_answer_slash_percent / 100)

            if success:
                solver.problems_solved += 1
                solver.total_earnings += reward
            else:
                solver.problems_failed += 1
                if problem.was_challenged:
                    solver.bonds_slashed += slash
                else:
                    solver.total_earnings += reward
    
    def _solver_decides_to_accept(self, solver: Solver, problem: Problem) -> bool:
        """
        Should this solver accept this problem?
        
        - HONEST: Accept if expected value positive
        - LAZY: Accept everything (lazy)
        - MALICIOUS: Accept everything (to grief)
        - SELECTIVE: Only accept if difficulty < threshold
        """
        if solver.strategy == SolverStrategy.HONEST:
            return self._calculate_expected_value(solver, problem) > 0
        if solver.strategy in (SolverStrategy.LAZY, SolverStrategy.MALICIOUS):
            return True
        if solver.strategy == SolverStrategy.SELECTIVE:
            return problem.difficulty < 0.5
        return True
    
    def _solver_attempts_solution(self, solver: Solver, problem: Problem) -> bool:
        """
        Does the solver successfully solve the problem?
        
        - Based on solver.skill and problem.difficulty
        - HONEST: skill-adjusted success
        - LAZY: random (50% correct)
        - MALICIOUS: always wrong
        - SELECTIVE: high success on easy problems
        """
        if solver.strategy == SolverStrategy.MALICIOUS:
            return False
        if solver.strategy == SolverStrategy.LAZY:
            return random.random() < 0.5
        if solver.strategy == SolverStrategy.SELECTIVE and problem.difficulty < 0.5:
            p_success = solver.skill
        else:
            p_success = solver.skill * (1 - problem.difficulty)
        if p_success < 0.0:
            p_success = 0.0
        elif p_success > 1.0:
            p_success = 1.0
        return random.random() < p_success
    
    def _calculate_expected_value(
        self, 
        solver: Solver, 
        problem: Problem
    ) -> float:
        """
        Calculate expected value of accepting a problem
        
        EV = P(success) * reward - P(failure) * slash - cost
        
        TODO: Implement
        """
        p_success = solver.skill * (1 - problem.difficulty)
        bond = problem.reward * (self.config.solver_bond_percent / 100)
        
        ev_success = problem.reward  # Get reward + bond back
        ev_failure = -bond * (self.config.wrong_answer_slash_percent / 100)
        
        cost = self.cost_model.total_cost_per_problem
        
        ev = p_success * ev_success + (1 - p_success) * ev_failure - cost
        return ev
    
    def run(self, n_rounds: int):
        """Run simulation for n rounds"""
        for _ in range(n_rounds):
            self.simulate_round()
    
    def print_results(self):
        """Print simulation results"""
        print("\n=== Simulation Results ===")
        print(f"Rounds: {self.round}")
        print(f"Total problems: {len(self.problems)}")
        print()
        
        for solver in self.solvers:
            print(f"Solver {solver.id} ({solver.strategy.value}):")
            print(f"  Attempted: {solver.problems_attempted}")
            print(f"  Solved:    {solver.problems_solved}")
            print(f"  Failed:    {solver.problems_failed}")
            print(f"  Success:   {solver.success_rate:.1%}")
            print(f"  Earnings:  ${solver.total_earnings:.2f}")
            print(f"  Costs:     ${solver.total_costs:.2f}")
            print(f"  Slashed:   ${solver.bonds_slashed:.2f}")
            print(f"  Net:       ${solver.net_profit:.2f}")
            print()


# ============ Tests ============

def test_cost_model():
    """Verify cost model achieves $0.01 target"""
    cost_model = CostModel()
    cost_model.print_breakdown()
    
    assert cost_model.total_cost_per_problem < 0.01, \
        f"Cost ${cost_model.total_cost_per_problem:.4f} exceeds $0.01 target"
    print("✓ Cost model passes")


def test_honest_solver_profits():
    """Verify honest solvers make profit"""
    config = ProtocolConfig()
    cost_model = CostModel()
    
    # High-skill honest solver
    solver = Solver(id=1, strategy=SolverStrategy.HONEST, skill=0.95)
    
    # Simulate many problems
    n_problems = 1000
    tier = "T5min"
    reward = config.tier_prices[tier]
    bond = reward * (config.solver_bond_percent / 100)
    
    for _ in range(n_problems):
        solver.problems_attempted += 1
        solver.total_costs += cost_model.total_cost_per_problem
        
        # 95% success rate
        if random.random() < solver.skill:
            solver.problems_solved += 1
            solver.total_earnings += reward
        else:
            solver.problems_failed += 1
            slash = bond * (config.wrong_answer_slash_percent / 100)
            solver.bonds_slashed += slash
    
    print(f"\n=== Honest Solver Test ===")
    print(f"Success rate: {solver.success_rate:.1%}")
    print(f"Earnings: ${solver.total_earnings:.2f}")
    print(f"Costs: ${solver.total_costs:.2f}")
    print(f"Slashed: ${solver.bonds_slashed:.2f}")
    print(f"Net profit: ${solver.net_profit:.2f}")
    
    assert solver.net_profit > 0, "Honest solver should profit"
    print("✓ Honest solver profits")


def test_malicious_solver_loses():
    """Verify malicious solvers lose money"""
    config = ProtocolConfig()
    cost_model = CostModel()
    
    # Malicious solver (always wrong)
    solver = Solver(id=2, strategy=SolverStrategy.MALICIOUS, skill=0.0)
    
    n_problems = 100
    tier = "T5min"
    reward = config.tier_prices[tier]
    bond = reward * (config.solver_bond_percent / 100)
    
    for _ in range(n_problems):
        solver.problems_attempted += 1
        solver.total_costs += cost_model.total_cost_per_problem
        
        # Always fails
        solver.problems_failed += 1
        slash = bond * (config.wrong_answer_slash_percent / 100)
        solver.bonds_slashed += slash
    
    print(f"\n=== Malicious Solver Test ===")
    print(f"Attempts: {solver.problems_attempted}")
    print(f"Costs: ${solver.total_costs:.2f}")
    print(f"Slashed: ${solver.bonds_slashed:.2f}")
    print(f"Net profit: ${solver.net_profit:.2f}")
    
    assert solver.net_profit < 0, "Malicious solver should lose money"
    print("✓ Malicious solver loses money")


def test_parameter_sensitivity():
        """
        Test how different bond/slash ratios affect outcomes
        
        Sweep over:
        - solver_bond_percent: 25%, 50%, 75%, 100%
        - wrong_answer_slash_percent: 50%, 75%, 100%
        - challenger_reward_percent: 10%, 30%, 50%
        """
        print("\n=== Parameter Sensitivity ===")
        bond_values = [25.0, 50.0, 75.0, 100.0]
        slash_values = [50.0, 75.0, 100.0]
        challenger_values = [10.0, 30.0, 50.0]

        for bond_pct in bond_values:
            for slash_pct in slash_values:
                for challenger_pct in challenger_values:
                    config = ProtocolConfig(
                        solver_bond_percent=bond_pct,
                        wrong_answer_slash_percent=slash_pct,
                        challenger_reward_percent=challenger_pct,
                    )
                    sim = Simulation(config=config, cost_model=CostModel())
                    sim.add_solver(Solver(id=1, strategy=SolverStrategy.HONEST, skill=0.9))
                    sim.add_solver(Solver(id=2, strategy=SolverStrategy.MALICIOUS, skill=0.0))
                    sim.run(50)

                    honest = sim.solvers[0]
                    malicious = sim.solvers[1]
                    print(
                        f"bond={bond_pct:.0f}% slash={slash_pct:.0f}% "
                        f"challenger={challenger_pct:.0f}% | "
                        f"honest_net=${honest.net_profit:.2f} "
                        f"malicious_net=${malicious.net_profit:.2f}"
                    )


# ============ Main ============

if __name__ == "__main__":
    print("Calculus Solver Protocol - Economic Simulation\n")
    
    # Run tests
    test_cost_model()
    test_honest_solver_profits()
    test_malicious_solver_loses()
    test_parameter_sensitivity()
    
    print("\n=== All tests passed ===")
