---
name: m-stock-scan
description: 美股市场扫描 — 批量分析多个美股标的，输出综合评级、买卖建议，并生成 WeChat Article 风格的 HTML 简报。
version: 2.1.0
author: Hermes Agent
tags: [us-stock, market-scan, batch-analysis, html-report, watchlist]
required_environment_variables: []
required_commands: []
---

# 美股市场扫描

对一批美股标的（最多 20 只）进行批量深度分析，汇总评级，买卖建议，生成 WeChat Article 风格的 HTML 简报。

---

## 输入

运行 skill 时通过 context 传入：
- 标的列表（ticker 格式）
- 可选：大盘基准（默认用 SPY/QQQ）
- 分析日期

---

## 分析流程

```
1. 数据获取
   - Step 1：并行 curl Yahoo Finance 行情数据（1日K线 + 60日K线）
   - Step 2：mcp__MiniMax__web_search 实时新闻（每个标的最多5条）

2. 技术指标计算（Python generate_html.py 自动完成）
   - MA / MACD / KDJ / 布林带
   - 综合评分（5维度110分制）

3. 汇总排名 + 生成 HTML
   - python3 generate_html.py
   - 输出：{project}/stock_report.html
```

---

## 数据获取

### Step 1：行情数据（并行 curl）

行情数据来自 Yahoo Finance（k线、技术指标），用 curl 并行拉取：

```bash
BASE="/Users/huangjicheng/go/src/github.com/market-scan/scan"
CODES="HOOD COIN TEM APLD CRWV VCX CRCL FLY"
for TICKER in $CODES; do
  curl -s --max-time 10 "https://query1.finance.yahoo.com/v8/finance/chart/${TICKER}?interval=1d&range=1d" \
    -H "User-Agent: Mozilla/5.0" -o "${BASE}/${TICKER}_1d.json" &
  curl -s --max-time 10 "https://query1.finance.yahoo.com/v8/finance/chart/${TICKER}?interval=1d&range=60d" \
    -H "User-Agent: Mozilla/5.0" -o "${BASE}/${TICKER}_60d.json" &
done
wait
# QQQ benchmark
curl -s --max-time 10 "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?interval=1d&range=1d" \
  -H "User-Agent: Mozilla/5.0" -o "${BASE}/QQQ_1d.json" &
curl -s --max-time 10 "https://query1.finance.yahoo.com/v8/finance/chart/QQQ?interval=1d&range=60d" \
  -H "User-Agent: Mozilla/5.0" -o "${BASE}/QQQ_60d.json" &
wait
```

### Step 2：实时新闻（MiniMax WebSearch MCP）

用 `mcp__MiniMax__web_search` 工具获取每个标的最新新闻（覆盖 Yahoo Finance 缓存的时效性不足问题）。

**重要：必须用 MCP 工具而非 curl**，因为 Yahoo Finance 新闻 API 会返回 403。

对每个 TICKER 执行以下 MCP 调用：

```
mcp__MiniMax__web_search(query="TICKER 股票 最新新闻")
```

每个标的最多取 5 条新闻，将结果转换为以下格式保存到 `{TICKER}_news.json`：

```json
{
  "news": [
    {
      "uuid": "唯一ID",
      "title": "新闻标题",
      "publisher": "媒体来源",
      "link": "https://...",
      "providerPublishTime": 毫秒时间戳,
      "type": "STORY"
    }
  ]
}
```

转换逻辑：
- `title`：直接取 WebSearch 结果的 `title` 字段
- `publisher`：从 `link` URL 提取域名作为 source
- `providerPublishTime`：将 WebSearch 结果的 `date` 字段（格式如 "2026-04-16"）转换为毫秒时间戳
- `uuid`：用 title 的 MD5 哈希生成

**示例**：对 HOOD 执行 `mcp__MiniMax__web_search(query="HOOD Robinhood SEC news 2026")`，把返回的 5 条新闻转换格式后写入 `HOOD_news.json`。对每个 TICKER 重复此步骤。

**搜索查询（每个 TICKER 执行 2 次 WebSearch）：**
- 英文：`mcp__MiniMax__web_search(query="TICKER stock latest news")`
- 中文：`mcp__MiniMax__web_search(query="TICKER 股票 最新新闻")`

