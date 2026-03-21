"""
Central configuration for the E-Commerce Analytics Platform.
All parameters are versioned and documented for reproducibility.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import os

# ─── Project Paths ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
REPORTS_DIR = ROOT_DIR / "reports"
MODELS_DIR = ROOT_DIR / "models"
FEATURE_STORE_DIR = ROOT_DIR / "feature_store"
STREAMING_DIR = ROOT_DIR / "streaming"

# Create directories
for d in [MODELS_DIR, FEATURE_STORE_DIR, STREAMING_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Database ─────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "ecommerce_analytics")
DB_USER = os.getenv("DB_USER", "analytics_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "analytics_pass")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
SQLITE_URL = f"sqlite:///{DATA_DIR}/analytics.db"

# ─── Data Generation ──────────────────────────────────────────────────────────
RANDOM_SEED = 42
N_CUSTOMERS = 15_000
N_PRODUCTS = 500
N_TRANSACTIONS = 180_000
DATE_START = "2022-01-01"
DATE_END = "2024-12-31"

PRODUCT_CATEGORIES = {
    "Electronics": {"avg_price": 320, "std_price": 180, "margin": 0.22},
    "Clothing": {"avg_price": 65, "std_price": 35, "margin": 0.55},
    "Home & Garden": {"avg_price": 95, "std_price": 60, "margin": 0.42},
    "Sports & Outdoors": {"avg_price": 110, "std_price": 70, "margin": 0.38},
    "Books & Media": {"avg_price": 22, "std_price": 12, "margin": 0.30},
    "Beauty & Personal Care": {"avg_price": 45, "std_price": 25, "margin": 0.62},
    "Food & Grocery": {"avg_price": 28, "std_price": 18, "margin": 0.28},
    "Toys & Games": {"avg_price": 52, "std_price": 32, "margin": 0.45},
    "Automotive": {"avg_price": 145, "std_price": 95, "margin": 0.33},
    "Office Supplies": {"avg_price": 38, "std_price": 22, "margin": 0.48},
}

CUSTOMER_SEGMENTS_GEN = {
    "Champions": {"proportion": 0.08, "freq_mult": 4.5, "recency_days": 15, "value_mult": 3.2},
    "Loyal": {"proportion": 0.12, "freq_mult": 3.0, "recency_days": 30, "value_mult": 2.1},
    "Potential_Loyalist": {"proportion": 0.15, "freq_mult": 2.0, "recency_days": 45, "value_mult": 1.5},
    "Recent_Customer": {"proportion": 0.10, "freq_mult": 1.2, "recency_days": 20, "value_mult": 0.8},
    "At_Risk": {"proportion": 0.18, "freq_mult": 1.8, "recency_days": 120, "value_mult": 1.4},
    "Hibernating": {"proportion": 0.20, "freq_mult": 1.1, "recency_days": 250, "value_mult": 0.7},
    "Lost": {"proportion": 0.17, "freq_mult": 0.8, "recency_days": 340, "value_mult": 0.5},
}

# ─── RFM Configuration ────────────────────────────────────────────────────────
RFM_SNAPSHOT_DATE = "2025-01-01"
RFM_QUANTILES = 5
KMEANS_N_CLUSTERS_RANGE = range(2, 12)
KMEANS_MAX_ITER = 500
KMEANS_N_INIT = 20
KMEANS_RANDOM_STATE = 42

# ─── A/B Testing ──────────────────────────────────────────────────────────────
AB_ALPHA = 0.05          # Significance level
AB_POWER = 0.80          # Statistical power (1 - beta)
AB_MDE = 0.05            # Minimum Detectable Effect (5%)
AB_BASELINE_CONVERSION = 0.035
AB_N_EXPERIMENTS = 8

AB_EXPERIMENTS = {
    "checkout_redesign": {
        "description": "Simplified single-page checkout vs. multi-step",
        "metric": "conversion_rate",
        "baseline": 0.032,
        "expected_lift": 0.18,
        "n_control": 12000,
        "n_treatment": 12000,
        "duration_days": 21,
    },
    "email_personalization": {
        "description": "Personalised product recommendations vs. generic newsletter",
        "metric": "click_through_rate",
        "baseline": 0.028,
        "expected_lift": 0.25,
        "n_control": 8000,
        "n_treatment": 8000,
        "duration_days": 14,
    },
    "price_discount_5pct": {
        "description": "5% loyalty discount banner vs. no discount",
        "metric": "conversion_rate",
        "baseline": 0.041,
        "expected_lift": 0.12,
        "n_control": 15000,
        "n_treatment": 15000,
        "duration_days": 28,
    },
    "free_shipping_threshold": {
        "description": "Free shipping at $50 threshold vs. $75",
        "metric": "average_order_value",
        "baseline": 68.5,
        "expected_lift": 0.08,
        "n_control": 10000,
        "n_treatment": 10000,
        "duration_days": 21,
    },
    "product_recommendation_algo": {
        "description": "Collaborative filtering vs. rule-based cross-sell",
        "metric": "revenue_per_session",
        "baseline": 12.4,
        "expected_lift": 0.15,
        "n_control": 9000,
        "n_treatment": 9000,
        "duration_days": 14,
    },
    "push_notification_timing": {
        "description": "AI-optimised send time vs. fixed 10AM",
        "metric": "open_rate",
        "baseline": 0.22,
        "expected_lift": 0.10,
        "n_control": 20000,
        "n_treatment": 20000,
        "duration_days": 7,
    },
    "cart_abandonment_email": {
        "description": "3-email sequence vs. single reminder",
        "metric": "recovery_rate",
        "baseline": 0.085,
        "expected_lift": 0.30,
        "n_control": 5000,
        "n_treatment": 5000,
        "duration_days": 14,
    },
    "homepage_hero_banner": {
        "description": "Dynamic seasonal banner vs. static brand banner",
        "metric": "engagement_rate",
        "baseline": 0.047,
        "expected_lift": 0.08,
        "n_control": 25000,
        "n_treatment": 25000,
        "duration_days": 10,
    },
}

# ─── Dashboard ────────────────────────────────────────────────────────────────
STREAMLIT_HOST = "0.0.0.0"
STREAMLIT_PORT = 8501
DASHBOARD_TITLE = "E-Commerce Analytics Intelligence Platform"
COMPANY_NAME = "NexaCommerce Analytics"
