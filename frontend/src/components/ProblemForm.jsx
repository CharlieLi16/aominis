import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import { PROBLEM_TYPES, TIME_TIERS, NETWORKS } from '../config';

function ProblemForm({ account, coreContract, usdcContract, network, onError }) {
    const [problemText, setProblemText] = useState('');
    const [problemType, setProblemType] = useState(0);
    const [timeTier, setTimeTier] = useState(1); // Default to 5min
    const [price, setPrice] = useState('0');
    const [submitting, setSubmitting] = useState(false);
    const [approving, setApproving] = useState(false);
    const [allowance, setAllowance] = useState('0');
    const [txHash, setTxHash] = useState(null);

    // Get price for selected tier
    useEffect(() => {
        const getPrice = async () => {
            if (!coreContract) return;
            try {
                const tierPrice = await coreContract.getTierPrice(timeTier);
                setPrice(ethers.formatUnits(tierPrice, 6));
            } catch (err) {
                console.error('Failed to get price:', err);
            }
        };
        getPrice();
    }, [coreContract, timeTier]);

    // Check allowance
    useEffect(() => {
        const checkAllowance = async () => {
            if (!usdcContract || !account || !coreContract) return;
            try {
                const allowed = await usdcContract.allowance(account, await coreContract.getAddress());
                setAllowance(ethers.formatUnits(allowed, 6));
            } catch (err) {
                console.error('Failed to check allowance:', err);
            }
        };
        checkAllowance();
    }, [usdcContract, account, coreContract]);

    // Approve USDC
    const handleApprove = async () => {
        if (!usdcContract || !coreContract) return;
        
        setApproving(true);
        try {
            const tx = await usdcContract.approve(
                await coreContract.getAddress(),
                ethers.parseUnits('1000000', 6) // Approve 1M USDC
            );
            await tx.wait();
            setAllowance('1000000');
        } catch (err) {
            onError(err.message);
        } finally {
            setApproving(false);
        }
    };

    // Submit problem
    const handleSubmit = async (e) => {
        e.preventDefault();
        
        if (!account) {
            onError('Please connect wallet first');
            return;
        }
        
        if (!problemText.trim()) {
            onError('Please enter a problem');
            return;
        }

        if (!coreContract) {
            onError('Contracts not loaded');
            return;
        }

        // Check allowance
        if (parseFloat(allowance) < parseFloat(price)) {
            onError('Please approve USDC first');
            return;
        }

        setSubmitting(true);
        setTxHash(null);

        try {
            // Create problem hash from text
            const problemHash = ethers.keccak256(ethers.toUtf8Bytes(problemText));
            
            const tx = await coreContract.postProblem(
                problemHash,
                problemType,
                timeTier
            );
            
            setTxHash(tx.hash);
            const receipt = await tx.wait();
            
            // Store problem text on platform API for solvers to access
            try {
                const apiUrl = import.meta.env.VITE_API_URL || '';
                await fetch(`${apiUrl}/api/problems`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        problemHash: problemHash,
                        problemText: problemText,
                        problemType: problemType
                    })
                });
            } catch (e) {
                console.log('Could not store problem on API:', e);
            }
            
            // Get orderId from event logs
            const iface = new ethers.Interface([
                "event ProblemPosted(uint256 indexed orderId, address indexed issuer, uint8 problemType, uint8 timeTier, uint256 reward)"
            ]);
            for (const log of receipt.logs) {
                try {
                    const parsed = iface.parseLog(log);
                    if (parsed && parsed.name === 'ProblemPosted') {
                        const orderId = parsed.args[0].toString();
                        // Save problem text to localStorage
                        const savedProblems = JSON.parse(localStorage.getItem('ominis_problems') || '{}');
                        savedProblems[orderId] = {
                            text: problemText,
                            type: problemType,
                            tier: timeTier,
                            hash: problemHash,
                            timestamp: Date.now()
                        };
                        localStorage.setItem('ominis_problems', JSON.stringify(savedProblems));
                        break;
                    }
                } catch (e) {}
            }
            
            // Clear form
            setProblemText('');
            
        } catch (err) {
            onError(err.message);
        } finally {
            setSubmitting(false);
        }
    };

    const needsApproval = parseFloat(allowance) < parseFloat(price);
    const networkConfig = NETWORKS[network];

    return (
        <div className="glass rounded-2xl p-6 animate-slide-up">
            <div className="flex items-center gap-2 mb-6">
                <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                <h2 className="text-xl font-semibold">Submit a Problem</h2>
            </div>

            <form onSubmit={handleSubmit}>
                {/* Problem Type */}
                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-300 mb-3">Problem Type</label>
                    <div className="grid grid-cols-5 gap-2">
                        {PROBLEM_TYPES.map(type => (
                            <button
                                key={type.id}
                                type="button"
                                onClick={() => setProblemType(type.id)}
                                className={`p-3 rounded-xl text-center transition-all ${
                                    problemType === type.id
                                        ? 'bg-blue-500/20 border-2 border-blue-500/50 text-blue-400'
                                        : 'bg-dark-800/50 border border-dark-600 text-gray-400 hover:border-dark-500'
                                }`}
                            >
                                <div className="text-xl mb-1">{type.icon}</div>
                                <div className="text-xs">{type.name}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Problem Text */}
                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                        Problem (LaTeX or plain text)
                    </label>
                    <textarea
                        value={problemText}
                        onChange={(e) => setProblemText(e.target.value)}
                        placeholder="Find the derivative of f(x) = x^2 + 3x - 5"
                        className="w-full bg-dark-800/50 border border-dark-600 rounded-xl px-4 py-3 text-sm h-32 resize-y focus:outline-none focus:border-blue-500 placeholder-gray-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                        Tip: Use ^ for exponents, * for multiplication
                    </p>
                </div>

                {/* Time Tier */}
                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-300 mb-3">
                        Time Limit (faster = more expensive)
                    </label>
                    <div className="grid grid-cols-4 gap-2">
                        {TIME_TIERS.map(tier => (
                            <button
                                key={tier.id}
                                type="button"
                                onClick={() => setTimeTier(tier.id)}
                                className={`p-3 rounded-xl text-center transition-all ${
                                    timeTier === tier.id
                                        ? 'bg-purple-500/20 border-2 border-purple-500/50 text-purple-400'
                                        : 'bg-dark-800/50 border border-dark-600 text-gray-400 hover:border-dark-500'
                                }`}
                            >
                                <div className="text-lg font-bold">{tier.name}</div>
                                <div className="text-xs opacity-70">{tier.description}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Price Display */}
                <div className="mb-6 p-4 bg-dark-800/50 rounded-xl border border-dark-600">
                    <div className="flex justify-between items-center">
                        <span className="text-gray-400">Price:</span>
                        <span className="text-2xl font-bold text-green-400">
                            ${parseFloat(price).toFixed(2)} USDC
                        </span>
                    </div>
                </div>

                {/* Approval / Submit Button */}
                {!account ? (
                    <div className="text-center text-gray-400 py-4">
                        Connect wallet to submit problems
                    </div>
                ) : needsApproval ? (
                    <button
                        type="button"
                        onClick={handleApprove}
                        disabled={approving}
                        className="w-full bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-400 hover:to-orange-400 text-white px-4 py-4 rounded-xl font-semibold btn-glow disabled:opacity-50"
                    >
                        {approving ? 'Approving...' : 'Approve USDC'}
                    </button>
                ) : (
                    <button
                        type="submit"
                        disabled={submitting || !problemText.trim()}
                        className="w-full bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-400 hover:to-emerald-500 text-white px-4 py-4 rounded-xl font-semibold btn-glow disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {submitting ? (
                            <>
                                <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                Submitting...
                            </>
                        ) : (
                            <>
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                                Submit Problem (${parseFloat(price).toFixed(2)})
                            </>
                        )}
                    </button>
                )}

                {/* Transaction Hash */}
                {txHash && (
                    <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-xl">
                        <div className="flex items-center gap-2 text-green-400 text-sm">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <span>Submitted!</span>
                            <a 
                                href={`${networkConfig?.explorer}/tx/${txHash}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="ml-auto text-blue-400 hover:underline"
                            >
                                View TX
                            </a>
                        </div>
                    </div>
                )}
            </form>
        </div>
    );
}

export default ProblemForm;
