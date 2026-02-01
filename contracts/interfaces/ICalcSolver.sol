// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ICalcSolver
 * @notice Shared interfaces and structs for Ominis Calculus Solver Protocol
 */

// ============ External Interfaces ============

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
}

// ============ Enums ============

enum ProblemType {
    DERIVATIVE,      // Find derivatives
    INTEGRAL,        // Compute integrals
    LIMIT,           // Evaluate limits
    DIFFERENTIAL_EQ, // Solve differential equations
    SERIES           // Series and sequences
}

enum TimeTier {
    T2min,   // 2 minutes - fastest, most expensive
    T5min,   // 5 minutes
    T15min,  // 15 minutes
    T1hour   // 1 hour - cheapest
}

enum OrderStatus {
    OPEN,       // Waiting for solver
    ACCEPTED,   // Solver accepted, working on solution
    COMMITTED,  // Solution hash committed
    REVEALED,   // Solution revealed, pending verification
    VERIFIED,   // Solution verified correct
    CHALLENGED, // Solution being challenged
    EXPIRED,    // Deadline passed without solution
    CANCELLED,  // Cancelled by issuer
    REJECTED    // Solution rejected after challenge
}

// ============ Structs ============

struct ProblemOrder {
    uint256 id;
    address issuer;
    bytes32 problemHash;       // IPFS hash or keccak256 of problem content
    ProblemType problemType;
    TimeTier timeTier;
    OrderStatus status;
    uint256 reward;
    uint256 createdAt;
    uint256 deadline;
    address solver;
}

struct SolutionSubmission {
    uint256 orderId;
    address solver;
    bytes32 commitHash;        // keccak256(solution + salt)
    string solution;           // Revealed solution
    bytes32 salt;              // Salt used in commit
    uint256 commitTime;
    uint256 revealTime;
    bool isRevealed;
}

struct Challenge {
    uint256 orderId;
    address challenger;
    uint256 stake;
    uint256 challengeTime;
    bool resolved;
    bool challengerWon;
    string reason;
}

struct SolverProfile {
    address solver;
    uint256 totalSolved;
    uint256 totalChallenged;
    uint256 challengesLost;
    uint256 totalEarned;
    uint256 reputation;        // 0-10000 (basis points)
    bool isActive;
}

struct PricingConfig {
    uint256 baseFee;           // Minimum fee in token units (e.g., 100000 = $0.10 USDC)
    uint256 gasEstimate;       // Estimated gas units for verification
    uint256 timePremiumBps;    // Time premium in basis points (100 = 1%)
}

// ============ Events ============

interface ICalcSolverEvents {
    event ProblemPosted(
        uint256 indexed orderId,
        address indexed issuer,
        ProblemType problemType,
        TimeTier timeTier,
        uint256 reward
    );
    
    event OrderAccepted(
        uint256 indexed orderId,
        address indexed solver
    );
    
    event SolutionCommitted(
        uint256 indexed orderId,
        address indexed solver,
        bytes32 commitHash
    );
    
    event SolutionRevealed(
        uint256 indexed orderId,
        address indexed solver,
        string solution
    );
    
    event SolutionVerified(
        uint256 indexed orderId,
        bool isCorrect
    );
    
    event ChallengeSubmitted(
        uint256 indexed orderId,
        address indexed challenger,
        uint256 stake
    );
    
    event ChallengeResolved(
        uint256 indexed orderId,
        bool challengerWon,
        address winner
    );
    
    event OrderExpired(
        uint256 indexed orderId
    );
    
    event RewardPaid(
        uint256 indexed orderId,
        address indexed recipient,
        uint256 amount
    );
}

// ============ Module Interfaces ============

interface IOrderBook {
    function postProblem(
        bytes32 problemHash,
        ProblemType problemType,
        TimeTier timeTier,
        address issuer
    ) external returns (uint256 orderId);
    
    function acceptOrder(uint256 orderId, address solver) external;
    function getOrder(uint256 orderId) external view returns (ProblemOrder memory);
    function getOpenOrders(uint256 offset, uint256 limit) external view returns (ProblemOrder[] memory);
    function getTierPrice(TimeTier tier) external view returns (uint256);
    function getTierDuration(TimeTier tier) external view returns (uint256);
    function updateOrderStatus(uint256 orderId, OrderStatus status) external;
    function setOrderSolver(uint256 orderId, address solver) external;
    function orderCount() external view returns (uint256);
}

interface IEscrow {
    function lockReward(uint256 orderId, address issuer, uint256 amount) external;
    function lockSolverBond(uint256 orderId, address solver, uint256 amount) external;
    function lockChallengeStake(uint256 orderId, address challenger, uint256 amount) external;
    function releaseRewardToSolver(uint256 orderId) external;
    function refundToIssuer(uint256 orderId) external;
    function slashSolver(uint256 orderId) external;
    function rewardChallenger(uint256 orderId) external;
    function slashChallenger(uint256 orderId) external;
    function getLockedReward(uint256 orderId) external view returns (uint256);
    function getSolverBond(uint256 orderId) external view returns (uint256);
}