**评分关键词（中英文，Python generate_html.py 中实现）：**
利好：`buy` `upgrade` `bull` `surge` `rally` `soar` `gain` `approval` `approved` `beat` `exceed` `catalyst` / `大涨` `上涨` `飙升` `暴涨` `回购` `利好` `改革` `取消` `批准` `受益` `催化`
利空：`sell` `downgrade` `crash` `warning` `lawsuit` `investigation` `fraud` `probe` `penalty` / `大跌` `下跌` `暴跌` `起诉` `调查` `罚款` `警告` `利空` `违规` `亏损`

---

## HTML 简报生成

分析完成后，将结果写入 `stock_report.html`（路径：`{project}/stock_report.html`）。

### 输出路径

```
{project}/stock_report.html
```

### HTML 模板

将以下模板复制到文件中，然后将所有 `{{VARIABLE}}` 替换为实际数据。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>美股市场扫描 · {{date}}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;600&display=swap');
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
.pick-score-num{font-family:var(--mono);font-size:20px;font-weight:700;color:var(--green);line-height:1}
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
.score-total{width:60px;height:60px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0}
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
}
</style>
</head>
<body>

<header class="pub-header">
  <div class="pub-brand"><span>·</span> 美股市场扫描</div>
  <div>
    <div class="pub-meta">{{date}} · {{count}} 只标的</div>
    <div class="pub-disclaimer">数据仅供参考，不构成投资建议</div>
  </div>
</header>

<section class="hero">
  <div class="hero-label">今日结论</div>
  <h1 class="hero-title">{{hero_title}}</h1>
  <p class="hero-sub">{{hero_sub}}</p>
  <div class="hero-picks">
{{hero_picks_html}}
  </div>
</section>

<section class="bench">
  <div>
    <div class="bench-name">{{benchmark_name}} ({{benchmark_ticker}})</div>
    <div class="bench-desc">{{benchmark_desc}}</div>
  </div>
  <div class="bench-stats">
    <div class="bench-stat"><div class="bench-stat-label">现价</div><div class="bench-stat-val">{{benchmark_price}}</div></div>
    <div class="bench-stat"><div class="bench-stat-label">今日</div><div class="bench-stat-val">{{benchmark_chg_d}}</div></div>
    <div class="bench-stat"><div class="bench-stat-label">60日涨跌</div><div class="bench-stat-val">{{benchmark_chg_60}}</div></div>
    <div class="bench-stat"><div class="bench-stat-label">52W高</div><div class="bench-stat-val">{{benchmark_high}}</div></div>
    <div class="bench-stat"><div class="bench-stat-label">52W低</div><div class="bench-stat-val">{{benchmark_low}}</div></div>
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
      <th>60日涨跌</th>
      <th class="hide-sm">52W位</th>
      <th class="action">建议</th>
    </tr>
  </thead>
  <tbody>
{{table_rows_html}}
  </tbody>
</table>

{{sector_hotspots_html}}

<footer class="footer">
  <p>美股市场扫描 · {{date}} · 共 {{count}} 只标的</p>
  <p class="disc">本报告仅供参考，不构成投资建议。投资有风险，决策需谨慎。</p>
</footer>

{{modals_html}}

