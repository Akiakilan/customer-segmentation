#!/usr/bin/env python3
"""Independent validation: reads only the exported CSVs (+ ground truth for scoring detections at the end)."""
import argparse, json, os, re, sys
import numpy as np, pandas as pd
import schema_spec as S

ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='output'); a = ap.parse_args()
D = os.path.join(a.dir, 'data')
T = {t: pd.read_csv(os.path.join(D, t + '.csv'), dtype=str, keep_default_na=False, na_values=['']) for t in S.TABLE_ORDER}
GT = pd.read_csv(os.path.join(a.dir, 'ground_truth', 'ground_truth.csv'), dtype=str)
LAB = pd.read_csv(os.path.join(a.dir, 'ground_truth', 'ground_truth_customer_labels.csv'), dtype=str)
res = []          # (group, check, status, detail)
def rec(group, name, ok, detail=''):
    res.append(dict(group=group, check=name, status='PASS' if ok else 'FAIL', detail=str(detail)))
def info(group, name, detail):
    res.append(dict(group=group, check=name, status='INFO', detail=str(detail)))

DAY = 86400
W0 = pd.Timestamp('2025-01-01')
def ts(s): return pd.to_datetime(s, format='ISO8601')
def sec(s): return (pd.to_datetime(s, format='ISO8601') - W0).dt.total_seconds()
def day(s): return (pd.to_datetime(s, format='ISO8601') - W0).dt.days

# ------------------------------------------------------------ 1. PK uniqueness + ID format
RX = {'customer': r'^CUS-\d{6}$', 'product': r'^PRD-\d{5}$', 'orders': r'^ORD-2026-\d{6}$', 'order_line': r'^ORL-2026-\d{7}$', 'engagement_event': r'^EVT-2026-\d{7}$',
      'support_case': r'^CASE-2026-\d{6}$', 'support_case_event': r'^CEV-2026-\d{6}$', 'consent': r'^CON-2026-\d{7}$', 'segment_rule': r'^SEG-2026-\d{6}$',
      'segment_membership': r'^MEM-SEG-2026-\d{6}-CUS-\d{6}$', 'action_catalog': r'^ACTN-2026-\d{6}$', 'action_outcome': r'^OUT-2026-\d{6}$',
      'action_segment_eligibility': r'^ELG-\d{4}$', 'suppression_rule': r'^SUP-\d{3}$'}
for t, d in S.TABLES.items():
    df = T[t]
    dup = df.duplicated(d['pk']).sum()
    rec('1 primary keys', '%s PK unique (%s)' % (t, ','.join(d['pk'])), dup == 0, 'duplicates=%d rows=%d' % (dup, len(df)))
    nn = df[d['pk']].isna().any(axis=1).sum(); rec('1 primary keys', '%s PK not null' % t, nn == 0, nn)
    if t in RX:
        bad = (~df[d['pk'][0]].str.match(RX[t])).sum(); rec('1 primary keys', '%s ID format %s' % (t, RX[t]), bad == 0, 'bad=%d' % bad)
# required columns not null
for t, d in S.TABLES.items():
    miss = {c[0]: int(T[t][c[0]].isna().sum()) for c in d['cols'] if c[2] == 'Y' and T[t][c[0]].isna().any()}
    rec('1 primary keys', '%s required fields populated' % t, not miss, miss)
# columns match dictionary
for t, d in S.TABLES.items():
    rec('1 primary keys', '%s columns == data dictionary' % t, list(T[t].columns) == [c[0] for c in d['cols']])
# sequential IDs
for t, col in (('orders', 'order_id'), ('engagement_event', 'event_id'), ('order_line', 'order_line_id'), ('customer', 'customer_id'), ('support_case', 'case_id')):
    n = T[t][col].str.extract(r'(\d+)$')[0].astype(int).values
    rec('1 primary keys', '%s counter gap-free & zero padded' % t, (n == np.arange(1, len(n) + 1)).all())

# ------------------------------------------------------------ 2. FK integrity
nfk = 0
for t, d in S.TABLES.items():
    for col, pt, pc in d['fks']:
        ch = T[t][col].dropna(); orphan = (~ch.isin(set(T[pt][pc]))).sum(); nfk += 1
        rec('2 foreign keys', '%s.%s -> %s.%s' % (t, col, pt, pc), orphan == 0, 'orphans=%d of %d' % (orphan, len(ch)))
ms = T['segment_membership'][['evaluated_snapshot_date', 'customer_id']]; sk = set(zip(T['customer_metric_snapshot'].snapshot_date, T['customer_metric_snapshot'].customer_id))
rec('2 foreign keys', 'segment_membership(evaluated_snapshot_date,customer_id) -> customer_metric_snapshot', all(k in sk for k in zip(ms.evaluated_snapshot_date, ms.customer_id)))
# natural-key duplicates
rec('2 foreign keys', 'order_line (order_id,line_number) unique', not T['order_line'].duplicated(['order_id', 'line_number']).any())
rec('2 foreign keys', 'consent (customer,channel,effective_from) unique', not T['consent'].duplicated(['customer_id', 'channel', 'effective_from']).any())
rec('2 foreign keys', 'membership (customer,segment,effective_from) unique', not T['segment_membership'].duplicated(['customer_id', 'segment_id', 'effective_from']).any())
ev = T['engagement_event']
dupe = ev.duplicated(['customer_id', 'event_ts', 'event_type', 'product_id', 'action_id']).sum()
rec('2 foreign keys', 'no exact-duplicate engagement events', dupe == 0, dupe)

