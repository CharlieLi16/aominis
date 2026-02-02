// Ominis Frontend Configuration

export const NETWORKS = {
    sepolia: {
        chainId: 11155111,
        chainIdHex: '0xaa36a7',
        name: 'Sepolia',
        rpc: 'https://ethereum-sepolia-rpc.publicnode.com',
        explorer: 'https://sepolia.etherscan.io',
        currency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
        usdc: '0x496e1D036D018C0930fBd199e30738efE0B4B753',
        contracts: {
            core: '0x62E49387FFc45F67079C147Ee4D4bB7d710767F0',
            orderBook: '0x9D662B02759C89748A0Cd1e40dab7925b267f0bb',
            escrow: '0xCD4284e0Ee4245F84c327D861Fb72C03ac354F8F',
            subscriptionManager: '0x9b07227938F62D206474A026a1551457bD1b05d1',
            botRegistry: '0x96e8d413d21081D1DD2949E580486945471a3113',
            ratingSystem: '0xfb4c8495Cb53dF5d1d4AA7883357c58d764B2870',
        }
    },
    arbitrum_sepolia: {
        chainId: 421614,
        chainIdHex: '0x66eee',
        name: 'Arbitrum Sepolia',
        rpc: 'https://sepolia-rollup.arbitrum.io/rpc',
        explorer: 'https://sepolia.arbiscan.io',
        currency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
        usdc: '',
        contracts: {
            core: '',
            orderBook: '',
            escrow: '',
        }
    },
    arbitrum_one: {
        chainId: 42161,
        chainIdHex: '0xa4b1',
        name: 'Arbitrum One',
        rpc: 'https://arb1.arbitrum.io/rpc',
        explorer: 'https://arbiscan.io',
        currency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
        usdc: '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
        contracts: {
            core: '',
            orderBook: '',
            escrow: '',
        }
    }
};

export const DEFAULT_NETWORK = 'sepolia';

export const PROBLEM_TYPES = [
    // Contract types 0-4 (calculus)
    { id: 0, name: 'Derivative', icon: '∂', promptLabel: 'derivative' },
    { id: 1, name: 'Integral', icon: '∫', promptLabel: 'integral' },
    { id: 2, name: 'Limit', icon: 'lim', promptLabel: 'limit' },
    { id: 3, name: 'Differential Eq', icon: 'dy/dx', promptLabel: 'differential equation' },
    { id: 4, name: 'Series', icon: 'Σ', promptLabel: 'series/summation' },
    // General math (on-chain as 0), prompt label for GPT
    { id: 0, name: 'Linear Algebra', icon: '⊕', promptLabel: 'linear algebra' },
    { id: 0, name: 'Statistics', icon: 'σ', promptLabel: 'statistics' },
    { id: 0, name: 'Probability', icon: 'P', promptLabel: 'probability' },
    { id: 0, name: 'Number Theory', icon: 'ℤ', promptLabel: 'number theory' },
    { id: 0, name: 'Geometry', icon: '△', promptLabel: 'geometry' },
    { id: 0, name: 'Other', icon: '?', promptLabel: '' },
];

