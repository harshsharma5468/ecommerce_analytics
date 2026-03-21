"""
Predictive ML Layer
─────────────────────────────────────────────────────────────────────────────
Machine learning models for:
- Churn Prediction (XGBoost/LightGBM + SHAP)
- Next Purchase Date (Survival Analysis)
- Customer Lifetime Value (BG/NBD + Gamma-Gamma)
- Product Recommendations (ALS Collaborative Filtering)
"""

from .churn_model import ChurnPredictor, train_churn_model
from .survival_analysis import NextPurchasePredictor, train_survival_model
from .clv_model import CLVPredictor, train_clv_model, BGNBDFitter, GammaGammaFitterWrapper
from .recommendation_engine import ProductRecommender, train_recommendation_model

__all__ = [
    'ChurnPredictor',
    'train_churn_model',
    'NextPurchasePredictor',
    'train_survival_model',
    'CLVPredictor',
    'train_clv_model',
    'BGNBDFitter',
    'GammaGammaFitterWrapper',
    'ProductRecommender',
    'train_recommendation_model',
]
