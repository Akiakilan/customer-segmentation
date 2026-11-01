#!/usr/bin/env python3
"""Explainable customer segmentation & next-best-action synthetic data generator.

Same code builds the starter and full datasets: only --n-customers / --n-orders / --n-events change.
Deterministic: every random stream is spawned from one SeedSequence(seed); no wall-clock or hash-order dependence.

Timeline (day index 0 = 2025-01-01):  data window 2025-01-01..2026-09-30
  snapshot 1 = 2026-07-01 (day 546): segments evaluated, actions recommended/sent, outcomes observed afterwards
  snapshot 2 = 2026-10-01 (day 638): current segments (end of window)
"""
import argparse, os, json, hashlib, gzip, sqlite3, time, sys, platform
import numpy as np
import pandas as pd
from types import SimpleNamespace as NS
import schema_spec as S

DAY = 86400
S1, S2 = 546, 638
D_END = 638
END_SEC = D_END * DAY
W0 = np.datetime64('2025-01-01')
T0 = np.datetime64('2025-01-01T00:00:00')
A_PROS, A_NEW, A_DORM, A_LOY, A_REG, A_OCC = range(6)
ARCH_NAMES = np.array(['prospect', 'new', 'dormant', 'loyal', 'regular', 'occasional'])
CC = S.CHANNELS_CONTACT                      # contact channels, index used in arrays
ET = {n: i for i, n in enumerate(S.EVENT_TYPES)}
ECH = {n: i for i, n in enumerate(S.EVENT_CH)}
SENT_ET = {'email': 'email_sent', 'sms': 'sms_sent', 'push': 'push_sent', 'phone': 'call_attempt'}
OPEN_ET = {'email': 'email_open', 'push': 'push_open', 'phone': 'call_connected'}
CLICK_ET = {'email': 'email_click', 'sms': 'sms_click'}


# ------------------------------------------------------------------ helpers
def dfmt(day):
    day = np.asarray(day, dtype='float64'); out = np.full(day.shape, None, dtype=object); ok = ~np.isnan(day)
    if ok.any():
        out[ok] = np.datetime_as_string(W0 + day[ok].astype('int64').astype('timedelta64[D]'), unit='D')
    return out

def tfmt(sec):
    sec = np.asarray(sec, dtype='float64'); out = np.full(sec.shape, None, dtype=object); ok = ~np.isnan(sec)
    if ok.any():
        s = np.datetime_as_string(T0 + sec[ok].astype('int64').astype('timedelta64[s]'), unit='s')
        out[ok] = np.char.replace(s, 'T', ' ')
    return out

def mk_ids(prefix, start, n, width):
    return np.char.add(prefix, np.char.zfill(np.arange(start, start + n).astype(str), width)).astype(object)

def money(c):
    return np.round(np.asarray(c, dtype='float64') / 100.0, 2)

def log(msg):
    print('[%7.1fs] %s' % (time.time() - LOG_T0, msg), flush=True)
LOG_T0 = time.time()


# ------------------------------------------------------------------ calendar / sampling
def build_calendar():
    d = np.arange(D_END)
    dates = W0 + d.astype('timedelta64[D]')
    month = dates.astype('datetime64[M]').astype(int) % 12 + 1
    mf = np.array([0, .90, .85, .95, 1.0, 1.0, .95, .95, 1.0, 1.05, 1.10, 1.40, 1.55])[month]
    wf = np.where(((d + 2) % 7) >= 5, 1.15, 1.0)             # 2025-01-01 is a Wednesday
    dens = mf * wf * (1 + 0.0006 * d)
    return np.concatenate([[0.0], np.cumsum(dens)])

def sample_days(r, C, lo, hi):
    a = C[lo]; b = C[hi + 1]
    t = a + r.random(len(lo)) * (b - a)
    d = np.searchsorted(C, t, side='right') - 1
    return np.clip(d, lo, hi).astype(np.int64)

def sod(r, n):  # seconds of day for behavioural events
    return np.where(r.random(n) < .7, r.integers(8 * 3600, 23 * 3600, size=n), r.integers(0, DAY, size=n))


# ------------------------------------------------------------------ master data
def make_customers(R, n):
    r = R['cust']
    arch = r.choice(6, size=n, p=[.08, .06, .16, .10, .35, .25])
    signup = np.zeros(n, np.int64); last_active = np.full(n, 637, np.int64)
    m = arch == A_NEW; signup[m] = r.integers(572, 631, size=m.sum())
    m = arch == A_DORM; k = m.sum(); la = r.integers(30, 455, size=k); last_active[m] = la
    signup[m] = (-900 + (la + 900) * r.random(k)).astype(np.int64)
    m = arch == A_PROS; k = m.sum(); signup[m] = (-900 + 1530 * r.beta(1.2, 1, size=k)).astype(np.int64)
    m = np.isin(arch, [A_LOY, A_REG, A_OCC]); k = m.sum(); signup[m] = (-900 + 1430 * r.beta(1.4, 1, size=k)).astype(np.int64)
    o = np.argsort(signup, kind='stable')
    arch, signup, last_active = arch[o], signup[o], last_active[o]
    g = NS(n=n, arch=arch, signup=signup, last_active=last_active)
    g.returner = (r.random(n) < .06) & (arch != A_PROS)
    g.high_service = r.random(n) < .07
    g.flag_wd = r.random(n) < .10
    rate = np.array([0, .4, 1.0, 5.0, 1.6, .6])[arch] * r.lognormal(0, .5, n)
    g.ord_rate = rate
    g.eng = np.array([.6, 2.0, .5, 4.0, 1.5, .7])[arch] * r.lognormal(0, .8, n)
    g.ev_hi = np.where(arch == A_DORM, np.minimum(637, last_active + 60), 637)
    g.case_hi = np.where(arch == A_DORM, np.minimum(637, last_active + 120), 637)
    g.region = np.array(S.REGIONS)[r.choice(5, n, p=[.35, .25, .25, .10, .05])]
    g.age = np.array(S.AGE_BANDS)[r.choice(5, n, p=[.12, .28, .27, .20, .13])]
    g.acq = np.array(S.ACQ)[r.choice(6, n, p=[.25, .2, .15, .1, .2, .1])]
    g.lang = np.array(S.LANGS)[r.choice(4, n, p=[.7, .12, .1, .08])]
    g.cap = r.choice([1, 2, 3, 4], size=n, p=[.2, .45, .25, .1])
    g.cust_id = mk_ids('CUS-', 1, n, 6)
    return g

def make_products(R, g, scale):
    r = R['prod']
    TAXO = [('Apparel', ['Tops', 'Bottoms', 'Outerwear', 'Footwear'], 45, .22, .22), ('Electronics', ['Audio', 'Wearables', 'Accessories'], 70, .06, .12),
            ('Home & Kitchen', ['Cookware', 'Decor', 'Storage'], 35, .08, .15), ('Beauty', ['Skincare', 'Haircare', 'Fragrance'], 25, .04, .14),
            ('Sports & Outdoors', ['Fitness', 'Camping', 'Cycling'], 40, .10, .12), ('Grocery & Gourmet', ['Pantry', 'Beverages', 'Snacks'], 12, .01, .12),
            ('Toys & Games', ['Games', 'Puzzles'], 22, .07, .07), ('Pet Supplies', ['Pet Food', 'Pet Accessories'], 20, .03, .06)]
    npd = max(60, int(300 * scale))
    cat = r.choice(8, size=npd, p=[t[4] for t in TAXO])
    sub = np.array([TAXO[c][1][r.integers(len(TAXO[c][1]))] for c in cat])
    med = np.array([TAXO[c][2] for c in cat])
    price = np.maximum(3.99, np.floor(med * r.lognormal(0, .5, npd)) + .99)
    cost = np.round(price * r.uniform(.35, .65, npd), 2)
    launch = np.where(r.random(npd) < .8, r.integers(-1200, -30, npd), r.integers(10, 520, npd))
    disc = np.full(npd, np.inf)
    dm = r.random(npd) < .08
    disc[dm] = np.minimum(600, np.maximum(launch[dm], 0) + r.integers(60, 400, dm.sum()))
    pop = 1.0 / (r.permutation(npd) + 1.0) ** .8
    brand = np.array(['Brand-' + 'ABCDEFGH'[i] for i in r.integers(0, 8, npd)])
    pid = mk_ids('PRD-', 1, npd, 5)
    names = np.array(['%s %s %d' % (b, s, i + 1) for i, (b, s) in enumerate(zip(brand, sub))])
    g.p = NS(n=npd, id=pid, cat=cat, cat_name=np.array([t[0] for t in TAXO])[cat], sub=sub, brand=brand, price_c=np.rint(price * 100).astype(np.int64),
             cost=cost, launch=launch, disc=disc, pop=pop / pop.sum(), name=names,
             ret=np.array([t[3] for t in TAXO])[cat], always=np.where((launch < 0) & np.isinf(disc))[0])
    return g.p

def sample_products(r, p, days):
    n = len(days); out = np.empty(n, np.int64); todo = np.arange(n)
    for _ in range(40):
        cand = r.choice(p.n, size=len(todo), p=p.pop)
        ok = (p.launch[cand] <= days[todo]) & (p.disc[cand] >= days[todo])
        out[todo[ok]] = cand[ok]; todo = todo[~ok]
        if len(todo) == 0:
            return out
    out[todo] = r.choice(p.always, size=len(todo))
    return out


