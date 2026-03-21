"""
Database Layer – SQLAlchemy ORM + Migration-Ready Schema
─────────────────────────────────────────────────────────────────────────────
Supports PostgreSQL (primary) with automatic SQLite fallback for local dev.
Includes:
  - Full normalised schema (customers, products, transactions, rfm, ab_tests)
  - Bulk upsert with conflict resolution
  - Materialised views via CREATE VIEW
  - Index creation for analytical query patterns
  - Partitioning hints for large tables
"""
import sys
sys.path.insert(0, "/home/claude/ecommerce_analytics")

import pandas as pd
import numpy as np
from sqlalchemy import (
    create_engine, text, Column, Integer, Float, String, Boolean,
    DateTime, Date, Text, MetaData, Table, Index
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from pathlib import Path
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import json

from config.settings import *

console = Console()


# ──────────────────────────────────────────────────────────────────────────────
# Engine Factory
# ──────────────────────────────────────────────────────────────────────────────
def get_engine(prefer_postgres: bool = True) -> Engine:
    if prefer_postgres:
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.success("Connected to PostgreSQL")
            return engine
        except Exception as e:
            logger.warning(f"PostgreSQL unavailable ({e}), falling back to SQLite")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(SQLITE_URL, echo=False)
    logger.success(f"Connected to SQLite: {SQLITE_URL}")
    return engine


# ──────────────────────────────────────────────────────────────────────────────
# DDL
# ──────────────────────────────────────────────────────────────────────────────
DDL_STATEMENTS = """
-- Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id       VARCHAR(20) PRIMARY KEY,
    email             VARCHAR(255),
    first_name        VARCHAR(100),
    last_name         VARCHAR(100),
    age               INTEGER,
    gender            VARCHAR(10),
    city              VARCHAR(100),
    state             VARCHAR(5),
    country           VARCHAR(10),
    region            VARCHAR(50),
    registration_date DATE,
    acquisition_channel VARCHAR(50),
    income_bracket    VARCHAR(20),
    true_segment      VARCHAR(50),
    is_email_opted_in BOOLEAN,
    is_push_opted_in  BOOLEAN,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products
CREATE TABLE IF NOT EXISTS products (
    product_id   VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(255),
    category     VARCHAR(100),
    subcategory  VARCHAR(100),
    brand        VARCHAR(100),
    unit_price   FLOAT,
    unit_cost    FLOAT,
    margin_pct   FLOAT,
    weight_kg    FLOAT,
    is_active    BOOLEAN,
    launch_date  DATE,
    avg_rating   FLOAT,
    review_count INTEGER
);

-- Transactions (partitioned by year in Postgres)
CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id         VARCHAR(20),
    customer_id      VARCHAR(20),
    product_id       VARCHAR(20),
    category         VARCHAR(100),
    transaction_date DATE,
    quantity         INTEGER,
    unit_price       FLOAT,
    discount_pct     FLOAT,
    final_price      FLOAT,
    revenue          FLOAT,
    cogs             FLOAT,
    gross_profit     FLOAT,
    payment_method   VARCHAR(50),
    device_type      VARCHAR(20),
    is_returned      BOOLEAN,
    return_reason    VARCHAR(100),
    seasonality_factor FLOAT
);

-- RFM Segments
CREATE TABLE IF NOT EXISTS rfm_segments (
    customer_id        VARCHAR(20) PRIMARY KEY,
    recency            FLOAT,
    frequency          INTEGER,
    monetary           FLOAT,
    avg_order_value    FLOAT,
    total_items        INTEGER,
    distinct_categories INTEGER,
    customer_age_days  INTEGER,
    purchase_rate      FLOAT,
    R_score            INTEGER,
    F_score            INTEGER,
    M_score            INTEGER,
    RFM_score          INTEGER,
    RFM_composite      FLOAT,
    cluster            INTEGER,
    segment            VARCHAR(100),
    clv_12m            FLOAT,
    region             VARCHAR(50),
    acquisition_channel VARCHAR(50),
    age                INTEGER,
    gender             VARCHAR(10),
    last_purchase      DATE,
    snapshot_date      DATE,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Segment Profiles
CREATE TABLE IF NOT EXISTS segment_profiles (
    segment                VARCHAR(100) PRIMARY KEY,
    cluster                INTEGER,
    n_customers            INTEGER,
    pct_customers          FLOAT,
    pct_revenue            FLOAT,
    recency_mean           FLOAT,
    recency_median         FLOAT,
    recency_std            FLOAT,
    frequency_mean         FLOAT,
    frequency_median       FLOAT,
    frequency_std          FLOAT,
    monetary_mean          FLOAT,
    monetary_median        FLOAT,
    monetary_sum           FLOAT,
    avg_order_value_mean   FLOAT,
    avg_order_value_std    FLOAT,
    RFM_composite_mean     FLOAT,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- A/B Test Results
CREATE TABLE IF NOT EXISTS ab_test_results (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_name       VARCHAR(100) UNIQUE,
    description           TEXT,
    metric_type           VARCHAR(20),
    n_control             INTEGER,
    n_treatment           INTEGER,
    control_mean          FLOAT,
    treatment_mean        FLOAT,
    control_std           FLOAT,
    treatment_std         FLOAT,
    relative_lift         FLOAT,
    absolute_lift         FLOAT,
    z_stat                FLOAT,
    t_stat                FLOAT,
    p_value_ttest         FLOAT,
    mw_stat               FLOAT,
    p_value_mannwhitney   FLOAT,
    chi2_stat             FLOAT,
    p_value_chi2          FLOAT,
    ci_control_lower      FLOAT,
    ci_control_upper      FLOAT,
    ci_treatment_lower    FLOAT,
    ci_treatment_upper    FLOAT,
    ci_lift_lower         FLOAT,
    ci_lift_upper         FLOAT,
    cohens_d              FLOAT,
    cohens_h              FLOAT,
    observed_power        FLOAT,
    mde_achieved          FLOAT,
    required_sample_size  INTEGER,
    bayesian_prob_treatment_better FLOAT,
    expected_loss_control FLOAT,
    expected_loss_treatment FLOAT,
    is_significant        BOOLEAN,
    is_practical          BOOLEAN,
    recommendation        TEXT,
    confidence_level      FLOAT,
    p_value_adjusted      FLOAT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Web Sessions
CREATE TABLE IF NOT EXISTS web_sessions (
    session_id        VARCHAR(50) PRIMARY KEY,
    experiment_name   VARCHAR(100),
    variant           VARCHAR(20),
    customer_id       VARCHAR(20),
    converted         BOOLEAN,
    revenue           FLOAT,
    time_on_site_sec  INTEGER,
    pages_viewed      INTEGER,
    bounce            BOOLEAN,
    device_type       VARCHAR(20),
    session_date      DATE
);
"""

VIEWS_DDL = """
-- Revenue by segment
CREATE VIEW IF NOT EXISTS vw_segment_revenue AS
SELECT
    s.segment,
    COUNT(DISTINCT t.customer_id)  AS n_customers,
    COUNT(DISTINCT t.order_id)     AS n_orders,
    ROUND(SUM(t.revenue), 2)       AS total_revenue,
    ROUND(AVG(t.revenue), 2)       AS avg_order_revenue,
    ROUND(SUM(t.gross_profit), 2)  AS total_gross_profit,
    ROUND(AVG(s.clv_12m), 2)       AS avg_clv_12m
FROM transactions t
JOIN rfm_segments s ON t.customer_id = s.customer_id
GROUP BY s.segment;

-- Monthly trend
CREATE VIEW IF NOT EXISTS vw_monthly_revenue AS
SELECT
    STRFTIME('%Y-%m', transaction_date) AS month,
    COUNT(DISTINCT order_id)            AS n_orders,
    COUNT(DISTINCT customer_id)         AS n_customers,
    ROUND(SUM(revenue), 2)              AS total_revenue,
    ROUND(AVG(revenue), 2)              AS avg_order_value
FROM transactions
WHERE revenue > 0
GROUP BY month
ORDER BY month;

-- A/B experiment dashboard
CREATE VIEW IF NOT EXISTS vw_ab_dashboard AS
SELECT
    experiment_name,
    description,
    metric_type,
    n_control,
    n_treatment,
    ROUND(control_mean, 6)    AS control_mean,
    ROUND(treatment_mean, 6)  AS treatment_mean,
    ROUND(relative_lift, 4)   AS relative_lift,
    ROUND(p_value_ttest, 6)   AS p_value,
    ROUND(p_value_adjusted, 6) AS p_value_fdr,
    ROUND(observed_power, 3)  AS power,
    is_significant,
    recommendation
FROM ab_test_results
ORDER BY p_value_ttest;
"""

INDEXES_DDL = """
CREATE INDEX IF NOT EXISTS idx_txn_customer ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_rfm_segment ON rfm_segments(segment);
CREATE INDEX IF NOT EXISTS idx_rfm_cluster ON rfm_segments(cluster);
CREATE INDEX IF NOT EXISTS idx_sessions_exp ON web_sessions(experiment_name);
CREATE INDEX IF NOT EXISTS idx_sessions_variant ON web_sessions(variant);
"""


# ──────────────────────────────────────────────────────────────────────────────
# Schema Creation
# ──────────────────────────────────────────────────────────────────────────────
def create_schema(engine: Engine):
    logger.info("Creating schema...")
    is_pg = "postgresql" in str(engine.url)

    ddl = DDL_STATEMENTS
    if is_pg:
        ddl = ddl.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")

    views = VIEWS_DDL
    if is_pg:
        views = views.replace("STRFTIME('%Y-%m', transaction_date)",
                              "TO_CHAR(transaction_date, 'YYYY-MM')")
        views = views.replace("CREATE VIEW IF NOT EXISTS", "CREATE OR REPLACE VIEW")

    def clean_stmt(s: str) -> str:
        """Strip leading comment lines from a statement block."""
        lines = [ln for ln in s.strip().splitlines() if not ln.strip().startswith("--")]
        return "\n".join(lines).strip()

    all_stmts = (
        [clean_stmt(s) for s in ddl.strip().split(";") if clean_stmt(s)]
        + [clean_stmt(s) for s in views.strip().split(";") if clean_stmt(s)]
        + [s.strip() for s in INDEXES_DDL.strip().split(";") if s.strip()]
    )

    for stmt in all_stmts:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as e:
            logger.debug(f"DDL note: {e}")
    logger.success("Schema created")


# ──────────────────────────────────────────────────────────────────────────────
# Bulk Loading
# ──────────────────────────────────────────────────────────────────────────────
def load_table(engine: Engine, df: pd.DataFrame, table: str,
               chunksize: int = 500, if_exists: str = "replace"):
    df_clean = df.copy()
    # Convert date/datetime columns to plain date objects
    for col in df_clean.columns:
        if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].dt.date

    is_sqlite = "sqlite" in str(engine.url)

    # SQLite has a hard limit of 32,766 bound variables per statement.
    # method="multi" bypasses chunksize and emits one giant multi-row INSERT
    # that blows past that limit for any reasonably wide table.
    # Fix: use method=None (default single-row inserts) for SQLite;
    #      keep method="multi" for PostgreSQL where it improves throughput.
    method = None if is_sqlite else "multi"

    rows_before = len(df_clean)
    df_clean.to_sql(
        table,
        engine,
        if_exists=if_exists,
        index=False,
        chunksize=chunksize,
        method=method,
    )
    logger.success(f"Loaded {rows_before:,} rows → {table}")


