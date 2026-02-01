// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ICalcSolver.sol";

/**
 * @title Escrow
 * @notice Manages fund locking, release, and slashing for Ominis Protocol
 */
contract Escrow is IEscrow {
    // ============ State Variables ============
    
    IERC20 public immutable paymentToken;
    address public core;
    address public owner;
    
    // Locked funds tracking
    mapping(uint256 => uint256) public lockedRewards;      // orderId => amount
    mapping(uint256 => address) public rewardIssuers;      // orderId => issuer address
    mapping(uint256 => uint256) public solverBonds;        // orderId => amount
    mapping(uint256 => address) public bondSolvers;        // orderId => solver address
    mapping(uint256 => uint256) public challengeStakes;    // orderId => amount
    mapping(uint256 => address) public challengers;        // orderId => challenger address
    
    // Protocol fees
    uint256 public protocolFees;
    uint256 public protocolFeeBps = 250; // 2.5%
    address public feeRecipient;
    
    // ============ Events ============
    
    event RewardLocked(uint256 indexed orderId, address indexed issuer, uint256 amount);
    event SolverBondLocked(uint256 indexed orderId, address indexed solver, uint256 amount);
    event ChallengeStakeLocked(uint256 indexed orderId, address indexed challenger, uint256 amount);
    event RewardReleased(uint256 indexed orderId, address indexed recipient, uint256 amount);
    event RefundIssued(uint256 indexed orderId, address indexed issuer, uint256 amount);
    event FundsSlashed(uint256 indexed orderId, address indexed from, uint256 amount);
    event ProtocolFeeCollected(uint256 amount);
    
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
    
    constructor(address _paymentToken, address _core) {
        require(_paymentToken != address(0), "Invalid token");
        require(_core != address(0), "Invalid core");
        
        paymentToken = IERC20(_paymentToken);
        core = _core;
        owner = msg.sender;
        feeRecipient = msg.sender;
    }
    
    // ============ Admin Functions ============
    
    function setCore(address _core) external onlyOwner {
        require(_core != address(0), "Invalid core");
        core = _core;
    }
    
    function setProtocolFeeBps(uint256 _feeBps) external onlyOwner {
        require(_feeBps <= 1000, "Fee too high"); // Max 10%
        protocolFeeBps = _feeBps;
    }
    
    function setFeeRecipient(address _recipient) external onlyOwner {
        require(_recipient != address(0), "Invalid recipient");
        feeRecipient = _recipient;
    }
    
    function withdrawProtocolFees() external onlyOwner {
        uint256 amount = protocolFees;
        require(amount > 0, "No fees to withdraw");
        
        protocolFees = 0;
        require(paymentToken.transfer(feeRecipient, amount), "Transfer failed");
        
        emit ProtocolFeeCollected(amount);
    }
    
    // ============ Locking Functions ============
    
    function lockReward(uint256 orderId, address issuer, uint256 amount) external onlyCore {
        require(lockedRewards[orderId] == 0, "Already locked");
        require(amount > 0, "Invalid amount");
        
        lockedRewards[orderId] = amount;
        rewardIssuers[orderId] = issuer;
        
        emit RewardLocked(orderId, issuer, amount);
    }
    
    function lockSolverBond(uint256 orderId, address solver, uint256 amount) external onlyCore {
        require(solverBonds[orderId] == 0, "Bond already locked");
        
        solverBonds[orderId] = amount;
        bondSolvers[orderId] = solver;
        
        emit SolverBondLocked(orderId, solver, amount);
    }
    
    function lockChallengeStake(uint256 orderId, address challenger, uint256 amount) external onlyCore {
        require(challengeStakes[orderId] == 0, "Stake already locked");
        require(amount > 0, "Invalid amount");
        
        challengeStakes[orderId] = amount;
        challengers[orderId] = challenger;
        
        emit ChallengeStakeLocked(orderId, challenger, amount);
    }
    
    // ============ Release Functions ============
    
    function releaseRewardToSolver(uint256 orderId) external onlyCore {
        uint256 reward = lockedRewards[orderId];
        require(reward > 0, "No reward locked");
        
        address solver = bondSolvers[orderId];
        require(solver != address(0), "No solver");
        
        // Calculate protocol fee
        uint256 fee = (reward * protocolFeeBps) / 10000;
        uint256 solverPayment = reward - fee;
        
        // Update state
        lockedRewards[orderId] = 0;
        protocolFees += fee;
        
        // Return solver bond
        uint256 bond = solverBonds[orderId];
        if (bond > 0) {
            solverBonds[orderId] = 0;
            solverPayment += bond;
        }
        
        // Transfer to solver
        require(paymentToken.transfer(solver, solverPayment), "Transfer failed");
        
        emit RewardReleased(orderId, solver, solverPayment);
    }
    
    function refundToIssuer(uint256 orderId) external onlyCore {
        uint256 reward = lockedRewards[orderId];
        require(reward > 0, "No reward to refund");
        
        address issuer = rewardIssuers[orderId];
        require(issuer != address(0), "No issuer");
        
        // Update state
        lockedRewards[orderId] = 0;
        
        // Transfer to issuer
        require(paymentToken.transfer(issuer, reward), "Transfer failed");
        
        emit RefundIssued(orderId, issuer, reward);
    }
    
    // ============ Slashing Functions ============
    
    function slashSolver(uint256 orderId) external onlyCore {
        uint256 bond = solverBonds[orderId];
        if (bond == 0) return;
        
        address solver = bondSolvers[orderId];
        
        // Move bond to protocol fees (could also go to challenger/issuer)
        solverBonds[orderId] = 0;
        protocolFees += bond;
        
        emit FundsSlashed(orderId, solver, bond);
    }
    
    function rewardChallenger(uint256 orderId) external onlyCore {
        address challenger = challengers[orderId];
        require(challenger != address(0), "No challenger");
        
        uint256 stake = challengeStakes[orderId];
        uint256 solverBond = solverBonds[orderId];
        
        // Challenger gets their stake back + portion of solver bond
        uint256 reward = stake + (solverBond / 2); // 50% of solver bond
        
        // Update state
        challengeStakes[orderId] = 0;
        if (solverBond > 0) {
            solverBonds[orderId] = 0;
            protocolFees += solverBond - (solverBond / 2); // Other 50% to protocol
        }
        
        // Transfer to challenger
        require(paymentToken.transfer(challenger, reward), "Transfer failed");
        
        emit RewardReleased(orderId, challenger, reward);
    }
    
    function slashChallenger(uint256 orderId) external onlyCore {
        uint256 stake = challengeStakes[orderId];
        if (stake == 0) return;
        
        address challenger = challengers[orderId];
        
        // Move stake to solver as bonus
        address solver = bondSolvers[orderId];
        
        challengeStakes[orderId] = 0;
        
        if (solver != address(0)) {
            // Give half to solver, half to protocol
            uint256 solverBonus = stake / 2;
            require(paymentToken.transfer(solver, solverBonus), "Transfer failed");
            protocolFees += stake - solverBonus;
        } else {
            protocolFees += stake;
        }
        
        emit FundsSlashed(orderId, challenger, stake);
    }
    
    // ============ View Functions ============
    
    function getLockedReward(uint256 orderId) external view returns (uint256) {
        return lockedRewards[orderId];
    }
    
    function getSolverBond(uint256 orderId) external view returns (uint256) {
        return solverBonds[orderId];
    }
    
    function getChallengeStake(uint256 orderId) external view returns (uint256) {
        return challengeStakes[orderId];
    }
    
    function getOrderFunds(uint256 orderId) external view returns (
        uint256 reward,
        uint256 bond,
        uint256 stake,
        address issuer,
        address solver,
        address challenger_
    ) {
        reward = lockedRewards[orderId];
        bond = solverBonds[orderId];
        stake = challengeStakes[orderId];
        issuer = rewardIssuers[orderId];
        solver = bondSolvers[orderId];
        challenger_ = challengers[orderId];
    }
}