<script>
function showDetail(code){
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
</html>
```

---

## HTML 模板变量说明

### 顶层变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `{{date}}` | 分析日期 | 2026-04-24 |
| `{{count}}` | 标的数量 | 8 |
| `{{hero_title}}` | 今日结论标题（一句市场判断） | 纳指走弱中，重点关注空天与加密板块 |
| `{{hero_sub}}` | 今日结论副标题（大盘一句话描述） | QQQ 今日 $178.50，60日涨跌 +2.3%，当前处于调整期 |
| `{{hero_picks_html}}` | Top 3 买入标的的 hero-pick HTML 片段 | 见下方 |
| `{{table_rows_html}}` | 完整排名表格的所有 tr 行 HTML | 见下方 |
| `{{sector_hotspots_html}}` | 板块热点 section HTML | 见下方 |
| `{{modals_html}}` | 所有个股弹窗 HTML | 见下方 |

### 大盘基准变量

| 变量 | 说明 |
|------|------|
| `{{benchmark_name}}` | 大盘名称，如"纳指100 ETF" |
| `{{benchmark_ticker}}` | 大盘 ticker，如"QQQ" |
| `{{benchmark_desc}}` | 描述，如"Invesco QQQ Trust · 大盘基准" |
| `{{benchmark_price}}` | 当前价格，如"$178.50" |
| `{{benchmark_chg_d}}` | 今日涨跌，如"+1.2%" |
| `{{benchmark_chg_60}}` | 60日涨跌，如"+5.3%" |
| `{{benchmark_high}}` | 52周高，如"$195.00" |
| `{{benchmark_low}}` | 52周低，如"$140.00" |

### Hero Picks（Top 3 买入标的）

从 ≥55 分的标的中取前 3，按总分降序。生成以下 HTML 片段（3 段拼接）：

```html
<div class="hero-pick" onclick="showDetail('TICKER')">
  <span class="pick-rank">#N</span>
  <div class="pick-info">
    <div class="pick-ticker">TICKER <small>公司全名</small></div>
    <div class="pick-reason">一句核心逻辑（从分析结果中提炼，最长40字）</div>
  </div>
  <div class="pick-score">
    <div class="pick-score-num">XX</div>
    <div class="pick-score-lbl">强烈买入/买入</div>
  </div>
</div>
```

### Table Rows（排名表格行）

每行生成一段 HTML（所有标的，拼接到一起）：

```html
<tr onclick="showDetail('TICKER')">
  <td class="rank">N</td>
  <td><div class="ticker">TICKER</div><div class="sname">公司全名</div></td>
  <td><span style="font-family:var(--mono);font-size:16px;font-weight:700;color:COLOR">XX</span><br><span class="badge badge-LEVEL">LABEL</span></td>
  <td class="hide-sm price">$XXX.XX</td>
  <td class="chg CHG_CLASS">▲/▼ XX.XX%</td>
  <td class="hide-sm pos52">XX%</td>
  <td class="action">交易建议（最核心的一句）</td>
</tr>
```

颜色规则：
- score >= 75：`var(--green)`
- score >= 55：`var(--green)`
- score >= 40：`#9a7a2e`
- score < 40：`var(--red)`

涨跌方向：上涨用 `▲` + `chg-up`，下跌用 `▼` + `chg-dn`

### 板块热点（Sector Hotspots）

从分析结果中归纳 3-4 个板块，拼接以下 HTML：

```html
<div class="section-hdr" style="margin-top:8px">板块热点</div>
<div class="sectors">
  <div class="sector-card">
    <div class="sector-icon">🚀</div>
    <div class="sector-body">
      <div class="sector-name">板块名</div>
      <div class="sector-desc">一句话板块判断，最长60字</div>
    </div>
  </div>
  <!-- 更多板块 -->
</div>
```

板块 icon 用对应 emoji：空天→🚀，加密→₿，AI算力→⚡，AI医疗→🏥，金融→🏦，消费→🛒，能源→⛽，工业→⚙️

### Modal（个股详情弹窗）

每个标的生成一个完整弹窗，拼接到 `{{modals_html}}`。

**头部颜色规则：**
- `score >= 75`：默认 `--ink` 背景
- `score >= 55`：默认 `--ink` 背景
- `score >= 40`：默认 `--ink` 背景
- `score < 40` 或 强烈卖出建议：背景 `#8b2525`（深红）

**Badge 样式：**
- score >= 75：`badge badge-strong`，"强烈买入"
- score >= 55：`badge badge-buy`，"买入"
- score >= 40：`badge badge-hold`，"持有"
- score < 40：`badge badge-sell`，"卖出"

**评分圆环颜色：**
- score >= 75：`var(--green)`
- score >= 55：`var(--gold)`
- score >= 40：`var(--gold)`
- score < 40：`var(--red)`

**技术指标表格 N/A 处理（重要）：**
- 有数据的行正常显示
- MA 全部无数据时：`<tr><td class='lbl'>MA5 · MA10 · MA20 · MA60</td><td class='val na-val'>— (历史数据不足)</td></tr>`
- MACD 无数据时：`<tr><td class='lbl'>MACD</td><td class='val na-val'>— (历史数据不足)</td></tr>`
- 布林带无数据时：`<tr><td class='lbl'>布林带</td><td class='val na-val'>— (历史数据不足)</td></tr>`
- 注意：只展示有实际值的行，不要留下 N/A 原文

**评分条颜色（5维度）：**
- 技术面：`#aaa`（历史数据不足）
- 基本面：`#5b9bd5`
- 板块：`var(--green)`
- 机构评级：`var(--gold)`
- 消息面：`var(--green)`（利好）或 `var(--red)`（利空）

**建议框样式：**
- 强烈买入（>=75）：`advice-box strong-buy`
- 卖出建议（<40 或明确卖出）：`advice-box sell`
- 其他：`advice-box`

每只股票的 modal 结构：
```html
<div class="m-overlay" id="modal-TICKER" onclick="closeModal(event,'TICKER')">
<div class="m-content" onclick="event.stopPropagation()">
  <button class="m-close" onclick="hideModal('TICKER')">✕</button>
  <div class="m-header">
    <div class="m-title-row">
      <div><h2 class="m-code">TICKER</h2><p class="m-name">公司全名</p></div>
      <span class="m-badge badge-BADGE">LABEL XX/110</span>
    </div>
    <div class="m-price-row">
      <span class="m-price">$XXX.XX</span>
      <div class="m-chg">
        <span class="chg-pill chg-pill-up">▲ 今日 +X.XX%</span>
        <span class="chg-pill chg-pill-up">▲ 60日 +XX.XX%</span>
      </div>
    </div>
  </div>
  <div class="m-body">
    <!-- 评分条 -->
    <div class="score-section">
      <div class="score-total" style="background:COLOR">XX<span class="score-denom">/110</span></div>
      <div class="score-bars">
        <div class="score-row"><span class="score-label">技术面</span><div class="score-track"><div class="score-fill" style="width:XX%;background:#aaa"></div></div><span class="score-val" style="color:#aaa">XX/30</span></div>
        <div class="score-row"><span class="score-label">基本面</span><div class="score-track"><div class="score-fill" style="width:XX%;background:#5b9bd5"></div></div><span class="score-val" style="color:#5b9bd5">XX/40</span></div>
        <div class="score-row"><span class="score-label">板块</span><div class="score-track"><div class="score-fill" style="width:XX%;background:var(--green)"></div></div><span class="score-val" style="color:var(--green)">XX/20</span></div>
        <div class="score-row"><span class="score-label">机构评级</span><div class="score-track"><div class="score-fill" style="width:XX%;background:var(--gold)"></div></div><span class="score-val" style="color:var(--gold)">XX/10</span></div>
        <div class="score-row"><span class="score-label">消息面</span><div class="score-track"><div class="score-fill" style="width:XX%;background:COLOR"></div></div><span class="score-val" style="color:COLOR">XX/10</span></div>
      </div>
    </div>

    <h3 class="section-title">技术面指标</h3>
    <table class="tech-table">
      <tr><td class="lbl">现价</td><td class="val">$XXX.XX</td></tr>
      <tr><td class="lbl">60日涨跌</td><td class="val VAL_CLASS">▲/▼XX.XX%</td></tr>
      <tr><td class="lbl">52W高 / 低</td><td class="val">$XXX.XX / $XXX.XX</td></tr>
      <tr><td class="lbl">52W位置</td><td class="val">XX%</td></tr>
      <tr><td class="lbl">成交量比</td><td class="val">X.Xx <span style="color:var(--muted);font-size:10px">(近20日均量)</span></td></tr>
      <tr><td class="lbl">KDJ/K · D · J</td><td class="val">XX.X · XX.X · XX.X <span class="note">超买/超卖</span></td></tr>
      <!-- MA 行（无数据时合并显示）-->
      <!-- MACD 行（无数据时显示灰色）-->
      <!-- 布林带行（无数据时显示灰色）-->
      <tr><td class="lbl">近10日缺口</td><td class="val">描述或"无明显缺口"</td></tr>
    </table>

    <h3 class="section-title">最新新闻</h3>
    <div class="news-list">
      <div class="news-item"><span class="news-title">新闻标题</span><span class="news-meta">MM-DD · 来源</span></div>
      <!-- 最多5条新闻 -->
    </div>

    <h3 class="section-title">交易建议</h3>
    <div class="advice-box ADVICE_CLASS">建议文本</div>
  </div>
</div>
</div>
```

---

## 输出文件写入

完成所有数据填充后，将完整 HTML 写入：
```
{project}/stock_report.html
```

---

## 局限性

- 批量分析每只股票只取 5 条新闻（避免 token 爆炸）
- 财报数据（营收/利润增速）无法通过 Yahoo API 获取时，用行业常识估算
- 不含期权/期货数据，纯股票基本面+技术面分析
- 建议配合大盘环境（SPY/QQQ）综合判断
- MA/MACD/布林带依赖60日历史数据，新股或流动性差的标的可能数据不足

---

## 更新记录

- v2.1.0 (2026-04-26) — 中英文双语新闻搜索（MiniMax WebSearch），中英文评分关键词，修复中文新闻无法识别利好/利空的问题
- v2.0.0 (2026-04-25) — 重写为 HTML 简报生成，WeChat Article 风格，结论优先架构
- v1.0.0 (2026-04-24) — 初始版本
