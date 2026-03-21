-- ═══════════════════════════════════════════════════════════════════════════
-- E-Commerce Analytics – Advanced SQL Query Library
-- For PostgreSQL (primary) | annotated for SQLite compatibility
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. RFM Segment Revenue Contribution (Pareto Analysis) ──────────────────
WITH seg_revenue AS (
    SELECT
        s.segment,
        COUNT(DISTINCT t.customer_id)       AS n_customers,
        COUNT(DISTINCT t.order_id)          AS n_orders,
        ROUND(SUM(t.revenue), 2)            AS total_revenue,
        ROUND(SUM(t.gross_profit), 2)       AS gross_profit,
        ROUND(AVG(s.clv_12m), 2)            AS avg_clv_12m,
        ROUND(AVG(s.recency), 1)            AS avg_recency_days,
        ROUND(AVG(s.frequency), 1)          AS avg_frequency,
        ROUND(AVG(s.monetary), 2)           AS avg_monetary
    FROM transactions t
    JOIN rfm_segments s ON t.customer_id = s.customer_id
    WHERE t.revenue > 0
    GROUP BY s.segment
),
totals AS (
    SELECT SUM(total_revenue) AS grand_total FROM seg_revenue
)
SELECT
    sr.*,
    ROUND(sr.total_revenue / t.grand_total * 100, 2)  AS pct_revenue,
    ROUND(sr.gross_profit / sr.total_revenue * 100, 2) AS gp_margin_pct,
    SUM(sr.total_revenue) OVER (ORDER BY sr.total_revenue DESC
                                  ROWS UNBOUNDED PRECEDING) AS cumulative_revenue,
    ROUND(SUM(sr.total_revenue) OVER (ORDER BY sr.total_revenue DESC
          ROWS UNBOUNDED PRECEDING) / t.grand_total * 100, 2) AS cumulative_pct
FROM seg_revenue sr, totals t
ORDER BY total_revenue DESC;


-- ─── 2. Customer Cohort Retention (Monthly) ──────────────────────────────────
-- PostgreSQL version
WITH cohorts AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(transaction_date))::DATE AS cohort_month
    FROM transactions
    GROUP BY customer_id
),
activity AS (
    SELECT
        t.customer_id,
        c.cohort_month,
        DATE_TRUNC('month', t.transaction_date)::DATE AS activity_month,
        EXTRACT(MONTH FROM AGE(
            DATE_TRUNC('month', t.transaction_date),
            c.cohort_month
        ))::INT AS months_since_cohort
    FROM transactions t
    JOIN cohorts c ON t.customer_id = c.customer_id
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_size
    FROM cohorts GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    a.months_since_cohort,
    COUNT(DISTINCT a.customer_id)    AS retained_customers,
    cs.cohort_size,
    ROUND(COUNT(DISTINCT a.customer_id)::NUMERIC / cs.cohort_size * 100, 2) AS retention_rate
FROM activity a
JOIN cohort_sizes cs ON a.cohort_month = cs.cohort_month
GROUP BY a.cohort_month, a.months_since_cohort, cs.cohort_size
ORDER BY a.cohort_month, a.months_since_cohort;


-- ─── 3. Product Affinity / Market Basket Analysis (Top Pairs) ────────────────
-- Find products frequently bought together in same order
WITH order_products AS (
    SELECT order_id, product_id, category
    FROM transactions
    WHERE revenue > 0
    GROUP BY order_id, product_id, category
),
product_pairs AS (
    SELECT
        a.product_id AS product_a,
        b.product_id AS product_b,
        a.category   AS cat_a,
        b.category   AS cat_b,
        COUNT(*)     AS co_occurrences
    FROM order_products a
    JOIN order_products b ON a.order_id = b.order_id AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id, a.category, b.category
)
SELECT *
FROM product_pairs
ORDER BY co_occurrences DESC
LIMIT 50;


-- ─── 4. Acquisition Channel ROI ───────────────────────────────────────────────
SELECT
    c.acquisition_channel,
    COUNT(DISTINCT c.customer_id)          AS total_customers,
    ROUND(AVG(s.clv_12m), 2)              AS avg_clv_12m,
    ROUND(SUM(s.clv_12m), 2)              AS total_clv_12m,
    ROUND(AVG(s.monetary), 2)             AS avg_ltv,
    ROUND(AVG(s.frequency), 2)            AS avg_orders,
    ROUND(AVG(s.recency), 1)              AS avg_recency,
    -- Champions % per channel
    ROUND(SUM(CASE WHEN s.segment = 'Champions' THEN 1 ELSE 0 END)::NUMERIC
          / COUNT(*) * 100, 2)            AS pct_champions,
    ROUND(SUM(CASE WHEN s.segment IN ('Hibernating','Lost') THEN 1 ELSE 0 END)::NUMERIC
          / COUNT(*) * 100, 2)            AS pct_churned
FROM customers c
JOIN rfm_segments s ON c.customer_id = s.customer_id
GROUP BY c.acquisition_channel
ORDER BY avg_clv_12m DESC;


-- ─── 5. A/B Test Statistical Summary with Decision Matrix ────────────────────
SELECT
    experiment_name,
    description,
    n_control + n_treatment                     AS total_participants,
    ROUND(control_mean * 100, 3)               AS control_rate_pct,
    ROUND(treatment_mean * 100, 3)             AS treatment_rate_pct,
    ROUND(relative_lift * 100, 2)              AS relative_lift_pct,
    ROUND(p_value_ttest, 6)                    AS p_value,
    ROUND(p_value_adjusted, 6)                 AS p_value_fdr,
    ROUND(observed_power * 100, 1)             AS power_pct,
    required_sample_size,
    ROUND(bayesian_prob_treatment_better * 100, 1) AS bayesian_prob_pct,
    CASE
        WHEN is_significant AND relative_lift > 0.05 THEN 'SHIP'
        WHEN is_significant AND relative_lift > 0     THEN 'CONSIDER'
        WHEN is_significant AND relative_lift < 0     THEN 'REJECT'
        WHEN NOT is_significant AND observed_power < 0.8 THEN 'EXTEND'
        ELSE 'NO_EFFECT'
    END                                        AS decision,
    is_significant,
    is_practical
FROM ab_test_results
ORDER BY p_value;


-- ─── 6. Segment Migration Potential ──────────────────────────────────────────
-- How many customers are on the boundary between segments?
SELECT
    segment,
    COUNT(*)                             AS n_customers,
    ROUND(AVG(RFM_composite), 3)        AS avg_rfm,
    ROUND(STDDEV(RFM_composite), 3)     AS std_rfm,
    ROUND(AVG(clv_12m), 2)             AS avg_clv,
    -- Customers close to upgrading (within 0.3 RFM units of next tier)
    COUNT(CASE WHEN RFM_composite BETWEEN
        (SELECT PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY RFM_composite) FROM rfm_segments)
        - 0.3 AND
        (SELECT PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY RFM_composite) FROM rfm_segments)
        THEN 1 END)                      AS upgrade_candidates
