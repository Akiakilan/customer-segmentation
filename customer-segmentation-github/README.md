# Explainable Customer Segmentation → Next-Best-Action: synthetic dataset + toolkit

100 % synthetic (no external data, no personal data). One generator builds both the **starter** (5k customers / 20k orders / 100k events) and the **full** (50k / 200k / 1M) datasets; only the scale parameters differ.

| | |
|---|---|
| Seed | `20261022` |
| Data window | 2025-01-01 … 2026-09-30 |
| Snapshot 1 | 2026-07-01 – segments evaluated, actions recommended/sent; outcomes observed over the following 90 days |
| Snapshot 2 | 2026-10-01 – current segments (end of window) |
| Validation | **187 checks pass / 0 fail** on both datasets (`validation_summary.md`) |
| Reproducibility | 2 independent regenerations are byte-identical (SHA-256 of every CSV) – `reproducibility_report.json` |


## Repository layout

- `src/` — generator, independent validator, evaluation script, reproducibility utility, and schema specification.
- `starter/` — compact 5k-customer CSV fixture, schema, ground truth, and generated reports (for a quick first run).
- `tests/` — smoke tests for validation and evaluation against the starter fixture.
- `requirements.txt` — Python dependencies.

The full 50k-customer dataset is intentionally **not committed**. Re-create it with the generator command below. Generated output folders are ignored by Git.

## Setup (Windows / VS Code)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\validate_data.py --dir starter
.\.venv\Scripts\python.exe src\evaluate_actions.py --dir starter
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If PowerShell blocks activation scripts, use the explicit `.venv\Scripts\python.exe` commands above; activation is not required.

## Run it
```bash
python -m pip install -r requirements.txt
# full dataset (≈75 s incl. SQLite + SQL seed; add --no-db --no-json for CSV only)
python src/generate_data.py --seed 20261022 --n-customers 50000 --n-orders 200000 --n-events 1000000 --out output
# starter dataset – same generator, smaller scale
python src/generate_data.py --seed 20261022 --n-customers 5000 --n-orders 20000 --n-events 100000 --out output_starter
python src/validate_data.py   --dir output          # independent re-derivation + ground-truth scoring
python src/evaluate_actions.py --dir output         # segment quality, funnel, holdout lift, ROI, compliance
python src/reproduce.py output                      # regenerate twice, compare row counts + SHA-256
```
Source files live in `src/`: `schema_spec.py` (single source of truth: schema, segment rules, action catalogue, suppression rules → data dictionary + DDL), `generate_data.py`, `validate_data.py`, `evaluate_actions.py`, `reproduce.py`.

## Output layout (per dataset)
`data/*.csv` (15 tables) · `json/*.json` (tables ≤120k rows) · `sql/schema.sql`→`schema/schema.sql`, `sql/seed.sql.gz` (full DDL+INSERT dump; foreign-key check = 0 violations) · `schema/data_dictionary.{md,csv,json}` · `ground_truth/` (**separate**) · `source_manifest.json` (parameters, command, seed, rows, SHA-256, provenance) · `validation_summary.{md,json}` · `evaluation_report.{md,json}` · `reproducibility_report.json`.

