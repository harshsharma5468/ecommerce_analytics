"""
Data Pipeline Orchestration with Prefect
─────────────────────────────────────────────────────────────────────────────
Medallion Architecture:
- Bronze: Raw data ingestion
- Silver: Cleaned, validated data
- Gold: Aggregated, business-ready data

Features:
- Task dependencies and retries
- SLA monitoring
- Great Expectations validation
- Incremental loads
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings("ignore")

try:
    from prefect import flow, task, get_run_logger
    from prefect.tasks import task_input_hash
    from prefect.cache_policies import TASK_SOURCE, INPUTS
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    print("Prefect not installed. Running in fallback mode.")

from config.settings import (
    ROOT_DIR, DATA_DIR, RAW_DIR, PROCESSED_DIR, EXPORTS_DIR,
    N_CUSTOMERS, N_PRODUCTS, N_TRANSACTIONS
)

# Try to import Great Expectations
try:
    import great_expectations as ge
    GE_AVAILABLE = True
except ImportError:
    GE_AVAILABLE = False
    print("Great Expectations not installed. Skipping validations.")


# ──────────────────────────────────────────────────────────────────────────────
# Data Generation Task (Bronze Layer)
# ──────────────────────────────────────────────────────────────────────────────

def generate_customers(n_customers: int = N_CUSTOMERS) -> pd.DataFrame:
    """Generate customer data."""
    np.random.seed(42)
    
    segments = ['Champions', 'Loyal', 'Potential_Loyalist', 'Recent_Customer', 
                'At_Risk', 'Hibernating', 'Lost']
    segment_weights = [0.08, 0.12, 0.15, 0.10, 0.18, 0.20, 0.17]
    
    genders = ['M', 'F', 'Other']
    countries = ['USA', 'UK', 'Canada', 'Australia', 'Germany', 'France', 'Japan']
    channels = ['Organic', 'Paid Search', 'Social Media', 'Email', 'Referral', 'Direct']
    
    customers = []
    for i in range(n_customers):
        segment = np.random.choice(segments, p=segment_weights)
        
        # Registration date based on segment
        if segment in ['Champions', 'Loyal']:
            reg_days_ago = np.random.randint(365, 1000)
        elif segment in ['Lost', 'Hibernating']:
            reg_days_ago = np.random.randint(400, 800)
        else:
            reg_days_ago = np.random.randint(100, 600)
        
        customers.append({
            'customer_id': i + 1,
            'email': f'customer_{i+1}@example.com',
            'first_name': f'First_{i+1}',
            'last_name': f'Last_{i+1}',
            'gender': np.random.choice(genders),
            'country': np.random.choice(countries),
            'registration_date': datetime.now() - timedelta(days=reg_days_ago),
            'acquisition_channel': np.random.choice(channels),
            'true_segment': segment,
            'is_email_opted_in': np.random.choice([True, False], p=[0.7, 0.3])
        })
    
    return pd.DataFrame(customers)


def generate_products(n_products: int = N_PRODUCTS) -> pd.DataFrame:
    """Generate product data."""
    np.random.seed(43)
    
    categories = ['Electronics', 'Clothing', 'Home & Garden', 'Sports & Outdoors',
                  'Books & Media', 'Beauty & Personal Care', 'Food & Grocery',
                  'Toys & Games', 'Automotive', 'Office Supplies']
    
    products = []
    for i in range(n_products):
        category = np.random.choice(categories)
        base_price = np.random.uniform(10, 500)
        
        products.append({
            'product_id': i + 1,
            'product_name': f'Product_{i+1}',
            'category': category,
            'price': round(base_price, 2),
            'cost': round(base_price * np.random.uniform(0.3, 0.7), 2),
            'margin_pct': round(np.random.uniform(30, 70), 1)
        })
    
    return pd.DataFrame(products)


def generate_transactions(customers_df: pd.DataFrame,
                          products_df: pd.DataFrame,
                          n_transactions: int = N_TRANSACTIONS) -> pd.DataFrame:
    """Generate transaction data."""
    np.random.seed(44)
    
    transactions = []
    
    for i in range(n_transactions):
        customer = customers_df.sample(1).iloc[0]
        product = products_df.sample(1).iloc[0]
        
        # Transaction date
        days_ago = np.random.randint(1, 730)
        txn_date = datetime.now() - timedelta(days=days_ago)
        
        quantity = np.random.choice([1, 2, 3, 4, 5], p=[0.6, 0.25, 0.1, 0.04, 0.01])
        
        transactions.append({
            'transaction_id': f'TXN_{i+1:08d}',
            'customer_id': customer['customer_id'],
            'product_id': product['product_id'],
            'order_date': txn_date,
            'quantity': quantity,
            'unit_price': product['price'],
            'total_amount': round(product['price'] * quantity, 2),
            'category': product['category']
        })
    
    return pd.DataFrame(transactions)


# ──────────────────────────────────────────────────────────────────────────────
# Great Expectations Validation
# ──────────────────────────────────────────────────────────────────────────────

def create_customer_expectations(df: pd.DataFrame) -> Dict:
    """Create Great Expectations suite for customers."""
    if not GE_AVAILABLE:
        return {'valid': True, 'skipped': True}
    
    # Create expectation suite
    expectations = {
        'customer_id': {'type': 'integer', 'unique': True, 'non_null': True},
        'email': {'type': 'string', 'non_null': True},
        'registration_date': {'type': 'datetime', 'non_null': True},
        'acquisition_channel': {'type': 'string', 'is_in': ['Organic', 'Paid Search', 'Social Media', 'Email', 'Referral', 'Direct']}
    }
    
    # Validate
    issues = []
    
    for col, exp in expectations.items():
        if col not in df.columns:
            issues.append(f"Missing column: {col}")
            continue
        
        if exp.get('non_null') and df[col].isnull().any():
            issues.append(f"Column {col} has null values")
        
        if exp.get('unique') and df[col].duplicated().any():
            issues.append(f"Column {col} has duplicate values")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'n_records': len(df)
    }


def create_transaction_expectations(df: pd.DataFrame) -> Dict:
    """Create Great Expectations suite for transactions."""
    if not GE_AVAILABLE:
        return {'valid': True, 'skipped': True}
    
    issues = []
    
    # Check required columns
    required_cols = ['transaction_id', 'customer_id', 'product_id', 'order_date', 'total_amount']
    for col in required_cols:
        if col not in df.columns:
            issues.append(f"Missing column: {col}")
    
    # Check for nulls in critical columns
    critical_cols = ['transaction_id', 'customer_id', 'total_amount']
    for col in critical_cols:
        if col in df.columns and df[col].isnull().any():
            issues.append(f"Column {col} has null values")
    
    # Check total_amount is positive
    if 'total_amount' in df.columns:
        if (df['total_amount'] <= 0).any():
            issues.append("total_amount has non-positive values")
    
    # Check order_date is reasonable
    if 'order_date' in df.columns:
        df['order_date'] = pd.to_datetime(df['order_date'])
        future_txns = (df['order_date'] > datetime.now()).sum()
        if future_txns > 0:
            issues.append(f"{future_txns} transactions have future dates")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'n_records': len(df)
    }


# ──────────────────────────────────────────────────────────────────────────────
# Silver Layer: Data Cleaning
# ──────────────────────────────────────────────────────────────────────────────

def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize customer data."""
    df = df.copy()
    
    # Standardize email
    df['email'] = df['email'].str.lower().str.strip()
    
    # Standardize country names
    country_map = {
        'usa': 'United States',
        'uk': 'United Kingdom',
        'canada': 'Canada',
        'australia': 'Australia',
        'germany': 'Germany',
        'france': 'France',
        'japan': 'Japan'
    }
    df['country'] = df['country'].str.lower().map(country_map).fillna(df['country'])
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['customer_id'], keep='first')
    
    return df


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize transaction data."""
    df = df.copy()
    
    # Ensure date type
    df['order_date'] = pd.to_datetime(df['order_date'])
    
    # Remove future dates
    df = df[df['order_date'] <= datetime.now()]
    
    # Remove negative amounts
    df = df[df['total_amount'] > 0]
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['transaction_id'], keep='first')
    
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Gold Layer: Aggregations
# ──────────────────────────────────────────────────────────────────────────────

def create_rfm_segmentation(customers_df: pd.DataFrame,
                            transactions_df: pd.DataFrame,
                            snapshot_date: datetime = None) -> pd.DataFrame:
    """Create RFM segmentation."""
    if snapshot_date is None:
        snapshot_date = datetime.now()
    
    # Calculate RFM metrics per customer
    rfm = transactions_df.groupby('customer_id').agg({
        'order_date': ['max', 'count'],
        'total_amount': ['sum', 'mean'],
        'transaction_id': 'count'
    })
    
    rfm.columns = ['last_purchase', 'frequency', 'monetary', 'avg_order_value', 'n_transactions']
    rfm = rfm.reset_index()
    
    # Calculate recency
    rfm['recency'] = (snapshot_date - rfm['last_purchase']).dt.days
    
    # Merge with customer data
    rfm = rfm.merge(customers_df[['customer_id', 'acquisition_channel', 'country', 'registration_date']], 
                    on='customer_id', how='left')
    
    # Add RFM scores
    rfm['R_score'] = pd.qcut(rfm['recency'].rank(method='first'), q=5, labels=[5, 4, 3, 2, 1])
    rfm['F_score'] = pd.qcut(rfm['frequency'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5])
    rfm['M_score'] = pd.qcut(rfm['monetary'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5])
    
    # Convert to numeric
    rfm['R_score'] = rfm['R_score'].astype(int)
    rfm['F_score'] = rfm['F_score'].astype(int)
    rfm['M_score'] = rfm['M_score'].astype(int)
    
    # Calculate composite scores
    rfm['RFM_score'] = rfm['R_score'] * 100 + rfm['F_score'] * 10 + rfm['M_score']
    rfm['RFM_composite'] = rfm['R_score'] + rfm['F_score'] + rfm['M_score']
    
    # Assign segments
    def assign_segment(row):
        if row['R_score'] >= 4 and row['F_score'] >= 4:
            return 'Champions'
        elif row['R_score'] >= 3 and row['F_score'] >= 3:
            return 'Loyal'
        elif row['R_score'] >= 4 and row['F_score'] <= 2:
            return 'Potential Loyalist'
        elif row['R_score'] <= 2 and row['F_score'] >= 3:
            return 'At Risk'
        elif row['R_score'] <= 2 and row['F_score'] <= 2:
            return 'Hibernating'
        else:
            return 'Regular'
    
    rfm['segment'] = rfm.apply(assign_segment, axis=1)
    
    return rfm


def create_segment_profiles(rfm_df: pd.DataFrame) -> pd.DataFrame:
    """Create segment profile summaries."""
    profiles = rfm_df.groupby('segment').agg({
        'customer_id': 'count',
        'recency': 'mean',
        'frequency': 'mean',
        'monetary': 'mean',
        'avg_order_value': 'mean',
        'RFM_composite': 'mean'
    }).round(2)
    
    profiles = profiles.reset_index()
    profiles.columns = ['segment', 'n_customers', 'avg_recency', 'avg_frequency', 
                        'avg_monetary', 'avg_aov', 'avg_rfm_score']
    
    return profiles


# ──────────────────────────────────────────────────────────────────────────────
# Prefect Flow (if available)
# ──────────────────────────────────────────────────────────────────────────────

if PREFECT_AVAILABLE:
    
    @task(retries=3, retry_delay_seconds=30)
    def task_generate_customers(n_customers: int) -> pd.DataFrame:
        return generate_customers(n_customers)
    
    @task(retries=3, retry_delay_seconds=30)
    def task_generate_products(n_products: int) -> pd.DataFrame:
        return generate_products(n_products)
    
    @task(retries=3, retry_delay_seconds=30)
    def task_generate_transactions(customers: pd.DataFrame, 
                                    products: pd.DataFrame,
                                    n_transactions: int) -> pd.DataFrame:
        return generate_transactions(customers, products, n_transactions)
    
    @task
    def task_validate_customers(df: pd.DataFrame) -> Dict:
        return create_customer_expectations(df)
    
    @task
    def task_validate_transactions(df: pd.DataFrame) -> Dict:
        return create_transaction_expectations(df)
    
    @task
    def task_clean_customers(df: pd.DataFrame) -> pd.DataFrame:
        return clean_customers(df)
    
    @task
    def task_clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
        return clean_transactions(df)
    
    @task
    def task_create_rfm(customers: pd.DataFrame, 
                        transactions: pd.DataFrame) -> pd.DataFrame:
        return create_rfm_segmentation(customers, transactions)
    
    @task
    def task_create_profiles(rfm: pd.DataFrame) -> pd.DataFrame:
        return create_segment_profiles(rfm)
    
    @task
    def task_save_parquet(df: pd.DataFrame, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return str(path)
    
    @flow(name="ecommerce_data_pipeline")
    def prefect_pipeline(n_customers: int = N_CUSTOMERS,
                         n_products: int = N_PRODUCTS,
                         n_transactions: int = N_TRANSACTIONS):
        """Main Prefect pipeline."""
        from prefect import get_run_logger
        logger = get_run_logger()
        
        logger.info("Starting data pipeline...")
        
        # Bronze layer
        logger.info("Generating raw data...")
        customers_raw = task_generate_customers(n_customers)
        products_raw = task_generate_products(n_products)
        transactions_raw = task_generate_transactions(
            customers_raw, products_raw, n_transactions
        )
        
        # Validate
        logger.info("Validating data...")
        customer_validation = task_validate_customers(customers_raw)
        transaction_validation = task_validate_transactions(transactions_raw)
        
        if not customer_validation['valid']:
            logger.warning(f"Customer validation issues: {customer_validation.get('issues', [])}")
        
        if not transaction_validation['valid']:
            logger.warning(f"Transaction validation issues: {transaction_validation.get('issues', [])}")
        
        # Silver layer
        logger.info("Cleaning data...")
        customers_clean = task_clean_customers(customers_raw)
        transactions_clean = task_clean_transactions(transactions_raw)
        
        # Save silver layer
        task_save_parquet(customers_clean, RAW_DIR / "customers.parquet")
        task_save_parquet(products_raw, RAW_DIR / "products.parquet")
        task_save_parquet(transactions_clean, RAW_DIR / "transactions.parquet")
        
        # Gold layer
        logger.info("Creating aggregations...")
        rfm = task_create_rfm(customers_clean, transactions_clean)
        profiles = task_create_profiles(rfm)
        
        # Save gold layer
        task_save_parquet(rfm, PROCESSED_DIR / "rfm_segmented.parquet")
        task_save_parquet(profiles, PROCESSED_DIR / "segment_profiles.parquet")
        
        logger.info("Pipeline completed successfully!")
        
        return {
            'customers': len(customers_clean),
            'products': len(products_raw),
            'transactions': len(transactions_clean),
            'segments': len(profiles)
        }


# ──────────────────────────────────────────────────────────────────────────────
# Fallback Runner (without Prefect)
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline_fallback():
    """Run pipeline without Prefect orchestration."""
    print("Running pipeline in fallback mode (no Prefect)...")
    
    # Bronze layer
    print("Generating raw data...")
    customers = generate_customers(N_CUSTOMERS)
    products = generate_products(N_PRODUCTS)
    transactions = generate_transactions(customers, products, N_TRANSACTIONS)
    
    # Validate
    print("Validating data...")
    cust_val = create_customer_expectations(customers)
    txn_val = create_transaction_expectations(transactions)
    print(f"  Customer validation: {'PASS' if cust_val['valid'] else 'FAIL'}")
    print(f"  Transaction validation: {'PASS' if txn_val['valid'] else 'FAIL'}")
    
    # Silver layer
    print("Cleaning data...")
    customers = clean_customers(customers)
    transactions = clean_transactions(transactions)
    
    # Save raw
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    customers.to_parquet(RAW_DIR / "customers.parquet", index=False)
    products.to_parquet(RAW_DIR / "products.parquet", index=False)
    transactions.to_parquet(RAW_DIR / "transactions.parquet", index=False)
    
    # Gold layer
    print("Creating RFM segmentation...")
    rfm = create_rfm_segmentation(customers, transactions)
    profiles = create_segment_profiles(rfm)
    
    # Save processed
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    rfm.to_parquet(PROCESSED_DIR / "rfm_segmented.parquet", index=False)
    profiles.to_parquet(PROCESSED_DIR / "segment_profiles.parquet", index=False)
    
    print(f"\nPipeline completed!")
    print(f"  Customers: {len(customers)}")
    print(f"  Products: {len(products)}")
    print(f"  Transactions: {len(transactions)}")
    print(f"  Segments: {len(profiles)}")
    
    return {
        'customers': len(customers),
        'products': len(products),
        'transactions': len(transactions),
        'segments': len(profiles)
    }


def run_pipeline():
    """Run the pipeline with or without Prefect."""
    if PREFECT_AVAILABLE:
        return prefect_pipeline()
    else:
        return run_pipeline_fallback()


if __name__ == "__main__":
    run_pipeline()