FROM rfm_segments
GROUP BY segment
ORDER BY avg_rfm DESC;


-- ─── 7. Revenue Seasonality Decomposition ────────────────────────────────────
SELECT
    STRFTIME('%w', transaction_date)     AS day_of_week,  -- 0=Sun
    STRFTIME('%H', transaction_date)     AS hour_of_day,
    COUNT(DISTINCT order_id)             AS n_orders,
    ROUND(SUM(revenue), 2)               AS total_revenue,
    ROUND(AVG(revenue), 2)               AS avg_order_revenue,
    ROUND(AVG(seasonality_factor), 3)    AS avg_seasonality
FROM transactions
WHERE revenue > 0
GROUP BY day_of_week, hour_of_day
ORDER BY total_revenue DESC;


-- ─── 8. Customer Lifetime Value Deciles ──────────────────────────────────────
WITH clv_deciles AS (
    SELECT
        customer_id,
        segment,
        clv_12m,
        NTILE(10) OVER (ORDER BY clv_12m DESC) AS decile
    FROM rfm_segments
)
SELECT
    decile,
    COUNT(*)                                AS n_customers,
    ROUND(MIN(clv_12m), 2)                 AS min_clv,
    ROUND(MAX(clv_12m), 2)                 AS max_clv,
    ROUND(AVG(clv_12m), 2)                 AS avg_clv,
    ROUND(SUM(clv_12m), 2)                 AS total_clv,
    ROUND(SUM(clv_12m) / SUM(SUM(clv_12m)) OVER () * 100, 2) AS pct_total_clv,
    MODE() WITHIN GROUP (ORDER BY segment) AS dominant_segment
FROM clv_deciles
GROUP BY decile
ORDER BY decile;


-- ─── 9. Return Rate Analysis by Category & Segment ───────────────────────────
SELECT
    t.category,
    s.segment,
    COUNT(*)                                          AS total_items,
    SUM(CASE WHEN t.is_returned THEN 1 ELSE 0 END)  AS returned_items,
    ROUND(SUM(CASE WHEN t.is_returned THEN 1 ELSE 0 END)::NUMERIC
          / COUNT(*) * 100, 2)                        AS return_rate_pct,
    ROUND(ABS(SUM(CASE WHEN t.revenue < 0 THEN t.revenue ELSE 0 END)), 2) AS lost_revenue
FROM transactions t
JOIN rfm_segments s ON t.customer_id = s.customer_id
GROUP BY t.category, s.segment
ORDER BY return_rate_pct DESC;


-- ─── 10. Experiment Sample Ratio Mismatch (SRM) Check ─────────────────────────
-- SRM: chi-square test that control/treatment split is as expected (50/50)
SELECT
    experiment_name,
    SUM(CASE WHEN variant = 'control' THEN 1 ELSE 0 END)   AS n_control,
    SUM(CASE WHEN variant = 'treatment' THEN 1 ELSE 0 END) AS n_treatment,
    COUNT(*)                                                 AS total,
    ROUND(
        SUM(CASE WHEN variant = 'control' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100, 2
    )                                                        AS control_pct,
    -- Simple SRM indicator: >5% deviation from 50/50
    CASE WHEN ABS(
        SUM(CASE WHEN variant = 'control' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) - 0.5
    ) > 0.05 THEN 'SRM_DETECTED' ELSE 'OK' END              AS srm_check
FROM web_sessions
GROUP BY experiment_name
ORDER BY experiment_name;
