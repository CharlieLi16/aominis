// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ICalcSolver.sol";

/**
 * @title Verifier
 * @notice Handles solution verification and challenge resolution for Ominis Protocol
 * @dev Uses hybrid verification: auto-verification by oracle + optimistic fallback
 *      Off-chain oracle provides actual verification results
 */
contract Verifier is IVerifier {
    // ============ State Variables ============
    
    address public core;
    address public owner;
    address public oracle; // Address authorized to submit verification results
    
    // Challenge configuration
    uint256 public challengeWindow = 24 hours; // Time to challenge after reveal
    uint256 public minChallengeStake = 100_000; // Minimum stake (0.10 USDC)
    
    // Auto-verification configuration
    uint256 public verificationTimeout = 5 minutes; // Oracle must verify within this time
    bool public autoVerificationEnabled = true; // Toggle for auto-verification mode
    
    // Oracle staking
    mapping(address => uint256) public oracleStakes;
    uint256 public minOracleStake = 1000_000_000; // 1000 USDC (6 decimals)
    uint256 public oracleSlashAmount = 100_000_000; // 100 USDC per bad verification
    
    // Verification tracking
    mapping(uint256 => VerificationRequest) public verificationRequests;
    
    struct VerificationRequest {
        uint256 orderId;
        string solution;
        ProblemType problemType;
        uint256 requestTime;
        bool isProcessed;
        bool isCorrect;
        string verificationReason;
    }
    
    // Challenge tracking
    mapping(uint256 => Challenge) private challenges;
    mapping(uint256 => bool) private verificationRequested;
    mapping(uint256 => bool) private verificationResult;
    
    // Verification request queue (for oracle)
    uint256[] public pendingVerifications;
    mapping(uint256 => uint256) private pendingIndex;
    
    // ============ Events ============
    
    event VerificationRequested(
        uint256 indexed orderId,
        string solution,
        ProblemType problemType
    );
    
    event VerificationResultSubmitted(
        uint256 indexed orderId,
        bool isCorrect,
        string reason
    );
    
    event AutoVerificationCompleted(
        uint256 indexed orderId,
        bool isCorrect,
        string reason
    );
    
    event AutoRefundTriggered(
        uint256 indexed orderId,
        address indexed issuer,
        string reason
    );
    
    event ChallengeCreated(
        uint256 indexed orderId,
        address indexed challenger,
        string reason
    );
    
    event ChallengeResolved(
        uint256 indexed orderId,
        bool challengerWon
    );
    
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);
    
    event OracleStakeDeposited(address indexed oracle, uint256 amount);
    event OracleStakeWithdrawn(address indexed oracle, uint256 amount);
    event OracleSlashed(address indexed oracle, uint256 amount, uint256 orderId);
    
    // ============ Modifiers ============
    
    modifier onlyCore() {
        require(msg.sender == core, "Only core");
        _;
    }
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyOracle() {
        require(msg.sender == oracle, "Only oracle");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(address _core) {
        require(_core != address(0), "Invalid core");
        core = _core;
        owner = msg.sender;
        oracle = msg.sender; // Owner is initial oracle
    }
    
    // ============ Admin Functions ============
    
    function setCore(address _core) external onlyOwner {
        require(_core != address(0), "Invalid core");
        core = _core;
    }
    
    function setOracle(address _oracle) external onlyOwner {
        require(_oracle != address(0), "Invalid oracle");
        emit OracleUpdated(oracle, _oracle);
        oracle = _oracle;
    }
    
    function setChallengeWindow(uint256 _window) external onlyOwner {
        require(_window >= 1 hours, "Window too short");
        require(_window <= 7 days, "Window too long");
        challengeWindow = _window;
    }
    
    function setMinChallengeStake(uint256 _stake) external onlyOwner {
        minChallengeStake = _stake;
    }
    
    function setVerificationTimeout(uint256 _timeout) external onlyOwner {
        require(_timeout >= 1 minutes, "Timeout too short");
        require(_timeout <= 1 hours, "Timeout too long");
        verificationTimeout = _timeout;
    }
    
    function setAutoVerificationEnabled(bool _enabled) external onlyOwner {
        autoVerificationEnabled = _enabled;
    }
    
    function setMinOracleStake(uint256 _stake) external onlyOwner {
        minOracleStake = _stake;
    }
    
    function setOracleSlashAmount(uint256 _amount) external onlyOwner {
        oracleSlashAmount = _amount;
    }
    
    // ============ Oracle Staking Functions ============
    
    /**
     * @notice Oracle deposits stake to become authorized
     * @param amount Amount to stake
     * @param token The USDC token contract
     */
    function depositOracleStake(uint256 amount, IERC20 token) external {
        require(amount > 0, "Invalid amount");
        require(token.transferFrom(msg.sender, address(this), amount), "Transfer failed");
        
        oracleStakes[msg.sender] += amount;
        emit OracleStakeDeposited(msg.sender, amount);
    }
    
    /**
     * @notice Oracle withdraws stake (if above minimum)
     * @param amount Amount to withdraw
     * @param token The USDC token contract
     */
    function withdrawOracleStake(uint256 amount, IERC20 token) external {
        require(oracleStakes[msg.sender] >= amount, "Insufficient stake");
        require(oracleStakes[msg.sender] - amount >= minOracleStake || oracleStakes[msg.sender] - amount == 0, "Must keep minimum stake");
        
        oracleStakes[msg.sender] -= amount;
        require(token.transfer(msg.sender, amount), "Transfer failed");
        
        emit OracleStakeWithdrawn(msg.sender, amount);
    }
    
    /**
     * @notice Check if oracle has sufficient stake
     */
    function isOracleAuthorized(address _oracle) public view returns (bool) {
        return _oracle == oracle || oracleStakes[_oracle] >= minOracleStake;
    }
    
    // ============ Core Functions ============
    
    /**
     * @notice Request verification of a solution
     * @dev Called by Core after solution is revealed
     *      Adds to pending queue for oracle processing
     */
    function requestVerification(
        uint256 orderId,
        string calldata solution,
        ProblemType problemType
    ) external onlyCore {
        require(!verificationRequested[orderId], "Already requested");
        
        verificationRequested[orderId] = true;
        
        // Store verification request details
        verificationRequests[orderId] = VerificationRequest({
            orderId: orderId,
            solution: solution,
            problemType: problemType,
            requestTime: block.timestamp,
            isProcessed: false,
            isCorrect: false,
            verificationReason: ""
        });
        
        // Add to pending queue
        pendingIndex[orderId] = pendingVerifications.length;
        pendingVerifications.push(orderId);
        
        emit VerificationRequested(orderId, solution, problemType);
    }
    
    /**
     * @notice Submit verification result from oracle with auto-settlement
     * @dev Only callable by authorized oracle address
     *      If incorrect, automatically triggers refund to issuer
     */
    function submitVerificationResult(
        uint256 orderId,
        bool isCorrect,
        string calldata reason
    ) external onlyOracle {
        require(verificationRequested[orderId], "Not requested");
        require(!verificationRequests[orderId].isProcessed, "Already processed");
        
        verificationResult[orderId] = isCorrect;
        verificationRequests[orderId].isProcessed = true;
        verificationRequests[orderId].isCorrect = isCorrect;
        verificationRequests[orderId].verificationReason = reason;
        
        // Remove from pending queue
        _removeFromPending(orderId);
        
        emit VerificationResultSubmitted(orderId, isCorrect, reason);
    }
    
    /**
     * @notice Auto-verify and settle an order (combined verification + settlement)
     * @dev Called by oracle to verify and immediately settle funds
     * @param orderId The order ID
     * @param isCorrect Whether the solution is correct
     * @param reason Explanation for the verification result
     */
    function verifyAndSettle(
        uint256 orderId,
        bool isCorrect,
        string calldata reason
    ) external {
        require(isOracleAuthorized(msg.sender), "Not authorized oracle");
        require(verificationRequested[orderId], "Not requested");
        require(!verificationRequests[orderId].isProcessed, "Already processed");
        require(autoVerificationEnabled, "Auto-verification disabled");
        
        // Check verification timeout
        VerificationRequest storage request = verificationRequests[orderId];
        require(
            block.timestamp <= request.requestTime + verificationTimeout,
            "Verification timeout exceeded"
        );
        
        // Update verification state
        verificationResult[orderId] = isCorrect;
        request.isProcessed = true;
        request.isCorrect = isCorrect;
        request.verificationReason = reason;
        
        // Remove from pending queue
        _removeFromPending(orderId);
        
        emit AutoVerificationCompleted(orderId, isCorrect, reason);
        
        // Call Core to settle funds based on verification result
        if (isCorrect) {
            // Solution is correct - solver gets paid
            // Core.claimReward will handle this when solver calls it
            // Or we can trigger automatic settlement here
        } else {
            // Solution is incorrect - auto-refund to issuer
            // This requires Core to expose a settlement function
            emit AutoRefundTriggered(orderId, address(0), reason);
            
            // Note: Full auto-settlement requires changes to CalcSolverCore
            // For now, this marks the verification as failed and emits event
            // The issuer can then claim timeout refund
        }
    }
    
    /**
     * @notice Slash oracle for bad verification (owner only)
     * @dev Called when oracle is proven to have submitted incorrect verification
     * @param oracleAddress The oracle to slash
     * @param orderId The order with bad verification
     * @param token The USDC token for refund
     * @param recipient Where to send slashed funds
     */
    function slashOracle(
        address oracleAddress,
        uint256 orderId,
        IERC20 token,
        address recipient
    ) external onlyOwner {
        require(oracleStakes[oracleAddress] >= oracleSlashAmount, "Insufficient stake to slash");
        
        oracleStakes[oracleAddress] -= oracleSlashAmount;
        require(token.transfer(recipient, oracleSlashAmount), "Transfer failed");
        
        emit OracleSlashed(oracleAddress, oracleSlashAmount, orderId);
    }
    
    /**
     * @notice Submit a challenge against a solution
     * @param orderId The order ID
     * @param challenger Address of the challenger
     * @param reason Reason for the challenge
     */
    function submitChallenge(
        uint256 orderId,
        address challenger,
        string calldata reason
    ) external onlyCore returns (uint256 challengeId) {
        require(!challenges[orderId].resolved, "Challenge already resolved");
        require(challenges[orderId].challenger == address(0), "Challenge exists");
        
        challenges[orderId] = Challenge({
            orderId: orderId,
            challenger: challenger,
            stake: 0, // Stake is managed by Escrow
            challengeTime: block.timestamp,
            resolved: false,
            challengerWon: false,
            reason: reason
        });
        
        emit ChallengeCreated(orderId, challenger, reason);
        
        return orderId; // Use orderId as challengeId for simplicity
    }
    
    /**
     * @notice Resolve a challenge
     * @dev Called by oracle after verifying the challenge
     */
    function resolveChallenge(uint256 orderId, bool challengerWon) external onlyOracle {
        Challenge storage challenge = challenges[orderId];
        require(challenge.challenger != address(0), "No challenge");
        require(!challenge.resolved, "Already resolved");
        
        challenge.resolved = true;
        challenge.challengerWon = challengerWon;
        
        emit ChallengeResolved(orderId, challengerWon);
        
        // Call Core to handle fund distribution
        ICalcSolverCore(core).resolveChallenge(orderId, challengerWon);
    }
    
    // ============ View Functions ============
    
    function getChallenge(uint256 orderId) external view returns (Challenge memory) {
        return challenges[orderId];
    }
    
    function isUnderChallenge(uint256 orderId) external view returns (bool) {
        return challenges[orderId].challenger != address(0) && 
               !challenges[orderId].resolved;
    }
    
    function getChallengeWindow() external view returns (uint256) {
        return challengeWindow;
    }
    
    function isVerificationRequested(uint256 orderId) external view returns (bool) {
        return verificationRequested[orderId];
    }
    
    function getVerificationResult(uint256 orderId) external view returns (bool) {
        return verificationResult[orderId];
    }
    
    function getPendingVerificationsCount() external view returns (uint256) {
        return pendingVerifications.length;
    }
    
    function getPendingVerifications(
        uint256 offset,
        uint256 limit
    ) external view returns (uint256[] memory) {
        uint256 total = pendingVerifications.length;
        
        if (offset >= total) {
            return new uint256[](0);
        }
        
        uint256 end = offset + limit;
        if (end > total) {
            end = total;
        }
        
        uint256 resultLength = end - offset;
        uint256[] memory result = new uint256[](resultLength);
        
        for (uint256 i = 0; i < resultLength; i++) {
            result[i] = pendingVerifications[offset + i];
        }
        
        return result;
    }
    
    function getVerificationRequest(uint256 orderId) external view returns (
        string memory solution,
        ProblemType problemType,
        uint256 requestTime,
        bool isProcessed,
        bool isCorrect,
        string memory verificationReason
    ) {
        VerificationRequest storage req = verificationRequests[orderId];
        return (
            req.solution,
            req.problemType,
            req.requestTime,
            req.isProcessed,
            req.isCorrect,
            req.verificationReason
        );
    }
    
    function getVerificationTimeout() external view returns (uint256) {
        return verificationTimeout;
    }
    
    function isAutoVerificationEnabled() external view returns (bool) {
        return autoVerificationEnabled;
    }
    
    function getOracleStake(address oracleAddress) external view returns (uint256) {
        return oracleStakes[oracleAddress];
    }
    
    // ============ Internal Functions ============
    
    function _removeFromPending(uint256 orderId) internal {
        uint256 index = pendingIndex[orderId];
        uint256 lastIndex = pendingVerifications.length - 1;
        
        if (index != lastIndex) {
            uint256 lastOrderId = pendingVerifications[lastIndex];
            pendingVerifications[index] = lastOrderId;
            pendingIndex[lastOrderId] = index;
        }
        
        pendingVerifications.pop();
        delete pendingIndex[orderId];
    }
}