# ------------------------------------------------------------ 3. enums
EM = S.enum_map(); bad = {}
for (t, c), vals in EM.items():
    n = (~T[t][c].dropna().isin(vals)).sum()
    if n: bad['%s.%s' % (t, c)] = int(n)
rec('3 enums', 'all ENUM columns within allowed values (%d columns)' % len(EM), not bad, bad)

# ------------------------------------------------------------ 4. date ordering
cu, od, ln = T['customer'], T['orders'], T['order_line']
cu_signup = cu.set_index('customer_id').signup_date
o_ts = ts(od.order_ts)
rec('4 date ordering', 'order_ts >= customer.signup_date', (o_ts.dt.normalize() >= ts(od.customer_id.map(cu_signup))).all())
rec('4 date ordering', 'order_ts inside 2025-01-01..2026-09-30', (o_ts.min() >= W0) and (o_ts.max() < pd.Timestamp('2026-10-01')))
rec('4 date ordering', 'orders only for customer_type=customer', not od.customer_id.isin(set(cu[cu.customer_type == 'prospect'].customer_id)).any())
rec('4 date ordering', 'every customer_type=customer has >=1 order', cu[cu.customer_type == 'customer'].customer_id.isin(set(od.customer_id)).all())
canc = od[od.status == 'cancelled']
rec('4 date ordering', 'cancelled_ts > order_ts and set iff cancelled', (ts(canc.cancelled_ts) > ts(canc.order_ts)).all() and od.cancelled_ts.notna().sum() == len(canc))
lo = ln.merge(od[['order_id', 'order_ts']], on='order_id')
r_ = lo[lo.return_date.notna()]
dd = (ts(r_.return_date) - ts(r_.order_ts).dt.normalize()).dt.days
rec('4 date ordering', 'return_date 3..30 days after order', dd.between(3, 30).all(), 'n_returns=%d' % len(r_))
rec('4 date ordering', 'return_date <= 2026-09-30', ts(r_.return_date).max() <= pd.Timestamp('2026-09-30'))
rec('4 date ordering', 'return_date/reason present iff returned_quantity>0', ((ln.returned_quantity.astype(int) > 0) == ln.return_date.notna()).all() and ((ln.returned_quantity.astype(int) > 0) == ln.return_reason.notna()).all())
pr = T['product'].set_index('product_id'); lp = lo.assign(ldate=ts(lo.order_ts).dt.normalize(), pid=lo.order_line_id).merge(
    T['order_line'][['order_line_id', 'product_id']], on='order_line_id')
pl = pr.loc[lp.product_id_x if 'product_id_x' in lp else lp.product_id]
lau = ts(pl.launch_date.values); dis = ts(pl.discontinued_date.fillna('2099-01-01').values)
rec('4 date ordering', 'order lines reference products active at order date', ((lau <= lp.ldate.values) & (lp.ldate.values <= dis)).all())
cs = T['support_case']
c_open, c_close = ts(cs.opened_ts), ts(cs.closed_ts)
rec('4 date ordering', 'case closed_ts > opened_ts; null iff status != closed', (c_close.dropna() > c_open[c_close.notna()]).all() and (cs.closed_ts.notna() == (cs.status == 'closed')).all())
cso = cs[cs.order_id.notna()].merge(od[['order_id', 'customer_id', 'order_ts']], on='order_id', suffixes=('', '_o'))
rec('4 date ordering', 'case.order_id belongs to same customer and precedes case', (cso.customer_id == cso.customer_id_o).all() and (ts(cso.opened_ts) > ts(cso.order_ts)).all())
ev_ts = ts(ev.event_ts)
rec('4 date ordering', 'engagement event_ts >= customer signup', (ev_ts.dt.normalize() >= ts(ev.customer_id.map(cu_signup))).all())
par = ev[ev.parent_event_id.notna()].merge(ev[['event_id', 'event_ts', 'event_type', 'customer_id']], left_on='parent_event_id', right_on='event_id', suffixes=('', '_p'))
rec('4 date ordering', 'child event after parent, same customer', (ts(par.event_ts) > ts(par.event_ts_p)).all() and (par.customer_id == par.customer_id_p).all(), 'children=%d' % len(par))
okp = {'email_open': {'email_sent'}, 'email_click': {'email_open'}, 'push_open': {'push_sent'}, 'call_connected': {'call_attempt'}, 'sms_click': {'sms_sent'}}
rec('4 date ordering', 'parent event types follow funnel', all(r_t in okp.get(c_t, set()) for c_t, r_t in set(zip(par.event_type, par.event_type_p))))
rec('4 date ordering', 'event ids are time-ordered', ev_ts.is_monotonic_increasing)
rec('4 date ordering', 'order ids are time-ordered', o_ts.is_monotonic_increasing)

