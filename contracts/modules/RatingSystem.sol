// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RatingSystem
 * @notice Manages reviews and ratings for Bots in the Solver Marketplace
 * @dev Users can submit reviews after receiving solutions, reviews are stored on-chain
 */
contract RatingSystem {
    // ============ Structs ============
    
    struct Review {
        address user;           // Reviewer address
        address bot;            // Bot being reviewed
        uint256 orderId;        // Associated order ID
        uint8 rating;           // 1-5 stars
        string comment;         // Review text
        uint256 timestamp;      // When review was submitted
        bool isVerified;        // Whether user actually used the bot for this order
    }
    
    struct BotRatingSummary {
        uint256 totalRating;    // Sum of all ratings
        uint256 reviewCount;    // Number of reviews
        uint256 fiveStarCount;  // Count of 5-star reviews
        uint256 fourStarCount;  // Count of 4-star reviews
        uint256 threeStarCount; // Count of 3-star reviews
        uint256 twoStarCount;   // Count of 2-star reviews
        uint256 oneStarCount;   // Count of 1-star reviews
    }
    
    // ============ State Variables ============
    
    address public owner;
    address public core;
    address public botRegistry;
    
    // Reviews storage
    mapping(uint256 => Review) public reviews;  // reviewId => Review
    uint256 public reviewCount;
    
    // Bot reviews mapping
    mapping(address => uint256[]) public botReviews;  // bot => reviewIds
    mapping(address => BotRatingSummary) public botSummaries;
    
    // User reviews mapping
    mapping(address => uint256[]) public userReviews;  // user => reviewIds
    
    // Prevent duplicate reviews for same order
    mapping(uint256 => bool) public orderReviewed;  // orderId => hasReview
    
    // Order to bot mapping (set by core when problem is solved)
    mapping(uint256 => address) public orderSolver;  // orderId => bot address
    
    // ============ Events ============
    
    event ReviewSubmitted(
        uint256 indexed reviewId,
        address indexed user,
        address indexed bot,
        uint256 orderId,
        uint8 rating
    );
    
    event ReviewUpdated(
        uint256 indexed reviewId,
        uint8 newRating,
        string newComment
    );
    
    event ReviewVerified(
        uint256 indexed reviewId,
        bool isVerified
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
    
    // ============ Constructor ============
    
    constructor() {
        owner = msg.sender;
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
    
    // ============ Core Functions ============
    
    /**
     * @notice Record which bot solved an order (called by Core)
     * @param orderId The order ID
     * @param bot The bot that solved it
     */
    function recordOrderSolver(uint256 orderId, address bot) external onlyCore {
        orderSolver[orderId] = bot;
    }
    
    // ============ Review Functions ============
    
    /**
     * @notice Submit a review for a bot
     * @param orderId The order ID this review is for
     * @param rating Rating from 1-5
     * @param comment Review comment
     */
    function submitReview(
        uint256 orderId,
        uint8 rating,
        string calldata comment
    ) external returns (uint256 reviewId) {
        require(rating >= 1 && rating <= 5, "Rating must be 1-5");
        require(!orderReviewed[orderId], "Order already reviewed");
        require(bytes(comment).length <= 1000, "Comment too long");
        
        address bot = orderSolver[orderId];
        require(bot != address(0), "Order not found or not solved");
        
        reviewId = reviewCount++;
        
        reviews[reviewId] = Review({
            user: msg.sender,
            bot: bot,
            orderId: orderId,
            rating: rating,
            comment: comment,
            timestamp: block.timestamp,
            isVerified: true  // Verified because we check orderSolver
        });
        
        // Update mappings
        botReviews[bot].push(reviewId);
        userReviews[msg.sender].push(reviewId);
        orderReviewed[orderId] = true;
        
        // Update bot summary
        _updateBotSummary(bot, rating, true);
        
        emit ReviewSubmitted(reviewId, msg.sender, bot, orderId, rating);
    }
    
    /**
     * @notice Submit a general review (without order verification)
     * @param bot The bot to review
     * @param rating Rating from 1-5
     * @param comment Review comment
     */
    function submitGeneralReview(
        address bot,
        uint8 rating,
        string calldata comment
    ) external returns (uint256 reviewId) {
        require(rating >= 1 && rating <= 5, "Rating must be 1-5");
        require(bot != address(0), "Invalid bot");
        require(bytes(comment).length <= 1000, "Comment too long");
        
        reviewId = reviewCount++;
        
        reviews[reviewId] = Review({
            user: msg.sender,
            bot: bot,
            orderId: 0,  // No specific order
            rating: rating,
            comment: comment,
            timestamp: block.timestamp,
            isVerified: false  // Not verified
        });
        
        // Update mappings
        botReviews[bot].push(reviewId);
        userReviews[msg.sender].push(reviewId);
        
        // Update bot summary (unverified reviews count less)
        _updateBotSummary(bot, rating, false);
        
        emit ReviewSubmitted(reviewId, msg.sender, bot, 0, rating);
    }
    
    /**
     * @notice Update an existing review
     * @param reviewId The review to update
     * @param newRating New rating
     * @param newComment New comment
     */
    function updateReview(
        uint256 reviewId,
        uint8 newRating,
        string calldata newComment
    ) external {
        require(reviewId < reviewCount, "Review not found");
        Review storage review = reviews[reviewId];
        require(review.user == msg.sender, "Not review owner");
        require(newRating >= 1 && newRating <= 5, "Rating must be 1-5");
        
        // Update bot summary (remove old, add new)
        _updateBotSummaryForChange(review.bot, review.rating, newRating);
        
        review.rating = newRating;
        review.comment = newComment;
        review.timestamp = block.timestamp;
        
        emit ReviewUpdated(reviewId, newRating, newComment);
    }
    
    // ============ Internal Functions ============
    
    function _updateBotSummary(address bot, uint8 rating, bool isVerified) internal {
        BotRatingSummary storage summary = botSummaries[bot];
        
        // Verified reviews count as 1.0, unverified as 0.5
        uint256 weight = isVerified ? 10 : 5;
        summary.totalRating += rating * weight;
        summary.reviewCount += weight;
        
        // Update star counts
        if (rating == 5) summary.fiveStarCount++;
        else if (rating == 4) summary.fourStarCount++;
        else if (rating == 3) summary.threeStarCount++;
        else if (rating == 2) summary.twoStarCount++;
        else if (rating == 1) summary.oneStarCount++;
    }
    
    function _updateBotSummaryForChange(address bot, uint8 oldRating, uint8 newRating) internal {
        BotRatingSummary storage summary = botSummaries[bot];
        
        // Remove old rating contribution (assume verified for simplicity)
        summary.totalRating = summary.totalRating - (oldRating * 10) + (newRating * 10);
        
        // Update star counts
        if (oldRating == 5) summary.fiveStarCount--;
        else if (oldRating == 4) summary.fourStarCount--;
        else if (oldRating == 3) summary.threeStarCount--;
        else if (oldRating == 2) summary.twoStarCount--;
        else if (oldRating == 1) summary.oneStarCount--;
        
        if (newRating == 5) summary.fiveStarCount++;
        else if (newRating == 4) summary.fourStarCount++;
        else if (newRating == 3) summary.threeStarCount++;
        else if (newRating == 2) summary.twoStarCount++;
        else if (newRating == 1) summary.oneStarCount++;
    }
    
    // ============ View Functions ============
    
    /**
     * @notice Get a review by ID
     * @param reviewId The review ID
     */
    function getReview(uint256 reviewId) external view returns (Review memory) {
        require(reviewId < reviewCount, "Review not found");
        return reviews[reviewId];
    }
    
    /**
     * @notice Get reviews for a bot (paginated)
     * @param bot The bot address
     * @param offset Starting index
     * @param limit Maximum reviews to return
     */
    function getBotReviews(
        address bot,
        uint256 offset,
        uint256 limit
    ) external view returns (Review[] memory) {
        uint256[] memory reviewIds = botReviews[bot];
        uint256 total = reviewIds.length;
        
        if (offset >= total) {
            return new Review[](0);
        }
        
        uint256 end = offset + limit;
        if (end > total) end = total;
        
        uint256 resultLength = end - offset;
        Review[] memory result = new Review[](resultLength);
        
        for (uint256 i = 0; i < resultLength; i++) {
            result[i] = reviews[reviewIds[offset + i]];
        }
        
        return result;
    }
    
    /**
     * @notice Get bot's average rating
     * @param bot The bot address
     * @return Average rating * 100 (e.g., 450 = 4.5 stars)
     */
    function getBotAverageRating(address bot) external view returns (uint256) {
        BotRatingSummary memory summary = botSummaries[bot];
        if (summary.reviewCount == 0) return 0;
        return (summary.totalRating * 100) / summary.reviewCount;
    }
    
    /**
     * @notice Get bot's rating summary
     * @param bot The bot address
     */
    function getBotRatingSummary(address bot) external view returns (BotRatingSummary memory) {
        return botSummaries[bot];
    }
    
    /**
     * @notice Get total review count for a bot
     * @param bot The bot address
     */
    function getBotReviewCount(address bot) external view returns (uint256) {
        return botReviews[bot].length;
    }
    
    /**
     * @notice Get user's submitted reviews
     * @param user The user address
     */
    function getUserReviews(address user) external view returns (uint256[] memory) {
        return userReviews[user];
    }
    
    /**
     * @notice Check if an order has been reviewed
     * @param orderId The order ID
     */
    function hasOrderBeenReviewed(uint256 orderId) external view returns (bool) {
        return orderReviewed[orderId];
    }
}
