#!/usr/bin/env python3
"""Generate stock scan HTML report — WeChat Article design."""

import json, math, os
from datetime import datetime

BASE = "/Users/huangjicheng/go/src/github.com/market-scan/scan"
CODES = ["HOOD","COIN","TEM","APLD","CRWV","VCX","CRCL","FLY"]
TODAY = datetime.now().strftime("%Y-%m-%d")

# ─── helpers ───────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path) as f:
        return json.load(f)

def fmt(v, spec=".2f"):
    if v is None: return "—"
    try: return f"{v:{spec}}"
    except: return str(v)

def fmt_num(v, spec=".2f"):
    if v is None: return "—"
    try: return f"{abs(v):{spec}}"
    except: return str(v)

def chg_class(v):
    if v is None: return "chg-neutral"
    return "chg-up" if v >= 0 else "chg-dn"

def chg_arrow(v):
    if v is None: return "—"
    return "▲" if v >= 0 else "▼"

def score_color(s):
    if s is None: return "#888"
    if s >= 75: return "#2e7d5e"
    if s >= 55: return "#2e7d5e"
    if s >= 40: return "#9a7a2e"
    return "#d64545"

def score_label(s):
    if s is None: return "暂无"
    if s >= 75: return "强烈买入"
    if s >= 55: return "买入"
    if s >= 40: return "持有"
    return "卖出"

def badge_class(s):
    if s >= 75: return "badge badge-strong"
    if s >= 55: return "badge badge-buy"
    if s >= 40: return "badge badge-hold"
    return "badge badge-sell"

def esc(s):
    if s is None: return ""
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def safe_float(val, default=0.0):
    if val is None: return default
    try: return float(val)
    except: return default

# ─── data loading ───────────────────────────────────────────────────────────────

def extract_klines(data):
    chart = data.get("chart") or data
    result = chart.get("result", [])
    if not result: return []
    r = result[0]
    ts = r.get("timestamp", [])
    quote = (r.get("indicators", {}).get("quote") or [{}])[0]
    closes  = quote.get("close", [])
    opens   = quote.get("open", [])
    highs   = quote.get("high", [])
    lows    = quote.get("low", [])
    volumes = quote.get("volume", [])
    out = []
    for i in range(len(ts)):
        out.append({
            "open":    opens[i]   if i < len(opens)   and opens[i]   is not None else None,
            "high":    highs[i]   if i < len(highs)   and highs[i]   is not None else None,
            "low":     lows[i]    if i < len(lows)    and lows[i]    is not None else None,
            "close":   closes[i]  if i < len(closes)  and closes[i]  is not None else None,
            "volume":  volumes[i] if i < len(volumes) and volumes[i] is not None else None,
        })
    return out

def load_news(raw):
    if isinstance(raw, dict):
        items = raw.get("news", [])
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    out = []
    for n in items[:5]:
        ts = n.get("providerPublishTime")
        out.append({
            "title":   n.get("title", ""),
            "date":    datetime.fromtimestamp(ts).strftime("%m-%d") if ts else "??",
            "source":  n.get("publisher", "") or n.get("publisher", ""),
        })
    return out

raw_stocks = {}
for c in CODES:
    raw_stocks[c] = {
        "1d":   extract_klines(load_json(f"{BASE}/{c}_1d.json")),
        "60d":  extract_klines(load_json(f"{BASE}/{c}_60d.json")),
        "news": load_news(load_json(f"{BASE}/{c}_news.json")),
    }

qqq_1d  = extract_klines(load_json(f"{BASE}/QQQ_1d.json"))
qqq_60d = extract_klines(load_json(f"{BASE}/QQQ_60d.json"))

# ─── technical indicators ──────────────────────────────────────────────────────

def calc_ma(klines, period):
    vals = [float(k["close"]) for k in klines[-period:] if k.get("close") is not None]
    return sum(vals)/len(vals) if len(vals) == period else None

def calc_macd(klines, fast=12, slow=26, signal=9):
    def ema(period):
        vals = [float(k["close"]) for k in klines if k.get("close") is not None]
        if len(vals) < period: return None
        m = 2/(period+1)
        e = sum(vals[:period])/period
        for p in vals[period:]: e = (p-e)*m + e
        return e
    ef = ema(fast); es = ema(slow)
    if ef is None or es is None: return None, None, None
    dif = ef - es
    k_list = [float(k["close"]) for k in klines if k.get("close") is not None]
    if len(k_list) < slow+signal: return dif, None, None
    dea = dif
    m = 2/(signal+1)
    for _ in range(signal): dea = (dif-dea)*m + dea
    return dif, dea, 2*(dif-dea)

def calc_kdj(klines, period=9):
    vals = klines[-period:]
    lows  = [float(k["low"])  for k in vals if k.get("low")  is not None]
    highs = [float(k["high"]) for k in vals if k.get("high") is not None]
    close = klines[-1].get("close")
    if not lows or not highs or close is None: return None, None, None
    rsv = 100*(float(close)-min(lows))/(max(highs)-min(lows)+1e-9)
    k = d = 50.0
    for _ in range(period-1):
        k = k*2/3 + rsv/3
        d = d*2/3 + k/3
    return k, d, 3*k-2*d

def calc_boll(klines, period=20):
    vals = [float(k["close"]) for k in klines[-period:] if k.get("close") is not None]
    if len(vals) < period: return None, None, None
    mid = sum(vals)/period
    std = math.sqrt(sum((v-mid)**2 for v in vals)/period)
    return mid+2*std, mid, mid-2*std

