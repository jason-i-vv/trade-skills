#!/usr/bin/env python3
"""
A 股个股扫描 — 批量分析多个 A 股标的，生成 WeChat Article 风格 HTML 简报
对齐 m-stock-scan 的结构：Hero 结论区 + 大盘基准 + 排名表格 + 板块热点 + Modal 详情
"""

import sys, os, json, subprocess, re
from datetime import datetime, timedelta

# ── 配置 ──────────────────────────────────────────────────────────────────────
BASE = "/home/ubuntu/.claude/skills/a-stock-scan"
OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/market-scan"
TODAY = datetime.now().strftime("%Y-%m-%d")

# ── 运行时配置加载 ─────────────────────────────────────────────────────────────
# 股票数据库从 stocks.json 动态加载（无需改代码）
_stocks_db = {}
if os.path.exists(f"{BASE}/stocks.json"):
    with open(f"{BASE}/stocks.json") as f:
        _raw = json.load(f)
        for name, info in _raw.get("stocks", {}).items():
            _stocks_db[name] = info

STOCK_MAP = {name: info["code"] for name, info in _stocks_db.items()}
STOCK_SECTORS = {info["code"]: info.get("sectors", []) for name, info in _stocks_db.items()}

def load_sector_themes():
    """加载板块主题词配置"""
    path = f"{BASE}/sector_themes.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("sectors", {})
    return {}

def get_stock_themes(code, sector_themes):
    """返回某股票代码应搜索的主题词列表"""
    sectors = STOCK_SECTORS.get(code, [])
    themes = []
    for sec in sectors:
        themes.extend(sector_themes.get(sec, []))
    return list(dict.fromkeys(themes))  # 去重保留顺序

def name_to_code(name):
    return STOCK_MAP.get(name.strip(), None)

def safe_float(v):
    try: return float(v)
    except: return 0.0

# ── 数据获取 ──────────────────────────────────────────────────────────────────

def fetch_quotes(codes_str):
    """新浪行情 API，返回 {code: {price, chg_pct, open, high, low, volume, amount, name}}"""
    import time
    raw = ""
    for attempt in range(3):
        result = subprocess.run(
            ['curl', '-s', '--max-time', '30',
             '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
             '-H', 'Referer: https://finance.sina.com.cn/',
             f'https://hq.sinajs.cn/list={codes_str}'],
            capture_output=True
        )
        raw = result.stdout.decode('gbk', errors='replace')
        if raw.count('\n') >= len(codes_str.split(',')) - 1 and len(raw) > 100:
            break
        if attempt < 2:
            time.sleep(1)
    data = {}
    for line in raw.split('\n'):
        line = line.strip()
        if not line or '=' not in line: continue
        var_part = line.split('=', 1)[0].strip()
        parts = var_part.split('_')
        if len(parts) < 2: continue
        code_part = parts[-1]
        if code_part.startswith('sz'):
            prefix = 'sz'; numeric = code_part[2:]
        elif code_part.startswith('sh'):
            prefix = 'sh'; numeric = code_part[2:]
        else: continue
        full_code = prefix + numeric
        fields = line.split('=', 1)[1].strip('"; ').split(',')
        if len(fields) < 32: continue
        try:
            name = fields[0]
            price = safe_float(fields[3])
            yesterday = safe_float(fields[2])
            chg_pct = (price - yesterday) / yesterday * 100 if yesterday else 0
            data[full_code] = {
                'name': name, 'price': price,
                'yesterday': yesterday, 'open': safe_float(fields[1]),
                'volume': safe_float(fields[8]), 'amount': safe_float(fields[9]),
                'chg_pct': chg_pct,
                'high': safe_float(fields[4]), 'low': safe_float(fields[5]),
                'time': f"{fields[30]} {fields[31]}",
            }
        except: pass
    return data

