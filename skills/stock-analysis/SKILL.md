---
name: stock-analysis
description: A 股个股深度分析 — 覆盖基本面、财报、板块热度、技术面，给出买入评级和交易建议，生成 WeChat Article 风格的 HTML 报告。
version: 2.0.0
author: Hermes Agent
tags: [a-stock, china, stock-analysis, fundamental, technical, sector, html-report]
required_environment_variables: []
required_commands: []
---

# A 股个股深度分析

分析单只 A 股股票，输出：基本面 + 板块热度 + 技术面 + 研报/新闻 + 买入评级 + 交易建议，并生成 WeChat Article 风格的 HTML 报告。

---

## 输入

运行 skill 时通过 context 传入：
- 股票代码（如 sh600519、sz000858、sz300750、sh688041）
- 分析日期

---

## 分析流程

```
1. 股票确认 → 解析股票代码（沪深/创业板/科创板）
2. 行情快照 → 实时价格、PE/PB、涨跌、成交量
3. 基本面   → 营收、利润、现金流、ROE、负债率、股息率
4. 财报     → 近2年关键科目（营收增速、净利增速，毛利率）
5. 板块热度 → 个股所属板块的资金热度（板块涨跌+资金流向）
6. 消息面   → 近一周新闻、研报摘要
7. 技术面   → K线、均线、MACD、KDJ、布林带、支撑压力位
8. 综合评级 → 买入/持有/卖出 + 理由 + 交易计划

9. 生成 HTML 报告
   - 输出到 {project}/stock_analysis_{代码}_{日期}.html
```

---

## 数据获取

### 1. 实时行情（腾讯API）

```bash
# 单股行情
curl -s --max-time 10 "https://qt.gtimg.cn/q=sh600519"   # 上海
curl -s --max-time 10 "https://qt.gtimg.cn/q=sz000858"   # 深圳
curl -s --max-time 10 "https://qt.gtimg.cn/q=sz300750"   # 创业板
curl -s --max-time 10 "https://qt.gtimg.cn/q=sh688041"   # 科创板
```

返回字段（~分隔，GBK编码，需 iconv）：
```
字段3=当前价, 字段4=昨收, 字段31=涨跌额, 字段32=涨跌幅%
字段33=最高, 字段34=最低, 字段36=成交量(手), 字段37=成交额(万)
字段39=PE, 字段40=总市值(万), 字段41=流通市值(万)
字段46=PB, 字段47=60日涨跌幅, 字段48=年初至今涨跌幅
字段12=所属板块名称
```

### 2. 日K线数据（QQ财经）

```bash
# 最近60日K线（用于技术分析）
curl -s --max-time 10 \
  "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=SECURITY_CODE,day,,,60,qfq" | iconv -f gbk -t utf-8
```

返回JSON格式：`kline_dayqfq={JSON};` — 注意响应是**变量赋值格式**，需先剥离前缀和末尾分号再解析：

```bash
# 正确解析方式
curl -s --max-time 10 \
  "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=SECURITY_CODE,day,,,60,qfq" \
  | iconv -f gbk -t utf-8 \
  | python3 -c "
import sys, json, re
raw = sys.stdin.read()
start = raw.find('=') + 1
json_str = raw[start:]
if json_str.endswith(';'): json_str = json_str[:-1]
d = json.loads(json_str)
days = d['data']['SECURITY_CODE']['qfqday']
for row in days:
    print(row[0], '收', row[2])
"
```

返回`data[SECURITY_CODE]["day"]`（前复权）或`["qfqday"]`（前复权K线），为数组列表 `[日期, 开, 收, 高, 低, 量]`

### 3. 财务数据（东方财富API）