## Entities, keys, relationships (full detail in `schema/data_dictionary.md`)
| Entity | PK | Foreign keys | Cardinality / notes |
|---|---|---|---|
| Customer | customer_id `CUS-000001` | – | 1:N to everything below; `customer_type` derived from order history; contact cap + preferred channel |
| Product | product_id `PRD-00001` | – | 8 categories > 22 subcategories; launch/discontinue dates enforced on lines |
| Order | order_id `ORD-2026-000001` | customer_id | 1 customer : N orders; status derived (completed / partially_returned / returned / cancelled) |
| OrderLine | order_line_id `ORL-2026-0000001` | order_id, product_id | **bridge Order N:M Product**; carries return events (return_date, reason, refund) |
| EngagementEvent | event_id `EVT-2026-0000001` | customer_id, product_id?, parent_event_id?, action_id? | sent→open→click funnels via parent_event_id |
| SupportCase (+ `support_case_event` history) | case_id `CASE-2026-000001` | customer_id, order_id? | status history is append-only (open→escalated→closed) |
| Consent | consent_id `CON-2026-0000001` | customer_id, previous_consent_id? | per-channel effective-dated chain granted→withdrawn→granted; never overwritten |
| SegmentRule | segment_id `SEG-2026-000001` | superseded_by? | versioned, executable `rule_params` JSON, effective dates, retired v1 of DORMANT kept |
| CustomerMetricSnapshot | (snapshot_date, customer_id) | customer_id | RFM + service + engagement evidence, derived from source |
| SegmentMembership | membership_id `MEM-<segment-id>-<customer-id>` | segment_id, customer_id, (snapshot,customer)→metrics | **bridge Customer N:M Segment**, effective_from/to, `is_current`, `explanation` text |
| ActionCatalog | action_id `ACTN-2026-000001` | – | 9 actions; bridge `action_segment_eligibility` (Action N:M Segment) |
| SuppressionRule | suppression_id `SUP-001` | – | 5 documented rules |
| ActionOutcome | outcome_id `OUT-2026-000001`* | customer, action, segment, membership, suppression?, sent_event?, attributed_order? | recommendation log + outcome lifecycle |

\*The brief lists `ACTN-2026-000001` without saying which entity owns it; I used it for the **ActionCatalog** key and added `OUT-2026-…`, `ORL-`, `EVT-`, `CASE-`, `CEV-`, `CON-`, `PRD-`, `SUP-`, `ELG-` for the rest (same zero-padded, immutable convention). Easy to swap in `schema_spec.py`.

## Business logic (all documented, deterministic, rule-driven)
* **Generation order**: customers, products, consent → pre-snapshot orders/lines/events/cases → snapshot-1 metrics & segments → action engine (recommend, suppress, send, respond) → post-snapshot orders (organic + action-induced), events, cases → attribution → snapshot-2 metrics & segments.
* **Derived, never independent**: order totals/refunds/status from lines; RFM metrics from orders+lines; segments from stored metrics via the rule JSON; lifecycle_state from metrics; case cost from minutes; outcomes from a response model whose induced orders are real orders in the order table; attribution recomputed from orders.
* **RFM bins** (`schema/business_rule_constants.json`): R ≤30/60/120/240 d → 5..1; F ≥10/6/4/2/1 → 5..1; M (net of returns) ≥$1500/800/400/150 → 5..1.
* **Exclusive lifecycle segments (first match wins)**: PROSPECT (no orders) → NEW (first order ≤60 d) → CHAMPIONS (R,F,M ≥4) → LOYAL (R≥3,F≥3) → AT_RISK (R≤2,F≥3) → DORMANT (>180 d, v2 effective 2026-07-01) → PROMISING (R≥3) → NEEDS_ATTENTION (catch-all). **Overlays** (non-exclusive): HIGH_SERVICE_COST (≥4 cases/12 m or ≥$120 service cost), HIGH_RETURNER (return rate ≥30 %, ≥3 orders), CONSENT_WITHDRAWN (90 d), EMAIL_ENGAGED (≥3 opens/90 d).
* **Every membership carries an explanation**, e.g. `rule AT_RISK v1: r_score=2 (<= 2); f_score=3 (>= 3)`.
* **Actions**: max 2 per customer (priority from the eligibility bridge). Suppression: SUP-001 no consent for any allowed channel at send time · SUP-002 frequency cap (customer cap 1–4 per 30 d) · SUP-003 unresolved complaint/escalation · SUP-004 7-day post-purchase quiet period · SUP-005 discount blocked for high returners. Service action (agent call) is exempt from marketing consent. 10 % random **holdout** of otherwise-sendable marketing recommendations gives a causal lift baseline.
* **Attribution**: last-touch among sent actions, 14-day window, earliest order credited; holdout rows use organic orders in the same window.
* **Realism**: seasonality (Nov–Dec peak, weekend/weekday), heavy-tailed order frequency (median 3, max 69), AOV ≈ $100, ≈8 % line return rate with category-specific rates and a "serial returner" flag, 2.2 % cancellations, zipf product popularity, consent withdrawal + re-grant, unsubscribe events caused by withdrawals, open/click funnels, high-service customers with escalations.

