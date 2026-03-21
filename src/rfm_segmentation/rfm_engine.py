"""
RFM-Based Customer Segmentation Engine
─────────────────────────────────────────────────────────────────────────────
Implements a full RFM pipeline:
  1. Feature Engineering  – Recency / Frequency / Monetary + derived features
  2. Optimal K Selection  – Elbow (inertia), Silhouette, Calinski-Harabasz, Davies-Bouldin
  3. K-Means Clustering   – Robust scaling, PCA visualisation
  4. Segment Profiling    – Business labels, actionable thresholds
  5. CLV Estimation       – BG/NBD-proxy via regression on RFM scores
  6. Export               – Parquet, CSV, JSON metadata
"""
import sys
sys.path.insert(0, "/home/claude/ecommerce_analytics")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path
from datetime import datetime
from sklearn.preprocessing import RobustScaler, MinMaxScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.pipeline import Pipeline
from scipy import stats
from kneed import KneeLocator
from loguru import logger
from rich.console import Console
from rich.table import Table
import warnings
warnings.filterwarnings("ignore")

from config.settings import *

console = Console()
plt.style.use("seaborn-v0_8-whitegrid")
COLORS = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B",
          "#44BBA4", "#E94F37", "#393E41", "#F5F5F5", "#6B4226"]


# ──────────────────────────────────────────────────────────────────────────────
# Feature Engineering
# ──────────────────────────────────────────────────────────────────────────────
def compute_rfm(transactions: pd.DataFrame,
                snapshot_date: str = RFM_SNAPSHOT_DATE) -> pd.DataFrame:
    logger.info("Computing RFM features...")

    snapshot = pd.Timestamp(snapshot_date)
    # Use total_amount (or revenue if available)
    amount_col = "total_amount" if "total_amount" in transactions.columns else "revenue"
    date_col = "order_date" if "order_date" in transactions.columns else "transaction_date"
    id_col = "transaction_id" if "transaction_id" in transactions.columns else "order_id"
    
    txn = transactions[transactions[amount_col] > 0].copy()
    txn["transaction_date"] = pd.to_datetime(txn[date_col])

    rfm = (
        txn.groupby("customer_id")
        .agg(
            last_purchase=("transaction_date", "max"),
            frequency=(id_col, "nunique"),
            monetary=(amount_col, "sum"),
            avg_order_value=(amount_col, lambda x: x[x > 0].mean()),
            total_items=("quantity", "sum"),
            distinct_categories=("category", "nunique"),
            first_purchase=("transaction_date", "min"),
        )
        .reset_index()
    )

    rfm["recency"] = (snapshot - rfm["last_purchase"]).dt.days
    rfm["customer_age_days"] = (snapshot - rfm["first_purchase"]).dt.days
    rfm["purchase_rate"] = rfm["frequency"] / (rfm["customer_age_days"] / 30).clip(lower=1)
    rfm["avg_items_per_order"] = rfm["total_items"] / rfm["frequency"]
    rfm["log_recency"] = np.log1p(rfm["recency"])
    rfm["log_frequency"] = np.log1p(rfm["frequency"])
    rfm["log_monetary"] = np.log1p(rfm["monetary"])

    # RFM Quintile scores (1=worst, 5=best)
    rfm["R_score"] = pd.qcut(rfm["recency"], q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F_score"] = pd.qcut(rfm["frequency"].rank(method="first"), q=5,
                              labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M_score"] = pd.qcut(rfm["monetary"].rank(method="first"), q=5,
                              labels=[1, 2, 3, 4, 5]).astype(int)

    rfm["RFM_score"] = rfm["R_score"] * 100 + rfm["F_score"] * 10 + rfm["M_score"]
    rfm["RFM_composite"] = (rfm["R_score"] + rfm["F_score"] + rfm["M_score"]) / 3

    logger.success(f"RFM computed for {len(rfm):,} customers")
    return rfm