# ------------------------------------------------------------------ consent (append-only interval history)
def make_consent(R, g):
    r = R['consent']; n = g.n
    grant = r.random((n, 4)) < np.array([.75, .45, .18, .35])
    wd = g.flag_wd & (g.signup + 7 <= 637)
    grant[wd & ~grant.any(1), 0] = True
    wsel = wd[:, None] & grant & (r.random((n, 4)) < .7)
    fix = wd & ~wsel.any(1); wsel[fix, np.argmax(grant[fix], axis=1)] = True
    lo_w = np.maximum(g.signup + 7, 0); wday_c = r.integers(lo_w, 638)
    rows = []; key = 0
    f1 = np.full((n, 4), np.inf); t1 = np.full((n, 4), np.inf); f2 = np.full((n, 4), np.inf); t2 = np.full((n, 4), np.inf)
    wsrc = [(['unsubscribe_link', 'preference_center'], [.7, .3]), (['stop_reply', 'preference_center'], [.7, .3]),
            (['preference_center', 'support_agent'], [.6, .4]), (['preference_center', 'support_agent'], [.6, .4])]
    for j in range(4):
        gi = np.where(grant[:, j])[0]; k = len(gi)
        gfrom = g.signup[gi] * DAY + r.integers(0, 8 * 3600, size=k)
        gsrc = r.choice(['signup_form', 'app_prompt'], size=k)
        w = wsel[gi, j]
        day = np.where(r.random(k) < .6, wday_c[gi], r.integers(lo_w[gi], 638))
        wsec = day * DAY + r.integers(0, DAY, size=k)
        rg = w & (r.random(k) < .08) & (day + 20 <= 637)
        rgday = day + r.integers(20, np.maximum(np.minimum(120, 637 - day), 20) + 1)
        rgsec = rgday * DAY + r.integers(0, DAY, size=k)
        wsrcs = r.choice(wsrc[j][0], size=k, p=wsrc[j][1])
        gk = key + np.arange(k); key += k
        wk = key + np.arange(w.sum()); key += w.sum()
        rk = key + np.arange(rg.sum()); key += rg.sum()
        rows.append(pd.DataFrame(dict(key=gk, cidx=gi, ch=j, status='granted', f=gfrom, t=np.where(w, wsec, np.nan), src=gsrc, prev=-1)))
        rows.append(pd.DataFrame(dict(key=wk, cidx=gi[w], ch=j, status='withdrawn', f=wsec[w], t=np.where(rg[w], rgsec[w], np.nan), src=wsrcs[w], prev=gk[w])))
        rows.append(pd.DataFrame(dict(key=rk, cidx=gi[rg], ch=j, status='granted', f=rgsec[rg], t=np.nan, src='preference_center', prev=wk[rg[w]] if False else wk[np.cumsum(w)[rg] - 1])))
        f1[gi, j] = gfrom; t1[gi, j] = np.where(w, wsec, np.inf)
        f2[gi[rg], j] = rgsec[rg]
    con = pd.concat(rows, ignore_index=True)
    con = con.sort_values(['f', 'cidx', 'ch', 'key'], kind='stable').reset_index(drop=True)
    con['consent_id'] = mk_ids('CON-2026-', 1, len(con), 7)
    kmap = pd.Series(con['consent_id'].values, index=con['key'].values)
    con['prev_id'] = np.where(con['prev'] >= 0, kmap.reindex(con['prev'].values).values, None)
    g.con = con; g.cons = (f1, t1, f2, t2)
    pref = np.full(n, 'none', dtype=object)
    for j in [3, 1, 2, 0]:                 # lowest priority first so email ends up preferred
        pref[grant[:, j] & (f1[:, j] <= g.signup * DAY + 8 * 3600)] = CC[j]
    g.pref = pref; g.pref_idx = np.array([CC.index(x) if x != 'none' else -1 for x in pref])
    return con

def consented(g, ch, cidx, ts):
    f1, t1, f2, t2 = g.cons
    return ((f1[cidx, ch] <= ts) & (ts < t1[cidx, ch])) | ((f2[cidx, ch] <= ts) & (ts < t2[cidx, ch]))


# ------------------------------------------------------------------ orders / lines
def gen_orders(R, g, C, plo, phi, n_total, must):
    r = R['order']; n = g.n
    lo = np.maximum(np.maximum(g.signup, 0), plo); hi = np.minimum(g.last_active, phi)
    valid = (hi >= lo) & (g.arch != A_PROS)
    mass = np.where(valid, C[np.clip(hi + 1, 0, D_END)] - C[np.clip(lo, 0, D_END)], 0)
    w = np.where(valid, g.ord_rate * mass, 0.0)
    base = (valid & must).astype(np.int64)
    extra = r.multinomial(n_total - base.sum(), w / w.sum())
    cnt = base + extra
    cidx = np.repeat(np.arange(n), cnt); m = len(cidx)
    day = sample_days(r, C, lo[cidx], hi[cidx])
    pc = r.random(m) < .25
    pct = np.where(pc, r.choice([10, 15, 20, 30], size=m, p=[.4, .25, .25, .1]), 0)
    return pd.DataFrame(dict(cidx=cidx, day=day, sec=r.integers(8 * 3600, 22 * 3600, size=m), chn=r.choice(4, size=m, p=[.52, .30, .12, .06]),
                             promo_pct=pct, promo_code=np.where(pct > 0, ['SAVE%d' % p for p in pct], None), cancelled=r.random(m) < .022))

def finalize_orders(R, o, start):
    r = R['order']
    o = o.sort_values(['day', 'sec', 'cidx'], kind='stable').reset_index(drop=True)
    o['order_id'] = mk_ids('ORD-2026-', start, len(o), 6)
    o['ts_sec'] = o['day'] * DAY + o['sec']
    o['cancel_sec'] = np.where(o['cancelled'], np.minimum(o['ts_sec'] + r.integers(600, 2 * DAY, size=len(o)), END_SEC - 1), np.nan)
    return o

def gen_lines(R, g, o, start):
    r = R['line']; p = g.p; nO = len(o)
    lam = np.array([1.0, 1.0, 1.0, 1.4, 1.0, .8])[g.arch[o.cidx.values]]
    nl = np.minimum(1 + r.poisson(lam), 6)
    oi = np.repeat(np.arange(nO), nl); L = len(oi)
    ln = np.arange(L) - np.repeat(np.cumsum(nl) - nl, nl) + 1
    cidx = o.cidx.values[oi]; day = o.day.values[oi]
    prod = sample_products(r, p, day)
    qty = r.choice([1, 2, 3], size=L, p=[.78, .17, .05])
    unit = p.price_c[prod]; gross = qty * unit
    pct = o.promo_pct.values[oi]
    disc = np.rint(gross * pct / 100.0).astype(np.int64); net = gross - disc
    canc = o.cancelled.values[oi]
    pr = np.minimum(p.ret[prod] * np.where(g.returner[cidx], 2.5, 1.0), .75)
    ret = (r.random(L) < pr) & ~canc
    rq = np.where((qty > 1) & (r.random(L) < .2), r.integers(1, qty + 1), qty)
    rq = np.where(ret, rq, 0)
    rday = day + r.integers(3, 31, size=L)
    ok = ret & (rday <= D_END - 1)
    rq = np.where(ok, rq, 0); rday = np.where(ok, rday, -1)
    refund = np.where(rq > 0, np.rint(net * rq / qty), 0).astype(np.int64)
    reason = r.choice(S.RETURN_REASONS, size=L, p=[.32, .22, .22, .24])
    ln_df = pd.DataFrame(dict(line_id=mk_ids('ORL-2026-', start, L, 7), order_id=o.order_id.values[oi], oi=oi, line_number=ln, cidx=cidx, o_day=day,
                              cancelled=canc, prod=prod, qty=qty, unit_c=unit, disc_c=disc, net_c=net, retqty=rq,
                              ret_day=np.where(rq > 0, rday, np.nan).astype(float), reason=np.where(rq > 0, reason, None), refund_c=refund))
    # derive order aggregates from lines
    sub = np.bincount(oi, weights=net, minlength=nO).astype(np.int64)
    dsum = np.bincount(oi, weights=disc, minlength=nO).astype(np.int64)
    rsum = np.bincount(oi, weights=refund, minlength=nO).astype(np.int64)
    qsum = np.bincount(oi, weights=qty, minlength=nO).astype(np.int64)
    rqsum = np.bincount(oi, weights=rq, minlength=nO).astype(np.int64)
    ship = np.where(sub < int(S.FREE_SHIP_THRESHOLD_USD * 100), int(S.SHIP_FEE_USD * 100), 0)
    tax = np.rint(sub * S.TAX_RATE).astype(np.int64)
    o['subtotal_c'] = sub; o['disc_c'] = dsum; o['ship_c'] = ship; o['tax_c'] = tax; o['total_c'] = sub + ship + tax
    o['refund_c'] = rsum; o['net_c'] = np.where(o.cancelled, 0, sub - rsum)
    o['status'] = np.where(o.cancelled, 'cancelled', np.where(rqsum == qsum, 'returned', np.where(rqsum > 0, 'partially_returned', 'completed')))
    return o, ln_df


# ------------------------------------------------------------------ engagement events
def ev_frame(cidx, ts, et, ch, prod=None, act=None, ekey=None, pkey=None):
    n = len(cidx)
    return pd.DataFrame(dict(cidx=cidx, ts=ts.astype(np.int64), et=et, ch=ch, prod=-1 if prod is None else prod, act=-1 if act is None else act,
                             ekey=-1 if ekey is None else ekey, pkey=-1 if pkey is None else pkey))