## Injected edge cases + ground truth (`ground_truth/`)
Baseline rows are generated valid first; four labelled anomaly types are then injected into only the targeted rows (never silently into others):

| issue_type | count (full) | what is wrong | how the validator detects it |
|---|---|---|---|
| conflicting_exclusive_segments | 120 | extra current `legacy_sync` membership in a second lifecycle segment | >1 current membership per exclusive group |
| action_violates_consent | 150 | consent-suppressed recommendation flipped to *sent*; log falsely says `granted` | consent intervals at send timestamp |
| return_not_netted | 150 | snapshot-2 metric row uses gross spend (refund = 0); memberships follow the wrong metric | recompute from order_line returns |
| outcome_wrong_action | 100 | outcome.action_id ≠ the action actually sent | compare with sent event; eligibility bridge; attribution |

`ground_truth.csv` (520 rows, with expected vs observed), `ground_truth_customer_labels.csv` (generator archetype/flags + the *true* expected segments), `ground_truth.json`. Validator precision and recall for all four types = **1.0**; a leakage check asserts no ground-truth/latent columns exist in input tables.

## Results (full dataset)
* **Segments are predictive** (next 90 days after snapshot 1): % buying – Champions 88.7 %, Loyal 60.3 %, New 41.1 %, At risk 39.6 %, Promising 38.4 %, Needs attention 28.8 %, Dormant 14.6 %, Prospect 2.2 %; net spend per customer $258 → $2; segment explains 25.5 % of spend variance (η²).
* **Actions** (69.6k recommendations: 17.1k suppressed, 5.3k holdout, 47.2k sent): strongest holdout lift for VIP early access (+7.9 pp, 36 % vs 28 %) and loyalty bonus (+3.8 pp, p<0.01), win-back +1.8 pp (significant but costs discounts), re-engagement +1.6 pp, first purchase +1.4 pp (z=6.4); cross-sell/welcome/returns guide not significant at this n. Full table with CIs, incremental revenue and ROI in `evaluation_report.md`.
* **Contact constraints**: 0 frequency-cap violations; 0 SUP-003/004/005 breaches; the 150 consent breaches are exactly the injected ones (rate 0.32 % of marketing sends).
* **Coverage** (validation §10): new/dormant/prospect customers, returns (31k orders), cancellations (4.3k), consent withdrawals (7.2k) and re-grants (533), escalated cases (4.3k), unresolved cases at window end, 5 suppression reasons all firing, boundary cases (594 customers at recency exactly 30/60/120/180; first-order-age = 60).

## Validation suite (ten groups, 187 checks)
PK uniqueness/format/gap-free counters · FK integrity (incl. composite FK, 0 SQLite FK violations) · enums from dictionary · date ordering (signup ≤ order ≤ return ≤ window end, parent-before-child events, case order links, product active at order date) · arithmetic reconciliation (lines → orders → metrics, recomputed independently from raw records) · lifecycle transitions (consent chains, case history, membership history/overlap) · segment membership == rules re-evaluated on stored metrics · contact constraints and suppression rules · attribution re-derivation · ground-truth scoring and leakage.

## Assumptions / limitations
* Only two snapshots, so memberships have at most one transition; actions run once (2 slots, 8–21 days apart).
* Suppression SUP-003/004/005 are evaluated at decision time (2026-07-01), consent and frequency cap at scheduled send time.
* Product prices are constant over the window; currency USD; tax/shipping are simple documented rules.
* Order `status` is the as-of-extract state; its history is retained via `cancelled_ts` and line `return_date`.
* Engagement events for web/app are not consent-gated (essential analytics); email/SMS/push sends are.
* Public data not used. If added later, record URL, version, retrieval date, licence, attribution, transformations and dropped fields in `source_manifest.json` (`sources` is empty by design).
