# Validation summary

**187 checks passed, 0 failed, 29 informational.**

## 1 primary keys

| status | check | detail |
|---|---|---|
| PASS | customer PK unique (customer_id) | duplicates=0 rows=5000 |
| PASS | customer PK not null | 0 |
| PASS | customer ID format ^CUS-\d{6}$ | bad=0 |
| PASS | product PK unique (product_id) | duplicates=0 rows=60 |
| PASS | product PK not null | 0 |
| PASS | product ID format ^PRD-\d{5}$ | bad=0 |
| PASS | orders PK unique (order_id) | duplicates=0 rows=20000 |
| PASS | orders PK not null | 0 |
| PASS | orders ID format ^ORD-2026-\d{6}$ | bad=0 |
| PASS | order_line PK unique (order_line_id) | duplicates=0 rows=41901 |
| PASS | order_line PK not null | 0 |
| PASS | order_line ID format ^ORL-2026-\d{7}$ | bad=0 |
| PASS | engagement_event PK unique (event_id) | duplicates=0 rows=100000 |
| PASS | engagement_event PK not null | 0 |
| PASS | engagement_event ID format ^EVT-2026-\d{7}$ | bad=0 |
| PASS | support_case PK unique (case_id) | duplicates=0 rows=3852 |
| PASS | support_case PK not null | 0 |
| PASS | support_case ID format ^CASE-2026-\d{6}$ | bad=0 |
| PASS | support_case_event PK unique (case_event_id) | duplicates=0 rows=8131 |
| PASS | support_case_event PK not null | 0 |
| PASS | support_case_event ID format ^CEV-2026-\d{6}$ | bad=0 |
| PASS | consent PK unique (consent_id) | duplicates=0 rows=9493 |
| PASS | consent PK not null | 0 |
| PASS | consent ID format ^CON-2026-\d{7}$ | bad=0 |
| PASS | segment_rule PK unique (segment_id) | duplicates=0 rows=13 |
| PASS | segment_rule PK not null | 0 |
| PASS | segment_rule ID format ^SEG-2026-\d{6}$ | bad=0 |
| PASS | customer_metric_snapshot PK unique (snapshot_date,customer_id) | duplicates=0 rows=9651 |
| PASS | customer_metric_snapshot PK not null | 0 |
| PASS | segment_membership PK unique (membership_id) | duplicates=0 rows=7853 |
| PASS | segment_membership PK not null | 0 |
| PASS | segment_membership ID format ^MEM-SEG-2026-\d{6}-CUS-\d{6}$ | bad=0 |
| PASS | action_catalog PK unique (action_id) | duplicates=0 rows=9 |
| PASS | action_catalog PK not null | 0 |
| PASS | action_catalog ID format ^ACTN-2026-\d{6}$ | bad=0 |
| PASS | action_segment_eligibility PK unique (eligibility_id) | duplicates=0 rows=13 |
| PASS | action_segment_eligibility PK not null | 0 |
| PASS | action_segment_eligibility ID format ^ELG-\d{4}$ | bad=0 |
| PASS | suppression_rule PK unique (suppression_id) | duplicates=0 rows=5 |
| PASS | suppression_rule PK not null | 0 |
| PASS | suppression_rule ID format ^SUP-\d{3}$ | bad=0 |
| PASS | action_outcome PK unique (outcome_id) | duplicates=0 rows=6941 |
| PASS | action_outcome PK not null | 0 |
| PASS | action_outcome ID format ^OUT-2026-\d{6}$ | bad=0 |
| PASS | customer required fields populated | {} |
| PASS | product required fields populated | {} |
| PASS | orders required fields populated | {} |
| PASS | order_line required fields populated | {} |
| PASS | engagement_event required fields populated | {} |
| PASS | support_case required fields populated | {} |
| PASS | support_case_event required fields populated | {} |
| PASS | consent required fields populated | {} |
| PASS | segment_rule required fields populated | {} |
| PASS | customer_metric_snapshot required fields populated | {} |
| PASS | segment_membership required fields populated | {} |
| PASS | action_catalog required fields populated | {} |
| PASS | action_segment_eligibility required fields populated | {} |
| PASS | suppression_rule required fields populated | {} |
| PASS | action_outcome required fields populated | {} |
| PASS | customer columns == data dictionary |  |
| PASS | product columns == data dictionary |  |
| PASS | orders columns == data dictionary |  |
| PASS | order_line columns == data dictionary |  |
| PASS | engagement_event columns == data dictionary |  |
| PASS | support_case columns == data dictionary |  |
| PASS | support_case_event columns == data dictionary |  |
| PASS | consent columns == data dictionary |  |
| PASS | segment_rule columns == data dictionary |  |
| PASS | customer_metric_snapshot columns == data dictionary |  |
| PASS | segment_membership columns == data dictionary |  |
| PASS | action_catalog columns == data dictionary |  |
| PASS | action_segment_eligibility columns == data dictionary |  |
| PASS | suppression_rule columns == data dictionary |  |
| PASS | action_outcome columns == data dictionary |  |
| PASS | orders counter gap-free & zero padded |  |
| PASS | engagement_event counter gap-free & zero padded |  |
| PASS | order_line counter gap-free & zero padded |  |
| PASS | customer counter gap-free & zero padded |  |
| PASS | support_case counter gap-free & zero padded |  |

