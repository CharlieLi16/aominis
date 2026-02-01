// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../contracts/CalcSolverCore.sol";
import "../contracts/modules/OrderBook.sol";
import "../contracts/modules/Escrow.sol";
import "../contracts/modules/SolutionManager.sol";
import "../contracts/modules/Verifier.sol";

/**
 * @title Deploy Script
 * @notice Deploys all Ominis Protocol contracts
 * 
 * Usage:
 *   forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast --verify
 */
contract DeployScript is Script {
    // Arbitrum Sepolia USDC address
    address constant USDC_ARBITRUM_SEPOLIA = 0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d;
    
    // Arbitrum One USDC address
    address constant USDC_ARBITRUM_ONE = 0xaf88d065e77c8cC2239327C5EDb3A432268e5831;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        // Determine USDC address based on chain
        address usdcAddress;
        uint256 chainId = block.chainid;
        
        if (chainId == 421614) {
            // Arbitrum Sepolia
            usdcAddress = USDC_ARBITRUM_SEPOLIA;
        } else if (chainId == 42161) {
            // Arbitrum One
            usdcAddress = USDC_ARBITRUM_ONE;
        } else {
            // For local testing, deploy a mock
            revert("Unsupported chain");
        }

        console.log("Deploying Ominis Protocol...");
        console.log("Chain ID:", chainId);
        console.log("Deployer:", deployer);
        console.log("USDC:", usdcAddress);

        vm.startBroadcast(deployerPrivateKey);

        // 1. Deploy Core
        CalcSolverCore core = new CalcSolverCore(usdcAddress);
        console.log("CalcSolverCore deployed at:", address(core));

        // 2. Deploy Modules
        OrderBook orderBook = new OrderBook(address(core));
        console.log("OrderBook deployed at:", address(orderBook));

        Escrow escrow = new Escrow(usdcAddress, address(core));
        console.log("Escrow deployed at:", address(escrow));

        SolutionManager solutionManager = new SolutionManager(address(core));
        console.log("SolutionManager deployed at:", address(solutionManager));

        Verifier verifier = new Verifier(address(core));
        console.log("Verifier deployed at:", address(verifier));

        // 3. Configure Core
        core.setModules(
            address(orderBook),
            address(escrow),
            address(solutionManager),
            address(verifier)
        );
        console.log("Modules configured in Core");

        // 4. Set oracle (deployer initially, should be changed later)
        verifier.setOracle(deployer);
        console.log("Oracle set to deployer (update this!)");

        vm.stopBroadcast();

        // Output deployment info
        console.log("");
        console.log("=== Deployment Complete ===");
        console.log("Core:", address(core));
        console.log("OrderBook:", address(orderBook));
        console.log("Escrow:", address(escrow));
        console.log("SolutionManager:", address(solutionManager));
        console.log("Verifier:", address(verifier));
    }
}

/**
 * @title Deploy Script for Local Testing
 * @notice Deploys all contracts with a mock USDC for local testing
 */
contract DeployLocalScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envOr("PRIVATE_KEY", uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        
        vm.startBroadcast(deployerPrivateKey);

        // Deploy mock USDC
        MockUSDC usdc = new MockUSDC();
        console.log("MockUSDC deployed at:", address(usdc));

        // Deploy Core
        CalcSolverCore core = new CalcSolverCore(address(usdc));
        console.log("CalcSolverCore deployed at:", address(core));

        // Deploy Modules
        OrderBook orderBook = new OrderBook(address(core));
        Escrow escrow = new Escrow(address(usdc), address(core));
        SolutionManager solutionManager = new SolutionManager(address(core));
        Verifier verifier = new Verifier(address(core));

        // Configure
        core.setModules(
            address(orderBook),
            address(escrow),
            address(solutionManager),
            address(verifier)
        );

        vm.stopBroadcast();

        console.log("=== Local Deployment Complete ===");
    }
}

// Simple mock for local testing
contract MockUSDC {
    string public name = "USD Coin";
    string public symbol = "USDC";
    uint8 public decimals = 6;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        totalSupply += amount;
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount);
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount);
        require(balanceOf[from] >= amount);
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}