def ma_order(klines):
    ma5  = calc_ma(klines, 5)
    ma10 = calc_ma(klines, 10)
    ma20 = calc_ma(klines, 20)
    ma60 = calc_ma(klines, 60)
    if not klines or klines[-1].get("close") is None: return False, False, (None,)*4
    price = float(klines[-1]["close"])
    above   = ma60 is not None and price > ma60
    aligned = all(x is not None for x in [ma5,ma10,ma20,ma60]) and ma5>ma10>ma20>ma60
    return above, aligned, (ma5, ma10, ma20, ma60)

def volume_ratio(klines):
    vols = [float(k["volume"]) for k in klines[-20:-1] if k.get("volume") is not None]
    cur  = klines[-1].get("volume")
    if not vols or cur is None: return 1.0
    return round(float(cur)/max(sum(vols)/len(vols), 1), 2)

def calc_gaps(klines):
    gaps = []
    for i in range(1, min(len(klines), 11)):
        prev = klines[-i-1].get("close")
        curr = klines[-i].get("open")
        if prev and curr and prev != 0:
            gaps.append(round((float(curr)-float(prev))/float(prev)*100, 1))
    return list(reversed(gaps))

# ─── scoring ───────────────────────────────────────────────────────────────────

def tech_score(k1, k60):
    s = 0
    above, aligned, _ = ma_order(k1)
    if above: s += 10
    if aligned: s += 10
    dif, dea, bar = calc_macd(k1)
    if dif and dif > 0: s += 10
    if bar and bar > 0: s += 5
    k, d, j = calc_kdj(k1)
    if k and k < 80: s += 5
    if len(k60) >= 20:
        closes = [float(k["close"]) for k in k60[-20:] if k.get("close") is not None]
        if len(closes) >= 20:
            pos = (closes[-1]-min(closes))/(max(closes)-min(closes)+1e-9)*100
            if pos > 60: s += 5
            elif pos < 40: s -= 5
    vr = volume_ratio(k1)
    if vr > 2: s += 5
    elif vr < 0.5: s -= 5
    return min(30, max(0, s))

def news_score(news_list):
    if not news_list: return 5
    # 利好关键词（中英文）
    pos_kw = [
        # 英文
        "buy","upgrade","bull","surge","growth","record","partnership","expansion",
        "rally","soar","jump","gain","rise","approval","approved","regulatory",
        "beat","exceed","outperform","strong","momentum","catalyst","bloom",
        # 中文
        "大涨","上涨","飙升","暴涨","创新高","回购","增持","利好",
        "改革","取消","批准","通过","赢家","受益","催化","突破","扩张","合作",
        "超预期","业绩","增长","利润","收入","分红","派息"
    ]
    # 利空关键词（中英文）
    neg_kw = [
        # 英文
        "sell","downgrade","bear","crash","warning","lawsuit","plunge","cut","fraud",
        "probe","investigation","penalty","fine","ban","restrict","charge","enforcement",
        "miss","weak","decline","fall","drop","risk","concern","fear","loss","violation",
        # 中文
        "大跌","下跌","暴跌","起诉","指控","调查","罚款","警告","利空",
        "违规","欺诈","减持","风险","亏损","泡沫","崩盘","腰斩","割肉","卖出"
    ]
    pos = sum(1 for n in news_list if any(w in n["title"]
        for w in pos_kw))
    neg = sum(1 for n in news_list if any(w in n["title"]
        for w in neg_kw))
    return min(10, max(0, 5 + pos*2 - neg*3))

def rating_score(news_list):
    n = len(news_list)
    if n >= 5: return 10
    if n >= 3: return 7
    if n >= 1: return 5
    return 3

SECTOR_MAP = {"COIN":8,"HOOD":7,"APLD":9,"CRWV":9,"TEM":8,"FLY":7,"CRCL":8,"VCX":4}

def fund_score(code, k60):
    if len(k60) < 2: return 20
    c0 = k60[0].get("close"); c1 = k60[-1].get("close")
    if not c0 or not c1 or float(c0) == 0: return 20
    chg = (float(c1)-float(c0))/float(c0)*100
    if chg > 20: return 40
    if chg > 10: return 35
    if chg > 0:  return 30
    if chg > -10: return 25
    if chg > -20: return 20
    return 15

# ─── build stock ───────────────────────────────────────────────────────────────

NAME_MAP = {
    "HOOD":"Robinhood Markets","COIN":"Coinbase Global","TEM":"Tempus AI",
    "APLD":"Applied Digital","CRWV":"CoreWeave","VCX":"Fundrise Growth",
    "CRCL":"Circle Internet","FLY":"Firefly Aerospace",
}

def build_stock(code, d):
    k1  = d["1d"]
    k60 = d["60d"]
    nw  = d["news"]

    price = safe_float(k1[-1].get("close")) if k1 else 0.0
    prev  = safe_float(k1[-2].get("close")) if len(k1)>1 else price
    chg_d = (price-prev)/prev*100 if prev else 0.0

    c0_60 = safe_float(k60[0].get("close")) if k60 else 0.0
    c60   = safe_float(k60[-1].get("close")) if k60 else 0.0
    chg_60d = (c60-c0_60)/c0_60*100 if c0_60 else 0.0

    high52 = max(safe_float(k["high"]) for k in k60 if k.get("high") is not None) if k60 else price
    low52  = min(safe_float(k["low"])  for k in k60 if k.get("low")  is not None) if k60 else price
    pos52  = (price-low52)/(high52-low52+1e-9)*100 if high52!=low52 else 50.0

    above, aligned, mas = ma_order(k1)
    ma5, ma10, ma20, ma60 = mas
    dif, dea, bar = calc_macd(k1)
    k, d, j = calc_kdj(k1)
    upper, mid_b, lower = calc_boll(k1)
    gaps = calc_gaps(k1)
    vr = volume_ratio(k1)

    price_in_boll = None
    if upper and lower and upper != lower:
        price_in_boll = round((price-lower)/(upper-lower)*100, 1)

    t_s  = tech_score(k1, k60)
    f_s  = fund_score(code, k60)
    sec  = SECTOR_MAP.get(code, 5)
    r_s  = rating_score(nw)
    n_s  = news_score(nw)
    total = t_s + f_s + sec + r_s + n_s

    return dict(code=code, name=NAME_MAP[code], price=price,
        chg_d=round(chg_d,2), chg_60d=round(chg_60d,2),
        high52=round(high52,2), low52=round(low52,2), pos52=round(pos52,1),
        volume_ratio=vr,
        ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60,
        above_ma60=above, ma_aligned=aligned,
        dif=dif, dea=dea, macd_bar=bar,
        k=k, d=d, j=j,
        boll_upper=upper, boll_mid=mid_b, boll_lower=lower,
        price_in_boll=price_in_boll, gaps=gaps,
        tech_score=t_s, fund_score=f_s, sector_score=sec,
        rating_score=r_s, news_score=n_s, total_score=total,
        news=nw)

