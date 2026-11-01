#!/usr/bin/env python3
"""Measurable outputs: segment quality, action funnel, holdout lift, ROI, compliance. Reads exported CSVs only (ground truth used only for the DQ-detection table)."""
import argparse, json, os
import numpy as np, pandas as pd
import schema_spec as S

ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='output'); a = ap.parse_args()
D = os.path.join(a.dir, 'data')
rd = lambda t: pd.read_csv(os.path.join(D, t + '.csv'), low_memory=False)
od, ln, pr, ao, sm, sr, ac, cu = [rd(t) for t in ('orders', 'order_line', 'product', 'action_outcome', 'segment_membership', 'segment_rule', 'action_catalog', 'customer')]
ev = pd.read_csv(os.path.join(D, 'engagement_event.csv'), usecols=['event_id', 'action_id'], dtype=str, low_memory=False)
R = {}
S1D = '2026-07-01'
# ------------------------------------------------ A. segment quality (predictive validity of the S1 segments on the following 90 days)
life = sr[sr.exclusive_group == 'lifecycle'].set_index('segment_id').segment_code
cur = sm[(sm.effective_from <= S1D) & (sm.effective_to.isna() | (sm.effective_to > S1D)) & (sm.assigned_by == 'rule_engine') & sm.segment_id.isin(life.index)].copy()
cur['seg'] = cur.segment_id.map(life)
o = od[(od.status != 'cancelled') & (od.order_ts >= S1D)]
fut = o.groupby('customer_id').agg(fut_orders=('order_id', 'count'), fut_net=('net_merchandise_value', 'sum'))
cur = cur.join(fut, on='customer_id'); cur[['fut_orders', 'fut_net']] = cur[['fut_orders', 'fut_net']].fillna(0)
cur['bought'] = cur.fut_orders > 0
seg_tbl = cur.groupby('seg').agg(customers=('customer_id', 'count'), pct_bought_next_90d=('bought', 'mean'), orders_per_customer=('fut_orders', 'mean'), net_spend_per_customer=('fut_net', 'mean')).round(3)
seg_tbl['share_of_customers'] = (seg_tbl.customers / seg_tbl.customers.sum()).round(3)
seg_tbl = seg_tbl.sort_values('net_spend_per_customer', ascending=False)
grand = cur.fut_net.mean(); ssb = (cur.groupby('seg').fut_net.agg(['count', 'mean']).pipe(lambda x: (x['count'] * (x['mean'] - grand) ** 2).sum())); sst = ((cur.fut_net - grand) ** 2).sum()
R['segment_quality'] = dict(table=seg_tbl.reset_index().to_dict('records'), eta_squared_future_spend_explained_by_segment=round(float(ssb / sst), 4))
# ------------------------------------------------ B. action funnel + holdout lift + ROI
ao['act_true'] = ao.sent_event_id.map(ev.set_index('event_id').action_id).fillna(ao.action_id)
acm = ac.set_index('action_id'); ao['code'] = ao.act_true.map(acm.action_code)
mrg = ln.merge(pr[['product_id', 'list_price', 'unit_cost']], on='product_id'); mrg = mrg[mrg.returned_quantity == 0]
margin = 1 - (mrg.quantity * mrg.unit_cost).sum() / mrg.line_net_amount.sum() if False else 1 - (mrg.quantity * mrg.unit_cost).sum() / (mrg.quantity * mrg.unit_price).sum()
R['gross_margin_rate_used'] = round(float(margin), 4)
rows = []
for code, g in ao.groupby('code'):
    t = g[g.experiment_group == 'treatment']; h = g[g.experiment_group == 'holdout']
    sent = g[g.decision == 'send']
    row = dict(action=code, recommended=len(g), suppressed=int((g.decision == 'suppress').sum()), holdout=len(h), sent=len(sent),
               open_rate=round(float(sent.opened_ts.notna().mean()), 4) if len(sent) else None, click_rate=round(float(sent.clicked_ts.notna().mean()), 4) if len(sent) else None)
    if len(t) and len(h):
        pt, ph = t.converted_flag.mean(), h.converted_flag.mean()
        se = np.sqrt(pt * (1 - pt) / len(t) + ph * (1 - ph) / len(h))
        inc_conv = (pt - ph) * len(t); inc_rev = (t.revenue_attributed.mean() - h.revenue_attributed.mean()) * len(t)
        cost = t.action_cost.sum() + t.discount_cost.sum()
        row.update(treated_conv=round(float(pt), 4), holdout_conv=round(float(ph), 4), abs_lift=round(float(pt - ph), 4), lift_ci95=[round(float(pt - ph - 1.96 * se), 4), round(float(pt - ph + 1.96 * se), 4)],
                   z=round(float((pt - ph) / se), 2), incremental_orders=round(float(inc_conv), 1), incremental_net_revenue=round(float(inc_rev), 2),
                   incremental_gross_profit=round(float(inc_rev * margin), 2), action_plus_discount_cost=round(float(cost), 2),
                   roi=round(float((inc_rev * margin - cost) / cost), 2) if cost > 0 else None)
    else:
        row.update(note='no holdout (operational/service action or n too small)', converted=round(float(sent.converted_flag.mean()), 4) if len(sent) else None)
    rows.append(row)