```bash
# 主要财务指标
curl -s --max-time 15 \
  "https://emweb.securities.eastmoney.com/PC_HSF10/FinanceAnalysis/Analysis?code=SH600519"

# 利润表（近4季度）
curl -s --max-time 15 \
  "https://emweb.securities.eastmoney.com/PC_HSF10/ProfitStatement/ProfitStatement?code=SH600519"

# 资产负债表
curl -s --max-time 15 \
  "https://emweb.securities.eastmoney.com/PC_HSF10/BalanceSheet/BalanceSheet?code=SH600519"
```

### 4. 个股新闻（东方财富）

```bash
curl -s --max-time 15 \
  "https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=10&page_index=1&ann_type=A&client_source=web&stock_list=SH600519"
```

### 5. 研报（东方财富研报API）

```bash
curl -s --max-time 15 \
  "https://reportapi.eastmoney.com/report/list?industryCode=*&pageSize=5&industry=*&rating=&ratingChange=&beginTime=2026-01-01&endTime={{date}}&pageNo=1&qType=0&orgCode=&rateType=0&_=1714000000000"
```

### 6. 板块资金流向

```bash
# 个股所属板块（从实时行情字段12获取）
# 然后用 a-stock-base skill 的板块API获取板块热度
```

---

## 股票代码规则

| 前缀 | 市场 | 示例 |
|------|------|------|
| sh6xxxxx | 上交所主板 | sh600519 = 贵州茅台 |
| sz0xxxxx | 深交所主板 | sz000858 = 五粮液 |
| sz3xxxxx | 创业板 | sz300750 = 宁德时代 |
| sh688xxx | 科创板 | sh688041 = 寒武纪 |

---

## 技术面计算

从60日K线数据计算：

```
均线: MA5, MA10, MA20, MA60（收盘价简单移动平均）
MACD: EMA12 - EMA26，signal=EMA9(DIF)
KDJ: RSV = (C-LLV)/(HHV-LLV)*100，K=2/3*prevK+1/3*RSV
布林: 中轨=MA20, 上轨=MA20+2*STD20, 下轨=MA20-2*STD20
RSI: 100-100/(1+RS)，RS=N日涨幅度均值/跌幅度均值
```

关键信号：
- 均线多头排列：MA5>MA10>MA20>MA60 → 强势
- MACD 金叉（DIF>DEA 且向上）→ 买入信号
- KDJ 金叉（K>D 且 K 从下向上）→ 短期买入信号
- 股价触及布林下轨且缩量 → 超卖反弹机会
- 股价触及布林上轨 + 放量 → 可能是波段卖点

---

## 评级标准

### 基本面评分（40分）
- ROE > 15% → 10分，10-15% → 6分，< 10% → 2分
- 营收增速 > 20% → 10分，10-20% → 6分，< 10% → 2分
- 净利增速 > 20% → 10分，10-20% → 6分，< 10% → 2分
- 毛利率（连续2年稳定或提升）→ 5分，下降 → 2分
- 负债率 < 60% → 5分，60-75% → 3分，> 75% → 0分
- 股息率 > 2.5% → 5分，1.5-2.5% → 3分，< 1.5% → 1分

### 技术面评分（30分）
- 均线多头排列 → 10分，空头排列 → -5分
- MACD 零轴上方金叉 → 8分，零轴下方 → 5分
- KDJ J值 < 20（超卖）→ 8分，J值 > 80（超买）→ -5分
- 缩量回踩布林中轨获得支撑 → 4分

### 板块热度评分（20分）
- 所属板块涨幅 > 2% + 资金净流入 → 20分
- 板块涨幅 > 1% 或资金净流入 → 12分
- 板块小幅涨跌，资金中性 → 6分
- 板块下跌且资金流出 → 0分

### 消息面评分（10分）
- 近一周有业绩超预期公告 / 研报覆盖 → +5分
- 近一周有政策利好（与个股业务相关）→ +5分
- 近一周无重大新闻 → 0分
- 近一周有利空（业绩下调 / 监管问询）→ -5分

### 综合评级

