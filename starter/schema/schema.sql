-- generated from schema_spec.py (SQLite dialect; portable to Postgres with minor type changes)

CREATE TABLE customer (
  customer_id TEXT NOT NULL,
  customer_type TEXT NOT NULL,
  signup_date TEXT NOT NULL,
  region TEXT NOT NULL,
  age_band TEXT NOT NULL,
  acquisition_channel TEXT NOT NULL,
  preferred_language TEXT NOT NULL,
  preferred_channel TEXT NOT NULL,
  max_marketing_contacts_per_30d INTEGER NOT NULL,
  lifecycle_state TEXT NOT NULL,
  lifecycle_as_of_date TEXT NOT NULL,
  PRIMARY KEY (customer_id)
);

CREATE TABLE product (
  product_id TEXT NOT NULL,
  sku TEXT NOT NULL,
  product_name TEXT NOT NULL,
  category TEXT NOT NULL,
  subcategory TEXT NOT NULL,
  brand TEXT NOT NULL,
  list_price REAL NOT NULL,
  unit_cost REAL NOT NULL,
  launch_date TEXT NOT NULL,
  discontinued_date TEXT,
  status TEXT NOT NULL,
  PRIMARY KEY (product_id)
);

CREATE TABLE orders (
  order_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  order_ts TEXT NOT NULL,
  channel TEXT NOT NULL,
  status TEXT NOT NULL,
  currency TEXT NOT NULL,
  promo_pct INTEGER NOT NULL,
  promo_code TEXT,
  discount_total REAL NOT NULL,
  subtotal REAL NOT NULL,
  shipping_fee REAL NOT NULL,
  tax_amount REAL NOT NULL,
  order_total REAL NOT NULL,
  refund_total REAL NOT NULL,
  net_merchandise_value REAL NOT NULL,
  cancelled_ts TEXT,
  PRIMARY KEY (order_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

CREATE TABLE order_line (
  order_line_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  line_number INTEGER NOT NULL,
  product_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price REAL NOT NULL,
  discount_amount REAL NOT NULL,
  line_net_amount REAL NOT NULL,
  returned_quantity INTEGER NOT NULL,
  return_date TEXT,
  return_reason TEXT,
  refund_amount REAL NOT NULL,
  PRIMARY KEY (order_line_id),
  FOREIGN KEY (order_id) REFERENCES orders(order_id),
  FOREIGN KEY (product_id) REFERENCES product(product_id)
);

CREATE TABLE action_catalog (
  action_id TEXT NOT NULL,
  action_code TEXT NOT NULL,
  action_name TEXT NOT NULL,
  purpose TEXT NOT NULL,
  objective TEXT NOT NULL,
  allowed_channels TEXT NOT NULL,
  requires_consent INTEGER NOT NULL,
  is_discount INTEGER NOT NULL,
  discount_pct INTEGER NOT NULL,
  unit_cost REAL NOT NULL,
  precondition TEXT,
  status TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  PRIMARY KEY (action_id)
);

CREATE TABLE engagement_event (
  event_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  event_type TEXT NOT NULL,
  channel TEXT NOT NULL,
  product_id TEXT,
  parent_event_id TEXT,
  action_id TEXT,
  PRIMARY KEY (event_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (product_id) REFERENCES product(product_id),
  FOREIGN KEY (parent_event_id) REFERENCES engagement_event(event_id),
  FOREIGN KEY (action_id) REFERENCES action_catalog(action_id)
);

CREATE TABLE support_case (
  case_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  order_id TEXT,
  opened_ts TEXT NOT NULL,
  closed_ts TEXT,
  category TEXT NOT NULL,
  priority TEXT NOT NULL,
  channel TEXT NOT NULL,
  status TEXT NOT NULL,
  escalated_flag INTEGER NOT NULL,
  escalated_ts TEXT,
  handling_minutes INTEGER,
  cost_amount REAL,
  csat_score INTEGER,
  PRIMARY KEY (case_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE TABLE support_case_event (
  case_event_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  event_ts TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT NOT NULL,
  PRIMARY KEY (case_event_id),
  FOREIGN KEY (case_id) REFERENCES support_case(case_id)
);

CREATE TABLE consent (
  consent_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  source TEXT NOT NULL,
  lawful_basis TEXT NOT NULL,
  previous_consent_id TEXT,
  PRIMARY KEY (consent_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (previous_consent_id) REFERENCES consent(consent_id)
);

CREATE TABLE segment_rule (
  segment_id TEXT NOT NULL,
  segment_code TEXT NOT NULL,
  segment_name TEXT NOT NULL,
  exclusive_group TEXT NOT NULL,
  is_exclusive INTEGER NOT NULL,
  priority INTEGER NOT NULL,
  rule_version INTEGER NOT NULL,
  rule_params TEXT NOT NULL,
  rule_expression TEXT NOT NULL,
  status TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  superseded_by TEXT,
  PRIMARY KEY (segment_id),
  FOREIGN KEY (superseded_by) REFERENCES segment_rule(segment_id)
);

CREATE TABLE customer_metric_snapshot (
  snapshot_date TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  n_orders INTEGER NOT NULL,
  first_order_date TEXT,
  last_order_date TEXT,
  recency_days INTEGER,
  first_order_age_days INTEGER,
  gross_merchandise REAL NOT NULL,
  refund_total REAL NOT NULL,
  net_monetary REAL NOT NULL,
  return_rate REAL NOT NULL,
  r_score INTEGER,
  f_score INTEGER,
  m_score INTEGER,
  opens_90d INTEGER NOT NULL,
  clicks_90d INTEGER NOT NULL,
  cases_12m INTEGER NOT NULL,
  service_cost_12m REAL NOT NULL,
  consent_withdrawals_90d INTEGER NOT NULL,
  PRIMARY KEY (snapshot_date, customer_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

CREATE TABLE segment_membership (
  membership_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  is_current INTEGER NOT NULL,
  evaluated_snapshot_date TEXT NOT NULL,
  explanation TEXT NOT NULL,
  assigned_by TEXT NOT NULL,
  PRIMARY KEY (membership_id),
  FOREIGN KEY (segment_id) REFERENCES segment_rule(segment_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (evaluated_snapshot_date, customer_id) REFERENCES customer_metric_snapshot(snapshot_date, customer_id)
);

CREATE TABLE action_segment_eligibility (
  eligibility_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  priority INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  PRIMARY KEY (eligibility_id),
  FOREIGN KEY (action_id) REFERENCES action_catalog(action_id),
  FOREIGN KEY (segment_id) REFERENCES segment_rule(segment_id)
);

CREATE TABLE suppression_rule (
  suppression_id TEXT NOT NULL,
  suppression_code TEXT NOT NULL,
  description TEXT NOT NULL,
  evaluation_point TEXT NOT NULL,
  applies_to TEXT NOT NULL,
  PRIMARY KEY (suppression_id)
);

CREATE TABLE action_outcome (
  outcome_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  membership_id TEXT NOT NULL,
  slot INTEGER NOT NULL,
  recommended_at TEXT NOT NULL,
  decision TEXT NOT NULL,
  suppression_id TEXT,
  experiment_group TEXT NOT NULL,
  channel TEXT NOT NULL,
  consent_check TEXT NOT NULL,
  scheduled_send_ts TEXT NOT NULL,
  sent_ts TEXT,
  sent_event_id TEXT,
  opened_ts TEXT,
  clicked_ts TEXT,
  attributed_order_id TEXT,
  attribution_window_days INTEGER NOT NULL,
  converted_flag INTEGER NOT NULL,
  status TEXT NOT NULL,
  revenue_attributed REAL NOT NULL,
  action_cost REAL NOT NULL,
  discount_cost REAL NOT NULL,
  PRIMARY KEY (outcome_id),
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (action_id) REFERENCES action_catalog(action_id),
  FOREIGN KEY (segment_id) REFERENCES segment_rule(segment_id),
  FOREIGN KEY (membership_id) REFERENCES segment_membership(membership_id),
  FOREIGN KEY (suppression_id) REFERENCES suppression_rule(suppression_id),
  FOREIGN KEY (sent_event_id) REFERENCES engagement_event(event_id),
  FOREIGN KEY (attributed_order_id) REFERENCES orders(order_id)
);
