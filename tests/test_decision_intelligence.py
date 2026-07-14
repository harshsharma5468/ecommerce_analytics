import pandas as pd
from src.decision_intelligence import daily_kpis, retention_matrix, detect_revenue_anomalies, inventory_priority

def sample_transactions():
    return pd.DataFrame({"order_id":[1,2,3,4],"customer_id":["a","a","b","c"],"order_date":["2026-01-01","2026-01-15","2026-02-01","2026-02-01"],"total_amount":[100,50,200,300]})

def test_daily_kpis_uses_unique_orders():
    result=daily_kpis(sample_transactions())
    assert result.orders.sum()==4
    assert result.net_revenue.sum()==650

def test_retention_has_initial_period():
    result=retention_matrix(sample_transactions())
    assert (result[0]==1).all()

def test_anomaly_output_has_flags():
    daily=pd.DataFrame({"date":pd.date_range("2026-01-01",periods=5),"net_revenue":[100,101,99,102,500]})
    assert "is_anomaly" in detect_revenue_anomalies(daily).columns

def test_inventory_prioritisation():
    inventory=pd.DataFrame({"sku":["x","y"],"on_hand":[4,100],"avg_daily_units":[2,2]})
    assert inventory_priority(inventory).iloc[0].priority=="critical"