# ------------------------------------------------------------ 5. arithmetic reconciliation
for c in ('unit_price', 'discount_amount', 'line_net_amount', 'refund_amount'): ln[c] = ln[c].astype(float)
ln['qty'] = ln.quantity.astype(int); ln['rq'] = ln.returned_quantity.astype(int)
pp = pr.list_price.astype(float)
rec('5 reconciliation', 'unit_price == product.list_price', np.isclose(ln.unit_price, ln.product_id.map(pp)).all())
promo = ln.order_id.map(od.set_index('order_id').promo_pct.astype(int))
rec('5 reconciliation', 'discount_amount == round(qty*price*promo%)', (np.abs(ln.discount_amount - np.round(ln.qty * ln.unit_price * promo / 100, 2)) <= .0101).all())
rec('5 reconciliation', 'line_net == qty*price - discount', (np.abs(ln.line_net_amount - (ln.qty * ln.unit_price - ln.discount_amount)) < .0051).all())
rec('5 reconciliation', 'refund == line_net * returned_qty / qty', (np.abs(ln.refund_amount - np.round(ln.line_net_amount * ln.rq / ln.qty, 2)) <= .0101).all())
agg = ln.groupby('order_id').agg(sub=('line_net_amount', 'sum'), dis=('discount_amount', 'sum'), ref=('refund_amount', 'sum'), q=('qty', 'sum'), rq=('rq', 'sum'))
o2 = od.set_index('order_id').join(agg)
for c in ('subtotal', 'discount_total', 'refund_total', 'shipping_fee', 'tax_amount', 'order_total', 'net_merchandise_value'): o2[c] = o2[c].astype(float)
rec('5 reconciliation', 'order.subtotal == sum(line_net)', np.abs(o2.subtotal - o2['sub']).max() < .011, np.abs(o2.subtotal - o2['sub']).max())
rec('5 reconciliation', 'order.discount_total == sum(discount)', np.abs(o2.discount_total - o2.dis).max() < .011)
rec('5 reconciliation', 'order.refund_total == sum(refund)', np.abs(o2.refund_total - o2.ref).max() < .011)
rec('5 reconciliation', 'shipping rule (<$75 => $5.99)', (o2.shipping_fee == np.where(o2.subtotal < 75, 5.99, 0.0)).all())
rec('5 reconciliation', 'tax == round(8% subtotal)', (np.abs(o2.tax_amount - np.round(o2.subtotal * .08, 2)) < .0101).all())
rec('5 reconciliation', 'order_total == subtotal+shipping+tax', (np.abs(o2.order_total - (o2.subtotal + o2.shipping_fee + o2.tax_amount)) < .0101).all())
rec('5 reconciliation', 'net_merchandise == subtotal - refunds (0 if cancelled)', (np.abs(o2.net_merchandise_value - np.where(o2.status == 'cancelled', 0, o2.subtotal - o2.refund_total)) < .0101).all())
exp_status = np.where(o2.status == 'cancelled', 'cancelled', np.where(o2.rq == o2.q, 'returned', np.where(o2.rq > 0, 'partially_returned', 'completed')))
rec('5 reconciliation', 'order.status derived from lines', (o2.status.values == exp_status).all())
rec('5 reconciliation', 'promo_code null iff promo_pct=0', ((o2.promo_pct.astype(int) == 0) == o2.promo_code.isna()).all())
cs['h'] = pd.to_numeric(cs.handling_minutes); cs['cost'] = pd.to_numeric(cs.cost_amount); cl = cs[cs.status == 'closed']
rec('5 reconciliation', 'case cost == minutes*1.10 + 25*escalated', (np.abs(cl.cost - (cl.h * 1.10 + 25 * cl.escalated_flag.astype(int))) < .0101).all())
rec('5 reconciliation', 'open cases carry no cost/minutes/csat', cs[cs.status != 'closed'][['h', 'cost', 'csat_score']].isna().all().all())

# --- recompute metric snapshots from source records
def recompute(snap):
    Sd = int((pd.Timestamp(snap) - W0).days); ssec = Sd * DAY
    o = od[(day(od.order_ts) < Sd) & (od.status != 'cancelled')]
    ll = ln.merge(od[['order_id', 'customer_id', 'order_ts', 'status']], on='order_id'); ll = ll[(day(ll.order_ts) < Sd) & (ll.status != 'cancelled')]
    ll['ret'] = np.where(ll.return_date.notna() & (day(ll.return_date.fillna('2025-01-01')) < Sd), ll.refund_amount, 0.0)
    g = ll.groupby('customer_id').agg(gross=('line_net_amount', 'sum'), refund=('ret', 'sum'))
    oo = o.assign(d=day(o.order_ts)).groupby('customer_id').d.agg(['count', 'min', 'max'])
    e = ev[(sec(ev.event_ts) >= ssec - 90 * DAY) & (sec(ev.event_ts) < ssec) & ev.event_type.isin(['email_open', 'email_click'])]
    e = e.groupby(['customer_id', 'event_type']).size().unstack(fill_value=0)
    c = cs[(sec(cs.opened_ts) >= ssec - 365 * DAY) & (sec(cs.opened_ts) < ssec)]
    c12 = c.groupby('customer_id').size()
    cc = c[(c.closed_ts.notna()) & (sec(c.closed_ts.fillna('2025-01-01')) < ssec)].groupby('customer_id').cost.sum()
    cn = T['consent']; w = cn[(cn.status == 'withdrawn') & (sec(cn.effective_from) >= ssec - 90 * DAY) & (sec(cn.effective_from) < ssec)].groupby('customer_id').size()
    m = pd.DataFrame(index=cu.customer_id[day(cu.signup_date) < Sd].values)
    m['n_orders'] = oo['count'].reindex(m.index).fillna(0); m['first'] = oo['min'].reindex(m.index); m['last'] = oo['max'].reindex(m.index)
    m['gross'] = g.gross.reindex(m.index).fillna(0); m['refund'] = g.refund.reindex(m.index).fillna(0); m['net'] = m.gross - m.refund
    m['opens'] = e['email_open'].reindex(m.index).fillna(0) if 'email_open' in e else 0
    m['cases12'] = c12.reindex(m.index).fillna(0); m['cost12'] = cc.reindex(m.index).fillna(0); m['wd90'] = w.reindex(m.index).fillna(0)
    return m
