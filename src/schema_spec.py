"""Single source of truth: schema/data dictionary, segment rules, action catalog, suppression rules.
Used by generator (to build data + DDL + dictionary) and by validator/evaluator (to re-derive decisions)."""
import json
import numpy as np

# ----------------------------------------------------------------------------- enums
REGIONS = ['North America', 'Europe', 'APAC', 'LATAM', 'MEA']
AGE_BANDS = ['18-24', '25-34', '35-44', '45-54', '55+']
ACQ = ['organic_search', 'paid_social', 'email_referral', 'affiliate', 'direct', 'store']
LANGS = ['en', 'es', 'fr', 'de']
CHANNELS_CONTACT = ['email', 'sms', 'phone', 'push']
LIFECYCLE = ['prospect', 'new', 'active', 'lapsing', 'dormant']
ORDER_CH = ['web', 'app', 'store', 'phone']
ORDER_STATUS = ['completed', 'partially_returned', 'returned', 'cancelled']
RETURN_REASONS = ['size_fit', 'defect', 'not_as_described', 'changed_mind']
EVENT_TYPES = ['web_visit', 'product_view', 'cart_add', 'app_session', 'email_sent', 'email_open', 'email_click',
               'sms_sent', 'sms_click', 'push_sent', 'push_open', 'call_attempt', 'call_connected', 'unsubscribe']
EVENT_CH = ['web', 'app', 'email', 'sms', 'push', 'phone']
CASE_CATS = ['delivery_issue', 'product_defect', 'billing', 'returns_refund', 'how_to', 'complaint', 'account_access']
CASE_PRI = ['low', 'normal', 'high']
CASE_CH = ['phone', 'chat', 'email']
CASE_STATUS = ['open', 'escalated', 'closed']
CONSENT_STATUS = ['granted', 'withdrawn']
CONSENT_SRC = ['signup_form', 'app_prompt', 'unsubscribe_link', 'stop_reply', 'preference_center', 'support_agent']
OUT_STATUS = ['suppressed', 'holdout', 'sent', 'opened', 'clicked', 'converted']
OUT_DECISION = ['send', 'suppress', 'holdout']
CONSENT_CHECK = ['granted', 'withdrawn', 'never_granted', 'not_required', 'not_evaluated']

# ----------------------------------------------------------------------------- constants (documented business rules)
RFM_BINS = {
    'R_recency_days': [[30, 5], [60, 4], [120, 3], [240, 2], [10**9, 1]],     # first bound >= recency -> score
    'F_orders': [[10, 5], [6, 4], [4, 3], [2, 2], [1, 1]],                      # first bound <= freq -> score
    'M_net_spend_usd': [[1500, 5], [800, 4], [400, 3], [150, 2], [0, 1]],       # first bound <= net spend -> score
}
TAX_RATE = 0.08
FREE_SHIP_THRESHOLD_USD = 75.00
SHIP_FEE_USD = 5.99
CASE_COST_PER_MIN = 1.10
CASE_ESCALATION_FEE = 25.00
ATTRIBUTION_WINDOW_DAYS = 14
HOLDOUT_RATE = 0.10

# ----------------------------------------------------------------------------- segment rules (rule-driven evaluation)
# params keys: <metric>_min (>=), _max (<=), _gt (>), _eq (==); 'any_of' = OR of param dicts. Empty params = catch-all.
SEGMENTS = [
    # code, name, group, exclusive, priority, params, version, status, eff_from, eff_to
    ('PROSPECT', 'Prospect (no completed purchase)', 'lifecycle', True, 1, {'n_orders_eq': 0}, 1, 'active', '2025-01-01', None),
    ('NEW', 'New customer (first order <= 60d)', 'lifecycle', True, 2, {'first_order_age_days_max': 60}, 1, 'active', '2025-01-01', None),
    ('CHAMPIONS', 'Champions', 'lifecycle', True, 3, {'r_score_min': 4, 'f_score_min': 4, 'm_score_min': 4}, 1, 'active', '2025-01-01', None),
    ('LOYAL', 'Loyal', 'lifecycle', True, 4, {'r_score_min': 3, 'f_score_min': 3}, 1, 'active', '2025-01-01', None),
    ('AT_RISK', 'At risk (lapsing frequent buyer)', 'lifecycle', True, 5, {'r_score_max': 2, 'f_score_min': 3}, 1, 'active', '2025-01-01', None),
    ('DORMANT', 'Dormant (> 180 days)', 'lifecycle', True, 6, {'recency_days_gt': 180}, 2, 'active', '2026-07-01', None),
    ('PROMISING', 'Promising (recent, low frequency)', 'lifecycle', True, 7, {'r_score_min': 3}, 1, 'active', '2025-01-01', None),
    ('NEEDS_ATTENTION', 'Needs attention (catch-all)', 'lifecycle', True, 8, {}, 1, 'active', '2025-01-01', None),
    ('HIGH_SERVICE_COST', 'High service cost account', 'overlay', False, 20,
     {'any_of': [{'cases_12m_min': 4}, {'service_cost_12m_min': 120}]}, 1, 'active', '2025-01-01', None),
    ('HIGH_RETURNER', 'High returner', 'overlay', False, 21, {'return_rate_min': 0.30, 'n_orders_min': 3}, 1, 'active', '2025-01-01', None),
    ('CONSENT_WITHDRAWN', 'Consent withdrawn (last 90d)', 'overlay', False, 22, {'consent_withdrawals_90d_min': 1}, 1, 'active', '2025-01-01', None),
    ('EMAIL_ENGAGED', 'Email engaged (>=3 opens in 90d)', 'overlay', False, 23, {'opens_90d_min': 3}, 1, 'active', '2025-01-01', None),
    ('DORMANT_V1', 'Dormant v1 (> 150 days) - superseded', 'lifecycle', True, 6, {'recency_days_gt': 150}, 1, 'retired', '2025-01-01', '2026-06-30'),
]
SEG_ID = {s[0]: 'SEG-2026-%06d' % (i + 1) for i, s in enumerate(SEGMENTS)}