R['action_performance'] = rows
sup = ao[ao.decision == 'suppress'].suppression_id.value_counts().to_dict()
R['suppression_breakdown'] = sup
sup_codes = rd('suppression_rule').set_index('suppression_id').suppression_code
R['suppression_breakdown_named'] = {sup_codes[k]: int(v) for k, v in sup.items()}
R['funnel_overall'] = dict(recommendations=len(ao), suppressed=int((ao.decision == 'suppress').sum()), holdout=int((ao.decision == 'holdout').sum()), sent=int((ao.decision == 'send').sum()),
                           opened=int(ao.opened_ts.notna().sum()), clicked=int(ao.clicked_ts.notna().sum()), converted_sent=int(((ao.decision == 'send') & (ao.converted_flag == 1)).sum()))
# ------------------------------------------------ C. compliance
val = json.load(open(os.path.join(a.dir, 'validation_summary.json'))) if os.path.exists(os.path.join(a.dir, 'validation_summary.json')) else None
gt = pd.read_csv(os.path.join(a.dir, 'ground_truth', 'ground_truth.csv'))
nviol = int((gt.issue_type == 'action_violates_consent').sum()); nsent_m = int(((ao.decision == 'send') & (ao.act_true.map(acm.purpose) == 'marketing')).sum())
R['compliance'] = dict(marketing_sends=nsent_m, consent_violations_injected_and_detected=nviol, consent_compliance_rate=round(1 - nviol / nsent_m, 5),
                       sends_blocked_for_missing_consent=int(sup.get('SUP-001', 0)), sends_blocked_by_frequency_cap=int(sup.get('SUP-002', 0)),
                       memberships_with_explanation_pct=round(float(sm.explanation.notna().mean()) * 100, 2))
R['data_quality_detection'] = [dict(issue=k, injected=int(v)) for k, v in gt.groupby('issue_type').size().items()]
if val:
    R['validation'] = dict(passed=val['passed'], failed=val['failed'])
json.dump(R, open(os.path.join(a.dir, 'evaluation_report.json'), 'w'), indent=1)
with open(os.path.join(a.dir, 'evaluation_report.md'), 'w') as f:
    f.write('# Evaluation report (generated)\n\n## A. Segment quality: do snapshot-1 (2026-07-01) segments predict the next 90 days?\n\n')
    f.write(seg_tbl.reset_index().to_markdown(index=False) + '\n\n')
    f.write('Eta-squared (share of next-90-day spend variance explained by lifecycle segment): **%.3f**\n\n' % R['segment_quality']['eta_squared_future_spend_explained_by_segment'])
    f.write('## B. Action performance (treatment vs random 10%% holdout; 14-day last-touch attribution; gross margin %.1f%%)\n\n' % (margin * 100))
    cols = ['action', 'recommended', 'suppressed', 'holdout', 'sent', 'open_rate', 'click_rate', 'treated_conv', 'holdout_conv', 'abs_lift', 'lift_ci95', 'z', 'incremental_orders', 'incremental_net_revenue', 'action_plus_discount_cost', 'roi']
    f.write(pd.DataFrame(rows).reindex(columns=cols).to_markdown(index=False) + '\n\n')
    f.write('## C. Suppression & compliance\n\n```json\n' + json.dumps(dict(suppression=R['suppression_breakdown_named'], funnel=R['funnel_overall'], compliance=R['compliance']), indent=1) + '\n```\n')
print(seg_tbl.to_string()); print(pd.DataFrame(rows).reindex(columns=cols).to_string()); print(R['compliance'], R['suppression_breakdown_named'])