STOCKS = [build_stock(c, raw_stocks[c]) for c in CODES]
STOCKS.sort(key=lambda x: x["total_score"], reverse=True)
for i, s in enumerate(STOCKS): s["rank"] = i+1

# ─── qqq ──────────────────────────────────────────────────────────────────────

qqq_price = safe_float(qqq_1d[-1].get("close")) if qqq_1d else 0.0
qqq_prev  = safe_float(qqq_1d[-2].get("close")) if len(qqq_1d)>1 else qqq_price
qqq_chg_d = (qqq_price-qqq_prev)/qqq_prev*100 if qqq_prev else 0.0
q60_0 = safe_float(qqq_60d[0].get("close")) if qqq_60d else 0.0
q60_l = safe_float(qqq_60d[-1].get("close")) if qqq_60d else 0.0
qqq_chg_60d = (q60_l-q60_0)/q60_0*100 if q60_0 else 0.0
qqq_high = fmt(max(safe_float(k["high"]) for k in qqq_60d if k.get("high") is not None) if qqq_60d else 0)
qqq_low  = fmt(min(safe_float(k["low"])  for k in qqq_60d if k.get("low")  is not None) if qqq_60d else 0)

# ─── hero picks (Top 3 >= 55) ─────────────────────────────────────────────────

def get_reason(s):
    code = s["code"]
    reasons = {
        "FLY":  "空天赛道政策催化，Q1财报（5/4）临近，KDJ低位反弹空间大",
        "CRCL": "稳定币USDC监管利好，60日涨幅最强，布林中轨支撑明确",
        "CRWV": "AI算力租赁核心资产，多头排列，中线目标$135",
        "APLD": "AI数据中心持续扩张，布林中轨支撑，目标$42",
        "COIN": "加密市场回调中$182附近有支撑，长期逻辑不变",
        "HOOD": "Q1财报（5月上旬）临近催化，回调后可布局",
        "VCX":  "基金暴跌后极端缺口未回补，均线空头排列，流动性差",
        "TEM":  "AI医疗赛道长期逻辑清晰，Q1财报是关键催化",
    }
    return reasons.get(code, f"{score_label(s['total_score'])}，关注量能变化")

buy_candidates = [s for s in STOCKS if s["total_score"] >= 55]
top3 = buy_candidates[:3] if len(buy_candidates) >= 3 else buy_candidates + STOCKS[len(buy_candidates):3-len(buy_candidates)+len(buy_candidates)]

hero_picks_html = ""
for rank, s in enumerate(top3, 1):
    label = score_label(s["total_score"])
    hero_picks_html += f"""<div class="hero-pick" onclick="showDetail('{s["code"]}')">
  <span class="pick-rank">#{rank}</span>
  <div class="pick-info">
    <div class="pick-ticker">{s["code"]} <small>{esc(s["name"])}</small></div>
    <div class="pick-reason">{esc(get_reason(s))}</div>
  </div>
  <div class="pick-score">
    <div class="pick-score-num" style="color:{score_color(s["total_score"])}">{s["total_score"]}</div>
    <div class="pick-score-lbl">{esc(label)}</div>
  </div>
</div>
"""

# ─── hero title / sub ──────────────────────────────────────────────────────────

buy_s  = [s for s in STOCKS if s["total_score"] >= 55]
sell_s = [s for s in STOCKS if s["total_score"] < 40]

if qqq_chg_d >= 0:
    bench_trend = "震荡偏强"
else:
    bench_trend = "震荡走弱"

if len(buy_s) >= 3:
    hero_title = f"重点关注 {', '.join(s['code'] for s in buy_s[:3])} 等{len(buy_s)}只标的"
elif len(buy_s) >= 1:
    hero_title = f"关注 {buy_s[0]['code']} 等买入机会"
else:
    hero_title = "当前无明确买入标的，等待机会"

hero_sub = f"QQQ 今日 {chg_arrow(qqq_chg_d)}{fmt_num(qqq_chg_d)}%，60日涨跌 {chg_arrow(qqq_chg_60d)}{fmt_num(qqq_chg_60d)}%，当前处于{bench_trend}期"

# ─── benchmark stats ─────────────────────────────────────────────────────────

bench_price = f"${fmt(qqq_price)}"
bench_chg_d = f"{chg_arrow(qqq_chg_d)} {fmt_num(qqq_chg_d)}%"
bench_chg_60 = f"{chg_arrow(qqq_chg_60d)} {fmt_num(qqq_chg_60d)}%"

# ─── table rows ───────────────────────────────────────────────────────────────

