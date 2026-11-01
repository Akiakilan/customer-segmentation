# Evaluation report (generated)

## A. Segment quality: do snapshot-1 (2026-07-01) segments predict the next 90 days?

| seg             |   customers |   pct_bought_next_90d |   orders_per_customer |   net_spend_per_customer |   share_of_customers |
|:----------------|------------:|----------------------:|----------------------:|-------------------------:|---------------------:|
| CHAMPIONS       |         289 |                 0.882 |                 2.696 |                  270.842 |                0.062 |
| LOYAL           |         911 |                 0.586 |                 1.076 |                   96.429 |                0.196 |
| AT_RISK         |         274 |                 0.398 |                 0.635 |                   56.57  |                0.059 |
| PROMISING       |         863 |                 0.363 |                 0.528 |                   48.186 |                0.186 |
| NEW             |         395 |                 0.372 |                 0.58  |                   45.901 |                0.085 |
| NEEDS_ATTENTION |         266 |                 0.32  |                 0.451 |                   34.029 |                0.057 |
| DORMANT         |        1244 |                 0.155 |                 0.191 |                   15.743 |                0.267 |
| PROSPECT        |         409 |                 0.024 |                 0.029 |                    1.394 |                0.088 |

Eta-squared (share of next-90-day spend variance explained by lifecycle segment): **0.262**

## B. Action performance (treatment vs random 10% holdout; 14-day last-touch attribution; gross margin 47.2%)

| action                   |   recommended |   suppressed |   holdout |   sent |   open_rate |   click_rate |   treated_conv |   holdout_conv |   abs_lift | lift_ci95         |      z |   incremental_orders |   incremental_net_revenue |   action_plus_discount_cost |    roi |
|:-------------------------|--------------:|-------------:|----------:|-------:|------------:|-------------:|---------------:|---------------:|-----------:|:------------------|-------:|---------------------:|--------------------------:|----------------------------:|-------:|
| CROSS_SELL_BUNDLE        |          1728 |          578 |       107 |   1043 |      0.3135 |       0.0527 |         0.1055 |         0.0654 |     0.04   | [-0.0104, 0.0905] |   1.56 |                 41.8 |                    478.43 |                       52.15 |   3.33 |
| FIRST_PURCHASE_INCENTIVE |           409 |           77 |        31 |    301 |      0.2658 |       0.0598 |         0.0199 |         0      |     0.0199 | [0.0041, 0.0357]  |   2.47 |                  6   |                    322.39 |                       51.56 |   1.95 |
| LOYALTY_BONUS_POINTS     |           911 |          258 |        63 |    590 |      0.3169 |       0.0763 |         0.1475 |         0.1429 |     0.0046 | [-0.0864, 0.0956] |   0.1  |                  2.7 |                   -416.12 |                       47.2  |  -5.16 |
| REENGAGEMENT_SURVEY      |          1510 |          291 |       112 |   1107 |      0.2981 |       0.0334 |         0.0361 |         0.0536 |    -0.0174 | [-0.0606, 0.0257] |  -0.79 |                -19.3 |                   1330.55 |                       55.35 |  10.36 |
| RETURN_PREVENTION_GUIDE  |           156 |           82 |         8 |     66 |      0.303  |       0.0455 |         0.1364 |         0.125  |     0.0114 | [-0.2323, 0.255]  |   0.09 |                  0.7 |                    637.12 |                        3.3  |  90.21 |
| SERVICE_RECOVERY_CALL    |            28 |            0 |         0 |     28 |      0.3929 |       0      |       nan      |       nan      |   nan      | nan               | nan    |                nan   |                    nan    |                      nan    | nan    |
| VIP_EARLY_ACCESS         |           289 |           86 |        26 |    177 |      0.3164 |       0.1073 |         0.3277 |         0.3077 |     0.02   | [-0.1704, 0.2104] |   0.21 |                  3.5 |                    208.86 |                        8.85 |  10.15 |
| WELCOME_SERIES           |           395 |           72 |        33 |    290 |      0.3414 |       0.0586 |         0.1241 |         0.0606 |     0.0635 | [-0.0263, 0.1534] |   1.39 |                 18.4 |                    520.46 |                       14.5  |  15.96 |
| WINBACK_DISCOUNT         |          1515 |          478 |       117 |    920 |      0.2511 |       0.0533 |         0.0522 |         0.0427 |     0.0094 | [-0.0299, 0.0488] |   0.47 |                  8.7 |                   -591.22 |                      216    |  -2.29 |

## C. Suppression & compliance

```json
{
 "suppression": {
  "NO_VALID_CONSENT": 1273,
  "PURCHASE_COOLDOWN": 301,
  "FREQUENCY_CAP": 293,
  "RETURNER_DISCOUNT_BLOCK": 53,
  "OPEN_COMPLAINT": 2
 },
 "funnel": {
  "recommendations": 6941,
  "suppressed": 1922,
  "holdout": 497,
  "sent": 4522,
  "opened": 1341,
  "clicked": 243,
  "converted_sent": 403
 },
 "compliance": {
  "marketing_sends": 4494,
  "consent_violations_injected_and_detected": 15,
  "consent_compliance_rate": 0.99666,
  "sends_blocked_for_missing_consent": 1273,
  "sends_blocked_by_frequency_cap": 293,
  "memberships_with_explanation_pct": 100.0
 }
}
```
