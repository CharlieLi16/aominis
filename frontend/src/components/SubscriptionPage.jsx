import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';

// Subscription tier configurations
const SUBSCRIPTION_TIERS = [
    {
        id: 0,
        name: 'Free',
        price: 0,
        credits: 5,
        features: ['5 questions/month', 'Answer only', 'Platform Bot'],
        color: 'gray',
        popular: false
    },
    {
        id: 1,
        name: 'Study',
        price: 9.99,
        credits: 100,
        features: ['100 questions/month', 'Answer + Steps', 'Problem Pool', 'Auto-verification'],
        color: 'blue',
        popular: true
    },
    {
        id: 2,
        name: 'Study+',
        price: 14.99,
        credits: -1, // unlimited
        features: ['Unlimited questions', 'Answer + Steps', 'Premium Bots', 'Priority response', 'Wrong answer refund'],
        color: 'purple',
        popular: false
    },
    {
        id: 3,
        name: 'Expert',
        price: 24.99,
        credits: -1, // unlimited
        features: ['Unlimited questions', 'Everything in Study+', 'Human experts', '1-on-1 tutoring', '100% guarantee'],
        color: 'yellow',
        popular: false
    }
];

// Bot Server URL
// Bot server URL (optional - for testing)
const BOT_SERVER_URL = import.meta.env.VITE_BOT_SERVER_URL || 'http://localhost:5001';

