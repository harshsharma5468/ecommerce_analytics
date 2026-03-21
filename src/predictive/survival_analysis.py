"""
Survival Analysis & Next Purchase Date Prediction
─────────────────────────────────────────────────────────────────────────────
Kaplan-Meier survival curves, Cox Proportional Hazards model
Predicts time until next purchase
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.model_selection import train_test_split
from lifelines import KaplanMeierFitter, CoxPHFitter, WeibullAFTFitter
from lifelines.utils import concordance_index
from lifelines.plotting import add_at_risk_counts
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

from config.settings import PROCESSED_DIR, MODELS_DIR, REPORTS_DIR


class NextPurchasePredictor:
    """
    Predict time until next purchase using survival analysis.
    
    Supports:
    - Kaplan-Meier estimator (non-parametric)
    - Cox Proportional Hazards (semi-parametric)
    - Weibull AFT (parametric)
    """
    
    def __init__(self, model_type: str = "cox"):
        self.model_type = model_type
        self.model = None
        self.km_fitter = KaplanMeierFitter()
        self.feature_names = None
        
    def prepare_survival_data(self, df: pd.DataFrame,
                              observation_end: pd.Timestamp = None) -> pd.DataFrame:
        """
        Prepare survival analysis data.
        
        Creates:
        - T: time to event (next purchase or censoring)
        - E: event indicator (1 = purchased, 0 = censored)
        """
        data = df.copy()
        
        if observation_end is None:
            observation_end = pd.Timestamp.now()
        
        if 'last_purchase' in data.columns:
            data['last_purchase'] = pd.to_datetime(data['last_purchase'])
            
            # If we have first and last purchase, estimate inter-purchase time
            if 'first_purchase' in data.columns:
                data['first_purchase'] = pd.to_datetime(data['first_purchase'])
                # Average inter-purchase time as baseline
                purchase_span = (data['last_purchase'] - data['first_purchase']).dt.days
                purchase_count = data['frequency'].clip(lower=1)
                avg_inter_purchase = purchase_span / purchase_count
                
                # Time since last purchase (recency)
                data['T'] = (observation_end - data['last_purchase']).dt.days
                
                # Event: did they purchase within expected time?
                data['E'] = (data['T'] <= avg_inter_purchase * 1.5).astype(int)
            else:
                # Use recency directly
                data['T'] = data['recency']
                # Assume event if they purchased recently enough
                data['E'] = (data['recency'] < data['recency'].median() * 2).astype(int)
        else:
            # Fallback using recency
            data['T'] = data['recency'].fillna(data['recency'].median())
            data['E'] = (data['T'] < data['T'].median() * 2).astype(int)
        
        return data
    
    def get_feature_columns(self) -> list:
        """Get feature columns for survival models."""
        return [
            'frequency', 'monetary', 'avg_order_value', 'total_items',
            'distinct_categories', 'purchase_rate', 'R_score', 'F_score', 'M_score',
            'RFM_score', 'clv_12m', 'log_recency', 'log_frequency', 'log_monetary'
        ]
    
    def fit_kaplan_meier(self, df: pd.DataFrame, group_col: str = None):
        """
        Fit Kaplan-Meier survival curve.
        
        Parameters
        ----------
        df : pd.DataFrame
            Survival data with T (duration) and E (event) columns
        group_col : str, optional
            Column to stratify by (e.g., 'segment')
        """
        data = self.prepare_survival_data(df)
        
        if group_col and group_col in data.columns:
            # Stratified KM curves
            groups = data[group_col].unique()
            self.km_fitter = {}
            
            for group in groups:
                mask = data[group_col] == group
                km = KaplanMeierFitter()
                km.fit(data.loc[mask, 'T'], data.loc[mask, 'E'], label=str(group))
                self.km_fitter[group] = km
            
            return self.km_fitter
        else:
            self.km_fitter.fit(data['T'], data['E'])
            return self.km_fitter
    
    def fit_cox(self, df: pd.DataFrame):
        """Fit Cox Proportional Hazards model."""
        data = self.prepare_survival_data(df)
        
        # Select features
        feature_cols = [c for c in self.get_feature_columns() if c in data.columns]
        X = data[feature_cols].fillna(0)
        
        # Prepare survival dataframe for Cox
        surv_df = pd.DataFrame({
            'T': data['T'],
            'E': data['E']
        })
        surv_df = pd.concat([surv_df, X], axis=1)
        
        # Fit Cox model
        self.model = CoxPHFitter(penalizer=0.1)
        self.model.fit(surv_df, duration_col='T', event_col='E')
        self.feature_names = feature_cols
        
        return self.model
    
    def fit_weibull(self, df: pd.DataFrame):
        """Fit Weibull Accelerated Failure Time model."""
        data = self.prepare_survival_data(df)
        
        feature_cols = [c for c in self.get_feature_columns() if c in data.columns]
        X = data[feature_cols].fillna(0)
        
        surv_df = pd.DataFrame({
            'T': data['T'],
            'E': data['E']
        })
        surv_df = pd.concat([surv_df, X], axis=1)
        
        self.model = WeibullAFTFitter(penalizer=0.1)
        self.model.fit(surv_df, duration_col='T', event_col='E')
        self.feature_names = feature_cols
        
        return self.model
    
    def fit(self, df: pd.DataFrame, group_col: str = None):
        """
        Fit the survival model(s).
        """
        if self.model_type == "kaplan_meier":
            return self.fit_kaplan_meier(df, group_col)
        elif self.model_type == "cox":
            return self.fit_cox(df)
        elif self.model_type == "weibull":
            return self.fit_weibull(df)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
    
    def predict_median_time(self, df: pd.DataFrame) -> np.ndarray:
        """Predict median time to next purchase."""
        data = self.prepare_survival_data(df)
        
        if self.model_type == "kaplan_meier":
            if isinstance(self.km_fitter, dict):
                # Stratified predictions
                predictions = []
                for idx, row in data.iterrows():
                    group = row.get('segment', 'Unknown')
                    if group in self.km_fitter:
                        med = self.km_fitter[group].median_survival_time_
                    else:
                        med = self.km_fitter[group].median_survival_time_ if hasattr(self.km_fitter, 'median_survival_time_') else 30
                    predictions.append(med)
                return np.array(predictions)
            else:
                return np.full(len(df), self.km_fitter.median_survival_time_)
        
        elif self.model_type in ["cox", "weibull"]:
            feature_cols = [c for c in self.get_feature_columns() if c in data.columns]
            X = data[feature_cols].fillna(0)
            
            if self.model_type == "cox":
                # Cox predicts hazard ratio, convert to time
                partial_hazard = self.model.predict_partial_hazard(X)
                baseline_median = self.model.baseline_survival_.index[
                    np.abs(self.model.baseline_survival_[0].values - 0.5).argmin()
                ]
                return baseline_median / partial_hazard.values.flatten()
            else:
                # Weibull AFT directly predicts time
                return self.model.predict_median(X).values.flatten()
        
        return np.full(len(df), 30)  # Default 30 days
    
    def predict_survival_function(self, df: pd.DataFrame, 
                                   times: np.ndarray = None) -> pd.DataFrame:
        """Predict survival probability at given times."""
        if times is None:
            times = np.arange(0, 365, 7)  # Weekly for a year
        
        data = self.prepare_survival_data(df)
        
        if self.model_type == "kaplan_meier":
            if isinstance(self.km_fitter, dict):
                results = {}
                for group, km in self.km_fitter.items():
                    results[group] = km.survival_function_at_times(times).values
                return pd.DataFrame(results, index=times)
            else:
                sf = self.km_fitter.survival_function_at_times(times).values
                return pd.DataFrame({'survival': sf}, index=times)
        
        elif self.model_type in ["cox", "weibull"]:
            feature_cols = [c for c in self.get_feature_columns() if c in data.columns]
            X = data[feature_cols].fillna(0)
            
            if self.model_type == "cox":
                sf = self.model.predict_survival_function(X, times=times)
            else:
                sf = self.model.predict_survival_function(X, times=times)
            
            return pd.DataFrame(sf.values, index=times)
        
        return pd.DataFrame()
    
    def get_concordance_index(self, df: pd.DataFrame) -> float:
        """Calculate concordance index (C-statistic)."""
        data = self.prepare_survival_data(df)
        
        if self.model_type in ["cox", "weibull"]:
            feature_cols = [c for c in self.get_feature_columns() if c in data.columns]
            X = data[feature_cols].fillna(0)
            
            risk_scores = self.model.predict_partial_hazard(X)
            ci = concordance_index(data['T'], -risk_scores, data['E'])
            return ci
        
        return 0.5
    
    def plot_kaplan_meier(self, df: pd.DataFrame, group_col: str = 'segment',
                          save_path: Path = None):
        """Plot Kaplan-Meier survival curves by group."""
        fig, ax = plt.subplots(figsize=(12, 8))

        self.fit_kaplan_meier(df, group_col)

        colors = plt.cm.tab10(np.linspace(0, 1, 10))

        for idx, (group, km) in enumerate(self.km_fitter.items()):
            km.plot_survival_function(ax=ax, color=colors[idx % len(colors)])

        ax.set_xlabel('Days Since Last Purchase', fontsize=12)
        ax.set_ylabel('Survival Probability', fontsize=12)
        ax.set_title('Kaplan-Meier Survival Curves by Segment', fontsize=14)
        ax.legend(title=group_col, loc='upper right')
        ax.grid(True, alpha=0.3)

        # Add at-risk counts (only if km_fitter is a single fitter, not dict)
        try:
            if not isinstance(self.km_fitter, dict):
                add_at_risk_counts(self.km_fitter, ax=ax)
        except Exception:
            pass  # Skip at-risk counts if not available

        plt.tight_layout()

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")

        return fig, ax
    
    def plot_cox_coefficients(self, save_path: Path = None):
        """Plot Cox model coefficients."""
        if self.model_type != "cox" or self.model is None:
            return None
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        summary = self.model.summary
        coef = summary['coef']
        p_values = summary['p']
        
        colors = ['green' if c < 0 else 'red' for c in coef]
        y_pos = np.arange(len(coef))
        
        ax.barh(y_pos, coef, color=colors, alpha=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(coef.index)
        ax.set_xlabel('Coefficient (Hazard Ratio log)', fontsize=12)
        ax.set_title('Cox Proportional Hazards Coefficients', fontsize=14)
        ax.axvline(x=0, color='black', linestyle='--', alpha=0.5)
        
        # Add significance stars
        for i, p in enumerate(p_values):
            star = '*' * (3 if p < 0.001 else 2 if p < 0.01 else 1 if p < 0.05 else 0)
            if star:
                ax.text(coef.iloc[i] + 0.01, i, star, va='center', fontsize=10)
        
        plt.tight_layout()
        
        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, ax
    
    def save(self, path: Path = None):
        """Save model to disk."""
        if path is None:
            path = MODELS_DIR / "survival_model.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: Path = None) -> 'NextPurchasePredictor':
        """Load model from disk."""
        if path is None:
            path = MODELS_DIR / "survival_model.pkl"
        return joblib.load(path)


def train_survival_model(model_type: str = "cox"):
    """
    Main function to train survival model.
    """
    print(f"Training {model_type} survival model...")
    
    # Load RFM data
    rfm_path = PROCESSED_DIR / "rfm_segmented.parquet"
    if not rfm_path.exists():
        raise FileNotFoundError(f"RFM data not found at {rfm_path}")
    
    df = pd.read_parquet(rfm_path)
    print(f"Loaded {len(df)} customers")
    
    # Train model
    predictor = NextPurchasePredictor(model_type=model_type)
    predictor.fit(df, group_col='segment')
    
    # Evaluate
    if model_type in ["cox", "weibull"]:
        try:
            ci = predictor.get_concordance_index(df)
            print(f"Concordance Index: {ci:.4f}")
        except Exception as e:
            print(f"Warning: Could not compute concordance index: {e}")

    # Predict next purchase time
    try:
        df['predicted_next_purchase_days'] = predictor.predict_median_time(df)
    except Exception as e:
        print(f"Warning: Could not predict next purchase time: {e}")
        df['predicted_next_purchase_days'] = 30  # Default value

    # Save predictions
    output_path = PROCESSED_DIR / "survival_predictions.parquet"
    df.to_parquet(output_path, index=False)
    print(f"Predictions saved to {output_path}")

    # Save model
    predictor.save()

    # Generate plots
    reports_dir = REPORTS_DIR / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        predictor.plot_kaplan_meier(
            df,
            group_col='segment',
            save_path=reports_dir / "kaplan_meier_survival.png"
        )
    except Exception as e:
        print(f"Warning: Could not generate Kaplan-Meier plot: {e}")

    if model_type == "cox":
        try:
            predictor.plot_cox_coefficients(
                save_path=reports_dir / "cox_coefficients.png"
            )
        except Exception as e:
            print(f"Warning: Could not generate Cox coefficients plot: {e}")

    return predictor


if __name__ == "__main__":
    train_survival_model(model_type="cox")