def rule_text(params):
    if not params:
        return 'TRUE (catch-all for remaining customers in the exclusive group)'
    if 'any_of' in params:
        return ' OR '.join('(%s)' % rule_text(p) for p in params['any_of'])
    sym = {'_min': '>=', '_max': '<=', '_gt': '>', '_eq': '=='}
    out = []
    for k, v in params.items():
        for suf, s in sym.items():
            if k.endswith(suf):
                out.append('%s %s %s' % (k[:-len(suf)], s, v))
    return ' AND '.join(out)

def eval_rule(params, m):
    """Vectorised rule evaluation on a metrics DataFrame (NaN -> condition false)."""
    n = len(m)
    if 'any_of' in params:
        r = np.zeros(n, bool)
        for p in params['any_of']:
            r |= eval_rule(p, m)
        return r
    r = np.ones(n, bool)
    for k, v in params.items():
        for suf in ('_min', '_max', '_gt', '_eq'):
            if k.endswith(suf):
                a = m[k[:-len(suf)]].to_numpy(dtype='float64', na_value=np.nan)
                with np.errstate(invalid='ignore'):
                    r &= {'_min': a >= v, '_max': a <= v, '_gt': a > v, '_eq': a == v}[suf]
    return r

def explain_row(params, row):
    """Human-readable evidence string for a membership: metric=value (condition)."""
    if not params:
        return 'no earlier exclusive rule matched'
    keys = []
    def walk(p):
        if 'any_of' in p:
            for q in p['any_of']:
                walk(q)
        else:
            keys.extend(p.items())
    walk(params)
    parts = []
    for k, v in keys:
        for suf, s in (('_min', '>='), ('_max', '<='), ('_gt', '>'), ('_eq', '==')):
            if k.endswith(suf):
                col = k[:-len(suf)]
                val = row[col]
                val = 'NA' if val is None or val != val else (('%.2f' % val) if isinstance(val, float) and val != int(val) else '%d' % val)
                parts.append('%s=%s (%s %s)' % (col, val, s, v))
    return '; '.join(parts)

