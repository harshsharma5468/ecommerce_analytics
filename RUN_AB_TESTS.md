# A/B Testing Engine - Run Commands

## Quick Start - Run Tests Locally
```bash
cd E:\ecommerce_analytics\src\ab_testing
python ab_engine.py
```

## Run with Docker Compose

### Option 1: Build and Run (Recommended)
```bash
docker compose run --profile ab-test ab-engine
```

### Option 2: Build Image First
```bash
docker compose build ab-engine
docker compose run --profile ab-test ab-engine
```

## Output Files

All results are saved to: `E:\ecommerce_analytics\data\processed\`

- **ab_test_results.csv** - Detailed CSV export
- **ab_test_results.json** - JSON format for database ingestion
- **ab_test_results.parquet** - Parquet binary format (fast)
- **figures/ab_results.png** - Results comparison chart
- **figures/forest_plot.png** - Forest plot of lifts
- **figures/power_analysis.png** - Power analysis curves

## Results Summary (Latest Run)

### Experiments Run: 8

#### RECOMMENDED TO SHIP (6):
1. **checkout_redesign** - +22.92% lift (p=0.0022)
2. **email_personalization** - +33.33% lift (p=0.0011)
3. **free_shipping_threshold** - +7.92% lift (p<0.0001)
4. **product_recommendation_algo** - +14.43% lift (p<0.0001)
5. **push_notification_timing** - +10.34% lift (p<0.0001)
6. **cart_abandonment_email** - +39.51% lift (p<0.0001)

#### NO EFFECT (2):
- **price_discount_5pct** - +3.79% lift (p=0.4949) - Not significant
- **homepage_hero_banner** - +1.46% lift (p=0.7108) - Not significant

## Statistical Method

- **Multiple Comparison Correction**: FDR (Benjamini-Hochberg)
- **Significance Level (α)**: 0.05
- **Power (1-β)**: 0.80
- **MDE (Minimum Detectable Effect)**: 5%

## Key Metrics

| Experiment | Metric Type | Control Mean | Treatment Mean | Lift | P-Value | Power |
|---|---|---|---|---|---|---|
| checkout_redesign | proportion | 3.20% | 3.93% | +22.92% | 0.0022 | 86.6% |
| email_personalization | proportion | 2.70% | 3.60% | +33.33% | 0.0011 | 90.4% |
| price_discount_5pct | proportion | 4.23% | 4.39% | +3.79% | 0.4949 | 10.5% |
| free_shipping_threshold | continuous | $68.57 | $74.00 | +7.92% | <0.0001 | 100% |
| product_recommendation_algo | continuous | $12.43 | $14.22 | +14.43% | <0.0001 | 100% |
| push_notification_timing | proportion | 22.25% | 24.55% | +10.34% | <0.0001 | 99.97% |
| cart_abandonment_email | proportion | 8.10% | 11.30% | +39.51% | <0.0001 | 99.97% |
| homepage_hero_banner | proportion | 4.92% | 5.00% | +1.46% | 0.7108 | 6.6% |

## Docker Usage Example

Run all A/B tests in a container with full environment:
```bash
cd E:\ecommerce_analytics
docker compose --profile ab-test up ab-engine
```

View container logs:
```bash
docker compose logs ab-engine
```

Stop container:
```bash
docker compose down
```
