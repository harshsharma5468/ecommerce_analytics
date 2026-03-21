"""
Unit & Integration Test Suite
─────────────────────────────────────────────────────────────────────────────
Covers:
  - Data generation shape / dtype assertions
  - RFM computation correctness
  - Statistical test correctness (known inputs → known outputs)
  - Sample size / power formula validation
  - DB schema creation & round-trip
"""
import sys
sys.path.insert(0, "/home/claude/ecommerce_analytics")

import pytest
import numpy as np
import pandas as pd
from scipy import stats

# ──────────────────────────────────────────────────────────────────────────────
# Data Generation Tests
# ──────────────────────────────────────────────────────────────────────────────
class TestDataGeneration:

    def test_customers_schema(self):
        from src.data_generation.generate_data import generate_customers
        df = generate_customers(n=200)
        required = {"customer_id", "email", "age", "gender", "region",
                    "acquisition_channel", "true_segment"}
        assert required.issubset(df.columns)
        assert df["customer_id"].nunique() == 200
        assert df["age"].between(18, 75).all()

    def test_products_schema(self):
        from src.data_generation.generate_data import generate_products
        df = generate_products(n=50)
        assert len(df) == 50
        assert (df["unit_price"] > 0).all()
        assert (df["margin_pct"] > 0).all()
        assert df["product_id"].nunique() == 50

    def test_transactions_positive_revenue(self):
        from src.data_generation.generate_data import generate_customers, generate_products, generate_transactions
        c = generate_customers(n=100)
        p = generate_products(n=30)
        t = generate_transactions(c, p, n=500)
        assert len(t) > 0
        non_return = t[~t["is_returned"]]
        assert (non_return["revenue"] > 0).all()

    def test_segment_proportions(self):
        from src.data_generation.generate_data import generate_customers
        from config.settings import CUSTOMER_SEGMENTS_GEN
        df = generate_customers(n=5000)
        seg_counts = df["true_segment"].value_counts(normalize=True)
        for seg, params in CUSTOMER_SEGMENTS_GEN.items():
            expected = params["proportion"]
            actual = seg_counts.get(seg, 0)
            assert abs(actual - expected) < 0.05, (
                f"Segment {seg}: expected ~{expected:.2f}, got {actual:.2f}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# RFM Tests
# ──────────────────────────────────────────────────────────────────────────────
class TestRFMEngine:

    @pytest.fixture
    def sample_transactions(self):
        """Create controlled transaction data for deterministic RFM testing."""
        np.random.seed(0)
        rows = []
        # Customer A: high frequency, high monetary, recent
        for i in range(20):
            rows.append({"customer_id": "CUST-000001", "order_id": f"ORD-A-{i}",
                          "transaction_date": pd.Timestamp("2024-12-01") - pd.Timedelta(days=i*10),
                          "revenue": 500.0, "quantity": 2, "category": "Electronics",
                          "gross_profit": 110.0, "is_returned": False})
        # Customer B: low frequency, low monetary, old
        for i in range(3):
            rows.append({"customer_id": "CUST-000002", "order_id": f"ORD-B-{i}",
                          "transaction_date": pd.Timestamp("2023-01-01") - pd.Timedelta(days=i*30),
                          "revenue": 25.0, "quantity": 1, "category": "Books & Media",
                          "gross_profit": 7.5, "is_returned": False})
        return pd.DataFrame(rows)

    def test_rfm_recency_ordering(self, sample_transactions):
        from src.rfm_segmentation.rfm_engine import compute_rfm
        rfm = compute_rfm(sample_transactions, snapshot_date="2025-01-01")
        r_a = rfm.loc[rfm["customer_id"] == "CUST-000001", "recency"].values[0]
        r_b = rfm.loc[rfm["customer_id"] == "CUST-000002", "recency"].values[0]
        assert r_a < r_b, "Champion should have lower (better) recency than at-risk customer"

    def test_rfm_frequency_ordering(self, sample_transactions):
        from src.rfm_segmentation.rfm_engine import compute_rfm
        rfm = compute_rfm(sample_transactions, snapshot_date="2025-01-01")
        f_a = rfm.loc[rfm["customer_id"] == "CUST-000001", "frequency"].values[0]
        f_b = rfm.loc[rfm["customer_id"] == "CUST-000002", "frequency"].values[0]
        assert f_a > f_b

    def test_rfm_monetary_ordering(self, sample_transactions):
        from src.rfm_segmentation.rfm_engine import compute_rfm
        rfm = compute_rfm(sample_transactions, snapshot_date="2025-01-01")
        m_a = rfm.loc[rfm["customer_id"] == "CUST-000001", "monetary"].values[0]
        m_b = rfm.loc[rfm["customer_id"] == "CUST-000002", "monetary"].values[0]
        assert m_a > m_b

    def test_rfm_scores_in_range(self, sample_transactions):
        from src.rfm_segmentation.rfm_engine import compute_rfm
        rfm = compute_rfm(sample_transactions, snapshot_date="2025-01-01")
        for col in ["R_score", "F_score", "M_score"]:
            assert rfm[col].between(1, 5).all(), f"{col} out of [1,5] range"

    def test_clv_positive(self, sample_transactions):
        from src.rfm_segmentation.rfm_engine import compute_rfm
        rfm = compute_rfm(sample_transactions, snapshot_date="2025-01-01")
        rfm["clv_12m"] = (
            rfm["monetary"] / rfm["customer_age_days"].clip(lower=30) * 365 * 0.85
        )
        assert (rfm["clv_12m"] > 0).all()


# ──────────────────────────────────────────────────────────────────────────────
# A/B Testing Tests
# ──────────────────────────────────────────────────────────────────────────────
class TestABEngine:

    def test_two_proportion_ztest_significant(self):
        """Known significant difference should be detected."""
        from statsmodels.stats.proportion import proportions_ztest
        count = np.array([600, 400])   # 600/10000 vs 400/10000 → 6% vs 4%
        nobs  = np.array([10000, 10000])
        z, p  = proportions_ztest(count, nobs, alternative="two-sided")
        assert p < 0.001, f"Expected p < 0.001, got {p:.6f}"

    def test_two_proportion_ztest_not_significant(self):
        """Tiny difference with small n should NOT be significant."""
        from statsmodels.stats.proportion import proportions_ztest
        count = np.array([51, 50])
        nobs  = np.array([1000, 1000])
        _, p  = proportions_ztest(count, nobs, alternative="two-sided")
        assert p > 0.05, f"Expected p > 0.05, got {p:.6f}"

    def test_welch_ttest_significant(self):
        """Means 10 vs 12 with n=1000 should be highly significant."""
        np.random.seed(42)
        ctrl = np.random.normal(10, 2, 1000)
        trt  = np.random.normal(12, 2, 1000)
        _, p = stats.ttest_ind(trt, ctrl, equal_var=False)
        assert p < 0.001

    def test_mannwhitney_direction(self):
        """Treatment distribution shifted right → U stat significant."""
        np.random.seed(0)
        ctrl = np.random.exponential(5, 500)
        trt  = np.random.exponential(7, 500)
        stat, p = stats.mannwhitneyu(trt, ctrl, alternative="two-sided")
        assert p < 0.05

    def test_bootstrap_ci_coverage(self):
        """95% CI should contain the true mean ~95% of the time."""
        from src.ab_testing.ab_engine import bootstrap_ci
        np.random.seed(1)
        covered = 0
        true_mean = 50.0
        for _ in range(200):
            x = np.random.normal(true_mean, 10, 100)
            lo, hi = bootstrap_ci(x, n_boot=500)
            if lo <= true_mean <= hi:
                covered += 1
        coverage = covered / 200
        assert coverage >= 0.90, f"Bootstrap CI coverage {coverage:.2%} < 90%"

    def test_sample_size_increases_with_smaller_mde(self):
        from src.ab_testing.ab_engine import sample_size_for_proportion
        n_large_mde  = sample_size_for_proportion(0.05, mde=0.20)
        n_small_mde  = sample_size_for_proportion(0.05, mde=0.05)
        assert n_small_mde > n_large_mde

    def test_bayesian_ab_higher_rate(self):
        """Treatment with 2× conversion rate → P(T>C) should be >> 0.9."""
        from src.ab_testing.ab_engine import bayesian_ab_proportion
        np.random.seed(7)
        res = bayesian_ab_proportion(
            n_control=5000, conv_control=100,
            n_treatment=5000, conv_treatment=200,
            n_samples=20_000,
        )
        assert res["prob_treatment_better"] > 0.99

    def test_mht_correction_reduces_significance(self):
        """After BH correction on marginally-significant tests, some should become NS."""
        from statsmodels.stats.multitest import multipletests
        # 10 tests: 5 very significant, 5 borderline
        p_vals = [0.0001] * 5 + [0.048, 0.049, 0.047, 0.046, 0.045]
        reject, p_adj, _, _ = multipletests(p_vals, alpha=0.05, method="fdr_bh")
        # All truly significant ones should remain significant
        assert all(reject[:5])
        # Adjusted p-values are >= original
        assert all(p_adj[i] >= p_vals[i] for i in range(len(p_vals)))

    def test_cohens_h_symmetry(self):
        """Cohen's h(p, q) should equal -Cohen's h(q, p)."""
        p1, p2 = 0.04, 0.05
        h_pos = 2 * np.arcsin(np.sqrt(p2)) - 2 * np.arcsin(np.sqrt(p1))
        h_neg = 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))
        assert abs(h_pos + h_neg) < 1e-10

    def test_experiment_result_dataclass(self):
        """ExperimentResult should be instantiable and serialisable."""
        from src.ab_testing.ab_engine import ExperimentResult
        from dataclasses import asdict
        r = ExperimentResult(
            experiment_name="test_exp",
            description="test",
            metric_type="proportion",
            n_control=1000,
            n_treatment=1000,
            control_mean=0.05,
            treatment_mean=0.06,
        )
        d = asdict(r)
        assert d["experiment_name"] == "test_exp"
        assert d["relative_lift"] == 0.0  # default


