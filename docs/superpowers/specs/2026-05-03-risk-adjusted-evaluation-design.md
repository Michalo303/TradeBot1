# Risk-Adjusted Evaluation Layer Design

## Goal

Improve TradeBot1 decision quality without changing `NostalgiaForInfinityX7` strategy logic.

The project currently has too little evidence to tune for profit safely:

- live dry-run has no closed trades yet
- the latest local 60-day backtest produced only 2 trades
- the strategy file is large external strategy code, so direct edits have high overfitting and regression risk

The evaluation layer will compare configuration and pairlist variants using risk-adjusted metrics, then recommend the next dry-run configuration.

## Non-Goals

- Do not enable live trading.
- Do not modify `NostalgiaForInfinityX7.py`.
- Do not optimize parameters from a small sample.
- Do not copy trading logic from forked repositories.
- Do not use private credentials or runtime databases in GitHub.

## Inputs

The evaluation will use existing public project files:

- `user_data/config/config.json`
- `user_data/config/blacklist-binance.json`
- `user_data/config/config.private.json.example`
- existing or generated static pairlist JSON files
- Freqtrade backtest JSON outputs

Private runtime files stay ignored:

- `AGENTS.md`
- `user_data/config/config.private.json`
- `user_data/tradesv3.sqlite*`
- market data under `user_data/data/`
- logs under `user_data/logs/`

## Pairlist Variants

The first implementation should support these variants:

1. `current_dynamic`
   - Uses the current `VolumePairList` configuration.
   - Represents the live dry-run behavior.

2. `conservative_static`
   - Uses liquid, established USDT pairs only.
   - Excludes known blacklist symbols, fan tokens, stable pairs, delisting-risk pairs, and pairs that recently caused OHLCV issues.

3. `expanded_static`
   - Uses a broader static whitelist after blacklist filtering.
   - Intended to test whether more eligible pairs improve trade count without unacceptable drawdown.

4. `current_backtest_static`
   - Uses the existing local static pairlist as a baseline.
   - Keeps continuity with prior backtest results.

## Timeranges

Backtests should be evaluated across multiple windows when data is available:

- short: 60 days
- medium: 180 days
- robust: 365 days or more

If a timerange has insufficient warmup data for NFI informative timeframes, the report must mark it as incomplete instead of treating it as valid evidence.

## Scoring

Each completed backtest receives a score from 0 to 100. The score is not a profit guarantee; it is a ranking aid.

Recommended initial weights:

- Profit factor: positive weight
- Max drawdown: strong negative weight
- Trade count: strong penalty below 30 closed trades
- Win rate: moderate positive weight
- Average trade duration: penalty for extreme holding times
- Daily consistency: positive weight for distributed gains, penalty for results driven by a few outlier days
- Log quality: hard penalty for OHLCV, pairlist, traceback, or analysis errors

The score must include a confidence label:

- `LOW`: fewer than 30 closed trades or incomplete timerange
- `MEDIUM`: 30-99 closed trades
- `HIGH`: 100+ closed trades across multiple windows

## Outputs

The evaluation should produce both machine-readable and human-readable outputs:

- `reports/risk-score-YYYY-MM-DD.json`
- `reports/risk-score-YYYY-MM-DD.md`

The Markdown report should include:

- tested config and pairlist variants
- timeranges
- key metrics per variant
- risk score per variant
- confidence label
- known limitations
- recommended next action

The recommended next action must be one of:

- `KEEP_CURRENT`
- `EXPAND_PAIRLIST`
- `TIGHTEN_PAIRLIST`
- `COLLECT_MORE_DATA`
- `DO_NOT_CHANGE_YET`

## Safety Rules

- Public default config must keep `"dry_run": true`.
- Web UI must remain bound to `127.0.0.1:8080:8080`.
- No report may recommend live trading unless the existing live checklist is complete.
- If closed trades are below 30, the report must prefer `COLLECT_MORE_DATA` or explicitly mark the recommendation as low confidence.
- Pairlist changes require backtest evidence and a follow-up dry-run observation period.
- Strategy logic changes require a separate design and approval.

## Repository Integration

The implementation should add small, auditable scripts rather than a large framework.

Suggested files:

- `scripts/run_backtest_matrix.py`
- `scripts/score_backtests.py`
- `reports/README.md`
- generated reports under `reports/`

Generated reports may be committed only if they do not contain secrets and are small enough to review. Large raw backtest artifacts remain ignored under `user_data/backtest_results/`.

## Validation

Before accepting the feature:

1. `python scripts/check_repo_safety.py` passes.
2. Scoring script can parse the existing local backtest JSON.
3. A low-sample backtest receives a `LOW` confidence label.
4. Reports clearly state that results are not a live trading recommendation.
5. No ignored runtime artifacts are tracked.

## Initial Recommendation

The current evidence does not justify strategy tuning. The next engineering step is to build scoring and reporting first, then run a backtest matrix once sufficient data is available.