table_rows_html = ""
for s in STOCKS:
    bc = badge_class(s["total_score"])
    lbl = score_label(s["total_score"])
    cc = score_color(s["total_score"])
    a_d = chg_arrow(s["chg_d"])
    c_d = chg_class(s["chg_d"])
    a_60 = chg_arrow(s["chg_60d"])
    c_60 = chg_class(s["chg_60d"])
    action_map = {
        "FLY": "等Q1财报落地后加仓",
        "CRCL": "布林中轨$96支撑，中线持有",
        "CRWV": "多头排列，持有，目标$135",
        "APLD": "$38-42区间高抛低吸",
        "COIN": "$182附近低吸，目标$215",
        "HOOD": "不加仓，等Q1财报催化",
        "VCX": "卖出，不建议建仓",
        "TEM": "$52附近低吸，目标$60",
    }
    action = action_map.get(s["code"], "关注量能变化")

    table_rows_html += f"""<tr onclick="showDetail('{s["code"]}')">
  <td class="rank">{s["rank"]}</td>
  <td><div class="ticker">{s["code"]}</div><div class="sname">{esc(s["name"])}</div></td>
  <td><span style="font-family:var(--mono);font-size:16px;font-weight:700;color:{cc}">{s["total_score"]}</span><br><span class="{bc.split()[1]}">{esc(lbl)}</span></td>
  <td class="hide-sm price">${fmt(s["price"])}</td>
  <td class="chg {c_d}">{a_d} {fmt_num(s["chg_d"])}%</td>
  <td class="hide-sm chg {c_60}">{a_60} {fmt_num(s["chg_60d"])}%</td>
  <td class="hide-sm pos52">{fmt(s["pos52"],".0f")}%</td>
  <td class="action">{esc(action)}</td>
</tr>
"""

# ─── sector hotspots ──────────────────────────────────────────────────────────

sector_data = [
    ("空天与国防", "🚀", "FLY领涨空天板块，政策支持叠加财报季催化，短期动能强劲"),
    ("加密资产", "₿", "COIN/CRCL受监管消息影响回调，CRCL 60日涨幅最强，趋势未坏"),
    ("AI算力", "⚡", "APLD/CRWV保持AI数据中心叙事，CRWV多头排列，APLD关注$42目标"),
    ("AI医疗", "🏥", "TEM赛道长期逻辑清晰，Q1财报（5月初）是近期关键节点"),
]

sector_hotspots_html = '<div class="section-hdr" style="margin-top:8px">板块热点</div>\n<div class="sectors">\n'
for name, icon, desc in sector_data:
    sector_hotspots_html += f"""<div class="sector-card">
  <div class="sector-icon">{icon}</div>
  <div class="sector-body">
    <div class="sector-name">{name}</div>
    <div class="sector-desc">{desc}</div>
  </div>
</div>
"""
sector_hotspots_html += "</div>\n"

# ─── modal ────────────────────────────────────────────────────────────────────