# ----------------------------------------------------------------------------- action catalog
# code, name, purpose, objective, channels, requires_consent, is_discount, discount_pct, unit_cost, base_click, base_conv
ACTIONS = [
    ('WELCOME_SERIES', 'Welcome series & first-repeat nudge', 'marketing', 'second_purchase', ['email', 'push'], True, False, 0, 0.05, 0.22, 0.35),
    ('FIRST_PURCHASE_INCENTIVE', 'First-purchase 10% incentive', 'marketing', 'first_purchase', ['email', 'sms'], True, True, 10, 0.06, 0.12, 0.30),
    ('VIP_EARLY_ACCESS', 'VIP early access to new range', 'marketing', 'repeat_purchase', ['email', 'push', 'sms'], True, False, 0, 0.05, 0.30, 0.45),
    ('LOYALTY_BONUS_POINTS', 'Loyalty bonus points offer', 'marketing', 'repeat_purchase', ['email', 'push'], True, False, 0, 0.08, 0.25, 0.35),
    ('CROSS_SELL_BUNDLE', 'Cross-sell bundle recommendation', 'marketing', 'basket_growth', ['email', 'push'], True, False, 0, 0.05, 0.16, 0.30),
    ('WINBACK_DISCOUNT', 'Win-back 15% discount', 'marketing', 'reactivation', ['email', 'sms'], True, True, 15, 0.06, 0.12, 0.30),
    ('REENGAGEMENT_SURVEY', 'Re-engagement survey with small incentive', 'marketing', 'reactivation', ['email', 'push'], True, False, 0, 0.05, 0.14, 0.22),
    ('SERVICE_RECOVERY_CALL', 'Agent service-recovery call (open complaint in last 30d)', 'service', 'retention', ['phone'], False, False, 0, 4.50, 0.0, 0.35),
    ('RETURN_PREVENTION_GUIDE', 'Size/fit guide & exchange-first offer', 'marketing', 'reduce_returns', ['email'], True, False, 0, 0.05, 0.10, 0.10),
]
ACT_ID = {a[0]: 'ACTN-2026-%06d' % (i + 1) for i, a in enumerate(ACTIONS)}
ACT_PRECONDITION = {'SERVICE_RECOVERY_CALL': 'complaint or escalated case opened in the 30 days before the decision date'}
# bridge (N:M action <-> segment): action, segment, priority (1 = best)
ELIGIBILITY = [
    ('WELCOME_SERIES', 'NEW', 1), ('FIRST_PURCHASE_INCENTIVE', 'PROSPECT', 1), ('VIP_EARLY_ACCESS', 'CHAMPIONS', 1),
    ('LOYALTY_BONUS_POINTS', 'LOYAL', 1), ('CROSS_SELL_BUNDLE', 'PROMISING', 1), ('CROSS_SELL_BUNDLE', 'LOYAL', 3),
    ('CROSS_SELL_BUNDLE', 'EMAIL_ENGAGED', 4), ('WINBACK_DISCOUNT', 'AT_RISK', 1), ('WINBACK_DISCOUNT', 'DORMANT', 2),
    ('REENGAGEMENT_SURVEY', 'DORMANT', 1), ('REENGAGEMENT_SURVEY', 'NEEDS_ATTENTION', 1),
    ('SERVICE_RECOVERY_CALL', 'HIGH_SERVICE_COST', 1), ('RETURN_PREVENTION_GUIDE', 'HIGH_RETURNER', 2),
]
SUPPRESSION = [
    # id, code, description, evaluation point, applies_to
    ('SUP-001', 'NO_VALID_CONSENT', 'Marketing action needs a granted consent row for the chosen channel at scheduled send time; no allowed channel has one.', 'send', 'marketing'),
    ('SUP-002', 'FREQUENCY_CAP', 'Marketing contacts sent in the previous 30 days + this one would exceed customer.max_marketing_contacts_per_30d.', 'send', 'marketing'),
    ('SUP-003', 'OPEN_COMPLAINT', 'Customer has a complaint/escalated support case still unresolved at decision time.', 'decision', 'marketing'),
    ('SUP-004', 'PURCHASE_COOLDOWN', 'Post-purchase quiet period: marketing actions other than WELCOME_SERIES are blocked if the customer ordered within 7 days before decision time.', 'decision', 'marketing (except welcome)'),
    ('SUP-005', 'RETURNER_DISCOUNT_BLOCK', 'Discount actions are blocked for customers in the HIGH_RETURNER overlay segment.', 'decision', 'marketing discount'),
]

# ----------------------------------------------------------------------------- schema / data dictionary
TABLES = {}
def C(name, typ, req, allowed, uniq, rule):
    return (name, typ, req, allowed, uniq, rule)
def T(name, desc, pk, fks, cols, card):
    TABLES[name] = dict(desc=desc, pk=pk, fks=fks, cols=cols, cardinality=card)

T('customer', 'Customer or prospect master record (pseudonymous; no personal data).', ['customer_id'], [],
  [C('customer_id', 'STRING', 'Y', 'CUS-######', 'Y', 'regex ^CUS-\\d{6}$; immutable; ordered by signup_date'),
   C('customer_type', 'ENUM', 'Y', ['customer', 'prospect'], 'N', 'customer => >=1 order of any status; prospect => 0 orders'),
   C('signup_date', 'DATE', 'Y', 'ISO-8601 date', 'N', '<= 2026-09-30; <= first order date'),
   C('region', 'ENUM', 'Y', REGIONS, 'N', ''), C('age_band', 'ENUM', 'Y', AGE_BANDS, 'N', ''),
   C('acquisition_channel', 'ENUM', 'Y', ACQ, 'N', ''), C('preferred_language', 'ENUM', 'Y', LANGS, 'N', ''),
   C('preferred_channel', 'ENUM', 'Y', CHANNELS_CONTACT + ['none'], 'N', "must be a channel with a granted consent at signup, else 'none'"),
   C('max_marketing_contacts_per_30d', 'INT', 'Y', '1..4 (contacts)', 'N', 'contact-frequency cap used by SUP-002'),
   C('lifecycle_state', 'ENUM', 'Y', LIFECYCLE, 'N', 'derived at lifecycle_as_of_date: prospect=no orders; new=first order<=60d; active=recency<=90d; lapsing=91-180d; dormant>180d'),
   C('lifecycle_as_of_date', 'DATE', 'Y', 'ISO-8601 date', 'N', '= 2026-10-01 (snapshot 2)')],
  '1 customer : N orders, N events, N cases, N consents, N memberships, N outcomes')

