import React, { useState, useEffect, useRef } from 'react';
import { ethers } from 'ethers';
import { PROBLEM_TYPES, TIME_TIERS, ORDER_STATUS, NETWORKS } from '../config';

// Core contract address for approvals (not Escrow!)
// The Core contract calls transferFrom to move USDC to Escrow
const CORE_ADDRESS = NETWORKS.sepolia?.contracts?.core || '0x05465FEd0ba03A012c87Ac215c249EeA48aEcFd0';

// Bot Server URL - WSL IP for Windows access
// Change this to your WSL IP if localhost doesn't work
const BOT_SERVER_URL = 'http://172.19.37.93:5001';

function SolverDashboard({ coreContract, usdcContract, account, network }) {
    const [orders, setOrders] = useState([]);
    const [myAccepted, setMyAccepted] = useState([]);
    const [loading, setLoading] = useState(false);
    const [botRunning, setBotRunning] = useState(false);
    const [logs, setLogs] = useState([]);
    const [stats, setStats] = useState({ solved: 0, earned: 0 });
    const [solverBalance, setSolverBalance] = useState({ eth: '0', usdc: '0' });
    const [acceptingOrder, setAcceptingOrder] = useState(null); // Track which order is being accepted
    const [processingOrders, setProcessingOrders] = useState(new Set()); // Track orders being processed by bot
    const [usdcAllowance, setUsdcAllowance] = useState('0');
    const [approving, setApproving] = useState(false);
    
    // Store pending reveals in localStorage so they persist across refreshes
    const [pendingReveals, setPendingReveals] = useState(() => {
        try {
            const saved = localStorage.getItem('ominis_pending_reveals');
            return saved ? JSON.parse(saved) : {};
        } catch {
            return {};
        }
    });
    
    // Sync to localStorage when pendingReveals changes
    useEffect(() => {
        try {
            localStorage.setItem('ominis_pending_reveals', JSON.stringify(pendingReveals));
        } catch (e) {
            console.error('Failed to save pending reveals:', e);
        }
    }, [pendingReveals]);
    
    // Bot configuration
    const [botConfig, setBotConfig] = useState({
        autoAccept: true,
        autoSolve: true,
        maxConcurrent: 3,
        acceptedTypes: [0, 1, 2, 3, 4], // All problem types
    });
    
    // Bot server state
    const [botServerConnected, setBotServerConnected] = useState(false);
    const [usePythonBot, setUsePythonBot] = useState(true); // Toggle between JS and Python bot
    const [serverLogs, setServerLogs] = useState([]);
    
    const botIntervalRef = useRef(null);
    const ordersRef = useRef(orders); // Ref to access latest orders in interval
    const logsIntervalRef = useRef(null);

    // Keep ordersRef in sync
    useEffect(() => {
        ordersRef.current = orders;
    }, [orders]);

    // Check bot server connection on mount
    useEffect(() => {
        checkBotServer();
    }, []);

    // Check if Python bot server is running
    const checkBotServer = async () => {
        console.log('Checking bot server at:', BOT_SERVER_URL);
        try {
            const res = await fetch(`${BOT_SERVER_URL}/health`, {
                method: 'GET',
                mode: 'cors',
            });
            console.log('Bot server response:', res.status);
            if (res.ok) {
                setBotServerConnected(true);
                addLog(`Connected to Python Bot Server at ${BOT_SERVER_URL}`, 'success');
                // Check if bot is already running
                const statusRes = await fetch(`${BOT_SERVER_URL}/status`);
                const status = await statusRes.json();
                if (status.running) {
                    setBotRunning(true);
                    startLogPolling();
                }
            } else {
                setBotServerConnected(false);
                addLog(`Bot server responded with status ${res.status}`, 'warning');
            }
        } catch (e) {
            console.error('Bot server check failed:', e);
            setBotServerConnected(false);
            addLog(`Cannot connect to Bot Server: ${e.message}`, 'error');
        }
    };

    // Fetch logs from Python bot server
    const fetchServerLogs = async () => {
        try {
            const res = await fetch(`${BOT_SERVER_URL}/logs?limit=50`);
            const data = await res.json();
            if (data.logs) {
                // Merge with existing logs, avoiding duplicates
                const newLogs = data.logs.map(log => ({
                    timestamp: log.timestamp,
                    message: log.message,
                    type: log.level === 'error' ? 'error' : 
                          log.level === 'success' ? 'success' : 
                          log.level === 'warning' ? 'warning' : 'info'
                }));
                setServerLogs(newLogs);
            }
        } catch (e) {
            console.error('Failed to fetch server logs:', e);
        }
    };

    // Start polling logs from server
    const startLogPolling = () => {
        if (logsIntervalRef.current) return;
        logsIntervalRef.current = setInterval(fetchServerLogs, 2000);
        fetchServerLogs(); // Fetch immediately
    };

    // Stop polling logs
    const stopLogPolling = () => {
        if (logsIntervalRef.current) {
            clearInterval(logsIntervalRef.current);
            logsIntervalRef.current = null;
        }
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopLogPolling();
        };
    }, []);

    // Fetch data on mount
    useEffect(() => {
        if (coreContract && account) {
            fetchOrders();
            fetchMyAccepted();
            fetchBalance();
            checkAllowance();
        }
    }, [coreContract, account]);

    // Check USDC allowance for Escrow
    const checkAllowance = async () => {
        if (!usdcContract || !account) return;
        try {
            const allowance = await usdcContract.allowance(account, CORE_ADDRESS);
            setUsdcAllowance(ethers.formatUnits(allowance, 6));
        } catch (e) {
            console.error('Error checking allowance:', e);
        }
    };

    // Approve USDC for Escrow
    const handleApprove = async (amount = '1000000') => { // Default 1M USDC
        if (!usdcContract) return false;
        setApproving(true);
        addLog(`Approving USDC for Escrow...`);
        try {
            const amountWei = ethers.parseUnits(amount, 6);
            const tx = await usdcContract.approve(CORE_ADDRESS, amountWei);
            addLog(`Approval TX sent: ${tx.hash.slice(0, 16)}...`);
            await tx.wait();
            addLog(`USDC approved!`, 'success');
            await checkAllowance();
            setApproving(false);
            return true;
        } catch (e) {
            addLog(`Approval failed: ${e.reason || e.message}`, 'error');
            setApproving(false);
            return false;
        }
    };

    const addLog = (message, type = 'info') => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [...prev.slice(-50), { timestamp, message, type }]);
    };

    const fetchBalance = async () => {
        if (!account || !usdcContract) return;
        try {
            const provider = usdcContract.runner.provider;
            const ethBal = await provider.getBalance(account);
            const usdcBal = await usdcContract.balanceOf(account);
            setSolverBalance({
                eth: ethers.formatEther(ethBal),
                usdc: ethers.formatUnits(usdcBal, 6)
            });
        } catch (e) {
            console.error('Error fetching balance:', e);
        }
    };

    const fetchOrders = async () => {
        if (!coreContract) return;
        setLoading(true);
        try {
            const filter = coreContract.filters.ProblemPosted();
            const events = await coreContract.queryFilter(filter, -10000);
            
            const fetchedOrders = [];
            for (const event of events) {
                try {
                    const orderId = event.args[0];
                    const order = await coreContract.getOrder(orderId);
                    if (Number(order.status) === 0) { // Only open orders
                        fetchedOrders.push({
                            id: Number(order.id),
                            issuer: order.issuer,
                            problemHash: order.problemHash,
                            problemType: Number(order.problemType),
                            timeTier: Number(order.timeTier),
                            status: Number(order.status),
                            reward: ethers.formatUnits(order.reward, 6),
                            deadline: Number(order.deadline) * 1000,
                            solver: order.solver,
                        });
                    }
                } catch (e) {}
            }
            setOrders(fetchedOrders.reverse());
            return fetchedOrders.reverse();
        } catch (e) {
            addLog(`Error fetching orders: ${e.message}`, 'error');
            return [];
        } finally {
            setLoading(false);
        }
    };

    const fetchMyAccepted = async () => {
        if (!coreContract || !account) return;
        try {
            const filter = coreContract.filters.OrderAccepted(null, account);
            const events = await coreContract.queryFilter(filter, -10000);
            
            const accepted = [];
            for (const event of events) {
                try {
                    const orderId = event.args[0];
                    const order = await coreContract.getOrder(orderId);
                    accepted.push({
                        id: Number(order.id),
                        problemType: Number(order.problemType),
                        timeTier: Number(order.timeTier),
                        status: Number(order.status),
                        reward: ethers.formatUnits(order.reward, 6),
                        deadline: Number(order.deadline) * 1000,
                    });
                } catch (e) {}
            }
            setMyAccepted(accepted.reverse());
        } catch (e) {}
    };

    // Math solver - generates placeholder solutions based on problem type (fallback)
    const solveProblem = (problemType) => {
        const solutions = {
            0: "f'(x) = 2x + 3", // Derivative
            1: "F(x) = x^2/2 + C", // Integral
            2: "lim(x->0) = 1", // Limit
            3: "y = Ce^x + x", // Differential Eq
            4: "Sum = n(n+1)/2", // Series
        };
        return solutions[problemType] || `Solution for type ${problemType}`;
    };

    // Solve using GPT via bot server API - returns solution with steps
    const solveWithGPT = async (orderId, problemType, problemHash) => {
        if (!botServerConnected) {
            addLog(`[GPT] Bot server not connected, using fallback`, 'warning');
            return { answer: solveProblem(problemType), steps: [] };
        }
        
        try {
            addLog(`[GPT] Solving order #${orderId} with GPT...`, 'info');
            
            // Get problem hash as string
            const hashStr = typeof problemHash === 'string' 
                ? problemHash 
                : (problemHash ? ethers.hexlify(problemHash) : '');
            
            // Try to get problem text from storage first
            let problemText = null;
            if (hashStr) {
                try {
                    const storedRes = await fetch(`${BOT_SERVER_URL}/problems/${hashStr.toLowerCase()}`);
                    const stored = await storedRes.json();
                    if (stored.success && stored.problem) {
                        problemText = stored.problem.text;
                        addLog(`[GPT] Found problem: ${problemText.substring(0, 50)}...`, 'info');
                    }
                } catch (e) {
                    console.log('Could not fetch stored problem:', e);
                }
            }
            
            // Call GPT solve API with order_id to store solution
            const res = await fetch(`${BOT_SERVER_URL}/solve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    problem_type: problemType,
                    problem_text: problemText,
                    problem_hash: hashStr,
                    order_id: orderId
                })
            });
            
            const data = await res.json();
            
            if (data.success && data.solution) {
                const stepsCount = data.steps?.length || 0;
                addLog(`[GPT] Solution: ${data.solution} (${stepsCount} steps)`, 'success');
                return { answer: data.solution, steps: data.steps || [] };
            } else {
                addLog(`[GPT] API error: ${data.error || 'Unknown error'}`, 'error');
                return { answer: data.solution || solveProblem(problemType), steps: data.steps || [] };
            }
        } catch (e) {
            addLog(`[GPT] Request failed: ${e.message}`, 'error');
            return { answer: solveProblem(problemType), steps: [] };
        }
    };

    const handleAccept = async (orderId) => {
        if (!coreContract || !usdcContract) return false;
        setAcceptingOrder(orderId);
        
        try {
            // Check USDC balance first
            const balanceWei = await usdcContract.balanceOf(account);
            const currentBalance = parseFloat(ethers.formatUnits(balanceWei, 6));
            addLog(`USDC balance: $${currentBalance.toFixed(2)}`, 'info');
            
            if (currentBalance < 1) {
                addLog(`ERROR: You need USDC to accept orders (for bond). Please get some USDC first!`, 'error');
                setAcceptingOrder(null);
                return false;
            }
            
            // Check allowance directly from contract (not state)
            const allowanceWei = await usdcContract.allowance(account, CORE_ADDRESS);
            const currentAllowance = parseFloat(ethers.formatUnits(allowanceWei, 6));
            addLog(`USDC allowance: $${currentAllowance.toFixed(2)}`, 'info');
            
            // Need at least some allowance for bond
            if (currentAllowance < currentBalance) {
                addLog(`Approving USDC for Escrow...`, 'warning');
                const approved = await handleApprove(Math.ceil(currentBalance * 2).toString()); // Approve 2x balance
                if (!approved) {
                    setAcceptingOrder(null);
                    return false;
                }
                // Wait for approval to be mined
                await new Promise(r => setTimeout(r, 2000));
            }
            
            addLog(`Accepting order #${orderId}...`);
            const tx = await coreContract.acceptOrder(orderId);
            addLog(`TX sent: ${tx.hash.slice(0, 16)}...`);
            await tx.wait();
            addLog(`Order #${orderId} accepted!`, 'success');
            await fetchOrders();
            await fetchMyAccepted();
            fetchBalance();
            checkAllowance();
            setAcceptingOrder(null);
            return true;
        } catch (e) {
            addLog(`Failed to accept: ${e.reason || e.message}`, 'error');
            setAcceptingOrder(null);
            return false;
        }
    };

    const handleCommit = async (orderId, solution) => {
        if (!coreContract) return false;
        
        // Generate salt and commit hash
        const salt = ethers.hexlify(ethers.randomBytes(32));
        const commitHash = ethers.solidityPackedKeccak256(
            ['string', 'bytes32'],
            [solution, salt]
        );
        
        addLog(`Committing solution for order #${orderId}...`);
        try {
            const tx = await coreContract.commitSolution(orderId, commitHash);
            await tx.wait();
            
            // Store for later reveal
            setPendingReveals(prev => ({ ...prev, [orderId]: { solution, salt } }));
            addLog(`Committed! Waiting for next block before reveal...`);
            
            // Wait for next block (Sepolia ~12s block time) + buffer
            await new Promise(r => setTimeout(r, 15000));
            addLog(`Revealing solution...`);
            
            const tx2 = await coreContract.revealSolution(orderId, solution, salt);
            await tx2.wait();
            addLog(`Solution revealed for order #${orderId}!`, 'success');
            
            // Clear pending
            setPendingReveals(prev => {
                const newPending = { ...prev };
                delete newPending[orderId];
                return newPending;
            });
            
            setStats(prev => ({ ...prev, solved: prev.solved + 1 }));
            fetchMyAccepted();
            return true;
        } catch (e) {
            addLog(`Failed: ${e.reason || e.message}`, 'error');
            // Keep pending reveal stored so user can retry
            return false;
        }
    };

    // Manual reveal for orders stuck in Committed state
    const handleReveal = async (orderId) => {
        if (!coreContract) return;
        
        const pending = pendingReveals[orderId];
        if (!pending) {
            // No stored data - need to re-commit
            addLog(`No stored commit data for order #${orderId}. You need to re-submit the solution.`, 'error');
            return;
        }
        
        addLog(`Revealing solution for order #${orderId}...`);
        try {
            const tx = await coreContract.revealSolution(orderId, pending.solution, pending.salt);
            await tx.wait();
            addLog(`Solution revealed!`, 'success');
            
            // Clear pending
            setPendingReveals(prev => {
                const newPending = { ...prev };
                delete newPending[orderId];
                return newPending;
            });
            
            setStats(prev => ({ ...prev, solved: prev.solved + 1 }));
            fetchMyAccepted();
        } catch (e) {
            addLog(`Reveal failed: ${e.reason || e.message}`, 'error');
        }
    };

    const handleClaimReward = async (orderId) => {
        if (!coreContract) return;
        addLog(`Claiming reward for order #${orderId}...`);
        try {
            const tx = await coreContract.claimReward(orderId);
            await tx.wait();
            addLog(`Reward claimed!`, 'success');
            fetchMyAccepted();
            fetchBalance();
        } catch (e) {
            addLog(`Failed: ${e.reason || e.message}`, 'error');
        }
    };

    // Auto-process a single order (accept -> solve -> submit)
    const autoProcessOrder = async (order) => {
        const orderId = order.id;
        
        // Mark as processing
        setProcessingOrders(prev => new Set([...prev, orderId]));
        
        addLog(`[BOT] Processing order #${orderId}...`, 'info');
        
        try {
            // Step 1: Accept the order
            if (botConfig.autoAccept) {
                const accepted = await handleAccept(orderId);
                if (!accepted) {
                    addLog(`[BOT] Failed to accept order #${orderId}`, 'error');
                    return;
                }
                
                // Wait for state to update
                await new Promise(r => setTimeout(r, 1000));
            }
            
            // Step 2: Solve and submit
            if (botConfig.autoSolve) {
                // Use GPT if bot server connected, otherwise fallback
                const result = await solveWithGPT(orderId, order.problemType, order.problemHash);
                const solution = result.answer;
                
                // Wait before submitting
                await new Promise(r => setTimeout(r, 2000));
                
                const submitted = await handleCommit(orderId, solution);
                if (submitted) {
                    addLog(`[BOT] Order #${orderId} completed!`, 'success');
                }
            }
        } catch (e) {
            addLog(`[BOT] Error processing order #${orderId}: ${e.message}`, 'error');
        } finally {
            // Remove from processing
            setProcessingOrders(prev => {
                const newSet = new Set(prev);
                newSet.delete(orderId);
                return newSet;
            });
        }
    };

    // Enhanced auto-bot with real functionality
    // Start bot - uses Python server if connected, otherwise JS bot
    const startBot = async () => {
        if (botRunning) return;
        
        // Try Python bot server first
        if (usePythonBot && botServerConnected) {
            try {
                // Update config on server
                await fetch(`${BOT_SERVER_URL}/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        auto_accept: botConfig.autoAccept,
                        auto_solve: botConfig.autoSolve,
                        max_concurrent: botConfig.maxConcurrent,
                        accepted_types: botConfig.acceptedTypes,
                    })
                });
                
                // Start bot
                const res = await fetch(`${BOT_SERVER_URL}/start`, { method: 'POST' });
                const data = await res.json();
                
                if (data.success) {
                    setBotRunning(true);
                    addLog('[PYTHON BOT] Started via server!', 'success');
                    startLogPolling();
                    return;
                } else {
                    addLog(`[PYTHON BOT] Failed to start: ${data.error}`, 'error');
                }
            } catch (e) {
                addLog(`[PYTHON BOT] Server error: ${e.message}. Falling back to JS bot.`, 'warning');
            }
        }
        
        // Fallback to JS bot
        setBotRunning(true);
        addLog('[JS BOT] Started! Monitoring for orders...', 'success');
        addLog(`[JS BOT] Config: autoAccept=${botConfig.autoAccept}, autoSolve=${botConfig.autoSolve}, maxConcurrent=${botConfig.maxConcurrent}`, 'info');
        
        botIntervalRef.current = setInterval(async () => {
            // Fetch latest orders
            const latestOrders = await fetchOrders();
            const currentOrders = latestOrders || ordersRef.current;
            
            // Find eligible order (not own order, within deadline, not already processing, accepted type)
            const eligible = currentOrders.find(o => 
                o.issuer.toLowerCase() !== account?.toLowerCase() &&
                o.deadline > Date.now() &&
                !processingOrders.has(o.id) &&
                botConfig.acceptedTypes.includes(o.problemType)
            );
            
            if (eligible && myAccepted.filter(o => o.status === 1).length < botConfig.maxConcurrent) {
                addLog(`[JS BOT] Found eligible order #${eligible.id} (${PROBLEM_TYPES[eligible.problemType]?.name})`, 'info');
                await autoProcessOrder(eligible);
            }
        }, 5000);
    };

    // Stop bot
    const stopBot = async () => {
        // Try to stop Python bot server
        if (usePythonBot && botServerConnected) {
            try {
                await fetch(`${BOT_SERVER_URL}/stop`, { method: 'POST' });
                stopLogPolling();
            } catch (e) {
                console.error('Failed to stop server bot:', e);
            }
        }
        
        // Stop JS bot
        setBotRunning(false);
        if (botIntervalRef.current) {
            clearInterval(botIntervalRef.current);
            botIntervalRef.current = null;
        }
        addLog('[BOT] Stopped.', 'warning');
    };

    const formatTimeLeft = (deadline) => {
        const diff = deadline - Date.now();
        if (diff <= 0) return 'Expired';
        const minutes = Math.floor(diff / 60000);
        if (minutes > 60) return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
        return `${minutes}m`;
    };

    // Render accept button based on state
    const renderAcceptButton = (order) => {
        const isOwnOrder = order.issuer.toLowerCase() === account?.toLowerCase();
        const isAccepting = acceptingOrder === order.id;
        const isProcessing = processingOrders.has(order.id);
        
        if (isOwnOrder) {
            return (
                <span className="bg-gray-500/20 text-gray-400 px-3 py-1 rounded text-xs">
                    Your Order
                </span>
            );
        }
        
        if (isAccepting || isProcessing) {
            return (
                <button disabled className="bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded text-xs flex items-center gap-1">
                    <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing
                </button>
            );
        }
        
        return (
            <button 
                onClick={() => handleAccept(order.id)}
                className="bg-green-500/20 text-green-400 px-3 py-1 rounded text-xs hover:bg-green-500/30"
            >
                Accept
            </button>
        );
    };

    if (!account) {
        return (
            <div className="glass rounded-2xl p-6 text-center py-12">
                <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-400 mb-2">Connect Wallet</h3>
                <p className="text-gray-500">Connect your solver wallet to start</p>
            </div>
        );
    }

    if (!coreContract) {
        return (
            <div className="glass rounded-2xl p-6 text-center py-12">
                <svg className="w-16 h-16 mx-auto mb-4 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h3 className="text-lg font-medium text-yellow-400 mb-2">Network Issue</h3>
                <p className="text-gray-500">Please switch to the correct network (Sepolia) to use the Solver Dashboard.</p>
                <p className="text-gray-600 text-sm mt-2">Make sure MetaMask is connected to Sepolia Ethereum.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Solver Stats */}
            <div className="glass rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold flex items-center gap-2">
                        <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                        </svg>
                        Solver Dashboard
                    </h2>
                    <div className="flex gap-2">
                        {!botRunning ? (
                            <button onClick={startBot} className="bg-green-500/20 text-green-400 px-4 py-2 rounded-lg text-sm hover:bg-green-500/30 flex items-center gap-2">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                Start Bot
                            </button>
                        ) : (
                            <button onClick={stopBot} className="bg-red-500/20 text-red-400 px-4 py-2 rounded-lg text-sm hover:bg-red-500/30 flex items-center gap-2">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                                </svg>
                                Stop Bot
                            </button>
                        )}
                    </div>
                </div>

                {/* Balance & Stats */}
                <div className="grid grid-cols-5 gap-4 mb-4">
                    <div className="bg-dark-800/50 rounded-xl p-3 text-center">
                        <div className="text-xs text-gray-500 mb-1">ETH Balance</div>
                        <div className="text-lg font-bold text-blue-400">{parseFloat(solverBalance.eth).toFixed(4)}</div>
                    </div>
                    <div className="bg-dark-800/50 rounded-xl p-3 text-center">
                        <div className="text-xs text-gray-500 mb-1">USDC Balance</div>
                        <div className="text-lg font-bold text-green-400">${parseFloat(solverBalance.usdc).toFixed(2)}</div>
                    </div>
                    <div className="bg-dark-800/50 rounded-xl p-3 text-center">
                        <div className="text-xs text-gray-500 mb-1">USDC Allowance</div>
                        <div className={`text-lg font-bold ${parseFloat(usdcAllowance) > 10 ? 'text-green-400' : 'text-yellow-400'}`}>
                            ${parseFloat(usdcAllowance).toFixed(2)}
                        </div>
                    </div>
                    <div className="bg-dark-800/50 rounded-xl p-3 text-center">
                        <div className="text-xs text-gray-500 mb-1">Problems Solved</div>
                        <div className="text-lg font-bold text-purple-400">{stats.solved}</div>
                    </div>
                    <div className="bg-dark-800/50 rounded-xl p-3 text-center">
                        <div className="text-xs text-gray-500 mb-1">Bot Status</div>
                        <div className={`text-lg font-bold ${botRunning ? 'text-green-400' : 'text-gray-400'}`}>
                            {botRunning ? 'Running' : 'Stopped'}
                        </div>
                    </div>
                </div>

                {/* Approve Button if low allowance */}
                {parseFloat(usdcAllowance) < 10 && (
                    <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4 mb-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-yellow-400 font-medium">USDC Approval Required</p>
                                <p className="text-gray-500 text-sm">You need to approve USDC for the Escrow contract to accept orders.</p>
                            </div>
                            <button 
                                onClick={() => handleApprove('10000')}
                                disabled={approving}
                                className="bg-yellow-500/20 text-yellow-400 px-4 py-2 rounded-lg text-sm hover:bg-yellow-500/30 disabled:opacity-50 flex items-center gap-2"
                            >
                                {approving ? (
                                    <>
                                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Approving...
                                    </>
                                ) : 'Approve USDC'}
                            </button>
                        </div>
                    </div>
                )}

                {/* Bot Configuration */}
                <div className="bg-dark-800/50 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-gray-300">Bot Configuration</h4>
                        <div className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-1 rounded ${botServerConnected ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                                {botServerConnected ? 'Python Server Connected' : 'Python Server Offline'}
                            </span>
                            <button 
                                onClick={checkBotServer}
                                className="text-xs text-gray-500 hover:text-gray-400"
                            >
                                Refresh
                            </button>
                        </div>
                    </div>
                    <div className="grid grid-cols-4 gap-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={usePythonBot}
                                onChange={(e) => setUsePythonBot(e.target.checked)}
                                disabled={!botServerConnected}
                                className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-blue-500 focus:ring-blue-500 disabled:opacity-50"
                            />
                            <span className={`text-sm ${botServerConnected ? 'text-blue-400' : 'text-gray-500'}`}>Use Python SDK</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={botConfig.autoAccept}
                                onChange={(e) => setBotConfig(prev => ({ ...prev, autoAccept: e.target.checked }))}
                                className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-green-500 focus:ring-green-500"
                            />
                            <span className="text-sm text-gray-400">Auto Accept</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input 
                                type="checkbox" 
                                checked={botConfig.autoSolve}
                                onChange={(e) => setBotConfig(prev => ({ ...prev, autoSolve: e.target.checked }))}
                                className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-green-500 focus:ring-green-500"
                            />
                            <span className="text-sm text-gray-400">Auto Solve</span>
                        </label>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-400">Max Orders:</span>
                            <select 
                                value={botConfig.maxConcurrent}
                                onChange={(e) => setBotConfig(prev => ({ ...prev, maxConcurrent: parseInt(e.target.value) }))}
                                className="bg-dark-700 border border-dark-600 rounded px-2 py-1 text-sm text-gray-300"
                            >
                                {[1, 2, 3, 4, 5].map(n => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
                {/* Open Orders */}
                <div className="glass rounded-2xl p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold">Open Orders ({orders.length})</h3>
                        <button onClick={fetchOrders} className="text-primary-400 text-sm hover:text-primary-300">
                            {loading ? 'Loading...' : 'Refresh'}
                        </button>
                    </div>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                        {orders.length === 0 ? (
                            <p className="text-gray-500 text-sm text-center py-4">No open orders</p>
                        ) : (
                            orders.map(order => (
                                <div key={order.id} className="bg-dark-800/50 rounded-lg p-3 flex justify-between items-center">
                                    <div>
                                        <div className="text-sm font-medium">
                                            #{order.id} - {PROBLEM_TYPES[order.problemType]?.name}
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            ${order.reward} | {formatTimeLeft(order.deadline)}
                                        </div>
                                    </div>
                                    {renderAcceptButton(order)}
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* My Accepted Orders */}
                <div className="glass rounded-2xl p-5">
                    <h3 className="font-semibold mb-4">My Accepted Orders ({myAccepted.length})</h3>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                        {myAccepted.length === 0 ? (
                            <p className="text-gray-500 text-sm text-center py-4">No accepted orders</p>
                        ) : (
                            myAccepted.map(order => (
                                <div key={order.id} className="bg-dark-800/50 rounded-lg p-3">
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="text-sm font-medium">#{order.id} - {PROBLEM_TYPES[order.problemType]?.name}</span>
                                        <span className={`text-xs px-2 py-0.5 rounded ${
                                            order.status === 1 ? 'bg-blue-500/20 text-blue-400' :
                                            order.status === 2 ? 'bg-purple-500/20 text-purple-400' :
                                            order.status === 3 ? 'bg-yellow-500/20 text-yellow-400' :
                                            order.status === 4 ? 'bg-green-500/20 text-green-400' :
                                            'bg-gray-500/20 text-gray-400'
                                        }`}>
                                            {ORDER_STATUS[order.status]?.name}
                                        </span>
                                    </div>
                                    <div className="flex gap-2">
                                        {order.status === 1 && (
                                            <>
                                                <button 
                                                    onClick={async () => {
                                                        const result = await solveWithGPT(order.id, order.problemType, order.problemHash);
                                                        handleCommit(order.id, result.answer);
                                                    }}
                                                    className="flex-1 bg-purple-500/20 text-purple-400 px-2 py-1 rounded text-xs hover:bg-purple-500/30"
                                                >
                                                    Auto Solve (GPT)
                                                </button>
                                                <button 
                                                    onClick={() => {
                                                        const solution = prompt('Enter solution:');
                                                        if (solution) handleCommit(order.id, solution);
                                                    }}
                                                    className="flex-1 bg-blue-500/20 text-blue-400 px-2 py-1 rounded text-xs hover:bg-blue-500/30"
                                                >
                                                    Manual
                                                </button>
                                            </>
                                        )}
                                        {order.status === 2 && (
                                            pendingReveals[order.id] ? (
                                                <button 
                                                    onClick={() => handleReveal(order.id)}
                                                    className="flex-1 bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded text-xs hover:bg-yellow-500/30"
                                                >
                                                    Reveal Solution
                                                </button>
                                            ) : (
                                                <span className="text-xs text-gray-500">
                                                    Commit data lost - wait for timeout or contact support
                                                </span>
                                            )
                                        )}
                                        {order.status === 3 && (
                                            <span className="text-xs text-gray-500">
                                                Waiting for verification period...
                                            </span>
                                        )}
                                        {order.status === 4 && (
                                            <button 
                                                onClick={() => handleClaimReward(order.id)}
                                                className="flex-1 bg-green-500/20 text-green-400 px-2 py-1 rounded text-xs hover:bg-green-500/30"
                                            >
                                                Claim Reward
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Logs */}
            <div className="glass rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold">Activity Log</h3>
                    <button 
                        onClick={() => setLogs([])}
                        className="text-xs text-gray-500 hover:text-gray-400"
                    >
                        Clear
                    </button>
                </div>
                <div className="bg-dark-900/50 rounded-lg p-3 h-40 overflow-y-auto font-mono text-xs">
                    {(() => {
                        // Combine local logs and server logs
                        const allLogs = usePythonBot && botServerConnected && serverLogs.length > 0 
                            ? serverLogs 
                            : logs;
                        
                        if (allLogs.length === 0) {
                            return <p className="text-gray-500">No activity yet...</p>;
                        }
                        
                        return allLogs.map((log, i) => (
                            <div key={i} className={`${
                                log.type === 'error' ? 'text-red-400' :
                                log.type === 'success' ? 'text-green-400' :
                                log.type === 'warning' ? 'text-yellow-400' :
                                'text-gray-400'
                            }`}>
                                [{log.timestamp}] {log.message}
                            </div>
                        ));
                    })()}
                </div>
            </div>
        </div>
    );
}

export default SolverDashboard;