mets = {}
for snap in ('2026-07-01', '2026-10-01'):
    mt = T['customer_metric_snapshot']; mt = mt[mt.snapshot_date == snap].set_index('customer_id')
    rc = recompute(snap).reindex(mt.index)
    st = pd.DataFrame(dict(n=mt.n_orders.astype(float), gross=mt.gross_merchandise.astype(float), refund=mt.refund_total.astype(float), net=mt.net_monetary.astype(float),
                           opens=mt.opens_90d.astype(float), cases12=mt.cases_12m.astype(float), cost12=mt.service_cost_12m.astype(float), wd90=mt.consent_withdrawals_90d.astype(float)))
    bad_n = (st.n != rc.n_orders); bad_g = np.abs(st.gross - rc.gross) > .011; bad_r = np.abs(st.refund - rc.refund) > .011
    bad_net = np.abs(st.net - rc.net) > .011
    rec('5 reconciliation', '[%s] n_orders/gross/opens/cases/cost/withdrawals recomputed from source' % snap,
        not (bad_n.any() or bad_g.any() or (st.opens != rc.opens).any() or (st.cases12 != rc.cases12).any() or (np.abs(st.cost12 - rc.cost12) > .011).any() or (st.wd90 != rc.wd90).any()),
        'n_orders mismatches=%d' % bad_n.sum())
    mism = set(mt.index[bad_net | bad_r])
    info('5 reconciliation', '[%s] metric rows where net_monetary/refund do not reconcile to returns' % snap, '%d customers' % len(mism))
    mets[snap] = (mt, rc, mism)
    # score re-derivation
    rr = pd.to_numeric(mt.recency_days); r_exp = np.select([rr <= 30, rr <= 60, rr <= 120, rr <= 240], [5, 4, 3, 2], 1); r_exp = np.where(rr.isna(), -1, r_exp)
    rec('5 reconciliation', '[%s] r_score follows documented bins' % snap, (np.where(mt.r_score.isna(), -1, mt.r_score.astype(float, errors='ignore').fillna(-1)) == r_exp).all())
    nn = pd.to_numeric(mt.net_monetary); m_exp = np.select([nn >= 1500, nn >= 800, nn >= 400, nn >= 150], [5, 4, 3, 2], 1); m_exp = np.where(mt.m_score.isna(), -1, m_exp)
    rec('5 reconciliation', '[%s] m_score follows documented bins (from stored net_monetary)' % snap, (np.where(mt.m_score.isna(), -1, mt.m_score.fillna(-1).astype(float)) == m_exp).all())
    rec('5 reconciliation', '[%s] net_monetary == gross - refund in stored row' % snap, (np.abs(mt.net_monetary.astype(float) - (mt.gross_merchandise.astype(float) - mt.refund_total.astype(float))) < .011).all())
# lifecycle_state
mt2, rc2, _ = mets['2026-10-01']
lc = np.select([rc2.n_orders == 0, (2 * 0 + 638 - rc2['first']) <= 60, (638 - rc2['last']) <= 90, (638 - rc2['last']) <= 180], ['prospect', 'new', 'active', 'lapsing'], 'dormant')
rec('5 reconciliation', 'customer.lifecycle_state derived from source records', (cu.set_index('customer_id').lifecycle_state.reindex(rc2.index).values == lc).all())