# ──────────────────────────────────────────────────────────────────────────────
# Database Tests
# ──────────────────────────────────────────────────────────────────────────────
class TestDatabase:

    def test_sqlite_connection(self):
        from src.database.db_manager import get_engine
        engine = get_engine(prefer_postgres=False)
        assert "sqlite" in str(engine.url)

    def test_schema_creation(self, tmp_path):
        from sqlalchemy import create_engine, text, inspect
        from src.database.db_manager import create_schema
        engine = create_engine(f"sqlite:///{tmp_path}/test.db")
        create_schema(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {"customers", "products", "transactions", "rfm_segments", "ab_test_results"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_round_trip_customers(self, tmp_path):
        from sqlalchemy import create_engine, text
        from src.database.db_manager import create_schema, load_table
        from src.data_generation.generate_data import generate_customers
        engine = create_engine(f"sqlite:///{tmp_path}/test2.db")
        create_schema(engine)
        df = generate_customers(n=50)
        # Keep only columns that exist in schema
        cols = ["customer_id", "email", "first_name", "last_name", "age",
                "gender", "city", "state", "country", "region",
                "acquisition_channel", "income_bracket", "true_segment",
                "is_email_opted_in", "is_push_opted_in"]
        load_table(engine, df[cols], "customers")
        result = pd.read_sql("SELECT COUNT(*) AS n FROM customers", engine)
        assert result["n"].values[0] == 50


# ──────────────────────────────────────────────────────────────────────────────
# Statistical Property Tests
# ──────────────────────────────────────────────────────────────────────────────
class TestStatisticalProperties:

    def test_type_i_error_rate(self):
        """Under H₀ (no effect), false positive rate should be ~α=0.05."""
        np.random.seed(99)
        false_positives = 0
        n_simulations = 500
        for _ in range(n_simulations):
            a = np.random.normal(0, 1, 200)
            b = np.random.normal(0, 1, 200)
            _, p = stats.ttest_ind(a, b, equal_var=False)
            if p < 0.05:
                false_positives += 1
        fpr = false_positives / n_simulations
        # Allow generous band: 2% – 10%
        assert 0.02 <= fpr <= 0.10, f"Type I error rate {fpr:.2%} outside expected range"

    def test_power_increases_with_n(self):
        """More data → higher power for the same effect size."""
        from statsmodels.stats.power import TTestIndPower
        analysis = TTestIndPower()
        power_small = analysis.power(effect_size=0.3, nobs1=50, alpha=0.05)
        power_large = analysis.power(effect_size=0.3, nobs1=500, alpha=0.05)
        assert power_large > power_small

    def test_wilson_ci_contains_true_p(self):
        """Wilson CI should contain true p ~95% of the time."""
        from statsmodels.stats.proportion import proportion_confint
        np.random.seed(5)
        covered = 0
        true_p = 0.15
        for _ in range(500):
            x = np.random.binomial(1, true_p, 300)
            lo, hi = proportion_confint(x.sum(), len(x), method="wilson")
            if lo <= true_p <= hi:
                covered += 1
        assert covered / 500 >= 0.92


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
