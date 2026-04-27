---
name: trade-check
description: Trend-following trade checker for Bybit — 顺大逆小 (follow the major trend, fade the minor pullback). Validates entries against trend, formation, signal, and risk before execution.
version: 1.0.0
author: Hermes Agent
tags: [bybit, trading, trend-following, technical-analysis, trade-check]
---

# Trade Check — 趋势回调交易校验

Evaluates whether a potential trade on Bybit aligns with the 顺大逆小 (follow the major, fade the minor) trend-following system.

## Core Philosophy

- **顺大** — Only trade in the direction of the major trend (higher timeframe)
- **逆小** — Enter on minor pullbacks/reversals against the micro structure
- **三合一** — Trend + Formation + Signal must ALL agree before entry

## When to Use

- User describes a potential trade (symbol, direction, entry zone)
- User asks "能不能做多/做空" or "可以进吗"
- User shares a chart or price level and asks for an opinion
- User wants pre-trade validation before placing an order on Bybit

## Evaluation Framework

### 1. 趋势 (Trend) — 大方向确认

Determine the higher-timeframe trend direction:
- **多頭趋势** — Price above key moving averages (MA50, MA200 on 4H/Daily)
- **空頭趋势** — Price below key moving averages
- **震荡** — No clear trend, warn that 顺大 is ambiguous

Tools: Bybit public API (klines), or user-provided chart/description.

### 2. 形态 (Formation) — 回调/整合结构

Identify the pullback or consolidation formation:
- **回调形态**: 旗形、三角形、楔形、矩形回调
- **入场形态**: 吞没、锤子线、Pin Bar、inside bar
- **危险形态**: V形反转、过大幅度延伸、无量突破

Rule: 逆小 means we want a clean pullback WITHIN the major trend, NOT a trend reversal.

### 3. 信号 (Signal) — 触发确认

Confirm with at least one clear signal:
- 价格行为信号 (price action): 支撑阻力反弹、突破量能
- 指标信号: RSI超卖/超买区反转、MACD背离、成交量收缩
- 订单结构: Order block、FVG、流动性扫描

### 4. 风控 (Risk) — 仓位与止损

- 止损设置: 须在关键结构外 (前高/低、MA200 ±1-2%)
- 盈亏比: 至少 1:1.5 以上，低于 1:1.2 建议放弃
- 仓位: 根据止损距离和账户风险承受计算
- 最大单笔风险: 不超过账户 1-2%

### 5. 综合评分 (Overall)

给出 0-100 的综合评分：

| 评分 | 信号 |
|------|------|
| 80-100 | 强烈做多/空，三合一完整，符合所有规则 |
| 60-79 | 可以做，略有瑕疵，需注意关键位 |
| 40-59 | 观望，矛盾信号较多，勉强可做 |
| 0-39 | 放弃，不符合系统，逆势或形态不清晰 |

## Workflow

1. **收集信息** — 交易对、时间框架、方向、入场区间、止损区间
2. **趋势判断** — 确认大方向是否符合
3. **形态分析** — 回调/整合是否清晰
4. **信号确认** — 触发条件是否存在
5. **风控评估** — 止损/止盈/仓位是否合理
6. **输出结论** — 评分 + 理由 + 操作建议

## Bybit API Integration

Use Bybit public API for market data (no auth required for read-only):

```
Klines:  GET https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=4H&limit=200
Tickers: GET https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT
```

## Output Format

```
=== 交易校验报告 ===

交易对:     BTCUSDT
方向:       做多 / 做空
时间框架:   4H
入场区间:   95,000 - 96,000
止损:       93,500
止盈:       101,000

【趋势】     ✅ 多头 (4H MA50 > MA200, 日线上升趋势)
【形态】     ✅ 旗形回调，回调至趋势线支撑
【信号】     ✅ RSI 背离 + 吞没形态
【风控】     ⚠️  盈亏比 1.4:1，偏低，建议观望

综合评分:   68/100
结论:       可以做，但盈亏比一般，建议轻仓或放弃
建议操作:   等待回调至 95,500 确认支撑后入场，止损放 94,000
```

## Limitations

- This skill provides analysis and recommendations only, not financial advice
- Always respect your own risk management rules
- Market conditions can change rapidly; re-check before execution
- No guaranteed outcomes — all trades carry risk