interface ISolutionManager {
    function commitSolution(uint256 orderId, address solver, bytes32 commitHash) external;
    function revealSolution(uint256 orderId, address solver, string calldata solution, bytes32 salt) external returns (bool);
    function getSubmission(uint256 orderId) external view returns (SolutionSubmission memory);
    function isCommitted(uint256 orderId) external view returns (bool);
    function isRevealed(uint256 orderId) external view returns (bool);
    function verifyCommitment(uint256 orderId, string calldata solution, bytes32 salt) external view returns (bool);
}

interface IVerifier {
    function requestVerification(uint256 orderId, string calldata solution, ProblemType problemType) external;
    function submitVerificationResult(uint256 orderId, bool isCorrect, string calldata reason) external;
    function submitChallenge(uint256 orderId, address challenger, string calldata reason) external returns (uint256 challengeId);
    function resolveChallenge(uint256 orderId, bool challengerWon) external;
    function getChallenge(uint256 orderId) external view returns (Challenge memory);
    function isUnderChallenge(uint256 orderId) external view returns (bool);
    function getChallengeWindow() external view returns (uint256);
}

// ============ Marketplace Interfaces ============

interface ISubscriptionManager {
    enum SubscriptionTier { FREE, STUDY, STUDY_PLUS, EXPERT }
    
    struct Subscription {
        address user;
        SubscriptionTier tier;
        uint256 startTime;
        uint256 endTime;
        uint256 creditsRemaining;
        uint256 creditsUsedThisMonth;
        uint256 lastCreditReset;
    }
    
    struct TierConfig {
        uint256 pricePerMonth;
        uint256 monthlyCredits;
        bool hasSteps;
        bool hasPremiumAccess;
        bool hasRefundGuarantee;
    }
    
    function subscribe(SubscriptionTier tier) external;
    function renewSubscription() external;
    function cancelSubscription() external;
    function useCredit(address user) external returns (bool);
    function recordSolverUsage(address solver) external;
    function getUserSubscription(address user) external view returns (Subscription memory);
    function hasPremiumAccess(address user) external view returns (bool);
    function hasRefundGuarantee(address user) external view returns (bool);
    function getCreditsRemaining(address user) external view returns (uint256);
}

interface IBotRegistry {
    struct BotInfo {
        address owner;
        string name;
        string description;
        string webhookUrl;
        bool isPremium;
        uint8[] supportedTypes;
        bool isActive;
        uint256 totalSolved;
        uint256 totalRating;
        uint256 ratingCount;
        uint256 monthlyUsage;
        uint256 registeredAt;
    }
    
    function registerBot(string calldata name, string calldata description, string calldata webhookUrl, bool isPremium, uint8[] calldata supportedTypes) external;
    function updateBot(string calldata name, string calldata description, string calldata webhookUrl, uint8[] calldata supportedTypes) external;
    function setBotStatus(bool isActive) external;
    function getBotInfo(address botAddress) external view returns (BotInfo memory);
    function incrementUsage(address botAddress) external;
    function recordSolution(address botAddress, uint256 orderId) external;
    function getTopBots(uint256 limit) external view returns (address[] memory);
    function getEligibleSolvers(uint8 problemType) external view returns (address[] memory);
    function getAverageRating(address botAddress) external view returns (uint256);
    function platformBot() external view returns (address);
}

interface IRatingSystem {
    struct Review {
        address user;
        address bot;
        uint256 orderId;
        uint8 rating;
        string comment;
        uint256 timestamp;
        bool isVerified;
    }
    
    function recordOrderSolver(uint256 orderId, address bot) external;
    function submitReview(uint256 orderId, uint8 rating, string calldata comment) external returns (uint256);
    function submitGeneralReview(address bot, uint8 rating, string calldata comment) external returns (uint256);
    function getBotReviews(address bot, uint256 offset, uint256 limit) external view returns (Review[] memory);
    function getBotAverageRating(address bot) external view returns (uint256);
    function getBotReviewCount(address bot) external view returns (uint256);
}

// ============ Core Interface ============

interface ICalcSolverCore {
    function postProblem(
        bytes32 problemHash,
        ProblemType problemType,
        TimeTier timeTier
    ) external returns (uint256 orderId);
    
    function acceptOrder(uint256 orderId) external;
    function commitSolution(uint256 orderId, bytes32 commitHash) external;
    function revealSolution(uint256 orderId, string calldata solution, bytes32 salt) external;
    function claimTimeout(uint256 orderId) external;
    function submitChallenge(uint256 orderId, string calldata reason) external;
    function cancelOrder(uint256 orderId) external;
    function resolveChallenge(uint256 orderId, bool challengerWon) external;
    
    // View functions
    function getOrder(uint256 orderId) external view returns (ProblemOrder memory);
    function getSolution(uint256 orderId) external view returns (SolutionSubmission memory);
    function getChallenge(uint256 orderId) external view returns (Challenge memory);
}