def modal_html(s):
    bc = badge_class(s["total_score"])
    lbl = score_label(s["total_score"])
    total = s["total_score"]
    cc = score_color(total)
    a_d = chg_arrow(s["chg_d"])
    a_60 = chg_arrow(s["chg_60d"])
    c_d = chg_class(s["chg_d"])
    c_60 = chg_class(s["chg_60d"])

    # modal header bg
    m_bg = "#8b2525" if total < 40 else "var(--ink)"

    # score ring color
    ring_color = cc

    # score bar configs
    configs = [
        ("技术面",    s["tech_score"],    30, "#aaa"),
        ("基本面",    s["fund_score"],    40, "#5b9bd5"),
        ("板块",      s["sector_score"],  20, "var(--green)"),
        ("机构评级",  s["rating_score"],  10, "var(--gold)"),
        ("消息面",    s["news_score"],    10, "var(--green)" if s["news_score"]>=5 else "var(--red)"),
    ]
    bars_html = ""
    for lbl_s, sc, mx, clr in configs:
        pct = sc/mx*100
        bars_html += f"""<div class="score-row"><span class="score-label">{lbl_s}</span><div class="score-track"><div class="score-fill" style="width:{pct:.0f}%;background:{clr}"></div></div><span class="score-val" style="color:{clr}">{sc}/{mx}</span></div>"""

    # KDJ note
    kdj_note = ""
    if s["j"]:
        if s["j"]>90: kdj_note = "⚠️严重超买"
        elif s["j"]<20: kdj_note = "⚠️严重超卖"
        elif s["j"]>80: kdj_note = "超买"
        elif s["j"]<30: kdj_note = "超卖"

    # boll note
    boll_note = ""
    if s["price_in_boll"] is not None:
        if s["price_in_boll"]>90: boll_note = "↑突破上轨"
        elif s["price_in_boll"]<10: boll_note = "↓跌破下轨"

    gaps_str = ", ".join("{0:+.1f}%".format(g) for g in s["gaps"]) if s["gaps"] else "无明显缺口"

    def trow(label, val, note=""):
        n = f' <span style="color:var(--muted);font-size:10px">{esc(note)}</span>' if note else ""
        return f"<tr><td class='lbl'>{esc(label)}</td><td class='val'>{esc(str(val))}{n}</td></tr>"

    # MA rows — handle N/A
    ma_rows = ""
    ma_vals = [s["ma5"], s["ma10"], s["ma20"], s["ma60"]]
    if any(v is not None for v in ma_vals):
        ma_rows = trow("MA5 · MA10 · MA20 · MA60",
            " · ".join(f"${fmt(v)}" if v is not None else "—" for v in ma_vals))
    else:
        ma_rows = trow("MA5 · MA10 · MA20 · MA60", "— (历史数据不足)")

    # MACD
    macd_rows = ""
    if s["dif"] is not None:
        macd_ok = s["dea"] is not None and s["dif"] > s["dea"]
        macd_note = "↑金叉" if macd_ok else "↓死叉"
        macd_zone = "零轴上方" if s["dif"] > 0 else "零轴下方"
        macd_bar_val = fmt(s["macd_bar"], ".3f") if s["macd_bar"] is not None else "—"
        macd_bar_note = ("红柱" if s["macd_bar"] and s["macd_bar"]>0 else "绿柱") if s["macd_bar"] is not None else ""
        macd_rows = trow("MACD/DIF", fmt(s["dif"],".3f"), macd_note) + \
                    trow("MACD/DEA", fmt(s["dea"],".3f"), macd_zone) + \
                    trow("MACD柱", macd_bar_val, macd_bar_note)
    else:
        macd_rows = trow("MACD", "— (历史数据不足)")

    # Boll
    boll_rows = ""
    if s["boll_upper"] is not None:
        boll_note2 = boll_note if boll_note else ""
        boll_rows = trow("布林上轨", f"${fmt(s['boll_upper'])}", boll_note2) + \
                    trow("布林中轨", f"${fmt(s['boll_mid'])}") + \
                    trow("布林下轨", f"${fmt(s['boll_lower'])}")
    else:
        boll_rows = trow("布林带", "— (历史数据不足)")

    # news
    news_html = ""
    if s["news"]:
        for n in s["news"][:5]:
            news_html += f"""<div class="news-item">
  <span class="news-title">{esc(n["title"])}</span>
  <span class="news-meta">{esc(n["date"])} · {esc(n["source"])}</span>
</div>
"""
    else:
        news_html = "<p style='font-size:12px;color:var(--muted)'>暂无最新新闻</p>"

    # advice
    advice_map = {
        "FLY":  f"持有。空天赛道政策支持，KDJ J={fmt(s['j'],'.0f')} 偏低有反弹空间。Q1财报（5月4日）是近期关键催化，等财报落地后再加仓。",
        "CRCL": f"持有。稳定币USDC监管利好预期，60日涨幅 {chg_arrow(s['chg_60d'])}{fmt_num(s['chg_60d'])}% 是本次最强。${fmt(s['price'])} 附近布林中轨支撑，中线目标$110。仓位10-15%。",
        "CRWV": f"持有。AI算力租赁核心标的，多头排列持续。${fmt(s['price'])} 附近有布林中轨支撑，目标$135。内部人减持是短期风险。仓位15%。",
        "APLD": f"AI数据中心扩张利好持续。KDJ J={fmt(s['j'],'.0f')} {'偏高' if s['j'] and s['j']>80 else '正常'}，{'布林已突破上轨，短线极热，等回调；' if boll_note else ''}${fmt(s['price'])} 附近有支撑，目标$42。止损$25。仓位5-10%。",
        "COIN": f"持有。加密市场回调 {chg_arrow(s['chg_60d'])}{fmt_num(s['chg_60d'])}% 拖累，${fmt(s['price'])} 附近有布林中轨支撑。止损$182，目标$215。仓位10-15%。",
        "HOOD": f"持有但不加仓。今日 {chg_arrow(s['chg_d'])}{fmt_num(s['chg_d'])}%，Q1财报（5月上旬）临近是关键催化。止损：${fmt(s['ma60'],'g') if s['ma60'] else '$77'}（跌破MA60），目标$88-91。仓位0-10%。",
        "VCX":  "❌ <strong>卖出，不建议建仓。</strong>均线空头排列，MACD零轴下方死叉。基金暴跌后极端缺口未回补，流动性极差，坚决回避。",
        "TEM":  f"持有。AI医疗赛道长期逻辑清晰，Q1财报（5月初）是近期关键催化。等${fmt(s['price'])} 附近支撑位低吸，止损${fmt(s['ma60'],'g') if s['ma60'] else '$42'}（跌破MA60）。目标$60。",
    }
    advice_text = advice_map.get(s["code"], f"{lbl} — {total}/110，注意控制仓位。")
    advice_cls = "strong-buy" if total >= 75 else ("sell" if total < 40 else "")
    advice_cls_attr = f"advice-box {advice_cls}" if advice_cls else "advice-box"

    badge_name = bc.split()[1]  # e.g. "badge-buy"

    return f"""
<div class="m-overlay" id="modal-{s["code"]}" onclick="closeModal(event,'{s["code"]}')">
<div class="m-content" onclick="event.stopPropagation()">
  <button class="m-close" onclick="hideModal('{s["code"]}')">✕</button>
  <div class="m-header" style="background:{m_bg}">
    <div class="m-title-row">
      <div><h2 class="m-code">{s["code"]}</h2><p class="m-name">{esc(s["name"])}</p></div>
      <span class="m-badge {badge_name}">{esc(lbl)} {total}/110</span>
    </div>
    <div class="m-price-row">
      <span class="m-price">${fmt(s["price"])}</span>
      <div class="m-chg">
        <span class="chg-pill chg-pill-up">{a_d} 今日 {fmt_num(s["chg_d"])}%</span>
        <span class="chg-pill chg-pill-up">{a_60} 60日 {fmt_num(s["chg_60d"])}%</span>
      </div>
    </div>
  </div>
  <div class="m-body">
    <div class="score-section">
      <div class="score-total" style="background:{ring_color}">{total}<span class="score-denom">/110</span></div>
      <div class="score-bars">
{bars_html}
      </div>
    </div>

    <h3 class="section-title">技术面指标</h3>
    <table class="tech-table">
      <tr><td class="lbl">现价</td><td class="val">${fmt(s["price"])}</td></tr>
      <tr><td class="lbl">60日涨跌</td><td class="val {c_60}">{a_60}{fmt_num(s["chg_60d"])}%</td></tr>
      <tr><td class="lbl">52W高 / 低</td><td class="val">${fmt(s["high52"])} / ${fmt(s["low52"])}</td></tr>
      <tr><td class="lbl">52W位置</td><td class="val">{fmt(s["pos52"],".0f")}%</td></tr>
      <tr><td class="lbl">成交量比</td><td class="val">{fmt(s["volume_ratio"],".1f")}x <span style="color:var(--muted);font-size:10px">(近20日均量)</span></td></tr>
      <tr><td class="lbl">KDJ/K · D · J</td><td class="val">{fmt(s["k"],".1f")} · {fmt(s["d"],".1f")} · {fmt(s["j"],".1f")} {esc(kdj_note)}</td></tr>
      {ma_rows}
      {macd_rows}
      {boll_rows}
      <tr><td class="lbl">近10日缺口</td><td class="val">{gaps_str}</td></tr>
    </table>

    <h3 class="section-title">最新新闻</h3>
    <div class="news-list">
{news_html}
    </div>

    <h3 class="section-title">交易建议</h3>
    <div class="{advice_cls_attr}">{advice_text}</div>
  </div>
</div>
</div>"""

