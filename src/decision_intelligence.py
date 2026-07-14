"""Decision intelligence layer for the NexaCommerce analytics platform.

This module turns transaction, customer and inventory data into an explainable
executive operating view. Inputs are pandas DataFrames and column names can be
configured for production schemas.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula: str
    grain: str
    guardrail: str

METRICS = (
    MetricDefinition("net_revenue", "sum(revenue) - sum(refunds)", "day", "exclude cancelled orders"),
    MetricDefinition("orders", "count(distinct order_id)", "day", "deduplicate order_id"),
    MetricDefinition("aov", "net_revenue / orders", "day", "report null when orders = 0"),
    MetricDefinition("repeat_purchase_rate", "repeat_customers / active_customers", "month", "customer_id required"),
)

def _date_column(df: pd.DataFrame) -> str:
    for column in ("order_date", "transaction_date", "date"):
        if column in df:
            return column
    raise ValueError("Expected order_date, transaction_date, or date column.")

def daily_kpis(transactions: pd.DataFrame) -> pd.DataFrame:
    required = {"order_id", "customer_id"}
    missing = required - set(transactions.columns)
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
    date_col = _date_column(transactions)
    amount_col = "revenue" if "revenue" in transactions else "total_amount"
    work = transactions.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[amount_col] = pd.to_numeric(work[amount_col], errors="coerce").fillna(0)
    work = work.dropna(subset=[date_col]).drop_duplicates("order_id")
    refunds = work["refund_amount"].fillna(0) if "refund_amount" in work else 0
    work["net_revenue"] = work[amount_col] - refunds
    daily = work.groupby(work[date_col].dt.date).agg(
        orders=("order_id", "nunique"),
        customers=("customer_id", "nunique"),
        gross_revenue=(amount_col, "sum"),
        net_revenue=("net_revenue", "sum"),
    ).reset_index(names="date")
    daily["aov"] = daily["net_revenue"] / daily["orders"].replace(0, np.nan)
    return daily.sort_values("date")

def retention_matrix(transactions: pd.DataFrame) -> pd.DataFrame:
    date_col = _date_column(transactions)
    work = transactions[["customer_id", date_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna().drop_duplicates()
    work["order_month"] = work[date_col].dt.to_period("M")
    work["cohort_month"] = work.groupby("customer_id")["order_month"].transform("min")
    work["period"] = (work["order_month"].astype(int) - work["cohort_month"].astype(int))
    counts = work.groupby(["cohort_month", "period"])["customer_id"].nunique().unstack(fill_value=0)
    return counts.div(counts[0], axis=0).round(4)

def detect_revenue_anomalies(daily: pd.DataFrame, z_threshold: float = 3.5) -> pd.DataFrame:
    if daily.empty:
        return daily.assign(is_anomaly=pd.Series(dtype=bool), robust_z=pd.Series(dtype=float))
    value = daily["net_revenue"].astype(float)
    median = value.median()
    mad = (value - median).abs().median()
    scale = 1.4826 * mad
    robust_z = (value - median) / scale if scale else pd.Series(0.0, index=daily.index)
    result = daily.copy()
    result["robust_z"] = robust_z.round(2)
    result["is_anomaly"] = result["robust_z"].abs() >= z_threshold
    return result

def inventory_priority(inventory: pd.DataFrame, target_days: int = 21) -> pd.DataFrame:
    required = {"sku", "on_hand", "avg_daily_units"}
    missing = required - set(inventory.columns)
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
    result = inventory.copy()
    result["days_of_cover"] = result["on_hand"] / result["avg_daily_units"].replace(0, np.nan)
    result["recommended_reorder_units"] = ((target_days * result["avg_daily_units"]) - result["on_hand"]).clip(lower=0).round()
    result["priority"] = np.select(
        [result["days_of_cover"].lt(7), result["days_of_cover"].lt(target_days)],
        ["critical", "reorder"], default="healthy",
    )
    return result.sort_values(["priority", "days_of_cover"])

def action_queue(daily: pd.DataFrame, inventory: pd.DataFrame | None = None) -> pd.DataFrame:
    actions = []
    for _, row in detect_revenue_anomalies(daily).query("is_anomaly").iterrows():
        direction = "drop" if row.robust_z < 0 else "spike"
        actions.append({"area": "revenue", "priority": "high", "action": "Investigate revenue " + direction, "evidence": "robust z-score=" + str(row.robust_z), "date": row.date})
    if inventory is not None:
        for _, row in inventory_priority(inventory).query("priority == 'critical'").iterrows():
            actions.append({"area": "inventory", "priority": "critical", "action": "Reorder SKU " + str(row.sku), "evidence": str(round(row.days_of_cover, 1)) + " days of cover", "date": pd.NaT})
    return pd.DataFrame(actions, columns=["area", "priority", "action", "evidence", "date"])
