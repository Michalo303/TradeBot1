# RobustTrendBreakout — Backtest Handoff

**Strategy version:** 1.0.0  
**Date:** 2026-05-05  
**Freqtrade INTERFACE_VERSION:** 3  
**Timeframe:** 1h + 4h informative  
**Exchange:** Binance spot, USDT pairs  
**Mode:** Long-only, no leverage  

## Concept

Donchian Channel breakout filtered by a dual-timeframe trend gate:

- **1h:** Price must be above EMA50 (fast, slope confirmed) and EMA200 (slow).
- **4h:** EMA200 slope must be positive AND 4h close must be above 4h EMA200.

Entry requires volume surge above a 20-bar baseline plus proximity to a rolling VWAP proxy (blocks pump-chases and deep-weakness buys). Exits are two-tiered: a soft 2-candle confirmation exit when price loses EMA50 + DC midline, and a hard exit when price falls below EMA200.

Risk management uses a custom ATR-based trailing stop clamped to a sensible price fraction, backed by static -9% stoploss fallback. Protections cap drawdown at ~8% and cool down after stoploss clusters.

**Goal:** Max drawdown 6–10%, stability across pairs and market regimes. Not optimised for maximum backtest profit.

---

## Parameter Reference

| Parameter | Default | Range | Hyperopt | Purpose |
|---|---|---|---|---|
| `dc_period` | 20 | 10–40 | buy | Donchian Channel lookback |
| `ema_fast_period` | 50 | 20–100 | buy | Fast EMA (trend + exit) |
| `ema_slow_period` | 200 | 100–300 | **off** | Slow EMA (hard filter + exit); canonical level, fixed |
| `ema_slope_bars` | 5 | 3–10 | buy | Bars over which EMA50 slope is measured |
| `ema_slope_min` | 0.0003 | 0.0001–0.001 | buy | Minimum fractional EMA50 slope to confirm uptrend |
| `atr_period` | 14 | 7–28 | sell | ATR lookback |
| `atr_sl_multiplier` | 2.2 | 1.5–3.5 | sell | ATR stop width; wider = more room, fewer triggers |
| `atr_min_pct` | 0.003 | 0.001–0.01 | **off** | Floor on ATR stop as fraction of price |
| `atr_max_pct` | 0.04 | 0.02–0.08 | **off** | Ceiling on ATR stop as fraction of price |
| `volume_sma_period` | 20 | 10–40 | buy | Volume baseline lookback |
| `volume_factor` | 1.3 | 1.0–2.5 | buy | Volume/SMA ratio required at entry |
| `volume_increasing` | True | bool | buy | Require volume > prior candle |
| `vwap_distance_min` | -0.01 | -0.05–0.0 | buy | Min distance below VWAP proxy (blocks deep-weakness buys) |
| `vwap_distance_max` | 0.05 | 0.01–0.15 | buy | Max distance above VWAP proxy (blocks pump-chases) |
| `use_stochrsi` | **False** | bool | buy | Enable StochRSI entry cap |
| `stochrsi_entry_max` | 90 | 60–90 | buy | Max StochRSI K at entry (only when enabled) |
| `use_fvg` | **False** | bool | **off** | Enable FVG confluence filter |
| `fvg_threshold` | 0.003 | 0.001–0.01 | **off** | Min FVG gap size as fraction of close |

**ROI (Variant B):** `{"0": 0.12, "720": 0.06, "1440": 0.03}` — lets trends run 30–60h before forcing a profit-take. Use `{"0": 100}` in hyperopt to let ATR trailing + exit signals fully control the trade.

**Trailing:** `trailing_stop_positive = 0.02`, `trailing_stop_positive_offset = 0.04` — protects profit without killing the trend too early.

---

## Dry-Run Config Fragment

Add to or override your `user_data/config/config.json`:

```json
{
  "strategy": "RobustTrendBreakout",
  "timeframe": "1h",
  "max_open_trades": 6,
  "stake_currency": "USDT",
  "stake_amount": "unlimited",
  "tradable_balance_ratio": 0.99,
  "dry_run": true,
  "dry_run_wallet": 1000,
  "trading_mode": "spot",
  "margin_mode": "",
  "exchange": {
    "name": "binance"
  },
  "pairlists": [
    {
      "method": "StaticPairList",
      "allow_inactive": false
    }
  ],
  "pair_whitelist": [
    "BTC/USDT", "ETH/USDT", "SOL/USDT",
    "BNB/USDT", "LINK/USDT", "AVAX/USDT"
  ],
  "order_types": {
    "entry": "limit",
    "exit": "limit",
    "emergency_exit": "limit",
    "force_entry": "limit",
    "force_exit": "limit",
    "stoploss": "limit",
    "stoploss_on_exchange": false
  },
  "unfilledtimeout": {
    "entry": 10,
    "exit": 10,
    "unit": "minutes"
  },
  "entry_pricing": {
    "price_side": "same",
    "use_order_book": false,
    "order_book_top": 1,
    "price_last_balance": 0.0,
    "check_depth_of_market": {
      "enabled": false,
      "bids_to_ask_depth": 20
    }
  },
  "exit_pricing": {
    "price_side": "same",
    "use_order_book": false,
    "order_book_top": 1
  }
}
```

