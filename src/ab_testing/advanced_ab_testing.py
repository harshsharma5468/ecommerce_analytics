"""
Advanced A/B Testing Platform
─────────────────────────────────────────────────────────────────────────────
Extensions:
- Sequential Testing (mSPRT - Modified Sequential Probability Ratio Test)
- Multi-Armed Bandit (Thompson Sampling)
- CUPED Variance Reduction
- SRM (Sample Ratio Mismatch) Detection
- Novelty Effect Detection
"""
import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import beta, norm
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict
import warnings
warnings.filterwarnings("ignore")


# ──────────────────────────────────────────────────────────────────────────────
# Sequential Testing (mSPRT)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SequentialTestConfig:
    """Configuration for sequential testing."""
    alpha: float = 0.05       # Type I error rate
    beta: float = 0.20        # Type II error rate (power = 1 - beta)
    effect_size: float = 0.05  # Minimum detectable effect
    variance: float = 1.0     # Estimated variance
    max_sample_size: int = 10000


class SequentialTester:
    """
    Modified Sequential Probability Ratio Test (mSPRT).
    
    Allows continuous monitoring without alpha inflation.
    Based on "Always Valid P-Values" methodology.
    """
    
    def __init__(self, config: SequentialTestConfig = None):
        self.config = config or SequentialTestConfig()
        self.log_likelihood_ratio = 0
        self.n_control = 0
        self.n_treatment = 0
        self.sum_control = 0
        self.sum_treatment = 0
        self.sum_sq_control = 0
        self.sum_sq_treatment = 0
        self.stopped = False
        self.stopped_early = False
        self.decision = None
        self.stopping_time = None
        
    def update(self, control_value: float, treatment_value: float):
        """Update sequential test with new observation."""
        if self.stopped:
            return
            
        self.n_control += 1
        self.n_treatment += 1
        self.sum_control += control_value
        self.sum_treatment += treatment_value
        self.sum_sq_control += control_value ** 2
        self.sum_sq_treatment += treatment_value ** 2
        
        self._update_llr()
        self._check_stopping()
        
    def update_batch(self, control_values: np.ndarray, treatment_values: np.ndarray):
        """Update with a batch of observations."""
        if self.stopped:
            return
            
        self.n_control += len(control_values)
        self.n_treatment += len(treatment_values)
        self.sum_control += np.sum(control_values)
        self.sum_treatment += np.sum(treatment_values)
        self.sum_sq_control += np.sum(control_values ** 2)
        self.sum_sq_treatment += np.sum(treatment_values ** 2)
        
        self._update_llr()
        self._check_stopping()
        
    def _update_llr(self):
        """Update log-likelihood ratio."""
        if self.n_control < 2 or self.n_treatment < 2:
            self.log_likelihood_ratio = 0
            return
        
        # Calculate means and variances
        mean_control = self.sum_control / self.n_control
        mean_treatment = self.sum_treatment / self.n_treatment
        
        var_control = (self.sum_sq_control / self.n_control) - mean_control ** 2
        var_treatment = (self.sum_sq_treatment / self.n_treatment) - mean_treatment ** 2
        
        # Pooled variance
        pooled_var = (var_control + var_treatment) / 2
        
        if pooled_var <= 0:
            self.log_likelihood_ratio = 0
            return
        
        # Log-likelihood ratio for difference in means
        diff = mean_treatment - mean_control
        se = np.sqrt(2 * pooled_var / self.n_control)  # Assuming equal sample sizes
        
        # Wald's SPRT statistic
        z = diff / se
        self.log_likelihood_ratio = z * np.sqrt(self.n_control + self.n_treatment)
        
    def _check_stopping(self):
        """Check if stopping boundary is crossed."""
        # Boundaries based on alpha and beta
        upper_boundary = np.sqrt(2 * self.n_control * np.log(1 / self.config.alpha))
        lower_boundary = -np.sqrt(2 * self.n_control * np.log(1 / self.config.beta))
        
        if self.log_likelihood_ratio > upper_boundary:
            self.stopped = True
            self.stopped_early = True
            self.decision = "reject_null"
            self.stopping_time = self.n_control + self.n_treatment
        elif self.log_likelihood_ratio < lower_boundary:
            self.stopped = True
            self.stopped_early = True
            self.decision = "fail_to_reject"
            self.stopping_time = self.n_control + self.n_treatment
        elif self.n_control + self.n_treatment >= self.config.max_sample_size:
            self.stopped = True
            self.stopped_early = False
            self.decision = "max_sample_reached"
            self.stopping_time = self.n_control + self.n_treatment
    
    def get_always_valid_pvalue(self) -> float:
        """
        Calculate always-valid p-value.
        
        This p-value remains valid even under optional stopping.
        """
        if self.n_control + self.n_treatment == 0:
            return 1.0
        
        # Ville's inequality-based p-value
        llr = self.log_likelihood_ratio
        pvalue = np.exp(-llr ** 2 / (2 * (self.n_control + self.n_treatment)))
        
        return min(1.0, pvalue)
    
    def get_confidence_sequence(self, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Get confidence sequence (always-valid confidence interval).
        """
        n = self.n_control + self.n_treatment
        if n == 0:
            return (-np.inf, np.inf)
        
        mean_diff = (self.sum_treatment / self.n_treatment) - (self.sum_control / self.n_control)
        
        # Width based on confidence sequence theory
        width = np.sqrt(2 * np.log(2 / (1 - confidence)) / n)
        
        return (mean_diff - width, mean_diff + width)
    
    def get_results(self) -> Dict:
        """Get comprehensive test results."""
        return {
            'n_control': self.n_control,
            'n_treatment': self.n_treatment,
            'mean_control': self.sum_control / max(1, self.n_control),
            'mean_treatment': self.sum_treatment / max(1, self.n_treatment),
            'log_likelihood_ratio': self.log_likelihood_ratio,
            'always_valid_pvalue': self.get_always_valid_pvalue(),
            'confidence_sequence': self.get_confidence_sequence(),
            'stopped': self.stopped,
            'stopped_early': self.stopped_early,
            'decision': self.decision,
            'stopping_time': self.stopping_time
        }


# ──────────────────────────────────────────────────────────────────────────────
# Multi-Armed Bandit (Thompson Sampling)
# ──────────────────────────────────────────────────────────────────────────────

class ThompsonSamplingBandit:
    """
    Thompson Sampling for Multi-Armed Bandit problems.
    
    Automatically balances exploration vs exploitation.
    """
    
    def __init__(self, n_arms: int = 2, arm_names: List[str] = None):
        self.n_arms = n_arms
        self.arm_names = arm_names or [f"arm_{i}" for i in range(n_arms)]
        
        # Beta distribution parameters (for Bernoulli rewards)
        self.alpha = np.ones(n_arms)  # Successes + 1
        self.beta = np.ones(n_arms)   # Failures + 1
        
        # For continuous rewards (Normal approximation)
        self.sum_rewards = np.zeros(n_arms)
        self.sum_sq_rewards = np.zeros(n_arms)
        self.n_pulls = np.zeros(n_arms)
        
        self.total_pulls = 0
        self.history = []
        
    def select_arm(self, use_thompson: bool = True) -> int:
        """
        Select next arm using Thompson Sampling.
        """
        if use_thompson:
            # Sample from posterior
            samples = np.random.beta(self.alpha, self.beta)
            return np.argmax(samples)
        else:
            # Greedy selection (for comparison)
            means = self.alpha / (self.alpha + self.beta)
            return np.argmax(means)
    
    def update(self, arm: int, reward: float, success: bool = None):
        """
        Update arm posterior with observed reward.
        
        Parameters
        ----------
        arm : int
            Index of the arm that was pulled
        reward : float
            Observed reward (can be continuous)
        success : bool, optional
            For Bernoulli rewards, whether it was a success
        """
        self.n_pulls[arm] += 1
        self.total_pulls += 1
        
        if success is not None:
            # Bernoulli update
            if success:
                self.alpha[arm] += 1
            else:
                self.beta[arm] += 1
        else:
            # Continuous reward - use Normal approximation
            self.sum_rewards[arm] += reward
            self.sum_sq_rewards[arm] += reward ** 2
            
            # Update Beta parameters using method of moments
            if self.n_pulls[arm] > 1:
                mean = self.sum_rewards[arm] / self.n_pulls[arm]
                var = (self.sum_sq_rewards[arm] / self.n_pulls[arm]) - mean ** 2
                
                # Convert to Beta parameters (scaled to [0, 1])
                if var > 0 and mean > 0 and mean < 1:
                    # Method of moments for Beta
                    total = mean * (1 - mean) / var - 1
                    self.alpha[arm] = mean * total + 1
                    self.beta[arm] = (1 - mean) * total + 1
        
        self.history.append({
            'arm': arm,
            'reward': reward,
            'total_pulls': self.total_pulls
        })
    
    def get_arm_statistics(self) -> pd.DataFrame:
        """Get statistics for each arm."""
        means = self.alpha / (self.alpha + self.beta)
        variances = (self.alpha * self.beta) / ((self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1))
        
        return pd.DataFrame({
            'arm_name': self.arm_names,
            'n_pulls': self.n_pulls,
            'mean_reward': means,
            'std_reward': np.sqrt(variances),
            'probability_best': self._estimate_probability_best()
        })
    
    def _estimate_probability_best(self, n_samples: int = 10000) -> np.ndarray:
        """Estimate probability each arm is the best."""
        samples = np.random.beta(self.alpha, self.beta, size=(n_samples, self.n_arms))
        best_arms = np.argmax(samples, axis=1)
        
        prob_best = np.zeros(self.n_arms)
        for i in range(self.n_arms):
            prob_best[i] = np.mean(best_arms == i)
        
        return prob_best
    
    def get_regret(self, optimal_mean: float) -> float:
        """Calculate cumulative regret."""
        total_reward = sum(h['reward'] for h in self.history)
        optimal_reward = optimal_mean * self.total_pulls
        return optimal_reward - total_reward


# ──────────────────────────────────────────────────────────────────────────────
# CUPED Variance Reduction
# ──────────────────────────────────────────────────────────────────────────────

class CUPEDAdjuster:
    """
    CUPED (Controlled-Experiment Using Pre-Experiment Data)
    
    Reduces variance by adjusting for pre-experiment covariates.
    """
    
    def __init__(self):
        self.theta = None
        self.mean_control_covariate = None
        
    def fit(self, control_outcome: np.ndarray, control_covariate: np.ndarray):
        """
        Fit CUPED using control group data.
        
        Parameters
        ----------
        control_outcome : np.ndarray
            Outcome variable for control group
        control_covariate : np.ndarray
            Pre-experiment covariate (e.g., pre-experiment metric)
        """
        # Calculate theta (optimal coefficient)
        cov = np.cov(control_outcome, control_covariate)[0, 1]
        var = np.var(control_covariate)
        
        self.theta = cov / var if var > 0 else 0
        self.mean_control_covariate = np.mean(control_covariate)
        
        return self
    
    def adjust(self, outcome: np.ndarray, covariate: np.ndarray) -> np.ndarray:
        """
        Adjust outcome using CUPED.
        
        Returns variance-reduced outcome.
        """
        if self.theta is None:
            raise ValueError("Must fit CUPED first using control group data")
        
        adjusted = outcome - self.theta * (covariate - self.mean_control_covariate)
        return adjusted
    
    def get_variance_reduction(self, original: np.ndarray, adjusted: np.ndarray) -> float:
        """Calculate variance reduction achieved."""
        var_original = np.var(original)
        var_adjusted = np.var(adjusted)
        
        return 1 - (var_adjusted / var_original) if var_original > 0 else 0


# ──────────────────────────────────────────────────────────────────────────────
# SRM Detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_srm(observed: np.ndarray, expected: np.ndarray = None,
               alpha: float = 0.05) -> Dict:
    """
    Detect Sample Ratio Mismatch (SRM).
    
    SRM indicates potential experiment contamination.
    
    Parameters
    ----------
    observed : np.ndarray
        Observed sample counts per variant
    expected : np.ndarray, optional
        Expected proportions (default: equal allocation)
    alpha : float
        Significance level
    
    Returns
    -------
    dict with chi-square statistic, p-value, and SRM detection result
    """
    n = len(observed)
    
    if expected is None:
        expected = np.ones(n) / n
    else:
        expected = np.array(expected)
        expected = expected / expected.sum()
    
    total = observed.sum()
    expected_counts = expected * total
    
    # Chi-square test
    chi_sq = ((observed - expected_counts) ** 2 / expected_counts).sum()
    df = n - 1
    p_value = 1 - stats.chi2.cdf(chi_sq, df)
    
    # Cramér's V for effect size
    cramers_v = np.sqrt(chi_sq / (total * (n - 1)))
    
    srm_detected = p_value < alpha
    
    return {
        'chi_square': chi_sq,
        'degrees_of_freedom': df,
        'p_value': p_value,
        'srm_detected': srm_detected,
        'cramers_v': cramers_v,
        'observed_proportions': observed / total,
        'expected_proportions': expected,
        'interpretation': _interpret_srm(srm_detected, cramers_v)
    }


def _interpret_srm(srm_detected: bool, cramers_v: float) -> str:
    """Interpret SRM results."""
    if not srm_detected:
        return "No SRM detected. Randomization appears valid."
    
    effect = "small" if cramers_v < 0.1 else "medium" if cramers_v < 0.3 else "large"
    return f"SRM detected with {effect} effect size. Check for randomization issues."


# ──────────────────────────────────────────────────────────────────────────────
# Novelty Effect Detection
# ──────────────────────────────────────────────────────────────────────────────

class NoveltyEffectDetector:
    """
    Detect novelty effects in A/B tests.
    
    Uses time-series decomposition to separate:
    - True treatment effect
    - Novelty effect (decaying over time)
    - Seasonal patterns
    """
    
    def __init__(self, window_size: int = 7):
        self.window_size = window_size
        self.daily_effects = []
        
    def add_daily_data(self, date: str, treatment_effect: float, 
                       n_treatment: int, n_control: int):
        """Add daily treatment effect observation."""
        self.daily_effects.append({
            'date': date,
            'effect': treatment_effect,
            'n_treatment': n_treatment,
            'n_control': n_control
        })
    
    def detect_novelty(self) -> Dict:
        """
        Detect if there's a novelty effect pattern.
        
        Novelty effect shows as:
        - Large initial effect
        - Decay over time
        """
        if len(self.daily_effects) < 2 * self.window_size:
            return {'novelty_detected': False, 'reason': 'Insufficient data'}
        
        df = pd.DataFrame(self.daily_effects)
        
        # Split into early and late periods
        mid = len(df) // 2
        early_effect = df.iloc[:mid]['effect'].mean()
        late_effect = df.iloc[mid:]['effect'].mean()
        
        # Calculate decay
        decay = early_effect - late_effect
        
        # Statistical test for difference
        t_stat, p_value = stats.ttest_ind(
            df.iloc[:mid]['effect'],
            df.iloc[mid:]['effect']
        )
        
        novelty_detected = (decay > 0) and (p_value < 0.05)
        
        return {
            'novelty_detected': novelty_detected,
            'early_effect': early_effect,
            'late_effect': late_effect,
            'decay': decay,
            'decay_percentage': decay / early_effect if early_effect > 0 else 0,
            'p_value': p_value,
            'interpretation': self._interpret_novelty(novelty_detected, decay, p_value)
        }
    
    def _interpret_novelty(self, detected: bool, decay: float, p_value: float) -> str:
        """Interpret novelty effect results."""
        if not detected:
            return "No significant novelty effect detected."
        
        return (f"Novelty effect detected. Initial effect decays by "
                f"{decay*100:.1f}% over time (p={p_value:.3f}). "
                f"Consider longer test duration or habituation period.")
    
    def plot_effect_over_time(self):
        """Plot treatment effect over time."""
        import matplotlib.pyplot as plt
        
        df = pd.DataFrame(self.daily_effects)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['date'], df['effect'], marker='o', linewidth=2)
        ax.axhline(y=df['effect'].mean(), color='red', linestyle='--', 
                   label=f"Mean effect: {df['effect'].mean():.4f}")
        
        # Add trend line
        z = np.polyfit(range(len(df)), df['effect'], 1)
        trend = np.poly1d(z)(range(len(df)))
        ax.plot(df['date'], trend, 'g--', alpha=0.5, label='Trend')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Treatment Effect', fontsize=12)
        ax.set_title('Treatment Effect Over Time (Novelty Detection)', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return fig, ax


# ──────────────────────────────────────────────────────────────────────────────
# Main Experiment Runner
# ──────────────────────────────────────────────────────────────────────────────

class AdvancedABTest:
    """
    Comprehensive A/B test with all advanced features.
    """
    
    def __init__(self, experiment_name: str, config: SequentialTestConfig = None):
        self.experiment_name = experiment_name
        self.sequential_tester = SequentialTester(config)
        self.novelty_detector = NoveltyEffectDetector()
        self.cuped_adjuster = CUPEDAdjuster()
        self.srm_check = None
        self.results = {}
        
    def run(self, control_data: pd.DataFrame, treatment_data: pd.DataFrame,
            metric_col: str = 'conversion', covariate_col: str = None,
            date_col: str = None) -> Dict:
        """
        Run comprehensive A/B test.
        
        Parameters
        ----------
        control_data : pd.DataFrame
            Control group data
        treatment_data : pd.DataFrame
            Treatment group data
            metric_col : str
            Column name for the metric
        covariate_col : str, optional
            Pre-experiment covariate for CUPED
        date_col : str, optional
            Date column for novelty detection
        """
        results = {
            'experiment_name': self.experiment_name,
            'basic_stats': {},
            'sequential': {},
            'cuped': {},
            'srm': {},
            'novelty': {}
        }
        
        # Basic statistics
        n_control = len(control_data)
        n_treatment = len(treatment_data)
        
        results['basic_stats'] = {
            'n_control': n_control,
            'n_treatment': n_treatment,
            'mean_control': control_data[metric_col].mean(),
            'mean_treatment': treatment_data[metric_col].mean(),
            'std_control': control_data[metric_col].std(),
            'std_treatment': treatment_data[metric_col].std()
        }
        
        # SRM Check
        observed = np.array([n_control, n_treatment])
        self.srm_check = detect_srm(observed)
        results['srm'] = self.srm_check
        
        # Standard t-test
        t_stat, p_value = stats.ttest_ind(
            control_data[metric_col],
            treatment_data[metric_col],
            equal_var=False
        )
        results['basic_stats']['t_statistic'] = t_stat
        results['basic_stats']['p_value'] = p_value
        
        # CUPED adjustment if covariate provided
        if covariate_col and covariate_col in control_data.columns:
            self.cuped_adjuster.fit(
                control_data[metric_col].values,
                control_data[covariate_col].values
            )
            
            adjusted_control = self.cuped_adjuster.adjust(
                control_data[metric_col].values,
                control_data[covariate_col].values
            )
            adjusted_treatment = self.cuped_adjuster.adjust(
                treatment_data[metric_col].values,
                treatment_data[covariate_col].values
            )
            
            var_reduction = self.cuped_adjuster.get_variance_reduction(
                control_data[metric_col].values,
                adjusted_control
            )
            
            t_stat_cuped, p_value_cuped = stats.ttest_ind(
                adjusted_control,
                adjusted_treatment,
                equal_var=False
            )
            
            results['cuped'] = {
                'variance_reduction': var_reduction,
                'adjusted_t_stat': t_stat_cuped,
                'adjusted_p_value': p_value_cuped
            }
        
        # Sequential testing
        for i in range(min(n_control, n_treatment)):
            self.sequential_tester.update(
                control_data.iloc[i][metric_col],
                treatment_data.iloc[i][metric_col]
            )
        
        results['sequential'] = self.sequential_tester.get_results()
        
        # Novelty detection if date provided
        if date_col and date_col in control_data.columns:
            # Group by date and calculate daily effects
            control_daily = control_data.groupby(date_col)[metric_col].mean()
            treatment_daily = treatment_data.groupby(date_col)[metric_col].mean()
            
            for date in control_daily.index:
                if date in treatment_daily.index:
                    effect = treatment_daily[date] - control_daily[date]
                    self.novelty_detector.add_daily_data(
                        str(date),
                        effect,
                        len(treatment_data[treatment_data[date_col] == date]),
                        len(control_data[control_data[date_col] == date])
                    )
            
            results['novelty'] = self.novelty_detector.detect_novelty()
        
        self.results = results
        return results


if __name__ == "__main__":
    # Example usage
    np.random.seed(42)
    
    # Generate synthetic data
    n = 1000
    control = pd.DataFrame({
        'conversion': np.random.binomial(1, 0.05, n),
        'pre_metric': np.random.normal(100, 20, n),
        'date': pd.date_range('2024-01-01', periods=n, freq='H')
    })
    
    treatment = pd.DataFrame({
        'conversion': np.random.binomial(1, 0.06, n),  # 20% lift
        'pre_metric': np.random.normal(100, 20, n),
        'date': pd.date_range('2024-01-01', periods=n, freq='H')
    })
    
    # Run advanced A/B test
    ab_test = AdvancedABTest("checkout_redesign")
    results = ab_test.run(control, treatment, 
                          metric_col='conversion',
                          covariate_col='pre_metric',
                          date_col='date')
    
    print("\n=== A/B Test Results ===")
    print(f"Control conversion: {results['basic_stats']['mean_control']:.4f}")
    print(f"Treatment conversion: {results['basic_stats']['mean_treatment']:.4f}")
    print(f"Standard p-value: {results['basic_stats']['p_value']:.4f}")
    
    if results['cuped']:
        print(f"\nCUPED variance reduction: {results['cuped']['variance_reduction']:.2%}")
        print(f"CUPED adjusted p-value: {results['cuped']['adjusted_p_value']:.4f}")
    
    print(f"\nAlways-valid p-value: {results['sequential']['always_valid_pvalue']:.4f}")
    print(f"Sequential decision: {results['sequential']['decision']}")
    
    print(f"\nSRM detected: {results['srm']['srm_detected']}")
    
    if results['novelty']:
        print(f"Novelty effect: {results['novelty']['novelty_detected']}")
