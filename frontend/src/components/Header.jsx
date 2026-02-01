import React from 'react';
import { NETWORKS } from '../config';

function Header({ account, chainId, network, usdcBalance, onConnect, onDisconnect, onSwitchNetwork, loading }) {
    const networkConfig = NETWORKS[network];

    return (
        <header className="glass rounded-2xl p-4 mb-6 animate-slide-up">
            <div className="flex justify-between items-center">
                {/* Logo */}
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
                        <span className="text-xl">∫</span>
                    </div>
                    <div>
                        <h1 className="text-xl font-bold gradient-text">Ominis</h1>
                        <p className="text-xs text-gray-400">Calculus Solver Protocol</p>
                    </div>
                </div>

                {/* Right side */}
                <div className="flex items-center gap-4">
                    {/* Network selector */}
                    <select
                        value={network}
                        onChange={(e) => onSwitchNetwork(e.target.value)}
                        className="bg-dark-800/50 border border-dark-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                    >
                        <optgroup label="Testnets">
                            <option value="sepolia">Sepolia (ETH)</option>
                            <option value="arbitrum_sepolia">Arbitrum Sepolia</option>
                        </optgroup>
                        <optgroup label="Mainnets">
                            <option value="arbitrum_one">Arbitrum One</option>
                        </optgroup>
                    </select>

                    {/* Balance */}
                    {account && (
                        <div className="hidden md:block bg-dark-800/50 border border-dark-600 rounded-lg px-3 py-2">
                            <span className="text-xs text-gray-400">USDC: </span>
                            <span className="text-sm font-mono text-green-400">
                                ${parseFloat(usdcBalance).toFixed(2)}
                            </span>
                        </div>
                    )}

                    {/* Connect/Disconnect button */}
                    {account ? (
                        <div className="flex items-center gap-2">
                            <div className="flex items-center gap-2 bg-green-500/20 border border-green-500/30 rounded-xl px-4 py-2">
                                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse-slow"></div>
                                <span className="text-sm font-mono text-green-400">
                                    {account.slice(0, 6)}...{account.slice(-4)}
                                </span>
                            </div>
                            <button
                                onClick={onDisconnect}
                                className="bg-red-500/20 border border-red-500/30 hover:bg-red-500/30 text-red-400 px-3 py-2 rounded-xl text-sm transition-all"
                                title="Disconnect Wallet"
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                                </svg>
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={onConnect}
                            disabled={loading}
                            className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 text-white px-5 py-2.5 rounded-xl font-medium btn-glow flex items-center gap-2 disabled:opacity-50"
                        >
                            {loading ? (
                                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            ) : (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                                </svg>
                            )}
                            Connect Wallet
                        </button>
                    )}
                </div>
            </div>
        </header>
    );
}

export default Header;