## 10 coverage

| status | check | detail |
|---|---|---|
| INFO | new customers (lifecycle_state=new) | 313 |
| INFO | dormant customers | 1593 |
| INFO | prospects | 412 |
| INFO | orders with returns (partial/full) | 3555 |
| INFO | cancelled orders (failure path) | 410 |
| INFO | high-service-cost accounts (current) | 233 |
| INFO | consent withdrawals | 723 |
| INFO | consent re-grants after withdrawal | 69 |
| INFO | suppressed recommendations | 1922 |
| INFO | holdout recommendations | 497 |
| INFO | unresolved support cases at window end | 6 |
| INFO | escalated cases | 433 |
| INFO | segment changes between snapshots (closed memberships, lifecycle) | 2018 |
| INFO | boundary: customers at recency exactly 30/60/120/180 on 2026-10-01 | 53 |
| INFO | boundary: customers with first_order_age exactly 60 on 2026-10-01 | 0 |
| INFO | boundary: cap=1 customers with suppressed second recommendation | 293 |
| INFO | suppression reasons | {'SUP-001': 1273, 'SUP-004': 301, 'SUP-002': 293, 'SUP-005': 53, 'SUP-003': 2} |
| INFO | table row counts | {'customer': 5000, 'product': 60, 'orders': 20000, 'order_line': 41901, 'action_catalog': 9, 'engagement_event': 100000, 'support_case': 3852, 'support_case_event': 8131, 'consent': 9493, 'segment_rule': 13, 'customer_metric_snapshot': 9651, 'segment_membership': 7853, 'action_segment_eligibility':  |

## 2 foreign keys

| status | check | detail |
|---|---|---|
| PASS | orders.customer_id -> customer.customer_id | orphans=0 of 20000 |
| PASS | order_line.order_id -> orders.order_id | orphans=0 of 41901 |
| PASS | order_line.product_id -> product.product_id | orphans=0 of 41901 |
| PASS | engagement_event.customer_id -> customer.customer_id | orphans=0 of 100000 |
| PASS | engagement_event.product_id -> product.product_id | orphans=0 of 31939 |
| PASS | engagement_event.parent_event_id -> engagement_event.event_id | orphans=0 of 5817 |
| PASS | engagement_event.action_id -> action_catalog.action_id | orphans=0 of 6106 |
| PASS | support_case.customer_id -> customer.customer_id | orphans=0 of 3852 |
| PASS | support_case.order_id -> orders.order_id | orphans=0 of 2133 |
| PASS | support_case_event.case_id -> support_case.case_id | orphans=0 of 8131 |
| PASS | consent.customer_id -> customer.customer_id | orphans=0 of 9493 |
| PASS | consent.previous_consent_id -> consent.consent_id | orphans=0 of 792 |
| PASS | segment_rule.superseded_by -> segment_rule.segment_id | orphans=0 of 1 |
| PASS | customer_metric_snapshot.customer_id -> customer.customer_id | orphans=0 of 9651 |
| PASS | segment_membership.segment_id -> segment_rule.segment_id | orphans=0 of 7853 |
| PASS | segment_membership.customer_id -> customer.customer_id | orphans=0 of 7853 |
| PASS | action_segment_eligibility.action_id -> action_catalog.action_id | orphans=0 of 13 |
| PASS | action_segment_eligibility.segment_id -> segment_rule.segment_id | orphans=0 of 13 |
| PASS | action_outcome.customer_id -> customer.customer_id | orphans=0 of 6941 |
| PASS | action_outcome.action_id -> action_catalog.action_id | orphans=0 of 6941 |
| PASS | action_outcome.segment_id -> segment_rule.segment_id | orphans=0 of 6941 |
| PASS | action_outcome.membership_id -> segment_membership.membership_id | orphans=0 of 6941 |
| PASS | action_outcome.suppression_id -> suppression_rule.suppression_id | orphans=0 of 1922 |
| PASS | action_outcome.sent_event_id -> engagement_event.event_id | orphans=0 of 4522 |
| PASS | action_outcome.attributed_order_id -> orders.order_id | orphans=0 of 441 |
| PASS | segment_membership(evaluated_snapshot_date,customer_id) -> customer_metric_snapshot |  |
| PASS | order_line (order_id,line_number) unique |  |
| PASS | consent (customer,channel,effective_from) unique |  |
| PASS | membership (customer,segment,effective_from) unique |  |
| PASS | no exact-duplicate engagement events | 0 |

## 3 enums

| status | check | detail |
|---|---|---|
| PASS | all ENUM columns within allowed values (32 columns) | {} |

## 4 date ordering

| status | check | detail |
|---|---|---|
| PASS | order_ts >= customer.signup_date |  |
| PASS | order_ts inside 2025-01-01..2026-09-30 |  |
| PASS | orders only for customer_type=customer |  |
| PASS | every customer_type=customer has >=1 order |  |
| PASS | cancelled_ts > order_ts and set iff cancelled |  |
| PASS | return_date 3..30 days after order | n_returns=3902 |
| PASS | return_date <= 2026-09-30 |  |
| PASS | return_date/reason present iff returned_quantity>0 |  |
| PASS | order lines reference products active at order date |  |
| PASS | case closed_ts > opened_ts; null iff status != closed |  |
| PASS | case.order_id belongs to same customer and precedes case |  |
| PASS | engagement event_ts >= customer signup |  |
| PASS | child event after parent, same customer | children=5817 |
| PASS | parent event types follow funnel |  |
| PASS | event ids are time-ordered |  |
| PASS | order ids are time-ordered |  |

## 5 reconciliation

| status | check | detail |
|---|---|---|
| PASS | unit_price == product.list_price |  |
| PASS | discount_amount == round(qty*price*promo%) |  |
| PASS | line_net == qty*price - discount |  |
| PASS | refund == line_net * returned_qty / qty |  |
| PASS | order.subtotal == sum(line_net) | 1.1368683772161603e-13 |
| PASS | order.discount_total == sum(discount) |  |
| PASS | order.refund_total == sum(refund) |  |
| PASS | shipping rule (<$75 => $5.99) |  |
| PASS | tax == round(8% subtotal) |  |
| PASS | order_total == subtotal+shipping+tax |  |
| PASS | net_merchandise == subtotal - refunds (0 if cancelled) |  |
| PASS | order.status derived from lines |  |
| PASS | promo_code null iff promo_pct=0 |  |
| PASS | case cost == minutes*1.10 + 25*escalated |  |
| PASS | open cases carry no cost/minutes/csat |  |
| PASS | [2026-07-01] n_orders/gross/opens/cases/cost/withdrawals recomputed from source | n_orders mismatches=0 |
| INFO | [2026-07-01] metric rows where net_monetary/refund do not reconcile to returns | 0 customers |
| PASS | [2026-07-01] r_score follows documented bins |  |
| PASS | [2026-07-01] m_score follows documented bins (from stored net_monetary) |  |
| PASS | [2026-07-01] net_monetary == gross - refund in stored row |  |
| PASS | [2026-10-01] n_orders/gross/opens/cases/cost/withdrawals recomputed from source | n_orders mismatches=0 |
| INFO | [2026-10-01] metric rows where net_monetary/refund do not reconcile to returns | 15 customers |
| PASS | [2026-10-01] r_score follows documented bins |  |
| PASS | [2026-10-01] m_score follows documented bins (from stored net_monetary) |  |
| PASS | [2026-10-01] net_monetary == gross - refund in stored row |  |
| PASS | customer.lifecycle_state derived from source records |  |

## 6 lifecycle

| status | check | detail |
|---|---|---|
| PASS | consent chains start granted and alternate granted/withdrawn |  |
| PASS | consent intervals contiguous, non-overlapping; effective_to == next effective_from |  |
| PASS | consent.previous_consent_id points to previous row in chain |  |
| INFO | consent withdrawals / customers with a withdrawal | 723 rows / 509 customers |
| PASS | support case transitions valid |  |
| PASS | support_case.status == last case event |  |
| PASS | case event timestamps agree with case row (open/escalated/closed) |  |
| PASS | membership is_current iff effective_to null; effective_to > effective_from |  |
| PASS | segment rule effective on membership effective_from; retired rules unused |  |
| INFO | customers with >1 current membership in exclusive lifecycle group (DETECTED) | 12 |
| INFO | overlapping exclusive-group memberships over time (rows involved) | 24 |
| PASS | membership history retained: closed rows exist (not overwritten) | closed rows=2186 |

## 7 segments

| status | check | detail |
|---|---|---|
| PASS | [2026-07-01] rule-engine memberships == re-evaluated rules on stored metrics | expected=5199 got=5199 missing=0 extra=0 |
| PASS | [2026-10-01] rule-engine memberships == re-evaluated rules on stored metrics | expected=5655 got=5655 missing=0 extra=0 |
| PASS | every membership has a non-empty explanation |  |
| PASS | rule-engine explanations cite the rule code |  |
| PASS | every customer in snapshot has exactly one lifecycle segment (rule_engine rows) |  |
| INFO | current segment sizes | {'DORMANT': 1380, 'LOYAL': 990, 'PROMISING': 707, 'PROSPECT': 438, 'AT_RISK': 414, 'NEEDS_ATTENTION': 385, 'CHAMPIONS': 382, 'NEW': 316, 'HIGH_SERVICE_COST': 233, 'HIGH_RETURNER': 212, 'CONSENT_WITHDRAWN': 155, 'EMAIL_ENGAGED': 55} |

## 8 contact constraints

| status | check | detail |
|---|---|---|
| INFO | marketing sends without consent at sent_ts (DETECTED) | 15 |
| INFO | sent events without consent (DETECTED, event level) | 15 |
| PASS | frequency cap respected (sends in rolling 30d <= cap) | violations=0 |
| PASS | service actions exempt from marketing consent; marketing actions carry consent_check |  |
| PASS | suppressed rows have suppression_id and no send; sent rows have send fields |  |
| PASS | scheduled_send_ts after recommended_at |  |
| INFO | outcomes whose action is not eligible for segment (bridge) (DETECTED) | 9 |
| PASS | outcome.membership matches customer+segment and was valid at decision date |  |
| PASS | SUP-003: no marketing send to customers with unresolved complaint at decision time | 0 |
| PASS | SUP-004: no non-welcome marketing send within 7d of last order |  |
| PASS | SUP-005: no discount send to HIGH_RETURNER overlay |  |
| INFO | holdout share of otherwise-sendable marketing | 0.100 |
| PASS | sent_event exists, same customer/timestamp |  |
| INFO | outcome.action_id differs from its sent event action_id (DETECTED) | 10 |
| PASS | attribution re-derivation (last touch, 14d) matches stored attributed_order_id | mismatch=0 of 4522 |
| PASS | converted_flag == attributed_order_id not null; status consistent |  |
| PASS | attributed order within window after sent_ts |  |
| PASS | revenue_attributed == order net_merchandise_value |  |

## 9 ground truth

| status | check | detail |
|---|---|---|
| PASS | conflicting_exclusive_segments: detection vs ground truth (precision=1.000 recall=1.000) | injected=12 TP=12 FP=0 FN=0 |
| PASS | action_violates_consent: detected sent events == injected (precision/recall 1.0) | injected=15 detected=15 |
| PASS | action_violates_consent: detected via outcome table == injected outcomes | detected=15 |
| PASS | return_not_netted: detection vs ground truth (precision=1.000 recall=1.000) | injected=15 TP=15 FP=0 FN=0 |
| PASS | outcome_wrong_action: detection vs ground truth (precision=1.000 recall=1.000) | injected=10 TP=10 FP=0 FN=0 |
| PASS | wrong-action rows also violate eligibility bridge (secondary signal) |  |
| PASS | no unlabelled exclusive-segment conflicts |  |
| PASS | no ground-truth / generator-latent columns in input tables | [] |
| PASS | ground truth entity_ids exist in inputs |  |
| PASS | ground truth lives in separate files |  |

