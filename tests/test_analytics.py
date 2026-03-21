"""
Test Suite for E-Commerce Analytics Platform
─────────────────────────────────────────────────────────────────────────────
Run with: pytest tests/ -v --cov=src
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import RAW_DIR, PROCESSED_DIR


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_customers():
    """Sample customer data for testing."""
    return pd.DataFrame({
        'customer_id': [1, 2, 3, 4, 5],
        'email': ['a@test.com', 'b@test.com', 'c@test.com', 'd@test.com', 'e@test.com'],
        'registration_date': pd.date_range('2023-01-01', periods=5),
        'acquisition_channel': ['Organic', 'Paid Search', 'Social Media', 'Email', 'Referral'],
        'country': ['USA', 'UK', 'Canada', 'Australia', 'Germany']
    })


@pytest.fixture
def sample_transactions():
    """Sample transaction data for testing."""
    return pd.DataFrame({
        'transaction_id': ['TXN_001', 'TXN_002', 'TXN_003', 'TXN_004', 'TXN_005'],
        'customer_id': [1, 2, 1, 3, 2],
        'product_id': [101, 102, 103, 104, 105],
        'order_date': pd.date_range('2023-06-01', periods=5),
        'quantity': [1, 2, 1, 3, 2],
        'total_amount': [100.0, 200.0, 150.0, 300.0, 250.0],
        'category': ['Electronics', 'Clothing', 'Electronics', 'Home', 'Sports']
    })


@pytest.fixture
def sample_rfm():
    """Sample RFM data for testing."""
    return pd.DataFrame({
        'customer_id': [1, 2, 3, 4, 5],
        'recency': [10, 30, 60, 120, 200],
        'frequency': [10, 5, 3, 2, 1],
        'monetary': [1000, 500, 300, 200, 100],
        'segment': ['Champions', 'Loyal', 'Regular', 'At Risk', 'Hibernating']
    })


# ──────────────────────────────────────────────────────────────────────────────
# Data Generation Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestDataGeneration:
    """Tests for data generation functions."""
    
    def test_generate_customers_structure(self):
        """Test customer data has correct structure."""
        from src.pipeline.orchestrator import generate_customers
        
        df = generate_customers(n_customers=100)
        
        assert len(df) == 100
        assert 'customer_id' in df.columns
        assert 'email' in df.columns
        assert 'registration_date' in df.columns
        assert df['customer_id'].is_unique
        assert df['customer_id'].notnull().all()
    
    def test_generate_products_structure(self):
        """Test product data has correct structure."""
        from src.pipeline.orchestrator import generate_products
        
        df = generate_products(n_products=50)
        
        assert len(df) == 50
        assert 'product_id' in df.columns
        assert 'category' in df.columns
        assert 'price' in df.columns
        assert (df['price'] > 0).all()
    
    def test_generate_transactions_structure(self):
        """Test transaction data has correct structure."""
        from src.pipeline.orchestrator import generate_customers, generate_products, generate_transactions
        
        customers = generate_customers(100)
        products = generate_products(50)
        transactions = generate_transactions(customers, products, 200)
        
        assert len(transactions) == 200
        assert 'transaction_id' in transactions.columns
        assert 'customer_id' in transactions.columns
        assert 'total_amount' in transactions.columns
        assert (transactions['total_amount'] > 0).all()


# ──────────────────────────────────────────────────────────────────────────────
# Data Cleaning Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestDataCleaning:
    """Tests for data cleaning functions."""

    def test_clean_customers_removes_duplicates(self):
        """Test that cleaning removes duplicate customers."""
        from src.pipeline.orchestrator import clean_customers

        df = pd.DataFrame({
            'customer_id': [1, 1, 2],
            'email': ['a@test.com', 'A@TEST.COM', 'b@test.com'],
            'country': ['USA', 'USA', 'UK']
        })

        cleaned = clean_customers(df)
        assert len(cleaned) == 2
    
    def test_clean_transactions_removes_futures(self):
        """Test that cleaning removes future transactions."""
        from src.pipeline.orchestrator import clean_transactions
        
        df = pd.DataFrame({
            'transaction_id': ['T1', 'T2', 'T3'],
            'order_date': ['2020-01-01', '2030-01-01', '2023-06-01'],
            'total_amount': [100, 200, 150]
        })
        
        cleaned = clean_transactions(df)
        # Future date should be removed
        assert len(cleaned) < 3
    
    def test_clean_transactions_removes_negative(self):
        """Test that cleaning removes negative amounts."""
        from src.pipeline.orchestrator import clean_transactions
        
        df = pd.DataFrame({
            'transaction_id': ['T1', 'T2', 'T3'],
            'order_date': ['2020-01-01', '2020-01-02', '2020-01-03'],
            'total_amount': [100, -50, 150]
        })
        
        cleaned = clean_transactions(df)
        assert (cleaned['total_amount'] > 0).all()


# ──────────────────────────────────────────────────────────────────────────────
# RFM Segmentation Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRFMSegmentation:
    """Tests for RFM segmentation."""
    
    def test_rfm_calculation(self, sample_transactions):
        """Test RFM metrics are calculated correctly."""
        from src.pipeline.orchestrator import create_rfm_segmentation
        
        # Create minimal customer data
        customers = pd.DataFrame({
            'customer_id': [1, 2, 3],
            'acquisition_channel': ['Organic', 'Paid', 'Social'],
            'country': ['USA', 'UK', 'Canada'],
            'registration_date': pd.date_range('2023-01-01', periods=3)
        })
        
        rfm = create_rfm_segmentation(customers, sample_transactions)
        
        assert 'recency' in rfm.columns
        assert 'frequency' in rfm.columns
        assert 'monetary' in rfm.columns
        assert 'segment' in rfm.columns
    
    def test_rfm_scores_assigned(self, sample_rfm):
        """Test RFM scores are assigned."""
        from src.pipeline.orchestrator import create_rfm_segmentation
        
        customers = pd.DataFrame({
            'customer_id': [1, 2, 3, 4, 5],
            'acquisition_channel': ['A'] * 5,
            'country': ['USA'] * 5,
            'registration_date': pd.date_range('2023-01-01', periods=5)
        })

        # Mock transactions
        transactions = pd.DataFrame({
            'customer_id': [1, 2, 3, 4, 5],
            'transaction_id': ['T1', 'T2', 'T3', 'T4', 'T5'],
            'order_date': pd.date_range('2023-06-01', periods=5),
            'total_amount': [100, 200, 300, 400, 500]
        })

        rfm = create_rfm_segmentation(customers, transactions)
        
        assert 'R_score' in rfm.columns
        assert 'F_score' in rfm.columns
        assert 'M_score' in rfm.columns
        assert rfm['R_score'].between(1, 5).all()


# ──────────────────────────────────────────────────────────────────────────────
# A/B Testing Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestABTesting:
    """Tests for A/B testing functions."""

    def test_standard_ttest(self):
        """Test standard t-test calculation."""
        from src.ab_testing.ab_engine import run_ab_test
        import pandas as pd

        # Create mock session data with proper experiment name from config
        np.random.seed(42)
        n_control = 1000
        n_treatment = 1000
        
        control_data = np.random.normal(100, 15, n_control)
        treatment_data = np.random.normal(105, 15, n_treatment)  # 5% lift
        
        sessions = pd.DataFrame({
            'session_id': range(n_control + n_treatment),
            'experiment_name': ['checkout_redesign'] * (n_control + n_treatment),
            'variant': ['control'] * n_control + ['treatment'] * n_treatment,
            'revenue': np.concatenate([control_data, treatment_data]),
            'converted': ([1] * int(n_control * 0.1) + [0] * (n_control - int(n_control * 0.1))) + 
                        ([1] * int(n_treatment * 0.12) + [0] * (n_treatment - int(n_treatment * 0.12)))
        })
        
        result = run_ab_test('checkout_redesign', sessions)

        # ExperimentResult is a dataclass with attributes
        assert hasattr(result, 'experiment_name')
        assert hasattr(result, 'absolute_lift')
        assert hasattr(result, 'p_value') or hasattr(result, 'z_stat')
    
    def test_chi_square_test(self):
        """Test chi-square test for conversion rates."""
        from scipy import stats

        # 100 conversions out of 1000 control, 120 out of 1000 treatment
        control_conversions = 100
        control_total = 1000
        treatment_conversions = 120
        treatment_total = 1000
        
        # Create contingency table
        contingency = np.array([
            [control_conversions, control_total - control_conversions],
            [treatment_conversions, treatment_total - treatment_conversions]
        ])
        
        chi_square, p_value, dof, expected = stats.chi2_contingency(contingency)

        assert chi_square > 0
        assert 0 <= p_value <= 1


# ──────────────────────────────────────────────────────────────────────────────
# Advanced A/B Testing Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAdvancedABTesting:
    """Tests for advanced A/B testing features."""
    
    def test_sequential_tester(self):
        """Test sequential testing."""
        from src.ab_testing.advanced_ab_testing import SequentialTester, SequentialTestConfig
        
        config = SequentialTestConfig(alpha=0.05, beta=0.20)
        tester = SequentialTester(config)
        
        # Simulate data
        np.random.seed(42)
        for _ in range(100):
            control = np.random.normal(100, 15)
            treatment = np.random.normal(105, 15)
            tester.update(control, treatment)
        
        results = tester.get_results()
        
        assert 'always_valid_pvalue' in results
        assert 'log_likelihood_ratio' in results
    
    def test_srm_detection(self):
        """Test Sample Ratio Mismatch detection."""
        from src.ab_testing.advanced_ab_testing import detect_srm
        
        # Normal allocation
        result = detect_srm(
            observed=np.array([500, 500]),
            expected=np.array([0.5, 0.5])
        )
        assert 'srm_detected' in result
        assert 'p_value' in result
        
        # SRM case
        result = detect_srm(
            observed=np.array([300, 700]),
            expected=np.array([0.5, 0.5])
        )
        assert result['srm_detected'] == True


# ──────────────────────────────────────────────────────────────────────────────
# Causal Inference Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCausalInference:
    """Tests for causal inference methods."""
    
    def test_propensity_score_matching(self):
        """Test propensity score matching."""
        from src.causal.inference import PropensityScoreMatcher
        
        np.random.seed(42)
        n = 100
        
        X = pd.DataFrame({
            'age': np.random.normal(45, 10, n),
            'income': np.random.normal(50000, 15000, n)
        })
        treatment = np.random.binomial(1, 0.5, n)
        outcome = np.random.normal(100, 20, n) + 10 * treatment
        
        matcher = PropensityScoreMatcher(caliper=0.1)
        matcher.fit_propensity_model(X, treatment)
        matcher.match(X, treatment, outcome)
        
        results = matcher.estimate_att()
        
        assert 'att' in results
        assert 'std_error' in results
    
    def test_diff_in_diff(self):
        """Test difference-in-differences."""
        from src.causal.inference import DifferenceInDifferences
        
        # Create panel data
        data = pd.DataFrame({
            'unit': [1, 1, 2, 2] * 10,
            'period': [0, 1] * 20,
            'treatment': [1, 1, 0, 0] * 10,
            'outcome': [100, 120, 100, 102] * 10  # Treatment effect of 18
        })
        
        did = DifferenceInDifferences()
        did.fit(data, 'treatment', 'period', 'outcome')
        
        results = did.get_results()
        
        assert 'did_estimate' in results
        assert results['did_estimate'] > 0


# ──────────────────────────────────────────────────────────────────────────────
# Decision Engine Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestDecisionEngine:
    """Tests for decision engine components."""
    
    def test_cusum_detector(self):
        """Test CUSUM anomaly detection."""
        from src.reports.decision_engine import CUSUMDetector
        
        np.random.seed(42)
        normal_data = np.random.normal(100, 10, 50)
        
        detector = CUSUMDetector()
        detector.fit(normal_data)
        
        # Add shift
        shifted_data = np.random.normal(115, 10, 20)
        all_data = np.concatenate([normal_data, shifted_data])
        
        anomalies = detector.detect_batch(all_data)
        
        # Should detect anomalies in shifted portion
        assert anomalies.sum() > 0
    
    def test_whatif_simulator(self):
        """Test what-if simulator."""
        from src.reports.decision_engine import WhatIfSimulator

        # Create proper baseline with both segments having customers
        baseline = pd.DataFrame({
            'segment': ['Champions'] * 50 + ['At Risk'] * 50,
            'clv_12m': [500] * 50 + [150] * 50
        })

        simulator = WhatIfSimulator(baseline)
        result = simulator.simulate_segment_conversion(
            'At Risk', 'Champions', 0.10
        )

        assert 'annual_revenue_impact' in result
        # CLV lift should be positive when moving from At Risk (150) to Champions (500)
        assert 'clv_lift_per_customer' in result
        assert result['clv_lift_per_customer'] > 0


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for the full pipeline."""
    
    def test_full_pipeline(self):
        """Test complete data pipeline."""
        from src.pipeline.orchestrator import run_pipeline_fallback
        
        result = run_pipeline_fallback()
        
        assert result['customers'] > 0
        assert result['transactions'] > 0
        
        # Check files exist
        assert (RAW_DIR / "customers.parquet").exists()
        assert (RAW_DIR / "transactions.parquet").exists()
        assert (PROCESSED_DIR / "rfm_segmented.parquet").exists()
    
    def test_data_quality_after_pipeline(self):
        """Test data quality after pipeline runs."""
        from src.pipeline.orchestrator import run_pipeline_fallback
        
        run_pipeline_fallback()
        
        # Load and validate
        customers = pd.read_parquet(RAW_DIR / "customers.parquet")
        transactions = pd.read_parquet(RAW_DIR / "transactions.parquet")
        
        # Customer checks
        assert customers['customer_id'].is_unique
        assert customers['email'].notnull().all()
        
        # Transaction checks
        assert transactions['total_amount'].gt(0).all()
        assert transactions['transaction_id'].is_unique


# ──────────────────────────────────────────────────────────────────────────────
# Run tests
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
