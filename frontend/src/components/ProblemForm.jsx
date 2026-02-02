import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import { PROBLEM_TYPES, TIME_TIERS, NETWORKS } from '../config';
import MarkdownRenderer from './MarkdownRenderer';

// Solving method options
const SOLVING_METHODS = [
    { id: 0, name: 'Platform Bot', description: 'Fast AI solver', icon: '🤖' },
    { id: 2, name: 'Problem Pool', description: 'Random solver', icon: '🎲' },
    { id: 1, name: 'Choose Bot', description: 'Select specific bot', icon: '⭐', premium: true },
];

function ProblemForm({ account, coreContract, usdcContract, network, onError, subscription }) {
    const [problemText, setProblemText] = useState('');
    const [selectedTypeIndex, setSelectedTypeIndex] = useState(0); // index into PROBLEM_TYPES
    const [problemTypeLabelOverride, setProblemTypeLabelOverride] = useState(''); // optional custom label for GPT
    const [timeTier, setTimeTier] = useState(1); // Default to 5min
    const [price, setPrice] = useState('0');
    const [submitting, setSubmitting] = useState(false);
    const [approving, setApproving] = useState(false);
    const [allowance, setAllowance] = useState('0');
    const [txHash, setTxHash] = useState(null);
    
    // Subscription mode state
    const [useSubscription, setUseSubscription] = useState(true); // Default to subscription mode
    const [solvingMethod, setSolvingMethod] = useState(0); // 0=Platform, 1=Specific, 2=Pool
    const [selectedBot, setSelectedBot] = useState('0x0000000000000000000000000000000000000000');
    const [subscriptionMode, setSubscriptionMode] = useState(false);
    
    // Image OCR state — frontend calls Bot Server /api/ocr (API key on server only)
    const [imageProcessing, setImageProcessing] = useState(false);
    const [imagePreview, setImagePreview] = useState(null);
    
    // Problem textarea expand/collapse
    const [textareaExpanded, setTextareaExpanded] = useState(false);

    // Skill / custom GPT prompt (optional instructions appended to solver prompt)
    const [skillInstructions, setSkillInstructions] = useState('');
    const [skillSectionOpen, setSkillSectionOpen] = useState(false);

    const botServerUrl = import.meta.env.VITE_BOT_SERVER_URL || 'https://aominis-quantl.pythonanywhere.com';

    const problemType = PROBLEM_TYPES[selectedTypeIndex]?.id ?? 0;
    const problemTypeLabel = (problemTypeLabelOverride.trim() || PROBLEM_TYPES[selectedTypeIndex]?.promptLabel || '').trim() || undefined;

    // Check if subscription mode is enabled on contract
    useEffect(() => {
        const checkSubscriptionMode = async () => {
            if (!coreContract) return;
            try {
                const enabled = await coreContract.isSubscriptionModeEnabled();
                setSubscriptionMode(enabled);
                setUseSubscription(enabled);
            } catch (e) {
                console.log('Subscription mode not available:', e);
                setSubscriptionMode(false);
                setUseSubscription(false);
            }
        };
        checkSubscriptionMode();
    }, [coreContract]);

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

    // Handle image upload — frontend calls Bot Server /api/ocr (API key on server only)
    const handleImageUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            onError('Please upload an image file');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            onError('Image too large. Maximum size is 10MB');
            return;
        }
        
        setImageProcessing(true);
        
        try {
            const dataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            setImagePreview(dataUrl);
            
            const res = await fetch(`${botServerUrl}/api/ocr`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataUrl }),
            });
            
            const data = await res.json();
            if (!data.success) {
                onError(data.error || '图片识别服务暂不可用');
                return;
            }
            const extracted = (data.text || '').trim();
            if (extracted) {
                if (problemText.trim()) {
                    setProblemText(prev => prev + '\n\n' + extracted);
                } else {
                    setProblemText(extracted);
                }
            } else {
                onError('No problem text extracted. Try another image.');
            }
        } catch (err) {
            console.error('OCR error:', err);
            onError('图片识别服务暂不可用: ' + err.message);
        } finally {
            setImageProcessing(false);
            e.target.value = '';
        }
    };
    
    // Clear image preview
    const clearImagePreview = () => {
        setImagePreview(null);
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

        // Check allowance for non-subscription mode
        if (!useSubscription && parseFloat(allowance) < parseFloat(price)) {
            onError('Please approve USDC first');
            return;
        }

        setSubmitting(true);
        setTxHash(null);

        try {
            // Create problem hash from text
            const problemHash = ethers.keccak256(ethers.toUtf8Bytes(problemText));
            
            let tx;
            
            if (useSubscription && subscriptionMode) {
                // Subscription mode - use credits
                tx = await coreContract.postProblemWithSubscription(
                    problemHash,
                    problemType,
                    solvingMethod,
                    selectedBot
                );
            } else {
                // Classic mode - pay per problem
                tx = await coreContract.postProblem(
                    problemHash,
                    problemType,
                    timeTier
                );
            }
            
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
                        problemType: problemType,
                        problemTypeLabel: problemTypeLabel || undefined,
                        skillInstructions: skillInstructions.trim() || undefined
                    })
                });
            } catch (e) {
                console.log('Could not store problem on API:', e);
            }
            
            // Get orderId from event logs
            const iface = new ethers.Interface([
                "event ProblemPosted(uint256 indexed orderId, address indexed issuer, uint8 problemType, uint8 timeTier, uint256 reward)"
            ]);
            let orderId = null;
            for (const log of receipt.logs) {
                try {
                    const parsed = iface.parseLog(log);
                    if (parsed && parsed.name === 'ProblemPosted') {
                        orderId = parsed.args[0].toString();
                        // Save problem text to localStorage
                        const savedProblems = JSON.parse(localStorage.getItem('ominis_problems') || '{}');
                        savedProblems[orderId] = {
                            text: problemText,
                            type: problemType,
                            typeLabel: problemTypeLabel,
                            skillInstructions: skillInstructions.trim() || undefined,
                            tier: timeTier,
                            hash: problemHash,
                            timestamp: Date.now(),
                            solvingMethod: useSubscription ? solvingMethod : null
                        };
                        localStorage.setItem('ominis_problems', JSON.stringify(savedProblems));
                        break;
                    }
                } catch (e) {}
            }
            
            // Notify Bot Server to solve and submit (subscription mode uses webhook)
            if (useSubscription && orderId) {
                // Subscription mode: call webhook to solve immediately and submit to chain
                try {
                    console.log(`Calling webhook for order #${orderId}...`);
                    const webhookResponse = await fetch(`${botServerUrl}/webhook/problem`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            order_id: parseInt(orderId),
                            problem_hash: problemHash,
                            problem_text: problemText,
                            problem_type: problemType,
                            problem_type_label: problemTypeLabel || undefined,
                            skill_instructions: skillInstructions.trim() || undefined,
                            submit_to_chain: true
                        })
                    });
                    const webhookResult = await webhookResponse.json();
                    console.log('Webhook result:', webhookResult);
                    
                    if (webhookResult.success) {
                        console.log(`Solution: ${webhookResult.solution}`);
                        if (webhookResult.reveal_tx) {
                            console.log(`Submitted to chain! TX: ${webhookResult.reveal_tx}`);
                        }
                    }
                } catch (e) {
                    console.log('Webhook call failed:', e);
                }
            } else {
                // Pay-per-question mode: just store problem for bot polling
                try {
                    await fetch(`${botServerUrl}/problems`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            hash: problemHash,
                            text: problemText,
                            type: problemType,
                            type_label: problemTypeLabel || undefined,
                            skill_instructions: skillInstructions.trim() || undefined
                        })
                    });
                    console.log('Problem stored to Bot Server');
                } catch (e) {
                    console.log('Could not store problem on Bot Server:', e);
                }
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
                {/* Problem Type - compact, wrap */}
                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-300 mb-1.5">Problem Type</label>
                    <div className="flex flex-wrap gap-1.5">
                        {PROBLEM_TYPES.map((type, idx) => (
                            <button
                                key={`${type.id}-${type.name}-${idx}`}
                                type="button"
                                onClick={() => setSelectedTypeIndex(idx)}
                                className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm transition-all ${
                                    selectedTypeIndex === idx
                                        ? 'bg-blue-500/20 border border-blue-500/50 text-blue-400'
                                        : 'bg-dark-800/50 border border-dark-600 text-gray-400 hover:border-dark-500'
                                }`}
                            >
                                <span className="text-base leading-none">{type.icon}</span>
                                <span>{type.name}</span>
                            </button>
                        ))}
                    </div>
                    {(PROBLEM_TYPES[selectedTypeIndex]?.promptLabel === '' || PROBLEM_TYPES[selectedTypeIndex]?.name === 'Other') && (
                        <div className="mt-2">
                            <label className="block text-xs font-medium text-gray-400 mb-1">Problem type for AI (e.g. numerical analysis)</label>
                            <input
                                type="text"
                                value={problemTypeLabelOverride}
                                onChange={(e) => setProblemTypeLabelOverride(e.target.value)}
                                placeholder="e.g. numerical analysis, abstract algebra"
                                className="w-full max-w-xs bg-dark-800/50 border border-dark-600 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
                            />
                        </div>
                    )}
                </div>

                {/* Skill / Custom prompt - independent region to modify GPT instructions */}
                <div className="mb-4 rounded-xl border border-dark-600 bg-dark-800/30 overflow-hidden">
                    <button
                        type="button"
                        onClick={() => setSkillSectionOpen(!skillSectionOpen)}
                        className="w-full flex items-center justify-between px-4 py-3 text-left text-sm font-medium text-gray-300 hover:bg-dark-700/50 transition-colors"
                    >
                        <span className="flex items-center gap-2">
                            <span className="text-base">⚙</span>
                            Skill / Custom prompt
                        </span>
                        <svg className={`w-4 h-4 text-gray-500 transition-transform ${skillSectionOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                    {skillSectionOpen && (
                        <div className="px-4 pb-4 pt-0 border-t border-dark-600/50">
                            <p className="text-xs text-gray-500 mb-2">Optional instructions added to the solver prompt (e.g. &quot;Always use SI units&quot;, &quot;Explain each step briefly&quot;).</p>
                            <textarea
                                value={skillInstructions}
                                onChange={(e) => setSkillInstructions(e.target.value)}
                                placeholder="e.g. Use SI units. Keep steps concise. Prefer exact fractions over decimals."
                                rows={3}
                                className="w-full bg-dark-800/50 border border-dark-600 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-y min-h-[4rem]"
                            />
                        </div>
                    )}
                </div>

                {/* Problem Text + Preview - resizable, wrap, fit */}
                <div className="mb-6 flex flex-col gap-2 min-h-0">
                    <div className="flex items-center justify-between mb-1">
                        <label className="block text-sm font-medium text-gray-300">
                            Problem (Markdown or plain text)
                        </label>
                        
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setTextareaExpanded(!textareaExpanded)}
                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-gray-400 hover:text-gray-300 hover:bg-dark-700/50 border border-dark-600"
                                title={textareaExpanded ? 'Collapse' : 'Expand'}
                            >
                                {textareaExpanded ? (
                                    <>
                                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                        Collapse
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                        </svg>
                                        Expand
                                    </>
                                )}
                            </button>
                            {/* Image Upload Buttons */}
                            <label className={`cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                                imageProcessing 
                                    ? 'bg-gray-500/20 text-gray-400 cursor-wait'
                                    : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 border border-blue-500/30'
                            }`}>
                                {imageProcessing ? (
                                    <>
                                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                        </svg>
                                        Processing...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                        Upload Image
                                    </>
                                )}
                                <input
                                    type="file"
                                    accept="image/*"
                                    onChange={handleImageUpload}
                                    disabled={imageProcessing}
                                    className="hidden"
                                />
                            </label>
                            
                            {/* Camera button for mobile */}
                            <label className={`cursor-pointer flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                                imageProcessing 
                                    ? 'bg-gray-500/20 text-gray-400 cursor-wait'
                                    : 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 border border-purple-500/30'
                            }`}>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                <input
                                    type="file"
                                    accept="image/*"
                                    capture="environment"
                                    onChange={handleImageUpload}
                                    disabled={imageProcessing}
                                    className="hidden"
                                />
                            </label>
                        </div>
                    </div>
                    
                    {/* Image Preview */}
                    {imagePreview && (
                        <div className="mb-2 relative">
                            <img 
                                src={imagePreview} 
                                alt="Uploaded problem" 
                                className="max-h-32 rounded-lg border border-dark-600"
                            />
                            <button
                                type="button"
                                onClick={clearImagePreview}
                                className="absolute top-1 right-1 bg-dark-800/80 text-gray-400 hover:text-white p-1 rounded-full"
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    )}
                    
                    <textarea
                        value={problemText}
                        onChange={(e) => setProblemText(e.target.value)}
                        placeholder="**Problem:** Find the derivative of f(x) = x^2 + 3x&#10;&#10;Or use math: $x^2$ or $$\\int_0^1 x\\,dx$$&#10;&#10;Or upload/take a photo of your problem!"
                        className={`w-full resize-y bg-dark-800/50 border border-dark-600 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500 placeholder-gray-500 ${
                            textareaExpanded ? 'min-h-[18rem] max-h-[50vh]' : 'min-h-[7rem] max-h-[24rem]'
                        }`}
                    />
                    
                    {/* Markdown Preview */}
                    {problemText.trim() && (
                        <div className="min-h-0 flex flex-col max-h-[20rem] rounded-lg border border-dark-600 bg-dark-700/50 overflow-hidden">
                            <div className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 text-xs text-gray-500 border-b border-dark-600">
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                                Preview
                            </div>
                            <div className="flex-1 overflow-auto p-3 text-gray-200 break-words min-w-0 prose prose-invert prose-sm max-w-none">
                                <MarkdownRenderer text={problemText} />
                            </div>
                        </div>
                    )}
                    
                    <p className="text-xs text-gray-500">
                        Tip: Use **bold**, - lists, $...$ or $$...$$ for math. Expand or drag textarea to resize.
                    </p>
                </div>

                {/* Mode Toggle (if subscription is available) */}
                {subscriptionMode && (
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-300 mb-3">Payment Mode</label>
                        <div className="grid grid-cols-2 gap-2">
                            <button
                                type="button"
                                onClick={() => setUseSubscription(true)}
                                className={`p-3 rounded-xl text-center transition-all ${
                                    useSubscription
                                        ? 'bg-green-500/20 border-2 border-green-500/50 text-green-400'
                                        : 'bg-dark-800/50 border border-dark-600 text-gray-400 hover:border-dark-500'
                                }`}
                            >
                                <div className="text-lg">💎</div>
                                <div className="text-sm font-medium">Use Credits</div>
                                <div className="text-xs opacity-70">1 credit per question</div>
                            </button>
                            <button
                                type="button"
                                onClick={() => setUseSubscription(false)}
                                className={`p-3 rounded-xl text-center transition-all ${
                                    !useSubscription
                                        ? 'bg-yellow-500/20 border-2 border-yellow-500/50 text-yellow-400'
                                        : 'bg-dark-800/50 border border-dark-600 text-gray-400 hover:border-dark-500'
                                }`}
                            >
                                <div className="text-lg">💵</div>
                                <div className="text-sm font-medium">Pay Per Question</div>
                                <div className="text-xs opacity-70">Classic mode</div>
                            </button>
                        </div>
                    </div>
                )}

                {/* Solving Method (Subscription Mode) */}
                {useSubscription && subscriptionMode && (
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-300 mb-3">Solving Method</label>
                        <div className="grid grid-cols-3 gap-2">
                            {SOLVING_METHODS.map(method => (
                                <button
                                    key={method.id}
                                    type="button"
                                    onClick={() => setSolvingMethod(method.id)}
                                    disabled={method.premium && subscription?.tier < 2}
                                    className={`p-3 rounded-xl text-center transition-all ${
                                        solvingMethod === method.id
                                            ? 'bg-purple-500/20 border-2 border-purple-500/50 text-purple-400'
                                            : method.premium && subscription?.tier < 2
                                                ? 'bg-dark-900/50 border border-dark-700 text-gray-600 cursor-not-allowed'
                                                : 'bg-dark-800/50 border border-dark-600 text-gray-400 hover:border-dark-500'
                                    }`}
                                >
                                    <div className="text-xl mb-1">{method.icon}</div>
                                    <div className="text-sm font-medium">{method.name}</div>
                                    <div className="text-xs opacity-70">{method.description}</div>
                                    {method.premium && subscription?.tier < 2 && (
                                        <div className="text-xs text-purple-400 mt-1">Study+ required</div>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Time Tier (Classic Mode Only) */}
                {!useSubscription && (
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
                )}

                {/* Price/Cost Display */}
                <div className="mb-6 p-4 bg-dark-800/50 rounded-xl border border-dark-600">
                    <div className="flex justify-between items-center">
                        <span className="text-gray-400">
                            {useSubscription ? 'Cost:' : 'Price:'}
                        </span>
                        {useSubscription ? (
                            <span className="text-2xl font-bold text-green-400">
                                1 Credit
                            </span>
                        ) : (
                            <span className="text-2xl font-bold text-green-400">
                                ${parseFloat(price).toFixed(2)} USDC
                            </span>
                        )}
                    </div>
                </div>

                {/* Approval / Submit Button */}
                {!account ? (
                    <div className="text-center text-gray-400 py-4">
                        Connect wallet to submit problems
                    </div>
                ) : !useSubscription && needsApproval ? (
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
                        ) : useSubscription ? (
                            <>
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                                Submit (1 Credit)
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
