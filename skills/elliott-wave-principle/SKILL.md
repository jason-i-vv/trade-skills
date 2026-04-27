---
name: elliott-wave-principle
description: Use when the user asks about Elliott Wave counts, impulse/corrective waves, Fibonacci targets, or A-share K-line main-rise/主升低吸 analysis from stock codes or chart screenshots, including 0号点、一高、1低、二高、2低, phase judgment, buy points, invalidation, and risk control.
---

# Elliott Wave Principle Skill

This skill helps you apply the Elliott Wave Principle to analyze financial market price data. It contains reference files with detailed rules, pattern descriptions, and guidelines.

## Quick Start

- If the user provides a chart or price data and asks for wave analysis, first determine the trend direction and look for the basic 5‑wave pattern (impulse) followed by a 3‑wave correction.
- If the user asks whether an A-share stock is in 主升浪/主升低吸, or provides only a stock code/chart screenshot for stage judgment, load `references/main-rise-low-buy-system.md` first, then use Elliott rules to map the structure to wave 1/2/3 or corrective alternatives.
- Use the reference files to verify rules and identify specific patterns.

## A股主升低吸核心规则

When the user provides an A-share stock code or chart and asks for 主升低吸 analysis, these rules are mandatory and take priority over loose Elliott labeling.

### Final Model

Use this as the highest-priority structure:

```text
0点 -> 最高/一高 -> 1点 -> 次高/二高 -> 2点 -> 主升段突破次高 -> 回踩操盘线买点
```

Mandatory relationships:

- `最高/一高 > 次高/二高`
- `2点 > 1点`
- Preferred confirmation: `主升段 > 次高/二高`

This is a head-and-shoulders / right-shoulder reversal model. `1点` and `2点` are shoulder lows; `次高/二高` is the confirmation high. The preferred buy is not at 二高; it appears after 2点 turns up, the 主升段 rises above 次高, and price pulls back to the operating line.

### Relabeling Rules

- `一高` uses closing price, not intraday highest price.
- `一高` must be confirmed by `二高`.
- `二高` cannot be higher than `一高`.
- If `二高 >= 一高`, relabel 二高 as the new 一高 and restart the count.
- If `二高 < 一高`, 一高 is confirmed and the accumulation stage can be considered complete.
- `1点` must be confirmed by `2点`.
- If `2点 <= 1点`, relabel 2点 as the new 1点 and wait for a fresh higher 2点.
- If price keeps breaking down after relabeling, mark the structure as failed.
- If `主升段 <= 次高`, treat it as a tracking setup, not a preferred buy.

### Buy Point Standard

The structure must be valid before looking for a buy. A valid buy requires:

- 2点 has turned upward or stabilized.
- Preferred: 主升段 after 2点 has risen above 次高/二高.
- Price pulls back to the operating line, touches it intraday, or stands back above it near the close.
- Buy candle is bullish, doji/cross-star, or a small controlled candle that holds the operating line.
- Late-session confirmation around 14:30-15:00 is preferred.

Do not buy when:

- The candle is a large bearish candle or consecutive bearish candles.
- Price cannot stand back above the operating line near the close.
- Price breaks 2点.
- Market or sector context is clearly weakening.

### Required Output For 主升低吸

When analyzing a stock, output:

1. Current stage: 建仓 / 洗盘 / 试盘 / 2点确认 / 主升段 / 回踩买点 / failed.
2. Key points: 0点, 最高/一高, 1点, 次高/二高, 2点, 主升段, current price.
3. Rule check: whether `最高 > 次高`, `2点 > 1点`, and `主升段 > 次高`.
4. Buy plan: 观察价, 2点确认价, 回踩操盘线买点, no-buy conditions.
5. Invalidation: 2点, operating line, 1点, and structure failure level.
6. Conclusion: confirmed / tracking / invalidated, with a probability-style score rather than certainty.

## Reference Files

The following files are available in the `references/` directory. Load them as needed based on the user’s question.

- **[basic-principles.md](references/basic-principles.md)** – Fundamental concepts: the 5‑3 wave structure, motive vs. corrective mode, wave degrees, labeling conventions.
- **[impulse-waves.md](references/impulse-waves.md)** – Rules for impulse waves (no overlap, wave 3 not shortest, etc.), extensions, truncations, diagonal triangles (ending and leading).
- **[corrective-patterns.md](references/corrective-patterns.md)** – Detailed descriptions of zigzags (single, double, triple), flats (regular, expanded, running), triangles (contracting, expanding), and combinations (double/triple threes).
- **[guidelines.md](references/guidelines.md)** – Key guidelines: alternation, channeling, volume characteristics, wave personality, and practical application tips.
- **[fibonacci-relationships.md](references/fibonacci-relationships.md)** – Fibonacci ratios in wave relationships (retracements, multiples, time sequences), how to apply them for price targets.
- **[glossary.md](references/glossary.md)** – Definitions of Elliott Wave terms (e.g., throw‑over, truncation, apex, etc.).
- **[main-rise-low-buy-system.md](references/main-rise-low-buy-system.md)** – A-share 主升低吸 framework distilled from confirmed main-rise chart samples and manuals: 0号点、一高、1低、二高、2低, phase scoring, buy triggers, invalidation, and risk control.

## How to Use This Skill

1. **Understand the user’s request**: Determine if they need wave counting, pattern identification, or explanation of concepts.
2. **Load relevant reference(s)**: For example, if the user asks about a specific corrective pattern, load `corrective-patterns.md`. If they ask about wave counting rules, load `impulse-waves.md` and `basic-principles.md`.
3. **For 主升低吸 requests**: Identify 0号启动点、最高/一高、1号低点、次高/二高、2号低点、主升段、买点; 一高以收盘价为准且要靠二高确认; final model requires 最高 > 次高 and 2点 > 1点; 二高不能高于一高, otherwise relabel 二高 as the new 一高; 2号点 must confirm 1号低点, otherwise relabel 2号点 as the new 1号低点 and wait for a fresh higher-low 2号点. Prefer setups where the 主升段 after 2号点 rises above 次高, then buy on the first valid operating-line pullback with bullish/doji candle.
4. **Apply the rules**: Use the information to analyze the provided price data. Remember that the Wave Principle and main-rise framework are probabilistic; multiple interpretations may be valid.
5. **Provide reasoning**: Explain the wave count or main-rise stage, key high/low points, buy conditions, invalidation levels, and risk controls.

## Important Notes

- Always prioritize the **rules** (e.g., wave 3 cannot be shortest, wave 4 cannot overlap wave 1 in an impulse) over guidelines.
- When in doubt, consult the glossary for term definitions.
- The examples in the reference files illustrate typical patterns; actual market patterns may vary.
- For a comprehensive understanding, you may load multiple references. The files are designed to be modular; load only what you need to keep context efficient.
- For stock-code or chart-based trading analysis, avoid presenting conclusions as certainty. Always distinguish "confirmed", "tracking", and "invalidated" structures, and include a clear invalidation level.
