import pandas as pd
import pytest
from src.decision_intelligence import daily_kpis, retention_matrix, detect_revenue_anomalies, inventory_priority, action_queue

def tx():
    return pd.DataFrame({"order_id":[1,2,3,4],"customer_id":["a","a","b","c"],"order_date":["2026-01-01","2026-02-01","2026-01-05","bad"],"total_amount":[100,50,75,200],"refund_amount":[0,5,None,0]})

def test_kpis_validate_revenue_and_refunds():
    out=daily_kpis(tx())
    assert out.net_revenue.sum()==220
    with pytest.raises(ValueError, match="revenue column"):
        daily_kpis(pd.DataFrame({"order_id":[1],"customer_id":["a"],"order_date":["2026-01-01"]}))

def test_kpis_validate_identity_columns():
    with pytest.raises(ValueError, match="customer_id"):
        daily_kpis(pd.DataFrame({"order_id":[1],"revenue":[1],"order_date":["2026-01-01"]}))

def test_retention_cohorts_and_invalid_dates():
    matrix=retention_matrix(tx())
    assert matrix.iloc[0][0]==1
    assert matrix.iloc[0][1]==0.5

def test_anomaly_edge_cases():
    daily=pd.DataFrame({"date":pd.date_range("2026-01-01",periods=6),"net_revenue":[100,102,101,5,99,1000]})
    out=detect_revenue_anomalies(daily,z_threshold=2)
    assert out.is_anomaly.sum()==2
    equal=detect_revenue_anomalies(pd.DataFrame({"date":pd.date_range("2026-01-01",periods=3),"net_revenue":[5,5,5]}))
    assert not equal.is_anomaly.any()
    empty=detect_revenue_anomalies(pd.DataFrame(columns=["date","net_revenue"]))
    assert empty.empty and empty.is_anomaly.dtype==bool

def test_inventory_states_and_zero_demand():
    out=inventory_priority(pd.DataFrame({"sku":["critical","reorder","healthy","zero"],"on_hand":[4,20,50,5],"avg_daily_units":[2,2,2,0]}))
    assert set(out.priority)=={"critical","reorder","healthy","no_demand"}
    with pytest.raises(ValueError, match="avg_daily_units"):
        inventory_priority(pd.DataFrame({"sku":["x"],"on_hand":[1]}))

def test_action_queue_includes_revenue_and_inventory():
    daily=pd.DataFrame({"date":pd.date_range("2026-01-01",periods=5),"net_revenue":[100,101,99,102,500]})
    inventory=pd.DataFrame({"sku":["x"],"on_hand":[2],"avg_daily_units":[2]})
    actions=action_queue(daily,inventory)
    assert {"revenue","inventory"} <= set(actions.area)
    assert "x" in set(actions.sku.dropna())