# ──────────────────────────────────────────────────────────────────────────────
# Optimal K Selection
# ──────────────────────────────────────────────────────────────────────────────
def find_optimal_k(X_scaled: np.ndarray,
                   k_range=KMEANS_N_CLUSTERS_RANGE) -> dict:
    logger.info("Running cluster validation metrics across K range...")

    inertias, silhouettes, ch_scores, db_scores = [], [], [], []
    k_list = list(k_range)

    for k in k_list:
        km = KMeans(n_clusters=k, max_iter=KMEANS_MAX_ITER,
                    n_init=KMEANS_N_INIT, random_state=KMEANS_RANDOM_STATE)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(X_scaled, labels, sample_size=5000))
        ch_scores.append(calinski_harabasz_score(X_scaled, labels))
        db_scores.append(davies_bouldin_score(X_scaled, labels))

    # Elbow detection
    kl = KneeLocator(k_list, inertias, curve="convex", direction="decreasing")
    elbow_k = kl.knee or 5

    # Best by silhouette
    best_sil_k = k_list[np.argmax(silhouettes)]

    # Composite score: normalise and combine
    sil_norm = np.array(silhouettes) / max(silhouettes)
    ch_norm = np.array(ch_scores) / max(ch_scores)
    db_norm = 1 - (np.array(db_scores) / max(db_scores))
    composite = (sil_norm + ch_norm + db_norm) / 3
    best_composite_k = k_list[np.argmax(composite)]

    results = {
        "k_list": k_list,
        "inertias": inertias,
        "silhouettes": silhouettes,
        "ch_scores": ch_scores,
        "db_scores": db_scores,
        "elbow_k": elbow_k,
        "best_silhouette_k": best_sil_k,
        "best_composite_k": best_composite_k,
        "recommended_k": best_composite_k,
    }

    logger.success(f"Optimal K → Elbow: {elbow_k}, Silhouette: {best_sil_k}, "
                   f"Composite: {best_composite_k}")
    return results


# ──────────────────────────────────────────────────────────────────────────────
# K-Means Clustering
# ──────────────────────────────────────────────────────────────────────────────
SEGMENT_LABEL_MAP = {
    # Will be assigned post-hoc based on centroid ranking
}

BUSINESS_LABELS = [
    "Champions",
    "Loyal Customers",
    "Potential Loyalists",
    "Recent Customers",
    "Promising",
    "Needs Attention",
    "At Risk",
    "Cannot Lose Them",
    "Hibernating",
    "Lost",
]

def assign_business_labels(cluster_profiles: pd.DataFrame) -> dict:
    """
    Rank clusters by composite RFM score and assign business labels.
    Champions = highest RFM, Lost = lowest.
    """
    ranked = cluster_profiles.sort_values("RFM_composite_mean", ascending=False)
    n = len(ranked)
    labels = BUSINESS_LABELS[:n]
    return dict(zip(ranked["cluster"].values, labels))


def fit_kmeans(rfm: pd.DataFrame, n_clusters: int) -> tuple:
    logger.info(f"Fitting K-Means with K={n_clusters}...")

    feature_cols = ["log_recency", "log_frequency", "log_monetary",
                    "avg_order_value", "purchase_rate", "distinct_categories"]

    X = rfm[feature_cols].fillna(0).values
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, max_iter=KMEANS_MAX_ITER,
                n_init=KMEANS_N_INIT, random_state=KMEANS_RANDOM_STATE)
    labels = km.fit_predict(X_scaled)

    rfm = rfm.copy()
    rfm["cluster"] = labels

    # Cluster profiles
    agg_dict = {
        "recency": ["mean", "median", "std"],
        "frequency": ["mean", "median", "std"],
        "monetary": ["mean", "median", "sum"],
        "avg_order_value": ["mean", "std"],
        "RFM_composite": ["mean"],
        "customer_id": "count",
    }
    profiles = rfm.groupby("cluster").agg(agg_dict)
    profiles.columns = ["_".join(c).strip("_") for c in profiles.columns]
    profiles = profiles.reset_index()
    profiles.rename(columns={"customer_id_count": "n_customers"}, inplace=True)
    profiles["pct_customers"] = profiles["n_customers"] / profiles["n_customers"].sum() * 100
    profiles["pct_revenue"] = (profiles["monetary_sum"] /
                                profiles["monetary_sum"].sum() * 100)

    # Business labels
    label_map = assign_business_labels(profiles)
    rfm["segment"] = rfm["cluster"].map(label_map)
    profiles["segment"] = profiles["cluster"].map(label_map)

    # CLV proxy: 12-month projected value
    rfm["clv_12m"] = (
        rfm["monetary"] / rfm["customer_age_days"].clip(lower=30) * 365 * 0.85
    ).round(2)

    metrics = {
        "inertia": km.inertia_,
        "silhouette": silhouette_score(X_scaled, labels, sample_size=5000),
        "calinski_harabasz": calinski_harabasz_score(X_scaled, labels),
        "davies_bouldin": davies_bouldin_score(X_scaled, labels),
    }

    logger.success(f"Clustering complete | Silhouette: {metrics['silhouette']:.4f}")
    return rfm, profiles, km, scaler, X_scaled, metrics


