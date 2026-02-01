# Ominis Solver Marketplace - Deployment Guide

## 项目状态

### 已完成
- [x] 智能合约 (SubscriptionManager, BotRegistry, RatingSystem)
- [x] CalcSolverCore 集成订阅模式
- [x] 前端 ProblemForm 支持 Solving Method 选择
- [x] Bot Server 部署到 PythonAnywhere
- [x] Vercel 前端部署

### 待完成
- [ ] 合约: `postProblemWithSubscription` 自动设置 ACCEPTED 状态
- [ ] Bot Server: 自动监听分配的订单并解题
- [ ] 测试完整流程

---

## 合约地址 (Sepolia)

```
USDC:               0x496e1D036D018C0930fBd199e30738efE0B4B753
Core (NEW):         0x62E49387FFc45F67079C147Ee4D4bB7d710767F0
OrderBook:          0x9D662B02759C89748A0Cd1e40dab7925b267f0bb
Escrow:             0xCD4284e0Ee4245F84c327D861Fb72C03ac354F8F
SolutionManager:    0x1D4e7970F7A709A33A319EE166E37C76e1178D13
Verifier:           0x905a2eC8E5448ce108E341895a980F1E24810ea0
BotRegistry:        0x96e8d413d21081D1DD2949E580486945471a3113
RatingSystem:       0xfb4c8495Cb53dF5d1d4AA7883357c58d764B2870
SubscriptionMgr:    0x9b07227938F62D206474A026a1551457bD1b05d1
```

---

## 待修改: CalcSolverCore.sol

文件: `contracts/CalcSolverCore.sol`

在 `postProblemWithSubscription` 函数中，第 224 行后添加:

```solidity
// 3. Create order (no payment needed, using subscription)
orderId = orderBook.postProblem(problemHash, problemType, TimeTier.T15min, msg.sender);

// NEW: 直接设置为 ACCEPTED 状态，不需要等待 accept
orderBook.setOrderSolver(orderId, assignedBot);
orderBook.updateOrderStatus(orderId, OrderStatus.ACCEPTED);
```

修改后需要:
1. `forge build` 编译
2. 重新部署 CalcSolverCore
3. 重新配置所有模块的 core 地址

---

## 待修改: bot_server.py

文件: `sdk/bot_server.py`

添加自动监听和解题功能:

```python
# ========== Auto-Solve for Assigned Orders ==========

import asyncio
from web3 import Web3

class AutoSolver:
    def __init__(self, sdk, bot_address):
        self.sdk = sdk
        self.bot_address = bot_address
        self.running = False
    
    async def check_assigned_orders(self):
        """检查分配给自己的订单"""
        # 获取 OrderAssignedToBot 事件
        # 过滤 bot == self.bot_address
        # 返回待处理的订单列表
        pass
    
    async def solve_order(self, order_id, problem_hash):
        """自动解题并提交"""
        # 1. 从 API 获取题目文本
        problem_text = await self.get_problem_text(problem_hash)
        
        # 2. 调用 GPT 解题
        solution = solve_with_gpt(problem_text)
        
        # 3. Commit solution
        salt = os.urandom(32)
        commit_hash = Web3.keccak(solution.encode() + salt)
        await self.sdk.commit_solution(order_id, commit_hash)
        
        # 4. Reveal solution
        await self.sdk.reveal_solution(order_id, solution, salt)
        
        return solution
    
    async def run_loop(self):
        """主循环"""
        self.running = True
        while self.running:
            try:
                orders = await self.check_assigned_orders()
                for order in orders:
                    await self.solve_order(order.id, order.problem_hash)
            except Exception as e:
                logger.error(f"Auto-solve error: {e}")
            await asyncio.sleep(5)

# 在 bot_loop 中集成
auto_solver = AutoSolver(sdk, bot_state.sdk.address)
```

---

## 部署配置

### PythonAnywhere

URL: `https://aominis-quantl.pythonanywhere.com`

环境变量 (`~/aominis/sdk/.env`):
```env
PRIVATE_KEY=你的Solver私钥
RPC_URL=https://sepolia.infura.io/v3/你的key
CORE_ADDRESS=0x62E49387FFc45F67079C147Ee4D4bB7d710767F0
ORDERBOOK_ADDRESS=0x9D662B02759C89748A0Cd1e40dab7925b267f0bb
OPENAI_API_KEY=sk-你的key
```

同步代码:
```bash
cd ~/aominis
git pull origin master
```

重启:
- Web 页面 → Reload

### Vercel

环境变量:
```
VITE_BOT_SERVER_URL=https://aominis-quantl.pythonanywhere.com
```

---

## 完整流程 (目标)

```
1. 用户选择 Platform Bot 提交问题
   └── postProblemWithSubscription(hash, type, PLATFORM_BOT, 0x0)
   
2. 合约创建订单，状态直接设为 ACCEPTED
   └── orderBot[orderId] = platformBotAddress
   └── emit OrderAssignedToBot(orderId, platformBot, PLATFORM_BOT)
   
3. Bot Server 监听事件，发现分配给自己的订单
   └── check OrderAssignedToBot events where bot == myAddress
   
4. Bot Server 自动解题
   └── GET /api/problems?hash=xxx 获取题目文本
   └── 调用 GPT 解题
   └── commitSolution(orderId, hash)
   └── revealSolution(orderId, solution, salt)
   
5. 用户看到答案
   └── 前端显示 solution + steps
   └── 可以评分
```

---

## 测试步骤

1. 本地测试合约修改:
   ```bash
   cd ~/crypto/aominis
   forge test
   ```

2. 部署新合约:
   ```bash
   forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast
   ```

3. 配置模块地址 (使用 deployer 工具)

4. 测试前端提交

5. 观察 Bot Server 日志

---

## 文件结构

```
aominis/
├── contracts/
│   ├── CalcSolverCore.sol          # 主合约 (需修改)
│   └── modules/
│       ├── SubscriptionManager.sol  # 订阅管理
│       ├── BotRegistry.sol          # Bot 注册
│       └── RatingSystem.sol         # 评分系统
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ProblemForm.jsx      # 提交问题 (已支持订阅模式)
│   │   │   ├── BotMarketplace.jsx   # Bot 选择
│   │   │   └── SubscriptionPage.jsx # 订阅页面
│   │   └── config.js                # 合约地址配置
│   └── api/
│       └── problems.js              # Vercel API 存储题目
└── sdk/
    ├── bot_server.py                # Bot Server (需添加自动解题)
    └── ominis_sdk.py                # SDK
```

---

## 联系

GitHub: https://github.com/CharlieLi16/aominis
