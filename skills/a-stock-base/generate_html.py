#!/usr/bin/env python3
"""
A 股大盘分析 HTML 报告生成器 — WeChat Article 风格
"""

import json, math, os, sys
from datetime import datetime, timedelta

OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/market-scan"
TODAY = datetime.now().strftime("%Y-%m-%d")

# ─── helpers ───────────────────────────────────────────────────────────────────

def chg_class(v):
    if v is None: return "chg-neutral"
    return "chg-up" if v >= 0 else "chg-dn"

def chg_arrow(v):
    if v is None: return "—"
    return "▲" if v >= 0 else "▼"

def fmt(v, spec=".2f"):
    if v is None: return "—"
    try: return f"{v:{spec}}"
    except: return str(v)

def fmt_num(v, spec=".2f"):
    if v is None: return "—"
    try: return f"{abs(v):{spec}}"
    except: return str(v)

def esc(s):
    if s is None: return ""
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def safe_float(val, default=0.0):
    if val is None: return default
    try: return float(val)
    except: return default

# ─── data fetching ────────────────────────────────────────────────────────────

def fetch_indices():
    """从腾讯行情 API 获取主要指数快照"""
    import subprocess
    result = subprocess.run(
        ['curl', '-s', '--max-time', '10',
         'https://qt.gtimg.cn/q=s_sh000001,s_sz399001,s_sz399006,s_sh000300,s_sh000016,s_sh000905'],
        capture_output=True
    )
    raw = result.stdout.decode('gbk', errors='replace')
    indices = {}
    for part in raw.split(';'):
        if '=' not in part: continue
        key_val = part.split('=', 1)[1].strip('"')
        fields = key_val.split('~')
        if len(fields) < 10: continue
        name = fields[1]
        price = safe_float(fields[3])
        chg_pct = safe_float(fields[5])  # 涨跌幅%
        indices[name] = {'price': price, 'chg_pct': chg_pct}
    return indices

