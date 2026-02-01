import React from 'react';

function CreditsBar({ creditsRemaining, tier, onUpgrade }) {
    const isUnlimited = creditsRemaining === 999 || tier >= 2;
    const isLow = !isUnlimited && creditsRemaining < 5;
    const isEmpty = !isUnlimited && creditsRemaining === 0;

    return (
        <div className={`glass rounded-xl p-4 flex items-center justify-between ${
            isEmpty ? 'border-red-500/30 bg-red-500/5' :
            isLow ? 'border-yellow-500/30 bg-yellow-500/5' :
            ''
        }`}>
            <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    isEmpty ? 'bg-red-500/20' :
                    isLow ? 'bg-yellow-500/20' :
                    'bg-gradient-to-br from-green-500/20 to-blue-500/20'
                }`}>
                    {isEmpty ? (
                        <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    ) : (
                        <svg className={`w-5 h-5 ${isLow ? 'text-yellow-400' : 'text-green-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    )}
                </div>
                <div>
                    <div className={`text-sm ${
                        isEmpty ? 'text-red-400' :
                        isLow ? 'text-yellow-400' :
                        'text-gray-400'
                    }`}>
                        {isEmpty ? 'No Credits Left' :
                         isLow ? 'Credits Running Low' :
                         'Credits Remaining'}
                    </div>
                    <div className="text-xl font-bold text-white">
                        {isUnlimited ? (
                            <span className="flex items-center gap-2">
                                <span>∞</span>
                                <span className="text-xs text-purple-400 font-normal">Unlimited</span>
                            </span>
                        ) : (
                            <span className={isEmpty ? 'text-red-400' : isLow ? 'text-yellow-400' : ''}>
                                {creditsRemaining}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Progress bar for limited plans */}
            {!isUnlimited && tier <= 1 && (
                <div className="flex-1 mx-4 max-w-xs">
                    <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                        <div 
                            className={`h-full rounded-full transition-all ${
                                isEmpty ? 'bg-red-500' :
                                isLow ? 'bg-yellow-500' :
                                'bg-green-500'
                            }`}
                            style={{ 
                                width: `${Math.min(100, (creditsRemaining / (tier === 0 ? 5 : 100)) * 100)}%` 
                            }}
                        />
                    </div>
                    <div className="text-xs text-gray-500 mt-1 text-right">
                        {creditsRemaining} / {tier === 0 ? 5 : 100}
                    </div>
                </div>
            )}

            {/* Upgrade button */}
            {(isEmpty || isLow || tier < 2) && onUpgrade && (
                <button 
                    onClick={onUpgrade}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                        isEmpty ? 'bg-red-500 text-white hover:bg-red-600' :
                        isLow ? 'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30' :
                        'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'
                    }`}
                >
                    {isEmpty ? 'Get Credits Now' :
                     isLow ? 'Get More Credits' :
                     'Upgrade Plan'}
                </button>
            )}
        </div>
    );
}

export default CreditsBar;
