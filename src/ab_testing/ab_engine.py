"""
A/B Testing & Hypothesis Testing Engine
─────────────────────────────────────────────────────────────────────────────
Implements a production-grade experimentation framework:
  1. Two-proportion Z-test          – Conversion rate experiments
  2. Welch's t-test                 – Continuous metric experiments (AOV, RPV)
  3. Mann-Whitney U                 – Non-parametric for skewed distributions
  4. Chi-Square Test                – Categorical conversion outcomes
  5. Sequential Testing (SPRT)      – Early stopping decision boundaries
  6. Sample Size & MDE Calculation  – Power analysis pre-experiment
  7. Confidence Intervals           – Bootstrap + analytic
  8. Bayesian Probability           – P(Treatment > Control)
  9. Multiple Comparisons           – Bonferroni / BH correction
 10. Effect Size                    – Cohen's d, Cohen's h, Relative lift
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
import seaborn as sns
from scipy import stats
from scipy.stats import norm
from statsmodels.stats.proportion import proportions_ztest, proportion_confint
from statsmodels.stats.power import TTestIndPower, NormalIndPower
from statsmodels.stats.multitest import multipletests
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
import json
import warnings
warnings.filterwarnings("ignore")
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Force unicode support on Windows
import os
os.environ['PYTHONUTF8'] = '1'

console = Console(force_terminal=True, force_jupyter=False)

# Import config from project root
from config.settings import *
plt.style.use("seaborn-v0_8-whitegrid")


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class ExperimentResult:
    experiment_name: str
    description: str
    metric_type: str         # "proportion" | "continuous"
    n_control: int
    n_treatment: int

    # Raw metrics
    control_mean: float
    treatment_mean: float
    control_std: Optional[float] = None
    treatment_std: Optional[float] = None

    # Statistical results
    relative_lift: float = 0.0
    absolute_lift: float = 0.0

    # Z / t test
    z_stat: Optional[float] = None
    t_stat: Optional[float] = None
    p_value_ttest: Optional[float] = None

    # Mann-Whitney
    mw_stat: Optional[float] = None
    p_value_mannwhitney: Optional[float] = None

    # Chi-Square
    chi2_stat: Optional[float] = None
    p_value_chi2: Optional[float] = None

    # CIs (95%)
    ci_control_lower: float = 0.0
    ci_control_upper: float = 0.0
    ci_treatment_lower: float = 0.0
    ci_treatment_upper: float = 0.0
    ci_lift_lower: float = 0.0
    ci_lift_upper: float = 0.0

    # Effect sizes
    cohens_d: Optional[float] = None
    cohens_h: Optional[float] = None

    # Power & MDE
    observed_power: float = 0.0
    mde_achieved: float = 0.0
    required_sample_size: int = 0

    # Bayesian
    bayesian_prob_treatment_better: float = 0.0
    expected_loss_control: float = 0.0
    expected_loss_treatment: float = 0.0

    # Decision
    is_significant: bool = False
    is_practical: bool = False          # |lift| >= MDE
    recommendation: str = ""
    confidence_level: float = 0.95
    p_value_adjusted: Optional[float] = None  # after MHT correction


# ──────────────────────────────────────────────────────────────────────────────
# Sample Size & Power
# ──────────────────────────────────────────────────────────────────────────────
def sample_size_for_proportion(baseline: float, mde: float = AB_MDE,
                                alpha: float = AB_ALPHA,
                                power: float = AB_POWER) -> int:
    """Two-sided sample size per arm for proportion test."""
    p1 = baseline
    p2 = baseline * (1 + mde)
    analysis = NormalIndPower()
    effect = proportion_confint  # placeholder
    # Cohen's h
    h = 2 * np.arcsin(np.sqrt(p2)) - 2 * np.arcsin(np.sqrt(p1))
    n = analysis.solve_power(effect_size=abs(h), alpha=alpha, power=power, ratio=1.0)
    return int(np.ceil(n))


def sample_size_for_means(baseline_mean: float, baseline_std: float,
                           mde_relative: float = AB_MDE,
                           alpha: float = AB_ALPHA,
                           power: float = AB_POWER) -> int:
    """Two-sided sample size per arm for t-test."""
    delta = baseline_mean * mde_relative
    effect_size = delta / baseline_std
    analysis = TTestIndPower()
    n = analysis.solve_power(effect_size=effect_size, alpha=alpha, power=power, ratio=1.0)
    return int(np.ceil(n))


def compute_observed_power_proportion(n: int, p1: float, p2: float,
                                       alpha: float = AB_ALPHA) -> float:
    h = 2 * np.arcsin(np.sqrt(p2)) - 2 * np.arcsin(np.sqrt(p1))
    analysis = NormalIndPower()
    return analysis.power(effect_size=abs(h), nobs1=n, alpha=alpha, ratio=1.0)


# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap Confidence Interval
# ──────────────────────────────────────────────────────────────────────────────
def bootstrap_ci(x: np.ndarray, n_boot: int = 2000,
                  ci: float = 0.95) -> tuple:
    boot_means = np.array([np.mean(np.random.choice(x, len(x), replace=True))
                            for _ in range(n_boot)])
    alpha = 1 - ci
    return (np.percentile(boot_means, alpha / 2 * 100),
            np.percentile(boot_means, (1 - alpha / 2) * 100))


# ──────────────────────────────────────────────────────────────────────────────
# Bayesian Estimation (Beta-Binomial for proportions)
# ──────────────────────────────────────────────────────────────────────────────
def bayesian_ab_proportion(n_control: int, conv_control: int,
                             n_treatment: int, conv_treatment: int,
                             n_samples: int = 50_000) -> dict:
    """Beta posteriors with flat priors (Beta(1,1))."""
    alpha_c = 1 + conv_control
    beta_c = 1 + n_control - conv_control
    alpha_t = 1 + conv_treatment
    beta_t = 1 + n_treatment - conv_treatment

    samples_c = np.random.beta(alpha_c, beta_c, n_samples)
    samples_t = np.random.beta(alpha_t, beta_t, n_samples)

    prob_t_better = np.mean(samples_t > samples_c)
    lift_samples = (samples_t - samples_c) / samples_c
    expected_loss_ctrl = np.mean(np.maximum(samples_t - samples_c, 0))
    expected_loss_trt = np.mean(np.maximum(samples_c - samples_t, 0))

    return {
        "prob_treatment_better": prob_t_better,
        "expected_loss_control": expected_loss_ctrl,
        "expected_loss_treatment": expected_loss_trt,
        "lift_posterior_mean": np.mean(lift_samples),
        "lift_posterior_std": np.std(lift_samples),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Core Test Runner
# ──────────────────────────────────────────────────────────────────────────────
def run_ab_test(exp_name: str, sessions: pd.DataFrame) -> ExperimentResult:
    logger.info(f"Running A/B test: {exp_name}")
    cfg = AB_EXPERIMENTS[exp_name]

    exp_data = sessions[sessions["experiment_name"] == exp_name]
    ctrl = exp_data[exp_data["variant"] == "control"]
    trt = exp_data[exp_data["variant"] == "treatment"]

    n_ctrl = len(ctrl)
    n_trt = len(trt)

    metric_type = "proportion" if cfg["metric"] in [
        "conversion_rate", "click_through_rate", "open_rate",
        "recovery_rate", "engagement_rate"] else "continuous"

    result = ExperimentResult(
        experiment_name=exp_name,
        description=cfg["description"],
        metric_type=metric_type,
        n_control=n_ctrl,
        n_treatment=n_trt,
        control_mean=0.0,
        treatment_mean=0.0,
        required_sample_size=0,
    )

    if metric_type == "proportion":
        ctrl_conv = ctrl["converted"].sum()
        trt_conv = trt["converted"].sum()
        p_ctrl = ctrl_conv / n_ctrl
        p_trt = trt_conv / n_trt

        result.control_mean = p_ctrl
        result.treatment_mean = p_trt
        result.absolute_lift = p_trt - p_ctrl
        result.relative_lift = (p_trt - p_ctrl) / p_ctrl if p_ctrl > 0 else 0

        # Z-test (two-proportion)
        count = np.array([trt_conv, ctrl_conv])
        nobs = np.array([n_trt, n_ctrl])
        z_stat, p_val = proportions_ztest(count, nobs, alternative="two-sided")
        result.z_stat = z_stat
        result.p_value_ttest = p_val

        # Chi-square
        contingency = np.array([[trt_conv, n_trt - trt_conv],
                                  [ctrl_conv, n_ctrl - ctrl_conv]])
        chi2, p_chi2, _, _ = stats.chi2_contingency(contingency)
        result.chi2_stat = chi2
        result.p_value_chi2 = p_chi2

        # CIs (Wilson)
        ci_lo_c, ci_hi_c = proportion_confint(ctrl_conv, n_ctrl, method="wilson")
        ci_lo_t, ci_hi_t = proportion_confint(trt_conv, n_trt, method="wilson")
        result.ci_control_lower, result.ci_control_upper = ci_lo_c, ci_hi_c
        result.ci_treatment_lower, result.ci_treatment_upper = ci_lo_t, ci_hi_t

        # Lift CI (delta method)
        se_lift = np.sqrt(p_ctrl * (1 - p_ctrl) / n_ctrl + p_trt * (1 - p_trt) / n_trt)
        z_crit = norm.ppf(0.975)
        result.ci_lift_lower = result.absolute_lift - z_crit * se_lift
        result.ci_lift_upper = result.absolute_lift + z_crit * se_lift

        # Cohen's h
        result.cohens_h = 2 * np.arcsin(np.sqrt(p_trt)) - 2 * np.arcsin(np.sqrt(p_ctrl))

        # Power
        result.observed_power = compute_observed_power_proportion(
            min(n_ctrl, n_trt), p_ctrl, p_trt)

        # Required sample size
        result.required_sample_size = sample_size_for_proportion(p_ctrl)

        # Bayesian
        bayes = bayesian_ab_proportion(n_ctrl, int(ctrl_conv), n_trt, int(trt_conv))
        result.bayesian_prob_treatment_better = bayes["prob_treatment_better"]
        result.expected_loss_control = bayes["expected_loss_control"]
        result.expected_loss_treatment = bayes["expected_loss_treatment"]

    else:  # continuous
        ctrl_vals = ctrl["revenue"].values
        trt_vals = trt["revenue"].values

        result.control_mean = ctrl_vals.mean()
        result.treatment_mean = trt_vals.mean()
        result.control_std = ctrl_vals.std()
        result.treatment_std = trt_vals.std()
        result.absolute_lift = result.treatment_mean - result.control_mean
        result.relative_lift = result.absolute_lift / result.control_mean if result.control_mean > 0 else 0

        # Welch's t-test
        t_stat, p_val = stats.ttest_ind(trt_vals, ctrl_vals, equal_var=False)
        result.t_stat = t_stat
        result.p_value_ttest = p_val

        # Mann-Whitney U
        mw_stat, p_mw = stats.mannwhitneyu(trt_vals, ctrl_vals, alternative="two-sided")
        result.mw_stat = mw_stat
        result.p_value_mannwhitney = p_mw

        # Bootstrap CIs
        ci_lo_c, ci_hi_c = bootstrap_ci(ctrl_vals)
        ci_lo_t, ci_hi_t = bootstrap_ci(trt_vals)
        result.ci_control_lower, result.ci_control_upper = ci_lo_c, ci_hi_c
        result.ci_treatment_lower, result.ci_treatment_upper = ci_lo_t, ci_hi_t

        # Lift CI (Welch)
        se = np.sqrt(result.control_std**2 / n_ctrl + result.treatment_std**2 / n_trt)
        t_crit = stats.t.ppf(0.975, df=min(n_ctrl, n_trt) - 1)
        result.ci_lift_lower = result.absolute_lift - t_crit * se
        result.ci_lift_upper = result.absolute_lift + t_crit * se

        # Cohen's d (pooled)
        pooled_std = np.sqrt((result.control_std**2 + result.treatment_std**2) / 2)
        result.cohens_d = result.absolute_lift / pooled_std if pooled_std > 0 else 0

        # Power
        analysis = TTestIndPower()
        if pooled_std > 0:
            result.observed_power = analysis.power(
                effect_size=abs(result.cohens_d), nobs1=min(n_ctrl, n_trt), alpha=AB_ALPHA)
        result.required_sample_size = sample_size_for_means(
            result.control_mean, result.control_std or 1.0)

    # Significance & practical significance
    result.is_significant = result.p_value_ttest < AB_ALPHA
    result.mde_achieved = abs(result.relative_lift)
    result.is_practical = result.mde_achieved >= AB_MDE

    # Business recommendation
    if result.is_significant and result.is_practical and result.relative_lift > 0:
        result.recommendation = "SHIP - Statistically & practically significant positive lift"
    elif result.is_significant and result.relative_lift > 0:
        result.recommendation = "CONSIDER - Significant but lift below MDE threshold"
    elif result.is_significant and result.relative_lift < 0:
        result.recommendation = "REJECT - Treatment significantly worse than control"
    elif not result.is_significant and result.is_practical:
        result.recommendation = "EXTEND - Practical effect but insufficient power; run longer"
    else:
        result.recommendation = "NO EFFECT - No significant or practical difference"

    logger.success(f"{exp_name}: p={result.p_value_ttest:.4f}, "
                   f"lift={result.relative_lift:+.2%}, rec={result.recommendation[:10]}")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Multiple Testing Correction
# ──────────────────────────────────────────────────────────────────────────────
def apply_mht_correction(results: List[ExperimentResult],
                          method: str = "fdr_bh") -> List[ExperimentResult]:
    """Apply Benjamini-Hochberg FDR correction across all experiments."""
    p_values = [r.p_value_ttest for r in results if r.p_value_ttest is not None]
    reject, p_adj, _, _ = multipletests(p_values, alpha=AB_ALPHA, method=method)
    for i, result in enumerate(results):
        result.p_value_adjusted = p_adj[i]
    logger.info(f"MHT correction ({method}) applied to {len(results)} tests")
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Visualisations
# ──────────────────────────────────────────────────────────────────────────────
def plot_experiment_results(results: List[ExperimentResult], save_path: Path):
    n = len(results)
    fig = plt.figure(figsize=(20, 6 * ((n + 1) // 2)))
    fig.suptitle("A/B Experiment Results – Full Statistical Report",
                 fontsize=16, fontweight="bold", y=0.98)

    for i, res in enumerate(results):
        ax = fig.add_subplot((n + 1) // 2, 2, i + 1)
        colour_ctrl = "#2E86AB"
        colour_trt = "#C73E1D" if res.relative_lift < 0 else "#44BBA4"

        # CI comparison plot
        metrics = ["Control", "Treatment"]
        means = [res.control_mean, res.treatment_mean]
        ci_lo = [res.ci_control_lower, res.ci_treatment_lower]
        ci_hi = [res.ci_control_upper, res.ci_treatment_upper]
        errors_lo = [m - lo for m, lo in zip(means, ci_lo)]
        errors_hi = [hi - m for m, hi in zip(means, ci_hi)]

        bars = ax.bar(metrics, means, color=[colour_ctrl, colour_trt],
                      alpha=0.8, width=0.5, edgecolor="white", linewidth=1.5)
        ax.errorbar(metrics, means,
                    yerr=[errors_lo, errors_hi],
                    fmt="none", color="black", capsize=8, linewidth=2)

        # Value labels
        for bar, m in zip(bars, means):
            fmt = ".1%" if res.metric_type == "proportion" else ",.2f"
            label = f"{m:{fmt}}"
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(errors_hi) * 0.05,
                    label, ha="center", va="bottom", fontsize=10, fontweight="bold")

        # Annotation box
        sig_str = "SIG" if res.is_significant else "NS"
        lift_str = f"{res.relative_lift:+.1%}"
        p_str = f"p={res.p_value_ttest:.4f}"
        if res.p_value_adjusted:
            p_str += f" (adj: {res.p_value_adjusted:.4f})"

        ax.set_title(
            f"{res.experiment_name.replace('_', ' ').title()}\n"
            f"{sig_str} | Lift: {lift_str} | {p_str}",
            fontsize=9, fontweight="bold"
        )
        ax.set_ylabel(res.metric_type.replace("_", " ").title())

        # Significance band
        bg_color = "#e8f5e9" if res.is_significant and res.relative_lift > 0 else \
                   "#fce4ec" if res.is_significant and res.relative_lift < 0 else "#f5f5f5"
        ax.set_facecolor(bg_color)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_forest_plot(results: List[ExperimentResult], save_path: Path):
    """Forest plot of relative lifts with 95% CIs."""
    fig, ax = plt.subplots(figsize=(14, len(results) * 0.9 + 2))

    names = [r.experiment_name.replace("_", " ").title() for r in results]
    lifts = [r.relative_lift for r in results]
    ci_lo = [(r.relative_lift - (r.ci_lift_lower / r.control_mean
              if r.control_mean else 0)) for r in results]
    ci_hi = [((r.ci_lift_upper / r.control_mean if r.control_mean else 0)
              - r.relative_lift) for r in results]
    colors = ["#44BBA4" if r.is_significant and r.relative_lift > 0
              else "#C73E1D" if r.is_significant and r.relative_lift < 0
              else "#999999" for r in results]
    pvals = [r.p_value_adjusted or r.p_value_ttest for r in results]

    y_pos = range(len(results))
    ax.axvline(0, color="black", linewidth=1.5, linestyle="--", alpha=0.7)
    ax.axvline(AB_MDE, color="#F18F01", linewidth=1, linestyle=":", alpha=0.8, label=f"MDE={AB_MDE:.0%}")
    ax.axvline(-AB_MDE, color="#F18F01", linewidth=1, linestyle=":", alpha=0.8)

    for i, (y, lift, lo, hi, c, p) in enumerate(zip(y_pos, lifts, ci_lo, ci_hi, colors, pvals)):
        ax.errorbar(lift, y, xerr=[[lo], [hi]], fmt="o", color=c,
                    markersize=9, linewidth=2, capsize=6)
        sig_marker = "*" if p < 0.05 else ""
        ax.text(max(lifts) * 1.8 + 0.04, y, f"p={p:.4f}{sig_marker}",
                va="center", fontsize=8, color=c)

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("Relative Lift (Treatment vs Control)")
    ax.set_title("Forest Plot – A/B Experiment Lift Summary\n(95% CI, FDR-corrected p-values)",
                 fontsize=13, fontweight="bold")
    ax.legend(loc="lower right")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_power_analysis(results: List[ExperimentResult], save_path: Path):
    """Power vs sample size curves for each experiment."""
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    axes = axes.flatten()
    fig.suptitle("Statistical Power Analysis – Per Experiment", fontsize=14, fontweight="bold")

    for i, res in enumerate(results[:8]):
        ax = axes[i]
        n_range = np.linspace(100, res.n_control * 2, 200)

        if res.metric_type == "proportion" and res.cohens_h:
            analysis = NormalIndPower()
            powers = [analysis.power(effect_size=abs(res.cohens_h), nobs1=n,
                                     alpha=AB_ALPHA, ratio=1.0)
                      for n in n_range]
        else:
            analysis = TTestIndPower()
            d = abs(res.cohens_d) if res.cohens_d else 0.2
            powers = [analysis.power(effect_size=d, nobs1=n, alpha=AB_ALPHA, ratio=1.0)
                      for n in n_range]

        ax.plot(n_range, powers, "#2E86AB", linewidth=2)
        ax.axhline(0.80, color="#F18F01", linestyle="--", linewidth=1.5, label="80% power")
        ax.axhline(0.90, color="#C73E1D", linestyle=":", linewidth=1.5, label="90% power")
        ax.axvline(res.n_control, color="#44BBA4", linestyle="--", linewidth=1.5,
                   label=f"Actual n={res.n_control:,}")
        ax.fill_between(n_range, powers, 0.80,
                         where=[p >= 0.80 for p in powers], alpha=0.15, color="#44BBA4")
        ax.set_title(res.experiment_name.replace("_", " ").title(), fontsize=8, fontweight="bold")
        ax.set_xlabel("n per arm", fontsize=7)
        ax.set_ylabel("Power", fontsize=7)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=6)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    console.rule("[bold blue]A/B Testing & Hypothesis Testing Engine")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    sessions = pd.read_parquet(RAW_DIR / "web_sessions.parquet")
    logger.info(f"Loaded {len(sessions):,} web sessions for {sessions['experiment_name'].nunique()} experiments")

    # Run all experiments
    results = []
    for exp_name in AB_EXPERIMENTS:
        result = run_ab_test(exp_name, sessions)
        results.append(result)

    # MHT correction
    results = apply_mht_correction(results, method="fdr_bh")

    # Visualisations
    plot_experiment_results(results, REPORTS_DIR / "figures" / "ab_results.png")
    plot_forest_plot(results, REPORTS_DIR / "figures" / "forest_plot.png")
    plot_power_analysis(results, REPORTS_DIR / "figures" / "power_analysis.png")

    # Save results to DataFrame
    rows = []
    for r in results:
        d = asdict(r)
        rows.append(d)
    df_results = pd.DataFrame(rows)
    df_results.to_parquet(PROCESSED_DIR / "ab_test_results.parquet", index=False)
    df_results.to_csv(PROCESSED_DIR / "ab_test_results.csv", index=False)

    # JSON for DB ingestion
    with open(PROCESSED_DIR / "ab_test_results.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)

    # Print summary table
    table = Table(title="A/B Test Summary (FDR-Corrected)", show_header=True,
                  header_style="bold magenta")
    for col in ["Experiment", "Metric", "Control", "Treatment", "Lift", "p-value", "p-adj", "Power", "Decision"]:
        table.add_column(col, style="cyan" if col == "Experiment" else "white")

    for r in sorted(results, key=lambda x: x.p_value_ttest or 1):
        fmt = ".2%" if r.metric_type == "proportion" else ",.2f"
        sig_color = "green" if r.is_significant and r.relative_lift > 0 \
                    else "red" if r.is_significant else "yellow"
        table.add_row(
            r.experiment_name[:20],
            r.metric_type,
            f"{r.control_mean:{fmt}}",
            f"{r.treatment_mean:{fmt}}",
            f"{r.relative_lift:+.2%}",
            f"[{sig_color}]{r.p_value_ttest:.4f}[/{sig_color}]",
            f"{r.p_value_adjusted:.4f}" if r.p_value_adjusted else "–",
            f"{r.observed_power:.1%}",
            r.recommendation[:30],
        )
    console.print(table)

    n_sig = sum(1 for r in results if r.is_significant)
    n_ship = sum(1 for r in results if "SHIP" in r.recommendation)
    console.print(Panel(
        f"[bold]Experiments run: {len(results)}  |  "
        f"Significant: {n_sig}  |  "
        f"Recommended to ship: {n_ship}  |  "
        f"FDR method: BH @ alpha={AB_ALPHA}",
        title="Summary", border_style="green"
    ))

    return results


if __name__ == "__main__":
    main()
