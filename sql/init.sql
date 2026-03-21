-- NexaCommerce Analytics Platform
-- PostgreSQL Database Initialization Script
-- This script runs automatically when the PostgreSQL container first starts

-- ──────────────────────────────────────────────────────────────────────────────
-- Enable Extensions
-- ──────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ──────────────────────────────────────────────────────────────────────────────
-- Create Schema
-- ──────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ml;

-- ──────────────────────────────────────────────────────────────────────────────
-- Raw Tables (Bronze Layer)
-- ──────────────────────────────────────────────────────────────────────────────

-- Customers table
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    age INTEGER,
    gender VARCHAR(20),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(50),
    registration_date TIMESTAMP,
    acquisition_channel VARCHAR(50),
    income_bracket VARCHAR(20),
    true_segment VARCHAR(50),
    is_email_opted_in BOOLEAN DEFAULT TRUE,
    is_push_opted_in BOOLEAN DEFAULT TRUE,
    lifetime_value_bucket VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE IF NOT EXISTS raw.products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(18, 2) NOT NULL,
    cost DECIMAL(18, 2),
    margin_pct DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions table
CREATE TABLE IF NOT EXISTS raw.transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    order_date TIMESTAMP NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(18, 2) NOT NULL,
    total_amount DECIMAL(18, 2) NOT NULL,
    category VARCHAR(100),
    payment_method VARCHAR(50),
    device_type VARCHAR(20),
    session_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_customer
        FOREIGN KEY (customer_id) REFERENCES raw.customers(customer_id),
    CONSTRAINT fk_product
        FOREIGN KEY (product_id) REFERENCES raw.products(product_id)
);

-- Sessions table
CREATE TABLE IF NOT EXISTS raw.sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    customer_id INTEGER,
    session_date TIMESTAMP NOT NULL,
    device_type VARCHAR(20),
    browser VARCHAR(50),
    os VARCHAR(50),
    referrer VARCHAR(255),
    landing_page VARCHAR(255),
    bounce BOOLEAN DEFAULT FALSE,
    session_duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- A/B Test Assignments