T('product', 'Product master with taxonomy (category > subcategory) and lifecycle.', ['product_id'], [],
  [C('product_id', 'STRING', 'Y', 'PRD-#####', 'Y', 'regex ^PRD-\\d{5}$'),
   C('sku', 'STRING', 'Y', 'SKU-<CAT3>-#####', 'Y', ''),
   C('product_name', 'STRING', 'Y', 'text', 'N', ''), C('category', 'STRING', 'Y', '8 top-level categories', 'N', ''),
   C('subcategory', 'STRING', 'Y', 'text', 'N', 'belongs to category'), C('brand', 'STRING', 'Y', 'text', 'N', ''),
   C('list_price', 'DECIMAL', 'Y', 'USD > 0', 'N', 'price effective for whole window; > unit_cost'),
   C('unit_cost', 'DECIMAL', 'Y', 'USD > 0', 'N', '< list_price'),
   C('launch_date', 'DATE', 'Y', 'ISO date', 'N', 'order lines may only reference products on/after launch_date'),
   C('discontinued_date', 'DATE', 'N', 'ISO date', 'N', '>= launch_date; order lines must be on/before this date'),
   C('status', 'ENUM', 'Y', ['active', 'discontinued'], 'N', 'discontinued <=> discontinued_date not null')],
  '1 product : N order_lines (order_line is the Order<->Product bridge, N:M)')

T('orders', 'Customer order header. All monetary values are derived from order_line.', ['order_id'],
  [('customer_id', 'customer', 'customer_id')],
  [C('order_id', 'STRING', 'Y', 'ORD-2026-######', 'Y', 'regex ^ORD-2026-\\d{6}$; sequential in order_ts order'),
   C('customer_id', 'STRING', 'Y', 'FK customer', 'N', 'customer_type=customer'),
   C('order_ts', 'TIMESTAMP', 'Y', 'YYYY-MM-DD HH:MM:SS', 'N', '>= signup_date; 2025-01-01..2026-09-30'),
   C('channel', 'ENUM', 'Y', ORDER_CH, 'N', ''),
   C('status', 'ENUM', 'Y', ORDER_STATUS, 'N', 'derived: cancelled | returned (all qty returned) | partially_returned | completed (as of data end; history = line return_date / cancelled_ts)'),
   C('currency', 'STRING', 'Y', 'USD', 'N', ''),
   C('promo_pct', 'INT', 'Y', '0,10,15,20,30 (%)', 'N', 'order-level promo applied to every line'),
   C('promo_code', 'STRING', 'N', 'SAVE<pct> or action_code', 'N', 'null iff promo_pct=0'),
   C('discount_total', 'DECIMAL', 'Y', 'USD >= 0', 'N', '= sum(order_line.discount_amount)'),
   C('subtotal', 'DECIMAL', 'Y', 'USD > 0', 'N', '= sum(order_line.line_net_amount)'),
   C('shipping_fee', 'DECIMAL', 'Y', 'USD', 'N', '= 5.99 if subtotal < 75.00 else 0.00'),
   C('tax_amount', 'DECIMAL', 'Y', 'USD', 'N', '= round(subtotal * 0.08, 2)'),
   C('order_total', 'DECIMAL', 'Y', 'USD', 'N', '= subtotal + shipping_fee + tax_amount'),
   C('refund_total', 'DECIMAL', 'Y', 'USD >= 0', 'N', '= sum(order_line.refund_amount); merchandise only'),
   C('net_merchandise_value', 'DECIMAL', 'Y', 'USD >= 0', 'N', '= subtotal - refund_total; 0 when cancelled (excluded from spend)'),
   C('cancelled_ts', 'TIMESTAMP', 'N', 'timestamp', 'N', '> order_ts; required iff status=cancelled')],
  '1 order : 1..N order_lines')

T('order_line', 'Order line = bridge between Order and Product; carries return events.', ['order_line_id'],
  [('order_id', 'orders', 'order_id'), ('product_id', 'product', 'product_id')],
  [C('order_line_id', 'STRING', 'Y', 'ORL-2026-#######', 'Y', 'regex ^ORL-2026-\\d{7}$'),
   C('order_id', 'STRING', 'Y', 'FK orders', 'N', ''), C('line_number', 'INT', 'Y', '1..6', 'N', '(order_id,line_number) unique'),
   C('product_id', 'STRING', 'Y', 'FK product', 'N', 'product active at order date'),
   C('quantity', 'INT', 'Y', '1..3 units', 'N', ''), C('unit_price', 'DECIMAL', 'Y', 'USD', 'N', '= product.list_price'),
   C('discount_amount', 'DECIMAL', 'Y', 'USD >= 0', 'N', '= round(qty*unit_price*promo_pct/100, 2)'),
   C('line_net_amount', 'DECIMAL', 'Y', 'USD', 'N', '= qty*unit_price - discount_amount'),
   C('returned_quantity', 'INT', 'Y', '0..quantity', 'N', ''),
   C('return_date', 'DATE', 'N', 'ISO date', 'N', 'required iff returned_quantity>0; order_date+3..30d; <= 2026-09-30'),
   C('return_reason', 'ENUM', 'N', RETURN_REASONS, 'N', 'required iff returned_quantity>0'),
   C('refund_amount', 'DECIMAL', 'Y', 'USD >= 0', 'N', '= round(line_net_amount * returned_quantity / quantity, 2)')],
  'N lines : 1 order; N lines : 1 product')

