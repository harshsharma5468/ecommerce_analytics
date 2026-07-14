# NexaCommerce Decision Intelligence

A production-style e-commerce analytics project that converts transaction, customer and inventory data into trusted executive decisions.

## What it delivers

- Executive KPIs: net revenue, orders, customers and AOV.
- Cohort retention analysis from first purchase through repeat orders.
- Robust revenue anomaly detection using median absolute deviation rather than fragile mean-only thresholds.
- Inventory prioritisation based on days of cover and suggested reorder quantity.
- An explainable action queue for revenue and inventory teams.
- Existing RFM segmentation, A/B experimentation and predictive modules remain available.

## Decision-intelligence architecture

Raw transactions and inventory → validated KPI layer → cohorts, anomaly detection and inventory cover → action queue → Streamlit executive dashboard.

## Metric contract

The metric definitions and guardrails are documented in docs/METRICS.md. This avoids ambiguous dashboard numbers and makes the project reviewable in an interview.

## Run locally

1. Create a Python 3.12 environment.
2. Install dependencies with pip install -r requirements.txt.
3. Run the pipeline with python run_pipeline.py.
4. Launch the dashboard with streamlit run src/dashboard/app.py.
5. Run quality tests with pytest tests -v.

## Advanced engineering practices

| Area | Included |
|---|---|
| Analytics modelling | KPI grain and guardrails, cohort retention and RFM segmentation |
| Statistics | A/B testing and robust anomaly detection |
| Decision support | Prioritised action queue and inventory days-of-cover |
| Machine learning | Churn, CLV, survival and recommendation modules |
| Reproducibility | Pinned dependencies, automated tests and Docker Compose |
| Operations | PostgreSQL, Redis, optional streaming and dbt profiles |

## Limitations

The supplied pipeline can generate synthetic data for demonstration. Business conclusions should only be made after connecting validated production order, customer and inventory sources. Thresholds in the action queue are configurable operating rules and require calibration to the business.