function SubscriptionPage({ account, usdcContract, network }) {
    const [currentTier, setCurrentTier] = useState(null);
    const [subscription, setSubscription] = useState(null);
    const [creditsRemaining, setCreditsRemaining] = useState(0);
    const [loading, setLoading] = useState(false);
    const [subscribing, setSubscribing] = useState(null);

    // Fetch subscription status
    useEffect(() => {
        if (account) {
            fetchSubscriptionStatus();
        }
    }, [account]);

    const fetchSubscriptionStatus = async () => {
        // In production, this would fetch from SubscriptionManager contract
        // For now, use mock data
        try {
            // Mock subscription status
            const mockSub = {
                tier: 0, // FREE
                endTime: Date.now() + 30 * 24 * 60 * 60 * 1000,
                creditsRemaining: 3,
                creditsUsedThisMonth: 2
            };
            setSubscription(mockSub);
            setCurrentTier(mockSub.tier);
            setCreditsRemaining(mockSub.creditsRemaining);
        } catch (e) {
            console.error('Error fetching subscription:', e);
        }
    };

    const handleSubscribe = async (tier) => {
        if (!account) {
            alert('Please connect wallet first');
            return;
        }

        setSubscribing(tier.id);
        try {
            // In production, this would:
            // 1. Approve USDC for SubscriptionManager
            // 2. Call subscribe(tier) on SubscriptionManager contract
            
            if (tier.price > 0 && usdcContract) {
                // Mock: would approve and transfer USDC
                console.log(`Subscribing to ${tier.name} for $${tier.price}`);
            }

            // Mock success
            await new Promise(r => setTimeout(r, 2000));
            
            setCurrentTier(tier.id);
            setCreditsRemaining(tier.credits === -1 ? 999 : tier.credits);
            setSubscription({
                tier: tier.id,
                endTime: Date.now() + 30 * 24 * 60 * 60 * 1000,
                creditsRemaining: tier.credits === -1 ? 999 : tier.credits,
                creditsUsedThisMonth: 0
            });

            alert(`Successfully subscribed to ${tier.name}!`);
        } catch (e) {
            alert(`Subscription failed: ${e.message}`);
        } finally {
            setSubscribing(null);
        }
    };

    const formatEndDate = (timestamp) => {
        return new Date(timestamp).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    };

    return (
        <div className="space-y-6">
            {/* Current Subscription Status */}
            {subscription && (
                <div className="glass rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-semibold flex items-center gap-2">
                            <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
                            </svg>
                            Your Subscription
                        </h2>
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                            currentTier === 0 ? 'bg-gray-500/20 text-gray-400' :
                            currentTier === 1 ? 'bg-blue-500/20 text-blue-400' :
                            currentTier === 2 ? 'bg-purple-500/20 text-purple-400' :
                            'bg-yellow-500/20 text-yellow-400'
                        }`}>
                            {SUBSCRIPTION_TIERS[currentTier]?.name || 'Free'}
                        </span>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <div className="bg-dark-800/50 rounded-xl p-4 text-center">
                            <div className="text-2xl font-bold text-green-400">
                                {creditsRemaining === 999 ? '∞' : creditsRemaining}
                            </div>
                            <div className="text-xs text-gray-500 mt-1">Credits Remaining</div>
                        </div>
                        <div className="bg-dark-800/50 rounded-xl p-4 text-center">
                            <div className="text-2xl font-bold text-blue-400">
                                {subscription.creditsUsedThisMonth}
                            </div>
                            <div className="text-xs text-gray-500 mt-1">Used This Month</div>
                        </div>
                        <div className="bg-dark-800/50 rounded-xl p-4 text-center">
                            <div className="text-sm font-medium text-gray-300">
                                {formatEndDate(subscription.endTime)}
                            </div>
                            <div className="text-xs text-gray-500 mt-1">Renews On</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Subscription Tiers */}
            <div className="glass rounded-2xl p-6">
                <h2 className="text-xl font-semibold mb-6 text-center">Choose Your Plan</h2>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {SUBSCRIPTION_TIERS.map(tier => (
                        <div 
                            key={tier.id}
                            className={`relative rounded-xl p-5 border transition-all ${
                                currentTier === tier.id
                                    ? 'border-green-500/50 bg-green-500/10'
                                    : tier.popular
                                        ? 'border-blue-500/50 bg-blue-500/5'
                                        : 'border-dark-600 bg-dark-800/30 hover:border-dark-500'
                            }`}
                        >
                            {/* Popular badge */}
                            {tier.popular && (
                                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                                    <span className="bg-blue-500 text-white text-xs px-3 py-1 rounded-full font-medium">
                                        Most Popular
                                    </span>
                                </div>
                            )}

                            {/* Current badge */}
                            {currentTier === tier.id && (
                                <div className="absolute -top-3 right-4">
                                    <span className="bg-green-500 text-white text-xs px-3 py-1 rounded-full font-medium">
                                        Current
                                    </span>
                                </div>
                            )}

                            {/* Tier name */}
                            <h3 className={`text-lg font-semibold mb-2 ${
                                tier.color === 'gray' ? 'text-gray-400' :
                                tier.color === 'blue' ? 'text-blue-400' :
                                tier.color === 'purple' ? 'text-purple-400' :
                                'text-yellow-400'
                            }`}>
                                {tier.name}
                            </h3>

                            {/* Price */}
                            <div className="mb-4">
                                <span className="text-3xl font-bold text-white">
                                    ${tier.price}
                                </span>
                                {tier.price > 0 && (
                                    <span className="text-gray-500 text-sm">/month</span>
                                )}
                            </div>

                            {/* Credits */}
                            <div className="text-sm text-gray-400 mb-4">
                                {tier.credits === -1 ? 'Unlimited questions' : `${tier.credits} questions/month`}
                            </div>

                            {/* Features */}
                            <ul className="space-y-2 mb-6">
                                {tier.features.map((feature, idx) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-300">
                                        <svg className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                        {feature}
                                    </li>
                                ))}
                            </ul>

                            {/* Subscribe button */}
                            <button
                                onClick={() => handleSubscribe(tier)}
                                disabled={subscribing !== null || currentTier === tier.id}
                                className={`w-full py-2.5 rounded-lg font-medium transition-all ${
                                    currentTier === tier.id
                                        ? 'bg-green-500/20 text-green-400 cursor-default'
                                        : tier.popular
                                            ? 'bg-blue-500 text-white hover:bg-blue-600'
                                            : 'bg-dark-600 text-gray-300 hover:bg-dark-500'
                                } disabled:opacity-50`}
                            >
                                {subscribing === tier.id ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                        </svg>
                                        Processing...
                                    </span>
                                ) : currentTier === tier.id ? (
                                    'Current Plan'
                                ) : currentTier !== null && currentTier < tier.id ? (
                                    'Upgrade'
                                ) : (
                                    tier.price === 0 ? 'Get Started' : 'Subscribe'
                                )}
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            {/* Comparison with competitors */}
            <div className="glass rounded-2xl p-6">
                <h3 className="text-lg font-semibold mb-4">Why Ominis?</h3>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-dark-700">
                                <th className="text-left py-2 px-3 text-gray-400">Feature</th>
                                <th className="text-center py-2 px-3 text-gray-400">Chegg</th>
                                <th className="text-center py-2 px-3 text-gray-400">ChatGPT</th>
                                <th className="text-center py-2 px-3 text-green-400">Ominis</th>
                            </tr>
                        </thead>
                        <tbody className="text-gray-300">
                            <tr className="border-b border-dark-800">
                                <td className="py-2 px-3">Price</td>
                                <td className="text-center py-2 px-3">$15.95/mo</td>
                                <td className="text-center py-2 px-3">$20/mo</td>
                                <td className="text-center py-2 px-3 text-green-400">$9.99/mo</td>
                            </tr>
                            <tr className="border-b border-dark-800">
                                <td className="py-2 px-3">New questions</td>
                                <td className="text-center py-2 px-3 text-red-400">Limited</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes</td>
                            </tr>
                            <tr className="border-b border-dark-800">
                                <td className="py-2 px-3">Step-by-step</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes</td>
                            </tr>
                            <tr className="border-b border-dark-800">
                                <td className="py-2 px-3">Accuracy verified</td>
                                <td className="text-center py-2 px-3 text-red-400">No</td>
                                <td className="text-center py-2 px-3 text-red-400">No</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes</td>
                            </tr>
                            <tr>
                                <td className="py-2 px-3">Wrong answer refund</td>
                                <td className="text-center py-2 px-3 text-red-400">No</td>
                                <td className="text-center py-2 px-3 text-red-400">No</td>
                                <td className="text-center py-2 px-3 text-green-400">Yes*</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <p className="text-xs text-gray-500 mt-3">*Study+ and Expert tiers only</p>
            </div>
        </div>
    );
}

export default SubscriptionPage;
