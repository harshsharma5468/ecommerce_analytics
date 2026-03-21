"""
Synthetic E-Commerce Dataset Generator
Produces statistically realistic transaction, customer, product, and
web-session data with embedded behavioural patterns for RFM and A/B testing.
"""
import sys
sys.path.insert(0, "/home/claude/ecommerce_analytics")

import numpy as np
import pandas as pd
from faker import Faker
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
import warnings
warnings.filterwarnings("ignore")

from config.settings import *

fake = Faker()
Faker.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
console = Console()


# ──────────────────────────────────────────────────────────────────────────────
# Customer Generation
# ──────────────────────────────────────────────────────────────────────────────
def generate_customers(n: int = N_CUSTOMERS) -> pd.DataFrame:
    logger.info(f"Generating {n:,} customers...")

    segments = list(CUSTOMER_SEGMENTS_GEN.keys())
    proportions = [v["proportion"] for v in CUSTOMER_SEGMENTS_GEN.values()]
    assigned_segments = np.random.choice(segments, size=n, p=proportions)

    acquisition_channels = ["organic_search", "paid_search", "social_media",
                            "email", "referral", "direct", "affiliate", "display_ads"]
    channel_probs = [0.28, 0.22, 0.18, 0.12, 0.08, 0.06, 0.04, 0.02]

    geo_regions = {
        "Northeast": 0.22, "Southeast": 0.18, "Midwest": 0.16,
        "Southwest": 0.14, "West": 0.20, "Northwest": 0.10,
    }

    customers = []
    for i in range(n):
        seg = assigned_segments[i]
        seg_params = CUSTOMER_SEGMENTS_GEN[seg]
        reg_date = fake.date_between(start_date="-3y", end_date="today")
        age = int(np.clip(np.random.normal(38, 12), 18, 75))
        income_bracket = np.random.choice(
            ["<30k", "30-50k", "50-75k", "75-100k", "100-150k", ">150k"],
            p=[0.12, 0.20, 0.25, 0.22, 0.14, 0.07]
        )

        customers.append({
            "customer_id": f"CUST-{i+1:06d}",
            "email": fake.email(),
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "age": age,
            "gender": np.random.choice(["M", "F", "Other"], p=[0.47, 0.50, 0.03]),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "country": "US",
            "region": np.random.choice(list(geo_regions.keys()), p=list(geo_regions.values())),
            "registration_date": reg_date,
            "acquisition_channel": np.random.choice(acquisition_channels, p=channel_probs),
            "income_bracket": income_bracket,
            "true_segment": seg,
            "is_email_opted_in": np.random.choice([True, False], p=[0.72, 0.28]),
            "is_push_opted_in": np.random.choice([True, False], p=[0.45, 0.55]),
            "lifetime_value_bucket": "unknown",
        })

    df = pd.DataFrame(customers)
    logger.success(f"Customers generated: {len(df):,} rows")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Product Catalogue
# ──────────────────────────────────────────────────────────────────────────────
def generate_products(n: int = N_PRODUCTS) -> pd.DataFrame:
    logger.info(f"Generating {n:,} products...")
    categories = list(PRODUCT_CATEGORIES.keys())
    per_cat = n // len(categories)

    products = []
    pid = 1
    for cat in categories:
        params = PRODUCT_CATEGORIES[cat]
        n_cat = per_cat + (n % len(categories) if cat == categories[-1] else 0)
        for _ in range(n_cat):
            base_price = max(1.99, np.random.normal(params["avg_price"], params["std_price"]))
            cost = base_price * (1 - params["margin"])
            products.append({
                "product_id": f"PROD-{pid:04d}",
                "product_name": f"{fake.word().capitalize()} {cat.split()[0]} {fake.word().capitalize()}",
                "category": cat,
                "subcategory": fake.word().capitalize(),
                "brand": fake.company().split()[0],
                "unit_price": round(base_price, 2),
                "unit_cost": round(cost, 2),
                "margin_pct": round(params["margin"] * 100, 1),
                "weight_kg": round(np.random.exponential(0.8) + 0.1, 2),
                "is_active": np.random.choice([True, False], p=[0.92, 0.08]),
                "launch_date": fake.date_between(start_date="-5y", end_date="-1y"),
                "avg_rating": round(np.random.beta(8, 2) * 4 + 1, 1),
                "review_count": int(np.random.exponential(120) + 5),
            })
            pid += 1

    df = pd.DataFrame(products)
    logger.success(f"Products generated: {len(df):,} rows")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Transactions