For production dry-run replace `StaticPairList` with the project's `pairlist-relaxed-filters.json` pairlist.

---

## Data Download

Download 1h and 4h data for all target pairs before backtesting:

```bash
freqtrade download-data \
  --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT LINK/USDT AVAX/USDT \
  --timeframe 1h \
  --timeframe 4h \
  --timerange 20210101-20241231 \
  --config user_data/config/config.json
```

Or via Docker:

```bash
docker compose run --rm freqtrade download-data \
  --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT LINK/USDT AVAX/USDT \
  --timeframe 1h --timeframe 4h \
  --timerange 20210101-20241231 \
  --config user_data/config/config.json
```

---

## Backtest Commands

Run each market regime separately to test robustness. These 6 pairs cover different volatility profiles: BTC/ETH provide sideways/bear context; SOL/AVAX provide high-beta bull moves; LINK/BNB are mid-range.

```bash
BASE_CONFIG="--config user_data/config/config.json"
PAIRS="BTC/USDT ETH/USDT SOL/USDT BNB/USDT LINK/USDT AVAX/USDT"
STRATEGY="--strategy RobustTrendBreakout"

# Bull market — 2021
freqtrade backtesting $STRATEGY --timerange 20210101-20211231 \
  --pairs $PAIRS --timeframe 1h $BASE_CONFIG --export trades

# Bear market — 2022
freqtrade backtesting $STRATEGY --timerange 20220101-20221231 \
  --pairs $PAIRS --timeframe 1h $BASE_CONFIG --export trades

# Sideways / recovery — 2023
freqtrade backtesting $STRATEGY --timerange 20230101-20231231 \
  --pairs $PAIRS --timeframe 1h $BASE_CONFIG --export trades

# Out-of-sample — 2024 (do not touch until ready to validate)
freqtrade backtesting $STRATEGY --timerange 20240101-20241231 \
  --pairs $PAIRS --timeframe 1h $BASE_CONFIG --export trades

# Broad static pairlist robustness check (2023–2024)
freqtrade backtesting $STRATEGY --timerange 20230101-20241231 \
  --config user_data/config/pairlist-backtest-static-binance-spot-usdt.json \
  --timeframe 1h $BASE_CONFIG --export trades
```

**Sanity check (1 month, runs in seconds):**

```bash
freqtrade backtesting --strategy RobustTrendBreakout \
  --timerange 20230101-20230201 \
  --pairs BTC/USDT ETH/USDT \
  --timeframe 1h --config user_data/config/config.json
```

---

## Hyperopt Commands

Use `CalmarHyperOptLoss` — it maximises annual return / max drawdown (Calmar ratio), directly matching the low-drawdown goal. Do **not** use `SharpeHyperOptLoss` (rewards smooth small gains, not our objective) or `MaxDrawDownHyperOptLoss` (too aggressive, can produce no-trade solutions).

Optimise buy-side (trend filters, volume, VWAP) and sell-side (ATR stop) separately to keep the search space manageable.

```bash
# Buy-side: optimise on bear + recovery period (difficult conditions)
freqtrade hyperopt \
  --strategy RobustTrendBreakout \
  --hyperopt-loss CalmarHyperOptLoss \
  --spaces buy \
  --timerange 20220101-20231231 \
  --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT LINK/USDT AVAX/USDT \
  --epochs 300 \
  --jobs -1 \
  --config user_data/config/config.json

# Sell-side: ATR multiplier and period
freqtrade hyperopt \
  --strategy RobustTrendBreakout \
  --hyperopt-loss CalmarHyperOptLoss \
  --spaces sell \
  --timerange 20220101-20231231 \
  --pairs BTC/USDT ETH/USDT SOL/USDT BNB/USDT LINK/USDT AVAX/USDT \
  --epochs 150 \
  --jobs -1 \
  --config user_data/config/config.json
```

**After hyperopt:** Always validate the found parameters on the **out-of-sample 2024** period before considering them for live trading.

