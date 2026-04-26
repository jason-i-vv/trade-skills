---
name: a-stock-base
description: A 股大盘实时分析 — 走势技术面、资金板块、时政要闻。服务于每日操盘决策。
version: 1.2.0
author: Hermes Agent
tags: [a-stock, china, intraday-analysis, sector-flow, news]
required_environment_variables: []
required_commands: []
feishu_doc:
  folder_token: "KeLbfwxltlvdikdLpUic5Zadnuh"   # market-scan 共享文件夹
  chat_id: "oc_053b511bbc1130d1a7011cd0839b965b" # 报告推送群
---

# A 股大盘实时分析

专注于 A 股每日操盘决策支持，聚焦三个核心维度：**大盘走势+技术面+资金**、**一周内重要时政**、**板块资金流向（昨日热/冷板块）**。

---

## 核心分析维度

### 维度一：大盘走势、技术面、资金

**数据获取（腾讯/QQ行情API）:**

```bash
# 1. 即时行情快照
curl -s --max-time 10 "https://qt.gtimg.cn/q=s_sh000001,s_sz399001,s_sz399006,s_sh000300,s_sh000016,s_sh000905" | iconv -f gbk -t utf-8

# 2. K线数据（近20日）
curl -s --max-time 10 "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=sh000001,day,,,20,qfq" | iconv -f gbk -t utf-8
```

**即时行情字段说明（字段~分隔）:**
- 字段3 = 当前价格
- 字段4 = 昨收
- 字段31 = 涨跌额
- 字段32 = 涨跌幅%
- 字段33 = 最高
- 字段34 = 最低
- 字段36 = 成交量(股)
- 字段37 = 成交额(元)
- 字段39 = PE
- 字段46 = PB

**技术面分析要点:**
- 短期: 5日线、10日线、20日线排列与交叉
- 中期: 布林中轨支撑/压力
- 量能: 放量突破/滞涨、缩量回调的判断
- K线形态: 上影线、下影线、吞没、十字星

**关键支撑压力位计算:**
```
上证: 5日线=?, 10日线=?, 20日线=?
布林上轨 = 中轨 + 2*标准差
布林下轨 = 中轨 - 2*标准差
```

---

### 维度二：一周内重要时政

**数据获取（新浪财经快讯API）:**

```bash
# 新浪财经快讯（宏观/政策/国际市场）
curl -s --max-time 10 -H "User-Agent: Mozilla/5.0" \
  -H "Referer: https://finance.sina.com.cn/" \
  "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=20&page=1"

# 东方财富宏观政策
curl -s --max-time 10 -H "User-Agent: Mozilla/5.0" \
  "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html"
```

**新闻过滤逻辑（Python）:**
```python
from datetime import datetime, timedelta
import re, json

# 新浪API返回JSON，取result.data，筛选最近7天(ctime > now-7days)
# 按ctime倒序，按日期分组输出
# 重点关注: 政策转向、地缘事件、汇率、重要数据发布
```

**重点跟踪新闻类型（按重要性排序）:**
1. 宏观政策（央行、财政部、发改委）— 直接影响货币+信用
2. 地缘政治（中美关系、中东、霍尔木兹）— 影响风险偏好+能源
3. 汇率（USD/CNY 7.3关口）— 影响外资流向
4. 重要经济数据（PMI、PPI、CPI、社融）
5. 证监会动态（IPO节奏、减持新规、两融风险提示）

---

### 维度三：板块资金流向（昨日热/冷板块）

**数据获取（新浪概念+行业板块API）:**

```bash
# 概念板块资金流向（GBK编码）
curl -s --max-time 15 \
  -H "User-Agent: Mozilla/5.0" \
  -H "Referer: https://finance.sina.com.cn/" \
  "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class" | iconv -f gbk -t utf-8

# 行业板块资金流向
curl -s --max-time 15 \
  -H "User-Agent: Mozilla/5.0" \
  -H "Referer: https://finance.sina.com.cn/" \
  "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=industry" | iconv -f gbk -t utf-8
```

