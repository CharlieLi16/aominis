import React, { useState, useEffect } from 'react';
import { PROBLEM_TYPES } from '../config';

// Bot Server URL
// Bot server URL (optional - for testing)
const BOT_SERVER_URL = import.meta.env.VITE_BOT_SERVER_URL || 'http://localhost:5001';

// Mock bot data (in production, fetch from BotRegistry contract)
const MOCK_BOTS = [
    {
        address: '0x1234...5678',
        name: 'MathGenius Pro',
        description: 'Specialized in derivatives and integrals with 99% accuracy',
        isPremium: true,
        supportedTypes: [0, 1, 2],
        isActive: true,
        totalSolved: 1543,
        avgRating: 4.8,
        ratingCount: 234
    },
    {
        address: '0xabcd...ef01',
        name: 'CalcMaster',
        description: 'Fast solver for all calculus problems',
        isPremium: false,
        supportedTypes: [0, 1, 2, 3, 4],
        isActive: true,
        totalSolved: 892,
        avgRating: 4.5,
        ratingCount: 156
    },
    {
        address: '0x9876...5432',
        name: 'DiffEq Expert',
        description: 'Expert in differential equations and series',
        isPremium: true,
        supportedTypes: [3, 4],
        isActive: true,
        totalSolved: 567,
        avgRating: 4.9,
        ratingCount: 89
    },
    {
        address: '0xfedc...ba98',
        name: 'QuickCalc',
        description: 'Fast answers for simple calculations',
        isPremium: false,
        supportedTypes: [0, 1, 2],
        isActive: true,
        totalSolved: 2341,
        avgRating: 4.2,
        ratingCount: 412
    }
];