T('engagement_event', 'Behavioural/marketing interaction events (web, app, email, sms, push, call).', ['event_id'],
  [('customer_id', 'customer', 'customer_id'), ('product_id', 'product', 'product_id'),
   ('parent_event_id', 'engagement_event', 'event_id'), ('action_id', 'action_catalog', 'action_id')],
  [C('event_id', 'STRING', 'Y', 'EVT-2026-#######', 'Y', 'regex ^EVT-2026-\\d{7}$; sequential in event_ts order'),
   C('customer_id', 'STRING', 'Y', 'FK customer', 'N', ''),
   C('event_ts', 'TIMESTAMP', 'Y', 'YYYY-MM-DD HH:MM:SS', 'N', '>= signup_date'),
   C('event_type', 'ENUM', 'Y', EVENT_TYPES, 'N', ''), C('channel', 'ENUM', 'Y', EVENT_CH, 'N', 'consistent with event_type'),
   C('product_id', 'STRING', 'N', 'FK product', 'N', 'only product_view/cart_add'),
   C('parent_event_id', 'STRING', 'N', 'FK engagement_event', 'N', 'open/click/connected -> the *_sent/call_attempt event; click -> open; parent.event_ts < child.event_ts'),
   C('action_id', 'STRING', 'N', 'FK action_catalog', 'N', 'set only on sends triggered by an action recommendation (and their opens/clicks)')],
  '1 event : 0..1 parent event')

T('support_case', 'Customer support case; current state (history in support_case_event).', ['case_id'],
  [('customer_id', 'customer', 'customer_id'), ('order_id', 'orders', 'order_id')],
  [C('case_id', 'STRING', 'Y', 'CASE-2026-######', 'Y', 'regex'), C('customer_id', 'STRING', 'Y', 'FK customer', 'N', ''),
   C('order_id', 'STRING', 'N', 'FK orders', 'N', 'if set, order belongs to same customer and order_ts < opened_ts'),
   C('opened_ts', 'TIMESTAMP', 'Y', 'timestamp', 'N', ''), C('closed_ts', 'TIMESTAMP', 'N', 'timestamp', 'N', '> opened_ts; null iff status != closed'),
   C('category', 'ENUM', 'Y', CASE_CATS, 'N', ''), C('priority', 'ENUM', 'Y', CASE_PRI, 'N', ''), C('channel', 'ENUM', 'Y', CASE_CH, 'N', ''),
   C('status', 'ENUM', 'Y', CASE_STATUS, 'N', 'lifecycle open -> [escalated] -> closed'),
   C('escalated_flag', 'BOOL', 'Y', '0/1', 'N', ''), C('escalated_ts', 'TIMESTAMP', 'N', 'timestamp', 'N', 'opened_ts < escalated_ts; set iff escalated_flag=1'),
   C('handling_minutes', 'INT', 'N', 'minutes', 'N', 'known when closed'),
   C('cost_amount', 'DECIMAL', 'N', 'USD', 'N', '= handling_minutes*1.10 + 25.00*escalated_flag (closed cases only)'),
   C('csat_score', 'INT', 'N', '1..5', 'N', 'closed cases only (optional survey)')],
  '1 customer : N cases; 1 order : 0..N cases')

T('support_case_event', 'Append-only status history for support cases.', ['case_event_id'], [('case_id', 'support_case', 'case_id')],
  [C('case_event_id', 'STRING', 'Y', 'CEV-2026-######', 'Y', ''), C('case_id', 'STRING', 'Y', 'FK support_case', 'N', ''),
   C('event_ts', 'TIMESTAMP', 'Y', 'timestamp', 'N', ''), C('from_status', 'ENUM', 'N', CASE_STATUS, 'N', 'null for creation'),
   C('to_status', 'ENUM', 'Y', CASE_STATUS, 'N', 'valid transitions: null>open, open>escalated, open>closed, escalated>closed')],
  '1 case : 1..3 events')