// Type-specific examples (must match backend bot_server TYPE_EXAMPLES for preview)
export const TYPE_EXAMPLES = {
    'derivative': `Example for derivative of f(x) = x² + 3x:
STEPS:
1. Apply power rule to x²: d/dx(x²) = 2x => 2x
2. Apply constant multiple rule to 3x: d/dx(3x) = 3 => 3
3. Sum the derivatives => 2x + 3

ANSWER: f'(x) = 2x + 3`,
    'integral': `Example for integral ∫(x² + 1) dx:
STEPS:
1. Integrate x²: ∫ x² dx = x³/3 => x³/3
2. Integrate 1: ∫ 1 dx = x => x
3. Add constant of integration => x³/3 + x + C

ANSWER: x³/3 + x + C`,
    'limit': `Example for limit lim_{x→0} sin(x)/x:
STEPS:
1. Direct substitution gives 0/0 (indeterminate) => apply L'Hôpital
2. Differentiate numerator and denominator: cos(x)/1 => 1

ANSWER: 1`,
    'differential equation': `Example for y' - 2y = 0:
STEPS:
1. Homogeneous ODE: y' = 2y => dy/y = 2 dx
2. Integrate: ln|y| = 2x + C₁ => y = Ce^(2x)

ANSWER: y = Ce^(2x)`,
    'series/summation': `Example for Σ_{k=1}^{n} k:
STEPS:
1. Formula for sum of first n positive integers => n(n+1)/2

ANSWER: n(n+1)/2`,
    'linear algebra': `Example for row reduce to RREF and state solution:
STEPS:
1. [Describe first row operation] => [resulting matrix]
2. [Describe next row operation] => [resulting matrix]
3. [Continue until RREF] => [RREF matrix]
4. Interpret pivots: free variables, particular solution => [solution set or "inconsistent" / "unique solution"]

ANSWER: [Give the final answer: e.g. "Unique solution x=..., y=..., z=..." or "Inconsistent" or "Infinitely many solutions: x=..., y=... in terms of free variable(s)"]`,
    'statistics': `Example for a statistics problem:
STEPS:
1. [First step] => [Result]
2. [Next step] => [Result]

ANSWER: [Final numerical or symbolic answer with units/interpretation if needed]`,
    'probability': `Example for a probability problem:
STEPS:
1. [Identify sample space or model] => [Result]
2. [Compute probability] => [Result]

ANSWER: [Final probability, e.g. P(A) = ...]`,
    'number theory': `Example for a number theory problem:
STEPS:
1. [First step] => [Result]
2. [Next step] => [Result]

ANSWER: [Final answer: integer, congruence, or proof summary]`,
    'geometry': `Example for a geometry problem:
STEPS:
1. [First step] => [Result]
2. [Next step] => [Result]

ANSWER: [Final length/area/volume or relationship]`,
};

export function getExampleForType(typeName) {
    const key = (typeName || '').trim().toLowerCase();
    return TYPE_EXAMPLES[key] || `Example:
STEPS:
1. [First step] => [Result]
2. [Next step] => [Result]

ANSWER: [Final answer in simplest form]`;
}

export const TIME_TIERS = [
    { id: 0, name: '2 min', duration: 120, description: 'Fastest - Premium' },
    { id: 1, name: '5 min', duration: 300, description: 'Fast' },
    { id: 2, name: '15 min', duration: 900, description: 'Standard' },
    { id: 3, name: '1 hour', duration: 3600, description: 'Economy' },
];

export const ORDER_STATUS = {
    0: { name: 'Open', color: 'green' },
    1: { name: 'Accepted', color: 'blue' },
    2: { name: 'Committed', color: 'purple' },
    3: { name: 'Revealed', color: 'yellow' },
    4: { name: 'Verified', color: 'green' },
    5: { name: 'Challenged', color: 'red' },
    6: { name: 'Expired', color: 'gray' },
    7: { name: 'Cancelled', color: 'gray' },
    8: { name: 'Rejected', color: 'red' },
};

// Contract ABIs (minimal for frontend)
export const CORE_ABI = [
    "function postProblem(bytes32 problemHash, uint8 problemType, uint8 timeTier) external returns (uint256)",
    "function postProblemWithSubscription(bytes32 problemHash, uint8 problemType, uint8 target, address targetBot) external returns (uint256)",
    "function isSubscriptionModeEnabled() external view returns (bool)",
    "function acceptOrder(uint256 orderId) external",
    "function commitSolution(uint256 orderId, bytes32 commitHash) external",
    "function revealSolution(uint256 orderId, string solution, bytes32 salt) external",
    "function claimReward(uint256 orderId) external",
    "function claimTimeout(uint256 orderId) external",
    "function submitChallenge(uint256 orderId, string reason) external",
    "function cancelOrder(uint256 orderId) external",
    "function getOrder(uint256 orderId) external view returns (tuple(uint256 id, address issuer, bytes32 problemHash, uint8 problemType, uint8 timeTier, uint8 status, uint256 reward, uint256 createdAt, uint256 deadline, address solver))",
    "function getTierPrice(uint8 tier) external view returns (uint256)",
    "function getOrderBot(uint256 orderId) external view returns (address)",
    "event ProblemPosted(uint256 indexed orderId, address indexed issuer, uint8 problemType, uint8 timeTier, uint256 reward)",
    "event OrderAccepted(uint256 indexed orderId, address indexed solver)",
    "event SolutionRevealed(uint256 indexed orderId, address indexed solver, string solution)",
    "event OrderAssignedToBot(uint256 indexed orderId, address indexed bot, uint8 targetType)",
];

export const USDC_ABI = [
    "function approve(address spender, uint256 amount) external returns (bool)",
    "function allowance(address owner, address spender) external view returns (uint256)",
    "function balanceOf(address account) external view returns (uint256)",
];