# ──────────────────────────────────────────────────────────────────────────────
def generate_transactions(customers: pd.DataFrame, products: pd.DataFrame,
                          n: int = N_TRANSACTIONS) -> pd.DataFrame:
    logger.info(f"Generating {n:,} transactions...")

    active_products = products[products["is_active"]].copy()
    cat_weights = {cat: 1 / PRODUCT_CATEGORIES[cat]["avg_price"]
                   for cat in PRODUCT_CATEGORIES}

    # Assign transaction counts per customer weighted by segment
    seg_freq = {s: CUSTOMER_SEGMENTS_GEN[s]["freq_mult"] for s in CUSTOMER_SEGMENTS_GEN}
    cust_freq = customers["true_segment"].map(seg_freq).values
    cust_freq_norm = cust_freq / cust_freq.sum()
    cust_tx_counts = np.random.multinomial(n, cust_freq_norm)

    start_dt = pd.Timestamp(DATE_START)
    end_dt = pd.Timestamp(DATE_END)
    span_days = (end_dt - start_dt).days

    records = []
    order_id = 1
    for idx, cust_row in customers.iterrows():
        n_tx = cust_tx_counts[idx]
        if n_tx == 0:
            continue
        seg = cust_row["true_segment"]
        seg_params = CUSTOMER_SEGMENTS_GEN[seg]

        # Recency-weighted dates: recent customers cluster near end
        recency_bias = seg_params["recency_days"]
        for _ in range(n_tx):
            if np.random.random() < 0.6:
                days_ago = int(np.random.exponential(recency_bias))
            else:
                days_ago = np.random.randint(0, span_days)
            days_ago = min(days_ago, span_days)
            tx_date = end_dt - pd.Timedelta(days=days_ago)

            # Seasonal multiplier
            month = tx_date.month
            seasonality = 1.0 + 0.3 * np.sin((month - 3) * np.pi / 6)

            n_items = max(1, int(np.random.poisson(2.2 * seg_params["value_mult"])))
            n_items = min(n_items, 15)

            # Sample products
            prod_sample = active_products.sample(n=n_items, replace=True)

            for _, prod in prod_sample.iterrows():
                qty = max(1, int(np.random.poisson(1.4)))
                unit_price = prod["unit_price"] * (1 + np.random.normal(0, 0.05))
                discount = 0.0
                if np.random.random() < 0.25:
                    discount = np.random.choice([0.05, 0.10, 0.15, 0.20])
                final_price = unit_price * (1 - discount)

                records.append({
                    "order_id": f"ORD-{order_id:08d}",
                    "customer_id": cust_row["customer_id"],
                    "product_id": prod["product_id"],
                    "category": prod["category"],
                    "transaction_date": tx_date.date(),
                    "quantity": qty,
                    "unit_price": round(unit_price, 2),
                    "discount_pct": discount,
                    "final_price": round(final_price, 2),
                    "revenue": round(final_price * qty, 2),
                    "cogs": round(prod["unit_cost"] * qty, 2),
                    "gross_profit": round((final_price - prod["unit_cost"]) * qty, 2),
                    "payment_method": np.random.choice(
                        ["credit_card", "debit_card", "paypal", "apple_pay", "buy_now_pay_later"],
                        p=[0.42, 0.28, 0.15, 0.10, 0.05]
                    ),
                    "device_type": np.random.choice(
                        ["desktop", "mobile", "tablet"], p=[0.42, 0.48, 0.10]
                    ),
                    "is_returned": np.random.random() < 0.06,
                    "return_reason": None,
                    "seasonality_factor": round(seasonality, 3),
                })
            order_id += 1

    df = pd.DataFrame(records)

    # Flag returns with reasons
    return_reasons = ["wrong_size", "defective", "not_as_described", "changed_mind", "damaged_shipping"]
    mask = df["is_returned"]
    df.loc[mask, "return_reason"] = np.random.choice(return_reasons, size=mask.sum())
    df.loc[mask, "revenue"] = df.loc[mask, "revenue"] * -1

    logger.success(f"Transactions generated: {len(df):,} rows")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Web Sessions (for A/B testing)
