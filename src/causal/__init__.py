"""
Causal Inference Module
─────────────────────────────────────────────────────────────────────────────
"""

from .inference import (
    PropensityScoreMatcher,
    DifferenceInDifferences,
    SyntheticControl,
    InversePropensityWeighting
)

__all__ = [
    'PropensityScoreMatcher',
    'DifferenceInDifferences',
    'SyntheticControl',
    'InversePropensityWeighting'
]