# ──────────────────────────────────────────────────────────────────────────────
# Visualisation
# ──────────────────────────────────────────────────────────────────────────────
def plot_k_selection(k_results: dict, save_path: Path):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Optimal Cluster Count – Multi-Metric Evaluation", fontsize=16, fontweight="bold")

    k = k_results["k_list"]
    best_k = k_results["recommended_k"]

    axes[0, 0].plot(k, k_results["inertias"], "bo-", linewidth=2, markersize=6)
    axes[0, 0].axvline(best_k, color="red", linestyle="--", alpha=0.7, label=f"K={best_k}")
    axes[0, 0].set_title("Elbow Method (Inertia)"); axes[0, 0].set_xlabel("K"); axes[0, 0].legend()

    axes[0, 1].plot(k, k_results["silhouettes"], "go-", linewidth=2, markersize=6)
    axes[0, 1].axvline(best_k, color="red", linestyle="--", alpha=0.7)
    axes[0, 1].set_title("Silhouette Score"); axes[0, 1].set_xlabel("K")

    axes[1, 0].plot(k, k_results["ch_scores"], "mo-", linewidth=2, markersize=6)
    axes[1, 0].axvline(best_k, color="red", linestyle="--", alpha=0.7)
    axes[1, 0].set_title("Calinski-Harabász Score"); axes[1, 0].set_xlabel("K")

    axes[1, 1].plot(k, k_results["db_scores"], "ro-", linewidth=2, markersize=6)
    axes[1, 1].axvline(best_k, color="red", linestyle="--", alpha=0.7)
    axes[1, 1].set_title("Davies-Bouldin Score (lower=better)"); axes[1, 1].set_xlabel("K")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_rfm_clusters(rfm: pd.DataFrame, X_scaled: np.ndarray, save_path: Path):
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    rfm = rfm.copy()
    rfm["PC1"] = X_pca[:, 0]
    rfm["PC2"] = X_pca[:, 1]

    segments = rfm["segment"].unique()
    color_map = {seg: COLORS[i % len(COLORS)] for i, seg in enumerate(sorted(segments))}

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    fig.suptitle("RFM Customer Segmentation – K-Means Clusters", fontsize=15, fontweight="bold")

    # PCA scatter
    for seg in segments:
        mask = rfm["segment"] == seg
        axes[0].scatter(rfm.loc[mask, "PC1"], rfm.loc[mask, "PC2"],
                        c=color_map[seg], label=seg, alpha=0.5, s=8)
    axes[0].set_title(f"PCA Projection (var explained: {pca.explained_variance_ratio_.sum():.1%})")
    axes[0].set_xlabel("PC1"); axes[0].set_ylabel("PC2")
    axes[0].legend(loc="upper right", fontsize=7, markerscale=3)

    # Bubble: Frequency vs Monetary, size=recency
    seg_agg = rfm.groupby("segment").agg(
        frequency_mean=("frequency", "mean"),
        monetary_mean=("monetary", "mean"),
        recency_mean=("recency", "mean"),
        n=("customer_id", "count"),
    ).reset_index()
    scatter = axes[1].scatter(
        seg_agg["frequency_mean"], seg_agg["monetary_mean"],
        s=seg_agg["n"] / 10, c=[color_map[s] for s in seg_agg["segment"]],
        alpha=0.8, edgecolors="white", linewidths=1.5
    )
    for _, row in seg_agg.iterrows():
        axes[1].annotate(row["segment"], (row["frequency_mean"], row["monetary_mean"]),
                         fontsize=8, ha="center", va="bottom")
    axes[1].set_title("Segment Bubble Chart\n(size = # customers, colour = segment)")
    axes[1].set_xlabel("Avg Frequency"); axes[1].set_ylabel("Avg Monetary (USD)")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_segment_heatmap(rfm: pd.DataFrame, save_path: Path):
    seg_profiles = rfm.groupby("segment").agg(
        Recency=("recency", "mean"),
        Frequency=("frequency", "mean"),
        Monetary=("monetary", "mean"),
        AOV=("avg_order_value", "mean"),
        CLV_12m=("clv_12m", "mean"),
        N_Customers=("customer_id", "count"),
    ).reset_index()

    # Normalise for heatmap
    numeric_cols = ["Recency", "Frequency", "Monetary", "AOV", "CLV_12m"]
    scaler = MinMaxScaler()
    heat_data = seg_profiles[numeric_cols].copy()
    heat_data["Recency"] = 1 - scaler.fit_transform(heat_data[["Recency"]])  # invert recency
    for col in ["Frequency", "Monetary", "AOV", "CLV_12m"]:
        heat_data[col] = scaler.fit_transform(heat_data[[col]])

    heat_data.index = seg_profiles["segment"]

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(heat_data, annot=True, fmt=".2f", cmap="RdYlGn",
                linewidths=0.5, ax=ax, vmin=0, vmax=1,
                annot_kws={"size": 10})
    ax.set_title("RFM Segment Profile Heatmap (Normalised 0–1)", fontsize=14, fontweight="bold")
    ax.set_xlabel(""); ax.set_ylabel("Segment")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    console.rule("[bold blue]RFM Segmentation Engine")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "figures").mkdir(parents=True, exist_ok=True)

    # Load
    txn = pd.read_parquet(RAW_DIR / "transactions.parquet")
    customers = pd.read_parquet(RAW_DIR / "customers.parquet")

    # RFM Features
    rfm = compute_rfm(txn)
    
    # Merge with available customer columns
    customer_cols = ["customer_id"]
    for col in ["region", "acquisition_channel", "age", "gender", "true_segment", "country"]:
        if col in customers.columns:
            customer_cols.append(col)
    
    rfm = rfm.merge(customers[customer_cols], on="customer_id", how="left")

    # Optimal K
    feature_cols = ["log_recency", "log_frequency", "log_monetary",
                    "avg_order_value", "purchase_rate", "distinct_categories"]
    X = rfm[feature_cols].fillna(0).values
    scaler_tmp = RobustScaler()
    X_scaled_tmp = scaler_tmp.fit_transform(X)
    k_results = find_optimal_k(X_scaled_tmp)
    plot_k_selection(k_results, REPORTS_DIR / "figures" / "k_selection.png")

    optimal_k = k_results["recommended_k"]
    console.print(f"\n[bold green]Optimal K selected: {optimal_k}")

    # Fit final model
    rfm_clustered, profiles, km_model, scaler, X_scaled, metrics = fit_kmeans(rfm, optimal_k)

    # Visualisations
    plot_rfm_clusters(rfm_clustered, X_scaled, REPORTS_DIR / "figures" / "rfm_clusters.png")
    plot_segment_heatmap(rfm_clustered, REPORTS_DIR / "figures" / "segment_heatmap.png")

    # Save
    rfm_clustered.to_parquet(PROCESSED_DIR / "rfm_segmented.parquet", index=False)
    rfm_clustered.to_csv(PROCESSED_DIR / "rfm_segmented.csv", index=False)
    profiles.to_parquet(PROCESSED_DIR / "segment_profiles.parquet", index=False)
    profiles.to_csv(PROCESSED_DIR / "segment_profiles.csv", index=False)

    # Summary table
    table = Table(title="Customer Segment Summary", show_header=True,
                  header_style="bold magenta")
    table.add_column("Segment", style="cyan")
    table.add_column("Customers", justify="right")
    table.add_column("% Cust", justify="right")
    table.add_column("Avg Recency", justify="right")
    table.add_column("Avg Frequency", justify="right")
    table.add_column("Avg Monetary", justify="right")
    table.add_column("% Revenue", justify="right")

    for _, row in profiles.sort_values("RFM_composite_mean", ascending=False).iterrows():
        table.add_row(
            str(row["segment"]),
            f"{int(row['n_customers']):,}",
            f"{row['pct_customers']:.1f}%",
            f"{row['recency_mean']:.0f}d",
            f"{row['frequency_mean']:.1f}",
            f"${row['monetary_mean']:,.0f}",
            f"{row['pct_revenue']:.1f}%",
        )
    console.print(table)

    console.print(f"\n[bold]Clustering Quality Metrics:")
    console.print(f"  Silhouette Score:       {metrics['silhouette']:.4f}")
    console.print(f"  Calinski-Harabász:      {metrics['calinski_harabasz']:.1f}")
    console.print(f"  Davies-Bouldin:         {metrics['davies_bouldin']:.4f}")

    return rfm_clustered, profiles, metrics


if __name__ == "__main__":
    main()
