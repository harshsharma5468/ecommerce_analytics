"""
Causal Inference Layer
─────────────────────────────────────────────────────────────────────────────
Methods for causal inference from observational data:
- Propensity Score Matching (PSM)
- Difference-in-Differences (DiD)
- Synthetic Control Method
- Inverse Propensity Weighting (IPW)
- Doubly Robust Estimation
"""
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.ensemble import GradientBoostingRegressor
from typing import Tuple, List, Dict, Optional
import warnings
warnings.filterwarnings("ignore")

import matplotlib.pyplot as plt


# ──────────────────────────────────────────────────────────────────────────────
# Propensity Score Matching
# ──────────────────────────────────────────────────────────────────────────────

class PropensityScoreMatcher:
    """
    Propensity Score Matching for causal inference.
    
    Estimates treatment effects from observational data by
    matching treated and control units with similar propensity scores.
    """
    
    def __init__(self, caliper: float = 0.05, matching_ratio: int = 1):
        self.caliper = caliper
        self.matching_ratio = matching_ratio
        self.propensity_model = None
        self.matches = None
        self.matched_data = None
        
    def fit_propensity_model(self, X: pd.DataFrame, treatment: np.ndarray):
        """
        Fit propensity score model (logistic regression).
        
        Parameters
        ----------
        X : pd.DataFrame
            Covariates for matching
        treatment : np.ndarray
            Treatment assignment (0/1)
        """
        self.propensity_model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            C=1.0
        )
        self.propensity_model.fit(X, treatment)
        
        return self
    
    def predict_propensity(self, X: pd.DataFrame) -> np.ndarray:
        """Predict propensity scores."""
        if self.propensity_model is None:
            raise ValueError("Must fit propensity model first")
        return self.propensity_model.predict_proba(X)[:, 1]
    
    def match(self, X: pd.DataFrame, treatment: np.ndarray,
              outcome: np.ndarray) -> pd.DataFrame:
        """
        Perform propensity score matching.
        
        Parameters
        ----------
        X : pd.DataFrame
            Covariates
        treatment : np.ndarray
            Treatment assignment
        outcome : np.ndarray
            Outcome variable
            
        Returns
        -------
        pd.DataFrame with matched pairs
        """
        # Get propensity scores
        propensity = self.predict_propensity(X)
        
        # Separate treated and control
        treated_idx = np.where(treatment == 1)[0]
        control_idx = np.where(treatment == 0)[0]
        
        treated_propensity = propensity[treated_idx]
        control_propensity = propensity[control_idx]
        
        # Match using nearest neighbors
        matches = []
        used_controls = set()
        
        for i, t_idx in enumerate(treated_idx):
            t_prop = treated_propensity[i]
            
            # Find unmatched controls within caliper
            available_controls = [c for c in control_idx if c not in used_controls]
            
            if len(available_controls) == 0:
                continue
            
            # Find nearest neighbor within caliper
            best_match = None
            best_distance = float('inf')
            
            for c_idx in available_controls:
                c_prop = propensity[c_idx]
                distance = abs(t_prop - c_prop)
                
                if distance < self.caliper and distance < best_distance:
                    best_distance = distance
                    best_match = c_idx
            
            if best_match is not None:
                matches.append((t_idx, best_match))
                used_controls.add(best_match)
        
        # Create matched dataset
        matched_rows = []
        for t_idx, c_idx in matches:
            # Treated
            row_t = X.iloc[t_idx].to_dict()
            row_t['treatment'] = 1
            row_t['outcome'] = outcome[t_idx]
            row_t['propensity'] = propensity[t_idx]
            row_t['match_id'] = len(matched_rows)
            matched_rows.append(row_t)
            
            # Control
            row_c = X.iloc[c_idx].to_dict()
            row_c['treatment'] = 0
            row_c['outcome'] = outcome[c_idx]
            row_c['propensity'] = propensity[c_idx]
            row_c['match_id'] = len(matched_rows) - 1
            matched_rows.append(row_c)
        
        self.matched_data = pd.DataFrame(matched_rows)
        self.matches = matches
        
        return self.matched_data
    
    def estimate_att(self) -> Dict:
        """
        Estimate Average Treatment Effect on the Treated (ATT).
        
        Returns
        -------
        dict with ATT estimate, standard error, and confidence interval
        """
        if self.matched_data is None:
            raise ValueError("Must run matching first")
        
        # Calculate within-pair differences
        treated = self.matched_data[self.matched_data['treatment'] == 1]
        control = self.matched_data[self.matched_data['treatment'] == 0]
        
        # Merge on match_id
        merged = pd.merge(
            treated[['match_id', 'outcome']].rename(columns={'outcome': 'treated_outcome'}),
            control[['match_id', 'outcome']].rename(columns={'outcome': 'control_outcome'}),
            on='match_id'
        )
        
        # Pair differences
        merged['diff'] = merged['treated_outcome'] - merged['control_outcome']
        
        att = merged['diff'].mean()
        se = merged['diff'].std() / np.sqrt(len(merged))
        
        ci_lower = att - 1.96 * se
        ci_upper = att + 1.96 * se
        
        t_stat = att / se
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(merged) - 1))
        
        return {
            'att': att,
            'std_error': se,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            't_statistic': t_stat,
            'p_value': p_value,
            'n_matches': len(merged),
            'interpretation': self._interpret_att(att, p_value)
        }
    
    def _interpret_att(self, att: float, p_value: float) -> str:
        """Interpret ATT results."""
        significance = "significant" if p_value < 0.05 else "not significant"
        direction = "positive" if att > 0 else "negative"
        return f"The treatment effect on treated is {att:.4f} ({significance}, {direction})"
    
    def check_balance(self) -> pd.DataFrame:
        """
        Check covariate balance after matching.
        
        Returns dataframe with standardized mean differences.
        """
        if self.matched_data is None:
            raise ValueError("Must run matching first")
        
        treated = self.matched_data[self.matched_data['treatment'] == 1]
        control = self.matched_data[self.matched_data['treatment'] == 0]
        
        balance_results = []
        
        for col in treated.columns:
            if col in ['treatment', 'outcome', 'propensity', 'match_id']:
                continue
            
            mean_t = treated[col].mean()
            mean_c = control[col].mean()
            std_t = treated[col].std()
            std_c = control[col].std()
            
            # Pooled standard deviation
            pooled_std = np.sqrt((std_t ** 2 + std_c ** 2) / 2)
            
            # Standardized mean difference
            smd = (mean_t - mean_c) / pooled_std if pooled_std > 0 else 0
            
            balance_results.append({
                'covariate': col,
                'mean_treated': mean_t,
                'mean_control': mean_c,
                'smd': smd,
                'balanced': abs(smd) < 0.1
            })
        
        return pd.DataFrame(balance_results)
    
    def plot_propensity_distribution(self, save_path: str = None):
        """Plot propensity score distribution by treatment group."""
        if self.matched_data is None:
            raise ValueError("Must run matching first")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        treated = self.matched_data[self.matched_data['treatment'] == 1]
        control = self.matched_data[self.matched_data['treatment'] == 0]
        
        ax.hist(treated['propensity'], alpha=0.5, bins=30, 
                label='Treated', color='#6366f1')
        ax.hist(control['propensity'], alpha=0.5, bins=30,
                label='Control', color='#34d399')
        
        ax.set_xlabel('Propensity Score', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.set_title('Propensity Score Distribution by Treatment Group', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, ax


# ──────────────────────────────────────────────────────────────────────────────
# Difference-in-Differences
# ──────────────────────────────────────────────────────────────────────────────

class DifferenceInDifferences:
    """
    Difference-in-Differences estimator.
    
    Estimates causal effects by comparing changes over time
    between treatment and control groups.
    """
    
    def __init__(self):
        self.pre_treatment_mean = {}
        self.post_treatment_mean = {}
        self.did_estimate = None
        self.regression_results = None
        
    def fit(self, data: pd.DataFrame, treatment_col: str, 
            period_col: str, outcome_col: str,
            unit_col: str = None):
        """
        Fit DiD model.
        
        Parameters
        ----------
        data : pd.DataFrame
            Panel data with treatment and control groups
        treatment_col : str
            Column indicating treatment status (0/1)
        period_col : str
            Column indicating time period (0=pre, 1=post)
        outcome_col : str
            Outcome variable
        unit_col : str, optional
            Unit identifier for panel data
        """
        # Group means
        groups = data.groupby([treatment_col, period_col])[outcome_col].agg(['mean', 'std', 'count'])
        
        self.pre_treatment_mean = {
            'control': groups.loc[(0, 0), 'mean'],
            'treatment': groups.loc[(1, 0), 'mean']
        }
        
        self.post_treatment_mean = {
            'control': groups.loc[(0, 1), 'mean'],
            'treatment': groups.loc[(1, 1), 'mean']
        }
        
        # DiD estimate
        treatment_change = self.post_treatment_mean['treatment'] - self.pre_treatment_mean['treatment']
        control_change = self.post_treatment_mean['control'] - self.pre_treatment_mean['control']
        
        self.did_estimate = treatment_change - control_change
        
        # Regression DiD
        data = data.copy()
        data['treatment_period'] = data[treatment_col] * data[period_col]
        
        model = LinearRegression()
        X = data[[treatment_col, period_col, 'treatment_period']]
        y = data[outcome_col]
        
        model.fit(X, y)
        
        self.regression_results = {
            'coefficients': {
                'treatment': model.coef_[0],
                'period': model.coef_[1],
                'did': model.coef_[2]
            },
            'intercept': model.intercept_,
            'r_squared': model.score(X, y)
        }
        
        return self
    
    def get_results(self) -> Dict:
        """Get comprehensive DiD results."""
        return {
            'did_estimate': self.did_estimate,
            'pre_treatment': self.pre_treatment_mean,
            'post_treatment': self.post_treatment_mean,
            'treatment_change': self.post_treatment_mean['treatment'] - self.pre_treatment_mean['treatment'],
            'control_change': self.post_treatment_mean['control'] - self.pre_treatment_mean['control'],
            'regression': self.regression_results,
            'interpretation': f"The treatment caused a change of {self.did_estimate:.4f} in the outcome"
        }
    
    def plot_parallel_trends(self, data: pd.DataFrame, treatment_col: str,
                             period_col: str, outcome_col: str,
                             save_path: str = None):
        """
        Plot parallel trends assumption.
        
        Shows outcome trends for treatment and control groups.
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Calculate means by period
        trends = data.groupby([treatment_col, period_col])[outcome_col].mean().unstack(0)
        
        periods = trends.index
        ax.plot(periods, trends[0], 'o--', label='Control', color='#34d399', linewidth=2)
        ax.plot(periods, trends[1], 's--', label='Treatment', color='#6366f1', linewidth=2)
        
        # Mark treatment period
        if len(periods) > 1:
            treatment_start = periods[len(periods) // 2]  # Approximate
            ax.axvline(x=treatment_start, color='red', linestyle='--', 
                       alpha=0.5, label='Treatment Start')
        
        ax.set_xlabel('Period', fontsize=12)
        ax.set_ylabel('Outcome', fontsize=12)
        ax.set_title('Parallel Trends: Treatment vs Control', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, ax


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic Control Method
# ──────────────────────────────────────────────────────────────────────────────

class SyntheticControl:
    """
    Synthetic Control Method.
    
    Constructs a weighted combination of control units to approximate
    the treatment unit's pre-intervention characteristics.
    """
    
    def __init__(self):
        self.weights = None
        self.synthetic_unit = None
        self.treatment_unit = None
        self.pre_period_rmse = None
        
    def fit(self, data: pd.DataFrame, treatment_unit: str,
            unit_col: str, time_col: str, outcome_col: str,
            covariates: List[str] = None,
            pre_period: Tuple = None):
        """
        Fit synthetic control.
        
        Parameters
        ----------
        data : pd.DataFrame
            Panel data
        treatment_unit : str
            Identifier for treated unit
        unit_col : str
            Unit identifier column
        time_col : str
            Time identifier column
        outcome_col : str
            Outcome variable
        covariates : list, optional
            Additional covariates for matching
        pre_period : tuple, optional
            (start, end) for pre-intervention period
        """
        self.treatment_unit = treatment_unit
        
        # Get treatment unit data
        treatment_data = data[data[unit_col] == treatment_unit]
        
        # Get control units data
        control_data = data[data[unit_col] != treatment_unit]
        control_units = control_data[unit_col].unique()
        
        # Create outcome matrix (units × time)
        outcome_pivot = data.pivot_table(
            index=unit_col, columns=time_col, values=outcome_col
        )
        
        treatment_outcome = outcome_pivot.loc[treatment_unit].values
        control_outcomes = outcome_pivot.drop(treatment_unit).values
        
        # If pre_period specified, restrict to pre-period
        if pre_period:
            pre_mask = (outcome_pivot.columns >= pre_period[0]) & \
                       (outcome_pivot.columns <= pre_period[1])
            treatment_outcome = treatment_outcome[pre_mask]
            control_outcomes = control_outcomes[:, pre_mask]
        
        # Find optimal weights using constrained optimization
        from scipy.optimize import minimize
        
        def objective(w):
            synthetic = np.dot(control_outcomes, w)
            return np.sum((treatment_outcome - synthetic) ** 2)
        
        # Constraints: weights sum to 1, non-negative
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        bounds = [(0, 1) for _ in range(len(control_units))]
        
        # Optimize
        result = minimize(
            objective,
            x0=np.ones(len(control_units)) / len(control_units),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        self.weights = result.x
        self.control_units = control_units
        
        # Construct synthetic unit
        self.synthetic_unit = np.dot(control_outcomes, self.weights)
        
        # Calculate pre-period RMSE
        self.pre_period_rmse = np.sqrt(np.mean((treatment_outcome - self.synthetic_unit) ** 2))
        
        return self
    
    def get_results(self) -> Dict:
        """Get synthetic control results."""
        return {
            'weights': dict(zip(self.control_units, self.weights)),
            'top_contributors': self._get_top_contributors(5),
            'pre_period_rmse': self.pre_period_rmse,
            'interpretation': "Synthetic control constructed from weighted combination of control units"
        }
    
    def _get_top_contributors(self, n: int = 5) -> List[Tuple]:
        """Get top n contributing control units."""
        sorted_idx = np.argsort(self.weights)[::-1]
        return [(self.control_units[i], self.weights[i]) for i in sorted_idx[:n]]
    
    def plot_synthetic_control(self, data: pd.DataFrame,
                               treatment_unit: str,
                               unit_col: str,
                               time_col: str,
                               outcome_col: str,
                               intervention_time: str = None,
                               save_path: str = None):
        """
        Plot actual vs synthetic outcome.
        """
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Get treatment unit time series
        treatment_ts = data[data[unit_col] == treatment_unit].set_index(time_col)[outcome_col]
        
        # Create synthetic time series
        synthetic_ts = pd.Series(
            self.synthetic_unit,
            index=treatment_ts.index,
            name='Synthetic'
        )
        
        # Plot
        ax.plot(treatment_ts.index, treatment_ts.values, 'o-', 
                label=f'{treatment_unit} (Actual)', color='#6366f1', linewidth=2)
        ax.plot(synthetic_ts.index, synthetic_ts.values, 's--',
                label='Synthetic Control', color='#34d399', linewidth=2)
        
        # Mark intervention
        if intervention_time:
            ax.axvline(x=intervention_time, color='red', linestyle='--',
                       alpha=0.5, label='Intervention')
        
        ax.set_xlabel(time_col, fontsize=12)
        ax.set_ylabel(outcome_col, fontsize=12)
        ax.set_title('Synthetic Control: Actual vs Counterfactual', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")
        
        return fig, ax


# ──────────────────────────────────────────────────────────────────────────────
# Inverse Propensity Weighting
# ──────────────────────────────────────────────────────────────────────────────

class InversePropensityWeighting:
    """
    Inverse Propensity Weighting (IPW) estimator.
    
    Weights observations by inverse of propensity score
    to create a pseudo-population where treatment is randomized.
    """
    
    def __init__(self, trim_threshold: float = 0.05):
        self.trim_threshold = trim_threshold
        self.propensity_model = None
        
    def fit(self, X: pd.DataFrame, treatment: np.ndarray):
        """Fit propensity model for IPW."""
        self.propensity_model = LogisticRegression(max_iter=1000, random_state=42)
        self.propensity_model.fit(X, treatment)
        return self
    
    def estimate_att(self, X: pd.DataFrame, treatment: np.ndarray,
                     outcome: np.ndarray) -> Dict:
        """
        Estimate ATT using IPW.
        """
        # Get propensity scores
        propensity = self.propensity_model.predict_proba(X)[:, 1]
        
        # Trim extreme propensity scores
        mask = (propensity > self.trim_threshold) & \
               (propensity < 1 - self.trim_threshold)
        
        propensity = propensity[mask]
        treatment = treatment[mask]
        outcome = outcome[mask]
        
        # Calculate IPW weights
        # For ATT: weight = 1 for treated, p/(1-p) for control
        weights = np.where(treatment == 1, 1, propensity / (1 - propensity))
        
        # Weighted outcomes
        treated_outcome = np.average(outcome[treatment == 1], 
                                      weights=weights[treatment == 1])
        control_outcome = np.average(outcome[treatment == 0],
                                      weights=weights[treatment == 0])
        
        att = treated_outcome - control_outcome
        
        # Bootstrap standard error
        n_bootstrap = 1000
        att_bootstrap = []
        
        for _ in range(n_bootstrap):
            idx = np.random.choice(len(outcome), len(outcome), replace=True)
            w = weights[idx]
            t = treatment[idx]
            o = outcome[idx]
            
            if len(t[t == 1]) > 0 and len(t[t == 0]) > 0:
                to = np.average(o[t == 1], weights=w[t == 1])
                co = np.average(o[t == 0], weights=w[t == 0])
                att_bootstrap.append(to - co)
        
        se = np.std(att_bootstrap)
        
        return {
            'att': att,
            'std_error': se,
            'ci_lower': att - 1.96 * se,
            'ci_upper': att + 1.96 * se,
            'n_effective': len(outcome)
        }


if __name__ == "__main__":
    # Example: Propensity Score Matching
    np.random.seed(42)
    n = 1000
    
    # Generate synthetic observational data
    X = pd.DataFrame({
        'age': np.random.normal(45, 12, n),
        'income': np.random.normal(50000, 15000, n),
        'education': np.random.binomial(1, 0.4, n),
        'health_score': np.random.normal(70, 15, n)
    })
    
    # Treatment assignment depends on covariates (selection bias)
    logit_p = -2 + 0.03 * X['age'] + 0.0001 * X['income'] + 0.5 * X['education']
    p = 1 / (1 + np.exp(-logit_p))
    treatment = np.random.binomial(1, p)
    
    # Outcome depends on treatment and covariates
    outcome = 100 + 15 * treatment + 0.5 * X['age'] + 0.001 * X['income'] + \
              10 * X['education'] + 0.3 * X['health_score'] + np.random.normal(0, 10, n)
    
    # PSM
    print("=== Propensity Score Matching ===")
    matcher = PropensityScoreMatcher(caliper=0.05)
    matcher.fit_propensity_model(X, treatment)
    matcher.match(X, treatment, outcome)
    
    att_results = matcher.estimate_att()
    print(f"ATT: {att_results['att']:.4f} (SE: {att_results['std_error']:.4f})")
    print(f"95% CI: [{att_results['ci_lower']:.4f}, {att_results['ci_upper']:.4f}]")
    print(f"P-value: {att_results['p_value']:.4f}")
    
    # Balance check
    balance = matcher.check_balance()
    print("\nCovariate Balance:")
    print(balance.to_string())
