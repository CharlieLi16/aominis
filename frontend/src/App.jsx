import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import Header from './components/Header';
import ProblemForm from './components/ProblemForm';
import ProblemList from './components/ProblemList';
import MyOrders from './components/MyOrders';
import SolverDashboard from './components/SolverDashboard';
import SubscriptionPage from './components/SubscriptionPage';
import BotMarketplace from './components/BotMarketplace';
import BotProfile from './components/BotProfile';
import CreditsBar from './components/CreditsBar';
import { NETWORKS, DEFAULT_NETWORK, CORE_ABI, USDC_ABI } from './config';

function App() {
    // Wallet state
    const [account, setAccount] = useState(null);
    const [provider, setProvider] = useState(null);
    const [signer, setSigner] = useState(null);
    const [chainId, setChainId] = useState(null);
    const [network, setNetwork] = useState(DEFAULT_NETWORK);
    
    // Contract state
    const [coreContract, setCoreContract] = useState(null);
    const [usdcContract, setUsdcContract] = useState(null);
    const [usdcBalance, setUsdcBalance] = useState('0');
    
    // UI state - check URL for initial tab
    const getInitialTab = () => {
        const path = window.location.pathname;
        if (path === '/solver') return 'solver';
        if (path === '/browse') return 'browse';
        if (path === '/orders') return 'myorders';
        if (path === '/subscribe') return 'subscribe';
        if (path === '/marketplace') return 'marketplace';
        return 'submit';
    };
    const [activeTab, setActiveTab] = useState(getInitialTab());
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    
    // Subscription state
    const [subscription, setSubscription] = useState(null);
    const [creditsRemaining, setCreditsRemaining] = useState(5);
    const [selectedBotProfile, setSelectedBotProfile] = useState(null);

    // Update URL when tab changes
    const handleTabChange = (tabId) => {
        setActiveTab(tabId);
        setSelectedBotProfile(null); // Clear bot profile when changing tabs
        const paths = { 
            submit: '/', 
            browse: '/browse', 
            myorders: '/orders', 
            solver: '/solver',
            subscribe: '/subscribe',
            marketplace: '/marketplace'
        };
        window.history.pushState({}, '', paths[tabId] || '/');
    };

    // Connect wallet
    const connectWallet = async () => {
        if (!window.ethereum) {
            setError('Please install MetaMask');
            return;
        }

        try {
            setLoading(true);
            setError(null); // Clear previous errors
            
            const accounts = await window.ethereum.request({ 
                method: 'eth_requestAccounts' 
            });
            
            const web3Provider = new ethers.BrowserProvider(window.ethereum);
            const web3Signer = await web3Provider.getSigner();
            const networkInfo = await web3Provider.getNetwork();
            const connectedChainId = Number(networkInfo.chainId);
            
            setAccount(accounts[0]);
            setProvider(web3Provider);
            setSigner(web3Signer);
            setChainId(connectedChainId);
            
            // Save connection state to localStorage
            localStorage.setItem('walletConnected', 'true');
            localStorage.setItem('lastAccount', accounts[0]);
            
            // Setup contracts with chain ID check
            await setupContracts(web3Signer, connectedChainId);
            
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    // Disconnect wallet
    const disconnectWallet = () => {
        setAccount(null);
        setProvider(null);
        setSigner(null);
        setChainId(null);
        setCoreContract(null);
        setUsdcContract(null);
        setUsdcBalance('0');
        
        // Clear localStorage
        localStorage.removeItem('walletConnected');
        localStorage.removeItem('lastAccount');
    };

    // Auto-reconnect on page load if previously connected
    useEffect(() => {
        const autoConnect = async () => {
            const wasConnected = localStorage.getItem('walletConnected');
            if (wasConnected && window.ethereum) {
                try {
                    // Check if still has permission
                    const accounts = await window.ethereum.request({ 
                        method: 'eth_accounts' 
                    });
                    if (accounts.length > 0) {
                        // Auto reconnect
                        await connectWallet();
                    } else {
                        // Permission revoked, clear storage
                        localStorage.removeItem('walletConnected');
                        localStorage.removeItem('lastAccount');
                    }
                } catch (err) {
                    console.log('Auto-connect failed:', err);
                }
            }
        };
        autoConnect();
    }, []);

    // Setup contracts
    const setupContracts = async (signer, connectedChainId) => {
        const networkConfig = NETWORKS[network];
        if (!networkConfig?.contracts?.core) {
            console.log('Contracts not deployed yet');
            return;
        }

        // Check if connected to the right network
        if (connectedChainId && connectedChainId !== networkConfig.chainId) {
            setError(`Wrong network! Please switch to ${networkConfig.name} (Chain ID: ${networkConfig.chainId}). You are on Chain ID: ${connectedChainId}`);
            return;
        }

        try {
            const core = new ethers.Contract(
                networkConfig.contracts.core,
                CORE_ABI,
                signer
            );
            setCoreContract(core);

            if (networkConfig.usdc) {
                const usdc = new ethers.Contract(
                    networkConfig.usdc,
                    USDC_ABI,
                    signer
                );
                setUsdcContract(usdc);

                // Get USDC balance with error handling
                try {
                    const balance = await usdc.balanceOf(await signer.getAddress());
                    setUsdcBalance(ethers.formatUnits(balance, 6));
                } catch (e) {
                    console.error('Error fetching USDC balance:', e);
                    setUsdcBalance('0');
                }
            }
        } catch (e) {
            setError(`Failed to setup contracts: ${e.message}`);
        }
    };

    // Switch network
    const switchNetwork = async (networkKey) => {
        const networkConfig = NETWORKS[networkKey];
        if (!networkConfig) return;

        try {
            await window.ethereum.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: networkConfig.chainIdHex }]
            });
            setNetwork(networkKey);
        } catch (err) {
            if (err.code === 4902) {
                await window.ethereum.request({
                    method: 'wallet_addEthereumChain',
                    params: [{
                        chainId: networkConfig.chainIdHex,
                        chainName: networkConfig.name,
                        nativeCurrency: networkConfig.currency,
                        rpcUrls: [networkConfig.rpc],
                        blockExplorerUrls: [networkConfig.explorer]
                    }]
                });
            }
        }
    };

    // Listen for account/chain changes
    useEffect(() => {
        if (window.ethereum) {
            window.ethereum.on('accountsChanged', (accounts) => {
                if (accounts.length === 0) {
                    setAccount(null);
                    setSigner(null);
                } else {
                    setAccount(accounts[0]);
                }
            });

            window.ethereum.on('chainChanged', () => {
                window.location.reload();
            });
        }
    }, []);

    // Handle browser back/forward
    useEffect(() => {
        const handlePopState = () => {
            setActiveTab(getInitialTab());
        };
        window.addEventListener('popstate', handlePopState);
        return () => window.removeEventListener('popstate', handlePopState);
    }, []);

    return (
        <div className="min-h-screen bg-dark-950 text-gray-100">
            {/* Background */}
            <div className="fixed inset-0 bg-gradient-to-br from-dark-900 via-dark-950 to-dark-900 -z-10"></div>
            <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-transparent -z-10"></div>

            <div className="container mx-auto px-4 py-6 max-w-6xl">
                {/* Header */}
                <Header 
                    account={account}
                    chainId={chainId}
                    network={network}
                    usdcBalance={usdcBalance}
                    onConnect={connectWallet}
                    onDisconnect={disconnectWallet}
                    onSwitchNetwork={switchNetwork}
                    loading={loading}
                />

                {/* Network mismatch warning */}
                {account && chainId && NETWORKS[network] && chainId !== NETWORKS[network].chainId && (
                    <div className="glass rounded-xl p-4 mb-6 border-yellow-500/30 bg-yellow-500/10">
                        <div className="flex items-center gap-2 text-yellow-400">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <span>
                                Wrong network! You're on Chain ID {chainId}, but need <strong>{NETWORKS[network].name}</strong> (Chain ID: {NETWORKS[network].chainId}).
                            </span>
                            <button 
                                onClick={() => switchNetwork(network)}
                                className="ml-auto bg-yellow-500/20 px-3 py-1 rounded text-sm hover:bg-yellow-500/30"
                            >
                                Switch Network
                            </button>
                        </div>
                    </div>
                )}

                {/* Error display */}
                {error && (
                    <div className="glass rounded-xl p-4 mb-6 border-red-500/30 bg-red-500/10">
                        <div className="flex items-center gap-2 text-red-400">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{error}</span>
                            <button onClick={() => setError(null)} className="ml-auto">×</button>
                        </div>
                    </div>
                )}

                {/* Tab Navigation */}
                <div className="glass rounded-xl p-1 mb-6 flex flex-wrap gap-1">
                    {[
                        { id: 'submit', label: 'Submit', icon: '📝' },
                        { id: 'marketplace', label: 'Bots', icon: '🤖' },
                        { id: 'browse', label: 'Browse', icon: '🔍' },
                        { id: 'myorders', label: 'Orders', icon: '📋' },
                        { id: 'subscribe', label: 'Subscribe', icon: '💎' },
                        { id: 'solver', label: 'Solver', icon: '⚙️' },
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => handleTabChange(tab.id)}
                            className={`flex-1 min-w-[100px] py-3 px-3 rounded-lg text-sm font-medium transition-all ${
                                activeTab === tab.id
                                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                                    : 'text-gray-400 hover:text-gray-300 hover:bg-dark-700/50'
                            }`}
                        >
                            <span className="mr-1">{tab.icon}</span>
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Main Content */}
                {activeTab === 'submit' && (
                    <ProblemForm 
                        account={account}
                        coreContract={coreContract}
                        usdcContract={usdcContract}
                        network={network}
                        onError={setError}
                    />
                )}
                
                {activeTab === 'browse' && (
                    <ProblemList 
                        coreContract={coreContract}
                        account={account}
                    />
                )}
                
                {activeTab === 'myorders' && (
                    <MyOrders 
                        coreContract={coreContract}
                        account={account}
                    />
                )}

                {activeTab === 'solver' && (
                    <SolverDashboard
                        coreContract={coreContract}
                        usdcContract={usdcContract}
                        account={account}
                        network={network}
                    />
                )}

                {activeTab === 'subscribe' && (
                    <SubscriptionPage
                        account={account}
                        usdcContract={usdcContract}
                        network={network}
                    />
                )}

                {activeTab === 'marketplace' && (
                    <>
                        {selectedBotProfile ? (
                            <BotProfile
                                botAddress={selectedBotProfile}
                                account={account}
                                onClose={() => setSelectedBotProfile(null)}
                            />
                        ) : (
                            <>
                                <CreditsBar
                                    creditsRemaining={creditsRemaining}
                                    tier={subscription?.tier || 0}
                                    onUpgrade={() => handleTabChange('subscribe')}
                                />
                                <div className="mt-6">
                                    <BotMarketplace
                                        account={account}
                                        subscription={subscription}
                                        creditsRemaining={creditsRemaining}
                                        onSelectBot={(selection) => {
                                            if (selection.bot) {
                                                setSelectedBotProfile(selection.bot.address);
                                            }
                                        }}
                                    />
                                </div>
                            </>
                        )}
                    </>
                )}

                {/* Footer */}
                <footer className="text-center text-gray-500 text-xs mt-8 pb-4">
                    <p>Ominis Protocol • Decentralized Calculus Solving</p>
                </footer>
            </div>
        </div>
    );
}

export default App;