function BotMarketplace({ 
    account, 
    subscription, 
    onSelectBot, 
    selectedType,
    creditsRemaining 
}) {
    const [bots, setBots] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedBot, setSelectedBot] = useState(null);
    const [sortBy, setSortBy] = useState('rating'); // rating, solved, name
    const [filterPremium, setFilterPremium] = useState(false);
    const [targetType, setTargetType] = useState('pool'); // pool, platform, specific

    useEffect(() => {
        fetchBots();
    }, []);

    const fetchBots = async () => {
        setLoading(true);
        try {
            // In production, fetch from BotRegistry contract
            // For now, use mock data
            await new Promise(r => setTimeout(r, 500));
            setBots(MOCK_BOTS);
        } catch (e) {
            console.error('Error fetching bots:', e);
        } finally {
            setLoading(false);
        }
    };

    const sortedBots = [...bots]
        .filter(bot => {
            // Filter by problem type support
            if (selectedType !== null && selectedType !== undefined) {
                if (!bot.supportedTypes.includes(selectedType)) return false;
            }
            // Filter premium
            if (filterPremium && !bot.isPremium) return false;
            return bot.isActive;
        })
        .sort((a, b) => {
            if (sortBy === 'rating') return b.avgRating - a.avgRating;
            if (sortBy === 'solved') return b.totalSolved - a.totalSolved;
            if (sortBy === 'name') return a.name.localeCompare(b.name);
            return 0;
        });

    const handleSelectBot = (bot) => {
        setSelectedBot(bot);
        if (onSelectBot) {
            onSelectBot({
                type: 'specific',
                bot: bot
            });
        }
    };

    const handleSelectTarget = (type) => {
        setTargetType(type);
        setSelectedBot(null);
        if (onSelectBot) {
            onSelectBot({
                type: type,
                bot: null
            });
        }
    };

    const canUsePremium = subscription?.tier >= 2; // Study+ or Expert

    const renderStars = (rating) => {
        const fullStars = Math.floor(rating);
        const hasHalf = rating % 1 >= 0.5;
        
        return (
            <div className="flex items-center gap-0.5">
                {[...Array(5)].map((_, i) => (
                    <svg 
                        key={i} 
                        className={`w-4 h-4 ${
                            i < fullStars ? 'text-yellow-400' : 
                            i === fullStars && hasHalf ? 'text-yellow-400/50' : 
                            'text-gray-600'
                        }`} 
                        fill="currentColor" 
                        viewBox="0 0 20 20"
                    >
                        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                ))}
                <span className="text-sm text-gray-400 ml-1">({rating.toFixed(1)})</span>
            </div>
        );
    };

    return (
        <div className="space-y-6">
            {/* Credits Bar */}
            <div className="glass rounded-xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-blue-500/20 flex items-center justify-center">
                        <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                    <div>
                        <div className="text-sm text-gray-400">Credits Remaining</div>
                        <div className="text-xl font-bold text-white">
                            {creditsRemaining === 999 ? '∞' : creditsRemaining}
                        </div>
                    </div>
                </div>
                {creditsRemaining < 10 && creditsRemaining !== 999 && (
                    <a 
                        href="#subscribe" 
                        className="bg-blue-500/20 text-blue-400 px-4 py-2 rounded-lg text-sm hover:bg-blue-500/30 transition"
                    >
                        Get More Credits
                    </a>
                )}
            </div>

            {/* Solving Method Selection */}
            <div className="glass rounded-2xl p-6">
                <h3 className="text-lg font-semibold mb-4">Choose Solving Method</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    {/* Platform Bot */}
                    <button
                        onClick={() => handleSelectTarget('platform')}
                        className={`p-4 rounded-xl border transition-all text-left ${
                            targetType === 'platform'
                                ? 'border-green-500/50 bg-green-500/10'
                                : 'border-dark-600 bg-dark-800/30 hover:border-dark-500'
                        }`}
                    >
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                                <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                </svg>
                            </div>
                            <div>
                                <div className="font-medium text-white">Platform Bot</div>
                                <div className="text-xs text-gray-500">1 credit</div>
                            </div>
                        </div>
                        <p className="text-sm text-gray-400">Basic AI solver, fast response</p>
                    </button>

                    {/* Problem Pool */}
                    <button
                        onClick={() => handleSelectTarget('pool')}
                        className={`p-4 rounded-xl border transition-all text-left ${
                            targetType === 'pool'
                                ? 'border-blue-500/50 bg-blue-500/10'
                                : 'border-dark-600 bg-dark-800/30 hover:border-dark-500'
                        }`}
                    >
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                </svg>
                            </div>
                            <div>
                                <div className="font-medium text-white">Problem Pool</div>
                                <div className="text-xs text-gray-500">1 credit</div>
                            </div>
                        </div>
                        <p className="text-sm text-gray-400">Random solver, quick answers</p>
                    </button>

                    {/* Choose Bot */}
                    <button
                        onClick={() => handleSelectTarget('specific')}
                        disabled={!canUsePremium}
                        className={`p-4 rounded-xl border transition-all text-left ${
                            targetType === 'specific'
                                ? 'border-purple-500/50 bg-purple-500/10'
                                : !canUsePremium
                                    ? 'border-dark-700 bg-dark-900/50 opacity-60 cursor-not-allowed'
                                    : 'border-dark-600 bg-dark-800/30 hover:border-dark-500'
                        }`}
                    >
                        <div className="flex items-center gap-3 mb-2">
                            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                                <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                </svg>
                            </div>
                            <div>
                                <div className="font-medium text-white">Choose Bot</div>
                                <div className="text-xs text-gray-500">1 credit</div>
                            </div>
                        </div>
                        <p className="text-sm text-gray-400">
                            {canUsePremium ? 'Select from top-rated solvers' : 'Requires Study+ subscription'}
                        </p>
                        {!canUsePremium && (
                            <div className="mt-2 flex items-center gap-1 text-xs text-purple-400">
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                                </svg>
                                Upgrade to unlock
                            </div>
                        )}
                    </button>
                </div>

                {/* Bot List (when specific is selected) */}
                {targetType === 'specific' && canUsePremium && (
                    <div className="border-t border-dark-700 pt-6">
                        {/* Filters */}
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <select
                                    value={sortBy}
                                    onChange={(e) => setSortBy(e.target.value)}
                                    className="bg-dark-700 border border-dark-600 rounded-lg px-3 py-1.5 text-sm text-gray-300"
                                >
                                    <option value="rating">Sort by Rating</option>
                                    <option value="solved">Sort by Problems Solved</option>
                                    <option value="name">Sort by Name</option>
                                </select>
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={filterPremium}
                                        onChange={(e) => setFilterPremium(e.target.checked)}
                                        className="w-4 h-4 rounded bg-dark-700 border-dark-600 text-purple-500"
                                    />
                                    <span className="text-sm text-gray-400">Premium only</span>
                                </label>
                            </div>
                            <span className="text-sm text-gray-500">{sortedBots.length} bots</span>
                        </div>

                        {/* Bot Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {loading ? (
                                <div className="col-span-2 text-center py-8 text-gray-500">
                                    Loading bots...
                                </div>
                            ) : sortedBots.length === 0 ? (
                                <div className="col-span-2 text-center py-8 text-gray-500">
                                    No bots found
                                </div>
                            ) : (
                                sortedBots.map((bot, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleSelectBot(bot)}
                                        className={`p-4 rounded-xl border text-left transition-all ${
                                            selectedBot?.address === bot.address
                                                ? 'border-purple-500/50 bg-purple-500/10'
                                                : 'border-dark-600 bg-dark-800/30 hover:border-dark-500'
                                        }`}
                                    >
                                        <div className="flex items-start justify-between mb-2">
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium text-white">{bot.name}</span>
                                                    {bot.isPremium && (
                                                        <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-0.5 rounded-full">
                                                            Premium
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="text-xs text-gray-500 mt-1">
                                                    {bot.address}
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                {renderStars(bot.avgRating)}
                                                <div className="text-xs text-gray-500 mt-1">
                                                    {bot.ratingCount} reviews
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <p className="text-sm text-gray-400 mb-3">{bot.description}</p>
                                        
                                        <div className="flex items-center justify-between">
                                            <div className="flex gap-1">
                                                {bot.supportedTypes.map(type => (
                                                    <span 
                                                        key={type}
                                                        className="bg-dark-700 text-gray-400 text-xs px-2 py-0.5 rounded"
                                                    >
                                                        {PROBLEM_TYPES.find(t => t.id === type)?.icon || type}
                                                    </span>
                                                ))}
                                            </div>
                                            <span className="text-xs text-gray-500">
                                                {bot.totalSolved.toLocaleString()} solved
                                            </span>
                                        </div>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default BotMarketplace;