def gen_bg_events(R, g, C, plo, phi, target, unsub, ekey0):
    """Background events for a phase; returns exactly `target` rows (chains + unsubscribes + filler)."""
    r = R['event']; n = g.n; p = g.p
    lo = np.maximum(np.maximum(g.signup, 0), plo); hi = np.minimum(g.ev_hi, phi)
    cut = (phi + 1) * DAY
    parts = []
    # --- email chain (consent-gated): sent -> open -> click
    f1, t1, _, _ = g.cons
    ef, et_ = f1[:, 0], t1[:, 0]
    has = np.isfinite(ef)
    elo = np.maximum(lo, np.where(has, (np.where(has, ef, 0) // DAY).astype(np.int64), 10 ** 6))
    ehi = np.minimum(hi, np.where(np.isfinite(et_), (np.where(np.isfinite(et_), et_, 0) // DAY).astype(np.int64) - 1, 10 ** 6))
    ev = has & (ehi >= elo)
    mass = np.where(ev, C[np.clip(ehi + 1, 0, D_END)] - C[np.clip(elo, 0, D_END)], 0)
    w = np.where(ev, g.eng * mass, 0.0)
    s_target = int(round(.12 * target))
    cnt = r.multinomial(s_target, w / w.sum())
    sc = np.repeat(np.arange(n), cnt)
    sd = sample_days(r, C, elo[sc], ehi[sc]); sts = sd * DAY + 9 * 3600 + r.integers(0, 3600, size=len(sc))
    sk = ekey0 + np.arange(len(sc)); ekey0 += len(sc)
    p_open = np.clip(np.array([.2, .35, .05, .45, .28, .15])[g.arch] * R['event'].lognormal(0, .4, n), .02, .9)
    p_click = np.clip(.14 * r.lognormal(0, .5, n), .02, .5)
    mo = (r.random(len(sc)) < p_open[sc])
    ots = sts[mo] + 60 + np.rint(r.exponential(10800, size=mo.sum())).astype(np.int64)
    keep = ots < cut
    oc = sc[mo][keep]; ots = ots[keep]; opk_parent = sk[mo][keep]
    ok_ = ekey0 + np.arange(len(oc)); ekey0 += len(oc)
    mc = r.random(len(oc)) < p_click[oc]
    cts = ots[mc] + 20 + np.rint(r.exponential(600, size=mc.sum())).astype(np.int64)
    keep2 = cts < cut
    cc = oc[mc][keep2]; cts = cts[keep2]; ckp = ok_[mc][keep2]
    ck = ekey0 + np.arange(len(cc)); ekey0 += len(cc)
    parts.append(ev_frame(sc, sts, ET['email_sent'], ECH['email'], ekey=sk))
    parts.append(ev_frame(oc, ots, ET['email_open'], ECH['email'], ekey=ok_, pkey=opk_parent))
    parts.append(ev_frame(cc, cts, ET['email_click'], ECH['email'], ekey=ck, pkey=ckp))
    # --- unsubscribes (caused by consent withdrawals)
    if len(unsub):
        uk = ekey0 + np.arange(len(unsub)); ekey0 += len(unsub)
        parts.append(ev_frame(unsub.cidx.values, unsub.f.values, ET['unsubscribe'], ECH['email'], ekey=uk))
    used = sum(len(x) for x in parts)
    rest = target - used
    assert rest > 0, 'target too small for chains'
    # --- filler behavioural events
    mass2 = np.where(hi >= lo, C[np.clip(hi + 1, 0, D_END)] - C[np.clip(lo, 0, D_END)], 0)
    w2 = np.where(hi >= lo, g.eng * mass2, 0.0)
    cnt2 = r.multinomial(rest, w2 / w2.sum())
    fc = np.repeat(np.arange(n), cnt2)
    fd = sample_days(r, C, lo[fc], hi[fc]); fts = fd * DAY + sod(r, len(fc))
    typ = r.choice(4, size=len(fc), p=[.36, .33, .08, .23])
    et = np.array([ET['web_visit'], ET['product_view'], ET['cart_add'], ET['app_session']])[typ]
    ch = np.where(typ == 0, ECH['web'], np.where(typ == 3, ECH['app'], np.where(r.random(len(fc)) < .6, ECH['web'], ECH['app'])))
    prod = np.full(len(fc), -1); pm = (typ == 1) | (typ == 2)
    prod[pm] = sample_products(r, p, fd[pm])
    fk = ekey0 + np.arange(len(fc)); ekey0 += len(fc)
    parts.append(ev_frame(fc, fts, et, ch, prod=prod, ekey=fk))
    out = pd.concat(parts, ignore_index=True)
    assert len(out) == target
    return out, ekey0

def finalize_events(ev, start):
    ev = ev.sort_values(['ts', 'ekey'], kind='stable').reset_index(drop=True)
    ev['event_id'] = mk_ids('EVT-2026-', start, len(ev), 7)
    return ev


# ------------------------------------------------------------------ support cases
def gen_cases(R, g, C, plo, phi, orders, lines, start):
    r = R['case']; n = g.n
    lo = np.maximum(np.maximum(g.signup, 0), plo); hi = np.minimum(g.case_hi, phi)
    valid = hi >= lo
    span = np.where(valid, hi - lo + 1, 0)
    rate = np.where(g.arch == A_PROS, .04, .22) + np.where(g.high_service, 4.5, 0) + np.where(g.returner, .4, 0)
    nc = r.poisson(rate * span / 365.0)
    bc = np.repeat(np.arange(n), nc); m = len(bc)
    bday = sample_days(r, C, lo[bc], hi[bc])
    pn = [.22, .17, .15, .12, .20, .08, .06]; ph = [.2, .25, .10, .10, .05, .25, .05]
    bcat = np.where(g.high_service[bc], r.choice(7, size=m, p=ph), r.choice(7, size=m, p=pn))
    bopen = bday * DAY + r.integers(8 * 3600, 20 * 3600, size=m)
    # link to an existing order of the same customer (order_ts earlier than case)
    o = orders.sort_values(['cidx', 'day', 'sec'], kind='stable')
    okey = (o.cidx.values * 1000 + o.day.values)
    pos = np.searchsorted(okey, bc * 1000 + bday, side='right'); st = np.searchsorted(okey, bc * 1000, side='left')
    avail = pos - st
    linkable = np.isin(bcat, [0, 1, 2, 3, 5]) & (avail > 0) & (r.random(m) < .8)
    pick = st + np.floor(r.random(m) * np.maximum(avail, 1)).astype(np.int64)
    pick = np.clip(pick, 0, max(len(o) - 1, 0))
    b_order = np.where(linkable, o.order_id.values[pick], None)
    b_ots = np.where(linkable, o.ts_sec.values[pick], -10 ** 12)
    bopen = np.where(linkable, np.maximum(bopen, b_ots + 1800 + r.integers(0, 3600, size=m)), bopen)
    # return-triggered cases
    lr = lines[lines.retqty > 0].groupby('order_id').ret_day.min()
    ro = orders.set_index('order_id').loc[lr.index]
    rd = np.maximum(ro.day.values + 1, lr.values.astype(np.int64) - r.integers(0, 3, size=len(lr)))
    sel = (rd >= plo) & (rd <= phi) & (r.random(len(lr)) < np.where(g.high_service[ro.cidx.values], .30, .12))
    rc = ro.cidx.values[sel]; rcopen = rd[sel] * DAY + r.integers(8 * 3600, 20 * 3600, size=sel.sum()); rorder = lr.index.values[sel]
    cidx = np.concatenate([bc, rc]); cat = np.concatenate([bcat, np.full(len(rc), 3)])
    opn = np.concatenate([bopen, rcopen]); order_id = np.concatenate([b_order, rorder]).astype(object)
    k = len(cidx)
    pri = np.empty(k, np.int64)
    u = r.random(k)
    pri = np.where(cat == 5, np.where(u < .7, 2, 1), np.where(cat == 1, np.where(u < .25, 2, np.where(u < .8, 1, 0)), np.where(u < .45, 0, np.where(u < .95, 1, 2))))
    chn = r.choice(3, size=k, p=[.35, .35, .30])
    mean_min = np.array([14, 35, 18, 22, 10, 45, 12])[cat]
    minutes = np.maximum(3, np.rint(r.gamma(3.0, mean_min / 3.0))).astype(np.int64)
    pesc = np.array([.04, .15, .04, .05, .02, .35, .02])[cat]
    esc = r.random(k) < pesc
    res_h = r.exponential(np.array([36, 24, 14])[pri]) + np.where(esc, 48, 0)
    close = opn + np.rint(res_h * 3600).astype(np.int64) + 600
    closed = close < END_SEC
    esc_sec = np.where(closed, opn + np.rint((close - opn) * r.uniform(.25, .6, k)), opn + np.rint(r.exponential(DAY, size=k)) + 300)
    esc = esc & (esc_sec < END_SEC) & (esc_sec > opn)
    esc_sec = np.where(esc, esc_sec, np.nan)
    cs = r.random(k) < .5
    csat = np.clip(np.rint(r.normal(4.1 - 1.2 * esc - .8 * (cat == 5) - .4 * (res_h > 48), .9)), 1, 5)
    df = pd.DataFrame(dict(cidx=cidx, order_id=order_id, open_sec=opn, cat=cat, pri=pri, chn=chn, esc=esc, esc_sec=esc_sec,
                           close_sec=np.where(closed, close, np.nan), minutes=np.where(closed, minutes, np.nan),
                           cost_c=np.where(closed, np.rint(minutes * S.CASE_COST_PER_MIN * 100 + S.CASE_ESCALATION_FEE * 100 * esc), np.nan),
                           csat=np.where(closed & cs, csat, np.nan)))
    df['status'] = np.where(closed, 'closed', np.where(esc, 'escalated', 'open'))
    df = df.sort_values(['open_sec', 'cidx'], kind='stable').reset_index(drop=True)
    df['case_id'] = mk_ids('CASE-2026-', start, len(df), 6)
    return df


# ------------------------------------------------------------------ metrics, segments
def score(vals, bins, direction):
    out = np.full(len(vals), np.nan)
    ok = ~np.isnan(vals)
    v = vals[ok]; s = np.empty(len(v))
    done = np.zeros(len(v), bool)
    for bound, sc in bins:
        hit = (~done) & ((v <= bound) if direction == 'le' else (v >= bound))
        s[hit] = sc; done |= hit
    out[ok] = s
    return out

def compute_metrics(g, Sday, O, L, EV, CS, CON):
    n = g.n; sec = Sday * DAY
    o = O[(O.day < Sday) & (~O.cancelled)]
    n_orders = np.bincount(o.cidx.values, minlength=n).astype(float)
    first = np.full(n, np.nan); last = np.full(n, np.nan)
    gb = o.groupby('cidx').day.agg(['min', 'max']); first[gb.index.values] = gb['min'].values; last[gb.index.values] = gb['max'].values
    l = L[(L.o_day < Sday) & (~L.cancelled)]
    gross = np.bincount(l.cidx.values, weights=l.net_c.values, minlength=n)
    rm = (l.ret_day.values < Sday)
    ref = np.bincount(l.cidx.values[rm], weights=l.refund_c.values[rm], minlength=n)
    e = EV[(EV.ts >= sec - 90 * DAY) & (EV.ts < sec)]
    opens = np.bincount(e.cidx.values[e.et.values == ET['email_open']], minlength=n)
    clicks = np.bincount(e.cidx.values[e.et.values == ET['email_click']], minlength=n)
    c = CS[(CS.open_sec >= sec - 365 * DAY) & (CS.open_sec < sec)]
    cases12 = np.bincount(c.cidx.values, minlength=n)
    cc = c[c.close_sec < sec]
    cost12 = np.bincount(cc.cidx.values, weights=cc.cost_c.values, minlength=n)
    w = CON[(CON.status == 'withdrawn') & (CON.f >= sec - 90 * DAY) & (CON.f < sec)]
    wd90 = np.bincount(w.cidx.values, minlength=n)
    sel = np.where(g.signup < Sday)[0]
    rec = Sday - last; age = Sday - first
    net = gross - ref
    has = n_orders > 0
    m = pd.DataFrame(dict(cidx=sel, n_orders=n_orders[sel], first_order_day=first[sel], last_order_day=last[sel], recency_days=rec[sel], first_order_age_days=age[sel],
                          gross_c=gross[sel], refund_c=ref[sel], net_c=net[sel],
                          return_rate=np.round(np.where(gross[sel] > 0, ref[sel] / np.maximum(gross[sel], 1), 0.0), 4),
                          opens_90d=opens[sel], clicks_90d=clicks[sel], cases_12m=cases12[sel], service_cost_c=cost12[sel], consent_withdrawals_90d=wd90[sel]))
    set_scores(m)
    return m

def set_scores(m):
    has = (m.n_orders.values > 0)
    r_ = score(m.recency_days.values.astype(float), S.RFM_BINS['R_recency_days'], 'le')
    f_ = score(np.where(has, m.n_orders.values, np.nan), S.RFM_BINS['F_orders'], 'ge')
    m_ = score(np.where(has, m.net_c.values / 100.0, np.nan), S.RFM_BINS['M_net_spend_usd'], 'ge')
    m['r_score'] = r_; m['f_score'] = f_; m['m_score'] = m_
    m['service_cost_12m'] = m.service_cost_c / 100.0

def assign_segments(m, date_str):
    segs = [(i, s) for i, s in enumerate(S.SEGMENTS) if s[7] == 'active' and s[8] <= date_str and (s[9] is None or s[9] >= date_str)]
    rem = np.ones(len(m), bool); rows = []
    for i, s in sorted([x for x in segs if x[1][3]], key=lambda x: x[1][4]):
        hit = S.eval_rule(s[5], m) & rem
        rem &= ~hit
        rows.append(pd.DataFrame(dict(cidx=m.cidx.values[hit], sidx=i)))
    for i, s in [x for x in segs if not x[1][3]]:
        hit = S.eval_rule(s[5], m)
        rows.append(pd.DataFrame(dict(cidx=m.cidx.values[hit], sidx=i)))
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------ action engine @ snapshot 1
def run_actions(R, g, m1, A1, CS_pre, ekey0, n_viol):
    r = R['act']; n = g.n
    act_idx = {a[0]: i for i, a in enumerate(S.ACTIONS)}; seg_idx = {s[0]: i for i, s in enumerate(S.SEGMENTS)}
    elig = pd.DataFrame([(act_idx[a], seg_idx[s], p) for a, s, p in S.ELIGIBILITY], columns=['aidx', 'sidx', 'prio'])
    cand = A1.merge(elig, on='sidx')
    sr = act_idx['SERVICE_RECOVERY_CALL']
    cs = CS_pre
    rc = cs[(cs.open_sec >= (S1 - 30) * DAY) & (cs.open_sec < S1 * DAY) & ((cs.cat == 5) | (cs.esc & (cs.esc_sec < S1 * DAY)))]
    recent_c = np.zeros(n, bool); recent_c[rc.cidx.values] = True
    cand = cand[~((cand.aidx == sr) & ~recent_c[cand.cidx.values])]
    cand = cand.sort_values(['cidx', 'prio', 'aidx'], kind='stable').drop_duplicates(['cidx', 'aidx'])
    cand['rank'] = cand.groupby('cidx').cumcount()
    cand = cand[cand['rank'] < 2].reset_index(drop=True)
    k = len(cand); cidx = cand.cidx.values; aidx = cand.aidx.values; slot = cand['rank'].values + 1
    A = S.ACTIONS
    mkt = np.array([a[2] == 'marketing' for a in A])[aidx]; isdisc = np.array([a[6] for a in A])[aidx]
    # open complaint at decision time
    oc = cs[(cs.open_sec < S1 * DAY) & ((cs.close_sec.isna()) | (cs.close_sec >= S1 * DAY)) & ((cs.cat == 5) | (cs.esc & (cs.esc_sec < S1 * DAY)))]
    open_c = np.zeros(n, bool); open_c[oc.cidx.values] = True
    recency = np.full(n, np.inf); recency[m1.cidx.values] = np.nan_to_num(m1.recency_days.values, nan=np.inf)
    hr_seg = seg_idx['HIGH_RETURNER']
    hret = np.zeros(n, bool); hret[A1.cidx.values[A1.sidx.values == hr_seg]] = True
    sup = np.zeros(k, np.int64)
    sup = np.where(mkt & open_c[cidx], 3, 0)
    notwelcome = aidx != act_idx['WELCOME_SERIES']
    sup = np.where((sup == 0) & mkt & notwelcome & (recency[cidx] <= 7), 4, sup)
    sup = np.where((sup == 0) & mkt & isdisc & hret[cidx], 5, sup)
    day1 = S1 + r.integers(1, 8, size=n); day2 = day1 + r.integers(8, 22, size=n)
    sched = np.where(slot == 1, day1[cidx], day2[cidx]) * DAY + r.integers(9 * 3600, 18 * 3600, size=k)
    # channel + consent at scheduled send time
    chan = np.zeros(k, np.int64); ccheck = np.full(k, 'not_evaluated', dtype=object)
    for a, act in enumerate(A):
        rows = np.where(aidx == a)[0]
        if len(rows) == 0: continue
        chans = [CC.index(c) for c in act[4]]
        if act[2] == 'service':
            chan[rows] = CC.index('phone'); ccheck[rows] = 'not_required'; continue
        ci = cidx[rows]; ts = sched[rows]
        chosen = np.full(len(rows), -1)
        pref = g.pref_idx[ci]
        for c in chans:
            ok = (chosen == -1) & (pref == c) & consented(g, c, ci, ts); chosen[ok] = c
        for c in chans:
            ok = (chosen == -1) & consented(g, c, ci, ts); chosen[ok] = c
        wdr = np.zeros(len(rows), bool)
        for c in chans:
            wdr |= (g.cons[0][ci, c] <= ts) & (g.cons[1][ci, c] <= ts) & ~consented(g, c, ci, ts)
        ev = sup[rows] == 0
        chan[rows] = np.where(chosen >= 0, chosen, chans[0])
        ccheck[rows[ev]] = np.where(chosen[ev] >= 0, 'granted', np.where(wdr[ev], 'withdrawn', 'never_granted'))
        bad = ev & (chosen < 0)
        sup[rows[bad]] = 1
    # slot processing: frequency cap then holdout
    decision = np.zeros(k, np.int64)   # 0 send 1 suppress 2 holdout
    s1_sent = np.zeros(n, bool); s1_ts = np.zeros(n, np.int64)
    for sl in (1, 2):
        ix = np.where(slot == sl)[0]
        if sl == 2:
            prior = s1_sent[cidx[ix]] & (s1_ts[cidx[ix]] > sched[ix] - 30 * DAY)
            capb = (sup[ix] == 0) & mkt[ix] & (prior.astype(int) + 1 > g.cap[cidx[ix]])
            sup[ix[capb]] = 2
        ho = (sup[ix] == 0) & mkt[ix] & (r.random(len(ix)) < S.HOLDOUT_RATE)
        decision[ix[ho]] = 2
        sent = (sup[ix] == 0) & ~ho
        if sl == 1:
            sg = ix[sent & mkt[ix]]; s1_sent[cidx[sg]] = True; s1_ts[cidx[sg]] = sched[sg]
    decision[sup > 0] = 1
    # --- injected anomaly: action violates consent (suppressed-for-consent rows flipped to sent)
    has_send = np.zeros(n, bool); has_send[cidx[decision == 0]] = True
    cand_v = np.where((sup == 1) & (slot == 1) & ~has_send[cidx])[0]
    if len(cand_v) and n_viol:
        wflag = ccheck[cand_v] == 'withdrawn'          # ccheck for suppressed consent rows holds withdrawn/never_granted
        order = np.concatenate([r.permutation(cand_v[wflag]), r.permutation(cand_v[~wflag])])
        nw = min(int(n_viol * .6), wflag.sum()); pick = np.concatenate([order[:nw], r.permutation(order[nw:])[:n_viol - nw]])
        pick = np.array(pick, dtype=np.int64)
        orig_chk = ccheck[pick].copy()
        decision[pick] = 0; sup[pick] = 0; ccheck[pick] = 'granted'   # falsified evidence
        viol_idx = pick; viol_chk = orig_chk
    else:
        viol_idx = np.array([], dtype=np.int64); viol_chk = np.array([], dtype=object)
    # --- responses
    sentm = decision == 0
    opens90 = np.zeros(n); opens90[m1.cidx.values] = m1.opens_90d.values
    fac = .70 + .10 * np.minimum(opens90[cidx], 6)
    is_viol = np.zeros(k, bool); is_viol[viol_idx] = True
    p_open_b = np.array([.42, 0.0, .60, .45])[chan]
    opened = sentm & ~is_viol & (chan != 1) & (r.random(k) < np.clip(p_open_b * fac, 0, .95))
    bc = np.array([a[9] for a in A])[aidx]; bv = np.array([a[10] for a in A])[aidx]
    clicked = (opened & (chan == 0) & (r.random(k) < np.clip(bc * 1.6 * fac, 0, .9))) | \
              (sentm & ~is_viol & (chan == 1) & (r.random(k) < np.clip(bc * 1.0 * fac, 0, .9)))
    engaged = clicked | (opened & np.isin(chan, [2, 3]))
    conv = engaged & (r.random(k) < bv)
    d_open = np.where(chan == 2, 300, np.where(chan == 3, 3600, 7200))
    open_ts = sched + 120 + np.rint(r.exponential(d_open)).astype(np.int64)
    click_ts = np.where(chan == 1, sched, open_ts) + 30 + np.rint(r.exponential(900, size=k)).astype(np.int64)
    eng_ts = np.where(np.isin(chan, [2, 3]), open_ts, click_ts)
    conv_ts = eng_ts + 600 + np.rint(r.exponential(1.2 * DAY, size=k)).astype(np.int64)
    conv = conv & (conv_ts <= sched + S_ATTR * DAY) & (conv_ts < END_SEC)
    # events for sends / opens / clicks
    ev = []
    sidx = np.where(sentm)[0]
    sk = np.full(k, -1); sk[sidx] = ekey0 + np.arange(len(sidx)); ekey0 += len(sidx)
    et_sent = np.array([ET[SENT_ET[c]] for c in CC])[chan[sidx]]
    ev.append(ev_frame(cidx[sidx], sched[sidx], et_sent, np.array([ECH[c] for c in CC])[chan[sidx]], act=aidx[sidx], ekey=sk[sidx]))
    oi_ = np.where(opened)[0]; ok = np.full(k, -1); ok[oi_] = ekey0 + np.arange(len(oi_)); ekey0 += len(oi_)
    ev.append(ev_frame(cidx[oi_], open_ts[oi_], np.array([ET.get(OPEN_ET.get(c, 'x'), -1) for c in CC])[chan[oi_]], np.array([ECH[c] for c in CC])[chan[oi_]],
                       act=aidx[oi_], ekey=ok[oi_], pkey=sk[oi_]))
    ci_ = np.where(clicked)[0]; ck = np.full(k, -1); ck[ci_] = ekey0 + np.arange(len(ci_)); ekey0 += len(ci_)
    par = np.where(chan[ci_] == 1, sk[ci_], ok[ci_])
    ev.append(ev_frame(cidx[ci_], click_ts[ci_], np.array([ET.get(CLICK_ET.get(c, 'x'), -1) for c in CC])[chan[ci_]], np.array([ECH[c] for c in CC])[chan[ci_]],
                       act=aidx[ci_], ekey=ck[ci_], pkey=par))
    ev = pd.concat(ev, ignore_index=True)
    assert (ev.et >= 0).all()
    # induced orders
    ii = np.where(conv)[0]
    pct = np.array([a[7] for a in A])[aidx[ii]]; code = np.array([a[0] for a in A], dtype=object)[aidx[ii]]
    induced = pd.DataFrame(dict(cidx=cidx[ii], day=conv_ts[ii] // DAY, sec=conv_ts[ii] % DAY, chn=np.where(r.random(len(ii)) < .6, 0, 1), promo_pct=pct,
                                promo_code=np.where(pct > 0, code, None), cancelled=False))
    out = pd.DataFrame(dict(cidx=cidx, aidx=aidx, sidx=cand.sidx.values, slot=slot, decision=decision, sup=sup, chan=chan, ccheck=ccheck, sched=sched,
                            sent_ts=np.where(sentm, sched, np.nan), sk=sk, open_ts=np.where(opened, open_ts, np.nan), click_ts=np.where(clicked, click_ts, np.nan)))
    out['holdout'] = decision == 2
    vexp = np.full(k, '', dtype=object); vexp[viol_idx] = viol_chk
    out['viol_expected'] = vexp
    return out, ev, induced, ekey0

S_ATTR = S.ATTRIBUTION_WINDOW_DAYS


def attribute(out, O):
    """Last-touch attribution among SENT outcomes; holdout rows use organic conversion in the same window."""
    o = O[~O.cancelled][['cidx', 'ts_sec', 'order_id', 'net_c', 'disc_c', 'promo_code']].sort_values('ts_sec', kind='stable')
    s = out[out.decision == 0][['cidx', 'sent_ts', 'aidx']].copy(); s['sent_ts'] = s['sent_ts'].astype(np.int64); s['orow'] = s.index
    s = s.sort_values('sent_ts', kind='stable')
    mg = pd.merge_asof(o, s, left_on='ts_sec', right_on='sent_ts', by='cidx', direction='backward')
    mg = mg[(mg.orow.notna()) & (mg.ts_sec <= mg.sent_ts + S_ATTR * DAY) & (mg.ts_sec > mg.sent_ts)]
    first = mg.sort_values('ts_sec', kind='stable').drop_duplicates('orow')
    res = pd.DataFrame(index=out.index, columns=['att_order', 'att_net', 'att_disc', 'att_promo'])
    res.loc[first.orow.astype(int).values, 'att_order'] = first.order_id.values
    res.loc[first.orow.astype(int).values, 'att_net'] = first.net_c.values
    res.loc[first.orow.astype(int).values, 'att_disc'] = first.disc_c.values
    res.loc[first.orow.astype(int).values, 'att_promo'] = first.promo_code.values
    h = out[out.decision == 2][['cidx', 'sched']].copy(); h['hrow'] = h.index
    hm = h.merge(o, on='cidx')
    hm = hm[(hm.ts_sec > hm.sched) & (hm.ts_sec <= hm.sched + S_ATTR * DAY)].sort_values('ts_sec', kind='stable').drop_duplicates('hrow')
    res.loc[hm.hrow.values, 'att_order'] = hm.order_id.values
    res.loc[hm.hrow.values, 'att_net'] = hm.net_c.values
    res.loc[hm.hrow.values, 'att_disc'] = hm.disc_c.values
    res.loc[hm.hrow.values, 'att_promo'] = hm.promo_code.values
    return res


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=20261022)
    ap.add_argument('--n-customers', type=int, default=50000)
    ap.add_argument('--n-orders', type=int, default=200000)
    ap.add_argument('--n-events', type=int, default=1000000)
    ap.add_argument('--out', default='output')
    ap.add_argument('--no-db', action='store_true', help='skip SQLite + SQL seed build')
    ap.add_argument('--no-json', action='store_true')
    a = ap.parse_args()
    N, NO, NE = a.n_customers, a.n_orders, a.n_events
    scale = N / 50000.0
    os.makedirs(a.out, exist_ok=True)
    names = ['cust', 'prod', 'consent', 'order', 'line', 'event', 'case', 'act', 'inject', 'misc']
    ss = np.random.SeedSequence(a.seed)
    R = {nm: np.random.default_rng(c) for nm, c in zip(names, ss.spawn(len(names)))}
    C = build_calendar()
    # ---------------- 1. parents
    g = make_customers(R, N); log('customers')
    p = make_products(R, g, scale)
    con = make_consent(R, g); log('products, consent: %d consent rows' % len(con))
    # ---------------- 2. pre-snapshot transactions
    n_pre = int(round(.83 * NO))
    o_pre = gen_orders(R, g, C, 0, S1 - 1, n_pre, g.arch != A_NEW)
    o_pre = finalize_orders(R, o_pre, 1)
    o_pre, l_pre = gen_lines(R, g, o_pre, 1); log('pre orders %d lines %d' % (len(o_pre), len(l_pre)))
    # events (pre)
    unsub_all = con[(con.status == 'withdrawn') & (con.ch == 0) & (con.src == 'unsubscribe_link')]
    unsub_pre = unsub_all[unsub_all.f < S1 * DAY]; unsub_post = unsub_all[unsub_all.f >= S1 * DAY]
    ekey = 0
    ev_pre, ekey = gen_bg_events(R, g, C, 0, S1 - 1, int(round(.80 * NE)), unsub_pre, ekey)
    ev_pre = finalize_events(ev_pre, 1); log('pre events %d' % len(ev_pre))
    cs_pre = gen_cases(R, g, C, 0, S1 - 1, o_pre, l_pre, 1); log('pre cases %d' % len(cs_pre))
    # ---------------- 3. snapshot 1: metrics, segments, actions
    m1 = compute_metrics(g, S1, o_pre, l_pre, ev_pre, cs_pre, con)
    A1 = assign_segments(m1, '2026-07-01'); log('snapshot1 segments %d rows' % len(A1))
    n_viol = max(5, int(round(.003 * N)))
    out, ev_act, induced, ekey = run_actions(R, g, m1, A1, cs_pre, ekey, n_viol)
    log('actions %d outcomes, %d induced orders, %d action events' % (len(out), len(induced), len(ev_act)))
    # ---------------- 4. post-snapshot
    n_post = NO - len(o_pre) - len(induced)
    o_post = gen_orders(R, g, C, S1, 637, n_post, g.arch == A_NEW)
    o_post = pd.concat([o_post, induced], ignore_index=True)
    o_post = finalize_orders(R, o_post, len(o_pre) + 1)
    o_post, l_post = gen_lines(R, g, o_post, len(l_pre) + 1)
    O = pd.concat([o_pre, o_post], ignore_index=True); L = pd.concat([l_pre, l_post], ignore_index=True)
    log('orders total %d lines %d' % (len(O), len(L)))
    target_post = NE - len(ev_pre) - len(ev_act)
    ev_bg_post, ekey = gen_bg_events(R, g, C, S1, 637, target_post, unsub_post, ekey)
    ev_post = finalize_events(pd.concat([ev_bg_post, ev_act], ignore_index=True), len(ev_pre) + 1)
    EV = pd.concat([ev_pre, ev_post], ignore_index=True); assert len(EV) == NE
    cs_post = gen_cases(R, g, C, S1, 637, O, L, len(cs_pre) + 1)
    CS = pd.concat([cs_pre, cs_post], ignore_index=True); log('events %d cases %d' % (len(EV), len(CS)))
    ek2id = pd.Series(EV.event_id.values, index=EV.ekey.values)
    # ---------------- 5. attribution
    att = attribute(out, O)
    # ---------------- 6. snapshot 2 + memberships
    m2 = compute_metrics(g, S2, O, L, EV, CS, con)
    A1_true = A1; seg_true2 = None
    # lifecycle state from TRUE metrics
    ec = np.select([m2.n_orders.values == 0, m2.first_order_age_days.values <= 60, m2.recency_days.values <= 90, m2.recency_days.values <= 180],
                   ['prospect', 'new', 'active', 'lapsing'], 'dormant')
    lifecycle = np.full(N, 'prospect', dtype=object); lifecycle[m2.cidx.values] = ec
    A2_true = assign_segments(m2, '2026-10-01')
    true_life2 = A2_true[A2_true.sidx.isin([i for i, s in enumerate(S.SEGMENTS) if s[3]])].set_index('cidx').sidx
    # inject: return not netted from spend (stored metrics only)
    ri = R['inject']
    n_rn = max(5, int(round(.003 * N)))
    elig_rn = np.where((m2.refund_c.values >= 5000))[0]
    pick_rn = np.sort(ri.choice(elig_rn, size=min(n_rn, len(elig_rn)), replace=False))
    gt_rn = pd.DataFrame(dict(cidx=m2.cidx.values[pick_rn], expected=m2.net_c.values[pick_rn] / 100.0, observed=m2.gross_c.values[pick_rn] / 100.0))
    m2s = m2.copy()
    m2s.loc[m2s.index[pick_rn], 'net_c'] = m2s.loc[m2s.index[pick_rn], 'gross_c']
    m2s.loc[m2s.index[pick_rn], 'refund_c'] = 0.0
    m2s.loc[m2s.index[pick_rn], 'return_rate'] = 0.0
    set_scores(m2s)
    A2 = assign_segments(m2s, '2026-10-01')
    # membership assembly with history (two snapshots)
    A1['snap'] = 1; A2['snap'] = 2
    mm = A1.merge(A2, on=['cidx', 'sidx'], how='outer', suffixes=('_1', '_2'), indicator=True)
    mem = pd.DataFrame(dict(cidx=mm.cidx, sidx=mm.sidx))
    both = mm._merge == 'both'; only1 = mm._merge == 'left_only'
    mem['eff_from'] = np.where(mm._merge == 'right_only', S2, S1)
    mem['eff_to'] = np.where(only1, S2, np.nan)
    mem['eval_snap'] = np.where(only1, S1, S2)
    mem['assigned_by'] = 'rule_engine'
    mem['inj'] = ''
    # inject: conflicting exclusive segments (extra current lifecycle membership)
    life_idx = [i for i, s in enumerate(S.SEGMENTS) if s[3] and s[7] == 'active']
    cur = mem[(mem.eval_snap == S2) & mem.sidx.isin(life_idx)]
    n_cf = max(5, int(round(.0024 * N)))
    pick = ri.choice(len(cur), size=min(n_cf, len(cur)), replace=False)
    existing = set(zip(mem.cidx.values, mem.sidx.values)); extra = []
    for rr in cur.iloc[np.sort(pick)].itertuples():
        opts = [i for i in life_idx if i != rr.sidx and (rr.cidx, i) not in existing]
        ns = opts[ri.integers(len(opts))]
        existing.add((rr.cidx, ns)); extra.append((rr.cidx, ns, rr.sidx))
    ex = pd.DataFrame(extra, columns=['cidx', 'sidx', 'true_sidx'])
    exm = pd.DataFrame(dict(cidx=ex.cidx, sidx=ex.sidx, eff_from=S2, eff_to=np.nan, eval_snap=S2, assigned_by='legacy_sync', inj=ex.true_sidx.astype(str)))
    mem = pd.concat([mem, exm], ignore_index=True)
    mem = mem.sort_values(['eff_from', 'cidx', 'sidx'], kind='stable').reset_index(drop=True)
    seg_ids = np.array([S.SEG_ID[s[0]] for s in S.SEGMENTS], dtype=object)
    mem['membership_id'] = np.char.add(np.char.add(np.char.add('MEM-', seg_ids[mem.sidx.values].astype(str)), '-'), g.cust_id[mem.cidx.values].astype(str)).astype(object)
    # explanations from the metrics used
    mk1 = m1.set_index('cidx'); mk2 = m2s.set_index('cidx')
    expl = np.empty(len(mem), dtype=object)
    for snap, mk in ((S1, mk1), (S2, mk2)):
        ix = np.where(mem.eval_snap.values == snap)[0]
        recs = mk.reindex(mem.cidx.values[ix]).to_dict('records')
        for j, rec in zip(ix, recs):
            s = S.SEGMENTS[mem.sidx.values[j]]
            expl[j] = ('rule %s v%d: ' % (s[0], s[6])) + S.explain_row(s[5], rec) if mem.assigned_by.values[j] == 'rule_engine' else 'imported by legacy_sync job; rule evidence not recorded'
    mem['explanation'] = expl
    log('memberships %d' % len(mem))
    # ---------------- 7. outcomes (log + subsequent outcome)
    act_ids = np.array([S.ACT_ID[x[0]] for x in S.ACTIONS], dtype=object)
    segmem = pd.Series(mem.membership_id.values, index=pd.MultiIndex.from_arrays([mem.cidx.values, mem.sidx.values]))
    out['membership_id'] = segmem.reindex(pd.MultiIndex.from_arrays([out.cidx.values, out.sidx.values])).values
    out = pd.concat([out, att], axis=1)
    out['converted'] = out.att_order.notna()
    out['status'] = np.select([out.decision == 1, out.decision == 2, out.converted, out.click_ts.notna(), out.open_ts.notna()],
                              ['suppressed', 'holdout', 'converted', 'clicked', 'opened'], 'sent')
    out = out.sort_values(['sched', 'cidx', 'slot'], kind='stable').reset_index(drop=True)
    out['outcome_id'] = mk_ids('OUT-2026-', 1, len(out), 6)
    is_mkt = np.array([x[2] == 'marketing' for x in S.ACTIONS])[out.aidx.values]
    ucost = np.array([x[8] for x in S.ACTIONS])[out.aidx.values]
    acode = np.array([x[0] for x in S.ACTIONS], dtype=object)[out.aidx.values]
    sent_ev = ek2id.reindex(out.sk.values).values
    ao = pd.DataFrame(dict(
        outcome_id=out.outcome_id.values, customer_id=g.cust_id[out.cidx.values], action_id=act_ids[out.aidx.values],
        segment_id=np.array([S.SEG_ID[s[0]] for s in S.SEGMENTS], dtype=object)[out.sidx.values], membership_id=out.membership_id.values,
        slot=out.slot.values, recommended_at=tfmt(np.full(len(out), S1 * DAY + 6 * 3600)),
        decision=np.array(['send', 'suppress', 'holdout'])[out.decision.values],
        suppression_id=np.where(out.sup.values > 0, ['SUP-%03d' % x for x in out.sup.values], None),
        experiment_group=np.where(out.decision.values == 2, 'holdout', np.where((out.decision.values == 0) & is_mkt, 'treatment', 'none')),
        channel=np.array(CC)[out.chan.values], consent_check=out.ccheck.values, scheduled_send_ts=tfmt(out.sched.values),
        sent_ts=tfmt(out.sent_ts.values), sent_event_id=np.where(out.sk.values >= 0, sent_ev, None),
        opened_ts=tfmt(out.open_ts.values), clicked_ts=tfmt(out.click_ts.values),
        attributed_order_id=out.att_order.values, attribution_window_days=S_ATTR, converted_flag=out.converted.astype(int).values,
        status=out.status.values,
        revenue_attributed=money(out.att_net.astype(float).fillna(0).values),
        action_cost=np.where(out.decision.values == 0, ucost, 0.0),
        discount_cost=np.where((out.decision.values == 0) & (out.att_promo.values == acode), money(out.att_disc.astype(float).fillna(0).values), 0.0)))
    ao.loc[ao.attributed_order_id.isna(), 'attributed_order_id'] = None
    # ---- ground truth: consent violations (identified through the falsified-evidence flag carried on the row)
    gt = []
    vrows = np.where(out.viol_expected.values != '')[0]
    for i in vrows:
        gt.append(dict(issue_type='action_violates_consent', entity='action_outcome', entity_id=ao.outcome_id.values[i], customer_id=ao.customer_id.values[i],
                       related_entity_id=ao.sent_event_id.values[i], expected_value='no granted %s consent at send time (%s) => must be suppressed (SUP-001)' % (ao.channel.values[i], out.viol_expected.values[i]),
                       observed_value='sent via %s; consent_check logged as granted' % ao.channel.values[i]))
    # ---- inject: outcome attributed to wrong action (converted sent outcomes get a different action_id)
    conv_idx = np.where((ao.decision.values == 'send') & (ao.converted_flag.values == 1) & (out.viol_expected.values == ''))[0]
    n_wa = max(5, int(round(.002 * N)))
    wa = np.sort(ri.choice(conv_idx, size=min(n_wa, len(conv_idx)), replace=False))
    for i in wa:
        orig = ao.action_id.values[i]; opts = [x for x in act_ids if x != orig]; new = opts[ri.integers(len(opts))]
        ao.iat[i, ao.columns.get_loc('action_id')] = new
        gt.append(dict(issue_type='outcome_wrong_action', entity='action_outcome', entity_id=ao.outcome_id.values[i], customer_id=ao.customer_id.values[i],
                       related_entity_id=ao.sent_event_id.values[i], expected_value=orig, observed_value=new))
    # ---- ground truth: conflicting exclusive segments + return not netted
    segcode = np.array([s[0] for s in S.SEGMENTS], dtype=object)
    mid_idx = pd.Series(mem.membership_id.values, index=pd.MultiIndex.from_arrays([mem.cidx.values, mem.sidx.values]))
    inj = mem[mem.assigned_by.values == 'legacy_sync']
    for rr in inj.itertuples():
        tm = mid_idx.get((rr.cidx, int(rr.inj)))
        gt.append(dict(issue_type='conflicting_exclusive_segments', entity='segment_membership', entity_id=rr.membership_id, customer_id=g.cust_id[rr.cidx],
                       related_entity_id=tm, expected_value='single lifecycle segment: %s' % segcode[int(rr.inj)],
                       observed_value='also member of %s (exclusive group lifecycle)' % segcode[rr.sidx]))
    for rr in gt_rn.itertuples():
        gt.append(dict(issue_type='return_not_netted', entity='customer_metric_snapshot', entity_id='2026-10-01|' + g.cust_id[rr.cidx], customer_id=g.cust_id[rr.cidx],
                       related_entity_id=None, expected_value='net_monetary=%.2f' % rr.expected, observed_value='net_monetary=%.2f (returns not netted)' % rr.observed))
    gtdf = pd.DataFrame(gt)
    gtdf.insert(0, 'gt_id', mk_ids('GT-', 1, len(gtdf), 5))
    # ---------------- 8. assemble tables
    TB = {}
    TB['customer'] = pd.DataFrame(dict(customer_id=g.cust_id, customer_type=np.where(np.isin(np.arange(N), O.cidx.values), 'customer', 'prospect'), signup_date=dfmt(g.signup),
                                       region=g.region, age_band=g.age, acquisition_channel=g.acq, preferred_language=g.lang, preferred_channel=g.pref,
                                       max_marketing_contacts_per_30d=g.cap, lifecycle_state=lifecycle, lifecycle_as_of_date='2026-10-01'))
    TB['product'] = pd.DataFrame(dict(product_id=p.id, sku=np.array(['SKU-%s-%s' % (c[:3].upper(), i[4:]) for c, i in zip(p.cat_name, p.id)]), product_name=p.name,
                                      category=p.cat_name, subcategory=p.sub, brand=p.brand, list_price=money(p.price_c), unit_cost=p.cost, launch_date=dfmt(p.launch),
                                      discontinued_date=dfmt(np.where(np.isinf(p.disc), np.nan, p.disc)), status=np.where(np.isinf(p.disc), 'active', 'discontinued')))
    TB['orders'] = pd.DataFrame(dict(order_id=O.order_id.values, customer_id=g.cust_id[O.cidx.values], order_ts=tfmt(O.ts_sec.values),
                                     channel=np.array(S.ORDER_CH)[O.chn.values], status=O.status.values, currency='USD', promo_pct=O.promo_pct.values,
                                     promo_code=O.promo_code.values, discount_total=money(O.disc_c), subtotal=money(O.subtotal_c), shipping_fee=money(O.ship_c),
                                     tax_amount=money(O.tax_c), order_total=money(O.total_c), refund_total=money(O.refund_c), net_merchandise_value=money(O.net_c),
                                     cancelled_ts=tfmt(O.cancel_sec.values)))
    TB['order_line'] = pd.DataFrame(dict(order_line_id=L.line_id.values, order_id=L.order_id.values, line_number=L.line_number.values, product_id=p.id[L['prod'].values],
                                         quantity=L.qty.values, unit_price=money(L.unit_c), discount_amount=money(L.disc_c), line_net_amount=money(L.net_c),
                                         returned_quantity=L.retqty.values, return_date=dfmt(L.ret_day.values), return_reason=L.reason.values, refund_amount=money(L.refund_c)))
    pid = np.where(EV['prod'].values >= 0, p.id[np.clip(EV['prod'].values, 0, None)], None)
    par = ek2id.reindex(EV.pkey.values).values; par = np.where(EV.pkey.values >= 0, par, None)
    TB['engagement_event'] = pd.DataFrame(dict(event_id=EV.event_id.values, customer_id=g.cust_id[EV.cidx.values], event_ts=tfmt(EV.ts.values),
                                               event_type=np.array(S.EVENT_TYPES)[EV.et.values], channel=np.array(S.EVENT_CH)[EV.ch.values], product_id=pid,
                                               parent_event_id=par, action_id=np.where(EV.act.values >= 0, act_ids[np.clip(EV.act.values, 0, None)], None)))
    TB['support_case'] = pd.DataFrame(dict(case_id=CS.case_id.values, customer_id=g.cust_id[CS.cidx.values], order_id=CS.order_id.values, opened_ts=tfmt(CS.open_sec.values),
                                           closed_ts=tfmt(CS.close_sec.values), category=np.array(S.CASE_CATS)[CS.cat.values], priority=np.array(S.CASE_PRI)[CS.pri.values],
                                           channel=np.array(S.CASE_CH)[CS.chn.values], status=CS.status.values, escalated_flag=CS.esc.astype(int).values,
                                           escalated_ts=tfmt(CS.esc_sec.values), handling_minutes=CS.minutes.astype('Int64').values,
                                           cost_amount=money(CS.cost_c.values), csat_score=CS.csat.astype('Int64').values))
    TB['support_case']['cost_amount'] = TB['support_case']['cost_amount'].where(CS.cost_c.notna().values)
    ce = [pd.DataFrame(dict(case_id=CS.case_id.values, ts=CS.open_sec.values, fr=None, to='open', rk=0))]
    m_ = CS.esc.values; ce.append(pd.DataFrame(dict(case_id=CS.case_id.values[m_], ts=CS.esc_sec.values[m_], fr='open', to='escalated', rk=1)))
    m_ = CS.close_sec.notna().values; ce.append(pd.DataFrame(dict(case_id=CS.case_id.values[m_], ts=CS.close_sec.values[m_],
                                                                   fr=np.where(CS.esc.values[m_], 'escalated', 'open'), to='closed', rk=2)))
    ce = pd.concat(ce, ignore_index=True).sort_values(['ts', 'case_id', 'rk'], kind='stable').reset_index(drop=True)
    TB['support_case_event'] = pd.DataFrame(dict(case_event_id=mk_ids('CEV-2026-', 1, len(ce), 6), case_id=ce.case_id.values, event_ts=tfmt(ce.ts.values),
                                                 from_status=ce.fr.values, to_status=ce.to.values))
    TB['consent'] = pd.DataFrame(dict(consent_id=con.consent_id.values, customer_id=g.cust_id[con.cidx.values], channel=np.array(CC)[con.ch.values], purpose='marketing',
                                      status=con.status.values, effective_from=tfmt(con.f.values), effective_to=tfmt(con.t.values), source=con.src.values,
                                      lawful_basis='consent', previous_consent_id=con.prev_id.values))
    sup_ = {s[0]: s for s in S.SEGMENTS}
    TB['segment_rule'] = pd.DataFrame([dict(segment_id=S.SEG_ID[s[0]], segment_code=s[0], segment_name=s[1], exclusive_group=s[2], is_exclusive=int(s[3]), priority=s[4],
                                            rule_version=s[6], rule_params=json.dumps(s[5], sort_keys=True), rule_expression=S.rule_text(s[5]), status=s[7],
                                            effective_from=s[8], effective_to=s[9], superseded_by=S.SEG_ID['DORMANT'] if s[0] == 'DORMANT_V1' else None) for s in S.SEGMENTS])
    def mframe(m, day):
        e = lambda c: m[c].astype('Int64').values
        return pd.DataFrame(dict(snapshot_date=dfmt(np.full(len(m), day)), customer_id=g.cust_id[m.cidx.values], n_orders=e('n_orders'),
                                 first_order_date=dfmt(m.first_order_day.values), last_order_date=dfmt(m.last_order_day.values), recency_days=e('recency_days'),
                                 first_order_age_days=e('first_order_age_days'), gross_merchandise=money(m.gross_c), refund_total=money(m.refund_c),
                                 net_monetary=money(m.net_c), return_rate=np.round(m.return_rate.values, 4), r_score=e('r_score'), f_score=e('f_score'), m_score=e('m_score'),
                                 opens_90d=e('opens_90d'), clicks_90d=e('clicks_90d'), cases_12m=e('cases_12m'), service_cost_12m=np.round(m.service_cost_12m.values, 2),
                                 consent_withdrawals_90d=e('consent_withdrawals_90d')))
    TB['customer_metric_snapshot'] = pd.concat([mframe(m1, S1), mframe(m2s, S2)], ignore_index=True)
    TB['segment_membership'] = pd.DataFrame(dict(membership_id=mem.membership_id.values, segment_id=np.array([S.SEG_ID[s[0]] for s in S.SEGMENTS], dtype=object)[mem.sidx.values],
                                                 customer_id=g.cust_id[mem.cidx.values], effective_from=dfmt(mem.eff_from.values), effective_to=dfmt(mem.eff_to.values),
                                                 is_current=mem.eff_to.isna().astype(int).values, evaluated_snapshot_date=dfmt(mem.eval_snap.values),
                                                 explanation=mem.explanation.values, assigned_by=mem.assigned_by.values))
    TB['action_catalog'] = pd.DataFrame([dict(action_id=S.ACT_ID[x[0]], action_code=x[0], action_name=x[1], purpose=x[2], objective=x[3], allowed_channels='|'.join(x[4]),
                                              requires_consent=int(x[5]), is_discount=int(x[6]), discount_pct=x[7], unit_cost=x[8],
                                              precondition=S.ACT_PRECONDITION.get(x[0]), status='active', effective_from='2025-01-01', effective_to=None) for x in S.ACTIONS])
    TB['action_segment_eligibility'] = pd.DataFrame([dict(eligibility_id='ELG-%04d' % (i + 1), action_id=S.ACT_ID[a], segment_id=S.SEG_ID[s], priority=pr,
                                                          effective_from='2025-01-01', effective_to=None) for i, (a, s, pr) in enumerate(S.ELIGIBILITY)])
    TB['suppression_rule'] = pd.DataFrame([dict(suppression_id=x[0], suppression_code=x[1], description=x[2], evaluation_point=x[3], applies_to=x[4]) for x in S.SUPPRESSION])
    TB['action_outcome'] = ao
    # ---------------- 9. ground-truth files (separate; never joined into inputs)
    life_idx = [i for i, s in enumerate(S.SEGMENTS) if s[3] and s[7] == 'active']
    t1 = A1[A1.sidx.isin(life_idx)].set_index('cidx').sidx; t2 = A2_true[A2_true.sidx.isin(life_idx)].set_index('cidx').sidx
    labels = pd.DataFrame(dict(customer_id=g.cust_id, generator_archetype=ARCH_NAMES[g.arch], flag_returner=g.returner.astype(int), flag_high_service=g.high_service.astype(int),
                               flag_consent_withdrawal_planned=g.flag_wd.astype(int),
                               expected_lifecycle_segment_2026_07_01=segcode[t1.reindex(np.arange(N)).fillna(-1).astype(int).clip(0).values],
                               expected_lifecycle_segment_2026_10_01=segcode[t2.reindex(np.arange(N)).fillna(-1).astype(int).clip(0).values]))
    labels.loc[~np.isin(np.arange(N), t1.index.values), 'expected_lifecycle_segment_2026_07_01'] = None
    labels.loc[~np.isin(np.arange(N), t2.index.values), 'expected_lifecycle_segment_2026_10_01'] = None
    write_outputs(a, TB, gtdf, labels, scale, N, NO, NE)


def write_outputs(a, TB, gtdf, labels, scale, N, NO, NE):
    out = a.out
    for sub in ('data', 'json', 'ground_truth', 'schema', 'sql'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    sums = {}
    for t in S.TABLE_ORDER:
        df = TB[t]
        path = os.path.join(out, 'data', t + '.csv'); df.to_csv(path, index=False, lineterminator='\n')
        sums[t] = dict(rows=len(df), sha256=sha256(path), bytes=os.path.getsize(path))
        if len(df) <= 120000 and not a.no_json:
            df.to_json(os.path.join(out, 'json', t + '.json'), orient='records', indent=None)
    gp = os.path.join(out, 'ground_truth', 'ground_truth.csv'); gtdf.to_csv(gp, index=False, lineterminator='\n')
    lp = os.path.join(out, 'ground_truth', 'ground_truth_customer_labels.csv'); labels.to_csv(lp, index=False, lineterminator='\n')
    sums['ground_truth'] = dict(rows=len(gtdf), sha256=sha256(gp)); sums['ground_truth_customer_labels'] = dict(rows=len(labels), sha256=sha256(lp))
    summ = gtdf.groupby('issue_type').size().to_dict()
    json.dump(dict(description='Known injected anomalies and expected labels. NOT an input feature source; never joined into input tables.',
                   anomaly_counts=summ, files=['ground_truth.csv', 'ground_truth_customer_labels.csv'], total_anomalies=int(len(gtdf))),
              open(os.path.join(out, 'ground_truth', 'ground_truth.json'), 'w'), indent=2)
    gtdf.to_json(os.path.join(out, 'ground_truth', 'ground_truth_rows.json'), orient='records')
    # schema artefacts
    open(os.path.join(out, 'schema', 'schema.sql'), 'w').write(S.ddl())
    dr = pd.DataFrame(S.dictionary_rows()); dr.to_csv(os.path.join(out, 'schema', 'data_dictionary.csv'), index=False, lineterminator='\n')
    dr.to_json(os.path.join(out, 'schema', 'data_dictionary.json'), orient='records', indent=1)
    write_dictionary_md(os.path.join(out, 'schema', 'data_dictionary.md'), dr)
    json.dump(dict(rfm_bins=S.RFM_BINS, tax_rate=S.TAX_RATE, free_shipping_threshold_usd=S.FREE_SHIP_THRESHOLD_USD, shipping_fee_usd=S.SHIP_FEE_USD,
                   case_cost_per_minute_usd=S.CASE_COST_PER_MIN, case_escalation_fee_usd=S.CASE_ESCALATION_FEE, attribution_window_days=S.ATTRIBUTION_WINDOW_DAYS,
                   holdout_rate=S.HOLDOUT_RATE, snapshot_dates=['2026-07-01', '2026-10-01'], data_window=['2025-01-01', '2026-09-30']),
              open(os.path.join(out, 'schema', 'business_rule_constants.json'), 'w'), indent=2)
    manifest = dict(generator='generate_data.py', command='python3 generate_data.py ' + ' '.join(sys.argv[1:]), seed=a.seed,
                    parameters=dict(n_customers=N, n_orders=NO, n_events=NE, scale=scale), python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                    external_data_used=False, provenance='100% synthetic; generated by seeded code. No external dataset, no personal data, no scraping.',
                    sources=[], files=sums)
    json.dump(manifest, open(os.path.join(out, 'source_manifest.json'), 'w'), indent=2)
    if not a.no_db:
        build_db(a, TB)
    log('exported %s' % out)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def write_dictionary_md(path, dr):
    with open(path, 'w') as f:
        f.write('# Data dictionary\n\nGenerated from `schema_spec.py`. Types: STRING, INT, DECIMAL (USD, 2dp), DATE (ISO-8601), TIMESTAMP (UTC, `YYYY-MM-DD HH:MM:SS`), BOOL (0/1), ENUM, JSON.\n\n')
        for t in S.TABLE_ORDER:
            d = S.TABLES[t]
            f.write('## %s\n\n%s\n\n- **Primary key:** %s\n- **Foreign keys:** %s\n- **Cardinality / relationships:** %s\n\n' % (
                t, d['desc'], ', '.join(d['pk']), '; '.join('%s -> %s.%s' % x for x in d['fks']) or 'none', d['cardinality']))
            f.write('| field | type | req | allowed values / units | unique | PK | FK | validation rule |\n|---|---|---|---|---|---|---|---|\n')
            for r in dr[dr.table == t].itertuples():
                f.write('| %s | %s | %s | %s | %s | %s | %s | %s |\n' % (r.field, r.type, r.required, str(r.allowed_values_or_units).replace('|', '\\|'), r.unique,
                                                                      r.primary_key, r.foreign_key, str(r.validation_rule).replace('|', '\\|')))
            f.write('\n')

def build_db(a, TB):
    d = os.path.join(a.out, 'sql'); dbp = os.path.join(d, 'cdp_seed.sqlite')
    if os.path.exists(dbp): os.remove(dbp)
    con = sqlite3.connect(dbp)
    con.executescript(S.ddl())
    for t in S.TABLE_ORDER:
        TB[t].to_sql(t, con, if_exists='append', index=False, chunksize=100000)
    con.commit()
    fk = con.execute('PRAGMA foreign_key_check').fetchall()
    log('sqlite built; foreign_key_check violations: %d' % len(fk))
    with gzip.GzipFile(os.path.join(d, 'seed.sql.gz'), 'wb', mtime=0) as gz:
        for line in con.iterdump():
            gz.write((line + '\n').encode())
    con.close()
    os.remove(dbp) if a.__dict__.get('drop_db') else None


if __name__ == '__main__':
    main()
