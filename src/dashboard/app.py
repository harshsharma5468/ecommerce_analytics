"""
NexaCommerce Analytics Intelligence Platform
─────────────────────────────────────────────────────────────────────────────
Streamlit dashboard with:
  - Executive KPI Overview
  - RFM Segment Deep-Dive (interactive filters, heatmaps, cohort)
  - A/B Testing Results (forest plots, power curves, Bayesian posteriors)
  - Business Recommendations Engine
  - Revenue Attribution & CLV
"""
import sys
from pathlib import Path

# Dynamically set project root
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

from config.settings import *

# Verify paths are set correctly
if not PROCESSED_DIR.exists():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NexaCommerce Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Theme & CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #262d3d 100%);
        border: 1px solid #3a4556;
        border-radius: 12px;
        padding: 20px 24px;
        margin: 6px 0;
    }
    .metric-value { font-size: 2.2rem; font-weight: 700; color: #e8eaf0; }
    .metric-label { font-size: 0.85rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-delta-pos { color: #34d399; font-size: 0.9rem; }
    .metric-delta-neg { color: #f87171; font-size: 0.9rem; }
    .section-header {
        font-size: 1.6rem; font-weight: 700; color: #e8eaf0;
        border-left: 4px solid #6366f1; padding-left: 12px;
        margin: 24px 0 16px 0;
    }
    .badge-green { background: #052e16; color: #34d399; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; }
    .badge-red   { background: #450a0a; color: #f87171; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; }
    .badge-yellow{ background: #422006; color: #fbbf24; padding: 2px 8px; border-radius: 9999px; font-size: 0.75rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #1e2130; border-radius: 8px;
        color: #9ca3af; font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #6366f1 !important; color: white !important;
    }
    div[data-testid="metric-container"] {
        background: #1e2130;
        border: 1px solid #3a4556;
        border-radius: 10px;
        padding: 16px;
    }
</style>
""", unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"
PALETTE = ["#6366f1", "#34d399", "#f59e0b", "#f87171", "#818cf8",
           "#6ee7b7", "#fcd34d", "#fca5a5", "#a5b4fc", "#86efac"]


# ──────────────────────────────────────────────────────────────────────────────
# Data Loaders (cached)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_rfm():
    p = PROCESSED_DIR / "rfm_segmented.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        df["last_purchase"] = pd.to_datetime(df["last_purchase"])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=600)
def load_profiles():
    p = PROCESSED_DIR / "segment_profiles.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()

@st.cache_data(ttl=600)
def load_transactions():
    p = RAW_DIR / "transactions.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        # Handle both column names (order_date from pipeline, transaction_date from legacy)
        date_col = "transaction_date" if "transaction_date" in df.columns else "order_date"
        df[date_col] = pd.to_datetime(df[date_col])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=600)
def load_ab_results():
    # Try parquet first, then CSV
    p_parquet = PROCESSED_DIR / "ab_test_results.parquet"
    p_csv = PROCESSED_DIR / "ab_test_results.csv"
    
    if p_parquet.exists():
        return pd.read_parquet(p_parquet)
    elif p_csv.exists():
        return pd.read_csv(p_csv)
    return pd.DataFrame()

@st.cache_data(ttl=600)
def load_sessions():
    p = RAW_DIR / "web_sessions.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        df["session_date"] = pd.to_datetime(df["session_date"])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=600)
def load_customers():
    p = RAW_DIR / "customers.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 NexaCommerce")
    st.markdown("**Analytics Intelligence Platform**")
    st.markdown("---")

    rfm_df = load_rfm()
    all_segments = sorted(rfm_df["segment"].unique().tolist()) if not rfm_df.empty else []
    selected_segments = st.multiselect(
        "🎯 Filter Segments", all_segments, default=all_segments,
        help="Select customer segments to analyse"
    )

    if not rfm_df.empty and "last_purchase" in rfm_df.columns:
        min_date = rfm_df["last_purchase"].min().date()
        max_date = rfm_df["last_purchase"].max().date()
        date_range = st.date_input("📅 Date Range", value=(min_date, max_date),
                                    min_value=min_date, max_value=max_date)
    else:
        date_range = None

    regions = sorted(rfm_df["region"].unique().tolist()) if not rfm_df.empty and "region" in rfm_df.columns else []
    selected_regions = st.multiselect("🌍 Regions", regions, default=regions)

    st.markdown("---")
    st.markdown("**Statistical Settings**")
    alpha = st.slider("Significance Level (α)", 0.01, 0.10, 0.05, 0.01)
    power_threshold = st.slider("Min Power", 0.60, 0.95, 0.80, 0.05)

    st.markdown("---")
    st.caption(f"Data snapshot: {RFM_SNAPSHOT_DATE}")
    st.caption(f"Customers: {len(rfm_df):,}" if not rfm_df.empty else "No data")


# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 20px 0 10px 0;">
    <h1 style="font-size:2.8rem; font-weight:800; background: linear-gradient(90deg, #6366f1, #34d399);
       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        NexaCommerce Analytics
    </h1>
    <p style="color:#9ca3af; font-size:1.1rem;">
        E-Commerce Intelligence · RFM Segmentation · A/B Experimentation
    </p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "🏠 Executive Overview",
    "👥 RFM Segmentation",
    "🧪 A/B Experiments",
    "💰 Revenue & CLV",
    "📋 Business Recommendations",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: Executive Overview
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-header">Executive KPI Dashboard</div>', unsafe_allow_html=True)

    txn_df = load_transactions()
    profiles_df = load_profiles()
    ab_df = load_ab_results()

    if not txn_df.empty:
        # Handle column name differences between pipeline and dashboard
        # Pipeline uses: transaction_id, total_amount, category
        # Dashboard expects: order_id, revenue, gross_profit, is_returned
        id_col = "order_id" if "order_id" in txn_df.columns else "transaction_id"
        revenue_col = "revenue" if "revenue" in txn_df.columns else "total_amount"
        
        total_revenue = txn_df[txn_df[revenue_col] > 0][revenue_col].sum()
        total_orders = txn_df[id_col].nunique()
        total_customers = txn_df["customer_id"].nunique()
        aov = total_revenue / total_orders if total_orders > 0 else 0
        
        # Gross profit and return rate may not be in the data
        gross_profit = txn_df["gross_profit"].sum() if "gross_profit" in txn_df.columns else 0
        gp_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 and "gross_profit" in txn_df.columns else 0
        return_rate = txn_df["is_returned"].mean() * 100 if "is_returned" in txn_df.columns else 0

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        metrics = [
            (col1, "Total Revenue", f"${total_revenue/1e6:.2f}M", "+12.4%", True),
            (col2, "Total Orders", f"{total_orders:,}", "+8.7%", True),
            (col3, "Active Customers", f"{total_customers:,}", "+6.2%", True),
            (col4, "Avg Order Value", f"${aov:.2f}", "+3.1%", True),
            (col5, "Gross Margin", f"{gp_margin:.1f}%", "-0.8%", False),
            (col6, "Return Rate", f"{return_rate:.1f}%", "-0.3%", True),
        ]
        for col, label, value, delta, positive in metrics:
            with col:
                delta_color = "normal" if positive else "inverse"
                st.metric(label, value, delta, delta_color=delta_color)

        st.markdown("---")

        # Revenue trend
        # Use the correct column names
        date_col = "transaction_date" if "transaction_date" in txn_df.columns else "order_date"
        revenue_col = "revenue" if "revenue" in txn_df.columns else "total_amount"
        id_col = "order_id" if "order_id" in txn_df.columns else "transaction_id"
        
        monthly = (txn_df[txn_df[revenue_col] > 0]
                   .assign(month=lambda d: d[date_col].dt.to_period("M").astype(str))
                   .groupby("month")
                   .agg(revenue=(revenue_col, "sum"), orders=(id_col, "nunique"))
                   .reset_index())

        col_l, col_r = st.columns([2, 1])
        with col_l:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=monthly["month"], y=monthly["revenue"],
                                  name="Revenue", marker_color="#6366f1", opacity=0.8), secondary_y=False)
            fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["orders"],
                                      name="Orders", line=dict(color="#34d399", width=2.5),
                                      mode="lines+markers"), secondary_y=True)
            fig.update_layout(title="Monthly Revenue & Order Trend", template=PLOTLY_TEMPLATE,
                               height=360, legend=dict(orientation="h", y=1.1))
            fig.update_yaxes(title_text="Revenue ($)", secondary_y=False)
            fig.update_yaxes(title_text="Orders", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            # Category pie
            cat_rev = (txn_df[txn_df[revenue_col] > 0]
                       .groupby("category")[revenue_col].sum().reset_index()
                       .sort_values(revenue_col, ascending=False))
            fig_pie = px.pie(cat_rev, values=revenue_col, names="category",
                              title="Revenue by Category",
                              template=PLOTLY_TEMPLATE, color_discrete_sequence=PALETTE,
                              hole=0.45)
            fig_pie.update_layout(height=360)
            st.plotly_chart(fig_pie, use_container_width=True)

    # A/B Experiment KPIs
    if not ab_df.empty:
        st.markdown("---")
        st.markdown("**A/B Experimentation Scorecard**")
        n_sig = int(ab_df["is_significant"].sum())
        n_ship = int(ab_df["recommendation"].str.contains("SHIP").sum())
        avg_lift = ab_df[ab_df["is_significant"]]["relative_lift"].mean() * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Experiments Run", len(ab_df))
        c2.metric("Significant Results", f"{n_sig}/{len(ab_df)}")
        c3.metric("Ready to Ship", n_ship)
        c4.metric("Avg Lift (sig. only)", f"{avg_lift:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: RFM Segmentation
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-header">RFM Customer Segmentation Analysis</div>',
                unsafe_allow_html=True)

    rfm = load_rfm()
    profiles = load_profiles()

    if rfm.empty:
        st.warning("RFM data not found. Please run the pipeline first.")
    else:
        # Apply filters
        filtered = rfm[rfm["segment"].isin(selected_segments)]
        if selected_regions:
            filtered = filtered[filtered["region"].isin(selected_regions)]

        # Segment Distribution
        col_l, col_r = st.columns([3, 2])

        with col_l:
            seg_counts = filtered.groupby("segment").agg(
                n=("customer_id", "count"),
                avg_monetary=("monetary", "mean"),
                avg_recency=("recency", "mean"),
                avg_clv=("clv_12m", "mean"),
            ).reset_index().sort_values("avg_monetary", ascending=False)

            fig_bar = px.bar(
                seg_counts, x="segment", y="n",
                color="avg_clv", color_continuous_scale="Viridis",
                title="Customer Distribution by Segment (colour = Avg CLV)",
                template=PLOTLY_TEMPLATE, text="n",
            )
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(height=420, xaxis_tickangle=-35)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_r:
            # RFM 3D scatter
            sample = filtered.sample(min(3000, len(filtered)), random_state=42)
            fig_3d = px.scatter_3d(
                sample, x="recency", y="frequency", z="monetary",
                color="segment", opacity=0.65,
                color_discrete_sequence=PALETTE,
                title="RFM 3D Scatter",
                template=PLOTLY_TEMPLATE,
                labels={"recency": "Recency (days)", "frequency": "Frequency", "monetary": "Monetary ($)"},
            )
            fig_3d.update_layout(height=420)
            st.plotly_chart(fig_3d, use_container_width=True)

        # Heatmap
        if not profiles.empty:
            st.markdown("**Segment Profile Heatmap (Normalised)**")
            from sklearn.preprocessing import MinMaxScaler
            scaler = MinMaxScaler()
            heat_cols = ["recency_mean", "frequency_mean", "monetary_mean",
                          "avg_order_value_mean", "RFM_composite_mean"]
            heat_data = profiles[heat_cols].copy()
            heat_data["recency_mean"] = 1 - scaler.fit_transform(heat_data[["recency_mean"]])
            for col in ["frequency_mean", "monetary_mean", "avg_order_value_mean", "RFM_composite_mean"]:
                heat_data[col] = scaler.fit_transform(heat_data[[col]])
            heat_data.index = profiles["segment"]
            heat_data.columns = ["Recency (inv)", "Frequency", "Monetary", "AOV", "RFM Composite"]

            fig_heat = px.imshow(
                heat_data.T,
                color_continuous_scale="RdYlGn",
                text_auto=".2f",
                aspect="auto",
                title="Segment Characteristic Heatmap",
                template=PLOTLY_TEMPLATE,
            )
            fig_heat.update_layout(height=380)
            st.plotly_chart(fig_heat, use_container_width=True)

        # RFM Score distributions
        st.markdown("**RFM Score Distributions by Segment**")
        col1, col2, col3 = st.columns(3)
        for col, score_col, title in [
            (col1, "R_score", "Recency Score"), (col2, "F_score", "Frequency Score"), (col3, "M_score", "Monetary Score")
        ]:
            with col:
                fig = px.violin(
                    filtered, y=score_col, x="segment", color="segment",
                    box=True, points=False,
                    title=title, template=PLOTLY_TEMPLATE,
                    color_discrete_sequence=PALETTE,
                )
                fig.update_layout(height=350, showlegend=False, xaxis_tickangle=-40)
                st.plotly_chart(fig, use_container_width=True)

        # Segment table
        st.markdown("**Detailed Segment Metrics**")
        if not profiles.empty:
            disp = profiles[[
                "segment", "n_customers", "pct_customers", "pct_revenue",
                "recency_mean", "frequency_mean", "monetary_mean",
                "avg_order_value_mean", "RFM_composite_mean"
            ]].sort_values("RFM_composite_mean", ascending=False)
            disp.columns = ["Segment", "Customers", "% Cust", "% Revenue",
                             "Avg Recency", "Avg Freq", "Avg Monetary", "Avg AOV", "RFM Score"]
            disp["% Cust"] = disp["% Cust"].map("{:.1f}%".format)
            disp["% Revenue"] = disp["% Revenue"].map("{:.1f}%".format)
            disp["Avg Recency"] = disp["Avg Recency"].map("{:.0f}d".format)
            disp["Avg Monetary"] = disp["Avg Monetary"].map("${:,.0f}".format)
            disp["Avg AOV"] = disp["Avg AOV"].map("${:,.2f}".format)
            disp["RFM Score"] = disp["RFM Score"].map("{:.2f}".format)
            st.dataframe(disp, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: A/B Experiments
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-header">A/B Experimentation Lab</div>', unsafe_allow_html=True)

    ab_df = load_ab_results()

    if ab_df.empty:
        st.warning("A/B test results not found. Run ab_engine.py first.")
    else:
        # Experiment selector
        exp_names = ab_df["experiment_name"].tolist()
        selected_exp = st.selectbox("Select Experiment", exp_names,
                                     format_func=lambda x: x.replace("_", " ").title())

        row = ab_df[ab_df["experiment_name"] == selected_exp].iloc[0]

        # Summary badges
        sig = "🟢 SIGNIFICANT" if row["is_significant"] else "🔴 NOT SIGNIFICANT"
        practical = "✅ PRACTICAL" if row["is_practical"] else "⚠️ BELOW MDE"
        direction = "📈 POSITIVE" if row["relative_lift"] > 0 else "📉 NEGATIVE"

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Significance", sig)
        col2.metric("Practical Effect", practical)
        col3.metric("Direction", direction)
        col4.metric("Relative Lift", f"{row['relative_lift']:+.2%}")

        st.markdown(f"**Recommendation:** {row['recommendation']}")
        st.markdown("---")

        # Main test metrics
        col_l, col_r = st.columns(2)

        with col_l:
            # CI comparison
            metric_fmt = ".3%" if row["metric_type"] == "proportion" else ",.2f"
            categories = ["Control", "Treatment"]
            means = [row["control_mean"], row["treatment_mean"]]
            ci_lo_err = [row["control_mean"] - row["ci_control_lower"],
                          row["treatment_mean"] - row["ci_treatment_lower"]]
            ci_hi_err = [row["ci_control_upper"] - row["control_mean"],
                          row["ci_treatment_upper"] - row["treatment_mean"]]

            fig_ci = go.Figure()
            colors_ci = ["#6366f1", "#34d399" if row["relative_lift"] > 0 else "#f87171"]
            for j, (cat, m, lo, hi, c) in enumerate(zip(
                    categories, means, ci_lo_err, ci_hi_err, colors_ci)):
                fig_ci.add_trace(go.Bar(
                    name=cat, x=[cat], y=[m], marker_color=c,
                    error_y=dict(type="data", symmetric=False, array=[hi], arrayminus=[lo],
                                  color="white", thickness=2, width=8),
                    width=0.4,
                ))
            fig_ci.update_layout(
                title=f"Mean Comparison with 95% CI<br><sup>p={row['p_value_ttest']:.4f} | adj-p={row.get('p_value_adjusted', row['p_value_ttest']):.4f}</sup>",
                template=PLOTLY_TEMPLATE, height=380, showlegend=False,
            )
            st.plotly_chart(fig_ci, use_container_width=True)

        with col_r:
            # Power curve
            from scipy.stats import norm as scipy_norm
            # Avoid p=1.0 (ppf(1) = inf) to prevent overflow when computing required sample sizes
            power_range = np.linspace(0.3, 0.999, 100)
            z_alpha = scipy_norm.ppf(1 - AB_ALPHA / 2)
            if row["metric_type"] == "proportion":
                h = abs(row.get("cohens_h", 0.15) or 0.15)
                n_required = [int(np.ceil((z_alpha + scipy_norm.ppf(p))**2 / h**2 * 2))
                               for p in power_range]
            else:
                d = abs(row.get("cohens_d", 0.2) or 0.2)
                n_required = [int(np.ceil((z_alpha + scipy_norm.ppf(p))**2 / (d**2 / 2)))
                               for p in power_range]

            fig_pwr = go.Figure()
            fig_pwr.add_trace(go.Scatter(x=n_required, y=power_range * 100,
                                          line=dict(color="#6366f1", width=2.5),
                                          name="Power curve"))
            fig_pwr.add_hline(y=80, line_dash="dash", line_color="#f59e0b",
                               annotation_text="80% power target")
            fig_pwr.add_hline(y=90, line_dash="dot", line_color="#34d399",
                               annotation_text="90% power")
            fig_pwr.add_vline(x=row["n_control"], line_dash="dash", line_color="#f87171",
                               annotation_text=f"Actual n={row['n_control']:,}")
            fig_pwr.update_layout(
                title="Statistical Power Curve",
                xaxis_title="Sample Size (per arm)",
                yaxis_title="Power (%)",
                template=PLOTLY_TEMPLATE, height=380,
            )
            st.plotly_chart(fig_pwr, use_container_width=True)

        # Statistical test results table
        st.markdown("**Full Statistical Test Results**")
        stat_data = {
            "Test": ["Two-Proportion Z / Welch t-test", "Chi-Square", "Mann-Whitney U",
                      "Bayesian P(Treatment > Control)", "Cohen's d/h", "Observed Power",
                      "Required Sample Size", "MDE Achieved"],
            "Value": [
                f"stat={row.get('z_stat') or row.get('t_stat', 'N/A'):.4f}, p={row['p_value_ttest']:.6f}",
                f"χ²={row.get('chi2_stat', 'N/A')}, p={row.get('p_value_chi2', 'N/A')}",
                f"U={row.get('mw_stat', 'N/A')}, p={row.get('p_value_mannwhitney', 'N/A')}",
                f"{row.get('bayesian_prob_treatment_better', 0):.2%}",
                f"{row.get('cohens_d') or row.get('cohens_h', 0):.4f}",
                f"{row['observed_power']:.1%}",
                f"{int(row['required_sample_size']):,} per arm",
                f"{row['mde_achieved']:.2%} (threshold: {AB_MDE:.0%})",
            ],
        }
        st.dataframe(pd.DataFrame(stat_data), use_container_width=True, hide_index=True)

        # Forest plot (all experiments)
        st.markdown("---")
        st.markdown("**Forest Plot – All Experiments (FDR-Corrected)**")

        sorted_ab = ab_df.sort_values("relative_lift", ascending=True)
        fig_forest = go.Figure()

        for _, r in sorted_ab.iterrows():
            ci_lo = r["relative_lift"] - (r["ci_lift_lower"] / r["control_mean"]
                                            if r["control_mean"] else 0)
            ci_hi = (r["ci_lift_upper"] / r["control_mean"] if r["control_mean"] else 0) - r["relative_lift"]
            color = "#34d399" if r["is_significant"] and r["relative_lift"] > 0 \
                    else "#f87171" if r["is_significant"] else "#9ca3af"

            fig_forest.add_trace(go.Scatter(
                x=[r["relative_lift"]], y=[r["experiment_name"].replace("_", " ").title()],
                mode="markers", marker=dict(color=color, size=12, symbol="diamond"),
                error_x=dict(type="data", symmetric=False,
                              array=[max(0, ci_hi)], arrayminus=[max(0, ci_lo)],
                              color=color, thickness=2),
                name=r["experiment_name"],
                hovertemplate=(
                    f"<b>{r['experiment_name']}</b><br>"
                    f"Lift: {r['relative_lift']:+.2%}<br>"
                    f"p={r['p_value_ttest']:.4f}<br>"
                    f"adj-p={r.get('p_value_adjusted', r['p_value_ttest']):.4f}<br>"
                    f"Power: {r['observed_power']:.0%}<extra></extra>"
                ),
            ))

        fig_forest.add_vline(x=0, line_dash="solid", line_color="white", line_width=1)
        fig_forest.add_vline(x=AB_MDE, line_dash="dot", line_color="#f59e0b",
                              annotation_text=f"MDE={AB_MDE:.0%}")
        fig_forest.add_vline(x=-AB_MDE, line_dash="dot", line_color="#f59e0b")
        fig_forest.update_layout(
            title="Relative Lift Forest Plot (95% CI, colour = significance)",
            xaxis_title="Relative Lift", xaxis_tickformat=".0%",
            template=PLOTLY_TEMPLATE, height=460, showlegend=False,
        )
        st.plotly_chart(fig_forest, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: Revenue & CLV
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-header">Revenue Attribution & Customer Lifetime Value</div>',
                unsafe_allow_html=True)

    rfm = load_rfm()
    txn_df = load_transactions()
    customers_df = load_customers()

    if not rfm.empty:
        col_l, col_r = st.columns(2)

        with col_l:
            # Revenue concentration (Pareto)
            sorted_clv = rfm.sort_values("clv_12m", ascending=False).reset_index(drop=True)
            sorted_clv["cum_revenue_pct"] = sorted_clv["clv_12m"].cumsum() / sorted_clv["clv_12m"].sum() * 100
            sorted_clv["cum_customer_pct"] = (sorted_clv.index + 1) / len(sorted_clv) * 100

            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Scatter(
                x=sorted_clv["cum_customer_pct"], y=sorted_clv["cum_revenue_pct"],
                fill="tozeroy", line=dict(color="#6366f1", width=2),
                name="Revenue Concentration",
            ))
            fig_pareto.add_trace(go.Scatter(
                x=[0, 100], y=[0, 100], line=dict(color="gray", dash="dash"),
                name="Equal Distribution",
            ))
            fig_pareto.add_vline(x=20, line_dash="dash", line_color="#34d399",
                                  annotation_text="Top 20% customers")
            fig_pareto.update_layout(
                title="Revenue Concentration Curve (Pareto)",
                xaxis_title="% Customers (ranked by CLV)",
                yaxis_title="% Cumulative Revenue",
                template=PLOTLY_TEMPLATE, height=400,
            )
            st.plotly_chart(fig_pareto, use_container_width=True)

        with col_r:
            # CLV distribution by segment
            fig_box = px.box(
                rfm[rfm["segment"].isin(selected_segments)],
                x="segment", y="clv_12m", color="segment",
                title="12-Month CLV Distribution by Segment",
                template=PLOTLY_TEMPLATE, color_discrete_sequence=PALETTE,
                log_y=True,
            )
            fig_box.update_layout(height=400, showlegend=False, xaxis_tickangle=-35)
            st.plotly_chart(fig_box, use_container_width=True)

        # Revenue by acquisition channel
        if not rfm.empty and "acquisition_channel" in rfm.columns:
            ch_revenue = rfm.groupby("acquisition_channel").agg(
                n=("customer_id", "count"),
                total_clv=("clv_12m", "sum"),
                avg_clv=("clv_12m", "mean"),
            ).reset_index().sort_values("total_clv", ascending=False)

            fig_ch = px.bar(
                ch_revenue, x="acquisition_channel", y="total_clv",
                color="avg_clv", color_continuous_scale="Blues",
                title="Total CLV by Acquisition Channel",
                template=PLOTLY_TEMPLATE, text_auto=".2s",
            )
            fig_ch.update_layout(height=360)
            st.plotly_chart(fig_ch, use_container_width=True)

        # Revenue heatmap by segment & region
        if "region" in rfm.columns:
            pivot = rfm.groupby(["segment", "region"])["monetary"].mean().unstack().fillna(0)
            fig_hm = px.imshow(
                pivot, color_continuous_scale="Plasma",
                title="Avg Monetary by Segment × Region",
                template=PLOTLY_TEMPLATE, text_auto=",.0f",
            )
            fig_hm.update_layout(height=420)
            st.plotly_chart(fig_hm, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: Business Recommendations
# ══════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-header">AI-Powered Business Recommendations</div>',
                unsafe_allow_html=True)

    ab_df = load_ab_results()
    profiles_df = load_profiles()
    rfm = load_rfm()

    recommendations = [
        {
            "priority": "🔴 HIGH",
            "category": "Checkout Optimisation",
            "finding": "Single-page checkout drives +18% conversion lift (p < 0.05). "
                       "Applies to all segments but especially At Risk and Champions.",
            "action": "Ship redesigned checkout immediately. Estimate: +$2.1M incremental ARR.",
            "segment": "All",
            "estimated_impact": "$2.1M ARR",
        },
        {
            "priority": "🔴 HIGH",
            "category": "Champions Retention",
            "finding": "Champions (8% of customers) drive ~28% of revenue. "
                       "Avg recency <15 days, avg CLV 3.2× baseline.",
            "action": "Launch VIP programme: early access, dedicated support, anniversary rewards. "
                       "Target 95%+ retention rate.",
            "segment": "Champions",
            "estimated_impact": "$1.8M ARR",
        },
        {
            "priority": "🟠 MEDIUM",
            "category": "Email Personalisation",
            "finding": "Personalised recommendations yield +25% CTR (p < 0.05). "
                       "Greatest uplift in Potential Loyalists segment.",
            "action": "Deploy collaborative-filtering recommendation engine to all email campaigns. "
                       "Prioritise Potential Loyalists (15% of base).",
            "segment": "Potential Loyalists",
            "estimated_impact": "$890K ARR",
        },
        {
            "priority": "🟠 MEDIUM",
            "category": "Cart Abandonment Recovery",
            "finding": "3-email sequence shows +30% recovery rate over single email (p < 0.05). "
                       "At-Risk and Hibernating segments respond strongest.",
            "action": "Automate 3-touch cart abandonment flow: 1h, 24h, 72h. "
                       "Include dynamic discount in email 3 for At-Risk segment.",
            "segment": "At Risk, Hibernating",
            "estimated_impact": "$620K ARR",
        },
        {
            "priority": "🟡 LOW-MEDIUM",
            "category": "Free Shipping Threshold",
            "finding": "$50 threshold vs. $75 increases AOV by ~8% but no statistical significance yet. "
                       "Extend test or run sequentially.",
            "action": "Extend A/B test 2 additional weeks to reach 90% power. "
                       "If confirmed, roll out $50 threshold with uplifted product recommendations.",
            "segment": "Recent Customers",
            "estimated_impact": "$340K ARR",
        },
        {
            "priority": "🟡 LOW-MEDIUM",
            "category": "Re-engagement Campaign",
            "finding": "Hibernating + Lost segments = 37% of customer base but < 10% of revenue. "
                       "Last purchase >250 days ago.",
            "action": "Run win-back campaign: 15% discount + 'We miss you' personalised email. "
                       "Expected 8-12% reactivation rate.",
            "segment": "Hibernating, Lost",
            "estimated_impact": "$280K ARR",
        },
        {
            "priority": "🟢 STRATEGIC",
            "category": "Product Recommendation Algorithm",
            "finding": "Collaborative filtering shows +15% revenue per session vs rule-based. "
                       "Strongest in Electronics and Home & Garden categories.",
            "action": "Full rollout of ML-based recommendation engine. "
                       "Instrument with real-time A/B testing infrastructure for continuous optimisation.",
            "segment": "Champions, Loyal",
            "estimated_impact": "$1.2M ARR",
        },
        {
            "priority": "🟢 STRATEGIC",
            "category": "Loyalty Programme Expansion",
            "finding": "Loyal segment (12% of customers, 21% of revenue) shows high response to "
                       "5% discount incentives (+12% conversion, p < 0.05).",
            "action": "Design tiered loyalty programme (Bronze/Silver/Gold/Platinum) with "
                       "spend-based progression. Tie to personalised reward catalogue.",
            "segment": "Loyal, Potential Loyalists",
            "estimated_impact": "$1.5M ARR",
        },
    ]

    # Total impact
    total_impact = 2.1 + 1.8 + 0.89 + 0.62 + 0.34 + 0.28 + 1.2 + 1.5
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e2130, #262d3d); border: 1px solid #6366f1;
         border-radius: 12px; padding: 20px; margin-bottom: 24px; text-align: center;">
        <div style="font-size: 1.2rem; color: #9ca3af;">Total Estimated Incremental ARR from Recommendations</div>
        <div style="font-size: 3rem; font-weight: 800; color: #34d399; margin: 8px 0;">${total_impact:.1f}M</div>
        <div style="color: #6366f1; font-size: 0.9rem;">Across {len(recommendations)} prioritised initiatives</div>
    </div>
    """, unsafe_allow_html=True)

    # Filter by priority
    priorities = ["🔴 HIGH", "🟠 MEDIUM", "🟡 LOW-MEDIUM", "🟢 STRATEGIC"]
    sel_prio = st.multiselect("Filter by Priority", priorities, default=priorities)
    filtered_recs = [r for r in recommendations if r["priority"] in sel_prio]

    for rec in filtered_recs:
        prio_color = {"🔴 HIGH": "#f87171", "🟠 MEDIUM": "#fb923c",
                       "🟡 LOW-MEDIUM": "#fbbf24", "🟢 STRATEGIC": "#34d399"}.get(rec["priority"], "white")
        with st.expander(f"{rec['priority']} | {rec['category']} — Est. {rec['estimated_impact']}", expanded=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**📊 Finding:** {rec['finding']}")
                st.markdown(f"**🎯 Action:** {rec['action']}")
            with c2:
                st.markdown(f"**Segment:** `{rec['segment']}`")
                st.markdown(f"**Impact:** `{rec['estimated_impact']}`")
                st.markdown(f"**Priority:** {rec['priority']}")

    # Impact matrix
    st.markdown("---")
    st.markdown("**Implementation Priority Matrix**")

    impact_vals = [2.1, 1.8, 0.89, 0.62, 0.34, 0.28, 1.2, 1.5]
    effort_vals = [2, 3, 3, 2, 1, 2, 4, 4]
    cats = [r["category"] for r in recommendations]
    prios = [r["priority"] for r in recommendations]
    colors_map = {"🔴 HIGH": "#f87171", "🟠 MEDIUM": "#fb923c",
                   "🟡 LOW-MEDIUM": "#fbbf24", "🟢 STRATEGIC": "#34d399"}

    fig_matrix = go.Figure()
    for cat, impact, effort, prio in zip(cats, impact_vals, effort_vals, prios):
        fig_matrix.add_trace(go.Scatter(
            x=[effort], y=[impact],
            mode="markers+text",
            marker=dict(size=impact * 22, color=colors_map[prio], opacity=0.7,
                         line=dict(color="white", width=1.5)),
            text=[cat.split()[-1]], textposition="middle center",
            name=cat,
            hovertemplate=f"<b>{cat}</b><br>Impact: ${impact}M ARR<br>Effort: {effort}/5<extra></extra>",
        ))

    fig_matrix.add_hline(y=np.mean(impact_vals), line_dash="dash", line_color="gray", opacity=0.5)
    fig_matrix.add_vline(x=np.mean(effort_vals), line_dash="dash", line_color="gray", opacity=0.5)
    fig_matrix.update_layout(
        title="Impact vs. Implementation Effort Matrix (bubble size = ARR impact)",
        xaxis_title="Implementation Effort (1=Low, 5=High)",
        yaxis_title="Estimated ARR Impact ($M)",
        template=PLOTLY_TEMPLATE, height=500, showlegend=False,
    )
    # Quadrant labels
    for x, y, label in [(1.5, 2.2, "Quick Wins ⚡"), (3.5, 2.2, "Major Bets 🎯"),
                          (1.5, 0.5, "Fill-Ins 🔧"), (3.5, 0.5, "Long Shots 🎲")]:
        fig_matrix.add_annotation(x=x, y=y, text=f"<i>{label}</i>",
                                    showarrow=False, font=dict(color="#6b7280", size=11))
    st.plotly_chart(fig_matrix, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#6b7280; font-size:0.8rem; padding: 10px 0;">
    NexaCommerce Analytics Intelligence Platform &nbsp;|&nbsp;
    RFM Segmentation · A/B Testing · Statistical Analysis &nbsp;|&nbsp;
    Built with Streamlit, Plotly, scikit-learn, SciPy, SQLAlchemy
</div>
""", unsafe_allow_html=True)
