"""Celery tasks for factor computation and analysis."""

import json
import logging
import uuid as uuid_lib
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
import scipy.stats as stats import celery_app
from app.engine.factor_engine import (
    FACTOR_CALCULATORS,
    FactorAnalysis,
    LayerBacktestResult,
    check_monotonicity,
    compute_layer_backtest,
)

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Lazy import to avoid loading DB engine at module level in non-worker contexts."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session, sessionmaker

    from app.core.config import get_settings

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)
    return sessionmaker(bind=engine)()


def _load_ohlcv_data(session, stock_codes: list[str], start_date: date, end_date: date) -> dict[str, list[dict]]:
    """Load daily OHLCV data for a batch of stocks."""
    from sqlalchemy import text

    rows = session.execute(
        text("""
            SELECT stock_code, trade_date, open, high, low, close, volume,
                   COALESCE(turnover_rate, 0) as turnover_rate
            FROM stock_daily
            WHERE stock_code = ANY(:codes)
              AND trade_date BETWEEN :start AND :end
            ORDER BY stock_code, trade_date
        """),
        {"codes": stock_codes, "start": start_date, "end": end_date},
    ).fetchall()

    data: dict[str, list[dict]] = {code: [] for code in stock_codes}
    for row in rows:
        data[row.stock_code].append({
            "trade_date": row.trade_date,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
            "turnover_rate": float(row.turnover_rate),
        })
    return data


def _get_active_stocks(session, as_of_date: date) -> list[str]:
    """Get list of actively trading stocks on or before a given date (no ST, no delist)."""
    from sqlalchemy import text

    rows = session.execute(
        text("""
            SELECT code FROM stock_basic
            WHERE list_date <= :as_of AND (delist_date IS NULL OR delist_date > :as_of)
              AND is_st = false AND status = 1
        """),
        {"as_of": as_of_date},
    ).fetchall()
    return [r.code for r in rows]


def _load_future_returns(
    session,
    stock_codes: list[str],
    trade_dates: set[date],
    forward_days: int,
    max_end_date: date,
) -> dict[str, dict[date, float]]:
    """Compute future N-day returns for each stock-trade_date pair."""
    from collections import defaultdict

    from sqlalchemy import text

    date_list = sorted(trade_dates)
    if not date_list:
        return {}

    min_date = min(date_list)
    # Load closes from min_date to max_end_date + some buffer
    rows = session.execute(
        text("""
            SELECT stock_code, trade_date, close
            FROM stock_daily
            WHERE stock_code = ANY(:codes)
              AND trade_date BETWEEN :start AND :end
            ORDER BY stock_code, trade_date
        """),
        {"codes": stock_codes, "start": min_date, "end": max_end_date + timedelta(days=30)},
    ).fetchall()

    # Build per-stock dict: trade_date → close
    closes_by_stock: dict[str, dict[date, float]] = defaultdict(dict)
    for r in rows:
        closes_by_stock[r.stock_code][r.trade_date] = float(r.close)

    # For each stock, compute forward returns
    result: dict[str, dict[date, float]] = {s: {} for s in stock_codes}
    for stock, closes in closes_by_stock.items():
        sorted_dates = sorted(closes.keys())
        if not sorted_dates:
            continue
        date_index = {d: i for i, d in enumerate(sorted_dates)}
        for dt in trade_dates:
            if dt not in date_index:
                result[stock][dt] = None
                continue
            idx = date_index[dt]
            future_idx = idx + forward_days
            if future_idx >= len(sorted_dates):
                result[stock][dt] = None
                continue
            future_date = sorted_dates[future_idx]
            if future_date > max_end_date:
                result[stock][dt] = None
                continue
            start_close = closes[dt]
            end_close = closes[future_date]
            if start_close == 0:
                result[stock][dt] = None
            else:
                result[stock][dt] = (end_close - start_close) / start_close

    return result


