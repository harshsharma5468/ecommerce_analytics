# Metric and decision contract

| Metric | Definition | Grain | Guardrail |
|---|---|---|---|
| Net revenue | Revenue less refunds | Day | Deduplicate by order ID; invalid dates are excluded. |
| Orders | Unique order IDs | Day | Never use raw row count. |
| AOV | Net revenue divided by orders | Day | Null when no orders exist. |
| Repeat purchase rate | Repeat customers divided by active customers | Month | Requires stable customer IDs. |
| Retention | Returning cohort customers divided by cohort size | Cohort-month | Cohort is first observed valid order. |

## Central policy

Decision thresholds are defined in the DecisionPolicy dataclass rather than being spread through business logic.

- Revenue anomaly: robust z-score at or above 3.5 by default.
- Critical inventory: under 7 days of cover.
- Reorder inventory: under 21 days of cover.
- Zero average demand: labeled no_demand, never silently healthy.

A deployment can pass a different DecisionPolicy into anomaly, inventory, or action functions to calibrate these defaults without rewriting calculations.
