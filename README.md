# 大A股票回测系统 | China A-Share Stock Backtest System

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-brightgreen)](https://vuejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

**[中文](#-简介) | [English](#-overview)**

---

## 简介

大A股票回测系统是一个功能完整的 A 股量化回测平台，支持策略可视化编辑、代码策略编写、事件驱动回测引擎、自动数据同步等功能。系统采用现代化的前后端分离架构，提供直观的用户界面来管理和执行股票策略回测。

## 功能特性

### 策略引擎
- **可视化策略编辑器** — 12 种技术指标（MA/EMA/BOLL/MACD/RSI/KDJ/金叉/死叉/成交量/换手率/涨跌幅/收盘价），无需编写代码即可构建策略
- **代码策略编辑器** — 支持 Python 代码自定义策略，内置多个策略模板（MA/买入持有/RSI）

### 回测引擎
- **事件驱动架构** — 行情逐日回放，支持 BAR/ORDER/FILL/RISK_REJECT 事件
- **未来函数防护** — LookAheadGuard 防止使用未来数据进行决策
- **多种仓位模式** — 固定金额 / 百分比 / 等权重分配
- **多周期支持** — 日线 / 周线 / 月线回测
- **完整风控** — T+1 交易限制、涨跌停限制、仓位控制、交易费用计算
- **绩效指标** — 夏普比率、最大回撤、卡尔马比率、索提诺比率、胜率、盈亏比等

### 数据管理
- **全 A 股覆盖** — 支持全市场 5000+ 只股票的日线数据
- **自动数据同步** — Celery Beat 定时增量同步 + 全量初始化
- **多数据源** — 支持 TickFlow 等数据源接入

### 选股与分析
- **策略选股器** — 基于策略信号对全市场进行扫描筛选
- **每日信号** — 自动运行策略扫描当日买入/卖出信号
- **回测对比** — 支持多个回测结果并列对比
- **报告导出** — 一键导出 CSV 格式回测报告

### 系统功能
- **用户认证** — JWT 认证，支持登录/注册
- **仪表盘** — 多维度统计概览、最近回测、常用策略
- **Docker 部署** — 一键 Docker Compose 部署，支持 GitHub Actions CI/CD

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy + Celery |
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts + Vite |
| 数据库 | PostgreSQL 16 + TimescaleDB |
| 缓存/队列 | Redis 7 + Celery |
| 部署 | Docker Compose + Nginx + GitHub Actions |

## 系统架构

```
┌──────────────────────────────────────────────────────┐
│                   Frontend (Vue 3)                    │
│  Dashboard | Strategies | Backtests | Data | Signals  │
└──────────────────────┬───────────────────────────────┘
                       │ /api/v1/*
┌──────────────────────▼───────────────────────────────┐
│                  API (FastAPI)                        │
│  /auth  /dashboard  /data  /strategies                │
│  /backtests  /picks  /factors  /analysis              │
└──────┬──────────┬──────────┬──────────────────────────┘
       │          │          │
  ┌────▼───┐  ┌───▼───┐  ┌──▼──────────────────┐
  │PostgreSQL│ │ Redis │  │  Celery Worker      │
  │+Timescale│ │       │  │  ├── run_backtest   │
  │   DB     │ │       │  │  ├── full_sync      │
  │          │ │       │  │  └── incr_sync      │
  └──────────┘  └───────┘  └───────────────────┘
```

## 快速开始

### 环境要求

- Docker & Docker Compose
- 或者本地 Python 3.12+ / Node.js 18+ / PostgreSQL 16 / Redis 7

### Docker Compose 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/lzusa/stock-backtest-system.git
cd stock-backtest-system

# 2. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 修改数据库密码等配置

# 3. 启动所有服务
docker compose up -d

# 4. 查看日志
docker compose logs -f api

# 5. 访问系统
# 浏览器打开 http://localhost
```

### 本地开发

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动 Celery Worker
celery -A app.celery_app worker --loglevel=info

# 启动 Celery Beat（定时任务）
celery -A app.celery_app beat --loglevel=info
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 数据库初始化

系统首次启动时会自动执行数据库初始化脚本，包括：

1. 安装 TimescaleDB 扩展
2. 创建核心表结构（stock_basic、stock_daily 等）
3. 创建 TimescaleDB 超表（hypertable）

如需全量同步历史数据：

```bash
# 通过 API 触发全量同步
curl -X POST http://localhost/api/v1/data/sync/full

# 或使用脚本
python sync_now.py
```

## 使用示例

### 创建可视化策略

1. 进入「策略管理」页面
2. 点击「新建策略」，选择「可视化编辑器」
3. 配置技术指标条件，例如：MA5 上穿 MA20 时买入
4. 保存策略

### 运行回测

1. 进入「回测管理」页面
2. 点击「新建回测」
3. 选择策略、设置时间范围、股票池、初始资金等参数
4. 提交回测任务（后台异步执行）
5. 回测完成后查看详细结果：收益曲线、绩效指标、交易明细

### 策略选股

1. 进入「每日信号」页面
2. 选择策略，系统自动扫描全市场
3. 查看符合条件的股票列表

## 项目结构

```
stock-backtest-system/
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── api/v1/            # REST API 路由
│   │   │   ├── auth/          # 用户认证
│   │   │   ├── backtests/     # 回测管理
│   │   │   ├── dashboard/     # 仪表盘
│   │   │   ├── data/          # 数据管理
│   │   │   ├── factors/       # 因子分析
│   │   │   ├── picks/         # 选股器
│   │   │   ├── strategies/    # 策略管理
│   │   │   └── system/        # 系统设置
│   │   ├── core/              # 核心配置（数据库、Redis、安全）
│   │   ├── engine/            # 回测引擎
│   │   │   ├── backtest.py    # 回测主引擎
│   │   │   ├── events.py      # 事件总线
│   │   │   ├── factor_engine.py
│   │   │   ├── lookahead_guard.py  # 未来函数防护
│   │   │   ├── market_replayer.py  # 行情回放器
│   │   │   ├── metrics.py     # 绩效指标计算
│   │   │   ├── result_collector.py
│   │   │   ├── risk_manager.py     # 风控
│   │   │   ├── strategy.py    # 策略基类
│   │   │   ├── trade_simulator.py  # 交易模拟器
│   │   │   └── visual_strategy.py  # 可视化策略运行时
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务服务层
│   │   └── tasks/             # Celery 异步任务
│   ├── alembic/               # 数据库迁移
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/               # HTTP 客户端
│   │   ├── components/        # 可复用组件
│   │   ├── layouts/           # 布局组件
│   │   ├── router/            # 路由配置
│   │   ├── stores/            # Pinia 状态管理
│   │   └── views/             # 页面视图
│   ├── package.json
│   └── vite.config.ts
├── docker/                     # Docker 配置
│   ├── Dockerfile.backend
│   ├── nginx/
│   └── postgres/
├── docker-compose.yml          # Docker Compose 编排
├── sync_now.py                 # 手动触发数据同步
└── sync_tickflow.py            # TickFlow 同步脚本
```

## API 文档

启动后端服务后，访问以下地址查看自动生成的 API 文档：

- Swagger UI: `http://localhost/docs`（仅开发模式）
- ReDoc: `http://localhost/redoc`（仅开发模式）

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 许可证

本项目采用 MIT 许可证 — 详见 [LICENSE](LICENSE) 文件。

---

## Overview

China A-Share Stock Backtest System is a full-featured quantitative backtesting platform for China's A-share market. It supports visual strategy editing, code-based strategy development, event-driven backtesting engine, and automatic data synchronization. Built with a modern decoupled architecture, it provides an intuitive user interface for managing and executing stock strategy backtests.

## Features

### Strategy Engine
- **Visual Strategy Editor** — 12 technical indicators (MA/EMA/BOLL/MACD/RSI/KDJ/Golden Cross/Death Cross/Volume/Turnover/Change/Close Price). Build strategies without writing code.
- **Code Strategy Editor** — Write custom strategies in Python with built-in templates (MA/Buy & Hold/RSI)

### Backtesting Engine
- **Event-Driven Architecture** — Chronological bar replay with BAR/ORDER/FILL/RISK_REJECT events
- **Lookahead Guard** — Prevents using future data for trading decisions
- **Multiple Position Modes** — Fixed amount / Percentage / Equal weight allocation
- **Multi-Period Support** — Daily / Weekly / Monthly backtesting
- **Comprehensive Risk Control** — T+1 trading limits, price limits, position control, transaction cost calculation
- **Performance Metrics** — Sharpe ratio, max drawdown, Calmar ratio, Sortino ratio, win rate, profit/loss ratio, and more

### Data Management
- **Full Market Coverage** — Supports daily data for 5000+ A-share stocks
- **Auto Data Sync** — Scheduled incremental sync via Celery Beat + full initialization
- **Multiple Data Sources** — Supports TickFlow and other data providers

### Stock Screening & Analysis
- **Strategy Screener** — Scan the entire market based on strategy signals
- **Daily Signals** — Automatically run strategies to find daily buy/sell signals
- **Backtest Comparison** — Compare multiple backtest results side by side
- **Report Export** — One-click CSV export of backtest reports

### System Features
- **User Authentication** — JWT-based auth with login/registration
- **Dashboard** — Multi-dimensional statistics, recent backtests, popular strategies
- **Docker Deployment** — One-click Docker Compose deployment with GitHub Actions CI/CD

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy + Celery |
| Frontend | Vue 3 + TypeScript + Element Plus + ECharts + Vite |
| Database | PostgreSQL 16 + TimescaleDB |
| Cache/Queue | Redis 7 + Celery |
| Deployment | Docker Compose + Nginx + GitHub Actions |

## System Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Frontend (Vue 3)                    │
│  Dashboard | Strategies | Backtests | Data | Signals  │
└──────────────────────┬───────────────────────────────┘
                       │ /api/v1/*
┌──────────────────────▼───────────────────────────────┐
│                  API (FastAPI)                        │
│  /auth  /dashboard  /data  /strategies                │
│  /backtests  /picks  /factors  /analysis              │
└──────┬──────────┬──────────┬──────────────────────────┘
       │          │          │
  ┌────▼───┐  ┌───▼───┐  ┌──▼──────────────────┐
  │PostgreSQL│ │ Redis │  │  Celery Worker      │
  │+Timescale│ │       │  │  ├── run_backtest   │
  │   DB     │ │       │  │  ├── full_sync      │
  │          │ │       │  │  └── incr_sync      │
  └──────────┘  └───────┘  └───────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Or locally: Python 3.12+ / Node.js 18+ / PostgreSQL 16 / Redis 7

### Docker Compose Deployment (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/lzusa/stock-backtest-system.git
cd stock-backtest-system

# 2. Configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env to set database password and other configs

# 3. Start all services
docker compose up -d

# 4. View logs
docker compose logs -f api

# 5. Access the system
# Open http://localhost in your browser
```

### Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery Worker
celery -A app.celery_app worker --loglevel=info

# Start Celery Beat (scheduled tasks)
celery -A app.celery_app beat --loglevel=info
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Database Initialization

On first startup, the system automatically runs database initialization scripts:

1. Install TimescaleDB extension
2. Create core table structures (stock_basic, stock_daily, etc.)
3. Create TimescaleDB hypertables

To sync historical data:

```bash
# Trigger full sync via API
curl -X POST http://localhost/api/v1/data/sync/full

# Or use the script
python sync_now.py
```

## Usage Examples

### Create a Visual Strategy

1. Go to "Strategy Management" page
2. Click "New Strategy", select "Visual Editor"
3. Configure technical indicator conditions (e.g., buy when MA5 crosses above MA20)
4. Save the strategy

### Run a Backtest

1. Go to "Backtest Management" page
2. Click "New Backtest"
3. Select strategy, set date range, stock pool, initial capital, etc.
4. Submit the backtest task (runs asynchronously in the background)
5. View detailed results after completion: equity curve, performance metrics, trade details

### Strategy Screening

1. Go to "Daily Signals" page
2. Select a strategy to automatically scan the market
3. View the list of stocks matching the criteria

## Project Structure

```
stock-backtest-system/
├── backend/                    # Python backend
│   ├── app/
│   │   ├── api/v1/            # REST API routes
│   │   │   ├── auth/          # User authentication
│   │   │   ├── backtests/     # Backtest management
│   │   │   ├── dashboard/     # Dashboard
│   │   │   ├── data/          # Data management
│   │   │   ├── factors/       # Factor analysis
│   │   │   ├── picks/         # Stock screener
│   │   │   ├── strategies/    # Strategy management
│   │   │   └── system/        # System settings
│   │   ├── core/              # Core config (DB, Redis, security)
│   │   ├── engine/            # Backtest engine
│   │   │   ├── backtest.py    # Main backtest engine
│   │   │   ├── events.py      # Event bus
│   │   │   ├── factor_engine.py
│   │   │   ├── lookahead_guard.py  # Lookahead protection
│   │   │   ├── market_replayer.py  # Market replay
│   │   │   ├── metrics.py     # Performance metrics
│   │   │   ├── result_collector.py
│   │   │   ├── risk_manager.py     # Risk management
│   │   │   ├── strategy.py    # Strategy base class
│   │   │   ├── trade_simulator.py  # Trade simulator
│   │   │   └── visual_strategy.py  # Visual strategy runtime
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business service layer
│   │   └── tasks/             # Celery async tasks
│   ├── alembic/               # Database migrations
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # Vue 3 frontend
│   ├── src/
│   │   ├── api/               # HTTP client
│   │   ├── components/        # Reusable components
│   │   ├── layouts/           # Layout components
│   │   ├── router/            # Router configuration
│   │   ├── stores/            # Pinia state management
│   │   └── views/             # Page views
│   ├── package.json
│   └── vite.config.ts
├── docker/                     # Docker configuration
│   ├── Dockerfile.backend
│   ├── nginx/
│   └── postgres/
├── docker-compose.yml          # Docker Compose orchestration
├── sync_now.py                 # Manual data sync trigger
└── sync_tickflow.py            # TickFlow sync script
```

## API Documentation

After starting the backend server, visit these URLs for auto-generated API docs:

- Swagger UI: `http://localhost/docs` (development mode only)
- ReDoc: `http://localhost/redoc` (development mode only)

## Contributing

Contributions are welcome! Please feel free to submit Issues and Pull Requests.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