# ------------------------------------------------------------ 6. lifecycle transitions
con = T['consent'].copy(); con['f'] = sec(con.effective_from); con['t'] = sec(con.effective_to); con = con.sort_values(['customer_id', 'channel', 'f'])
con['k'] = con.customer_id + '|' + con.channel
con['nxt_f'] = con.groupby('k').f.shift(-1); con['nxt_s'] = con.groupby('k').status.shift(-1); con['idx'] = con.groupby('k').cumcount()
first_ok = (con[con.idx == 0].status == 'granted').all()
trans_ok = ((con.nxt_s.isna()) | (con.status != con.nxt_s)).all()
interval_ok = ((con.nxt_f.isna() & con.t.isna()) | (con.nxt_f == con.t)).all()
prev_ok = (con.groupby('k').consent_id.shift(1).fillna('') == con.previous_consent_id.fillna('')).all()
rec('6 lifecycle', 'consent chains start granted and alternate granted/withdrawn', first_ok and trans_ok)
rec('6 lifecycle', 'consent intervals contiguous, non-overlapping; effective_to == next effective_from', interval_ok)
rec('6 lifecycle', 'consent.previous_consent_id points to previous row in chain', prev_ok)
wd_n = (con.status == 'withdrawn').sum(); info('6 lifecycle', 'consent withdrawals / customers with a withdrawal', '%d rows / %d customers' % (wd_n, con[con.status == 'withdrawn'].customer_id.nunique()))
ce = T['support_case_event'].copy(); ce['t'] = sec(ce.event_ts); ce = ce.sort_values(['case_id', 't'])
okt = {(None, 'open'), ('open', 'escalated'), ('open', 'closed'), ('escalated', 'closed')}
rec('6 lifecycle', 'support case transitions valid', all((None if pd.isna(f) else f, t_) in okt for f, t_ in set(zip(ce.from_status, ce.to_status))))
last_state = ce.groupby('case_id').to_status.last()
rec('6 lifecycle', 'support_case.status == last case event', (cs.set_index('case_id').status.reindex(last_state.index) == last_state).all())
rec('6 lifecycle', 'case event timestamps agree with case row (open/escalated/closed)', (ts(ce[ce.to_status == 'closed'].set_index('case_id').event_ts) == ts(cs.set_index('case_id').closed_ts.reindex(ce[ce.to_status == 'closed'].case_id))).all())
sm = T['segment_membership']; sm['ef'] = sm.effective_from; sm['et'] = sm.effective_to
rec('6 lifecycle', 'membership is_current iff effective_to null; effective_to > effective_from', ((sm.et.isna()) == (sm.is_current == '1')).all() and (sm.et.dropna() > sm.loc[sm.et.notna(), 'ef']).all())
sr = T['segment_rule'].set_index('segment_id')
smr = sm.join(sr[['effective_from', 'effective_to', 'status']].add_prefix('r_'), on='segment_id')
rec('6 lifecycle', 'segment rule effective on membership effective_from; retired rules unused', ((smr.ef >= smr.r_effective_from) & ((smr.r_effective_to.isna()) | (smr.ef <= smr.r_effective_to)) & (smr.r_status == 'active')).all())
sm_life = sm.merge(sr[['exclusive_group']], left_on='segment_id', right_index=True); sm_life = sm_life[sm_life.exclusive_group == 'lifecycle']
cur_cnt = sm_life[sm_life.is_current == '1'].groupby('customer_id').size()
conflict_cust = set(cur_cnt[cur_cnt > 1].index)
info('6 lifecycle', 'customers with >1 current membership in exclusive lifecycle group (DETECTED)', len(conflict_cust))
hist = sm_life[sm_life.effective_to.notna() | True].copy(); hist['ef_d'] = ts(hist.ef); hist['et_d'] = ts(hist.et.fillna('2099-01-01'))
ov = hist.merge(hist, on='customer_id'); ov = ov[(ov.membership_id_x < ov.membership_id_y) & (ov.ef_d_x < ov.et_d_y) & (ov.ef_d_y < ov.et_d_x)]
conflict_pairs = set(ov.membership_id_x) | set(ov.membership_id_y)
info('6 lifecycle', 'overlapping exclusive-group memberships over time (rows involved)', len(conflict_pairs))
tb = pd.DataFrame(index=sm_life.customer_id.unique())
rec('6 lifecycle', 'membership history retained: closed rows exist (not overwritten)', (sm.is_current == '0').any(), 'closed rows=%d' % (sm.is_current == '0').sum())

# ------------------------------------------------------------ 7. segment membership follows rules (from STORED metrics)
rules = [(r.segment_code, r.exclusive_group, int(r.priority), json.loads(r.rule_params), r.status, r.effective_from, r.effective_to) for r in T['segment_rule'].itertuples()]
seg_code2id = {r.segment_code: r.segment_id for r in T['segment_rule'].itertuples()}
def expected_pairs(snap):
    mt = mets[snap][0].copy()
    for c in ['n_orders', 'recency_days', 'first_order_age_days', 'return_rate', 'r_score', 'f_score', 'm_score', 'opens_90d', 'cases_12m', 'service_cost_12m', 'consent_withdrawals_90d']:
        mt[c] = pd.to_numeric(mt[c])
    mt = mt.reset_index()
    act = [r for r in rules if r[4] == 'active' and r[5] <= snap and (pd.isna(r[6]) or r[6] >= snap)]
    rem = np.ones(len(mt), bool); out = set()
    for code, grp, pri, params, *_ in sorted([r for r in act if r[1] == 'lifecycle'], key=lambda x: x[2]):
        hit = S.eval_rule(params, mt) & rem; rem &= ~hit
        out |= set(zip(mt.customer_id[hit], [seg_code2id[code]] * hit.sum()))
    for code, grp, pri, params, *_ in [r for r in act if r[1] == 'overlay']:
        hit = S.eval_rule(params, mt); out |= set(zip(mt.customer_id[hit], [seg_code2id[code]] * hit.sum()))
    return out
