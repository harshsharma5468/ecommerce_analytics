"""
BG/NBD + Gamma-Gamma Model for Customer Lifetime Value
─────────────────────────────────────────────────────────────────────────────
Probabilistic CLV modeling using:
- BG/NBD (Beta-Geometric/Negative Binomial Distribution) for transaction frequency
- Gamma-Gamma model for monetary value
- Discounted Cash Flow for CLV calculation
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

from config.settings import PROCESSED_DIR, MODELS_DIR, REPORTS_DIR

try:
    from lifetimes import BetaGeoFitter, GammaGammaFitter
    LIFETIMES_AVAILABLE = True
except ImportError:
    LIFETIMES_AVAILABLE = False
    print("Warning: lifetimes package not installed. Using simplified implementation.")


class BGNBDFitter:
    """
    BG/NBD model for predicting customer transaction frequency.
    
    If lifetimes is not available, uses a simplified implementation.
    """
    
    def __init__(self):
        self.model = None
        self.params = {}
        
    def prepare_data(self, df: pd.DataFrame,
                     frequency_col: str = 'frequency',
                     recency_col: str = 'recency',
                     T_col: str = 'customer_age_days') -> pd.DataFrame:
        """
        Prepare data for BG/NBD model.
        
        Returns dataframe with:
        - frequency: number of repeat purchases
        - recency: time between first and last purchase
        - T: total observation time
        """
        data = pd.DataFrame({
            'frequency': df[frequency_col] if frequency_col in df.columns else 0,
            'recency': df[recency_col] if recency_col in df.columns else 30,
            'T': df[T_col] if T_col in df.columns else df[recency_col] * 2
        })
        
        # Ensure non-negative values
        data = data.clip(lower=0)
        data['T'] = data['T'].clip(lower=1)  # T must be positive
        
        return data
    
    def fit(self, df: pd.DataFrame, penalizer_coef: float = 1.0):
        """Fit BG/NBD model."""
        data = self.prepare_data(df)

        if LIFETIMES_AVAILABLE:
            self.model = BetaGeoFitter(penalizer_coef=penalizer_coef)
            self.model.fit(
                data['frequency'],
                data['recency'],
                data['T']
            )
            self.params = {
                'r': self.model.params_['r'],
                'alpha': self.model.params_['alpha'],
                'a': self.model.params_['a'],
                'b': self.model.params_['b']
            }
        else:
            # Simplified implementation using MLE
            self._fit_simplified(data)

        return self
    
    def _fit_simplified(self, data: pd.DataFrame):
        """Simplified BG/NBD using method of moments."""
        # Method of moments estimation
        mean_freq = data['frequency'].mean()
        var_freq = data['frequency'].var()
        mean_recency = data['recency'].mean()
        
        # Estimate parameters (simplified)
        self.params = {
            'r': max(0.5, mean_freq ** 2 / var_freq) if var_freq > 0 else 1.0,
            'alpha': max(1.0, mean_freq / self.params.get('r', 1)),
            'a': max(0.5, 1.0),
            'b': max(0.5, mean_recency / 30)
        }
        
        self.model = 'simplified'
    
    def predict_expected_purchases(self, t: float, 
                                    frequency: np.ndarray = None,
                                    recency: np.ndarray = None,
                                    T: np.ndarray = None) -> np.ndarray:
        """
        Predict expected number of purchases in next t time units.
        """
        if LIFETIMES_AVAILABLE and self.model is not None:
            if frequency is not None:
                return self.model.expected_number_of_additional_purchases(
                    t, frequency, recency, T
                )
            else:
                # Average prediction
                return np.full(len(frequency) if frequency is not None else 1,
                              self.model.expected_number_of_purchases_up_to_time(t).mean())
        else:
            # Simplified prediction
            r = self.params.get('r', 1)
            alpha = self.params.get('alpha', 1)
            
            expected = r * t / (alpha + t)
            
            if frequency is not None:
                # Adjust for individual history
                adjustment = 1 + 0.1 * (frequency - frequency.mean())
                expected = expected * adjustment
            
            return expected
    
    def predict_probability_alive(self, frequency: np.ndarray,
                                   recency: np.ndarray,
                                   T: np.ndarray) -> np.ndarray:
        """Predict probability customer is still alive."""
        if LIFETIMES_AVAILABLE and hasattr(self.model, 'conditional_probability_alive'):
            return self.model.conditional_probability_alive(
                frequency, recency, T
            )
        else:
            # Simplified: based on recency ratio
            recency_ratio = recency / (T + 1)
            frequency_weight = np.log1p(frequency) / 5
            alive_prob = (1 - recency_ratio) * 0.7 + frequency_weight * 0.3
            return np.clip(alive_prob, 0.01, 0.99)
    
    def plot_expected_purchases(self, t_max: int = 52, save_path: Path = None):
        """Plot expected purchases over time."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        t = np.arange(0, t_max, 1)
        
        if LIFETIMES_AVAILABLE and self.model is not None:
            expected = self.model.expected_number_of_purchases_up_to_time(t)
        else:
            r = self.params.get('r', 1)
            alpha = self.params.get('alpha', 1)
            expected = r * t / (alpha + t)
        
        ax.plot(t, expected, linewidth=2, color='#6366f1')
        ax.fill_between(t, expected * 0.8, expected * 1.2, alpha=0.3, color='#6366f1')
        ax.set_xlabel('Time (weeks)', fontsize=12)
        ax.set_ylabel('Expected Purchases', fontsize=12)
        ax.set_title('Expected Cumulative Purchases Over Time', fontsize=14)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, ax


