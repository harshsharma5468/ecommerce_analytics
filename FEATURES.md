# Feature Reference Guide
─────────────────────────────────────────────────────────────────────────────
Complete reference for all features added to NexaCommerce Analytics Platform

## Table of Contents

1. [Predictive ML Layer](#1-predictive-ml-layer)
2. [Real-Time Streaming](#2-real-time-streaming)
3. [Advanced Experimentation](#3-advanced-experimentation)
4. [Causal Inference](#4-causal-inference)
5. [Decision Engine](#5-decision-engine)
6. [Data Pipeline](#6-data-pipeline)
7. [dbt Transformations](#7-dbt-transformations)
8. [Feature Store](#8-feature-store)
9. [CI/CD & Testing](#9-cicd--testing)

---

## 1. Predictive ML Layer

### 1.1 Churn Prediction (`src/predictive/churn_model.py`)

**Purpose:** Predict which customers are likely to churn in the next 30/60/90 days.

**Algorithm:** XGBoost/LightGBM with SHAP explainability

**Usage:**
```python
from src.predictive import train_churn_model, ChurnPredictor

# Train model
predictor = train_churn_model(horizon_days=30, model_type="xgboost")

# Load saved model
predictor = ChurnPredictor.load()

# Predict
df['churn_prob'] = predictor.predict(df)
df['churn_pred'] = predictor.predict_class(df, threshold=0.5)

# Explainability
shap_values = predictor.get_shap_values(df)
importance = predictor.get_feature_importance(top_n=15)
```

**Key Features:**
- Handles class imbalance with `scale_pos_weight`
- 5-fold stratified cross-validation
- SHAP values for feature importance
- Adjustable decision threshold

**Output Columns:**
- `churn_probability` (float): Probability of churning
- `churn_predicted` (int): Binary prediction (0/1)

---

### 1.2 Survival Analysis (`src/predictive/survival_analysis.py`)

**Purpose:** Predict time until next purchase using survival analysis.

**Algorithms:**
- Kaplan-Meier (non-parametric)
- Cox Proportional Hazards (semi-parametric)
- Weibull AFT (parametric)

**Usage:**
```python
from src.predictive import train_survival_model, NextPurchasePredictor

# Train Cox model
predictor = train_survival_model(model_type="cox")

# Predict median time to next purchase
df['predicted_next_purchase_days'] = predictor.predict_median_time(df)

# Get survival probabilities
survival_probs = predictor.predict_survival_function(df, times=np.arange(0, 365, 7))

# Evaluate
ci = predictor.get_concordance_index(df)
print(f"Concordance Index: {ci:.4f}")
```

**Output Columns:**
- `predicted_next_purchase_days` (float): Expected days until next purchase
- `survival_probability` (float): Probability of not churning at time t

---

### 1.3 CLV Model (`src/predictive/clv_model.py`)

**Purpose:** Calculate probabilistic Customer Lifetime Value using BG/NBD + Gamma-Gamma.

**Components:**
- **BG/NBD:** Models transaction frequency
- **Gamma-Gamma:** Models monetary value per transaction

**Usage:**
```python
from src.predictive import train_clv_model, CLVPredictor

# Train model
predictor = train_clv_model()

# Predict CLV
predictions = predictor.predict_clv(df)

# Access components
predictions['bgnbd_expected_transactions']  # Expected purchases in 52 weeks
predictions['prob_alive']                    # Probability customer is active
predictions['gg_expected_value']             # Expected transaction value
predictions['clv_bgnbd']                     # Final CLV estimate
```

**Output Columns:**
- `bgnbd_expected_transactions` (float)
- `prob_alive` (float)
- `gg_expected_value` (float)
- `clv_bgnbd` (float)

---

### 1.4 Product Recommendations (`src/predictive/recommendation_engine.py`)

**Purpose:** Generate personalized product recommendations.

**Algorithms:**
- ALS (Alternating Least Squares) Matrix Factorization
- Item-based Collaborative Filtering
- Hybrid scoring with popularity

**Usage:**
```python
from src.predictive import train_recommendation_model, ProductRecommender

# Train model
recommender = train_recommendation_model()

# Get recommendations for a customer
recs = recommender.recommend_for_user(
    customer_id=12345,
    n_recommendations=10,
    exclude_purchased=True
)

# Get similar items
similar = recommender.recommend_similar_items(
    product_id=678,
    n_recommendations=5
)

# Evaluate
metrics = recommender.evaluate(data)
print(f"Precision@10: {metrics['precision@k']:.4f}")
```

**Output Columns:**
- `product_id` (int)
- `score` (float): Recommendation score
- `similarity` (float): Item similarity score

---

## 2. Real-Time Streaming

### 2.1 Transaction Stream (`src/streaming/realtime_stream.py`)

**Purpose:** Simulate real-time transaction streaming with live RFM updates.

**Usage:**
```python
from src.streaming import (
    get_simulator,
    start_streaming,
    stop_streaming,
    get_streaming_data
)

# Start streaming
start_streaming()

# Get live data
data = get_streaming_data()
print(data['status']['live_metrics'])
# {
#   'transactions_per_minute': 12.5,
#   'revenue_per_minute': 1250.00,
#   'unique_customers_5min': 45
# }

# Stop streaming
stop_streaming()
```

**Components:**
- `TransactionStreamGenerator`: Creates realistic transaction events
- `RealTimeRFMUpdater`: Updates RFM scores as transactions arrive
- `StreamingDashboard`: Provides metrics for dashboard

**Metrics Available:**
- Transactions per minute (TPM)
- Revenue per minute (RPM)
- Unique customers (5-min window)
- Average order value
- Category breakdown
- Device type distribution
- Regional distribution

---

## 3. Advanced Experimentation

### 3.1 Sequential Testing (`src/ab_testing/advanced_ab_testing.py`)

**Purpose:** Run A/B tests with continuous monitoring without alpha inflation.

**Method:** Modified Sequential Probability Ratio Test (mSPRT)

**Usage:**
```python
from src.ab_testing.advanced_ab_testing import (
    SequentialTester,
    SequentialTestConfig
)

config = SequentialTestConfig(
    alpha=0.05,
    beta=0.20,
    effect_size=0.05,
    max_sample_size=10000
)

tester = SequentialTester(config)

# Update with each observation
for control_val, treatment_val in zip(control_data, treatment_data):
    tester.update(control_val, treatment_val)
    
    # Check if we can stop early
    if tester.stopped:
        print(f"Stopped early at n={tester.stopping_time}")
        break

results = tester.get_results()
print(f"Always-valid p-value: {results['always_valid_pvalue']}")
print(f"Decision: {results['decision']}")
```

**Output:**
- `always_valid_pvalue`: Valid under optional stopping
- `confidence_sequence`: Always-valid confidence interval
- `stopped`: Whether test stopped early
- `decision`: "reject_null", "fail_to_reject", or "max_sample_reached"

---

### 3.2 Thompson Sampling Bandit

**Purpose:** Automatically balance exploration vs exploitation in multi-armed bandits.

**Usage:**
```python
from src.ab_testing.advanced_ab_testing import ThompsonSamplingBandit

bandit = ThompsonSamplingBandit(
    n_arms=3,
    arm_names=['control', 'treatment_a', 'treatment_b']
)

# Run adaptive experiment
for _ in range(1000):
    arm = bandit.select_arm(use_thompson=True)
    reward = pull_arm(arm)  # Your function
    bandit.update(arm, reward)

# Get results
stats = bandit.get_arm_statistics()
print(stats[['arm_name', 'mean_reward', 'probability_best']])

# Calculate regret
regret = bandit.get_regret(optimal_mean=0.10)
```

**Output:**
- `n_pulls`: Number of times each arm was selected
- `mean_reward`: Estimated reward for each arm
- `probability_best`: Probability each arm is optimal

---

### 3.3 CUPED Variance Reduction

**Purpose:** Reduce variance in A/B tests using pre-experiment covariates.

**Usage:**
```python
from src.ab_testing.advanced_ab_testing import CUPEDAdjuster

adjuster = CUPEDAdjuster()

# Fit on control group
adjuster.fit(
    control_outcome,
    control_covariate  # Pre-experiment metric
)

# Adjust outcomes
adjusted_control = adjuster.adjust(control_outcome, control_covariate)
adjusted_treatment = adjuster.adjust(treatment_outcome, treatment_covariate)

# Calculate variance reduction
var_reduction = adjuster.get_variance_reduction(
    control_outcome,
    adjusted_control
)
print(f"Variance reduced by {var_reduction:.2%}")
```

---

### 3.4 SRM Detection

**Purpose:** Detect Sample Ratio Mismatch indicating randomization issues.

**Usage:**
```python
from src.ab_testing.advanced_ab_testing import detect_srm

result = detect_srm(
    observed=np.array([4500, 5500]),
    expected=np.array([0.5, 0.5])
)

if result['srm_detected']:
    print(f"⚠️ SRM detected! p={result['p_value']:.4f}")
    print(f"Effect size (Cramér's V): {result['cramers_v']:.3f}")
```

---

## 4. Causal Inference

### 4.1 Propensity Score Matching (`src/causal/inference.py`)

**Purpose:** Estimate treatment effects from observational data.

**Usage:**
```python
from src.causal import PropensityScoreMatcher

matcher = PropensityScoreMatcher(caliper=0.05, matching_ratio=1)

# Fit propensity model
matcher.fit_propensity_model(X_covariates, treatment_assignment)

# Match treated to controls
matched_data = matcher.match(X_covariates, treatment, outcome)

# Estimate ATT
att_results = matcher.estimate_att()
print(f"ATT: {att_results['att']:.4f}")
print(f"95% CI: [{att_results['ci_lower']:.4f}, {att_results['ci_upper']:.4f}]")

# Check balance
balance = matcher.check_balance()
print(f"Balanced covariates: {balance['balanced'].sum()}/{len(balance)}")
```

**Output:**
- `att`: Average Treatment Effect on the Treated
- `std_error`: Standard error
- `ci_lower`, `ci_upper`: 95% confidence interval
- `p_value`: Statistical significance

---

### 4.2 Difference-in-Differences

**Purpose:** Estimate causal effects using panel data.

**Usage:**
```python
from src.causal import DifferenceInDifferences

did = DifferenceInDifferences()
did.fit(
    panel_data,
    treatment_col='is_treated',
    period_col='is_post',
    outcome_col='revenue'
)

results = did.get_results()
print(f"DiD Estimate: {results['did_estimate']:.4f}")
print(f"Treatment change: {results['treatment_change']:.4f}")
print(f"Control change: {results['control_change']:.4f}")
```

---

### 4.3 Synthetic Control

**Purpose:** Construct counterfactual for treated unit using weighted controls.

**Usage:**
```python
from src.causal import SyntheticControl

sc = SyntheticControl()
sc.fit(
    panel_data,
    treatment_unit='California',
    unit_col='state',
    time_col='year',
    outcome_col='gdp',
    pre_period=(2010, 2019)
)

results = sc.get_results()
print(f"Top contributors: {results['top_contributors']}")
print(f"Pre-period RMSE: {sc.pre_period_rmse:.4f}")
```

---

## 5. Decision Engine

### 5.1 Anomaly Detection (CUSUM) (`src/reports/decision_engine.py`)

**Purpose:** Detect anomalies in time series using Cumulative Sum control chart.

**Usage:**
```python
from src.reports.decision_engine import CUSUMDetector

detector = CUSUMDetector(
    target=100,    # Process mean
    slack=0.5,     # Allowable deviation
    threshold=5.0  # Alert threshold
)

# Fit on historical data
detector.fit(historical_data)

# Monitor stream
for new_value in data_stream:
    is_anomaly, info = detector.update(new_value)
    if is_anomaly:
        print(f"⚠️ Anomaly: {info['anomaly_type']}")
        print(f"  Value: {info['value']:.2f}")
        print(f"  Deviation: {info['deviation']:.2f}")
```

---

### 5.2 What-If Simulator

**Purpose:** Simulate business scenarios and estimate revenue impact.

**Usage:**
```python
from src.reports.decision_engine import WhatIfSimulator

simulator = WhatIfSimulator(baseline_data)

# Scenario 1: Segment conversion
result = simulator.simulate_segment_conversion(
    from_segment='At Risk',
    to_segment='Loyal',
    conversion_rate=0.10
)
print(f"Revenue impact: ${result['annual_revenue_impact']:,.0f}")

# Scenario 2: Churn reduction
result = simulator.simulate_churn_reduction(
    churn_reduction_pct=0.25,
    target_segments=['At Risk', 'Hibernating']
)
print(f"Customers retained: {result['customers_retained']:.0f}")

# Scenario 3: Price change
result = simulator.simulate_price_change(
    price_change_pct=0.05,  # 5% increase
    affected_revenue=1000000
)
print(f"Profit impact: ${result['profit_change']:,.0f}")
```

---

### 5.3 Cohort Retention Heatmap

**Purpose:** Analyze and visualize cohort retention patterns.

**Usage:**
```python
from src.reports.decision_engine import CohortRetentionAnalyzer

analyzer = CohortRetentionAnalyzer()

# Prepare cohorts
analyzer.prepare_cohorts(transactions_df, cohort_period='month')

# Calculate retention matrix
retention = analyzer.calculate_retention()

# Plot heatmap
fig, ax = analyzer.plot_heatmap(save_path='retention_heatmap.png')

# Get summary stats
stats = analyzer.get_summary_stats()
print(f"Average P1 retention: {stats['avg_retention_p1']:.1%}")
print(f"Best cohort: {stats['best_cohort']}")
```

---

### 5.4 Auto-Generated Narratives

**Purpose:** Generate natural language summaries of analytics insights.

**Usage:**
```python
from src.reports.decision_engine import NarrativeGenerator

generator = NarrativeGenerator()

# KPI summary
summary = generator.generate_kpi_summary({
    'revenue': 1250000,
    'revenue_change': 12.5,
    'customers': 15000,
    'clv': 450,
    'top_segment': 'Champions',
    'top_segment_count': 1200
})

# Anomaly alert
alert = generator.generate_anomaly_alert(
    metric='Daily Revenue',
    value=85000,
    expected=100000,
    std=5000
)

# Executive summary
exec_summary = generator.generate_executive_summary({
    'revenue': 1250000,
    'opportunities': [...],
    'alerts': [...]
})
```

---

## 6. Data Pipeline

### 6.1 Prefect Orchestration (`src/pipeline/orchestrator.py`)

**Purpose:** Orchestrate data pipeline with retries, SLAs, and monitoring.

**Usage:**
```python
from src.pipeline import run_pipeline, run_pipeline_fallback

# Run with Prefect (if installed)
results = run_pipeline()

# Or run fallback mode
results = run_pipeline_fallback()

print(f"Generated {results['customers']} customers")
print(f"Generated {results['transactions']} transactions")
```

**Medallion Architecture:**
- **Bronze:** Raw data with validation
- **Silver:** Cleaned, standardized data
- **Gold:** Business-ready aggregations

---

## 7. dbt Transformations

### 7.1 Running dbt

```bash
# Run all models
dbt run

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve

# Run specific model
dbt run --model mart_customer_clv
```

### 7.2 Model Structure

```
dbt/models/
├── staging/
│   ├── stg_customers.sql      # Cleaned customer data
│   └── stg_transactions.sql   # Cleaned transaction data
├── intermediate/
│   └── int_rfm_segmentation.sql  # RFM calculations
├── marts/
│   └── mart_customer_clv.sql     # CLV mart table
└── schema.yml                   # Schema tests
```

---

## 8. Feature Store

### 8.1 Feast Configuration (`feature_store/feature_store.py`)

**Purpose:** Serve features for ML models with point-in-time correctness.

**Usage:**
```python
from feast import FeatureStore

store = FeatureStore(repo_path="feature_store")

# Get online features
features = store.get_online_features(
    features=[
        "rfm_features:recency",
        "rfm_features:frequency",
        "rfm_features:monetary",
        "clv_features:clv_12m",
    ],
    entity_rows=[{"customer_id": 12345}],
).to_dict()

# Get historical features for training
training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "customer_demographics:acquisition_channel",
        "rfm_features:rfm_composite",
        "clv_features:clv_12m",
    ],
).to_df()
```

**Feature Views:**
- `customer_demographics`: Customer attributes
- `transaction_features`: Aggregated transactions
- `rfm_features`: RFM scores and segments
- `clv_features`: CLV predictions

---

## 9. CI/CD & Testing

### 9.1 Running Tests

```bash
# Full test suite
pytest tests/ -v --cov=src --cov-report=html

# Parallel test execution
pytest tests/ -v -n auto

# Specific test category
pytest tests/ -v -m unit
pytest tests/ -v -m integration
```

### 9.2 GitHub Actions

The CI/CD pipeline (`.github/workflows/ci.yml`) runs:
- Multi-Python version testing (3.10, 3.11, 3.12)
- Cross-platform testing (Ubuntu, Windows)
- Data validation
- Security scanning (safety, bandit)
- Coverage reporting (Codecov)
- Documentation generation

### 9.3 Great Expectations Validation

```python
from src.pipeline.orchestrator import (
    create_customer_expectations,
    create_transaction_expectations
)

# Validate customers
customer_validation = create_customer_expectations(customers_df)
if not customer_validation['valid']:
    print(f"Issues: {customer_validation['issues']}")

# Validate transactions
txn_validation = create_transaction_expectations(transactions_df)
if not txn_validation['valid']:
    print(f"Issues: {txn_validation['issues']}")
```

---

## Quick Reference Card

| Feature | Module | Key Function |
|---------|--------|--------------|
| Churn Prediction | `src/predictive/churn_model.py` | `train_churn_model()` |
| Survival Analysis | `src/predictive/survival_analysis.py` | `train_survival_model()` |
| CLV Model | `src/predictive/clv_model.py` | `train_clv_model()` |
| Recommendations | `src/predictive/recommendation_engine.py` | `train_recommendation_model()` |
| Streaming | `src/streaming/realtime_stream.py` | `start_streaming()` |
| Sequential Testing | `src/ab_testing/advanced_ab_testing.py` | `SequentialTester()` |
| Thompson Sampling | `src/ab_testing/advanced_ab_testing.py` | `ThompsonSamplingBandit()` |
| PSM | `src/causal/inference.py` | `PropensityScoreMatcher()` |
| DiD | `src/causal/inference.py` | `DifferenceInDifferences()` |
| CUSUM | `src/reports/decision_engine.py` | `CUSUMDetector()` |
| What-If | `src/reports/decision_engine.py` | `WhatIfSimulator()` |
| Pipeline | `src/pipeline/orchestrator.py` | `run_pipeline()` |

---

*For more details, see the inline documentation in each module.*