modals_html = "\n".join(modal_html(s) for s in STOCKS)

# ─── CSS ──────────────────────────────────────────────────────────────────────

CSS = """@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --ink:#1a1a1a;--gold:#c9a84c;--gold-light:#e8c96d;
  --red:#d64545;--green:#2e7d5e;--muted:#888;
  --border:#e0ddd8;--bg:#fafaf8;--card:#ffffff;
  --mono:'SF Mono','Fira Code','Courier New',monospace;
}
html{font-size:16px;scroll-behavior:smooth}
body{
  font-family:'Noto Sans SC','PingFang SC',sans-serif;
  background:var(--bg);color:var(--ink);line-height:1.7;
  -webkit-font-smoothing:antialiased;max-width:720px;margin:0 auto;padding:0 20px
}
.pub-header{padding:40px 0 24px;border-bottom:1px solid var(--border);margin-bottom:36px;display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px}
.pub-brand{font-family:'Noto Serif SC',serif;font-size:22px;font-weight:700;color:var(--ink);letter-spacing:-0.3px}
.pub-brand span{color:var(--gold)}
.pub-meta{font-size:12px;color:var(--muted);letter-spacing:0.5px}
.pub-disclaimer{font-size:11px;color:var(--muted);margin-top:4px}
.hero{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:28px 28px 24px;margin-bottom:36px;box-shadow:0 1px 4px rgba(0,0,0,0.04)}
.hero-label{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:6px}
.hero-label::before{content:'';display:block;width:20px;height:1px;background:var(--gold)}
.hero-title{font-family:'Noto Serif SC',serif;font-size:20px;font-weight:700;color:var(--ink);margin-bottom:6px;line-height:1.4}
.hero-sub{font-size:13px;color:var(--muted);margin-bottom:24px}
.hero-picks{display:flex;flex-direction:column;gap:10px}
.hero-pick{display:flex;align-items:center;gap:14px;padding:12px 14px;background:var(--bg);border-radius:3px;border-left:3px solid var(--gold);cursor:pointer}
.hero-pick:hover{background:rgba(201,168,76,0.05)}
.pick-rank{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--gold);background:rgba(201,168,76,0.1);padding:2px 7px;border-radius:2px;flex-shrink:0}
.pick-info{flex:1;min-width:0}
.pick-ticker{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--ink)}
.pick-ticker small{font-size:11px;font-weight:400;color:var(--muted)}
.pick-reason{font-size:12px;color:#555;margin-top:2px}
.pick-score{text-align:right;flex-shrink:0}
.pick-score-num{font-family:var(--mono);font-size:20px;font-weight:700;line-height:1}
.pick-score-lbl{font-size:10px;color:var(--muted)}
.bench{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:20px 24px;margin-bottom:36px;display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap}
.bench-name{font-family:'Noto Serif SC',serif;font-size:16px;font-weight:600;color:var(--ink)}
.bench-desc{font-size:11px;color:var(--muted)}
.bench-stats{display:flex;gap:20px;flex-wrap:wrap}
.bench-stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
.bench-stat-val{font-family:var(--mono);font-size:14px;font-weight:600;color:var(--ink)}
.section-hdr{font-family:'Noto Serif SC',serif;font-size:16px;font-weight:700;color:var(--ink);padding-bottom:10px;border-bottom:2px solid var(--ink);margin-bottom:20px;display:flex;align-items:baseline;justify-content:space-between}
.section-hdr span{font-family:'Noto Sans SC',sans-serif;font-size:12px;font-weight:400;color:var(--muted)}
.tbl{width:100%;border-collapse:collapse;margin-bottom:40px;font-size:13px}
.tbl th{font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted);font-weight:500;padding:8px 10px;text-align:left;border-bottom:1px solid var(--border)}
.tbl td{padding:11px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:rgba(201,168,76,0.03)}
.tbl tr{cursor:pointer}
.tbl .rank{font-family:var(--mono);font-size:11px;color:var(--muted);width:32px}
.tbl .ticker{font-family:var(--mono);font-weight:700;font-size:14px;color:var(--ink);line-height:1.2}
.tbl .sname{font-size:10px;color:var(--muted);margin-top:1px}
.badge{display:inline-block;padding:2px 7px;border-radius:2px;font-size:10px;font-weight:600;margin-top:3px;white-space:nowrap}
.badge-buy{background:rgba(46,125,94,0.1);color:var(--green)}
.badge-hold{background:rgba(201,168,76,0.15);color:#9a7a2e}
.badge-sell{background:rgba(214,69,69,0.1);color:var(--red)}
.badge-strong{background:rgba(46,125,94,0.15);color:var(--green);font-weight:700}
.tbl .price{font-family:var(--mono);font-weight:600;font-size:13px}
.chg{font-family:var(--mono);font-size:12px}
.chg-up{color:var(--green)}.chg-dn{color:var(--red)}.chg-neutral{color:var(--muted)}
.tbl .pos52{font-family:var(--mono);font-size:12px;color:var(--muted)}
.tbl .action{font-size:12px;color:var(--muted);text-align:right}
.sectors{margin-bottom:40px;display:flex;flex-direction:column;gap:10px}
.sector-card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:14px 18px;display:flex;align-items:flex-start;gap:14px}
.sector-icon{font-size:20px;flex-shrink:0;margin-top:1px}
.sector-body{flex:1}
.sector-name{font-weight:600;font-size:13px;color:var(--ink);margin-bottom:2px}
.sector-desc{font-size:12px;color:#555;line-height:1.5}
.footer{text-align:center;padding:32px 0;border-top:1px solid var(--border);margin-top:48px}
.footer p{font-size:11px;color:var(--muted)}
.footer .disc{margin-top:4px;font-size:10px}
.m-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:1000;overflow-y:auto;backdrop-filter:blur(2px)}
.m-overlay.open{display:flex;align-items:flex-start;justify-content:center;padding:24px 12px}
.m-content{background:var(--card);border-radius:6px;width:100%;max-width:560px;position:relative;box-shadow:0 20px 60px rgba(0,0,0,0.2);margin:auto}
.m-close{position:absolute;top:14px;right:14px;width:30px;height:30px;border-radius:50%;background:var(--bg);border:1px solid var(--border);cursor:pointer;font-size:13px;color:var(--muted);display:flex;align-items:center;justify-content:center;transition:background .15s}
.m-close:hover{background:var(--border)}
.m-header{background:var(--ink);border-radius:6px 6px 0 0;padding:20px 20px 16px;color:#fff}
.m-title-row{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;gap:10px}
.m-code{font-family:var(--mono);font-size:22px;font-weight:700;color:#fff;line-height:1}
.m-name{font-size:11px;color:rgba(255,255,255,0.5);margin-top:3px}
.m-badge{padding:4px 10px;border-radius:3px;font-size:11px;font-weight:700;flex-shrink:0}
.m-price-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.m-price{font-family:var(--mono);font-size:28px;font-weight:700;color:#fff;line-height:1}
.m-chg{display:flex;gap:8px;flex-wrap:wrap}
.chg-pill{padding:3px 9px;border-radius:3px;font-size:11px;font-weight:500}
.chg-pill-up{background:rgba(46,125,94,0.25);color:#7ecbaa}
.chg-pill-dn{background:rgba(214,69,69,0.25);color:#f08080}
.m-body{padding:18px 20px}
.score-section{display:flex;gap:14px;align-items:center;background:var(--bg);border-radius:4px;padding:12px;margin-bottom:16px;flex-wrap:wrap}
.score-total{width:60px;height:60px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0;color:#fff}
.score-denom{font-size:9px;opacity:.7;font-weight:400}
.score-bars{flex:1;min-width:160px}
.score-row{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.score-row:last-child{margin-bottom:0}
.score-label{width:44px;font-size:11px;color:var(--muted);flex-shrink:0}
.score-track{flex:1;height:4px;background:#e8e5e0;border-radius:2px;overflow:hidden}
.score-fill{height:100%;border-radius:2px}
.score-val{width:28px;text-align:right;font-size:11px;font-weight:700;flex-shrink:0}
.tech-table{width:100%;border-collapse:collapse;margin-bottom:16px}
.tech-table tr:nth-child(even){background:var(--bg)}
.tech-table td{padding:6px 10px;font-size:12px;border-bottom:1px solid var(--border)}
.tech-table .lbl{color:var(--muted);font-weight:500;width:38%}
.tech-table .val{font-family:var(--mono);color:var(--ink);font-weight:600}
.val-up{color:var(--green)}.val-dn{color:var(--red)}
.na-val{color:#bbb}
.news-list{display:flex;flex-direction:column;gap:6px}
.news-item{background:var(--bg);border-radius:3px;padding:8px 12px;border-left:2px solid var(--gold)}
.news-title{font-size:12px;color:var(--ink);font-weight:500;display:block;line-height:1.4}
.news-meta{font-size:10px;color:var(--muted);margin-top:2px;display:block}
.advice-box{background:var(--bg);border-radius:4px;padding:12px 15px;font-size:13px;color:var(--ink);line-height:1.7;border-left:3px solid var(--gold)}
.advice-box.strong-buy{border-left-color:var(--green);background:rgba(46,125,94,0.05)}
.advice-box.sell{border-left-color:var(--red);background:rgba(214,69,69,0.05)}
.section-title{font-family:'Noto Serif SC',serif;font-size:13px;font-weight:700;color:var(--ink);margin:14px 0 8px;padding-bottom:5px;border-bottom:1px solid var(--border)}
.section-title:first-child{margin-top:0}
@media(max-width:600px){
  body{padding:0 14px}
  .pub-header{padding:28px 0 18px;margin-bottom:28px}
  .hero{padding:20px 16px}
  .bench{flex-direction:column;gap:12px}
  .tbl{font-size:12px}
  .tbl .hide-sm{display:none}
  .m-overlay.open{padding:0;align-items:flex-end}
  .m-content{max-width:100%;border-radius:6px 6px 0 0}
}"""