# ──────────────────────────────────────────────────────────────────────────────
def generate_web_sessions(customers: pd.DataFrame, n_sessions: int = 400_000) -> pd.DataFrame:
    logger.info(f"Generating {n_sessions:,} web sessions...")

    cust_ids = customers["customer_id"].values
    n_anon = int(n_sessions * 0.35)
    n_known = n_sessions - n_anon

    PROPORTION_METRICS = {
        "conversion_rate", "click_through_rate", "open_rate",
        "recovery_rate", "engagement_rate",
    }

    sessions = []
    for exp_name, exp_cfg in AB_EXPERIMENTS.items():
        n_ctrl = exp_cfg["n_control"]
        n_trt  = exp_cfg["n_treatment"]
        baseline = exp_cfg["baseline"]
        lift     = exp_cfg["expected_lift"]
        is_prop  = exp_cfg["metric"] in PROPORTION_METRICS

        # ── Control group ──────────────────────────────────────────────────
        if is_prop:
            ctrl_conv_arr = np.random.binomial(1, float(baseline), n_ctrl)
        else:
            # Continuous metric: revenue / AOV / RPV
            ctrl_vals = np.maximum(0, np.random.normal(float(baseline), float(baseline) * 0.4, n_ctrl))
            ctrl_conv_arr = (ctrl_vals > 0).astype(int)

        for i in range(n_ctrl):
            converted = bool(ctrl_conv_arr[i])
            if is_prop:
                rev = round(max(0, np.random.normal(68, 28)), 2) if converted else 0.0
            else:
                rev = round(float(ctrl_vals[i]), 2)
            sessions.append({
                "session_id":        f"SES-{exp_name[:4].upper()}-C-{i:06d}",
                "experiment_name":   exp_name,
                "variant":           "control",
                "customer_id":       np.random.choice(cust_ids) if np.random.random() > 0.3 else None,
                "converted":         converted,
                "revenue":           rev,
                "time_on_site_sec":  int(np.random.exponential(240) + 30),
                "pages_viewed":      max(1, int(np.random.poisson(4.2))),
                "bounce":            bool(np.random.random() < 0.38),
                "device_type":       np.random.choice(["desktop", "mobile", "tablet"], p=[0.42, 0.48, 0.10]),
                "session_date":      fake.date_between(start_date="-60d", end_date="-1d"),
            })

        # ── Treatment group ────────────────────────────────────────────────
        if is_prop:
            trt_rate      = min(0.99, float(baseline) * (1 + lift))
            trt_conv_arr  = np.random.binomial(1, trt_rate, n_trt)
        else:
            trt_mean      = float(baseline) * (1 + lift)
            trt_vals      = np.maximum(0, np.random.normal(trt_mean, trt_mean * 0.4, n_trt))
            trt_conv_arr  = (trt_vals > 0).astype(int)

        for i in range(n_trt):
            converted = bool(trt_conv_arr[i])
            if is_prop:
                rev = round(max(0, np.random.normal(72, 28)), 2) if converted else 0.0
            else:
                rev = round(float(trt_vals[i]), 2)
            sessions.append({
                "session_id":        f"SES-{exp_name[:4].upper()}-T-{i:06d}",
                "experiment_name":   exp_name,
                "variant":           "treatment",
                "customer_id":       np.random.choice(cust_ids) if np.random.random() > 0.3 else None,
                "converted":         converted,
                "revenue":           rev,
                "time_on_site_sec":  int(np.random.exponential(280) + 35),
                "pages_viewed":      max(1, int(np.random.poisson(4.8))),
                "bounce":            bool(np.random.random() < 0.33),
                "device_type":       np.random.choice(["desktop", "mobile", "tablet"], p=[0.42, 0.48, 0.10]),
                "session_date":      fake.date_between(start_date="-60d", end_date="-1d"),
            })

    df = pd.DataFrame(sessions)
    logger.success(f"Web sessions generated: {len(df):,} rows")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    console.rule("[bold blue]E-Commerce Data Generation Pipeline")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), console=console) as progress:

        t1 = progress.add_task("Generating customers...", total=None)
        customers = generate_customers()
        customers.to_parquet(RAW_DIR / "customers.parquet", index=False)
        customers.to_csv(RAW_DIR / "customers.csv", index=False)
        progress.update(t1, completed=True, description="✅ Customers")

        t2 = progress.add_task("Generating products...", total=None)
        products = generate_products()
        products.to_parquet(RAW_DIR / "products.parquet", index=False)
        products.to_csv(RAW_DIR / "products.csv", index=False)
        progress.update(t2, completed=True, description="✅ Products")

        t3 = progress.add_task("Generating transactions...", total=None)
        transactions = generate_transactions(customers, products)
        transactions.to_parquet(RAW_DIR / "transactions.parquet", index=False)
        transactions.to_csv(RAW_DIR / "transactions.csv", index=False)
        progress.update(t3, completed=True, description="✅ Transactions")

        t4 = progress.add_task("Generating web sessions...", total=None)
        sessions = generate_web_sessions(customers)
        sessions.to_parquet(RAW_DIR / "web_sessions.parquet", index=False)
        sessions.to_csv(RAW_DIR / "web_sessions.csv", index=False)
        progress.update(t4, completed=True, description="✅ Web Sessions")

    console.print("\n[bold green]✅ Data generation complete!")
    console.print(f"  Customers:    {len(customers):>10,}")
    console.print(f"  Products:     {len(products):>10,}")
    console.print(f"  Transactions: {len(transactions):>10,}")
    console.print(f"  Web Sessions: {len(sessions):>10,}")
    console.print(f"\n  📁 Saved to: {RAW_DIR}")

    return customers, products, transactions, sessions


if __name__ == "__main__":
    main()