CREATE TABLE IF NOT EXISTS raw.ab_test_assignments (
    assignment_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    experiment_name VARCHAR(100) NOT NULL,
    variant VARCHAR(50) NOT NULL,  -- 'control' or 'treatment'
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_customer_experiment
        UNIQUE (customer_id, experiment_name)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Staging Tables (Silver Layer)
-- ──────────────────────────────────────────────────────────────────────────────

-- Cleaned customers
CREATE TABLE IF NOT EXISTS staging.customers (
    customer_id INTEGER PRIMARY KEY,
    customer_key UUID DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    gender VARCHAR(20),
    country VARCHAR(100),
    region VARCHAR(50),
    registration_date DATE,
    acquisition_channel VARCHAR(50),
    is_email_opted_in BOOLEAN,
    is_push_opted_in BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cleaned transactions
CREATE TABLE IF NOT EXISTS staging.transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    transaction_key UUID DEFAULT uuid_generate_v4(),
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    order_date TIMESTAMP NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(18, 2) NOT NULL,
    total_amount DECIMAL(18, 2) NOT NULL,
    category VARCHAR(100),
    order_year INTEGER,
    order_month INTEGER,
    order_quarter INTEGER,
    order_day_of_week INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Analytics Tables (Gold Layer)
-- ──────────────────────────────────────────────────────────────────────────────

-- RFM Segmentation
CREATE TABLE IF NOT EXISTS analytics.rfm_segmentation (
    customer_id INTEGER PRIMARY KEY,
    recency INTEGER NOT NULL,
    frequency INTEGER NOT NULL,
    monetary DECIMAL(18, 2) NOT NULL,
    avg_order_value DECIMAL(18, 2),
    total_items INTEGER,
    distinct_categories INTEGER,
    first_purchase TIMESTAMP,
    last_purchase TIMESTAMP,
    customer_age_days INTEGER,
    r_score INTEGER NOT NULL,
    f_score INTEGER NOT NULL,
    m_score INTEGER NOT NULL,
    rfm_score INTEGER NOT NULL,
    rfm_composite INTEGER NOT NULL,
    segment VARCHAR(50) NOT NULL,
    acquisition_channel VARCHAR(50),
    region VARCHAR(50),
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customer CLV
CREATE TABLE IF NOT EXISTS analytics.customer_clv (
    customer_id INTEGER PRIMARY KEY,
    clv_12m DECIMAL(18, 2) NOT NULL,
    clv_decile INTEGER NOT NULL,
    segment VARCHAR(50),
    acquisition_channel VARCHAR(50),
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily Metrics
CREATE TABLE IF NOT EXISTS analytics.daily_metrics (
    date DATE PRIMARY KEY,
    total_revenue DECIMAL(18, 2),
    total_orders INTEGER,
    unique_customers INTEGER,
    avg_order_value DECIMAL(18, 2),
    new_customers INTEGER,
    returning_customers INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ──────────────────────────────────────────────────────────────────────────────
-- ML Tables
-- ──────────────────────────────────────────────────────────────────────────────

-- Churn Predictions
CREATE TABLE IF NOT EXISTS ml.churn_predictions (
    customer_id INTEGER PRIMARY KEY,
    churn_probability DECIMAL(5, 4),
    churn_predicted BOOLEAN,
    model_version VARCHAR(20),
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product Recommendations
CREATE TABLE IF NOT EXISTS ml.product_recommendations (
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    score DECIMAL(10, 6) NOT NULL,
    rank INTEGER NOT NULL,
    model_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, product_id)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- Indexes for Performance
-- ──────────────────────────────────────────────────────────────────────────────

-- Customer indexes
CREATE INDEX IF NOT EXISTS idx_customers_email ON raw.customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_acquisition_channel ON raw.customers(acquisition_channel);
CREATE INDEX IF NOT EXISTS idx_customers_registration_date ON raw.customers(registration_date);

-- Transaction indexes
CREATE INDEX IF NOT EXISTS idx_transactions_customer_id ON raw.transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_product_id ON raw.transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_transactions_order_date ON raw.transactions(order_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON raw.transactions(category);

-- RFM indexes
CREATE INDEX IF NOT EXISTS idx_rfm_segment ON analytics.rfm_segmentation(segment);
CREATE INDEX IF NOT EXISTS idx_rfm_score ON analytics.rfm_segmentation(rfm_score);

-- ──────────────────────────────────────────────────────────────────────────────
-- Views for Common Queries
-- ──────────────────────────────────────────────────────────────────────────────

-- Segment summary view
CREATE OR REPLACE VIEW analytics.vw_segment_summary AS
SELECT 
    segment,
    COUNT(*) as n_customers,
    ROUND(AVG(recency), 1) as avg_recency,
    ROUND(AVG(frequency), 2) as avg_frequency,
    ROUND(AVG(monetary), 2) as avg_monetary,
    ROUND(SUM(monetary), 2) as total_revenue,
    ROUND(AVG(rfm_composite), 1) as avg_rfm_composite
FROM analytics.rfm_segmentation
GROUP BY segment
ORDER BY avg_monetary DESC;

-- Revenue by acquisition channel
CREATE OR REPLACE VIEW analytics.vw_revenue_by_channel AS
SELECT 
    r.acquisition_channel,
    COUNT(DISTINCT r.customer_id) as n_customers,
    ROUND(SUM(r.monetary), 2) as total_revenue,
    ROUND(AVG(r.monetary), 2) as avg_revenue_per_customer,
    ROUND(AVG(r.clv_12m), 2) as avg_clv
FROM analytics.rfm_segmentation r
LEFT JOIN analytics.customer_clv c ON r.customer_id = c.customer_id
GROUP BY r.acquisition_channel
ORDER BY total_revenue DESC;

-- Daily revenue trend
CREATE OR REPLACE VIEW analytics.vw_daily_revenue AS
SELECT 
    DATE(order_date) as date,
    COUNT(*) as n_orders,
    SUM(total_amount) as total_revenue,
    AVG(total_amount) as avg_order_value,
    COUNT(DISTINCT customer_id) as unique_customers
FROM raw.transactions
GROUP BY DATE(order_date)
ORDER BY date DESC;

-- ──────────────────────────────────────────────────────────────────────────────
-- Insert Sample Data (for testing)
-- ──────────────────────────────────────────────────────────────────────────────

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA raw TO analytics_user;
GRANT ALL PRIVILEGES ON SCHEMA staging TO analytics_user;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO analytics_user;
GRANT ALL PRIVILEGES ON SCHEMA ml TO analytics_user;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA raw TO analytics_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA staging TO analytics_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO analytics_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ml TO analytics_user;

-- Grant on sequences
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO analytics_user;

-- Comment on tables
COMMENT ON TABLE raw.customers IS 'Bronze layer: Raw customer data';
COMMENT ON TABLE raw.transactions IS 'Bronze layer: Raw transaction data';
COMMENT ON TABLE staging.customers IS 'Silver layer: Cleaned customer data';
COMMENT ON TABLE staging.transactions IS 'Silver layer: Cleaned transaction data';
COMMENT ON TABLE analytics.rfm_segmentation IS 'Gold layer: RFM segmentation results';
COMMENT ON TABLE analytics.customer_clv IS 'Gold layer: Customer lifetime value';
