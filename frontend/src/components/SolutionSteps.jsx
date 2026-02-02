import React, { useState, useEffect } from 'react';
import MarkdownRenderer from './MarkdownRenderer';

// Bot Server URL - same as SolverDashboard
// Bot server URL for fetching solution steps
const BOT_SERVER_URL = import.meta.env.VITE_BOT_SERVER_URL || 'http://localhost:5001';

/**
 * SolutionSteps - Displays step-by-step solution for an order
 * Fetches solution data from bot server and displays with verification status
 */
function SolutionSteps({ orderId, solution, showFetch = true }) {
    const [solutionData, setSolutionData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [expanded, setExpanded] = useState(false);

    // Fetch solution steps from bot server
    useEffect(() => {
        if (orderId && showFetch) {
            fetchSolutionSteps();
        }
    }, [orderId]);

    const fetchSolutionSteps = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${BOT_SERVER_URL}/solutions/${orderId}/steps`);
            const data = await res.json();
            if (data.success) {
                setSolutionData(data);
            } else {
                // No steps stored, just show the answer
                setSolutionData({
                    answer: solution,
                    steps: [],
                    verified: false,
                    verification_status: 'not_available'
                });
            }
        } catch (e) {
            console.error('Failed to fetch solution steps:', e);
            setError('Could not fetch solution details');
            // Fallback to just showing the answer
            setSolutionData({
                answer: solution,
                steps: [],
                verified: false,
                verification_status: 'not_available'
            });
        } finally {
            setLoading(false);
        }
    };

    // Get verification badge
    const getVerificationBadge = (status, verified) => {
        if (verified) {
            return (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-500/20 text-green-400 border border-green-500/30">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Verified
                </span>
            );
        }
        
        switch (status) {
            case 'pending':
                return (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                        </svg>
                        Verifying...
                    </span>
                );
            case 'failed':
                return (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-400 border border-red-500/30">
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                        Failed
                    </span>
                );
            default:
                return (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-500/20 text-gray-400 border border-gray-500/30">
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                        </svg>
                        Unverified
                    </span>
                );
        }
    };

    if (loading) {
        return (
            <div className="bg-dark-700/50 rounded-lg p-4 animate-pulse">
                <div className="h-4 bg-dark-600 rounded w-1/3 mb-3"></div>
                <div className="h-3 bg-dark-600 rounded w-full mb-2"></div>
                <div className="h-3 bg-dark-600 rounded w-2/3"></div>
            </div>
        );
    }

    // If no solution data and not loading, show simple answer
    if (!solutionData && solution) {
        return (
            <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-green-400 font-medium">Solution</span>
                    {getVerificationBadge('not_available', false)}
                </div>
                <div className="text-white text-sm break-words prose prose-invert prose-sm max-w-none">
                    <MarkdownRenderer text={solution} />
                </div>
            </div>
        );
    }

    if (!solutionData) return null;

    const hasSteps = solutionData.steps && solutionData.steps.length > 0;

    return (
        <div className="bg-gradient-to-br from-green-500/10 to-blue-500/10 border border-green-500/30 rounded-lg overflow-hidden">
            {/* Header with answer and verification status */}
            <div className="p-4 border-b border-dark-700/50">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-green-400 font-medium uppercase tracking-wider">
                        Final Answer
                    </span>
                    {getVerificationBadge(solutionData.verification_status, solutionData.verified)}
                </div>
                <div className="text-white text-lg font-bold break-words prose prose-invert prose-sm max-w-none">
                    <MarkdownRenderer text={solutionData.answer || solution} />
                </div>
            </div>

            {/* Steps section (collapsible) */}
            {hasSteps && (
                <>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="w-full px-4 py-2 flex items-center justify-between text-sm text-gray-400 hover:text-gray-300 hover:bg-dark-700/30 transition-colors"
                    >
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                            </svg>
                            View Solution Steps ({solutionData.steps.length} steps)
                        </span>
                        <svg 
                            className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} 
                            fill="none" 
                            stroke="currentColor" 
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>

                    {expanded && (
                        <div className="px-4 pb-4 space-y-3">
                            {solutionData.steps.map((step, index) => (
                                <div 
                                    key={index}
                                    className="flex gap-3 bg-dark-800/50 rounded-lg p-3"
                                >
                                    {/* Step number */}
                                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30 flex items-center justify-center text-sm font-bold text-blue-400">
                                        {step.step || index + 1}
                                    </div>
                                    
                                    {/* Step content */}
                                    <div className="flex-1 min-w-0">
                                        <div className="text-gray-300 text-sm prose prose-invert prose-sm max-w-none">
                                            <MarkdownRenderer text={step.content} />
                                        </div>
                                        {step.result && (
                                            <div className="mt-1 text-sm text-green-400 bg-dark-900/50 rounded px-2 py-1 prose prose-invert prose-sm max-w-none">
                                                <MarkdownRenderer text={step.result} />
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}

                            {/* Steps hash for verification */}
                            {solutionData.steps_hash && (
                                <div className="text-xs text-gray-500 pt-2 border-t border-dark-700/50">
                                    <span className="text-gray-600">Steps Hash: </span>
                                    <span className="font-mono">{solutionData.steps_hash.slice(0, 20)}...</span>
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}

            {/* No steps message */}
            {!hasSteps && (
                <div className="px-4 py-3 text-xs text-gray-500 bg-dark-800/30">
                    <svg className="w-4 h-4 inline-block mr-1 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Step-by-step solution not available for this order
                </div>
            )}

            {/* Error message */}
            {error && (
                <div className="px-4 py-2 text-xs text-red-400 bg-red-500/10">
                    {error}
                </div>
            )}
        </div>
    );
}

export default SolutionSteps;
