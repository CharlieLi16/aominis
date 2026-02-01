// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ICalcSolver.sol";

/**
 * @title BotRegistry
 * @notice Manages Bot registration, status, and usage tracking for the Solver Marketplace
 * @dev Bots can register, set their capabilities, and track usage for revenue sharing
 */
contract BotRegistry {
    // ============ Structs ============
    
    struct BotInfo {
        address owner;              // Solver/operator address
        string name;                // Bot display name
        string description;         // Bot description
        string webhookUrl;          // Webhook URL for push notifications (optional)
        bool isPremium;             // Premium bot (requires Study+ subscription)
        uint8[] supportedTypes;     // Supported problem types (0-4)
        bool isActive;              // Currently online/accepting problems
        uint256 totalSolved;        // Total problems solved
        uint256 totalRating;        // Sum of all ratings (for averaging)
        uint256 ratingCount;        // Number of ratings received
        uint256 monthlyUsage;       // Usage count this month
        uint256 registeredAt;       // Registration timestamp
    }
    
    // ============ State Variables ============
    
    address public owner;
    address public core;
    address public subscriptionManager;
    
    // Bot registry
    mapping(address => BotInfo) public bots;
    address[] public registeredBots;
    mapping(address => bool) public isRegistered;
    
    // Platform bot (owned by protocol)
    address public platformBot;
    
    // Monthly tracking
    uint256 public currentMonthStart;
    uint256 public totalMonthlyUsage;
    
    // ============ Events ============
    
    event BotRegistered(
        address indexed botAddress,
        address indexed owner,
        string name,
        bool isPremium
    );
    
    event BotUpdated(
        address indexed botAddress,
        string name,
        bool isActive
    );
    
    event BotStatusChanged(
        address indexed botAddress,
        bool isActive
    );
    
    event BotUsageRecorded(
        address indexed botAddress,
        uint256 monthlyUsage
    );
    
    event BotRated(
        address indexed botAddress,
        address indexed user,
        uint8 rating
    );
    
    event ProblemSolved(
        address indexed botAddress,
        uint256 orderId
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
    
    modifier onlyBotOwner(address botAddress) {
        require(bots[botAddress].owner == msg.sender, "Not bot owner");
        _;
    }
    
    // ============ Constructor ============
    
    constructor() {
        owner = msg.sender;
        currentMonthStart = block.timestamp;
    }
    
    // ============ Admin Functions ============
    
    function setCore(address _core) external onlyOwner {
        require(_core != address(0), "Invalid core");
        core = _core;
    }
    
    function setSubscriptionManager(address _manager) external onlyOwner {
        require(_manager != address(0), "Invalid manager");
        subscriptionManager = _manager;
    }
    
    function setPlatformBot(address _bot) external onlyOwner {
        platformBot = _bot;
    }
    
    // ============ Bot Registration ============
    
    /**
     * @notice Register a new bot
     * @param name Bot display name
     * @param description Bot description
     * @param webhookUrl Webhook URL for receiving problems (optional)
     * @param isPremium Whether this is a premium bot
     * @param supportedTypes Array of supported problem types
     */
    function registerBot(
        string calldata name,
        string calldata description,
        string calldata webhookUrl,
        bool isPremium,
        uint8[] calldata supportedTypes
    ) external {
        require(!isRegistered[msg.sender], "Already registered");
        require(bytes(name).length > 0, "Name required");
        require(supportedTypes.length > 0, "Must support at least one type");
        
        // Validate problem types (0-4)
        for (uint i = 0; i < supportedTypes.length; i++) {
            require(supportedTypes[i] <= 4, "Invalid problem type");
        }
        
        bots[msg.sender] = BotInfo({
            owner: msg.sender,
            name: name,
            description: description,
            webhookUrl: webhookUrl,
            isPremium: isPremium,
            supportedTypes: supportedTypes,
            isActive: true,
            totalSolved: 0,
            totalRating: 0,
            ratingCount: 0,
            monthlyUsage: 0,
            registeredAt: block.timestamp
        });
        
        registeredBots.push(msg.sender);
        isRegistered[msg.sender] = true;
        
        emit BotRegistered(msg.sender, msg.sender, name, isPremium);
    }
    
    /**
     * @notice Update bot information
     * @param name New bot name
     * @param description New description
     * @param webhookUrl New webhook URL
     * @param supportedTypes New supported types
     */
    function updateBot(
        string calldata name,
        string calldata description,
        string calldata webhookUrl,
        uint8[] calldata supportedTypes
    ) external onlyBotOwner(msg.sender) {
        require(isRegistered[msg.sender], "Not registered");
        
        BotInfo storage bot = bots[msg.sender];
        bot.name = name;
        bot.description = description;
        bot.webhookUrl = webhookUrl;
        bot.supportedTypes = supportedTypes;
        
        emit BotUpdated(msg.sender, name, bot.isActive);
    }
    
    /**
     * @notice Set bot active/inactive status
     * @param isActive Whether the bot is accepting problems
     */
    function setBotStatus(bool isActive) external onlyBotOwner(msg.sender) {
        require(isRegistered[msg.sender], "Not registered");
        bots[msg.sender].isActive = isActive;
        emit BotStatusChanged(msg.sender, isActive);
    }
    
    /**
     * @notice Set bot as premium or standard
     * @param isPremium Whether the bot is premium
     */
    function setPremiumStatus(bool isPremium) external onlyBotOwner(msg.sender) {
        require(isRegistered[msg.sender], "Not registered");
        bots[msg.sender].isPremium = isPremium;
    }
    
    // ============ Usage Tracking ============
    
    /**
     * @notice Increment bot usage count (called when bot solves a problem)
     * @param botAddress The bot address
     */
    function incrementUsage(address botAddress) external onlyCore {
        require(isRegistered[botAddress] || botAddress == platformBot, "Bot not registered");
        
        // Reset monthly counters if new month
        if (block.timestamp > currentMonthStart + 30 days) {
            _resetMonthlyCounters();
        }
        
        bots[botAddress].monthlyUsage++;
        totalMonthlyUsage++;
        
        emit BotUsageRecorded(botAddress, bots[botAddress].monthlyUsage);
    }
    
    /**
     * @notice Record a successful solution
     * @param botAddress The bot that solved
     * @param orderId The order ID
     */
    function recordSolution(address botAddress, uint256 orderId) external onlyCore {
        require(isRegistered[botAddress] || botAddress == platformBot, "Bot not registered");
        bots[botAddress].totalSolved++;
        emit ProblemSolved(botAddress, orderId);
    }
    
    /**
     * @notice Submit a rating for a bot
     * @param botAddress The bot to rate
     * @param rating Rating from 1-5
     */
    function rateBot(address botAddress, uint8 rating) external {
        require(isRegistered[botAddress], "Bot not registered");
        require(rating >= 1 && rating <= 5, "Rating must be 1-5");
        
        BotInfo storage bot = bots[botAddress];
        bot.totalRating += rating;
        bot.ratingCount++;
        
        emit BotRated(botAddress, msg.sender, rating);
    }
    
    // ============ Internal Functions ============
    
    function _resetMonthlyCounters() internal {
        for (uint i = 0; i < registeredBots.length; i++) {
            bots[registeredBots[i]].monthlyUsage = 0;
        }
        totalMonthlyUsage = 0;
        currentMonthStart = block.timestamp;
    }
    
    // ============ View Functions ============
    
    function getBotInfo(address botAddress) external view returns (BotInfo memory) {
        return bots[botAddress];
    }
    
    function getBotCount() external view returns (uint256) {
        return registeredBots.length;
    }
    
    function getAverageRating(address botAddress) external view returns (uint256) {
        BotInfo memory bot = bots[botAddress];
        if (bot.ratingCount == 0) return 0;
        return (bot.totalRating * 100) / bot.ratingCount; // Returns rating * 100 (e.g., 450 = 4.5 stars)
    }
    
    /**
     * @notice Get top bots by rating
     * @param limit Maximum number of bots to return
     * @return topBots Array of top bot addresses
     */
    function getTopBots(uint256 limit) external view returns (address[] memory) {
        uint256 count = registeredBots.length;
        if (limit > count) limit = count;
        
        // Simple selection (in production, use more efficient sorting)
        address[] memory result = new address[](limit);
        uint256[] memory ratings = new uint256[](count);
        
        // Calculate ratings
        for (uint i = 0; i < count; i++) {
            BotInfo memory bot = bots[registeredBots[i]];
            if (bot.ratingCount > 0 && bot.isActive) {
                ratings[i] = (bot.totalRating * 1000) / bot.ratingCount;
            }
        }
        
        // Select top (simple O(n*limit) selection)
        bool[] memory selected = new bool[](count);
        for (uint j = 0; j < limit; j++) {
            uint256 maxRating = 0;
            uint256 maxIndex = 0;
            for (uint i = 0; i < count; i++) {
                if (!selected[i] && ratings[i] > maxRating) {
                    maxRating = ratings[i];
                    maxIndex = i;
                }
            }
            if (maxRating > 0) {
                result[j] = registeredBots[maxIndex];
                selected[maxIndex] = true;
            }
        }
        
        return result;
    }
    
    /**
     * @notice Get bots that support a specific problem type
     * @param problemType The problem type (0-4)
     * @return eligibleBots Array of bot addresses
     */
    function getBotsByType(uint8 problemType) external view returns (address[] memory) {
        require(problemType <= 4, "Invalid type");
        
        // Count eligible bots first
        uint256 count = 0;
        for (uint i = 0; i < registeredBots.length; i++) {
            BotInfo memory bot = bots[registeredBots[i]];
            if (bot.isActive && _supportsType(bot.supportedTypes, problemType)) {
                count++;
            }
        }
        
        // Build result array
        address[] memory result = new address[](count);
        uint256 idx = 0;
        for (uint i = 0; i < registeredBots.length; i++) {
            BotInfo memory bot = bots[registeredBots[i]];
            if (bot.isActive && _supportsType(bot.supportedTypes, problemType)) {
                result[idx++] = registeredBots[i];
            }
        }
        
        return result;
    }
    
    function _supportsType(uint8[] memory types, uint8 target) internal pure returns (bool) {
        for (uint i = 0; i < types.length; i++) {
            if (types[i] == target) return true;
        }
        return false;
    }
    
    /**
     * @notice Get active bots for problem pool assignment
     * @param problemType The problem type
     * @return eligibleBots Array of active bot addresses
     */
    function getEligibleSolvers(uint8 problemType) external view returns (address[] memory) {
        // Count eligible
        uint256 count = 0;
        for (uint i = 0; i < registeredBots.length; i++) {
            BotInfo memory bot = bots[registeredBots[i]];
            if (bot.isActive && !bot.isPremium && _supportsType(bot.supportedTypes, problemType)) {
                count++;
            }
        }
        
        // Add platform bot if exists
        if (platformBot != address(0)) count++;
        
        // Build result
        address[] memory result = new address[](count);
        uint256 idx = 0;
        
        if (platformBot != address(0)) {
            result[idx++] = platformBot;
        }
        
        for (uint i = 0; i < registeredBots.length; i++) {
            BotInfo memory bot = bots[registeredBots[i]];
            if (bot.isActive && !bot.isPremium && _supportsType(bot.supportedTypes, problemType)) {
                result[idx++] = registeredBots[i];
            }
        }
        
        return result;
    }
    
    /**
     * @notice Calculate solver's share of monthly revenue
     * @param botAddress The bot address
     * @return share Percentage share in basis points (10000 = 100%)
     */
    function calculateSolverShareBps(address botAddress) external view returns (uint256) {
        if (totalMonthlyUsage == 0) return 0;
        
        BotInfo memory bot = bots[botAddress];
        
        // Base share from usage
        uint256 usageShare = (bot.monthlyUsage * 10000) / totalMonthlyUsage;
        
        // Rating bonus (up to 20% extra for 5-star bots)
        uint256 ratingBonus = 0;
        if (bot.ratingCount > 0) {
            uint256 avgRating = (bot.totalRating * 100) / bot.ratingCount; // 100-500
            ratingBonus = (usageShare * (avgRating - 100)) / 2000; // Max 20% bonus
        }
        
        return usageShare + ratingBonus;
    }
    
    /**
     * @notice Get all registered bot addresses
     */
    function getAllBots() external view returns (address[] memory) {
        return registeredBots;
    }
}