T('consent', 'Per-channel marketing consent as an append-only interval history.', ['consent_id'],
  [('customer_id', 'customer', 'customer_id'), ('previous_consent_id', 'consent', 'consent_id')],
  [C('consent_id', 'STRING', 'Y', 'CON-2026-#######', 'Y', ''), C('customer_id', 'STRING', 'Y', 'FK customer', 'N', ''),
   C('channel', 'ENUM', 'Y', CHANNELS_CONTACT, 'N', ''), C('purpose', 'STRING', 'Y', 'marketing', 'N', ''),
   C('status', 'ENUM', 'Y', CONSENT_STATUS, 'N', 'per (customer,channel): granted -> withdrawn -> granted ...'),
   C('effective_from', 'TIMESTAMP', 'Y', 'timestamp', 'N', ''),
   C('effective_to', 'TIMESTAMP', 'N', 'timestamp', 'N', 'null = current; equals effective_from of the next row; intervals never overlap'),
   C('source', 'ENUM', 'Y', CONSENT_SRC, 'N', ''), C('lawful_basis', 'STRING', 'Y', 'consent', 'N', ''),
   C('previous_consent_id', 'STRING', 'N', 'FK consent', 'N', 'previous row in the (customer,channel) chain')],
  '1 customer : 0..N consent rows per channel')

T('segment_rule', 'Versioned segment definitions (rule-driven; params JSON is executable).', ['segment_id'],
  [('superseded_by', 'segment_rule', 'segment_id')],
  [C('segment_id', 'STRING', 'Y', 'SEG-2026-######', 'Y', ''), C('segment_code', 'STRING', 'Y', 'text', 'N', ''),
   C('segment_name', 'STRING', 'Y', 'text', 'N', ''), C('exclusive_group', 'ENUM', 'Y', ['lifecycle', 'overlay'], 'N', 'lifecycle = mutually exclusive; overlay = additive'),
   C('is_exclusive', 'BOOL', 'Y', '0/1', 'N', '1 for lifecycle group'), C('priority', 'INT', 'Y', 'lower wins within exclusive group', 'N', ''),
   C('rule_version', 'INT', 'Y', '>=1', 'N', ''), C('rule_params', 'JSON', 'Y', 'JSON object', 'N', 'executable conditions on customer_metric_snapshot'),
   C('rule_expression', 'STRING', 'Y', 'text', 'N', 'human readable form of rule_params'),
   C('status', 'ENUM', 'Y', ['active', 'retired'], 'N', ''), C('effective_from', 'DATE', 'Y', 'date', 'N', ''),
   C('effective_to', 'DATE', 'N', 'date', 'N', ''), C('superseded_by', 'STRING', 'N', 'FK segment_rule', 'N', '')],
  '1 rule : N memberships')

T('customer_metric_snapshot', 'Derived RFM + service/engagement metrics per customer per snapshot date (evidence for memberships).',
  ['snapshot_date', 'customer_id'], [('customer_id', 'customer', 'customer_id')],
  [C('snapshot_date', 'DATE', 'Y', '2026-07-01 | 2026-10-01', 'N', 'metrics use only data strictly before this date'),
   C('customer_id', 'STRING', 'Y', 'FK customer', 'N', 'signup_date < snapshot_date'),
   C('n_orders', 'INT', 'Y', '>=0', 'N', 'non-cancelled orders before snapshot'),
   C('first_order_date', 'DATE', 'N', '', 'N', ''), C('last_order_date', 'DATE', 'N', '', 'N', ''),
   C('recency_days', 'INT', 'N', 'days', 'N', '= snapshot_date - last_order_date'),
   C('first_order_age_days', 'INT', 'N', 'days', 'N', '= snapshot_date - first_order_date'),
   C('gross_merchandise', 'DECIMAL', 'Y', 'USD', 'N', '= sum(line_net_amount) of non-cancelled orders'),
   C('refund_total', 'DECIMAL', 'Y', 'USD', 'N', '= sum(refund_amount) with return_date < snapshot_date'),
   C('net_monetary', 'DECIMAL', 'Y', 'USD', 'N', '= gross_merchandise - refund_total (returns netted)'),
   C('return_rate', 'DECIMAL', 'Y', '0..1', 'N', '= refund_total / gross_merchandise'),
   C('r_score', 'INT', 'N', '1..5', 'N', 'see RFM bins'), C('f_score', 'INT', 'N', '1..5', 'N', ''), C('m_score', 'INT', 'N', '1..5', 'N', 'from net_monetary'),
   C('opens_90d', 'INT', 'Y', '>=0', 'N', 'email_open events in the 90 days before snapshot'),
   C('clicks_90d', 'INT', 'Y', '>=0', 'N', 'email_click events in the 90 days before snapshot'),
   C('cases_12m', 'INT', 'Y', '>=0', 'N', 'cases opened in the 365 days before snapshot'),
   C('service_cost_12m', 'DECIMAL', 'Y', 'USD', 'N', 'sum cost_amount of cases opened in last 365d and closed before snapshot'),
   C('consent_withdrawals_90d', 'INT', 'Y', '>=0', 'N', 'withdrawn consent rows effective in the 90 days before snapshot')],
  '1 customer : 1 row per snapshot date')

