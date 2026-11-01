# Data dictionary

Generated from `schema_spec.py`. Types: STRING, INT, DECIMAL (USD, 2dp), DATE (ISO-8601), TIMESTAMP (UTC, `YYYY-MM-DD HH:MM:SS`), BOOL (0/1), ENUM, JSON.

## customer

Customer or prospect master record (pseudonymous; no personal data).

- **Primary key:** customer_id
- **Foreign keys:** none
- **Cardinality / relationships:** 1 customer : N orders, N events, N cases, N consents, N memberships, N outcomes

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| customer_id | STRING | Y | CUS-###### | Y | Y |  | regex ^CUS-\d{6}$; immutable; ordered by signup_date |
| customer_type | ENUM | Y | customer\|prospect | N | N |  | customer => >=1 order of any status; prospect => 0 orders |
| signup_date | DATE | Y | ISO-8601 date | N | N |  | <= 2026-09-30; <= first order date |
| region | ENUM | Y | North America\|Europe\|APAC\|LATAM\|MEA | N | N |  |  |
| age_band | ENUM | Y | 18-24\|25-34\|35-44\|45-54\|55+ | N | N |  |  |
| acquisition_channel | ENUM | Y | organic_search\|paid_social\|email_referral\|affiliate\|direct\|store | N | N |  |  |
| preferred_language | ENUM | Y | en\|es\|fr\|de | N | N |  |  |
| preferred_channel | ENUM | Y | email\|sms\|phone\|push\|none | N | N |  | must be a channel with a granted consent at signup, else 'none' |
| max_marketing_contacts_per_30d | INT | Y | 1..4 (contacts) | N | N |  | contact-frequency cap used by SUP-002 |
| lifecycle_state | ENUM | Y | prospect\|new\|active\|lapsing\|dormant | N | N |  | derived at lifecycle_as_of_date: prospect=no orders; new=first order<=60d; active=recency<=90d; lapsing=91-180d; dormant>180d |
| lifecycle_as_of_date | DATE | Y | ISO-8601 date | N | N |  | = 2026-10-01 (snapshot 2) |

## product

Product master with taxonomy (category > subcategory) and lifecycle.

- **Primary key:** product_id
- **Foreign keys:** none
- **Cardinality / relationships:** 1 product : N order_lines (order_line is the Order<->Product bridge, N:M)

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| product_id | STRING | Y | PRD-##### | Y | Y |  | regex ^PRD-\d{5}$ |
| sku | STRING | Y | SKU-<CAT3>-##### | Y | N |  |  |
| product_name | STRING | Y | text | N | N |  |  |
| category | STRING | Y | 8 top-level categories | N | N |  |  |
| subcategory | STRING | Y | text | N | N |  | belongs to category |
| brand | STRING | Y | text | N | N |  |  |
| list_price | DECIMAL | Y | USD > 0 | N | N |  | price effective for whole window; > unit_cost |
| unit_cost | DECIMAL | Y | USD > 0 | N | N |  | < list_price |
| launch_date | DATE | Y | ISO date | N | N |  | order lines may only reference products on/after launch_date |
| discontinued_date | DATE | N | ISO date | N | N |  | >= launch_date; order lines must be on/before this date |
| status | ENUM | Y | active\|discontinued | N | N |  | discontinued <=> discontinued_date not null |

## orders

Customer order header. All monetary values are derived from order_line.

- **Primary key:** order_id
- **Foreign keys:** customer_id -> customer.customer_id
- **Cardinality / relationships:** 1 order : 1..N order_lines

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| order_id | STRING | Y | ORD-2026-###### | Y | Y |  | regex ^ORD-2026-\d{6}$; sequential in order_ts order |
| customer_id | STRING | Y | FK customer | N | N | customer.customer_id | customer_type=customer |
| order_ts | TIMESTAMP | Y | YYYY-MM-DD HH:MM:SS | N | N |  | >= signup_date; 2025-01-01..2026-09-30 |
| channel | ENUM | Y | web\|app\|store\|phone | N | N |  |  |
| status | ENUM | Y | completed\|partially_returned\|returned\|cancelled | N | N |  | derived: cancelled \| returned (all qty returned) \| partially_returned \| completed (as of data end; history = line return_date / cancelled_ts) |
| currency | STRING | Y | USD | N | N |  |  |
| promo_pct | INT | Y | 0,10,15,20,30 (%) | N | N |  | order-level promo applied to every line |
| promo_code | STRING | N | SAVE<pct> or action_code | N | N |  | null iff promo_pct=0 |
| discount_total | DECIMAL | Y | USD >= 0 | N | N |  | = sum(order_line.discount_amount) |
| subtotal | DECIMAL | Y | USD > 0 | N | N |  | = sum(order_line.line_net_amount) |
| shipping_fee | DECIMAL | Y | USD | N | N |  | = 5.99 if subtotal < 75.00 else 0.00 |
| tax_amount | DECIMAL | Y | USD | N | N |  | = round(subtotal * 0.08, 2) |
| order_total | DECIMAL | Y | USD | N | N |  | = subtotal + shipping_fee + tax_amount |
| refund_total | DECIMAL | Y | USD >= 0 | N | N |  | = sum(order_line.refund_amount); merchandise only |
| net_merchandise_value | DECIMAL | Y | USD >= 0 | N | N |  | = subtotal - refund_total; 0 when cancelled (excluded from spend) |
| cancelled_ts | TIMESTAMP | N | timestamp | N | N |  | > order_ts; required iff status=cancelled |

