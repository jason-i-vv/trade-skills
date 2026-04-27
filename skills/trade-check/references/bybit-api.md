# Bybit Public API Reference

No API key required for read-only market data.

## Base URL
```
https://api.bybit.com
```

## Key Endpoints

### K线 / Klines
```bash
curl "https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=4H&limit=200"
```
- `category`: `spot` | `linear` | `inverse`
- `symbol`: e.g. `BTCUSDT`, `ETHUSDT`
- `interval`: `1` `3` `5` `15` `30` `60` `120` `240` `300` `900` `1800` `3600` `7200` `D` `W` `M`
- `limit`: max 200

### 行情 Tick / Tickers
```bash
curl "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT"
```
Returns: last price, volume, bid/ask, etc.

### 订单簿 Orderbook
```bash
curl "https://api.bybit.com/v5/market/orderbook?category=spot&symbol=BTCUSDT&limit=50"
```

### 交易历史 Recent Trades
```bash
curl "https://api.bybit.com/v5/market/recent-trade?category=spot&symbol=BTCUSDT&limit=50"
```

## Symbol Naming
- Spot: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`
- Linear (USDT perpetuals): `BTCUSDT.P` (use `linear` category)
- Inverse: `BTCUSD` (use `inverse` category)

## Notes
- Use `linear` category for USDT-margined perpetuals
- All spot symbols use `spot` category
- Timestamps are in milliseconds (ms)
