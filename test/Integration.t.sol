// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/CalcSolverCore.sol";
import "../contracts/modules/OrderBook.sol";
import "../contracts/modules/Escrow.sol";
import "../contracts/modules/SolutionManager.sol";
import "../contracts/modules/Verifier.sol";
import "./mocks/MockERC20.sol";

/**
 * @title Integration Tests
 * @notice End-to-end tests for the full protocol flow
 */
contract IntegrationTest is Test {
    CalcSolverCore public core;
    OrderBook public orderBook;
    Escrow public escrow;
    SolutionManager public solutionManager;
    Verifier public verifier;
    MockERC20 public usdc;

    address public owner = address(1);
    address public issuer = address(2);
    address public solver = address(3);
    address public challenger = address(4);
    address public oracle = address(5);

    function setUp() public {
        vm.startPrank(owner);

        usdc = new MockERC20("USD Coin", "USDC", 6);
        core = new CalcSolverCore(address(usdc));
        orderBook = new OrderBook(address(core));
        escrow = new Escrow(address(usdc), address(core));
        solutionManager = new SolutionManager(address(core));
        verifier = new Verifier(address(core));

        core.setModules(
            address(orderBook),
            address(escrow),
            address(solutionManager),
            address(verifier)
        );
        verifier.setOracle(oracle);

        vm.stopPrank();

        // Fund all users
        usdc.mint(issuer, 10000 * 1e6);
        usdc.mint(solver, 10000 * 1e6);
        usdc.mint(challenger, 10000 * 1e6);

        vm.prank(issuer);
        usdc.approve(address(core), type(uint256).max);
        vm.prank(solver);
        usdc.approve(address(core), type(uint256).max);
        vm.prank(challenger);
        usdc.approve(address(core), type(uint256).max);
    }

    // ============ Happy Path ============

    function test_FullFlow_HappyPath() public {
        // 1. Issuer posts problem
        bytes32 problemHash = keccak256("Integrate x^2 dx");
        
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.INTEGRAL, TimeTier.T15min);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.OPEN));

        // 2. Solver accepts
        uint256 solverBalanceBefore = usdc.balanceOf(solver);
        
        vm.prank(solver);
        core.acceptOrder(orderId);

        order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.ACCEPTED));
        assertEq(order.solver, solver);

        // 3. Solver commits solution
        string memory solution = "x^3/3 + C";
        bytes32 salt = keccak256("my_secret_salt");
        bytes32 commitHash = keccak256(abi.encodePacked(solution, salt));

        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.COMMITTED));

        // 4. Solver reveals solution
        vm.warp(block.timestamp + 2);
        
        vm.prank(solver);
        core.revealSolution(orderId, solution, salt);

        order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.REVEALED));

        SolutionSubmission memory submission = core.getSolution(orderId);
        assertEq(submission.solution, solution);
        assertTrue(submission.isRevealed);

        // 5. Wait for challenge window to pass
        vm.warp(block.timestamp + 25 hours);

        // 6. Solver claims reward
        vm.prank(solver);
        core.claimReward(orderId);

        order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.VERIFIED));

        // Solver should have more than before (reward - bond = profit)
        uint256 solverBalanceAfter = usdc.balanceOf(solver);
        assertGt(solverBalanceAfter, solverBalanceBefore);
    }

    // ============ Challenge Flow ============

    function test_FullFlow_ChallengeWins() public {
        // Setup: Post, accept, commit, reveal
        bytes32 problemHash = keccak256("Find limit of sin(x)/x as x->0");
        
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.LIMIT, TimeTier.T5min);
        
        vm.prank(solver);
        core.acceptOrder(orderId);

        string memory wrongSolution = "0"; // Wrong! Correct answer is 1
        bytes32 salt = keccak256("salt123");
        bytes32 commitHash = keccak256(abi.encodePacked(wrongSolution, salt));

        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        vm.warp(block.timestamp + 2);
        vm.prank(solver);
        core.revealSolution(orderId, wrongSolution, salt);

        // Challenger submits challenge
        uint256 challengerBalanceBefore = usdc.balanceOf(challenger);
        
        vm.prank(challenger);
        core.submitChallenge(orderId, "Answer should be 1, not 0");

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.CHALLENGED));

        // Oracle resolves challenge in favor of challenger
        vm.prank(oracle);
        verifier.resolveChallenge(orderId, true); // challenger wins

        order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.REJECTED));

        // Challenger should have same or more tokens (stake back + bonus if any)
        uint256 challengerBalanceAfter = usdc.balanceOf(challenger);
        assertGe(challengerBalanceAfter, challengerBalanceBefore);
    }

    function test_FullFlow_ChallengeLoses() public {
        bytes32 problemHash = keccak256("Derivative of e^x");
        
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        
        vm.prank(solver);
        core.acceptOrder(orderId);

        string memory correctSolution = "e^x";
        bytes32 salt = keccak256("correct_salt");
        bytes32 commitHash = keccak256(abi.encodePacked(correctSolution, salt));

        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        vm.warp(block.timestamp + 2);
        vm.prank(solver);
        core.revealSolution(orderId, correctSolution, salt);

        uint256 solverBalanceBefore = usdc.balanceOf(solver);

        // Challenger wrongly challenges
        vm.prank(challenger);
        core.submitChallenge(orderId, "I think this is wrong");

        // Oracle resolves in favor of solver
        vm.prank(oracle);
        verifier.resolveChallenge(orderId, false); // challenger loses

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.VERIFIED));

        // Solver gets reward + part of challenger's stake
        uint256 solverBalanceAfter = usdc.balanceOf(solver);
        assertGt(solverBalanceAfter, solverBalanceBefore);
    }

    // ============ Timeout Flow ============

    function test_FullFlow_Timeout_NoSolver() public {
        bytes32 problemHash = keccak256("Hard problem");
        uint256 issuerBalanceBefore = usdc.balanceOf(issuer);
        
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DIFFERENTIAL_EQ, TimeTier.T2min);

        uint256 issuerBalanceAfterPost = usdc.balanceOf(issuer);
        assertLt(issuerBalanceAfterPost, issuerBalanceBefore);

        // No one accepts, deadline passes
        vm.warp(block.timestamp + 3 minutes);

        vm.prank(issuer);
        core.claimTimeout(orderId);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.EXPIRED));

        // Issuer gets refund
        uint256 issuerBalanceAfterRefund = usdc.balanceOf(issuer);
        assertEq(issuerBalanceAfterRefund, issuerBalanceBefore);
    }

    function test_FullFlow_Timeout_SolverAcceptedButFailed() public {
        bytes32 problemHash = keccak256("Very hard problem");
        
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.SERIES, TimeTier.T2min);

        uint256 solverBalanceBefore = usdc.balanceOf(solver);
        
        vm.prank(solver);
        core.acceptOrder(orderId);

        uint256 solverBond = escrow.getSolverBond(orderId);
        assertGt(solverBond, 0);

        // Solver accepts but doesn't deliver
        vm.warp(block.timestamp + 3 minutes);

        vm.prank(issuer);
        core.claimTimeout(orderId);

        // Solver loses bond
        assertEq(escrow.getSolverBond(orderId), 0);
        assertLt(usdc.balanceOf(solver), solverBalanceBefore);
    }

    // ============ Multiple Orders ============

    function test_MultipleOrdersConcurrently() public {
        // Post 5 orders
        uint256[] memory orderIds = new uint256[](5);
        
        for (uint256 i = 0; i < 5; i++) {
            bytes32 hash = keccak256(abi.encodePacked("Problem", i));
            vm.prank(issuer);
            orderIds[i] = core.postProblem(hash, ProblemType(i % 5), TimeTier(i % 4));
        }

        // Verify all are open
        for (uint256 i = 0; i < 5; i++) {
            ProblemOrder memory order = core.getOrder(orderIds[i]);
            assertEq(uint8(order.status), uint8(OrderStatus.OPEN));
        }

        // Solver accepts and solves first 3
        for (uint256 i = 0; i < 3; i++) {
            vm.prank(solver);
            core.acceptOrder(orderIds[i]);

            string memory sol = string(abi.encodePacked("Solution", i));
            bytes32 salt = keccak256(abi.encodePacked("salt", i));
            bytes32 commitHash = keccak256(abi.encodePacked(sol, salt));

            vm.prank(solver);
            core.commitSolution(orderIds[i], commitHash);

            vm.warp(block.timestamp + 2);

            vm.prank(solver);
            core.revealSolution(orderIds[i], sol, salt);
        }

        // Cancel one
        vm.prank(issuer);
        core.cancelOrder(orderIds[3]);

        // Let last one timeout
        vm.warp(block.timestamp + 2 hours);
        vm.prank(issuer);
        core.claimTimeout(orderIds[4]);

        // Verify final states
        assertEq(uint8(core.getOrder(orderIds[0]).status), uint8(OrderStatus.REVEALED));
        assertEq(uint8(core.getOrder(orderIds[1]).status), uint8(OrderStatus.REVEALED));
        assertEq(uint8(core.getOrder(orderIds[2]).status), uint8(OrderStatus.REVEALED));
        assertEq(uint8(core.getOrder(orderIds[3]).status), uint8(OrderStatus.CANCELLED));
        assertEq(uint8(core.getOrder(orderIds[4]).status), uint8(OrderStatus.EXPIRED));
    }

    // ============ Edge Cases ============

    function test_EdgeCase_ExactDeadline() public {
        bytes32 problemHash = keccak256("Deadline test");
        
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        ProblemOrder memory order = core.getOrder(orderId);
        uint256 deadline = order.deadline;

        // Warp to exactly deadline
        vm.warp(deadline);

        // Should still be able to accept (at deadline, not past)
        // Note: This depends on implementation (< vs <=)
        // Our implementation uses <, so at exact deadline it's expired
        vm.expectRevert("Order expired");
        vm.prank(solver);
        core.acceptOrder(orderId);
    }

    function test_EdgeCase_MinimumPricing() public {
        // Even with zero gas price, should have base fee
        vm.fee(0);
        
        uint256 price = orderBook.getTierPrice(TimeTier.T1hour);
        assertGt(price, 0);
    }
}