## order_line

Order line = bridge between Order and Product; carries return events.

- **Primary key:** order_line_id
- **Foreign keys:** order_id -> orders.order_id; product_id -> product.product_id
- **Cardinality / relationships:** N lines : 1 order; N lines : 1 product

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| order_line_id | STRING | Y | ORL-2026-####### | Y | Y |  | regex ^ORL-2026-\d{7}$ |
| order_id | STRING | Y | FK orders | N | N | orders.order_id |  |
| line_number | INT | Y | 1..6 | N | N |  | (order_id,line_number) unique |
| product_id | STRING | Y | FK product | N | N | product.product_id | product active at order date |
| quantity | INT | Y | 1..3 units | N | N |  |  |
| unit_price | DECIMAL | Y | USD | N | N |  | = product.list_price |
| discount_amount | DECIMAL | Y | USD >= 0 | N | N |  | = round(qty*unit_price*promo_pct/100, 2) |
| line_net_amount | DECIMAL | Y | USD | N | N |  | = qty*unit_price - discount_amount |
| returned_quantity | INT | Y | 0..quantity | N | N |  |  |
| return_date | DATE | N | ISO date | N | N |  | required iff returned_quantity>0; order_date+3..30d; <= 2026-09-30 |
| return_reason | ENUM | N | size_fit\|defect\|not_as_described\|changed_mind | N | N |  | required iff returned_quantity>0 |
| refund_amount | DECIMAL | Y | USD >= 0 | N | N |  | = round(line_net_amount * returned_quantity / quantity, 2) |

## action_catalog

Catalogue of recommendable actions.

- **Primary key:** action_id
- **Foreign keys:** none
- **Cardinality / relationships:** 1 action : N outcomes

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| action_id | STRING | Y | ACTN-2026-###### | Y | Y |  |  |
| action_code | STRING | Y | text | Y | N |  |  |
| action_name | STRING | Y | text | N | N |  |  |
| purpose | ENUM | Y | marketing\|service | N | N |  | service actions do not need marketing consent |
| objective | STRING | Y | text | N | N |  |  |
| allowed_channels | STRING | Y | pipe-separated, preference order | N | N |  |  |
| requires_consent | BOOL | Y | 0/1 | N | N |  | 1 iff purpose = marketing |
| is_discount | BOOL | Y | 0/1 | N | N |  |  |
| discount_pct | INT | Y | 0..30 | N | N |  |  |
| unit_cost | DECIMAL | Y | USD per send/call | N | N |  |  |
| precondition | STRING | N | text | N | N |  |  |
| status | ENUM | Y | active | N | N |  |  |
| effective_from | DATE | Y | date | N | N |  |  |
| effective_to | DATE | N | date | N | N |  |  |

## engagement_event

Behavioural/marketing interaction events (web, app, email, sms, push, call).

- **Primary key:** event_id
- **Foreign keys:** customer_id -> customer.customer_id; product_id -> product.product_id; parent_event_id -> engagement_event.event_id; action_id -> action_catalog.action_id
- **Cardinality / relationships:** 1 event : 0..1 parent event

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| event_id | STRING | Y | EVT-2026-####### | Y | Y |  | regex ^EVT-2026-\d{7}$; sequential in event_ts order |
| customer_id | STRING | Y | FK customer | N | N | customer.customer_id |  |
| event_ts | TIMESTAMP | Y | YYYY-MM-DD HH:MM:SS | N | N |  | >= signup_date |
| event_type | ENUM | Y | web_visit\|product_view\|cart_add\|app_session\|email_sent\|email_open\|email_click\|sms_sent\|sms_click\|push_sent\|push_open\|call_attempt\|call_connected\|unsubscribe | N | N |  |  |
| channel | ENUM | Y | web\|app\|email\|sms\|push\|phone | N | N |  | consistent with event_type |
| product_id | STRING | N | FK product | N | N | product.product_id | only product_view/cart_add |
| parent_event_id | STRING | N | FK engagement_event | N | N | engagement_event.event_id | open/click/connected -> the *_sent/call_attempt event; click -> open; parent.event_ts < child.event_ts |
| action_id | STRING | N | FK action_catalog | N | N | action_catalog.action_id | set only on sends triggered by an action recommendation (and their opens/clicks) |