# ─── assemble HTML ─────────────────────────────────────────────────────────────

html_parts = []
html_parts.append('<!DOCTYPE html>\n')
html_parts.append('<html lang="zh-CN">\n')
html_parts.append('<head>\n')
html_parts.append('<meta charset="UTF-8">\n')
html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
html_parts.append(f'<title>美股市场扫描 · {TODAY}</title>\n')
html_parts.append('<style>\n')
html_parts.append(CSS)
html_parts.append('\n</style>\n')
html_parts.append('</head>\n')
html_parts.append('<body>\n')
html_parts.append('<header class="pub-header">\n')
html_parts.append('<div class="pub-brand"><span>·</span> 美股市场扫描</div>\n')
html_parts.append('<div>\n')
html_parts.append(f'<div class="pub-meta">{TODAY} · {len(CODES)} 只标的</div>\n')
html_parts.append('<div class="pub-disclaimer">数据仅供参考，不构成投资建议</div>\n')
html_parts.append('</div>\n')
html_parts.append('</header>\n')
html_parts.append('<section class="hero">\n')
html_parts.append('<div class="hero-label">今日结论</div>\n')
html_parts.append(f'<h1 class="hero-title">{esc(hero_title)}</h1>\n')
html_parts.append(f'<p class="hero-sub">{esc(hero_sub)}</p>\n')
html_parts.append('<div class="hero-picks">\n')
html_parts.append(hero_picks_html)
html_parts.append('</div>\n')
html_parts.append('</section>\n')
html_parts.append('<section class="bench">\n')
html_parts.append('<div>\n')
html_parts.append('<div class="bench-name">纳指100 ETF (QQQ)</div>\n')
html_parts.append('<div class="bench-desc">Invesco QQQ Trust · 大盘基准</div>\n')
html_parts.append('</div>\n')
html_parts.append('<div class="bench-stats">\n')
html_parts.append(f'<div class="bench-stat"><div class="bench-stat-label">现价</div><div class="bench-stat-val">{bench_price}</div></div>\n')
html_parts.append(f'<div class="bench-stat"><div class="bench-stat-label">今日</div><div class="bench-stat-val">{bench_chg_d}</div></div>\n')
html_parts.append(f'<div class="bench-stat"><div class="bench-stat-label">60日涨跌</div><div class="bench-stat-val">{bench_chg_60}</div></div>\n')
html_parts.append(f'<div class="bench-stat"><div class="bench-stat-label">52W高</div><div class="bench-stat-val">${qqq_high}</div></div>\n')
html_parts.append(f'<div class="bench-stat"><div class="bench-stat-label">52W低</div><div class="bench-stat-val">${qqq_low}</div></div>\n')
html_parts.append('</div>\n')
html_parts.append('</section>\n')
html_parts.append('<div class="section-hdr">全部标的 <span>按综合评分降序</span></div>\n')
html_parts.append('<table class="tbl">\n')
html_parts.append('<thead>\n')
html_parts.append('<tr>\n')
html_parts.append('<th class="rank">#</th>\n')
html_parts.append('<th>标的</th>\n')
html_parts.append('<th>评分</th>\n')
html_parts.append('<th class="hide-sm">现价</th>\n')
html_parts.append('<th>60日涨跌</th>\n')
html_parts.append('<th class="hide-sm">52W位</th>\n')
html_parts.append('<th class="action">建议</th>\n')
html_parts.append('</tr>\n')
html_parts.append('</thead>\n')
html_parts.append('<tbody>\n')
html_parts.append(table_rows_html)
html_parts.append('</tbody>\n')
html_parts.append('</table>\n')
html_parts.append(sector_hotspots_html)
html_parts.append('<footer class="footer">\n')
html_parts.append(f'<p>美股市场扫描 · {TODAY} · 共 {len(CODES)} 只标的</p>\n')
html_parts.append('<p class="disc">本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。</p>\n')
html_parts.append('</footer>\n')
html_parts.append(modals_html)
html_parts.append('<script>\n')
html_parts.append("""function showDetail(code){
  var m=document.getElementById('modal-'+code);
  if(m){m.classList.add('open');document.body.style.overflow='hidden'}
}
function hideModal(code){
  var m=document.getElementById('modal-'+code);
  if(m){m.classList.remove('open');document.body.style.overflow=''}
}
function closeModal(e,code){
  if(e.target===e.currentTarget)hideModal(code);
}
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){
    document.querySelectorAll('.m-overlay.open').forEach(function(m){m.classList.remove('open')});
    document.body.style.overflow='';
  }
});
var touchStartY=0;
document.querySelectorAll('.m-overlay').forEach(function(o){
  o.addEventListener('touchstart',function(e){touchStartY=e.changedTouches[0].screenY},{passive:true});
  o.addEventListener('touchend',function(e){
    if(e.changedTouches[0].screenY-touchStartY>80){o.classList.remove('open');document.body.style.overflow=''}
  },{passive:true});
});
</script>
</body>
</html>""")
html = "".join(html_parts)

# ─── write output ─────────────────────────────────────────────────────────────

out_path = f"{BASE}/stock_report.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Generated {out_path} ({len(html):,} bytes)")
print()
for s in STOCKS:
    lbl = score_label(s["total_score"])
    print(f"  #{s['rank']:d} {s['code']:4s} price=${fmt(s['price']):>8}  60d={chg_arrow(s['chg_60d'])}{fmt_num(s['chg_60d']):>7}%  score={s['total_score']:3d}  {lbl}")
    print(f"        技术{s['tech_score']}/30 基本面{s['fund_score']}/40 板块{s['sector_score']}/20 评级{s['rating_score']}/10 新闻{s['news_score']}/10")
