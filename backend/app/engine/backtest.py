"""Main backtest engine — event-driven orchestrator.

Ties together all components:
- MarketReplayer feeds bars chronologically
- IStrategy generates orders from bars
- RiskManager validates orders
- TradeSimulator executes fills + manages portfolio
- LookAheadGuard prevents future leaks
- ResultCollector captures equity curve + returns
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.engine.events import Event, EventBus, EventType
from app.engine.lookahead_guard import LookAheadGuard
from app.engine.market_replayer import MarketReplayer
from app.engine.metrics import PerformanceMetrics, compute_metrics
from app.engine.result_collector import ResultCollector
from app.engine.risk_manager import RiskConfig, RiskManager
from app.engine.strategy import IStrategy, Order, Portfolio
from app.engine.trade_simulator import TradeSimulator

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    stock_pool: list[str] = field(default_factory=list)
    start_date: date = date(2020, 1, 1)
    end_date: date = date(2025, 12, 31)
    initial_capital: float = 1_000_000.0
    benchmark: str = "000300.SH"
    position_mode: str = "fixed"    # "fixed" | "percent" | "equal_weight"
    period: str = "daily"          # "daily" | "weekly" | "monthly"
    adjust_mode: str = "forward"    # "forward" / "backward" / "none"
    risk: RiskConfig | None = None

    def __post_init__(self):
        if self.risk is None:
            self.risk = RiskConfig()


@dataclass
class BacktestResult:
    """Full result of a backtest run."""

    config: BacktestConfig
    metrics: PerformanceMetrics
    equity_curve: dict[str, float]           # date → nav
    daily_returns: dict[str, float]          # date → return
    benchmark_returns: dict[str, float] = field(default_factory=dict)  # date → benchmark return
    trades: list[dict] = field(default_factory=list)
    position_snapshots: dict[str, dict] = field(default_factory=dict)


class BacktestEngine:
    """Main backtest engine — event-driven, chronological bar replay."""

    def __init__(
        self,
        config: BacktestConfig,
        session_factory: Callable[[], Session],
    ):
        self.config = config
        self._session_factory = session_factory

        # Components
        self.event_bus = EventBus()
        self.lookahead = LookAheadGuard()
        self.market = MarketReplayer(
            session_factory,
            config.stock_pool,
            config.start_date,
            config.end_date,
            config.period,
        )
        self.risk = RiskManager(config.risk)
        self.trader = TradeSimulator(config.initial_capital, self.risk, self.event_bus)
        self.collector = ResultCollector()
        self.strategy: IStrategy | None = None

        # State
        self._prev_close: dict[str, float] = {}  # symbol → previous close
        self._prev_value: float = config.initial_capital

        # Wire event handlers
        self._wire_events()

    def set_strategy(self, strategy: IStrategy) -> None:
        self.strategy = strategy

    def _load_benchmark(self) -> dict[date, float]:
        """Load benchmark index daily close prices for the backtest period."""
        from sqlalchemy import text
        benchmark = self.config.benchmark
        result: dict[date, float] = {}
        try:
            with self._session_factory() as s:
                rows = s.execute(
                    text(
                        """SELECT trade_date, close FROM stock_daily
                        WHERE code = :code AND trade_date >= :start AND trade_date <= :end
                        ORDER BY trade_date"""
                    ),
                    {"code": benchmark, "start": self.config.start_date, "end": self.config.end_date},
                ).fetchall()
                for row in rows:
                    result[row[0]] = float(row[1])
            logger.info(f"Loaded benchmark {benchmark}: {len(result)} days")
        except Exception as e:
            logger.warning(f"Failed to load benchmark {benchmark}: {e}")
        return result

    def _wire_events(self) -> None:
        def on_bar(event: Event) -> None:
            if not self.strategy:
                return
            bar_data = event.data

            # Update market prices in portfolio
            self.trader.mark_to_market(bar_data)

            # Run strategy for each stock in the pool
            for symbol in self.config.stock_pool:
                bar = bar_data.get(symbol)
                if bar is None:
                    continue
                if not self.lookahead.validate_bar(symbol, bar, event.timestamp):
                    continue

                strategy_ctx = self.strategy._context
                strategy_ctx.current_date = event.timestamp

                orders = self.strategy.on_bar(strategy_ctx, bar, self.trader.portfolio)
                if not orders:
                    continue

                for order in orders:
                    order.timestamp = event.timestamp
                    prev_c = self._prev_close.get(symbol, bar.get("close", 0))
                    self.trader.process_order(order, bar, prev_c)

            # Update prev_close for next day
            for symbol, b in bar_data.items():
                self._prev_close[symbol] = b.get("close", 0)

        def on_fill(event: Event) -> None:
            pass  # fills already handled in process_order

        def on_risk_reject(event: Event) -> None:
            d = event.data
            logger.debug(
                f"[{event.timestamp}] Rejected {d.get('symbol')} "
                f"{d.get('order', {}).side if hasattr(d.get('order', {}), 'side') else '?'}: "
                f"{d.get('reason', '?')}"
            )

        self.event_bus.subscribe(EventType.BAR, on_bar)
        self.event_bus.subscribe(EventType.FILL, on_fill)
        self.event_bus.subscribe(EventType.RISK_REJECT, on_risk_reject)

    def run(self) -> BacktestResult:
        """Execute the backtest."""
        if not self.strategy:
            raise RuntimeError("No strategy set. Call set_strategy() first.")

        logger.info(
            f"Starting backtest: {self.config.start_date} → {self.config.end_date}, "
            f"{len(self.config.stock_pool)} stocks, ¥{self.config.initial_capital:,.0f}"
        )

        # Load market data
        self.market.load()

        # Load benchmark data
        benchmark_closes: dict[date, float] = self._load_benchmark()

        # Init strategy
        from app.engine.strategy import StrategyContext

        ctx = StrategyContext(self.market, self.config.start_date)
        self.strategy._context = ctx
        self.strategy.on_init(ctx)

        total_days = len(self.market._all_dates)
        self.collector.set_progress_callback(
            lambda cur, tot: logger.info(f"Progress: {cur}/{tot} ({cur/tot*100:.0f}%)"),
            total_days,
        )

        # Track benchmark returns
        benchmark_rets: dict[str, float] = {}
        prev_bench_close: float = 0.0

        # Main loop
        while self.market.has_next():
            bars = self.market.next_day()
            if not bars:
                continue

            current_date = self.market.current_date()
            self.trader.set_date(current_date)

            # Publish BAR event (triggers strategy + fills)
            self.event_bus.publish(
                Event(EventType.BAR, current_date, bars)
            )

            # Record daily results
            portfolio = self.trader.portfolio
            current_value = portfolio.total_value
            daily_return = (
                (current_value - self._prev_value) / self._prev_value
                if self._prev_value > 0
                else 0.0
            )
            self._prev_value = current_value

            positions_snap = {
                sym: {
                    "quantity": pos.quantity,
                    "price": pos.current_price,
                    "value": pos.market_value,
                }
                for sym, pos in portfolio.positions.items()
                if pos.quantity > 0
            }

            self.collector.record_day(current_date, current_value, daily_return, positions_snap)

            # Compute benchmark daily return
            bench_close = benchmark_closes.get(current_date)
            if bench_close and bench_close > 0 and prev_bench_close > 0:
                bench_ret = (bench_close - prev_bench_close) / prev_bench_close
                benchmark_rets[str(current_date)] = bench_ret
                prev_bench_close = bench_close
            elif bench_close and bench_close > 0:
                prev_bench_close = bench_close

        # Strategy cleanup
        self.strategy.on_stop(ctx, self.trader.portfolio)

        # Compute metrics
        daily_rets = self.collector.get_daily_returns()
        bench_daily_list = [benchmark_rets[d] for d in sorted(benchmark_rets)] if benchmark_rets else None
        metrics = compute_metrics(
            daily_returns=daily_rets,
            initial_capital=self.config.initial_capital,
            benchmark_returns=bench_daily_list,
            trades=self.trader.trades,
        )

        logger.info(
            f"Backtest complete: total_return={metrics.total_return*100:.2f}%, "
            f"sharpe={metrics.sharpe_ratio:.2f}, max_dd={metrics.max_drawdown*100:.2f}%, "
            f"trades={metrics.trade_count}"
        )

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            equity_curve=self.collector.get_equity_curve(),
            daily_returns=self.collector.get_daily_returns_with_dates(),
            benchmark_returns=benchmark_rets,
            trades=self.trader.trades,
            position_snapshots=self.collector.position_snapshots,
        )
