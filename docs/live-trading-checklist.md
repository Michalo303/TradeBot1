# Live Trading Checklist

Complete ALL items below before switching `dry_run` to `false`.

## 14-Day Dry-Run Review Criteria

- [ ] Win rate > 55%
- [ ] Profit factor > 1.2
- [ ] Max drawdown < 15%
- [ ] Average trade duration < 24h (or confirmed intentional by logs)
- [ ] No persistent OHLCV or informative timeframe errors in logs
- [ ] No pairlist failures
- [ ] At least 30 closed trades for statistical validity
- [ ] Profitable days >= 10 of 14
- [ ] Resource usage stable (CPU, RAM)

**If too few trades (< 20 in 14 days):** Increase `number_assets` from 30 to 50 in `config.json` pairlist, re-run dry-run for another 14 days before evaluating. Do NOT change strategy logic in the first review cycle.

---

## Binance API Key Creation (Step-by-Step)

1. Go to https://www.binance.com → Log in
2. Profile icon (top right) → **API Management**
3. **Create API** → select **System generated**
4. Name: `freqtrade-spot-live`
5. Complete 2FA verification
6. In API key settings:
   - ✅ Enable **Reading**
   - ✅ Enable **Spot & Margin Trading**
   - ❌ **Disable Withdrawals** (critical — never enable on a bot key)
   - Optionally set **IP restriction** to your home/server IP
7. Copy **API Key** and **Secret Key** — secret shown only once
8. Store ONLY in `user_data/config/config.private.json` (gitignored)

---

## Live Config Changes

In `user_data/config/config.json`:
```json
"dry_run": false,
"tradable_balance_ratio": 0.50
```
Start with 0.50 ratio. Increase to 0.99 only after first profitable week.

In `user_data/config/config.private.json` — add exchange section:
```json
"exchange": {
  "key": "YOUR_BINANCE_API_KEY",
  "secret": "YOUR_BINANCE_API_SECRET"
}
```

---

## Pre-Live Checklist

- [ ] 14-day dry-run metrics reviewed (see criteria above)
- [ ] Backtest re-run on last 30 days with current pairlist
- [ ] Binance API key created with spot-only + no-withdrawals
- [ ] API keys stored in config.private.json (NOT in git)
- [ ] Telegram notifications confirmed working
- [ ] Web UI přístupné přes SSH tunnel (`ssh -L 8080:localhost:8080 root@91.99.99.158`) → http://localhost:8080
- [ ] Emergency stop documented: `docker compose stop freqtrade`
- [ ] Calendar reminder set for 7-day live review

---

## Backtest Baseline (fill after Task 10)

| Metric | Backtest Result |
|--------|----------------|
| Total trades | |
| Win rate | |
| Profit factor | |
| Max drawdown | |
| Avg trade duration | |