T('segment_membership', 'Effective-dated customer<->segment bridge (N:M). History retained: rows are closed, never overwritten.',
  ['membership_id'], [('segment_id', 'segment_rule', 'segment_id'), ('customer_id', 'customer', 'customer_id')],
  [C('membership_id', 'STRING', 'Y', 'MEM-<segment-id>-<customer-id>', 'Y', 'regex ^MEM-SEG-2026-\\d{6}-CUS-\\d{6}$'),
   C('segment_id', 'STRING', 'Y', 'FK segment_rule', 'N', ''), C('customer_id', 'STRING', 'Y', 'FK customer', 'N', ''),
   C('effective_from', 'DATE', 'Y', 'date', 'N', 'segment rule must be effective on this date'),
   C('effective_to', 'DATE', 'N', 'date', 'N', 'null = current; > effective_from'),
   C('is_current', 'BOOL', 'Y', '0/1', 'N', '1 iff effective_to is null'),
   C('evaluated_snapshot_date', 'DATE', 'Y', 'date', 'N', 'FK (snapshot_date, customer_id) -> customer_metric_snapshot'),
   C('explanation', 'STRING', 'Y', 'text', 'N', 'metric=value (condition) evidence for the rule'),
   C('assigned_by', 'STRING', 'Y', 'rule_engine | legacy_sync', 'N', '')],
  'N customers : M segments; <=1 current lifecycle-group membership per customer')

T('action_catalog', 'Catalogue of recommendable actions.', ['action_id'], [],
  [C('action_id', 'STRING', 'Y', 'ACTN-2026-######', 'Y', ''), C('action_code', 'STRING', 'Y', 'text', 'Y', ''),
   C('action_name', 'STRING', 'Y', 'text', 'N', ''), C('purpose', 'ENUM', 'Y', ['marketing', 'service'], 'N', 'service actions do not need marketing consent'),
   C('objective', 'STRING', 'Y', 'text', 'N', ''), C('allowed_channels', 'STRING', 'Y', 'pipe-separated, preference order', 'N', ''),
   C('requires_consent', 'BOOL', 'Y', '0/1', 'N', '1 iff purpose = marketing'), C('is_discount', 'BOOL', 'Y', '0/1', 'N', ''),
   C('discount_pct', 'INT', 'Y', '0..30', 'N', ''), C('unit_cost', 'DECIMAL', 'Y', 'USD per send/call', 'N', ''),
   C('precondition', 'STRING', 'N', 'text', 'N', ''), C('status', 'ENUM', 'Y', ['active'], 'N', ''),
   C('effective_from', 'DATE', 'Y', 'date', 'N', ''), C('effective_to', 'DATE', 'N', 'date', 'N', '')],
  '1 action : N outcomes')

T('action_segment_eligibility', 'Bridge: which actions may be recommended to which segments (N:M).', ['eligibility_id'],
  [('action_id', 'action_catalog', 'action_id'), ('segment_id', 'segment_rule', 'segment_id')],
  [C('eligibility_id', 'STRING', 'Y', 'ELG-####', 'Y', ''), C('action_id', 'STRING', 'Y', 'FK action_catalog', 'N', ''),
   C('segment_id', 'STRING', 'Y', 'FK segment_rule', 'N', ''), C('priority', 'INT', 'Y', '1..9', 'N', '1 = preferred'),
   C('effective_from', 'DATE', 'Y', 'date', 'N', ''), C('effective_to', 'DATE', 'N', 'date', 'N', '')],
  'N actions : M segments')

T('suppression_rule', 'Documented contact suppression rules referenced by outcomes.', ['suppression_id'], [],
  [C('suppression_id', 'STRING', 'Y', 'SUP-###', 'Y', ''), C('suppression_code', 'STRING', 'Y', 'text', 'Y', ''),
   C('description', 'STRING', 'Y', 'text', 'N', ''), C('evaluation_point', 'ENUM', 'Y', ['decision', 'send'], 'N', ''),
   C('applies_to', 'STRING', 'Y', 'text', 'N', '')], '1 rule : N suppressed outcomes')

