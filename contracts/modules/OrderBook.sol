// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ICalcSolver.sol";

/**
 * @title OrderBook
 * @notice Manages problem orders and pricing for Ominis Protocol
 */
contract OrderBook is IOrderBook {
    // ============ State Variables ============
    
    address public core;
    address public owner;
    
    uint256 private _orderCount;
    mapping(uint256 => ProblemOrder) private orders;
    
    // Pricing configuration per tier
    mapping(TimeTier => PricingConfig) public tierPricing;
    mapping(TimeTier => uint256) public tierDurations;
    mapping(TimeTier => uint256) public tierPrices; // Cached prices
    
    // Track open orders for efficient listing
    uint256[] private openOrderIds;
    mapping(uint256 => uint256) private openOrderIndex; // orderId => index in openOrderIds
    
    // ============ Modifiers ============
    
    modifier onlyCore() {
        require(msg.sender == core, "Only core");
        _;
    }
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(address _core) {
        require(_core != address(0), "Invalid core");
        core = _core;
        owner = msg.sender;
        
        // Initialize tier pricing (USDC has 6 decimals)
        // T2min: Fast, premium pricing
        tierPricing[TimeTier.T2min] = PricingConfig({
            baseFee: 1_500_000,      // $1.50 base
            gasEstimate: 150_000,    // ~150k gas for full flow
            timePremiumBps: 500      // 5% time premium
        });
        tierDurations[TimeTier.T2min] = 2 minutes;
        
        // T5min: Standard fast
        tierPricing[TimeTier.T5min] = PricingConfig({
            baseFee: 1_000_000,      // $1.00 base
            gasEstimate: 150_000,
            timePremiumBps: 300      // 3% time premium
        });
        tierDurations[TimeTier.T5min] = 5 minutes;
        
        // T15min: Normal
        tierPricing[TimeTier.T15min] = PricingConfig({
            baseFee: 750_000,        // $0.75 base
            gasEstimate: 150_000,
            timePremiumBps: 150      // 1.5% time premium
        });
        tierDurations[TimeTier.T15min] = 15 minutes;
        
        // T1hour: Economy
        tierPricing[TimeTier.T1hour] = PricingConfig({
            baseFee: 500_000,        // $0.50 base
            gasEstimate: 150_000,
            timePremiumBps: 50       // 0.5% time premium
        });
        tierDurations[TimeTier.T1hour] = 1 hours;
        
        // Initialize cached prices
        _updateAllPrices();
    }
    
    // ============ Admin Functions ============
    
    function setCore(address _core) external onlyOwner {
        require(_core != address(0), "Invalid core");
        core = _core;
    }
    
    function setPricingConfig(TimeTier tier, PricingConfig calldata config) external onlyOwner {
        tierPricing[tier] = config;
        _updatePrice(tier);
    }
    
    function setTierDuration(TimeTier tier, uint256 duration) external onlyOwner {
        require(duration > 0, "Invalid duration");
        tierDurations[tier] = duration;
    }
    
    function updatePrices() external {
        _updateAllPrices();
    }
    
    // ============ Core Functions ============
    
    function postProblem(
        bytes32 problemHash,
        ProblemType problemType,
        TimeTier timeTier,
        address issuer
    ) external onlyCore returns (uint256 orderId) {
        orderId = _orderCount++;
        
        uint256 duration = tierDurations[timeTier];
        uint256 deadline = block.timestamp + duration;
        
        orders[orderId] = ProblemOrder({
            id: orderId,
            issuer: issuer,
            problemHash: problemHash,
            problemType: problemType,
            timeTier: timeTier,
            status: OrderStatus.OPEN,
            reward: tierPrices[timeTier],
            createdAt: block.timestamp,
            deadline: deadline,
            solver: address(0)
        });
        
        // Add to open orders list
        openOrderIndex[orderId] = openOrderIds.length;
        openOrderIds.push(orderId);
    }
    
    function acceptOrder(uint256 orderId, address solver) external onlyCore {
        require(orders[orderId].status == OrderStatus.OPEN, "Order not open");
        orders[orderId].status = OrderStatus.ACCEPTED;
        orders[orderId].solver = solver;
        
        // Remove from open orders list
        _removeFromOpenOrders(orderId);
    }
    
    function updateOrderStatus(uint256 orderId, OrderStatus status) external onlyCore {
        require(orderId < _orderCount, "Invalid order");
        
        OrderStatus currentStatus = orders[orderId].status;
        
        // If transitioning from OPEN, remove from open list
        if (currentStatus == OrderStatus.OPEN && status != OrderStatus.OPEN) {
            _removeFromOpenOrders(orderId);
        }
        
        orders[orderId].status = status;
    }
    
    function setOrderSolver(uint256 orderId, address solver) external onlyCore {
        require(orderId < _orderCount, "Invalid order");
        orders[orderId].solver = solver;
    }
    
    // ============ View Functions ============
    
    function getOrder(uint256 orderId) external view returns (ProblemOrder memory) {
        require(orderId < _orderCount, "Invalid order");
        return orders[orderId];
    }
    
    function getOpenOrders(uint256 offset, uint256 limit) external view returns (ProblemOrder[] memory) {
        uint256 total = openOrderIds.length;
        
        if (offset >= total) {
            return new ProblemOrder[](0);
        }
        
        uint256 end = offset + limit;
        if (end > total) {
            end = total;
        }
        
        uint256 resultLength = end - offset;
        ProblemOrder[] memory result = new ProblemOrder[](resultLength);
        
        for (uint256 i = 0; i < resultLength; i++) {
            result[i] = orders[openOrderIds[offset + i]];
        }
        
        return result;
    }
    
    function getTierPrice(TimeTier tier) external view returns (uint256) {
        return tierPrices[tier];
    }
    
    function getTierDuration(TimeTier tier) external view returns (uint256) {
        return tierDurations[tier];
    }
    
    function orderCount() external view returns (uint256) {
        return _orderCount;
    }
    
    function openOrderCount() external view returns (uint256) {
        return openOrderIds.length;
    }
    
    function calculatePrice(TimeTier tier) public view returns (uint256) {
        PricingConfig memory config = tierPricing[tier];
        
        // Base fee
        uint256 price = config.baseFee;
        
        // Add gas compensation (approximate: gasEstimate * gasPrice in gwei * price ratio)
        // For simplicity, we use a fixed estimate here
        // In production, this could query an oracle
        uint256 gasCompensation = (config.gasEstimate * tx.gasprice) / 1e12; // Convert to ~USDC scale
        price += gasCompensation;
        
        // Add time premium
        uint256 timePremium = (price * config.timePremiumBps) / 10000;
        price += timePremium;
        
        return price;
    }
    
    function getPricingBreakdown(TimeTier tier) external view returns (
        uint256 baseFee,
        uint256 gasCompensation,
        uint256 timePremium,
        uint256 totalPrice
    ) {
        PricingConfig memory config = tierPricing[tier];
        
        baseFee = config.baseFee;
        gasCompensation = (config.gasEstimate * tx.gasprice) / 1e12;
        uint256 subtotal = baseFee + gasCompensation;
        timePremium = (subtotal * config.timePremiumBps) / 10000;
        totalPrice = subtotal + timePremium;
    }
    
    // ============ Internal Functions ============
    
    function _updatePrice(TimeTier tier) internal {
        tierPrices[tier] = calculatePrice(tier);
    }
    
    function _updateAllPrices() internal {
        _updatePrice(TimeTier.T2min);
        _updatePrice(TimeTier.T5min);
        _updatePrice(TimeTier.T15min);
        _updatePrice(TimeTier.T1hour);
    }
    
    function _removeFromOpenOrders(uint256 orderId) internal {
        uint256 index = openOrderIndex[orderId];
        uint256 lastIndex = openOrderIds.length - 1;
        
        if (index != lastIndex) {
            uint256 lastOrderId = openOrderIds[lastIndex];
            openOrderIds[index] = lastOrderId;
            openOrderIndex[lastOrderId] = index;
        }
        
        openOrderIds.pop();
        delete openOrderIndex[orderId];
    }
}