## support_case

Customer support case; current state (history in support_case_event).

- **Primary key:** case_id
- **Foreign keys:** customer_id -> customer.customer_id; order_id -> orders.order_id
- **Cardinality / relationships:** 1 customer : N cases; 1 order : 0..N cases

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| case_id | STRING | Y | CASE-2026-###### | Y | Y |  | regex |
| customer_id | STRING | Y | FK customer | N | N | customer.customer_id |  |
| order_id | STRING | N | FK orders | N | N | orders.order_id | if set, order belongs to same customer and order_ts < opened_ts |
| opened_ts | TIMESTAMP | Y | timestamp | N | N |  |  |
| closed_ts | TIMESTAMP | N | timestamp | N | N |  | > opened_ts; null iff status != closed |
| category | ENUM | Y | delivery_issue\|product_defect\|billing\|returns_refund\|how_to\|complaint\|account_access | N | N |  |  |
| priority | ENUM | Y | low\|normal\|high | N | N |  |  |
| channel | ENUM | Y | phone\|chat\|email | N | N |  |  |
| status | ENUM | Y | open\|escalated\|closed | N | N |  | lifecycle open -> [escalated] -> closed |
| escalated_flag | BOOL | Y | 0/1 | N | N |  |  |
| escalated_ts | TIMESTAMP | N | timestamp | N | N |  | opened_ts < escalated_ts; set iff escalated_flag=1 |
| handling_minutes | INT | N | minutes | N | N |  | known when closed |
| cost_amount | DECIMAL | N | USD | N | N |  | = handling_minutes*1.10 + 25.00*escalated_flag (closed cases only) |
| csat_score | INT | N | 1..5 | N | N |  | closed cases only (optional survey) |

## support_case_event

Append-only status history for support cases.

- **Primary key:** case_event_id
- **Foreign keys:** case_id -> support_case.case_id
- **Cardinality / relationships:** 1 case : 1..3 events

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| case_event_id | STRING | Y | CEV-2026-###### | Y | Y |  |  |
| case_id | STRING | Y | FK support_case | N | N | support_case.case_id |  |
| event_ts | TIMESTAMP | Y | timestamp | N | N |  |  |
| from_status | ENUM | N | open\|escalated\|closed | N | N |  | null for creation |
| to_status | ENUM | Y | open\|escalated\|closed | N | N |  | valid transitions: null>open, open>escalated, open>closed, escalated>closed |

## consent

Per-channel marketing consent as an append-only interval history.

- **Primary key:** consent_id
- **Foreign keys:** customer_id -> customer.customer_id; previous_consent_id -> consent.consent_id
- **Cardinality / relationships:** 1 customer : 0..N consent rows per channel

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| consent_id | STRING | Y | CON-2026-####### | Y | Y |  |  |
| customer_id | STRING | Y | FK customer | N | N | customer.customer_id |  |
| channel | ENUM | Y | email\|sms\|phone\|push | N | N |  |  |
| purpose | STRING | Y | marketing | N | N |  |  |
| status | ENUM | Y | granted\|withdrawn | N | N |  | per (customer,channel): granted -> withdrawn -> granted ... |
| effective_from | TIMESTAMP | Y | timestamp | N | N |  |  |
| effective_to | TIMESTAMP | N | timestamp | N | N |  | null = current; equals effective_from of the next row; intervals never overlap |
| source | ENUM | Y | signup_form\|app_prompt\|unsubscribe_link\|stop_reply\|preference_center\|support_agent | N | N |  |  |
| lawful_basis | STRING | Y | consent | N | N |  |  |
| previous_consent_id | STRING | N | FK consent | N | N | consent.consent_id | previous row in the (customer,channel) chain |

## segment_rule

Versioned segment definitions (rule-driven; params JSON is executable).