| 总分 | 评级 | 说明 |
|------|------|------|
| 75-100 | 强烈买入 | 基本面优秀 + 技术突破 + 板块共振 |
| 55-74 | 买入 | 基本面良好或技术面走强 |
| 35-54 | 持有 | 中性，等待更好买点 |
| < 35 | 卖出 | 基本面恶化或技术破位 |

---

## HTML 报告生成

分析完成后，将结果写入 HTML 文件（路径：`{project}/stock_analysis_{代码}_{日期}.html`）。

### 输出路径

```
{project}/stock_analysis_{股票代码}_{YYYYMMDD}.html
```

例如：`stock_analysis_sh600519_20260425.html`

### HTML 模板

将以下模板复制到文件中，然后将所有 `{{VARIABLE}}` 替换为实际数据。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{stock_name}}{{code}} 个股分析 · {{date}}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --ink:#1a1a1a;--gold:#c9a84c;--gold-light:#e8c96d;
  --red:#d64545;--green:#2e7d5e;--muted:#888;
  --border:#e0ddd8;--bg:#fafaf8;--card:#ffffff;
  --mono:'SF Mono','Fira Code','Courier New',monospace;
}
html{font-size:16px}
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

/* Stock Hero */
.stock-hero{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:28px 28px 24px;margin-bottom:36px;box-shadow:0 1px 4px rgba(0,0,0,0.04)}
.hero-label{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);font-weight:600;margin-bottom:16px;display:flex;align-items:center;gap:6px}
.hero-label::before{content:'';display:block;width:20px;height:1px;background:var(--gold)}
.hero-title{font-family:'Noto Serif SC',serif;font-size:20px;font-weight:700;color:var(--ink);margin-bottom:6px;line-height:1.4}
.hero-sub{font-size:13px;color:var(--muted);margin-bottom:20px}
.price-row{display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:16px}
.price-main{font-family:var(--mono);font-size:36px;font-weight:700;color:var(--ink);line-height:1}
.price-chg{font-family:var(--mono);font-size:16px;font-weight:600;line-height:1;padding-bottom:4px}
.chg-up{color:var(--green)}.chg-dn{color:var(--red)}
.stats-row{display:flex;gap:16px;flex-wrap:wrap}
.stat-item{}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
.stat-val{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ink)}
.rating-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:3px;font-size:13px;font-weight:700}
.rating-badge.strong-buy{background:rgba(46,125,94,0.12);color:var(--green)}
.rating-badge.buy{background:rgba(46,125,94,0.08);color:#3d8a5f}
.rating-badge.hold{background:rgba(201,168,76,0.12);color:#9a7a2e}
.rating-badge.sell{background:rgba(214,69,69,0.1);color:var(--red)}
.rating-badge .score{font-family:var(--mono);font-size:15px}

/* Section */
.section-hdr{font-family:'Noto Serif SC',serif;font-size:16px;font-weight:700;color:var(--ink);padding-bottom:10px;border-bottom:2px solid var(--ink);margin:32px 0 16px;display:flex;align-items:baseline;justify-content:space-between}
.section-hdr span{font-family:'Noto Sans SC',sans-serif;font-size:12px;font-weight:400;color:var(--muted)}

/* Score Section */
.score-section{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--border);border-radius:4px;padding:14px;margin-bottom:20px;flex-wrap:wrap}
.score-total{width:64px;height:64px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0}
.score-denom{font-size:9px;opacity:.7;font-weight:400}
.score-bars{flex:1;min-width:180px}
.score-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.score-row:last-child{margin-bottom:0}
.score-label{width:50px;font-size:11px;color:var(--muted);flex-shrink:0}
.score-track{flex:1;height:5px;background:#e8e5e0;border-radius:3px;overflow:hidden}
.score-fill{height:100%;border-radius:3px}
.score-val{width:32px;text-align:right;font-size:11px;font-weight:700;flex-shrink:0}

/* Data Tables */
.data-card{background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden;margin-bottom:20px}
.data-table{width:100%;border-collapse:collapse}
.data-table td{padding:8px 14px;font-size:13px;border-bottom:1px solid var(--border);vertical-align:middle}
.data-table tr:last-child td{border-bottom:none}
.data-table tr:nth-child(even) td{background:rgba(0,0,0,0.015)}
.data-table .lbl{color:var(--muted);font-weight:500;width:40%}
.data-table .val{font-family:var(--mono);font-weight:600;color:var(--ink)}
.data-table .val-up{color:var(--green)}.data-table .val-dn{color:var(--red)}
.data-table .na{color:#bbb}

/* News */
.news-list{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}
.news-card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:12px 14px;border-left:3px solid var(--gold)}
.news-date{font-size:10px;color:var(--muted);margin-bottom:3px}
.news-title{font-size:13px;color:var(--ink);font-weight:500;line-height:1.4}
.news-source{font-size:10px;color:var(--muted);margin-top:2px}
.no-news{font-size:12px;color:var(--muted);font-style:italic;background:var(--card);border:1px solid var(--border);border-radius:4px;padding:12px 14px}

/* Advice */
.advice-box{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:16px 18px;margin-bottom:20px}
.advice-box.strong-buy{border-left:4px solid var(--green);background:rgba(46,125,94,0.04)}
.advice-box.buy{border-left:4px solid var(--green)}
.advice-box.hold{border-left:4px solid var(--gold);background:rgba(201,168,76,0.04)}
.advice-box.sell{border-left:4px solid var(--red);background:rgba(214,69,69,0.04)}
.advice-title{font-weight:600;font-size:13px;color:var(--ink);margin-bottom:8px}
.advice-row{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:6px}
.advice-item{display:flex;align-items:baseline;gap:6px}
.advice-item .label{font-size:11px;color:var(--muted)}
.advice-item .value{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--ink)}
.advice-risk{font-size:12px;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px solid var(--border)}

/* Footer */
.footer{text-align:center;padding:32px 0;border-top:1px solid var(--border);margin-top:48px}
.footer p{font-size:11px;color:var(--muted)}
.footer .disc{margin-top:4px;font-size:10px}

/* Responsive */
@media(max-width:600px){
  body{padding:0 14px}
  .pub-header{padding:28px 0 18px;margin-bottom:28px}
  .stock-hero{padding:20px 16px}
  .price-main{font-size:28px}
  .score-total{width:52px;height:52px}
  .advice-row{gap:10px}
}
</style>
</head>
<body>

<header class="pub-header">
  <div class="pub-brand"><span>·</span> A 股个股分析</div>
  <div>
    <div class="pub-meta">{{stock_name}} ({{market}})</div>
    <div class="pub-disclaimer">数据仅供参考，不构成投资建议</div>
  </div>
</header>

<!-- 行情快照 Hero -->
<section class="stock-hero">
  <div class="hero-label">行情快照</div>
  <h1 class="hero-title">{{stock_name}} ({{code}})</h1>
  <p class="hero-sub">{{sector}} · {{date}}</p>
  <div class="price-row">
    <span class="price-main">{{price}}</span>
    <span class="price-chg CHG_CLASS">{{chg_amount}} ({{chg_pct}})</span>
  </div>
  <div class="stats-row">
    <div class="stat-item"><div class="stat-label">今高 / 今低</div><div class="stat-val">{{high}} / {{low}}</div></div>
    <div class="stat-item"><div class="stat-label">成交额</div><div class="stat-val">{{turnover}}</div></div>
    <div class="stat-item"><div class="stat-label">PE</div><div class="stat-val">{{pe}}</div></div>
    <div class="stat-item"><div class="stat-label">PB</div><div class="stat-val">{{pb}}</div></div>
    <div class="stat-item"><div class="stat-label">总市值</div><div class="stat-val">{{mktcap}}</div></div>
    <div class="stat-item"><div class="stat-label">60日涨跌</div><div class="stat-val CHG_CLASS">{{chg_60}}</div></div>
  </div>
  <div style="margin-top:16px">
    <span class="rating-badge RATING_CLASS">
      <span class="score">{{score}}</span>/100 · {{rating_label}}
    </span>
  </div>
</section>

<!-- 评分 -->
<div class="section-hdr">综合评分</div>
<div class="score-section">
  <div class="score-total" style="background:RATING_COLOR">
    {{score}}<span class="score-denom">/100</span>
  </div>
  <div class="score-bars">
    <div class="score-row">
      <span class="score-label">基本面</span>
      <div class="score-track"><div class="score-fill" style="width:FUND_PCT%;background:#5b9bd5"></div></div>
      <span class="score-val" style="color:#5b9bd5">{{fund_score}}/40</span>
    </div>
    <div class="score-row">
      <span class="score-label">技术面</span>
      <div class="score-track"><div class="score-fill" style="width:TECH_PCT%;background:#aaa"></div></div>
      <span class="score-val" style="color:#aaa">{{tech_score}}/30</span>
    </div>
    <div class="score-row">
      <span class="score-label">板块热度</span>
      <div class="score-track"><div class="score-fill" style="width:SECTOR_PCT%;background:var(--green)"></div></div>
      <span class="score-val" style="color:var(--green)">{{sector_score}}/20</span>
    </div>
    <div class="score-row">
      <span class="score-label">消息面</span>
      <div class="score-track"><div class="score-fill" style="width:NEWS_PCT%;background:var(--gold)"></div></div>
      <span class="score-val" style="color:var(--gold)">{{news_score}}/10</span>
    </div>
  </div>
</div>

<!-- 基本面 -->
<div class="section-hdr">基本面 <span>近4季度</span></div>
<div class="data-card">
  <table class="data-table">
    <tr><td class="lbl">营收</td><td class="val">{{revenue}}</td></tr>
    <tr><td class="lbl">营收增速</td><td class="val CHG_CLASS">{{revenue_growth}}</td></tr>
    <tr><td class="lbl">净利润</td><td class="val">{{netprofit}}</td></tr>
    <tr><td class="lbl">净利润增速</td><td class="val CHG_CLASS">{{netprofit_growth}}</td></tr>
    <tr><td class="lbl">ROE</td><td class="val">{{roe}}</td></tr>
    <tr><td class="lbl">毛利率</td><td class="val">{{gross_margin}}</td></tr>
    <tr><td class="lbl">负债率</td><td class="val">{{debt_ratio}}</td></tr>
    <tr><td class="lbl">股息率</td><td class="val">{{dividend_yield}}</td></tr>
  </table>
</div>

<!-- 财报质量 -->
<div class="section-hdr">财报质量评估</div>
<div class="data-card">
  <table class="data-table">
    <tr><td class="lbl">现金流/净利润</td><td class="val">{{cf_np_ratio}}</td></tr>
    <tr><td class="lbl">应收账款增速</td><td class="val">{{ar_growth}}</td></tr>
    <tr><td class="lbl">商誉占净资产</td><td class="val {{risk_class}}">{{goodwill_ratio}}</td></tr>
    <tr><td class="lbl">存货周转</td><td class="val">{{inventory_turnover}}</td></tr>
  </table>
</div>

<!-- 板块热度 -->
<div class="section-hdr">板块热度</div>
<div class="data-card">
  <table class="data-table">
    <tr><td class="lbl">所属板块</td><td class="val">{{sector}}</td></tr>
    <tr><td class="lbl">板块涨跌</td><td class="val CHG_CLASS">{{sector_chg}}</td></tr>
    <tr><td class="lbl">板块资金</td><td class="val CHG_CLASS">{{sector_flow}}</td></tr>
  </table>
</div>

<!-- 技术面 -->
<div class="section-hdr">技术面</div>
<div class="data-card">
  <table class="data-table">
    <tr><td class="lbl">均线</td><td class="val">MA5={{ma5}} MA10={{ma10}} MA20={{ma20}} MA60={{ma60}}</td></tr>
    <tr><td class="lbl">趋势</td><td class="val">{{trend}}</td></tr>
    <tr><td class="lbl">MACD</td><td class="val">DIF={{dif}} DEA={{dea}} ({{macd_signal}})</td></tr>
    <tr><td class="lbl">KDJ</td><td class="val">K={{k}} D={{d}} J={{j}} ({{kdj_signal}})</td></tr>
    <tr><td class="lbl">布林</td><td class="val">上轨={{upper}} 中轨={{middle}} 下轨={{lower}}</td></tr>
    <tr><td class="lbl">支撑位</td><td class="val">{{support}}</td></tr>
    <tr><td class="lbl">压力位</td><td class="val">{{resistance}}</td></tr>
  </table>
</div>

<!-- 新闻 -->
<div class="section-hdr">近一周新闻</div>
{{news_html}}

<!-- 交易建议 -->
<div class="section-hdr">交易建议</div>
<div class="advice-box {{advice_class}}">
  <div class="advice-title">{{rating_label}} — {{advice_summary}}</div>
  <div class="advice-row">
    <div class="advice-item"><span class="label">入场区间</span><span class="value">{{entry_range}}</span></div>
    <div class="advice-item"><span class="label">止损位</span><span class="value" style="color:var(--red)">{{stop_loss}}</span></div>
    <div class="advice-item"><span class="label">目标位</span><span class="value" style="color:var(--green)">{{target}}</span></div>
    <div class="advice-item"><span class="label">仓位</span><span class="value">{{position}}</span></div>
    <div class="advice-item"><span class="label">持有周期</span><span class="value">{{holding_period}}</span></div>
  </div>
  {{#if risk}}
  <div class="advice-risk">风险提示：{{risk}}</div>
  {{/if}}
</div>

<footer class="footer">
  <p>{{stock_name}} ({{code}}) · 个股分析 · {{date}}</p>
  <p class="disc">本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。</p>
</footer>

</body>
</html>
```

---

## HTML 模板变量说明

### 基础信息

| 变量 | 说明 | 示例 |
|------|------|------|
| `{{date}}` | 分析日期 | 2026-04-25 |
| `{{stock_name}}` | 公司简称 | 贵州茅台 |
| `{{code}}` | 股票代码 | sh600519 |
| `{{market}}` | 市场 | 上交所主板 |

### 行情快照

| 变量 | 说明 |
|------|------|
| `{{price}}` | 现价（含货币单位） | ￥1680.00 |
| `{{chg_amount}}` | 涨跌额（含符号） | +20.50 |
| `{{chg_pct}}` | 涨跌幅（含符号） | +1.23% |
| `{{CHG_CLASS}}` | 颜色类：`chg-up`（上涨）或 `chg-dn`（下跌） |
| `{{high}}` / `{{low}}` | 今高 / 今低 |
| `{{turnover}}` | 成交额（格式化） | 28.5亿 |
| `{{pe}}` / `{{pb}}` | PE / PB 值，N/A 则显示 "—" |
| `{{mktcap}}` | 总市值（格式化） | 2.1万亿 |
| `{{chg_60}}` | 60日涨跌（含符号颜色） | +12.5% |

### 评级

| 变量 | 说明 |
|------|------|
| `{{score}}` | 总分（数字） |
| `{{rating_label}}` | 强烈买入 / 买入 / 持有 / 卖出 |
| `{{RATING_CLASS}}` | `strong-buy` / `buy` / `hold` / `sell` |
| `{{RATING_COLOR}}` | `var(--green)` / `var(--gold)` / `var(--red)` |

### 评分分项

| 变量 | 说明 |
|------|------|
| `{{fund_score}}` / `{{FUND_PCT}}` | 基本面得分 / 百分比（得分/40*100） |
| `{{tech_score}}` / `{{TECH_PCT}}` | 技术面得分 / 百分比 |
| `{{sector_score}}` / `{{SECTOR_PCT}}` | 板块得分 / 百分比 |
| `{{news_score}}` / `{{NEWS_PCT}}` | 消息面得分 / 百分比 |

### 基本面

| 变量 | 说明 |
|------|------|
| `{{revenue}}` | 营收（含单位） |
| `{{revenue_growth}}` | 营收增速（含颜色类） |
| `{{netprofit}}` | 净利润（含单位） |
| `{{netprofit_growth}}` | 净利增速 |
| `{{roe}}` / `{{gross_margin}}` | ROE / 毛利率 |
| `{{debt_ratio}}` / `{{dividend_yield}}` | 负债率 / 股息率 |

### 财报质量

| 变量 | 说明 |
|------|------|
| `{{cf_np_ratio}}` | 现金流/净利润比 |
| `{{ar_growth}}` | 应收账款增速 |
| `{{goodwill_ratio}}` | 商誉占净资产（含颜色类） |
| `{{inventory_turnover}}` | 存货周转 |
| `{{risk_class}}` | 商誉>30%时为 `val-dn`，否则为空 |

### 板块

| 变量 | 说明 |
|------|------|
| `{{sector}}` | 所属板块名称 |
| `{{sector_chg}}` | 板块涨跌（含颜色类） |
| `{{sector_flow}}` | 板块资金流向（含颜色类） |

### 技术面

| 变量 | 说明 | N/A 时 |
|------|------|--------|
| `{{ma5}}` / `{{ma10}}` / `{{ma20}}` / `{{ma60}}` | 各均线值 | 显示 "—" |
| `{{trend}}` | 趋势描述 | — |
| `{{dif}}` / `{{dea}}` | MACD 值 | "—" |
| `{{macd_signal}}` | 金叉/死叉状态 | "—" |
| `{{k}}` / `{{d}}` / `{{j}}` | KDJ 值 | — |
| `{{kdj_signal}}` | 超买/超卖/正常 | — |
| `{{upper}}` / `{{middle}}` / `{{lower}}` | 布林轨道 | 显示 "—" |
| `{{support}}` | 支撑位（逗号分隔） | "—" |
| `{{resistance}}` | 压力位（逗号分隔） | "—" |

### 新闻

`{{news_html}}` — 新闻列表 HTML 片段：

```html
<div class="news-list">
  <div class="news-card">
    <div class="news-date">04-23</div>
    <div class="news-title">新闻标题</div>
    <div class="news-source">来源</div>
  </div>
  <!-- 最多10条 -->
</div>
```

无新闻时：
```html
<div class="no-news">近一周无重大新闻公告</div>
```

### 交易建议

| 变量 | 说明 |
|------|------|
| `{{advice_class}}` | `strong-buy` / `buy` / `hold` / `sell` |
| `{{advice_summary}}` | 一句话建议摘要 |
| `{{entry_range}}` | 入场区间，含货币单位 |
| `{{stop_loss}}` | 止损位，含货币单位 |
| `{{target}}` | 目标位，含货币单位 |
| `{{position}}` | 仓位建议 |
| `{{holding_period}}` | 短（1-2周）/ 中（1-3月）/ 长（3月+） |
| `{{risk}}` | 风险提示，无则不输出 risk 区块 |

---

## 输出文件写入

完成所有数据填充后，将完整 HTML 写入：
```
{project}/stock_analysis_{股票代码}_{YYYYMMDD}.html
```

例如：`stock_analysis_sh600519_20260425.html`

同时终端输出完整报告文本供快速查看。

---

## 更新记录

- v2.0.0 (2026-04-26) — 重写为 HTML 报告，WeChat Article 风格
- v1.0.0 (2026-04-24) — 初始版本
