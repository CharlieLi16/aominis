// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./interfaces/ICalcSolver.sol";

/**
 * @title CalcSolverCore
 * @notice Main coordinator contract for Ominis Calculus Solver Protocol
 * @dev Orchestrates interactions between OrderBook, Escrow, SolutionManager, Verifier,
 *      SubscriptionManager, BotRegistry, and RatingSystem
 */
contract CalcSolverCore is ICalcSolverCore, ICalcSolverEvents {
    // ============ Enums ============
    
    enum TargetType {
        PLATFORM_BOT,   // Use platform's default bot
        SPECIFIC_BOT,   // User chooses a specific bot
        PROBLEM_POOL    // Random assignment from pool
    }
    
    // ============ State Variables ============
    
    IERC20 public immutable paymentToken;
    IOrderBook public orderBook;
    IEscrow public escrow;
    ISolutionManager public solutionManager;
    IVerifier public verifier;
    
    // Marketplace modules
    ISubscriptionManager public subscriptionManager;
    IBotRegistry public botRegistry;
    IRatingSystem public ratingSystem;
    
    address public owner;
    bool public paused;
    bool public subscriptionModeEnabled;  // Toggle between old per-payment and new subscription mode
    
    uint256 public solverBondBps = 1000; // 10% of reward as solver bond
    uint256 public challengeStakeBps = 2000; // 20% of reward as challenge stake
    uint256 public protocolFeeBps = 250; // 2.5% protocol fee
    
    // Order to Bot mapping for marketplace
    mapping(uint256 => address) public orderBot;  // orderId => assigned bot
    
    // Reentrancy guard
    uint256 private constant NOT_ENTERED = 1;
    uint256 private constant ENTERED = 2;
    uint256 private _status;
    
    // ============ Modifiers ============
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }
    
    modifier whenNotPaused() {
        require(!paused, "Protocol paused");
        _;
    }
    
    modifier nonReentrant() {
        require(_status != ENTERED, "Reentrant call");
        _status = ENTERED;
        _;
        _status = NOT_ENTERED;
    }
    
    // ============ Constructor ============
    
    constructor(address _paymentToken) {
        require(_paymentToken != address(0), "Invalid token");
        paymentToken = IERC20(_paymentToken);
        owner = msg.sender;
        _status = NOT_ENTERED;
    }
    
    // ============ Admin Functions ============
    
    function setModules(
        address _orderBook,
        address _escrow,
        address _solutionManager,
        address _verifier
    ) external onlyOwner {
        require(_orderBook != address(0), "Invalid orderBook");
        require(_escrow != address(0), "Invalid escrow");
        require(_solutionManager != address(0), "Invalid solutionManager");
        require(_verifier != address(0), "Invalid verifier");
        
        orderBook = IOrderBook(_orderBook);
        escrow = IEscrow(_escrow);
        solutionManager = ISolutionManager(_solutionManager);
        verifier = IVerifier(_verifier);
    }
    
    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
    }
    
    function setFees(
        uint256 _solverBondBps,
        uint256 _challengeStakeBps,
        uint256 _protocolFeeBps
    ) external onlyOwner {
        require(_solverBondBps <= 5000, "Bond too high");
        require(_challengeStakeBps <= 5000, "Stake too high");
        require(_protocolFeeBps <= 1000, "Fee too high");
        
        solverBondBps = _solverBondBps;
        challengeStakeBps = _challengeStakeBps;
        protocolFeeBps = _protocolFeeBps;
    }
    
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Invalid owner");
        owner = newOwner;
    }
    
    function setMarketplaceModules(
        address _subscriptionManager,
        address _botRegistry,
        address _ratingSystem
    ) external onlyOwner {
        if (_subscriptionManager != address(0)) {
            subscriptionManager = ISubscriptionManager(_subscriptionManager);
        }
        if (_botRegistry != address(0)) {
            botRegistry = IBotRegistry(_botRegistry);
        }
        if (_ratingSystem != address(0)) {
            ratingSystem = IRatingSystem(_ratingSystem);
        }
    }
    
    function setSubscriptionMode(bool enabled) external onlyOwner {
        subscriptionModeEnabled = enabled;
    }
    
    // ============ Core Functions ============
    
    /**
     * @notice Post a new calculus problem
     * @param problemHash IPFS hash or keccak256 of problem content
     * @param problemType Type of calculus problem
     * @param timeTier Time tier for solving (affects price and deadline)
     */
    function postProblem(
        bytes32 problemHash,
        ProblemType problemType,
        TimeTier timeTier
    ) external whenNotPaused nonReentrant returns (uint256 orderId) {
        require(problemHash != bytes32(0), "Invalid problem hash");
        
        // Get price for this tier
        uint256 price = orderBook.getTierPrice(timeTier);
        require(price > 0, "Price not set");
        
        // Transfer payment to escrow
        require(
            paymentToken.transferFrom(msg.sender, address(escrow), price),
            "Token transfer failed"
        );
        
        // Create order
        orderId = orderBook.postProblem(problemHash, problemType, timeTier, msg.sender);
        
        // Lock reward in escrow
        escrow.lockReward(orderId, msg.sender, price);
        
        emit ProblemPosted(orderId, msg.sender, problemType, timeTier, price);
    }
    
    /**
     * @notice Post a problem using subscription credits (Marketplace mode)
     * @param problemHash IPFS hash or keccak256 of problem content
     * @param problemType Type of calculus problem
     * @param target How to route this problem (platform bot, specific bot, or pool)
     * @param targetBot The specific bot address (if target == SPECIFIC_BOT)
     */
    function postProblemWithSubscription(
        bytes32 problemHash,
        ProblemType problemType,
        TargetType target,
        address targetBot
    ) external whenNotPaused nonReentrant returns (uint256 orderId) {
        require(subscriptionModeEnabled, "Subscription mode not enabled");
        require(problemHash != bytes32(0), "Invalid problem hash");
        require(address(subscriptionManager) != address(0), "Subscription manager not set");
        require(address(botRegistry) != address(0), "Bot registry not set");
        
        // 1. Check and use credit
        require(subscriptionManager.useCredit(msg.sender), "No credits remaining");
        
        // 2. Validate target and premium access
        address assignedBot;
        
        if (target == TargetType.PLATFORM_BOT) {
            assignedBot = botRegistry.platformBot();
            require(assignedBot != address(0), "Platform bot not set");
        } 
        else if (target == TargetType.SPECIFIC_BOT) {
            require(targetBot != address(0), "Target bot required");
            IBotRegistry.BotInfo memory bot = botRegistry.getBotInfo(targetBot);
            require(bot.isActive, "Bot not active");
            
            // Check premium access if needed
            if (bot.isPremium) {
                require(
                    subscriptionManager.hasPremiumAccess(msg.sender),
                    "Upgrade to Study+ for Premium Bots"
                );
            }
            assignedBot = targetBot;
        }
        else if (target == TargetType.PROBLEM_POOL) {
            // Random assignment from pool
            assignedBot = _assignFromPool(uint8(problemType));
            require(assignedBot != address(0), "No eligible solvers");
        }
        
        // 3. Create order (no payment needed, using subscription)
        // Use T15min as default tier for subscription orders
        orderId = orderBook.postProblem(problemHash, problemType, TimeTier.T15min, msg.sender);
        
        // 4. Record bot assignment and usage
        orderBot[orderId] = assignedBot;
        botRegistry.incrementUsage(assignedBot);
        subscriptionManager.recordSolverUsage(assignedBot);
        
        // 5. Record for rating system
        if (address(ratingSystem) != address(0)) {
            ratingSystem.recordOrderSolver(orderId, assignedBot);
        }
        
        emit ProblemPosted(orderId, msg.sender, problemType, TimeTier.T15min, 0);
        emit OrderAssignedToBot(orderId, assignedBot, target);
    }
    
    /**
     * @notice Assign a problem to a random solver from the pool
     * @param problemType The problem type
     * @return selectedBot The randomly selected bot address
     */
    function _assignFromPool(uint8 problemType) internal view returns (address) {
        address[] memory eligible = botRegistry.getEligibleSolvers(problemType);
        if (eligible.length == 0) return address(0);
        
        // Pseudo-random selection based on block hash
        uint256 randomIndex = uint256(blockhash(block.number - 1)) % eligible.length;
        return eligible[randomIndex];
    }
    
    // ============ Events for Marketplace ============
    
    event OrderAssignedToBot(
        uint256 indexed orderId,
        address indexed bot,
        TargetType targetType
    );
    
    /**
     * @notice Accept an open order to become its solver
     * @param orderId The order to accept
     */
    function acceptOrder(uint256 orderId) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        
        require(order.status == OrderStatus.OPEN, "Order not open");
        require(order.issuer != msg.sender, "Cannot solve own problem");
        require(block.timestamp < order.deadline, "Order expired");
        
        // Calculate and transfer solver bond
        uint256 bond = (order.reward * solverBondBps) / 10000;
        if (bond > 0) {
            require(
                paymentToken.transferFrom(msg.sender, address(escrow), bond),
                "Bond transfer failed"
            );
            escrow.lockSolverBond(orderId, msg.sender, bond);
        }
        
        // Update order
        orderBook.acceptOrder(orderId, msg.sender);
        
        emit OrderAccepted(orderId, msg.sender);
    }
    
    /**
     * @notice Commit a solution hash (first step of commit-reveal)
     * @param orderId The order ID
     * @param commitHash keccak256(abi.encodePacked(solution, salt))
     */
    function commitSolution(uint256 orderId, bytes32 commitHash) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        
        require(order.status == OrderStatus.ACCEPTED, "Order not accepted");
        require(order.solver == msg.sender, "Not the solver");
        require(block.timestamp < order.deadline, "Deadline passed");
        require(commitHash != bytes32(0), "Invalid commit hash");
        
        // Commit solution
        solutionManager.commitSolution(orderId, msg.sender, commitHash);
        orderBook.updateOrderStatus(orderId, OrderStatus.COMMITTED);
        
        emit SolutionCommitted(orderId, msg.sender, commitHash);
    }
    
    /**
     * @notice Reveal a previously committed solution
     * @param orderId The order ID
     * @param solution The actual solution string
     * @param salt The salt used in the commit
     */
    function revealSolution(
        uint256 orderId,
        string calldata solution,
        bytes32 salt
    ) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        
        require(order.status == OrderStatus.COMMITTED, "Not committed");
        require(order.solver == msg.sender, "Not the solver");
        
        // Reveal and verify commitment
        bool valid = solutionManager.revealSolution(orderId, msg.sender, solution, salt);
        require(valid, "Invalid reveal");
        
        // Update status to revealed (starts challenge window)
        orderBook.updateOrderStatus(orderId, OrderStatus.REVEALED);
        
        emit SolutionRevealed(orderId, msg.sender, solution);
        
        // Request verification (could trigger oracle call)
        verifier.requestVerification(orderId, solution, order.problemType);
        
        // Record solution in bot registry if marketplace mode
        if (address(botRegistry) != address(0) && orderBot[orderId] != address(0)) {
            botRegistry.recordSolution(orderBot[orderId], orderId);
        }
    }
    
    /**
     * @notice Claim reward after challenge window expires without challenge
     * @param orderId The order ID
     */
    function claimReward(uint256 orderId) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        SolutionSubmission memory submission = solutionManager.getSubmission(orderId);
        
        require(order.status == OrderStatus.REVEALED, "Not revealed");
        require(order.solver == msg.sender, "Not the solver");
        require(submission.isRevealed, "Solution not revealed");
        
        // Check challenge window has passed
        uint256 challengeWindow = verifier.getChallengeWindow();
        require(
            block.timestamp > submission.revealTime + challengeWindow,
            "Challenge window active"
        );
        require(!verifier.isUnderChallenge(orderId), "Under challenge");
        
        // Mark as verified and release funds
        orderBook.updateOrderStatus(orderId, OrderStatus.VERIFIED);
        escrow.releaseRewardToSolver(orderId);
        
        emit SolutionVerified(orderId, true);
        emit RewardPaid(orderId, msg.sender, order.reward);
    }
    
    /**
     * @notice Claim timeout refund when solver fails to deliver
     * @param orderId The order ID
     */
    function claimTimeout(uint256 orderId) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        
        require(
            order.status == OrderStatus.OPEN || 
            order.status == OrderStatus.ACCEPTED ||
            order.status == OrderStatus.COMMITTED,
            "Invalid status for timeout"
        );
        require(block.timestamp > order.deadline, "Deadline not passed");
        require(order.issuer == msg.sender, "Not the issuer");
        
        // Update status
        orderBook.updateOrderStatus(orderId, OrderStatus.EXPIRED);
        
        // Refund issuer
        escrow.refundToIssuer(orderId);
        
        // Slash solver bond if they accepted but didn't deliver
        if (order.status == OrderStatus.ACCEPTED || order.status == OrderStatus.COMMITTED) {
            escrow.slashSolver(orderId);
        }
        
        emit OrderExpired(orderId);
    }
    
    /**
     * @notice Submit a challenge against a revealed solution
     * @param orderId The order ID
     * @param reason Reason for the challenge
     */
    function submitChallenge(uint256 orderId, string calldata reason) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        SolutionSubmission memory submission = solutionManager.getSubmission(orderId);
        
        require(order.status == OrderStatus.REVEALED, "Not revealed");
        require(submission.isRevealed, "Solution not revealed");
        require(order.solver != msg.sender, "Solver cannot challenge");
        require(order.issuer != msg.sender || bytes(reason).length > 0, "Issuer needs reason");
        
        // Check within challenge window
        uint256 challengeWindow = verifier.getChallengeWindow();
        require(
            block.timestamp <= submission.revealTime + challengeWindow,
            "Challenge window closed"
        );
        
        // Calculate and transfer challenge stake
        uint256 stake = (order.reward * challengeStakeBps) / 10000;
        require(
            paymentToken.transferFrom(msg.sender, address(escrow), stake),
            "Stake transfer failed"
        );
        escrow.lockChallengeStake(orderId, msg.sender, stake);
        
        // Submit challenge
        verifier.submitChallenge(orderId, msg.sender, reason);
        orderBook.updateOrderStatus(orderId, OrderStatus.CHALLENGED);
        
        emit ChallengeSubmitted(orderId, msg.sender, stake);
    }
    
    /**
     * @notice Cancel an open order (issuer only, before anyone accepts)
     * @param orderId The order ID
     */
    function cancelOrder(uint256 orderId) external whenNotPaused nonReentrant {
        ProblemOrder memory order = orderBook.getOrder(orderId);
        
        require(order.status == OrderStatus.OPEN, "Can only cancel open orders");
        require(order.issuer == msg.sender, "Not the issuer");
        
        orderBook.updateOrderStatus(orderId, OrderStatus.CANCELLED);
        escrow.refundToIssuer(orderId);
    }
    
    /**
     * @notice Resolve a challenge (called by verifier/oracle)
     * @param orderId The order ID
     * @param challengerWon Whether the challenger was correct
     */
    function resolveChallenge(uint256 orderId, bool challengerWon) external {
        require(msg.sender == address(verifier), "Only verifier");
        
        ProblemOrder memory order = orderBook.getOrder(orderId);
        require(order.status == OrderStatus.CHALLENGED, "Not under challenge");
        
        if (challengerWon) {
            // Solution was incorrect
            orderBook.updateOrderStatus(orderId, OrderStatus.REJECTED);
            escrow.slashSolver(orderId);
            escrow.rewardChallenger(orderId);
            escrow.refundToIssuer(orderId);
        } else {
            // Solution was correct, challenger loses stake
            orderBook.updateOrderStatus(orderId, OrderStatus.VERIFIED);
            escrow.slashChallenger(orderId);
            escrow.releaseRewardToSolver(orderId);
        }
        
        Challenge memory challenge = verifier.getChallenge(orderId);
        address winner = challengerWon ? challenge.challenger : order.solver;
        
        emit ChallengeResolved(orderId, challengerWon, winner);
    }
    
    // ============ View Functions ============
    
    function getOrder(uint256 orderId) external view returns (ProblemOrder memory) {
        return orderBook.getOrder(orderId);
    }
    
    function getSolution(uint256 orderId) external view returns (SolutionSubmission memory) {
        return solutionManager.getSubmission(orderId);
    }
    
    function getChallenge(uint256 orderId) external view returns (Challenge memory) {
        return verifier.getChallenge(orderId);
    }
    
    function getOpenOrders(uint256 offset, uint256 limit) external view returns (ProblemOrder[] memory) {
        return orderBook.getOpenOrders(offset, limit);
    }
    
    function getTierPrice(TimeTier tier) external view returns (uint256) {
        return orderBook.getTierPrice(tier);
    }
    
    function getOrderBot(uint256 orderId) external view returns (address) {
        return orderBot[orderId];
    }
    
    function isSubscriptionModeEnabled() external view returns (bool) {
        return subscriptionModeEnabled;
    }
}