- **Primary key:** segment_id
- **Foreign keys:** superseded_by -> segment_rule.segment_id
- **Cardinality / relationships:** 1 rule : N memberships

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| segment_id | STRING | Y | SEG-2026-###### | Y | Y |  |  |
| segment_code | STRING | Y | text | N | N |  |  |
| segment_name | STRING | Y | text | N | N |  |  |
| exclusive_group | ENUM | Y | lifecycle\|overlay | N | N |  | lifecycle = mutually exclusive; overlay = additive |
| is_exclusive | BOOL | Y | 0/1 | N | N |  | 1 for lifecycle group |
| priority | INT | Y | lower wins within exclusive group | N | N |  |  |
| rule_version | INT | Y | >=1 | N | N |  |  |
| rule_params | JSON | Y | JSON object | N | N |  | executable conditions on customer_metric_snapshot |
| rule_expression | STRING | Y | text | N | N |  | human readable form of rule_params |
| status | ENUM | Y | active\|retired | N | N |  |  |
| effective_from | DATE | Y | date | N | N |  |  |
| effective_to | DATE | N | date | N | N |  |  |
| superseded_by | STRING | N | FK segment_rule | N | N | segment_rule.segment_id |  |

## customer_metric_snapshot

Derived RFM + service/engagement metrics per customer per snapshot date (evidence for memberships).

- **Primary key:** snapshot_date, customer_id
- **Foreign keys:** customer_id -> customer.customer_id
- **Cardinality / relationships:** 1 customer : 1 row per snapshot date

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| snapshot_date | DATE | Y | 2026-07-01 \| 2026-10-01 | N | Y |  | metrics use only data strictly before this date |
| customer_id | STRING | Y | FK customer | N | Y | customer.customer_id | signup_date < snapshot_date |
| n_orders | INT | Y | >=0 | N | N |  | non-cancelled orders before snapshot |
| first_order_date | DATE | N |  | N | N |  |  |
| last_order_date | DATE | N |  | N | N |  |  |
| recency_days | INT | N | days | N | N |  | = snapshot_date - last_order_date |
| first_order_age_days | INT | N | days | N | N |  | = snapshot_date - first_order_date |
| gross_merchandise | DECIMAL | Y | USD | N | N |  | = sum(line_net_amount) of non-cancelled orders |
| refund_total | DECIMAL | Y | USD | N | N |  | = sum(refund_amount) with return_date < snapshot_date |
| net_monetary | DECIMAL | Y | USD | N | N |  | = gross_merchandise - refund_total (returns netted) |
| return_rate | DECIMAL | Y | 0..1 | N | N |  | = refund_total / gross_merchandise |
| r_score | INT | N | 1..5 | N | N |  | see RFM bins |
| f_score | INT | N | 1..5 | N | N |  |  |
| m_score | INT | N | 1..5 | N | N |  | from net_monetary |
| opens_90d | INT | Y | >=0 | N | N |  | email_open events in the 90 days before snapshot |
| clicks_90d | INT | Y | >=0 | N | N |  | email_click events in the 90 days before snapshot |
| cases_12m | INT | Y | >=0 | N | N |  | cases opened in the 365 days before snapshot |
| service_cost_12m | DECIMAL | Y | USD | N | N |  | sum cost_amount of cases opened in last 365d and closed before snapshot |
| consent_withdrawals_90d | INT | Y | >=0 | N | N |  | withdrawn consent rows effective in the 90 days before snapshot |

## segment_membership

Effective-dated customer<->segment bridge (N:M). History retained: rows are closed, never overwritten.

- **Primary key:** membership_id
- **Foreign keys:** segment_id -> segment_rule.segment_id; customer_id -> customer.customer_id
- **Cardinality / relationships:** N customers : M segments; <=1 current lifecycle-group membership per customer

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| membership_id | STRING | Y | MEM-<segment-id>-<customer-id> | Y | Y |  | regex ^MEM-SEG-2026-\d{6}-CUS-\d{6}$ |
| segment_id | STRING | Y | FK segment_rule | N | N | segment_rule.segment_id |  |
| customer_id | STRING | Y | FK customer | N | N | customer.customer_id |  |
| effective_from | DATE | Y | date | N | N |  | segment rule must be effective on this date |
| effective_to | DATE | N | date | N | N |  | null = current; > effective_from |
| is_current | BOOL | Y | 0/1 | N | N |  | 1 iff effective_to is null |
| evaluated_snapshot_date | DATE | Y | date | N | N |  | FK (snapshot_date, customer_id) -> customer_metric_snapshot |
| explanation | STRING | Y | text | N | N |  | metric=value (condition) evidence for the rule |
| assigned_by | STRING | Y | rule_engine \| legacy_sync | N | N |  |  |

## action_segment_eligibility

Bridge: which actions may be recommended to which segments (N:M).