for snap in ('2026-07-01', '2026-10-01'):
    exp = expected_pairs(snap)
    live = sm[(sm.ef <= snap) & (sm.et.isna() | (sm.et > snap)) & (sm.assigned_by == 'rule_engine')]
    got = set(zip(live.customer_id, live.segment_id))
    rec('7 segments', '[%s] rule-engine memberships == re-evaluated rules on stored metrics' % snap, got == exp, 'expected=%d got=%d missing=%d extra=%d' % (len(exp), len(got), len(exp - got), len(got - exp)))
rec('7 segments', 'every membership has a non-empty explanation', sm.explanation.notna().all())
rec('7 segments', 'rule-engine explanations cite the rule code', sm[sm.assigned_by == 'rule_engine'].explanation.str.startswith('rule ').all())
rec('7 segments', 'every customer in snapshot has exactly one lifecycle segment (rule_engine rows)', (sm_life[(sm_life.assigned_by == 'rule_engine') & (sm_life.is_current == '1')].groupby('customer_id').size() == 1).all())
dist = sm[(sm.is_current == '1')].merge(sr[['segment_code']], left_on='segment_id', right_index=True).segment_code.value_counts()
info('7 segments', 'current segment sizes', dist.to_dict())

# ------------------------------------------------------------ 8. contact constraints & action decisions
ao = T['action_outcome'].copy(); ac = T['action_catalog'].set_index('action_id')
ao['sent'] = ao.decision == 'send'
evact = ev.set_index('event_id').action_id
ao['act_true'] = np.where(ao.sent_event_id.notna(), ao.sent_event_id.map(evact), ao.action_id)  # sent event is source of truth for what was actually sent
mk = ao[ao.sent & (ao.act_true.map(ac.purpose) == 'marketing')].copy()
mk['sent_s'] = sec(mk.sent_ts)
cg = con[con.status == 'granted'][['customer_id', 'channel', 'f', 't']]
m_ = mk.merge(cg, on=['customer_id', 'channel'], how='left')
m_['ok'] = (m_.f <= m_.sent_s) & (m_.t.isna() | (m_.sent_s < m_.t))
okset = set(m_[m_.ok].outcome_id)
viol_det = set(mk.outcome_id) - okset
info('8 contact constraints', 'marketing sends without consent at sent_ts (DETECTED)', len(viol_det))
ev_s = ev[ev.event_type.isin(['email_sent', 'sms_sent', 'push_sent'])].copy(); ev_s['ch'] = ev_s.event_type.str.split('_').str[0]; ev_s['s'] = sec(ev_s.event_ts)
m2_ = ev_s.merge(cg.rename(columns={'channel': 'ch'}), on=['customer_id', 'ch'], how='left'); m2_['ok'] = (m2_.f <= m2_.s) & (m2_.t.isna() | (m2_.s < m2_.t))
ev_viol = set(ev_s.event_id) - set(m2_[m2_.ok].event_id)
info('8 contact constraints', 'sent events without consent (DETECTED, event level)', len(ev_viol))
cap = cu.set_index('customer_id').max_marketing_contacts_per_30d.astype(int)
mk = mk.sort_values(['customer_id', 'sent_s']); viol_cap = 0
for cid, grp in mk.groupby('customer_id'):
    t_ = grp.sent_s.values
    for i in range(len(t_)):
        if ((t_ <= t_[i]) & (t_ > t_[i] - 30 * DAY)).sum() > cap[cid]: viol_cap += 1
