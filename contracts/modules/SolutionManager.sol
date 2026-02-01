// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../interfaces/ICalcSolver.sol";

/**
 * @title SolutionManager
 * @notice Handles commit-reveal pattern for solution submission
 */
contract SolutionManager is ISolutionManager {
    // ============ State Variables ============
    
    address public core;
    address public owner;
    
    mapping(uint256 => SolutionSubmission) private submissions;
    
    // Minimum time between commit and reveal (prevents same-block reveal)
    uint256 public minRevealDelay = 1; // 1 block minimum
    
    // ============ Events ============
    
    event SolutionCommitted(
        uint256 indexed orderId,
        address indexed solver,
        bytes32 commitHash,
        uint256 timestamp
    );
    
    event SolutionRevealed(
        uint256 indexed orderId,
        address indexed solver,
        string solution,
        uint256 timestamp
    );
    
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
    }
    
    // ============ Admin Functions ============
    
    function setCore(address _core) external onlyOwner {
        require(_core != address(0), "Invalid core");
        core = _core;
    }
    
    function setMinRevealDelay(uint256 _delay) external onlyOwner {
        minRevealDelay = _delay;
    }
    
    // ============ Core Functions ============
    
    /**
     * @notice Commit a solution hash
     * @param orderId The order ID
     * @param solver The solver address
     * @param commitHash keccak256(abi.encodePacked(solution, salt))
     */
    function commitSolution(
        uint256 orderId,
        address solver,
        bytes32 commitHash
    ) external onlyCore {
        require(commitHash != bytes32(0), "Invalid commit hash");
        require(submissions[orderId].commitHash == bytes32(0), "Already committed");
        
        submissions[orderId] = SolutionSubmission({
            orderId: orderId,
            solver: solver,
            commitHash: commitHash,
            solution: "",
            salt: bytes32(0),
            commitTime: block.timestamp,
            revealTime: 0,
            isRevealed: false
        });
        
        emit SolutionCommitted(orderId, solver, commitHash, block.timestamp);
    }
    
    /**
     * @notice Reveal a previously committed solution
     * @param orderId The order ID
     * @param solver The solver address (must match committer)
     * @param solution The actual solution string
     * @param salt The salt used in the commit
     * @return valid Whether the reveal matches the commit
     */
    function revealSolution(
        uint256 orderId,
        address solver,
        string calldata solution,
        bytes32 salt
    ) external onlyCore returns (bool valid) {
        SolutionSubmission storage submission = submissions[orderId];
        
        require(submission.commitHash != bytes32(0), "Not committed");
        require(!submission.isRevealed, "Already revealed");
        require(submission.solver == solver, "Wrong solver");
        require(block.timestamp >= submission.commitTime + minRevealDelay, "Too early");
        
        // Verify the commitment
        bytes32 expectedHash = keccak256(abi.encodePacked(solution, salt));
        valid = (expectedHash == submission.commitHash);
        
        if (valid) {
            submission.solution = solution;
            submission.salt = salt;
            submission.revealTime = block.timestamp;
            submission.isRevealed = true;
            
            emit SolutionRevealed(orderId, solver, solution, block.timestamp);
        }
        
        return valid;
    }
    
    // ============ View Functions ============
    
    function getSubmission(uint256 orderId) external view returns (SolutionSubmission memory) {
        return submissions[orderId];
    }
    
    function isCommitted(uint256 orderId) external view returns (bool) {
        return submissions[orderId].commitHash != bytes32(0);
    }
    
    function isRevealed(uint256 orderId) external view returns (bool) {
        return submissions[orderId].isRevealed;
    }
    
    function verifyCommitment(
        uint256 orderId,
        string calldata solution,
        bytes32 salt
    ) external view returns (bool) {
        bytes32 expectedHash = keccak256(abi.encodePacked(solution, salt));
        return expectedHash == submissions[orderId].commitHash;
    }
    
    function getCommitHash(uint256 orderId) external view returns (bytes32) {
        return submissions[orderId].commitHash;
    }
    
    function getSolver(uint256 orderId) external view returns (address) {
        return submissions[orderId].solver;
    }
    
    function getCommitTime(uint256 orderId) external view returns (uint256) {
        return submissions[orderId].commitTime;
    }
    
    function getRevealTime(uint256 orderId) external view returns (uint256) {
        return submissions[orderId].revealTime;
    }
    
    /**
     * @notice Compute the commit hash for a solution and salt
     * @dev Helper function for off-chain use
     */
    function computeCommitHash(
        string calldata solution,
        bytes32 salt
    ) external pure returns (bytes32) {
        return keccak256(abi.encodePacked(solution, salt));
    }
}