T('action_outcome', 'Recommendation log + subsequent outcome (one row per customer x recommended action).', ['outcome_id'],
  [('customer_id', 'customer', 'customer_id'), ('action_id', 'action_catalog', 'action_id'),
   ('segment_id', 'segment_rule', 'segment_id'), ('membership_id', 'segment_membership', 'membership_id'),
   ('suppression_id', 'suppression_rule', 'suppression_id'), ('sent_event_id', 'engagement_event', 'event_id'),
   ('attributed_order_id', 'orders', 'order_id')],
  [C('outcome_id', 'STRING', 'Y', 'OUT-2026-######', 'Y', 'ID convention extension (not in brief)'),
   C('customer_id', 'STRING', 'Y', 'FK customer', 'N', ''), C('action_id', 'STRING', 'Y', 'FK action_catalog', 'N', 'must be eligible for segment_id (bridge)'),
   C('segment_id', 'STRING', 'Y', 'FK segment_rule', 'N', 'segment that triggered the recommendation'),
   C('membership_id', 'STRING', 'Y', 'FK segment_membership', 'N', 'membership valid at recommended_at'),
   C('slot', 'INT', 'Y', '1|2', 'N', 'max two recommendations per customer per run'),
   C('recommended_at', 'TIMESTAMP', 'Y', 'timestamp', 'N', 'decision time = snapshot 2026-07-01'),
   C('decision', 'ENUM', 'Y', OUT_DECISION, 'N', ''),
   C('suppression_id', 'STRING', 'N', 'FK suppression_rule', 'N', 'iff decision=suppress'),
   C('experiment_group', 'ENUM', 'Y', ['treatment', 'holdout', 'none'], 'N', 'holdout = random 10% of otherwise-sendable marketing recommendations'),
   C('channel', 'ENUM', 'Y', CHANNELS_CONTACT, 'N', 'chosen (or intended) channel'),
   C('consent_check', 'ENUM', 'Y', CONSENT_CHECK, 'N', 'result of consent evaluation at scheduled send time'),
   C('scheduled_send_ts', 'TIMESTAMP', 'Y', 'timestamp', 'N', '> recommended_at'),
   C('sent_ts', 'TIMESTAMP', 'N', 'timestamp', 'N', 'iff decision=send'), C('sent_event_id', 'STRING', 'N', 'FK engagement_event', 'N', 'iff decision=send'),
   C('opened_ts', 'TIMESTAMP', 'N', 'timestamp', 'N', ''), C('clicked_ts', 'TIMESTAMP', 'N', 'timestamp', 'N', ''),
   C('attributed_order_id', 'STRING', 'N', 'FK orders', 'N', 'earliest non-cancelled order of the customer within 14d after sent_ts for which this send is the last touch (holdout: within 14d after scheduled_send_ts)'),
   C('attribution_window_days', 'INT', 'Y', '14', 'N', ''), C('converted_flag', 'BOOL', 'Y', '0/1', 'N', '1 iff attributed_order_id not null'),
   C('status', 'ENUM', 'Y', OUT_STATUS, 'N', 'furthest funnel stage reached; holdout/suppressed are terminal'),
   C('revenue_attributed', 'DECIMAL', 'Y', 'USD', 'N', '= orders.net_merchandise_value of attributed order, else 0'),
   C('action_cost', 'DECIMAL', 'Y', 'USD', 'N', '= action.unit_cost if sent else 0'),
   C('discount_cost', 'DECIMAL', 'Y', 'USD', 'N', '= orders.discount_total when attributed order used this action promo_code')],
  '1 outcome : 1 customer, 1 action, 1 triggering segment')

# ------------------------------------------------------------------ DDL / dictionary helpers
SQLT = {'STRING': 'TEXT', 'INT': 'INTEGER', 'DECIMAL': 'REAL', 'DATE': 'TEXT', 'TIMESTAMP': 'TEXT', 'BOOL': 'INTEGER', 'JSON': 'TEXT', 'ENUM': 'TEXT'}
TABLE_ORDER = ['customer', 'product', 'orders', 'order_line', 'action_catalog', 'engagement_event', 'support_case', 'support_case_event',
               'consent', 'segment_rule', 'customer_metric_snapshot', 'segment_membership', 'action_segment_eligibility',
               'suppression_rule', 'action_outcome']

def ddl():
    out = ['-- generated from schema_spec.py (SQLite dialect; portable to Postgres with minor type changes)']
    for t in TABLE_ORDER:
        d = TABLES[t]
        lines = []
        for c in d['cols']:
            lines.append('  %s %s%s' % (c[0], SQLT[c[1]], ' NOT NULL' if c[2] == 'Y' else ''))
        lines.append('  PRIMARY KEY (%s)' % ', '.join(d['pk']))
        for col, rt, rc in d['fks']:
            lines.append('  FOREIGN KEY (%s) REFERENCES %s(%s)' % (col, rt, rc))
        if t == 'segment_membership':
            lines.append('  FOREIGN KEY (evaluated_snapshot_date, customer_id) REFERENCES customer_metric_snapshot(snapshot_date, customer_id)')
        out.append('CREATE TABLE %s (\n%s\n);' % (t, ',\n'.join(lines)))
    return '\n\n'.join(out) + '\n'

def dictionary_rows():
    rows = []
    for t in TABLE_ORDER:
        d = TABLES[t]
        for c in d['cols']:
            allowed = '|'.join(c[3]) if isinstance(c[3], list) else c[3]
            fk = [f for f in d['fks'] if f[0] == c[0]]
            rows.append(dict(table=t, field=c[0], type=c[1], required=c[2], allowed_values_or_units=allowed, unique=c[4],
                             primary_key='Y' if c[0] in d['pk'] else 'N', foreign_key=('%s.%s' % (fk[0][1], fk[0][2])) if fk else '',
                             validation_rule=c[5]))
    return rows

def enum_map():
    m = {}
    for t, d in TABLES.items():
        for c in d['cols']:
            if isinstance(c[3], list):
                m[(t, c[0])] = set(c[3])
    return m