// Subscription Manager ABI
export const SUBSCRIPTION_MANAGER_ABI = [
    "function subscribe(uint8 tier) external",
    "function renewSubscription() external",
    "function cancelSubscription() external",
    "function useCredit(address user) external returns (bool)",
    "function getUserSubscription(address user) external view returns (tuple(address user, uint8 tier, uint256 startTime, uint256 endTime, uint256 creditsRemaining, uint256 creditsUsedThisMonth, uint256 lastCreditReset))",
    "function getTierConfig(uint8 tier) external view returns (tuple(uint256 pricePerMonth, uint256 monthlyCredits, bool hasSteps, bool hasPremiumAccess, bool hasRefundGuarantee))",
    "function isSubscriptionActive(address user) external view returns (bool)",
    "function hasCreditsRemaining(address user) external view returns (bool)",
    "function hasPremiumAccess(address user) external view returns (bool)",
    "function getCreditsRemaining(address user) external view returns (uint256)",
    "function getTierPrice(uint8 tier) external view returns (uint256)",
    "event SubscriptionCreated(address indexed user, uint8 tier, uint256 endTime)",
    "event SubscriptionRenewed(address indexed user, uint8 tier, uint256 newEndTime)",
    "event CreditUsed(address indexed user, uint256 creditsRemaining)",
];

// Bot Registry ABI
export const BOT_REGISTRY_ABI = [
    "function registerBot(string name, string description, string webhookUrl, bool isPremium, uint8[] supportedTypes) external",
    "function updateBot(string name, string description, string webhookUrl, uint8[] supportedTypes) external",
    "function setBotStatus(bool isActive) external",
    "function getBotInfo(address botAddress) external view returns (tuple(address owner, string name, string description, string webhookUrl, bool isPremium, uint8[] supportedTypes, bool isActive, uint256 totalSolved, uint256 totalRating, uint256 ratingCount, uint256 monthlyUsage, uint256 registeredAt))",
    "function getTopBots(uint256 limit) external view returns (address[])",
    "function getBotsByType(uint8 problemType) external view returns (address[])",
    "function getAverageRating(address botAddress) external view returns (uint256)",
    "function isRegistered(address botAddress) external view returns (bool)",
    "function platformBot() external view returns (address)",
    "event BotRegistered(address indexed botAddress, address indexed owner, string name, bool isPremium)",
    "event BotStatusChanged(address indexed botAddress, bool isActive)",
];

// Rating System ABI
export const RATING_SYSTEM_ABI = [
    "function submitReview(uint256 orderId, uint8 rating, string comment) external returns (uint256)",
    "function submitGeneralReview(address bot, uint8 rating, string comment) external returns (uint256)",
    "function updateReview(uint256 reviewId, uint8 newRating, string newComment) external",
    "function getReview(uint256 reviewId) external view returns (tuple(address user, address bot, uint256 orderId, uint8 rating, string comment, uint256 timestamp, bool isVerified))",
    "function getBotReviews(address bot, uint256 offset, uint256 limit) external view returns (tuple(address user, address bot, uint256 orderId, uint8 rating, string comment, uint256 timestamp, bool isVerified)[])",
    "function getBotAverageRating(address bot) external view returns (uint256)",
    "function getBotReviewCount(address bot) external view returns (uint256)",
    "event ReviewSubmitted(uint256 indexed reviewId, address indexed user, address indexed bot, uint256 orderId, uint8 rating)",
];

// Subscription tiers
export const SUBSCRIPTION_TIERS = {
    FREE: { id: 0, name: 'Free', price: 0, credits: 5 },
    STUDY: { id: 1, name: 'Study', price: 9.99, credits: 100 },
    STUDY_PLUS: { id: 2, name: 'Study+', price: 14.99, credits: -1 },
    EXPERT: { id: 3, name: 'Expert', price: 24.99, credits: -1 },
};

// Extended Core ABI with subscription functions
export const CORE_ABI_EXTENDED = [
    ...CORE_ABI,
    "function postProblemWithSubscription(bytes32 problemHash, uint8 problemType, uint8 target, address targetBot) external returns (uint256)",
    "function getOrderBot(uint256 orderId) external view returns (address)",
    "function isSubscriptionModeEnabled() external view returns (bool)",
    "event OrderAssignedToBot(uint256 indexed orderId, address indexed bot, uint8 targetType)",
];
