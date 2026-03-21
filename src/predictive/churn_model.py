"""
Churn Prediction Model
─────────────────────────────────────────────────────────────────────────────
XGBoost/LightGBM binary classifier with SHAP explainability
Predicts customers likely to churn in the next 30/60/90 days
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_recall_curve,
    confusion_matrix, average_precision_score
)
import xgboost as xgb
import lightgbm as lgb
import warnings
warnings.filterwarnings("ignore")

# Optional SHAP import
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

from config.settings import PROCESSED_DIR, MODELS_DIR


class ChurnPredictor:
    """
    Churn prediction using gradient boosting with SHAP explainability.
    
    Churn is defined as no purchase in the next 30/60/90 days.
    """
    
    def __init__(self, model_type: str = "xgboost"):
        self.model_type = model_type
        self.model = None
        self.feature_names = None
        self.shap_explainer = None
        self.threshold = 0.5
        
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for churn prediction.
        Uses RFM features + behavioral signals.
        """
        features = df.copy()

        # RFM features (already in data) - check what's available
        base_feature_cols = [
            'recency', 'frequency', 'monetary', 'avg_order_value',
            'R_score', 'F_score', 'M_score', 'RFM_score', 'RFM_composite'
        ]
        
        # Optional features that may not exist
        optional_features = [
            'total_items', 'distinct_categories', 'purchase_rate',
            'avg_items_per_order', 'log_recency', 'log_frequency',
            'log_monetary', 'clv_12m', 'customer_age_days'
        ]
        
        # Only include columns that exist
        feature_cols = [c for c in base_feature_cols if c in features.columns]
        feature_cols.extend([c for c in optional_features if c in features.columns])

        # Add derived features if base columns exist
        if 'recency' in features.columns and 'frequency' in features.columns:
            features['recency_frequency_ratio'] = features['recency'] / (features['frequency'] + 1)
            feature_cols.append('recency_frequency_ratio')
        
        if 'monetary' in features.columns and 'total_items' in features.columns:
            features['monetary_per_item'] = features['monetary'] / (features['total_items'] + 1)
            feature_cols.append('monetary_per_item')
        
        if 'distinct_categories' in features.columns and 'frequency' in features.columns:
            features['category_diversity'] = features['distinct_categories'] / (features['frequency'] + 1)
            feature_cols.append('category_diversity')
        
        if all(c in features.columns for c in ['R_score', 'F_score', 'M_score']):
            features['rfm_interaction'] = features['R_score'] * features['F_score'] * features['M_score']
            feature_cols.append('rfm_interaction')

        # Age feature if available - derive tenure months
        if 'customer_age_days' in features.columns:
            features['customer_tenure_months'] = features['customer_age_days'] / 30
            if 'customer_tenure_months' not in feature_cols:
                feature_cols.append('customer_tenure_months')

        # Remove duplicates while preserving order
        seen = set()
        feature_cols = [x for x in feature_cols if not (x in seen or seen.add(x))]

        # Ensure all feature columns exist
        available_cols = [c for c in feature_cols if c in features.columns]

        return features[available_cols].fillna(0)
    
    def create_churn_label(self, df: pd.DataFrame, 
                           last_purchase_col: str = 'last_purchase',
                           horizon_days: int = 30,
                           reference_date: pd.Timestamp = None) -> pd.Series:
        """
        Create binary churn label based on purchase recency.
        
        Churn = 1 if no purchase in the last `horizon_days` before reference_date
        """
        if reference_date is None:
            reference_date = pd.Timestamp.now()
        elif isinstance(reference_date, str):
            reference_date = pd.Timestamp(reference_date)
            
        if last_purchase_col in df.columns:
            last_purchase = pd.to_datetime(df[last_purchase_col])
            days_since_purchase = (reference_date - last_purchase).dt.days
            churn = (days_since_purchase > horizon_days).astype(int)
        else:
            # Fallback: use recency column
            churn = (df['recency'] > horizon_days).astype(int)
            
        return churn
    
    def fit(self, df: pd.DataFrame, target_col: str = None,
            horizon_days: int = 30, test_size: float = 0.2,
            n_folds: int = 5, reference_date: pd.Timestamp = None):
        """
        Train the churn prediction model.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe with customer features
        target_col : str, optional
            Pre-computed target column. If None, churn is computed from last_purchase
        horizon_days : int
            Days threshold for churn definition
        test_size : float
            Test split ratio
        n_folds : int
            Number of CV folds
        reference_date : pd.Timestamp
            Reference date for churn calculation
        """
        # Prepare features
        X = self.prepare_features(df)
        self.feature_names = X.columns.tolist()
        
        # Prepare target
        if target_col and target_col in df.columns:
            y = df[target_col]
        else:
            y = self.create_churn_label(df, horizon_days=horizon_days, 
                                        reference_date=reference_date)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Handle class imbalance
        scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
        
        if self.model_type == "xgboost":
            self.model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                scale_pos_weight=scale_pos_weight,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                gamma=0.1,
                reg_alpha=0.1,
                reg_lambda=1,
                random_state=42,
                n_jobs=-1,
                eval_metric='auc'
            )
        else:  # lightgbm
            self.model = lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                scale_pos_weight=scale_pos_weight,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_samples=20,
                reg_alpha=0.1,
                reg_lambda=1,
                random_state=42,
                n_jobs=-1,
                metric='auc'
            )
        
        # Cross-validation
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
        cv_scores = []
        
        for train_idx, val_idx in cv.split(X_train, y_train):
            X_cv_train, X_cv_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
            y_cv_train, y_cv_val = y_train.iloc[train_idx], y_train.iloc[val_idx]
            
            self.model.fit(
                X_cv_train, y_cv_train,
                eval_set=[(X_cv_val, y_cv_val)],
                verbose=False
            )
            cv_scores.append(roc_auc_score(y_cv_val, self.model.predict_proba(X_cv_val)[:, 1]))
        
        print(f"CV AUC-ROC: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")
        
        # Final training on full training set
        self.model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        
        # Evaluate on test set
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        
        print("\n=== Test Set Evaluation ===")
        print(f"AUC-ROC: {roc_auc_score(y_test, y_pred_proba):.4f}")
        print(f"Average Precision: {average_precision_score(y_test, y_pred_proba):.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, digits=4))

        # Initialize SHAP explainer (if available)
        if SHAP_AVAILABLE:
            self.shap_explainer = shap.TreeExplainer(self.model)
        else:
            self.shap_explainer = None

        return self
    
    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict churn probability."""
        X = self.prepare_features(df)
        return self.model.predict_proba(X)[:, 1]
    
    def predict_class(self, df: pd.DataFrame, threshold: float = None) -> np.ndarray:
        """Predict churn class."""
        proba = self.predict(df)
        return (proba >= (threshold or self.threshold)).astype(int)
    
    def get_shap_values(self, df: pd.DataFrame) -> np.ndarray:
        """Get SHAP values for explainability."""
        if not SHAP_AVAILABLE or self.shap_explainer is None:
            raise ImportError("SHAP not installed. Install with: pip install shap")
        X = self.prepare_features(df)
        return self.shap_explainer.shap_values(X)
    
    def get_feature_importance(self, top_n: int = 15) -> pd.DataFrame:
        """Get feature importance dataframe."""
        if self.model is None:
            return pd.DataFrame()
            
        importance = self.model.feature_importances_
        return pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False).head(top_n)
    
    def get_shap_summary_plot_data(self, df: pd.DataFrame) -> dict:
        """Get data for SHAP summary plot (for Streamlit)."""
        if not SHAP_AVAILABLE or self.shap_explainer is None:
            return {'error': 'SHAP not available'}
        X = self.prepare_features(df)
        shap_values = self.shap_explainer.shap_values(X)
        
        # Handle different SHAP output formats
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Binary classification
        
        return {
            'shap_values': shap_values,
            'features': X.values,
            'feature_names': self.feature_names
        }
    
    def save(self, path: Path = None):
        """Save model to disk."""
        if path is None:
            path = MODELS_DIR / "churn_model.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: Path = None) -> 'ChurnPredictor':
        """Load model from disk."""
        if path is None:
            path = MODELS_DIR / "churn_model.pkl"
        return joblib.load(path)


def train_churn_model(horizon_days: int = 30, model_type: str = "xgboost"):
    """
    Main function to train and save churn model.
    """
    print(f"Training churn prediction model (horizon={horizon_days} days)...")
    
    # Load RFM data
    rfm_path = PROCESSED_DIR / "rfm_segmented.parquet"
    if not rfm_path.exists():
        raise FileNotFoundError(f"RFM data not found at {rfm_path}")
    
    df = pd.read_parquet(rfm_path)
    print(f"Loaded {len(df)} customers")
    
    # Train model
    predictor = ChurnPredictor(model_type=model_type)
    predictor.fit(df, horizon_days=horizon_days)
    
    # Feature importance
    print("\n=== Top 15 Feature Importances ===")
    print(predictor.get_feature_importance(15))
    
    # Save model
    predictor.save()
    
    # Save predictions back to parquet
    df['churn_probability'] = predictor.predict(df)
    df['churn_predicted'] = predictor.predict_class(df)
    
    output_path = PROCESSED_DIR / "churn_predictions.parquet"
    df.to_parquet(output_path, index=False)
    print(f"\nPredictions saved to {output_path}")
    
    return predictor


if __name__ == "__main__":
    train_churn_model(horizon_days=30, model_type="xgboost")