**板块数据解析:**
```
字段[1] = 板块名称
字段[4] = 涨跌幅%
字段[5] = 资金净流入(万元)，正=流入，负=流出
字段[6] = 成交量(股)
字段[7] = 成交额(元)
字段[12] = 代表股
```

**板块分析逻辑:**
- 热板块 = 涨幅排行前10 + 资金净流入前10（有资金主动拉升）
- 冷板块 = 跌幅前10 + 资金净流出前10（资金主动撤离）
- 关注资金和涨跌方向不一致的板块（逆势流入/流出）

**注意:** 新浪数据为T-1日（昨日收盘后更新），盘中只能看前一交易日数据。

---

## 报告模板

每次分析按以下格式输出（无Markdown，纯文本）:

```
=== A 股大盘分析 ===  [日期 时间]

【一、大盘走势 + 技术面 + 资金】
上证: ???  涨跌?%  成交???亿(半日/全天预估)
沪深300: ???  创业板: ???  上证50: ???

K线回顾（近5日）:
  日期  开盘  收盘  最高  最低  成交量  涨跌幅

技术面:
  5日线??? / 10日线??? / 20日线???
  布林轨道: 上轨??? 中轨??? 下轨???
  关键支撑: ???  关键压力: ???

资金定性:（北向/两融/ETF定性方向）

【二、近一周重要时政】  [重点标注]
=== 04-24 ===
  · [时政标题]
=== 04-23 ===
  · [时政标题]
...

【三、昨日板块资金流向】

  最热板块（资金流入+涨幅共振）:
  1. ???  涨幅?%  净流入?亿  代表股:???
  ...

  最冷板块（资金流出+跌幅共振）:
  1. ???  涨幅?%  净流出?亿  代表股:???
  ...

  异动板块（涨跌与资金流向背离）:
  · ???  涨幅?%  但资金净流出?亿  ← 为何背离?

综合结论:
  短线: ???（方向+关键点位）
  中线: ???（方向+逻辑）
  操作建议: 仓位? 回避? 关注?
```

---

## 数据源速查

| 数据 | 来源 | 地址 | 更新频率 |
|------|------|------|----------|
| 即时行情 | 腾讯行情 | `qt.gtimg.cn` | 实时 |
| 日K线 | QQ财经 | `web.ifzq.gtimg.cn` | 盘中/收盘 |
| 板块资金 | 新浪财经 | `vip.stock.finance.sina.com.cn` | T+1收盘后 |
| 时政新闻 | 新浪快讯 | `feed.mix.sina.com.cn` (lid=2516) | 实时 |
| 宏观政策 | 东方财富 | `newsapi.eastmoney.com` (kuaixun) | 实时 |

## 关键标尺（经验值）

| 现象 | 信号含义 |
|------|----------|
| 放量长阳+突破关键位 | 短线启动信号 |
| 缩量上涨/高位十字星 | 短线顶部预警 |
| 放量滞涨（上影线） | 主力出货嫌疑 |
| 北向持续净流入+指数上涨 | 外资驱动，可跟进 |
| 两融余额快速攀升 | 杠杆资金疯狂，离顶不远 |
| 涨停家数逐周递减 | 情绪降温，持币观望 |
| 板块内个股普涨+龙头未涨停 | 补涨行情，热度接近尾声 |

## 输出：写入飞书

分析完成后，写入飞书文档并推送群通知。调用 `feishu-doc` skill：

```
Skill: feishu-doc
1. 获取 tenant_access_token
2. 在 folder_token=KeLbfwxltlvdikdLpUic5Zadnuh 创建文档
3. 分批写入内容（每批≤50块）
4. 发群通知到 chat_id=oc_053b511bbc1130d1a7011cd0839b965b
5. 本地同步备份到 /home/ubuntu/market-scan/
```

飞书文档链接格式：`https://qcnl509g8z28.feishu.cn/docx/{document_id}`

---

## 局限性

- 新浪板块数据为T-1日，盘中只能定性判断
- 腾讯/QQ行情无资金流向字段，需结合板块数据
- 新闻需人工过滤优先级，系统无法自动判断重要性
- 地缘政治事件无法预测，可能瞬间改变市场方向