def _save_factor_values(session, factor_id: str, values: list[dict]) -> None:
    """Batch insert factor values."""
    from sqlalchemy import text

    for batch in _chunks(values, 500):
        # Upsert
        stmt = text("""
            INSERT INTO factor_value (factor_id, stock_code, trade_date, value, rank_pct)
            VALUES (:fid, :code, :date, :val, :rank)
            ON CONFLICT (factor_id, stock_code, trade_date) DO UPDATE
            SET value = EXCLUDED.value, rank_pct = EXCLUDED.rank_pct
        """)
        session.execute(stmt, [
            {"fid": factor_id, "code": v["stock_code"], "date": v["trade_date"],
             "val": v["value"], "rank": v.get("rank_pct")}
            for v in batch
        ])
    session.commit()


def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


@celery_app.task(bind=True, max_retries=2)
def run_factor_analysis(
    self,
    factor_name: str,
    factor_id: str,
    start_date: str,
    end_date: str,
    group_count: int = 10,
    forward_days: int = 10,
) -> dict[str, Any]:
    """Full factor analysis: compute values + layer backtest + IC + save to DB."""
    session = _get_sync_session()
    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)
    analysis_id = str(uuid_lib.uuid4())

    try:
        # Update analysis status
        _update_analysis(session, factor_id, None, analysis_id, "running")

        # 1. Get active stocks for the period
        active_stocks = _get_active_stocks(session, e_date)
        if not active_stocks:
            raise ValueError("No active stocks found")

        # 2. Get trading dates
        from sqlalchemy import text

        date_rows = session.execute(
            text("""
                SELECT DISTINCT trade_date FROM stock_daily
                WHERE trade_date BETWEEN :start AND :end
                ORDER BY trade_date
            """),
            {"start": s_date, "end": e_date},
        ).fetchall()
        trade_dates = set(r.trade_date for r in date_rows)
        if not trade_dates:
            raise ValueError("No trading data in date range")

        # 3. Load OHLCV data
        ohlcv_data = _load_ohlcv_data(session, active_stocks, s_date - timedelta(days=120), e_date)

        # 4. Compute factor values for each stock on each date
        calculator = FACTOR_CALCULATORS.get(factor_name)
        if calculator is None:
            raise ValueError(f"Unknown factor: {factor_name}")

        factor_values = []  # [{stock_code, trade_date, value}]
        import pandas as pd

        for stock, rows in ohlcv_data.items():
            if len(rows) < 20:
                continue
            df = pd.DataFrame(rows)
            df = df.sort_values("trade_date")
            for i in range(20, len(df)):
                sub = df.iloc[:i + 1]
                trade_dt = sub.iloc[-1]["trade_date"]
                val = calculator(sub)
                if not np.isnan(val):
                    factor_values.append({
                        "stock_code": stock, "trade_date": trade_dt, "value": float(val),
                    })

        # Compute rank percentiles per day
        from collections import defaultdict

        by_date: dict[date, list[dict]] = defaultdict(list)
        for fv in factor_values:
            by_date[fv["trade_date"]].append(fv)

        for dt, fvs in by_date.items():
            vals = np.array([f["value"] for f in fvs], dtype=float)
            ranks = np.argsort(np.argsort(vals))
            n = len(vals)
            for i, fv in enumerate(fvs):
                fv["rank_pct"] = float(ranks[i] / (n - 1) * 100) if n > 1 else 50.0

        # Save factor values
        _save_factor_values(session, factor_id, factor_values)

        self.update_state(state="PROGRESS", meta={"stage": "factor_values_done", "count": len(factor_values)})

        # 5. Compute future returns
        future_ret_data = _load_future_returns(session, active_stocks, trade_dates, forward_days, e_date)

        # 6. Layer backtest per day
        daily_results: dict[date, LayerBacktestResult] = {}
        for dt in sorted(trade_dates):
            fv_map = {fv["stock_code"]: fv["value"] for fv in by_date.get(dt, [])}
            fr_map = {s: future_ret_data.get(s, {}).get(dt) for s in active_stocks}
            fr_map = {k: v for k, v in fr_map.items() if v is not None}
            if not fv_map or not fr_map:
                continue
            result = compute_layer_backtest(fv_map, fr_map, group_count)
            if result.stock_count >= group_count * 2:
                daily_results[dt] = result

        # 7. Aggregate
        ic_values = [r.ic_pearson for r in daily_results.values() if r.ic_pearson]
        ic_mean = float(np.mean(ic_values)) if ic_values else 0.0
        ic_std = float(np.std(ic_values)) if ic_values else 0.0
        icir = ic_mean / ic_std if ic_std != 0 else 0.0

        # Average layer returns
        group_rets: dict[int, list[float]] = {}
        for r in daily_results.values():
            for g, ret in r.group_returns.items():
                group_rets.setdefault(g, []).append(ret)
        avg_layer_returns = {g: float(np.mean(rets)) for g, rets in group_rets.items()}

        # Cumulative layer returns
        layer_cumulative: dict[int, dict[str, float]] = {}
        for dt in sorted(daily_results.keys()):
            for g in range(group_count):
                layer_cumulative.setdefault(g, {})
                if dt in daily_results:
                    layer_cumulative[g][dt.isoformat()] = daily_results[dt].group_returns.get(g, 0.0)
        # Cumulative sum
        for g in layer_cumulative:
            running = 0.0
            for dt in sorted(layer_cumulative[g].keys()):
                running += layer_cumulative[g][dt]
                layer_cumulative[g][dt] = running

        mono = check_monotonicity(avg_layer_returns)

        # 8. Save analysis results
        _update_analysis(
            session, factor_id, analysis_id, "completed",
            ic_mean=ic_mean, ic_std=ic_std, icir=icir,
            ic_series={d.isoformat(): r.ic_pearson for d, r in daily_results.items()},
            layer_returns={str(g): ret for g, ret in avg_layer_returns.items()},
            layer_cumulative={str(g): vals for g, vals in layer_cumulative.items()},
            monotonicity=float(mono),
        )

        return {
            "analysis_id": analysis_id,
            "ic_mean": ic_mean,
            "ic_std": ic_std,
            "icir": icir,
            "monotonicity": mono,
            "stock_count": len(active_stocks),
            "factor_value_count": len(factor_values),
        }

    except Exception as e:
        logger.error(f"Factor analysis failed: {e}", exc_info=True)
        _update_analysis(session, factor_id, analysis_id, "failed", error=str(e))
        raise


