"""Backtest engine — event-driven architecture.

Components:
- events: Event types and EventBus
- strategy: Strategy base class (IStrategy)
- lookahead_guard: Future leak prevention
- market_replayer: Chronological bar replay
- risk_manager: A-share rule enforcement
- trade_simulator: Order matching + account
- metrics: Performance statistics
- result_collector: Track portfolio/equity over time
- backtest: Main orchestrator (BacktestEngine)
"""

from app.engine.backtest import BacktestEngine, BacktestConfig

__all__ = ["BacktestEngine", "BacktestConfig"]
