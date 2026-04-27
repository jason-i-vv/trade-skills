---
name: a-stock-scan
description: A股个股扫描 — 批量分析多个 A 股标的，输出综合评级、买卖建议，并生成 WeChat Article 风格的 HTML 简报。
version: 1.0.0
author: Hermes Agent
tags: [a-stock, market-scan, batch-analysis, html-report, watchlist]
required_environment_variables: []
required_commands: []
---

# A股个股扫描

对一批 A 股标的（最多 20 只）进行批量深度分析，汇总评级，买卖建议，生成 WeChat Article 风格的 HTML 简报。

---

## 输入

运行 skill 时通过 context 传入：
- 标的列表（股票名称，支持：贵州茅台、中科电气、拓维信息、品高软件 等）
- 可选：大盘基准（默认用沪深300 / 上证指数）
- 分析日期

---

## 分析流程

```
1. 数据获取
   - Step 1：并行 curl 腾讯行情（实时报价）+ QQ 财经（日K线）
   - Step 2：搜索新闻（MiniMax WebSearch，每个标的最多5条，7天内）

2. 技术指标计算（Python generate_html.py 自动完成）
   - MA / MACD / KDJ / 布林带 / 量价分析
   - 综合评分（5维度110分制）

3. 汇总排名 + 生成 HTML
   - python3 generate_html.py
   - 输出：{OUTPUT_DIR}/a_stock_scan_YYYY-MM-DD_NNN.html
```

---

## 数据获取

### Step 1：行情数据（并行 curl）

股票名称到腾讯代码的映射：
- 深交所股票（sz）: `sz + 6位代码`（如中科电气 → sz300035）
- 上交所股票（sh）: `sh + 6位代码`（如贵州茅台 → sh600519）
- 创业板（sz）: `sz + 6位代码`（如拓维信息 → sz002261）
- 科创板（sh）: `sh + 6位代码`（如品高软件 → sh688382）

```bash
# 腾讯实时行情
curl -s --max-time 10 "https://qt.gtimg.cn/q=sz300035,sz002261,sh600519,sh688382" | iconv -f gbk -t utf-8

# QQ 财经日K线（60日）
curl -s --max-time 10 "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=sz300035,day,,,60,qfq" | iconv -f gbk -t utf-8
```

### Step 2：新闻搜索

```bash
# MiniMax WebSearch（每个标的）
mcp__MiniMax__web_search(query="中科电气 股票 最新新闻 2026")
```

---

## A股个股评分体系（110分）

| 维度 | 满分 | 说明 |
|------|------|------|
| 技术面 | 30 | MA多头排列、MACD金叉/死叉、KDJ超买超卖、量价配合 |
| 基本面 | 40 | PE/PB合理区间、净利润增速、营收增长 |
| 板块热度 | 20 | 所属板块涨跌、主力资金流向 |
| 机构评级 | 10 | 研报覆盖、目标价空间 |
| 消息面 | 10 | 7天内新闻数量、正负面 |

---

## 评级定义

- **强烈推荐（85+）**：技术+基本面+板块共振，上涨概率高
- **推荐（70-84）**：多个维度向好，可择机介入
- **中性（50-69）**：无明显方向，等待确认
- **回避（<50）**：技术破位或基本面恶化

---

## 输出格式

```
=== A股个股扫描 ===  [日期]

【扫描标的】（共 N 只）
  序号 | 名称 | 代码 | 现价 | 涨跌幅 | 综合评分 | 评级 | 建议

【技术亮点】
  - MA 多头排列标的
  - MACD 金叉标的
  - 放量突破标的

【操作建议】
  重点关注 / 谨慎介入 / 回避

Generated: {OUTPUT_DIR}/a_stock_scan_YYYY-MM-DD_NNN.html
```

---

## 股票名称映射表（常用标的）

| 股票名称 | 交易所 | 代码 |
|----------|--------|------|
| 中科电气 | 深圳(创业板) | sz300035 |
| 拓维信息 | 深圳(中小板) | sz002261 |
| 品高软件 | 上海(科创板) | sh688382 |
| 贵州茅台 | 上海 | sh600519 |
| 宁德时代 | 深圳(创业板) | sz300750 |
| 比亚迪 | 深圳 | sz002594 |
| 中国平安 | 上海 | sh601318 |
| 中芯国际 | 上海(科创板) | sh688981 |

如遇未知股票，根据名称自动搜索判断交易所。

---

## 输出：写入本地文件

分析完成后，写入本地 HTML 文件：
- 路径：`/home/ubuntu/market-scan/a_stock_scan_YYYY-MM-DD_NNN.html`
- 支持通过 `sys.argv[1]` 指定其他目录
- URL：`http://150.109.233.168/reports/a_stock_scan_YYYY-MM-DD_NNN.html`