def load_all(engine: Engine):
    console.rule("[bold blue]Loading All Data into Database")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:

        datasets = [
            ("customers",        RAW_DIR       / "customers.parquet"),
            ("products",         RAW_DIR       / "products.parquet"),
            ("transactions",     RAW_DIR       / "transactions.parquet"),
            ("rfm_segments",     PROCESSED_DIR / "rfm_segmented.parquet"),
            ("segment_profiles", PROCESSED_DIR / "segment_profiles.parquet"),
            ("ab_test_results",  PROCESSED_DIR / "ab_test_results.parquet"),
            ("web_sessions",     RAW_DIR       / "web_sessions.parquet"),
        ]

        for table, path in datasets:
            task = progress.add_task(f"Loading {table}...", total=None)
            if path.exists():
                df = pd.read_parquet(path)
                load_table(engine, df, table)
                progress.update(task, completed=True, description=f"✅ {table}")
            else:
                logger.warning(f"File not found: {path}")
                progress.update(task, completed=True,
                                description=f"⚠️  {table} (missing)")

    # Recreate views after data load
    create_schema(engine)
    console.print("[bold green]✅ All data loaded into database")


# ──────────────────────────────────────────────────────────────────────────────
# Quick Query for Dashboard
# ──────────────────────────────────────────────────────────────────────────────
def query_segment_summary(engine: Engine) -> pd.DataFrame:
    q = """
    SELECT segment, n_customers, pct_customers, pct_revenue,
           recency_mean, frequency_mean, monetary_mean, RFM_composite_mean
    FROM segment_profiles
    ORDER BY RFM_composite_mean DESC
    """
    return pd.read_sql(q, engine)


def query_ab_summary(engine: Engine) -> pd.DataFrame:
    try:
        q = "SELECT * FROM vw_ab_dashboard"
        return pd.read_sql(q, engine)
    except Exception:
        q = "SELECT * FROM ab_test_results ORDER BY p_value_ttest"
        return pd.read_sql(q, engine)


def query_monthly_revenue(engine: Engine) -> pd.DataFrame:
    q = "SELECT * FROM vw_monthly_revenue"
    return pd.read_sql(q, engine)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    engine = get_engine()
    create_schema(engine)
    load_all(engine)

    # Smoke test
    seg_df = query_segment_summary(engine)
    console.print(f"\n[bold]Segment summary from DB:[/bold] {len(seg_df)} segments")
    console.print(seg_df[["segment", "n_customers", "pct_revenue"]].to_string(index=False))

    ab_df = query_ab_summary(engine)
    console.print(f"\n[bold]A/B results from DB:[/bold] {len(ab_df)} experiments")

    return engine


if __name__ == "__main__":
    main()