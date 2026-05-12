-- Stock backtest system — core tables
-- TimescaleDB hypertable conversion is optional
-- Uncomment CREATE EXTENSION and create_hypertable if TimescaleDB is installed

-- CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Core stock tables
CREATE TABLE IF NOT EXISTS stock_basic (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(12)   NOT NULL,
    name            VARCHAR(64)   NOT NULL,
    exchange        VARCHAR(8)    NOT NULL,
    list_date       DATE,
    delist_date     DATE,
    status          SMALLINT      DEFAULT 1,
    industry        VARCHAR(128),
    sector          VARCHAR(32),
    is_st           BOOLEAN       DEFAULT false,
    created_at      TIMESTAMPTZ   DEFAULT now(),
    updated_at      TIMESTAMPTZ   DEFAULT now(),
    CONSTRAINT uk_stock_code UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS trade_calendar (
    trade_date      DATE PRIMARY KEY,
    is_trade_day    BOOLEAN       NOT NULL DEFAULT true,
    pre_trade_date  DATE,
    next_trade_date DATE
);

CREATE TABLE IF NOT EXISTS stock_daily (
    id              BIGSERIAL,
    code            VARCHAR(12)   NOT NULL,
    trade_date      DATE          NOT NULL,
    open            NUMERIC(12,4) NOT NULL,
    high            NUMERIC(12,4) NOT NULL,
    low             NUMERIC(12,4) NOT NULL,
    close           NUMERIC(12,4) NOT NULL,
    volume          NUMERIC(20,2) NOT NULL,
    amount          NUMERIC(24,2) NOT NULL,
    turnover_rate   NUMERIC(8,4),
    source          VARCHAR(32)   DEFAULT 'efinance',
    CONSTRAINT pk_stock_daily PRIMARY KEY (code, trade_date)
);

-- Convert to hypertable (requires TimescaleDB)
-- SELECT create_hypertable('stock_daily', 'trade_date',
--     chunk_time_interval => INTERVAL '1 month',
--     if_not_exists => true
-- );

CREATE INDEX IF NOT EXISTS idx_daily_code_date ON stock_daily (code, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_date ON stock_daily (trade_date DESC);

-- Adj factor table
CREATE TABLE IF NOT EXISTS stock_adj_factor (
    id              BIGSERIAL,
    code            VARCHAR(12)   NOT NULL,
    trade_date      DATE          NOT NULL,
    adj_factor      NUMERIC(16,8) NOT NULL,
    source          VARCHAR(32)   DEFAULT 'efinance',
    CONSTRAINT pk_adj_factor PRIMARY KEY (code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_adj_code_date ON stock_adj_factor (code, trade_date DESC);

-- Suspend table
CREATE TABLE IF NOT EXISTS stock_suspend (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(12)   NOT NULL,
    suspend_date    DATE          NOT NULL,
    resume_date     DATE,
    suspend_type    VARCHAR(32),
    reason          TEXT
);

CREATE INDEX IF NOT EXISTS idx_suspend_code_date ON stock_suspend (code, suspend_date, resume_date);

-- Limit price table
CREATE TABLE IF NOT EXISTS stock_limit_price (
    id              BIGSERIAL,
    code            VARCHAR(12)   NOT NULL,
    trade_date      DATE          NOT NULL,
    up_limit        NUMERIC(12,4) NOT NULL,
    down_limit      NUMERIC(12,4) NOT NULL,
    CONSTRAINT pk_limit_price PRIMARY KEY (code, trade_date)
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    username        VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active       BOOLEAN DEFAULT true,
    is_superuser    BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Strategy table
CREATE TABLE IF NOT EXISTS strategy (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    type            VARCHAR(20) NOT NULL,
    rules_json      JSONB,
    code_content    TEXT,
    market          VARCHAR(10) DEFAULT 'A股',
    period          VARCHAR(10) DEFAULT 'daily',
    risk_control    JSONB,
    version         INTEGER DEFAULT 1,
    is_shared       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Backtest task table
CREATE TABLE IF NOT EXISTS backtest_task (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    strategy_id     UUID NOT NULL,
    name            VARCHAR(200),
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    stock_pool      JSONB DEFAULT '{}',
    initial_capital NUMERIC(20,4) DEFAULT 1000000,
    position_mode   VARCHAR(20) DEFAULT 'fixed',
    benchmark       VARCHAR(16) DEFAULT '000300.SH',
    adjust_mode     VARCHAR(10) DEFAULT 'forward',
    cost_config     JSONB DEFAULT '{"commission": 0.0003, "stamp_tax": 0.001, "transfer_fee": 0.000015}',
    status          VARCHAR(20) DEFAULT 'pending',
    celery_task_id  VARCHAR(100),
    progress        INTEGER DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Backtest result table
CREATE TABLE IF NOT EXISTS backtest_result (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL UNIQUE,
    total_return    NUMERIC(10,4),
    annual_return   NUMERIC(10,4),
    max_drawdown    NUMERIC(10,4),
    sharpe_ratio    NUMERIC(10,4),
    calmar_ratio    NUMERIC(10,4),
    win_rate        NUMERIC(10,4),
    profit_loss_ratio NUMERIC(10,4),
    trade_count     INTEGER DEFAULT 0,
    avg_hold_days   NUMERIC(10,2),
    equity_curve    JSONB,
    drawdown_curve  JSONB,
    monthly_returns JSONB,
    daily_returns   JSONB
);

-- Backtest trade table
CREATE TABLE IF NOT EXISTS backtest_trade (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL,
    stock_code      VARCHAR(12) NOT NULL,
    buy_date        DATE NOT NULL,
    buy_price       NUMERIC(12,4) NOT NULL,
    buy_reason      TEXT,
    sell_date       DATE NOT NULL,
    sell_price      NUMERIC(12,4) NOT NULL,
    sell_reason     TEXT,
    quantity        INTEGER DEFAULT 100,
    hold_days       INTEGER DEFAULT 0,
    return_rate     NUMERIC(10,4),
    return_amount   NUMERIC(20,4)
);

-- Data sync tables
CREATE TABLE IF NOT EXISTS data_sync_log (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(32) NOT NULL,
    table_name      VARCHAR(64) NOT NULL,
    start_date      DATE,
    end_date        DATE,
    status          VARCHAR(16) NOT NULL,
    row_count       INTEGER,
    error_msg       TEXT,
    started_at      TIMESTAMPTZ DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS data_source_watermark (
    source          VARCHAR(32) NOT NULL,
    table_name      VARCHAR(64) NOT NULL,
    last_sync_date  DATE NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (source, table_name)
);

CREATE TABLE IF NOT EXISTS data_source_config (
    id              SERIAL PRIMARY KEY,
    source_name     VARCHAR(32) NOT NULL UNIQUE,
    source_type     VARCHAR(32) NOT NULL,
    priority        SMALLINT DEFAULT 0,
    enabled         BOOLEAN DEFAULT true,
    config_json     JSONB,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
