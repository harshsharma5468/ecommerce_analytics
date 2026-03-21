"""
Data Pipeline Module
─────────────────────────────────────────────────────────────────────────────
"""

from .orchestrator import (
    run_pipeline,
    run_pipeline_fallback,
    generate_customers,
    generate_products,
    generate_transactions,
    clean_customers,
    clean_transactions,
    create_rfm_segmentation,
    create_segment_profiles
)

__all__ = [
    'run_pipeline',
    'run_pipeline_fallback',
    'generate_customers',
    'generate_products',
    'generate_transactions',
    'clean_customers',
    'clean_transactions',
    'create_rfm_segmentation',
    'create_segment_profiles'
]
