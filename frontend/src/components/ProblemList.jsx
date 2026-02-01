import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import { PROBLEM_TYPES, TIME_TIERS, ORDER_STATUS } from '../config';

function ProblemList({ coreContract, account }) {
    const [orders, setOrders] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState('all'); // all, open

    // Fetch orders from blockchain
    useEffect(() => {
        if (coreContract) {
            fetchOrders();
        }
    }, [coreContract]);

    const fetchOrders = async () => {
        if (!coreContract) return;
        
        setLoading(true);
        try {
            // Get all ProblemPosted events
            const filter = coreContract.filters.ProblemPosted();
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
        } catch (e) {
            console.error('Error fetching orders:', e);
        } finally {
            setLoading(false);
        }
    };

    const handleAccept = async (orderId) => {
        if (!coreContract || !account) {
            alert('Please connect wallet first');
            return;
        }
        try {
            const tx = await coreContract.acceptOrder(orderId);
            await tx.wait();
            alert('Order accepted! Now solve and submit the solution.');
            fetchOrders();
        } catch (e) {
            alert('Accept failed: ' + e.message);
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

    // Filter orders
    const filteredOrders = orders.filter(order => {
        if (filter === 'open') return order.status === 0;
        return true;
    });

    return (
        <div className="glass rounded-2xl p-6 animate-slide-up">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <h2 className="text-xl font-semibold">Browse Problems</h2>
                </div>

                <div className="flex items-center gap-3">
                    {/* Filter */}
                    <div className="flex gap-2">
                        {['all', 'open'].map(f => (
                            <button
                                key={f}
                                onClick={() => setFilter(f)}
                                className={`px-3 py-1 rounded-lg text-sm ${
                                    filter === f
                                        ? 'bg-blue-500/20 text-blue-400'
                                        : 'text-gray-400 hover:text-gray-300'
                                }`}
                            >
                                {f.charAt(0).toUpperCase() + f.slice(1)}
                            </button>
                        ))}
                    </div>
                    
                    {/* Refresh */}
                    <button 
                        onClick={fetchOrders}
                        className="text-primary-400 hover:text-primary-300 text-sm flex items-center gap-1"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                        {loading ? 'Loading...' : 'Refresh'}
                    </button>
                </div>
            </div>

            {/* Info Banner */}
            <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
                <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 text-blue-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="text-sm text-blue-300">
                        <p className="font-medium">For Solver Bots</p>
                        <p className="text-blue-400/70">
                            This list shows available problems. Use the SDK to build automated solving bots 
                            that can accept and solve problems programmatically.
                        </p>
                    </div>
                </div>
            </div>

            {/* Orders List */}
            <div className="space-y-3">
                {loading ? (
                    <div className="text-center py-12 text-gray-500">
                        <svg className="w-8 h-8 mx-auto mb-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                        <p>Loading problems...</p>
                    </div>
                ) : filteredOrders.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                        <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p>No problems available</p>
                    </div>
                ) : (
                    filteredOrders.map(order => (
                        <div 
                            key={order.id}
                            className="bg-dark-800/50 border border-dark-700 rounded-xl p-4 hover:bg-dark-700/50 hover:border-dark-600 transition-all"
                        >
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center text-lg">
                                        {PROBLEM_TYPES[order.problemType]?.icon}
                                    </div>
                                    <div>
                                        <div className="font-medium">
                                            {PROBLEM_TYPES[order.problemType]?.name} Problem
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            Order #{order.id} - {TIME_TIERS[order.timeTier]?.name} tier
                                        </div>
                                    </div>
                                </div>
                                {getStatusBadge(order.status)}
                            </div>

                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4 text-sm">
                                    <div>
                                        <span className="text-gray-500">Reward: </span>
                                        <span className="text-green-400 font-medium">${order.reward}</span>
                                    </div>
                                    <div>
                                        <span className="text-gray-500">Time left: </span>
                                        <span className={order.deadline < Date.now() ? 'text-red-400' : 'text-yellow-400'}>
                                            {formatTimeLeft(order.deadline)}
                                        </span>
                                    </div>
                                    <div className="text-gray-500 text-xs">
                                        Issuer: {order.issuer.slice(0, 6)}...{order.issuer.slice(-4)}
                                    </div>
                                </div>
                                
                                {order.status === 0 && order.deadline > Date.now() && account && order.issuer.toLowerCase() !== account.toLowerCase() && (
                                    <button 
                                        onClick={() => handleAccept(order.id)}
                                        className="bg-green-500/20 text-green-400 px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-500/30 transition-all"
                                    >
                                        Accept & Solve
                                    </button>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Stats */}
            <div className="mt-6 flex justify-center gap-4 text-sm text-gray-500">
                <span>Total: {orders.length}</span>
                <span>Open: {orders.filter(o => o.status === 0).length}</span>
            </div>
        </div>
    );
}

export default ProblemList;
