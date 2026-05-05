# TradeBot1

Freqtrade dry-run setup for Binance Spot using the `NostalgiaForInfinityX7` strategy.

The project is currently configured for paper trading only. Do not switch to live trading before completing the checklist in `docs/live-trading-checklist.md`.

## What Is Included

- Docker Compose service for `freqtradeorg/freqtrade:2024.5`
- Dry-run Freqtrade configuration
- NFI X7 strategy file
- Binance blacklist and static pairlists
- Live-trading readiness checklist
- Example private configuration template

## What Is Not Committed

The following files are intentionally ignored:

- `AGENTS.md`
- `.env`
- `user_data/config/config.private.json`
- market data under `user_data/data/`
- logs under `user_data/logs/`
- SQLite runtime databases
- backtest result artefacts

## Basic Commands

Start or update the bot:

```bash
docker compose up -d --force-recreate
```

Check status:

```bash
docker ps
docker logs freqtrade-nfi-dryrun --tail 100
```

Stop the bot:

```bash
docker compose stop
```

Run repository checks:

```bash
python scripts/check_repo_safety.py
python -m unittest discover -s tests -v
```

Generate a risk-score report from a Freqtrade backtest JSON:

```bash
python scripts/score_backtests.py user_data/backtest_results/backtest-result-YYYY-MM-DD_HH-MM-SS.json --output-dir reports
```

## Live Trading

Live trading is intentionally disabled by default:

```json
"dry_run": true
```

Before enabling live trading, complete every item in `docs/live-trading-checklist.md`, create Binance API keys without withdrawal permissions, and store credentials only in `user_data/config/config.private.json`.