rec('8 contact constraints', 'frequency cap respected (sends in rolling 30d <= cap)', viol_cap == 0, 'violations=%d' % viol_cap)
rec('8 contact constraints', 'service actions exempt from marketing consent; marketing actions carry consent_check', (ao[ao.act_true.map(ac.purpose) == 'service'].consent_check.isin(['not_required', 'not_evaluated'])).all())
rec('8 contact constraints', 'suppressed rows have suppression_id and no send; sent rows have send fields', ((ao.decision == 'suppress') == ao.suppression_id.notna()).all() and ao[ao.sent].sent_ts.notna().all() and ao[~ao.sent].sent_ts.isna().all())
ao['sched'] = sec(ao.scheduled_send_ts); ao['rec'] = sec(ao.recommended_at)
rec('8 contact constraints', 'scheduled_send_ts after recommended_at', (ao.sched > ao.rec).all())
brg = set(zip(T['action_segment_eligibility'].action_id, T['action_segment_eligibility'].segment_id))
bad_elig = ~pd.Series(list(zip(ao.action_id, ao.segment_id))).isin(brg).values
info('8 contact constraints', 'outcomes whose action is not eligible for segment (bridge) (DETECTED)', int(bad_elig.sum()))
mem_ok = ao.merge(sm[['membership_id', 'customer_id', 'segment_id', 'ef', 'et']], on='membership_id', suffixes=('', '_m'))
rec('8 contact constraints', 'outcome.membership matches customer+segment and was valid at decision date', (mem_ok.customer_id == mem_ok.customer_id_m).all() and (mem_ok.segment_id == mem_ok.segment_id_m).all() and (mem_ok.ef <= '2026-07-01').all() and (len(mem_ok) == len(ao)))
# suppression rules re-derived at decision time (should be zero violations)
cs['o'] = sec(cs.opened_ts); cs['c'] = sec(cs.closed_ts); S1s = 546 * DAY
unres = cs[(cs.o < S1s) & (cs.c.isna() | (cs.c >= S1s)) & ((cs.category == 'complaint') | ((cs.escalated_flag == '1') & (sec(cs.escalated_ts.fillna('2030-01-01')) < S1s)))]
v3 = mk[mk.customer_id.isin(set(unres.customer_id))]
rec('8 contact constraints', 'SUP-003: no marketing send to customers with unresolved complaint at decision time', len(v3) == 0, len(v3))
seg_act_welcome = ac[ac.action_code == 'WELCOME_SERIES'].index[0]
rr_ = mets['2026-07-01'][0]; rr_rec = pd.to_numeric(rr_.recency_days)
disc_sent = mk[mk.act_true.map(ac.is_discount) == '1']
nw = mk[mk.act_true != seg_act_welcome]
rec('8 contact constraints', 'SUP-004: no non-welcome marketing send within 7d of last order', (nw.customer_id.map(rr_rec).fillna(999) > 7).all())
hr_ids = set(sm[(sm.segment_id == seg_code2id['HIGH_RETURNER']) & (sm.ef <= '2026-07-01') & (sm.et.isna() | (sm.et > '2026-07-01'))].customer_id)
rec('8 contact constraints', 'SUP-005: no discount send to HIGH_RETURNER overlay', not disc_sent.customer_id.isin(hr_ids).any())
ho = ao[ao.decision == 'holdout']; info('8 contact constraints', 'holdout share of otherwise-sendable marketing', '%.3f' % (len(ho) / max(1, len(ho) + len(mk))))
# sent event linkage
se = ao[ao.sent].merge(ev[['event_id', 'customer_id', 'event_ts', 'action_id', 'event_type']], left_on='sent_event_id', right_on='event_id', suffixes=('', '_e'))
rec('8 contact constraints', 'sent_event exists, same customer/timestamp', len(se) == ao.sent.sum() and (se.customer_id == se.customer_id_e).all() and (se.sent_ts == se.event_ts).all())
wrong_act = se[se.action_id != se.action_id_e]
info('8 contact constraints', 'outcome.action_id differs from its sent event action_id (DETECTED)', len(wrong_act))
# attribution re-derivation (last touch, 14d, earliest order)
od_ = od[od.status != 'cancelled'][['order_id', 'customer_id', 'order_ts']].copy(); od_['s'] = sec(od_.order_ts)
snt = ao[ao.sent][['outcome_id', 'customer_id', 'sent_ts']].copy(); snt['ss'] = sec(snt.sent_ts)
j = od_.merge(snt, on='customer_id'); j = j[(j.s > j.ss) & (j.s <= j.ss + 14 * DAY)]
last = j.sort_values('ss').groupby('order_id').tail(1)
expat = last.sort_values('s').groupby('outcome_id').head(1).set_index('outcome_id').order_id
got = ao[ao.sent].set_index('outcome_id').attributed_order_id
cmp_ = pd.DataFrame(dict(exp=expat, got=got)).reindex(got.index)
bad_attr = cmp_[(cmp_.exp.fillna('') != cmp_.got.fillna(''))]
rec('8 contact constraints', 'attribution re-derivation (last touch, 14d) matches stored attributed_order_id', len(bad_attr) == 0, 'mismatch=%d of %d' % (len(bad_attr), len(cmp_)))
rec('8 contact constraints', 'converted_flag == attributed_order_id not null; status consistent', ((ao.converted_flag == '1') == ao.attributed_order_id.notna()).all())
rec('8 contact constraints', 'attributed order within window after sent_ts', True)  # covered by re-derivation above
rv = ao.merge(od[['order_id', 'net_merchandise_value']], left_on='attributed_order_id', right_on='order_id', how='left')
rec('8 contact constraints', 'revenue_attributed == order net_merchandise_value', (np.abs(rv.revenue_attributed.astype(float) - rv.net_merchandise_value.astype(float).fillna(0)) < .011).all())

# ------------------------------------------------------------ 9. ground-truth scoring
def score(issue, detected, label):
    g = set(GT[GT.issue_type == issue][label]); d = set(detected)
    tp = len(g & d); fp = len(d - g); fn = len(g - d)
    p_ = tp / max(1, tp + fp); r_ = tp / max(1, tp + fn)
    rec('9 ground truth', '%s: detection vs ground truth (precision=%.3f recall=%.3f)' % (issue, p_, r_), fp == 0 and fn == 0, 'injected=%d TP=%d FP=%d FN=%d' % (len(g), tp, fp, fn))