---

## Key Metrics to Evaluate

Primary (in priority order for this strategy):

| Metric | Target | Hard Stop |
|---|---|---|
| Max drawdown | < 10% | > 15% → reject |
| Calmar ratio | > 1.0 | < 0.5 → reject |
| Profit factor | > 1.3 | < 1.0 → reject |
| Trade count (per year) | > 30 | < 20 → insufficient evidence |
| Win rate | > 50% | — (lower is ok if avg win/loss > 2.0) |
| Avg win / avg loss | > 1.5 | < 1.0 → reject |
| Avg trade duration | 4–48h | < 1h or > 96h → investigate |

Secondary (reported, not optimised):

- Sharpe ratio
- Recovery factor (total profit / max drawdown)
- Max consecutive losses
- Percent profitable candles / days
- Market exposure %

**Cross-pair check:** No single pair should account for more than 40% of total profit. If it does, the strategy is not robust — it relies on one pair's bull run.

---

## Overfitting Warning Signs

Stop and re-evaluate if you see any of these:

- **Extreme bull performance only** — 2021 Calmar > 10, but 2022 Calmar < 0.5. The strategy has found 2021's noise, not a signal.
- **Win rate > 75%** in backtest — almost always overfit in a trend-following strategy.
- **Trade count < 20 per year** — statistical noise. No parameter set is valid.
- **Hyperopt improvement > 50% over defaults** — large gaps from defaults suggest the found parameters are specific to the training window.
- **`ema_slow_period` converges to extremes** (< 150 or = 300) — discard result; it means 200 is not the right level for this data *window* (not the market).
- **`dc_period` converges to 10 (minimum)** — strategy is becoming a noise-reactive system, not a breakout system.
- **Wildly different optimal parameters across time windows** — instability = overfit. A robust strategy should have similar optimal ranges in bull and bear.
- **Good 4-pair result, bad on 2 pairs** — probably overfit to 4 specific price histories.

---

## Pre-Live Deployment Checklist

### Backtest thresholds

- [ ] Strategy file imports without errors: `freqtrade list-strategies --strategy-path user_data/strategies/`
- [ ] Bear-period (2022) max drawdown < 15%
- [ ] Bear-period profit factor > 1.0 (strategy must not net-lose in bear)
- [ ] Bull-period profit factor > 1.5
- [ ] At least 50 closed trades across all periods combined
- [ ] No single pair > 40% of total profit
- [ ] Average trade duration between 2h and 72h
- [ ] Out-of-sample (2024) results are broadly consistent with in-sample (not >2× worse)

### Code checks

- [ ] `INTERFACE_VERSION = 3` is set
- [ ] `use_custom_stoploss = True` is set
- [ ] `startup_candle_count = 400` is set (covers max EMA slow range + buffer)
- [ ] `can_short = False` is set
- [ ] All entry signals have `enter_tag`; all exit signals have `exit_tag`
- [ ] No `qtpylib` import (unused in this strategy)
- [ ] No future candle references (no `.shift(-n)` in indicator logic)

### Dry-run (minimum 14 days)

- [ ] Win rate > 50%
- [ ] Max drawdown < 10%
- [ ] At least 15 closed trades
- [ ] No persistent OHLCV data errors in logs
- [ ] Dry-run results broadly consistent with backtest (same regime)
- [ ] Telegram notifications working

### Before live

- [ ] Binance API key configured (spot-only, no withdrawal permissions)
- [ ] `dry_run: false` set intentionally (not accidentally)
- [ ] Position size reviewed: `stake_amount = "unlimited"` + `tradable_balance_ratio = 0.99` with `max_open_trades = 6` means each trade is ~1/6 of wallet
- [ ] `stoploss_on_exchange: false` confirmed (bot manages stops)
- [ ] All items in `docs/live-trading-checklist.md` passed

---

## Notes on Market Regimes

**Bull (2021-style):** Expect high win rate, strong profit factor, potential drawdown from late-trend entries. Monitor `vwap_distance_max` — pump-chase filter. Calmar > 3 is suspicious; > 5 is likely overfit.

**Bear (2022-style):** Donchian breakouts will trigger on dead-cat bounces. The 4h trend gate (EMA200 slope + price above EMA200) is the main defence. Expect profit factor 0.9–1.3 at best. If profit factor < 0.8 in bear, tighten entry filters or accept the strategy as bull-only.

**Sideways (2023-style):** Most trades will be stopped out. Low trade count expected. The `LowProfitPairs` protection will suppress bad pairs. Focus on drawdown, not profit.