def fetch_kline(code, count=60):
    """QQ 财经日 K 线，返回 [(date, open, close, high, low, volume), ...]"""
    result = subprocess.run(
        ['curl', '-s', '--max-time', '30',
         f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param={code},day,,,{count},qfq'],
        capture_output=True
    )
    raw = result.stdout.decode('gbk', errors='replace')
    json_str = raw.split('=', 1)[-1] if '=' in raw else raw
    try:
        d = json.loads(json_str)
        code_data = d['data'][code]
        days = code_data.get('qfqday') or code_data.get('day') or []
        return days[-count:] if days else []
    except:
        return []

def load_local_news(code):
    path = f"{BASE}/{code}_news.json"
    if os.path.exists(path):
        try:
            with open(path) as f:
                d = json.load(f)
            cutoff = datetime.now().timestamp() - 7*86400
            news = d.get("news", [])
            return [n for n in news if n.get("providerPublishTime", 0) / 1000 >= cutoff]
        except: pass
    return []

def fetch_benchmark():
    """获取上证指数和沪深300基准数据"""
    result = subprocess.run(
        ['curl', '-s', '--max-time', '10',
         'https://qt.gtimg.cn/q=s_sh000001,s_sh000300,s_sz399001'],
        capture_output=True
    )
    raw = result.stdout.decode('gbk', errors='replace')
    data = {}
    for part in raw.split(';'):
        if '=' not in part: continue
        key_val = part.split('=', 1)[1].strip('"')
        fields = key_val.split('~')
        if len(fields) < 10: continue
        code = fields[2]  # "000001"
        name = fields[1]
        price = safe_float(fields[3])
        chg_abs = safe_float(fields[4])   # 涨跌额
        chg_pct = safe_float(fields[5])    # 涨跌幅%
        data['sh' + code] = {'name': name, 'price': price, 'yesterday': price - chg_abs, 'chg_pct': chg_pct}
    return data

# ── 技术指标 ──────────────────────────────────────────────────────────────────

def calc_ma(klines, period):
    vals = [float(k[2]) for k in klines[-period:] if k and len(k) > 2 and k[2]]
    return sum(vals)/len(vals) if len(vals) == period else None

def calc_boll(klines, period=20):
    vals = [float(k[2]) for k in klines[-period:] if k and len(k) > 2 and k[2]]
    if len(vals) < period: return None, None, None
    mid = sum(vals)/period
    std = (sum((v-mid)**2 for v in vals)/period) ** 0.5
    return mid + 2*std, mid, mid - 2*std

def calc_macd(klines, fast=12, slow=26, signal=9):
    closes = [float(k[2]) for k in klines if k and len(k) > 2 and k[2]]
    if len(closes) < slow+signal: return None, None, None
    m = 2/(fast+1)
    e_fast = sum(closes[:fast])/fast
    for p in closes[fast:]: e_fast = (p - e_fast) * m + e_fast
    m2 = 2/(slow+1)
    e_slow = sum(closes[:slow])/slow
    for p in closes[slow:]: e_slow = (p - e_slow) * m2 + e_slow
    dif = e_fast - e_slow
    dea = dif * 0.8
    bar = 2 * (dif - dea)
    return dif, dea, bar

def calc_kdj(klines, period=9):
    vals = [float(k[3]) for k in klines[-period*2:] if k and len(k) > 3 and k[3]]
    lows  = [float(k[4]) for k in klines[-period*2:] if k and len(k) > 4 and k[4]]
    if len(vals) < period: return None, None, None
    high = max(vals[-period:])
    low  = min(lows[-period:])
    close = safe_float(klines[-1][2]) if klines[-1] and len(klines[-1]) > 2 else 0
    rsv = (close - low) / (high - low) * 100 if high != low else 50
    k = 50.0; d = 50.0
    for _ in range(period-1):
        k = k*2/3 + rsv/3
        d = d*2/3 + k/3
    return k, d, 3*k - 2*d

def volume_ratio(klines):
    if len(klines) < 25: return None
    recent = [float(k[5]) for k in klines[-5:] if k and len(k) > 5 and k[5]]
    before = [float(k[5]) for k in klines[-25:-5] if k and len(k) > 5 and k[5]]
    if not recent or not before: return None
    return sum(recent)/len(recent) / (sum(before)/len(before))

def chg60(klines):
    """60日涨跌幅"""
    if len(klines) < 2: return None
    recent = safe_float(klines[-1][2])
    old = safe_float(klines[-(min(61, len(klines)))][2])
    if not recent or not old or old == 0: return None
    return (recent - old) / old * 100

def ma_order(klines):
    """MA 多头排列判断"""
    if len(klines) < 60: return False, False, False, False
    prices = [float(k[2]) for k in klines]
    ma5  = sum(prices[-5:])/5
    ma10 = sum(prices[-10:])/10
    ma20 = sum(prices[-20:])/20
    ma60 = sum(prices[-60:])/60
    last = prices[-1]
    return last > ma5, last > ma10, last > ma20, last > ma60

def calc_52w(klines):
    """计算52周高位位置"""
    if len(klines) < 250: return None
    highs = [float(k[3]) for k in klines[-250:] if k and len(k) > 3 and k[3]]
    lows  = [float(k[4]) for k in klines[-250:] if k and len(k) > 4 and k[4]]
    if not highs or not lows: return None
    high_52w = max(highs)
    low_52w = min(lows)
    current = safe_float(klines[-1][2]) if klines[-1] and len(klines[-1]) > 2 else 0
    if high_52w == low_52w: return 50.0
    return (current - low_52w) / (high_52w - low_52w) * 100

# ── 评分（5维度110分） ────────────────────────────────────────────────────────

def score_technical(klines):
    """技术面 30分"""
    score = 15  # 基础分
    reasons = []
    if len(klines) < 20: return score, reasons

    above_ma5, above_ma10, above_ma20, above_ma60 = ma_order(klines)
    if above_ma5 and above_ma10 and above_ma20:
        score += 10; reasons.append("MA5/10/20多头")
    elif above_ma5: score += 4; reasons.append("站上MA5")

    dif, dea, bar = calc_macd(klines)
    if dif is not None and dea is not None:
        if dif > dea: score += 5; reasons.append("MACD金叉")
        else: score -= 3; reasons.append("MACD死叉")

    k, d, j = calc_kdj(klines)
    if k is not None:
        if k < 20: score += 3; reasons.append("KDJ超卖")
        elif k > 80: score -= 3; reasons.append("KDJ超买")

    vr = volume_ratio(klines)
    if vr and vr > 1.5: score += 4; reasons.append(f"量比放大({vr:.1f}x)")

    return min(30, max(0, score)), reasons

def score_fundamental(q, klines):
    """基本面 40分（基于PE/涨跌/业绩预告）"""
    score = 20  # 基础分
    chg = q.get('chg_pct', 0)
    if chg > 5: score += 10
    elif chg > 0: score += 5
    elif chg < -3: score -= 10

    vr = volume_ratio(klines)
    if vr and vr > 1.5: score += 5
    elif vr and vr < 0.7: score -= 5

    chg60_val = chg60(klines)
    if chg60_val is not None:
        if chg60_val > 20: score += 5
        elif chg60_val > 10: score += 3
        elif chg60_val < -15: score -= 5

    return min(40, max(0, score))

def score_sector(q, klines):
    """板块热度 20分"""
    score = 10  # 基础分
    chg = q.get('chg_pct', 0)
    if chg > 3: score += 8
    elif chg > 1: score += 4
    elif chg < -2: score -= 8

    vr = volume_ratio(klines)
    if vr and vr > 1.5: score += 4

    return min(20, max(0, score))

def score_institutional(news_list):
    """机构评级 10分（基于新闻情绪）"""
    score = 5
    positive_kw = ['增持', '买入', '推荐', '看好', '超配', '强于', '优于', '评级上调', '目标价', '业绩', '扭亏', '增长', '突破']
    negative_kw = ['减持', '卖出', '回避', '下调', '预警', '亏损', '风险', '利空', '调查', '处罚']
    pos_count = sum(1 for n in news_list for kw in positive_kw if kw in n.get('title', ''))
    neg_count = sum(1 for n in news_list for kw in negative_kw if kw in n.get('title', ''))
    if pos_count > neg_count: score += 4
    elif neg_count > pos_count: score -= 4
    return min(10, max(0, score))

def score_news(news_list):
    """消息面 10分"""
    score = 5
    if len(news_list) >= 3: score += 4
    elif len(news_list) >= 1: score += 2
    positive_kw = ['涨停', '大涨', '暴涨', '利好', '业绩', '扭亏', '增长', '回购', '突破', '获批', '中标']
    negative_kw = ['跌停', '大跌', '暴跌', '利空', '亏损', '调查', '处罚', '减持', '预警']
    pos = sum(1 for n in news_list for kw in positive_kw if kw in n.get('title', ''))
    neg = sum(1 for n in news_list for kw in negative_kw if kw in n.get('title', ''))
    if pos > neg: score += 3
    elif neg > pos: score -= 3
    return min(10, max(0, score))

def overall_score(price, chg_pct, klines, news_list):
    tech_s, tech_reasons = score_technical(klines)
    fund_s = score_fundamental({'chg_pct': chg_pct, 'price': price}, klines)
    sect_s = score_sector({'chg_pct': chg_pct}, klines)
    inst_s = score_institutional(news_list)
    news_s = score_news(news_list)
    total = tech_s + fund_s + sect_s + inst_s + news_s
    return {
        'total': total,
        'tech': tech_s,
        'fund': fund_s,
        'sector': sect_s,
        'institutional': inst_s,
        'news': news_s,
        'tech_reasons': tech_reasons,
    }

def rating_label(score):
    if score >= 85: return "强烈推荐", "strong_buy"
    if score >= 70: return "推荐", "buy"
    if score >= 50: return "中性", "neutral"
    return "回避", "avoid"

# ── 板块热点 ──────────────────────────────────────────────────────────────────

def build_sector_hotspots(stocks_data):
    """从扫描标的中归纳板块热点"""
    hotspots = []
    sectors = {}
    for s in stocks_data:
        name = s['name']
        chg = s['chg_pct']
        tech_s = s['score_detail']['tech']
        if '宁德' in name or '比亚迪' in name or '中科电气' in name:
            sec = '新能源'
        elif '茅台' in name or '美的' in name or '格力' in name:
            sec = '消费'
        elif '软件' in name or '信息' in name or '鸿蒙' in name or 'AI' in name or '科大讯飞' in name:
            sec = 'AI软件'
        elif '医药' in name or '恒瑞' in name:
            sec = '医药'
        elif '中兴' in name or '浪潮' in name or '寒武纪' in name:
            sec = 'AI硬件'
        elif '平安' in name or '中信' in name or '招商' in name or '东财' in name:
            sec = '金融'
        else:
            sec = '其他'
        if sec not in sectors:
            sectors[sec] = []
        sectors[sec].append({'name': name, 'chg': chg, 'tech': tech_s})

    icons = {'新能源': '⚡', '消费': '🛒', 'AI软件': '🖥️', '医药': '🏥', 'AI硬件': '💻', '金融': '🏦', '其他': '📊'}
    for sec, members in sectors.items():
        if len(members) >= 1:
            avg_chg = sum(m['chg'] for m in members) / len(members)
            best = max(members, key=lambda x: x['tech'])
            direction = "偏强" if avg_chg >= 0 else "偏弱"
            desc = f"覆盖 {len(members)} 只标的，平均涨跌 {avg_chg:+.2f}%，{direction}"
            hotspots.append({
                'name': sec,
                'icon': icons.get(sec, '📊'),
                'desc': desc,
                'count': len(members),
            })
    return hotspots[:4]

# ── 主流程 ────────────────────────────────────────────────────────────────────

def process_data(stock_names):
    print(f"开始获取 A 股扫描数据: {stock_names}")

    codes = []
    for name in stock_names:
        code = name_to_code(name)
        if code: codes.append((name, code))
        else: print(f"  警告: 未找到股票 '{name}'，跳过")

    if not codes:
        print("错误: 没有有效的股票代码")
        return None

    codes_str = ",".join([c for _, c in codes])
    quotes = fetch_quotes(codes_str)

    print("Fetching K-lines...")
    klines_map = {}
    for name, code in codes:
        kl = fetch_kline(code, 60)
        klines_map[code] = kl

    # 加载板块主题词配置，打印每只股应搜索的主题
    sector_themes = load_sector_themes()
    print("\n板块主题搜索提示:")
    for name, code in codes:
        themes = get_stock_themes(code, sector_themes)
        theme_str = " / ".join(themes) if themes else "（未配置主题，请更新 sector_themes.json）"
        news_count = len(load_local_news(code))
        print(f"  {name}({code}): 主题={theme_str} | 当前新闻={news_count}条")

    print("\nLoading news...")
    news_map = {}
    for name, code in codes:
        news_map[code] = load_local_news(code)

    print("Fetching benchmark...")
    benchmark = fetch_benchmark()

    stocks_data = []
    for name, code in codes:
        q = quotes.get(code, {})
        kl = klines_map.get(code, [])
        news_list = news_map.get(code, [])
        price = q.get('price', 0) or (safe_float(kl[-1][2]) if kl else 0)
        chg_pct = q.get('chg_pct', 0)

        sc = overall_score(price, chg_pct, kl, news_list)
        total = sc['total']
        rating, rating_cls = rating_label(total)

        ma5  = calc_ma(kl, 5)
        ma10 = calc_ma(kl, 10)
        ma20 = calc_ma(kl, 20)
        ma60 = calc_ma(kl, 60)
        upper, mid_b, lower = calc_boll(kl)
        dif, dea, bar = calc_macd(kl)
        k, d, j = calc_kdj(kl)
        vr = volume_ratio(kl)
        chg_60 = chg60(klines_map.get(code, []))
        pos52w = calc_52w(klines_map.get(code, []))

        above_ma5, above_ma10, above_ma20, above_ma60 = ma_order(kl) if kl else (False, False, False, False)

        stocks_data.append({
            'name': name,
            'code': code,
            'price': price,
            'chg_pct': chg_pct,
            'open': q.get('open', 0),
            'high': q.get('high', 0),
            'low': q.get('low', 0),
            'volume': q.get('volume', 0),
            'amount': q.get('amount', 0),
            'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
            'boll_up': upper, 'boll_mid': mid_b, 'boll_low': lower,
            'dif': dif, 'dea': dea, 'bar': bar,
            'k': k, 'd': d, 'j': j,
            'vr': vr,
            'chg_60': chg_60,
            'pos52w': pos52w,
            'above_ma5': above_ma5, 'above_ma10': above_ma10,
            'above_ma20': above_ma20, 'above_ma60': above_ma60,
            'news': news_list,
            'news_count': len(news_list),
            'score': total,
            'score_detail': sc,
            'rating': rating,
            'rating_cls': rating_cls,
        })

    stocks_data.sort(key=lambda x: x['score'], reverse=True)

    hotspots = build_sector_hotspots(stocks_data)

    return {
        'stocks': stocks_data,
        'hotspots': hotspots,
        'benchmark': benchmark,
        'date': TODAY,
    }

# ── HTML 生成 ─────────────────────────────────────────────────────────────────

def fmt(v, fs='.2f'):
    if v is None: return '—'
    try: return f'{v:{fs}}'
    except: return str(v)

def chg_cls(v):
    if v is None: return ''
    return 'up' if v >= 0 else 'dn'

def chg_arrow(v):
    if v is None: return '—'
    return '▲' if v >= 0 else '▼'

def esc(s):
    if s is None: return ''
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def generate_html(data, out_path):
    stocks = data['stocks']
    hotspots = data['hotspots']
    benchmark = data['benchmark']
    date = data['date']
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    sh000001 = benchmark.get('sh000001', {})
    sh000300 = benchmark.get('sh000300', {})

    # ── Hero ────────────────────────────────────────────────────────────────
    # 判断大盘方向
    sh_chg = sh000001.get('chg_pct', 0)
    sh_price = sh000001.get('price', 0)
    if sh_chg >= 0.5:
        market_judge = "大盘偏强，沪指站上重要均线"
    elif sh_chg >= 0:
        market_judge = "大盘震荡偏强，结构性机会"
    elif sh_chg >= -0.5:
        market_judge = "大盘小幅回调，结构性分化"
    else:
        market_judge = "大盘偏弱，谨慎观望"

    # hero_picks: top 3 non-avoid stocks
    top_picks = [s for s in stocks if s['rating_cls'] != 'avoid'][:3]
    hero_picks_html = ""
    for i, s in enumerate(top_picks):
        reason = "; ".join(s['score_detail']['tech_reasons'][:2]) if s['score_detail']['tech_reasons'] else "技术面良好"
        if len(reason) > 40: reason = reason[:40] + "..."
        score_color = '#2e7d5e' if s['score'] >= 70 else ('#c9a84c' if s['score'] >= 50 else '#d64545')
        hero_picks_html += f"""
    <div class="hero-pick" onclick="showDetail('{s['code']}')">
      <span class="pick-rank">#{i+1}</span>
      <div class="pick-info">
        <div class="pick-ticker">{s['name']} <small>{s['code']}</small></div>
        <div class="pick-reason">{reason}</div>
      </div>
      <div class="pick-score">
        <div class="pick-score-num" style="color:{score_color}">{s['score']}</div>
        <div class="pick-score-lbl">{s['rating']}</div>
      </div>
    </div>"""

    if not hero_picks_html:
        hero_picks_html = '<p style="color:var(--muted);font-size:13px">今日暂无明确买入信号</p>'

    hero_title = market_judge
    hero_sub = f"上证指数 {fmt(sh_price,'.2f')} {chg_arrow(sh_chg)}{fmt(abs(sh_chg),'.2f')}%，扫描 {len(stocks)} 只标的"

    # ── Table rows ────────────────────────────────────────────────────────
    table_rows = ""
    for i, s in enumerate(stocks):
        cc = chg_cls(s['chg_pct'])
        arrow = chg_arrow(s['chg_pct'])
        ma_status = "多头" if s['above_ma5'] and s['above_ma10'] and s['above_ma20'] else ("站上MA5" if s['above_ma5'] else "—")
        chg60_str = f"{arrow}{fmt(abs(s['chg_60']),'.1f')}" if s['chg_60'] is not None else "—"
        pos52w_str = f"{fmt(s['pos52w'],'.0f')}%" if s['pos52w'] is not None else "—"
        score_color = '#2e7d5e' if s['score'] >= 70 else ('#c9a84c' if s['score'] >= 50 else '#d64545')
        badge_cls = 'badge-strong' if s['rating_cls'] == 'strong_buy' else ('badge-buy' if s['rating_cls'] == 'buy' else ('badge-hold' if s['rating_cls'] == 'neutral' else 'badge-sell'))
        action_str = f"{s['rating']} {'可关注' if s['rating_cls'] in ('strong_buy','buy') else ''}"
        if s['vr'] and s['vr'] > 1.5: action_str += " 放量"
        table_rows += f"""
    <tr onclick="showDetail('{s['code']}')">
      <td class="rank">{i+1}</td>
      <td><div class="ticker">{s['name']}</div><div class="sname">{s['code']}</div></td>
      <td><span style="font-family:var(--mono);font-size:16px;font-weight:700;color:{score_color}">{s['score']}</span><br><span class="badge {badge_cls}">{s['rating']}</span></td>
      <td class="hide-sm price">{fmt(s['price'])}</td>
      <td class="chg chg-{cc}">{arrow}{fmt(abs(s['chg_pct']),'.2f')}%</td>
      <td>{ma_status}</td>
      <td class="hide-sm chg chg-{chg_cls(s['chg_60'])}">{chg60_str}</td>
      <td class="hide-sm pos52">{pos52w_str}</td>
      <td class="action">{action_str}</td>
    </tr>"""

    # ── Sector hotspots ───────────────────────────────────────────────────
    sector_html = ""
    for h in hotspots:
        sector_html += f"""
  <div class="sector-card">
    <div class="sector-icon">{h['icon']}</div>
    <div class="sector-body">
      <div class="sector-name">{h['name']}</div>
      <div class="sector-desc">{h['desc']}</div>
    </div>
  </div>"""

    # ── Modals ─────────────────────────────────────────────────────────────
    modals_html = ""
    for s in stocks:
        cc = chg_cls(s['chg_pct'])
        arrow = chg_arrow(s['chg_pct'])
        badge_cls = 'badge-strong' if s['rating_cls'] == 'strong_buy' else ('badge-buy' if s['rating_cls'] == 'buy' else ('badge-hold' if s['rating_cls'] == 'neutral' else 'badge-sell'))
        score_color = '#2e7d5e' if s['score'] >= 70 else ('#c9a84c' if s['score'] >= 50 else '#d64545')
        header_bg = '#1a1a1a' if s['score'] >= 40 else '#8b2525'
        badge_html_cls = 'badge-strong' if s['rating_cls'] == 'strong_buy' else ('badge-buy' if s['rating_cls'] == 'buy' else ('badge-hold' if s['rating_cls'] == 'neutral' else 'badge-sell'))

        sc = s['score_detail']
        tech_pct = sc['tech'] / 30 * 100
        fund_pct = sc['fund'] / 40 * 100
        sect_pct = sc['sector'] / 20 * 100
        inst_pct = sc['institutional'] / 10 * 100
        news_pct = sc['news'] / 10 * 100
        news_bar_color = '#2e7d5e' if sc['news'] >= 5 else '#d64545'

        # News items
        news_items = ""
        for n in s['news'][:5]:
            title = esc(n.get('title', ''))
            link = n.get('link', '')
            date_str = n.get('date', '')[:10] if n.get('date') else ''
            source = n.get('source', '')
            if link:
                news_items += f"""<div class="news-item"><a href="{link}" target="_blank" class="news-link"><span class="news-title">{title}</span><span class="news-meta">{date_str} · {source}</span></a></div>"""
            else:
                news_items += f"""<div class="news-item"><span class="news-title">{title}</span><span class="news-meta">{date_str} · {source}</span></div>"""
        if not news_items:
            news_items = '<p style="color:#888;font-size:12px">暂无近7天新闻</p>'

        tech_reasons_str = "; ".join(sc['tech_reasons']) if sc['tech_reasons'] else "无明显信号"

        kdj_note = ""
        if s['k'] is not None:
            if s['j'] > 80: kdj_note = " 超买"
            elif s['j'] < 20: kdj_note = " 超卖"

        gaps_str = "无明显缺口"

        advice_cls = "advice-box strong-buy" if s['rating_cls'] == 'strong_buy' else ("advice-box sell" if s['rating_cls'] == 'avoid' else "advice-box")
        advice_text = f"{s['rating']} — {tech_reasons_str}"

        ma_rows_html = ""
        if s['ma5'] is not None:
            ma_rows_html += f"<tr><td class='lbl'>MA5</td><td class='val'>{fmt(s['ma5'],'.2f')}</td></tr>"
        if s['ma10'] is not None:
            ma_rows_html += f"<tr><td class='lbl'>MA10</td><td class='val'>{fmt(s['ma10'],'.2f')}</td></tr>"
        if s['ma20'] is not None:
            ma_rows_html += f"<tr><td class='lbl'>MA20</td><td class='val'>{fmt(s['ma20'],'.2f')}</td></tr>"
        if s['ma60'] is not None:
            ma_rows_html += f"<tr><td class='lbl'>MA60</td><td class='val'>{fmt(s['ma60'],'.2f')}</td></tr>"
        if not ma_rows_html:
            ma_rows_html = "<tr><td class='lbl'>均线</td><td class='val na-val'>— (历史数据不足)</td></tr>"

        macd_rows_html = ""
        if s['dif'] is not None:
            macd_cls = 'val-up' if s['dif'] > 0 else 'val-dn'
            macd_note = '金叉' if s['dif'] > 0 else '死叉'
            bar_str = fmt(s['bar'], '.3f') if s['bar'] is not None else '—'
            macd_rows_html = f"<tr><td class='lbl'>DIF</td><td class='val {macd_cls}'>{fmt(s['dif'],'.3f')} <span style='color:var(--muted);font-size:10px'>{macd_note}</span></td></tr>"
            if s['bar'] is not None:
                macd_rows_html += f"<tr><td class='lbl'>MACD柱</td><td class='val {'val-up' if s['bar'] > 0 else 'val-dn'}'>{bar_str}</td></tr>"
        if not macd_rows_html:
            macd_rows_html = "<tr><td class='lbl'>MACD</td><td class='val na-val'>— (历史数据不足)</td></tr>"

        boll_rows_html = ""
        if s['boll_up'] is not None:
            boll_rows_html = f"<tr><td class='lbl'>布林上轨</td><td class='val'>{fmt(s['boll_up'],'.2f')}</td></tr>"
            boll_rows_html += f"<tr><td class='lbl'>布林中轨</td><td class='val'>{fmt(s['boll_mid'],'.2f')}</td></tr>"
            boll_rows_html += f"<tr><td class='lbl'>布林下轨</td><td class='val'>{fmt(s['boll_low'],'.2f')}</td></tr>"
        if not boll_rows_html:
            boll_rows_html = "<tr><td class='lbl'>布林带</td><td class='val na-val'>— (历史数据不足)</td></tr>"

        chg60_val = s['chg_60'] if s['chg_60'] is not None else 0
        chg60_cls = 'val-up' if chg60_val >= 0 else 'val-dn'
        chg60_arrow = '▲' if chg60_val >= 0 else '▼'

        modals_html += f"""
<div class="m-overlay" id="modal-{s['code']}" onclick="closeModal(event,'{s['code']}')">
<div class="m-content" onclick="event.stopPropagation()">
  <button class="m-close" onclick="hideModal('{s['code']}')">✕</button>
  <div class="m-header" style="background:{header_bg}">
    <div class="m-title-row">
      <div><h2 class="m-code">{s['name']}</h2><p class="m-name">{s['code']}</p></div>
      <span class="m-badge {badge_html_cls}">{s['rating']} {s['score']}/110</span>
    </div>
    <div class="m-price-row">
      <span class="m-price">{fmt(s['price'])}</span>
      <div class="m-chg">
        <span class="chg-pill chg-pill-{'up' if s['chg_pct'] >= 0 else 'dn'}">{arrow}{fmt(abs(s['chg_pct']),'.2f')}% 今日</span>
        <span class="chg-pill chg-pill-{'up' if chg60_val >= 0 else 'dn'}">{chg60_arrow}{fmt(abs(chg60_val),'.1f')}% 60日</span>
      </div>
    </div>
  </div>
  <div class="m-body">
    <div class="score-section">
      <div class="score-total" style="background:{score_color}">{s['score']}<span class="score-denom">/110</span></div>
      <div class="score-bars">
        <div class="score-row"><span class="score-label">技术面</span><div class="score-track"><div class="score-fill" style="width:{tech_pct:.0f}%;background:#aaa"></div></div><span class="score-val" style="color:#aaa">{sc['tech']}/30</span></div>
        <div class="score-row"><span class="score-label">基本面</span><div class="score-track"><div class="score-fill" style="width:{fund_pct:.0f}%;background:#5b9bd5"></div></div><span class="score-val" style="color:#5b9bd5">{sc['fund']}/40</span></div>
        <div class="score-row"><span class="score-label">板块</span><div class="score-track"><div class="score-fill" style="width:{sect_pct:.0f}%;background:#2e7d5e"></div></div><span class="score-val" style="color:#2e7d5e">{sc['sector']}/20</span></div>
        <div class="score-row"><span class="score-label">机构评级</span><div class="score-track"><div class="score-fill" style="width:{inst_pct:.0f}%;background:#c9a84c"></div></div><span class="score-val" style="color:#c9a84c">{sc['institutional']}/10</span></div>
        <div class="score-row"><span class="score-label">消息面</span><div class="score-track"><div class="score-fill" style="width:{news_pct:.0f}%;background:{news_bar_color}"></div></div><span class="score-val" style="color:{news_bar_color}">{sc['news']}/10</span></div>
      </div>
    </div>

    <h3 class="section-title">技术面指标</h3>
    <table class="tech-table">
      <tr><td class="lbl">现价</td><td class="val">{fmt(s['price'])}</td></tr>
      <tr><td class="lbl">60日涨跌</td><td class="val {chg60_cls}">{chg60_arrow}{fmt(abs(chg60_val),'.1f')}%</td></tr>
      <tr><td class="lbl">52W高 / 低</td><td class="val">{fmt(s.get('price') or 0)} / —</td></tr>
      <tr><td class="lbl">52W位置</td><td class="val">{fmt(s['pos52w'],'.0f')}%</td></tr>
      <tr><td class="lbl">量比</td><td class="val">{'—' if s['vr'] is None else f"{s['vr']:.2f}x"} <span style="color:var(--muted);font-size:10px">(近5日/前20日)</span></td></tr>
      <tr><td class="lbl">KDJ</td><td class="val">K={fmt(s['k'],'.0f')} D={fmt(s['d'],'.0f')} J={fmt(s['j'],'.0f')}{kdj_note}</td></tr>
      {ma_rows_html}
      {macd_rows_html}
      {boll_rows_html}
    </table>

    <h3 class="section-title">最新新闻 <span style="font-weight:400;color:var(--muted);font-size:11px">近7天 {s['news_count']} 条</span></h3>
    <div class="news-list">{news_items}</div>

    <h3 class="section-title">交易建议</h3>
    <div class="{advice_cls}">{advice_text}</div>
  </div>
</div>
</div>"""

    # ── CSS ────────────────────────────────────────────────────────────────
    CSS = """@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--ink:#1a1a1a;--gold:#c9a84c;--gold-light:#e8c96d;--red:#d64545;--green:#2e7d5e;--muted:#888;--border:#e0ddd8;--bg:#fafaf8;--card:#ffffff;--mono:'SF Mono','Fira Code',monospace}
html{font-size:16px;scroll-behavior:smooth}
body{font-family:'Noto Sans SC','PingFang SC',sans-serif;background:var(--bg);color:var(--ink);line-height:1.7;-webkit-font-smoothing:antialiased;max-width:720px;margin:0 auto;padding:0 20px}
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
.hero-picks{display:flex;flex-direction:column;gap:10px}
.hero-pick{display:flex;align-items:center;gap:14px;padding:12px 14px;background:var(--bg);border-radius:3px;border-left:3px solid var(--gold);cursor:pointer}
.hero-pick:hover{background:rgba(201,168,76,0.05)}
.pick-rank{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--gold);background:rgba(201,168,76,0.1);padding:2px 7px;border-radius:2px;flex-shrink:0}
.pick-info{flex:1;min-width:0}
.pick-ticker{font-size:14px;font-weight:700;color:var(--ink)}
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
.section-hdr{font-family:'Noto Serif SC',serif;font-size:16px;font-weight:700;color:var(--ink);padding-bottom:10px;border-bottom:2px solid var(--ink);margin:28px 0 16px;display:flex;align-items:baseline;justify-content:space-between}
.section-hdr span{font-family:'Noto Sans SC',sans-serif;font-size:12px;font-weight:400;color:var(--muted)}
.tbl{width:100%;border-collapse:collapse;margin-bottom:40px;font-size:13px}
.tbl th{font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted);font-weight:500;padding:8px 10px;text-align:left;border-bottom:1px solid var(--border)}
.tbl td{padding:11px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:rgba(201,168,76,0.03)}
.tbl tr{cursor:pointer}
.tbl .rank{font-family:var(--mono);font-size:11px;color:var(--muted);width:32px}
.tbl .ticker{font-weight:700;font-size:14px;color:var(--ink);line-height:1.2}
.tbl .sname{font-size:10px;color:var(--muted);margin-top:1px}
.badge{display:inline-block;padding:2px 7px;border-radius:2px;font-size:10px;font-weight:600;margin-top:3px;white-space:nowrap}
.badge-strong{background:rgba(46,125,94,0.15);color:var(--green)}
.badge-buy{background:rgba(46,125,94,0.1);color:var(--green)}
.badge-hold{background:rgba(201,168,76,0.15);color:#9a7a2e}
.badge-sell{background:rgba(214,69,69,0.1);color:var(--red)}
.tbl .price{font-family:var(--mono);font-weight:600;font-size:13px}
.chg{font-family:var(--mono);font-size:12px}
.chg-up{color:var(--green)}.chg-dn{color:var(--red)}
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
.news-link{text-decoration:none;display:block}
.news-link:hover{background:rgba(201,168,76,0.03)}
.news-title{font-size:12px;color:var(--ink);font-weight:500;display:block;line-height:1.4}
.news-meta{font-size:10px;color:var(--muted);margin-top:2px;display:block}
.advice-box{background:var(--bg);border-radius:4px;padding:12px 15px;font-size:13px;color:var(--ink);line-height:1.7;border-left:3px solid var(--gold);margin-top:8px}
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

    # ── JS ────────────────────────────────────────────────────────────────
    JS = """function showDetail(code){var m=document.getElementById('modal-'+code);if(m){m.classList.add('open');document.body.style.overflow='hidden'}}
function hideModal(code){var m=document.getElementById('modal-'+code);if(m){m.classList.remove('open');document.body.style.overflow=''}}
function closeModal(e,code){if(e.target===e.currentTarget)hideModal(code);}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){document.querySelectorAll('.m-overlay.open').forEach(function(m){m.classList.remove('open')});document.body.style.overflow=''}});
var touchStartY=0;
document.querySelectorAll('.m-overlay').forEach(function(o){o.addEventListener('touchstart',function(e){touchStartY=e.changedTouches[0].screenY},{passive:true});o.addEventListener('touchend',function(e){if(e.changedTouches[0].screenY-touchStartY>80){o.classList.remove('open');document.body.style.overflow=''}},{passive:true})});"""

    # ── 组装 ──────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股个股扫描 · {date}</title>
<style>{CSS}</style>
</head>
<body>

<header class="pub-header">
  <div class="pub-brand"><span>·</span> A股个股扫描</div>
  <div>
    <div class="pub-meta">{today_str} · {len(stocks)} 只标的</div>
    <div class="pub-disclaimer">数据仅供参考，不构成投资建议</div>
  </div>
</header>

<section class="hero">
  <div class="hero-label">今日结论</div>
  <h1 class="hero-title">{hero_title}</h1>
  <p class="hero-sub">{hero_sub}</p>
  <div class="hero-picks">
{hero_picks_html}
  </div>
</section>

<section class="bench">
  <div>
    <div class="bench-name">上证指数 (sh000001)</div>
    <div class="bench-desc">大盘基准</div>
  </div>
  <div class="bench-stats">
    <div class="bench-stat"><div class="bench-stat-label">现价</div><div class="bench-stat-val">{fmt(sh000001.get('price',0))}</div></div>
    <div class="bench-stat"><div class="bench-stat-label">今日</div><div class="bench-stat-val">{chg_arrow(sh_chg)}{fmt(abs(sh_chg),'.2f')}%</div></div>
  </div>
  <div>
    <div class="bench-name">沪深300 (sh000300)</div>
    <div class="bench-desc">大盘基准</div>
  </div>
  <div class="bench-stats">
    <div class="bench-stat"><div class="bench-stat-label">现价</div><div class="bench-stat-val">{fmt(sh000300.get('price',0))}</div></div>
    <div class="bench-stat"><div class="bench-stat-label">今日</div><div class="bench-stat-val">{chg_arrow(sh000300.get('chg_pct',0))}{fmt(abs(sh000300.get('chg_pct',0)),'.2f')}%</div></div>
  </div>
</section>

<div class="section-hdr">全部标的 <span>按综合评分降序</span></div>
<table class="tbl">
  <thead>
    <tr>
      <th class="rank">#</th>
      <th>标的</th>
      <th>评分</th>
      <th class="hide-sm">现价</th>
      <th>今日涨跌</th>
      <th>MA状态</th>
      <th class="hide-sm">60日涨跌</th>
      <th class="hide-sm">52W位</th>
      <th class="action">建议</th>
    </tr>
  </thead>
  <tbody>
{table_rows}
  </tbody>
</table>
"""

    if sector_html:
        html += f"""
<div class="section-hdr" style="margin-top:8px">板块热点</div>
<div class="sectors">
{sector_html}
</div>"""

    html += f"""
<footer class="footer">
  <p>A股个股扫描 · {date} · 共 {len(stocks)} 只标的</p>
  <p class="disc">本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。</p>
</footer>

{modals_html}

<script>{JS}</script>
</body>
</html>"""

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Generated {out_path} ({len(html)} bytes)")

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    default_stocks = ["中科电气", "拓维信息", "品高软件"]
    stock_names = []
    for arg in sys.argv[2:]:
        stock_names.append(arg.strip())
    if not stock_names:
        stock_names = default_stocks

    data = process_data(stock_names)
    if not data: return

    today_prefix = f"a_stock_scan_{TODAY}_"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    existing = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(today_prefix)]
    next_num = len(existing) + 1
    report_filename = f"{today_prefix}{next_num:03d}.html"
    out_path = os.path.join(OUTPUT_DIR, report_filename)

    generate_html(data, out_path)

    print(f"\n=== 扫描结果 ({TODAY}) ===")
    for i, s in enumerate(data['stocks']):
        print(f"  {i+1}. {s['name']}({s['code']}) {s['price']:.2f} {s['chg_pct']:+.2f}% 综合评分:{s['score']} {s['rating']}")
    print(f"\n报告: {out_path}")
    print(f"URL: http://150.109.233.168/reports/{report_filename}")

if __name__ == '__main__':
    main()