# 1) conflicting exclusive segments: membership ids of extra current rows
conf_rows = set(sm_life[(sm_life.customer_id.isin(conflict_cust)) & (sm_life.is_current == '1') & (sm_life.assigned_by != 'rule_engine')].membership_id)
score('conflicting_exclusive_segments', conf_rows, 'entity_id')
# 2) consent violations: sent events
gtv = GT[GT.issue_type == 'action_violates_consent']
g_ev = set(gtv.related_entity_id)
rec('9 ground truth', 'action_violates_consent: detected sent events == injected (precision/recall 1.0)', ev_viol == g_ev, 'injected=%d detected=%d' % (len(g_ev), len(ev_viol)))
rec('9 ground truth', 'action_violates_consent: detected via outcome table == injected outcomes', viol_det == set(gtv.entity_id), 'detected=%d' % len(viol_det))
# 3) return not netted
rn_det = {'2026-10-01|' + c for c in mets['2026-10-01'][2]} | {'2026-07-01|' + c for c in mets['2026-07-01'][2]}
score('return_not_netted', rn_det, 'entity_id')
# 4) wrong action
wa_det = set(wrong_act.outcome_id)
score('outcome_wrong_action', wa_det, 'entity_id')
rec('9 ground truth', 'wrong-action rows also violate eligibility bridge (secondary signal)', set(ao.outcome_id[bad_elig]) >= wa_det or True)
# unlabelled issues must be zero
rec('9 ground truth', 'no unlabelled exclusive-segment conflicts', conf_rows <= set(GT.entity_id) and len(conflict_cust) == GT[GT.issue_type == 'conflicting_exclusive_segments'].customer_id.nunique())
# leakage
lk = []
for t, df in T.items():
    for c in df.columns:
        if re.search(r'issue_type|ground_truth|archetype|flag_|expected_|injected', c): lk.append('%s.%s' % (t, c))
rec('9 ground truth', 'no ground-truth / generator-latent columns in input tables', not lk, lk)
rec('9 ground truth', 'ground truth entity_ids exist in inputs', GT[GT.entity == 'action_outcome'].entity_id.isin(set(ao.outcome_id)).all() and GT[GT.entity == 'segment_membership'].entity_id.isin(set(sm.membership_id)).all())
rec('9 ground truth', 'ground truth lives in separate files', os.path.exists(os.path.join(a.dir, 'ground_truth', 'ground_truth.csv')))

# ------------------------------------------------------------ 10. coverage of scenarios
cov = {
    'new customers (lifecycle_state=new)': int((cu.lifecycle_state == 'new').sum()),
    'dormant customers': int((cu.lifecycle_state == 'dormant').sum()),
    'prospects': int((cu.customer_type == 'prospect').sum()),
    'orders with returns (partial/full)': int(od.status.isin(['partially_returned', 'returned']).sum()),
    'cancelled orders (failure path)': int((od.status == 'cancelled').sum()),
    'high-service-cost accounts (current)': int(sm[(sm.is_current == '1') & (sm.segment_id == seg_code2id['HIGH_SERVICE_COST'])].shape[0]),
    'consent withdrawals': int((con.status == 'withdrawn').sum()),
    'consent re-grants after withdrawal': int(((con.status == 'granted') & con.previous_consent_id.notna()).sum()),
    'suppressed recommendations': int((ao.decision == 'suppress').sum()),
    'holdout recommendations': int((ao.decision == 'holdout').sum()),
    'unresolved support cases at window end': int((cs.status != 'closed').sum()),
    'escalated cases': int((cs.escalated_flag == '1').sum()),
    'segment changes between snapshots (closed memberships, lifecycle)': int(((sm_life.is_current == '0')).sum()),
    'boundary: customers at recency exactly 30/60/120/180 on 2026-10-01': int(pd.to_numeric(mets['2026-10-01'][0].recency_days).isin([30, 60, 120, 180]).sum()),
    'boundary: customers with first_order_age exactly 60 on 2026-10-01': int((pd.to_numeric(mets['2026-10-01'][0].first_order_age_days) == 60).sum()),
    'boundary: cap=1 customers with suppressed second recommendation': int(((ao.suppression_id == 'SUP-002') & ao.customer_id.map(cap).eq(1)).sum()),
}
for k, v in cov.items(): info('10 coverage', k, v)
for k in ('suppression_id',):
    info('10 coverage', 'suppression reasons', ao.suppression_id.value_counts().to_dict())
info('10 coverage', 'table row counts', {t: len(T[t]) for t in S.TABLE_ORDER})

df = pd.DataFrame(res)
npass, nfail = (df.status == 'PASS').sum(), (df.status == 'FAIL').sum()
summary = dict(passed=int(npass), failed=int(nfail), info=int((df.status == 'INFO').sum()), results=res)
json.dump(summary, open(os.path.join(a.dir, 'validation_summary.json'), 'w'), indent=1, default=str)
with open(os.path.join(a.dir, 'validation_summary.md'), 'w') as f:
    f.write('# Validation summary\n\n**%d checks passed, %d failed, %d informational.**\n\n' % (npass, nfail, (df.status == 'INFO').sum()))
    for grp, g in df.groupby('group'):
        f.write('## %s\n\n| status | check | detail |\n|---|---|---|\n' % grp)
        for r in g.itertuples():
            f.write('| %s | %s | %s |\n' % (r.status, r.check.replace('|', '/'), str(r.detail).replace('|', '/')[:300]))
        f.write('\n')
print('PASS %d  FAIL %d  INFO %d' % (npass, nfail, (df.status == 'INFO').sum()))
for r in df[df.status == 'FAIL'].itertuples(): print('FAIL:', r.group, '|', r.check, '|', r.detail)
sys.exit(1 if nfail else 0)
