import React, { useState, useEffect } from 'react';
import { PROBLEM_TYPES } from '../config';

// Bot Server URL
// Bot server URL (optional - for testing)
const BOT_SERVER_URL = import.meta.env.VITE_BOT_SERVER_URL || 'http://localhost:5001';

function BotProfile({ botAddress, account, onClose }) {
    const [bot, setBot] = useState(null);
    const [reviews, setReviews] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submittingReview, setSubmittingReview] = useState(false);
    const [newReview, setNewReview] = useState({ rating: 5, comment: '' });
    const [activeTab, setActiveTab] = useState('overview'); // overview, reviews, stats

    useEffect(() => {
        if (botAddress) {
            fetchBotData();
        }
    }, [botAddress]);

    const fetchBotData = async () => {
        setLoading(true);
        try {
            // In production, fetch from BotRegistry and RatingSystem contracts
            await new Promise(r => setTimeout(r, 500));
            
            // Mock bot data
            setBot({
                address: botAddress,
                name: 'MathGenius Pro',
                description: 'Specialized in derivatives and integrals with 99% accuracy. Built with advanced AI models trained on millions of calculus problems.',
                isPremium: true,
                supportedTypes: [0, 1, 2],
                isActive: true,
                totalSolved: 1543,
                avgRating: 4.8,
                ratingCount: 234,
                monthlyUsage: 456,
                monthlyEarnings: 234.56,
                owner: '0x9876...5432',
                registeredAt: Date.now() - 90 * 24 * 60 * 60 * 1000,
                successRate: 98.5,
                avgResponseTime: 12.3, // seconds
            });

            // Mock reviews
            setReviews([
                {
                    id: 1,
                    user: '0xabc...123',
                    rating: 5,
                    comment: 'Excellent solver! Got the correct answer with detailed steps. Highly recommend.',
                    timestamp: Date.now() - 2 * 24 * 60 * 60 * 1000,
                    orderId: 156,
                    isVerified: true
                },
                {
                    id: 2,
                    user: '0xdef...456',
                    rating: 4,
                    comment: 'Good but sometimes takes a bit longer for complex integrals.',
                    timestamp: Date.now() - 5 * 24 * 60 * 60 * 1000,
                    orderId: 142,
                    isVerified: true
                },
                {
                    id: 3,
                    user: '0x789...abc',
                    rating: 5,
                    comment: 'Perfect! Solved my differential equation problem in seconds.',
                    timestamp: Date.now() - 10 * 24 * 60 * 60 * 1000,
                    orderId: 128,
                    isVerified: true
                },
                {
                    id: 4,
                    user: '0x321...fed',
                    rating: 4,
                    comment: 'Very reliable solver. Steps are clear and easy to follow.',
                    timestamp: Date.now() - 15 * 24 * 60 * 60 * 1000,
                    orderId: 115,
                    isVerified: true
                }
            ]);
        } catch (e) {
            console.error('Error fetching bot data:', e);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmitReview = async () => {
        if (!account) {
            alert('Please connect wallet first');
            return;
        }
        if (!newReview.comment.trim()) {
            alert('Please enter a comment');
            return;
        }

        setSubmittingReview(true);
        try {
            // In production, call RatingSystem contract
            await new Promise(r => setTimeout(r, 1000));
            
            // Add to local reviews
            const review = {
                id: reviews.length + 1,
                user: account.slice(0, 6) + '...' + account.slice(-3),
                rating: newReview.rating,
                comment: newReview.comment,
                timestamp: Date.now(),
                orderId: null,
                isVerified: false
            };
            setReviews([review, ...reviews]);
            setNewReview({ rating: 5, comment: '' });
            alert('Review submitted successfully!');
        } catch (e) {
            alert(`Error submitting review: ${e.message}`);
        } finally {
            setSubmittingReview(false);
        }
    };

    const renderStars = (rating, size = 'md', interactive = false) => {
        const sizeClass = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-6 h-6' : 'w-5 h-5';
        const fullStars = Math.floor(rating);
        const hasHalf = rating % 1 >= 0.5;
        
        return (
            <div className="flex items-center gap-0.5">
                {[1, 2, 3, 4, 5].map((star) => (
                    <button
                        key={star}
                        type="button"
                        disabled={!interactive}
                        onClick={() => interactive && setNewReview({ ...newReview, rating: star })}
                        className={interactive ? 'cursor-pointer hover:scale-110 transition' : ''}
                    >
                        <svg 
                            className={`${sizeClass} ${
                                star <= (interactive ? newReview.rating : fullStars) ? 'text-yellow-400' : 
                                !interactive && star === fullStars + 1 && hasHalf ? 'text-yellow-400/50' : 
                                'text-gray-600'
                            }`} 
                            fill="currentColor" 
                            viewBox="0 0 20 20"
                        >
                            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                    </button>
                ))}
            </div>
        );
    };

    const formatDate = (timestamp) => {
        const now = Date.now();
        const diff = now - timestamp;
        const days = Math.floor(diff / (24 * 60 * 60 * 1000));
        
        if (days === 0) return 'Today';
        if (days === 1) return 'Yesterday';
        if (days < 7) return `${days} days ago`;
        if (days < 30) return `${Math.floor(days / 7)} weeks ago`;
        return `${Math.floor(days / 30)} months ago`;
    };

    if (loading) {
        return (
            <div className="glass rounded-2xl p-8 text-center">
                <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
                <p className="text-gray-400">Loading bot profile...</p>
            </div>
        );
    }

    if (!bot) {
        return (
            <div className="glass rounded-2xl p-8 text-center">
                <p className="text-gray-400">Bot not found</p>
            </div>
        );
    }

    return (
        <div className="glass rounded-2xl overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 p-6">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-2xl">
                            🤖
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h2 className="text-2xl font-bold text-white">{bot.name}</h2>
                                {bot.isPremium && (
                                    <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-0.5 rounded-full">
                                        Premium
                                    </span>
                                )}
                                {bot.isActive && (
                                    <span className="bg-green-500/20 text-green-400 text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                                        <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></span>
                                        Online
                                    </span>
                                )}
                            </div>
                            <div className="text-sm text-gray-400 mt-1">{bot.address}</div>
                            <div className="flex items-center gap-4 mt-2">
                                {renderStars(bot.avgRating)}
                                <span className="text-sm text-gray-400">({bot.ratingCount} reviews)</span>
                            </div>
                        </div>
                    </div>
                    {onClose && (
                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-white p-2"
                        >
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    )}
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-dark-700 px-6">
                <div className="flex gap-6">
                    {['overview', 'reviews', 'stats'].map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`py-3 text-sm font-medium border-b-2 transition ${
                                activeTab === tab
                                    ? 'text-blue-400 border-blue-400'
                                    : 'text-gray-400 border-transparent hover:text-gray-300'
                            }`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content */}
            <div className="p-6">
                {activeTab === 'overview' && (
                    <div className="space-y-6">
                        {/* Description */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-2">About</h3>
                            <p className="text-gray-300">{bot.description}</p>
                        </div>

                        {/* Supported Types */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-2">Supported Problem Types</h3>
                            <div className="flex flex-wrap gap-2">
                                {bot.supportedTypes.map(type => {
                                    const typeInfo = PROBLEM_TYPES.find(t => t.id === type);
                                    return (
                                        <span 
                                            key={type}
                                            className="bg-dark-700 text-gray-300 px-3 py-1.5 rounded-lg flex items-center gap-2"
                                        >
                                            <span className="text-blue-400">{typeInfo?.icon}</span>
                                            {typeInfo?.name}
                                        </span>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Quick Stats */}
                        <div className="grid grid-cols-3 gap-4">
                            <div className="bg-dark-800/50 rounded-xl p-4 text-center">
                                <div className="text-2xl font-bold text-green-400">{bot.totalSolved.toLocaleString()}</div>
                                <div className="text-xs text-gray-500 mt-1">Problems Solved</div>
                            </div>
                            <div className="bg-dark-800/50 rounded-xl p-4 text-center">
                                <div className="text-2xl font-bold text-blue-400">{bot.successRate}%</div>
                                <div className="text-xs text-gray-500 mt-1">Success Rate</div>
                            </div>
                            <div className="bg-dark-800/50 rounded-xl p-4 text-center">
                                <div className="text-2xl font-bold text-purple-400">{bot.avgResponseTime}s</div>
                                <div className="text-xs text-gray-500 mt-1">Avg Response</div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'reviews' && (
                    <div className="space-y-6">
                        {/* Write Review */}
                        <div className="bg-dark-800/30 rounded-xl p-4">
                            <h3 className="font-medium text-white mb-3">Write a Review</h3>
                            <div className="mb-3">
                                <label className="text-sm text-gray-400 mb-1 block">Rating</label>
                                {renderStars(newReview.rating, 'lg', true)}
                            </div>
                            <textarea
                                value={newReview.comment}
                                onChange={(e) => setNewReview({ ...newReview, comment: e.target.value })}
                                placeholder="Share your experience with this bot..."
                                className="w-full bg-dark-700 border border-dark-600 rounded-lg p-3 text-sm text-gray-300 resize-none h-24"
                            />
                            <button
                                onClick={handleSubmitReview}
                                disabled={submittingReview || !newReview.comment.trim()}
                                className="mt-3 bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-600 transition disabled:opacity-50"
                            >
                                {submittingReview ? 'Submitting...' : 'Submit Review'}
                            </button>
                        </div>

                        {/* Reviews List */}
                        <div className="space-y-4">
                            {reviews.map(review => (
                                <div key={review.id} className="border-b border-dark-700 pb-4">
                                    <div className="flex items-start justify-between mb-2">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center text-xs">
                                                {review.user.slice(0, 2)}
                                            </div>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-sm text-gray-300">{review.user}</span>
                                                    {review.isVerified && (
                                                        <span className="bg-green-500/20 text-green-400 text-xs px-1.5 py-0.5 rounded">
                                                            Verified
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    {renderStars(review.rating, 'sm')}
                                                </div>
                                            </div>
                                        </div>
                                        <span className="text-xs text-gray-500">{formatDate(review.timestamp)}</span>
                                    </div>
                                    <p className="text-sm text-gray-400 ml-11">{review.comment}</p>
                                    {review.orderId && (
                                        <div className="ml-11 mt-2 text-xs text-gray-500">
                                            Order #{review.orderId}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {activeTab === 'stats' && (
                    <div className="space-y-6">
                        {/* Performance Stats */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-3">Performance</h3>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-dark-800/50 rounded-xl p-4">
                                    <div className="text-sm text-gray-400 mb-1">Total Solved</div>
                                    <div className="text-2xl font-bold text-white">{bot.totalSolved.toLocaleString()}</div>
                                </div>
                                <div className="bg-dark-800/50 rounded-xl p-4">
                                    <div className="text-sm text-gray-400 mb-1">This Month</div>
                                    <div className="text-2xl font-bold text-white">{bot.monthlyUsage}</div>
                                </div>
                                <div className="bg-dark-800/50 rounded-xl p-4">
                                    <div className="text-sm text-gray-400 mb-1">Success Rate</div>
                                    <div className="text-2xl font-bold text-green-400">{bot.successRate}%</div>
                                </div>
                                <div className="bg-dark-800/50 rounded-xl p-4">
                                    <div className="text-sm text-gray-400 mb-1">Avg Response</div>
                                    <div className="text-2xl font-bold text-blue-400">{bot.avgResponseTime}s</div>
                                </div>
                            </div>
                        </div>

                        {/* Rating Breakdown */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-3">Rating Breakdown</h3>
                            <div className="space-y-2">
                                {[5, 4, 3, 2, 1].map(stars => {
                                    const count = reviews.filter(r => r.rating === stars).length;
                                    const percent = reviews.length > 0 ? (count / reviews.length) * 100 : 0;
                                    return (
                                        <div key={stars} className="flex items-center gap-3">
                                            <span className="text-sm text-gray-400 w-6">{stars}</span>
                                            <svg className="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                            </svg>
                                            <div className="flex-1 bg-dark-700 rounded-full h-2">
                                                <div 
                                                    className="bg-yellow-400 h-2 rounded-full"
                                                    style={{ width: `${percent}%` }}
                                                ></div>
                                            </div>
                                            <span className="text-sm text-gray-500 w-8">{count}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Bot Info */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-400 mb-3">Bot Information</h3>
                            <div className="bg-dark-800/50 rounded-xl p-4 space-y-3">
                                <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Owner</span>
                                    <span className="text-sm text-gray-300">{bot.owner}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Registered</span>
                                    <span className="text-sm text-gray-300">{formatDate(bot.registeredAt)}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-sm text-gray-400">Monthly Earnings</span>
                                    <span className="text-sm text-green-400">${bot.monthlyEarnings.toFixed(2)}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default BotProfile;