class GammaGammaFitterWrapper:
    """
    Gamma-Gamma model for predicting monetary value.
    """
    
    def __init__(self):
        self.model = None
        self.params = {}
        
    def prepare_data(self, df: pd.DataFrame,
                     monetary_col: str = 'monetary',
                     frequency_col: str = 'frequency') -> pd.DataFrame:
        """Prepare data for Gamma-Gamma model."""
        data = pd.DataFrame({
            'monetary': df[monetary_col] if monetary_col in df.columns else 100,
            'frequency': df[frequency_col] if frequency_col in df.columns else 1
        })
        
        # Filter out zero or negative monetary values
        data = data[data['monetary'] > 0]
        data = data[data['frequency'] > 0]
        
        return data
    
    def fit(self, df: pd.DataFrame, penalizer_coef: float = 1.0):
        """Fit Gamma-Gamma model."""
        data = self.prepare_data(df)

        if LIFETIMES_AVAILABLE:
            self.model = GammaGammaFitter(penalizer_coef=penalizer_coef)
            self.model.fit(
                data['frequency'],
                data['monetary']
            )
            self.params = {
                'p': self.model.params_['p'],
                'q': self.model.params_['q'],
                'v': self.model.params_['v']
            }
        else:
            # Simplified implementation
            self._fit_simplified(data)

        return self
    
    def _fit_simplified(self, data: pd.DataFrame):
        """Simplified Gamma-Gamma using method of moments."""
        mean_monetary = data['monetary'].mean()
        var_monetary = data['monetary'].var()
        mean_freq = data['frequency'].mean()
        
        # Estimate parameters
        cv = np.sqrt(var_monetary) / mean_monetary if mean_monetary > 0 else 1
        
        self.params = {
            'p': max(0.5, 1 / cv ** 2),
            'q': max(0.5, mean_monetary / 100),
            'v': max(1.0, mean_monetary)
        }
        
        self.model = 'simplified'
    
    def predict_expected_value(self, frequency: np.ndarray = None,
                                monetary: np.ndarray = None) -> np.ndarray:
        """
        Predict expected average transaction value.
        """
        if LIFETIMES_AVAILABLE and self.model is not None:
            if frequency is not None and monetary is not None:
                return self.model.conditional_expected_average_transaction_value(
                    frequency, monetary
                )
            else:
                return np.full(len(frequency) if frequency is not None else 1,
                              self.model.expected_average_transaction_value())
        else:
            # Simplified: regression to mean
            p = self.params.get('p', 1)
            v = self.params.get('v', 100)
            
            if monetary is not None:
                # Shrinkage estimator
                expected = (p * v + frequency * monetary) / (p + frequency)
            else:
                expected = np.full(len(frequency) if frequency is not None else 1, v)
            
            return expected
    
    def plot_monetary_distribution(self, df: pd.DataFrame, save_path: Path = None):
        """Plot observed vs predicted monetary distribution."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        data = self.prepare_data(df)
        
        # Observed distribution
        ax.hist(data['monetary'], bins=50, alpha=0.5, label='Observed', 
                color='#34d399', density=True)
        
        # Predicted mean
        pred_mean = self.predict_expected_value(
            data['frequency'].values,
            data['monetary'].values
        )
        ax.hist(pred_mean, bins=50, alpha=0.5, label='Predicted (GG)', 
                color='#6366f1', density=True)
        
        ax.set_xlabel('Average Transaction Value ($)', fontsize=12)
        ax.set_ylabel('Density', fontsize=12)
        ax.set_title('Monetary Value Distribution: Observed vs Gamma-Gamma', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, ax


class CLVPredictor:
    """
    Combined CLV prediction using BG/NBD + Gamma-Gamma.
    """
    
    def __init__(self, discount_rate: float = 0.1, time_horizon: int = 52):
        self.bgnbd = BGNBDFitter()
        self.gg = GammaGammaFitterWrapper()
        self.discount_rate = discount_rate  # Annual discount rate
        self.time_horizon = time_horizon  # Weeks
        
    def fit(self, df: pd.DataFrame, bgnbd_penalizer: float = 1.0, gg_penalizer: float = 1.0):
        """Fit both BG/NBD and Gamma-Gamma models."""
        self.bgnbd.fit(df, penalizer_coef=bgnbd_penalizer)
        self.gg.fit(df, penalizer_coef=gg_penalizer)
        return self
    
    def predict_clv(self, df: pd.DataFrame, 
                    frequency_col: str = 'frequency',
                    recency_col: str = 'recency',
                    T_col: str = 'customer_age_days',
                    monetary_col: str = 'monetary') -> pd.DataFrame:
        """
        Predict CLV for each customer.
        
        CLV = (Expected Transactions) × (Expected Transaction Value) × (Profit Margin)
        """
        data = self.bgnbd.prepare_data(df)
        monetary = df[monetary_col].values if monetary_col in df.columns else np.ones(len(df)) * 100
        frequency = data['frequency'].values
        recency = data['recency'].values
        T = data['T'].values
        
        # Expected transactions in time horizon
        expected_transactions = self.bgnbd.predict_expected_purchases(
            self.time_horizon, frequency, recency, T
        )
        
        # Probability of being alive
        prob_alive = self.bgnbd.predict_probability_alive(frequency, recency, T)
        
        # Expected transaction value
        expected_value = self.gg.predict_expected_value(frequency, monetary)
        
        # CLV calculation (discounted)
        weekly_discount = self.discount_rate / 52
        discount_factor = (1 - (1 + weekly_discount) ** (-self.time_horizon)) / weekly_discount
        discount_factor = discount_factor / 52  # Annualize
        
        clv = expected_transactions * expected_value * prob_alive * discount_factor
        
        result = pd.DataFrame({
            'customer_id': df['customer_id'] if 'customer_id' in df.columns else range(len(df)),
            'bgnbd_expected_transactions': expected_transactions,
            'prob_alive': prob_alive,
            'gg_expected_value': expected_value,
            'clv_bgnbd': clv
        })
        
        return result
    
    def plot_clv_distribution(self, df: pd.DataFrame, save_path: Path = None):
        """Plot CLV distribution."""
        predictions = self.predict_clv(df)

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        # CLV distribution
        axes[0].hist(predictions['clv_bgnbd'], bins=50, color='#6366f1', alpha=0.7, edgecolor='black')
        axes[0].set_xlabel('CLV ($)', fontsize=12)
        axes[0].set_ylabel('Count', fontsize=12)
        axes[0].set_title('CLV Distribution (BG/NBD + GG)', fontsize=14)
        axes[0].grid(True, alpha=0.3)

        # Expected transactions
        axes[1].hist(predictions['bgnbd_expected_transactions'], bins=50, color='#34d399', alpha=0.7)
        axes[1].set_xlabel('Expected Transactions (52 weeks)', fontsize=12)
        axes[1].set_title('Expected Transactions', fontsize=14)
        axes[1].grid(True, alpha=0.3)

        # Probability alive
        axes[2].hist(predictions['prob_alive'], bins=50, color='#f59e0b', alpha=0.7)
        axes[2].set_xlabel('Probability Alive', fontsize=12)
        axes[2].set_title('Customer Survival Probability', fontsize=14)
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, axes
    
    def save(self, path: Path = None):
        """Save model to disk."""
        if path is None:
            path = MODELS_DIR / "clv_model.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: Path = None) -> 'CLVPredictor':
        """Load model from disk."""
        if path is None:
            path = MODELS_DIR / "clv_model.pkl"
        return joblib.load(path)


def train_clv_model():
    """
    Main function to train CLV model.
    """
    print("Training BG/NBD + Gamma-Gamma CLV model...")

    # Load RFM data
    rfm_path = PROCESSED_DIR / "rfm_segmented.parquet"
    if not rfm_path.exists():
        raise FileNotFoundError(f"RFM data not found at {rfm_path}")

    df = pd.read_parquet(rfm_path)
    print(f"Loaded {len(df)} customers")

    # Train model with higher penalizer for better convergence
    predictor = CLVPredictor(discount_rate=0.1, time_horizon=52)
    predictor.fit(df, bgnbd_penalizer=1.0, gg_penalizer=1.0)

    # Predict CLV
    predictions = predictor.predict_clv(df)

    # Merge with original data (avoid duplicates)
    cols_to_keep = [c for c in df.columns if c not in predictions.columns]
    df_clv = pd.concat([df[cols_to_keep].reset_index(drop=True), predictions], axis=1)

    # Save predictions
    output_path = PROCESSED_DIR / "clv_predictions.parquet"
    df_clv.to_parquet(output_path, index=False)
    print(f"Predictions saved to {output_path}")

    # Save model
    predictor.save()

    # Generate plots
    reports_dir = REPORTS_DIR / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        predictor.bgnbd.plot_expected_purchases(
            save_path=reports_dir / "bgnbd_expected_purchases.png"
        )
    except Exception as e:
        print(f"Warning: Could not generate BG/NBD expected purchases plot: {e}")

    try:
        predictor.gg.plot_monetary_distribution(
            df, save_path=reports_dir / "gamma_gamma_monetary.png"
        )
    except Exception as e:
        print(f"Warning: Could not generate Gamma-Gamma monetary plot: {e}")

    try:
        predictor.plot_clv_distribution(
            df, save_path=reports_dir / "clv_distribution.png"
        )
    except Exception as e:
        print(f"Warning: Could not generate CLV distribution plot: {e}")

    print(f"\nCLV Statistics:")
    print(predictions['clv_bgnbd'].describe())

    return predictor, predictions


if __name__ == "__main__":
    train_clv_model()
