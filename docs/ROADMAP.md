# 大A回测系统 — 项目文档

## 访问信息

- **生产环境：** http://170.106.103.184/stock/
- **GitHub：** https://github.com/2578D/stock-backtest-system
- **登录：** admin / admin123
- **部署：** GitHub Actions → SCP → docker compose up（push master 自动部署）

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy + Celery |
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts + Vite |
| 数据库 | PostgreSQL 16（stock_basic 5851只 + stock_daily 1712万行） |
| 缓存/队列 | Redis 7 + Celery（回测任务 + 数据同步） |
| 数据源 | TickFlow Free API（批量K线） |
| 部署 | Docker Compose（api + celery-worker + celery-beat + postgres + redis + nginx） |

## 系统架构

```
前端 (Vue3 SPA)
  ↓ /api/v1/*
API (FastAPI)
  ├── /auth         认证（JWT）
  ├── /dashboard    仪表盘统计
  ├── /data         股票列表 + 行情数据 + 同步管理
  ├── /strategies   策略 CRUD（可视化 + 代码）
  ├── /backtests    回测创建 + 结果查询
  ├── /picks        策略选股器
  └── /system       系统设置

Celery Worker
  ├── run_backtest        异步回测执行
  ├── full_init_sync      全量数据同步
  └── incremental_sync    增量数据同步（Celery Beat 每小时）

回测引擎 (app/engine/)
  ├── events.py           事件总线（BAR/ORDER/FILL/RISK_REJECT）
  ├── strategy.py         策略基类 IStrategy
  ├── lookahead_guard.py  未来函数防护
  ├── market_replayer.py  行情逐日回放器
  ├── risk_manager.py     风控（T+1/涨跌停/仓位/费用）
  ├── trade_simulator.py  交易模拟器（撮合+账户）
  ├── metrics.py          绩效指标（夏普/回撤/卡尔马/索提诺）
  ├── backtest.py         回测主引擎
  └── visual_strategy.py  可视化策略运行时（12种指标）
```

## 已完成功能

### 策略引擎
- ✅ 可视化策略编辑器 — 12 种指标（MA/EMA/BOLL/MACD/RSI/KDJ/金叉/死叉/成交量/换手率/涨跌幅/收盘价）
- ✅ 代码策略编辑器 — 3 个模板（MA/买入持有/RSI），exec 执行
- ✅ 策略 CRUD + 列表页

### 回测
- ✅ 事件驱动引擎（8模块，1095行）
- ✅ Celery 异步回测任务
- ✅ 回测详情页 — 8 指标卡片 + 风险详情 + 交易明细
- ✅ 股票池输入（autocomplete + tag + 批量）

### 数据
- ✅ 全A股日线数据（5406只，1712万行）
- ✅ TickFlow 全量同步 + 增量同步
- ✅ Celery Beat 每天收盘后自动增量
- ✅ 数据新鲜度标识

### 选股
- ✅ 策略选股器 — 对全市场最新一天跑策略信号扫描
- ✅ 筛选：市场范围 + 排除ST/停牌

### 仪表盘
- ✅ 4 维度统计卡片 + 最近回测 + 常用策略

---

## 开发路线图

### Phase 2 — 策略研究升级（当前）

#### 1. 收益曲线图 🔴 P0
**目标：** 回测详情页可视化资金曲线

- [ ] 后端：`GET /backtests/{id}/result` 新增 `equity_curve` 结构化数据
- [ ] 前端：ECharts 双轴图 — 资金曲线 + 每日收益率柱状图
- [ ] 叠加基准对比（沪深300 在同一张图上）
- [ ] 标注最大回撤区间（阴影区域）

#### 3. 基准对比 🔴 P0
**目标：** 回测结果有参照系

- [ ] 后端：获取沪深300/中证500 基准收益率序列
- [ ] 前端：资金曲线图上叠加基准曲线
- [ ] 指标卡片新增「超额收益」「基准收益」对比
- [ ] 跑赢/跑输大盘一目了然

#### 4. 多股票组合回测 🔴 P0
**目标：** 固定资金池，多只股票共享仓位

- [ ] 后端：组合回测模式 — 同一资金池，策略在股票池中分配
- [ ] 仓位管理：固定金额、等权重、按信号强度排序
- [ ] 前端：组合回测页面 — 选股票池 → 设仓位模式 → 开始回测
- [ ] 结果展示：组合级别的资金曲线 + 各成分股贡献度

#### 5. 回测对比 🟡 P1
**目标：** 多个回测结果放在一起比较

- [ ] 前端：「对比」页面 — 选 2-5 个已完成回测
- [ ] 并排展示：总收益 / 夏普 / 最大回撤 / 胜率
- [ ] 资金曲线叠加（不同颜色）
- [ ] 支持保存对比组

#### 6. 导出报告 🟡 P1
**目标：** 一键导出回测分析结果

- [ ] 后端：生成 HTML/PDF 报告（绩效指标 + 曲线图 + 交易明细）
- [ ] 前端：回测详情页「导出」按钮
- [ ] Excel 导出：交易记录明细表

### Phase 3 — 走向实盘

#### 7. 每日信号 🟡 P1
**目标：** 基于策略的每日选股信号

- [ ] 后端：每日自动运行所有启用策略的选股器
- [ ] 前端：「今日信号」页面 — 策略 × 股票 = 买卖信号列表
- [ ] 信号历史存档
- [ ] 信号统计：准确率、平均收益（事后验证）

#### 8. 多周期策略 🟡 P1
**目标：** 支持周线/月线 + 多周期组合

- [ ] 后端：周线/月线 K 线数据聚合
- [ ] 策略编辑器：新增周期选择（日线/周线/月线）
- [ ] 多周期条件：日线上穿 MA5 且 周线在 MA20 上方
- [ ] 回测引擎适配多周期数据回放

### Skipped

#### 2. 参数优化（搁置）
暂不实现。手动调参现阶段够用。

---

## 策略模板参考

### MA 金叉策略（代码）
```python
class MAStrategy(IStrategy):
    def on_init(self, context):
        self.fast = 5
        self.slow = 20

    def on_bar(self, context, bar, portfolio):
        symbol = bar.get("code", "")
        df = context.data(symbol, lookback=self.slow + 1)
        closes = df["close"].tolist()
        
        ma_fast = sum(closes[-self.fast:]) / self.fast
        ma_slow = sum(closes[-self.slow:]) / self.slow
        prev_fast = sum(closes[-self.fast-1:-1]) / self.fast
        prev_slow = sum(closes[-self.slow-1:-1]) / self.slow
        
        orders = []
        price = bar["close"]
        
        # 金叉买入
        if prev_fast <= prev_slow and ma_fast > ma_slow:
            qty = int(100000 / price / 100) * 100
            orders.append(Order(symbol, "buy", qty, price, "金叉"))
        
        # 死叉卖出
        if prev_fast >= prev_slow and ma_fast < ma_slow:
            pos = portfolio.positions.get(symbol)
            if pos and pos.quantity > 0:
                orders.append(Order(symbol, "sell", pos.quantity, price, "死叉"))
        
        return orders
```
