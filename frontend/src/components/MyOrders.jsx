import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import { PROBLEM_TYPES, TIME_TIERS, ORDER_STATUS } from '../config';
import SolutionSteps from './SolutionSteps';

const API_URL = import.meta.env.VITE_API_URL || '';

function MyOrders({ coreContract, account }) {
    const [orders, setOrders] = useState([]);
    const [solutions, setSolutions] = useState({}); // {orderId: solution}
    const [problems, setProblems] = useState({}); // {orderId: {text, type, ...}}
    const [loading, setLoading] = useState(false);
    const [tab, setTab] = useState('issued'); // issued, solving

    // Load saved problems from localStorage first, then fetch from API
    useEffect(() => {
        try {
            const saved = localStorage.getItem('ominis_problems');
            if (saved) {
                setProblems(JSON.parse(saved));
            }
        } catch (e) {
            console.error('Failed to load saved problems:', e);
        }
    }, []);

    // Fetch orders from blockchain
    useEffect(() => {
        if (coreContract && account) {
            fetchMyOrders();
        }
    }, [coreContract, account]);

    const fetchMyOrders = async () => {
        if (!coreContract || !account) return;
        
        setLoading(true);
        try {
            // Get ProblemPosted events for this user
            const filter = coreContract.filters.ProblemPosted(null, account);
            const events = await coreContract.queryFilter(filter, -10000); // Last 10000 blocks
            
            const fetchedOrders = [];
            for (const event of events) {
                try {
                    const orderId = event.args[0];
                    const order = await coreContract.getOrder(orderId);
                    
                    fetchedOrders.push({
                        id: Number(order.id),
                        issuer: order.issuer,
                        problemHash: order.problemHash,
                        problemType: Number(order.problemType),
                        timeTier: Number(order.timeTier),
                        status: Number(order.status),
                        reward: ethers.formatUnits(order.reward, 6),
                        createdAt: Number(order.createdAt),
                        deadline: Number(order.deadline) * 1000, // Convert to ms
                        solver: order.solver,
                    });
                } catch (e) {
                    console.error('Error fetching order:', e);
                }
            }
            
            setOrders(fetchedOrders.reverse()); // Newest first
            
            // Fetch solutions for revealed orders
            await fetchSolutions(fetchedOrders);
        } catch (e) {
            console.error('Error fetching orders:', e);
        } finally {
            setLoading(false);
        }
    };

    const fetchSolutions = async (orderList) => {
        if (!coreContract) return;
        
        const solutionMap = {};
        
        // Get SolutionRevealed events
        const filter = coreContract.filters.SolutionRevealed();
        const events = await coreContract.queryFilter(filter, -10000);
        
        for (const event of events) {
            const orderId = Number(event.args[0]);
            const solution = event.args[2]; // solution is the 3rd argument
            solutionMap[orderId] = solution;
        }
        
        setSolutions(solutionMap);
    };

    // Fetch problem text from API for orders not in localStorage
    const fetchProblemText = async (orderId, problemHash) => {
        // Skip if already have this problem
        if (problems[orderId]) return;

        try {
            // Try to fetch from API by hash (use query param format)
            const response = await fetch(`${API_URL}/api/problems?hash=${problemHash}`);
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.text) {
                    setProblems(prev => {
                        const updated = { ...prev, [orderId]: { text: data.text } };
                        // Also save to localStorage
                        localStorage.setItem('ominis_problems', JSON.stringify(updated));
                        return updated;
                    });
                }
            }
        } catch (e) {
            console.log(`Could not fetch problem ${orderId} from API:`, e);
        }
    };

    // Fetch missing problem texts when orders are loaded
    useEffect(() => {
        if (orders.length > 0) {
            orders.forEach(order => {
                if (!problems[order.id] && order.problemHash) {
                    fetchProblemText(order.id, order.problemHash);
                }
            });
        }
    }, [orders]);

    const handleCancel = async (orderId) => {
        if (!coreContract) return;
        try {
            const tx = await coreContract.cancelOrder(orderId);
            await tx.wait();
            fetchMyOrders(); // Refresh
        } catch (e) {
            alert('Cancel failed: ' + e.message);
        }
    };

    const handleClaimTimeout = async (orderId) => {
        if (!coreContract) return;
        try {
            const tx = await coreContract.claimTimeout(orderId);
            await tx.wait();
            fetchMyOrders();
        } catch (e) {
            alert('Claim timeout failed: ' + e.message);
        }
    };

    const getStatusBadge = (status) => {
        const statusInfo = ORDER_STATUS[status] || { name: 'Unknown', color: 'gray' };
        const colorClasses = {
            green: 'bg-green-500/20 text-green-400 border-green-500/30',
            blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
            purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
            yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
            red: 'bg-red-500/20 text-red-400 border-red-500/30',
            gray: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
        };
        return (
            <span className={`px-2 py-1 rounded-full text-xs border ${colorClasses[statusInfo.color]}`}>
                {statusInfo.name}
            </span>
        );
    };

    const formatTimeLeft = (deadline) => {
        const diff = deadline - Date.now();
        if (diff <= 0) return 'Expired';
        
        const minutes = Math.floor(diff / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        
        if (minutes > 60) {
            return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
        }
        return `${minutes}m ${seconds}s`;
    };

    if (!account) {
        return (
            <div className="glass rounded-2xl p-6 animate-slide-up">
                <div className="text-center py-12">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                    <h3 className="text-lg font-medium text-gray-400 mb-2">Connect Wallet</h3>
                    <p className="text-gray-500">Connect your wallet to view your orders</p>
                </div>
            </div>
        );
    }

    return (
        <div className="glass rounded-2xl p-6 animate-slide-up">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                    </svg>
                    <h2 className="text-xl font-semibold">My Orders</h2>
                </div>

                <button 
                    onClick={fetchMyOrders}
                    className="text-primary-400 hover:text-primary-300 text-sm flex items-center gap-1"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                    </svg>
                    {loading ? 'Loading...' : 'Refresh'}
                </button>
            </div>

            {/* Orders List */}
            <div className="space-y-3">
                {loading ? (
                    <div className="text-center py-12 text-gray-500">
                        <svg className="w-8 h-8 mx-auto mb-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                        <p>Loading orders...</p>
                    </div>
                ) : orders.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                        <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                        </svg>
                        <p>No problems posted yet</p>
                    </div>
                ) : (
                    orders.map(order => (
                        <div 
                            key={order.id}
                            className="bg-dark-800/50 border border-dark-700 rounded-xl p-4"
                        >
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center text-lg">
                                        {PROBLEM_TYPES[order.problemType]?.icon}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium">
                                            Order #{order.id} - {PROBLEM_TYPES[order.problemType]?.name}
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            {TIME_TIERS[order.timeTier]?.name} tier
                                        </div>
                                    </div>
                                </div>
                                {getStatusBadge(order.status)}
                            </div>

                            {/* Problem Text */}
                            {problems[order.id] && (
                                <div className="bg-dark-700/50 rounded-lg p-3 mb-3">
                                    <div className="text-xs text-gray-500 mb-1">Your Problem:</div>
                                    <div className="text-sm text-gray-200 whitespace-pre-wrap">
                                        {problems[order.id].text}
                                    </div>
                                </div>
                            )}

                            {/* Order details */}
                            <div className="mb-3 text-sm">
                                <div className="flex justify-between text-gray-400">
                                    <span>Reward:</span>
                                    <span className="text-green-400 font-medium">${order.reward} USDC</span>
                                </div>
                                <div className="flex justify-between text-gray-400">
                                    <span>Time left:</span>
                                    <span className={order.deadline < Date.now() ? 'text-red-400' : 'text-yellow-400'}>
                                        {formatTimeLeft(order.deadline)}
                                    </span>
                                </div>
                                {order.solver && order.solver !== '0x0000000000000000000000000000000000000000' && (
                                    <div className="flex justify-between text-gray-400">
                                        <span>Solver:</span>
                                        <span className="text-blue-400 font-mono text-xs">
                                            {order.solver.slice(0, 6)}...{order.solver.slice(-4)}
                                        </span>
                                    </div>
                                )}
                            </div>

                            {/* Show Solution with Steps if revealed (status 3, 4, or 5) */}
                            {(order.status >= 3 && order.status <= 5) && solutions[order.id] && (
                                <div className="mb-3">
                                    <SolutionSteps 
                                        orderId={order.id} 
                                        solution={solutions[order.id]}
                                        showFetch={true}
                                    />
                                </div>
                            )}

                            {/* Waiting for solution message */}
                            {order.status === 1 && (
                                <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mb-3 text-sm text-blue-400">
                                    Solver is working on your problem...
                                </div>
                            )}
                            {order.status === 2 && (
                                <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3 mb-3 text-sm text-purple-400">
                                    Solver has committed a solution, waiting for reveal...
                                </div>
                            )}

                            {/* Actions based on status */}
                            <div className="flex gap-2 justify-end">
                                {/* Status 0 = Open - can cancel */}
                                {order.status === 0 && (
                                    <button 
                                        onClick={() => handleCancel(order.id)}
                                        className="bg-gray-500/20 text-gray-400 px-3 py-1.5 rounded-lg text-sm hover:bg-gray-500/30"
                                    >
                                        Cancel
                                    </button>
                                )}
                                
                                {/* Expired and not resolved */}
                                {order.status === 0 && order.deadline < Date.now() && (
                                    <button 
                                        onClick={() => handleClaimTimeout(order.id)}
                                        className="bg-yellow-500/20 text-yellow-400 px-3 py-1.5 rounded-lg text-sm hover:bg-yellow-500/30"
                                    >
                                        Claim Timeout
                                    </button>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

export default MyOrders;
