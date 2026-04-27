# A-Share Main-Rise Low-Buy System

This reference extends Elliott Wave analysis with an A-share chart framework for judging 主升浪 / 主升低吸 opportunities. It was distilled from confirmed main-rise K-line screenshots and a local manual library.

Use this file when the user asks:

- "处于第几浪 / 什么阶段 / 是否主升"
- "什么时候走主升浪"
- "关键高低点是什么"
- "如果要买，什么点买"
- Gives only a stock code or daily chart screenshot and expects stage judgment

## Core Structure

Main-rise low-buy structure:

```text
0号启动点 -> 一高 -> 1号低点 -> 二高/试盘 -> 2号低点 -> 买点 -> 主升加速
```

## Final Main-Rise Low-Buy Model

This is the highest-priority model for future stock-code analysis:

```text
0点 -> 最高/一高 -> 1点 -> 次高/二高 -> 2点 -> 主升段突破次高 -> 回踩操盘线买点
```

Mandatory position relationships:

- `最高/一高 > 次高/二高`.
- `2点 > 1点`.
- The preferred `主升段` after 2点 should rise above `次高/二高`.

Interpretation:

- Highs are descending before confirmation: 一高 is the highest high, 二高 is the lower secondary high.
- Lows are rising before the buy point: 2点 must be higher than 1点.
- This is a head-and-shoulders / right-shoulder reversal model: 1点 and 2点 are shoulder lows, and 二高/次高 is the confirmation high.
- The strongest buy setup is not at 二高. It appears after 2点 turns upward, price forms a 主升段 above 次高, and then pulls back to the operating line with a valid buy candle.

Decision priority:

- If `最高 <= 次高`, relabel 次高 as the new 一高 and restart the count.
- If `2点 <= 1点`, relabel 2点 as the new 1点 and wait for a fresh higher 2点.
- If `主升段 <= 次高`, the pattern is only a tracking setup; do not call it a preferred buy.
- If `主升段 > 次高`, wait for the first valid operating-line pullback as the preferred buy point.

## High-Point Relabeling Rule

This rule is mandatory for labeling the structure:

- 一高 uses closing price, not intraday highest price.
- 一高 must be confirmed by 二高.
- 二高 must not be higher than 一高.
- If the proposed 二高 is higher than 一高, it is no longer 二高; relabel it as the new 一高.
- After relabeling, restart the count from that new 一高 and wait for the next 1号低点, 二高, 2号低点, and buy point.
- A 二高 is a test near the previous high, not a confirmed new high.
- If 二高 does not exceed 一高, 一高 is confirmed and the main-force accumulation phase is considered complete.
- If price breaks above 一高 after 2号点 and buy point are already confirmed, that is main-rise confirmation, not a relabeling of the old 二高.

Practical judgment:

- Prefer using closing price to confirm whether a high is effective.
- If only an intraday wick slightly pierces 一高 and the close falls back below it, treat it as a pressure test and require the next sessions to confirm.
- If the close clearly exceeds 一高, relabel it as the new 一高.

## Low-Point Confirmation Rule

This is the head-and-shoulders / right-shoulder confirmation logic of the framework:

- 1号低点 must be confirmed by 2号低点.
- 2号低点 should be higher than 1号低点. This confirms rising lows and the right-shoulder structure.
- If the proposed 2号低点 is lower than 1号低点, the old 1号低点 is invalid; relabel the lower 2号低点 as the new 1号低点.
- After relabeling, wait for price to recover near 二高, then pull back again. The next pullback low must be higher than the new 1号低点 to become a valid 2号低点.
- The system gives 1号低点 only one breakdown/relabeling chance. If price keeps breaking down after the relabel, declare the structure failed.

Head-and-shoulders interpretation:

- 0号启动点 is the base/start of reversal.
- 一高 and 二高 act like neckline/test highs; 二高 confirms 一高 only when it does not exceed 一高.
- 1号低点 and 2号低点 form the left/right shoulder lows.
- A higher 2号低点 is the right shoulder; the buy point appears after that right shoulder stabilizes and price turns up.
- Preferred confirmation occurs when the 主升段 after 2号点 rises above 二高/次高, then pulls back to the operating line.

Elliott mapping:

- `0号启动点 -> 一高`: first reversal leg, often wave 1 or smaller-degree i wave.
- `一高 -> 1号低点`: wash/correction, often wave 2; it must not break 0号点.
- `1号低点 -> 二高`: test/confirmation leg, often the first sign of wave 3 preparation.
- `二高 -> 2号低点`: final low-buy pullback before the main-rise; often small wave 2 before acceleration.
- `2号点后突破/沿操盘线上行`: likely wave 3 / main-rise confirmation.

Do not force Elliott labels. If price action violates impulse rules, describe it as corrective rebound, range, or failed structure.

## Phase Judgment

### 1. 建仓 / 一涨

Required evidence:

- Clear bottom or 0号启动点.
- Strong reversal from the bottom.
- Prefer big bullish candle, limit-up, gap, or consecutive bullish candles.
- Volume or capital consensus improves.
- Price reclaims the operating line / key moving averages.

Weak evidence:

- Small rebound still under a falling trend.
- No volume, no capital confirmation.
- Immediate retracement back into the old range.

### 2. 洗盘 / 二回

Required evidence:

- Pullback does not break 0号启动点.
- Better if volume contracts on the pullback.
- No limit-down or repeated large bearish candles.
- 1号低点 is visible.
- Pullback stabilizes near operating line, platform, neckline, or MA cluster.

Failure signs:

- Heavy-volume decline.
- Breaks 0号点 or important structure low.
- Rebound volume is weak while decline volume is strong.

### 3. 试盘 / 二高

Required evidence:

- 二高 approaches 一高 / prior high / platform resistance, but must not be higher than 一高.
- If the proposed 二高 exceeds 一高, relabel it as the new 一高 and restart the structure count.
- Better with volume expansion, big bullish candle, or limit-up.
- Main-force/capital signal remains positive.
- After the test, price does not collapse with heavy selling.

Failure signs:

- 二高 is far below previous resistance.
- Proposed 二高 exceeds 一高 but the analyst still labels it as 二高; this is a counting error.
- Breakout has no volume.
- Breakout is followed by heavy-volume long upper shadow or sharp selloff.

### 4. 2号点确认

Required evidence:

- 2号低点 must be higher than 1号低点 for direct confirmation.
- If 2号低点 is lower than 1号低点, relabel 2号低点 as the new 1号低点 and wait for a fresh higher-low 2号点.
- Price does not stay below the operating line for long.
- Key platform/neckline support remains valid.
- Stop-fall candle appears: bullish candle, doji, or small controlled candle.

Failure signs:

- Breaks 2号点.
- Breaks the relabeled new 1号低点 again; this means the structure failed.
- Breaks operating line on close and cannot recover quickly.
- Large bearish candles appear during supposed low-buy zone.

### 5. 主升确认

Strong confirmation:

- Price breaks 二高/次高 / platform / neckline with volume.
- Preferred model: 主升段 after 2号点 rises above 二高/次高.
- Pullback after breakout does not break support.
- Moving averages turn upward and begin bullish alignment.
- MACD green bars shrink or red bars expand; DIF/DEA trend upward.
- Sector and market do not drag the stock down.

Weak confirmation:

- Breaks resistance but volume is insufficient.
- Only individual strength, no sector support.
- Breakout repeatedly fails at the same price band.

## Pattern Types

### Type A: Relabel Then Reconfirm

```text
0号点 -> 一高 -> early low -> 二高 -> lower low becomes new 1号低点 -> rebound near 二高 -> higher 2号低点 -> 买点
```

Use this when the second adjustment low breaks the first low. The first low is invalid, the lower low becomes the new 1号低点, and the analyst must wait for one more rebound near 二高 plus a higher pullback low. This is slower but still valid if the next low rises.

### Type B: Direct Higher-Low Confirmation

```text
0号点 -> 一高 -> 1号低点 -> 二高(不高于一高) -> 2号低点(高于1号低点) -> 买点
```

This is the cleaner structure: 2号低点 directly holds above 1号低点, forming rising lows and a right shoulder. It usually has higher priority than Type A.

## Buy Point Standard

The buy point appears only after the model is valid and 2号点 has reversed. Structure confirmation means "enter buy-point watch"; the actual buy trigger must still satisfy the operating-line and candle rules.

Mandatory setup:

- The stock already satisfies the selection structure: valid 一高/二高, valid 1号低点/2号低点, and no relabeling rule is currently unresolved.
- Final model relationships hold: 最高/一高 > 次高/二高 and 2点 > 1点.
- 2号点 has turned upward or stabilized.
- Preferred: the 主升段 after 2号点 has risen above 次高/二高.
- Price pulls back to the operating line, or touches the operating line intraday.
- If price is below/near the operating line intraday, it should stand back above the operating line near the close.

Valid buy candle:

- Bullish candle.
- Doji / cross star.
- Small controlled candle that holds the operating line.
- Late-session confirmation around 14:30-15:00 is preferred.

Invalid buy candle:

- Consecutive bearish candles.
- Large bearish candle.
- Weak close below the operating line.
- Price breaks 2号点.

Preferred low-buy:

- Strongest version: 主升段 > 次高/二高, then first pullback to the operating line prints a bullish candle or doji.
- 2号点 confirmed, then price retraces to the operating line and prints a bullish candle or doji.
- Price touches the operating line intraday and recovers before the close.
- Price stands above the operating line near the close after a controlled pullback.
- Volume expands on renewed attack after the valid buy candle.

Avoid buying:

- Big bearish candle or consecutive bearish candles.
- Chasing immediately after a large breakout.
- Price breaks 2号点.
- Price closes below the operating line and fails to recover.
- Sector is fading or market index is breaking down.

Special note:

- If price touches the operating line intraday but closes weak, wait.
- If price dips below the operating line but quickly reclaims it and does not break 2号点, it can still become a valid low-buy setup.
- If the chart does not show a clear operating line, state that the buy standard is not fully confirmable from the image; use any proxy line only when explicitly declared.

## Invalidation and Risk

Hard invalidation:

- Breaks 2号低点.
- Closes below operating line and cannot reclaim within 1-2 sessions.
- Heavy-volume breakdown of platform or neckline.
- 二高 breakout fails and turns into consecutive selloff.

Risk controls:

- Always name the invalidation level.
- Separate "tracking setup" from "confirmed buy point".
- If market is weak, lower position size and require Type A confirmation.
- If market and sector are strong, Type B may be acceptable but still needs a clear stop.

## Market and Sector Filter

Always judge from large to small:

```text
Market index -> sector/theme -> individual stock structure -> buy point
```

Favorable:

- Market index holds trend or recovers key support.
- Sector has multiple stocks breaking out.
- The stock is not isolated strength.

Unfavorable:

- Market index breaks trend support.
- Sector is fading.
- Individual stock breaks out alone and fails to attract follow-through.

## Scoring Model

Use this 100-point framework for stock-code or screenshot analysis:

| Dimension | Points | Criteria |
| --- | ---: | --- |
| Structure | 25 | 0-一高-1低-二高-2低 is clear; 二高不高于一高; lows rise |
| First-leg strength | 15 | Big bullish candle, limit-up, gap, consecutive bullish candles |
| Pullback quality | 15 | Contracting volume, no large bearish damage, holds support |
| Capital/volume consensus | 20 | Volume inflow, MACD improvement, red bars expand |
| Moving averages | 10 | MA cluster turns up, price above key MAs |
| Market/sector | 10 | Index and sector support the setup |
| Buy discipline | 5 | Low-buy near support, not chasing |

Interpretation:

- `80+`: strong main-rise candidate; wait for or act only at system buy point.
- `65-79`: trackable; needs buy point or capital confirmation.
- `50-64`: may be rebound/test; do not heavy-position.
- `<50`: main-rise evidence insufficient.

## Standard Output Template

For A-share stock analysis, answer in this shape:

```text
1. 当前阶段：
   建仓 / 洗盘 / 试盘 / 2号点确认 / 主升初期 / 主升中后段 / 失败结构

2. 关键高低点：
   0号点：
   一高：
   1号低点：
   二高：
   2号低点：
   当前价：

3. 波浪定位：
   当前可能处于：
   替代计数：
   失效条件：

4. 主升条件：
   已满足：
   未满足：

5. 买点与风控：
   低吸买点：
   突破确认买点：
   不买条件：
   止损/失效位：

6. 综合评分与结论：
   主升评分：
   操作倾向：
```

## Language Discipline

- Say "更像/倾向于/需要确认", not "一定/必然".
- Distinguish confirmed structure from tracking setup.
- Do not give isolated buy advice without invalidation and market/sector context.
- If chart data is incomplete, state the missing data and give conditional judgment.
