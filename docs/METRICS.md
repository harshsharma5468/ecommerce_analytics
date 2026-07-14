# Metric contract

| Metric | Definition | Grain | Guardrail |
|---|---|---|---|
| Net revenue | Revenue less refunds | Day | Deduplicate by order ID and exclude cancelled orders. |
| Orders | Unique order IDs | Day | Never use raw row count. |
| AOV | Net revenue divided by orders | Day | Null when orders are zero. |
| Repeat purchase rate | Repeat customers divided by active customers | Month | Requires stable customer IDs. |
| Retention | Customers returning in month N divided by original cohort | Cohort-month | Cohorts are based on first observed order. |

## Decision rules

- A revenue anomaly is flagged at absolute robust z-score of at least 3.5.
- Inventory is critical below seven days of cover.
- Reorder is recommended below the configured target days of cover, default 21.

These rules are transparent defaults, not universal business thresholds. They should be calibrated to the company operating model.