def fetch_kline(code='sh000001', count=20):
    """从 QQ 财经获取日 K 线数据"""
    import subprocess
    result = subprocess.run(
        ['curl', '-s', '--max-time', '10',
         f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={code},day,,,{count},qfq'],
        capture_output=True
    )
    raw = result.stdout.decode('gbk', errors='replace')
    # 去掉变量赋值前缀
    json_str = raw.split('=', 1)[-1] if '=' in raw else raw
    try:
        d = json.loads(json_str)
        return d['data'][code]['day']
    except:
        return []

def fetch_sector_data():
    """获取新浪板块数据（概念+行业）"""
    import subprocess
    results = {'concept': [], 'industry': []}
    for ptype in ['class', 'industry']:
        result = subprocess.run(
            ['curl', '-s', '--max-time', '15',
             '-H', 'User-Agent: Mozilla/5.0',
             '-H', 'Referer: https://finance.sina.com.cn/',
             f'https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param={ptype}'],
            capture_output=True
        )
        raw = result.stdout.decode('gbk', errors='replace')
        # 解析 var S_Finance_bankuai_xxx = {...}
        if '=' not in raw: continue
        json_str = raw.split('=', 1)[-1].rstrip(';')
        try:
            d = json.loads(json_str)
            for key, val in d.items():
                fields = val.split(',')
                if len(fields) < 6: continue
                name = fields[1]
                chg_pct = safe_float(fields[5])  # 涨跌幅%
                chg_abs = safe_float(fields[4])  # 涨跌额
                stock = fields[12] if len(fields) > 12 else (fields[8] if len(fields) > 8 else '')  # 代表股名称
                item = {'name': name, 'chg_pct': chg_pct, 'chg_abs': chg_abs, 'stock': stock}
                if ptype == 'class':
                    results['concept'].append(item)
                else:
                    results['industry'].append(item)
        except: pass
    return results

def fetch_news():
    """获取最近7天重要新闻"""
    import subprocess
    all_news = []
    cutoff = (datetime.now() - timedelta(days=7)).timestamp()

    # 新浪快讯
    result = subprocess.run(
        ['curl', '-s', '--max-time', '10',
         '-H', 'User-Agent: Mozilla/5.0',
         '-H', 'Referer: https://finance.sina.com.cn/',
         'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=30&page=1'],
        capture_output=True
    )
    try:
        d = json.loads(result.stdout.decode('utf-8', errors='replace'))
        items = d.get('result', {}).get('data', [])
        for it in items[:30]:
            ctime = it.get('ctime', '')
            try:
                if ctime.isdigit():
                    ts = int(ctime)
                    if ts < cutoff: continue
                    date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                else:
                    ts = datetime.strptime(ctime, '%Y-%m-%d %H:%M:%S').timestamp()
                    if ts < cutoff: continue
                    date_str = ctime[:10]
            except: continue
            all_news.append({
                'title': it.get('title', ''),
                'date': date_str,
                'source': '新浪',
                'link': it.get('url', ''),
            })
    except: pass

    # 东方财富宏观
    result2 = subprocess.run(
        ['curl', '-s', '--max-time', '10',
         '-H', 'User-Agent: Mozilla/5.0',
         'https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html'],
        capture_output=True
    )
    try:
        d2 = json.loads(result2.stdout.decode('utf-8', errors='replace'))
        items2 = d2.get('list', [])
        for it in items2[:30]:
            st = it.get('showtime', '')[:10]
            all_news.append({
                'title': it.get('title', ''),
                'date': st,
                'source': '东方财富',
                'link': it.get('url', ''),
            })
    except: pass

    # 去重+按日期分组
    seen = set()
    unique = []
    for n in all_news:
        key = n['title'][:30]
        if key not in seen:
            seen.add(key)
            unique.append(n)

    # 按日期分组
    by_date = {}
    for n in unique:
        d = n['date'][:10] if n['date'] else '??'
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(n)

    return by_date

# ─── technical indicators ─────────────────────────────────────────────────────

def calc_ma(klines, period):
    vals = [float(k[2]) for k in klines[-period:] if k and len(k) > 2 and k[2]]
    return sum(vals)/len(vals) if len(vals) == period else None

def calc_boll(klines, period=20):
    vals = [float(k[2]) for k in klines[-period:] if k and len(k) > 2 and k[2]]
    if len(vals) < period: return None, None, None
    mid = sum(vals)/period
    std = math.sqrt(sum((v-mid)**2 for v in vals)/period)
    return mid+2*std, mid, mid-2*std

def calc_gaps(klines):
    gaps = []
    for i in range(1, min(len(klines), 11)):
        prev = safe_float(klines[-i-1][2]) if klines[-i-1] and len(klines[-i-1]) > 2 else None
        cur = safe_float(klines[-i][1]) if klines[-i] and len(klines[-i]) > 1 else None
        if prev and cur and prev != 0:
            gaps.append(round((cur-prev)/prev*100, 1))
    return list(reversed(gaps))

def calc_kdj(klines, period=9):
    vals = klines[-period:]
    lows  = [float(k[4]) for k in vals if k and len(k) > 4 and k[4]]
    highs = [float(k[3]) for k in vals if k and len(k) > 3 and k[3]]
    close = safe_float(klines[-1][2]) if klines[-1] and len(klines[-1]) > 2 else None
    if not lows or not highs or close is None: return None, None, None
    rsv = 100*(close-min(lows))/(max(highs)-min(lows)+1e-9)
    k = d = 50.0
    for _ in range(period-1):
        k = k*2/3 + rsv/3
        d = d*2/3 + k/3
    return k, d, 3*k-2*d

def calc_macd(klines, fast=12, slow=26, signal=9):
    def ema(period):
        vals = [float(k[2]) for k in klines if k and len(k) > 2 and k[2]]
        if len(vals) < period: return None
        m = 2/(period+1)
        e = sum(vals[:period])/period
        for p in vals[period:]: e = (p-e)*m + e
        return e
    ef = ema(fast); es = ema(slow)
    if ef is None or es is None: return None, None, None
    dif = ef - es
    return dif, None, None

def ma_order(klines):
    ma5  = calc_ma(klines, 5)
    ma10 = calc_ma(klines, 10)
    ma20 = calc_ma(klines, 20)
    ma60 = calc_ma(klines, 60) if len(klines) >= 60 else None
    price = safe_float(klines[-1][2]) if klines[-1] and len(klines[-1]) > 2 else None
    above = ma60 is not None and price is not None and price > ma60
    aligned = all(x is not None for x in [ma5, ma10, ma20, ma60]) and ma5 > ma10 > ma20 > ma60
    return above, aligned, (ma5, ma10, ma20, ma60)

# ─── data processing ──────────────────────────────────────────────────────────

def process_data():
    print("Fetching indices...")
    indices = fetch_indices()

    print("Fetching K-line...")
    klines = fetch_kline('sh000001', 60)
    closes = [float(k[2]) for k in klines if k and len(k) > 2 and k[2]]

    print("Fetching sector data...")
    sectors = fetch_sector_data()

    print("Fetching news...")
    news_by_date = fetch_news()

    # Technical indicators
    ma5, ma10, ma20, ma60 = None, None, None, None
    if len(klines) >= 5:
        ma5 = calc_ma(klines, 5)
    if len(klines) >= 10:
        ma10 = calc_ma(klines, 10)
    if len(klines) >= 20:
        ma20 = calc_ma(klines, 20)
    if len(klines) >= 60:
        ma60 = calc_ma(klines, 60)

    boll_up, boll_mid, boll_low = calc_boll(klines, 20)
    dif, dea, bar = calc_macd(klines)
    k, d, j = calc_kdj(klines)
    gaps = calc_gaps(klines)

    # Sector sorting
    concept_sorted = sorted(sectors.get('concept', []), key=lambda x: x['chg_pct'], reverse=True)
    industry_sorted = sorted(sectors.get('industry', []), key=lambda x: x['chg_pct'], reverse=True)

    # Last close
    last_close = safe_float(klines[-1][2]) if klines and len(klines[-1]) > 2 else None
    prev_close = safe_float(klines[-2][2]) if len(klines) > 1 and len(klines[-2]) > 2 else last_close
    chg_d = (last_close - prev_close) / prev_close * 100 if prev_close else None

    # Volume
    vols = [float(k[5]) for k in klines[-5:] if k and len(k) > 5 and k[5]]
    avg_vol = sum(vols) / len(vols) if vols else 0
    last_vol = float(klines[-1][5]) if klines[-1] and len(klines[-1]) > 5 else 0

    return {
        'indices': indices,
        'klines': klines[-5:],
        'all_klines': klines,
        'closes': closes,
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
        'boll_up': boll_up, 'boll_mid': boll_mid, 'boll_low': boll_low,
        'dif': dif, 'dea': dea, 'macd_bar': bar,
        'k': k, 'd': d, 'j': j,
        'gaps': gaps,
        'last_close': last_close,
        'chg_d': chg_d,
        'avg_vol': avg_vol,
        'last_vol': last_vol,
        'concept_hot': concept_sorted[:8],
        'concept_cold': concept_sorted[-5:],
        'industry_hot': industry_sorted[:5],
        'industry_cold': industry_sorted[-5:],
        'news_by_date': news_by_date,
    }

# ─── HTML generation ─────────────────────────────────────────────────────────

def build_index_cards(indices):
    """大盘指数卡片"""
    cards = []
    for name, d in indices.items():
        cc = "chg-up" if d['chg_pct'] >= 0 else "chg-dn"
        arrow = "▲" if d['chg_pct'] >= 0 else "▼"
        cards.append(f"""<div class="idx-card">
    <div class="idx-name">{name}</div>
    <div class="idx-price">{fmt(d['price'], '.2f')}</div>
    <div class="idx-chg {cc}">{arrow} {fmt_num(d['chg_pct'], '.2f')}%</div>
  </div>""")
    return "\n".join(cards)

def build_kline_table(klines):
    rows = []
    all_klines = klines  # already last 5
    for i, k in enumerate(all_klines):
        date = k[0]
        open_p = k[1]
        close = k[2]
        high = k[3]
        low = k[4]
        vol = k[5]
        prev_close = float(all_klines[i-1][2]) if i > 0 else float(close)
        chg = (float(close) - prev_close) / prev_close * 100
        arrow = "▲" if chg >= 0 else "▼"
        cc = "chg-up" if chg >= 0 else "chg-dn"
        rows.append(f"""<tr>
  <td>{date[5:]}</td>
  <td>{open_p}</td>
  <td>{close}</td>
  <td>{high}</td>
  <td>{low}</td>
  <td>{float(vol)/1e8:.2f}亿</td>
  <td class="{cc}">{arrow} {fmt_num(chg)}%</td>
</tr>""")
    return "\n".join(rows)

def build_sector_table(items, hot=True):
    rows = []
    for item in items:
        cc = "chg-up" if item['chg_pct'] >= 0 else "chg-dn"
        arrow = "▲" if item['chg_pct'] >= 0 else "▼"
        rows.append(f"""<tr>
  <td class="sector-name">{item['name']}</td>
  <td class="{cc}">{arrow} {fmt_num(item['chg_pct'])}%</td>
  <td>{item['stock']}</td>
</tr>""")
    return "\n".join(rows)

def build_news_section(news_by_date):
    sections = []
    for date in sorted(news_by_date.keys(), reverse=True):
        items = news_by_date[date]
        items_html = []
        for n in items[:5]:
            link = n.get('link', '')
            title = esc(n['title'])
            source = esc(n.get('source', ''))
            if link:
                items_html.append(f"""<div class="news-item"><a href="{link}" target="_blank" class="news-link"><span class="news-title">{title}</span><span class="news-meta">{date} · {source}</span></a></div>""")
            else:
                items_html.append(f"""<div class="news-item"><span class="news-title">{title}</span><span class="news-meta">{date} · {source}</span></div>""")
        sections.append(f"""<div class="news-date-group">
  <div class="news-date-label">{date}</div>
  <div class="news-list">{"".join(items_html)}</div>
</div>""")
    return "\n".join(sections[:7])  # max 7 days

def generate_html(data):
    indices = data['indices']
    klines_5 = data['klines']
    ma5 = data['ma5']; ma10 = data['ma10']; ma20 = data['ma20']; ma60 = data['ma60']
    boll_up = data['boll_up']; boll_mid = data['boll_mid']; boll_low = data['boll_low']
    dif = data['dif']; dea = data['dea']; macd_bar = data['macd_bar']
    k, d, j = data['k'], data['d'], data['j']
    gaps = data['gaps']
    last_close = data['last_close']
    chg_d = data['chg_d']

    # KDJ note
    kdj_note = ""
    if k and d and j:
        if j > 90: kdj_note = "严重超买"
        elif j < 20: kdj_note = "严重超卖"
        elif j > 80: kdj_note = "超买"
        elif j < 30: kdj_note = "超卖"

    # MA rows
    ma_vals = [('MA5', ma5), ('MA10', ma10), ('MA20', ma20), ('MA60', ma60)]
    ma_rows = []
    for label, val in ma_vals:
        if val:
            ma_rows.append(f"<tr><td class='lbl'>{label}</td><td class='val'>{val:.2f}</td></tr>")
    ma_html = "\n".join(ma_rows) if ma_rows else "<tr><td class='lbl'>均线</td><td class='val na-val'>— (历史数据不足)</td></tr>"

    # MACD
    if dif is not None:
        macd_cls = "val-up" if dif > 0 else "val-dn"
        macd_note = "零轴上方" if dif > 0 else "零轴下方"
        macd_bar_str = fmt(macd_bar, '.3f') if macd_bar is not None else "—"
        macd_bar_cls = "val-up" if macd_bar and macd_bar > 0 else "val-dn"
        macd_note_str = "金叉" if dif > 0 else "死叉"
        macd_html = f"""
    <div class="tech-row"><span class="tech-label">DIF</span><span class="tech-val {macd_cls}">{dif:.3f} <span style='color:var(--muted);font-size:10px'>{macd_note_str}</span></span></div>
    <div class="tech-row"><span class="tech-label">MACD柱</span><span class="tech-val {macd_bar_cls}">{macd_bar_str}</span></div>"""
    else:
        macd_html = "<tr><td class='lbl'>MACD</td><td class='val na-val'>— (历史数据不足)</td></tr>"

    # Bollinger
    if boll_up is not None:
        boll_html = f"""<tr><td class='lbl'>布林上轨</td><td class='val'>{boll_up:.2f}</td></tr>
<tr><td class='lbl'>布林中轨</td><td class='val'>{boll_mid:.2f}</td></tr>
<tr><td class='lbl'>布林下轨</td><td class='val'>{boll_low:.2f}</td></tr>"""
    else:
        boll_html = "<tr><td class='lbl'>布林带</td><td class='val na-val'>— (历史数据不足)</td></tr>"

    # Gap
    gaps_str = ", ".join(f"{'+' if g > 0 else ''}{g:.1f}%" for g in gaps) if gaps else "无明显缺口"

    # Volume
    vol_ratio = data['last_vol'] / data['avg_vol'] if data['avg_vol'] else 1.0
    vol_status = "放量" if vol_ratio > 1.2 else "缩量" if vol_ratio < 0.8 else "正常"

    # Trend assessment
    above_ma5 = last_close > ma5 if (last_close and ma5) else None
    above_ma20 = last_close > ma20 if (last_close and ma20) else None
    trend = "多头排列" if (ma5 and ma20 and ma5 > ma10 > ma20) else ("空头排列" if (ma5 and ma20 and ma5 < ma10 < ma20) else "震荡整理")

    # Conclusion
    if above_ma20 and boll_low and last_close > boll_low:
        outlook_short = f"短线偏多，现价{last_close:.0f}在20日线{ma20:.0f}上方，关注布林上轨{boll_up:.0f}压力"
    elif not above_ma20 and boll_mid and last_close < boll_mid:
        outlook_short = f"短线偏弱，跌破20日线{ma20:.0f}，关注布林下轨{boll_low:.0f}支撑"
    else:
        outlook_short = f"短线震荡，{last_close:.0f}附近整理，均线{trend}"

    outlook_mid = f"中线震荡偏多，20日线({ma20:.0f})上行，布林下轨({boll_low:.0f})支撑未破趋势未变" if above_ma20 else f"中线偏弱，等待企稳信号"

    # ── CSS ──────────────────────────────────────────────────────────────────
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
.hero-sub{font-size:13px;color:var(--muted);margin-bottom:20px}
.idx-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.idx-card{background:var(--bg);border-radius:3px;padding:10px 12px;text-align:center}
.idx-name{font-size:10px;color:var(--muted);margin-bottom:4px}
.idx-price{font-family:var(--mono);font-size:16px;font-weight:700;color:var(--ink)}
.idx-chg{font-family:var(--mono);font-size:12px;margin-top:2px}
.section-hdr{font-family:'Noto Serif SC',serif;font-size:16px;font-weight:700;color:var(--ink);padding-bottom:10px;border-bottom:2px solid var(--ink);margin:28px 0 16px;display:flex;align-items:baseline;justify-content:space-between}
.section-hdr span{font-family:'Noto Sans SC',sans-serif;font-size:12px;font-weight:400;color:var(--muted)}
.kline-table{width:100%;border-collapse:collapse;margin-bottom:24px;font-size:13px}
.kline-table th{font-size:10px;text-transform:uppercase;letter-spacing:0.5px;color:var(--muted);font-weight:500;padding:8px 10px;text-align:left;border-bottom:1px solid var(--border)}
.kline-table td{padding:9px 10px;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:12px}
.kline-table tr:last-child td{border-bottom:none}
.chg-up{color:var(--green)}.chg-dn{color:var(--red)}.chg-neutral{color:var(--muted)}
.tech-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
.tech-card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:16px}
.tech-card-title{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--gold);font-weight:600;margin-bottom:10px}
.tech-row{display:flex;justify-content:space-between;padding:4px 0;font-size:13px;border-bottom:1px solid var(--border)}
.tech-row:last-child{border-bottom:none}
.tech-label{color:var(--muted)}
.tech-val{font-family:var(--mono);font-weight:600}
.sector-table{width:100%;border-collapse:collapse;margin-bottom:32px;font-size:13px}
.sector-table th{font-size:10px;text-transform:uppercase;letter-spacing:0.5px;color:var(--muted);font-weight:500;padding:8px 10px;text-align:left;border-bottom:1px solid var(--border)}
.sector-table td{padding:8px 10px;border-bottom:1px solid var(--border);font-size:12px}
.sector-table tr:last-child td{border-bottom:none}
.sector-name{font-weight:600}
.news-date-group{margin-bottom:20px}
.news-date-label{font-size:12px;font-weight:600;color:var(--ink);margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)}
.news-list{display:flex;flex-direction:column;gap:6px}
.news-item{background:var(--card);border:1px solid var(--border);border-radius:3px;padding:8px 12px;border-left:3px solid var(--gold)}
.news-link{text-decoration:none;display:block}
.news-link:hover{background:rgba(201,168,76,0.05)}
.news-title{font-size:12px;color:var(--ink);font-weight:500;display:block;line-height:1.4}
.news-meta{font-size:10px;color:var(--muted);margin-top:2px;display:block}
.conclusion-box{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:20px 24px;margin-top:24px}
.conclusion-title{font-family:'Noto Serif SC',serif;font-size:14px;font-weight:700;color:var(--ink);margin-bottom:12px}
.conclusion-row{display:flex;gap:16px;margin-bottom:10px;font-size:13px}
.conclusion-label{min-width:48px;font-weight:600;color:var(--ink)}
.conclusion-val{color:#555}
.advice-box{background:var(--bg);border-radius:4px;padding:12px 15px;font-size:13px;color:var(--ink);line-height:1.7;border-left:3px solid var(--gold);margin-top:16px}
.footer{text-align:center;padding:32px 0;border-top:1px solid var(--border);margin-top:48px}
.footer p{font-size:11px;color:var(--muted)}
.footer .disc{margin-top:4px;font-size:10px}
.val-up{color:var(--green)}.val-dn{color:var(--red)}.na-val{color:#bbb}
@media(max-width:600px){
  body{padding:0 14px}
  .pub-header{padding:28px 0 18px;margin-bottom:28px}
  .hero{padding:20px 16px}
  .idx-grid{grid-template-columns:1fr 1fr}
  .tech-grid{grid-template-columns:1fr}
}"""

    # ── build HTML ───────────────────────────────────────────────────────────
    kline_rows = build_kline_table(klines_5)
    idx_cards = build_index_cards(indices)
    sector_hot = build_sector_table(data['concept_hot'][:5])
    sector_cold = build_sector_table(data['concept_cold'][:5])
    news_html = build_news_section(data['news_by_date'])

    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A 股大盘分析 · {today_str}</title>
<style>
{CSS}
</style>
</head>
<body>

<header class="pub-header">
  <div class="pub-brand"><span>·</span> A 股大盘分析</div>
  <div>
    <div class="pub-meta">{today_str}</div>
    <div class="pub-disclaimer">数据仅供参考，不构成投资建议</div>
  </div>
</header>

<section class="hero">
  <div class="hero-label">大盘快照</div>
  <div class="idx-grid">
{idx_cards}
  </div>
</section>

<div class="section-hdr">K线回顾 <span>近5日上证指数</span></div>
<table class="kline-table">
  <thead><tr><th>日期</th><th>开盘</th><th>收盘</th><th>最高</th><th>最低</th><th>成交量</th><th>涨跌</th></tr></thead>
  <tbody>
{kline_rows}
  </tbody>
</table>

<div class="section-hdr">技术面指标</div>
<div class="tech-grid">
  <div class="tech-card">
    <div class="tech-card-title">均线系统</div>
    <div class="tech-row"><span class="tech-label">5日线</span><span class="tech-val">{fmt(ma5)}</span></div>
    <div class="tech-row"><span class="tech-label">10日线</span><span class="tech-val">{fmt(ma10)}</span></div>
    <div class="tech-row"><span class="tech-label">20日线</span><span class="tech-val">{fmt(ma20)}</span></div>
    <div class="tech-row"><span class="tech-label">60日线</span><span class="tech-val">{fmt(ma60)}</span></div>
  </div>
  <div class="tech-card">
    <div class="tech-card-title">布林轨道</div>
    <div class="tech-row"><span class="tech-label">上轨</span><span class="tech-val">{fmt(boll_up)}</span></div>
    <div class="tech-row"><span class="tech-label">中轨</span><span class="tech-val">{fmt(boll_mid)}</span></div>
    <div class="tech-row"><span class="tech-label">下轨</span><span class="tech-val">{fmt(boll_low)}</span></div>
    <div class="tech-row"><span class="tech-label">量能</span><span class="tech-val">{vol_ratio:.2f}x ({vol_status})</span></div>
  </div>
  <div class="tech-card">
    <div class="tech-card-title">MACD</div>
    {macd_html}
  </div>
  <div class="tech-card">
    <div class="tech-card-title">KDJ</div>
    <div class="tech-row"><span class="tech-label">K</span><span class="tech-val">{fmt(k,'.1f')}</span></div>
    <div class="tech-row"><span class="tech-label">D</span><span class="tech-val">{fmt(d,'.1f')}</span></div>
    <div class="tech-row"><span class="tech-label">J</span><span class="tech-val">{fmt(j,'.1f')}{' '+kdj_note if kdj_note else ''}</span></div>
    <div class="tech-row"><span class="tech-label">缺口</span><span class="tech-val">{gaps_str}</span></div>
  </div>
</div>

<div class="section-hdr">板块资金流向 <span>T-1日 · 概念板块</span></div>
<div class="section-hdr" style="font-size:13px;margin-top:0">最热板块</div>
<table class="sector-table">
  <thead><tr><th>板块名称</th><th>涨跌幅</th><th>代表股</th></tr></thead>
  <tbody>
{sector_hot}
  </tbody>
</table>

<div class="section-hdr" style="font-size:13px;margin-top:0">最冷板块</div>
<table class="sector-table">
  <thead><tr><th>板块名称</th><th>涨跌幅</th><th>代表股</th></tr></thead>
  <tbody>
{sector_cold}
  </tbody>
</table>

<div class="section-hdr">近一周重要时政</div>
{news_html}

<div class="conclusion-box">
  <div class="conclusion-title">综合结论</div>
  <div class="conclusion-row">
    <span class="conclusion-label">短线</span>
    <span class="conclusion-val">{outlook_short}</span>
  </div>
  <div class="conclusion-row">
    <span class="conclusion-label">中线</span>
    <span class="conclusion-val">{outlook_mid}</span>
  </div>
  <div class="advice-box">
    <strong>操作建议：</strong>仓位5-6成，关注锂矿/新能源超跌反弹；回避军工（地缘消息反复）、光伏（产能过剩）。当前处于{trend}，突破4106方可进一步看多。
  </div>
</div>

<footer class="footer">
  <p>A 股大盘分析 · {today_str}</p>
  <p class="disc">本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。</p>
</footer>

</body>
</html>"""

    return html

# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    print("开始获取 A 股数据...")
    data = process_data()
    html = generate_html(data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today_prefix = f"a_stock_{TODAY}_"
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(today_prefix)]
    next_num = len(existing) + 1
    report_filename = f"{today_prefix}{next_num:03d}.html"
    out_path = os.path.join(OUTPUT_DIR, report_filename)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated {out_path} ({len(html):,} bytes)")
    print(f"\n=== 关键数据 ===")
    for name, d in data['indices'].items():
        print(f"  {name}: {d['price']} {d['chg_pct']:+.2f}%")

if __name__ == "__main__":
    main()
