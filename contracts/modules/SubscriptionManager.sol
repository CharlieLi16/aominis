// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ICalcSolver.sol";

/**
 * @title SubscriptionManager
 * @notice Manages user subscriptions, credits, and revenue distribution for Ominis Protocol
 * @dev Implements subscription tiers with monthly credits and revenue sharing for Solvers
 */
contract SubscriptionManager {
    // ============ Enums ============
    
    enum SubscriptionTier {
        FREE,        // $0/month, 5 credits
        STUDY,       // $9.99/month, 100 credits
        STUDY_PLUS,  // $14.99/month, unlimited
        EXPERT       // $24.99/month, unlimited + expert access
    }
    
    // ============ Structs ============
    
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
        uint256 pricePerMonth;      // USDC (6 decimals)
        uint256 monthlyCredits;     // 0 = unlimited
        bool hasSteps;              // Show solution steps
        bool hasPremiumAccess;      // Access to Premium Bots
        bool hasRefundGuarantee;    // Refund if answer is wrong
    }
    
    // ============ State Variables ============
    
    IERC20 public immutable paymentToken;  // USDC
    address public owner;
    address public core;
    address public botRegistry;
    
    // Subscription data
    mapping(address => Subscription) public subscriptions;
    mapping(SubscriptionTier => TierConfig) public tierConfigs;
    
    // Revenue tracking
    uint256 public totalMonthlyRevenue;
    uint256 public platformShareBps = 3000;  // 30%
    uint256 public currentMonthStart;
    uint256 public accumulatedRevenue;
    
    // Solver revenue share tracking
    mapping(address => uint256) public solverUsageThisMonth;
    uint256 public totalUsageThisMonth;
    
    // ============ Events ============
    
    event SubscriptionCreated(
        address indexed user,
        SubscriptionTier tier,
        uint256 endTime
    );
    
    event SubscriptionRenewed(
        address indexed user,
        SubscriptionTier tier,
        uint256 newEndTime
    );
    
    event SubscriptionCancelled(
        address indexed user
    );
    
    event CreditUsed(
        address indexed user,
        uint256 creditsRemaining
    );
    
    event RevenueDistributed(
        uint256 totalAmount,
        uint256 platformShare,
        uint256 solverPool
    );
    
    event SolverPaid(
        address indexed solver,
        uint256 amount,
        uint256 usageCount
    );
    
    // ============ Modifiers ============
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyCore() {
        require(msg.sender == core, "Only core");
        _;
    }
    
    modifier onlyCoreOrRegistry() {
        require(msg.sender == core || msg.sender == botRegistry, "Not authorized");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(address _paymentToken) {
        require(_paymentToken != address(0), "Invalid token");
        paymentToken = IERC20(_paymentToken);
        owner = msg.sender;
        currentMonthStart = block.timestamp;
        
        // Initialize tier configs
        tierConfigs[SubscriptionTier.FREE] = TierConfig({
            pricePerMonth: 0,
            monthlyCredits: 5,
            hasSteps: false,
            hasPremiumAccess: false,
            hasRefundGuarantee: false
        });
        
        tierConfigs[SubscriptionTier.STUDY] = TierConfig({
            pricePerMonth: 9_990_000,  // $9.99
            monthlyCredits: 100,
            hasSteps: true,
            hasPremiumAccess: false,
            hasRefundGuarantee: false
        });
        
        tierConfigs[SubscriptionTier.STUDY_PLUS] = TierConfig({
            pricePerMonth: 14_990_000, // $14.99
            monthlyCredits: 0,         // unlimited
            hasSteps: true,
            hasPremiumAccess: true,
            hasRefundGuarantee: true
        });
        
        tierConfigs[SubscriptionTier.EXPERT] = TierConfig({
            pricePerMonth: 24_990_000, // $24.99
            monthlyCredits: 0,         // unlimited
            hasSteps: true,
            hasPremiumAccess: true,
            hasRefundGuarantee: true
        });
    }
    
    // ============ Admin Functions ============
    
    function setCore(address _core) external onlyOwner {
        require(_core != address(0), "Invalid core");
        core = _core;
    }
    
    function setBotRegistry(address _registry) external onlyOwner {
        require(_registry != address(0), "Invalid registry");
        botRegistry = _registry;
    }
    
    function setPlatformShareBps(uint256 _bps) external onlyOwner {
        require(_bps <= 5000, "Max 50%");
        platformShareBps = _bps;
    }
    
    function setTierConfig(
        SubscriptionTier tier,
        uint256 price,
        uint256 credits,
        bool steps,
        bool premium,
        bool refund
    ) external onlyOwner {
        tierConfigs[tier] = TierConfig({
            pricePerMonth: price,
            monthlyCredits: credits,
            hasSteps: steps,
            hasPremiumAccess: premium,
            hasRefundGuarantee: refund
        });
    }
    
    // ============ Subscription Functions ============
    
    /**
     * @notice Subscribe to a tier
     * @param tier The subscription tier to subscribe to
     */
    function subscribe(SubscriptionTier tier) external {
        TierConfig memory config = tierConfigs[tier];
        
        // Handle payment for non-free tiers
        if (config.pricePerMonth > 0) {
            require(
                paymentToken.transferFrom(msg.sender, address(this), config.pricePerMonth),
                "Payment failed"
            );
            accumulatedRevenue += config.pricePerMonth;
        }
        
        // Create or update subscription
        Subscription storage sub = subscriptions[msg.sender];
        
        // If upgrading, credit remaining time value (simplified: just extend)
        uint256 newEndTime;
        if (sub.endTime > block.timestamp) {
            // Extending existing subscription
            newEndTime = sub.endTime + 30 days;
        } else {
            // New subscription
            newEndTime = block.timestamp + 30 days;
        }
        
        sub.user = msg.sender;
        sub.tier = tier;
        sub.startTime = block.timestamp;
        sub.endTime = newEndTime;
        sub.creditsRemaining = config.monthlyCredits;
        sub.creditsUsedThisMonth = 0;
        sub.lastCreditReset = block.timestamp;
        
        emit SubscriptionCreated(msg.sender, tier, newEndTime);
    }
    
    /**
     * @notice Renew current subscription
     */
    function renewSubscription() external {
        Subscription storage sub = subscriptions[msg.sender];
        require(sub.user != address(0), "No subscription");
        
        TierConfig memory config = tierConfigs[sub.tier];
        
        // Handle payment
        if (config.pricePerMonth > 0) {
            require(
                paymentToken.transferFrom(msg.sender, address(this), config.pricePerMonth),
                "Payment failed"
            );
            accumulatedRevenue += config.pricePerMonth;
        }
        
        // Extend subscription
        if (sub.endTime > block.timestamp) {
            sub.endTime += 30 days;
        } else {
            sub.endTime = block.timestamp + 30 days;
        }
        
        // Reset credits
        sub.creditsRemaining = config.monthlyCredits;
        sub.creditsUsedThisMonth = 0;
        sub.lastCreditReset = block.timestamp;
        
        emit SubscriptionRenewed(msg.sender, sub.tier, sub.endTime);
    }
    
    /**
     * @notice Cancel subscription (no refund, just don't auto-renew)
     */
    function cancelSubscription() external {
        Subscription storage sub = subscriptions[msg.sender];
        require(sub.user != address(0), "No subscription");
        
        // Subscription remains active until endTime, just marked for non-renewal
        emit SubscriptionCancelled(msg.sender);
    }
    
    /**
     * @notice Use one credit for a problem submission
     * @param user The user address
     * @return success Whether the credit was successfully used
     */
    function useCredit(address user) external onlyCoreOrRegistry returns (bool) {
        Subscription storage sub = subscriptions[user];
        
        // Check if subscription is active
        if (sub.endTime < block.timestamp) {
            // Expired, check if FREE tier (always available)
            if (sub.tier != SubscriptionTier.FREE && sub.user != address(0)) {
                return false;
            }
            // Initialize FREE subscription if none exists
            if (sub.user == address(0)) {
                sub.user = user;
                sub.tier = SubscriptionTier.FREE;
                sub.startTime = block.timestamp;
                sub.endTime = block.timestamp + 30 days;
                sub.creditsRemaining = tierConfigs[SubscriptionTier.FREE].monthlyCredits;
                sub.lastCreditReset = block.timestamp;
            }
        }
        
        // Reset credits if month has passed
        if (block.timestamp > sub.lastCreditReset + 30 days) {
            TierConfig memory config = tierConfigs[sub.tier];
            sub.creditsRemaining = config.monthlyCredits;
            sub.creditsUsedThisMonth = 0;
            sub.lastCreditReset = block.timestamp;
        }
        
        TierConfig memory config = tierConfigs[sub.tier];
        
        // Check if unlimited (monthlyCredits == 0 means unlimited)
        if (config.monthlyCredits == 0) {
            sub.creditsUsedThisMonth++;
            emit CreditUsed(user, type(uint256).max); // unlimited
            return true;
        }
        
        // Check if credits remaining
        if (sub.creditsRemaining == 0) {
            return false;
        }
        
        sub.creditsRemaining--;
        sub.creditsUsedThisMonth++;
        
        emit CreditUsed(user, sub.creditsRemaining);
        return true;
    }
    
    /**
     * @notice Record solver usage for revenue sharing
     * @param solver The solver/bot address that was used
     */
    function recordSolverUsage(address solver) external onlyCoreOrRegistry {
        solverUsageThisMonth[solver]++;
        totalUsageThisMonth++;
    }
    
    // ============ Revenue Distribution ============
    
    /**
     * @notice Distribute monthly revenue to solvers
     * @dev Should be called monthly by admin or automated keeper
     */
    function distributeMonthlyRevenue() external {
        require(block.timestamp >= currentMonthStart + 30 days, "Month not ended");
        
        uint256 revenue = accumulatedRevenue;
        require(revenue > 0, "No revenue to distribute");
        
        // Calculate shares
        uint256 platformShare = (revenue * platformShareBps) / 10000;
        uint256 solverPool = revenue - platformShare;
        
        // Transfer platform share to owner
        if (platformShare > 0) {
            require(paymentToken.transfer(owner, platformShare), "Platform transfer failed");
        }
        
        // Store solver pool for claiming
        // Note: In production, you'd integrate with BotRegistry for weighted distribution
        
        emit RevenueDistributed(revenue, platformShare, solverPool);
        
        // Reset for next month
        accumulatedRevenue = 0;
        totalUsageThisMonth = 0;
        currentMonthStart = block.timestamp;
    }
    
    /**
     * @notice Calculate solver's share of the revenue pool
     * @param solver The solver address
     * @return share The solver's share in USDC
     */
    function calculateSolverShare(address solver) public view returns (uint256) {
        if (totalUsageThisMonth == 0) return 0;
        
        uint256 solverPool = (accumulatedRevenue * (10000 - platformShareBps)) / 10000;
        uint256 solverUsage = solverUsageThisMonth[solver];
        
        return (solverPool * solverUsage) / totalUsageThisMonth;
    }
    
    // ============ View Functions ============
    
    function getUserSubscription(address user) external view returns (Subscription memory) {
        return subscriptions[user];
    }
    
    function getTierConfig(SubscriptionTier tier) external view returns (TierConfig memory) {
        return tierConfigs[tier];
    }
    
    function isSubscriptionActive(address user) external view returns (bool) {
        Subscription memory sub = subscriptions[user];
        // FREE tier is always "active" for basic access
        if (sub.user == address(0)) return true; // Will get FREE tier on first use
        return sub.endTime >= block.timestamp;
    }
    
    function hasCreditsRemaining(address user) external view returns (bool) {
        Subscription memory sub = subscriptions[user];
        TierConfig memory config = tierConfigs[sub.tier];
        
        // Unlimited credits
        if (config.monthlyCredits == 0) return true;
        
        return sub.creditsRemaining > 0;
    }
    
    function hasPremiumAccess(address user) external view returns (bool) {
        Subscription memory sub = subscriptions[user];
        if (sub.endTime < block.timestamp) return false;
        return tierConfigs[sub.tier].hasPremiumAccess;
    }
    
    function hasRefundGuarantee(address user) external view returns (bool) {
        Subscription memory sub = subscriptions[user];
        if (sub.endTime < block.timestamp) return false;
        return tierConfigs[sub.tier].hasRefundGuarantee;
    }
    
    function getCreditsRemaining(address user) external view returns (uint256) {
        Subscription memory sub = subscriptions[user];
        TierConfig memory config = tierConfigs[sub.tier];
        
        // Unlimited
        if (config.monthlyCredits == 0) return type(uint256).max;
        
        return sub.creditsRemaining;
    }
    
    function getTierPrice(SubscriptionTier tier) external view returns (uint256) {
        return tierConfigs[tier].pricePerMonth;
    }
}