- **Primary key:** eligibility_id
- **Foreign keys:** action_id -> action_catalog.action_id; segment_id -> segment_rule.segment_id
- **Cardinality / relationships:** N actions : M segments

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| eligibility_id | STRING | Y | ELG-#### | Y | Y |  |  |
| action_id | STRING | Y | FK action_catalog | N | N | action_catalog.action_id |  |
| segment_id | STRING | Y | FK segment_rule | N | N | segment_rule.segment_id |  |
| priority | INT | Y | 1..9 | N | N |  | 1 = preferred |
| effective_from | DATE | Y | date | N | N |  |  |
| effective_to | DATE | N | date | N | N |  |  |

## suppression_rule

Documented contact suppression rules referenced by outcomes.

- **Primary key:** suppression_id
- **Foreign keys:** none
- **Cardinality / relationships:** 1 rule : N suppressed outcomes

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| suppression_id | STRING | Y | SUP-### | Y | Y |  |  |
| suppression_code | STRING | Y | text | Y | N |  |  |
| description | STRING | Y | text | N | N |  |  |
| evaluation_point | ENUM | Y | decision\|send | N | N |  |  |
| applies_to | STRING | Y | text | N | N |  |  |

## action_outcome

Recommendation log + subsequent outcome (one row per customer x recommended action).

- **Primary key:** outcome_id
- **Foreign keys:** customer_id -> customer.customer_id; action_id -> action_catalog.action_id; segment_id -> segment_rule.segment_id; membership_id -> segment_membership.membership_id; suppression_id -> suppression_rule.suppression_id; sent_event_id -> engagement_event.event_id; attributed_order_id -> orders.order_id
- **Cardinality / relationships:** 1 outcome : 1 customer, 1 action, 1 triggering segment

| field | type | req | allowed values / units | unique | PK | FK | validation rule |
|---|---|---|---|---|---|---|---|
| outcome_id | STRING | Y | OUT-2026-###### | Y | Y |  | ID convention extension (not in brief) |
| customer_id | STRING | Y | FK customer | N | N | customer.customer_id |  |
| action_id | STRING | Y | FK action_catalog | N | N | action_catalog.action_id | must be eligible for segment_id (bridge) |
| segment_id | STRING | Y | FK segment_rule | N | N | segment_rule.segment_id | segment that triggered the recommendation |
| membership_id | STRING | Y | FK segment_membership | N | N | segment_membership.membership_id | membership valid at recommended_at |
| slot | INT | Y | 1\|2 | N | N |  | max two recommendations per customer per run |
| recommended_at | TIMESTAMP | Y | timestamp | N | N |  | decision time = snapshot 2026-07-01 |
| decision | ENUM | Y | send\|suppress\|holdout | N | N |  |  |
| suppression_id | STRING | N | FK suppression_rule | N | N | suppression_rule.suppression_id | iff decision=suppress |
| experiment_group | ENUM | Y | treatment\|holdout\|none | N | N |  | holdout = random 10% of otherwise-sendable marketing recommendations |
| channel | ENUM | Y | email\|sms\|phone\|push | N | N |  | chosen (or intended) channel |
| consent_check | ENUM | Y | granted\|withdrawn\|never_granted\|not_required\|not_evaluated | N | N |  | result of consent evaluation at scheduled send time |
| scheduled_send_ts | TIMESTAMP | Y | timestamp | N | N |  | > recommended_at |
| sent_ts | TIMESTAMP | N | timestamp | N | N |  | iff decision=send |
| sent_event_id | STRING | N | FK engagement_event | N | N | engagement_event.event_id | iff decision=send |
| opened_ts | TIMESTAMP | N | timestamp | N | N |  |  |
| clicked_ts | TIMESTAMP | N | timestamp | N | N |  |  |
| attributed_order_id | STRING | N | FK orders | N | N | orders.order_id | earliest non-cancelled order of the customer within 14d after sent_ts for which this send is the last touch (holdout: within 14d after scheduled_send_ts) |
| attribution_window_days | INT | Y | 14 | N | N |  |  |
| converted_flag | BOOL | Y | 0/1 | N | N |  | 1 iff attributed_order_id not null |
| status | ENUM | Y | suppressed\|holdout\|sent\|opened\|clicked\|converted | N | N |  | furthest funnel stage reached; holdout/suppressed are terminal |
| revenue_attributed | DECIMAL | Y | USD | N | N |  | = orders.net_merchandise_value of attributed order, else 0 |
| action_cost | DECIMAL | Y | USD | N | N |  | = action.unit_cost if sent else 0 |
| discount_cost | DECIMAL | Y | USD | N | N |  | = orders.discount_total when attributed order used this action promo_code |

