"""Explainable decision intelligence for ecommerce operations."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula: str
    grain: str
    guardrail: str

@dataclass(frozen=True)
class DecisionPolicy:
    anomaly_z_threshold: float = 3.5
    critical_cover_days: int = 7
    reorder_cover_days: int = 21

METRICS = (
    MetricDefinition("net_revenue", "sum(revenue) - sum(refund_amount)", "day", "deduplicate order_id"),
    MetricDefinition("orders", "count(distinct order_id)", "day", "deduplicate order_id"),
    MetricDefinition("aov", "net_revenue / orders", "day", "null when orders are zero"),
    MetricDefinition("repeat_purchase_rate", "repeat_customers / active_customers", "month", "stable customer_id required"),
)
DEFAULT_POLICY = DecisionPolicy()

def metric_contract() -> pd.DataFrame:
    """Expose the contract for dashboards and data-catalog consumers."""
    return pd.DataFrame([item.__dict__ for item in METRICS])

def _date_column(frame: pd.DataFrame) -> str:
    for name in ("order_date", "transaction_date", "date"):
        if name in frame.columns:
            return name
    raise ValueError("Expected one date column: order_date, transaction_date, or date.")

def _amount_column(frame: pd.DataFrame) -> str:
    if "revenue" in frame.columns:
        return "revenue"
    if "total_amount" in frame.columns:
        return "total_amount"
    raise ValueError("Expected one revenue column: revenue or total_amount.")

def daily_kpis(transactions: pd.DataFrame) -> pd.DataFrame:
    missing = {"order_id", "customer_id"} - set(transactions.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    date_col, amount_col = _date_column(transactions), _amount_column(transactions)
    work = transactions.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[amount_col] = pd.to_numeric(work[amount_col], errors="coerce").fillna(0)
    work = work.dropna(subset=[date_col]).drop_duplicates("order_id")
    refunds = pd.to_numeric(work["refund_amount"], errors="coerce").fillna(0) if "refund_amount" in work else 0
    work["net_revenue"] = work[amount_col] - refunds
    daily = work.groupby(work[date_col].dt.date).agg(orders=("order_id","nunique"), customers=("customer_id","nunique"), gross_revenue=(amount_col,"sum"), net_revenue=("net_revenue","sum")).reset_index(names="date")
    daily["aov"] = daily["net_revenue"] / daily["orders"].replace(0, np.nan)
    daily.attrs["metric_contract"] = metric_contract().to_dict("records")
    return daily.sort_values("date")

def retention_matrix(transactions: pd.DataFrame) -> pd.DataFrame:
    date_col = _date_column(transactions)
    work = transactions[["customer_id", date_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna().drop_duplicates()
    work["order_month"] = work[date_col].dt.to_period("M")
    work["cohort_month"] = work.groupby("customer_id")["order_month"].transform("min")
    work["period"] = work["order_month"].astype(int) - work["cohort_month"].astype(int)
    counts = work.groupby(["cohort_month","period"])["customer_id"].nunique().unstack(fill_value=0)
    return counts.div(counts.get(0, 1), axis=0).round(4)

def detect_revenue_anomalies(daily: pd.DataFrame, z_threshold: float | None = None, policy: DecisionPolicy = DEFAULT_POLICY) -> pd.DataFrame:
    threshold = policy.anomaly_z_threshold if z_threshold is None else z_threshold
    result = daily.copy()
    if result.empty:
        result["robust_z"] = pd.Series(dtype="float64")
        result["is_anomaly"] = pd.Series(dtype="bool")
        return result
    value = pd.to_numeric(result["net_revenue"], errors="coerce")
    median = value.median()
    mad = (value - median).abs().median()
    robust_z = pd.Series(0.0, index=result.index) if not mad else 0.6745 * (value - median) / mad
    result["robust_z"] = robust_z.round(2)
    result["is_anomaly"] = result["robust_z"].abs() >= threshold
    return result

def inventory_priority(inventory: pd.DataFrame, policy: DecisionPolicy = DEFAULT_POLICY) -> pd.DataFrame:
    missing = {"sku","on_hand","avg_daily_units"} - set(inventory.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    result = inventory.copy()
    result["on_hand"] = pd.to_numeric(result["on_hand"], errors="coerce")
    result["avg_daily_units"] = pd.to_numeric(result["avg_daily_units"], errors="coerce")
    result["days_of_cover"] = result["on_hand"] / result["avg_daily_units"].replace(0, np.nan)
    result["recommended_reorder_units"] = ((policy.reorder_cover_days * result["avg_daily_units"]) - result["on_hand"]).clip(lower=0).fillna(0).round()
    result["priority"] = np.select([result["days_of_cover"].isna(), result["days_of_cover"].lt(policy.critical_cover_days), result["days_of_cover"].lt(policy.reorder_cover_days)], ["no_demand","critical","reorder"], default="healthy")
    rank = {"critical":0,"reorder":1,"healthy":2,"no_demand":3}
    return result.assign(_rank=result["priority"].map(rank)).sort_values(["_rank","days_of_cover"], na_position="last").drop(columns="_rank")

def action_queue(daily: pd.DataFrame, inventory: pd.DataFrame | None = None, policy: DecisionPolicy = DEFAULT_POLICY) -> pd.DataFrame:
    actions = []
    for _, row in detect_revenue_anomalies(daily, policy=policy).query("is_anomaly").iterrows():
        direction = "drop" if row.robust_z < 0 else "spike"
        actions.append({"area":"revenue","priority":"high","action":"Investigate revenue " + direction,"evidence":"robust z-score=" + str(row.robust_z),"date":row.date,"sku":None})
    if inventory is not None and not inventory.empty:
        for _, row in inventory_priority(inventory, policy=policy).query("priority == 'critical'").iterrows():
            actions.append({"area":"inventory","priority":"critical","action":"Reorder SKU " + str(row.sku),"evidence":str(round(row.days_of_cover,1)) + " days of cover","date":pd.NaT,"sku":row.sku})
    return pd.DataFrame(actions, columns=["area","priority","action","evidence","date","sku"])
