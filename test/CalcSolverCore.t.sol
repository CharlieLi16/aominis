// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/CalcSolverCore.sol";
import "../contracts/modules/OrderBook.sol";
import "../contracts/modules/Escrow.sol";
import "../contracts/modules/SolutionManager.sol";
import "../contracts/modules/Verifier.sol";
import "./mocks/MockERC20.sol";

contract CalcSolverCoreTest is Test {
    // Contracts
    CalcSolverCore public core;
    OrderBook public orderBook;
    Escrow public escrow;
    SolutionManager public solutionManager;
    Verifier public verifier;
    MockERC20 public usdc;

    // Users
    address public owner = address(1);
    address public issuer = address(2);
    address public solver = address(3);
    address public challenger = address(4);
    address public oracle = address(5);

    // Test data
    bytes32 public problemHash = keccak256("Find derivative of x^2 + 3x");
    string public solution = "2x + 3";
    bytes32 public salt = keccak256("random_salt");
    bytes32 public commitHash;

    // Events
    event ProblemPosted(uint256 indexed orderId, address indexed issuer, ProblemType problemType, TimeTier timeTier, uint256 reward);
    event OrderAccepted(uint256 indexed orderId, address indexed solver);
    event SolutionCommitted(uint256 indexed orderId, address indexed solver, bytes32 commitHash);
    event SolutionRevealed(uint256 indexed orderId, address indexed solver, string solution);

    function setUp() public {
        vm.startPrank(owner);

        // Deploy mock USDC
        usdc = new MockERC20("USD Coin", "USDC", 6);

        // Deploy core
        core = new CalcSolverCore(address(usdc));

        // Deploy modules
        orderBook = new OrderBook(address(core));
        escrow = new Escrow(address(usdc), address(core));
        solutionManager = new SolutionManager(address(core));
        verifier = new Verifier(address(core));

        // Configure core
        core.setModules(
            address(orderBook),
            address(escrow),
            address(solutionManager),
            address(verifier)
        );

        // Set oracle
        verifier.setOracle(oracle);

        vm.stopPrank();

        // Fund users
        usdc.mint(issuer, 1000 * 1e6); // 1000 USDC
        usdc.mint(solver, 1000 * 1e6);
        usdc.mint(challenger, 1000 * 1e6);

        // Approve core to spend
        vm.prank(issuer);
        usdc.approve(address(core), type(uint256).max);
        vm.prank(solver);
        usdc.approve(address(core), type(uint256).max);
        vm.prank(challenger);
        usdc.approve(address(core), type(uint256).max);

        // Compute commit hash
        commitHash = keccak256(abi.encodePacked(solution, salt));
    }

    // ============ Post Problem Tests ============

    function test_PostProblem() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        assertEq(orderId, 0);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(order.issuer, issuer);
        assertEq(order.problemHash, problemHash);
        assertEq(uint8(order.problemType), uint8(ProblemType.DERIVATIVE));
        assertEq(uint8(order.timeTier), uint8(TimeTier.T5min));
        assertEq(uint8(order.status), uint8(OrderStatus.OPEN));
        assertGt(order.reward, 0);
    }

    function test_PostProblem_EmitsEvent() public {
        uint256 expectedPrice = orderBook.getTierPrice(TimeTier.T5min);

        vm.expectEmit(true, true, false, true);
        emit ProblemPosted(0, issuer, ProblemType.DERIVATIVE, TimeTier.T5min, expectedPrice);

        vm.prank(issuer);
        core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
    }

    function test_PostProblem_TransfersPayment() public {
        uint256 balanceBefore = usdc.balanceOf(issuer);
        uint256 price = orderBook.getTierPrice(TimeTier.T5min);

        vm.prank(issuer);
        core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        assertEq(usdc.balanceOf(issuer), balanceBefore - price);
        assertEq(escrow.getLockedReward(0), price);
    }

    function test_RevertWhen_PostProblem_InvalidHash() public {
        vm.expectRevert("Invalid problem hash");
        vm.prank(issuer);
        core.postProblem(bytes32(0), ProblemType.DERIVATIVE, TimeTier.T5min);
    }

    function test_RevertWhen_PostProblem_InsufficientBalance() public {
        address poorUser = address(100);
        vm.prank(poorUser);
        usdc.approve(address(core), type(uint256).max);

        vm.expectRevert("Insufficient balance");
        vm.prank(poorUser);
        core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
    }

    // ============ Accept Order Tests ============

    function test_AcceptOrder() public {
        // Post problem
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        // Accept order
        vm.prank(solver);
        core.acceptOrder(orderId);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(order.solver, solver);
        assertEq(uint8(order.status), uint8(OrderStatus.ACCEPTED));
    }

    function test_AcceptOrder_LocksBond() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        uint256 balanceBefore = usdc.balanceOf(solver);

        vm.prank(solver);
        core.acceptOrder(orderId);

        uint256 bond = escrow.getSolverBond(orderId);
        assertGt(bond, 0);
        assertEq(usdc.balanceOf(solver), balanceBefore - bond);
    }

    function test_RevertWhen_AcceptOrder_NotOpen() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);

        address anotherSolver = address(10);
        usdc.mint(anotherSolver, 1000 * 1e6);
        vm.prank(anotherSolver);
        usdc.approve(address(core), type(uint256).max);
        
        vm.expectRevert("Order not open");
        vm.prank(anotherSolver);
        core.acceptOrder(orderId);
    }

    function test_RevertWhen_AcceptOrder_IssuerCannotSolve() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        vm.expectRevert("Cannot solve own problem");
        vm.prank(issuer);
        core.acceptOrder(orderId);
    }

    // ============ Commit Solution Tests ============

    function test_CommitSolution() public {
        // Setup
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);

        // Commit
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.COMMITTED));

        SolutionSubmission memory submission = core.getSolution(orderId);
        assertEq(submission.commitHash, commitHash);
        assertEq(submission.solver, solver);
    }

    function test_RevertWhen_CommitSolution_NotSolver() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);

        vm.expectRevert("Not the solver");
        vm.prank(issuer);
        core.commitSolution(orderId, commitHash);
    }

    // ============ Reveal Solution Tests ============

    function test_RevealSolution() public {
        // Setup
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        // Advance time past min reveal delay
        vm.warp(block.timestamp + 2);

        // Reveal
        vm.prank(solver);
        core.revealSolution(orderId, solution, salt);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.REVEALED));

        SolutionSubmission memory submission = core.getSolution(orderId);
        assertEq(submission.isRevealed, true);
        assertEq(submission.solution, solution);
    }

    function test_RevertWhen_RevealSolution_WrongSalt() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        vm.warp(block.timestamp + 2);

        bytes32 wrongSalt = keccak256("wrong_salt");
        vm.expectRevert("Invalid reveal");
        vm.prank(solver);
        core.revealSolution(orderId, solution, wrongSalt);
    }

    // ============ Claim Reward Tests ============

    function test_ClaimReward() public {
        // Full flow
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);

        vm.warp(block.timestamp + 2);
        vm.prank(solver);
        core.revealSolution(orderId, solution, salt);

        // Wait for challenge window
        vm.warp(block.timestamp + 25 hours);

        uint256 balanceBefore = usdc.balanceOf(solver);

        vm.prank(solver);
        core.claimReward(orderId);

        assertGt(usdc.balanceOf(solver), balanceBefore);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.VERIFIED));
    }

    function test_RevertWhen_ClaimReward_ChallengeWindowActive() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);
        vm.warp(block.timestamp + 2);
        vm.prank(solver);
        core.revealSolution(orderId, solution, salt);

        // Try to claim immediately (within challenge window)
        vm.expectRevert("Challenge window active");
        vm.prank(solver);
        core.claimReward(orderId);
    }

    // ============ Timeout Tests ============

    function test_ClaimTimeout() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        // Wait past deadline
        vm.warp(block.timestamp + 6 minutes);

        uint256 balanceBefore = usdc.balanceOf(issuer);

        vm.prank(issuer);
        core.claimTimeout(orderId);

        assertGt(usdc.balanceOf(issuer), balanceBefore);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.EXPIRED));
    }

    function test_ClaimTimeout_SlashesSolverBond() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);

        uint256 bond = escrow.getSolverBond(orderId);
        assertGt(bond, 0);

        // Wait past deadline
        vm.warp(block.timestamp + 6 minutes);

        vm.prank(issuer);
        core.claimTimeout(orderId);

        // Bond should be slashed (moved to protocol fees)
        assertEq(escrow.getSolverBond(orderId), 0);
    }

    // ============ Challenge Tests ============

    function test_SubmitChallenge() public {
        // Full flow to revealed state
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);
        vm.warp(block.timestamp + 2);
        vm.prank(solver);
        core.revealSolution(orderId, solution, salt);

        // Submit challenge
        vm.prank(challenger);
        core.submitChallenge(orderId, "Solution is incorrect");

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.CHALLENGED));

        Challenge memory challenge = core.getChallenge(orderId);
        assertEq(challenge.challenger, challenger);
    }

    function test_RevertWhen_SubmitChallenge_AfterWindow() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, commitHash);
        vm.warp(block.timestamp + 2);
        vm.prank(solver);
        core.revealSolution(orderId, solution, salt);

        // Wait past challenge window
        vm.warp(block.timestamp + 25 hours);

        vm.expectRevert("Challenge window closed");
        vm.prank(challenger);
        core.submitChallenge(orderId, "Too late");
    }

    // ============ Cancel Order Tests ============

    function test_CancelOrder() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        uint256 balanceBefore = usdc.balanceOf(issuer);

        vm.prank(issuer);
        core.cancelOrder(orderId);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.status), uint8(OrderStatus.CANCELLED));
        assertGt(usdc.balanceOf(issuer), balanceBefore);
    }

    function test_RevertWhen_CancelOrder_NotIssuer() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);

        vm.expectRevert("Not the issuer");
        vm.prank(solver);
        core.cancelOrder(orderId);
    }

    function test_RevertWhen_CancelOrder_AlreadyAccepted() public {
        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);

        vm.expectRevert("Can only cancel open orders");
        vm.prank(issuer);
        core.cancelOrder(orderId);
    }

    // ============ Fuzz Tests ============

    function testFuzz_PostProblem_DifferentTiers(uint8 tierIndex) public {
        vm.assume(tierIndex < 4);
        TimeTier tier = TimeTier(tierIndex);

        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, tier);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.timeTier), tierIndex);
        assertGt(order.reward, 0);
    }

    function testFuzz_PostProblem_DifferentTypes(uint8 typeIndex) public {
        vm.assume(typeIndex < 5);
        ProblemType pType = ProblemType(typeIndex);

        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, pType, TimeTier.T5min);

        ProblemOrder memory order = core.getOrder(orderId);
        assertEq(uint8(order.problemType), typeIndex);
    }

    function testFuzz_CommitReveal_AnySalt(bytes32 randomSalt) public {
        vm.assume(randomSalt != bytes32(0));

        bytes32 testCommitHash = keccak256(abi.encodePacked(solution, randomSalt));

        vm.prank(issuer);
        uint256 orderId = core.postProblem(problemHash, ProblemType.DERIVATIVE, TimeTier.T5min);
        vm.prank(solver);
        core.acceptOrder(orderId);
        vm.prank(solver);
        core.commitSolution(orderId, testCommitHash);

        vm.warp(block.timestamp + 2);

        vm.prank(solver);
        core.revealSolution(orderId, solution, randomSalt);

        SolutionSubmission memory submission = core.getSolution(orderId);
        assertTrue(submission.isRevealed);
    }
}
