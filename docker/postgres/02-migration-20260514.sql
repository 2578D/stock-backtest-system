-- Migration: add benchmark and missing columns to backtest_result
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS benchmark_curve JSONB;
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS benchmark_return NUMERIC(10,4);
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS excess_return NUMERIC(10,4);
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS total_return_amount NUMERIC(16,2);
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS max_drawdown_days INTEGER;
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS sortino_ratio NUMERIC(10,4);
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS max_single_profit NUMERIC(16,2);
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS max_single_loss NUMERIC(16,2);
ALTER TABLE backtest_result ADD COLUMN IF NOT EXISTS avg_hold_days NUMERIC(10,2);

ALTER TABLE backtest_task ADD COLUMN IF NOT EXISTS period VARCHAR(10) DEFAULT 'daily';
ALTER TABLE backtest_task ADD COLUMN IF NOT EXISTS position_mode VARCHAR(20) DEFAULT 'fixed';