def _update_analysis(
    session,
    factor_id: str,
    analysis_id: str | None = None,
    status: str = "running",
    **kwargs,
) -> None:
    """Insert or update factor_analysis row."""
    from sqlalchemy import text

    if analysis_id is None:
        return

    # Check if row exists
    existing = session.execute(
        text("SELECT id FROM factor_analysis WHERE id = :aid"),
        {"aid": analysis_id},
    ).fetchone()

    if existing:
        sets = ["status = :status"]
        params: dict[str, Any] = {"status": status, "aid": analysis_id}
        for k, v in kwargs.items():
            if k in ("ic_mean", "ic_std", "icir", "monotonicity"):
                sets.append(f"{k} = :{k}")
                params[k] = v
            elif k in ("ic_series", "layer_returns", "layer_cumulative"):
                sets.append(f"{k} = :{k}")
                params[k] = json.dumps(v)
            elif k == "error":
                sets.append("error_message = :error")
                params["error"] = v
        session.execute(
            text(f"UPDATE factor_analysis SET {', '.join(sets)} WHERE id = :aid"),
            params,
        )
    else:
        session.execute(
            text("""
                INSERT INTO factor_analysis
                (id, factor_id, start_date, end_date, group_count, forward_days, status, error_message,
                 ic_mean, ic_std, icir, ic_series, layer_returns, layer_cumulative, monotonicity)
                VALUES (:id, :factor_id, NOW(), NOW(), 10, 10, :status, :error,
                        :ic_mean, :ic_std, :icir, :ic_series, :layer_returns, :layer_cumulative, :mono)
            """),
            {
                "id": analysis_id,
                "factor_id": factor_id,
                "status": status,
                "error": kwargs.get("error", ""),
                "ic_mean": kwargs.get("ic_mean"),
                "ic_std": kwargs.get("ic_std"),
                "icir": kwargs.get("icir"),
                "ic_series": json.dumps(kwargs.get("ic_series", {})),
                "layer_returns": json.dumps(kwargs.get("layer_returns", {})),
                "layer_cumulative": json.dumps(kwargs.get("layer_cumulative", {})),
                "mono": kwargs.get("monotonicity"),
            },
        )
    session.commit()
